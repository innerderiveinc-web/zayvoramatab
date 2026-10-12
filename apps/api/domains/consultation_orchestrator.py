"""Unified Consultation Workspace & Clinical Workflow Orchestrator Domain Service.
Phase 8: Multi-lane consultation orchestration, server-authoritative state machine,
section completion tracking, safety firewall gating, and atomic electronic finalization.
"""

import json
import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    NotFoundError,
    ValidationError,
    ConflictError,
    ForbiddenError,
    AuthenticationError,
    SafetyBlockedError
)
from apps.api.core.security import verify_pin, calculate_prescription_hash
from apps.api.core.audit import log_audit_event
from apps.api.domains.patients import PatientService
from apps.api.domains.encounters import EncounterService
from apps.api.domains.prescriptions import PrescriptionService
from apps.api.domains.safety_firewall import SafetyFirewallEngine

SECTION_KEYS = [
    "visit",
    "history_observations",
    "unani_assessment",
    "modern_assessment",
    "plan_nuskha",
    "safety_review",
    "finalize"
]

SECTION_STATUSES = [
    "not_started",
    "in_progress",
    "complete",
    "not_applicable",
    "needs_review"
]

# Canonical orchestrator lifecycle states
WORKFLOW_STATES = [
    "scheduled",
    "checked_in",
    "in_consultation",
    "draft",
    "pending_review",
    "safety_review_required",
    "ready_for_signoff",
    "signed",
    "completed",
    "cancelled",
    "entered_in_error"
]

ALLOWED_ORCHESTRATOR_TRANSITIONS: Dict[str, List[str]] = {
    # Initial & intake
    "scheduled": ["checked_in", "cancelled"],
    "checked_in": ["in_consultation", "draft", "cancelled"],
    
    # Active consultation & draft
    "in_consultation": ["draft", "pending_review", "safety_review_required", "ready_for_signoff", "cancelled"],
    "draft": ["in_consultation", "pending_review", "safety_review_required", "ready_for_signoff", "cancelled"],
    "DRAFT": ["in_consultation", "draft", "pending_review", "safety_review_required", "ready_for_signoff", "cancelled"],
    "IN_PROGRESS": ["in_consultation", "draft", "pending_review", "safety_review_required", "ready_for_signoff", "completed", "cancelled"],
    
    # Review & safety gates
    "pending_review": ["safety_review_required", "ready_for_signoff", "in_consultation", "draft", "cancelled"],
    "safety_review_required": ["ready_for_signoff", "in_consultation", "draft", "cancelled"],
    "ready_for_signoff": ["signed", "completed", "in_consultation", "draft", "safety_review_required", "cancelled"],
    
    # Finalization & terminal
    "signed": ["completed", "entered_in_error"],
    "completed": ["entered_in_error"],
    "COMPLETED": ["entered_in_error"],
    "cancelled": [],
    "CANCELLED": [],
    "entered_in_error": []
}


class ConsultationOrchestratorService:
    """Core domain service orchestrating the multi-lane consultation workspace."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)
        self.safety_firewall = SafetyFirewallEngine(db_path)

    # --------------------------------------------------------------------------
    # 1. WORKSPACE AGGREGATE
    # --------------------------------------------------------------------------

    def get_workspace(self, encounter_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch the complete unified consultation workspace aggregate for an encounter.
        Aggregates:
        - Encounter metadata and workflow state
        - Patient 360 overview (allergies, conditions, demographics)
        - Section states (7 guided sections)
        - Draft data across clinical lanes (Visit, History/Vitals, Unani, Modern, Plan/Nuskha, Safety)
        - Server-authoritative sign-off eligibility calculation
        - Document bundles and follow-up tasks
        """
        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            encounter = EncounterService.get_encounter_by_id(conn, org_id, encounter_id)
            patient_id = encounter["patient_id"]

            # 1. Patient Demographics & Profile
            cur = conn.cursor()
            cur.execute("""
                SELECT p.id, p.mrn, p.display_name, p.given_name, p.family_name,
                       p.date_of_birth, p.estimated_age, p.sex, p.preferred_language,
                       p.status, p.created_at
                FROM patients p
                WHERE p.id = ? AND p.organization_id = ?;
            """, (patient_id, org_id))
            patient_row = cur.fetchone()
            if not patient_row:
                raise NotFoundError(f"Patient '{patient_id}' not found.")
            patient_data = dict(patient_row)

            # Patient Allergies (from consents or findings)
            cur.execute("""
                SELECT identifier_type, identifier_value, normalized_value
                FROM patient_identifiers
                WHERE patient_id = ? AND is_retired = 0;
            """, (patient_id,))
            patient_data["identifiers"] = [dict(r) for r in cur.fetchall()]

            # 2. Section States
            cur.execute("""
                SELECT section_key, status, completion_metadata_json, version_number,
                       updated_by, updated_at
                FROM encounter_section_states
                WHERE encounter_id = ?;
            """, (encounter_id,))
            existing_sections = {r["section_key"]: dict(r) for r in cur.fetchall()}

            sections_map = {}
            for key in SECTION_KEYS:
                if key in existing_sections:
                    sec = existing_sections[key]
                    sec["completion_metadata"] = json.loads(sec["completion_metadata_json"]) if sec.get("completion_metadata_json") else {}
                    sections_map[key] = sec
                else:
                    sections_map[key] = {
                        "section_key": key,
                        "status": "not_started",
                        "completion_metadata": {},
                        "version_number": 1,
                        "updated_by": None,
                        "updated_at": None
                    }

            # 3. Draft Lane Data:
            # A. Visit Lane
            visit_data = {
                "encounter_type": encounter.get("encounter_type", "OPD_VISIT"),
                "reason_for_visit": encounter.get("reason_for_visit", ""),
                "token_number": encounter.get("token_number"),
                "started_at": encounter.get("started_at"),
                "facility_name": encounter.get("facility_name"),
                "practitioner_name": encounter.get("practitioner_name")
            }

            # B. History & Observations (Modern Assessment observations / vitals)
            cur.execute("""
                SELECT id, status, chief_complaint, history_of_present_illness,
                       working_assessment, clinical_rationale, physical_examination_json,
                       review_of_systems_json
                FROM modern_clinical_assessments
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            modern_row = cur.fetchone()
            modern_data = dict(modern_row) if modern_row else None

            # C. Unani Assessment Lane
            cur.execute("""
                SELECT id, status, dominant_mizaj as primary_mizaj, secondary_mizaj,
                       mizaj_rationale, clinical_reasoning
                FROM unani_assessments
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            unani_row = cur.fetchone()
            unani_data = dict(unani_row) if unani_row else None

            # D. Care Plan (Usul-e-Ilaj) Lane
            cur.execute("""
                SELECT id, title, overall_goal, clinical_rationale, status
                FROM care_plans
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            care_plan_row = cur.fetchone()
            care_plan_data = dict(care_plan_row) if care_plan_row else None

            # E. Prescription / Nuskha Lane
            cur.execute("""
                SELECT id, prescription_number, status, overall_safety_state,
                       version_number, signed_at, signed_by
                FROM prescriptions
                WHERE encounter_id = ? AND organization_id = ? AND status != 'CANCELLED'
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            rx_row = cur.fetchone()
            rx_data = None
            if rx_row:
                rx_data = dict(rx_row)
                cur.execute("""
                    SELECT id, item_name, dosage_form, dose_amount, dose_unit,
                           route, frequency, duration_days, instructions, anupan_vehicle,
                           formulation_id, sort_order
                    FROM prescription_items
                    WHERE prescription_id = ?
                    ORDER BY sort_order ASC, id ASC;
                """, (rx_data["id"],))
                rx_data["items"] = [dict(it) for it in cur.fetchall()]

            # F. Safety Preflight Lane (Latest Run)
            cur.execute("""
                SELECT id, overall_status, ruleset_version, coverage_report_json,
                       clinician_id, executed_at
                FROM safety_preflight_runs
                WHERE encounter_id = ? AND organization_id = ? AND is_latest = 1
                ORDER BY executed_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            preflight_row = cur.fetchone()
            preflight_data = None
            if preflight_row:
                preflight_data = dict(preflight_row)
                preflight_data["coverage_report"] = json.loads(preflight_data["coverage_report_json"]) if preflight_data.get("coverage_report_json") else {}
                cur.execute("""
                    SELECT f.*,
                           d.disposition_type, d.clinical_rationale, d.created_at as disposition_at
                    FROM safety_findings f
                    LEFT JOIN safety_finding_dispositions d ON f.id = d.finding_id
                    WHERE f.run_id = ?
                    ORDER BY f.severity DESC, f.created_at ASC;
                """, (preflight_data["id"],))
                preflight_data["findings"] = [dict(f) for f in cur.fetchall()]

            # 4. Generated Documents
            cur.execute("""
                SELECT id, document_type, version_number, document_hash,
                       generated_by, created_at
                FROM encounter_documents
                WHERE encounter_id = ?
                ORDER BY created_at ASC;
            """, (encounter_id,))
            documents = [dict(doc) for doc in cur.fetchall()]

            # 5. Follow-up Tasks
            cur.execute("""
                SELECT id, patient_id, due_date, task_description, status,
                       created_by, created_at
                FROM encounter_followup_tasks
                WHERE encounter_id = ?
                ORDER BY due_date ASC;
            """, (encounter_id,))
            followup_tasks = [dict(t) for t in cur.fetchall()]

            # 6. State Transitions Audit Trail
            cur.execute("""
                SELECT id, from_state, to_state, actor_id, reason, transitioned_at
                FROM encounter_state_transitions
                WHERE encounter_id = ?
                ORDER BY transitioned_at ASC;
            """, (encounter_id,))
            transitions_history = [dict(t) for t in cur.fetchall()]

            # 7. Server-Authoritative Sign-off Eligibility Gate
            eligibility = self._compute_signoff_eligibility(
                conn=conn,
                encounter=encounter,
                sections=sections_map,
                rx_data=rx_data,
                preflight_data=preflight_data,
                user_ctx=user_ctx
            )

            return {
                "encounter": encounter,
                "patient": patient_data,
                "sections": sections_map,
                "draft_lanes": {
                    "visit": visit_data,
                    "history_observations": modern_data,
                    "unani_assessment": unani_data,
                    "care_plan": care_plan_data,
                    "prescription": rx_data,
                    "safety_preflight": preflight_data
                },
                "signoff_eligibility": eligibility,
                "documents": documents,
                "followup_tasks": followup_tasks,
                "transitions_history": transitions_history
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. AUTOSAVE & DRAFT SYNCHRONIZATION
    # --------------------------------------------------------------------------

    def save_workspace_draft(self, encounter_id: str, payload: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Debounced server-side draft synchronization with optimistic concurrency control.
        Safely patches in-progress draft details across sections.
        """
        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            user_id = user_ctx["user_id"]
            encounter = EncounterService.get_encounter_by_id(conn, org_id, encounter_id)

            if encounter["status"] in ["COMPLETED", "completed", "CANCELLED", "cancelled", "ENTERED_IN_ERROR", "entered_in_error"]:
                raise ConflictError(f"Cannot edit encounter in terminal state '{encounter['status']}'.")

            # Check optimistic concurrency
            client_version = payload.get("version") or payload.get("version_number")
            if client_version is not None and client_version != encounter["version"]:
                raise ConflictError(
                    "Encounter was modified concurrently by another session. Please reload.",
                    details={"server_version": encounter["version"], "client_version": client_version}
                )

            # Update base visit details if provided
            reason_for_visit = payload.get("reason_for_visit")
            encounter_type = payload.get("encounter_type")
            new_version = encounter["version"] + 1

            if reason_for_visit is not None or encounter_type is not None:
                conn.execute("""
                    UPDATE encounters
                    SET reason_for_visit = COALESCE(?, reason_for_visit),
                        encounter_type = COALESCE(?, encounter_type),
                        version = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND organization_id = ?;
                """, (reason_for_visit, encounter_type, new_version, encounter_id, org_id))

            # Mark updated sections as in_progress if currently not_started
            updated_sections = payload.get("updated_sections") or []
            for sec_key in updated_sections:
                if sec_key in SECTION_KEYS:
                    self._ensure_section_state(
                        conn=conn,
                        encounter_id=encounter_id,
                        section_key=sec_key,
                        status="in_progress",
                        user_id=user_id,
                        metadata={"autosaved_at": datetime.utcnow().isoformat()}
                    )

            conn.commit()

            return {
                "status": "saved",
                "version_number": new_version,
                "saved_at": datetime.utcnow().isoformat()
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. SECTION COMPLETION & STATE MACHINE ORCHESTRATION
    # --------------------------------------------------------------------------

    def update_section_state(
        self,
        encounter_id: str,
        section_key: str,
        status: str,
        metadata: Optional[Dict[str, Any]],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update the completion state of a guided consultation section.
        Validates statuses and mandatory clinical rationale for 'not_applicable'.
        """
        if section_key not in SECTION_KEYS:
            raise ValidationError(f"Invalid section_key '{section_key}'. Allowed: {', '.join(SECTION_KEYS)}")

        if status not in SECTION_STATUSES:
            raise ValidationError(f"Invalid status '{status}'. Allowed: {', '.join(SECTION_STATUSES)}")

        metadata = metadata or {}
        if status == "not_applicable" and not (metadata.get("reason") or metadata.get("clinical_rationale")):
            raise ValidationError(f"A documented clinical rationale is required when marking section '{section_key}' as not applicable.")

        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            user_id = user_ctx["user_id"]
            encounter = EncounterService.get_encounter_by_id(conn, org_id, encounter_id)

            if encounter["status"] in ["COMPLETED", "completed", "CANCELLED", "cancelled", "ENTERED_IN_ERROR", "entered_in_error"]:
                raise ConflictError(f"Cannot update sections on an encounter in terminal state '{encounter['status']}'.")

            updated = self._ensure_section_state(
                conn=conn,
                encounter_id=encounter_id,
                section_key=section_key,
                status=status,
                user_id=user_id,
                metadata=metadata
            )
            conn.commit()

            return updated
        finally:
            conn.close()

    def _ensure_section_state(
        self,
        conn: sqlite3.Connection,
        encounter_id: str,
        section_key: str,
        status: str,
        user_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, version_number, status
            FROM encounter_section_states
            WHERE encounter_id = ? AND section_key = ?;
        """, (encounter_id, section_key))
        row = cur.fetchone()

        meta_json = json.dumps(metadata)
        if row:
            new_ver = row["version_number"] + 1
            sec_id = row["id"]
            conn.execute("""
                UPDATE encounter_section_states
                SET status = ?, completion_metadata_json = ?, version_number = ?,
                    updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (status, meta_json, new_ver, user_id, sec_id))
        else:
            sec_id = f"sec-{uuid.uuid4().hex[:12]}"
            new_ver = 1
            conn.execute("""
                INSERT INTO encounter_section_states (
                    id, encounter_id, section_key, status, completion_metadata_json,
                    version_number, updated_by
                ) VALUES (?, ?, ?, ?, ?, 1, ?);
            """, (sec_id, encounter_id, section_key, status, meta_json, user_id))

        return {
            "id": sec_id,
            "section_key": section_key,
            "status": status,
            "completion_metadata": metadata,
            "version_number": new_ver,
            "updated_by": user_id
        }

    def transition_encounter_state(
        self,
        encounter_id: str,
        target_state: str,
        user_ctx: Dict[str, Any],
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transition encounter workflow state through the server-authoritative state machine.
        Validates transition graph and records immutable transition audit.
        """
        target_norm = target_state.strip().lower()
        if target_norm not in [s.lower() for s in WORKFLOW_STATES]:
            raise ValidationError(f"Invalid target state '{target_state}'. Allowed: {', '.join(WORKFLOW_STATES)}")

        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            user_id = user_ctx["user_id"]
            encounter = EncounterService.get_encounter_by_id(conn, org_id, encounter_id)
            current_state = encounter["status"]

            # Validate transition graph
            allowed_next = ALLOWED_ORCHESTRATOR_TRANSITIONS.get(current_state)
            if allowed_next is None:
                allowed_next = ALLOWED_ORCHESTRATOR_TRANSITIONS.get(current_state.lower(), [])

            normalized_allowed = [s.lower() for s in allowed_next]
            if target_norm not in normalized_allowed:
                raise ValidationError(
                    f"Invalid workflow state transition from '{current_state}' to '{target_state}'. Allowed next states: {', '.join(allowed_next) or 'None'}.",
                    details={"current_state": current_state, "target_state": target_state}
                )

            new_ver = encounter["version"] + 1
            ended_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S") if target_norm in ["completed", "cancelled", "entered_in_error"] else None

            # Update encounter
            conn.execute("""
                UPDATE encounters
                SET status = ?, version = ?, ended_at = COALESCE(?, ended_at),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
            """, (target_norm, new_ver, ended_at, encounter_id, org_id))

            # Record transition audit
            trans_id = f"trans-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO encounter_state_transitions (
                    id, encounter_id, from_state, to_state, actor_id, reason
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (trans_id, encounter_id, current_state, target_norm, user_id, reason))

            log_audit_event(
                conn=conn,
                action_type="ENCOUNTER_STATE_TRANSITIONED",
                target_entity_type="ENCOUNTER",
                target_entity_id=encounter_id,
                organization_id=org_id,
                facility_id=encounter["facility_id"],
                actor_id=user_id,
                outcome="SUCCESS",
                details={"from_state": current_state, "to_state": target_norm, "reason": reason}
            )

            conn.commit()

            return {
                "encounter_id": encounter_id,
                "previous_state": current_state,
                "new_state": target_norm,
                "version_number": new_ver,
                "transition_id": trans_id
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. SERVER-AUTHORITATIVE SIGN-OFF ELIGIBILITY GATE
    # --------------------------------------------------------------------------

    def validate_signoff_eligibility(self, encounter_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Public endpoint to test sign-off readiness."""
        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            encounter = EncounterService.get_encounter_by_id(conn, org_id, encounter_id)

            cur = conn.cursor()
            cur.execute("""
                SELECT section_key, status, completion_metadata_json
                FROM encounter_section_states
                WHERE encounter_id = ?;
            """, (encounter_id,))
            sections_map = {r["section_key"]: dict(r) for r in cur.fetchall()}

            # Prescription
            cur.execute("""
                SELECT id, status, version_number
                FROM prescriptions
                WHERE encounter_id = ? AND organization_id = ? AND status != 'CANCELLED'
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            rx_row = cur.fetchone()
            rx_data = None
            if rx_row:
                rx_data = dict(rx_row)
                cur.execute("SELECT count(*) as cnt FROM prescription_items WHERE prescription_id = ?;", (rx_data["id"],))
                rx_data["items_count"] = cur.fetchone()["cnt"]

            # Safety Preflight
            cur.execute("""
                SELECT id, overall_status, is_latest
                FROM safety_preflight_runs
                WHERE encounter_id = ? AND organization_id = ? AND is_latest = 1
                ORDER BY executed_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            preflight_row = cur.fetchone()
            preflight_data = None
            if preflight_row:
                preflight_data = dict(preflight_row)
                cur.execute("""
                    SELECT f.*, d.disposition_type, d.clinical_rationale
                    FROM safety_findings f
                    LEFT JOIN safety_finding_dispositions d ON f.id = d.finding_id
                    WHERE f.run_id = ?;
                """, (preflight_data["id"],))
                preflight_data["findings"] = [dict(f) for f in cur.fetchall()]

            return self._compute_signoff_eligibility(
                conn=conn,
                encounter=encounter,
                sections=sections_map,
                rx_data=rx_data,
                preflight_data=preflight_data,
                user_ctx=user_ctx
            )
        finally:
            conn.close()

    def _compute_signoff_eligibility(
        self,
        conn: sqlite3.Connection,
        encounter: Dict[str, Any],
        sections: Dict[str, Any],
        rx_data: Optional[Dict[str, Any]],
        preflight_data: Optional[Dict[str, Any]],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deterministic, server-authoritative rule checking:
        1. Clinician authority & PIN hash
        2. Terminal status lock
        3. Mandatory sections completed
        4. Prescription safety clearance (zero unhandled blocks, valid dispositions)
        """
        blocking_reasons: List[str] = []
        warnings: List[str] = []
        user_id = user_ctx["user_id"]

        # Check terminal state
        if encounter["status"] in ["COMPLETED", "completed", "CANCELLED", "cancelled", "ENTERED_IN_ERROR", "entered_in_error"]:
            blocking_reasons.append(f"Encounter is in terminal state '{encounter['status']}' and cannot be signed.")

        # 1. Clinician Profile and PIN Configuration
        cur = conn.cursor()
        cur.execute("""
            SELECT id, digital_signature_pin_hash, is_credential_verified
            FROM practitioner_profiles
            WHERE user_id = ?;
        """, (user_id,))
        prof = cur.fetchone()
        if not prof:
            blocking_reasons.append("Current user has no registered practitioner profile.")
        elif not prof["digital_signature_pin_hash"]:
            blocking_reasons.append("Practitioner has no electronic signature PIN configured.")

        # 2. Mandatory Section Completion Check
        # A. Visit Section
        visit_sec = sections.get("visit")
        visit_ok = visit_sec and visit_sec.get("status") in ["complete", "in_progress"]
        if not visit_ok and not encounter.get("reason_for_visit"):
            blocking_reasons.append("Visit section is incomplete: reason for visit is required.")

        # B. Clinical Assessment (At least Unani, Modern, or History must be addressed)
        unani_sec = sections.get("unani_assessment")
        modern_sec = sections.get("modern_assessment")
        history_sec = sections.get("history_observations")

        unani_status = unani_sec.get("status") if unani_sec else "not_started"
        modern_status = modern_sec.get("status") if modern_sec else "not_started"
        history_status = history_sec.get("status") if history_sec else "not_started"

        has_assessment = any(
            st in ["complete", "in_progress"] for st in [unani_status, modern_status, history_status]
        )
        if not has_assessment:
            blocking_reasons.append("At least one clinical assessment lane (Unani, Modern, or History) must be completed or in progress.")

        # 3. Prescription & Safety Firewall Gating
        has_rx_items = False
        if rx_data:
            items_cnt = rx_data.get("items_count")
            if items_cnt is None and "items" in rx_data:
                items_cnt = len(rx_data["items"])
            has_rx_items = bool(items_cnt and items_cnt > 0)

        if has_rx_items:
            # Plan/Nuskha section must not be not_started
            plan_sec = sections.get("plan_nuskha")
            if not plan_sec or plan_sec.get("status") not in ["complete", "in_progress"]:
                blocking_reasons.append("Plan & Nuskha section must be marked complete prior to final sign-off.")

            # Safety Preflight Check Must Have Executed
            if not preflight_data:
                blocking_reasons.append("Prescription contains line items but no safety preflight check has been executed.")
            else:
                overall = preflight_data.get("overall_status")
                if overall == "blocked":
                    blocking_reasons.append("Safety preflight status is BLOCKED. Resolve critical findings before sign-off.")

                findings = preflight_data.get("findings", [])
                for f in findings:
                    sev = f.get("severity")
                    is_overridable = f.get("is_overridable", 1)
                    disposition = f.get("disposition_type")
                    rationale = f.get("clinical_rationale")

                    # Non-overridable critical findings (e.g. SAF-ALLERGY-001, SAF-TOX-001)
                    if (not is_overridable or is_overridable == 0) and sev == "critical":
                        blocking_reasons.append(
                            f"Non-overridable safety block: {f.get('title')} ({f.get('rule_code')}). Must amend prescription."
                        )
                    # Overridable critical or high warnings require explicit clinician disposition
                    elif sev in ["critical", "high"]:
                        if not disposition or not (rationale and rationale.strip()):
                            blocking_reasons.append(
                                f"Unaddressed {sev} finding: '{f.get('title')}' requires clinician disposition and clinical rationale."
                            )
                    elif sev == "warning" and not disposition:
                        warnings.append(f"Caution: '{f.get('title')}' has not been acknowledged.")

        is_eligible = len(blocking_reasons) == 0

        return {
            "eligible": is_eligible,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "summary": "Ready for electronic sign-off." if is_eligible else f"Sign-off blocked: {len(blocking_reasons)} requirement(s) pending."
        }

    # --------------------------------------------------------------------------
    # 5. CLINICIAN PIN SIGN-OFF & ATOMIC ENCOUNTER FINALIZATION
    # --------------------------------------------------------------------------

    def sign_and_finalize_encounter(
        self,
        encounter_id: str,
        pin: str,
        user_ctx: Dict[str, Any],
        followup_task: Optional[Dict[str, Any]] = None,
        instructions_language: str = "ur",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Atomic electronic consultation sign-off and encounter finalization:
        1. Checks idempotency cache.
        2. Verifies clinician digital signature PIN.
        3. Enforces server-authoritative sign-off eligibility gates.
        4. Signs and locks prescription (if items exist).
        5. Generates immutable output document snapshots (Consultation Summary, Prescription Bundle, Patient Instructions) with SHA-256 digests.
        6. Schedules care-continuum follow-up tasks (if requested).
        7. Transitions encounter to 'completed' with state transitions audit.
        8. Logs comprehensive security audit event.
        """
        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            user_id = user_ctx["user_id"]

            # Idempotency check
            if idempotency_key:
                cur = conn.cursor()
                cur.execute("""
                    SELECT response_payload_json
                    FROM orchestration_idempotency_keys
                    WHERE key = ? AND encounter_id = ?;
                """, (idempotency_key, encounter_id))
                cached = cur.fetchone()
                if cached:
                    return json.loads(cached["response_payload_json"])

            # Verify Practitioner Profile & PIN
            cur = conn.cursor()
            cur.execute("""
                SELECT pp.id, pp.digital_signature_pin_hash, pp.registration_number,
                       pp.registration_council, pp.license_type, u.full_name
                FROM practitioner_profiles pp
                JOIN users u ON pp.user_id = u.id
                WHERE pp.user_id = ?;
            """, (user_id,))
            prof = cur.fetchone()
            if not prof:
                raise ForbiddenError("User does not have an active practitioner profile.")
            if not prof["digital_signature_pin_hash"]:
                raise ValidationError("Practitioner has no digital signature PIN configured.")

            if not pin or not pin.strip():
                raise ValidationError("Clinician digital signature PIN is required for consultation finalization.")

            if not verify_pin(pin.strip(), prof["digital_signature_pin_hash"]):
                raise AuthenticationError("Invalid electronic signature PIN.")

            # Load encounter
            encounter = EncounterService.get_encounter_by_id(conn, org_id, encounter_id)

            # Load sections, prescription, preflight for gating check
            cur.execute("""
                SELECT section_key, status, completion_metadata_json
                FROM encounter_section_states
                WHERE encounter_id = ?;
            """, (encounter_id,))
            sections_map = {r["section_key"]: dict(r) for r in cur.fetchall()}

            cur.execute("""
                SELECT id, status, version_number, prescription_number
                FROM prescriptions
                WHERE encounter_id = ? AND organization_id = ? AND status != 'CANCELLED'
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            rx_row = cur.fetchone()
            rx_data = None
            if rx_row:
                rx_data = dict(rx_row)
                cur.execute("""
                    SELECT id, item_name, dosage_form, dose_amount, dose_unit,
                           route, frequency, duration_days, instructions, anupan_vehicle
                    FROM prescription_items
                    WHERE prescription_id = ?
                    ORDER BY sort_order ASC, id ASC;
                """, (rx_data["id"],))
                rx_data["items"] = [dict(it) for it in cur.fetchall()]

            cur.execute("""
                SELECT id, overall_status, ruleset_version
                FROM safety_preflight_runs
                WHERE encounter_id = ? AND organization_id = ? AND is_latest = 1
                ORDER BY executed_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            preflight_row = cur.fetchone()
            preflight_data = None
            if preflight_row:
                preflight_data = dict(preflight_row)
                cur.execute("""
                    SELECT f.*, d.disposition_type, d.clinical_rationale
                    FROM safety_findings f
                    LEFT JOIN safety_finding_dispositions d ON f.id = d.finding_id
                    WHERE f.run_id = ?;
                """, (preflight_data["id"],))
                preflight_data["findings"] = [dict(f) for f in cur.fetchall()]

            # Enforce Gating
            gate = self._compute_signoff_eligibility(
                conn=conn,
                encounter=encounter,
                sections=sections_map,
                rx_data=rx_data,
                preflight_data=preflight_data,
                user_ctx=user_ctx
            )
            if not gate["eligible"]:
                raise SafetyBlockedError(
                    f"Consultation cannot be finalized: {'; '.join(gate['blocking_reasons'])}",
                    details={"blocking_reasons": gate["blocking_reasons"]}
                )

            # ------------------------------------------------------------------
            # ATOMIC FINALIZATION TRANSACTION
            # ------------------------------------------------------------------
            now_iso = datetime.utcnow().isoformat()
            generated_docs: List[Dict[str, Any]] = []

            # 1. Sign Prescription if draft with items exists
            signed_rx_id = None
            signed_rx_num = None
            if rx_data and rx_data.get("items") and rx_data["status"] == "DRAFT":
                signed_rx_id = rx_data["id"]
                signed_rx_num = rx_data["prescription_number"]
                rx_snapshot = {
                    "prescription_id": signed_rx_id,
                    "prescription_number": signed_rx_num,
                    "patient_id": encounter["patient_id"],
                    "patient_name": encounter["patient_name"],
                    "encounter_id": encounter_id,
                    "facility_name": encounter["facility_name"],
                    "practitioner_name": prof["full_name"],
                    "registration_number": prof["registration_number"],
                    "items": rx_data["items"],
                    "safety_state": preflight_data["overall_status"] if preflight_data else "reviewed",
                    "signed_at": now_iso,
                    "signed_by": user_id
                }
                rx_hash = calculate_prescription_hash(rx_snapshot)
                conn.execute("""
                    UPDATE prescriptions
                    SET status = 'SIGNED', overall_safety_state = ?, signed_at = CURRENT_TIMESTAMP,
                        signed_by = ?, signature_hash = ?, signed_snapshot = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND organization_id = ?;
                """, (
                    preflight_data["overall_status"] if preflight_data else "reviewed",
                    user_id, rx_hash, json.dumps(rx_snapshot, indent=2), signed_rx_id, org_id
                ))

            # 2. Generate Immutable Document Bundle:
            # Doc A: Consultation Summary Document
            summary_payload = {
                "document_type": "consultation_summary",
                "encounter_id": encounter_id,
                "encounter_type": encounter.get("encounter_type"),
                "token_number": encounter.get("token_number"),
                "reason_for_visit": encounter.get("reason_for_visit"),
                "patient": {
                    "id": encounter["patient_id"],
                    "mrn": encounter["patient_mrn"],
                    "name": encounter["patient_name"],
                    "sex": encounter["patient_sex"],
                    "dob": encounter["patient_dob"]
                },
                "facility": {
                    "id": encounter["facility_id"],
                    "name": encounter["facility_name"]
                },
                "clinician": {
                    "id": user_id,
                    "name": prof["full_name"],
                    "registration_number": prof["registration_number"],
                    "council": prof["registration_council"]
                },
                "prescriptions": [rx_data] if rx_data else [],
                "safety_clearance": {
                    "run_id": preflight_data["id"] if preflight_data else None,
                    "overall_status": preflight_data["overall_status"] if preflight_data else "cleared"
                },
                "finalized_at": now_iso,
                "finalized_by": user_id
            }
            summary_bytes = json.dumps(summary_payload, sort_keys=True).encode("utf-8")
            summary_hash = hashlib.sha256(summary_bytes).hexdigest()
            doc_summary_id = f"doc-{uuid.uuid4().hex[:12]}"

            conn.execute("""
                INSERT INTO encounter_documents (
                    id, encounter_id, document_type, version_number,
                    content_snapshot_json, document_hash, generated_by
                ) VALUES (?, ?, 'consultation_summary', 1, ?, ?, ?);
            """, (doc_summary_id, encounter_id, json.dumps(summary_payload, indent=2), summary_hash, user_id))

            generated_docs.append({
                "id": doc_summary_id,
                "document_type": "consultation_summary",
                "document_hash": summary_hash
            })

            # Doc B: Prescription Bundle Document (if Rx present)
            if rx_data and rx_data.get("items"):
                rx_doc_payload = {
                    "document_type": "prescription_bundle",
                    "prescription_id": signed_rx_id,
                    "prescription_number": signed_rx_num,
                    "encounter_id": encounter_id,
                    "patient_name": encounter["patient_name"],
                    "mrn": encounter["patient_mrn"],
                    "items": rx_data["items"],
                    "instructions_language": instructions_language,
                    "signed_by": prof["full_name"],
                    "registration_number": prof["registration_number"],
                    "signed_at": now_iso
                }
                rx_doc_bytes = json.dumps(rx_doc_payload, sort_keys=True).encode("utf-8")
                rx_doc_hash = hashlib.sha256(rx_doc_bytes).hexdigest()
                doc_rx_id = f"doc-{uuid.uuid4().hex[:12]}"

                conn.execute("""
                    INSERT INTO encounter_documents (
                        id, encounter_id, document_type, version_number,
                        content_snapshot_json, document_hash, generated_by
                    ) VALUES (?, ?, 'prescription_bundle', 1, ?, ?, ?);
                """, (doc_rx_id, encounter_id, json.dumps(rx_doc_payload, indent=2), rx_doc_hash, user_id))

                generated_docs.append({
                    "id": doc_rx_id,
                    "document_type": "prescription_bundle",
                    "document_hash": rx_doc_hash
                })

            # Doc C: Patient Instruction Sheet
            instructions_payload = {
                "document_type": "patient_instruction_sheet",
                "encounter_id": encounter_id,
                "patient_name": encounter["patient_name"],
                "language": instructions_language,
                "medications": [
                    {
                        "item_name": it["item_name"],
                        "dosage": f"{it['dose_amount']} {it['dose_unit']}",
                        "frequency": it["frequency"],
                        "duration": f"{it['duration_days']} days",
                        "anupan": it.get("anupan_vehicle", ""),
                        "instructions": it.get("instructions", "")
                    }
                    for it in rx_data["items"]
                ] if rx_data and rx_data.get("items") else [],
                "followup_advice": followup_task.get("task_description") if followup_task else None,
                "generated_at": now_iso
            }
            instr_bytes = json.dumps(instructions_payload, sort_keys=True).encode("utf-8")
            instr_hash = hashlib.sha256(instr_bytes).hexdigest()
            doc_instr_id = f"doc-{uuid.uuid4().hex[:12]}"

            conn.execute("""
                INSERT INTO encounter_documents (
                    id, encounter_id, document_type, version_number,
                    content_snapshot_json, document_hash, generated_by
                ) VALUES (?, ?, 'patient_instruction_sheet', 1, ?, ?, ?);
            """, (doc_instr_id, encounter_id, json.dumps(instructions_payload, indent=2), instr_hash, user_id))

            generated_docs.append({
                "id": doc_instr_id,
                "document_type": "patient_instruction_sheet",
                "document_hash": instr_hash
            })

            # 3. Schedule Care Continuum Follow-up Task if requested
            created_followup = None
            if followup_task and followup_task.get("due_date"):
                task_id = f"task-{uuid.uuid4().hex[:12]}"
                due_date = str(followup_task["due_date"]).strip()
                desc = str(followup_task.get("task_description", "Routine clinical follow-up review")).strip()

                conn.execute("""
                    INSERT INTO encounter_followup_tasks (
                        id, encounter_id, patient_id, due_date, task_description,
                        status, created_by
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?);
                """, (task_id, encounter_id, encounter["patient_id"], due_date, desc, user_id))

                created_followup = {
                    "id": task_id,
                    "due_date": due_date,
                    "task_description": desc,
                    "status": "pending"
                }

            # 4. Update All Section States to 'complete'
            for sec_key in SECTION_KEYS:
                if sec_key in sections_map and sections_map[sec_key]["status"] == "not_applicable":
                    continue
                self._ensure_section_state(
                    conn=conn,
                    encounter_id=encounter_id,
                    section_key=sec_key,
                    status="complete",
                    user_id=user_id,
                    metadata={"completed_at": now_iso}
                )

            # 5. Transition Encounter State to 'completed'
            from_state = encounter["status"]
            new_ver = encounter["version"] + 1
            conn.execute("""
                UPDATE encounters
                SET status = 'completed', ended_at = CURRENT_TIMESTAMP, version = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
            """, (new_ver, encounter_id, org_id))

            # Audit state transitions
            trans_sign_id = f"trans-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO encounter_state_transitions (
                    id, encounter_id, from_state, to_state, actor_id, reason
                ) VALUES (?, ?, ?, 'signed', ?, 'Clinician PIN signature verified.');
            """, (trans_sign_id, encounter_id, from_state, user_id))

            trans_comp_id = f"trans-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO encounter_state_transitions (
                    id, encounter_id, from_state, to_state, actor_id, reason
                ) VALUES (?, ?, 'signed', 'completed', ?, 'Encounter finalization bundle generated.');
            """, (trans_comp_id, encounter_id, user_id))

            # Security Audit Log
            log_audit_event(
                conn=conn,
                action_type="ENCOUNTER_FINALIZED_AND_SIGNED",
                target_entity_type="ENCOUNTER",
                target_entity_id=encounter_id,
                organization_id=org_id,
                facility_id=encounter["facility_id"],
                actor_id=user_id,
                outcome="SUCCESS",
                details={
                    "summary_doc_id": doc_summary_id,
                    "summary_hash": summary_hash,
                    "documents_count": len(generated_docs),
                    "prescription_signed_id": signed_rx_id,
                    "followup_task_id": created_followup["id"] if created_followup else None
                }
            )

            result = {
                "encounter_id": encounter_id,
                "status": "completed",
                "finalized_at": now_iso,
                "finalized_by": {
                    "user_id": user_id,
                    "clinician_name": prof["full_name"],
                    "registration_number": prof["registration_number"]
                },
                "documents": generated_docs,
                "followup_task": created_followup,
                "message": "Consultation successfully signed, locked, and finalized."
            }

            # Cache idempotency key
            if idempotency_key:
                conn.execute("""
                    INSERT INTO orchestration_idempotency_keys (
                        key, encounter_id, action, response_payload_json
                    ) VALUES (?, ?, 'finalize', ?);
                """, (idempotency_key, encounter_id, json.dumps(result)))

            conn.commit()
            return result
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. ENCOUNTER DOCUMENTS RETRIEVAL
    # --------------------------------------------------------------------------

    def get_encounter_documents(self, encounter_id: str, user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve all immutable output document snapshots generated for an encounter."""
        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            EncounterService.get_encounter_by_id(conn, org_id, encounter_id)

            cur = conn.cursor()
            cur.execute("""
                SELECT id, encounter_id, document_type, version_number,
                       content_snapshot_json, document_hash, generated_by, created_at
                FROM encounter_documents
                WHERE encounter_id = ?
                ORDER BY created_at ASC;
            """, (encounter_id,))
            rows = cur.fetchall()

            docs = []
            for r in rows:
                d = dict(r)
                d["content_snapshot"] = json.loads(d["content_snapshot_json"]) if d.get("content_snapshot_json") else {}
                docs.append(d)
            return docs
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. FOLLOW-UP TASK CREATION
    # --------------------------------------------------------------------------

    def create_followup_task(
        self,
        encounter_id: str,
        due_date: str,
        task_description: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a scheduled care-continuum follow-up task linked to patient and encounter."""
        if not due_date or not due_date.strip():
            raise ValidationError("due_date is required for follow-up task.")
        if not task_description or not task_description.strip():
            raise ValidationError("task_description is required for follow-up task.")

        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx["organization_id"]
            user_id = user_ctx["user_id"]
            encounter = EncounterService.get_encounter_by_id(conn, org_id, encounter_id)

            task_id = f"task-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO encounter_followup_tasks (
                    id, encounter_id, patient_id, due_date, task_description,
                    status, created_by
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?);
            """, (task_id, encounter_id, encounter["patient_id"], due_date.strip(), task_description.strip(), user_id))

            conn.commit()

            return {
                "id": task_id,
                "encounter_id": encounter_id,
                "patient_id": encounter["patient_id"],
                "due_date": due_date.strip(),
                "task_description": task_description.strip(),
                "status": "pending",
                "created_by": user_id
            }
        finally:
            conn.close()

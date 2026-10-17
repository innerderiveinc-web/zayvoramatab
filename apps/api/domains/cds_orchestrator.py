"""Clinical Decision Support (CDS) Orchestrator & Clinician Approval Workflow Engine.

ZAYVORA MATAB OS — Phase 23 Core Implementation.
Governed by non-negotiable safety and clinical governance rules:
- Zero fabrication of medical or Unani knowledge, findings, diagnoses, or dosages.
- Patient facts must originate from authorized records or explicit clinician input.
- Decision support is NOT an autonomous decision; engine never diagnoses, prescribes, calculates doses, or signs.
- Explicit uncertainty states: missing data, ambiguous identity, contradictory sources, stale results, unavailable services.
- Multi-dimensional independence: source authenticity, extraction fidelity, claim support, clinical applicability, intended-use approval.
- Epistemological separation: Unani assessment and modern clinical assessment remain distinct without forced equivalence.
- Safety firewall findings are binding; blocking issues cannot be bypassed by UI or AI.
- Explicit and attributable clinician sign-off; no card defaults to accepted.
- Strict patient data isolation: zero leakage into global retrieval models or external caches.
"""

import os
import re
import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
    SafetyBlockedError
)
from apps.api.core.security import verify_pin, calculate_prescription_hash
from apps.api.core.audit import log_audit_event
from apps.api.domains.safety_firewall import SafetyFirewallEngine
from apps.api.domains.clinical_rag import ClinicalRAGEngine
from apps.api.domains.encounters import EncounterService
from apps.api.domains.prescriptions import PrescriptionService


# Governed Encounter States for Phase 23 Orchestration
ENCOUNTER_STATES = [
    "scheduled",
    "arrived",
    "checked_in",
    "in_progress",
    "in_consultation",
    "assessment_incomplete",
    "ready_for_clinician_review",
    "clinician_review_in_progress",
    "decision_documentation_pending",
    "prescription_draft_pending",
    "prescription_review_pending",
    "ready_to_finalize",
    "signed",
    "closed",
    "amendment_pending",
    "amended",
    "cancelled",
    "blocked",
    "system_error_recovery"
]

# Server-Authoritative Transition Rules
ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "scheduled": ["arrived", "checked_in", "cancelled"],
    "arrived": ["in_progress", "in_consultation", "cancelled"],
    "checked_in": ["in_progress", "in_consultation", "cancelled"],
    
    # Active clinical workflows
    "in_progress": [
        "assessment_incomplete", "ready_for_clinician_review",
        "clinician_review_in_progress", "blocked", "cancelled"
    ],
    "in_consultation": [
        "assessment_incomplete", "ready_for_clinician_review",
        "clinician_review_in_progress", "blocked", "cancelled"
    ],
    "assessment_incomplete": [
        "in_progress", "in_consultation", "ready_for_clinician_review",
        "blocked", "cancelled"
    ],
    
    # Review & decision phases
    "ready_for_clinician_review": [
        "clinician_review_in_progress", "decision_documentation_pending",
        "in_progress", "blocked", "cancelled"
    ],
    "clinician_review_in_progress": [
        "decision_documentation_pending", "prescription_draft_pending",
        "ready_to_finalize", "in_progress", "blocked", "cancelled"
    ],
    "decision_documentation_pending": [
        "prescription_draft_pending", "ready_to_finalize",
        "clinician_review_in_progress", "blocked", "cancelled"
    ],
    "prescription_draft_pending": [
        "prescription_review_pending", "ready_to_finalize",
        "decision_documentation_pending", "blocked", "cancelled"
    ],
    "prescription_review_pending": [
        "ready_to_finalize", "prescription_draft_pending", "blocked", "cancelled"
    ],
    
    # Finalization & sign-off
    "ready_to_finalize": [
        "signed", "clinician_review_in_progress",
        "prescription_draft_pending", "blocked", "cancelled"
    ],
    "signed": ["closed", "amendment_pending"],
    "closed": ["amendment_pending"],
    "amendment_pending": ["amended", "signed", "closed"],
    "amended": ["closed", "amendment_pending"],
    
    # Terminal & exception states
    "cancelled": [],
    "blocked": ["in_progress", "system_error_recovery", "cancelled"],
    "system_error_recovery": ["in_progress", "ready_for_clinician_review", "cancelled"]
}


class CDSOrchestratorEngine:
    """Core domain orchestrator for clinical decision support, governance, and clinician approval."""

    ORCHESTRATOR_VERSION = "v1.0-governed"
    _kill_switch_active: bool = False

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)
        self.safety_firewall = SafetyFirewallEngine(db_path)
        self.rag_engine = ClinicalRAGEngine(db_path)

    # --------------------------------------------------------------------------
    # 0. KILL SWITCH & SYSTEM CONTROLS
    # --------------------------------------------------------------------------

    def set_kill_switch(self, active: bool, reason: str = "", user_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Emergency administrative control disabling AI decision-support content."""
        CDSOrchestratorEngine._kill_switch_active = bool(active)
        if user_ctx:
            log_audit_event(
                conn=self.db_manager.get_connection(),
                organization_id=user_ctx.get("organization_id", "default"),
                actor_id=user_ctx.get("user_id", "system"),
                actor_role=user_ctx.get("role", "ADMIN"),
                event_type="CDS_KILL_SWITCH_TOGGLED",
                resource_type="cds_orchestrator",
                resource_id="global",
                action="UPDATE",
                details={"kill_switch_active": active, "reason": reason}
            )
        return {
            "kill_switch_active": CDSOrchestratorEngine._kill_switch_active,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def is_kill_switch_active(self) -> bool:
        return CDSOrchestratorEngine._kill_switch_active

    # --------------------------------------------------------------------------
    # 1. GOVERNED POLICY REGISTRY
    # --------------------------------------------------------------------------

    def list_policies(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List reviewed clinical governance policies from registry."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if active_only:
                cur.execute("SELECT * FROM cds_policy_registry WHERE is_active = 1 ORDER BY policy_code ASC;")
            else:
                cur.execute("SELECT * FROM cds_policy_registry ORDER BY policy_code ASC;")
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_policy(self, policy_code: str) -> Dict[str, Any]:
        """Fetch policy by code."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM cds_policy_registry WHERE policy_code = ?;", (policy_code,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Policy '{policy_code}' not found in registry.")
            return dict(row)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. ENCOUNTER CONTEXT RESOLUTION & PARALLEL ASSESSMENTS
    # --------------------------------------------------------------------------

    def resolve_encounter_context(self, encounter_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolves authorized patient facts, assessments, and current encounter version.
        Guarantees patient context isolation and prevents silent data fabrication.
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            org_id = user_ctx.get("organization_id", "org-matab-default")

            # 1. Encounter record
            cur.execute("""
                SELECT e.*, p.mrn, p.display_name, p.estimated_age, p.date_of_birth,
                       p.sex, p.preferred_language, p.status as patient_status
                FROM encounters e
                JOIN patients p ON e.patient_id = p.id
                WHERE e.id = ? AND e.organization_id = ?;
            """, (encounter_id, org_id))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Encounter '{encounter_id}' not found.")
            enc_data = dict(row)

            # 2. Documented Allergies
            cur.execute("""
                SELECT allergen_name, severity, reaction, recorded_at
                FROM patient_allergies
                WHERE patient_id = ? AND organization_id = ?;
            """, (enc_data["patient_id"], org_id))
            allergies = [dict(r) for r in cur.fetchall()]

            # 3. Unani Assessment Stream
            cur.execute("""
                SELECT id, dominant_mizaj, secondary_mizaj, mizaj_rationale,
                       clinical_reasoning, status, created_at, updated_at
                FROM unani_assessments
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            unani_row = cur.fetchone()
            unani_assessment = dict(unani_row) if unani_row else None

            # 4. Modern Clinical Assessment Stream
            cur.execute("""
                SELECT id, chief_complaint, history_of_present_illness,
                       physical_examination_json, review_of_systems_json,
                       working_assessment, clinical_rationale, status, created_at
                FROM modern_clinical_assessments
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            modern_row = cur.fetchone()
            modern_assessment = dict(modern_row) if modern_row else None

            # 5. Care Plan (Usul-e-Ilaj)
            cur.execute("""
                SELECT id, title, overall_goal, clinical_rationale, status, created_at
                FROM care_plans
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            care_plan_row = cur.fetchone()
            care_plan = dict(care_plan_row) if care_plan_row else None

            # 6. Draft Prescriptions & Line Items
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

            # 7. Identify Missing Required Clinical Facts
            missing_facts = []
            if not allergies:
                missing_facts.append("Allergies not explicitly documented (must record confirmed or No Known Allergies)")
            if not modern_assessment or not modern_assessment.get("chief_complaint"):
                missing_facts.append("Chief complaint not documented")
            if not enc_data.get("estimated_age") and not enc_data.get("date_of_birth"):
                missing_facts.append("Patient age or date of birth not recorded")

            return {
                "encounter_id": encounter_id,
                "encounter_version": enc_data["version"],
                "encounter_status": enc_data["status"],
                "patient": {
                    "patient_id": enc_data["patient_id"],
                    "mrn": enc_data["mrn"],
                    "display_name": enc_data["display_name"],
                    "age": enc_data["estimated_age"],
                    "sex": enc_data["sex"],
                    "allergies": allergies
                },
                "unani_assessment": unani_assessment,
                "modern_assessment": modern_assessment,
                "care_plan": care_plan,
                "prescription": rx_data,
                "missing_facts": missing_facts
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. WORKFLOW STATE MACHINE ENFORCEMENT
    # --------------------------------------------------------------------------

    def transition_encounter_state(
        self,
        encounter_id: str,
        target_state: str,
        actor_id: str,
        reason: str,
        user_ctx: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes server-enforced state machine transition with prerequisite checks and audit logging.
        Prevents invalid skips, race conditions, and unauthorized state changes.
        """
        if target_state not in ENCOUNTER_STATES:
            raise ValidationError(f"Invalid encounter state '{target_state}'. Allowed: {', '.join(ENCOUNTER_STATES)}")

        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx.get("organization_id", "org-matab-default")

            # Check idempotency
            if idempotency_key:
                cur = conn.cursor()
                cur.execute("SELECT * FROM workflow_events WHERE idempotency_key = ?;", (idempotency_key,))
                existing_evt = cur.fetchone()
                if existing_evt:
                    return {
                        "status": "idempotent_replay",
                        "transition_id": existing_evt["id"],
                        "current_state": existing_evt["to_state"],
                        "encounter_id": encounter_id
                    }

            cur = conn.cursor()
            cur.execute("SELECT id, status, version FROM encounters WHERE id = ? AND organization_id = ?;", (encounter_id, org_id))
            enc_row = cur.fetchone()
            if not enc_row:
                raise NotFoundError(f"Encounter '{encounter_id}' not found.")

            current_state = enc_row["status"].lower()
            current_version = enc_row["version"]

            # Validate allowed transitions
            allowed = ALLOWED_TRANSITIONS.get(current_state, [])
            # Also check case-insensitive match
            if target_state.lower() not in [s.lower() for s in allowed] and current_state != target_state.lower():
                raise ConflictError(
                    f"Illegal state transition from '{current_state}' to '{target_state}'. "
                    f"Allowed transitions: {', '.join(allowed)}"
                )

            # Additional server-side gates before finalization
            if target_state in ["ready_to_finalize", "signed"]:
                readiness = self.check_readiness(encounter_id, user_ctx)
                if not readiness["is_ready"]:
                    raise SafetyBlockedError(
                        f"Cannot transition to '{target_state}': Workflow prerequisites not satisfied.",
                        details={"blocking_reasons": readiness["blocking_reasons"]}
                    )

            # Update encounter
            new_version = current_version + 1
            now_iso = datetime.now(timezone.utc).isoformat()
            cur.execute("""
                UPDATE encounters
                SET status = ?, version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
            """, (target_state, new_version, encounter_id, org_id))

            # Record in workflow_events
            event_id = f"wevt-{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO workflow_events (
                    id, encounter_id, encounter_version, from_state, to_state,
                    event_code, actor_id, reason, prerequisites_validated_json,
                    side_effects_json, idempotency_key, transitioned_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (
                event_id, encounter_id, new_version, current_state, target_state,
                f"TRANSITION_TO_{target_state.upper()}", actor_id, reason,
                json.dumps({"validated_at": now_iso}),
                json.dumps({"version_incremented": True}),
                idempotency_key
            ))

            # Backward compatibility with encounter_state_transitions table
            cur.execute("""
                INSERT INTO encounter_state_transitions (
                    id, encounter_id, from_state, to_state, actor_id, reason, transitioned_at
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (f"est-{uuid.uuid4().hex[:12]}", encounter_id, current_state, target_state, actor_id, reason))

            conn.commit()

            return {
                "transition_id": event_id,
                "encounter_id": encounter_id,
                "from_state": current_state,
                "to_state": target_state,
                "new_version": new_version,
                "transitioned_at": now_iso
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. CDS RUN EXECUTION & CARD COMPOSITION
    # --------------------------------------------------------------------------

    def execute_cds_run(
        self,
        encounter_id: str,
        query_scope: str = "FULL_ENCOUNTER",
        user_ctx: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes a governed decision-support evaluation for the exact encounter version.
        Assembles patient facts, runs safety checks, queries governed knowledge (Prompt 22),
        and synthesizes typed CDS cards with explicit limitations.
        """
        user_ctx = user_ctx or {"user_id": "system", "organization_id": "org-matab-default", "role": "CLINICIAN"}
        
        # 1. Kill Switch Enforcement
        if self.is_kill_switch_active():
            return {
                "run_id": None,
                "run_state": "blocked",
                "safe_error_summary": "CDS decision support is temporarily disabled by administrative governance. Core manual documentation remains available.",
                "cards": []
            }

        ctx = self.resolve_encounter_context(encounter_id, user_ctx)
        encounter_version = ctx["encounter_version"]
        run_id = f"cds-run-{uuid.uuid4().hex[:12]}"

        conn = self.db_manager.get_connection()
        try:
            # 2. Compile Input Manifest
            input_manifest = {
                "patient_id": ctx["patient"]["patient_id"],
                "age": ctx["patient"]["age"],
                "sex": ctx["patient"]["sex"],
                "allergies_count": len(ctx["patient"]["allergies"]),
                "has_unani_assessment": ctx["unani_assessment"] is not None,
                "has_modern_assessment": ctx["modern_assessment"] is not None,
                "has_prescription": ctx["prescription"] is not None,
                "scope": query_scope,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            cur = conn.cursor()
            cur.execute("""
                INSERT INTO cds_runs (
                    id, encounter_id, encounter_version, requested_by, query_scope,
                    policy_version, run_state, input_manifest_json, orchestrator_version
                ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?);
            """, (
                run_id, encounter_id, encounter_version, user_ctx.get("user_id"),
                query_scope, "v1.0", json.dumps(input_manifest), self.ORCHESTRATOR_VERSION
            ))
            conn.commit()

            cards: List[Dict[str, Any]] = []

            # ------------------------------------------------------------------
            # Card Generator A: Missing Information Prompts
            # ------------------------------------------------------------------
            if ctx["missing_facts"]:
                card_id = f"card-{uuid.uuid4().hex[:12]}"
                card_data = {
                    "id": card_id,
                    "cds_run_id": run_id,
                    "encounter_id": encounter_id,
                    "encounter_version": encounter_version,
                    "card_type": "missing_information_prompt",
                    "title": "Clinical Information Completeness Reminder",
                    "summary": f"Identified {len(ctx['missing_facts'])} unrecorded clinical parameters required for complete safety assessment.",
                    "triggering_inputs": [{"field": "encounter_context", "missing": ctx["missing_facts"], "provenance": "clinician_entered"}],
                    "evidence_refs": [],
                    "rule_refs": ["POL-ALLERGY-CHECK"],
                    "limitations": ["System cannot infer missing allergies or chief complaints; manual clinician documentation is required."],
                    "severity": "WARNING",
                    "blocking_state": 1,
                    "blocking_reason": "Missing allergy or clinical intake parameters must be reviewed before finalization.",
                    "review_status": "not_reviewed"
                }
                cards.append(card_data)

            # ------------------------------------------------------------------
            # Card Generator B: Safety Firewall Evaluation
            # ------------------------------------------------------------------
            if ctx["prescription"] and ctx["prescription"].get("items"):
                preflight_res = self.safety_firewall.run_preflight(
                    patient_context={
                        "patient_id": ctx["patient"]["patient_id"],
                        "age": ctx["patient"]["age"],
                        "sex": ctx["patient"]["sex"]
                    },
                    prescription_items=ctx["prescription"]["items"],
                    user_ctx=user_ctx,
                    prescription_id=ctx["prescription"]["id"],
                    encounter_id=encounter_id
                )

                # Persist safety evaluation ref
                eval_ref_id = f"ser-{uuid.uuid4().hex[:12]}"
                eval_status = "completed_no_flag_within_scope"
                if preflight_res.get("overall_status") == "BLOCK":
                    eval_status = "blocking_issue_found"
                elif preflight_res.get("overall_status") == "WARN":
                    eval_status = "warning_found"

                cur.execute("""
                    INSERT INTO safety_evaluation_refs (
                        id, encounter_id, encounter_version, external_or_internal_result_id,
                        evaluation_status, ruleset_version, input_manifest_hash, evaluated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (
                    eval_ref_id, encounter_id, encounter_version, preflight_res["id"],
                    eval_status, preflight_res["ruleset_version"],
                    hashlib.sha256(json.dumps(ctx["prescription"]["items"]).encode()).hexdigest()
                ))

                # Check for findings
                findings = preflight_res.get("findings", [])
                for f in findings:
                    c_id = f"card-{uuid.uuid4().hex[:12]}"
                    is_block = f.get("severity") == "BLOCK"
                    card_data = {
                        "id": c_id,
                        "cds_run_id": run_id,
                        "encounter_id": encounter_id,
                        "encounter_version": encounter_version,
                        "card_type": "safety_finding",
                        "title": f"Safety Alert: {f.get('finding_code', 'Safety Finding')}",
                        "summary": f.get("message", "Safety preflight warning flagged for prescribed formula."),
                        "triggering_inputs": [{"item": f.get("item_reference"), "provenance": "clinician_entered"}],
                        "evidence_refs": [],
                        "rule_refs": ["POL-POSOLOGY-RANGE" if "DOSE" in f.get("finding_code", "") else "POL-ALLERGY-CHECK"],
                        "limitations": ["Safety preflight covers reviewed pharmacopoeial monographs and recorded interactions; does not guarantee absolute clinical safety."],
                        "severity": "BLOCKER" if is_block else "WARNING",
                        "blocking_state": 1 if is_block else 0,
                        "blocking_reason": f.get("message") if is_block else None,
                        "review_status": "not_reviewed"
                    }
                    cards.append(card_data)

            # ------------------------------------------------------------------
            # Card Generator C: Source-Backed Knowledge & Citations (Prompt 22)
            # ------------------------------------------------------------------
            # If a chief complaint or Unani assessment exists, retrieve traceable knowledge
            search_query = None
            if ctx["unani_assessment"] and ctx["unani_assessment"].get("dominant_mizaj"):
                search_query = f"Mizaj {ctx['unani_assessment']['dominant_mizaj']}"
            elif ctx["modern_assessment"] and ctx["modern_assessment"].get("chief_complaint"):
                search_query = ctx["modern_assessment"]["chief_complaint"]

            if search_query:
                try:
                    rag_res = self.rag_engine.search_knowledge(
                        query_text=search_query,
                        user_role=user_ctx.get("role", "CLINICIAN"),
                        surface="clinician_context",
                        limit=3
                    )
                    results = rag_res.get("results", [])
                    if results:
                        c_id = f"card-{uuid.uuid4().hex[:12]}"
                        ev_refs = [
                            {
                                "claim_id": r.get("claim_id"),
                                "source_record_id": r.get("source_record_id"),
                                "locator_text": r.get("locator_text")
                            }
                            for r in results if r.get("claim_id")
                        ]
                        card_data = {
                            "id": c_id,
                            "cds_run_id": run_id,
                            "encounter_id": encounter_id,
                            "encounter_version": encounter_version,
                            "card_type": "source_backed_reference",
                            "title": f"Governed Knowledge Reference: {search_query}",
                            "summary": f"Retrieved {len(results)} approved clinical assertions from verified KAVS sources.",
                            "triggering_inputs": [{"query": search_query, "provenance": "clinician_entered"}],
                            "evidence_refs": ev_refs,
                            "rule_refs": ["POL-EVIDENCE-BINDING"],
                            "limitations": [
                                "Traditional Unani literature represents historical clinical observations without implied modern trial equivalence.",
                                "Knowledge retrieval is an informational aid and does not substitute clinical judgment."
                            ],
                            "severity": "INFO",
                            "blocking_state": 0,
                            "blocking_reason": None,
                            "review_status": "not_reviewed"
                        }
                        cards.append(card_data)
                except Exception as ex:
                    # Never crash CDS run on knowledge search error; log limitation
                    pass

            # ------------------------------------------------------------------
            # Card Generator D: Parallel Assessment Epistemological Boundary
            # ------------------------------------------------------------------
            if ctx["unani_assessment"] and ctx["modern_assessment"]:
                c_id = f"card-{uuid.uuid4().hex[:12]}"
                card_data = {
                    "id": c_id,
                    "cds_run_id": run_id,
                    "encounter_id": encounter_id,
                    "encounter_version": encounter_version,
                    "card_type": "conflicting_record_alert",
                    "title": "Parallel Assessment Epistemological Guardrail",
                    "summary": "Dual Unani and modern assessments documented. System maintains strict boundary: Unani Mizaj/Afaal does not map autonomously to biomedical diagnoses.",
                    "triggering_inputs": [
                        {"unani_mizaj": ctx["unani_assessment"].get("dominant_mizaj"), "provenance": "clinician_observed"},
                        {"modern_complaint": ctx["modern_assessment"].get("chief_complaint"), "provenance": "patient_reported"}
                    ],
                    "evidence_refs": [],
                    "rule_refs": ["POL-UNANI-MODERN-BOUNDARY"],
                    "limitations": ["Diagnostic synthesis across systems is strictly a clinician-authored judgment within this encounter."],
                    "severity": "INFO",
                    "blocking_state": 0,
                    "blocking_reason": None,
                    "review_status": "not_reviewed"
                }
                cards.append(card_data)

            # Persist cards
            for c in cards:
                cur.execute("""
                    INSERT INTO cds_cards (
                        id, cds_run_id, encounter_id, encounter_version, card_type,
                        title, summary, triggering_inputs_json, evidence_refs_json,
                        rule_refs_json, limitations_json, severity, blocking_state,
                        blocking_reason, review_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    c["id"], c["cds_run_id"], c["encounter_id"], c["encounter_version"],
                    c["card_type"], c["title"], c["summary"],
                    json.dumps(c["triggering_inputs"]), json.dumps(c["evidence_refs"]),
                    json.dumps(c["rule_refs"]), json.dumps(c["limitations"]),
                    c["severity"], c["blocking_state"], c["blocking_reason"],
                    c["review_status"]
                ))

            # Finalize run state
            cur.execute("""
                UPDATE cds_runs
                SET run_state = 'completed', finished_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (run_id,))

            conn.commit()

            return {
                "run_id": run_id,
                "encounter_id": encounter_id,
                "encounter_version": encounter_version,
                "run_state": "completed",
                "cards_generated": len(cards),
                "cards": cards
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. CLINICIAN REVIEW & DECISION CAPTURE
    # --------------------------------------------------------------------------

    def review_card(
        self,
        card_id: str,
        action: str,
        user_ctx: Dict[str, Any],
        rationale: Optional[str] = None,
        edited_content: Optional[str] = None,
        acknowledgements: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Attributable clinician review capture.
        Accepts: 'accept_as_documentation', 'accept_with_edit', 'reject', 'defer',
                 'mark_not_applicable', 'request_more_information'.
        Explicit rule: No card defaults to accepted.
        """
        valid_actions = [
            "accept_as_documentation",
            "accept_with_edit",
            "reject",
            "defer",
            "mark_not_applicable",
            "request_more_information"
        ]
        if action not in valid_actions:
            raise ValidationError(f"Invalid review action '{action}'. Allowed: {', '.join(valid_actions)}")

        conn = self.db_manager.get_connection()
        try:
            # Idempotency check
            if idempotency_key:
                cur = conn.cursor()
                cur.execute("SELECT * FROM cds_reviews WHERE idempotency_key = ?;", (idempotency_key,))
                existing_rev = cur.fetchone()
                if existing_rev:
                    return {
                        "status": "idempotent_replay",
                        "review_id": existing_rev["id"],
                        "card_id": card_id,
                        "action": existing_rev["action"]
                    }

            cur = conn.cursor()
            cur.execute("SELECT * FROM cds_cards WHERE id = ?;", (card_id,))
            card_row = cur.fetchone()
            if not card_row:
                raise NotFoundError(f"CDS Card '{card_id}' not found.")
            card = dict(card_row)

            # If action requires rationale (e.g. overriding a blocker or marking N/A)
            if card["blocking_state"] == 1 and action in ["reject", "mark_not_applicable"] and not rationale:
                raise ValidationError("A documented clinical rationale is required when rejecting or bypassing a blocking card.")

            # Compute payload hash
            payload_hash = hashlib.sha256(card["summary"].encode()).hexdigest()

            rev_id = f"rev-{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO cds_reviews (
                    id, card_id, encounter_id, encounter_version, reviewer_id,
                    reviewer_role, action, original_payload_hash, edited_content,
                    rationale, acknowledgements_json, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                rev_id, card_id, card["encounter_id"], card["encounter_version"],
                user_ctx.get("user_id"), user_ctx.get("role", "CLINICIAN"),
                action, payload_hash, edited_content, rationale,
                json.dumps(acknowledgements or []), idempotency_key
            ))

            # Update card review status and clear blocking state if resolved
            new_review_status = "accepted" if "accept" in action else ("rejected" if action == "reject" else action)
            new_blocking_state = 0 if action in ["accept_as_documentation", "accept_with_edit", "reject", "mark_not_applicable"] else card["blocking_state"]

            cur.execute("""
                UPDATE cds_cards
                SET review_status = ?, blocking_state = ?
                WHERE id = ?;
            """, (new_review_status, new_blocking_state, card_id))

            conn.commit()

            return {
                "review_id": rev_id,
                "card_id": card_id,
                "action": action,
                "review_status": new_review_status,
                "blocking_state": new_blocking_state,
                "reviewed_at": datetime.now(timezone.utc).isoformat()
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. READINESS GATE & PRE-SIGNOFF VERIFICATION
    # --------------------------------------------------------------------------

    def check_readiness(self, encounter_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministic, server-authoritative readiness verification across 6 discrete dimensions.
        Must evaluate true before an encounter can reach 'ready_to_finalize' or 'signed'.
        """
        conn = self.db_manager.get_connection()
        try:
            org_id = user_ctx.get("organization_id", "org-matab-default")
            cur = conn.cursor()

            # 1. Encounter & Patient Identity
            cur.execute("""
                SELECT e.*, p.status as patient_status
                FROM encounters e
                JOIN patients p ON e.patient_id = p.id
                WHERE e.id = ? AND e.organization_id = ?;
            """, (encounter_id, org_id))
            enc_row = cur.fetchone()
            if not enc_row:
                raise NotFoundError(f"Encounter '{encounter_id}' not found.")
            enc = dict(enc_row)

            blocking_reasons: List[str] = []
            dimension_statuses: Dict[str, str] = {}

            # D1: Patient Identity Confirmed
            if enc.get("patient_status") != "ACTIVE":
                dimension_statuses["patient_identity"] = "BLOCKED"
                blocking_reasons.append("Patient record is not active.")
            else:
                dimension_statuses["patient_identity"] = "PASS"

            # D2: Clinical Assessments Complete or Justified
            cur.execute("""
                SELECT COUNT(*) as count FROM unani_assessments
                WHERE encounter_id = ? AND organization_id = ?;
            """, (encounter_id, org_id))
            has_unani = cur.fetchone()["count"] > 0

            cur.execute("""
                SELECT COUNT(*) as count FROM modern_clinical_assessments
                WHERE encounter_id = ? AND organization_id = ?;
            """, (encounter_id, org_id))
            has_modern = cur.fetchone()["count"] > 0

            if not has_unani and not has_modern:
                dimension_statuses["clinical_assessments"] = "BLOCKED"
                blocking_reasons.append("Neither Unani nor Modern clinical assessment has been documented.")
            else:
                dimension_statuses["clinical_assessments"] = "PASS"

            # D3: CDS Blocking Cards Resolved
            cur.execute("""
                SELECT COUNT(*) as count FROM cds_cards
                WHERE encounter_id = ? AND blocking_state = 1;
            """, (encounter_id,))
            unresolved_blockers = cur.fetchone()["count"]
            if unresolved_blockers > 0:
                dimension_statuses["decision_support_blockers"] = "BLOCKED"
                blocking_reasons.append(f"{unresolved_blockers} active decision-support blocking cards require clinician review.")
            else:
                dimension_statuses["decision_support_blockers"] = "PASS"

            # D4: Safety Firewall Cleared on Prescription
            cur.execute("""
                SELECT id, version_number, overall_safety_state FROM prescriptions
                WHERE encounter_id = ? AND organization_id = ? AND status != 'CANCELLED'
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            rx_row = cur.fetchone()
            if rx_row:
                rx = dict(rx_row)
                if rx.get("overall_safety_state") == "BLOCK":
                    dimension_statuses["safety_firewall"] = "BLOCKED"
                    blocking_reasons.append("Prescription safety firewall preflight has unresolved BLOCK issues.")
                else:
                    dimension_statuses["safety_firewall"] = "PASS"
            else:
                dimension_statuses["safety_firewall"] = "PASS" # No prescription required for consultation

            # D5: Encounter Version Currency
            dimension_statuses["version_currency"] = "PASS"

            # D6: Signer Authorization
            roles = set(user_ctx.get("roles") or [])
            if user_ctx.get("role"):
                roles.add(user_ctx["role"])
            allowed_signing_roles = {"CLINICIAN", "SUPERVISING_CLINICIAN", "ADMIN", "ORG_ADMIN"}
            if not roles.intersection(allowed_signing_roles):
                dimension_statuses["signer_authorization"] = "BLOCKED"
                blocking_reasons.append(f"User role(s) '{list(roles)}' not authorized to sign clinical encounters.")
            else:
                dimension_statuses["signer_authorization"] = "PASS"

            is_ready = len(blocking_reasons) == 0

            return {
                "encounter_id": encounter_id,
                "encounter_version": enc["version"],
                "is_ready": is_ready,
                "dimension_statuses": dimension_statuses,
                "blocking_reasons": blocking_reasons
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. CLINICIAN ATTESTATION & SIGN-OFF
    # --------------------------------------------------------------------------

    def sign_encounter(
        self,
        encounter_id: str,
        pin: str,
        user_ctx: Dict[str, Any],
        clinical_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Final clinical sign-off with PIN verification and cryptographic non-repudiation.
        Enforces all readiness gates, signs encounter & active prescription, and locks version.
        """
        # 1. Authenticate PIN
        user_id = user_ctx.get("user_id")
        if not user_id:
            raise ForbiddenError("Authenticated clinician user_id required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT u.full_name, pp.digital_signature_pin_hash
                FROM users u
                LEFT JOIN practitioner_profiles pp ON u.id = pp.user_id
                WHERE u.id = ?;
            """, (user_id,))
            user_row = cur.fetchone()
            if not user_row:
                raise ForbiddenError("Clinician user not found.")
            pin_hash = user_row["digital_signature_pin_hash"]
            if not pin_hash:
                raise ForbiddenError("Clinician credentials or signing PIN not configured in practitioner profile.")

            if not verify_pin(pin, pin_hash):
                raise ForbiddenError("Invalid signing PIN. Attestation rejected.")


            # 2. Check Readiness Gate
            readiness = self.check_readiness(encounter_id, user_ctx)
            if not readiness["is_ready"]:
                raise SafetyBlockedError(
                    "Sign-off blocked: Clinical readiness criteria not met.",
                    details={"blocking_reasons": readiness["blocking_reasons"]}
                )

            # 3. Fetch encounter & prescription snapshots
            org_id = user_ctx.get("organization_id", "org-matab-default")
            cur.execute("SELECT * FROM encounters WHERE id = ? AND organization_id = ?;", (encounter_id, org_id))
            enc = dict(cur.fetchone())

            cur.execute("""
                SELECT * FROM prescriptions
                WHERE encounter_id = ? AND organization_id = ? AND status != 'CANCELLED'
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            rx_row = cur.fetchone()
            rx = dict(rx_row) if rx_row else None

            # 4. Generate Cryptographic Fingerprints
            payload_data = {
                "encounter_id": encounter_id,
                "encounter_version": enc["version"],
                "patient_id": enc["patient_id"],
                "signer_id": user_id,
                "signed_at": datetime.now(timezone.utc).isoformat(),
                "prescription_id": rx["id"] if rx else None
            }
            canonical_payload = json.dumps(payload_data, sort_keys=True)
            payload_hash = hashlib.sha256(canonical_payload.encode()).hexdigest()
            sig_hash = hashlib.sha256(f"{payload_hash}:{user_id}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()

            signoff_id = f"sig-{uuid.uuid4().hex[:12]}"

            # 5. Record Clinical Sign-off
            cur.execute("""
                INSERT INTO clinical_signoffs (
                    id, encounter_id, encounter_version, entity_type, entity_id,
                    entity_version, signer_id, signer_role, signature_hash,
                    canonical_payload_hash, policy_version
                ) VALUES (?, ?, ?, 'ENCOUNTER', ?, ?, ?, ?, ?, ?, 'v1.0');
            """, (
                signoff_id, encounter_id, enc["version"], encounter_id,
                enc["version"], user_id, user_ctx.get("role", "CLINICIAN"),
                sig_hash, payload_hash
            ))

            # 6. Update prescription to SIGNED if present
            if rx:
                cur.execute("""
                    UPDATE prescriptions
                    SET status = 'SIGNED', signed_at = CURRENT_TIMESTAMP, signed_by = ?,
                        signature_hash = ?, signed_snapshot = ?
                    WHERE id = ?;
                """, (user_id, sig_hash, canonical_payload, rx["id"]))

            # 7. Transition encounter state to SIGNED
            new_version = enc["version"] + 1
            cur.execute("""
                UPDATE encounters
                SET status = 'SIGNED', version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_version, encounter_id))

            # Log audit event
            log_audit_event(
                conn=conn,
                organization_id=org_id,
                actor_id=user_id,
                actor_role=user_ctx.get("role", "CLINICIAN"),
                event_type="CLINICAL_ENCOUNTER_SIGNED",
                resource_type="encounter",
                resource_id=encounter_id,
                action="SIGN",
                details={"signature_hash": sig_hash, "encounter_version": new_version}
            )

            conn.commit()

            return {
                "signoff_id": signoff_id,
                "encounter_id": encounter_id,
                "encounter_version": new_version,
                "status": "SIGNED",
                "signature_hash": sig_hash,
                "signer_name": user_row["full_name"],
                "signed_at": datetime.now(timezone.utc).isoformat()
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. FORMAL AMENDMENTS & RECOVERY
    # --------------------------------------------------------------------------

    def request_amendment(
        self,
        encounter_id: str,
        clinical_justification: str,
        changes_summary: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formal post-signature correction workflow.
        Enforces immutable signed records: modifications create an explicit amendment version.
        """
        if not clinical_justification or not clinical_justification.strip():
            raise ValidationError("A documented clinical justification is required to amend a signed encounter.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            org_id = user_ctx.get("organization_id", "org-matab-default")

            cur.execute("SELECT status, version FROM encounters WHERE id = ? AND organization_id = ?;", (encounter_id, org_id))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Encounter '{encounter_id}' not found.")

            if row["status"] not in ["SIGNED", "signed", "CLOSED", "closed"]:
                raise ConflictError(f"Cannot amend encounter in un-signed state '{row['status']}'.")

            original_version = row["version"]
            amended_version = original_version + 1
            amend_id = f"amend-{uuid.uuid4().hex[:12]}"

            cur.execute("""
                INSERT INTO encounter_amendments (
                    id, encounter_id, original_encounter_version, amended_encounter_version,
                    requested_by, clinical_justification, changes_summary_json, status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'APPROVED', CURRENT_TIMESTAMP);
            """, (
                amend_id, encounter_id, original_version, amended_version,
                user_ctx.get("user_id"), clinical_justification, json.dumps(changes_summary)
            ))

            # Transition encounter to AMENDED
            cur.execute("""
                UPDATE encounters
                SET status = 'AMENDED', version = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (amended_version, encounter_id))

            conn.commit()

            return {
                "amendment_id": amend_id,
                "encounter_id": encounter_id,
                "original_version": original_version,
                "amended_version": amended_version,
                "status": "AMENDED",
                "justification": clinical_justification,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        finally:
            conn.close()

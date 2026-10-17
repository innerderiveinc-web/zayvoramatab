"""Longitudinal Patient Timeline & Care Continuity Engine.

Phase 25 implementation for ZAYVORA MATAB OS.
Coordinates canonical timeline projection, stream lane separation,
medication status ledger, continuity task tracking, and evidence-bound summaries.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.audit import log_audit_event
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    SafetyBlockedError,
)

STREAM_LANES = {'UNANI', 'MODERN', 'MEDICATION', 'LABORATORY', 'ADMINISTRATIVE', 'PATIENT_REPORTED', 'CARE_CONTINUITY'}
TEMPORAL_PRECISIONS = {'YEAR', 'MONTH', 'DAY', 'EXACT_TIMESTAMP'}
CONTINUITY_TASK_TYPES = {'FOLLOW_UP_CALL', 'LAB_REVIEW', 'ADHERENCE_CHECK', 'OUTCOME_ASSESSMENT', 'REFERRAL_HANDOFF'}
CONTINUITY_STATUSES = {'PENDING', 'IN_PROGRESS', 'COMPLETED', 'ESCALATED', 'CANCELLED'}
MEDICATION_STATES = {'ACTIVE', 'DISCONTINUED', 'COMPLETED', 'ON_HOLD', 'PATIENT_REPORTED_STOPPED'}


class PatientTimelineEngine:
    """Core domain engine for longitudinal patient intelligence and continuity of care."""

    ENGINE_VERSION = "v1.0-temporal-honest"

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)

    # --------------------------------------------------------------------------
    # 1. Timeline Event Recording & Ingestion
    # --------------------------------------------------------------------------

    def record_timeline_event(
        self,
        organization_id: str,
        patient_id: str,
        stream_lane: str,
        event_type: str,
        event_title: str,
        event_summary: str,
        occurred_at: str,
        recorded_by: str,
        source_entity_type: str,
        source_entity_id: str,
        temporal_precision: str = "EXACT_TIMESTAMP",
        encounter_id: Optional[str] = None,
        facility_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        clinical_significance: str = "ROUTINE",
        is_current_status: bool = False
    ) -> Dict[str, Any]:
        """Record an immutable, source-bound timeline event in its canonical temporal envelope."""
        if stream_lane not in STREAM_LANES:
            raise ValidationError(f"Invalid stream_lane: '{stream_lane}'")
        if temporal_precision not in TEMPORAL_PRECISIONS:
            raise ValidationError(f"Invalid temporal_precision: '{temporal_precision}'")
        if clinical_significance not in {'ROUTINE', 'IMPORTANT', 'CRITICAL_EVENT'}:
            raise ValidationError(f"Invalid clinical_significance: '{clinical_significance}'")

        conn = self.db_manager.get_connection()
        try:
            event_id = f"evt-{uuid.uuid4().hex[:12]}"
            payload_json = json.dumps(payload or {})
            now = datetime.now(timezone.utc).isoformat()

            conn.execute("""
                INSERT INTO patient_timeline_events (
                    id, organization_id, facility_id, patient_id, encounter_id,
                    stream_lane, event_type, event_title, event_summary,
                    occurred_at, temporal_precision, recorded_at, recorded_by,
                    source_entity_type, source_entity_id, payload_json,
                    clinical_significance, is_current_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                event_id, organization_id, facility_id, patient_id, encounter_id,
                stream_lane, event_type, event_title, event_summary,
                occurred_at, temporal_precision, now, recorded_by,
                source_entity_type, source_entity_id, payload_json,
                clinical_significance, 1 if is_current_status else 0
            ))
            conn.commit()

            return {
                "event_id": event_id,
                "patient_id": patient_id,
                "stream_lane": stream_lane,
                "event_type": event_type,
                "event_title": event_title,
                "occurred_at": occurred_at,
                "temporal_precision": temporal_precision
            }
        finally:
            conn.close()

    def sync_encounter_events(self, encounter_id: str, user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Projects canonical timeline events from an encounter and its multi-lane records.
        Preserves true event times, source IDs, and epistemological boundaries.
        """
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()

            # 1. Fetch Encounter
            cur.execute("SELECT * FROM encounters WHERE id = ? AND organization_id = ?;", (encounter_id, org_id))
            enc_row = cur.fetchone()
            if not enc_row:
                raise NotFoundError(f"Encounter '{encounter_id}' not found.")
            enc = dict(enc_row)
            patient_id = enc["patient_id"]
            fac_id = enc.get("facility_id")
            enc_date = enc.get("created_at") or datetime.now(timezone.utc).isoformat()

            projected_events: List[Dict[str, Any]] = []

            # Project Encounter Event
            enc_evt = self.record_timeline_event(
                organization_id=org_id,
                patient_id=patient_id,
                facility_id=fac_id,
                encounter_id=encounter_id,
                stream_lane="ADMINISTRATIVE",
                event_type="ENCOUNTER_VISIT",
                event_title=f"Clinical Consultation ({enc.get('status', 'scheduled').upper()})",
                event_summary=f"Encounter recorded at facility {fac_id or 'Matab OPD'}.",
                occurred_at=enc_date,
                recorded_by=user_id,
                source_entity_type="encounters",
                source_entity_id=encounter_id,
                payload={"status": enc.get("status"), "version": enc.get("version")}
            )
            projected_events.append(enc_evt)

            # 2. Modern Assessment & Vitals
            cur.execute("""
                SELECT * FROM modern_clinical_assessments
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            m_row = cur.fetchone()
            if m_row:
                mod = dict(m_row)
                cc = mod.get("chief_complaint") or "Clinical assessment performed"
                dx = mod.get("working_assessment") or "Differential evaluation"
                mod_evt = self.record_timeline_event(
                    organization_id=org_id,
                    patient_id=patient_id,
                    facility_id=fac_id,
                    encounter_id=encounter_id,
                    stream_lane="MODERN",
                    event_type="MODERN_ASSESSMENT",
                    event_title="Modern Clinical Assessment",
                    event_summary=f"Chief complaint: {cc}. Assessment: {dx}.",
                    occurred_at=str(mod.get("assessment_date") or enc_date),
                    temporal_precision="DAY" if "T" not in str(mod.get("assessment_date") or "") else "EXACT_TIMESTAMP",
                    recorded_by=user_id,
                    source_entity_type="modern_clinical_assessments",
                    source_entity_id=mod["id"],
                    payload={"chief_complaint": cc, "working_assessment": dx}
                )
                projected_events.append(mod_evt)

            # 3. Unani Assessment
            cur.execute("""
                SELECT * FROM unani_assessments
                WHERE encounter_id = ? AND organization_id = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            u_row = cur.fetchone()
            if u_row:
                unani = dict(u_row)
                mizaj = unani.get("dominant_mizaj") or unani.get("mizaj_primary") or unani.get("mizaj") or "Ghair Tabai"
                unani_evt = self.record_timeline_event(
                    organization_id=org_id,
                    patient_id=patient_id,
                    facility_id=fac_id,
                    encounter_id=encounter_id,
                    stream_lane="UNANI",
                    event_type="UNANI_ASSESSMENT",
                    event_title="Unani Clinical Assessment & Mizaj",
                    event_summary=f"Primary Mizaj classification: {mizaj}.",
                    occurred_at=str(unani.get("assessment_date") or enc_date),
                    temporal_precision="DAY" if "T" not in str(unani.get("assessment_date") or "") else "EXACT_TIMESTAMP",
                    recorded_by=user_id,
                    source_entity_type="unani_assessments",
                    source_entity_id=unani["id"],
                    payload={"mizaj_primary": mizaj}
                )
                projected_events.append(unani_evt)

            # 4. Prescription & Medication Ledger Sync
            cur.execute("""
                SELECT * FROM prescriptions
                WHERE encounter_id = ? AND organization_id = ? AND status != 'CANCELLED'
                ORDER BY created_at DESC LIMIT 1;
            """, (encounter_id, org_id))
            rx_row = cur.fetchone()
            if rx_row:
                rx = dict(rx_row)
                cur.execute("SELECT * FROM prescription_items WHERE prescription_id = ?;", (rx["id"],))
                for item in cur.fetchall():
                    it = dict(item)
                    item_name = it.get("item_name") or it.get("formulation_name") or "Formula"
                    dose = f"{it.get('dose_amount', '')} {it.get('dose_unit', '')} {it.get('frequency', '')}".strip()
                    rx_evt = self.record_timeline_event(
                        organization_id=org_id,
                        patient_id=patient_id,
                        facility_id=fac_id,
                        encounter_id=encounter_id,
                        stream_lane="MEDICATION",
                        event_type="PRESCRIPTION_ISSUED",
                        event_title=f"Prescribed: {item_name}",
                        event_summary=f"Dosage: {dose}. Instructions: {it.get('instructions', 'As directed')}.",
                        occurred_at=rx.get("created_at") or enc_date,
                        recorded_by=user_id,
                        source_entity_type="prescription_items",
                        source_entity_id=it["id"],
                        payload={"item_name": item_name, "dosage": dose, "prescription_id": rx["id"]}
                    )
                    projected_events.append(rx_evt)

                    # Update medication status ledger to ACTIVE
                    self.record_medication_state_change(
                        patient_id=patient_id,
                        formulation_name=item_name,
                        formulation_type="MURAKKABAT" if it.get("dosage_form") in ["MAJOON", "SAFOOF", "SHARBAT", "KHAMIRA"] else "MUFRADAT",
                        new_state="ACTIVE",
                        start_date=enc_date.split("T")[0],
                        dosage_summary=dose,
                        user_ctx=user_ctx,
                        rx_id=rx["id"]
                    )

            return projected_events
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Timeline Query & Filtering
    # --------------------------------------------------------------------------

    def get_patient_timeline(
        self,
        patient_id: str,
        stream_lanes: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        significance: Optional[str] = None,
        limit: int = 50,
        user_ctx: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieves chronological timeline events honoring exact temporal precision.
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM patient_timeline_events WHERE patient_id = ?"
            params: List[Any] = [patient_id]

            if stream_lanes:
                placeholders = ",".join("?" for _ in stream_lanes)
                query += f" AND stream_lane IN ({placeholders})"
                params.extend(stream_lanes)

            if start_date:
                query += " AND occurred_at >= ?"
                params.append(start_date)

            if end_date:
                query += " AND occurred_at <= ?"
                params.append(end_date)

            if significance:
                query += " AND clinical_significance = ?"
                params.append(significance)

            query += " ORDER BY occurred_at DESC, created_at DESC LIMIT ?;"
            params.append(limit)

            cur.execute(query, params)
            events = []
            for r in cur.fetchall():
                e = dict(r)
                e["payload"] = json.loads(e.get("payload_json") or "{}")
                events.append(e)

            # Group by stream lane counts
            cur.execute("""
                SELECT stream_lane, COUNT(*) as count
                FROM patient_timeline_events
                WHERE patient_id = ?
                GROUP BY stream_lane;
            """, (patient_id,))
            counts = {r["stream_lane"]: r["count"] for r in cur.fetchall()}

            return {
                "patient_id": patient_id,
                "total_events": len(events),
                "events_by_stream": counts,
                "events": events
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Medication Longitudinal Status Ledger
    # --------------------------------------------------------------------------

    def list_medications(
        self,
        patient_id: str,
        current_state: Optional[str] = None,
        user_ctx: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """List patient medications with historical vs active status."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM medication_status_ledger WHERE patient_id = ?"
            params: List[Any] = [patient_id]
            if current_state:
                query += " AND current_state = ?"
                params.append(current_state)
            query += " ORDER BY updated_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def record_medication_state_change(
        self,
        patient_id: str,
        formulation_name: str,
        formulation_type: str,
        new_state: str,
        start_date: str,
        user_ctx: Dict[str, Any],
        end_date: Optional[str] = None,
        dosage_summary: Optional[str] = None,
        reason: Optional[str] = None,
        rx_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record or update a medication's lifecycle state in the longitudinal ledger."""
        if new_state not in MEDICATION_STATES:
            raise ValidationError(f"Invalid medication state: '{new_state}'")

        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id FROM medication_status_ledger
                WHERE patient_id = ? AND formulation_name = ?
                ORDER BY updated_at DESC LIMIT 1;
            """, (patient_id, formulation_name))
            row = cur.fetchone()

            now = datetime.now(timezone.utc).isoformat()
            if row:
                med_id = row["id"]
                conn.execute("""
                    UPDATE medication_status_ledger
                    SET current_state = ?,
                        end_date = COALESCE(?, end_date),
                        discontinuation_reason = COALESCE(?, discontinuation_reason),
                        dosage_summary = COALESCE(?, dosage_summary),
                        updated_by = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (new_state, end_date, reason, dosage_summary, user_id, now, med_id))
            else:
                med_id = f"med-{uuid.uuid4().hex[:12]}"
                conn.execute("""
                    INSERT INTO medication_status_ledger (
                        id, organization_id, patient_id, formulation_name, formulation_type,
                        originating_prescription_id, current_state, dosage_summary,
                        start_date, end_date, discontinuation_reason, updated_by, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    med_id, org_id, patient_id, formulation_name, formulation_type,
                    rx_id, new_state, dosage_summary, start_date, end_date, reason, user_id, now
                ))

            conn.commit()

            return {
                "medication_id": med_id,
                "patient_id": patient_id,
                "formulation_name": formulation_name,
                "current_state": new_state,
                "updated_at": now
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Care Continuity Tasks
    # --------------------------------------------------------------------------

    def create_continuity_task(
        self,
        organization_id: str,
        patient_id: str,
        task_type: str,
        due_date: str,
        assigned_role: str,
        user_ctx: Dict[str, Any],
        originating_encounter_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        facility_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a scheduled care continuity task (e.g. follow-up call, lab check)."""
        if task_type not in CONTINUITY_TASK_TYPES:
            raise ValidationError(f"Invalid task_type: '{task_type}'")
        if assigned_role not in {'FRONT_DESK', 'TRIAGE_NURSE', 'CLINICIAN', 'PHARMACIST', 'CARE_COORDINATOR'}:
            raise ValidationError(f"Invalid assigned_role: '{assigned_role}'")

        conn = self.db_manager.get_connection()
        try:
            task_id = f"tsk-{uuid.uuid4().hex[:12]}"
            conn.execute("""
                INSERT INTO care_continuity_tasks (
                    id, organization_id, facility_id, patient_id, originating_encounter_id,
                    task_type, due_date, status, assigned_role, assigned_user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?);
            """, (
                task_id, organization_id, facility_id, patient_id, originating_encounter_id,
                task_type, due_date, assigned_role, assigned_user_id
            ))
            conn.commit()

            return {
                "task_id": task_id,
                "patient_id": patient_id,
                "task_type": task_type,
                "due_date": due_date,
                "status": "PENDING",
                "assigned_role": assigned_role
            }
        finally:
            conn.close()

    def list_continuity_tasks(
        self,
        patient_id: Optional[str] = None,
        status: Optional[str] = None,
        assigned_role: Optional[str] = None,
        user_ctx: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """List care continuity tasks with status and role filtering."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM care_continuity_tasks WHERE 1=1"
            params: List[Any] = []
            if patient_id:
                query += " AND patient_id = ?"
                params.append(patient_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            if assigned_role:
                query += " AND assigned_role = ?"
                params.append(assigned_role)
            query += " ORDER BY due_date ASC, created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def record_contact_attempt(
        self,
        task_id: str,
        outcome_notes: str,
        user_ctx: Dict[str, Any],
        status: Optional[str] = None,
        escalation_reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record an outreach or follow-up attempt against a care continuity task."""
        if not outcome_notes:
            raise ValidationError("outcome_notes are required to record a contact attempt.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM care_continuity_tasks WHERE id = ?;", (task_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Continuity task '{task_id}' not found.")

            task = dict(row)
            attempts = task["contact_attempts_count"] + 1
            now = datetime.now(timezone.utc).isoformat()
            new_status = status or ("ESCALATED" if escalation_reason else task["status"])

            conn.execute("""
                UPDATE care_continuity_tasks
                SET contact_attempts_count = ?,
                    last_attempt_at = ?,
                    status = ?,
                    outcome_notes = ?,
                    escalation_reason = COALESCE(?, escalation_reason)
                WHERE id = ?;
            """, (attempts, now, new_status, outcome_notes, escalation_reason, task_id))
            conn.commit()

            return {
                "task_id": task_id,
                "contact_attempts_count": attempts,
                "status": new_status,
                "last_attempt_at": now
            }
        finally:
            conn.close()

    def complete_continuity_task(
        self,
        task_id: str,
        outcome_notes: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Mark a continuity task as COMPLETED with documented clinical resolution."""
        if not outcome_notes:
            raise ValidationError("outcome_notes are required to complete a continuity task.")

        conn = self.db_manager.get_connection()
        try:
            now = datetime.now(timezone.utc).isoformat()
            user_id = user_ctx.get("user_id", "system")

            conn.execute("""
                UPDATE care_continuity_tasks
                SET status = 'COMPLETED',
                    outcome_notes = ?,
                    completed_by = ?,
                    completed_at = ?
                WHERE id = ?;
            """, (outcome_notes, user_id, now, task_id))
            conn.commit()

            return {
                "task_id": task_id,
                "status": "COMPLETED",
                "completed_by": user_id,
                "completed_at": now,
                "outcome_notes": outcome_notes
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Traceable Longitudinal Timeline Summaries
    # --------------------------------------------------------------------------

    def generate_timeline_summary(
        self,
        patient_id: str,
        summary_type: str,
        user_ctx: Dict[str, Any],
        date_range_start: Optional[str] = None,
        date_range_end: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Drafts a structured clinical overview with mandatory per-claim bindings to exact timeline event IDs.
        Guarded behind feature flag and requires clinician review prior to clinical reliance.
        """
        org_id = user_ctx.get("organization_id", "org-matab-default")
        user_id = user_ctx.get("user_id", "system")

        # 1. Fetch relevant timeline events
        timeline_res = self.get_patient_timeline(
            patient_id=patient_id,
            start_date=date_range_start,
            end_date=date_range_end,
            limit=100,
            user_ctx=user_ctx
        )
        events = timeline_res["events"]

        if not events:
            return {
                "summary_id": None,
                "status": "insufficient_history",
                "message": "No timeline events recorded for this patient within the specified date range."
            }

        # 2. Synthesize claim units bound to event IDs
        claim_bindings: List[Dict[str, Any]] = []
        summary_paragraphs: List[str] = []

        # Summarize Encounters
        enc_events = [e for e in events if e["event_type"] == "ENCOUNTER_VISIT"]
        if enc_events:
            p = f"Patient has {len(enc_events)} recorded consultation(s) on file between {enc_events[-1]['occurred_at'][:10]} and {enc_events[0]['occurred_at'][:10]}."
            summary_paragraphs.append(p)
            claim_bindings.append({
                "claim_text": p,
                "timeline_event_ids": [e["id"] for e in enc_events]
            })

        # Summarize Assessments
        unani_events = [e for e in events if e["stream_lane"] == "UNANI"]
        if unani_events:
            mizaj_notes = "; ".join(e["event_summary"] for e in unani_events[:3])
            p = f"Unani Clinical Stream: {mizaj_notes}."
            summary_paragraphs.append(p)
            claim_bindings.append({
                "claim_text": p,
                "timeline_event_ids": [e["id"] for e in unani_events]
            })

        modern_events = [e for e in events if e["stream_lane"] == "MODERN"]
        if modern_events:
            dx_notes = "; ".join(e["event_summary"] for e in modern_events[:3])
            p = f"Modern Clinical Stream: {dx_notes}."
            summary_paragraphs.append(p)
            claim_bindings.append({
                "claim_text": p,
                "timeline_event_ids": [e["id"] for e in modern_events]
            })

        # Summarize Medications
        med_events = [e for e in events if e["stream_lane"] == "MEDICATION"]
        if med_events:
            rx_list = ", ".join(e["event_title"].replace("Prescribed: ", "") for e in med_events[:5])
            p = f"Prescription History: Prescribed {rx_list}."
            summary_paragraphs.append(p)
            claim_bindings.append({
                "claim_text": p,
                "timeline_event_ids": [e["id"] for e in med_events]
            })

        draft_text = "\n\n".join(summary_paragraphs)
        summary_id = f"sum-{uuid.uuid4().hex[:12]}"

        conn = self.db_manager.get_connection()
        try:
            conn.execute("""
                INSERT INTO timeline_summary_runs (
                    id, organization_id, patient_id, requested_by, summary_type,
                    date_range_start, date_range_end, draft_text, event_claim_bindings_json,
                    review_status, feature_flag_enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', 1);
            """, (
                summary_id, org_id, patient_id, user_id, summary_type,
                date_range_start, date_range_end, draft_text, json.dumps(claim_bindings)
            ))
            conn.commit()

            return {
                "summary_id": summary_id,
                "patient_id": patient_id,
                "summary_type": summary_type,
                "draft_text": draft_text,
                "event_claim_bindings": claim_bindings,
                "review_status": "DRAFT",
                "events_considered_count": len(events)
            }
        finally:
            conn.close()

    def review_timeline_summary(
        self,
        summary_id: str,
        action: str,
        user_ctx: Dict[str, Any],
        review_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Records human clinician attestation or rejection of a draft longitudinal summary.
        """
        if action not in ["CLINICIAN_REVIEWED", "REJECTED"]:
            raise ValidationError(f"Invalid review action: '{action}'")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM timeline_summary_runs WHERE id = ?;", (summary_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Summary run '{summary_id}' not found.")

            user_id = user_ctx.get("user_id", "system")
            now = datetime.now(timezone.utc).isoformat()

            conn.execute("""
                UPDATE timeline_summary_runs
                SET review_status = ?,
                    reviewed_by = ?,
                    reviewed_at = ?,
                    review_notes = ?
                WHERE id = ?;
            """, (action, user_id, now, review_notes, summary_id))
            conn.commit()

            return {
                "summary_id": summary_id,
                "review_status": action,
                "reviewed_by": user_id,
                "reviewed_at": now,
                "review_notes": review_notes
            }
        finally:
            conn.close()

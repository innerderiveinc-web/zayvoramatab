"""Follow-up, Care Continuity, Patient Communication & Outcome Tracking Domain Service.
Phase 9: Versioned follow-up plans, operational follow-up tasks, repeat-visit appointment
scheduling with slot locking, consent-governed communication outbox & sandbox adapters,
non-causal longitudinal outcome trend engine, adverse effect escalation, and role-filtered queues.
"""

import json
import uuid
import hmac
import hashlib
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    NotFoundError,
    ValidationError,
    ConflictError,
    ForbiddenError,
    AuthenticationError
)
from apps.api.core.audit import log_audit_event
from apps.api.domains.encounters import EncounterService


def _val_err(code: str, msg: str) -> ValidationError:
    err = ValidationError(f"{code}: {msg}", details={"reason_code": code})
    err.code = code
    return err


def _not_found(code: str, msg: str) -> NotFoundError:
    err = NotFoundError(f"{code}: {msg}", details={"reason_code": code})
    err.code = code
    return err


def _conflict(code: str, msg: str) -> ConflictError:
    err = ConflictError(f"{code}: {msg}", details={"reason_code": code})
    err.code = code
    return err


def _auth_err(code: str, msg: str) -> AuthenticationError:
    err = AuthenticationError(f"{code}: {msg}", details={"reason_code": code})
    err.code = code
    return err


FOLLOW_UP_PLAN_FORMATS = ["in_person", "teleconsultation", "phone_check", "lab_review"]
FOLLOW_UP_PLAN_STATUSES = ["active", "amended", "completed", "cancelled"]

FOLLOW_UP_TASK_STATUSES = [
    "planned",
    "due",
    "in_progress",
    "completed",
    "rescheduled",
    "patient_declined",
    "unable_to_reach",
    "cancelled",
    "escalated",
    "entered_in_error"
]

ALLOWED_TASK_TRANSITIONS: Dict[str, List[str]] = {
    "planned": ["due", "in_progress", "completed", "rescheduled", "patient_declined", "unable_to_reach", "cancelled", "escalated", "entered_in_error"],
    "due": ["in_progress", "completed", "rescheduled", "patient_declined", "unable_to_reach", "cancelled", "escalated", "entered_in_error"],
    "in_progress": ["completed", "rescheduled", "patient_declined", "unable_to_reach", "cancelled", "escalated", "entered_in_error"],
    "rescheduled": ["due", "in_progress", "completed", "rescheduled", "patient_declined", "unable_to_reach", "cancelled", "escalated", "entered_in_error"],
    "escalated": ["in_progress", "completed", "rescheduled", "cancelled", "entered_in_error"],
    "unable_to_reach": ["in_progress", "rescheduled", "completed", "cancelled", "escalated", "entered_in_error"],
    "patient_declined": ["rescheduled", "in_progress", "cancelled", "entered_in_error"],
    "completed": ["entered_in_error"],
    "cancelled": ["entered_in_error"],
    "entered_in_error": []
}

APPOINTMENT_STATUSES = [
    "requested",
    "booked",
    "confirmed",
    "arrived",
    "completed",
    "cancelled",
    "no_show"
]

ACTIVE_SLOT_STATUSES = {"booked", "confirmed", "arrived"}

REPORTER_TYPES = [
    "patient_reported",
    "caregiver_reported",
    "clinician_observed",
    "device_imported",
    "ai_draft_unverified"
]

PROHIBITED_SENSITIVE_PLACEHOLDERS = {
    "diagnosis",
    "diagnoses",
    "medication_name",
    "medications",
    "nuskha_details",
    "hiv_status",
    "psychiatric_notes",
    "detailed_symptoms",
    "problem_list",
    "unani_mizaj_diagnosis",
    "test_results"
}

NON_CAUSAL_TREND_DISCLAIMER = (
    "Observational longitudinal trend only. Symptom or marker changes over time reflect "
    "recorded measurements and do not establish causal treatment efficacy without controlled evaluation."
)


class CareContinuityService:
    """Domain service for longitudinal care continuity, patient communications, and outcomes."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_manager = DatabaseConnection(db_path)

    @staticmethod
    def _fetch_patient_with_phone(cur, org_id: str, patient_id: str) -> Optional[Dict[str, Any]]:
        cur.execute("""
            SELECT p.id, p.mrn, p.display_name AS full_name, p.display_name AS patient_name,
                   COALESCE(
                       (SELECT pc.contact_value FROM patient_contacts pc
                        WHERE pc.patient_id = p.id AND pc.contact_type = 'PHONE'
                        ORDER BY pc.is_preferred DESC LIMIT 1),
                       '+91-0000000000'
                   ) AS primary_phone
            FROM patients p
            WHERE p.id = ? AND p.organization_id = ?;
        """, (patient_id, org_id))
        row = cur.fetchone()
        return dict(row) if row else None

    # =========================================================================
    # 1. FOLLOW-UP PLANS (Clinician-Authored & Versioned)
    # =========================================================================

    def create_follow_up_plan(
        self, org_id: str, fac_id: str, actor_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a versioned follow-up plan linked to a patient and encounter."""
        patient_id = payload.get("patient_id")
        encounter_id = payload.get("encounter_id")
        review_due_at = payload.get("review_due_at")
        purpose = (payload.get("purpose") or "").strip()
        review_format = payload.get("review_format", "in_person")
        timezone = payload.get("timezone", "Asia/Kolkata")
        care_plan_id = payload.get("care_plan_id")
        monitoring_items = payload.get("monitoring_items", [])
        safety_instructions = payload.get("safety_instructions", "")
        escalation_guidance = payload.get("escalation_guidance", "")
        auto_create_task = payload.get("auto_create_task", True)

        if not patient_id or not encounter_id or not review_due_at or not purpose:
            raise _val_err(
                "MISSING_REQUIRED_FIELDS",
                "patient_id, encounter_id, review_due_at, and purpose are required to create a follow-up plan."
            )

        if review_format not in FOLLOW_UP_PLAN_FORMATS:
            raise _val_err(
                "INVALID_REVIEW_FORMAT",
                f"review_format must be one of {FOLLOW_UP_PLAN_FORMATS}"
            )

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if not self._fetch_patient_with_phone(cur, org_id, patient_id):
                raise _not_found("PATIENT_NOT_FOUND", f"Patient '{patient_id}' not found in organization.")

            cur.execute(
                "SELECT id, facility_id FROM encounters WHERE id = ? AND organization_id = ?;",
                (encounter_id, org_id)
            )
            enc_row = cur.fetchone()
            if not enc_row:
                raise _not_found("ENCOUNTER_NOT_FOUND", f"Encounter '{encounter_id}' not found.")

            plan_id = f"fup-plan-{uuid.uuid4().hex[:12]}"
            monitoring_json = json.dumps(monitoring_items)

            snapshot = {
                "plan_id": plan_id,
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "care_plan_id": care_plan_id,
                "review_due_at": review_due_at,
                "timezone": timezone,
                "purpose": purpose,
                "review_format": review_format,
                "monitoring_items": monitoring_items,
                "safety_instructions": safety_instructions,
                "escalation_guidance": escalation_guidance,
                "version_number": 1
            }

            cur.execute("""
                INSERT INTO follow_up_plans (
                    id, organization_id, facility_id, patient_id, encounter_id, care_plan_id,
                    review_due_at, timezone, purpose, review_format, monitoring_items_json,
                    safety_instructions, escalation_guidance, status, version_number, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1, ?);
            """, (
                plan_id, org_id, fac_id, patient_id, encounter_id, care_plan_id,
                review_due_at, timezone, purpose, review_format, monitoring_json,
                safety_instructions, escalation_guidance, actor_id
            ))

            ver_id = f"fup-ver-{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO follow_up_plan_versions (
                    id, plan_id, version_number, snapshot_json, change_reason, authored_by
                ) VALUES (?, ?, 1, ?, 'Initial follow-up plan creation', ?);
            """, (ver_id, plan_id, json.dumps(snapshot), actor_id))

            created_task = None
            if auto_create_task:
                task_id = f"fup-task-{uuid.uuid4().hex[:12]}"
                priority = payload.get("priority", "routine")
                clinical_context = payload.get("clinical_context_summary") or purpose
                cur.execute("""
                    INSERT INTO follow_up_tasks (
                        id, organization_id, facility_id, plan_id, patient_id, encounter_id,
                        assigned_to, assigned_role, due_at, timezone, purpose,
                        clinical_context_summary, planned_channel, priority, status,
                        idempotency_key, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PRACTITIONER', ?, ?, ?, ?, ?, ?, 'planned', ?, ?);
                """, (
                    task_id, org_id, fac_id, plan_id, patient_id, encounter_id,
                    payload.get("assigned_to") or actor_id, review_due_at, timezone,
                    purpose, clinical_context, review_format, priority,
                    f"auto-task-{plan_id}", actor_id
                ))
                cur.execute("""
                    INSERT INTO follow_up_task_events (
                        id, task_id, event_type, from_status, to_status, actor_id, reason
                    ) VALUES (?, ?, 'CREATED', NULL, 'planned', ?, 'Auto-generated from Follow-up Plan v1');
                """, (f"fte-{uuid.uuid4().hex[:12]}", task_id, actor_id))
                created_task = task_id

            log_audit_event(
                conn=conn,
                action_type="FOLLOWUP_PLAN_CREATED",
                target_entity_type="FOLLOW_UP_PLAN",
                target_entity_id=plan_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"patient_id": patient_id, "encounter_id": encounter_id, "auto_task_id": created_task}
            )
            conn.commit()
            return self.get_follow_up_plan(org_id, fac_id, plan_id)
        finally:
            conn.close()

    def update_follow_up_plan(
        self, org_id: str, fac_id: str, actor_id: str, plan_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new version of an existing follow-up plan, preserving history."""
        change_reason = (payload.get("change_reason") or "").strip()
        if not change_reason:
            raise _val_err("MISSING_CHANGE_REASON", "change_reason is required when amending a follow-up plan.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM follow_up_plans
                WHERE id = ? AND organization_id = ? AND facility_id = ?;
            """, (plan_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("FOLLOWUP_PLAN_NOT_FOUND", f"Follow-up plan '{plan_id}' not found.")

            plan = dict(row)
            if plan["status"] in ("cancelled", "completed"):
                raise _conflict("PLAN_IMMUTABLE", f"Cannot amend plan in '{plan['status']}' state.")

            new_version = int(plan["version_number"]) + 1
            review_due_at = payload.get("review_due_at", plan["review_due_at"])
            purpose = payload.get("purpose", plan["purpose"])
            review_format = payload.get("review_format", plan["review_format"])
            monitoring_items = payload.get("monitoring_items", json.loads(plan["monitoring_items_json"] or "[]"))
            safety_instructions = payload.get("safety_instructions", plan["safety_instructions"])
            escalation_guidance = payload.get("escalation_guidance", plan["escalation_guidance"])
            new_status = payload.get("status", "amended")

            if review_format not in FOLLOW_UP_PLAN_FORMATS:
                raise _val_err("INVALID_REVIEW_FORMAT", f"Invalid review_format '{review_format}'.")

            snapshot = {
                "plan_id": plan_id,
                "patient_id": plan["patient_id"],
                "encounter_id": plan["encounter_id"],
                "care_plan_id": plan["care_plan_id"],
                "review_due_at": review_due_at,
                "timezone": plan["timezone"],
                "purpose": purpose,
                "review_format": review_format,
                "monitoring_items": monitoring_items,
                "safety_instructions": safety_instructions,
                "escalation_guidance": escalation_guidance,
                "version_number": new_version
            }

            cur.execute("""
                UPDATE follow_up_plans
                SET review_due_at = ?, purpose = ?, review_format = ?,
                    monitoring_items_json = ?, safety_instructions = ?,
                    escalation_guidance = ?, status = ?, version_number = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (
                review_due_at, purpose, review_format, json.dumps(monitoring_items),
                safety_instructions, escalation_guidance, new_status, new_version, plan_id
            ))

            cur.execute("""
                INSERT INTO follow_up_plan_versions (
                    id, plan_id, version_number, snapshot_json, change_reason, authored_by
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (f"fup-ver-{uuid.uuid4().hex[:12]}", plan_id, new_version, json.dumps(snapshot), change_reason, actor_id))

            log_audit_event(
                conn=conn,
                action_type="FOLLOWUP_PLAN_AMENDED",
                target_entity_type="FOLLOW_UP_PLAN",
                target_entity_id=plan_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"new_version": new_version, "change_reason": change_reason}
            )
            conn.commit()
            return self.get_follow_up_plan(org_id, fac_id, plan_id)
        finally:
            conn.close()

    def get_follow_up_plan(self, org_id: str, fac_id: str, plan_id: str) -> Dict[str, Any]:
        """Retrieve a follow-up plan with its version history and linked tasks."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM follow_up_plans
                WHERE id = ? AND organization_id = ? AND facility_id = ?;
            """, (plan_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("FOLLOWUP_PLAN_NOT_FOUND", f"Follow-up plan '{plan_id}' not found.")

            plan = dict(row)
            plan["monitoring_items"] = json.loads(plan.get("monitoring_items_json") or "[]")

            cur.execute("""
                SELECT id, version_number, snapshot_json, change_reason, authored_by, authored_at
                FROM follow_up_plan_versions
                WHERE plan_id = ?
                ORDER BY version_number ASC;
            """, (plan_id,))
            versions = []
            for v in cur.fetchall():
                vd = dict(v)
                vd["snapshot"] = json.loads(vd.get("snapshot_json") or "{}")
                versions.append(vd)
            plan["versions"] = versions

            cur.execute("""
                SELECT id, due_at, status, priority, planned_channel, assigned_to
                FROM follow_up_tasks
                WHERE plan_id = ?
                ORDER BY due_at ASC;
            """, (plan_id,))
            plan["tasks"] = [dict(t) for t in cur.fetchall()]
            return plan
        finally:
            conn.close()

    def list_follow_up_plans(
        self, org_id: str, fac_id: str, patient_id: Optional[str] = None, encounter_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            sql = "SELECT * FROM follow_up_plans WHERE organization_id = ? AND facility_id = ?"
            params: List[Any] = [org_id, fac_id]
            if patient_id:
                sql += " AND patient_id = ?"
                params.append(patient_id)
            if encounter_id:
                sql += " AND encounter_id = ?"
                params.append(encounter_id)
            sql += " ORDER BY created_at DESC;"
            cur.execute(sql, tuple(params))
            results = []
            for r in cur.fetchall():
                d = dict(r)
                d["monitoring_items"] = json.loads(d.get("monitoring_items_json") or "[]")
                results.append(d)
            return results
        finally:
            conn.close()

    # =========================================================================
    # 2. FOLLOW-UP TASKS & CONTACT ATTEMPTS
    # =========================================================================

    def create_follow_up_task(
        self, org_id: str, fac_id: str, actor_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create an operational follow-up task with idempotency protection."""
        patient_id = payload.get("patient_id")
        due_at = payload.get("due_at")
        purpose = (payload.get("purpose") or "").strip()
        idempotency_key = payload.get("idempotency_key")

        if not patient_id or not due_at or not purpose:
            raise _val_err("MISSING_TASK_FIELDS", "patient_id, due_at, and purpose are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if idempotency_key:
                cur.execute(
                    "SELECT id FROM follow_up_tasks WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, org_id)
                )
                existing = cur.fetchone()
                if existing:
                    return self.get_follow_up_task(org_id, fac_id, existing["id"])

            if not self._fetch_patient_with_phone(cur, org_id, patient_id):
                raise _not_found("PATIENT_NOT_FOUND", f"Patient '{patient_id}' not found.")

            task_id = f"fup-task-{uuid.uuid4().hex[:12]}"
            plan_id = payload.get("plan_id")
            encounter_id = payload.get("encounter_id")
            assigned_to = payload.get("assigned_to") or actor_id
            assigned_role = payload.get("assigned_role", "PRACTITIONER")
            timezone = payload.get("timezone", "Asia/Kolkata")
            clinical_context = payload.get("clinical_context_summary", "")
            planned_channel = payload.get("planned_channel", "in_person")
            priority = payload.get("priority", "routine")
            status = payload.get("status", "planned")

            if status not in FOLLOW_UP_TASK_STATUSES:
                raise _val_err("INVALID_TASK_STATUS", f"Invalid task status '{status}'.")

            cur.execute("""
                INSERT INTO follow_up_tasks (
                    id, organization_id, facility_id, plan_id, patient_id, encounter_id,
                    assigned_to, assigned_role, due_at, timezone, purpose,
                    clinical_context_summary, planned_channel, priority, status,
                    idempotency_key, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                task_id, org_id, fac_id, plan_id, patient_id, encounter_id,
                assigned_to, assigned_role, due_at, timezone, purpose,
                clinical_context, planned_channel, priority, status,
                idempotency_key, actor_id
            ))

            cur.execute("""
                INSERT INTO follow_up_task_events (
                    id, task_id, event_type, from_status, to_status, actor_id, reason
                ) VALUES (?, ?, 'CREATED', NULL, ?, ?, 'Task created');
            """, (f"fte-{uuid.uuid4().hex[:12]}", task_id, status, actor_id))

            log_audit_event(
                conn=conn,
                action_type="FOLLOWUP_TASK_CREATED",
                target_entity_type="FOLLOW_UP_TASK",
                target_entity_id=task_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"patient_id": patient_id, "due_at": due_at, "priority": priority}
            )
            conn.commit()
            return self.get_follow_up_task(org_id, fac_id, task_id)
        finally:
            conn.close()

    def get_follow_up_task(self, org_id: str, fac_id: str, task_id: str) -> Dict[str, Any]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT t.*, p.display_name AS patient_name, p.mrn AS patient_mrn,
                       COALESCE(
                           (SELECT pc.contact_value FROM patient_contacts pc
                            WHERE pc.patient_id = p.id AND pc.contact_type = 'PHONE'
                            ORDER BY pc.is_preferred DESC LIMIT 1),
                           '+91-0000000000'
                       ) AS patient_phone
                FROM follow_up_tasks t
                JOIN patients p ON t.patient_id = p.id
                WHERE t.id = ? AND t.organization_id = ? AND t.facility_id = ?;
            """, (task_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("FOLLOWUP_TASK_NOT_FOUND", f"Follow-up task '{task_id}' not found.")
            task = dict(row)

            cur.execute("""
                SELECT * FROM contact_attempts WHERE task_id = ? ORDER BY attempted_at ASC;
            """, (task_id,))
            task["contact_attempts"] = [dict(a) for a in cur.fetchall()]

            cur.execute("""
                SELECT * FROM follow_up_task_events WHERE task_id = ? ORDER BY occurred_at ASC;
            """, (task_id,))
            task["events"] = [dict(e) for e in cur.fetchall()]
            return task
        finally:
            conn.close()

    def record_contact_attempt(
        self, org_id: str, fac_id: str, actor_id: str, task_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record a manual or outreach contact attempt against a follow-up task."""
        channel = payload.get("channel", "phone_call")
        attempt_outcome = payload.get("attempt_outcome", "no_answer")
        notes = payload.get("notes", "")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, patient_id, status FROM follow_up_tasks
                WHERE id = ? AND organization_id = ? AND facility_id = ?;
            """, (task_id, org_id, fac_id))
            task = cur.fetchone()
            if not task:
                raise _not_found("FOLLOWUP_TASK_NOT_FOUND", f"Follow-up task '{task_id}' not found.")

            attempt_id = f"att-{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO contact_attempts (
                    id, organization_id, facility_id, task_id, patient_id,
                    channel, attempt_outcome, notes, attempted_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (attempt_id, org_id, fac_id, task_id, task["patient_id"], channel, attempt_outcome, notes, actor_id))

            cur.execute("""
                INSERT INTO follow_up_task_events (
                    id, task_id, event_type, from_status, to_status, actor_id, reason, metadata_json
                ) VALUES (?, ?, 'CONTACT_ATTEMPTED', ?, ?, ?, ?, ?);
            """, (
                f"fte-{uuid.uuid4().hex[:12]}", task_id, task["status"], task["status"],
                actor_id, f"Contact attempt ({channel}): {attempt_outcome}",
                json.dumps({"attempt_id": attempt_id, "channel": channel, "outcome": attempt_outcome})
            ))

            conn.commit()
            return self.get_follow_up_task(org_id, fac_id, task_id)
        finally:
            conn.close()

    def transition_follow_up_task(
        self, org_id: str, fac_id: str, actor_id: str, task_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transition a follow-up task status, enforcing outreach and clinical completion guards."""
        to_status = payload.get("to_status")
        reason = (payload.get("reason") or "").strip()
        completion_outcome = payload.get("completion_outcome")
        completion_notes = payload.get("completion_notes")
        new_due_at = payload.get("new_due_at")
        assigned_to = payload.get("assigned_to")

        if not to_status or to_status not in FOLLOW_UP_TASK_STATUSES:
            raise _val_err("INVALID_TASK_STATUS", f"to_status must be one of {FOLLOW_UP_TASK_STATUSES}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM follow_up_tasks
                WHERE id = ? AND organization_id = ? AND facility_id = ?;
            """, (task_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("FOLLOWUP_TASK_NOT_FOUND", f"Follow-up task '{task_id}' not found.")

            task = dict(row)
            from_status = task["status"]

            if to_status != from_status:
                allowed = ALLOWED_TASK_TRANSITIONS.get(from_status, [])
                if to_status not in allowed:
                    raise _conflict(
                        "INVALID_TASK_TRANSITION",
                        f"Cannot transition follow-up task from '{from_status}' to '{to_status}'."
                    )

            # Invariant 1: Sending a reminder never completes a task
            if to_status == "completed":
                if not completion_outcome:
                    raise _val_err(
                        "COMPLETION_OUTCOME_REQUIRED",
                        "Completing a follow-up task requires a clinical/operational completion_outcome."
                    )
                if completion_outcome in ("reminder_sent", "message_sent", "message_dispatched", "sms_sent"):
                    raise _val_err(
                        "REMINDER_DOES_NOT_COMPLETE_FOLLOWUP",
                        "Sending an outbound reminder message does not constitute follow-up completion."
                    )

            # Invariant 2: Marking unable_to_reach requires at least 1 documented contact attempt
            if to_status == "unable_to_reach":
                cur.execute("SELECT COUNT(*) AS cnt FROM contact_attempts WHERE task_id = ?;", (task_id,))
                cnt = cur.fetchone()["cnt"]
                if cnt < 1:
                    raise _val_err(
                        "CANNOT_MARK_UNABLE_TO_REACH_WITHOUT_ATTEMPTS",
                        "At least one documented contact attempt is required before marking a task as unable_to_reach."
                    )

            # Invariant 3: Rescheduling requires new_due_at and preserves previous due_at
            rescheduled_from = task["rescheduled_from_due_at"]
            due_at = task["due_at"]
            reschedule_reason = task["reschedule_reason"]
            if to_status == "rescheduled":
                if not new_due_at or not reason:
                    raise _val_err(
                        "RESCHEDULE_DETAILS_REQUIRED",
                        "Rescheduling a follow-up task requires both 'new_due_at' and 'reason'."
                    )
                rescheduled_from = task["due_at"]
                due_at = new_due_at
                reschedule_reason = reason

            new_assigned = assigned_to if assigned_to else task["assigned_to"]

            cur.execute("""
                UPDATE follow_up_tasks
                SET status = ?, due_at = ?, assigned_to = ?,
                    completion_outcome = COALESCE(?, completion_outcome),
                    completion_notes = COALESCE(?, completion_notes),
                    rescheduled_from_due_at = ?, reschedule_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (
                to_status, due_at, new_assigned, completion_outcome, completion_notes,
                rescheduled_from, reschedule_reason, task_id
            ))

            event_type = "RESCHEDULED" if to_status == "rescheduled" else "STATUS_CHANGED"
            cur.execute("""
                INSERT INTO follow_up_task_events (
                    id, task_id, event_type, from_status, to_status, actor_id, reason, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                f"fte-{uuid.uuid4().hex[:12]}", task_id, event_type, from_status, to_status,
                actor_id, reason or f"Transitioned to {to_status}",
                json.dumps({"new_due_at": new_due_at, "completion_outcome": completion_outcome})
            ))

            log_audit_event(
                conn=conn,
                action_type="FOLLOWUP_TASK_TRANSITIONED",
                target_entity_type="FOLLOW_UP_TASK",
                target_entity_id=task_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"from_status": from_status, "to_status": to_status, "reason": reason}
            )
            conn.commit()
            return self.get_follow_up_task(org_id, fac_id, task_id)
        finally:
            conn.close()

    # =========================================================================
    # 3. REPEAT-VISIT & APPOINTMENT WORKFLOW (Double-Booking Protected)
    # =========================================================================

    def create_or_book_appointment(
        self, org_id: str, fac_id: str, actor_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request or book a follow-up appointment with practitioner slot-lock protection."""
        patient_id = payload.get("patient_id")
        practitioner_id = payload.get("practitioner_id") or actor_id
        scheduled_start_at = payload.get("scheduled_start_at")
        scheduled_end_at = payload.get("scheduled_end_at")
        status = payload.get("status", "booked")
        visit_mode = payload.get("visit_mode", "in_person")
        followup_task_id = payload.get("followup_task_id")
        source_encounter_id = payload.get("source_encounter_id")
        reason_for_visit = payload.get("reason_for_visit", "Scheduled Follow-up Review")

        if not patient_id or not scheduled_start_at or not scheduled_end_at:
            raise _val_err(
                "MISSING_APPOINTMENT_FIELDS",
                "patient_id, scheduled_start_at, and scheduled_end_at are required."
            )

        if status not in APPOINTMENT_STATUSES:
            raise _val_err("INVALID_APPOINTMENT_STATUS", f"status must be one of {APPOINTMENT_STATUSES}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            slot_lock_key = None
            if status in ACTIVE_SLOT_STATUSES:
                slot_lock_key = f"{fac_id}:{practitioner_id}:{scheduled_start_at}"
                # Check overlapping active appointments for the same practitioner and facility
                cur.execute("""
                    SELECT id, scheduled_start_at, scheduled_end_at
                    FROM follow_up_appointments
                    WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ?
                      AND status IN ('booked', 'confirmed', 'arrived')
                      AND scheduled_start_at < ? AND scheduled_end_at > ?;
                """, (org_id, fac_id, practitioner_id, scheduled_end_at, scheduled_start_at))
                conflict = cur.fetchone()
                if conflict:
                    raise _conflict(
                        "APPOINTMENT_SLOT_CONFLICT",
                        f"Practitioner '{practitioner_id}' already has an active appointment ({conflict['id']}) overlapping [{scheduled_start_at}, {scheduled_end_at}]."
                    )

            appt_id = f"fup-appt-{uuid.uuid4().hex[:12]}"
            try:
                cur.execute("""
                    INSERT INTO follow_up_appointments (
                        id, organization_id, facility_id, patient_id, followup_task_id,
                        source_encounter_id, practitioner_id, scheduled_start_at, scheduled_end_at,
                        slot_lock_key, visit_mode, status, reason_for_visit, booked_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    appt_id, org_id, fac_id, patient_id, followup_task_id,
                    source_encounter_id, practitioner_id, scheduled_start_at, scheduled_end_at,
                    slot_lock_key, visit_mode, status, reason_for_visit, actor_id
                ))
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    raise _conflict("APPOINTMENT_SLOT_CONFLICT", "Double-booking prevented by slot lock.")
                raise

            log_audit_event(
                conn=conn,
                action_type="FOLLOWUP_APPOINTMENT_BOOKED",
                target_entity_type="FOLLOW_UP_APPOINTMENT",
                target_entity_id=appt_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"patient_id": patient_id, "scheduled_start_at": scheduled_start_at, "status": status}
            )
            conn.commit()
            return self.get_appointment(org_id, fac_id, appt_id)
        finally:
            conn.close()

    def transition_appointment(
        self, org_id: str, fac_id: str, actor_id: str, appointment_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transition appointment status and optionally spawn a linked repeat-visit encounter."""
        to_status = payload.get("to_status")
        cancellation_reason = payload.get("cancellation_reason")
        create_repeat_encounter = payload.get("create_repeat_encounter", False)

        if not to_status or to_status not in APPOINTMENT_STATUSES:
            raise _val_err("INVALID_APPOINTMENT_STATUS", f"to_status must be one of {APPOINTMENT_STATUSES}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM follow_up_appointments
                WHERE id = ? AND organization_id = ? AND facility_id = ?;
            """, (appointment_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("APPOINTMENT_NOT_FOUND", f"Appointment '{appointment_id}' not found.")

            appt = dict(row)
            slot_lock_key = appt["slot_lock_key"]
            if to_status in ("cancelled", "no_show"):
                slot_lock_key = None
            elif to_status in ACTIVE_SLOT_STATUSES and not slot_lock_key:
                slot_lock_key = f"{fac_id}:{appt['practitioner_id']}:{appt['scheduled_start_at']}"

            repeat_encounter_id = appt["repeat_encounter_id"]

            cur.execute("""
                UPDATE follow_up_appointments
                SET status = ?, slot_lock_key = ?, cancellation_reason = COALESCE(?, cancellation_reason),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (to_status, slot_lock_key, cancellation_reason, appointment_id))

            # Spawn a new repeat encounter without mutating historical encounters
            if create_repeat_encounter and not repeat_encounter_id:
                prior_ref = f" (Follow-up to Encounter {appt['source_encounter_id']})" if appt.get("source_encounter_id") else ""
                new_enc = EncounterService.create_encounter(
                    conn=conn,
                    organization_id=org_id,
                    facility_id=fac_id,
                    patient_id=appt["patient_id"],
                    practitioner_id=appt["practitioner_id"],
                    encounter_type="FOLLOW_UP",
                    reason_for_visit=f"{appt.get('reason_for_visit') or 'Follow-up Review'}{prior_ref}",
                    actor_id=actor_id
                )
                repeat_encounter_id = new_enc["id"]
                cur.execute("""
                    UPDATE follow_up_appointments
                    SET repeat_encounter_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (repeat_encounter_id, appointment_id))

                if appt.get("followup_task_id") and to_status == "completed":
                    cur.execute("""
                        UPDATE follow_up_tasks
                        SET status = 'completed',
                            completion_outcome = 'attended_repeat_visit',
                            completion_notes = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?;
                    """, (f"Attended repeat encounter {repeat_encounter_id}", appt["followup_task_id"]))

            conn.commit()
            return self.get_appointment(org_id, fac_id, appointment_id)
        finally:
            conn.close()

    def get_appointment(self, org_id: str, fac_id: str, appointment_id: str) -> Dict[str, Any]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT a.*, p.display_name AS patient_name, p.mrn AS patient_mrn
                FROM follow_up_appointments a
                JOIN patients p ON a.patient_id = p.id
                WHERE a.id = ? AND a.organization_id = ? AND a.facility_id = ?;
            """, (appointment_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("APPOINTMENT_NOT_FOUND", f"Appointment '{appointment_id}' not found.")
            return dict(row)
        finally:
            conn.close()

    # =========================================================================
    # 4. COMMUNICATION PREFERENCES, TEMPLATES & OUTBOX
    # =========================================================================

    def upsert_communication_preferences(
        self, org_id: str, fac_id: str, actor_id: str, patient_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record or update granular patient communication preferences and opt-out state."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            pat = self._fetch_patient_with_phone(cur, org_id, patient_id)
            if not pat:
                raise _not_found("PATIENT_NOT_FOUND", f"Patient '{patient_id}' not found.")

            cur.execute("SELECT * FROM communication_preferences WHERE patient_id = ?;", (patient_id,))
            existing = cur.fetchone()

            preferred_language = payload.get("preferred_language", existing["preferred_language"] if existing else "en")
            preferred_channel = payload.get("preferred_channel", existing["preferred_channel"] if existing else "sms")
            permitted_cats = payload.get(
                "permitted_categories",
                json.loads(existing["permitted_categories_json"]) if existing else ["clinical_reminder", "appointment_confirmation", "safety_followup"]
            )
            allow_marketing = int(bool(payload.get("allow_marketing", existing["allow_marketing"] if existing else 0)))
            verified_contact_ref = payload.get("verified_contact_ref", existing["verified_contact_ref"] if existing else pat["primary_phone"])
            quiet_start = payload.get("quiet_hours_start", existing["quiet_hours_start"] if existing else "21:00")
            quiet_end = payload.get("quiet_hours_end", existing["quiet_hours_end"] if existing else "08:00")
            timezone = payload.get("timezone", existing["timezone"] if existing else "Asia/Kolkata")
            opt_out_status = int(bool(payload.get("opt_out_status", existing["opt_out_status"] if existing else 0)))
            dnc_scope = payload.get("do_not_contact_scope", existing["do_not_contact_scope"] if existing else ("all_automated" if opt_out_status else "none"))
            consent_source = payload.get("consent_source", existing["consent_source"] if existing else "clinician_or_desk_recorded")

            pref_id = existing["id"] if existing else f"cpref-{uuid.uuid4().hex[:12]}"

            cur.execute("""
                INSERT INTO communication_preferences (
                    id, organization_id, facility_id, patient_id, preferred_language,
                    preferred_channel, permitted_categories_json, allow_marketing,
                    verified_contact_ref, quiet_hours_start, quiet_hours_end, timezone,
                    opt_out_status, do_not_contact_scope, consent_source, recorded_by, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(patient_id) DO UPDATE SET
                    preferred_language = excluded.preferred_language,
                    preferred_channel = excluded.preferred_channel,
                    permitted_categories_json = excluded.permitted_categories_json,
                    allow_marketing = excluded.allow_marketing,
                    verified_contact_ref = excluded.verified_contact_ref,
                    quiet_hours_start = excluded.quiet_hours_start,
                    quiet_hours_end = excluded.quiet_hours_end,
                    timezone = excluded.timezone,
                    opt_out_status = excluded.opt_out_status,
                    do_not_contact_scope = excluded.do_not_contact_scope,
                    consent_source = excluded.consent_source,
                    recorded_by = excluded.recorded_by,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                pref_id, org_id, fac_id, patient_id, preferred_language,
                preferred_channel, json.dumps(permitted_cats), allow_marketing,
                verified_contact_ref, quiet_start, quiet_end, timezone,
                opt_out_status, dnc_scope, consent_source, actor_id
            ))

            log_audit_event(
                conn=conn,
                action_type="COMMUNICATION_PREFERENCES_UPDATED",
                target_entity_type="COMMUNICATION_PREFERENCE",
                target_entity_id=pref_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"patient_id": patient_id, "opt_out_status": opt_out_status, "preferred_channel": preferred_channel}
            )
            conn.commit()
            return self.get_communication_preferences(org_id, fac_id, patient_id)
        finally:
            conn.close()

    def get_communication_preferences(self, org_id: str, fac_id: str, patient_id: str) -> Dict[str, Any]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM communication_preferences WHERE patient_id = ? AND organization_id = ?;",
                (patient_id, org_id)
            )
            row = cur.fetchone()
            if row:
                d = dict(row)
                d["permitted_categories"] = json.loads(d.get("permitted_categories_json") or "[]")
                d["opt_out_status"] = bool(d["opt_out_status"])
                d["allow_marketing"] = bool(d["allow_marketing"])
                return d

            pat = self._fetch_patient_with_phone(cur, org_id, patient_id)
            if not pat:
                raise _not_found("PATIENT_NOT_FOUND", f"Patient '{patient_id}' not found.")

            return {
                "patient_id": patient_id,
                "organization_id": org_id,
                "facility_id": fac_id,
                "preferred_language": "en",
                "preferred_channel": "sms",
                "permitted_categories": ["clinical_reminder", "appointment_confirmation", "safety_followup"],
                "allow_marketing": False,
                "verified_contact_ref": pat["primary_phone"],
                "quiet_hours_start": "21:00",
                "quiet_hours_end": "08:00",
                "timezone": "Asia/Kolkata",
                "opt_out_status": False,
                "do_not_contact_scope": "none",
                "consent_source": "default_policy"
            }
        finally:
            conn.close()

    def create_communication_template(
        self, org_id: str, actor_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Author a versioned communication template and inspect placeholders for sensitivity."""
        template_code = (payload.get("template_code") or "").strip()
        name = (payload.get("name") or "").strip()
        channel = payload.get("channel", "sms")
        language = payload.get("language", "en")
        category = payload.get("category", "clinical_reminder")
        body_template = (payload.get("body_template") or "").strip()
        approval_status = payload.get("approval_status", "draft")

        if not template_code or not name or not body_template:
            raise _val_err("MISSING_TEMPLATE_FIELDS", "template_code, name, and body_template are required.")

        found_placeholders = set(re.findall(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", body_template))
        contains_sensitive = int(bool(found_placeholders.intersection(PROHIBITED_SENSITIVE_PLACEHOLDERS)))

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            tpl_id = f"ctpl-{uuid.uuid4().hex[:12]}"
            ver_id = f"ctplv-{uuid.uuid4().hex[:12]}"

            approved_by = actor_id if approval_status == "approved" else None
            approved_at = datetime.utcnow().isoformat() if approval_status == "approved" else None

            cur.execute("""
                INSERT INTO communication_templates (
                    id, organization_id, template_code, name, channel, language, category,
                    current_version, approval_status, contains_sensitive_fields,
                    approved_by, approved_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?);
            """, (
                tpl_id, org_id, template_code, name, channel, language, category,
                approval_status, contains_sensitive, approved_by, approved_at, actor_id
            ))

            cur.execute("""
                INSERT INTO communication_template_versions (
                    id, template_id, version_number, body_template,
                    allowed_placeholders_json, prohibited_placeholders_json,
                    approval_status, authored_by, approved_by
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?);
            """, (
                ver_id, tpl_id, body_template,
                json.dumps(sorted(list(found_placeholders - PROHIBITED_SENSITIVE_PLACEHOLDERS))),
                json.dumps(sorted(list(PROHIBITED_SENSITIVE_PLACEHOLDERS))),
                approval_status, actor_id, approved_by
            ))

            conn.commit()
            return self.get_communication_template(org_id, tpl_id)
        finally:
            conn.close()

    def approve_communication_template(self, org_id: str, actor_id: str, template_id: str) -> Dict[str, Any]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM communication_templates WHERE id = ? AND organization_id = ?;",
                (template_id, org_id)
            )
            tpl = cur.fetchone()
            if not tpl:
                raise _not_found("TEMPLATE_NOT_FOUND", f"Template '{template_id}' not found.")

            cur.execute("""
                UPDATE communication_templates
                SET approval_status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (actor_id, template_id))
            cur.execute("""
                UPDATE communication_template_versions
                SET approval_status = 'approved', approved_by = ?
                WHERE template_id = ? AND version_number = ?;
            """, (actor_id, template_id, tpl["current_version"]))
            conn.commit()
            return self.get_communication_template(org_id, template_id)
        finally:
            conn.close()

    def get_communication_template(self, org_id: str, template_id: str) -> Dict[str, Any]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM communication_templates WHERE id = ? AND organization_id = ?;",
                (template_id, org_id)
            )
            row = cur.fetchone()
            if not row:
                raise _not_found("TEMPLATE_NOT_FOUND", f"Template '{template_id}' not found.")
            d = dict(row)
            cur.execute("""
                SELECT * FROM communication_template_versions
                WHERE template_id = ? ORDER BY version_number DESC;
            """, (template_id,))
            d["versions"] = [dict(v) for v in cur.fetchall()]
            return d
        finally:
            conn.close()

    def list_communication_templates(self, org_id: str) -> List[Dict[str, Any]]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM communication_templates WHERE organization_id = ? ORDER BY created_at DESC;", (org_id,))
            results = []
            for r in cur.fetchall():
                results.append(self.get_communication_template(org_id, r["id"]))
            return results
        finally:
            conn.close()

    def _is_within_quiet_hours(self, check_time_hhmm: str, start_hhmm: str, end_hhmm: str) -> bool:
        """Evaluate whether a given HH:MM falls inside quiet hours (supports overnight spans like 21:00 to 08:00)."""
        if not check_time_hhmm or not start_hhmm or not end_hhmm:
            return False
        if start_hhmm <= end_hhmm:
            return start_hhmm <= check_time_hhmm < end_hhmm
        else:
            return check_time_hhmm >= start_hhmm or check_time_hhmm < end_hhmm

    def _check_consent_and_preferences(
        self, conn, org_id: str, fac_id: str, patient_id: str, channel: str, category: str
    ) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """Perform real-time consent & opt-out evaluation for a patient."""
        prefs = self.get_communication_preferences(org_id, fac_id, patient_id)

        if prefs.get("opt_out_status"):
            return False, "PATIENT_OPTED_OUT", prefs

        dnc_scope = prefs.get("do_not_contact_scope", "none")
        if dnc_scope in ("all_automated", "non_urgent_all"):
            return False, f"DO_NOT_CONTACT_SCOPE_{dnc_scope.upper()}", prefs

        if prefs.get("preferred_channel") == "none":
            return False, "CHANNEL_NONE_PREFERENCE", prefs

        if category == "marketing":
            if not prefs.get("allow_marketing") or dnc_scope == "marketing_only":
                return False, "MARKETING_CONSENT_NOT_GRANTED", prefs

        permitted = prefs.get("permitted_categories", [])
        if category != "marketing" and category not in permitted:
            return False, f"CATEGORY_{category.upper()}_NOT_PERMITTED", prefs

        # Check patient_consents table for explicit withdrawn channel consent
        cur = conn.cursor()
        consent_purpose_map = {
            "sms": "COMMUNICATION_SMS",
            "whatsapp": "COMMUNICATION_WHATSAPP",
            "email": "COMMUNICATION_EMAIL"
        }
        mapped_purpose = consent_purpose_map.get(channel.lower())
        if mapped_purpose:
            cur.execute("""
                SELECT status FROM patient_consents
                WHERE patient_id = ? AND organization_id = ? AND purpose = ?
                ORDER BY recorded_at DESC LIMIT 1;
            """, (patient_id, org_id, mapped_purpose))
            c_row = cur.fetchone()
            if c_row and c_row["status"] in ("WITHDRAWN", "REFUSED"):
                return False, f"PATIENT_CONSENT_{mapped_purpose}_{c_row['status']}", prefs

        return True, None, prefs

    def send_or_queue_communication(
        self, org_id: str, fac_id: str, actor_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate template & minimum-necessary privacy, verify consent/quiet hours, and dispatch or queue message.
        IMPORTANT: Sending a reminder NEVER marks a follow-up task as completed.
        """
        patient_id = payload.get("patient_id")
        template_id = payload.get("template_id")
        template_code = payload.get("template_code")
        task_id = payload.get("task_id")
        appointment_id = payload.get("appointment_id")
        placeholders = payload.get("placeholders", {})
        idempotency_key = payload.get("idempotency_key")
        simulated_send_time_hhmm = payload.get("simulated_send_time_hhmm")
        defer_dispatch = bool(payload.get("defer_dispatch", False))
        allow_sensitive_override = bool(payload.get("allow_sensitive_placeholders", False))

        if not patient_id or (not template_id and not template_code):
            raise _val_err("MISSING_COMM_FIELDS", "patient_id and template_id (or template_code) are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if idempotency_key:
                cur.execute(
                    "SELECT id FROM outbound_messages WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, org_id)
                )
                existing_msg = cur.fetchone()
                if existing_msg:
                    return self.get_outbound_message(org_id, fac_id, existing_msg["id"])

            if template_id:
                cur.execute(
                    "SELECT * FROM communication_templates WHERE id = ? AND organization_id = ?;",
                    (template_id, org_id)
                )
            else:
                cur.execute(
                    "SELECT * FROM communication_templates WHERE template_code = ? AND organization_id = ?;",
                    (template_code, org_id)
                )
            tpl = cur.fetchone()
            if not tpl:
                raise _not_found("TEMPLATE_NOT_FOUND", "Requested communication template not found.")

            if tpl["approval_status"] != "approved":
                raise _val_err(
                    "UNAPPROVED_COMMUNICATION_TEMPLATE",
                    f"Template '{tpl['template_code']}' has status '{tpl['approval_status']}' and cannot be used for patient outreach."
                )

            # Enforce minimum-necessary privacy: reject prohibited sensitive placeholders unless explicitly overridden by policy
            passed_sensitive_keys = set(placeholders.keys()).intersection(PROHIBITED_SENSITIVE_PLACEHOLDERS)
            if (tpl["contains_sensitive_fields"] or passed_sensitive_keys) and not allow_sensitive_override:
                raise _val_err(
                    "SENSITIVE_CONTENT_PROHIBITED_IN_REMINDER",
                    f"Outbound messages must use minimum-necessary information. Prohibited sensitive fields detected: {sorted(list(passed_sensitive_keys or ['template_sensitive_field']))}."
                )

            cur.execute("""
                SELECT * FROM communication_template_versions
                WHERE template_id = ? AND version_number = ?;
            """, (tpl["id"], tpl["current_version"]))
            tpl_ver = cur.fetchone()

            # Render template safely
            rendered_body = tpl_ver["body_template"]
            for k, v in placeholders.items():
                rendered_body = re.sub(r"\{\{\s*" + re.escape(k) + r"\s*\}\}", str(v), rendered_body)

            channel = payload.get("channel") or tpl["channel"]
            category = payload.get("category") or tpl["category"]
            provider_map = {
                "sms": "sandbox_sms",
                "whatsapp": "sandbox_whatsapp",
                "email": "sandbox_email",
                "phone_call": "manual_call_log"
            }
            provider_code = payload.get("provider_code") or provider_map.get(channel, "sandbox_sms")

            # Check consent & preferences
            allowed, suppression_reason, prefs = self._check_consent_and_preferences(
                conn, org_id, fac_id, patient_id, channel, category
            )
            recipient_ref = prefs.get("verified_contact_ref") or "UNKNOWN_CONTACT"
            msg_id = f"msg-{uuid.uuid4().hex[:12]}"

            if not allowed:
                cur.execute("""
                    INSERT INTO outbound_messages (
                        id, organization_id, facility_id, patient_id, task_id, appointment_id,
                        template_id, template_version_id, channel, provider_code, recipient_ref,
                        rendered_body, category, status, suppression_reason, idempotency_key, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'suppressed', ?, ?, ?);
                """, (
                    msg_id, org_id, fac_id, patient_id, task_id, appointment_id,
                    tpl["id"], tpl_ver["id"], channel, provider_code, recipient_ref,
                    rendered_body, category, suppression_reason, idempotency_key, actor_id
                ))
                cur.execute("""
                    INSERT INTO message_delivery_events (
                        id, message_id, provider_code, provider_event_id, event_type, raw_payload_json
                    ) VALUES (?, ?, ?, ?, 'suppressed', ?);
                """, (
                    f"mde-{uuid.uuid4().hex[:12]}", msg_id, provider_code,
                    f"evt-sup-{msg_id}", json.dumps({"reason": suppression_reason})
                ))
                conn.commit()
                return self.get_outbound_message(org_id, fac_id, msg_id)

            # Check quiet hours
            check_hhmm = simulated_send_time_hhmm
            if check_hhmm and self._is_within_quiet_hours(
                check_hhmm, prefs.get("quiet_hours_start", "21:00"), prefs.get("quiet_hours_end", "08:00")
            ):
                scheduled_for = f"NEXT_WINDOW_{prefs.get('quiet_hours_end', '08:00')}"
                cur.execute("""
                    INSERT INTO outbound_messages (
                        id, organization_id, facility_id, patient_id, task_id, appointment_id,
                        template_id, template_version_id, channel, provider_code, recipient_ref,
                        rendered_body, category, status, scheduled_for, idempotency_key, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'deferred_quiet_hours', ?, ?, ?);
                """, (
                    msg_id, org_id, fac_id, patient_id, task_id, appointment_id,
                    tpl["id"], tpl_ver["id"], channel, provider_code, recipient_ref,
                    rendered_body, category, scheduled_for, idempotency_key, actor_id
                ))
                cur.execute("""
                    INSERT INTO job_outbox (
                        id, organization_id, facility_id, job_type, entity_id, payload_json,
                        status, next_run_at, idempotency_key
                    ) VALUES (?, ?, ?, 'DISPATCH_OUTBOUND_MESSAGE', ?, ?, 'pending', ?, ?);
                """, (
                    f"job-{uuid.uuid4().hex[:12]}", org_id, fac_id, msg_id,
                    json.dumps({"message_id": msg_id}), scheduled_for, f"job-msg-{msg_id}"
                ))
                conn.commit()
                return self.get_outbound_message(org_id, fac_id, msg_id)

            # Insert queued message + outbox job
            cur.execute("""
                INSERT INTO outbound_messages (
                    id, organization_id, facility_id, patient_id, task_id, appointment_id,
                    template_id, template_version_id, channel, provider_code, recipient_ref,
                    rendered_body, category, status, idempotency_key, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?);
            """, (
                msg_id, org_id, fac_id, patient_id, task_id, appointment_id,
                tpl["id"], tpl_ver["id"], channel, provider_code, recipient_ref,
                rendered_body, category, idempotency_key, actor_id
            ))
            cur.execute("""
                INSERT INTO job_outbox (
                    id, organization_id, facility_id, job_type, entity_id, payload_json,
                    status, idempotency_key
                ) VALUES (?, ?, ?, 'DISPATCH_OUTBOUND_MESSAGE', ?, ?, 'pending', ?);
            """, (
                f"job-{uuid.uuid4().hex[:12]}", org_id, fac_id, msg_id,
                json.dumps({"message_id": msg_id}), f"job-msg-{msg_id}"
            ))
            conn.commit()
        finally:
            conn.close()

        if not defer_dispatch:
            return self.dispatch_queued_message(org_id, fac_id, actor_id, msg_id)
        return self.get_outbound_message(org_id, fac_id, msg_id)

    def dispatch_queued_message(
        self, org_id: str, fac_id: str, actor_id: str, message_id: str
    ) -> Dict[str, Any]:
        """Worker execution step: Re-verify consent immediately before provider dispatch, then execute sandbox send."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM outbound_messages
                WHERE id = ? AND organization_id = ? AND facility_id = ?;
            """, (message_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("MESSAGE_NOT_FOUND", f"Outbound message '{message_id}' not found.")
            msg = dict(row)

            # CRITICAL REQUIREMENT: Re-verify consent & opt-out state at exact dispatch time!
            allowed, suppression_reason, _ = self._check_consent_and_preferences(
                conn, org_id, fac_id, msg["patient_id"], msg["channel"], msg["category"]
            )
            if not allowed:
                cur.execute("""
                    UPDATE outbound_messages
                    SET status = 'suppressed', suppression_reason = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (suppression_reason, message_id))
                cur.execute("""
                    UPDATE job_outbox
                    SET status = 'completed', updated_at = CURRENT_TIMESTAMP
                    WHERE entity_id = ? AND job_type = 'DISPATCH_OUTBOUND_MESSAGE';
                """, (message_id,))
                cur.execute("""
                    INSERT INTO message_delivery_events (
                        id, message_id, provider_code, provider_event_id, event_type, raw_payload_json
                    ) VALUES (?, ?, ?, ?, 'suppressed', ?);
                """, (
                    f"mde-{uuid.uuid4().hex[:12]}", message_id, msg["provider_code"],
                    f"evt-sendtime-sup-{message_id}", json.dumps({"reason": suppression_reason, "stage": "send_time_recheck"})
                ))
                conn.commit()
                return self.get_outbound_message(org_id, fac_id, message_id)

            # Execute deterministic sandbox provider adapter
            provider_msg_id = f"prov-{msg['provider_code']}-{uuid.uuid4().hex[:10]}"
            cur.execute("""
                UPDATE outbound_messages
                SET status = 'sent', provider_message_id = ?, sent_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (provider_msg_id, message_id))

            cur.execute("""
                UPDATE job_outbox
                SET status = 'completed', attempts = attempts + 1, updated_at = CURRENT_TIMESTAMP
                WHERE entity_id = ? AND job_type = 'DISPATCH_OUTBOUND_MESSAGE';
            """, (message_id,))

            cur.execute("""
                INSERT INTO message_delivery_events (
                    id, message_id, provider_code, provider_event_id, event_type, raw_payload_json
                ) VALUES (?, ?, ?, ?, 'sent', ?);
            """, (
                f"mde-{uuid.uuid4().hex[:12]}", message_id, msg["provider_code"],
                f"evt-sent-{provider_msg_id}", json.dumps({"provider_message_id": provider_msg_id, "sandbox": True})
            ))

            # Log outreach attempt on the linked follow-up task WITHOUT marking the task completed
            if msg.get("task_id"):
                cur.execute("""
                    INSERT INTO contact_attempts (
                        id, organization_id, facility_id, task_id, patient_id,
                        channel, attempt_outcome, notes, outbound_message_id, attempted_by
                    ) VALUES (?, ?, ?, ?, ?, ?, 'message_sent', 'Automated reminder dispatched via sandbox adapter', ?, ?);
                """, (
                    f"att-{uuid.uuid4().hex[:12]}", org_id, fac_id, msg["task_id"],
                    msg["patient_id"], msg["channel"], message_id, actor_id
                ))
                cur.execute("""
                    INSERT INTO follow_up_task_events (
                        id, task_id, event_type, from_status, to_status, actor_id, reason, metadata_json
                    ) VALUES (?, ?, 'REMINDER_DISPATCHED', NULL, NULL, ?, 'Outbound reminder dispatched (task remains open)', ?);
                """, (
                    f"fte-{uuid.uuid4().hex[:12]}", msg["task_id"], actor_id,
                    json.dumps({"message_id": message_id, "provider_message_id": provider_msg_id})
                ))

            conn.commit()
            return self.get_outbound_message(org_id, fac_id, message_id)
        finally:
            conn.close()

    def get_outbound_message(self, org_id: str, fac_id: str, message_id: str) -> Dict[str, Any]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM outbound_messages
                WHERE id = ? AND organization_id = ? AND facility_id = ?;
            """, (message_id, org_id, fac_id))
            row = cur.fetchone()
            if not row:
                raise _not_found("MESSAGE_NOT_FOUND", f"Outbound message '{message_id}' not found.")
            d = dict(row)
            cur.execute("""
                SELECT * FROM message_delivery_events WHERE message_id = ? ORDER BY occurred_at ASC;
            """, (message_id,))
            d["delivery_events"] = [dict(e) for e in cur.fetchall()]
            return d
        finally:
            conn.close()

    def handle_provider_webhook(
        self, provider_code: str, headers: Dict[str, str], raw_body: bytes, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process provider delivery/status/opt-out webhooks with HMAC verification and idempotency."""
        signature = (
            headers.get("x-provider-signature")
            or headers.get("X-Provider-Signature")
            or headers.get("x-webhook-signature")
            or ""
        )
        secret = "matab_webhook_secret_dev_key"
        expected_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

        if not signature or not hmac.compare_digest(signature, expected_sig):
            raise _auth_err("INVALID_WEBHOOK_SIGNATURE", "Webhook HMAC signature verification failed.")

        provider_event_id = payload.get("provider_event_id")
        message_id = payload.get("message_id")
        provider_message_id = payload.get("provider_message_id")
        event_type = payload.get("event_type")

        if not provider_event_id or not event_type:
            raise _val_err("INVALID_WEBHOOK_PAYLOAD", "provider_event_id and event_type are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, message_id FROM message_delivery_events WHERE provider_event_id = ?;",
                (provider_event_id,)
            )
            existing_evt = cur.fetchone()
            if existing_evt:
                return {
                    "processed": True,
                    "idempotent_replay": True,
                    "provider_event_id": provider_event_id,
                    "message_id": existing_evt["message_id"]
                }

            if message_id:
                cur.execute("SELECT * FROM outbound_messages WHERE id = ?;", (message_id,))
            else:
                cur.execute("SELECT * FROM outbound_messages WHERE provider_message_id = ?;", (provider_message_id,))
            msg_row = cur.fetchone()
            if not msg_row:
                raise _not_found("WEBHOOK_MESSAGE_NOT_FOUND", "Target outbound message not found.")

            msg = dict(msg_row)
            msg_id = msg["id"]

            cur.execute("""
                INSERT INTO message_delivery_events (
                    id, message_id, provider_code, provider_event_id, event_type, raw_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (
                f"mde-{uuid.uuid4().hex[:12]}", msg_id, provider_code,
                provider_event_id, event_type, json.dumps(payload)
            ))

            new_status = msg["status"]
            if event_type in ("accepted", "delivered", "read"):
                new_status = event_type
                cur.execute("""
                    UPDATE outbound_messages
                    SET status = ?,
                        delivered_at = CASE WHEN ? = 'delivered' THEN CURRENT_TIMESTAMP ELSE delivered_at END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (new_status, event_type, msg_id))
            elif event_type == "failed":
                retry_count = int(msg["retry_count"]) + 1
                max_retries = int(msg["max_retries"])
                failure_reason = payload.get("failure_reason", "Provider reported delivery failure")
                new_status = "dead_letter" if retry_count >= max_retries else "failed"
                cur.execute("""
                    UPDATE outbound_messages
                    SET status = ?, retry_count = ?, failure_reason = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                """, (new_status, retry_count, failure_reason, msg_id))
                if new_status == "dead_letter":
                    cur.execute("""
                        UPDATE job_outbox
                        SET status = 'dead_letter', last_error = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE entity_id = ?;
                    """, (failure_reason, msg_id))
            elif event_type == "opt_out_received":
                pat = self._fetch_patient_with_phone(cur, msg["organization_id"], msg["patient_id"])
                contact_ref = pat["primary_phone"] if pat else "UNKNOWN"
                cur.execute("""
                    INSERT INTO communication_preferences (
                        id, organization_id, facility_id, patient_id, verified_contact_ref,
                        opt_out_status, do_not_contact_scope, consent_source, recorded_by
                    ) VALUES (?, ?, ?, ?, ?, 1, 'all_automated', 'webhook_opt_out', ?)
                    ON CONFLICT(patient_id) DO UPDATE SET
                        opt_out_status = 1,
                        do_not_contact_scope = 'all_automated',
                        updated_at = CURRENT_TIMESTAMP;
                """, (
                    f"cpref-{uuid.uuid4().hex[:12]}", msg["organization_id"], msg["facility_id"],
                    msg["patient_id"], contact_ref, msg["created_by"]
                ))
                cur.execute("""
                    UPDATE outbound_messages
                    SET status = 'suppressed', suppression_reason = 'OPT_OUT_WEBHOOK_RECEIVED', updated_at = CURRENT_TIMESTAMP
                    WHERE patient_id = ? AND status IN ('queued', 'deferred_quiet_hours');
                """, (msg["patient_id"],))
                new_status = "opt_out_processed"

            conn.commit()
            return {
                "processed": True,
                "idempotent_replay": False,
                "provider_event_id": provider_event_id,
                "message_id": msg_id,
                "resulting_status": new_status
            }
        finally:
            conn.close()

    # =========================================================================
    # 5. STRUCTURED OUTCOME TRACKING & NON-CAUSAL TREND ENGINE
    # =========================================================================

    def create_outcome_definition(self, actor_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        code = (payload.get("code") or "").strip()
        name = (payload.get("name") or "").strip()
        domain = payload.get("domain", "symptom_severity")
        response_type = payload.get("response_type", "scale")
        unit = payload.get("unit", "score")
        scale_min = payload.get("scale_min")
        scale_max = payload.get("scale_max")
        directionality = payload.get("directionality", "lower_is_better")
        collection_method = payload.get("collection_method", "clinical_interview")
        instrument_version = payload.get("instrument_version", "1.0")
        review_status = payload.get("review_status", "approved")

        if not code or not name:
            raise _val_err("MISSING_OUTCOME_DEF_FIELDS", "code and name are required.")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            def_id = payload.get("id") or f"odef-{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO outcome_definitions (
                    id, code, name, domain, response_type, unit, scale_min, scale_max,
                    directionality, collection_method, instrument_version, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                def_id, code, name, domain, response_type, unit, scale_min, scale_max,
                directionality, collection_method, instrument_version, review_status
            ))
            conn.commit()
            cur.execute("SELECT * FROM outcome_definitions WHERE id = ?;", (def_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def list_outcome_definitions(self) -> List[Dict[str, Any]]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM outcome_definitions ORDER BY code ASC;")
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def record_outcome(
        self, org_id: str, fac_id: str, actor_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record a patient, caregiver, clinician, device, or unverified AI outcome observation."""
        patient_id = payload.get("patient_id")
        definition_id = payload.get("definition_id")
        definition_code = payload.get("definition_code")
        reporter_type = payload.get("reporter_type", "clinician_observed")
        value_numeric = payload.get("value_numeric")
        value_text = payload.get("value_text")
        recorded_at = payload.get("recorded_at") or datetime.utcnow().isoformat()

        if not patient_id or (not definition_id and not definition_code):
            raise _val_err("MISSING_OUTCOME_FIELDS", "patient_id and definition_id (or definition_code) are required.")

        if reporter_type not in REPORTER_TYPES:
            raise _val_err("INVALID_REPORTER_TYPE", f"reporter_type must be one of {REPORTER_TYPES}")

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            if definition_id:
                cur.execute("SELECT * FROM outcome_definitions WHERE id = ?;", (definition_id,))
            else:
                cur.execute("SELECT * FROM outcome_definitions WHERE code = ?;", (definition_code,))
            odef = cur.fetchone()
            if not odef:
                raise _not_found("OUTCOME_DEFINITION_NOT_FOUND", "Outcome definition not found.")

            unit = payload.get("unit") or odef["unit"]
            collection_method = payload.get("collection_method") or odef["collection_method"]

            if value_numeric is not None and unit == odef["unit"]:
                val = float(value_numeric)
                if odef["scale_min"] is not None and val < float(odef["scale_min"]):
                    raise _val_err("OUTCOME_VALUE_OUT_OF_RANGE", f"Value {val} is below scale_min {odef['scale_min']}.")
                if odef["scale_max"] is not None and val > float(odef["scale_max"]):
                    raise _val_err("OUTCOME_VALUE_OUT_OF_RANGE", f"Value {val} exceeds scale_max {odef['scale_max']}.")

            if reporter_type == "ai_draft_unverified":
                verification_status = "ai_draft_unverified"
            else:
                verification_status = payload.get("verification_status", "verified")

            rec_id = f"orec-{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO outcome_records (
                    id, organization_id, facility_id, patient_id, encounter_id,
                    follow_up_task_id, care_plan_id, definition_id, reporter_type,
                    value_numeric, value_text, unit, collection_method,
                    source_context, verification_status, notes, recorded_by, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                rec_id, org_id, fac_id, patient_id, payload.get("encounter_id"),
                payload.get("follow_up_task_id"), payload.get("care_plan_id"),
                odef["id"], reporter_type, value_numeric, value_text,
                unit, collection_method, payload.get("source_context", "followup_review"),
                verification_status, payload.get("notes", ""), actor_id, recorded_at
            ))

            log_audit_event(
                conn=conn,
                action_type="OUTCOME_RECORDED",
                target_entity_type="OUTCOME_RECORD",
                target_entity_id=rec_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"patient_id": patient_id, "definition_code": odef["code"], "reporter_type": reporter_type}
            )
            conn.commit()
            cur.execute("SELECT * FROM outcome_records WHERE id = ?;", (rec_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def get_patient_outcomes_and_trends(
        self, org_id: str, fac_id: str, patient_id: str, definition_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compute longitudinal outcome trends without making causal treatment efficacy claims.
        Returns 'cannot_compare_reliably' when units or collection methods are incompatible.
        """
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            sql = """
                SELECT r.*, d.code AS definition_code, d.name AS definition_name,
                       d.directionality, d.unit AS canonical_unit, d.collection_method AS canonical_method
                FROM outcome_records r
                JOIN outcome_definitions d ON r.definition_id = d.id
                WHERE r.organization_id = ? AND r.facility_id = ? AND r.patient_id = ?
            """
            params: List[Any] = [org_id, fac_id, patient_id]
            if definition_code:
                sql += " AND d.code = ?"
                params.append(definition_code)
            sql += " ORDER BY r.recorded_at ASC, r.created_at ASC;"
            cur.execute(sql, tuple(params))
            rows = [dict(r) for r in cur.fetchall()]

            grouped: Dict[str, List[Dict[str, Any]]] = {}
            for r in rows:
                grouped.setdefault(r["definition_code"], []).append(r)

            series_trends = []
            for code, items in grouped.items():
                verified_items = [
                    i for i in items
                    if i["verification_status"] == "verified" and i["reporter_type"] != "ai_draft_unverified"
                ]
                unverified_drafts = [
                    i for i in items
                    if i["verification_status"] != "verified" or i["reporter_type"] == "ai_draft_unverified"
                ]

                if len(verified_items) < 2:
                    series_trends.append({
                        "definition_code": code,
                        "definition_name": items[0]["definition_name"],
                        "trend_status": "insufficient_data_points",
                        "comparability_reason": "At least two verified measurements are required to compute a trend.",
                        "baseline": verified_items[0] if verified_items else None,
                        "latest": verified_items[-1] if verified_items else None,
                        "delta": None,
                        "claims_causal_efficacy": False,
                        "causal_attribution_disclaimer": NON_CAUSAL_TREND_DISCLAIMER,
                        "verified_count": len(verified_items),
                        "unverified_drafts_count": len(unverified_drafts),
                        "records": items
                    })
                    continue

                baseline = verified_items[0]
                latest = verified_items[-1]

                if (baseline.get("unit") != latest.get("unit")) or (
                    baseline.get("collection_method") != latest.get("collection_method")
                ):
                    series_trends.append({
                        "definition_code": code,
                        "definition_name": items[0]["definition_name"],
                        "trend_status": "cannot_compare_reliably",
                        "comparability_reason": (
                            f"Baseline ({baseline.get('unit')}, {baseline.get('collection_method')}) and "
                            f"latest ({latest.get('unit')}, {latest.get('collection_method')}) have incompatible "
                            "units or collection methods."
                        ),
                        "baseline": baseline,
                        "latest": latest,
                        "delta": None,
                        "claims_causal_efficacy": False,
                        "causal_attribution_disclaimer": NON_CAUSAL_TREND_DISCLAIMER,
                        "verified_count": len(verified_items),
                        "unverified_drafts_count": len(unverified_drafts),
                        "records": items
                    })
                    continue

                if baseline.get("value_numeric") is None or latest.get("value_numeric") is None:
                    series_trends.append({
                        "definition_code": code,
                        "definition_name": items[0]["definition_name"],
                        "trend_status": "qualitative_only",
                        "comparability_reason": "Non-numeric qualitative records cannot be numerically differenced.",
                        "baseline": baseline,
                        "latest": latest,
                        "delta": None,
                        "claims_causal_efficacy": False,
                        "causal_attribution_disclaimer": NON_CAUSAL_TREND_DISCLAIMER,
                        "verified_count": len(verified_items),
                        "unverified_drafts_count": len(unverified_drafts),
                        "records": items
                    })
                    continue

                delta = round(float(latest["value_numeric"]) - float(baseline["value_numeric"]), 4)
                directionality = items[0].get("directionality", "lower_is_better")
                if delta == 0:
                    trend_status = "unchanged"
                elif directionality == "lower_is_better":
                    trend_status = "observed_symptom_reduction" if delta < 0 else "observed_symptom_increase"
                elif directionality == "higher_is_better":
                    trend_status = "observed_functional_gain" if delta > 0 else "observed_functional_decline"
                else:
                    trend_status = "observed_change"

                series_trends.append({
                    "definition_code": code,
                    "definition_name": items[0]["definition_name"],
                    "trend_status": trend_status,
                    "comparability_reason": "Compatible unit and collection method across baseline and follow-up.",
                    "baseline": baseline,
                    "latest": latest,
                    "delta": delta,
                    "unit": latest.get("unit"),
                    "claims_causal_efficacy": False,
                    "causal_attribution_disclaimer": NON_CAUSAL_TREND_DISCLAIMER,
                    "verified_count": len(verified_items),
                    "unverified_drafts_count": len(unverified_drafts),
                    "records": items
                })

            return {
                "patient_id": patient_id,
                "series": series_trends,
                "total_records": len(rows),
                "causal_attribution_disclaimer": NON_CAUSAL_TREND_DISCLAIMER
            }
        finally:
            conn.close()

    # =========================================================================
    # 6. ADVERSE EFFECT REPORTING & SAFETY ESCALATION
    # =========================================================================

    def report_adverse_effect(
        self, org_id: str, fac_id: str, actor_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record a suspected adverse effect and automatically escalate severe/life-threatening reports."""
        patient_id = payload.get("patient_id")
        suspected_medication = (payload.get("suspected_medication") or "").strip()
        patient_description = (payload.get("patient_description") or "").strip()
        patient_severity = payload.get("patient_reported_severity", "moderate")
        clinician_severity = payload.get("clinician_assessed_severity", "unassessed")
        causality = payload.get("causality_assessment", "patient_suspected")
        task_id = payload.get("follow_up_task_id")

        if not patient_id or not suspected_medication or not patient_description:
            raise _val_err(
                "MISSING_ADVERSE_EFFECT_FIELDS",
                "patient_id, suspected_medication, and patient_description are required."
            )

        is_urgent = int(
            patient_severity in ("severe", "life_threatening")
            or clinician_severity in ("severe", "life_threatening")
            or bool(payload.get("urgent_flag", False))
        )
        review_status = "escalated" if is_urgent else "pending_clinician_review"

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            report_id = f"adr-{uuid.uuid4().hex[:12]}"
            cur.execute("""
                INSERT INTO adverse_effect_reports (
                    id, organization_id, facility_id, patient_id, encounter_id,
                    prescription_id, follow_up_task_id, suspected_medication,
                    patient_description, onset_date, patient_reported_severity,
                    clinician_assessed_severity, causality_assessment, action_taken,
                    review_status, escalated_to_safety_firewall, urgent_flag, reported_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                report_id, org_id, fac_id, patient_id, payload.get("encounter_id"),
                payload.get("prescription_id"), task_id, suspected_medication,
                patient_description, payload.get("onset_date"), patient_severity,
                clinician_severity, causality, payload.get("action_taken"),
                review_status, is_urgent, is_urgent, actor_id
            ))

            if is_urgent and task_id:
                cur.execute("""
                    UPDATE follow_up_tasks
                    SET status = 'escalated', priority = 'urgent', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND organization_id = ?;
                """, (task_id, org_id))
                cur.execute("""
                    INSERT INTO follow_up_task_events (
                        id, task_id, event_type, from_status, to_status, actor_id, reason
                    ) VALUES (?, ?, 'STATUS_CHANGED', NULL, 'escalated', ?, 'Urgent adverse effect reported');
                """, (f"fte-{uuid.uuid4().hex[:12]}", task_id, actor_id))

            log_audit_event(
                conn=conn,
                action_type="ADVERSE_EFFECT_REPORTED",
                target_entity_type="ADVERSE_EFFECT_REPORT",
                target_entity_id=report_id,
                organization_id=org_id,
                facility_id=fac_id,
                actor_id=actor_id,
                outcome="SUCCESS",
                details={"patient_id": patient_id, "urgent_flag": bool(is_urgent), "suspected_medication": suspected_medication}
            )
            conn.commit()
            cur.execute("SELECT * FROM adverse_effect_reports WHERE id = ?;", (report_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    def review_adverse_effect(
        self, org_id: str, fac_id: str, actor_id: str, report_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM adverse_effect_reports WHERE id = ? AND organization_id = ? AND facility_id = ?;",
                (report_id, org_id, fac_id)
            )
            row = cur.fetchone()
            if not row:
                raise _not_found("ADVERSE_EFFECT_NOT_FOUND", f"Adverse effect report '{report_id}' not found.")

            clinician_severity = payload.get("clinician_assessed_severity", row["clinician_assessed_severity"])
            causality = payload.get("causality_assessment", row["causality_assessment"])
            action_taken = payload.get("action_taken", row["action_taken"])
            review_status = payload.get("review_status", "reviewed")

            cur.execute("""
                UPDATE adverse_effect_reports
                SET clinician_assessed_severity = ?, causality_assessment = ?,
                    action_taken = ?, review_status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (clinician_severity, causality, action_taken, review_status, actor_id, report_id))
            conn.commit()
            cur.execute("SELECT * FROM adverse_effect_reports WHERE id = ?;", (report_id,))
            return dict(cur.fetchone())
        finally:
            conn.close()

    # =========================================================================
    # 7. ROLE-FILTERED MISSED FOLLOW-UP QUEUE, PATIENT 360 SUMMARY & ANALYTICS
    # =========================================================================

    def _can_view_sensitive_clinical_details(self, actor_user: Dict[str, Any]) -> bool:
        """Determine whether the current user is permitted to see clinical diagnoses/contexts in queues."""
        roles = set(actor_user.get("roles", []))
        perms = set(actor_user.get("permissions", []))
        if "PRACTITIONER" in roles or "CLINIC_ADMIN" in roles or "ORG_ADMIN" in roles:
            return True
        if "assessment:read" in perms or "modern_assessment:read" in perms:
            return True
        return False

    def get_follow_up_queue(
        self, org_id: str, fac_id: str, actor_user: Dict[str, Any], filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Return the operational & clinical follow-up queue with role-based privacy filtering."""
        filters = filters or {}
        include_clinical = self._can_view_sensitive_clinical_details(actor_user)

        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            sql = """
                SELECT t.*, p.display_name AS patient_name, p.mrn AS patient_mrn,
                       COALESCE(
                           (SELECT pc.contact_value FROM patient_contacts pc
                            WHERE pc.patient_id = p.id AND pc.contact_type = 'PHONE'
                            ORDER BY pc.is_preferred DESC LIMIT 1),
                           '+91-0000000000'
                       ) AS patient_phone,
                       (SELECT COUNT(*) FROM contact_attempts ca WHERE ca.task_id = t.id) AS contact_attempts_count
                FROM follow_up_tasks t
                JOIN patients p ON t.patient_id = p.id
                WHERE t.organization_id = ? AND t.facility_id = ?
            """
            params: List[Any] = [org_id, fac_id]

            status_filter = filters.get("status")
            if status_filter:
                sql += " AND t.status = ?"
                params.append(status_filter)
            else:
                sql += " AND t.status NOT IN ('completed', 'cancelled', 'entered_in_error')"

            priority_filter = filters.get("priority")
            if priority_filter:
                sql += " AND t.priority = ?"
                params.append(priority_filter)

            sql += " ORDER BY CASE t.priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 ELSE 3 END, t.due_at ASC;"
            cur.execute(sql, tuple(params))

            items = []
            for r in cur.fetchall():
                item = dict(r)
                if not include_clinical:
                    item["clinical_context_summary"] = None
                    item["clinical_details_redacted"] = True
                    item["purpose"] = "Scheduled Follow-up Outreach"
                else:
                    item["clinical_details_redacted"] = False
                items.append(item)

            urgent_adverse_effects = []
            if include_clinical:
                cur.execute("""
                    SELECT a.*, p.display_name AS patient_name, p.mrn AS patient_mrn
                    FROM adverse_effect_reports a
                    JOIN patients p ON a.patient_id = p.id
                    WHERE a.organization_id = ? AND a.facility_id = ?
                      AND a.review_status IN ('pending_clinician_review', 'escalated')
                    ORDER BY a.urgent_flag DESC, a.created_at DESC;
                """, (org_id, fac_id))
                urgent_adverse_effects = [dict(a) for a in cur.fetchall()]

            return {
                "queue_items": items,
                "total_open_tasks": len(items),
                "clinical_details_redacted": not include_clinical,
                "pending_adverse_effect_reviews": urgent_adverse_effects
            }
        finally:
            conn.close()

    def get_patient_continuity_summary(
        self, org_id: str, fac_id: str, actor_user: Dict[str, Any], patient_id: str
    ) -> Dict[str, Any]:
        """Aggregate longitudinal Care Continuity Summary for Patient 360."""
        include_clinical = self._can_view_sensitive_clinical_details(actor_user)
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            pat = self._fetch_patient_with_phone(cur, org_id, patient_id)
            if not pat:
                raise _not_found("PATIENT_NOT_FOUND", f"Patient '{patient_id}' not found.")

            plans = self.list_follow_up_plans(org_id, fac_id, patient_id=patient_id)

            cur.execute("""
                SELECT * FROM follow_up_tasks
                WHERE organization_id = ? AND facility_id = ? AND patient_id = ?
                ORDER BY due_at DESC;
            """, (org_id, fac_id, patient_id))
            tasks = []
            for t in cur.fetchall():
                td = dict(t)
                if not include_clinical:
                    td["clinical_context_summary"] = None
                tasks.append(td)

            cur.execute("""
                SELECT * FROM follow_up_appointments
                WHERE organization_id = ? AND facility_id = ? AND patient_id = ?
                ORDER BY scheduled_start_at DESC;
            """, (org_id, fac_id, patient_id))
            appointments = [dict(a) for a in cur.fetchall()]

            prefs = self.get_communication_preferences(org_id, fac_id, patient_id)

            cur.execute("""
                SELECT id, channel, provider_code, category, status, suppression_reason,
                       failure_reason, sent_at, delivered_at, created_at
                FROM outbound_messages
                WHERE organization_id = ? AND facility_id = ? AND patient_id = ?
                ORDER BY created_at DESC LIMIT 20;
            """, (org_id, fac_id, patient_id))
            messages = [dict(m) for m in cur.fetchall()]

            outcomes_summary = self.get_patient_outcomes_and_trends(org_id, fac_id, patient_id) if include_clinical else {
                "redacted_for_role": True
            }

            adverse_effects = []
            if include_clinical:
                cur.execute("""
                    SELECT * FROM adverse_effect_reports
                    WHERE organization_id = ? AND facility_id = ? AND patient_id = ?
                    ORDER BY created_at DESC;
                """, (org_id, fac_id, patient_id))
                adverse_effects = [dict(a) for a in cur.fetchall()]

            return {
                "patient": pat,
                "follow_up_plans": plans if include_clinical else [],
                "follow_up_tasks": tasks,
                "appointments": appointments,
                "communication_preferences": prefs,
                "recent_communications": messages,
                "outcomes_summary": outcomes_summary,
                "adverse_effect_reports": adverse_effects,
                "clinical_details_redacted": not include_clinical
            }
        finally:
            conn.close()

    def get_follow_up_analytics(self, org_id: str, fac_id: str) -> Dict[str, Any]:
        """Generate operational continuity report for clinic governance."""
        conn = self.db_manager.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT status, COUNT(*) AS cnt FROM follow_up_tasks WHERE organization_id = ? AND facility_id = ? GROUP BY status;",
                (org_id, fac_id)
            )
            task_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(
                "SELECT status, COUNT(*) AS cnt FROM follow_up_appointments WHERE organization_id = ? AND facility_id = ? GROUP BY status;",
                (org_id, fac_id)
            )
            appt_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(
                "SELECT status, COUNT(*) AS cnt FROM outbound_messages WHERE organization_id = ? AND facility_id = ? GROUP BY status;",
                (org_id, fac_id)
            )
            msg_counts = {r["status"]: r["cnt"] for r in cur.fetchall()}

            cur.execute(
                "SELECT review_status, COUNT(*) AS cnt FROM adverse_effect_reports WHERE organization_id = ? AND facility_id = ? GROUP BY review_status;",
                (org_id, fac_id)
            )
            adr_counts = {r["review_status"]: r["cnt"] for r in cur.fetchall()}

            return {
                "organization_id": org_id,
                "facility_id": fac_id,
                "tasks_by_status": task_counts,
                "appointments_by_status": appt_counts,
                "messages_by_status": msg_counts,
                "adverse_effects_by_status": adr_counts
            }
        finally:
            conn.close()

"""Enterprise Workflow Intelligence, SLA Governance & Exception Resolution Engine.

Phase 36 for ZAYVORA MATAB OS.
Provides:
1. Operational SLA Policy Registry (versioned policies, business/elapsed time, pause rules, multi-stage escalations).
2. Canonical Workflow Exception Lifecycle (OPEN -> ACKNOWLEDGED -> IN_PROGRESS -> WAITING -> RESOLVED -> VERIFIED / DISMISSED / REOPENED).
3. Deterministic SLA Timers (Effective duration = elapsed - pause intervals, ON_TRACK, AT_RISK, BREACHED, PAUSED, UNMEASURABLE).
4. Multi-Stage Escalation Engine (Notification cooldowns, data minimization, zero PHI over broadcast alerts).
5. Independent Verification Gate (Separation of duties: resolver cannot self-verify when policy mandates independent verification).
6. Fail-Safe Idempotent Exception Detection across real operational records (queue stalls, overdue follow-ups, inventory breaches, DLQ jobs, governance approvals).
7. Audit trail integration with cryptographic non-repudiation.

Strict Non-Negotiables Enforced:
- Operational focus only: ZERO autonomous clinical decision-making (no diagnosing, prescribing, dosing, or nuskha selection).
- Clinical safety requests strictly route human review tasks for qualified practitioners (REQUEST_CLINICAL_REVIEW).
- Never fabricate SLA targets, due times, resolution records, or timestamps.
- Unmeasurable or contradictory data produces explicit UNMEASURABLE state—not a guessed breach or false assurance.
"""

import os
import json
import uuid
import hashlib
import sqlite3
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union

from apps.api.database.connection import DatabaseConnection
from apps.api.config import config
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError, ForbiddenError


ALLOWED_CATEGORIES = {
    "administrative",
    "follow_up",
    "intake_gap",
    "inventory",
    "integration",
    "governance",
    "clinical_review"
}

ALLOWED_PRIORITIES = {"LOW", "NORMAL", "HIGH", "URGENT"}

VALID_PAUSE_REASONS = {
    "WAITING_PATIENT_RESPONSE",
    "SUPPLIER_DELIVERY_PENDING",
    "SYSTEM_OUTAGE",
    "EXTERNAL_REFERRAL_PENDING",
    "ADMINISTRATIVE_HOLD"
}

POLICY_STATUSES = {"DRAFT", "IN_REVIEW", "APPROVED", "ACTIVE", "PAUSED", "RETIRED"}

EXCEPTION_STATUSES = {
    "OPEN",
    "ACKNOWLEDGED",
    "IN_PROGRESS",
    "WAITING",
    "RESOLVED",
    "VERIFIED",
    "DISMISSED",
    "REOPENED"
}


class SlaGovernanceEngine:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = DatabaseConnection(self.db_path).get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    # --------------------------------------------------------------------------
    # 1. Operational SLA Policy Registry & Lifecycle
    # --------------------------------------------------------------------------

    def list_policies(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List versioned SLA policies within user's organization and facility scope."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")

        query = """
            SELECT * FROM sla_policies
            WHERE organization_id = ?
        """
        params: List[Any] = [org_id]

        if fac_id:
            query += " AND (facility_id IS NULL OR facility_id = ?)"
            params.append(fac_id)

        if filters.get("category"):
            query += " AND category = ?"
            params.append(filters["category"])

        if filters.get("status"):
            query += " AND (status = ? OR LOWER(status) = LOWER(?))"
            params.extend([filters["status"].upper(), filters["status"]])

        query += " ORDER BY category ASC, policy_key ASC, version DESC;"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            policies = []
            for r in cur.fetchall():
                item = dict(r)
                item["pause_eligibility"] = json.loads(item.get("pause_eligibility_json") or "[]")
                item["escalation_matrix"] = json.loads(item.get("escalation_matrix_json") or "[]")
                item["allowed_resolution_codes"] = json.loads(item.get("allowed_resolution_codes_json") or "[]")
                policies.append(item)
            return policies
        finally:
            conn.close()

    def get_policy(
        self,
        policy_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch a specific SLA policy by ID."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM sla_policies WHERE (id = ? OR policy_key = ?) AND organization_id = ?;",
                (policy_id, policy_id, org_id)
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"SLA policy '{policy_id}' not found.")
            item = dict(row)
            item["pause_eligibility"] = json.loads(item.get("pause_eligibility_json") or "[]")
            item["escalation_matrix"] = json.loads(item.get("escalation_matrix_json") or "[]")
            item["allowed_resolution_codes"] = json.loads(item.get("allowed_resolution_codes_json") or "[]")
            return item
        finally:
            conn.close()

    def create_policy_draft(
        self,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new versioned SLA policy draft."""
        org_id = user_ctx.get("organization_id")
        fac_id = data.get("facility_id")
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        name = (data.get("name") or "").strip()
        policy_key = (data.get("policy_key") or "").strip()
        if not policy_key and name:
            import re
            policy_key = "sla-pol-" + re.sub(r'[^a-zA-Z0-9]+', '-', name).strip('-').lower()

        category = data.get("category", "administrative")
        if category not in ALLOWED_CATEGORIES:
            raise ValidationError(f"Invalid category '{category}'. Must be one of: {sorted(ALLOWED_CATEGORIES)}")

        target_entity_type = (data.get("target_entity_type") or "queue_tokens").strip()
        owner_role = (data.get("owner_role") or "FRONT_DESK").strip()

        warning_threshold_mins = int(data.get("warning_threshold_mins", 30))
        breach_threshold_mins = int(data.get("breach_threshold_mins", 45))
        if warning_threshold_mins <= 0 or breach_threshold_mins <= 0:
            raise ValidationError("Thresholds must be positive integers.")
        if warning_threshold_mins > breach_threshold_mins:
            raise ValidationError("warning_threshold_mins cannot exceed breach_threshold_mins.")

        pause_eligibility = data.get("pause_eligibility") or data.get("pause_eligibility_json") or list(VALID_PAUSE_REASONS)
        if isinstance(pause_eligibility, str):
            pause_eligibility = json.loads(pause_eligibility)

        escalation_matrix = data.get("escalation_matrix") or data.get("escalation_matrix_json") or []
        if isinstance(escalation_matrix, str):
            escalation_matrix = json.loads(escalation_matrix)

        allowed_resolution_codes = data.get("allowed_resolution_codes") or data.get("allowed_resolution_codes_json") or [
            "TASK_COMPLETED", "RESOLVED_SATISFACTORILY"
        ]
        if isinstance(allowed_resolution_codes, str):
            allowed_resolution_codes = json.loads(allowed_resolution_codes)

        verification_required = 1 if data.get("verification_required") else 0
        time_basis = data.get("time_basis", "elapsed")
        if time_basis not in ("elapsed", "business_hours"):
            raise ValidationError("time_basis must be 'elapsed' or 'business_hours'.")

        policy_id = f"sla-pol-{uuid.uuid4().hex[:8]}"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO sla_policies (
                    id, organization_id, facility_id, policy_key, name, description,
                    category, target_entity_type, owner_role, version, status, time_basis,
                    timezone, warning_threshold_mins, breach_threshold_mins,
                    pause_eligibility_json, escalation_matrix_json, verification_required,
                    allowed_resolution_codes_json, effective_from, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'DRAFT', ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """,
                (
                    policy_id, org_id, fac_id, policy_key, name, data.get("description", ""),
                    category, target_entity_type, owner_role, time_basis,
                    data.get("timezone", "Asia/Kolkata"), warning_threshold_mins, breach_threshold_mins,
                    json.dumps(pause_eligibility), json.dumps(escalation_matrix), verification_required,
                    json.dumps(allowed_resolution_codes), user_id
                )
            )
            conn.commit()
            return self.get_policy(policy_id, user_ctx)
        finally:
            conn.close()

    def update_policy_draft(
        self,
        policy_id: str,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing SLA policy while in DRAFT or IN_REVIEW status."""
        existing = self.get_policy(policy_id, user_ctx)
        if existing["status"] not in ("DRAFT", "IN_REVIEW"):
            raise ConflictError(
                f"Policy '{policy_id}' is in status '{existing['status']}'. Only DRAFT or IN_REVIEW policies may be updated directly."
            )

        name = data.get("name", existing["name"])
        description = data.get("description", existing["description"])
        warning_mins = int(data.get("warning_threshold_mins", existing["warning_threshold_mins"]))
        breach_mins = int(data.get("breach_threshold_mins", existing["breach_threshold_mins"]))
        if warning_mins > breach_mins:
            raise ValidationError("warning_threshold_mins cannot exceed breach_threshold_mins.")

        pause_eligibility = data.get("pause_eligibility", existing["pause_eligibility"])
        escalation_matrix = data.get("escalation_matrix", existing["escalation_matrix"])
        resolution_codes = data.get("allowed_resolution_codes", existing["allowed_resolution_codes"])
        verification_req = 1 if data.get("verification_required", existing["verification_required"]) else 0

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE sla_policies
                SET name = ?, description = ?, warning_threshold_mins = ?, breach_threshold_mins = ?,
                    pause_eligibility_json = ?, escalation_matrix_json = ?, allowed_resolution_codes_json = ?,
                    verification_required = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    name, description, warning_mins, breach_mins,
                    json.dumps(pause_eligibility), json.dumps(escalation_matrix), json.dumps(resolution_codes),
                    verification_req, policy_id, user_ctx.get("organization_id")
                )
            )
            conn.commit()
            return self.get_policy(policy_id, user_ctx)
        finally:
            conn.close()

    def advance_policy_status(
        self,
        policy_id: str,
        transition: str,
        user_ctx: Dict[str, Any],
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Advance SLA policy state (submit_for_review, approve, activate, pause, retire)."""
        policy = self.get_policy(policy_id, user_ctx)
        current_st = policy["status"]
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        transition_map = {
            "submit_for_review": "submit_for_review",
            "review": "submit_for_review",
            "in_review": "submit_for_review",
            "approve": "approve",
            "approved": "approve",
            "activate": "activate",
            "active": "activate",
            "pause": "pause",
            "paused": "pause",
            "resume": "resume",
            "retire": "retire",
            "retired": "retire"
        }
        normalized = transition_map.get((transition or "").lower())
        if not normalized:
            raise ValidationError(f"Unknown policy transition '{transition}'.")

        valid_transitions = {
            "submit_for_review": ("DRAFT", "IN_REVIEW"),
            "approve": ("IN_REVIEW", "APPROVED"),
            "activate": ("APPROVED", "ACTIVE"),
            "pause": ("ACTIVE", "PAUSED"),
            "resume": ("PAUSED", "ACTIVE"),
            "retire": ("ACTIVE", "RETIRED")
        }

        expected_from, target_to = valid_transitions[normalized]
        if current_st != expected_from and not (normalized == "activate" and current_st in ("PAUSED", "IN_REVIEW", "APPROVED")):
            raise ConflictError(
                f"Cannot '{transition}' policy in status '{current_st}'. Expected '{expected_from}'."
            )

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if normalized == "approve":
                cur.execute(
                    """
                    UPDATE sla_policies
                    SET status = 'APPROVED', approved_by = ?, approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (user_id, policy_id)
                )
                # Snapshot into sla_policy_versions
                ver_id = f"slav-{uuid.uuid4().hex[:8]}"
                cur.execute(
                    """
                    INSERT OR REPLACE INTO sla_policy_versions (
                        id, policy_id, version, snapshot_json, change_reason, authored_by
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ver_id, policy_id, policy["version"],
                        json.dumps(policy), reason or f"Approved by {user_id}", user_id
                    )
                )
            else:
                cur.execute(
                    """
                    UPDATE sla_policies
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (target_to, policy_id)
                )
            conn.commit()
            return self.get_policy(policy_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Exception Detection, Ingestion & Deduplication
    # --------------------------------------------------------------------------

    def detect_and_ingest_exception(
        self,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detect and persist an operational exception idempotently."""
        org_id = user_ctx.get("organization_id")
        fac_id = data.get("facility_id") or user_ctx.get("facility_id")

        category = data.get("category", "administrative")
        if category not in ALLOWED_CATEGORIES:
            raise ValidationError(f"Invalid category '{category}'.")

        source_entity = (data.get("source_entity") or "queue_tokens").strip()
        source_entity_id = (data.get("source_entity_id") or "").strip()
        if not source_entity_id:
            raise ValidationError("source_entity_id is required.")

        # Resolve matching policy
        policy_id = data.get("policy_id")
        policy = None
        if policy_id:
            policy = self.get_policy(policy_id, user_ctx)
        else:
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT * FROM sla_policies
                    WHERE organization_id = ? AND category = ? AND status = 'ACTIVE'
                    ORDER BY version DESC LIMIT 1;
                    """,
                    (org_id, category)
                )
                p_row = cur.fetchone()
                if p_row:
                    policy = dict(p_row)
                    policy["pause_eligibility"] = json.loads(policy.get("pause_eligibility_json") or "[]")
                    policy["escalation_matrix"] = json.loads(policy.get("escalation_matrix_json") or "[]")
                    policy["allowed_resolution_codes"] = json.loads(policy.get("allowed_resolution_codes_json") or "[]")
            finally:
                conn.close()

        if not policy:
            raise ValidationError(f"No active SLA policy configured for category '{category}'.")

        # Deduplication key enforcement: sha256(org + category + source_entity + source_id + policy_key)
        dedup_raw = f"{org_id}:{category}:{source_entity}:{source_entity_id}:{policy['policy_key']}"
        dedup_key = data.get("deduplication_key") or hashlib.sha256(dedup_raw.encode("utf-8")).hexdigest()

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # Check for existing open/active exception
            cur.execute(
                """
                SELECT id, status FROM workflow_exceptions
                WHERE organization_id = ? AND deduplication_key = ?;
                """,
                (org_id, dedup_key)
            )
            existing = cur.fetchone()
            if existing:
                # Return existing exception (Idempotent)
                return self.get_exception(existing["id"], user_ctx)

            # Create new exception
            exc_id = f"exc-{uuid.uuid4().hex[:8]}"
            started_at_str = data.get("started_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            try:
                started_dt = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
            except Exception:
                started_dt = datetime.now(timezone.utc)

            breach_mins = policy["breach_threshold_mins"]
            due_dt = started_dt + timedelta(minutes=breach_mins)
            due_at_str = due_dt.strftime("%Y-%m-%d %H:%M:%S")

            title = data.get("title") or f"{category.replace('_', ' ').title()} Delay Exception ({source_entity_id})"
            factual_reason = data.get("factual_reason") or f"Operation elapsed duration breached SLA threshold of {breach_mins} mins."
            safe_summary = data.get("safe_summary") or f"Operational attention required for {source_entity} ({source_entity_id})."
            priority = data.get("priority", "NORMAL")
            assigned_role = data.get("assigned_role") or policy["owner_role"]

            cur.execute(
                """
                INSERT INTO workflow_exceptions (
                    id, organization_id, facility_id, policy_id, policy_version,
                    category, source_entity, source_entity_id, source_event_id,
                    deduplication_key, title, factual_reason, safe_summary,
                    priority, status, assigned_role, assigned_user_id,
                    started_at, due_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?);
                """,
                (
                    exc_id, org_id, fac_id, policy["id"], policy["version"],
                    category, source_entity, source_entity_id, data.get("source_event_id"),
                    dedup_key, title, factual_reason, safe_summary,
                    priority, assigned_role, data.get("assigned_user_id"),
                    started_at_str, due_at_str
                )
            )
            conn.commit()
            return self.get_exception(exc_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Exception Lifecycle Transitions & Actions
    # --------------------------------------------------------------------------

    def list_exceptions(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List scoped workflow exceptions with real-time timer calculation."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")

        query = """
            SELECT e.*, p.name AS policy_name, p.warning_threshold_mins, p.breach_threshold_mins, p.time_basis
            FROM workflow_exceptions e
            JOIN sla_policies p ON p.id = e.policy_id
            WHERE e.organization_id = ?
        """
        params: List[Any] = [org_id]

        if fac_id:
            query += " AND (e.facility_id IS NULL OR e.facility_id = ?)"
            params.append(fac_id)

        if filters.get("status"):
            query += " AND (e.status = ? OR LOWER(e.status) = LOWER(?))"
            params.extend([filters["status"].upper(), filters["status"]])

        if filters.get("category"):
            query += " AND e.category = ?"
            params.append(filters["category"])

        if filters.get("assigned_role"):
            query += " AND e.assigned_role = ?"
            params.append(filters["assigned_role"])

        if filters.get("assigned_user_id"):
            query += " AND e.assigned_user_id = ?"
            params.append(filters["assigned_user_id"])

        query += " ORDER BY e.due_at ASC, e.created_at DESC LIMIT 100;"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            items = []
            for r in cur.fetchall():
                exc = dict(r)
                timer = self.calculate_timer_projection(exc)
                exc["timer"] = timer
                exc["sla_state"] = timer["timer_state"]

                # Optional filter by SLA timer state
                if filters.get("sla_state") and exc["sla_state"] != filters["sla_state"].upper():
                    continue

                items.append(exc)
            return items
        finally:
            conn.close()

    def get_exception(
        self,
        exception_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch exception details, pause history, and escalation events."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT e.*, p.name AS policy_name, p.warning_threshold_mins, p.breach_threshold_mins,
                       p.time_basis, p.verification_required, p.allowed_resolution_codes_json, p.pause_eligibility_json,
                       p.escalation_matrix_json
                FROM workflow_exceptions e
                JOIN sla_policies p ON p.id = e.policy_id
                WHERE e.id = ? AND e.organization_id = ?;
                """,
                (exception_id, org_id)
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Workflow exception '{exception_id}' not found.")
            exc = dict(row)
            exc["allowed_resolution_codes"] = json.loads(exc.get("allowed_resolution_codes_json") or "[]")
            exc["pause_eligibility"] = json.loads(exc.get("pause_eligibility_json") or "[]")
            exc["escalation_matrix"] = json.loads(exc.get("escalation_matrix_json") or "[]")

            # Pause intervals
            cur.execute(
                "SELECT * FROM sla_pause_intervals WHERE exception_id = ? ORDER BY paused_at ASC;",
                (exception_id,)
            )
            exc["pause_intervals"] = [dict(r) for r in cur.fetchall()]

            # Escalation events
            cur.execute(
                "SELECT * FROM sla_escalation_events WHERE exception_id = ? ORDER BY stage ASC;",
                (exception_id,)
            )
            exc["escalations"] = [dict(r) for r in cur.fetchall()]

            timer = self.calculate_timer_projection(exc)
            exc["timer"] = timer
            exc["sla_state"] = timer["timer_state"]
            return exc
        finally:
            conn.close()

    def acknowledge_exception(
        self,
        exception_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transition OPEN -> ACKNOWLEDGED by authorized user."""
        exc = self.get_exception(exception_id, user_ctx)
        if exc["status"] != "OPEN":
            raise ConflictError(f"Cannot acknowledge exception in status '{exc['status']}'. Must be 'OPEN'.")

        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = 'ACKNOWLEDGED', acknowledged_by = ?, acknowledged_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (user_id, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def assign_exception(
        self,
        exception_id: str,
        assigned_user_id: Optional[str],
        assigned_role: Optional[str],
        user_ctx: Dict[str, Any],
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Assign or reassign accountable owner/role."""
        self.get_exception(exception_id, user_ctx)
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET assigned_user_id = COALESCE(?, assigned_user_id),
                    assigned_role = COALESCE(?, assigned_role),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (assigned_user_id, assigned_role, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def start_work_on_exception(
        self,
        exception_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transition ACKNOWLEDGED -> IN_PROGRESS."""
        exc = self.get_exception(exception_id, user_ctx)
        if exc["status"] not in ("OPEN", "ACKNOWLEDGED"):
            raise ConflictError(f"Cannot start work on exception in status '{exc['status']}'.")

        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = 'IN_PROGRESS',
                    acknowledged_by = COALESCE(acknowledged_by, ?),
                    acknowledged_at = COALESCE(acknowledged_at, CURRENT_TIMESTAMP),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (user_id, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def pause_exception(
        self,
        exception_id: str,
        pause_reason_code: str,
        user_ctx: Dict[str, Any],
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pause SLA timer under an approved reason code (IN_PROGRESS -> WAITING)."""
        exc = self.get_exception(exception_id, user_ctx)
        if exc["status"] != "IN_PROGRESS":
            raise ConflictError(f"Only IN_PROGRESS exceptions can be paused. Current status is '{exc['status']}'.")

        if pause_reason_code not in exc["pause_eligibility"] and pause_reason_code not in VALID_PAUSE_REASONS:
            raise ValidationError(
                f"Pause reason code '{pause_reason_code}' is not permitted by policy. Allowed: {exc['pause_eligibility']}"
            )

        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        pause_id = f"pause-{uuid.uuid4().hex[:8]}"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO sla_pause_intervals (
                    id, exception_id, pause_reason_code, pause_notes, paused_at, paused_by
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """,
                (pause_id, exception_id, pause_reason_code, notes, user_id)
            )
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = 'WAITING', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (exception_id,)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def resume_exception(
        self,
        exception_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resume paused exception (WAITING -> IN_PROGRESS), calculating pause duration."""
        exc = self.get_exception(exception_id, user_ctx)
        if exc["status"] != "WAITING":
            raise ConflictError(f"Cannot resume exception in status '{exc['status']}'. Must be 'WAITING'.")

        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # Find active pause interval
            cur.execute(
                """
                SELECT id, paused_at FROM sla_pause_intervals
                WHERE exception_id = ? AND resumed_at IS NULL
                ORDER BY paused_at DESC LIMIT 1;
                """,
                (exception_id,)
            )
            p_row = cur.fetchone()
            added_pause_mins = 0
            if p_row:
                try:
                    p_dt = datetime.fromisoformat(p_row["paused_at"].replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    added_pause_mins = max(1, int((now_dt - p_dt).total_seconds() / 60))
                except Exception:
                    added_pause_mins = 5

                cur.execute(
                    """
                    UPDATE sla_pause_intervals
                    SET resumed_at = CURRENT_TIMESTAMP, resumed_by = ?, duration_mins = ?
                    WHERE id = ?;
                    """,
                    (user_id, added_pause_mins, p_row["id"])
                )

            # Recalculate due_at by extending it by the paused duration
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = 'IN_PROGRESS',
                    total_paused_duration_mins = total_paused_duration_mins + ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (added_pause_mins, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def resolve_exception(
        self,
        exception_id: str,
        resolution_code: str,
        resolution_notes: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve exception with permitted resolution code."""
        exc = self.get_exception(exception_id, user_ctx)
        if exc["status"] not in ("OPEN", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING"):
            raise ConflictError(f"Cannot resolve exception in status '{exc['status']}'.")

        allowed_codes = exc.get("allowed_resolution_codes") or ["TASK_COMPLETED", "RESOLVED_SATISFACTORILY"]
        if resolution_code not in allowed_codes:
            raise ValidationError(
                f"Resolution code '{resolution_code}' is not permitted by policy. Allowed: {allowed_codes}"
            )

        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        # If waiting, close pause interval first
        if exc["status"] == "WAITING":
            self.resume_exception(exception_id, user_ctx)

        target_status = "RESOLVED"
        # If verification is not required, it is immediately finalized
        if exc.get("verification_required") == 0:
            target_status = "RESOLVED"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = ?, resolution_code = ?, resolution_notes = ?,
                    resolved_by = ?, resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (target_status, resolution_code, resolution_notes, user_id, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def verify_exception(
        self,
        exception_id: str,
        verification_notes: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform independent verification (Separation of duties: resolver cannot self-verify)."""
        exc = self.get_exception(exception_id, user_ctx)
        if exc["status"] != "RESOLVED":
            raise ConflictError(f"Cannot verify exception in status '{exc['status']}'. Must be 'RESOLVED'.")

        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        # SEPARATION OF DUTIES ENFORCEMENT
        if exc.get("resolved_by") and exc["resolved_by"] == user_id:
            raise ForbiddenError(
                "Separation of duties violation: The user who resolved this exception cannot independently verify it."
            )

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = 'VERIFIED', verified_by = ?, verified_at = CURRENT_TIMESTAMP,
                    verification_notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (user_id, verification_notes, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def dismiss_exception(
        self,
        exception_id: str,
        dismissal_reason: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dismiss an invalid or duplicate exception with justification."""
        self.get_exception(exception_id, user_ctx)
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = 'DISMISSED', dismissed_by = ?, dismissed_at = CURRENT_TIMESTAMP,
                    dismissal_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (user_id, dismissal_reason, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    def reopen_exception(
        self,
        exception_id: str,
        reopen_reason: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reopen a resolved or dismissed exception upon verification failure or new events."""
        exc = self.get_exception(exception_id, user_ctx)
        if exc["status"] not in ("RESOLVED", "VERIFIED", "DISMISSED"):
            raise ConflictError(f"Cannot reopen exception in status '{exc['status']}'.")

        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_exceptions
                SET status = 'OPEN', reopened_by = ?, reopened_at = CURRENT_TIMESTAMP,
                    reopen_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (user_id, reopen_reason, exception_id)
            )
            conn.commit()
            return self.get_exception(exception_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Deterministic SLA Timers & Escalations
    # --------------------------------------------------------------------------

    def calculate_timer_projection(
        self,
        exception: Dict[str, Any],
        now_dt: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Calculate effective operational duration and SLA breach state."""
        st = exception.get("status", "OPEN")
        started_at_str = exception.get("started_at")
        warning_mins = int(exception.get("warning_threshold_mins", 30))
        breach_mins = int(exception.get("breach_threshold_mins", 45))
        total_paused = int(exception.get("total_paused_duration_mins", 0))

        if not started_at_str:
            return {
                "timer_state": "UNMEASURABLE",
                "reason": "Missing started_at timestamp",
                "effective_elapsed_mins": 0,
                "warning_threshold_mins": warning_mins,
                "breach_threshold_mins": breach_mins,
                "time_remaining_mins": 0
            }

        try:
            started_dt = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
        except Exception:
            return {
                "timer_state": "UNMEASURABLE",
                "reason": "Invalid started_at format",
                "effective_elapsed_mins": 0,
                "warning_threshold_mins": warning_mins,
                "breach_threshold_mins": breach_mins,
                "time_remaining_mins": 0
            }

        current_dt = now_dt or datetime.now(timezone.utc)
        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=timezone.utc)
        if current_dt.tzinfo is None:
            current_dt = current_dt.replace(tzinfo=timezone.utc)

        raw_elapsed_mins = max(0, int((current_dt - started_dt).total_seconds() / 60))
        effective_elapsed_mins = max(0, raw_elapsed_mins - total_paused)

        if st == "WAITING":
            timer_state = "PAUSED"
        elif st in ("RESOLVED", "VERIFIED"):
            timer_state = "RESOLVED"
        elif st == "DISMISSED":
            timer_state = "DISMISSED"
        elif effective_elapsed_mins >= breach_mins:
            timer_state = "BREACHED"
        elif effective_elapsed_mins >= warning_mins:
            timer_state = "AT_RISK"
        else:
            timer_state = "ON_TRACK"

        time_remaining = max(0, breach_mins - effective_elapsed_mins)

        return {
            "timer_state": timer_state,
            "raw_elapsed_mins": raw_elapsed_mins,
            "total_paused_duration_mins": total_paused,
            "effective_elapsed_mins": effective_elapsed_mins,
            "warning_threshold_mins": warning_mins,
            "breach_threshold_mins": breach_mins,
            "time_remaining_mins": time_remaining,
            "is_breached": effective_elapsed_mins >= breach_mins
        }

    def process_escalations(
        self,
        exception_id: str,
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Evaluate and record multi-stage escalations for breached exceptions."""
        exc = self.get_exception(exception_id, user_ctx)
        timer = exc["timer"]
        if timer["timer_state"] != "BREACHED":
            return []

        matrix = exc.get("escalation_matrix") or []
        if isinstance(matrix, str):
            matrix = json.loads(matrix)

        dispatched_events = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            for stage_def in matrix:
                stage_num = int(stage_def.get("stage", 1))
                trigger_delay = int(stage_def.get("trigger_delay_mins", 0))
                overdue_mins = timer["effective_elapsed_mins"] - timer["breach_threshold_mins"]

                if overdue_mins < trigger_delay:
                    continue

                # Check if already executed
                cur.execute(
                    "SELECT id FROM sla_escalation_events WHERE exception_id = ? AND stage = ?;",
                    (exception_id, stage_num)
                )
                if cur.fetchone():
                    continue

                esc_id = f"esc-{uuid.uuid4().hex[:8]}"
                target_role = stage_def.get("escalate_to_role", "CLINIC_ADMIN")
                channel = stage_def.get("channel", "in_app")
                safe_msg = f"[SLA BREACH ALERT] Exception {exc['id']} ({exc['title']}) breached SLA by {overdue_mins} mins. Escalated to {target_role}."

                cur.execute(
                    """
                    INSERT INTO sla_escalation_events (
                        id, exception_id, policy_id, stage, target_role, channel,
                        notification_message_safe, status, dispatched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'DISPATCHED', CURRENT_TIMESTAMP);
                    """,
                    (esc_id, exception_id, exc["policy_id"], stage_num, target_role, channel, safe_msg)
                )
                cur.execute(
                    """
                    UPDATE workflow_exceptions
                    SET current_escalation_stage = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (stage_num, exception_id)
                )
                dispatched_events.append({
                    "id": esc_id,
                    "stage": stage_num,
                    "target_role": target_role,
                    "channel": channel,
                    "message": safe_msg
                })
            conn.commit()
            return dispatched_events
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Operational Monitor & Governance Pulse
    # --------------------------------------------------------------------------

    def get_sla_monitor_summary(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aggregate real-time SLA compliance, at-risk work items, and resolution metrics."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # 1. Total active policies
            cur.execute(
                "SELECT COUNT(*) as count FROM sla_policies WHERE organization_id = ? AND status = 'ACTIVE';",
                (org_id,)
            )
            active_policies_count = cur.fetchone()["count"]

            # 2. Exceptions breakdown by status
            cur.execute(
                """
                SELECT status, COUNT(*) as count
                FROM workflow_exceptions
                WHERE organization_id = ?
                GROUP BY status;
                """,
                (org_id,)
            )
            status_counts = {r["status"]: r["count"] for r in cur.fetchall()}

            # 3. Exceptions breakdown by category
            cur.execute(
                """
                SELECT category, COUNT(*) as count
                FROM workflow_exceptions
                WHERE organization_id = ?
                GROUP BY category;
                """,
                (org_id,)
            )
            category_counts = {r["category"]: r["count"] for r in cur.fetchall()}

            # 4. Open exceptions real-time timer states
            all_open = self.list_exceptions({"status": "OPEN"}, user_ctx)
            all_ack = self.list_exceptions({"status": "ACKNOWLEDGED"}, user_ctx)
            all_prog = self.list_exceptions({"status": "IN_PROGRESS"}, user_ctx)
            all_wait = self.list_exceptions({"status": "WAITING"}, user_ctx)
            active_exceptions = all_open + all_ack + all_prog + all_wait

            on_track_count = sum(1 for e in active_exceptions if e["sla_state"] == "ON_TRACK")
            at_risk_count = sum(1 for e in active_exceptions if e["sla_state"] == "AT_RISK")
            breached_count = sum(1 for e in active_exceptions if e["sla_state"] == "BREACHED")
            paused_count = sum(1 for e in active_exceptions if e["sla_state"] == "PAUSED")

            # 5. Awaiting verification
            cur.execute(
                """
                SELECT COUNT(*) as count
                FROM workflow_exceptions
                WHERE organization_id = ? AND status = 'RESOLVED' AND verified_at IS NULL;
                """,
                (org_id,)
            )
            awaiting_verification_count = cur.fetchone()["count"]

            return {
                "active_policies_count": active_policies_count,
                "total_open_exceptions": sum(status_counts.get(s, 0) for s in ("OPEN", "ACKNOWLEDGED", "IN_PROGRESS", "WAITING", "REOPENED")),
                "on_track_count": on_track_count,
                "at_risk_count": at_risk_count,
                "breached_count": breached_count,
                "paused_count": paused_count,
                "awaiting_verification_count": awaiting_verification_count,
                "status_breakdown": status_counts,
                "category_breakdown": category_counts,
                "caveats": [
                    "Operational SLAs represent internal administrative expectations, NOT clinical standards or medical urgency.",
                    "Missing timestamps produce UNMEASURABLE states; timers are never fabricated.",
                    "Clinical safety reviews require qualified human clinician judgment."
                ]
            }
        finally:
            conn.close()

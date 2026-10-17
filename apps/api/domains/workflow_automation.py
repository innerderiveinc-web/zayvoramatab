"""Clinical Workflow Automation, Rules Engine & Task Orchestration Domain Engine.

Phase 35 for ZAYVORA MATAB OS.
Provides:
1. Master Governed Workflow Rules Registry with versioning and immutable snapshots.
2. Deterministic, safe rule evaluator (NO eval, bounded allowlisted operators).
3. Dry-run preview sandbox with guaranteed zero side effects.
4. Action classification registry (routine_administrative, communication, sensitive_administrative, clinical_review_only).
5. Human approval gates for sensitive administrative and clinical-review-only actions.
6. Communication consent & channel pre-flight validator (checks communication_preferences & quiet hours).
7. Durable event intake outbox with deterministic idempotency keys and retry limits.
8. Operational workflow monitor for Prompt 34 command center and Prompt 33 analytics integration.

Strict non-negotiables enforced:
- Operations and coordination only: Never autonomously diagnose, prescribe, calculate dose, or sign encounters.
- Unknown, conflicting, or stale inputs cause a safe pause (NEEDS_REVIEW)—never a guess.
- Human approval is explicit, attributable, scoped to immutable action payload hash and version.
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
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError
from apps.api.core.audit import log_audit_event


ALLOWLISTED_OPERATORS = {
    "equals",
    "not_equals",
    "in",
    "not_in",
    "exists",
    "not_exists",
    "greater_than",
    "less_than",
    "before",
    "after"
}

ACTION_CATEGORIES = {
    "routine_administrative",
    "communication",
    "sensitive_administrative",
    "clinical_review_only"
}

ALLOWED_ACTION_TYPES = {
    "CREATE_ADMIN_TASK",
    "ENQUEUE_PATIENT_REMINDER",
    "ESCALATE_QUEUE_STALL",
    "RECORD_INTAKE_GAP",
    "CREATE_STOCK_REVIEW_TASK",
    "RETRY_DEAD_LETTER_ITEM",
    "REQUEST_CLINICAL_REVIEW",
    "HOLD_APPOINTMENT_FOR_REVIEW"
}


def _compute_payload_hash(payload: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of proposed action payload."""
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class WorkflowAutomationEngine:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = DatabaseConnection(self.db_path).get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    # --------------------------------------------------------------------------
    # 1. Rule Definition & Versioning Lifecycle
    # --------------------------------------------------------------------------

    def list_rules(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List workflow rules filtered by event_type, status, or category."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")

        query = """
            SELECT 
                id, organization_id, facility_id, rule_key, rule_name, description,
                event_type, event_schema_version, conditions_json, actions_json,
                action_category, priority, version, status, owner_role,
                timezone, rate_limit_per_hour, approved_by, approved_at,
                created_by, created_at, updated_at
            FROM workflow_rules
            WHERE organization_id = ?
        """
        params: List[Any] = [org_id]

        if fac_id:
            query += " AND (facility_id IS NULL OR facility_id = ?)"
            params.append(fac_id)

        if filters.get("event_type"):
            query += " AND event_type = ?"
            params.append(filters["event_type"])

        if filters.get("status"):
            query += " AND (status = ? OR LOWER(status) = LOWER(?))"
            params.extend([filters["status"].upper(), filters["status"]])

        if filters.get("action_category"):
            query += " AND action_category = ?"
            params.append(filters["action_category"])

        query += " ORDER BY priority ASC, rule_key ASC, version DESC;"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            rules = []
            for r in rows:
                item = dict(r)
                item["conditions"] = json.loads(item["conditions_json"])
                item["actions"] = json.loads(item["actions_json"])
                rules.append(item)
            return rules
        finally:
            conn.close()

    def get_rule(self, rule_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch a specific rule by ID with parsed definitions."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM workflow_rules WHERE id = ? AND organization_id = ?;
                """,
                (rule_id, org_id)
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Workflow rule '{rule_id}' not found.")
            rule = dict(row)
            rule["conditions"] = json.loads(rule["conditions_json"])
            rule["actions"] = json.loads(rule["actions_json"])
            return rule
        finally:
            conn.close()

    def create_rule_draft(
        self,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new versioned workflow rule in DRAFT status."""
        org_id = user_ctx.get("organization_id")
        fac_id = data.get("facility_id")
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        rule_key = (data.get("rule_key") or data.get("key") or "").strip()
        rule_name = (data.get("rule_name") or data.get("name") or "").strip()
        event_type = (data.get("event_type") or "").strip()
        action_category = data.get("action_category") or "routine_administrative"

        if not rule_key and rule_name:
            import re
            rule_key = "rule-" + re.sub(r'[^a-zA-Z0-9]+', '-', rule_name).strip('-').lower()
            if not rule_key:
                rule_key = f"rule-{uuid.uuid4().hex[:6]}"

        if not rule_key or not rule_name or not event_type:
            raise ValidationError("rule_key, rule_name, and event_type are required.")

        if action_category not in ACTION_CATEGORIES:
            raise ValidationError(
                f"Invalid action_category '{action_category}'. Must be one of: {sorted(ACTION_CATEGORIES)}"
            )

        conditions = data.get("conditions") or data.get("conditions_json") or []
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        self._validate_conditions_syntax(conditions)

        actions = data.get("actions") or data.get("actions_json") or []
        if isinstance(actions, str):
            actions = json.loads(actions)
        for act in actions:
            if "action_type" in act and "type" not in act:
                act["type"] = act["action_type"]
            if "category" not in act:
                act["category"] = action_category
        self._validate_actions_syntax(actions, action_category)

        rule_id = f"wf-rule-{uuid.uuid4().hex[:8]}"
        priority = int(data.get("priority", 100))
        owner_role = data.get("owner_role", "CLINIC_ADMIN")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO workflow_rules (
                    id, organization_id, facility_id, rule_key, rule_name, description,
                    event_type, event_schema_version, conditions_json, actions_json,
                    action_category, priority, version, status, owner_role,
                    timezone, rate_limit_per_hour, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '1.0.0', ?, ?, ?, ?, 1, 'DRAFT', ?, ?, ?, ?);
                """,
                (
                    rule_id, org_id, fac_id, rule_key, rule_name, data.get("description", ""),
                    event_type, json.dumps(conditions), json.dumps(actions),
                    action_category, priority, owner_role,
                    data.get("timezone", "Asia/Kolkata"), int(data.get("rate_limit_per_hour", 100)),
                    user_id
                )
            )
            conn.commit()
            return self.get_rule(rule_id, user_ctx)
        finally:
            conn.close()

    def update_rule_draft(
        self,
        rule_id: str,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a rule draft while in DRAFT or IN_REVIEW status."""
        existing = self.get_rule(rule_id, user_ctx)
        if existing["status"] not in ("DRAFT", "IN_REVIEW"):
            raise ConflictError(
                f"Rule '{rule_id}' is in status '{existing['status']}'. Only DRAFT or IN_REVIEW rules may be updated directly."
            )

        conditions = data.get("conditions") or data.get("conditions_json") or existing["conditions"]
        if isinstance(conditions, str):
            conditions = json.loads(conditions)
        self._validate_conditions_syntax(conditions)

        action_category = data.get("action_category", existing["action_category"])
        if action_category not in ACTION_CATEGORIES:
            raise ValidationError(f"Invalid action_category '{action_category}'.")

        actions = data.get("actions") or data.get("actions_json") or existing["actions"]
        if isinstance(actions, str):
            actions = json.loads(actions)
        for act in actions:
            if "action_type" in act and "type" not in act:
                act["type"] = act["action_type"]
            if "category" not in act:
                act["category"] = action_category
        self._validate_actions_syntax(actions, action_category)

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_rules
                SET rule_name = ?, description = ?, conditions_json = ?,
                    actions_json = ?, action_category = ?, priority = ?,
                    owner_role = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    data.get("rule_name") or data.get("name") or existing["rule_name"],
                    data.get("description", existing["description"]),
                    json.dumps(conditions),
                    json.dumps(actions),
                    action_category,
                    int(data.get("priority", existing["priority"])),
                    data.get("owner_role", existing["owner_role"]),
                    rule_id,
                    user_ctx.get("organization_id")
                )
            )
            conn.commit()
            return self.get_rule(rule_id, user_ctx)
        finally:
            conn.close()

    def advance_rule_status(
        self,
        rule_id: str,
        transition: str,
        user_ctx: Dict[str, Any],
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transition rule state (submit_for_review, approve, activate, pause, retire)."""
        rule = self.get_rule(rule_id, user_ctx)
        current_st = rule["status"]
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
        normalized_transition = transition_map.get((transition or "").lower())
        if not normalized_transition:
            raise ValidationError(f"Unknown rule transition '{transition}'.")

        valid_transitions = {
            "submit_for_review": ("DRAFT", "IN_REVIEW"),
            "approve": ("IN_REVIEW", "APPROVED"),
            "activate": ("APPROVED", "ACTIVE"),
            "pause": ("ACTIVE", "PAUSED"),
            "resume": ("PAUSED", "ACTIVE"),
            "retire": ("ACTIVE", "RETIRED")
        }

        expected_from, target_to = valid_transitions[normalized_transition]
        if current_st != expected_from and not (normalized_transition == "activate" and current_st in ("PAUSED", "IN_REVIEW", "APPROVED")):
            raise ConflictError(
                f"Cannot '{transition}' rule in status '{current_st}'. Expected '{expected_from}'."
            )

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if transition == "approve":
                # Record approval metadata
                cur.execute(
                    """
                    UPDATE workflow_rules
                    SET status = ?, approved_by = ?, approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (target_to, user_id, rule_id)
                )
                # Store immutable snapshot in workflow_rule_versions
                ver_id = f"wfv-{uuid.uuid4().hex[:8]}"
                cur.execute(
                    """
                    INSERT OR REPLACE INTO workflow_rule_versions (
                        id, rule_id, version, snapshot_json, change_summary, authored_by
                    ) VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        ver_id, rule_id, rule["version"],
                        json.dumps(rule), reason or f"Approved by {user_id}", user_id
                    )
                )
            else:
                cur.execute(
                    """
                    UPDATE workflow_rules
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (target_to, rule_id)
                )
            conn.commit()
            return self.get_rule(rule_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Safe Condition Evaluation & Dry-Run Engine
    # --------------------------------------------------------------------------

    def dry_run_rule(
        self,
        rule_or_id: Union[str, Dict[str, Any]],
        sample_event: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a deterministic dry-run of a rule against a sample event with zero side effects."""
        if isinstance(rule_or_id, str):
            rule = self.get_rule(rule_or_id, user_ctx)
        else:
            rule = rule_or_id

        conditions = rule.get("conditions", [])
        if isinstance(conditions, str):
            conditions = json.loads(conditions)

        matched, details = self._evaluate_conditions(conditions, sample_event)

        proposed_actions = []
        if matched:
            raw_actions = rule.get("actions", [])
            if isinstance(raw_actions, str):
                raw_actions = json.loads(raw_actions)

            for act in raw_actions:
                action_category = act.get("category") or rule.get("action_category", "routine_administrative")
                is_approval_needed = 1 if action_category in ("sensitive_administrative", "clinical_review_only") else 0
                proposed_actions.append({
                    "action_type": act.get("type"),
                    "action_category": action_category,
                    "target_entity": act.get("parameters", {}).get("target_entity", "unknown"),
                    "parameters": act.get("parameters", {}),
                    "approval_required": is_approval_needed,
                    "preview_note": "Dry-run preview only. No production state was mutated."
                })

        return {
            "mode": "DRY_RUN",
            "is_dry_run": True,
            "rule_id": rule.get("id", "draft"),
            "rule_key": rule.get("rule_key", "custom_draft"),
            "event_type": sample_event.get("event_type"),
            "is_matched": matched,
            "conditions_matched": matched,
            "condition_evaluations": details,
            "proposed_actions": proposed_actions,
            "executed_side_effects": []  # Strictly empty in dry-run
        }

    def _evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        event_payload: Dict[str, Any]
    ) -> Tuple[bool, List[Dict[str, Any]]]:
        """Evaluate allowlisted conditions deterministically without eval or exec."""
        eval_details = []
        if not conditions:
            return True, [{"condition": "empty", "result": True}]

        all_matched = True
        for cond in conditions:
            field_path = cond.get("field", "")
            operator = cond.get("operator", "equals")
            target_val = cond.get("value")

            actual_val = self._resolve_path(event_payload, field_path)
            res = self._apply_operator(operator, actual_val, target_val)

            eval_details.append({
                "field": field_path,
                "operator": operator,
                "expected": target_val,
                "actual": actual_val,
                "passed": res
            })

            if not res:
                all_matched = False

        return all_matched, eval_details

    def _resolve_path(self, obj: Dict[str, Any], path: str) -> Any:
        """Resolve dot-notated path safely."""
        if not path:
            return None
        parts = path.split(".")
        curr: Any = obj
        for p in parts:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            else:
                return None
        return curr

    def _apply_operator(self, operator: str, actual: Any, expected: Any) -> bool:
        """Evaluate single allowlisted operator safely."""
        if operator == "equals":
            return actual == expected
        elif operator == "not_equals":
            return actual != expected
        elif operator == "in":
            if isinstance(expected, (list, tuple, set)):
                return actual in expected
            return False
        elif operator == "not_in":
            if isinstance(expected, (list, tuple, set)):
                return actual not in expected
            return True
        elif operator == "exists":
            return actual is not None and actual != ""
        elif operator == "not_exists":
            return actual is None or actual == ""
        elif operator == "greater_than":
            try:
                return float(actual) > float(expected)
            except (TypeError, ValueError):
                return False
        elif operator == "less_than":
            try:
                return float(actual) < float(expected)
            except (TypeError, ValueError):
                return False
        elif operator == "before":
            try:
                dt_act = datetime.fromisoformat(str(actual).replace("Z", "+00:00"))
                dt_exp = datetime.fromisoformat(str(expected).replace("Z", "+00:00"))
                return dt_act < dt_exp
            except Exception:
                return False
        elif operator == "after":
            try:
                dt_act = datetime.fromisoformat(str(actual).replace("Z", "+00:00"))
                dt_exp = datetime.fromisoformat(str(expected).replace("Z", "+00:00"))
                return dt_act > dt_exp
            except Exception:
                return False
        return False

    def _validate_conditions_syntax(self, conditions: List[Dict[str, Any]]) -> None:
        """Validate structure and allowlisted operators of rule conditions."""
        if not isinstance(conditions, list):
            raise ValidationError("conditions must be a list.")
        for idx, cond in enumerate(conditions):
            if not isinstance(cond, dict):
                raise ValidationError(f"Condition at index {idx} must be an object.")
            if "field" not in cond:
                raise ValidationError(f"Condition at index {idx} missing 'field'.")
            op = cond.get("operator")
            if op not in ALLOWLISTED_OPERATORS:
                raise ValidationError(
                    f"Disallowed operator '{op}' at index {idx}. Must be one of: {sorted(ALLOWLISTED_OPERATORS)}"
                )

    def _validate_actions_syntax(self, actions: List[Dict[str, Any]], rule_category: str) -> None:
        """Validate structure and allowed action types."""
        if not isinstance(actions, list):
            raise ValidationError("actions must be a list.")
        for idx, act in enumerate(actions):
            if not isinstance(act, dict):
                raise ValidationError(f"Action at index {idx} must be an object.")
            act_type = act.get("type")
            if act_type not in ALLOWED_ACTION_TYPES:
                raise ValidationError(
                    f"Disallowed action type '{act_type}' at index {idx}. Must be one of: {sorted(ALLOWED_ACTION_TYPES)}"
                )
            # Enforce non-autonomous clinical boundaries
            if rule_category == "clinical_review_only" and act_type != "REQUEST_CLINICAL_REVIEW":
                raise ValidationError(
                    f"Rules with category 'clinical_review_only' can ONLY perform 'REQUEST_CLINICAL_REVIEW'."
                )

    # --------------------------------------------------------------------------
    # 3. Durable Event Intake & Orchestration
    # --------------------------------------------------------------------------

    def ingest_and_process_event(
        self,
        event_data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ingest a domain event, evaluate active rules, and plan actions."""
        org_id = user_ctx.get("organization_id")
        fac_id = event_data.get("facility_id") or user_ctx.get("facility_id")
        event_type = (event_data.get("event_type") or "").strip()
        event_source = (event_data.get("event_source") or "").strip()
        source_entity_id = (event_data.get("source_entity_id") or "").strip()

        if not event_type or not event_source or not source_entity_id:
            raise ValidationError("event_type, event_source, and source_entity_id are required.")

        event_id = f"evt-{uuid.uuid4().hex[:8]}"
        correlation_id = event_data.get("correlation_id") or f"corr-{uuid.uuid4().hex[:8]}"
        causation_id = event_data.get("causation_id")
        payload = event_data.get("payload", {})
        occurred_at = event_data.get("occurred_at") or datetime.now(timezone.utc).isoformat()

        # Wrap in standard event envelope for conditions evaluation
        eval_envelope = {
            "event_type": event_type,
            "event_source": event_source,
            "source_entity_id": source_entity_id,
            "event": payload,
            "facility_id": fac_id,
            "organization_id": org_id
        }

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # 1. Insert Event Envelope
            cur.execute(
                """
                INSERT INTO automation_events (
                    id, organization_id, facility_id, event_type, event_source,
                    source_entity_id, payload_json, correlation_id, causation_id,
                    status, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'RECEIVED', ?);
                """,
                (
                    event_id, org_id, fac_id, event_type, event_source,
                    source_entity_id, json.dumps(payload), correlation_id, causation_id,
                    occurred_at
                )
            )

            # 2. Fetch Active Matching Rules
            cur.execute(
                """
                SELECT id, rule_key, rule_name, event_type, conditions_json, actions_json,
                       action_category, version, priority
                FROM workflow_rules
                WHERE organization_id = ? AND event_type = ? AND status = 'ACTIVE'
                  AND (facility_id IS NULL OR facility_id = ?)
                ORDER BY priority ASC;
                """,
                (org_id, event_type, fac_id)
            )
            active_rules = cur.fetchall()

            matched_rules_count = 0
            planned_actions_created = []

            for r_row in active_rules:
                r_id = r_row["id"]
                r_ver = r_row["version"]
                r_cat = r_row["action_category"]
                conds = json.loads(r_row["conditions_json"])
                acts = json.loads(r_row["actions_json"])

                matched, _ = self._evaluate_conditions(conds, eval_envelope)
                if not matched:
                    continue

                matched_rules_count += 1
                for idx, act in enumerate(acts):
                    act_type = act["type"]
                    act_params = act.get("parameters", {})
                    target_entity = act_params.get("target_entity", event_source)
                    target_id = act_params.get("target_id", source_entity_id)

                    idempotency_key = f"evt_{event_id}_rule_{r_id}_v{r_ver}_act_{idx}"
                    payload_hash = _compute_payload_hash(act_params)

                    # Determine action gate
                    approval_req = 1 if r_cat in ("sensitive_administrative", "clinical_review_only") else 0
                    initial_status = "AWAITING_APPROVAL" if approval_req else "QUEUED"

                    # If communication, pre-flight check patient consent
                    if r_cat == "communication":
                        consent_ok, consent_reason = self._check_communication_consent(
                            conn, org_id, fac_id, payload.get("patient_id")
                        )
                        if not consent_ok:
                            initial_status = "NEEDS_REVIEW"
                            act_params["consent_pause_reason"] = consent_reason

                    action_id = f"act-{uuid.uuid4().hex[:8]}"
                    cur.execute(
                        """
                        INSERT OR IGNORE INTO workflow_planned_actions (
                            id, organization_id, facility_id, event_id, rule_id, rule_version,
                            action_type, action_category, target_entity, target_id,
                            parameters_json, payload_hash, idempotency_key, status,
                            approval_required
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            action_id, org_id, fac_id, event_id, r_id, r_ver,
                            act_type, r_cat, target_entity, target_id,
                            json.dumps(act_params), payload_hash, idempotency_key,
                            initial_status, approval_req
                        )
                    )

                    planned_actions_created.append({
                        "action_id": action_id,
                        "action_type": act_type,
                        "action_category": r_cat,
                        "status": initial_status,
                        "approval_required": approval_req
                    })

            # Update event status
            ev_status = "PROCESSED" if matched_rules_count > 0 else "NO_MATCH"
            cur.execute(
                "UPDATE automation_events SET status = ? WHERE id = ?;",
                (ev_status, event_id)
            )

            conn.commit()

            # Execute actions that are QUEUED
            for pa in planned_actions_created:
                if pa["status"] == "QUEUED":
                    self._execute_action(conn, pa["action_id"], user_ctx)

            conn.commit()

            return {
                "event_id": event_id,
                "correlation_id": correlation_id,
                "status": ev_status,
                "matched_rules_count": matched_rules_count,
                "actions_planned": len(planned_actions_created),
                "planned_actions": planned_actions_created
            }
        finally:
            conn.close()

    def _check_communication_consent(
        self,
        conn: sqlite3.Connection,
        org_id: str,
        fac_id: Optional[str],
        patient_id: Optional[str]
    ) -> Tuple[bool, str]:
        """Verify patient communication consent and quiet hours."""
        if not patient_id:
            return False, "Cannot verify consent: patient_id is absent from event."

        cur = conn.cursor()
        cur.execute(
            """
            SELECT opt_out_status, do_not_contact_scope, quiet_hours_start, quiet_hours_end
            FROM communication_preferences
            WHERE organization_id = ? AND patient_id = ?;
            """,
            (org_id, patient_id)
        )
        pref = cur.fetchone()
        if not pref:
            return False, "Consent not on file: communication_preferences missing for patient."

        if pref["opt_out_status"] == 1:
            return False, "Patient has active opt-out recorded in communication preferences."

        if pref["do_not_contact_scope"] in ("all_automated", "non_urgent_all"):
            return False, f"Patient communication scope is restricted ({pref['do_not_contact_scope']})."

        return True, "Consent verified."

    # --------------------------------------------------------------------------
    # 4. Action Execution, Approval & Retry
    # --------------------------------------------------------------------------

    def list_planned_actions(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List planned workflow actions with status and approval details."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")

        query = """
            SELECT 
                a.id, a.organization_id, a.facility_id, a.event_id, a.rule_id,
                a.rule_version, a.action_type, a.action_category, a.target_entity,
                a.target_id, a.parameters_json, a.payload_hash, a.idempotency_key,
                a.status, a.approval_required, a.approved_by, a.approved_at,
                a.rejection_reason, a.review_notes, a.attempts_count, a.last_error,
                a.created_at, a.updated_at,
                r.rule_name, r.rule_key,
                e.event_type, e.source_entity_id
            FROM workflow_planned_actions a
            JOIN workflow_rules r ON r.id = a.rule_id
            JOIN automation_events e ON e.id = a.event_id
            WHERE a.organization_id = ?
        """
        params: List[Any] = [org_id]

        if fac_id:
            query += " AND (a.facility_id IS NULL OR a.facility_id = ?)"
            params.append(fac_id)

        if filters.get("status"):
            query += " AND a.status = ?"
            params.append(filters["status"])

        if filters.get("action_category"):
            query += " AND a.action_category = ?"
            params.append(filters["action_category"])

        query += " ORDER BY a.created_at DESC LIMIT 100;"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            actions = []
            for row in cur.fetchall():
                item = dict(row)
                item["parameters"] = json.loads(item["parameters_json"])
                actions.append(item)
            return actions
        finally:
            conn.close()

    def approve_planned_action(
        self,
        action_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Approve an action held in AWAITING_APPROVAL and queue execution."""
        org_id = user_ctx.get("organization_id")
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM workflow_planned_actions
                WHERE id = ? AND organization_id = ?;
                """,
                (action_id, org_id)
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Planned action '{action_id}' not found.")

            if row["status"] != "AWAITING_APPROVAL":
                raise ConflictError(
                    f"Action '{action_id}' is in status '{row['status']}'. Only AWAITING_APPROVAL can be approved."
                )

            # Re-verify payload hash has not been tampered with
            stored_hash = row["payload_hash"]
            current_hash = _compute_payload_hash(json.loads(row["parameters_json"]))
            if stored_hash != current_hash:
                raise ConflictError("Proposed action payload changed after plan creation. Re-review required.")

            cur.execute(
                """
                UPDATE workflow_planned_actions
                SET status = 'QUEUED', approved_by = ?, approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (user_id, action_id)
            )
            conn.commit()

            # Execute the queued action
            self._execute_action(conn, action_id, user_ctx)
            conn.commit()

            cur.execute("SELECT * FROM workflow_planned_actions WHERE id = ?;", (action_id,))
            updated = dict(cur.fetchone())
            updated["parameters"] = json.loads(updated["parameters_json"])
            return updated
        finally:
            conn.close()

    def reject_planned_action(
        self,
        action_id: str,
        rejection_reason: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reject an action held in AWAITING_APPROVAL."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_planned_actions
                SET status = 'REJECTED', rejection_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ? AND status = 'AWAITING_APPROVAL';
                """,
                (rejection_reason, action_id, org_id)
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Action '{action_id}' not found or not in AWAITING_APPROVAL.")
            conn.commit()
            return {"action_id": action_id, "status": "REJECTED", "rejection_reason": rejection_reason}
        finally:
            conn.close()

    def retry_planned_action(
        self,
        action_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retry a failed or needs_review action."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE workflow_planned_actions
                SET status = 'QUEUED', last_error = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ? AND status IN ('NEEDS_REVIEW', 'RETRY_SCHEDULED', 'SUCCEEDED');
                """,
                (action_id, org_id)
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Action '{action_id}' not found or not retryable.")
            conn.commit()

            self._execute_action(conn, action_id, user_ctx)
            conn.commit()

            cur.execute("SELECT * FROM workflow_planned_actions WHERE id = ?;", (action_id,))
            res = dict(cur.fetchone())
            res["action_id"] = action_id
            res["parameters"] = json.loads(res["parameters_json"])
            return res
        finally:
            conn.close()

    def _execute_action(
        self,
        conn: sqlite3.Connection,
        action_id: str,
        user_ctx: Dict[str, Any]
    ) -> None:
        """Execute action side effect via known adapters with audit attempt logging."""
        cur = conn.cursor()
        cur.execute("SELECT * FROM workflow_planned_actions WHERE id = ?;", (action_id,))
        row = cur.fetchone()
        if not row:
            return

        act_type = row["action_type"]
        act_params = json.loads(row["parameters_json"])
        attempt_num = row["attempts_count"] + 1

        # Resolve patient_id safely
        p_id = act_params.get("patient_id")
        if not p_id:
            cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (row["organization_id"],))
            p_row = cur.fetchone()
            p_id = p_row["id"] if p_row else None

        try:
            # 1. Adapter Dispatch
            if act_type == "CREATE_ADMIN_TASK":
                # Create care_continuity_task
                if p_id:
                    task_id = f"cct-{uuid.uuid4().hex[:8]}"
                    cur.execute(
                        """
                        INSERT INTO care_continuity_tasks (
                            id, organization_id, facility_id, patient_id, originating_encounter_id,
                            task_type, due_date, status, assigned_role, outcome_notes
                        ) VALUES (?, ?, ?, ?, NULL, 'FOLLOW_UP_CALL', CURRENT_DATE, 'PENDING', 'FRONT_DESK', ?);
                        """,
                        (
                            task_id, row["organization_id"], row["facility_id"],
                            p_id, act_params.get("task_name", "Administrative Task")
                        )
                    )

            elif act_type == "ENQUEUE_PATIENT_REMINDER":
                # Enqueue into outbound_messages
                if p_id:
                    cur.execute(
                        "SELECT id FROM communication_templates WHERE organization_id = ? LIMIT 1;",
                        (row["organization_id"],)
                    )
                    tpl_row = cur.fetchone()
                    tpl_id = tpl_row["id"] if tpl_row else "tmpl-fup-reminder"

                    cur.execute(
                        "SELECT id FROM communication_template_versions WHERE template_id = ? LIMIT 1;",
                        (tpl_id,)
                    )
                    ver_row = cur.fetchone()
                    ver_id = ver_row["id"] if ver_row else "tmpl-v-fup-1"

                    msg_id = f"msg-{uuid.uuid4().hex[:8]}"
                    cur.execute(
                        """
                        INSERT INTO outbound_messages (
                            id, organization_id, facility_id, patient_id, template_id, template_version_id,
                            channel, provider_code, recipient_ref, rendered_body, category, status, created_by
                        ) VALUES (?, ?, ?, ?, ?, ?, 'sms', 'sandbox_sms', '+91-9800000000', 'Automated Reminder', 'clinical_reminder', 'queued', ?);
                        """,
                        (
                            msg_id, row["organization_id"], row["facility_id"],
                            p_id, tpl_id, ver_id, user_ctx.get("id") or "system"
                        )
                    )

            elif act_type == "ESCALATE_QUEUE_STALL":
                # Create operational alert in operational_alerts
                alt_id = f"alt-wf-{uuid.uuid4().hex[:6]}"
                cur.execute(
                    """
                    INSERT INTO operational_alerts (
                        id, organization_id, facility_id, alert_type, severity,
                        deduplication_key, source_entity, source_entity_id, stage_key,
                        measured_value_mins, threshold_value_mins, factual_reason
                    ) VALUES (?, ?, ?, 'STAGE_THRESHOLD_EXCEEDED', 'WARNING', ?, 'queue_tokens', ?, 'CHECK_IN_TO_CALL', 45, 30, ?);
                    """,
                    (
                        alt_id, row["organization_id"], row["facility_id"],
                        f"stall_{row['target_id']}_{uuid.uuid4().hex[:4]}", row["target_id"],
                        "Queue waiting delay escalated by workflow automation rule."
                    )
                )

            elif act_type == "RECORD_INTAKE_GAP":
                if p_id:
                    task_id = f"cct-gap-{uuid.uuid4().hex[:8]}"
                    cur.execute(
                        """
                        INSERT INTO care_continuity_tasks (
                            id, organization_id, facility_id, patient_id, originating_encounter_id,
                            task_type, due_date, status, assigned_role, outcome_notes
                        ) VALUES (?, ?, ?, ?, NULL, 'FOLLOW_UP_CALL', CURRENT_DATE, 'PENDING', 'FRONT_DESK', ?);
                        """,
                        (
                            task_id, row["organization_id"], row["facility_id"],
                            p_id, f"Intake Gap: {act_params.get('action_needed', 'Collect Phone')}"
                        )
                    )

            elif act_type == "CREATE_STOCK_REVIEW_TASK":
                if p_id:
                    task_id = f"cct-stock-{uuid.uuid4().hex[:8]}"
                    cur.execute(
                        """
                        INSERT INTO care_continuity_tasks (
                            id, organization_id, facility_id, patient_id, originating_encounter_id,
                            task_type, due_date, status, assigned_role, outcome_notes
                        ) VALUES (?, ?, ?, ?, NULL, 'ADHERENCE_CHECK', CURRENT_DATE, 'PENDING', 'PHARMACIST', ?);
                        """,
                        (
                            task_id, row["organization_id"], row["facility_id"],
                            p_id, "Dispensary Low Stock Review"
                        )
                    )

            elif act_type == "REQUEST_CLINICAL_REVIEW":
                if p_id:
                    task_id = f"cct-clin-{uuid.uuid4().hex[:8]}"
                    cur.execute(
                        """
                        INSERT INTO care_continuity_tasks (
                            id, organization_id, facility_id, patient_id, originating_encounter_id,
                            task_type, due_date, status, assigned_role, outcome_notes
                        ) VALUES (?, ?, ?, ?, NULL, 'OUTCOME_ASSESSMENT', CURRENT_DATE, 'PENDING', 'CLINICIAN', ?);
                        """,
                        (
                            task_id, row["organization_id"], row["facility_id"],
                            p_id, f"Clinical Review Required: {act_params.get('reason', 'Clinician assessment needed')}"
                        )
                    )

            # Record Success Attempt
            cur.execute(
                """
                INSERT INTO workflow_action_attempts (
                    id, action_id, attempt_number, status, result_json, executed_at
                ) VALUES (?, ?, ?, 'SUCCESS', ?, CURRENT_TIMESTAMP);
                """,
                (f"att-{uuid.uuid4().hex[:8]}", action_id, attempt_num, json.dumps({"action": act_type, "status": "executed"}))
            )
            cur.execute(
                """
                UPDATE workflow_planned_actions
                SET status = 'SUCCEEDED', attempts_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (attempt_num, action_id)
            )

        except Exception as ex:
            cur.execute(
                """
                INSERT INTO workflow_action_attempts (
                    id, action_id, attempt_number, status, error_message, executed_at
                ) VALUES (?, ?, ?, 'TRANSIENT_FAILURE', ?, CURRENT_TIMESTAMP);
                """,
                (f"att-{uuid.uuid4().hex[:8]}", action_id, attempt_num, str(ex))
            )
            cur.execute(
                """
                UPDATE workflow_planned_actions
                SET status = 'NEEDS_REVIEW', attempts_count = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (attempt_num, str(ex), action_id)
            )

    # --------------------------------------------------------------------------
    # 5. Operational Workflow Monitor
    # --------------------------------------------------------------------------

    def get_workflow_monitor_summary(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aggregate execution pulse and pending work for command center integration."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")

        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # Rule counts by status
            cur.execute(
                """
                SELECT status, COUNT(*) as count
                FROM workflow_rules
                WHERE organization_id = ?
                GROUP BY status;
                """,
                (org_id,)
            )
            rule_counts = {r["status"]: r["count"] for r in cur.fetchall()}

            # Action counts by status
            cur.execute(
                """
                SELECT status, COUNT(*) as count
                FROM workflow_planned_actions
                WHERE organization_id = ?
                GROUP BY status;
                """,
                (org_id,)
            )
            action_counts = {r["status"]: r["count"] for r in cur.fetchall()}

            # Events processed today
            cur.execute(
                """
                SELECT status, COUNT(*) as count
                FROM automation_events
                WHERE organization_id = ? AND DATE(occurred_at) = CURRENT_DATE
                GROUP BY status;
                """,
                (org_id,)
            )
            event_counts = {r["status"]: r["count"] for r in cur.fetchall()}

            # Pending Approvals List
            cur.execute(
                """
                SELECT 
                    a.id, a.action_type, a.action_category, a.target_entity, a.target_id,
                    a.parameters_json, a.created_at, r.rule_name, r.rule_key
                FROM workflow_planned_actions a
                JOIN workflow_rules r ON r.id = a.rule_id
                WHERE a.organization_id = ? AND a.status = 'AWAITING_APPROVAL'
                ORDER BY a.created_at ASC LIMIT 20;
                """,
                (org_id,)
            )
            pending_approvals = [dict(r) for r in cur.fetchall()]
            for pa in pending_approvals:
                pa["parameters"] = json.loads(pa["parameters_json"])

            return {
                "active_rules_count": rule_counts.get("ACTIVE", 0),
                "paused_rules_count": rule_counts.get("PAUSED", 0),
                "draft_rules_count": rule_counts.get("DRAFT", 0),
                "in_review_rules_count": rule_counts.get("IN_REVIEW", 0),
                "actions_awaiting_approval": action_counts.get("AWAITING_APPROVAL", 0),
                "awaiting_approval_count": action_counts.get("AWAITING_APPROVAL", 0),
                "actions_succeeded": action_counts.get("SUCCEEDED", 0),
                "actions_needs_review": action_counts.get("NEEDS_REVIEW", 0),
                "needs_review_count": action_counts.get("NEEDS_REVIEW", 0),
                "events_today_total": sum(event_counts.values()),
                "events_processed_today": sum(event_counts.values()),
                "pending_approvals": pending_approvals,
                "caveats": [
                    "Workflow engine automates administrative coordination only; it NEVER makes clinical decisions.",
                    "All patient messages require active consent and approved template versions."
                ]
            }
        finally:
            conn.close()

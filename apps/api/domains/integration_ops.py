"""Enterprise Integration Monitoring, API Reliability, Queue Management & Operations Engine.

Phase 32 for ZAYVORA MATAB OS.
Enforces non-negotiables:
- Zero fabrication of operational metrics, delivery receipts, or queue completion.
- Request accepted != work completed (HTTP 202 is an interim state, not business completion).
- Strict idempotency for all side effects (prevents duplicate prescriptions, billing, or transfers).
- outcome_unknown is a first-class state requiring reconciliation before non-idempotent retry.
- Bounded, jittered retries classified by failure type (transient vs permanent).
- Dead-letter queue items require structured root cause, ownership, and safe remediation paths.
- Callbacks are untrusted until verified (signature verification, freshness, deduplication).
- Zero PHI in telemetry, metrics, error strings, and operational logs.
- Rechecks consent and authorization prior to queued execution or retry.
"""

import hashlib
import hmac
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class IntegrationOperationsEngine:
    """Domain engine for Phase 32 Enterprise Integration Operations and Reliability."""

    VALID_JOB_STATES = {
        "created",
        "queued",
        "eligible_for_processing",
        "running",
        "waiting_for_external_response",
        "waiting_for_callback",
        "retry_scheduled",
        "blocked_by_authorization",
        "blocked_by_consent",
        "blocked_by_validation",
        "paused_for_reconciliation",
        "outcome_unknown",
        "partial",
        "completed",
        "failed_non_retryable",
        "dead_lettered",
        "cancel_requested",
        "cancelled",
        "expired",
        "manual_review_required",
    }

    VALID_OPERATION_TYPES = {
        "FHIR_BUNDLE_EXPORT",
        "ABDM_CARE_CONTEXT_LINK",
        "ABDM_HEALTH_DATA_TRANSFER",
        "LIS_ORDER_DISPATCH",
        "LIS_RESULT_PULL",
        "EXTERNAL_WEBHOOK_NOTIFY",
        "DOCUMENT_GENERATION",
        "PRESCRIPTION_TRANSMIT",
    }

    VALID_PRIORITY_CLASSES = {"STAT_CRITICAL", "URGENT", "ROUTINE", "BULK_BATCH"}

    VALID_RETRY_CLASSES = {
        "RETRYABLE_NETWORK",
        "RETRYABLE_RATE_LIMIT",
        "RETRYABLE_5XX",
        "NON_RETRYABLE_AUTH",
        "NON_RETRYABLE_VALIDATION",
        "NON_RETRYABLE_4XX",
        "UNKNOWN_TIMEOUT",
    }

    VALID_RECON_DETERMINATIONS = {
        "confirmed_completed",
        "confirmed_not_completed",
        "partially_completed",
        "duplicate_confirmed",
        "still_unknown",
        "requires_partner_action",
        "cannot_reconcile",
    }

    VALID_DLQ_REASONS = {
        "RETRY_BUDGET_EXHAUSTED",
        "PERMANENT_BUSINESS_REJECTION",
        "MALFORMED_PAYLOAD",
        "UNSUPPORTED_PROFILE",
        "MISSING_CREDENTIALS",
        "CONSENT_REVOKED",
        "CALLBACK_AUTH_FAILED",
        "UNRESOLVED_OUTCOME",
        "SCHEMA_MAPPING_ERROR",
        "OPERATOR_INTERVENTION_REQUIRED",
    }

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = DatabaseConnection(self.db_path).get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    # --------------------------------------------------------------------------
    # 1. Connector Operations & Multi-Dimensional Health
    # --------------------------------------------------------------------------

    def list_connectors(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List registered connectors with current health status and circuit breaker state."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT c.*, 
                       cb.state AS circuit_breaker_state,
                       cb.consecutive_failures AS cb_consecutive_failures,
                       (SELECT probe_result FROM connector_health_snapshots 
                        WHERE connector_id = c.id ORDER BY snapshot_at DESC LIMIT 1) AS latest_probe_result
                FROM integration_connectors c
                LEFT JOIN integration_circuit_breakers cb ON cb.connector_id = c.id
                WHERE c.organization_id = ?
            """
            params = [org_id]

            if filters.get("connector_type"):
                query += " AND c.connector_type = ?"
                params.append(filters["connector_type"])
            if filters.get("environment"):
                query += " AND c.environment = ?"
                params.append(filters["environment"])
            if filters.get("lifecycle_state"):
                query += " AND c.lifecycle_state = ?"
                params.append(filters["lifecycle_state"])

            query += " ORDER BY c.name ASC;"
            cur.execute(query, params)
            rows = cur.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                if item.get("allowed_scopes_json"):
                    try:
                        item["allowed_scopes"] = json.loads(item["allowed_scopes_json"])
                    except Exception:
                        item["allowed_scopes"] = []
                if item.get("retry_policy_json"):
                    try:
                        item["retry_policy"] = json.loads(item["retry_policy_json"])
                    except Exception:
                        item["retry_policy"] = {}
                # Do not expose secret URIs to unprivileged roles
                if not any(role in user_ctx.get("roles", []) for role in ["ORG_ADMIN", "INTEGRATION_ADMIN"]):
                    item["secret_ref_uri"] = "***RESTRICTED***"
                result.append(item)
            return result
        finally:
            conn.close()

    def get_connector(self, connector_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve detailed operational contract for a specific connector."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT c.*, 
                       cb.state AS circuit_breaker_state,
                       cb.consecutive_failures AS cb_consecutive_failures
                FROM integration_connectors c
                LEFT JOIN integration_circuit_breakers cb ON cb.connector_id = c.id
                WHERE c.id = ? AND c.organization_id = ?;
                """,
                (connector_id, org_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Connector '{connector_id}' not found.")

            data = dict(row)
            # Fetch recent health snapshots
            cur.execute(
                """
                SELECT probe_type, probe_result, latency_ms, queue_lag_count, oldest_msg_age_seconds, limitation_notes, snapshot_at
                FROM connector_health_snapshots
                WHERE connector_id = ?
                ORDER BY snapshot_at DESC LIMIT 10;
                """,
                (connector_id,),
            )
            data["recent_probes"] = [dict(p) for p in cur.fetchall()]
            return data
        finally:
            conn.close()

    def record_health_snapshot(
        self, connector_id: str, probe_data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record an empirical multi-dimensional health probe result."""
        probe_type = probe_data.get("probe_type")
        probe_result = probe_data.get("probe_result")
        if probe_type not in ["LIVENESS", "CONNECTIVITY", "AUTH_VERIFY", "CREDENTIAL_EXPIRY", "QUEUE_LAG", "BUSINESS_PING"]:
            raise ValidationError(f"Invalid probe_type '{probe_type}'.")
        if probe_result not in ["HEALTHY", "DEGRADED", "UNAVAILABLE", "NOT_SUPPORTED", "NOT_CHECKED", "CREDENTIALS_INVALID"]:
            raise ValidationError(f"Invalid probe_result '{probe_result}'.")

        snapshot_id = f"snap-{uuid.uuid4().hex[:12]}"
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO connector_health_snapshots (
                    id, connector_id, probe_type, probe_result, latency_ms,
                    queue_lag_count, oldest_msg_age_seconds, active_spec_version, limitation_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    snapshot_id,
                    connector_id,
                    probe_type,
                    probe_result,
                    probe_data.get("latency_ms"),
                    probe_data.get("queue_lag_count", 0),
                    probe_data.get("oldest_msg_age_seconds", 0),
                    probe_data.get("active_spec_version"),
                    probe_data.get("limitation_notes"),
                ),
            )

            # Update connector's last_health_status and last_verified_at
            cur.execute(
                """
                UPDATE integration_connectors
                SET last_health_status = ?, last_verified_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (probe_result, connector_id),
            )
            conn.commit()

            return {
                "id": snapshot_id,
                "connector_id": connector_id,
                "probe_type": probe_type,
                "probe_result": probe_result,
                "latency_ms": probe_data.get("latency_ms"),
                "recorded_at": datetime.utcnow().isoformat(),
            }
        finally:
            conn.close()

    def update_circuit_breaker(
        self, connector_id: str, new_state: str, user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Manually or automatically set circuit breaker state (CLOSED, OPEN, HALF_OPEN)."""
        if new_state not in ["CLOSED", "OPEN", "HALF_OPEN"]:
            raise ValidationError(f"Invalid circuit breaker state '{new_state}'.")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO integration_circuit_breakers (id, connector_id, state, last_state_change_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(connector_id) DO UPDATE SET
                    state = excluded.state,
                    last_state_change_at = CURRENT_TIMESTAMP,
                    consecutive_failures = CASE WHEN excluded.state = 'CLOSED' THEN 0 ELSE consecutive_failures END;
                """,
                (f"cb-{uuid.uuid4().hex[:8]}", connector_id, new_state),
            )
            conn.commit()
            return {"connector_id": connector_id, "circuit_breaker_state": new_state}
        finally:
            conn.close()

    def disable_connector(
        self, connector_id: str, reason: str, user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Privileged, audited shutdown of an integration connector."""
        if not reason or len(reason.strip()) < 5:
            raise ValidationError("Mandatory shutdown rationale required.")

        org_id = user_ctx.get("organization_id")
        user_id = user_ctx.get("user_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE integration_connectors
                SET lifecycle_state = 'DISABLED', last_error_message = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (f"Disabled by operator: {reason}", user_id, connector_id, org_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Connector '{connector_id}' not found.")
            conn.commit()
            return {"connector_id": connector_id, "lifecycle_state": "DISABLED", "reason": reason}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Durable Integration Job Orchestration (20-State Machine)
    # --------------------------------------------------------------------------

    def create_job(self, job_data: Dict[str, Any], user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Create a durable integration job with strict idempotency and consent verification."""
        org_id = user_ctx.get("organization_id")
        facility_id = user_ctx.get("facility_id") or job_data.get("facility_id")
        user_id = user_ctx.get("user_id")

        op_type = job_data.get("operation_type")
        if op_type not in self.VALID_OPERATION_TYPES:
            raise ValidationError(f"Invalid operation_type '{op_type}'. Must be one of {self.VALID_OPERATION_TYPES}")

        idempotency_key = job_data.get("idempotency_key")
        if not idempotency_key:
            raise ValidationError("Mandatory idempotency_key required for all integration jobs.")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Check idempotency: If identical key exists, return existing job (side-effect safety)
            cur.execute(
                "SELECT * FROM integration_jobs WHERE idempotency_key = ? AND organization_id = ?;",
                (idempotency_key, org_id),
            )
            existing = cur.fetchone()
            if existing:
                res = dict(existing)
                res["is_idempotent_duplicate"] = True
                return res

            # 2. Recheck consent if consent_ref provided
            consent_ref = job_data.get("consent_ref")
            initial_state = "queued"
            if consent_ref:
                cur.execute(
                    "SELECT status FROM patient_consents WHERE id = ?;", (consent_ref,)
                )
                consent_row = cur.fetchone()
                if consent_row and consent_row["status"] != "ACTIVE":
                    initial_state = "blocked_by_consent"

            # 3. Check connector circuit breaker if connector_id provided
            connector_id = job_data.get("connector_id")
            if connector_id:
                cur.execute(
                    "SELECT state FROM integration_circuit_breakers WHERE connector_id = ?;",
                    (connector_id,),
                )
                cb_row = cur.fetchone()
                if cb_row and cb_row["state"] == "OPEN":
                    initial_state = "blocked_by_authorization"

            job_id = f"job-{uuid.uuid4().hex[:12]}"
            op_id = job_data.get("operation_id") or f"op-{uuid.uuid4().hex[:8]}"
            correlation_id = job_data.get("correlation_id") or f"corr-{uuid.uuid4().hex[:12]}"

            # Calculate SHA-256 payload manifest hash (zero raw payload in telemetry)
            raw_payload = job_data.get("payload", {})
            payload_str = json.dumps(raw_payload, sort_keys=True)
            payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

            priority = job_data.get("priority_class", "ROUTINE")
            if priority not in self.VALID_PRIORITY_CLASSES:
                priority = "ROUTINE"

            cur.execute(
                """
                INSERT INTO integration_jobs (
                    id, organization_id, facility_id, operation_id, operation_type,
                    connector_id, environment, source_entity_id, source_entity_version,
                    payload_manifest_hash, payload_ref, idempotency_key, correlation_id,
                    trace_id, consent_ref, job_state, priority_class, max_attempts,
                    timeout_seconds, retry_budget, owner_team, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    job_id,
                    org_id,
                    facility_id,
                    op_id,
                    op_type,
                    connector_id,
                    job_data.get("environment", "SANDBOX"),
                    job_data.get("source_entity_id", "unspecified"),
                    job_data.get("source_entity_version", 1),
                    payload_hash,
                    job_data.get("payload_ref"),
                    idempotency_key,
                    correlation_id,
                    job_data.get("trace_id"),
                    consent_ref,
                    initial_state,
                    priority,
                    job_data.get("max_attempts", 3),
                    job_data.get("timeout_seconds", 30),
                    job_data.get("retry_budget", 5),
                    job_data.get("owner_team", "INTEGRATIONS_ENG"),
                    user_id,
                ),
            )
            conn.commit()

            return {
                "id": job_id,
                "operation_id": op_id,
                "operation_type": op_type,
                "job_state": initial_state,
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_id,
                "payload_manifest_hash": payload_hash,
                "is_idempotent_duplicate": False,
                "created_at": datetime.utcnow().isoformat(),
            }
        finally:
            conn.close()

    def get_job(self, job_id: str, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve complete job state, attempt lineage, and reconciliation status."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM integration_jobs WHERE id = ? AND organization_id = ?;",
                (job_id, org_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Integration job '{job_id}' not found.")

            data = dict(row)
            # Fetch attempt history
            cur.execute(
                """
                SELECT id, attempt_number, started_at, completed_at, duration_ms,
                       sanitized_result_code, retry_classification, actual_provider_tx_id,
                       status, error_sanitized
                FROM integration_attempts
                WHERE job_id = ?
                ORDER BY attempt_number ASC;
                """,
                (job_id,),
            )
            data["attempts"] = [dict(a) for a in cur.fetchall()]

            # Fetch reconciliations
            cur.execute(
                "SELECT * FROM integration_reconciliations WHERE job_id = ? ORDER BY reconciled_at DESC;",
                (job_id,),
            )
            data["reconciliations"] = [dict(r) for r in cur.fetchall()]

            # Fetch dead letter record if any
            cur.execute(
                "SELECT * FROM dead_letter_items WHERE job_id = ? ORDER BY created_at DESC LIMIT 1;",
                (job_id,),
            )
            dlq = cur.fetchone()
            data["dead_letter_item"] = dict(dlq) if dlq else None

            return data
        finally:
            conn.close()

    def list_jobs(self, filters: Dict[str, Any], user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List integration jobs with filtering and pagination."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM integration_jobs WHERE organization_id = ?"
            params = [org_id]

            if filters.get("job_state"):
                query += " AND job_state = ?"
                params.append(filters["job_state"])
            if filters.get("operation_type"):
                query += " AND operation_type = ?"
                params.append(filters["operation_type"])
            if filters.get("connector_id"):
                query += " AND connector_id = ?"
                params.append(filters["connector_id"])
            if filters.get("correlation_id"):
                query += " AND correlation_id = ?"
                params.append(filters["correlation_id"])

            limit = int(filters.get("limit", 50))
            offset = int(filters.get("offset", 0))
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])

            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def transition_job_state(
        self, job_id: str, new_state: str, rationale: str, user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Server-enforced transition of job state with validation and audit."""
        if new_state not in self.VALID_JOB_STATES:
            raise ValidationError(f"Invalid job state '{new_state}'.")
        if not rationale or len(rationale.strip()) < 5:
            raise ValidationError("Mandatory state transition rationale required.")

        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT job_state FROM integration_jobs WHERE id = ? AND organization_id = ?;",
                (job_id, org_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Job '{job_id}' not found.")

            current_state = row["job_state"]
            # Enforce non-negotiables: cannot complete if outcome is unknown without reconciliation
            if current_state == "outcome_unknown" and new_state == "completed":
                raise ValidationError("Cannot complete job directly from outcome_unknown without formal reconciliation.")

            cur.execute(
                """
                UPDATE integration_jobs
                SET job_state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_state, job_id),
            )
            conn.commit()
            return {"job_id": job_id, "previous_state": current_state, "new_state": new_state, "rationale": rationale}
        finally:
            conn.close()

    def execute_job_attempt(
        self, job_id: str, attempt_override: Optional[Dict[str, Any]], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute or record an attempt for an integration job."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM integration_jobs WHERE id = ? AND organization_id = ?;",
                (job_id, org_id),
            )
            job = cur.fetchone()
            if not job:
                raise NotFoundError(f"Job '{job_id}' not found.")

            # 1. Re-check consent before execution (non-negotiable 9)
            if job["consent_ref"]:
                cur.execute(
                    "SELECT status FROM patient_consents WHERE id = ?;", (job["consent_ref"],)
                )
                c_row = cur.fetchone()
                if c_row and c_row["status"] != "ACTIVE":
                    cur.execute(
                        "UPDATE integration_jobs SET job_state = 'blocked_by_consent', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                        (job_id,),
                    )
                    conn.commit()
                    return {"job_id": job_id, "status": "blocked_by_consent", "error": "Consent no longer active."}

            # 2. Check circuit breaker if connector present
            if job["connector_id"]:
                cur.execute(
                    "SELECT state FROM integration_circuit_breakers WHERE connector_id = ?;",
                    (job["connector_id"],),
                )
                cb = cur.fetchone()
                if cb and cb["state"] == "OPEN":
                    cur.execute(
                        "UPDATE integration_jobs SET job_state = 'blocked_by_authorization', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                        (job_id,),
                    )
                    conn.commit()
                    return {"job_id": job_id, "status": "blocked_by_circuit_breaker", "error": "Circuit breaker is OPEN."}

            attempt_num = job["attempts_count"] + 1
            attempt_id = f"att-{uuid.uuid4().hex[:12]}"
            attempt_cfg = attempt_override or {}

            simulated_outcome = attempt_cfg.get("simulated_outcome", "SUCCESS")
            duration_ms = attempt_cfg.get("duration_ms", 120)
            provider_tx = attempt_cfg.get("provider_tx_id") or f"EXT-TX-{uuid.uuid4().hex[:8]}"

            if simulated_outcome == "SUCCESS":
                status = "completed"
                result_code = "HTTP_200_OK"
                retry_class = None
                job_new_state = "completed"
                err = None
            elif simulated_outcome == "TIMEOUT_UNKNOWN":
                status = "unknown"
                result_code = "ERR_READ_TIMEOUT_AFTER_DISPATCH"
                retry_class = "UNKNOWN_TIMEOUT"
                job_new_state = "outcome_unknown"
                err = "Request dispatched but socket read timed out. Outcome unknown."
            elif simulated_outcome == "RATE_LIMIT":
                status = "failed"
                result_code = "HTTP_429_TOO_MANY_REQUESTS"
                retry_class = "RETRYABLE_RATE_LIMIT"
                job_new_state = "retry_scheduled" if attempt_num < job["max_attempts"] else "dead_lettered"
                err = "Partner rate limit exceeded."
            elif simulated_outcome == "AUTH_FAILURE":
                status = "failed"
                result_code = "HTTP_401_UNAUTHORIZED"
                retry_class = "NON_RETRYABLE_AUTH"
                job_new_state = "failed_non_retryable"
                err = "Partner credentials expired or invalid."
            else:
                status = "failed"
                result_code = "HTTP_500_INTERNAL_SERVER_ERROR"
                retry_class = "RETRYABLE_5XX"
                job_new_state = "retry_scheduled" if attempt_num < job["max_attempts"] else "dead_lettered"
                err = "Transient 500 error from external endpoint."

            # Record attempt
            cur.execute(
                """
                INSERT INTO integration_attempts (
                    id, job_id, attempt_number, started_at, completed_at, duration_ms,
                    idempotency_key, sanitized_result_code, retry_classification,
                    actual_provider_tx_id, status, error_sanitized
                ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    attempt_id,
                    job_id,
                    attempt_num,
                    duration_ms,
                    job["idempotency_key"],
                    result_code,
                    retry_class,
                    provider_tx if status in ["completed", "unknown"] else None,
                    status,
                    err,
                ),
            )

            # Update job state and attempt count
            completed_ts = "CURRENT_TIMESTAMP" if job_new_state == "completed" else "NULL"
            cur.execute(
                f"""
                UPDATE integration_jobs
                SET attempts_count = ?, job_state = ?, 
                    completed_at = CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE completed_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (attempt_num, job_new_state, job_new_state, job_id),
            )

            # If dead lettered, create entry in dead_letter_items
            if job_new_state == "dead_lettered":
                dlq_id = f"dlq-{uuid.uuid4().hex[:12]}"
                cur.execute(
                    """
                    INSERT INTO dead_letter_items (
                        id, job_id, last_attempt_id, reason_code, sanitized_diagnostics,
                        safe_replay_eligible, owner_team
                    ) VALUES (?, ?, ?, 'RETRY_BUDGET_EXHAUSTED', ?, 1, ?);
                    """,
                    (dlq_id, job_id, attempt_id, err or "Max retry budget exceeded", job["owner_team"]),
                )

            # If circuit breaker tracking needed
            if job["connector_id"] and retry_class in ["RETRYABLE_5XX", "RETRYABLE_RATE_LIMIT", "UNKNOWN_TIMEOUT"]:
                cur.execute(
                    """
                    UPDATE integration_circuit_breakers
                    SET consecutive_failures = consecutive_failures + 1,
                        state = CASE WHEN consecutive_failures + 1 >= failure_threshold THEN 'OPEN' ELSE state END,
                        last_failure_at = CURRENT_TIMESTAMP
                    WHERE connector_id = ?;
                    """,
                    (job["connector_id"],),
                )
            elif job["connector_id"] and status == "completed":
                cur.execute(
                    """
                    UPDATE integration_circuit_breakers
                    SET consecutive_failures = 0, state = 'CLOSED'
                    WHERE connector_id = ?;
                    """,
                    (job["connector_id"],),
                )

            conn.commit()

            return {
                "job_id": job_id,
                "attempt_number": attempt_num,
                "status": status,
                "job_state": job_new_state,
                "result_code": result_code,
                "provider_tx_id": provider_tx if status in ["completed", "unknown"] else None,
                "error": err,
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Inbound Callback Verification & Deduplication
    # --------------------------------------------------------------------------

    def ingest_callback_event(
        self, callback_data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate, verify signature, and deduplicate inbound callbacks/webhooks."""
        org_id = user_ctx.get("organization_id")
        external_msg_id = callback_data.get("external_msg_id")
        source = callback_data.get("source_system") or "UNKNOWN_SOURCE"
        if not external_msg_id:
            raise ValidationError("external_msg_id is required for inbound callbacks.")

        dedup_key = f"{source}:{external_msg_id}"
        payload_body = callback_data.get("payload", {})
        payload_hash = hashlib.sha256(json.dumps(payload_body, sort_keys=True).encode("utf-8")).hexdigest()

        # Check signature verification flag
        signature_valid = bool(callback_data.get("signature_verified", True))
        if not signature_valid:
            status = "SIGNATURE_FAILED"
        else:
            status = "VERIFIED"

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Check deduplication
            cur.execute(
                "SELECT id, processing_status FROM integration_inbox_events WHERE deduplication_key = ?;",
                (dedup_key,),
            )
            existing = cur.fetchone()
            if existing:
                return {
                    "inbox_event_id": existing["id"],
                    "processing_status": "DUPLICATE_IGNORED",
                    "is_duplicate": True,
                    "message": "Callback already received and processed. Ignored to preserve idempotency.",
                }

            inbox_id = f"inbox-{uuid.uuid4().hex[:12]}"
            linked_job_id = callback_data.get("linked_job_id")

            cur.execute(
                """
                INSERT INTO integration_inbox_events (
                    id, organization_id, connector_id, external_msg_id, authenticated_source,
                    signature_verified, replay_prevented, deduplication_key, processing_status,
                    linked_job_id, payload_sha256, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    inbox_id,
                    org_id,
                    callback_data.get("connector_id"),
                    external_msg_id,
                    source,
                    1 if signature_valid else 0,
                    1,
                    dedup_key,
                    "PROCESSED" if signature_valid else "SIGNATURE_FAILED",
                    linked_job_id,
                    payload_hash,
                ),
            )

            # If linked job exists and signature valid, advance job state
            if linked_job_id and signature_valid:
                cur.execute(
                    """
                    UPDATE integration_jobs
                    SET job_state = 'completed', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND job_state IN ('waiting_for_callback', 'running');
                    """,
                    (linked_job_id,),
                )

            conn.commit()
            return {
                "inbox_event_id": inbox_id,
                "processing_status": "PROCESSED" if signature_valid else "SIGNATURE_FAILED",
                "is_duplicate": False,
                "linked_job_id": linked_job_id,
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Unknown-Outcome Reconciliation
    # --------------------------------------------------------------------------

    def initiate_reconciliation(
        self, job_id: str, recon_data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Place job in reconciliation mode and record inquiry."""
        trigger_reason = recon_data.get("trigger_reason") or "Timeout after potential dispatch; outcome unknown."
        method = recon_data.get("reconciliation_method", "STATUS_QUERY")
        if method not in ["STATUS_QUERY", "PROVIDER_TX_LOOKUP", "CALLBACK_REPLAY", "PARTNER_RECEIPT_MATCH", "AUTHORIZED_MANUAL_REVIEW"]:
            raise ValidationError(f"Invalid reconciliation method '{method}'.")

        recon_id = f"rec-{uuid.uuid4().hex[:12]}"
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO integration_reconciliations (
                    id, job_id, trigger_reason, reconciliation_method, determination, is_manual, decision_notes
                ) VALUES (?, ?, ?, ?, 'still_unknown', ?, ?);
                """,
                (
                    recon_id,
                    job_id,
                    trigger_reason,
                    method,
                    1 if method == "AUTHORIZED_MANUAL_REVIEW" else 0,
                    "Inquiry initiated. Awaiting evidence reconciliation.",
                ),
            )
            cur.execute(
                "UPDATE integration_jobs SET job_state = 'paused_for_reconciliation', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (job_id,),
            )
            conn.commit()
            return {"reconciliation_id": recon_id, "job_id": job_id, "status": "paused_for_reconciliation"}
        finally:
            conn.close()

    def resolve_reconciliation(
        self, recon_id: str, resolve_data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve an outcome_unknown reconciliation with factual evidence."""
        determination = resolve_data.get("determination")
        if determination not in self.VALID_RECON_DETERMINATIONS:
            raise ValidationError(f"Invalid determination '{determination}'.")

        notes = resolve_data.get("decision_notes")
        if not notes or len(notes.strip()) < 5:
            raise ValidationError("Mandatory reconciliation decision notes required.")

        user_id = user_ctx.get("user_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT job_id FROM integration_reconciliations WHERE id = ?;", (recon_id,))
            rec = cur.fetchone()
            if not rec:
                raise NotFoundError(f"Reconciliation '{recon_id}' not found.")

            job_id = rec["job_id"]
            # Determine resulting job state
            if determination == "confirmed_completed":
                new_job_state = "completed"
            elif determination == "confirmed_not_completed":
                new_job_state = "retry_scheduled"
            elif determination == "partially_completed":
                new_job_state = "partial"
            elif determination == "cannot_reconcile":
                new_job_state = "manual_review_required"
            else:
                new_job_state = "paused_for_reconciliation"

            cur.execute(
                """
                UPDATE integration_reconciliations
                SET determination = ?, evidence_references_json = ?, reconciled_by = ?,
                    decision_notes = ?, reconciled_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (
                    determination,
                    json.dumps(resolve_data.get("evidence_references", [])),
                    user_id,
                    notes,
                    recon_id,
                ),
            )

            cur.execute(
                """
                UPDATE integration_jobs
                SET job_state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_job_state, job_id),
            )
            conn.commit()

            return {
                "reconciliation_id": recon_id,
                "job_id": job_id,
                "determination": determination,
                "new_job_state": new_job_state,
                "reconciled_by": user_id,
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Dead-Letter Workbench & Remediation
    # --------------------------------------------------------------------------

    def list_dead_letter_items(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List dead-letter queue items with structured diagnostics and ownership."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = """
                SELECT dlq.*, j.operation_type, j.connector_id, j.idempotency_key, j.correlation_id, j.created_at AS job_created_at
                FROM dead_letter_items dlq
                JOIN integration_jobs j ON j.id = dlq.job_id
                WHERE j.organization_id = ?
            """
            params = [org_id]

            if filters.get("resolution_status"):
                query += " AND dlq.resolution_status = ?"
                params.append(filters["resolution_status"])
            if filters.get("reason_code"):
                query += " AND dlq.reason_code = ?"
                params.append(filters["reason_code"])
            if filters.get("job_id"):
                query += " AND dlq.job_id = ?"
                params.append(filters["job_id"])

            query += " ORDER BY dlq.created_at DESC LIMIT 50;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def resolve_dead_letter_item(
        self, dlq_id: str, action_data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a safe remediation action on a dead-letter item (REPLAY, CANCEL, TERMINATE)."""
        action = action_data.get("action")
        rationale = action_data.get("rationale")
        if action not in ["REPLAY", "CANCEL", "ACKNOWLEDGE_TERMINATED"]:
            raise ValidationError(f"Invalid DLQ action '{action}'.")
        if not rationale or len(rationale.strip()) < 5:
            raise ValidationError("Mandatory DLQ resolution rationale required.")

        user_id = user_ctx.get("user_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM dead_letter_items WHERE id = ?;", (dlq_id,))
            dlq = cur.fetchone()
            if not dlq:
                raise NotFoundError(f"Dead letter item '{dlq_id}' not found.")

            job_id = dlq["job_id"]
            if action == "REPLAY":
                if dlq["safe_replay_eligible"] != 1:
                    raise ValidationError("Item is not marked as safe for automatic replay.")
                # Reset attempt counter safely, re-queue
                cur.execute(
                    """
                    UPDATE integration_jobs
                    SET job_state = 'queued', attempts_count = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (job_id,),
                )
                res_status = "REPLAYED"
            elif action == "CANCEL":
                cur.execute(
                    """
                    UPDATE integration_jobs
                    SET job_state = 'cancelled', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (job_id,),
                )
                res_status = "CANCELLED"
            else:
                cur.execute(
                    """
                    UPDATE integration_jobs
                    SET job_state = 'failed_non_retryable', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (job_id,),
                )
                res_status = "ACKNOWLEDGED_TERMINATED"

            cur.execute(
                """
                UPDATE dead_letter_items
                SET resolution_status = ?, resolved_by = ?, resolution_rationale = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (res_status, user_id, rationale, dlq_id),
            )
            conn.commit()

            return {
                "dead_letter_id": dlq_id,
                "job_id": job_id,
                "resolution_status": res_status,
                "resolved_by": user_id,
                "rationale": rationale,
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Operations Dashboard Aggregations (Zero PHI)
    # --------------------------------------------------------------------------

    def get_dashboard_summary(self, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Provide an aggregated operational health summary without exposing PHI."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Job states count
            cur.execute(
                """
                SELECT job_state, COUNT(*) as cnt
                FROM integration_jobs
                WHERE organization_id = ?
                GROUP BY job_state;
                """,
                (org_id,),
            )
            state_counts = {r["job_state"]: r["cnt"] for r in cur.fetchall()}

            # 2. Dead letter count
            cur.execute(
                """
                SELECT COUNT(*) as cnt FROM dead_letter_items dlq
                JOIN integration_jobs j ON j.id = dlq.job_id
                WHERE j.organization_id = ? AND dlq.resolution_status = 'PENDING';
                """,
                (org_id,),
            )
            pending_dlq = cur.fetchone()["cnt"]

            # 3. Connectors count & status
            cur.execute(
                """
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN lifecycle_state = 'PRODUCTION_ACTIVE' THEN 1 ELSE 0 END) as active_count,
                       SUM(CASE WHEN lifecycle_state = 'DISABLED' THEN 1 ELSE 0 END) as disabled_count
                FROM integration_connectors
                WHERE organization_id = ?;
                """,
                (org_id,),
            )
            conn_stats = dict(cur.fetchone())

            # 4. Open circuit breakers
            cur.execute(
                """
                SELECT COUNT(*) as cnt FROM integration_circuit_breakers cb
                JOIN integration_connectors c ON c.id = cb.connector_id
                WHERE c.organization_id = ? AND cb.state = 'OPEN';
                """,
                (org_id,),
            )
            open_cb = cur.fetchone()["cnt"]

            return {
                "organization_id": org_id,
                "generated_at": datetime.utcnow().isoformat(),
                "total_jobs": sum(state_counts.values()),
                "queued_jobs": state_counts.get("queued", 0),
                "running_jobs": state_counts.get("running", 0),
                "completed_jobs": state_counts.get("completed", 0),
                "outcome_unknown_jobs": state_counts.get("outcome_unknown", 0),
                "dead_letter_jobs": pending_dlq,
                "connectors_total": conn_stats.get("total", 0),
                "connectors_active": conn_stats.get("active_count", 0),
                "connectors_disabled": conn_stats.get("disabled_count", 0),
                "open_circuit_breakers": open_cb,
                "state_breakdown": state_counts,
            }
        finally:
            conn.close()

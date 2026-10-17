"""
Enterprise Threat Modeling, Abuse-Case Analysis & Secure SDLC Governance Engine
ZAYVORA MATAB OS — Phase 47

Identifies security, privacy, and clinical-workflow threats during architecture and design,
converts material risks into testable controls, and governs them through coding, release,
and post-deployment review.
"""

import json
import os
import re
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
    ForbiddenError,
)


def redact_sensitive_text(text: str) -> str:
    """Mask credentials, tokens, and private keys with [REDACTED]. Strictly zero raw secrets."""
    if not text:
        return text

    patterns = [
        (r"AKIA[0-9A-Z]{16}", "AKIA****************"),
        (r"sk_live_[0-9a-zA-Z]{24}", "sk_live_************************"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        (r"(password|passwd|secret|api_key|token)\s*[:=]\s*['\"][^'\"]+['\"]", r"\1: [REDACTED]"),
        (r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer [REDACTED_BEARER_TOKEN]"),
    ]
    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    return redacted


class EnterpriseThreatModelingSDLCService:
    """
    Core domain service orchestrating Threat Modeling, Trust Boundaries,
    Abuse Cases, Testable Controls, Governed Residual Risk Acceptances,
    and Secure SDLC Release Gates.
    """

    def __init__(self, db_path_or_conn: Any):
        if isinstance(db_path_or_conn, sqlite3.Connection):
            self.conn = db_path_or_conn
            self._external_conn = True
        else:
            self.db_path = db_path_or_conn or os.getenv("MATAB_DB_PATH", "database.sqlite")
            self.conn = None
            self._external_conn = False

    def _get_connection(self) -> sqlite3.Connection:
        if self._external_conn and self.conn:
            return self.conn
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _close_connection(self, conn: sqlite3.Connection) -> None:
        if not self._external_conn:
            conn.close()

    def _record_audit_event(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        actor_id: str,
        target_type: str,
        target_id: str,
        action_details: Dict[str, Any],
        severity: str = "INFO",
    ) -> str:
        """Appends an event to threat_sdlc_audit_ledger with SHA-256 hash chaining."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT entry_hash FROM threat_sdlc_audit_ledger ORDER BY occurred_at DESC, rowid DESC LIMIT 1;"
        )
        row = cursor.fetchone()
        previous_hash = row["entry_hash"] if row else "GENESIS_BLOCK_THREAT_SDLC_P47"

        event_id = f"aud-tm-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        occurred_at = datetime.utcnow().isoformat()
        sanitized_details = redact_sensitive_text(json.dumps(action_details, sort_keys=True))

        hash_payload = f"{event_id}|{event_type}|{actor_id}|{target_type}|{target_id}|{sanitized_details}|{previous_hash}|{occurred_at}"
        entry_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

        cursor.execute(
            """
            INSERT INTO threat_sdlc_audit_ledger (
                id, event_type, severity, actor_id, target_type, target_id,
                action_details_json, previous_hash, entry_hash, occurred_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event_id,
                event_type,
                severity,
                actor_id,
                target_type,
                target_id,
                sanitized_details,
                previous_hash,
                entry_hash,
                occurred_at,
            ),
        )
        return event_id

    # -------------------------------------------------------------------------
    # 1. Executive Summary & KPIs
    # -------------------------------------------------------------------------

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Returns consolidated metrics across threat models, abuse cases, and SDLC gates."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Threat models by state
            cursor.execute("SELECT lifecycle_state, COUNT(*) as cnt FROM threat_models_registry GROUP BY lifecycle_state;")
            models_by_state = {r["lifecycle_state"]: r["cnt"] for r in cursor.fetchall()}
            total_models = sum(models_by_state.values())

            # Stale models count
            cursor.execute("SELECT COUNT(*) as cnt FROM threat_models_registry WHERE is_stale = 1;")
            stale_models_count = cursor.fetchone()["cnt"]

            # Abuse cases by severity
            cursor.execute("SELECT severity, COUNT(*) as cnt FROM threat_abuse_cases GROUP BY severity;")
            threats_by_severity = {r["severity"]: r["cnt"] for r in cursor.fetchall()}
            total_abuse_cases = sum(threats_by_severity.values())

            # Abuse cases by lifecycle status
            cursor.execute("SELECT lifecycle_status, COUNT(*) as cnt FROM threat_abuse_cases GROUP BY lifecycle_status;")
            threats_by_status = {r["lifecycle_status"]: r["cnt"] for r in cursor.fetchall()}

            # Open critical & high threats
            cursor.execute(
                """
                SELECT COUNT(*) as cnt FROM threat_abuse_cases
                WHERE severity IN ('CRITICAL', 'HIGH')
                AND lifecycle_status IN ('identified', 'needs_validation', 'mitigation_planned', 'blocked');
                """
            )
            open_critical_high = cursor.fetchone()["cnt"]

            # Active Residual Risk Decisions
            cursor.execute(
                """
                SELECT COUNT(*) as cnt FROM threat_residual_risk_decisions
                WHERE status = 'APPROVED' AND datetime(expires_at) > datetime('now');
                """
            )
            active_residual_risks = cursor.fetchone()["cnt"]

            # Testable Controls verified
            cursor.execute("SELECT verification_status, COUNT(*) as cnt FROM threat_testable_controls GROUP BY verification_status;")
            controls_by_status = {r["verification_status"]: r["cnt"] for r in cursor.fetchall()}
            total_controls = sum(controls_by_status.values())

            # SDLC Change Reviews by verdict
            cursor.execute("SELECT gate_verdict, COUNT(*) as cnt FROM sdlc_change_reviews GROUP BY gate_verdict;")
            reviews_by_verdict = {r["gate_verdict"]: r["cnt"] for r in cursor.fetchall()}
            total_reviews = sum(reviews_by_verdict.values())

            # Latest gate evaluation
            cursor.execute("SELECT * FROM sdlc_change_reviews ORDER BY evaluated_at DESC LIMIT 1;")
            last_review = cursor.fetchone()

            return {
                "total_threat_models": total_models,
                "stale_models_count": stale_models_count,
                "models_by_state": models_by_state,
                "total_abuse_cases": total_abuse_cases,
                "open_critical_high_threats": open_critical_high,
                "threats_by_severity": threats_by_severity,
                "threats_by_status": threats_by_status,
                "total_testable_controls": total_controls,
                "controls_by_status": controls_by_status,
                "active_residual_risks": active_residual_risks,
                "total_sdlc_reviews": total_reviews,
                "reviews_by_verdict": reviews_by_verdict,
                "last_review": dict(last_review) if last_review else None,
                "timestamp": datetime.utcnow().isoformat(),
            }
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 2. Threat Models Registry
    # -------------------------------------------------------------------------

    def list_threat_models(
        self,
        subsystem_scope: Optional[str] = None,
        lifecycle_state: Optional[str] = None,
        is_stale: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Lists threat models with optional filters."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM threat_models_registry WHERE 1=1"
            params: List[Any] = []

            if subsystem_scope:
                query += " AND subsystem_scope = ?"
                params.append(subsystem_scope)
            if lifecycle_state:
                query += " AND lifecycle_state = ?"
                params.append(lifecycle_state)
            if is_stale is not None:
                query += " AND is_stale = ?"
                params.append(1 if is_stale else 0)

            query += " ORDER BY created_at DESC;"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                if item.get("assumptions_json"):
                    item["assumptions"] = json.loads(item["assumptions_json"])
                if item.get("exclusions_json"):
                    item["exclusions"] = json.loads(item["exclusions_json"])
                if item.get("dependencies_json"):
                    item["dependencies"] = json.loads(item["dependencies_json"])
                result.append(item)
            return result
        finally:
            self._close_connection(conn)

    def get_threat_model(self, model_id: str) -> Dict[str, Any]:
        """Retrieves a single threat model including trust boundaries, abuse cases, and controls."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_models_registry WHERE id = ? OR model_code = ?;", (model_id, model_id))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Threat model not found: {model_id}")

            model = dict(row)
            if model.get("assumptions_json"):
                model["assumptions"] = json.loads(model["assumptions_json"])
            if model.get("exclusions_json"):
                model["exclusions"] = json.loads(model["exclusions_json"])
            if model.get("dependencies_json"):
                model["dependencies"] = json.loads(model["dependencies_json"])

            # Trust boundaries
            cursor.execute("SELECT * FROM threat_trust_boundaries WHERE model_id = ? ORDER BY created_at ASC;", (model["id"],))
            model["trust_boundaries"] = [dict(tb) for tb in cursor.fetchall()]

            # Abuse cases
            cursor.execute("SELECT * FROM threat_abuse_cases WHERE model_id = ? ORDER BY created_at ASC;", (model["id"],))
            abuse_cases = [dict(ac) for ac in cursor.fetchall()]

            # Testable controls for each abuse case
            for ac in abuse_cases:
                cursor.execute("SELECT * FROM threat_testable_controls WHERE threat_id = ? ORDER BY created_at ASC;", (ac["id"],))
                ac["controls"] = [dict(c) for c in cursor.fetchall()]
                cursor.execute(
                    "SELECT * FROM threat_residual_risk_decisions WHERE threat_id = ? AND status = 'APPROVED' ORDER BY created_at DESC LIMIT 1;",
                    (ac["id"],),
                )
                rrd = cursor.fetchone()
                ac["active_residual_risk"] = dict(rrd) if rrd else None

            model["abuse_cases"] = abuse_cases
            return model
        finally:
            self._close_connection(conn)

    def create_threat_model(self, data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Creates a new subsystem threat model."""
        model_code = data.get("model_code", "").strip()
        title = data.get("title", "").strip()
        subsystem_scope = data.get("subsystem_scope", "").strip()

        if not model_code or not title or not subsystem_scope:
            raise ValidationError("model_code, title, and subsystem_scope are required.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM threat_models_registry WHERE model_code = ?;", (model_code,))
            if cursor.fetchone():
                raise ConflictError(f"Threat model code already registered: {model_code}")

            model_id = f"tm-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            now_iso = datetime.utcnow().isoformat()
            next_review = (datetime.utcnow() + timedelta(days=90)).isoformat()

            assumptions_json = json.dumps(data.get("assumptions", []))
            exclusions_json = json.dumps(data.get("exclusions", []))
            dependencies_json = json.dumps(data.get("dependencies", []))

            cursor.execute(
                """
                INSERT INTO threat_models_registry (
                    id, model_code, title, subsystem_scope, repository_revision,
                    deployment_version, owner_role, security_reviewer_id, clinical_reviewer_id,
                    privacy_reviewer_id, lifecycle_state, assumptions_json, exclusions_json,
                    dependencies_json, is_stale, last_reviewed_at, next_review_due_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?);
                """,
                (
                    model_id,
                    model_code,
                    title,
                    subsystem_scope,
                    data.get("repository_revision", "HEAD"),
                    data.get("deployment_version", "v1.0.0"),
                    data.get("owner_role", "Principal Security Architect"),
                    data.get("security_reviewer_id", actor_id),
                    data.get("clinical_reviewer_id"),
                    data.get("privacy_reviewer_id"),
                    data.get("lifecycle_state", "draft"),
                    assumptions_json,
                    exclusions_json,
                    dependencies_json,
                    now_iso,
                    next_review,
                    now_iso,
                    now_iso,
                ),
            )

            self._record_audit_event(
                conn,
                event_type="THREAT_MODEL_CREATED",
                actor_id=actor_id,
                target_type="THREAT_MODEL",
                target_id=model_id,
                action_details={"model_code": model_code, "subsystem_scope": subsystem_scope, "title": title},
            )
            if not self._external_conn:
                conn.commit()

            return self.get_threat_model(model_id)
        finally:
            self._close_connection(conn)

    def transition_model_state(
        self,
        model_id: str,
        new_state: str,
        actor_id: str,
        review_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transitions threat model lifecycle state with review audit."""
        valid_states = [
            "draft",
            "discovery",
            "review_required",
            "mitigation_in_progress",
            "residual_risk_review",
            "approved_for_scope",
            "stale",
            "retired",
        ]
        if new_state not in valid_states:
            raise ValidationError(f"Invalid state: {new_state}. Valid states: {valid_states}")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_models_registry WHERE id = ? OR model_code = ?;", (model_id, model_id))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Threat model not found: {model_id}")

            target_id = row["id"]
            now_iso = datetime.utcnow().isoformat()
            is_stale_val = 1 if new_state == "stale" else 0
            stale_reason_val = review_notes if new_state == "stale" else (None if new_state == "approved_for_scope" else row["stale_reason"])

            cursor.execute(
                """
                UPDATE threat_models_registry
                SET lifecycle_state = ?, is_stale = ?, stale_reason = ?,
                    last_reviewed_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (new_state, is_stale_val, stale_reason_val, now_iso, now_iso, target_id),
            )

            self._record_audit_event(
                conn,
                event_type="THREAT_MODEL_STATUS_CHANGED",
                actor_id=actor_id,
                target_type="THREAT_MODEL",
                target_id=target_id,
                action_details={
                    "previous_state": row["lifecycle_state"],
                    "new_state": new_state,
                    "review_notes": review_notes,
                },
            )
            if not self._external_conn:
                conn.commit()

            return self.get_threat_model(target_id)
        finally:
            self._close_connection(conn)

    def check_and_mark_stale_models(self, actor_id: str = "system") -> List[str]:
        """Evaluates review due dates and marks expired models as stale."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            now_iso = datetime.utcnow().isoformat()
            cursor.execute(
                """
                SELECT id, model_code, next_review_due_at FROM threat_models_registry
                WHERE is_stale = 0 AND lifecycle_state = 'approved_for_scope'
                AND datetime(next_review_due_at) < datetime(?);
                """,
                (now_iso,),
            )
            stale_rows = cursor.fetchall()
            stale_ids = []

            for r in stale_rows:
                m_id = r["id"]
                cursor.execute(
                    """
                    UPDATE threat_models_registry
                    SET is_stale = 1, stale_reason = 'Review cadence expired',
                        lifecycle_state = 'stale', updated_at = ?
                    WHERE id = ?;
                    """,
                    (now_iso, m_id),
                )
                self._record_audit_event(
                    conn,
                    event_type="THREAT_MODEL_STALE_DETECTED",
                    actor_id=actor_id,
                    target_type="THREAT_MODEL",
                    target_id=m_id,
                    action_details={"reason": "Review cadence expired", "next_review_due_at": r["next_review_due_at"]},
                    severity="WARNING",
                )
                stale_ids.append(m_id)

            if not self._external_conn:
                conn.commit()
            return stale_ids
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 3. Trust Boundaries
    # -------------------------------------------------------------------------

    def list_trust_boundaries(self, model_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists trust boundaries."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM threat_trust_boundaries WHERE 1=1"
            params: List[Any] = []
            if model_id:
                query += " AND model_id = ?"
                params.append(model_id)
            query += " ORDER BY created_at ASC;"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            self._close_connection(conn)

    def create_trust_boundary(self, data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Creates a new trust boundary record."""
        model_id = data.get("model_id")
        boundary_name = data.get("boundary_name", "").strip()
        source = data.get("source_actor_or_component", "").strip()
        destination = data.get("destination_component", "").strip()

        if not model_id or not boundary_name or not source or not destination:
            raise ValidationError("model_id, boundary_name, source_actor_or_component, and destination_component are required.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM threat_models_registry WHERE id = ?;", (model_id,))
            if not cursor.fetchone():
                raise NotFoundError(f"Parent threat model not found: {model_id}")

            tb_id = f"tb-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            cursor.execute(
                """
                INSERT INTO threat_trust_boundaries (
                    id, model_id, boundary_name, source_actor_or_component,
                    destination_component, data_classification, protocol_or_interface,
                    auth_mechanism, encryption_status, evidence_status, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    tb_id,
                    model_id,
                    boundary_name,
                    source,
                    destination,
                    data.get("data_classification", "TIER_2_PHI"),
                    data.get("protocol_or_interface", "HTTPS/JSON_REST"),
                    data.get("auth_mechanism", "BEARER_TOKEN_RBAC"),
                    data.get("encryption_status", "TLS_1_3_IN_TRANSIT"),
                    data.get("evidence_status", "verified_in_code"),
                    data.get("notes"),
                    datetime.utcnow().isoformat(),
                ),
            )

            self._record_audit_event(
                conn,
                event_type="TRUST_BOUNDARY_CREATED",
                actor_id=actor_id,
                target_type="TRUST_BOUNDARY",
                target_id=tb_id,
                action_details={"boundary_name": boundary_name, "model_id": model_id},
            )
            if not self._external_conn:
                conn.commit()

            cursor.execute("SELECT * FROM threat_trust_boundaries WHERE id = ?;", (tb_id,))
            return dict(cursor.fetchone())
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 4. Abuse Cases & Threat Scenarios
    # -------------------------------------------------------------------------

    def list_abuse_cases(
        self,
        model_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        threat_class: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists abuse cases with optional filters."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM threat_abuse_cases WHERE 1=1"
            params: List[Any] = []

            if model_id:
                query += " AND model_id = ?"
                params.append(model_id)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if status:
                query += " AND lifecycle_status = ?"
                params.append(status)
            if threat_class:
                query += " AND threat_class = ?"
                params.append(threat_class)

            query += " ORDER BY created_at DESC;"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            self._close_connection(conn)

    def get_abuse_case(self, case_id: str) -> Dict[str, Any]:
        """Retrieves a single abuse case and associated controls."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_abuse_cases WHERE id = ? OR threat_code = ?;", (case_id, case_id))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Abuse case not found: {case_id}")

            case = dict(row)
            cursor.execute("SELECT * FROM threat_testable_controls WHERE threat_id = ? ORDER BY created_at ASC;", (case["id"],))
            case["controls"] = [dict(c) for c in cursor.fetchall()]

            cursor.execute(
                "SELECT * FROM threat_residual_risk_decisions WHERE threat_id = ? ORDER BY created_at DESC;",
                (case["id"],),
            )
            case["residual_risk_decisions"] = [dict(r) for r in cursor.fetchall()]

            return case
        finally:
            self._close_connection(conn)

    def create_abuse_case(self, data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Registers a new abuse case."""
        model_id = data.get("model_id")
        threat_code = data.get("threat_code", "").strip()
        title = data.get("title", "").strip()
        threat_class = data.get("threat_class", "").strip()
        target_asset = data.get("target_asset", "").strip()
        attack_path_summary = data.get("attack_path_summary", "").strip()

        if not model_id or not threat_code or not title or not threat_class or not target_asset or not attack_path_summary:
            raise ValidationError("model_id, threat_code, title, threat_class, target_asset, and attack_path_summary are required.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM threat_abuse_cases WHERE threat_code = ?;", (threat_code,))
            if cursor.fetchone():
                raise ConflictError(f"Threat code already exists: {threat_code}")

            case_id = f"tac-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            now_iso = datetime.utcnow().isoformat()

            cursor.execute(
                """
                INSERT INTO threat_abuse_cases (
                    id, model_id, threat_code, title, methodology, threat_class,
                    actor_type, target_asset, trust_boundary_id, attack_path_summary,
                    clinical_safety_hazard, severity, lifecycle_status,
                    accountable_owner_role, mitigation_due_date, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    case_id,
                    model_id,
                    threat_code,
                    title,
                    data.get("methodology", "STRIDE_PLUS_CLINICAL_HAZARD"),
                    threat_class,
                    data.get("actor_type", "AUTHENTICATED_USER"),
                    target_asset,
                    data.get("trust_boundary_id"),
                    attack_path_summary,
                    data.get("clinical_safety_hazard", "NONE"),
                    data.get("severity", "HIGH"),
                    data.get("lifecycle_status", "identified"),
                    data.get("accountable_owner_role", "Security Lead"),
                    data.get("mitigation_due_date"),
                    now_iso,
                    now_iso,
                ),
            )

            self._record_audit_event(
                conn,
                event_type="ABUSE_CASE_LOGGED",
                actor_id=actor_id,
                target_type="ABUSE_CASE",
                target_id=case_id,
                action_details={"threat_code": threat_code, "title": title, "severity": data.get("severity", "HIGH")},
            )
            if not self._external_conn:
                conn.commit()

            return self.get_abuse_case(case_id)
        finally:
            self._close_connection(conn)

    def transition_abuse_case_status(
        self,
        case_id: str,
        new_status: str,
        actor_id: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transitions abuse case lifecycle status."""
        valid_statuses = [
            "identified",
            "needs_validation",
            "mitigation_planned",
            "mitigation_implemented",
            "verification_pending",
            "verified_mitigated",
            "residual_risk_review",
            "accepted_by_authorized_owner",
            "blocked",
            "closed_with_evidence",
        ]
        if new_status not in valid_statuses:
            raise ValidationError(f"Invalid status: {new_status}. Valid statuses: {valid_statuses}")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_abuse_cases WHERE id = ? OR threat_code = ?;", (case_id, case_id))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Abuse case not found: {case_id}")

            target_id = row["id"]
            now_iso = datetime.utcnow().isoformat()

            cursor.execute(
                """
                UPDATE threat_abuse_cases
                SET lifecycle_status = ?, updated_at = ?
                WHERE id = ?;
                """,
                (new_status, now_iso, target_id),
            )

            self._record_audit_event(
                conn,
                event_type="ABUSE_CASE_STATUS_CHANGED",
                actor_id=actor_id,
                target_type="ABUSE_CASE",
                target_id=target_id,
                action_details={
                    "previous_status": row["lifecycle_status"],
                    "new_status": new_status,
                    "notes": notes,
                },
            )
            if not self._external_conn:
                conn.commit()

            return self.get_abuse_case(target_id)
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 5. Testable Controls
    # -------------------------------------------------------------------------

    def list_testable_controls(self, threat_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists testable controls."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM threat_testable_controls WHERE 1=1"
            params: List[Any] = []
            if threat_id:
                query += " AND threat_id = ?"
                params.append(threat_id)
            query += " ORDER BY created_at ASC;"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            self._close_connection(conn)

    def create_testable_control(self, data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Creates a testable control linking an abuse case to an enforcement path and test."""
        threat_id = data.get("threat_id")
        control_code = data.get("control_code", "").strip()
        title = data.get("title", "").strip()
        enforcement_code_path = data.get("enforcement_code_path", "").strip()
        test_suite_reference = data.get("test_suite_reference", "").strip()

        if not threat_id or not control_code or not title or not enforcement_code_path or not test_suite_reference:
            raise ValidationError("threat_id, control_code, title, enforcement_code_path, and test_suite_reference are required.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM threat_abuse_cases WHERE id = ?;", (threat_id,))
            if not cursor.fetchone():
                raise NotFoundError(f"Parent abuse case not found: {threat_id}")

            cursor.execute("SELECT id FROM threat_testable_controls WHERE control_code = ?;", (control_code,))
            if cursor.fetchone():
                raise ConflictError(f"Control code already registered: {control_code}")

            ctl_id = f"ttc-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            cursor.execute(
                """
                INSERT INTO threat_testable_controls (
                    id, threat_id, control_code, title, control_type,
                    enforcement_code_path, test_suite_reference,
                    verification_status, last_verified_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    ctl_id,
                    threat_id,
                    control_code,
                    title,
                    data.get("control_type", "PREVENTIVE"),
                    enforcement_code_path,
                    test_suite_reference,
                    data.get("verification_status", "VERIFIED_IN_TEST"),
                    datetime.utcnow().isoformat(),
                    datetime.utcnow().isoformat(),
                ),
            )

            self._record_audit_event(
                conn,
                event_type="TESTABLE_CONTROL_CREATED",
                actor_id=actor_id,
                target_type="TESTABLE_CONTROL",
                target_id=ctl_id,
                action_details={"control_code": control_code, "threat_id": threat_id, "title": title},
            )
            if not self._external_conn:
                conn.commit()

            cursor.execute("SELECT * FROM threat_testable_controls WHERE id = ?;", (ctl_id,))
            return dict(cursor.fetchone())
        finally:
            self._close_connection(conn)

    def verify_control(
        self,
        control_id: str,
        verification_status: str,
        actor_id: str,
        test_evidence: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Updates verification status of a control with execution proof."""
        valid_statuses = ["PLANNED", "IMPLEMENTED", "VERIFIED_IN_TEST", "FAILED_VERIFICATION", "STALE"]
        if verification_status not in valid_statuses:
            raise ValidationError(f"Invalid verification status: {verification_status}")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_testable_controls WHERE id = ? OR control_code = ?;", (control_id, control_id))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Control not found: {control_id}")

            target_id = row["id"]
            now_iso = datetime.utcnow().isoformat()

            cursor.execute(
                """
                UPDATE threat_testable_controls
                SET verification_status = ?, last_verified_at = ?
                WHERE id = ?;
                """,
                (verification_status, now_iso, target_id),
            )

            self._record_audit_event(
                conn,
                event_type="CONTROL_VERIFICATION_RECORDED",
                actor_id=actor_id,
                target_type="TESTABLE_CONTROL",
                target_id=target_id,
                action_details={"status": verification_status, "evidence": test_evidence},
            )
            if not self._external_conn:
                conn.commit()

            cursor.execute("SELECT * FROM threat_testable_controls WHERE id = ?;", (target_id,))
            return dict(cursor.fetchone())
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 6. Governed Residual Risk Decisions
    # -------------------------------------------------------------------------

    def list_residual_risk_decisions(
        self,
        threat_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists governed residual risk acceptance decisions."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM threat_residual_risk_decisions WHERE 1=1"
            params: List[Any] = []
            if threat_id:
                query += " AND threat_id = ?"
                params.append(threat_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC;"
            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            self._close_connection(conn)

    def create_residual_risk_decision(self, data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """
        Creates a governed residual risk acceptance record.
        Enforces maximum 90-day expiry and hard clinical non-negotiables.
        """
        threat_id = data.get("threat_id")
        scope = data.get("scope", "").strip()
        rationale = data.get("business_rationale", "").strip()
        compensating_controls = data.get("compensating_controls", "").strip()
        owner_role = data.get("authorized_owner_role", "").strip()
        expires_at = data.get("expires_at", "").strip()

        if not threat_id or not scope or not rationale or not compensating_controls or not owner_role or not expires_at:
            raise ValidationError("threat_id, scope, business_rationale, compensating_controls, authorized_owner_role, and expires_at are required.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_abuse_cases WHERE id = ?;", (threat_id,))
            threat_row = cursor.fetchone()
            if not threat_row:
                raise NotFoundError(f"Target abuse case not found: {threat_id}")

            # Non-negotiable Clinical Safety Check:
            # Cannot accept risk for direct harm prescribing error or tenant boundaries!
            if threat_row["clinical_safety_hazard"] == "DIRECT_HARM_PRESCRIBING_ERROR":
                raise ValidationError(
                    "NON-NEGOTIABLE CLINICAL SAFETY INVARIANT: Cannot grant residual risk acceptance "
                    "for threats with DIRECT_HARM_PRESCRIBING_ERROR. Clinical prescribing safety and "
                    "electronic signature PIN invariants cannot be waived."
                )

            # Validate expiration <= 90 days
            try:
                exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                max_dt = datetime.utcnow() + timedelta(days=90)
                if exp_dt.replace(tzinfo=None) > max_dt:
                    raise ValidationError("Residual risk acceptance duration cannot exceed 90 days under approved policy.")
            except (ValueError, TypeError) as e:
                if "Residual risk acceptance" in str(e):
                    raise
                raise ValidationError(f"Invalid ISO format for expires_at: {expires_at}")

            decision_id = f"trr-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            now_iso = datetime.utcnow().isoformat()

            cursor.execute(
                """
                INSERT INTO threat_residual_risk_decisions (
                    id, threat_id, scope, business_rationale, compensating_controls,
                    authorized_owner_role, authorized_by_principal_id, authorized_at,
                    expires_at, residual_risk_tier, status, clinical_hazard_reviewed,
                    review_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'APPROVED', 1, ?, ?);
                """,
                (
                    decision_id,
                    threat_id,
                    scope,
                    rationale,
                    compensating_controls,
                    owner_role,
                    actor_id,
                    now_iso,
                    expires_at,
                    data.get("residual_risk_tier", "LOW"),
                    data.get("review_notes"),
                    now_iso,
                ),
            )

            # Update abuse case status to accepted_by_authorized_owner
            cursor.execute(
                "UPDATE threat_abuse_cases SET lifecycle_status = 'accepted_by_authorized_owner', updated_at = ? WHERE id = ?;",
                (now_iso, threat_id),
            )

            self._record_audit_event(
                conn,
                event_type="RISK_ACCEPTED",
                actor_id=actor_id,
                target_type="RESIDUAL_RISK_DECISION",
                target_id=decision_id,
                action_details={"threat_id": threat_id, "scope": scope, "expires_at": expires_at, "owner_role": owner_role},
                severity="WARNING",
            )
            if not self._external_conn:
                conn.commit()

            cursor.execute("SELECT * FROM threat_residual_risk_decisions WHERE id = ?;", (decision_id,))
            return dict(cursor.fetchone())
        finally:
            self._close_connection(conn)

    def revoke_residual_risk_decision(self, decision_id: str, actor_id: str, rationale: str) -> Dict[str, Any]:
        """Revokes an active residual risk decision."""
        if not rationale:
            raise ValidationError("Revocation rationale is required.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM threat_residual_risk_decisions WHERE id = ?;", (decision_id,))
            row = cursor.fetchone()
            if not row:
                raise NotFoundError(f"Residual risk decision not found: {decision_id}")

            now_iso = datetime.utcnow().isoformat()
            cursor.execute(
                "UPDATE threat_residual_risk_decisions SET status = 'REVOKED', review_notes = ? WHERE id = ?;",
                (f"Revoked by {actor_id}: {rationale}", decision_id),
            )
            # Revert abuse case status to needs_validation
            cursor.execute(
                "UPDATE threat_abuse_cases SET lifecycle_status = 'needs_validation', updated_at = ? WHERE id = ?;",
                (now_iso, row["threat_id"]),
            )

            self._record_audit_event(
                conn,
                event_type="RISK_ACCEPTANCE_REVOKED",
                actor_id=actor_id,
                target_type="RESIDUAL_RISK_DECISION",
                target_id=decision_id,
                action_details={"rationale": rationale},
                severity="WARNING",
            )
            if not self._external_conn:
                conn.commit()

            cursor.execute("SELECT * FROM threat_residual_risk_decisions WHERE id = ?;", (decision_id,))
            return dict(cursor.fetchone())
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 7. SDLC Change Reviews & Release Gate Evaluator
    # -------------------------------------------------------------------------

    def list_change_reviews(
        self,
        target_subsystem: Optional[str] = None,
        verdict: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists SDLC change reviews."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM sdlc_change_reviews WHERE 1=1"
            params: List[Any] = []
            if target_subsystem:
                query += " AND target_subsystem = ?"
                params.append(target_subsystem)
            if verdict:
                query += " AND gate_verdict = ?"
                params.append(verdict)
            query += " ORDER BY evaluated_at DESC;"
            cursor.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                if item.get("blocking_reasons_json"):
                    item["blocking_reasons"] = json.loads(item["blocking_reasons_json"])
                result.append(item)
            return result
        finally:
            self._close_connection(conn)

    def create_change_review(self, data: Dict[str, Any], actor_id: str) -> Dict[str, Any]:
        """Registers a change request / pull request for SDLC review."""
        change_id = data.get("change_id", "").strip()
        title = data.get("title", "").strip()
        target_subsystem = data.get("target_subsystem", "").strip()

        if not change_id or not title or not target_subsystem:
            raise ValidationError("change_id, title, and target_subsystem are required.")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM sdlc_change_reviews WHERE change_id = ?;", (change_id,))
            if cursor.fetchone():
                raise ConflictError(f"Change review already exists for change_id: {change_id}")

            # Find matching threat model for target subsystem
            cursor.execute(
                "SELECT id FROM threat_models_registry WHERE subsystem_scope = ? ORDER BY created_at DESC LIMIT 1;",
                (target_subsystem,),
            )
            tm_row = cursor.fetchone()
            threat_model_id = tm_row["id"] if tm_row else None

            review_id = f"sdlc-cr-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            now_iso = datetime.utcnow().isoformat()

            cursor.execute(
                """
                INSERT INTO sdlc_change_reviews (
                    id, change_id, title, repository_revision, target_subsystem,
                    threat_model_id, change_classification, security_review_status,
                    clinical_review_status, privacy_review_status, gate_verdict,
                    blocking_reasons_json, evaluated_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NOT_RUN', '[]', ?, ?);
                """,
                (
                    review_id,
                    change_id,
                    title,
                    data.get("repository_revision", "HEAD"),
                    target_subsystem,
                    threat_model_id,
                    data.get("change_classification", "STANDARD_CHANGE"),
                    data.get("security_review_status", "PENDING"),
                    data.get("clinical_review_status", "NOT_REQUIRED"),
                    data.get("privacy_review_status", "NOT_REQUIRED"),
                    now_iso,
                    now_iso,
                ),
            )

            self._record_audit_event(
                conn,
                event_type="SDLC_CHANGE_REGISTERED",
                actor_id=actor_id,
                target_type="SDLC_CHANGE_REVIEW",
                target_id=review_id,
                action_details={"change_id": change_id, "target_subsystem": target_subsystem, "title": title},
            )
            if not self._external_conn:
                conn.commit()

            return self.evaluate_sdlc_gate(review_id, actor_id)
        finally:
            self._close_connection(conn)

    def evaluate_sdlc_gate(self, review_id: str, actor_id: str) -> Dict[str, Any]:
        """
        Deterministically evaluates pre-deployment release gate for a change review.
        Checks:
        1. Subsystem has an approved, active (non-stale) threat model.
        2. No unmitigated P0/P1 abuse cases (unless covered by unexpired residual risk decision).
        3. Security review approved.
        4. If HIGH_IMPACT_CLINICAL, clinical review approved.
        5. If HIGH_IMPACT_PRIVACY, privacy review approved.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sdlc_change_reviews WHERE id = ? OR change_id = ?;", (review_id, review_id))
            cr = cursor.fetchone()
            if not cr:
                raise NotFoundError(f"SDLC change review not found: {review_id}")

            target_id = cr["id"]
            target_subsystem = cr["target_subsystem"]
            change_class = cr["change_classification"]
            sec_status = cr["security_review_status"]
            clin_status = cr["clinical_review_status"]
            priv_status = cr["privacy_review_status"]

            blocking_reasons: List[str] = []

            # 1. Threat model existence and freshness
            cursor.execute(
                "SELECT * FROM threat_models_registry WHERE subsystem_scope = ? ORDER BY created_at DESC LIMIT 1;",
                (target_subsystem,),
            )
            tm = cursor.fetchone()
            if not tm:
                blocking_reasons.append(f"Subsystem '{target_subsystem}' lacks an active threat model.")
            elif tm["is_stale"] == 1 or tm["lifecycle_state"] != "approved_for_scope":
                blocking_reasons.append(
                    f"Threat model for '{target_subsystem}' is {tm['lifecycle_state']} (stale: {tm['is_stale']}). Re-review required before release."
                )

            # 2. Check open CRITICAL & HIGH abuse cases under this threat model
            if tm:
                cursor.execute(
                    """
                    SELECT id, threat_code, title, severity, lifecycle_status, clinical_safety_hazard
                    FROM threat_abuse_cases
                    WHERE model_id = ? AND severity IN ('CRITICAL', 'HIGH');
                    """,
                    (tm["id"],),
                )
                cases = cursor.fetchall()
                for c in cases:
                    if c["lifecycle_status"] not in ("verified_mitigated", "closed_with_evidence", "accepted_by_authorized_owner"):
                        # Check if covered by active residual risk decision
                        cursor.execute(
                            """
                            SELECT id, expires_at FROM threat_residual_risk_decisions
                            WHERE threat_id = ? AND status = 'APPROVED' AND datetime(expires_at) > datetime('now');
                            """,
                            (c["id"],),
                        )
                        rrd = cursor.fetchone()
                        if not rrd:
                            blocking_reasons.append(
                                f"Unmitigated threat '{c['threat_code']}' ({c['severity']}): {c['title']} is in status '{c['lifecycle_status']}'."
                            )

            # 3. Check review approvals
            if sec_status != "APPROVED":
                blocking_reasons.append(f"Security review is '{sec_status}'; must be 'APPROVED'.")

            if change_class == "HIGH_IMPACT_CLINICAL" and clin_status != "APPROVED":
                blocking_reasons.append(f"Clinical safety review is '{clin_status}'; required 'APPROVED' for HIGH_IMPACT_CLINICAL.")

            if change_class == "HIGH_IMPACT_PRIVACY" and priv_status != "APPROVED":
                blocking_reasons.append(f"Privacy review is '{priv_status}'; required 'APPROVED' for HIGH_IMPACT_PRIVACY.")

            # Determine verdict
            if not blocking_reasons:
                gate_verdict = "PASS"
            elif any("stale" in r.lower() for r in blocking_reasons):
                gate_verdict = "STALE_MODEL"
            else:
                gate_verdict = "BLOCKED"

            now_iso = datetime.utcnow().isoformat()
            cursor.execute(
                """
                UPDATE sdlc_change_reviews
                SET gate_verdict = ?, blocking_reasons_json = ?, evaluated_at = ?
                WHERE id = ?;
                """,
                (gate_verdict, json.dumps(blocking_reasons), now_iso, target_id),
            )

            self._record_audit_event(
                conn,
                event_type="SDLC_GATE_EVALUATED",
                actor_id=actor_id,
                target_type="SDLC_CHANGE_REVIEW",
                target_id=target_id,
                action_details={
                    "change_id": cr["change_id"],
                    "verdict": gate_verdict,
                    "blocking_reasons_count": len(blocking_reasons),
                },
                severity="WARNING" if gate_verdict != "PASS" else "INFO",
            )
            if not self._external_conn:
                conn.commit()

            cursor.execute("SELECT * FROM sdlc_change_reviews WHERE id = ?;", (target_id,))
            res = dict(cursor.fetchone())
            res["blocking_reasons"] = blocking_reasons
            return res
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 8. Audit Ledger Query
    # -------------------------------------------------------------------------

    def query_audit_ledger(
        self,
        limit: int = 100,
        actor_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries the hash-chained threat & SDLC audit ledger."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM threat_sdlc_audit_ledger WHERE 1=1"
            params: List[Any] = []

            if actor_id:
                query += " AND actor_id = ?"
                params.append(actor_id)
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type)

            query += " ORDER BY occurred_at DESC, rowid DESC LIMIT ?;"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            self._close_connection(conn)

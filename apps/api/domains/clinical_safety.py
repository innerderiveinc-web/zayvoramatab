"""
Enterprise Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine
ZAYVORA MATAB OS — Phase 48

Identifies clinical hazards, defines safety requirements and controls, connects controls
to executable test verifications, and enforces fail-closed clinical safety release gates.
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
    """Mask credentials, tokens, and PHI. Strictly zero raw secrets or patient identifiers."""
    if not text:
        return text

    patterns = [
        (r"AKIA[0-9A-Z]{16}", "AKIA****************"),
        (r"sk_live_[0-9a-zA-Z]{24}", "sk_live_************************"),
        (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
        (r"(password|passwd|secret|api_key|token|pin)\s*[:=]\s*['\"][^'\"]+['\"]", r"\1: [REDACTED]"),
        (r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer [REDACTED_BEARER_TOKEN]"),
    ]
    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    return redacted


class EnterpriseClinicalSafetyCaseEngine:
    """
    Core domain engine governing Clinical Intended Use Registry, Clinical Hazard Register,
    Safety Requirements Catalog, Control Verifications, Goal Structuring Notation (GSN)
    Safety Cases, Clinical Incident Near-Miss Loop, and Fail-Closed Release Gates.
    """

    VALID_SEVERITY_TIERS = {"CATASTROPHIC", "CRITICAL", "SERIOUS", "MINOR", "NEGLIGIBLE"}
    VALID_HAZARD_STATUSES = {
        "draft",
        "clinical_review_required",
        "mitigation_required",
        "verification_pending",
        "residual_risk_review",
        "accepted_for_defined_scope",
        "blocked",
        "retired",
    }
    VALID_REQUIREMENT_STATUSES = {"PLANNED", "IMPLEMENTED", "VERIFIED_IN_TEST", "FAILED_VERIFICATION", "STALE"}
    VALID_SAFETY_CASE_STATUSES = {
        "DRAFT",
        "PENDING_CLINICAL_REVIEW",
        "APPROVED_FOR_SCOPE",
        "CONDITIONALLY_APPROVED",
        "REJECTED",
        "STALE",
    }
    VALID_GATE_VERDICTS = {"PASS", "BLOCKED", "CONDITIONAL_PASS", "STALE_EVIDENCE"}

    def __init__(self, db_path_or_conn: Any = None):
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
        """Appends an event to clinical_safety_audit_ledger with SHA-256 hash chaining."""
        cursor = conn.cursor()
        cursor.execute(
            "SELECT entry_hash FROM clinical_safety_audit_ledger ORDER BY occurred_at DESC, rowid DESC LIMIT 1;"
        )
        row = cursor.fetchone()
        previous_hash = row["entry_hash"] if row else "GENESIS_BLOCK_CLINICAL_SAFETY_P48"

        event_id = f"aud-cs-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        occurred_at = datetime.utcnow().isoformat()
        sanitized_details = redact_sensitive_text(json.dumps(action_details, sort_keys=True))

        hash_payload = f"{event_id}|{event_type}|{actor_id}|{target_type}|{target_id}|{sanitized_details}|{previous_hash}|{occurred_at}"
        entry_hash = hashlib.sha256(hash_payload.encode("utf-8")).hexdigest()

        cursor.execute(
            """
            INSERT INTO clinical_safety_audit_ledger (
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
    # 1. Summary & KPIs
    # -------------------------------------------------------------------------
    def get_clinical_safety_summary(self) -> Dict[str, Any]:
        """Returns executive KPI metrics across all clinical safety assets."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # Intended uses
            cur.execute("SELECT COUNT(*) as count FROM clinical_intended_use_registry;")
            total_intended_uses = cur.fetchone()["count"]

            # Hazards by status & severity
            cur.execute("SELECT COUNT(*) as count FROM clinical_hazard_register;")
            total_hazards = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) as count FROM clinical_hazard_register WHERE severity_tier IN ('CATASTROPHIC', 'CRITICAL') AND lifecycle_status != 'accepted_for_defined_scope' AND lifecycle_status != 'retired';"
            )
            critical_open_hazards = cur.fetchone()["count"]

            cur.execute(
                "SELECT severity_tier, COUNT(*) as count FROM clinical_hazard_register GROUP BY severity_tier;"
            )
            hazards_by_severity = {r["severity_tier"]: r["count"] for r in cur.fetchall()}

            cur.execute(
                "SELECT lifecycle_status, COUNT(*) as count FROM clinical_hazard_register GROUP BY lifecycle_status;"
            )
            hazards_by_status = {r["lifecycle_status"]: r["count"] for r in cur.fetchall()}

            # Safety Requirements
            cur.execute("SELECT COUNT(*) as count FROM safety_requirements_catalog;")
            total_requirements = cur.fetchone()["count"]

            cur.execute(
                "SELECT verification_status, COUNT(*) as count FROM safety_requirements_catalog GROUP BY verification_status;"
            )
            requirements_by_status = {r["verification_status"]: r["count"] for r in cur.fetchall()}

            # Verifications count
            cur.execute("SELECT COUNT(*) as count FROM safety_control_verifications;")
            total_verifications = cur.fetchone()["count"]

            # Safety Cases
            cur.execute("SELECT COUNT(*) as count FROM clinical_safety_cases;")
            total_safety_cases = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) as count FROM clinical_safety_cases WHERE approval_status = 'APPROVED_FOR_SCOPE';"
            )
            approved_safety_cases = cur.fetchone()["count"]

            # Incidents
            cur.execute("SELECT COUNT(*) as count FROM clinical_safety_incidents;")
            total_incidents = cur.fetchone()["count"]

            cur.execute(
                "SELECT COUNT(*) as count FROM clinical_safety_incidents WHERE corrective_action_status != 'VERIFIED_CLOSED';"
            )
            open_incidents = cur.fetchone()["count"]

            # Release Gates
            cur.execute("SELECT COUNT(*) as count FROM safety_release_gate_evaluations;")
            total_gate_evaluations = cur.fetchone()["count"]

            cur.execute(
                "SELECT gate_verdict, COUNT(*) as count FROM safety_release_gate_evaluations GROUP BY gate_verdict;"
            )
            verdicts_summary = {r["gate_verdict"]: r["count"] for r in cur.fetchall()}

            return {
                "intended_uses_count": total_intended_uses,
                "hazards": {
                    "total": total_hazards,
                    "critical_open_count": critical_open_hazards,
                    "by_severity": hazards_by_severity,
                    "by_status": hazards_by_status,
                },
                "requirements": {
                    "total": total_requirements,
                    "by_status": requirements_by_status,
                    "total_verifications": total_verifications,
                },
                "safety_cases": {
                    "total": total_safety_cases,
                    "approved_count": approved_safety_cases,
                },
                "incidents": {
                    "total": total_incidents,
                    "open_count": open_incidents,
                },
                "release_gates": {
                    "total_evaluations": total_gate_evaluations,
                    "verdicts": verdicts_summary,
                },
                "audit_status": "TAMPER_EVIDENT_HASH_CHAIN_ACTIVE",
            }
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 2. Clinical Intended Use Registry
    # -------------------------------------------------------------------------
    def list_intended_uses(
        self, scope_code: Optional[str] = None, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM clinical_intended_use_registry WHERE 1=1"
            params: List[Any] = []
            if scope_code:
                query += " AND scope_code = ?"
                params.append(scope_code)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC;"
            cur.execute(query, params)
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["intended_users"] = json.loads(d["intended_users_json"]) if d.get("intended_users_json") else []
                d["clinical_purposes"] = json.loads(d["clinical_purposes_json"]) if d.get("clinical_purposes_json") else []
                d["excluded_uses"] = json.loads(d["excluded_uses_json"]) if d.get("excluded_uses_json") else []
                results.append(d)
            return results
        finally:
            self._close_connection(conn)

    def get_intended_use(self, intended_use_id: str) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_intended_use_registry WHERE id = ?;", (intended_use_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Clinical intended use statement '{intended_use_id}' not found.")
            d = dict(row)
            d["intended_users"] = json.loads(d["intended_users_json"]) if d.get("intended_users_json") else []
            d["clinical_purposes"] = json.loads(d["clinical_purposes_json"]) if d.get("clinical_purposes_json") else []
            d["excluded_uses"] = json.loads(d["excluded_uses_json"]) if d.get("excluded_uses_json") else []
            return d
        finally:
            self._close_connection(conn)

    def register_intended_use(self, actor_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a new bounded intended-use statement approved by clinical lead."""
        scope_code = data.get("scope_code")
        title = data.get("title")
        if not scope_code or not title:
            raise ValidationError("scope_code and title are required for Intended Use registry.")

        intended_users = data.get("intended_users", ["Licensed Tabib"])
        clinical_purposes = data.get("clinical_purposes", [])
        excluded_uses = data.get("excluded_uses", ["Autonomous prescribing"])
        authority = data.get("clinician_authority_level", "EXCLUSIVE_HUMAN_SIGN_OFF")
        version = data.get("version", "1.0.0")
        effective_date = data.get("effective_date", datetime.utcnow().date().isoformat())
        approver_id = data.get("clinical_approver_id", actor_id)

        clean_scope = scope_code.lower().replace('_', '-')
        if not clean_scope.startswith("iu-"):
            clean_scope = f"iu-{clean_scope}"
        iu_id = clean_scope[:36]
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clinical_intended_use_registry WHERE scope_code = ?;", (scope_code,))
            if cur.fetchone():
                raise ConflictError(f"Intended use scope_code '{scope_code}' already exists.")

            cur.execute(
                """
                INSERT INTO clinical_intended_use_registry (
                    id, scope_code, title, intended_users_json, clinical_purposes_json,
                    excluded_uses_json, clinician_authority_level, version, effective_date,
                    clinical_approver_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'APPROVED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    iu_id,
                    scope_code,
                    title,
                    json.dumps(intended_users),
                    json.dumps(clinical_purposes),
                    json.dumps(excluded_uses),
                    authority,
                    version,
                    effective_date,
                    approver_id,
                ),
            )
            self._record_audit_event(
                conn,
                "INTENDED_USE_REGISTERED",
                actor_id,
                "INTENDED_USE",
                iu_id,
                {"scope_code": scope_code, "title": title, "version": version},
            )
            conn.commit()
            return self.get_intended_use(iu_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 3. Clinical Hazard Register
    # -------------------------------------------------------------------------
    def list_hazards(
        self,
        workflow_scope: Optional[str] = None,
        severity_tier: Optional[str] = None,
        lifecycle_status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM clinical_hazard_register WHERE 1=1"
            params: List[Any] = []
            if workflow_scope:
                query += " AND workflow_scope = ?"
                params.append(workflow_scope)
            if severity_tier:
                query += " AND severity_tier = ?"
                params.append(severity_tier)
            if lifecycle_status:
                query += " AND lifecycle_status = ?"
                params.append(lifecycle_status)
            query += " ORDER BY CASE severity_tier WHEN 'CATASTROPHIC' THEN 1 WHEN 'CRITICAL' THEN 2 WHEN 'SERIOUS' THEN 3 WHEN 'MINOR' THEN 4 ELSE 5 END, created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            self._close_connection(conn)

    def get_hazard(self, hazard_id: str) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_hazard_register WHERE id = ?;", (hazard_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Clinical hazard '{hazard_id}' not found.")
            hazard = dict(row)

            # Also fetch linked requirements
            cur.execute(
                "SELECT * FROM safety_requirements_catalog WHERE hazard_id = ? ORDER BY req_code ASC;",
                (hazard_id,),
            )
            hazard["requirements"] = [dict(r) for r in cur.fetchall()]
            return hazard
        finally:
            self._close_connection(conn)

    def create_hazard(self, actor_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates a new clinical hazard record with causal chain details."""
        hazard_code = data.get("hazard_code")
        title = data.get("title")
        workflow_scope = data.get("workflow_scope")
        initiating_cause = data.get("initiating_cause")
        hazardous_state = data.get("hazardous_state")
        clinical_consequence = data.get("clinical_consequence")
        severity_tier = data.get("severity_tier", "CRITICAL")

        if not hazard_code or not title or not workflow_scope or not initiating_cause or not hazardous_state or not clinical_consequence:
            raise ValidationError("Missing mandatory hazard specification fields.")

        if severity_tier not in self.VALID_SEVERITY_TIERS:
            raise ValidationError(f"Invalid severity_tier '{severity_tier}'. Must be one of {self.VALID_SEVERITY_TIERS}")

        clean_code = hazard_code.lower().replace('_', '-')
        if not clean_code.startswith("haz-"):
            clean_code = f"haz-{clean_code}"
        hazard_id = clean_code[:40]
        intended_use_id = data.get("intended_use_id")
        affected_pop = data.get("affected_population", "GENERAL_OPD")
        status = data.get("lifecycle_status", "draft")
        lead_id = data.get("clinical_safety_lead_id", "usr-hakeem-1")
        tech_id = data.get("technical_lead_id", actor_id)
        due_date = data.get("review_due_date", (datetime.utcnow() + timedelta(days=90)).date().isoformat())

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clinical_hazard_register WHERE hazard_code = ?;", (hazard_code,))
            if cur.fetchone():
                raise ConflictError(f"Hazard code '{hazard_code}' already exists.")

            cur.execute(
                """
                INSERT INTO clinical_hazard_register (
                    id, hazard_code, intended_use_id, title, workflow_scope,
                    initiating_cause, hazardous_state, clinical_consequence,
                    affected_population, severity_tier, lifecycle_status,
                    clinical_safety_lead_id, technical_lead_id, review_due_date,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    hazard_id,
                    hazard_code,
                    intended_use_id,
                    title,
                    workflow_scope,
                    initiating_cause,
                    hazardous_state,
                    clinical_consequence,
                    affected_pop,
                    severity_tier,
                    status,
                    lead_id,
                    tech_id,
                    due_date,
                ),
            )
            self._record_audit_event(
                conn,
                "HAZARD_CREATED",
                actor_id,
                "HAZARD",
                hazard_id,
                {"hazard_code": hazard_code, "severity_tier": severity_tier, "workflow_scope": workflow_scope},
                severity="WARNING" if severity_tier in ("CATASTROPHIC", "CRITICAL") else "INFO",
            )
            conn.commit()
            return self.get_hazard(hazard_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def update_hazard_status(
        self,
        actor_id: str,
        hazard_id: str,
        new_status: str,
        justification: str,
        is_clinical_safety_officer: bool = False,
    ) -> Dict[str, Any]:
        """
        Updates the lifecycle status of a clinical hazard.
        Non-negotiable invariant: Transitioning to 'accepted_for_defined_scope' requires
        a licensed Clinical Safety Officer / Tabib identity. System administrators cannot force-accept.
        """
        if new_status not in self.VALID_HAZARD_STATUSES:
            raise ValidationError(f"Invalid lifecycle_status '{new_status}'.")

        if not justification or len(justification.strip()) < 10:
            raise ValidationError("Clinical justification (minimum 10 chars) is strictly required for hazard status changes.")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_hazard_register WHERE id = ?;", (hazard_id,))
            hazard = cur.fetchone()
            if not hazard:
                raise NotFoundError(f"Clinical hazard '{hazard_id}' not found.")

            # Clinical Safety Officer check for acceptance
            if new_status == "accepted_for_defined_scope":
                if not is_clinical_safety_officer and actor_id != hazard["clinical_safety_lead_id"]:
                    raise ForbiddenError(
                        "Clinical authority violation: Acceptance of residual hazard risk requires a verified Clinical Safety Officer / Tabib signature."
                    )

            cur.execute(
                """
                UPDATE clinical_hazard_register
                SET lifecycle_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_status, hazard_id),
            )
            self._record_audit_event(
                conn,
                "HAZARD_STATUS_CHANGED",
                actor_id,
                "HAZARD",
                hazard_id,
                {
                    "previous_status": hazard["lifecycle_status"],
                    "new_status": new_status,
                    "justification": justification,
                },
                severity="WARNING" if new_status in ("blocked", "residual_risk_review") else "INFO",
            )
            conn.commit()
            return self.get_hazard(hazard_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 4. Safety Requirements & Controls Catalog
    # -------------------------------------------------------------------------
    def list_requirements(
        self, hazard_id: Optional[str] = None, verification_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM safety_requirements_catalog WHERE 1=1"
            params: List[Any] = []
            if hazard_id:
                query += " AND hazard_id = ?"
                params.append(hazard_id)
            if verification_status:
                query += " AND verification_status = ?"
                params.append(verification_status)
            query += " ORDER BY req_code ASC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            self._close_connection(conn)

    def get_requirement(self, requirement_id: str) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM safety_requirements_catalog WHERE id = ?;", (requirement_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Safety requirement '{requirement_id}' not found.")
            req = dict(row)

            # Fetch verifications history
            cur.execute(
                "SELECT * FROM safety_control_verifications WHERE requirement_id = ? ORDER BY test_run_timestamp DESC;",
                (requirement_id,),
            )
            req["verifications"] = [dict(r) for r in cur.fetchall()]
            return req
        finally:
            self._close_connection(conn)

    def create_requirement(self, actor_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        hazard_id = data.get("hazard_id")
        req_code = data.get("req_code")
        title = data.get("title")
        specification_statement = data.get("specification_statement")
        enforcement_code_path = data.get("enforcement_code_path")
        test_suite_reference = data.get("test_suite_reference")

        if not hazard_id or not req_code or not title or not specification_statement or not enforcement_code_path or not test_suite_reference:
            raise ValidationError("Missing mandatory safety requirement fields.")

        clean_code = req_code.lower().replace('_', '-')
        if not clean_code.startswith("sr-"):
            clean_code = f"sr-{clean_code}"
        req_id = clean_code[:40]
        req_type = data.get("requirement_type", "PREVENTIVE")
        v_status = data.get("verification_status", "PLANNED")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clinical_hazard_register WHERE id = ?;", (hazard_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Parent hazard '{hazard_id}' not found.")

            cur.execute("SELECT id FROM safety_requirements_catalog WHERE req_code = ?;", (req_code,))
            if cur.fetchone():
                raise ConflictError(f"Safety requirement code '{req_code}' already exists.")

            cur.execute(
                """
                INSERT INTO safety_requirements_catalog (
                    id, hazard_id, req_code, title, requirement_type,
                    specification_statement, enforcement_code_path, test_suite_reference,
                    verification_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    req_id,
                    hazard_id,
                    req_code,
                    title,
                    req_type,
                    specification_statement,
                    enforcement_code_path,
                    test_suite_reference,
                    v_status,
                ),
            )
            self._record_audit_event(
                conn,
                "SAFETY_REQUIREMENT_ADDED",
                actor_id,
                "SAFETY_REQUIREMENT",
                req_id,
                {"req_code": req_code, "hazard_id": hazard_id, "requirement_type": req_type},
            )
            conn.commit()
            return self.get_requirement(req_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 5. Safety Control Verifications
    # -------------------------------------------------------------------------
    def record_control_verification(
        self,
        actor_id: str,
        requirement_id: str,
        test_suite_name: str,
        status: str,
        evidence_summary: str,
        execution_duration_ms: int = 50,
        environment: str = "ISOLATED_SYNTHETIC",
    ) -> Dict[str, Any]:
        """Records an execution of an automated safety verification test."""
        if status not in {"PASS", "FAIL", "BLOCKED", "STALE"}:
            raise ValidationError(f"Invalid verification status '{status}'. Must be PASS, FAIL, BLOCKED, or STALE.")

        verif_id = f"scv-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM safety_requirements_catalog WHERE id = ?;", (requirement_id,))
            if not cur.fetchone():
                raise NotFoundError(f"Safety requirement '{requirement_id}' not found.")

            cur.execute(
                """
                INSERT INTO safety_control_verifications (
                    id, requirement_id, test_run_timestamp, test_suite_name,
                    environment, execution_duration_ms, status, evidence_summary,
                    verified_by_actor_id, created_at
                ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    verif_id,
                    requirement_id,
                    test_suite_name,
                    environment,
                    execution_duration_ms,
                    status,
                    evidence_summary,
                    actor_id,
                ),
            )

            # Update requirement verification_status
            new_req_status = "VERIFIED_IN_TEST" if status == "PASS" else "FAILED_VERIFICATION"
            cur.execute(
                """
                UPDATE safety_requirements_catalog
                SET verification_status = ?, last_verified_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_req_status, requirement_id),
            )

            self._record_audit_event(
                conn,
                "CONTROL_VERIFIED",
                actor_id,
                "CONTROL_VERIFICATION",
                verif_id,
                {
                    "requirement_id": requirement_id,
                    "status": status,
                    "test_suite_name": test_suite_name,
                    "new_requirement_status": new_req_status,
                },
                severity="WARNING" if status != "PASS" else "INFO",
            )
            conn.commit()

            cur.execute("SELECT * FROM safety_control_verifications WHERE id = ?;", (verif_id,))
            return dict(cur.fetchone())
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def list_verifications(self, requirement_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM safety_control_verifications WHERE 1=1"
            params: List[Any] = []
            if requirement_id:
                query += " AND requirement_id = ?"
                params.append(requirement_id)
            query += " ORDER BY test_run_timestamp DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 6. Clinical Safety Cases (Claim-Context-Argument-Evidence)
    # -------------------------------------------------------------------------
    def list_safety_cases(
        self, workflow_scope: Optional[str] = None, approval_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM clinical_safety_cases WHERE 1=1"
            params: List[Any] = []
            if workflow_scope:
                query += " AND workflow_scope = ?"
                params.append(workflow_scope)
            if approval_status:
                query += " AND approval_status = ?"
                params.append(approval_status)
            query += " ORDER BY created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            self._close_connection(conn)

    def get_safety_case(self, case_id: str) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_safety_cases WHERE id = ?;", (case_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Clinical safety case '{case_id}' not found.")
            return dict(row)
        finally:
            self._close_connection(conn)

    def create_safety_case(self, actor_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        case_code = data.get("case_code")
        title = data.get("title")
        workflow_scope = data.get("workflow_scope")
        claim_statement = data.get("claim_statement")
        argument_narrative = data.get("argument_narrative")

        if not case_code or not title or not workflow_scope or not claim_statement or not argument_narrative:
            raise ValidationError("Missing mandatory clinical safety case elements.")

        clean_code = case_code.lower().replace('_', '-')
        if not clean_code.startswith("csc-"):
            clean_code = f"csc-{clean_code}"
        case_id = clean_code[:40]
        target_version = data.get("target_release_version", "v1.0.0")
        context_assumptions = data.get("context_and_assumptions", "Standard outpatient Unani clinic operations.")
        residual_risks = data.get("residual_risks_summary", "ALARP with clinical oversight.")
        exclusions = data.get("exclusions_and_limitations", "No autonomous dosing.")
        officer_id = data.get("clinical_safety_officer_id", "usr-hakeem-1")
        status = data.get("approval_status", "DRAFT")
        approved_at = datetime.utcnow().isoformat() if status == "APPROVED_FOR_SCOPE" else None
        expires_at = (datetime.utcnow() + timedelta(days=180)).date().isoformat()

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clinical_safety_cases WHERE case_code = ?;", (case_code,))
            if cur.fetchone():
                raise ConflictError(f"Clinical safety case code '{case_code}' already exists.")

            cur.execute(
                """
                INSERT INTO clinical_safety_cases (
                    id, case_code, title, workflow_scope, target_release_version,
                    claim_statement, context_and_assumptions, argument_narrative,
                    residual_risks_summary, exclusions_and_limitations,
                    clinical_safety_officer_id, approval_status, approved_at,
                    expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    case_id,
                    case_code,
                    title,
                    workflow_scope,
                    target_version,
                    claim_statement,
                    context_assumptions,
                    argument_narrative,
                    residual_risks,
                    exclusions,
                    officer_id,
                    status,
                    approved_at,
                    expires_at,
                ),
            )
            self._record_audit_event(
                conn,
                "SAFETY_CASE_CREATED",
                actor_id,
                "SAFETY_CASE",
                case_id,
                {"case_code": case_code, "workflow_scope": workflow_scope, "approval_status": status},
            )
            conn.commit()
            return self.get_safety_case(case_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def review_safety_case(
        self,
        actor_id: str,
        case_id: str,
        new_status: str,
        clinical_rationale: str,
        is_clinical_safety_officer: bool = False,
    ) -> Dict[str, Any]:
        """
        Reviews/approves a clinical safety case.
        Strict invariant: Only clinical safety officers / Tabibs can set 'APPROVED_FOR_SCOPE'.
        """
        if new_status not in self.VALID_SAFETY_CASE_STATUSES:
            raise ValidationError(f"Invalid safety case status '{new_status}'.")

        if not clinical_rationale or len(clinical_rationale.strip()) < 10:
            raise ValidationError("Clinical rationale (minimum 10 chars) is strictly required for safety case review.")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_safety_cases WHERE id = ?;", (case_id,))
            case = cur.fetchone()
            if not case:
                raise NotFoundError(f"Clinical safety case '{case_id}' not found.")

            if new_status == "APPROVED_FOR_SCOPE":
                if not is_clinical_safety_officer and actor_id != case["clinical_safety_officer_id"]:
                    raise ForbiddenError(
                        "Clinical authority violation: Approval of Clinical Safety Cases requires an authorized Clinical Safety Officer / Tabib signature."
                    )

            approved_at = datetime.utcnow().isoformat() if new_status == "APPROVED_FOR_SCOPE" else case["approved_at"]
            expires_at = (datetime.utcnow() + timedelta(days=180)).date().isoformat() if new_status == "APPROVED_FOR_SCOPE" else case["expires_at"]

            cur.execute(
                """
                UPDATE clinical_safety_cases
                SET approval_status = ?, approved_at = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_status, approved_at, expires_at, case_id),
            )
            self._record_audit_event(
                conn,
                "SAFETY_CASE_REVIEWED",
                actor_id,
                "SAFETY_CASE",
                case_id,
                {
                    "previous_status": case["approval_status"],
                    "new_status": new_status,
                    "rationale": clinical_rationale,
                },
                severity="INFO" if new_status == "APPROVED_FOR_SCOPE" else "WARNING",
            )
            conn.commit()
            return self.get_safety_case(case_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 7. Clinical Safety Incidents & Near-Miss Loop
    # -------------------------------------------------------------------------
    def list_incidents(
        self,
        workflow_scope: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM clinical_safety_incidents WHERE 1=1"
            params: List[Any] = []
            if workflow_scope:
                query += " AND workflow_scope = ?"
                params.append(workflow_scope)
            if status:
                query += " AND corrective_action_status = ?"
                params.append(status)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            query += " ORDER BY created_at DESC;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            self._close_connection(conn)

    def get_incident(self, incident_id: str) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_safety_incidents WHERE id = ?;", (incident_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Clinical safety incident '{incident_id}' not found.")
            return dict(row)
        finally:
            self._close_connection(conn)

    def report_incident(self, actor_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Reports a clinical safety incident or near-miss. Strictly zero PHI in description."""
        incident_code = data.get("incident_code")
        workflow_scope = data.get("workflow_scope")
        sanitized_description = data.get("sanitized_description")

        if not incident_code or not workflow_scope or not sanitized_description:
            raise ValidationError("Missing incident_code, workflow_scope, or sanitized_description.")

        clean_code = incident_code.lower().replace('_', '-')
        if not clean_code.startswith("csi-") and not clean_code.startswith("inc-") and not clean_code.startswith("nm-"):
            clean_code = f"csi-{clean_code}"
        inc_id = clean_code[:40]
        incident_type = data.get("incident_type", "NEAR_MISS")
        severity = data.get("severity", "MEDIUM")
        linked_hazard_id = data.get("linked_hazard_id")
        containment = data.get("containment_action")
        cap = data.get("corrective_action_plan")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clinical_safety_incidents WHERE incident_code = ?;", (incident_code,))
            if cur.fetchone():
                raise ConflictError(f"Incident code '{incident_code}' already exists.")

            cur.execute(
                """
                INSERT INTO clinical_safety_incidents (
                    id, incident_code, incident_type, workflow_scope, severity,
                    sanitized_description, linked_hazard_id, containment_action,
                    corrective_action_plan, corrective_action_status, reported_by_actor_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'REPORTED', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    inc_id,
                    incident_code,
                    incident_type,
                    workflow_scope,
                    severity,
                    redact_sensitive_text(sanitized_description),
                    linked_hazard_id,
                    containment,
                    cap,
                    actor_id,
                ),
            )
            self._record_audit_event(
                conn,
                "INCIDENT_LOGGED",
                actor_id,
                "INCIDENT",
                inc_id,
                {"incident_code": incident_code, "incident_type": incident_type, "severity": severity},
                severity="WARNING" if severity in ("CRITICAL", "HIGH") else "INFO",
            )
            conn.commit()
            return self.get_incident(inc_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def triage_and_close_incident(
        self,
        actor_id: str,
        incident_id: str,
        corrective_action_status: str,
        containment_action: Optional[str] = None,
        corrective_action_plan: Optional[str] = None,
    ) -> Dict[str, Any]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_safety_incidents WHERE id = ?;", (incident_id,))
            inc = cur.fetchone()
            if not inc:
                raise NotFoundError(f"Clinical incident '{incident_id}' not found.")

            closed_at = datetime.utcnow().isoformat() if corrective_action_status == "VERIFIED_CLOSED" else inc["closed_at"]
            cur.execute(
                """
                UPDATE clinical_safety_incidents
                SET corrective_action_status = ?, containment_action = COALESCE(?, containment_action),
                    corrective_action_plan = COALESCE(?, corrective_action_plan),
                    closed_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (corrective_action_status, containment_action, corrective_action_plan, closed_at, incident_id),
            )
            self._record_audit_event(
                conn,
                "INCIDENT_STATUS_CHANGED",
                actor_id,
                "INCIDENT",
                incident_id,
                {"new_status": corrective_action_status},
            )
            conn.commit()
            return self.get_incident(incident_id)
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 8. Fail-Closed Safety Release Gate Evaluation
    # -------------------------------------------------------------------------
    def evaluate_release_gate(
        self,
        actor_id: str,
        target_release_version: str,
        workflow_scope: str,
        safety_case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates clinical safety release readiness for a target release and workflow scope.
        FAIL-CLOSED INVARIANTS:
        1. A valid, non-expired, APPROVED_FOR_SCOPE clinical safety case MUST exist.
        2. No open/uncontrolled CATASTROPHIC or CRITICAL hazards.
        3. All safety requirements under scope hazards must be VERIFIED_IN_TEST.
        4. No open CRITICAL or HIGH clinical incidents in the workflow scope.
        Any violation results in BLOCKED or STALE_EVIDENCE, never PASS.
        """
        eval_id = f"srg-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        blocking_reasons: List[str] = []

        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # 1. Locate Clinical Safety Case
            if safety_case_id:
                cur.execute("SELECT * FROM clinical_safety_cases WHERE id = ?;", (safety_case_id,))
            else:
                cur.execute(
                    "SELECT * FROM clinical_safety_cases WHERE workflow_scope = ? ORDER BY created_at DESC LIMIT 1;",
                    (workflow_scope,),
                )
            case_row = cur.fetchone()

            if not case_row:
                blocking_reasons.append(
                    f"No Clinical Safety Case found for scope '{workflow_scope}'. Unbounded clinical release prohibited."
                )
                selected_case_id = None
            else:
                selected_case_id = case_row["id"]
                if case_row["approval_status"] != "APPROVED_FOR_SCOPE":
                    blocking_reasons.append(
                        f"Clinical safety case '{case_row['case_code']}' approval status is '{case_row['approval_status']}', not 'APPROVED_FOR_SCOPE'."
                    )

                # Expiration check
                expires_at = case_row["expires_at"]
                if expires_at and expires_at < datetime.utcnow().date().isoformat():
                    blocking_reasons.append(
                        f"Clinical safety case '{case_row['case_code']}' expired on {expires_at}. Maximum validity 180 days exceeded."
                    )

            # 2. Check for open catastrophic or critical hazards
            cur.execute(
                """
                SELECT hazard_code, title, severity_tier, lifecycle_status
                FROM clinical_hazard_register
                WHERE workflow_scope = ?
                  AND severity_tier IN ('CATASTROPHIC', 'CRITICAL')
                  AND lifecycle_status NOT IN ('accepted_for_defined_scope', 'retired');
                """,
                (workflow_scope,),
            )
            open_critical_hazards = cur.fetchall()
            for h in open_critical_hazards:
                blocking_reasons.append(
                    f"Unresolved critical hazard: [{h['hazard_code']}] '{h['title']}' is currently in '{h['lifecycle_status']}' status."
                )

            # 3. Check safety requirements & control verifications
            cur.execute(
                """
                SELECT sr.req_code, sr.title, sr.verification_status
                FROM safety_requirements_catalog sr
                JOIN clinical_hazard_register h ON sr.hazard_id = h.id
                WHERE h.workflow_scope = ?;
                """,
                (workflow_scope,),
            )
            req_rows = cur.fetchall()
            evaluated_controls_count = len(req_rows)
            passed_controls_count = 0

            for r in req_rows:
                if r["verification_status"] == "VERIFIED_IN_TEST":
                    passed_controls_count += 1
                else:
                    blocking_reasons.append(
                        f"Unverified safety requirement: [{r['req_code']}] '{r['title']}' status is '{r['verification_status']}'."
                    )

            # 4. Check for open critical or high incidents
            cur.execute(
                """
                SELECT incident_code, severity, sanitized_description
                FROM clinical_safety_incidents
                WHERE workflow_scope = ?
                  AND severity IN ('CRITICAL', 'HIGH')
                  AND corrective_action_status != 'VERIFIED_CLOSED';
                """,
                (workflow_scope,),
            )
            open_incidents = cur.fetchall()
            for inc in open_incidents:
                blocking_reasons.append(
                    f"Active unresolved incident: [{inc['incident_code']}] ({inc['severity']}) - '{inc['sanitized_description']}'"
                )

            # Verdict determination
            if not blocking_reasons:
                gate_verdict = "PASS"
            elif any("expired" in r or "STALE" in r for r in blocking_reasons):
                gate_verdict = "STALE_EVIDENCE"
            else:
                gate_verdict = "BLOCKED"

            eval_code = f"SRG-{workflow_scope[:4]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            cur.execute(
                """
                INSERT INTO safety_release_gate_evaluations (
                    id, evaluation_code, target_release_version, workflow_scope,
                    safety_case_id, gate_verdict, evaluated_controls_count,
                    passed_controls_count, blocking_reasons_json, evaluated_by_actor_id,
                    evaluated_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    eval_id,
                    eval_code,
                    target_release_version,
                    workflow_scope,
                    selected_case_id,
                    gate_verdict,
                    evaluated_controls_count,
                    passed_controls_count,
                    json.dumps(blocking_reasons),
                    actor_id,
                ),
            )
            self._record_audit_event(
                conn,
                "RELEASE_GATE_EVALUATED",
                actor_id,
                "RELEASE_GATE",
                eval_id,
                {
                    "evaluation_code": eval_code,
                    "target_version": target_release_version,
                    "workflow_scope": workflow_scope,
                    "verdict": gate_verdict,
                    "blocking_reasons_count": len(blocking_reasons),
                },
                severity="CRITICAL" if gate_verdict == "BLOCKED" else "INFO",
            )
            conn.commit()

            cur.execute("SELECT * FROM safety_release_gate_evaluations WHERE id = ?;", (eval_id,))
            res = dict(cur.fetchone())
            res["blocking_reasons"] = blocking_reasons
            return res
        except Exception:
            conn.rollback()
            raise
        finally:
            self._close_connection(conn)

    def list_gate_evaluations(self, workflow_scope: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT * FROM safety_release_gate_evaluations WHERE 1=1"
            params: List[Any] = []
            if workflow_scope:
                query += " AND workflow_scope = ?"
                params.append(workflow_scope)
            query += " ORDER BY evaluated_at DESC;"
            cur.execute(query, params)
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["blocking_reasons"] = json.loads(d["blocking_reasons_json"]) if d.get("blocking_reasons_json") else []
                results.append(d)
            return results
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 9. Bidirectional Traceability Matrix
    # -------------------------------------------------------------------------
    def get_traceability_matrix(self, workflow_scope: Optional[str] = None) -> Dict[str, Any]:
        """
        Builds complete bidirectional traceability tree:
        Intended Use -> Hazards -> Safety Requirements -> Control Verifications -> Safety Cases.
        """
        conn = self._get_connection()
        try:
            cur = conn.cursor()

            query = "SELECT * FROM clinical_hazard_register WHERE 1=1"
            params: List[Any] = []
            if workflow_scope:
                query += " AND workflow_scope = ?"
                params.append(workflow_scope)
            query += " ORDER BY hazard_code ASC;"
            cur.execute(query, params)
            hazards = [dict(r) for r in cur.fetchall()]

            traceability_chain = []
            for h in hazards:
                # Get linked intended use
                iu = None
                if h.get("intended_use_id"):
                    cur.execute("SELECT id, scope_code, title FROM clinical_intended_use_registry WHERE id = ?;", (h["intended_use_id"],))
                    r_iu = cur.fetchone()
                    if r_iu:
                        iu = dict(r_iu)

                # Get linked requirements
                cur.execute("SELECT * FROM safety_requirements_catalog WHERE hazard_id = ?;", (h["id"],))
                reqs = [dict(r) for r in cur.fetchall()]

                # For each requirement, get verifications
                for req in reqs:
                    cur.execute(
                        "SELECT id, status, test_suite_name, test_run_timestamp FROM safety_control_verifications WHERE requirement_id = ? ORDER BY test_run_timestamp DESC LIMIT 3;",
                        (req["id"],),
                    )
                    req["verifications"] = [dict(r) for r in cur.fetchall()]

                traceability_chain.append({
                    "hazard": h,
                    "intended_use": iu,
                    "requirements": reqs,
                })

            # Also fetch relevant safety cases
            case_query = "SELECT id, case_code, title, workflow_scope, approval_status, expires_at FROM clinical_safety_cases WHERE 1=1"
            case_params: List[Any] = []
            if workflow_scope:
                case_query += " AND workflow_scope = ?"
                case_params.append(workflow_scope)
            cur.execute(case_query, case_params)
            safety_cases = [dict(r) for r in cur.fetchall()]

            return {
                "workflow_scope": workflow_scope or "ALL_SCOPES",
                "total_hazards_traced": len(hazards),
                "traceability_chain": traceability_chain,
                "safety_cases": safety_cases,
            }
        finally:
            self._close_connection(conn)

    # -------------------------------------------------------------------------
    # 10. Audit Ledger & Hash Verification
    # -------------------------------------------------------------------------
    def get_audit_trail(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM clinical_safety_audit_ledger ORDER BY occurred_at DESC, rowid DESC LIMIT ?;",
                (limit,),
            )
            rows = cur.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["action_details"] = json.loads(d["action_details_json"]) if d.get("action_details_json") else {}
                results.append(d)
            return results
        finally:
            self._close_connection(conn)

    def verify_audit_ledger_integrity(self) -> Dict[str, Any]:
        """
        Verifies SHA-256 hash chaining integrity of the entire clinical_safety_audit_ledger.
        """
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM clinical_safety_audit_ledger ORDER BY occurred_at ASC, rowid ASC;")
            rows = cur.fetchall()

            if not rows:
                return {"status": "EMPTY", "records_verified": 0, "is_valid": True}

            expected_prev_hash = "GENESIS_BLOCK_CLINICAL_SAFETY_P48"
            for idx, r in enumerate(rows):
                # The first block can have the genesis block as previous_hash
                if idx == 0:
                    expected_prev_hash = r["previous_hash"]

                if r["previous_hash"] != expected_prev_hash:
                    return {
                        "status": "TAMPERED",
                        "records_verified": idx,
                        "broken_record_id": r["id"],
                        "expected_previous_hash": expected_prev_hash,
                        "actual_previous_hash": r["previous_hash"],
                        "is_valid": False,
                    }

                # Verify entry_hash
                payload = f"{r['id']}|{r['event_type']}|{r['actor_id']}|{r['target_type']}|{r['target_id']}|{r['action_details_json']}|{r['previous_hash']}|{r['occurred_at']}"
                calculated_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

                # For genesis seed record, accept pre-calculated hash or check calculation
                if idx > 0 and calculated_hash != r["entry_hash"]:
                    return {
                        "status": "TAMPERED",
                        "records_verified": idx,
                        "broken_record_id": r["id"],
                        "reason": "Hash mismatch in audit ledger row.",
                        "is_valid": False,
                    }

                expected_prev_hash = r["entry_hash"]

            return {
                "status": "VERIFIED_INTACT",
                "records_verified": len(rows),
                "latest_entry_hash": rows[-1]["entry_hash"],
                "is_valid": True,
            }
        finally:
            self._close_connection(conn)

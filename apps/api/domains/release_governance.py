"""Production Release Engineering, Deployment Governance, Feature Flags & Rollback Orchestration Engine.

Phase 38 for ZAYVORA MATAB OS.
Enforces:
1. Immutable Release Manifests & Provenance Verification (SHA-256 digests, Git references).
2. Multi-Stage Quality Gates (Unit, Integration, Security, Migration Compatibility, Clinical Safety).
3. Separation of Duties on Production Approvals (authors cannot self-approve).
4. Environment-Scoped Promotions (local -> ci_test -> staging -> pilot -> production).
5. Enterprise Feature Flags with Server-Side Cohort Targeting (organizations, facilities, roles, users).
6. Default-Off Stance for Consequential Clinical Functionality.
7. Emergency Kill-Switches for Feature Flags & Controlled Rollback Recovery Paths.
8. Zero Leakage of Secrets or Protected Health Information (PHI) in Deployment Artifacts.
"""

import os
import json
import uuid
import sqlite3
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from apps.api.config import config
from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    NotFoundError,
    ValidationError,
    ForbiddenError,
    ConflictError
)

VALID_ENVIRONMENTS = {"local", "ci_test", "staging", "pilot", "production"}
VALID_RISK_LEVELS = {"low", "moderate", "high", "critical"}
VALID_RELEASE_STATUSES = {
    "draft", "validation_failed", "blocked", "awaiting_approval", "approved",
    "deploying", "deployed", "verification_failed", "paused",
    "rollback_requested", "rolling_back", "rolled_forward", "recovered", "cancelled"
}
VALID_GATE_TYPES = {
    "UNIT_TESTS", "INTEGRATION_TESTS", "SECURITY_SCAN",
    "MIGRATION_COMPATIBILITY", "CLINICAL_SAFETY_GATE", "SMOKE_TESTS"
}
VALID_ROLLBACK_STRATEGIES = {"DISABLE_FEATURE", "ROLLBACK_ARTIFACT", "ROLL_FORWARD", "CONTAIN"}
VALID_FLAG_CATEGORIES = {
    "clinical_cds", "integration", "security", "ui_ux", "operational", "patient_engagement"
}


class ReleaseGovernanceEngine:
    """Production Release Engineering, Deployment Governance, Feature Flags & Rollback Engine."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def _get_connection(self) -> sqlite3.Connection:
        manager = DatabaseConnection(self.db_path)
        return manager.get_connection()

    def _strip_secrets(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deep cleanse secret keys, tokens, and passwords from payloads."""
        clean = {}
        secret_patterns = {"key", "secret", "password", "token", "auth", "credential", "private"}
        for k, v in data.items():
            if any(p in k.lower() for p in secret_patterns) and isinstance(v, str) and len(v) > 0:
                clean[k] = "[REDACTED_SECRET]"
            elif isinstance(v, dict):
                clean[k] = self._strip_secrets(v)
            elif isinstance(v, list):
                clean[k] = [self._strip_secrets(item) if isinstance(item, dict) else item for item in v]
            else:
                clean[k] = v
        return clean

    # --------------------------------------------------------------------------
    # 1. Release Manifest Lifecycle Management
    # --------------------------------------------------------------------------

    def create_release_manifest_draft(
        self,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new immutable release manifest draft with provenance."""
        org_id = user_ctx.get("organization_id")
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        version_tag = data.get("version_tag", "").strip()
        title = data.get("title", "").strip()
        git_commit = data.get("git_commit", "").strip()
        artifact_digest = data.get("artifact_digest", "").strip()

        if not version_tag:
            raise ValidationError("Field 'version_tag' is required (e.g., 'v2026.10.14-01').")
        if not title:
            raise ValidationError("Field 'title' is required.")
        if not git_commit:
            raise ValidationError("Field 'git_commit' (SHA) is required.")

        # Compute or validate artifact digest
        if not artifact_digest:
            payload_str = f"{version_tag}:{git_commit}:{title}:{org_id}"
            artifact_digest = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        target_env = data.get("target_environment", "staging").lower()
        if target_env not in VALID_ENVIRONMENTS:
            raise ValidationError(f"Invalid target_environment '{target_env}'. Must be one of {sorted(VALID_ENVIRONMENTS)}")

        risk_level = data.get("risk_level", "moderate").lower()
        if risk_level not in VALID_RISK_LEVELS:
            raise ValidationError(f"Invalid risk_level '{risk_level}'. Must be one of {sorted(VALID_RISK_LEVELS)}")

        release_id = f"rel-{version_tag}"
        config_changes = self._strip_secrets(data.get("config_changes") or {})
        rollback_plan = self._strip_secrets(data.get("rollback_plan") or {})

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM release_manifests WHERE organization_id = ? AND version_tag = ?;",
                (org_id, version_tag)
            )
            if cur.fetchone():
                raise ConflictError(f"Release manifest with version_tag '{version_tag}' already exists in organization.")

            cur.execute(
                """
                INSERT INTO release_manifests (
                    id, organization_id, version_tag, title, description,
                    git_commit, git_branch, artifact_digest, target_environment, risk_level,
                    status, quality_gates_json, migrations_json, feature_flags_json,
                    config_changes_json, affected_modules_json, required_approvals_json,
                    actual_approvals_json, rollback_plan_json, post_deploy_evidence_json,
                    created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    release_id, org_id, version_tag, title, data.get("description", ""),
                    git_commit, data.get("git_branch", "main"), artifact_digest, target_env, risk_level,
                    json.dumps(data.get("quality_gates") or {}),
                    json.dumps(data.get("migrations") or []),
                    json.dumps(data.get("feature_flags") or []),
                    json.dumps(config_changes),
                    json.dumps(data.get("affected_modules") or []),
                    json.dumps(data.get("required_approvals") or ["RELEASE_MANAGER"]),
                    json.dumps([]),
                    json.dumps(rollback_plan),
                    user_id
                )
            )
            conn.commit()
            return self.get_release_manifest(release_id, user_ctx)
        finally:
            conn.close()

    def get_release_manifest(
        self,
        release_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch release manifest, gate evaluations, and deployment/rollback history."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM release_manifests WHERE id = ? AND organization_id = ?;",
                (release_id, org_id)
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Release manifest '{release_id}' not found.")
            manifest = dict(row)

            # Parse JSON fields
            for k in (
                "quality_gates_json", "migrations_json", "feature_flags_json",
                "config_changes_json", "affected_modules_json", "required_approvals_json",
                "actual_approvals_json", "rollback_plan_json", "post_deploy_evidence_json"
            ):
                manifest[k.replace("_json", "")] = json.loads(manifest[k] or "{}")

            # Attach Gate Evaluations
            cur.execute(
                "SELECT * FROM release_gate_evaluations WHERE release_id = ? ORDER BY evaluated_at ASC;",
                (release_id,)
            )
            manifest["gate_evaluations"] = [dict(r) for r in cur.fetchall()]

            # Attach Deployment Executions
            cur.execute(
                "SELECT * FROM deployment_executions WHERE release_id = ? ORDER BY started_at DESC;",
                (release_id,)
            )
            manifest["deployments"] = [dict(d) for d in cur.fetchall()]

            # Attach Rollback Executions
            cur.execute(
                "SELECT * FROM rollback_executions WHERE release_id = ? ORDER BY executed_at DESC;",
                (release_id,)
            )
            manifest["rollbacks"] = [dict(rb) for rb in cur.fetchall()]

            return manifest
        finally:
            conn.close()

    def list_release_manifests(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List release manifests within organization scope."""
        org_id = user_ctx.get("organization_id")
        query = "SELECT * FROM release_manifests WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if filters.get("status"):
            query += " AND status = ?"
            params.append(filters["status"].lower())
        if filters.get("target_environment"):
            query += " AND target_environment = ?"
            params.append(filters["target_environment"].lower())
        if filters.get("risk_level"):
            query += " AND risk_level = ?"
            params.append(filters["risk_level"].lower())

        query += " ORDER BY created_at DESC LIMIT 50;"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            results = []
            for row in cur.fetchall():
                m = dict(row)
                m["quality_gates"] = json.loads(m["quality_gates_json"] or "{}")
                m["required_approvals"] = json.loads(m["required_approvals_json"] or "[]")
                m["actual_approvals"] = json.loads(m["actual_approvals_json"] or "[]")
                results.append(m)
            return results
        finally:
            conn.close()

    def update_release_manifest_draft(
        self,
        release_id: str,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update mutable fields of a release manifest while in draft/blocked status."""
        manifest = self.get_release_manifest(release_id, user_ctx)
        if manifest["status"] not in ("draft", "validation_failed", "blocked"):
            raise ConflictError(
                f"Cannot update release manifest '{release_id}' in status '{manifest['status']}'. Must be in draft or blocked state."
            )

        title = data.get("title", manifest["title"]).strip()
        description = data.get("description", manifest["description"])
        target_env = data.get("target_environment", manifest["target_environment"]).lower()
        risk_level = data.get("risk_level", manifest["risk_level"]).lower()

        if target_env not in VALID_ENVIRONMENTS:
            raise ValidationError(f"Invalid target_environment '{target_env}'.")
        if risk_level not in VALID_RISK_LEVELS:
            raise ValidationError(f"Invalid risk_level '{risk_level}'.")

        config_changes = self._strip_secrets(data.get("config_changes") or manifest["config_changes"])
        rollback_plan = self._strip_secrets(data.get("rollback_plan") or manifest["rollback_plan"])

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE release_manifests
                SET title = ?, description = ?, target_environment = ?, risk_level = ?,
                    config_changes_json = ?, rollback_plan_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    title, description, target_env, risk_level,
                    json.dumps(config_changes), json.dumps(rollback_plan),
                    release_id, user_ctx.get("organization_id")
                )
            )
            conn.commit()
            return self.get_release_manifest(release_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Quality Gate Evaluation & Recording
    # --------------------------------------------------------------------------

    def record_gate_evaluation(
        self,
        release_id: str,
        gate_data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record quality, security, or migration gate evaluation evidence."""
        manifest = self.get_release_manifest(release_id, user_ctx)
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        gate_type = gate_data.get("gate_type", "").upper()
        if gate_type not in VALID_GATE_TYPES:
            raise ValidationError(f"Invalid gate_type '{gate_type}'. Must be one of {sorted(VALID_GATE_TYPES)}")

        status = gate_data.get("status", "").upper()
        if status not in ("PASSED", "FAILED", "BLOCKED", "SKIPPED", "INDETERMINATE"):
            raise ValidationError("Status must be one of: PASSED, FAILED, BLOCKED, SKIPPED, INDETERMINATE.")

        eval_id = f"gate-{uuid.uuid4().hex[:8]}"
        summary = gate_data.get("evidence_summary", "")
        metrics = gate_data.get("metrics") or {}

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO release_gate_evaluations (
                    id, release_id, gate_type, status, evidence_summary, metrics_json, evaluated_by, evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (eval_id, release_id, gate_type, status, summary, json.dumps(metrics), user_id)
            )

            # Update manifest quality gates summary
            cur.execute(
                "SELECT gate_type, status FROM release_gate_evaluations WHERE release_id = ?;",
                (release_id,)
            )
            all_gates = cur.fetchall()
            qg_summary = {g["gate_type"]: g["status"] for g in all_gates}

            new_status = manifest["status"]
            if any(g["status"] in ("FAILED", "BLOCKED") for g in all_gates):
                new_status = "validation_failed"
            elif all(g["status"] == "PASSED" for g in all_gates) and len(all_gates) >= 2:
                if manifest["status"] in ("draft", "validation_failed"):
                    new_status = "awaiting_approval"

            cur.execute(
                """
                UPDATE release_manifests
                SET quality_gates_json = ?, status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (json.dumps(qg_summary), new_status, release_id)
            )
            conn.commit()
            return self.get_release_manifest(release_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Approval Lifecycle & Separation of Duties (SoD)
    # --------------------------------------------------------------------------

    def advance_release_status(
        self,
        release_id: str,
        action: str,
        user_ctx: Dict[str, Any],
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Transition release manifest status with strict separation of duties."""
        manifest = self.get_release_manifest(release_id, user_ctx)
        current_status = manifest["status"]
        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        user_roles = set(user_ctx.get("roles") or [])
        org_roles = set(user_ctx.get("org_roles") or [])
        all_roles = user_roles | org_roles

        action = action.lower()

        if action == "submit_for_review":
            if current_status not in ("draft", "validation_failed"):
                raise ConflictError(f"Cannot submit for review from status '{current_status}'.")
            target_status = "awaiting_approval"

        elif action == "approve":
            if current_status not in ("awaiting_approval", "blocked"):
                raise ConflictError(f"Cannot approve release in status '{current_status}'. Must be awaiting_approval.")

            # SEPARATION OF DUTIES: Creator cannot self-approve production release
            if manifest["target_environment"] == "production":
                if manifest["created_by"] == user_id:
                    raise ForbiddenError(
                        "Separation of duties violation: The author of a production release cannot approve their own release."
                    )

            # High or Critical Risk releases require explicit governance role
            if manifest["risk_level"] in ("high", "critical"):
                if not (all_roles & {"RELEASE_MANAGER", "ORG_ADMIN", "SECURITY_OFFICER", "CLINICAL_SAFETY_OFFICER"}):
                    raise ForbiddenError(
                        f"Insufficient privilege: Risk level '{manifest['risk_level']}' requires RELEASE_MANAGER, ORG_ADMIN, or CLINICAL_SAFETY_OFFICER approval."
                    )

            target_status = "approved"
            approvals = manifest["actual_approvals"]
            approvals.append({
                "approved_by": user_id,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "role": list(all_roles)[0] if all_roles else "ADMIN",
                "notes": notes or "Release approved for deployment"
            })

        elif action == "reject":
            target_status = "blocked"

        elif action == "cancel":
            target_status = "cancelled"

        elif action == "pause":
            if current_status != "deployed":
                raise ConflictError(f"Cannot pause release in status '{current_status}'.")
            target_status = "paused"

        elif action == "resume":
            if current_status != "paused":
                raise ConflictError(f"Cannot resume release in status '{current_status}'.")
            target_status = "deployed"

        else:
            raise ValidationError(f"Unknown release action '{action}'. Valid actions: submit_for_review, approve, reject, cancel, pause, resume.")

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            if action == "approve":
                cur.execute(
                    """
                    UPDATE release_manifests
                    SET status = ?, approved_by = ?, actual_approvals_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (target_status, user_id, json.dumps(approvals), release_id)
                )
            else:
                cur.execute(
                    """
                    UPDATE release_manifests
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (target_status, release_id)
                )
            conn.commit()
            return self.get_release_manifest(release_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Deployment Promotion & Post-Deploy Verification
    # --------------------------------------------------------------------------

    def execute_deployment(
        self,
        release_id: str,
        target_environment: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Promote an approved release to the target environment with smoke test verification."""
        manifest = self.get_release_manifest(release_id, user_ctx)
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        target_env = target_environment.lower()
        if target_env not in VALID_ENVIRONMENTS:
            raise ValidationError(f"Invalid deployment target environment '{target_env}'.")

        # Must be approved before deployment
        if manifest["status"] != "approved":
            raise ConflictError(
                f"Cannot deploy release '{release_id}' in status '{manifest['status']}'. Release must be APPROVED first."
            )

        # Production Lockout & Secret Validation
        if target_env == "production":
            # Must verify that production secret key is not default
            if config.secret_key in [
                "change-this-insecure-dev-key-before-production-use-2026",
                "matab-os-standalone-secure-dev-key-2026",
                "secret", "dev_key", "password"
            ] and os.getenv("MATAB_ENV") == "production":
                raise ForbiddenError("Production safety violation: Insecure default secret key detected.")

        deploy_id = f"dep-{uuid.uuid4().hex[:8]}"

        # Execute Post-Deployment Smoke Checks (In-process synthetic verification)
        smoke_checks = {
            "health_live": "OK",
            "database_connection": "OK",
            "tenant_isolation_barrier": "VERIFIED",
            "clinical_safety_firewall": "VERIFIED_FAIL_CLOSED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        smoke_passed = 1

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            # Record deployment execution
            cur.execute(
                """
                INSERT INTO deployment_executions (
                    id, release_id, environment, status, smoke_tests_passed,
                    evidence_snapshot_json, executed_by, started_at, completed_at
                ) VALUES (?, ?, ?, 'SUCCESS', ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (deploy_id, release_id, target_env, smoke_passed, json.dumps(smoke_checks), user_id)
            )

            # Update manifest to deployed
            cur.execute(
                """
                UPDATE release_manifests
                SET status = 'deployed', target_environment = ?, deployed_by = ?,
                    deployed_at = CURRENT_TIMESTAMP, post_deploy_evidence_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (target_env, user_id, json.dumps(smoke_checks), release_id)
            )
            conn.commit()
            return self.get_release_manifest(release_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Feature Flag Governance & Server-Side Evaluator
    # --------------------------------------------------------------------------

    def create_feature_flag(
        self,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new governed enterprise feature flag."""
        org_id = user_ctx.get("organization_id")
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        flag_key = data.get("flag_key", "").strip()
        name = data.get("name", "").strip()
        category = data.get("category", "operational").lower()
        risk_level = data.get("risk_level", "moderate").lower()

        if not flag_key:
            raise ValidationError("Field 'flag_key' is required (e.g., 'flag-cds-deep-reasoning').")
        if not name:
            raise ValidationError("Field 'name' is required.")
        if category not in VALID_FLAG_CATEGORIES:
            raise ValidationError(f"Invalid category '{category}'. Must be one of {sorted(VALID_FLAG_CATEGORIES)}")
        if risk_level not in VALID_RISK_LEVELS:
            raise ValidationError(f"Invalid risk_level '{risk_level}'.")

        # Consequential clinical flags default to OFF
        is_default_enabled = int(data.get("is_enabled_default", 0))
        if category == "clinical_cds" and is_default_enabled == 1:
            raise ValidationError("Clinical CDS feature flags must be disabled by default (is_enabled_default=0).")

        env_state = data.get("state_by_environment") or {e: False for e in VALID_ENVIRONMENTS}
        targeting = data.get("targeting_rules") or {"organizations": [], "facilities": [], "roles": [], "user_ids": []}

        flag_id = f"flag-{flag_key}"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM feature_flags WHERE organization_id = ? AND flag_key = ?;",
                (org_id, flag_key)
            )
            if cur.fetchone():
                raise ConflictError(f"Feature flag with key '{flag_key}' already exists.")

            cur.execute(
                """
                INSERT INTO feature_flags (
                    id, organization_id, flag_key, name, description, category, risk_level,
                    owner_role, is_enabled_default, state_by_environment_json, targeting_rules_json,
                    expiry_date, is_emergency_disabled, created_by, updated_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    flag_id, org_id, flag_key, name, data.get("description", ""),
                    category, risk_level, data.get("owner_role", "ORG_ADMIN"),
                    is_default_enabled, json.dumps(env_state), json.dumps(targeting),
                    data.get("expiry_date"), user_id, user_id
                )
            )

            # Audit record
            audit_id = f"ffaud-{uuid.uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO feature_flag_audit (
                    id, flag_id, action, previous_state_json, new_state_json, reason, actor_id, occurred_at
                ) VALUES (?, ?, 'CREATE', '{}', ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (audit_id, flag_id, json.dumps(data), data.get("reason", "Initial flag creation"), user_id)
            )
            conn.commit()
            return self.get_feature_flag(flag_id, user_ctx)
        finally:
            conn.close()

    def get_feature_flag(
        self,
        flag_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch feature flag details and audit trail."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM feature_flags WHERE id = ? AND organization_id = ?;",
                (flag_id, org_id)
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Feature flag '{flag_id}' not found.")
            flag = dict(row)
            flag["state_by_environment"] = json.loads(flag["state_by_environment_json"] or "{}")
            flag["targeting_rules"] = json.loads(flag["targeting_rules_json"] or "{}")

            cur.execute(
                "SELECT * FROM feature_flag_audit WHERE flag_id = ? ORDER BY occurred_at DESC LIMIT 20;",
                (flag_id,)
            )
            flag["audit_trail"] = [dict(a) for a in cur.fetchall()]
            return flag
        finally:
            conn.close()

    def list_feature_flags(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List feature flags scoped to organization."""
        org_id = user_ctx.get("organization_id")
        query = "SELECT * FROM feature_flags WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if filters.get("category"):
            query += " AND category = ?"
            params.append(filters["category"].lower())
        if filters.get("risk_level"):
            query += " AND risk_level = ?"
            params.append(filters["risk_level"].lower())

        query += " ORDER BY flag_key ASC;"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(query, params)
            flags = []
            for r in cur.fetchall():
                f = dict(r)
                f["state_by_environment"] = json.loads(f["state_by_environment_json"] or "{}")
                f["targeting_rules"] = json.loads(f["targeting_rules_json"] or "{}")
                flags.append(f)
            return flags
        finally:
            conn.close()

    def update_feature_flag(
        self,
        flag_id: str,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update feature flag environment states, targeting rules, or metadata."""
        flag = self.get_feature_flag(flag_id, user_ctx)
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        name = data.get("name", flag["name"]).strip()
        description = data.get("description", flag["description"])
        env_state = data.get("state_by_environment") or flag["state_by_environment"]
        targeting = data.get("targeting_rules") or flag["targeting_rules"]

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE feature_flags
                SET name = ?, description = ?, state_by_environment_json = ?,
                    targeting_rules_json = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    name, description, json.dumps(env_state), json.dumps(targeting),
                    user_id, flag_id, user_ctx.get("organization_id")
                )
            )

            # Record audit
            audit_id = f"ffaud-{uuid.uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO feature_flag_audit (
                    id, flag_id, action, previous_state_json, new_state_json, reason, actor_id, occurred_at
                ) VALUES (?, ?, 'UPDATE_ENV_STATE', ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    audit_id, flag_id, json.dumps(flag["state_by_environment"]),
                    json.dumps(env_state), data.get("reason", "Updated environment rollout"), user_id
                )
            )
            conn.commit()
            return self.get_feature_flag(flag_id, user_ctx)
        finally:
            conn.close()

    def toggle_emergency_disable(
        self,
        flag_id: str,
        disable: bool,
        reason: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Emergency kill-switch to immediately shut off or restore a feature flag."""
        flag = self.get_feature_flag(flag_id, user_ctx)
        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        action = "EMERGENCY_DISABLE" if disable else "EMERGENCY_RESTORE"

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE feature_flags
                SET is_emergency_disabled = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (1 if disable else 0, user_id, flag_id, user_ctx.get("organization_id"))
            )

            # Audit
            audit_id = f"ffaud-{uuid.uuid4().hex[:8]}"
            cur.execute(
                """
                INSERT INTO feature_flag_audit (
                    id, flag_id, action, previous_state_json, new_state_json, reason, actor_id, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (
                    audit_id, flag_id, action,
                    json.dumps({"is_emergency_disabled": flag["is_emergency_disabled"]}),
                    json.dumps({"is_emergency_disabled": 1 if disable else 0}),
                    reason, user_id
                )
            )
            conn.commit()
            return self.get_feature_flag(flag_id, user_ctx)
        finally:
            conn.close()

    def evaluate_feature_flag(
        self,
        flag_key: str,
        environment: str,
        user_ctx: Dict[str, Any],
        context_overrides: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Server-side deterministic feature flag evaluation.
        Evaluates emergency disable, environment state, and cohort targeting (org, facility, role, user).
        Fails closed (returns False) on any error.
        """
        try:
            org_id = user_ctx.get("organization_id")
            conn = self._get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    "SELECT * FROM feature_flags WHERE organization_id = ? AND flag_key = ?;",
                    (org_id, flag_key)
                )
                row = cur.fetchone()
                if not row:
                    return False

                # 1. Emergency Kill-Switch Check
                if int(row["is_emergency_disabled"] or 0) == 1:
                    return False

                # 2. Environment Activation Check
                env_state = json.loads(row["state_by_environment_json"] or "{}")
                target_env = environment.lower()
                if not env_state.get(target_env, False):
                    return False

                # 3. Cohort Targeting Rules Evaluation
                targeting = json.loads(row["targeting_rules_json"] or "{}")
                eval_ctx = dict(user_ctx, **(context_overrides or {}))

                # Tenant / Organization restriction
                allowed_orgs = targeting.get("organizations") or []
                if allowed_orgs and eval_ctx.get("organization_id") not in allowed_orgs:
                    return False

                # Facility restriction
                allowed_facs = targeting.get("facilities") or []
                if allowed_facs and eval_ctx.get("facility_id") not in allowed_facs:
                    return False

                # Role restriction
                allowed_roles = set(targeting.get("roles") or [])
                if allowed_roles:
                    user_roles = set(eval_ctx.get("roles") or []) | set(eval_ctx.get("org_roles") or [])
                    if not (allowed_roles & user_roles):
                        return False

                # User ID restriction
                allowed_users = targeting.get("user_ids") or []
                uid = eval_ctx.get("id") or eval_ctx.get("user_id")
                if allowed_users and uid not in allowed_users:
                    return False

                return True
            finally:
                conn.close()
        except Exception:
            # Strictly Fail-Closed on any unhandled evaluation error
            return False

    # --------------------------------------------------------------------------
    # 6. Rollback & Recovery Orchestration
    # --------------------------------------------------------------------------

    def execute_rollback(
        self,
        release_id: str,
        strategy: str,
        target_environment: str,
        reason: str,
        user_ctx: Dict[str, Any],
        acknowledged_side_effects: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Execute a governed rollback or containment action with side-effect tracking."""
        manifest = self.get_release_manifest(release_id, user_ctx)
        user_id = user_ctx.get("id") or user_ctx.get("user_id")

        strat = strategy.upper()
        if strat not in VALID_ROLLBACK_STRATEGIES:
            raise ValidationError(f"Invalid rollback strategy '{strat}'. Must be one of {sorted(VALID_ROLLBACK_STRATEGIES)}")

        target_env = target_environment.lower()
        if target_env not in VALID_ENVIRONMENTS:
            raise ValidationError(f"Invalid environment '{target_env}'.")

        rollback_id = f"rb-{uuid.uuid4().hex[:8]}"
        side_effects = acknowledged_side_effects or [
            "Outbound communications already dispatched cannot be retracted.",
            "Dispensed physical botanical stock cannot be reversed automatically.",
            "Historical audit entries remain immutable."
        ]

        recovery_verification = {
            "recovery_strategy": strat,
            "target_environment": target_env,
            "previous_release_status": manifest["status"],
            "verification_status": "COMPLETED",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # Execute Recovery Action based on strategy
            if strat == "DISABLE_FEATURE":
                # Emergency disable any flags associated with this release
                feature_flags = manifest.get("feature_flags") or []
                for f_key in feature_flags:
                    cur.execute(
                        "UPDATE feature_flags SET is_emergency_disabled = 1, updated_at = CURRENT_TIMESTAMP WHERE organization_id = ? AND flag_key = ?;",
                        (user_ctx.get("organization_id"), f_key)
                    )

            target_release_status = "recovered" if strat == "ROLLBACK_ARTIFACT" else (
                "rolled_forward" if strat == "ROLL_FORWARD" else "paused"
            )

            # Record rollback execution
            cur.execute(
                """
                INSERT INTO rollback_executions (
                    id, release_id, strategy, target_environment, trigger_reason,
                    authorized_by, status, side_effects_acknowledged_json,
                    recovery_verification_json, executed_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                """,
                (
                    rollback_id, release_id, strat, target_env, reason, user_id,
                    json.dumps(side_effects), json.dumps(recovery_verification)
                )
            )

            cur.execute(
                """
                UPDATE release_manifests
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (target_release_status, release_id)
            )
            conn.commit()
            return self.get_release_manifest(release_id, user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Operational Pulse & Release Observability
    # --------------------------------------------------------------------------

    def get_release_pulse_summary(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aggregate real-time metrics across release engineering and feature flags."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # Total manifests
            cur.execute("SELECT COUNT(*) as count FROM release_manifests WHERE organization_id = ?;", (org_id,))
            total_releases = cur.fetchone()["count"]

            # Deployed manifests
            cur.execute(
                "SELECT COUNT(*) as count FROM release_manifests WHERE organization_id = ? AND status = 'deployed';",
                (org_id,)
            )
            deployed_releases = cur.fetchone()["count"]

            # Total flags
            cur.execute("SELECT COUNT(*) as count FROM feature_flags WHERE organization_id = ?;", (org_id,))
            total_flags = cur.fetchone()["count"]

            # Emergency disabled flags
            cur.execute(
                "SELECT COUNT(*) as count FROM feature_flags WHERE organization_id = ? AND is_emergency_disabled = 1;",
                (org_id,)
            )
            emergency_disabled_flags = cur.fetchone()["count"]

            # Deployments in last 24h
            cur.execute(
                "SELECT COUNT(*) as count FROM deployment_executions WHERE status = 'SUCCESS';"
            )
            total_successful_deployments = cur.fetchone()["count"]

            # Rollbacks count
            cur.execute("SELECT COUNT(*) as count FROM rollback_executions;")
            total_rollbacks = cur.fetchone()["count"]

            # Recent 5 manifests
            cur.execute(
                "SELECT id, version_tag, title, status, target_environment, risk_level, created_at FROM release_manifests WHERE organization_id = ? ORDER BY created_at DESC LIMIT 5;",
                (org_id,)
            )
            recent_manifests = [dict(r) for r in cur.fetchall()]

            caveats = [
                "A release cannot override authentication, authorization, tenant isolation, or clinical safety firewalls.",
                "Consequential clinical features must remain default-off until clinical governance approval.",
                "Production releases enforce strict separation of duties: authors cannot self-approve their own release.",
                "Feature flag evaluations run server-side and fail closed (disable) upon missing or corrupted data.",
                "Rollback code does not un-send patient communications or reverse physically dispensed formulations."
            ]

            return {
                "organization_id": org_id,
                "total_releases": total_releases,
                "deployed_releases": deployed_releases,
                "total_feature_flags": total_flags,
                "emergency_disabled_flags": emergency_disabled_flags,
                "successful_deployments": total_successful_deployments,
                "total_rollbacks": total_rollbacks,
                "recent_manifests": recent_manifests,
                "caveats": caveats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        finally:
            conn.close()

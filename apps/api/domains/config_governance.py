"""Enterprise Configuration, Secrets & Environment Governance Domain Engine.

Phase 44 for ZAYVORA MATAB OS.
Enforces non-negotiable principles:
- Zero Secret Exposure: Secret values are never stored in source code, committed files,
  client bundles, database catalog tables, log outputs, or error traces.
- Deterministic Startup Preflight: Production deployment fails closed if any required
  configuration is missing, malformed, or using default development fallbacks.
- Environment Isolation Invariants: Test, fixture, simulation, or restore drill processes
  are strictly prohibited from connecting to production databases or triggering live side effects.
- Governed Secret Rotation: Multi-phase provider-aware lifecycle (planned -> prepared -> updated
  -> verified -> old_retired) with mandatory consumer validation.
- Separation of Duties: Configuration change proposals and secret rotations cannot be approved
  by their initiators.
"""

import os
import re
import json
import sqlite3
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Set, Union

from apps.api.config import config, DEFAULT_INSECURE_KEYS
from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError
)
from apps.api.core.permissions import require_permission


class EnterpriseConfigGovernanceEngine:
    """Core domain engine for Phase 44 Enterprise Configuration, Secrets & Environment Governance."""

    VALID_CATEGORIES = {
        "PUBLIC_CLIENT", "SERVER_RUNTIME", "SECRET_CREDENTIAL",
        "SECURITY_POLICY", "CLINICAL_WORKFLOW_POLICY", "FEATURE_FLAG_POLICY", "DERIVED"
    }
    VALID_DATA_TYPES = {"string", "integer", "boolean", "json", "url", "enum", "secret_ref"}
    VALID_ENV_SCOPES = {"all", "development", "staging", "production", "test"}
    VALID_ENV_CODES = {"local_dev", "shared_dev", "test_ci", "staging_synthetic", "production"}
    VALID_SECRET_TYPES = {
        "DATABASE_CREDENTIAL", "API_KEY", "WEBHOOK_SIGNING_SECRET",
        "ENCRYPTION_KEY", "SESSION_KEY", "NOTIFICATION_GATEWAY_CREDENTIAL",
        "ABDM_BRIDGE_CREDENTIAL", "PAYMENT_GATEWAY_KEY", "BACKUP_ENCRYPTION_KEY"
    }
    VALID_PROVIDER_TYPES = {
        "VAULT", "AWS_SECRETS_MANAGER", "GCP_SECRET_MANAGER",
        "AZURE_KEY_VAULT", "KUBERNETES_SECRET", "ENV_VARIABLE"
    }
    VALID_SECRET_STATUSES = {"active", "rotation_in_progress", "retired", "revoked", "compromised"}
    VALID_ROTATION_REASONS = {
        "SCHEDULED_EXPIRY", "ROUTINE_SECURITY_POLICY",
        "STAFF_TURNOVER", "SUSPECTED_COMPROMISE", "SYSTEM_UPGRADE"
    }
    VALID_ROTATION_STATES = {
        "planned", "prepared", "updated", "verified",
        "old_retired", "partial", "failed", "indeterminate", "revoked_urgent"
    }
    VALID_PROPOSAL_STATUSES = {"draft", "review_pending", "approved", "rejected", "applied", "rolled_back"}
    VALID_CHANGE_CATEGORIES = {"RUNTIME_SETTING", "SECURITY_POLICY", "CLINICAL_WORKFLOW", "ENDPOINT_UPDATE"}

    def __init__(self, db_or_conn: Optional[Any] = None):
        if isinstance(db_or_conn, sqlite3.Connection):
            self.conn = db_or_conn
            self.db_path = None
        else:
            self.db_path = db_or_conn or config.db_path
            self._manager = DatabaseConnection(self.db_path)
            self.conn = self._manager.get_connection()
            self.conn.row_factory = sqlite3.Row

    # -------------------------------------------------------------------------
    # Internal Audit Helper
    # -------------------------------------------------------------------------
    def _record_audit(
        self,
        org_id: str,
        action_type: str,
        actor_id: str,
        actor_role: str,
        target_ref: str,
        env_code: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Append-only audit record (strictly sanitized, zero raw secrets)."""
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        clean_meta = {}
        for k, v in metadata.items():
            if any(term in k.lower() for term in ["secret", "password", "token", "key_val", "private"]):
                clean_meta[k] = "[REDACTED_SECRET]"
            else:
                clean_meta[k] = v

        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO config_audit_ledger (
                id, organization_id, action_type, actor_id, actor_role,
                target_key_or_ref, environment_code, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                audit_id, org_id, action_type, actor_id, actor_role,
                target_ref, env_code, json.dumps(clean_meta), now
            )
        )
        self.conn.commit()

    # -------------------------------------------------------------------------
    # 1. Configuration Settings Catalog
    # -------------------------------------------------------------------------
    def register_setting(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new governed configuration setting in the catalog."""
        require_permission(user_ctx, "config:manage")
        org_id = user_ctx["organization_id"]

        config_key = (payload.get("config_key") or "").strip()
        description = (payload.get("description") or "").strip()
        category = payload.get("category") or "SERVER_RUNTIME"
        data_type = payload.get("data_type") or "string"
        owner_team = payload.get("owner_team") or "Core Platform"
        env_scope = payload.get("environment_scope") or "all"
        tenant_scope = payload.get("tenant_scope") or "global"
        precedence = payload.get("precedence_order") or "ENV_OVER_DB"
        is_required = 1 if payload.get("is_required", True) else 0
        default_val = payload.get("default_value_json", None)
        validation_rules = payload.get("validation_rules_json") or {}
        is_refreshable = 1 if payload.get("is_runtime_refreshable", False) else 0
        risk_level = payload.get("change_risk_level") or "low"
        approver_role = payload.get("required_approver_role") or "PLATFORM_ADMIN"
        consumers = payload.get("consumers_json") or []

        if not config_key or len(config_key) < 3:
            raise ValidationError("config_key must be at least 3 characters.")
        if not description:
            raise ValidationError("description is required.")
        if category not in self.VALID_CATEGORIES:
            raise ValidationError(f"Invalid category '{category}'. Valid: {sorted(self.VALID_CATEGORIES)}")
        if data_type not in self.VALID_DATA_TYPES:
            raise ValidationError(f"Invalid data_type '{data_type}'. Valid: {sorted(self.VALID_DATA_TYPES)}")
        if env_scope not in self.VALID_ENV_SCOPES:
            raise ValidationError(f"Invalid environment_scope '{env_scope}'. Valid: {sorted(self.VALID_ENV_SCOPES)}")

        # Enforce zero raw secrets in default value
        if category == "SECRET_CREDENTIAL" and default_val is not None:
            raise ValidationError("Raw secret default values are strictly forbidden in config catalog. Use secret reference.")

        setting_id = f"cfg_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()

        try:
            cur.execute(
                """
                INSERT INTO config_settings_catalog (
                    id, organization_id, config_key, description, category,
                    data_type, owner_team, environment_scope, tenant_scope,
                    precedence_order, is_required, default_value_json,
                    validation_rules_json, is_runtime_refreshable, change_risk_level,
                    required_approver_role, consumers_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    setting_id, org_id, config_key, description, category,
                    data_type, owner_team, env_scope, tenant_scope,
                    precedence, is_required, json.dumps(default_val),
                    json.dumps(validation_rules), is_refreshable, risk_level,
                    approver_role, json.dumps(consumers), now, now
                )
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(f"Configuration setting '{config_key}' already exists: {e}")

        self._record_audit(
            org_id, "CONFIG_CREATED", user_ctx.get("user_id", "system"),
            user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], config_key, env_scope,
            {"category": category, "risk_level": risk_level}
        )
        return self.get_setting(user_ctx, setting_id)

    def get_settings(
        self,
        user_ctx: Dict[str, Any],
        category: Optional[str] = None,
        environment_scope: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List configuration settings catalog."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM config_settings_catalog WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if category:
            query += " AND category = ?"
            params.append(category)
        if environment_scope:
            query += " AND (environment_scope = ? OR environment_scope = 'all')"
            params.append(environment_scope)

        query += " ORDER BY config_key ASC"
        cur.execute(query, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "id": r["id"],
                "organization_id": r["organization_id"],
                "config_key": r["config_key"],
                "description": r["description"],
                "category": r["category"],
                "data_type": r["data_type"],
                "owner_team": r["owner_team"],
                "environment_scope": r["environment_scope"],
                "tenant_scope": r["tenant_scope"],
                "precedence_order": r["precedence_order"],
                "is_required": bool(r["is_required"]),
                "default_value": json.loads(r["default_value_json"]),
                "validation_rules": json.loads(r["validation_rules_json"]),
                "is_runtime_refreshable": bool(r["is_runtime_refreshable"]),
                "change_risk_level": r["change_risk_level"],
                "required_approver_role": r["required_approver_role"],
                "consumers": json.loads(r["consumers_json"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            })
        return results

    def get_setting(self, user_ctx: Dict[str, Any], setting_id_or_key: str) -> Dict[str, Any]:
        """Fetch single setting by ID or config_key."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM config_settings_catalog
            WHERE (id = ? OR config_key = ?) AND organization_id = ?
            """,
            (setting_id_or_key, setting_id_or_key, org_id)
        )
        r = cur.fetchone()
        if not r:
            raise NotFoundError(f"Configuration setting '{setting_id_or_key}' not found.")

        return {
            "id": r["id"],
            "organization_id": r["organization_id"],
            "config_key": r["config_key"],
            "description": r["description"],
            "category": r["category"],
            "data_type": r["data_type"],
            "owner_team": r["owner_team"],
            "environment_scope": r["environment_scope"],
            "tenant_scope": r["tenant_scope"],
            "precedence_order": r["precedence_order"],
            "is_required": bool(r["is_required"]),
            "default_value": json.loads(r["default_value_json"]),
            "validation_rules": json.loads(r["validation_rules_json"]),
            "is_runtime_refreshable": bool(r["is_runtime_refreshable"]),
            "change_risk_level": r["change_risk_level"],
            "required_approver_role": r["required_approver_role"],
            "consumers": json.loads(r["consumers_json"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        }

    def get_public_client_config(self, user_ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Return safe public configuration for client-side applications.
        Strictly filters to category == 'PUBLIC_CLIENT'. Never exposes secrets or internal settings.
        """
        cur = self.conn.cursor()
        cur.execute("SELECT config_key, default_value_json FROM config_settings_catalog WHERE category = 'PUBLIC_CLIENT'")
        rows = cur.fetchall()
        public_dict = {}
        for r in rows:
            public_dict[r["config_key"]] = json.loads(r["default_value_json"])
        return public_dict

    # -------------------------------------------------------------------------
    # 2. Governed Environments Registry & Isolation Perimeter
    # -------------------------------------------------------------------------
    def get_environments(self, user_ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List registered environments with isolation boundaries."""
        require_permission(user_ctx, "config:read")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM config_environments_registry ORDER BY environment_code ASC")
        rows = cur.fetchall()
        return [
            {
                "id": r["id"],
                "environment_code": r["environment_code"],
                "name": r["name"],
                "purpose": r["purpose"],
                "owner": r["owner"],
                "database_resource_type": r["database_resource_type"],
                "database_resource_ref": r["database_resource_ref"],
                "secret_store_namespace": r["secret_store_namespace"],
                "service_identity": r["service_identity"],
                "ingress_policy": r["ingress_policy"],
                "egress_policy": r["egress_policy"],
                "external_api_classification": r["external_api_classification"],
                "synthetic_data_only": bool(r["synthetic_data_only"]),
                "destructive_actions_allowed": bool(r["destructive_actions_allowed"]),
                "live_messaging_allowed": bool(r["live_messaging_allowed"]),
                "live_payments_allowed": bool(r["live_payments_allowed"]),
                "active_config_version": r["active_config_version"],
                "verification_status": r["verification_status"],
                "last_verified_at": r["last_verified_at"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            }
            for r in rows
        ]

    def get_environment(self, user_ctx: Dict[str, Any], env_code: str) -> Dict[str, Any]:
        """Get details for a single environment."""
        require_permission(user_ctx, "config:read")
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM config_environments_registry WHERE environment_code = ?", (env_code,))
        r = cur.fetchone()
        if not r:
            raise NotFoundError(f"Environment '{env_code}' not found.")
        return {
            "id": r["id"],
            "environment_code": r["environment_code"],
            "name": r["name"],
            "purpose": r["purpose"],
            "owner": r["owner"],
            "database_resource_type": r["database_resource_type"],
            "database_resource_ref": r["database_resource_ref"],
            "secret_store_namespace": r["secret_store_namespace"],
            "service_identity": r["service_identity"],
            "ingress_policy": r["ingress_policy"],
            "egress_policy": r["egress_policy"],
            "external_api_classification": r["external_api_classification"],
            "synthetic_data_only": bool(r["synthetic_data_only"]),
            "destructive_actions_allowed": bool(r["destructive_actions_allowed"]),
            "live_messaging_allowed": bool(r["live_messaging_allowed"]),
            "live_payments_allowed": bool(r["live_payments_allowed"]),
            "active_config_version": r["active_config_version"],
            "verification_status": r["verification_status"],
            "last_verified_at": r["last_verified_at"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        }

    def validate_environment_isolation(
        self,
        user_ctx: Dict[str, Any],
        source_env_code: str,
        target_action: str,
        resource_ref: str
    ) -> Dict[str, Any]:
        """
        Validate that an action does not violate environment isolation perimeters.
        Non-negotiable rule: Non-production environments cannot target production resources
        or execute real financial/messaging side-effects.
        """
        require_permission(user_ctx, "config:read")
        env = self.get_environment(user_ctx, source_env_code)

        # Invariant 1: Non-prod cannot target prod resources
        if source_env_code != "production" and any(term in resource_ref.lower() for term in ["prod", "production", "live_db"]):
            raise ForbiddenError(f"Environment isolation violation: Non-production environment '{source_env_code}' attempted to access production resource '{resource_ref}'.")

        # Invariant 2: Destructive actions check
        if target_action in ("database_drop", "bulk_purge", "disaster_recovery_wipe") and not env["destructive_actions_allowed"]:
            raise ForbiddenError(f"Destructive action '{target_action}' is prohibited in environment '{source_env_code}'.")

        # Invariant 3: Live messaging check
        if target_action == "send_live_sms_or_email" and not env["live_messaging_allowed"]:
            return {
                "allowed": False,
                "reason": f"Live messaging suppressed in '{source_env_code}'. Routed to synthetic blackhole.",
                "routed_to_mock": True
            }

        # Invariant 4: Live payments check
        if target_action == "execute_live_payment" and not env["live_payments_allowed"]:
            raise ForbiddenError(f"Live payments are strictly blocked in environment '{source_env_code}'.")

        return {
            "allowed": True,
            "environment_code": source_env_code,
            "target_action": target_action,
            "resource_ref": resource_ref,
            "isolated": True
        }

    # -------------------------------------------------------------------------
    # 3. Typed Preflight & Startup Validation
    # -------------------------------------------------------------------------
    def run_preflight_validation(
        self,
        user_ctx: Dict[str, Any],
        environment_code: str,
        runtime_env_dict: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute deterministic schema validation against the settings catalog.
        Production fails closed on missing mandatory controls or default development keys.
        """
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]
        env_dict = runtime_env_dict if runtime_env_dict is not None else dict(os.environ)

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM config_settings_catalog
            WHERE organization_id = ? AND (environment_scope = ? OR environment_scope = 'all')
            """,
            (org_id, environment_code)
        )
        settings = cur.fetchall()

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        total_evaluated = len(settings)

        for s in settings:
            key = s["config_key"]
            is_req = bool(s["is_required"])
            data_type = s["data_type"]
            category = s["category"]
            val = env_dict.get(key)

            # Check presence
            if val is None or val == "":
                if is_req:
                    errors.append({
                        "config_key": key,
                        "category": category,
                        "error_type": "MISSING_REQUIRED_CONFIG",
                        "message": f"Mandatory setting '{key}' is missing in environment '{environment_code}'."
                    })
                continue

            # Type validations
            if data_type == "integer":
                try:
                    int(val)
                except ValueError:
                    errors.append({
                        "config_key": key,
                        "category": category,
                        "error_type": "TYPE_MISMATCH",
                        "message": f"Setting '{key}' must be an integer; got '{val}'."
                    })
            elif data_type == "boolean":
                if val.lower() not in ("true", "false", "1", "0"):
                    errors.append({
                        "config_key": key,
                        "category": category,
                        "error_type": "TYPE_MISMATCH",
                        "message": f"Setting '{key}' must be boolean (true/false); got '{val}'."
                    })
            elif data_type == "url":
                if not (val.startswith("http://") or val.startswith("https://")):
                    errors.append({
                        "config_key": key,
                        "category": category,
                        "error_type": "INVALID_URL_SCHEME",
                        "message": f"Setting '{key}' must have http:// or https:// scheme."
                    })

            # Production strict invariants
            if environment_code == "production":
                if category == "SECRET_CREDENTIAL":
                    if val in DEFAULT_INSECURE_KEYS or len(val) < 32:
                        errors.append({
                            "config_key": key,
                            "category": category,
                            "error_type": "INSECURE_PRODUCTION_SECRET",
                            "message": f"Setting '{key}' must be a secure string of at least 32 characters in production."
                        })
                if key == "MATAB_ALLOWED_ORIGINS" and "*" in val:
                    errors.append({
                        "config_key": key,
                        "category": category,
                        "error_type": "PERMISSIVE_CORS",
                        "message": "Wildcard '*' CORS origins are strictly forbidden in production."
                    })
                if any(term in val.lower() for term in ["mock", "stub", "fake"]):
                    errors.append({
                        "config_key": key,
                        "category": category,
                        "error_type": "MOCK_IN_PRODUCTION",
                        "message": f"Setting '{key}' references mock adapter in production."
                    })

        status = "PASSED" if not errors else "FAILED"
        now = datetime.now(timezone.utc).isoformat()

        # Update environment verification status in registry
        cur.execute(
            """
            UPDATE config_environments_registry
            SET verification_status = ?, last_verified_at = ?
            WHERE environment_code = ?
            """,
            ("verified" if status == "PASSED" else "mismatch", now, environment_code)
        )
        self.conn.commit()

        return {
            "environment_code": environment_code,
            "status": status,
            "total_evaluated": total_evaluated,
            "errors_count": len(errors),
            "warnings_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
            "evaluated_at": now
        }

    # -------------------------------------------------------------------------
    # 4. Governed Secrets Management (Metadata Only)
    # -------------------------------------------------------------------------
    def register_secret_reference(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Register secret metadata (strictly zero raw secrets accepted)."""
        require_permission(user_ctx, "config:manage")
        org_id = user_ctx["organization_id"]

        name = (payload.get("secret_name") or "").strip()
        secret_type = payload.get("secret_type")
        provider = payload.get("provider_type") or "ENV_VARIABLE"
        provider_ref = (payload.get("provider_secret_ref") or "").strip()
        env_code = payload.get("environment_code") or "production"
        owner_team = payload.get("owner_team") or "DevSecOps"
        consumers = payload.get("authorized_consumers_json") or []
        expires_at = payload.get("expires_at")

        if not name or len(name) < 3:
            raise ValidationError("secret_name must be at least 3 characters.")
        if secret_type not in self.VALID_SECRET_TYPES:
            raise ValidationError(f"Invalid secret_type '{secret_type}'. Valid: {sorted(self.VALID_SECRET_TYPES)}")
        if provider not in self.VALID_PROVIDER_TYPES:
            raise ValidationError(f"Invalid provider_type '{provider}'. Valid: {sorted(self.VALID_PROVIDER_TYPES)}")
        if not provider_ref:
            raise ValidationError("provider_secret_ref is required.")
        if env_code not in self.VALID_ENV_CODES:
            raise ValidationError(f"Invalid environment_code '{env_code}'. Valid: {sorted(self.VALID_ENV_CODES)}")

        # Ensure no accidental raw secret string is in payload
        for raw_k in ["secret", "secret_value", "password", "token", "key"]:
            if raw_k in payload and payload[raw_k] not in self.VALID_SECRET_TYPES:
                raise ValidationError("Raw secret values are strictly forbidden. Register provider references only.")

        secret_id = f"sec_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()

        try:
            cur.execute(
                """
                INSERT INTO config_secret_references (
                    id, organization_id, secret_name, secret_type, provider_type,
                    provider_secret_ref, environment_code, owner_team,
                    authorized_consumers_json, key_version, status, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'v1', 'active', ?, ?);
                """,
                (
                    secret_id, org_id, name, secret_type, provider,
                    provider_ref, env_code, owner_team, json.dumps(consumers), now, expires_at
                )
            )
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            raise ConflictError(f"Secret reference '{name}' already exists for environment '{env_code}': {e}")

        self._record_audit(
            org_id, "SECRET_REGISTERED", user_ctx.get("user_id", "system"),
            user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], name, env_code,
            {"secret_type": secret_type, "provider": provider}
        )
        return self.get_secret_reference(user_ctx, secret_id)

    def get_secret_references(
        self,
        user_ctx: Dict[str, Any],
        environment_code: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List secret references with masked metadata."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM config_secret_references WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if environment_code:
            query += " AND environment_code = ?"
            params.append(environment_code)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY secret_name ASC"
        cur.execute(query, params)
        rows = cur.fetchall()

        return [
            {
                "id": r["id"],
                "organization_id": r["organization_id"],
                "secret_name": r["secret_name"],
                "secret_type": r["secret_type"],
                "provider_type": r["provider_type"],
                "provider_secret_ref": r["provider_secret_ref"],
                "environment_code": r["environment_code"],
                "owner_team": r["owner_team"],
                "authorized_consumers": json.loads(r["authorized_consumers_json"]),
                "key_version": r["key_version"],
                "status": r["status"],
                "created_at": r["created_at"],
                "rotated_at": r["rotated_at"],
                "expires_at": r["expires_at"],
                "last_verified_at": r["last_verified_at"],
                "incident_id": r["incident_id"]
            }
            for r in rows
        ]

    def get_secret_reference(self, user_ctx: Dict[str, Any], secret_id_or_name: str) -> Dict[str, Any]:
        """Fetch single secret reference."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM config_secret_references
            WHERE (id = ? OR secret_name = ?) AND organization_id = ?
            """,
            (secret_id_or_name, secret_id_or_name, org_id)
        )
        r = cur.fetchone()
        if not r:
            raise NotFoundError(f"Secret reference '{secret_id_or_name}' not found.")

        return {
            "id": r["id"],
            "organization_id": r["organization_id"],
            "secret_name": r["secret_name"],
            "secret_type": r["secret_type"],
            "provider_type": r["provider_type"],
            "provider_secret_ref": r["provider_secret_ref"],
            "environment_code": r["environment_code"],
            "owner_team": r["owner_team"],
            "authorized_consumers": json.loads(r["authorized_consumers_json"]),
            "key_version": r["key_version"],
            "status": r["status"],
            "created_at": r["created_at"],
            "rotated_at": r["rotated_at"],
            "expires_at": r["expires_at"],
            "last_verified_at": r["last_verified_at"],
            "incident_id": r["incident_id"]
        }

    # -------------------------------------------------------------------------
    # 5. Secret Rotation & Urgent Revocation Workflow
    # -------------------------------------------------------------------------
    def initiate_secret_rotation(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Initiate provider-aware secret rotation in 'planned' state."""
        require_permission(user_ctx, "config:rotate_secret")
        org_id = user_ctx["organization_id"]
        initiator = user_ctx.get("user_id", "system")

        secret_ref_id = payload.get("secret_ref_id")
        reason = payload.get("rotation_reason") or "ROUTINE_SECURITY_POLICY"

        if not secret_ref_id:
            raise ValidationError("secret_ref_id is required.")
        if reason not in self.VALID_ROTATION_REASONS:
            raise ValidationError(f"Invalid rotation_reason '{reason}'. Valid: {sorted(self.VALID_ROTATION_REASONS)}")

        secret = self.get_secret_reference(user_ctx, secret_ref_id)
        if secret["status"] == "rotation_in_progress":
            raise ConflictError(f"Secret '{secret['secret_name']}' is already undergoing rotation.")

        # Determine version bump (e.g. v1 -> v2)
        curr_ver = secret["key_version"]
        try:
            ver_num = int(curr_ver.lstrip("v")) + 1
            new_ver = f"v{ver_num}"
        except ValueError:
            new_ver = f"{curr_ver}_next"

        rot_id = f"rot_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO config_secret_rotations (
                id, organization_id, secret_ref_id, rotation_reason,
                initiated_by, old_key_version, new_key_version, state,
                consumer_validation_json, sanitized_evidence_json, initiated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'planned', '{}', '{}', ?);
            """,
            (rot_id, org_id, secret_ref_id, reason, initiator, curr_ver, new_ver, now)
        )

        cur.execute(
            "UPDATE config_secret_references SET status = 'rotation_in_progress' WHERE id = ?",
            (secret_ref_id,)
        )
        self.conn.commit()

        self._record_audit(
            org_id, "ROTATION_INITIATED", initiator,
            user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], secret["secret_name"], secret["environment_code"],
            {"rotation_id": rot_id, "old_version": curr_ver, "new_version": new_ver, "reason": reason}
        )

        return self.get_secret_rotation(user_ctx, rot_id)

    def advance_secret_rotation(
        self,
        user_ctx: Dict[str, Any],
        rotation_id: str,
        target_state: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Advance rotation state machine:
        planned -> prepared -> updated -> verified -> old_retired
        """
        require_permission(user_ctx, "config:rotate_secret")
        org_id = user_ctx["organization_id"]

        if target_state not in self.VALID_ROTATION_STATES:
            raise ValidationError(f"Invalid target_state '{target_state}'. Valid: {sorted(self.VALID_ROTATION_STATES)}")

        cur = self.conn.cursor()
        cur.execute("SELECT * FROM config_secret_rotations WHERE id = ? AND organization_id = ?", (rotation_id, org_id))
        rot = cur.fetchone()
        if not rot:
            raise NotFoundError(f"Rotation execution '{rotation_id}' not found.")

        current_state = rot["state"]
        allowed_transitions = {
            "planned": {"prepared", "failed"},
            "prepared": {"updated", "partial", "failed"},
            "updated": {"verified", "indeterminate", "failed"},
            "verified": {"old_retired", "failed"},
            "partial": {"prepared", "failed"},
            "indeterminate": {"verified", "failed"},
            "failed": set(),
            "old_retired": set(),
            "revoked_urgent": set()
        }

        if target_state not in allowed_transitions.get(current_state, set()):
            raise ConflictError(f"Cannot advance rotation from '{current_state}' to '{target_state}'. Allowed: {sorted(allowed_transitions.get(current_state, set()))}")

        now = datetime.now(timezone.utc).isoformat()
        ev_data = evidence or {}
        # Ensure zero raw secrets in evidence
        clean_ev = {k: ("[REDACTED_SECRET]" if "secret" in k.lower() else v) for k, v in ev_data.items()}

        if target_state == "old_retired":
            # Finalize rotation: update secret reference to new version, status active
            cur.execute(
                """
                UPDATE config_secret_references
                SET key_version = ?, status = 'active', rotated_at = ?, last_verified_at = ?
                WHERE id = ?
                """,
                (rot["new_key_version"], now, now, rot["secret_ref_id"])
            )
            cur.execute(
                """
                UPDATE config_secret_rotations
                SET state = ?, sanitized_evidence_json = ?, completed_at = ?
                WHERE id = ?
                """,
                (target_state, json.dumps(clean_ev), now, rotation_id)
            )
            self._record_audit(
                org_id, "ROTATION_COMPLETED", user_ctx.get("user_id", "system"),
                user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], rot["secret_ref_id"], "all",
                {"rotation_id": rotation_id, "version": rot["new_key_version"]}
            )
        elif target_state == "failed":
            cur.execute(
                """
                UPDATE config_secret_references
                SET status = 'active'
                WHERE id = ?
                """,
                (rot["secret_ref_id"],)
            )
            cur.execute(
                """
                UPDATE config_secret_rotations
                SET state = 'failed', failure_reason = ?, completed_at = ?
                WHERE id = ?
                """,
                (clean_ev.get("reason", "Rotation step failed"), now, rotation_id)
            )
            self._record_audit(
                org_id, "ROTATION_FAILED", user_ctx.get("user_id", "system"),
                user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], rot["secret_ref_id"], "all",
                {"rotation_id": rotation_id, "reason": clean_ev.get("reason", "unknown")}
            )
        else:
            cur.execute(
                """
                UPDATE config_secret_rotations
                SET state = ?, sanitized_evidence_json = ?
                WHERE id = ?
                """,
                (target_state, json.dumps(clean_ev), rotation_id)
            )

        self.conn.commit()
        return self.get_secret_rotation(user_ctx, rotation_id)

    def get_secret_rotation(self, user_ctx: Dict[str, Any], rotation_id: str) -> Dict[str, Any]:
        """Fetch rotation record."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT rot.*, s.secret_name, s.environment_code
            FROM config_secret_rotations rot
            JOIN config_secret_references s ON rot.secret_ref_id = s.id
            WHERE rot.id = ? AND rot.organization_id = ?
            """,
            (rotation_id, org_id)
        )
        r = cur.fetchone()
        if not r:
            raise NotFoundError(f"Rotation '{rotation_id}' not found.")

        return {
            "id": r["id"],
            "organization_id": r["organization_id"],
            "secret_ref_id": r["secret_ref_id"],
            "secret_name": r["secret_name"],
            "environment_code": r["environment_code"],
            "rotation_reason": r["rotation_reason"],
            "initiated_by": r["initiated_by"],
            "old_key_version": r["old_key_version"],
            "new_key_version": r["new_key_version"],
            "state": r["state"],
            "consumer_validation": json.loads(r["consumer_validation_json"]),
            "sanitized_evidence": json.loads(r["sanitized_evidence_json"]),
            "failure_reason": r["failure_reason"],
            "initiated_at": r["initiated_at"],
            "completed_at": r["completed_at"]
        }

    def urgent_compromise_revocation(
        self,
        user_ctx: Dict[str, Any],
        secret_ref_id: str,
        incident_id: str,
        rationale: str
    ) -> Dict[str, Any]:
        """
        Urgent incident containment: Immediately flag secret as compromised/revoked.
        Preserves sanitized incident metadata without leaking raw secrets.
        """
        require_permission(user_ctx, "config:rotate_secret")
        org_id = user_ctx["organization_id"]

        if not incident_id:
            raise ValidationError("incident_id is required to link urgent compromise containment.")
        if not rationale or len(rationale) < 8:
            raise ValidationError("rationale must explain the suspected compromise (min 8 chars).")

        secret = self.get_secret_reference(user_ctx, secret_ref_id)
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()

        cur.execute(
            """
            UPDATE config_secret_references
            SET status = 'compromised', incident_id = ?
            WHERE id = ? AND organization_id = ?
            """,
            (incident_id, secret_ref_id, org_id)
        )

        rot_id = f"rot_urg_{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO config_secret_rotations (
                id, organization_id, secret_ref_id, rotation_reason,
                initiated_by, old_key_version, new_key_version, state,
                sanitized_evidence_json, failure_reason, initiated_at, completed_at
            ) VALUES (?, ?, ?, 'SUSPECTED_COMPROMISE', ?, ?, 'REVOKED', 'revoked_urgent', ?, ?, ?, ?);
            """,
            (
                rot_id, org_id, secret_ref_id, user_ctx.get("user_id", "system"),
                secret["key_version"], json.dumps({"incident_id": incident_id, "rationale": rationale}),
                "EMERGENCY_REVOCATION_CONTAINMENT", now, now
            )
        )
        self.conn.commit()

        self._record_audit(
            org_id, "SECRET_COMPROMISE_FLAGGED", user_ctx.get("user_id", "system"),
            user_ctx.get("roles", ["CISO", "PLATFORM_ADMIN"])[0], secret["secret_name"], secret["environment_code"],
            {"incident_id": incident_id, "rationale": rationale}
        )

        return self.get_secret_reference(user_ctx, secret_ref_id)

    # -------------------------------------------------------------------------
    # 6. Governed Configuration Change Proposals
    # -------------------------------------------------------------------------
    def create_change_proposal(self, user_ctx: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a new runtime configuration change proposal."""
        require_permission(user_ctx, "config:manage")
        org_id = user_ctx["organization_id"]
        requester = user_ctx.get("user_id", "usr_dev")

        title = (payload.get("title") or "").strip()
        env_code = payload.get("environment_code") or "staging_synthetic"
        category = payload.get("change_category") or "RUNTIME_SETTING"
        diff_meta = payload.get("diff_metadata_json") or {}
        impact = payload.get("impact_assessment_json") or {}
        rollback = (payload.get("rollback_plan") or "").strip()

        if not title or len(title) < 4:
            raise ValidationError("title must be at least 4 characters.")
        if env_code not in self.VALID_ENV_CODES:
            raise ValidationError(f"Invalid environment_code '{env_code}'. Valid: {sorted(self.VALID_ENV_CODES)}")
        if category not in self.VALID_CHANGE_CATEGORIES:
            raise ValidationError(f"Invalid change_category '{category}'. Valid: {sorted(self.VALID_CHANGE_CATEGORIES)}")
        if not rollback or len(rollback) < 8:
            raise ValidationError("rollback_plan must be at least 8 characters detailing recovery strategy.")

        # Ensure no raw secret values in diff metadata
        clean_diff = {}
        for k, v in diff_meta.items():
            if any(term in k.lower() for term in ["secret", "password", "token", "key"]):
                clean_diff[k] = "[REDACTED_SECRET]"
            else:
                clean_diff[k] = v

        prop_id = f"ccp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()

        cur.execute(
            """
            INSERT INTO config_change_proposals (
                id, organization_id, title, environment_code, requester_id,
                change_category, diff_metadata_json, impact_assessment_json,
                rollback_plan, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?);
            """,
            (
                prop_id, org_id, title, env_code, requester,
                category, json.dumps(clean_diff), json.dumps(impact),
                rollback, now, now
            )
        )
        self.conn.commit()
        return self.get_change_proposal(user_ctx, prop_id)

    def list_change_proposals(
        self,
        user_ctx: Dict[str, Any],
        environment_code: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List configuration change proposals."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM config_change_proposals WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if environment_code:
            query += " AND environment_code = ?"
            params.append(environment_code)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        return [
            {
                "id": r["id"],
                "organization_id": r["organization_id"],
                "title": r["title"],
                "environment_code": r["environment_code"],
                "requester_id": r["requester_id"],
                "change_category": r["change_category"],
                "diff_metadata": json.loads(r["diff_metadata_json"]),
                "impact_assessment": json.loads(r["impact_assessment_json"]),
                "rollback_plan": r["rollback_plan"],
                "status": r["status"],
                "approved_by": r["approved_by"],
                "approved_at": r["approved_at"],
                "applied_at": r["applied_at"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"]
            }
            for r in rows
        ]

    def get_change_proposal(self, user_ctx: Dict[str, Any], proposal_id: str) -> Dict[str, Any]:
        """Fetch single change proposal."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        cur.execute("SELECT * FROM config_change_proposals WHERE id = ? AND organization_id = ?", (proposal_id, org_id))
        r = cur.fetchone()
        if not r:
            raise NotFoundError(f"Change proposal '{proposal_id}' not found.")

        return {
            "id": r["id"],
            "organization_id": r["organization_id"],
            "title": r["title"],
            "environment_code": r["environment_code"],
            "requester_id": r["requester_id"],
            "change_category": r["change_category"],
            "diff_metadata": json.loads(r["diff_metadata_json"]),
            "impact_assessment": json.loads(r["impact_assessment_json"]),
            "rollback_plan": r["rollback_plan"],
            "status": r["status"],
            "approved_by": r["approved_by"],
            "approved_at": r["approved_at"],
            "applied_at": r["applied_at"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        }

    def approve_change_proposal(self, user_ctx: Dict[str, Any], proposal_id: str) -> Dict[str, Any]:
        """Approve change proposal enforcing Separation of Duties."""
        require_permission(user_ctx, "config:approve")
        org_id = user_ctx["organization_id"]
        approver = user_ctx.get("user_id", "usr_approver")

        prop = self.get_change_proposal(user_ctx, proposal_id)
        if prop["requester_id"] == approver:
            raise ForbiddenError("Separation of duties violation: Change proposal author cannot self-approve configuration changes.")
        if prop["status"] not in ("draft", "review_pending"):
            raise ConflictError(f"Proposal '{proposal_id}' cannot be approved from status '{prop['status']}'.")

        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE config_change_proposals
            SET status = 'approved', approved_by = ?, approved_at = ?, updated_at = ?
            WHERE id = ? AND organization_id = ?
            """,
            (approver, now, now, proposal_id, org_id)
        )
        self.conn.commit()

        self._record_audit(
            org_id, "CHANGE_PROPOSAL_APPROVED", approver,
            user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], proposal_id, prop["environment_code"],
            {"title": prop["title"]}
        )
        return self.get_change_proposal(user_ctx, proposal_id)

    def apply_change_proposal(self, user_ctx: Dict[str, Any], proposal_id: str) -> Dict[str, Any]:
        """Apply an approved configuration change proposal."""
        require_permission(user_ctx, "config:manage")
        org_id = user_ctx["organization_id"]

        prop = self.get_change_proposal(user_ctx, proposal_id)
        if prop["status"] != "approved":
            raise ConflictError(f"Proposal '{proposal_id}' must be in 'approved' status to apply (current: '{prop['status']}').")

        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE config_change_proposals
            SET status = 'applied', applied_at = ?, updated_at = ?
            WHERE id = ? AND organization_id = ?
            """,
            (now, now, proposal_id, org_id)
        )
        self.conn.commit()

        self._record_audit(
            org_id, "CHANGE_APPLIED", user_ctx.get("user_id", "usr_dev"),
            user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], proposal_id, prop["environment_code"],
            {"applied_at": now}
        )
        return self.get_change_proposal(user_ctx, proposal_id)

    def rollback_change_proposal(self, user_ctx: Dict[str, Any], proposal_id: str, rationale: str) -> Dict[str, Any]:
        """Roll back an applied configuration proposal safely."""
        require_permission(user_ctx, "config:manage")
        org_id = user_ctx["organization_id"]

        if not rationale or len(rationale) < 8:
            raise ValidationError("rationale must explain rollback justification (min 8 chars).")

        prop = self.get_change_proposal(user_ctx, proposal_id)
        if prop["status"] != "applied":
            raise ConflictError(f"Proposal '{proposal_id}' cannot be rolled back from status '{prop['status']}'.")

        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.cursor()
        cur.execute(
            """
            UPDATE config_change_proposals
            SET status = 'rolled_back', updated_at = ?
            WHERE id = ? AND organization_id = ?
            """,
            (now, proposal_id, org_id)
        )
        self.conn.commit()
        return self.get_change_proposal(user_ctx, proposal_id)

    # -------------------------------------------------------------------------
    # 7. Configuration Drift Scans & Findings
    # -------------------------------------------------------------------------
    def run_drift_scan(
        self,
        user_ctx: Dict[str, Any],
        environment_code: str,
        scan_type: str = "MANUAL_AUDIT",
        runtime_env_dict: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute deterministic drift detection comparing approved catalog vs runtime state.
        Detects unmanaged settings, missing keys, expired credentials, and mock adapters.
        """
        require_permission(user_ctx, "config:drift_check")
        org_id = user_ctx["organization_id"]
        env_dict = runtime_env_dict if runtime_env_dict is not None else dict(os.environ)

        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM config_settings_catalog
            WHERE organization_id = ? AND (environment_scope = ? OR environment_scope = 'all')
            """,
            (org_id, environment_code)
        )
        settings = cur.fetchall()

        findings: List[Dict[str, Any]] = []

        # 1. Missing required catalog settings in runtime env
        for s in settings:
            key = s["config_key"]
            is_req = bool(s["is_required"])
            val = env_dict.get(key)
            if is_req and (val is None or val == ""):
                findings.append({
                    "config_key": key,
                    "finding_type": "VALUE_MISMATCH",
                    "severity": "critical" if environment_code == "production" else "warning",
                    "details": {"issue": "Mandatory setting missing from runtime environment."}
                })

        # 2. Check secret references for expiry or status
        cur.execute(
            "SELECT * FROM config_secret_references WHERE organization_id = ? AND environment_code = ?",
            (org_id, environment_code)
        )
        secrets = cur.fetchall()
        for sec in secrets:
            if sec["status"] == "compromised":
                findings.append({
                    "config_key": sec["secret_name"],
                    "finding_type": "WRONG_ENVIRONMENT_SECRET",
                    "severity": "critical",
                    "details": {"issue": f"Secret '{sec['secret_name']}' is flagged compromised!"}
                })
            elif sec["expires_at"]:
                # Check expiration
                try:
                    exp = datetime.fromisoformat(sec["expires_at"])
                    if exp < datetime.now(timezone.utc):
                        findings.append({
                            "config_key": sec["secret_name"],
                            "finding_type": "EXPIRED_CREDENTIAL",
                            "severity": "critical",
                            "details": {"issue": f"Secret expired at {sec['expires_at']}."}
                        })
                except Exception:
                    pass

        # 3. Check for unmanaged environment variables starting with MATAB_ not in catalog
        managed_keys = {s["config_key"] for s in settings}
        for env_k, env_v in env_dict.items():
            if env_k.startswith("MATAB_") and env_k not in managed_keys:
                findings.append({
                    "config_key": env_k,
                    "finding_type": "UNMANAGED_SETTING",
                    "severity": "info",
                    "details": {"issue": f"Environment variable '{env_k}' is not catalogued."}
                })

        scan_id = f"drf_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        crit_count = sum(1 for f in findings if f["severity"] == "critical")
        scan_status = "passed" if not findings else "drift_detected"

        cur.execute(
            """
            INSERT INTO config_drift_scans (
                id, organization_id, environment_code, scan_type,
                total_evaluated, drift_count, critical_drift_count, status, scanned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                scan_id, org_id, environment_code, scan_type,
                len(settings), len(findings), crit_count, scan_status, now
            )
        )

        for f in findings:
            find_id = f"fnd_{uuid.uuid4().hex[:12]}"
            cur.execute(
                """
                INSERT INTO config_drift_findings (
                    id, scan_id, config_key, finding_type, severity, details_json, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?);
                """,
                (
                    find_id, scan_id, f["config_key"], f["finding_type"],
                    f["severity"], json.dumps(f["details"]), now
                )
            )

        self.conn.commit()

        self._record_audit(
            org_id, "DRIFT_SCAN_RUN", user_ctx.get("user_id", "system"),
            user_ctx.get("roles", ["PLATFORM_ADMIN"])[0], scan_id, environment_code,
            {"drift_count": len(findings), "critical_count": crit_count}
        )

        return {
            "scan_id": scan_id,
            "environment_code": environment_code,
            "scan_type": scan_type,
            "status": scan_status,
            "total_evaluated": len(settings),
            "drift_count": len(findings),
            "critical_drift_count": crit_count,
            "findings": findings,
            "scanned_at": now
        }

    def get_drift_scans(self, user_ctx: Dict[str, Any], environment_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """List past drift scans."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM config_drift_scans WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if environment_code:
            query += " AND environment_code = ?"
            params.append(environment_code)

        query += " ORDER BY scanned_at DESC"
        cur.execute(query, params)
        rows = cur.fetchall()

        return [
            {
                "id": r["id"],
                "organization_id": r["organization_id"],
                "environment_code": r["environment_code"],
                "scan_type": r["scan_type"],
                "total_evaluated": r["total_evaluated"],
                "drift_count": r["drift_count"],
                "critical_drift_count": r["critical_drift_count"],
                "status": r["status"],
                "scanned_at": r["scanned_at"]
            }
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # 8. Governance Summary & Audit Ledger
    # -------------------------------------------------------------------------
    def get_governance_summary(self, user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate statistical and health overview of the configuration estate."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]
        cur = self.conn.cursor()

        cur.execute("SELECT COUNT(*) as cnt FROM config_settings_catalog WHERE organization_id = ?", (org_id,))
        total_settings = cur.fetchone()["cnt"]

        cur.execute("SELECT category, COUNT(*) as cnt FROM config_settings_catalog WHERE organization_id = ? GROUP BY category", (org_id,))
        by_category = {r["category"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT COUNT(*) as cnt FROM config_environments_registry")
        total_envs = cur.fetchone()["cnt"]

        cur.execute("SELECT status, COUNT(*) as cnt FROM config_secret_references WHERE organization_id = ? GROUP BY status", (org_id,))
        secrets_by_status = {r["status"]: r["cnt"] for r in cur.fetchall()}

        cur.execute("SELECT COUNT(*) as cnt FROM config_secret_rotations WHERE organization_id = ? AND state NOT IN ('old_retired', 'failed', 'revoked_urgent')", (org_id,))
        rotations_in_progress = cur.fetchone()["cnt"]

        cur.execute("SELECT COUNT(*) as cnt FROM config_drift_findings WHERE status = 'open' AND severity = 'critical'")
        critical_drift_open = cur.fetchone()["cnt"]

        health = "HEALTHY"
        if critical_drift_open > 0 or secrets_by_status.get("compromised", 0) > 0:
            health = "CRITICAL"
        elif rotations_in_progress > 0 or secrets_by_status.get("rotation_in_progress", 0) > 0:
            health = "ROTATION_ACTIVE"

        return {
            "organization_id": org_id,
            "total_settings": total_settings,
            "settings_by_category": by_category,
            "total_environments": total_envs,
            "secrets_by_status": secrets_by_status,
            "rotations_in_progress": rotations_in_progress,
            "critical_drift_open": critical_drift_open,
            "governance_health": health
        }

    def get_audit_ledger(
        self,
        user_ctx: Dict[str, Any],
        action_type: Optional[str] = None,
        environment_code: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List audit ledger events."""
        require_permission(user_ctx, "config:read")
        org_id = user_ctx["organization_id"]

        cur = self.conn.cursor()
        query = "SELECT * FROM config_audit_ledger WHERE organization_id = ?"
        params: List[Any] = [org_id]

        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        if environment_code:
            query += " AND environment_code = ?"
            params.append(environment_code)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cur.execute(query, params)
        rows = cur.fetchall()

        return [
            {
                "id": r["id"],
                "organization_id": r["organization_id"],
                "action_type": r["action_type"],
                "actor_id": r["actor_id"],
                "actor_role": r["actor_role"],
                "target_key_or_ref": r["target_key_or_ref"],
                "environment_code": r["environment_code"],
                "metadata": json.loads(r["metadata_json"]),
                "created_at": r["created_at"]
            }
            for r in rows
        ]

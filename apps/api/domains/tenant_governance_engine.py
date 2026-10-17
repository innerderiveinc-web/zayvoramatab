"""Domain Engine for Enterprise Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance.

Phase 55 of ZAYVORA MATAB OS.
Enforces fail-closed multi-tenancy, idempotent provisioning, governed lifecycle state transitions,
cross-tenant relationship shielding, offboarding dry-runs, time-bounded break-glass support access,
plan entitlements, and tamper-evident SHA-256 audit chaining.
"""

import hashlib
import json
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
)
from apps.api.core.security import hash_password


class TenantGovernanceEngine:
    VALID_LIFECYCLE_STATUSES = {
        "PROVISIONING",
        "ACTIVE",
        "SUSPENDED",
        "OFFBOARDING",
        "DECOMMISSIONED",
    }

    VALID_TRANSITIONS = {
        "PROVISIONING": {"ACTIVE", "DECOMMISSIONED"},
        "ACTIVE": {"SUSPENDED", "OFFBOARDING"},
        "SUSPENDED": {"ACTIVE", "OFFBOARDING"},
        "OFFBOARDING": {"DECOMMISSIONED", "ACTIVE"},
        "DECOMMISSIONED": set(),
    }

    VALID_REASON_CODES = {
        "EMERGENCY_CLINICAL_INVESTIGATION",
        "SYSTEM_OUTAGE_REMEDIATION",
        "REGULATORY_COMPLIANCE_AUDIT",
        "CUSTOMER_REQUESTED_SUPPORT",
    }

    VALID_PLAN_TIERS = {"STARTER", "PROFESSIONAL", "ENTERPRISE", "CUSTOM"}

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    # -------------------------------------------------------------------------
    # 1. Idempotent Tenant Provisioning
    # -------------------------------------------------------------------------

    def provision_tenant(self, data: Dict[str, Any], actor_id: str = "SYSTEM") -> Dict[str, Any]:
        """Idempotently provision a new tenant with primary facility, admin, and baseline entitlements."""
        name = data.get("name", "").strip()
        if not name:
            raise ValidationError("Organization/Tenant name is required.")

        code = data.get("code", "").strip().upper()
        if not code:
            # Generate deterministic slug from name
            code = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:16]

        idempotency_key = data.get("idempotency_key") or data.get("provisioning_idempotency_key")
        cursor = self.conn.cursor()

        # Idempotency check
        if idempotency_key:
            cursor.execute(
                "SELECT tenant_id FROM saas_tenant_lifecycle WHERE provisioning_idempotency_key = ?",
                (idempotency_key,),
            )
            existing = cursor.fetchone()
            if existing:
                return self.get_tenant(existing["tenant_id"])

        # Check code uniqueness
        cursor.execute("SELECT id FROM organizations WHERE code = ?", (code,))
        code_row = cursor.fetchone()
        if code_row:
            if idempotency_key:
                return self.get_tenant(code_row["id"])
            raise ConflictError(f"Organization code '{code}' already exists.")

        tenant_id = data.get("tenant_id") or f"ORG-{uuid.uuid4().hex[:8].upper()}"
        license_num = data.get("license_number")
        profile_type = data.get("profile_type", "MATAB")
        plan_tier = data.get("plan_tier", "PROFESSIONAL")
        if plan_tier not in self.VALID_PLAN_TIERS:
            raise ValidationError(f"Invalid plan tier '{plan_tier}'. Must be one of {sorted(self.VALID_PLAN_TIERS)}")

        now = datetime.now(timezone.utc).isoformat()

        # 1. Insert organizations
        cursor.execute(
            """
            INSERT INTO organizations (id, name, code, license_number, profile_type, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (tenant_id, name, code, license_num, profile_type, now, now),
        )

        # 2. Insert primary facility
        primary_facility_id = f"FAC-{uuid.uuid4().hex[:8].upper()}"
        fac_name = data.get("facility_name") or f"{name} Main Matab"
        fac_code = f"{code}-MAIN"[:20]
        cursor.execute(
            """
            INSERT INTO facilities (id, organization_id, name, code, address, phone, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (primary_facility_id, tenant_id, fac_name, fac_code, data.get("address"), data.get("phone"), now, now),
        )

        # 3. Create initial admin user if supplied
        admin_user_id = None
        admin_username = data.get("admin_username")
        admin_email = data.get("admin_email")
        admin_password = data.get("admin_password") or "MatabTemp@123"
        admin_name = data.get("admin_full_name", f"{name} Administrator")

        if admin_username:
            cursor.execute("SELECT id FROM users WHERE username = ?", (admin_username,))
            if cursor.fetchone():
                admin_username = f"{admin_username}-{uuid.uuid4().hex[:4]}"

            admin_user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
            pwd_hash = hash_password(admin_password)
            cursor.execute(
                """
                INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (admin_user_id, tenant_id, admin_username, admin_email, pwd_hash, admin_name, now, now),
            )

            # Assign ORG_ADMIN role if role exists
            cursor.execute("SELECT id FROM roles WHERE code = 'ORG_ADMIN'")
            role_row = cursor.fetchone()
            if role_row:
                cursor.execute(
                    """
                    INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active, created_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (f"UOM-{uuid.uuid4().hex[:8].upper()}", admin_user_id, tenant_id, role_row["id"], now),
                )

        # 4. Insert saas_tenant_lifecycle
        cursor.execute(
            """
            INSERT INTO saas_tenant_lifecycle (
                tenant_id, status, status_reason, provisioning_idempotency_key, provisioned_by,
                activated_at, created_at, updated_at
            ) VALUES (?, 'ACTIVE', 'Initial automated provisioning', ?, ?, ?, ?, ?)
            """,
            (tenant_id, idempotency_key, actor_id, now, now, now),
        )

        # 5. Insert saas_tenant_entitlements
        max_practitioners = int(data.get("max_active_practitioners", 10))
        max_facs = int(data.get("max_facilities", 5))
        max_storage = int(data.get("max_storage_mb", 5000))
        rate_limit = int(data.get("api_rate_limit_rpm", 120))
        cursor.execute(
            """
            INSERT INTO saas_tenant_entitlements (
                tenant_id, plan_tier, max_active_practitioners, max_facilities,
                max_storage_mb, api_rate_limit_rpm, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (tenant_id, plan_tier, max_practitioners, max_facs, max_storage, rate_limit, now, now),
        )
        self.conn.commit()

        # Audit event
        self._record_governance_event(
            tenant_id=tenant_id,
            event_type="TENANT_PROVISIONED",
            actor_id=actor_id,
            target_id=tenant_id,
            payload={
                "name": name,
                "code": code,
                "primary_facility_id": primary_facility_id,
                "admin_user_id": admin_user_id,
                "plan_tier": plan_tier,
            },
        )

        return self.get_tenant(tenant_id)

    def get_tenant(self, tenant_id: str) -> Dict[str, Any]:
        """Fetch full tenant profile, primary facility, lifecycle state, and plan entitlements."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT o.id, o.name, o.code, o.license_number, o.profile_type, o.is_active, o.created_at,
                   l.status as lifecycle_status, l.status_reason, l.activated_at, l.suspended_at, l.offboarded_at,
                   e.plan_tier, e.max_active_practitioners, e.max_facilities, e.max_storage_mb, e.api_rate_limit_rpm,
                   e.features_enabled_json
            FROM organizations o
            LEFT JOIN saas_tenant_lifecycle l ON o.id = l.tenant_id
            LEFT JOIN saas_tenant_entitlements e ON o.id = e.tenant_id
            WHERE o.id = ?
            """,
            (tenant_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Tenant '{tenant_id}' not found.")

        # Facilities count
        cursor.execute("SELECT COUNT(*) FROM facilities WHERE organization_id = ? AND is_active = 1", (tenant_id,))
        fac_count = cursor.fetchone()[0]

        # Active users count
        cursor.execute("SELECT COUNT(*) FROM users WHERE organization_id = ? AND is_active = 1", (tenant_id,))
        user_count = cursor.fetchone()[0]

        features = []
        if row["features_enabled_json"]:
            try:
                features = json.loads(row["features_enabled_json"])
            except Exception:
                features = []

        return {
            "tenant_id": row["id"],
            "name": row["name"],
            "code": row["code"],
            "license_number": row["license_number"],
            "profile_type": row["profile_type"],
            "is_active": bool(row["is_active"]),
            "lifecycle_status": row["lifecycle_status"] or ("ACTIVE" if row["is_active"] else "SUSPENDED"),
            "status_reason": row["status_reason"],
            "activated_at": row["activated_at"],
            "suspended_at": row["suspended_at"],
            "offboarded_at": row["offboarded_at"],
            "entitlements": {
                "plan_tier": row["plan_tier"] or "PROFESSIONAL",
                "max_active_practitioners": row["max_active_practitioners"] or 10,
                "max_facilities": row["max_facilities"] or 5,
                "max_storage_mb": row["max_storage_mb"] or 5000,
                "api_rate_limit_rpm": row["api_rate_limit_rpm"] or 120,
                "features_enabled": features,
            },
            "active_facilities_count": fac_count,
            "active_users_count": user_count,
            "created_at": row["created_at"],
        }

    def list_tenants(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List tenants with optional lifecycle status filter."""
        cursor = self.conn.cursor()
        query = (
            "SELECT o.id, o.name, o.code, o.profile_type, o.is_active, o.created_at, "
            "l.status as lifecycle_status, e.plan_tier "
            "FROM organizations o "
            "LEFT JOIN saas_tenant_lifecycle l ON o.id = l.tenant_id "
            "LEFT JOIN saas_tenant_entitlements e ON o.id = e.tenant_id "
        )
        params: List[Any] = []
        if status:
            query += "WHERE l.status = ? "
            params.append(status)
        query += "ORDER BY o.created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "tenant_id": r["id"],
                "name": r["name"],
                "code": r["code"],
                "profile_type": r["profile_type"],
                "is_active": bool(r["is_active"]),
                "lifecycle_status": r["lifecycle_status"] or ("ACTIVE" if r["is_active"] else "SUSPENDED"),
                "plan_tier": r["plan_tier"] or "PROFESSIONAL",
                "created_at": r["created_at"],
            })
        return result

    # -------------------------------------------------------------------------
    # 2. Lifecycle State Transitions
    # -------------------------------------------------------------------------

    def transition_tenant_status(
        self, tenant_id: str, new_status: str, reason: str, actor_id: str = "SYSTEM"
    ) -> Dict[str, Any]:
        """Execute validated state transition on tenant lifecycle."""
        tenant = self.get_tenant(tenant_id)
        current_status = tenant["lifecycle_status"]

        if new_status not in self.VALID_LIFECYCLE_STATUSES:
            raise ValidationError(
                f"Invalid lifecycle status '{new_status}'. Must be one of {sorted(self.VALID_LIFECYCLE_STATUSES)}"
            )

        if current_status == new_status:
            return tenant

        allowed = self.VALID_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Illegal transition from '{current_status}' to '{new_status}'. Allowed: {sorted(allowed)}"
            )

        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()

        # Update lifecycle
        cursor.execute(
            """
            INSERT INTO saas_tenant_lifecycle (tenant_id, status, previous_status, status_reason, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id) DO UPDATE SET
                previous_status = excluded.previous_status,
                status = excluded.status,
                status_reason = excluded.status_reason,
                activated_at = CASE WHEN excluded.status = 'ACTIVE' THEN ? ELSE activated_at END,
                suspended_at = CASE WHEN excluded.status = 'SUSPENDED' THEN ? ELSE suspended_at END,
                offboarded_at = CASE WHEN excluded.status = 'OFFBOARDING' THEN ? ELSE offboarded_at END,
                updated_at = ?
            """,
            (tenant_id, new_status, current_status, reason, now, now, now, now, now, now),
        )

        # Mirror to organizations.is_active
        is_active = 1 if new_status == "ACTIVE" else 0
        cursor.execute("UPDATE organizations SET is_active = ?, updated_at = ? WHERE id = ?", (is_active, now, tenant_id))

        # If suspended or decommissioned, terminate active user sessions immediately
        if new_status in ("SUSPENDED", "DECOMMISSIONED"):
            cursor.execute("DELETE FROM sessions WHERE organization_id = ?", (tenant_id,))

        self.conn.commit()

        # Audit
        self._record_governance_event(
            tenant_id=tenant_id,
            event_type="LIFECYCLE_TRANSITION",
            actor_id=actor_id,
            target_id=tenant_id,
            payload={
                "from_status": current_status,
                "to_status": new_status,
                "reason": reason,
            },
        )

        return self.get_tenant(tenant_id)

    # -------------------------------------------------------------------------
    # 3. Cross-Tenant Relationship & IDOR Shielding
    # -------------------------------------------------------------------------

    def validate_entity_ownership(self, tenant_id: str, entity_type: str, entity_id: str) -> bool:
        """Verify that a target resource belongs strictly to the requesting tenant."""
        cursor = self.conn.cursor()
        table_map = {
            "patient": ("patients", "organization_id"),
            "encounter": ("encounters", "organization_id"),
            "prescription": ("prescriptions", "organization_id"),
            "facility": ("facilities", "organization_id"),
            "user": ("users", "organization_id"),
            "appointment": ("appointments", "organization_id"),
            "care_plan": ("care_plans", "organization_id"),
        }

        if entity_type not in table_map:
            raise ValidationError(f"Unknown entity type '{entity_type}'.")

        table, col = table_map[entity_type]
        cursor.execute(f"SELECT {col} FROM {table} WHERE id = ?", (entity_id,))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"{entity_type.capitalize()} '{entity_id}' not found.")

        owner_org = row[col]
        if owner_org != tenant_id:
            raise ForbiddenError(
                f"Cross-tenant access violation: {entity_type} '{entity_id}' does not belong to your organization.",
                details={"code": "CROSS_TENANT_ACCESS_DENIED", "entity_type": entity_type, "entity_id": entity_id},
            )
        return True

    def validate_cross_tenant_relationship(
        self, tenant_id: str, parent_type: str, parent_id: str, child_type: str, child_id: str
    ) -> bool:
        """Enforce that parent and child entities in a relationship both belong to the same tenant."""
        self.validate_entity_ownership(tenant_id, parent_type, parent_id)
        self.validate_entity_ownership(tenant_id, child_type, child_id)
        return True

    # -------------------------------------------------------------------------
    # 4. Offboarding Dry-Run & Tenant-Scoped Export
    # -------------------------------------------------------------------------

    def get_offboarding_impact_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Calculate counts of all tenant-scoped data and detect active clinical blockers."""
        tenant = self.get_tenant(tenant_id)
        cursor = self.conn.cursor()

        counts = {}
        for entity, tbl in [
            ("patients", "patients"),
            ("encounters", "encounters"),
            ("prescriptions", "prescriptions"),
            ("facilities", "facilities"),
            ("users", "users"),
            ("care_plans", "care_plans"),
            ("appointments", "appointments"),
            ("invoices", "billing_invoices"),
            ("audit_events", "audit_events"),
        ]:
            try:
                col = "organization_id"
                cursor.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {col} = ?", (tenant_id,))
                counts[entity] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                counts[entity] = 0

        # Check for open/active clinical encounters
        open_encounters = 0
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM encounters WHERE organization_id = ? AND status IN ('IN_PROGRESS', 'DRAFT', 'SCHEDULED')",
                (tenant_id,),
            )
            open_encounters = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            pass

        can_decommission = open_encounters == 0
        blockers = []
        if open_encounters > 0:
            blockers.append(f"{open_encounters} active or draft clinical encounters must be signed or discharged first.")

        return {
            "tenant_id": tenant_id,
            "tenant_name": tenant["name"],
            "current_status": tenant["lifecycle_status"],
            "data_summary": counts,
            "open_clinical_encounters": open_encounters,
            "can_decommission": can_decommission,
            "blockers": blockers,
        }

    @staticmethod
    def _sanitize_cell(val: Any) -> Any:
        """Mitigate CSV formula injection on text fields starting with =, +, -, @, tab, or carriage return."""
        if isinstance(val, str) and val.strip().startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{val}"
        return val

    def export_tenant_data(self, tenant_id: str, actor_id: str = "SYSTEM") -> Dict[str, Any]:
        """Export complete tenant clinical and operational data in sanitized format."""
        self.get_tenant(tenant_id)  # validate exists
        cursor = self.conn.cursor()

        export_bundle: Dict[str, Any] = {
            "export_id": f"EXP-{uuid.uuid4().hex[:8].upper()}",
            "tenant_id": tenant_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by": actor_id,
        }

        # Gather data
        for key, tbl in [
            ("patients", "patients"),
            ("encounters", "encounters"),
            ("prescriptions", "prescriptions"),
            ("facilities", "facilities"),
            ("care_plans", "care_plans"),
            ("appointments", "appointments"),
        ]:
            try:
                cursor.execute(f"SELECT * FROM {tbl} WHERE organization_id = ?", (tenant_id,))
                rows = cursor.fetchall()
                sanitized_rows = []
                for r in rows:
                    row_dict = dict(r)
                    sanitized = {k: self._sanitize_cell(v) for k, v in row_dict.items()}
                    sanitized_rows.append(sanitized)
                export_bundle[key] = sanitized_rows
            except sqlite3.OperationalError:
                export_bundle[key] = []

        self._record_governance_event(
            tenant_id=tenant_id,
            event_type="TENANT_EXPORTED",
            actor_id=actor_id,
            target_id=export_bundle["export_id"],
            payload={
                "patient_count": len(export_bundle["patients"]),
                "encounter_count": len(export_bundle["encounters"]),
                "prescription_count": len(export_bundle["prescriptions"]),
            },
        )

        return export_bundle

    # -------------------------------------------------------------------------
    # 5. Break-Glass Support Access
    # -------------------------------------------------------------------------

    def create_break_glass_ticket(
        self,
        target_tenant_id: str,
        support_user_id: str,
        reason_code: str,
        justification: str,
        duration_minutes: int = 30,
        approved_by: str = "SECURITY_OFFICER",
        actor_id: str = "SYSTEM",
    ) -> Dict[str, Any]:
        """Issue time-bounded, reason-coded support break-glass session."""
        self.get_tenant(target_tenant_id)  # validate target exists

        if reason_code not in self.VALID_REASON_CODES:
            raise ValidationError(
                f"Invalid reason code '{reason_code}'. Must be one of {sorted(self.VALID_REASON_CODES)}"
            )

        justification = justification.strip()
        if len(justification) < 15:
            raise ValidationError("Detailed operational justification (min 15 chars) is mandatory for break-glass.")

        if duration_minutes <= 0 or duration_minutes > 60:
            raise ValidationError("Break-glass duration must be between 1 and 60 minutes.")

        ticket_id = f"BGT-{uuid.uuid4().hex[:8].upper()}"
        session_token = f"bg_{secrets.token_hex(24)}"
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(minutes=duration_minutes)).isoformat()
        now_iso = now.isoformat()

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO saas_break_glass_tickets (
                ticket_id, target_tenant_id, support_user_id, reason_code, justification,
                duration_minutes, status, approved_by, session_token, started_at, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                target_tenant_id,
                support_user_id,
                reason_code,
                justification,
                duration_minutes,
                approved_by,
                session_token,
                now_iso,
                expires_at,
                now_iso,
            ),
        )
        self.conn.commit()

        self._record_governance_event(
            tenant_id=target_tenant_id,
            event_type="BREAK_GLASS_GRANTED",
            actor_id=actor_id,
            target_id=ticket_id,
            payload={
                "support_user_id": support_user_id,
                "reason_code": reason_code,
                "duration_minutes": duration_minutes,
                "expires_at": expires_at,
            },
        )

        return {
            "ticket_id": ticket_id,
            "target_tenant_id": target_tenant_id,
            "support_user_id": support_user_id,
            "reason_code": reason_code,
            "duration_minutes": duration_minutes,
            "status": "ACTIVE",
            "session_token": session_token,
            "started_at": now_iso,
            "expires_at": expires_at,
        }

    def revoke_break_glass_ticket(self, ticket_id: str, reason: str = "Admin revocation", actor_id: str = "SYSTEM") -> Dict[str, Any]:
        """Revoke active break-glass ticket immediately."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM saas_break_glass_tickets WHERE ticket_id = ?", (ticket_id,))
        row = cursor.fetchone()
        if not row:
            raise NotFoundError(f"Break-glass ticket '{ticket_id}' not found.")

        now = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            "UPDATE saas_break_glass_tickets SET status = 'REVOKED', revoked_at = ?, revoked_reason = ? WHERE ticket_id = ?",
            (now, reason, ticket_id),
        )
        self.conn.commit()

        self._record_governance_event(
            tenant_id=row["target_tenant_id"],
            event_type="BREAK_GLASS_REVOKED",
            actor_id=actor_id,
            target_id=ticket_id,
            payload={"reason": reason},
        )

        return {"ticket_id": ticket_id, "status": "REVOKED", "revoked_at": now}

    def list_break_glass_tickets(self, target_tenant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List break-glass tickets, checking and updating expired sessions."""
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()

        # Auto-expire tickets past expiration
        cursor.execute(
            "UPDATE saas_break_glass_tickets SET status = 'EXPIRED' WHERE status = 'ACTIVE' AND expires_at < ?",
            (now_iso,),
        )
        self.conn.commit()

        query = (
            "SELECT ticket_id, target_tenant_id, support_user_id, reason_code, justification, "
            "duration_minutes, status, approved_by, started_at, expires_at, revoked_at "
            "FROM saas_break_glass_tickets "
        )
        params: List[Any] = []
        if target_tenant_id:
            query += "WHERE target_tenant_id = ? "
            params.append(target_tenant_id)
        query += "ORDER BY started_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    # -------------------------------------------------------------------------
    # 6. SaaS Entitlements & Quotas
    # -------------------------------------------------------------------------

    def update_entitlements(self, tenant_id: str, data: Dict[str, Any], actor_id: str = "SYSTEM") -> Dict[str, Any]:
        """Update tenant plan tier and resource quotas."""
        self.get_tenant(tenant_id)
        plan_tier = data.get("plan_tier")
        if plan_tier and plan_tier not in self.VALID_PLAN_TIERS:
            raise ValidationError(f"Invalid plan tier '{plan_tier}'.")

        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.cursor()

        features_json = None
        if "features_enabled" in data:
            features_json = json.dumps(data["features_enabled"])

        cursor.execute(
            """
            UPDATE saas_tenant_entitlements SET
                plan_tier = COALESCE(?, plan_tier),
                max_active_practitioners = COALESCE(?, max_active_practitioners),
                max_facilities = COALESCE(?, max_facilities),
                max_storage_mb = COALESCE(?, max_storage_mb),
                api_rate_limit_rpm = COALESCE(?, api_rate_limit_rpm),
                features_enabled_json = COALESCE(?, features_enabled_json),
                updated_at = ?
            WHERE tenant_id = ?
            """,
            (
                plan_tier,
                data.get("max_active_practitioners"),
                data.get("max_facilities"),
                data.get("max_storage_mb"),
                data.get("api_rate_limit_rpm"),
                features_json,
                now,
                tenant_id,
            ),
        )
        self.conn.commit()

        self._record_governance_event(
            tenant_id=tenant_id,
            event_type="ENTITLEMENTS_UPDATED",
            actor_id=actor_id,
            target_id=tenant_id,
            payload=data,
        )

        return self.get_tenant(tenant_id)["entitlements"]

    def check_quota(self, tenant_id: str, resource_type: str) -> Dict[str, Any]:
        """Verify whether tenant is within plan quota limits."""
        tenant = self.get_tenant(tenant_id)
        ent = tenant["entitlements"]

        if resource_type == "facilities":
            current = tenant["active_facilities_count"]
            limit = ent["max_facilities"]
        elif resource_type == "practitioners":
            current = tenant["active_users_count"]
            limit = ent["max_active_practitioners"]
        else:
            raise ValidationError(f"Unknown quota resource '{resource_type}'.")

        exceeded = current >= limit
        return {
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "current_usage": current,
            "quota_limit": limit,
            "quota_exceeded": exceeded,
            "remaining": max(0, limit - current),
        }

    # -------------------------------------------------------------------------
    # 7. Cryptographic SHA-256 Chained Governance Ledger
    # -------------------------------------------------------------------------

    def _record_governance_event(
        self,
        tenant_id: str,
        event_type: str,
        actor_id: str,
        target_id: str,
        payload: Dict[str, Any],
    ) -> str:
        """Append an immutable SHA-256 block to saas_governance_audit_ledger."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT ledger_id, sequence_number, record_hash FROM saas_governance_audit_ledger ORDER BY sequence_number DESC LIMIT 1"
        )
        last_block = cursor.fetchone()

        if last_block:
            prev_seq = last_block["sequence_number"]
            prev_hash = last_block["record_hash"]
            seq = prev_seq + 1
        else:
            prev_hash = "0" * 64
            seq = 1

        ledger_id = f"SGL-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc).isoformat()
        payload_str = json.dumps(payload, sort_keys=True)

        raw_content = f"{prev_hash}|{ledger_id}|{event_type}|{payload_str}|{now}"
        record_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()

        cursor.execute(
            """
            INSERT INTO saas_governance_audit_ledger (
                ledger_id, sequence_number, tenant_id, event_type, actor_id,
                target_id, payload_json, prev_hash, record_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ledger_id,
                seq,
                tenant_id,
                event_type,
                actor_id,
                target_id,
                payload_str,
                prev_hash,
                record_hash,
                now,
            ),
        )
        self.conn.commit()
        return ledger_id

    def verify_audit_ledger_integrity(self) -> Dict[str, Any]:
        """Verify unbroken cryptographic SHA-256 chain of saas_governance_audit_ledger."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ledger_id, sequence_number, prev_hash, record_hash, event_type, payload_json, created_at
            FROM saas_governance_audit_ledger ORDER BY sequence_number ASC
            """
        )
        rows = cursor.fetchall()

        if not rows:
            return {"verified": True, "blocks_checked": 0, "status": "EMPTY_LEDGER"}

        expected_prev = "0" * 64

        for i in range(len(rows)):
            row = rows[i]
            ledger_id, seq, declared_prev, declared_hash, event_type, payload_str, created_at = (
                row["ledger_id"],
                row["sequence_number"],
                row["prev_hash"],
                row["record_hash"],
                row["event_type"],
                row["payload_json"],
                row["created_at"],
            )

            if i == 0:
                if declared_prev != expected_prev:
                    return {
                        "verified": False,
                        "tamper_detected": True,
                        "failed_at_sequence": seq,
                        "reason": "Genesis block prev_hash invalid",
                    }
            else:
                if declared_prev != expected_prev:
                    return {
                        "verified": False,
                        "tamper_detected": True,
                        "failed_at_sequence": seq,
                        "reason": f"Hash chain broken at seq {seq}: declared {declared_prev[:12]} != expected {expected_prev[:12]}",
                    }

            raw_content = f"{declared_prev}|{ledger_id}|{event_type}|{payload_str}|{created_at}"
            computed_hash = hashlib.sha256(raw_content.encode("utf-8")).hexdigest()
            if computed_hash != declared_hash:
                return {
                    "verified": False,
                    "tamper_detected": True,
                    "failed_at_sequence": seq,
                    "reason": f"Record hash mismatch at seq {seq}: declared {declared_hash[:12]} != computed {computed_hash[:12]}",
                }
            expected_prev = declared_hash

        return {
            "verified": True,
            "blocks_checked": len(rows),
            "status": "CHAIN_INTEGRITY_VERIFIED",
            "genesis_block_id": rows[0]["ledger_id"],
            "latest_block_id": rows[-1]["ledger_id"],
        }

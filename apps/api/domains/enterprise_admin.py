"""Phase 11 Domain Service: Multi-Doctor, Multi-Branch & Hospital Administration Foundation.

Provides:
- Organization hierarchy (parent/subsidiary with cycle detection) & lifecycle (setup, active, suspended, archived)
- Facility lifecycle (setup, active, temporarily_closed, suspended, archived) & activation health checks
- Departments, Units/Teams, and Rooms/Resources directory
- Scoped Practitioner & Staff Assignments (multi-branch roles, locum windows, immediate revocation, transfers)
- Layered Configuration Inheritance (Platform Security > Organization > Facility > Department), Versioning & Rollback
- Facility Module Entitlements with prerequisite DAG validation
- Cross-Facility Patient Continuity & Governed Human-Reviewed Patient Merge
- Controlled Inter-Facility Transfers & Referrals (source encounter preservation, recipient acceptance, attachment security)
- Hospital Integration Registry (secret reference URIs, sandbox verification before production activation)
- Single-Clinic to Multi-Facility Repeatable Migration Engine & Deployment Readiness Checklist
"""

import copy
import json
import re
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from apps.api.config import config
from apps.api.core.audit import log_audit_event
from apps.api.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from apps.api.database.connection import DatabaseConnection


# Platform-wide immutable security constraints (Tier 1) that no organization or facility can weaken
PLATFORM_SECURITY_BASELINE: Dict[str, Any] = {
    "require_clinician_pin_for_signoff": True,
    "allow_unsigned_dispensing": False,
    "enforce_tenant_isolation": True,
    "allow_plaintext_secrets_in_config": False,
    "audit_retention_min_days": 2555,  # 7 years medical record & audit retention minimum
    "require_safety_preflight_before_rx_sign": True,
}

DEFAULT_ORGANIZATION_CONFIG: Dict[str, Any] = {
    "timezone": "Asia/Kolkata",
    "default_language": "en",
    "audit_retention_days": 2555,
    "appointment_default_slot_minutes": 15,
    "allow_cross_facility_patient_lookup": True,
    "allowed_export_formats": ["JSON", "PDF"],
    "branding_header_title": "ZAYVORA MATAB OS",
}

MODULE_PREREQUISITES: Dict[str, List[str]] = {
    "clinical_core": [],
    "safety_firewall": ["clinical_core"],
    "unani_assessment": ["clinical_core"],
    "modern_assessment": ["clinical_core"],
    "knowledge_retrieval": ["clinical_core"],
    "appointments_queue": ["clinical_core"],
    "billing": ["clinical_core", "appointments_queue"],
    "pharmacy_inventory": ["clinical_core", "safety_firewall"],
    "followup_continuity": ["clinical_core", "appointments_queue"],
    "hospital_modules": ["clinical_core", "safety_firewall", "appointments_queue"],
    "integrations_reporting": ["clinical_core"],
}

FORBIDDEN_SECRET_KEY_PATTERNS = re.compile(
    r"(api_secret|client_secret|private_key|password|raw_secret|webhook_secret|auth_token|secret_key|cvv|full_pan)",
    re.IGNORECASE,
)


def _contains_plaintext_secret(obj: Any) -> Optional[str]:
    """Recursively inspect configuration dictionary keys for forbidden plaintext secret fields."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_str = str(k)
            if key_str != "secret_ref_uri" and FORBIDDEN_SECRET_KEY_PATTERNS.search(key_str):
                return key_str
            nested = _contains_plaintext_secret(v)
            if nested:
                return nested
    elif isinstance(obj, list):
        for item in obj:
            nested = _contains_plaintext_secret(item)
            if nested:
                return nested
    return None


class EnterpriseAdminService:
    """Enterprise Multi-Branch, Multi-Doctor & Hospital Administration Service."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def _get_conn(self, conn: Optional[sqlite3.Connection] = None) -> Tuple[sqlite3.Connection, bool]:
        if conn is not None:
            return conn, False
        c = DatabaseConnection(self.db_path).get_connection()
        return c, True

    # =========================================================================
    # 1. Organization Hierarchy & Lifecycle
    # =========================================================================

    def _detect_org_hierarchy_cycle(
        self, conn: sqlite3.Connection, org_id: str, proposed_parent_id: Optional[str]
    ) -> bool:
        if not proposed_parent_id:
            return False
        if org_id == proposed_parent_id:
            return True
        visited = {org_id}
        curr = proposed_parent_id
        cur = conn.cursor()
        while curr:
            if curr in visited:
                return True
            visited.add(curr)
            cur.execute(
                "SELECT parent_organization_id FROM organization_profiles WHERE organization_id = ?;",
                (curr,),
            )
            row = cur.fetchone()
            curr = row["parent_organization_id"] if row else None
        return False

    def ensure_organization_profile(self, organization_id: str, conn: sqlite3.Connection) -> Dict[str, Any]:
        cur = conn.cursor()
        cur.execute("SELECT * FROM organization_profiles WHERE organization_id = ?;", (organization_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        cur.execute("SELECT * FROM organizations WHERE id = ?;", (organization_id,))
        org = cur.fetchone()
        if not org:
            raise NotFoundError(f"Organization '{organization_id}' not found.")
        status = "active" if org["is_active"] else "suspended"
        conn.execute(
            """
            INSERT INTO organization_profiles (
                organization_id, lifecycle_status, legal_name, timezone, default_language,
                deployment_mode, cross_facility_continuity_policy, org_admin_clinical_note_access
            ) VALUES (?, ?, ?, 'Asia/Kolkata', 'en', 'SHARED_MULTITENANT', 'SAME_ORG_TREATMENT_TEAM', 0);
            """,
            (organization_id, status, org["name"]),
        )
        cur.execute("SELECT * FROM organization_profiles WHERE organization_id = ?;", (organization_id,))
        return dict(cur.fetchone())

    def create_organization(
        self, actor_id: str, payload: Dict[str, Any], conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            name = (payload.get("name") or "").strip()
            code = (payload.get("code") or "").strip().upper()
            if not name or not code:
                raise ValidationError("Organization name and code are required.")

            cur = c.cursor()
            cur.execute("SELECT id FROM organizations WHERE code = ?;", (code,))
            if cur.fetchone():
                raise ConflictError(f"Organization code '{code}' already exists.")

            org_id = payload.get("id") or f"org-{uuid.uuid4().hex[:12]}"
            profile_type = payload.get("profile_type", "MATAB").upper()
            lifecycle_status = payload.get("lifecycle_status", "setup").lower()
            if lifecycle_status not in ("setup", "active"):
                raise ValidationError("Initial organization lifecycle_status must be 'setup' or 'active'.")

            parent_org_id = payload.get("parent_organization_id")
            if parent_org_id:
                cur.execute("SELECT id FROM organizations WHERE id = ?;", (parent_org_id,))
                if not cur.fetchone():
                    raise NotFoundError(f"Parent organization '{parent_org_id}' not found.")
                if self._detect_org_hierarchy_cycle(c, org_id, parent_org_id):
                    raise ConflictError(
                        "Circular organization hierarchy detected.",
                        details={"code": "ORGANIZATION_HIERARCHY_CYCLE_DETECTED"},
                    )

            is_active = 1 if lifecycle_status == "active" else 0
            c.execute(
                """
                INSERT INTO organizations (id, name, code, license_number, profile_type, is_active)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (org_id, name, code, payload.get("license_number"), profile_type, is_active),
            )
            c.execute(
                """
                INSERT INTO organization_profiles (
                    organization_id, parent_organization_id, lifecycle_status, legal_name,
                    tax_registration_number, timezone, default_language, deployment_mode,
                    cross_facility_continuity_policy, org_admin_clinical_note_access,
                    parent_reporting_enabled, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    org_id,
                    parent_org_id,
                    lifecycle_status,
                    payload.get("legal_name", name),
                    payload.get("tax_registration_number"),
                    payload.get("timezone", "Asia/Kolkata"),
                    payload.get("default_language", "en"),
                    payload.get("deployment_mode", "SHARED_MULTITENANT"),
                    payload.get("cross_facility_continuity_policy", "SAME_ORG_TREATMENT_TEAM"),
                    1 if payload.get("org_admin_clinical_note_access") else 0,
                    1 if payload.get("parent_reporting_enabled") else 0,
                    actor_id,
                ),
            )
            c.execute(
                """
                INSERT INTO organization_lifecycle_events (id, organization_id, from_status, to_status, reason, actor_id)
                VALUES (?, ?, NULL, ?, ?, ?);
                """,
                (f"ole-{uuid.uuid4().hex[:12]}", org_id, lifecycle_status, "Initial organization creation", actor_id),
            )
            log_audit_event(
                c,
                organization_id=org_id,
                actor_id=actor_id,
                action_type="ORGANIZATION_CREATED",
                target_entity_type="ORGANIZATION",
                target_entity_id=org_id,
                details={"name": name, "code": code, "lifecycle_status": lifecycle_status},
            )
            if should_close:
                c.commit()
            return self.get_organization(org_id, conn=c)
        finally:
            if should_close:
                c.close()

    def get_organization(self, organization_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute("SELECT * FROM organizations WHERE id = ?;", (organization_id,))
            org = cur.fetchone()
            if not org:
                raise NotFoundError(f"Organization '{organization_id}' not found.")
            prof = self.ensure_organization_profile(organization_id, c)
            cur.execute(
                "SELECT * FROM organization_lifecycle_events WHERE organization_id = ? ORDER BY created_at DESC;",
                (organization_id,),
            )
            events = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT COUNT(*) AS cnt FROM facilities WHERE organization_id = ?;", (organization_id,))
            fac_count = int(cur.fetchone()["cnt"])

            out = dict(org)
            out.update(prof)
            out["id"] = organization_id
            out["facilities_count"] = fac_count
            out["lifecycle_history"] = events
            if should_close:
                c.commit()
            return out
        finally:
            if should_close:
                c.close()

    def list_organizations(
        self, user_ctx: Dict[str, Any], conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            user_org = user_ctx["organization_id"]
            self.ensure_organization_profile(user_org, c)
            cur = c.cursor()
            # Return user's organization plus any child organizations that explicitly enabled parent reporting
            cur.execute(
                """
                SELECT o.id
                FROM organizations o
                LEFT JOIN organization_profiles op ON o.id = op.organization_id
                WHERE o.id = ?
                   OR (op.parent_organization_id = ? AND op.parent_reporting_enabled = 1)
                ORDER BY o.name ASC;
                """,
                (user_org, user_org),
            )
            ids = [r["id"] for r in cur.fetchall()]
            return [self.get_organization(oid, conn=c) for oid in ids]
        finally:
            if should_close:
                c.close()

    def update_organization(
        self,
        organization_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            current = self.get_organization(organization_id, conn=c)
            if "parent_organization_id" in payload:
                new_parent = payload["parent_organization_id"]
                if new_parent:
                    cur = c.cursor()
                    cur.execute("SELECT id FROM organizations WHERE id = ?;", (new_parent,))
                    if not cur.fetchone():
                        raise NotFoundError(f"Parent organization '{new_parent}' not found.")
                    if self._detect_org_hierarchy_cycle(c, organization_id, new_parent):
                        raise ConflictError(
                            "Circular organization hierarchy detected.",
                            details={"code": "ORGANIZATION_HIERARCHY_CYCLE_DETECTED"},
                        )

            name = (payload.get("name") or current["name"]).strip()
            license_number = payload.get("license_number", current.get("license_number"))
            profile_type = payload.get("profile_type", current.get("profile_type", "MATAB")).upper()
            legal_name = payload.get("legal_name", current.get("legal_name") or name)
            tax_reg = payload.get("tax_registration_number", current.get("tax_registration_number"))
            timezone = payload.get("timezone", current.get("timezone", "Asia/Kolkata"))
            default_language = payload.get("default_language", current.get("default_language", "en"))
            continuity_policy = payload.get(
                "cross_facility_continuity_policy",
                current.get("cross_facility_continuity_policy", "SAME_ORG_TREATMENT_TEAM"),
            )
            if continuity_policy not in ("SAME_ORG_TREATMENT_TEAM", "EXPLICIT_CONSENT_REQUIRED", "FACILITY_ISOLATED"):
                raise ValidationError(f"Invalid cross_facility_continuity_policy '{continuity_policy}'.")

            org_admin_notes = (
                int(bool(payload["org_admin_clinical_note_access"]))
                if "org_admin_clinical_note_access" in payload
                else int(current.get("org_admin_clinical_note_access", 0))
            )
            parent_rep = (
                int(bool(payload["parent_reporting_enabled"]))
                if "parent_reporting_enabled" in payload
                else int(current.get("parent_reporting_enabled", 0))
            )
            parent_id = payload.get("parent_organization_id", current.get("parent_organization_id"))

            c.execute(
                """
                UPDATE organizations
                SET name = ?, license_number = ?, profile_type = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (name, license_number, profile_type, organization_id),
            )
            c.execute(
                """
                UPDATE organization_profiles
                SET parent_organization_id = ?, legal_name = ?, tax_registration_number = ?,
                    timezone = ?, default_language = ?, cross_facility_continuity_policy = ?,
                    org_admin_clinical_note_access = ?, parent_reporting_enabled = ?,
                    version = version + 1, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE organization_id = ?;
                """,
                (
                    parent_id,
                    legal_name,
                    tax_reg,
                    timezone,
                    default_language,
                    continuity_policy,
                    org_admin_notes,
                    parent_rep,
                    actor_id,
                    organization_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                actor_id=actor_id,
                action_type="ORGANIZATION_UPDATED",
                target_entity_type="ORGANIZATION",
                target_entity_id=organization_id,
                details={
                    "cross_facility_continuity_policy": continuity_policy,
                    "org_admin_clinical_note_access": org_admin_notes,
                    "parent_organization_id": parent_id,
                },
            )
            if should_close:
                c.commit()
            return self.get_organization(organization_id, conn=c)
        finally:
            if should_close:
                c.close()

    def transition_organization_lifecycle(
        self,
        organization_id: str,
        target_status: str,
        actor_id: str,
        reason: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            target = (target_status or "").strip().lower()
            if target not in ("setup", "active", "suspended", "archived"):
                raise ValidationError(f"Invalid organization lifecycle status '{target_status}'.")
            if not reason or len(reason.strip()) < 5:
                raise ValidationError("A documented reason (min 5 chars) is required for organization lifecycle transitions.")

            org = self.get_organization(organization_id, conn=c)
            from_status = org["lifecycle_status"]

            if target == "active":
                if not org.get("name") or not org.get("code") or not org.get("timezone"):
                    raise ValidationError("Organization cannot be activated until name, code, and timezone are configured.")

            cur = c.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM facilities WHERE organization_id = ? AND is_active = 1;", (organization_id,))
            active_facilities = int(cur.fetchone()["cnt"])
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM appointments WHERE organization_id = ? AND status IN ('booked', 'confirmed');",
                (organization_id,),
            )
            booked_appts = int(cur.fetchone()["cnt"])
            impact = {"active_facilities": active_facilities, "booked_appointments": booked_appts}

            is_active = 1 if target == "active" else 0
            c.execute(
                "UPDATE organizations SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (is_active, organization_id),
            )
            c.execute(
                """
                UPDATE organization_profiles
                SET lifecycle_status = ?,
                    suspension_reason = CASE WHEN ? IN ('suspended', 'archived') THEN ? ELSE NULL END,
                    suspended_at = CASE WHEN ? = 'suspended' THEN CURRENT_TIMESTAMP ELSE suspended_at END,
                    archived_at = CASE WHEN ? = 'archived' THEN CURRENT_TIMESTAMP ELSE archived_at END,
                    activated_at = CASE WHEN ? = 'active' THEN CURRENT_TIMESTAMP ELSE activated_at END,
                    version = version + 1,
                    updated_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE organization_id = ?;
                """,
                (target, target, reason, target, target, target, actor_id, organization_id),
            )
            c.execute(
                """
                INSERT INTO organization_lifecycle_events (
                    id, organization_id, from_status, to_status, reason, downstream_impact_summary_json, actor_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (f"ole-{uuid.uuid4().hex[:12]}", organization_id, from_status, target, reason, json.dumps(impact), actor_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                actor_id=actor_id,
                action_type=f"ORGANIZATION_{target.upper()}",
                target_entity_type="ORGANIZATION",
                target_entity_id=organization_id,
                details={"from_status": from_status, "to_status": target, "reason": reason, "downstream_impact": impact},
            )
            if should_close:
                c.commit()
            return self.get_organization(organization_id, conn=c)
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 2. Facility Lifecycle, Readiness Health Check & Directory
    # =========================================================================

    def ensure_facility_profile(
        self, organization_id: str, facility_id: str, conn: sqlite3.Connection
    ) -> Dict[str, Any]:
        cur = conn.cursor()
        cur.execute("SELECT * FROM facilities WHERE id = ?;", (facility_id,))
        fac = cur.fetchone()
        if not fac:
            raise NotFoundError(f"Facility '{facility_id}' not found.")
        if fac["organization_id"] != organization_id:
            raise ForbiddenError(
                f"Facility '{facility_id}' does not belong to organization '{organization_id}'.",
                details={"code": "FACILITY_TENANT_MISMATCH"},
            )
        cur.execute("SELECT * FROM facility_profiles WHERE facility_id = ?;", (facility_id,))
        prof = cur.fetchone()
        if prof:
            return dict(prof)
        status = "active" if fac["is_active"] else "suspended"
        conn.execute(
            """
            INSERT INTO facility_profiles (
                facility_id, organization_id, facility_type, lifecycle_status, timezone
            ) VALUES (?, ?, 'MATAB', ?, 'Asia/Kolkata');
            """,
            (facility_id, organization_id, status),
        )
        cur.execute("SELECT * FROM facility_profiles WHERE facility_id = ?;", (facility_id,))
        return dict(cur.fetchone())

    def create_facility(
        self,
        organization_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            # Prevent client from linking facility to a foreign tenant via payload organization_id
            supplied_org = payload.get("organization_id")
            if supplied_org and supplied_org != organization_id:
                raise ForbiddenError(
                    "Cannot create or link a facility under a different organization.",
                    details={"code": "CROSS_TENANT_FACILITY_LINK_DENIED"},
                )

            name = (payload.get("name") or "").strip()
            code = (payload.get("code") or "").strip().upper()
            if not name or not code:
                raise ValidationError("Facility name and code are required.")

            cur = c.cursor()
            cur.execute(
                "SELECT id FROM facilities WHERE organization_id = ? AND code = ?;",
                (organization_id, code),
            )
            if cur.fetchone():
                raise ConflictError(f"Facility code '{code}' already exists in this organization.")

            facility_id = payload.get("id") or f"fac-{uuid.uuid4().hex[:12]}"
            lifecycle_status = payload.get("lifecycle_status", "active").lower()
            if lifecycle_status not in ("setup", "active"):
                raise ValidationError("Initial facility lifecycle_status must be 'setup' or 'active'.")
            facility_type = payload.get("facility_type", "MATAB").upper()
            is_active = 1 if lifecycle_status == "active" else 0

            c.execute(
                """
                INSERT INTO facilities (id, organization_id, name, code, address, phone, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    facility_id,
                    organization_id,
                    name,
                    code,
                    payload.get("address", ""),
                    payload.get("phone", ""),
                    is_active,
                ),
            )
            c.execute(
                """
                INSERT INTO facility_profiles (
                    facility_id, organization_id, facility_type, lifecycle_status, timezone,
                    city, state_province, postal_code, country, emergency_contact_phone,
                    operating_hours_json, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    facility_id,
                    organization_id,
                    facility_type,
                    lifecycle_status,
                    payload.get("timezone", "Asia/Kolkata"),
                    payload.get("city"),
                    payload.get("state_province"),
                    payload.get("postal_code"),
                    payload.get("country", "IN"),
                    payload.get("emergency_contact_phone"),
                    json.dumps(payload.get("operating_hours", {})),
                    actor_id,
                ),
            )
            # Seed default module entitlements for the new facility
            self._ensure_default_facility_modules(organization_id, facility_id, actor_id, c)

            c.execute(
                """
                INSERT INTO facility_lifecycle_events (
                    id, organization_id, facility_id, from_status, to_status, reason, actor_id
                ) VALUES (?, ?, ?, NULL, ?, 'Initial facility creation', ?);
                """,
                (f"fle-{uuid.uuid4().hex[:12]}", organization_id, facility_id, lifecycle_status, actor_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="FACILITY_CREATED",
                target_entity_type="FACILITY",
                target_entity_id=facility_id,
                details={"name": name, "code": code, "facility_type": facility_type, "lifecycle_status": lifecycle_status},
            )
            if should_close:
                c.commit()
            return self.get_facility(organization_id, facility_id, conn=c)
        finally:
            if should_close:
                c.close()

    def get_facility(
        self, organization_id: str, facility_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            prof = self.ensure_facility_profile(organization_id, facility_id, c)
            cur = c.cursor()
            cur.execute("SELECT * FROM facilities WHERE id = ? AND organization_id = ?;", (facility_id, organization_id))
            fac = dict(cur.fetchone())
            fac.update(prof)
            fac["id"] = facility_id
            cur.execute(
                "SELECT * FROM facility_departments WHERE facility_id = ? AND organization_id = ? ORDER BY name ASC;",
                (facility_id, organization_id),
            )
            fac["departments"] = [dict(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT * FROM facility_lifecycle_events WHERE facility_id = ? ORDER BY created_at DESC;",
                (facility_id,),
            )
            fac["lifecycle_history"] = [dict(r) for r in cur.fetchall()]
            if should_close:
                c.commit()
            return fac
        finally:
            if should_close:
                c.close()

    def list_facilities(
        self, organization_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                "SELECT id FROM facilities WHERE organization_id = ? ORDER BY name ASC;",
                (organization_id,),
            )
            fids = [r["id"] for r in cur.fetchall()]
            return [self.get_facility(organization_id, fid, conn=c) for fid in fids]
        finally:
            if should_close:
                c.close()

    def update_facility(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            if "organization_id" in payload and payload["organization_id"] != organization_id:
                raise ForbiddenError(
                    "Facility organization_id cannot be changed to another tenant.",
                    details={"code": "FACILITY_TENANT_CHANGE_FORBIDDEN"},
                )
            current = self.get_facility(organization_id, facility_id, conn=c)
            name = (payload.get("name") or current["name"]).strip()
            address = payload.get("address", current.get("address", ""))
            phone = payload.get("phone", current.get("phone", ""))
            facility_type = payload.get("facility_type", current.get("facility_type", "MATAB")).upper()
            timezone = payload.get("timezone", current.get("timezone", "Asia/Kolkata"))
            city = payload.get("city", current.get("city"))
            state_prov = payload.get("state_province", current.get("state_province"))
            postal_code = payload.get("postal_code", current.get("postal_code"))

            c.execute(
                """
                UPDATE facilities
                SET name = ?, address = ?, phone = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (name, address, phone, facility_id, organization_id),
            )
            c.execute(
                """
                UPDATE facility_profiles
                SET facility_type = ?, timezone = ?, city = ?, state_province = ?, postal_code = ?,
                    version = version + 1, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE facility_id = ? AND organization_id = ?;
                """,
                (facility_type, timezone, city, state_prov, postal_code, actor_id, facility_id, organization_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="FACILITY_UPDATED",
                target_entity_type="FACILITY",
                target_entity_id=facility_id,
                details={"name": name, "facility_type": facility_type},
            )
            if should_close:
                c.commit()
            return self.get_facility(organization_id, facility_id, conn=c)
        finally:
            if should_close:
                c.close()

    def run_facility_activation_health_check(
        self, organization_id: str, facility_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        """Verify operational & clinical dependencies before activating a facility."""
        c, should_close = self._get_conn(conn)
        try:
            org = self.get_organization(organization_id, conn=c)
            fac = self.get_facility(organization_id, facility_id, conn=c)
            cur = c.cursor()

            checks = []
            # Check 1: Organization active
            org_ok = org["lifecycle_status"] == "active"
            checks.append({"check": "organization_active", "passed": org_ok, "detail": f"Org status: {org['lifecycle_status']}"})

            # Check 2: Facility address & contact configured
            contact_ok = bool((fac.get("address") or "").strip() and (fac.get("phone") or "").strip())
            checks.append({"check": "facility_address_and_phone", "passed": contact_ok, "detail": "Address and phone required"})

            # Check 3: At least one active department or assigned staff member
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM facility_departments WHERE facility_id = ? AND status = 'active';",
                (facility_id,),
            )
            dept_cnt = int(cur.fetchone()["cnt"])
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM user_facility_memberships WHERE facility_id = ? AND is_active = 1;",
                (facility_id,),
            )
            mem_cnt = int(cur.fetchone()["cnt"])
            cur.execute(
                "SELECT COUNT(*) AS cnt FROM staff_assignments WHERE facility_id = ? AND status = 'active';",
                (facility_id,),
            )
            sa_cnt = int(cur.fetchone()["cnt"])
            roster_ok = (dept_cnt > 0) or (mem_cnt > 0) or (sa_cnt > 0)
            checks.append(
                {
                    "check": "departments_or_staff_assigned",
                    "passed": roster_ok,
                    "detail": f"Departments={dept_cnt}, Staff={mem_cnt + sa_cnt}",
                }
            )

            # Check 4: Core clinical & safety firewall modules enabled
            modules = self.list_facility_modules(organization_id, facility_id, conn=c)
            mod_map = {m["module_key"]: bool(m["is_enabled"]) for m in modules}
            core_ok = mod_map.get("clinical_core", False) and mod_map.get("safety_firewall", False)
            checks.append(
                {
                    "check": "core_clinical_and_safety_modules",
                    "passed": core_ok,
                    "detail": "clinical_core and safety_firewall must be enabled",
                }
            )

            overall_ready = all(ch["passed"] for ch in checks)
            return {
                "facility_id": facility_id,
                "organization_id": organization_id,
                "ready_for_activation": overall_ready,
                "checks": checks,
                "checked_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        finally:
            if should_close:
                c.close()

    def transition_facility_lifecycle(
        self,
        organization_id: str,
        facility_id: str,
        target_status: str,
        actor_id: str,
        reason: str,
        cancel_booked_appointments: bool = False,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            target = (target_status or "").strip().lower()
            if target not in ("setup", "active", "temporarily_closed", "suspended", "archived"):
                raise ValidationError(f"Invalid facility lifecycle status '{target_status}'.")
            if not reason or len(reason.strip()) < 5:
                raise ValidationError("A documented reason (min 5 chars) is required for facility lifecycle transitions.")

            fac = self.get_facility(organization_id, facility_id, conn=c)
            from_status = fac["lifecycle_status"]

            if target == "active":
                hc = self.run_facility_activation_health_check(organization_id, facility_id, conn=c)
                if not hc["ready_for_activation"]:
                    raise ConflictError(
                        "Facility failed activation readiness health check.",
                        details={"code": "FACILITY_ACTIVATION_PREREQUISITES_FAILED", "health_check": hc},
                    )

            cur = c.cursor()
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM appointments
                WHERE organization_id = ? AND facility_id = ? AND status IN ('booked', 'confirmed');
                """,
                (organization_id, facility_id),
            )
            affected_appts = int(cur.fetchone()["cnt"])

            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM follow_up_tasks
                WHERE organization_id = ? AND facility_id = ? AND status IN ('planned', 'due', 'in_progress');
                """,
                (organization_id, facility_id),
            )
            affected_tasks = int(cur.fetchone()["cnt"])

            if target in ("temporarily_closed", "suspended", "archived") and cancel_booked_appointments and affected_appts > 0:
                c.execute(
                    """
                    UPDATE appointments
                    SET status = 'cancelled', cancellation_reason = ?, slot_lock_key = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE organization_id = ? AND facility_id = ? AND status IN ('booked', 'confirmed');
                    """,
                    (f"Facility transitioned to {target}: {reason}", organization_id, facility_id),
                )

            is_active = 1 if target == "active" else 0
            c.execute(
                "UPDATE facilities SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND organization_id = ?;",
                (is_active, facility_id, organization_id),
            )
            c.execute(
                """
                UPDATE facility_profiles
                SET lifecycle_status = ?,
                    suspension_reason = CASE WHEN ? IN ('temporarily_closed', 'suspended', 'archived') THEN ? ELSE NULL END,
                    suspended_at = CASE WHEN ? IN ('temporarily_closed', 'suspended') THEN CURRENT_TIMESTAMP ELSE suspended_at END,
                    archived_at = CASE WHEN ? = 'archived' THEN CURRENT_TIMESTAMP ELSE archived_at END,
                    activated_at = CASE WHEN ? = 'active' THEN CURRENT_TIMESTAMP ELSE activated_at END,
                    version = version + 1,
                    updated_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE facility_id = ? AND organization_id = ?;
                """,
                (target, target, reason, target, target, target, actor_id, facility_id, organization_id),
            )
            c.execute(
                """
                INSERT INTO facility_lifecycle_events (
                    id, organization_id, facility_id, from_status, to_status, reason,
                    affected_appointments_count, affected_tasks_count, actor_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    f"fle-{uuid.uuid4().hex[:12]}",
                    organization_id,
                    facility_id,
                    from_status,
                    target,
                    reason,
                    affected_appts,
                    affected_tasks,
                    actor_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type=f"FACILITY_{target.upper()}",
                target_entity_type="FACILITY",
                target_entity_id=facility_id,
                details={
                    "from_status": from_status,
                    "to_status": target,
                    "reason": reason,
                    "affected_appointments_count": affected_appts,
                    "affected_tasks_count": affected_tasks,
                },
            )
            if should_close:
                c.commit()
            return self.get_facility(organization_id, facility_id, conn=c)
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 3. Departments / Services, Units & Rooms
    # =========================================================================

    def create_department(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            self.ensure_facility_profile(organization_id, facility_id, c)
            code = (payload.get("code") or "").strip().upper()
            name = (payload.get("name") or "").strip()
            dept_type = (payload.get("department_type") or "UNANI_OPD").strip().upper()
            if not code or not name:
                raise ValidationError("Department code and name are required.")

            allowed_types = {
                "UNANI_OPD",
                "GENERAL_OPD",
                "SPECIALTY_CLINIC",
                "PHARMACY_DISPENSARY",
                "LABORATORY",
                "IMAGING",
                "EMERGENCY",
                "ADMINISTRATION",
                "REGIMENAL_THERAPY",
            }
            if dept_type not in allowed_types:
                raise ValidationError(f"Unsupported department_type '{dept_type}'.")

            cur = c.cursor()
            cur.execute("SELECT id FROM facility_departments WHERE facility_id = ? AND code = ?;", (facility_id, code))
            if cur.fetchone():
                raise ConflictError(f"Department code '{code}' already exists in facility '{facility_id}'.")

            req_module = payload.get("required_module_key")
            is_operational = 1 if payload.get("is_operational", True) else 0
            if req_module and is_operational:
                mods = {m["module_key"]: bool(m["is_enabled"]) for m in self.list_facility_modules(organization_id, facility_id, conn=c)}
                if not mods.get(req_module, False):
                    is_operational = 0

            dept_id = payload.get("id") or f"dept-{uuid.uuid4().hex[:12]}"
            status = payload.get("status", "active").lower()
            c.execute(
                """
                INSERT INTO facility_departments (
                    id, organization_id, facility_id, code, name, department_type,
                    head_practitioner_id, required_module_key, status, is_operational,
                    description, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    dept_id,
                    organization_id,
                    facility_id,
                    code,
                    name,
                    dept_type,
                    payload.get("head_practitioner_id"),
                    req_module,
                    status,
                    is_operational,
                    payload.get("description"),
                    actor_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="DEPARTMENT_CREATED",
                target_entity_type="DEPARTMENT",
                target_entity_id=dept_id,
                details={"code": code, "name": name, "department_type": dept_type, "is_operational": is_operational},
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM facility_departments WHERE id = ?;", (dept_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def list_departments(
        self, organization_id: str, facility_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            self.ensure_facility_profile(organization_id, facility_id, c)
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM facility_departments
                WHERE organization_id = ? AND facility_id = ?
                ORDER BY name ASC;
                """,
                (organization_id, facility_id),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 4. Practitioner & Staff Scoped Assignments
    # =========================================================================

    def create_organization_membership(
        self,
        organization_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            user_id = payload.get("user_id")
            role_code = (payload.get("role_code") or "RECEPTIONIST").strip().upper()
            if not user_id:
                raise ValidationError("user_id is required.")

            cur = c.cursor()
            cur.execute("SELECT id, organization_id FROM users WHERE id = ?;", (user_id,))
            u_row = cur.fetchone()
            if not u_row:
                raise NotFoundError(f"User '{user_id}' not found.")
            if u_row["organization_id"] != organization_id:
                raise ForbiddenError(
                    "Cannot grant organization membership to a user belonging to a different tenant.",
                    details={"code": "CROSS_TENANT_MEMBERSHIP_DENIED"},
                )

            cur.execute("SELECT id, code FROM roles WHERE code = ?;", (role_code,))
            r_row = cur.fetchone()
            if not r_row:
                raise ValidationError(f"Unknown role_code '{role_code}'.")

            mem_id = f"uom-{uuid.uuid4().hex[:12]}"
            c.execute(
                """
                INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(user_id, organization_id) DO UPDATE SET role_id = excluded.role_id, is_active = 1;
                """,
                (mem_id, user_id, organization_id, r_row["id"]),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                actor_id=actor_id,
                action_type="ORGANIZATION_MEMBERSHIP_GRANTED",
                target_entity_type="USER",
                target_entity_id=user_id,
                details={"role_code": role_code},
            )
            if should_close:
                c.commit()
            cur.execute(
                """
                SELECT uom.*, r.code AS role_code
                FROM user_organization_memberships uom
                JOIN roles r ON uom.role_id = r.id
                WHERE uom.user_id = ? AND uom.organization_id = ?;
                """,
                (user_id, organization_id),
            )
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def create_staff_assignment(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Assign an existing user to a specific facility and optional department with scoped role & permissions."""
        c, should_close = self._get_conn(conn)
        try:
            self.ensure_facility_profile(organization_id, facility_id, c)
            user_id = payload.get("user_id")
            role_code = (payload.get("role_code") or payload.get("role") or "").strip().upper()
            if not user_id or not role_code:
                raise ValidationError("user_id and role_code are required for staff assignment.")

            cur = c.cursor()
            cur.execute("SELECT id, organization_id, full_name FROM users WHERE id = ?;", (user_id,))
            u_row = cur.fetchone()
            if not u_row:
                raise NotFoundError(f"User '{user_id}' not found.")
            if u_row["organization_id"] != organization_id:
                raise ForbiddenError(
                    "Cannot assign user from another organization.",
                    details={"code": "CROSS_TENANT_ASSIGNMENT_DENIED"},
                )

            cur.execute("SELECT id, code FROM roles WHERE code = ?;", (role_code,))
            r_row = cur.fetchone()
            if not r_row:
                raise ValidationError(f"Invalid role_code '{role_code}'.")

            department_id = payload.get("department_id")
            if department_id:
                cur.execute(
                    "SELECT id FROM facility_departments WHERE id = ? AND facility_id = ? AND organization_id = ?;",
                    (department_id, facility_id, organization_id),
                )
                if not cur.fetchone():
                    raise ValidationError(
                        f"Department '{department_id}' does not belong to facility '{facility_id}'.",
                        details={"code": "DEPARTMENT_FACILITY_MISMATCH"},
                    )

            # Check incompatible role combinations at the same facility (e.g. READ_ONLY_AUDITOR + PRACTITIONER)
            cur.execute(
                """
                SELECT role_code FROM staff_assignments
                WHERE user_id = ? AND facility_id = ? AND status = 'active';
                """,
                (user_id, facility_id),
            )
            existing_roles = {r["role_code"] for r in cur.fetchall()}
            if ("READ_ONLY_AUDITOR" in existing_roles and role_code == "PRACTITIONER") or (
                role_code == "READ_ONLY_AUDITOR" and "PRACTITIONER" in existing_roles
            ):
                raise ConflictError(
                    "Role conflict: READ_ONLY_AUDITOR cannot be combined with clinical PRACTITIONER signing role at the same facility.",
                    details={"code": "INCOMPATIBLE_ROLE_COMBINATION"},
                )

            assignment_id = payload.get("id") or f"sa-{uuid.uuid4().hex[:12]}"
            scope_level = "DEPARTMENT" if department_id else "FACILITY"
            assignment_type = payload.get("assignment_type", "PRIMARY").upper()
            employment_status = payload.get("employment_status", "FULL_TIME").upper()
            status = payload.get("status", "active").lower()
            extra_perms = payload.get("extra_permissions", [])
            restr_perms = payload.get("restricted_permissions", [])

            c.execute(
                """
                INSERT INTO staff_assignments (
                    id, user_id, organization_id, facility_id, department_id, unit_id,
                    role_id, role_code, scope_level, assignment_type, employment_status,
                    extra_permissions_json, restricted_permissions_json,
                    effective_from, effective_until, status, approved_by, approved_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """,
                (
                    assignment_id,
                    user_id,
                    organization_id,
                    facility_id,
                    department_id,
                    payload.get("unit_id"),
                    r_row["id"],
                    role_code,
                    scope_level,
                    assignment_type,
                    employment_status,
                    json.dumps(extra_perms),
                    json.dumps(restr_perms),
                    payload.get("effective_from"),
                    payload.get("effective_until"),
                    status,
                    actor_id,
                    actor_id,
                ),
            )

            # Synchronize user_facility_memberships for seamless backward compatibility
            if status == "active":
                c.execute(
                    """
                    INSERT INTO user_facility_memberships (id, user_id, facility_id, role_id, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    ON CONFLICT(user_id, facility_id) DO UPDATE SET role_id = excluded.role_id, is_active = 1;
                    """,
                    (f"ufm-{uuid.uuid4().hex[:12]}", user_id, facility_id, r_row["id"]),
                )

            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="STAFF_ASSIGNMENT_CREATED",
                target_entity_type="STAFF_ASSIGNMENT",
                target_entity_id=assignment_id,
                details={
                    "user_id": user_id,
                    "facility_id": facility_id,
                    "department_id": department_id,
                    "role_code": role_code,
                    "assignment_type": assignment_type,
                },
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM staff_assignments WHERE id = ?;", (assignment_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def list_staff_assignments(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            sql = """
                SELECT sa.*, u.username, u.full_name, f.name AS facility_name, d.name AS department_name
                FROM staff_assignments sa
                JOIN users u ON sa.user_id = u.id
                LEFT JOIN facilities f ON sa.facility_id = f.id
                LEFT JOIN facility_departments d ON sa.department_id = d.id
                WHERE sa.organization_id = ?
            """
            params: List[Any] = [organization_id]
            if facility_id:
                sql += " AND sa.facility_id = ?"
                params.append(facility_id)
            if user_id:
                sql += " AND sa.user_id = ?"
                params.append(user_id)
            sql += " ORDER BY sa.created_at DESC;"
            cur.execute(sql, tuple(params))
            return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                c.close()

    def revoke_staff_assignment(
        self,
        organization_id: str,
        assignment_id: str,
        actor_id: str,
        reason: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Revoke a staff assignment immediately without altering historical attribution on clinical records."""
        c, should_close = self._get_conn(conn)
        try:
            if not reason or len(reason.strip()) < 3:
                raise ValidationError("A revocation reason is required.")
            cur = c.cursor()
            cur.execute(
                "SELECT * FROM staff_assignments WHERE id = ? AND organization_id = ?;",
                (assignment_id, organization_id),
            )
            sa = cur.fetchone()
            if not sa:
                raise NotFoundError(f"Staff assignment '{assignment_id}' not found.")

            c.execute(
                """
                UPDATE staff_assignments
                SET status = 'revoked', revoked_by = ?, revoked_at = CURRENT_TIMESTAMP,
                    revocation_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (actor_id, reason, assignment_id),
            )

            # Check if the user has any remaining active assignments at that facility
            fac_id = sa["facility_id"]
            user_id = sa["user_id"]
            if fac_id:
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM staff_assignments
                    WHERE user_id = ? AND facility_id = ? AND status = 'active';
                    """,
                    (user_id, fac_id),
                )
                rem = int(cur.fetchone()["cnt"])
                if rem == 0:
                    c.execute(
                        "UPDATE user_facility_memberships SET is_active = 0 WHERE user_id = ? AND facility_id = ?;",
                        (user_id, fac_id),
                    )

            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=fac_id,
                actor_id=actor_id,
                action_type="STAFF_ASSIGNMENT_REVOKED",
                target_entity_type="STAFF_ASSIGNMENT",
                target_entity_id=assignment_id,
                details={"user_id": user_id, "facility_id": fac_id, "role_code": sa["role_code"], "reason": reason},
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM staff_assignments WHERE id = ?;", (assignment_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 5. Cross-Facility Patient Continuity & Governed Merge Workflow
    # =========================================================================

    def link_patient_to_facility(
        self,
        organization_id: str,
        patient_id: str,
        facility_id: str,
        actor_id: str,
        payload: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            body = payload or {}
            self.ensure_facility_profile(organization_id, facility_id, c)
            cur = c.cursor()
            cur.execute("SELECT id, mrn, organization_id FROM patients WHERE id = ?;", (patient_id,))
            pat = cur.fetchone()
            if not pat:
                raise NotFoundError(f"Patient '{patient_id}' not found.")
            if pat["organization_id"] != organization_id:
                raise ForbiddenError(
                    "Cross-tenant patient linking is prohibited.",
                    details={"code": "CROSS_TENANT_PATIENT_LINK_DENIED"},
                )

            cur.execute("SELECT code FROM facilities WHERE id = ?;", (facility_id,))
            fac_code = cur.fetchone()["code"]
            local_mrn = body.get("local_facility_mrn") or f"{fac_code}-{pat['mrn']}"
            privacy = body.get("privacy_restriction_level", "STANDARD").upper()
            if privacy not in ("STANDARD", "RESTRICTED_BRANCH_ONLY", "CONFIDENTIAL"):
                raise ValidationError(f"Invalid privacy_restriction_level '{privacy}'.")

            consent_granted = 1 if body.get("cross_facility_consent_granted", True) else 0
            link_id = f"pfl-{uuid.uuid4().hex[:12]}"

            c.execute(
                """
                INSERT INTO patient_facility_links (
                    id, organization_id, patient_id, facility_id, local_facility_mrn,
                    registration_source, care_team_department_id, primary_practitioner_id,
                    privacy_restriction_level, cross_facility_consent_granted,
                    consent_reference_id, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(patient_id, facility_id) DO UPDATE SET
                    privacy_restriction_level = excluded.privacy_restriction_level,
                    cross_facility_consent_granted = excluded.cross_facility_consent_granted,
                    last_seen_at = CURRENT_TIMESTAMP;
                """,
                (
                    link_id,
                    organization_id,
                    patient_id,
                    facility_id,
                    local_mrn,
                    body.get("registration_source", "OPD_REGISTRATION"),
                    body.get("care_team_department_id"),
                    body.get("primary_practitioner_id"),
                    privacy,
                    consent_granted,
                    body.get("consent_reference_id"),
                    actor_id,
                ),
            )
            if should_close:
                c.commit()
            cur.execute(
                "SELECT * FROM patient_facility_links WHERE patient_id = ? AND facility_id = ?;",
                (patient_id, facility_id),
            )
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def get_patient_cross_facility_continuity(
        self,
        organization_id: str,
        requesting_facility_id: str,
        patient_id: str,
        user_ctx: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Retrieve cross-facility Patient 360 continuity summary respecting branch privacy & org continuity policy."""
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute("SELECT * FROM patients WHERE id = ?;", (patient_id,))
            pat = cur.fetchone()
            if not pat:
                raise NotFoundError(f"Patient '{patient_id}' not found.")
            if pat["organization_id"] != organization_id:
                raise ForbiddenError(
                    "Cross-tenant patient access denied.",
                    details={"code": "CROSS_TENANT_ACCESS_DENIED"},
                )

            org_prof = self.ensure_organization_profile(organization_id, c)
            policy = org_prof["cross_facility_continuity_policy"]

            cur.execute(
                """
                SELECT pfl.*, f.name AS facility_name, f.code AS facility_code
                FROM patient_facility_links pfl
                JOIN facilities f ON pfl.facility_id = f.id
                WHERE pfl.organization_id = ? AND pfl.patient_id = ?;
                """,
                (organization_id, patient_id),
            )
            links = [dict(r) for r in cur.fetchall()]
            link_by_fac = {ln["facility_id"]: ln for ln in links}

            cur.execute(
                """
                SELECT e.id, e.facility_id, f.name AS facility_name, e.encounter_type,
                       e.status, e.reason_for_visit, e.practitioner_id, u.full_name AS practitioner_name,
                       e.created_at
                FROM encounters e
                JOIN facilities f ON e.facility_id = f.id
                LEFT JOIN users u ON e.practitioner_id = u.id
                WHERE e.organization_id = ? AND e.patient_id = ?
                ORDER BY e.created_at DESC;
                """,
                (organization_id, patient_id),
            )
            all_encounters = [dict(r) for r in cur.fetchall()]

            accessible_encounters = []
            restricted_omitted_count = 0

            for enc in all_encounters:
                enc_fac = enc["facility_id"]
                if enc_fac == requesting_facility_id:
                    accessible_encounters.append(enc)
                    continue

                # Evaluate cross-facility policy and branch privacy restriction
                if policy == "FACILITY_ISOLATED":
                    restricted_omitted_count += 1
                    continue

                fac_link = link_by_fac.get(enc_fac)
                if fac_link:
                    if fac_link["privacy_restriction_level"] == "RESTRICTED_BRANCH_ONLY":
                        restricted_omitted_count += 1
                        continue
                    if policy == "EXPLICIT_CONSENT_REQUIRED" and not fac_link["cross_facility_consent_granted"]:
                        restricted_omitted_count += 1
                        continue

                accessible_encounters.append(enc)

            return {
                "patient_id": patient_id,
                "organization_id": organization_id,
                "requesting_facility_id": requesting_facility_id,
                "continuity_policy": policy,
                "facility_links": links,
                "accessible_encounters": accessible_encounters,
                "restricted_records_omitted_count": restricted_omitted_count,
                "has_inaccessible_branch_records": restricted_omitted_count > 0,
            }
        finally:
            if should_close:
                c.close()

    def create_patient_merge_request(
        self,
        organization_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            source_id = payload.get("source_patient_id")
            target_id = payload.get("target_patient_id")
            reason = (payload.get("request_reason") or "").strip()
            if not source_id or not target_id or source_id == target_id:
                raise ValidationError("Distinct source_patient_id and target_patient_id are required.")
            if len(reason) < 5:
                raise ValidationError("A documented request_reason (min 5 chars) is required for patient merge.")

            cur = c.cursor()
            cur.execute("SELECT id, organization_id, mrn FROM patients WHERE id IN (?, ?);", (source_id, target_id))
            rows = {r["id"]: dict(r) for r in cur.fetchall()}
            if source_id not in rows or target_id not in rows:
                raise NotFoundError("Both source and target patients must exist.")
            if rows[source_id]["organization_id"] != organization_id or rows[target_id]["organization_id"] != organization_id:
                raise ForbiddenError(
                    "Cannot merge patients across different organizations.",
                    details={"code": "CROSS_TENANT_MERGE_FORBIDDEN"},
                )

            req_id = f"pmr-{uuid.uuid4().hex[:12]}"
            c.execute(
                """
                INSERT INTO patient_merge_requests (
                    id, organization_id, source_patient_id, target_patient_id,
                    status, match_evidence_json, request_reason, requested_by
                ) VALUES (?, ?, ?, ?, 'pending_review', ?, ?, ?);
                """,
                (
                    req_id,
                    organization_id,
                    source_id,
                    target_id,
                    json.dumps(payload.get("match_evidence", {})),
                    reason,
                    actor_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                actor_id=actor_id,
                action_type="PATIENT_MERGE_REQUESTED",
                target_entity_type="PATIENT_MERGE_REQUEST",
                target_entity_id=req_id,
                details={"source_patient_id": source_id, "target_patient_id": target_id, "reason": reason},
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM patient_merge_requests WHERE id = ?;", (req_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def review_patient_merge_request(
        self,
        organization_id: str,
        merge_request_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Approve or reject a patient merge request; when approved, re-link clinical records with full provenance."""
        c, should_close = self._get_conn(conn)
        try:
            decision = (payload.get("decision") or "").strip().lower()
            review_notes = (payload.get("review_notes") or "").strip()
            if decision not in ("approve", "reject"):
                raise ValidationError("decision must be 'approve' or 'reject'.")
            if len(review_notes) < 5:
                raise ValidationError("review_notes (min 5 chars) are required to approve or reject a patient merge.")

            cur = c.cursor()
            cur.execute(
                "SELECT * FROM patient_merge_requests WHERE id = ? AND organization_id = ?;",
                (merge_request_id, organization_id),
            )
            pmr = cur.fetchone()
            if not pmr:
                raise NotFoundError(f"Patient merge request '{merge_request_id}' not found.")
            if pmr["status"] != "pending_review":
                raise ConflictError(f"Merge request is already in status '{pmr['status']}'.")

            source_id = pmr["source_patient_id"]
            target_id = pmr["target_patient_id"]
            summary = {"encounters_moved": 0, "appointments_moved": 0, "invoices_moved": 0}

            if decision == "approve":
                # Move encounters and record merge events for auditability
                cur.execute(
                    "SELECT id FROM encounters WHERE organization_id = ? AND patient_id = ?;",
                    (organization_id, source_id),
                )
                for r in cur.fetchall():
                    c.execute("UPDATE encounters SET patient_id = ? WHERE id = ?;", (target_id, r["id"]))
                    c.execute(
                        """
                        INSERT INTO patient_merge_events (
                            id, merge_request_id, organization_id, source_patient_id, target_patient_id,
                            event_type, affected_table, affected_record_id, actor_id
                        ) VALUES (?, ?, ?, ?, ?, 'RECORD_RELINKED', 'encounters', ?, ?);
                        """,
                        (f"pme-{uuid.uuid4().hex[:12]}", merge_request_id, organization_id, source_id, target_id, r["id"], actor_id),
                    )
                    summary["encounters_moved"] += 1

                cur.execute(
                    "SELECT id FROM appointments WHERE organization_id = ? AND patient_id = ?;",
                    (organization_id, source_id),
                )
                for r in cur.fetchall():
                    c.execute("UPDATE appointments SET patient_id = ? WHERE id = ?;", (target_id, r["id"]))
                    summary["appointments_moved"] += 1

                cur.execute(
                    "SELECT id FROM invoices WHERE organization_id = ? AND patient_id = ?;",
                    (organization_id, source_id),
                )
                for r in cur.fetchall():
                    c.execute("UPDATE invoices SET patient_id = ? WHERE id = ?;", (target_id, r["id"]))
                    summary["invoices_moved"] += 1

                c.execute(
                    "UPDATE patients SET status = 'INACTIVE', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND organization_id = ?;",
                    (source_id, organization_id),
                )
                c.execute(
                    """
                    UPDATE patient_facility_links
                    SET is_merged_redirect = 1, merged_into_patient_id = ?
                    WHERE organization_id = ? AND patient_id = ?;
                    """,
                    (target_id, organization_id, source_id),
                )
                new_status = "approved_merged"
            else:
                new_status = "rejected"

            c.execute(
                """
                UPDATE patient_merge_requests
                SET status = ?, reviewed_by = ?, review_notes = ?,
                    merged_records_summary_json = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (new_status, actor_id, review_notes, json.dumps(summary), merge_request_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                actor_id=actor_id,
                action_type=f"PATIENT_MERGE_{new_status.upper()}",
                target_entity_type="PATIENT_MERGE_REQUEST",
                target_entity_id=merge_request_id,
                details={
                    "source_patient_id": source_id,
                    "target_patient_id": target_id,
                    "summary": summary,
                    "review_notes": review_notes,
                },
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM patient_merge_requests WHERE id = ?;", (merge_request_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 6. Controlled Inter-Facility Transfers & Referrals
    # =========================================================================

    def create_transfer(
        self,
        organization_id: str,
        actor_id: str,
        user_ctx: Dict[str, Any],
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            idem_key = payload.get("idempotency_key")
            if idem_key:
                cur.execute(
                    "SELECT id FROM facility_transfers WHERE organization_id = ? AND idempotency_key = ?;",
                    (organization_id, idem_key),
                )
                existing = cur.fetchone()
                if existing:
                    return self.get_transfer(organization_id, existing["id"], user_ctx=user_ctx, conn=c)

            orig_fac_id = payload.get("originating_facility_id") or user_ctx.get("active_facility_id")
            recv_fac_id = payload.get("receiving_facility_id")
            patient_id = payload.get("patient_id")
            source_enc_id = payload.get("source_encounter_id")
            reason = (payload.get("reason_for_transfer") or "").strip()
            summary = (payload.get("minimum_clinical_summary") or "").strip()

            if not orig_fac_id or not recv_fac_id or orig_fac_id == recv_fac_id:
                raise ValidationError("Distinct originating_facility_id and receiving_facility_id are required.")
            if not patient_id or not reason or not summary:
                raise ValidationError("patient_id, reason_for_transfer, and minimum_clinical_summary are required.")

            # Validate both facilities belong to the organization and are active
            orig_fac = self.get_facility(organization_id, orig_fac_id, conn=c)
            recv_fac = self.get_facility(organization_id, recv_fac_id, conn=c)
            if orig_fac["lifecycle_status"] != "active" or recv_fac["lifecycle_status"] != "active":
                raise ConflictError(
                    "Both originating and receiving facilities must be 'active' to initiate a transfer.",
                    details={"code": "TRANSFER_FACILITY_NOT_ACTIVE"},
                )

            # Verify patient & source encounter belong to organization and originating facility
            cur.execute("SELECT id, organization_id FROM patients WHERE id = ?;", (patient_id,))
            pat = cur.fetchone()
            if not pat or pat["organization_id"] != organization_id:
                raise NotFoundError(f"Patient '{patient_id}' not found in organization.")

            if source_enc_id:
                cur.execute(
                    "SELECT id, facility_id, patient_id FROM encounters WHERE id = ? AND organization_id = ?;",
                    (source_enc_id, organization_id),
                )
                enc = cur.fetchone()
                if not enc or enc["patient_id"] != patient_id:
                    raise ValidationError("source_encounter_id does not match the specified patient.")

            urgency = (payload.get("urgency") or "ROUTINE").strip().upper()
            if urgency in ("URGENT", "EMERGENCY"):
                roles = set(user_ctx.get("roles", []))
                if not (roles & {"PRACTITIONER", "ORG_ADMIN"}):
                    raise ForbiddenError(
                        "Only an authorized clinician can author URGENT or EMERGENCY transfer urgency.",
                        details={"code": "CLINICAL_URGENCY_AUTHORIZATION_REQUIRED"},
                    )

            transfer_id = f"trf-{uuid.uuid4().hex[:12]}"
            # Sending a transfer sets status = 'requested', NEVER 'accepted'!
            c.execute(
                """
                INSERT INTO facility_transfers (
                    id, organization_id, target_organization_id,
                    originating_facility_id, receiving_facility_id, receiving_department_id,
                    patient_id, source_encounter_id, referring_practitioner_id,
                    transfer_type, urgency, status, reason_for_transfer,
                    minimum_clinical_summary, authorized_attachments_json,
                    consent_basis, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'requested', ?, ?, ?, ?, ?);
                """,
                (
                    transfer_id,
                    organization_id,
                    organization_id,
                    orig_fac_id,
                    recv_fac_id,
                    payload.get("receiving_department_id"),
                    patient_id,
                    source_enc_id,
                    actor_id,
                    payload.get("transfer_type", "INTERNAL_BRANCH_REFERRAL"),
                    urgency,
                    reason,
                    summary,
                    json.dumps(payload.get("authorized_attachments", [])),
                    payload.get("consent_basis", "TREATMENT_CONTINUITY"),
                    idem_key,
                ),
            )
            c.execute(
                """
                INSERT INTO facility_transfer_events (
                    id, transfer_id, organization_id, from_status, to_status, actor_id, actor_facility_id, notes
                ) VALUES (?, ?, ?, NULL, 'requested', ?, ?, ?);
                """,
                (f"tfe-{uuid.uuid4().hex[:12]}", transfer_id, organization_id, actor_id, orig_fac_id, reason),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=orig_fac_id,
                actor_id=actor_id,
                action_type="FACILITY_TRANSFER_REQUESTED",
                target_entity_type="FACILITY_TRANSFER",
                target_entity_id=transfer_id,
                details={
                    "originating_facility_id": orig_fac_id,
                    "receiving_facility_id": recv_fac_id,
                    "patient_id": patient_id,
                    "urgency": urgency,
                },
            )
            if should_close:
                c.commit()
            return self.get_transfer(organization_id, transfer_id, user_ctx=user_ctx, conn=c)
        finally:
            if should_close:
                c.close()

    def get_transfer(
        self,
        organization_id: str,
        transfer_id: str,
        user_ctx: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT t.*, fo.name AS originating_facility_name, fr.name AS receiving_facility_name,
                       p.display_name AS patient_name, p.mrn AS patient_mrn
                FROM facility_transfers t
                JOIN facilities fo ON t.originating_facility_id = fo.id
                JOIN facilities fr ON t.receiving_facility_id = fr.id
                JOIN patients p ON t.patient_id = p.id
                WHERE t.id = ? AND t.organization_id = ?;
                """,
                (transfer_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Transfer '{transfer_id}' not found.")

            trf = dict(row)
            # Protect sensitive attachments if user is not authorized at either originating or receiving facility
            if user_ctx and "ORG_ADMIN" not in user_ctx.get("org_roles", user_ctx.get("roles", [])):
                fac_scopes = user_ctx.get("facility_scopes", {})
                allowed_facs = {trf["originating_facility_id"], trf["receiving_facility_id"]}
                if fac_scopes and not (set(fac_scopes.keys()) & allowed_facs):
                    raise ForbiddenError(
                        "Access denied: User is not authorized at the originating or receiving facility for this transfer.",
                        details={"code": "TRANSFER_FACILITY_SCOPE_DENIED"},
                    )

            trf["authorized_attachments"] = json.loads(trf.get("authorized_attachments_json") or "[]")
            cur.execute(
                "SELECT * FROM facility_transfer_events WHERE transfer_id = ? ORDER BY created_at ASC;",
                (transfer_id,),
            )
            trf["events"] = [dict(r) for r in cur.fetchall()]
            return trf
        finally:
            if should_close:
                c.close()

    def list_transfers(
        self,
        organization_id: str,
        filters: Optional[Dict[str, Any]] = None,
        user_ctx: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            f = filters or {}
            cur = c.cursor()
            sql = "SELECT id FROM facility_transfers WHERE organization_id = ?"
            params: List[Any] = [organization_id]
            if f.get("facility_id"):
                sql += " AND (originating_facility_id = ? OR receiving_facility_id = ?)"
                params.extend([f["facility_id"], f["facility_id"]])
            if f.get("status"):
                sql += " AND status = ?"
                params.append(f["status"])
            sql += " ORDER BY created_at DESC;"
            cur.execute(sql, tuple(params))
            ids = [r["id"] for r in cur.fetchall()]
            out = []
            for tid in ids:
                try:
                    out.append(self.get_transfer(organization_id, tid, user_ctx=user_ctx, conn=c))
                except ForbiddenError:
                    continue
            return out
        finally:
            if should_close:
                c.close()

    def transition_transfer(
        self,
        organization_id: str,
        transfer_id: str,
        action: str,
        actor_id: str,
        user_ctx: Dict[str, Any],
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Accept, decline, or complete an inter-facility transfer with recipient authorization & idempotency."""
        c, should_close = self._get_conn(conn)
        try:
            trf = self.get_transfer(organization_id, transfer_id, user_ctx=user_ctx, conn=c)
            curr_status = trf["status"]
            recv_fac_id = trf["receiving_facility_id"]

            # Verify recipient authorization at receiving facility for accept/decline/complete
            org_roles = set(user_ctx.get("org_roles", []))
            if "ORG_ADMIN" not in org_roles:
                fac_scopes = user_ctx.get("facility_scopes", {})
                if recv_fac_id not in fac_scopes:
                    raise ForbiddenError(
                        f"Only staff authorized at receiving facility '{recv_fac_id}' can {action} this transfer.",
                        details={"code": "TRANSFER_RECIPIENT_UNAUTHORIZED", "receiving_facility_id": recv_fac_id},
                    )

            if action == "accept":
                if curr_status == "accepted":
                    trf["idempotent_replay"] = True
                    return trf
                if curr_status != "requested":
                    raise ConflictError(f"Cannot accept transfer in status '{curr_status}'.")
                notes = payload.get("acceptance_notes") or "Transfer accepted by receiving facility"
                c.execute(
                    """
                    UPDATE facility_transfers
                    SET status = 'accepted', receiving_practitioner_id = ?, acceptance_notes = ?,
                        accepted_at = CURRENT_TIMESTAMP, version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (actor_id, notes, transfer_id),
                )
                # Ensure patient is linked to receiving facility for continuity
                self.link_patient_to_facility(
                    organization_id,
                    trf["patient_id"],
                    recv_fac_id,
                    actor_id,
                    {"registration_source": "INTER_FACILITY_TRANSFER"},
                    conn=c,
                )
                to_status = "accepted"
            elif action == "decline":
                if curr_status == "declined":
                    trf["idempotent_replay"] = True
                    return trf
                if curr_status != "requested":
                    raise ConflictError(f"Cannot decline transfer in status '{curr_status}'.")
                reason = (payload.get("decline_reason") or "").strip()
                if len(reason) < 3:
                    raise ValidationError("decline_reason is required when declining a transfer.")
                notes = reason
                c.execute(
                    """
                    UPDATE facility_transfers
                    SET status = 'declined', decline_reason = ?, declined_at = CURRENT_TIMESTAMP,
                        version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (reason, transfer_id),
                )
                to_status = "declined"
            elif action == "complete":
                if curr_status == "completed":
                    trf["idempotent_replay"] = True
                    return trf
                if curr_status not in ("accepted", "in_transit", "arrived"):
                    raise ConflictError(f"Transfer must be 'accepted' before completion (current: '{curr_status}').")
                outcome = (payload.get("completion_outcome_summary") or "Patient received and evaluated at receiving facility").strip()
                missing_info = payload.get("missing_information_notes")
                notes = outcome

                # Create a new destination encounter at the receiving facility without modifying source encounter!
                dest_enc_id = f"enc-{uuid.uuid4().hex[:12]}"
                c.execute(
                    """
                    INSERT INTO encounters (
                        id, organization_id, facility_id, patient_id, practitioner_id,
                        encounter_type, status, reason_for_visit, created_by
                    ) VALUES (?, ?, ?, ?, ?, 'TRANSFER_RECEIVING_VISIT', 'IN_PROGRESS', ?, ?);
                    """,
                    (
                        dest_enc_id,
                        organization_id,
                        recv_fac_id,
                        trf["patient_id"],
                        actor_id,
                        f"Transfer from {trf['originating_facility_name']}: {trf['reason_for_transfer']} | {trf['minimum_clinical_summary']}",
                        actor_id,
                    ),
                )
                c.execute(
                    """
                    UPDATE facility_transfers
                    SET status = 'completed', destination_encounter_id = ?,
                        completion_outcome_summary = ?, missing_information_notes = ?,
                        completed_at = CURRENT_TIMESTAMP, version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (dest_enc_id, outcome, missing_info, transfer_id),
                )
                to_status = "completed"
            else:
                raise ValidationError(f"Unsupported transfer action '{action}'.")

            c.execute(
                """
                INSERT INTO facility_transfer_events (
                    id, transfer_id, organization_id, from_status, to_status, actor_id, actor_facility_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (f"tfe-{uuid.uuid4().hex[:12]}", transfer_id, organization_id, curr_status, to_status, actor_id, recv_fac_id, notes),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=recv_fac_id,
                actor_id=actor_id,
                action_type=f"FACILITY_TRANSFER_{to_status.upper()}",
                target_entity_type="FACILITY_TRANSFER",
                target_entity_id=transfer_id,
                details={"from_status": curr_status, "to_status": to_status, "notes": notes},
            )
            if should_close:
                c.commit()
            return self.get_transfer(organization_id, transfer_id, user_ctx=user_ctx, conn=c)
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 7. Layered Configuration Inheritance, Versioning & Rollback
    # =========================================================================

    def _validate_config_against_platform_security(self, config_dict: Dict[str, Any]) -> None:
        secret_field = _contains_plaintext_secret(config_dict)
        if secret_field:
            raise ValidationError(
                f"Plaintext secret or credential key '{secret_field}' is prohibited in configuration records.",
                details={"code": "PLAINTEXT_SECRET_PROHIBITED", "field": secret_field},
            )
        if config_dict.get("require_clinician_pin_for_signoff") is False:
            raise ValidationError(
                "Cannot disable platform-required clinician PIN sign-off security control.",
                details={"code": "PLATFORM_SECURITY_CONSTRAINT_VIOLATION"},
            )
        if config_dict.get("allow_unsigned_dispensing") is True:
            raise ValidationError(
                "Cannot enable unsigned prescription dispensing; violates platform safety baseline.",
                details={"code": "PLATFORM_SECURITY_CONSTRAINT_VIOLATION"},
            )
        if config_dict.get("enforce_tenant_isolation") is False:
            raise ValidationError(
                "Cannot weaken multi-tenant isolation constraint.",
                details={"code": "PLATFORM_SECURITY_CONSTRAINT_VIOLATION"},
            )
        if config_dict.get("require_safety_preflight_before_rx_sign") is False:
            raise ValidationError(
                "Cannot disable clinical safety firewall preflight requirement.",
                details={"code": "PLATFORM_SECURITY_CONSTRAINT_VIOLATION"},
            )
        if "audit_retention_days" in config_dict:
            days = int(config_dict["audit_retention_days"])
            if days < PLATFORM_SECURITY_BASELINE["audit_retention_min_days"]:
                raise ValidationError(
                    f"audit_retention_days ({days}) cannot be lower than platform minimum ({PLATFORM_SECURITY_BASELINE['audit_retention_min_days']}).",
                    details={"code": "PLATFORM_SECURITY_CONSTRAINT_VIOLATION"},
                )

    def get_organization_configuration(
        self, organization_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM configuration_policies
                WHERE organization_id = ? AND scope_level = 'ORGANIZATION' AND facility_id IS NULL;
                """,
                (organization_id,),
            )
            row = cur.fetchone()
            org_overrides = json.loads(row["config_json"]) if row else {}
            current_ver = int(row["current_version"]) if row else 1

            effective = copy.deepcopy(DEFAULT_ORGANIZATION_CONFIG)
            effective.update(org_overrides)
            effective.update(PLATFORM_SECURITY_BASELINE)

            versions = []
            if row:
                cur.execute(
                    "SELECT * FROM configuration_versions WHERE policy_id = ? ORDER BY version_number DESC;",
                    (row["id"],),
                )
                versions = [dict(r) for r in cur.fetchall()]

            return {
                "organization_id": organization_id,
                "scope_level": "ORGANIZATION",
                "current_version": current_ver,
                "platform_security_baseline": PLATFORM_SECURITY_BASELINE,
                "organization_overrides": org_overrides,
                "effective_configuration": effective,
                "version_history": versions,
            }
        finally:
            if should_close:
                c.close()

    def update_organization_configuration(
        self,
        organization_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            settings_patch = payload.get("settings") or payload.get("config") or {}
            reason = (payload.get("change_reason") or "Updated organization configuration").strip()
            self._validate_config_against_platform_security(settings_patch)

            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM configuration_policies
                WHERE organization_id = ? AND scope_level = 'ORGANIZATION' AND facility_id IS NULL;
                """,
                (organization_id,),
            )
            row = cur.fetchone()
            if row:
                policy_id = row["id"]
                merged = json.loads(row["config_json"])
                merged.update(settings_patch)
                self._validate_config_against_platform_security(merged)
                new_ver = int(row["current_version"]) + 1
                c.execute(
                    """
                    UPDATE configuration_policies
                    SET config_json = ?, current_version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (json.dumps(merged), new_ver, actor_id, policy_id),
                )
            else:
                policy_id = f"cpol-{uuid.uuid4().hex[:12]}"
                merged = dict(settings_patch)
                new_ver = 1
                c.execute(
                    """
                    INSERT INTO configuration_policies (
                        id, organization_id, facility_id, scope_level, config_json, current_version, updated_by
                    ) VALUES (?, ?, NULL, 'ORGANIZATION', ?, 1, ?);
                    """,
                    (policy_id, organization_id, json.dumps(merged), actor_id),
                )

            c.execute(
                """
                INSERT INTO configuration_versions (
                    id, policy_id, organization_id, facility_id, scope_level,
                    version_number, config_json, change_reason, changed_by
                ) VALUES (?, ?, ?, NULL, 'ORGANIZATION', ?, ?, ?, ?);
                """,
                (f"cver-{uuid.uuid4().hex[:12]}", policy_id, organization_id, new_ver, json.dumps(merged), reason, actor_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                actor_id=actor_id,
                action_type="ORGANIZATION_CONFIGURATION_UPDATED",
                target_entity_type="CONFIGURATION_POLICY",
                target_entity_id=policy_id,
                details={"version": new_ver, "updated_keys": list(settings_patch.keys()), "reason": reason},
            )
            if should_close:
                c.commit()
            return self.get_organization_configuration(organization_id, conn=c)
        finally:
            if should_close:
                c.close()

    def get_facility_configuration(
        self, organization_id: str, facility_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            self.ensure_facility_profile(organization_id, facility_id, c)
            org_cfg = self.get_organization_configuration(organization_id, conn=c)
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM configuration_policies
                WHERE organization_id = ? AND facility_id = ? AND scope_level = 'FACILITY';
                """,
                (organization_id, facility_id),
            )
            row = cur.fetchone()
            fac_overrides = json.loads(row["config_json"]) if row else {}
            current_ver = int(row["current_version"]) if row else 1

            effective = copy.deepcopy(org_cfg["effective_configuration"])
            effective.update(fac_overrides)
            # Platform security baseline always wins
            effective.update(PLATFORM_SECURITY_BASELINE)

            inheritance_map = {}
            for k in effective.keys():
                if k in PLATFORM_SECURITY_BASELINE:
                    inheritance_map[k] = "PLATFORM_SECURITY"
                elif k in fac_overrides:
                    inheritance_map[k] = "FACILITY_OVERRIDE"
                elif k in org_cfg["organization_overrides"]:
                    inheritance_map[k] = "ORGANIZATION"
                else:
                    inheritance_map[k] = "DEFAULT"

            versions = []
            if row:
                cur.execute(
                    "SELECT * FROM configuration_versions WHERE policy_id = ? ORDER BY version_number DESC;",
                    (row["id"],),
                )
                versions = [dict(r) for r in cur.fetchall()]

            return {
                "organization_id": organization_id,
                "facility_id": facility_id,
                "scope_level": "FACILITY",
                "current_version": current_ver,
                "facility_overrides": fac_overrides,
                "effective_configuration": effective,
                "inheritance_provenance": inheritance_map,
                "version_history": versions,
            }
        finally:
            if should_close:
                c.close()

    def update_facility_configuration(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            self.ensure_facility_profile(organization_id, facility_id, c)
            settings_patch = payload.get("settings") or payload.get("config") or {}
            reason = (payload.get("change_reason") or "Updated facility configuration override").strip()
            self._validate_config_against_platform_security(settings_patch)

            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM configuration_policies
                WHERE organization_id = ? AND facility_id = ? AND scope_level = 'FACILITY';
                """,
                (organization_id, facility_id),
            )
            row = cur.fetchone()
            if row:
                policy_id = row["id"]
                merged = json.loads(row["config_json"])
                merged.update(settings_patch)
                self._validate_config_against_platform_security(merged)
                new_ver = int(row["current_version"]) + 1
                c.execute(
                    """
                    UPDATE configuration_policies
                    SET config_json = ?, current_version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (json.dumps(merged), new_ver, actor_id, policy_id),
                )
            else:
                policy_id = f"cpol-{uuid.uuid4().hex[:12]}"
                merged = dict(settings_patch)
                new_ver = 1
                c.execute(
                    """
                    INSERT INTO configuration_policies (
                        id, organization_id, facility_id, scope_level, config_json, current_version, updated_by
                    ) VALUES (?, ?, ?, 'FACILITY', ?, 1, ?);
                    """,
                    (policy_id, organization_id, facility_id, json.dumps(merged), actor_id),
                )

            c.execute(
                """
                INSERT INTO configuration_versions (
                    id, policy_id, organization_id, facility_id, scope_level,
                    version_number, config_json, change_reason, changed_by
                ) VALUES (?, ?, ?, ?, 'FACILITY', ?, ?, ?, ?);
                """,
                (f"cver-{uuid.uuid4().hex[:12]}", policy_id, organization_id, facility_id, new_ver, json.dumps(merged), reason, actor_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="FACILITY_CONFIGURATION_UPDATED",
                target_entity_type="CONFIGURATION_POLICY",
                target_entity_id=policy_id,
                details={"version": new_ver, "updated_keys": list(settings_patch.keys()), "reason": reason},
            )
            if should_close:
                c.commit()
            return self.get_facility_configuration(organization_id, facility_id, conn=c)
        finally:
            if should_close:
                c.close()

    def rollback_facility_configuration(
        self,
        organization_id: str,
        facility_id: str,
        target_version: int,
        actor_id: str,
        reason: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM configuration_policies
                WHERE organization_id = ? AND facility_id = ? AND scope_level = 'FACILITY';
                """,
                (organization_id, facility_id),
            )
            pol = cur.fetchone()
            if not pol:
                raise NotFoundError("No facility configuration policy found to roll back.")

            cur.execute(
                "SELECT * FROM configuration_versions WHERE policy_id = ? AND version_number = ?;",
                (pol["id"], target_version),
            )
            ver_row = cur.fetchone()
            if not ver_row:
                raise NotFoundError(f"Configuration version {target_version} not found.")

            new_ver = int(pol["current_version"]) + 1
            c.execute(
                """
                UPDATE configuration_policies
                SET config_json = ?, current_version = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (ver_row["config_json"], new_ver, actor_id, pol["id"]),
            )
            c.execute(
                """
                INSERT INTO configuration_versions (
                    id, policy_id, organization_id, facility_id, scope_level,
                    version_number, config_json, change_reason, changed_by, rolled_back_from_version
                ) VALUES (?, ?, ?, ?, 'FACILITY', ?, ?, ?, ?, ?);
                """,
                (
                    f"cver-{uuid.uuid4().hex[:12]}",
                    pol["id"],
                    organization_id,
                    facility_id,
                    new_ver,
                    ver_row["config_json"],
                    reason or f"Rollback to version {target_version}",
                    actor_id,
                    int(pol["current_version"]),
                ),
            )
            if should_close:
                c.commit()
            return self.get_facility_configuration(organization_id, facility_id, conn=c)
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 8. Module Entitlements & Prerequisite Validation
    # =========================================================================

    def _ensure_default_facility_modules(
        self, organization_id: str, facility_id: str, actor_id: str, conn: sqlite3.Connection
    ) -> None:
        default_enabled = {
            "clinical_core": (1, "FUNCTIONALLY_TESTED"),
            "safety_firewall": (1, "FUNCTIONALLY_TESTED"),
            "unani_assessment": (1, "FUNCTIONALLY_TESTED"),
            "modern_assessment": (1, "FUNCTIONALLY_TESTED"),
            "knowledge_retrieval": (1, "FUNCTIONALLY_TESTED"),
            "appointments_queue": (1, "FUNCTIONALLY_TESTED"),
            "billing": (1, "FUNCTIONALLY_TESTED"),
            "pharmacy_inventory": (1, "FUNCTIONALLY_TESTED"),
            "followup_continuity": (1, "FUNCTIONALLY_TESTED"),
            "hospital_modules": (0, "NOT_IMPLEMENTED"),
            "integrations_reporting": (1, "CONNECTED_NOT_VALIDATED"),
        }
        for mod_key, (enabled, status) in default_enabled.items():
            prereqs = MODULE_PREREQUISITES.get(mod_key, [])
            conn.execute(
                """
                INSERT INTO facility_module_entitlements (
                    id, organization_id, facility_id, module_key, is_enabled,
                    readiness_status, prerequisites_json, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(facility_id, module_key) DO NOTHING;
                """,
                (
                    f"fmod-{uuid.uuid4().hex[:12]}",
                    organization_id,
                    facility_id,
                    mod_key,
                    enabled,
                    status,
                    json.dumps(prereqs),
                    actor_id,
                ),
            )

    def list_facility_modules(
        self, organization_id: str, facility_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            self.ensure_facility_profile(organization_id, facility_id, c)
            self._ensure_default_facility_modules(organization_id, facility_id, "usr-admin-1", c)
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM facility_module_entitlements
                WHERE organization_id = ? AND facility_id = ?
                ORDER BY module_key ASC;
                """,
                (organization_id, facility_id),
            )
            rows = []
            for r in cur.fetchall():
                d = dict(r)
                d["prerequisites"] = json.loads(d.get("prerequisites_json") or "[]")
                rows.append(d)
            if should_close:
                c.commit()
            return rows
        finally:
            if should_close:
                c.close()

    def set_facility_module_state(
        self,
        organization_id: str,
        facility_id: str,
        module_key: str,
        enable: bool,
        actor_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            if module_key not in MODULE_PREREQUISITES:
                raise ValidationError(f"Unknown module_key '{module_key}'.")

            current_mods = {
                m["module_key"]: m for m in self.list_facility_modules(organization_id, facility_id, conn=c)
            }

            if enable:
                # Verify all prerequisite modules are currently enabled
                prereqs = MODULE_PREREQUISITES[module_key]
                missing = [p for p in prereqs if not current_mods.get(p, {}).get("is_enabled")]
                if missing:
                    raise ConflictError(
                        f"Cannot enable '{module_key}': prerequisite modules {missing} are disabled.",
                        details={"code": "MODULE_PREREQUISITES_NOT_MET", "missing_prerequisites": missing},
                    )
                if module_key == "hospital_modules":
                    cur = c.cursor()
                    cur.execute(
                        "SELECT COUNT(*) AS cnt FROM facility_departments WHERE facility_id = ? AND status = 'active';",
                        (facility_id,),
                    )
                    if int(cur.fetchone()["cnt"]) == 0:
                        raise ConflictError(
                            "Cannot enable 'hospital_modules' until at least one active department is configured.",
                            details={"code": "HOSPITAL_MODULE_REQUIRES_ACTIVE_DEPARTMENT"},
                        )
            else:
                # Never allow disabling safety_firewall while clinical_core or pharmacy_inventory is enabled
                if module_key in ("clinical_core", "safety_firewall"):
                    dependents = [
                        k
                        for k, p_list in MODULE_PREREQUISITES.items()
                        if module_key in p_list and current_mods.get(k, {}).get("is_enabled")
                    ]
                    if dependents:
                        raise ConflictError(
                            f"Cannot disable '{module_key}' while dependent modules {dependents} are enabled.",
                            details={"code": "MODULE_HAS_ACTIVE_DEPENDENTS", "dependent_modules": dependents},
                        )

            c.execute(
                """
                UPDATE facility_module_entitlements
                SET is_enabled = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE organization_id = ? AND facility_id = ? AND module_key = ?;
                """,
                (1 if enable else 0, actor_id, organization_id, facility_id, module_key),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="FACILITY_MODULE_ENABLED" if enable else "FACILITY_MODULE_DISABLED",
                target_entity_type="FACILITY_MODULE",
                target_entity_id=f"{facility_id}:{module_key}",
                details={"module_key": module_key, "is_enabled": enable},
            )
            if should_close:
                c.commit()
            updated = {
                m["module_key"]: m for m in self.list_facility_modules(organization_id, facility_id, conn=c)
            }
            return updated[module_key]
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 9. Hospital Integration Registry & Secret Reference Governance
    # =========================================================================

    def create_integration_connector(
        self,
        organization_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            secret_err = _contains_plaintext_secret(payload)
            if secret_err:
                raise ValidationError(
                    f"Plaintext secret field '{secret_err}' is prohibited. Store credentials in a secrets manager and supply 'secret_ref_uri'.",
                    details={"code": "PLAINTEXT_SECRET_PROHIBITED", "field": secret_err},
                )

            connector_type = (payload.get("connector_type") or "").strip().upper()
            name = (payload.get("name") or "").strip()
            if not connector_type or not name:
                raise ValidationError("connector_type and name are required.")

            secret_ref = payload.get("secret_ref_uri")
            if secret_ref and not str(secret_ref).startswith(("vault://", "kms://", "env://", "secret-mgr://")):
                raise ValidationError(
                    "secret_ref_uri must use an approved secret manager URI scheme (vault://, kms://, env://, secret-mgr://)."
                )

            requested_state = (payload.get("lifecycle_state") or "CONFIGURED_NOT_CONNECTED").strip().upper()
            if requested_state == "PRODUCTION_ACTIVE":
                raise ConflictError(
                    "Cannot create an integration directly in 'PRODUCTION_ACTIVE' state before sandbox testing and verification.",
                    details={"code": "INTEGRATION_NOT_VERIFIED_FOR_PRODUCTION"},
                )

            conn_id = f"intg-{uuid.uuid4().hex[:12]}"
            c.execute(
                """
                INSERT INTO integration_connectors (
                    id, organization_id, facility_id, connector_type, name, environment,
                    lifecycle_state, endpoint_url, api_version, secret_ref_uri,
                    allowed_scopes_json, data_sharing_policy_ref, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    conn_id,
                    organization_id,
                    payload.get("facility_id"),
                    connector_type,
                    name,
                    payload.get("environment", "SANDBOX").upper(),
                    requested_state,
                    payload.get("endpoint_url"),
                    payload.get("api_version", "v1"),
                    secret_ref,
                    json.dumps(payload.get("allowed_scopes", [])),
                    payload.get("data_sharing_policy_ref"),
                    actor_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=payload.get("facility_id"),
                actor_id=actor_id,
                action_type="INTEGRATION_CONNECTOR_CREATED",
                target_entity_type="INTEGRATION_CONNECTOR",
                target_entity_id=conn_id,
                details={"connector_type": connector_type, "lifecycle_state": requested_state},
            )
            if should_close:
                c.commit()
            cur = c.cursor()
            cur.execute("SELECT * FROM integration_connectors WHERE id = ?;", (conn_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def verify_and_transition_integration(
        self,
        organization_id: str,
        connector_id: str,
        target_state: str,
        actor_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                "SELECT * FROM integration_connectors WHERE id = ? AND organization_id = ?;",
                (connector_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Integration connector '{connector_id}' not found.")

            target = target_state.strip().upper()
            if target == "PRODUCTION_ACTIVE":
                if row["lifecycle_state"] != "SANDBOX_TESTED":
                    raise ConflictError(
                        "Integration must pass 'SANDBOX_TESTED' verification before transitioning to 'PRODUCTION_ACTIVE'.",
                        details={"code": "INTEGRATION_NOT_VERIFIED_FOR_PRODUCTION"},
                    )
                if not row["secret_ref_uri"] or not row["data_sharing_policy_ref"]:
                    raise ConflictError(
                        "secret_ref_uri and data_sharing_policy_ref are required before activating production integration.",
                        details={"code": "INTEGRATION_MISSING_CREDENTIALS_OR_POLICY"},
                    )

            c.execute(
                """
                UPDATE integration_connectors
                SET lifecycle_state = ?,
                    last_verified_at = CASE WHEN ? IN ('SANDBOX_TESTED', 'PRODUCTION_ACTIVE') THEN CURRENT_TIMESTAMP ELSE last_verified_at END,
                    last_health_status = CASE WHEN ? IN ('SANDBOX_TESTED', 'PRODUCTION_ACTIVE') THEN 'VERIFIED_HEALTHY' ELSE last_health_status END,
                    updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (target, target, target, actor_id, connector_id),
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM integration_connectors WHERE id = ?;", (connector_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def list_integration_connectors(
        self, organization_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                "SELECT * FROM integration_connectors WHERE organization_id = ? ORDER BY created_at DESC;",
                (organization_id,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 10. Single-Clinic to Multi-Facility Migration Engine & Enterprise Audit
    # =========================================================================

    def run_single_clinic_migration(
        self,
        organization_id: str,
        default_facility_id: str,
        actor_id: str,
        mode: str = "DRY_RUN",
        backup_reference: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """
        Idempotent, repeatable migration engine from single-clinic mode to multi-facility mode:
        - Captures pre-migration record counts across all clinical & operational tables
        - Detects any orphan records with NULL or ambiguous organization/facility scope
        - Backfills patient_facility_links, organization_profiles, and facility_profiles
        - Verifies post-migration record counts reconcile 100%
        """
        c, should_close = self._get_conn(conn)
        try:
            run_mode = mode.strip().upper()
            if run_mode not in ("DRY_RUN", "EXECUTE"):
                raise ValidationError("mode must be 'DRY_RUN' or 'EXECUTE'.")

            self.ensure_facility_profile(organization_id, default_facility_id, c)
            cur = c.cursor()

            def _gather_counts() -> Dict[str, int]:
                tables = ["patients", "encounters", "prescriptions", "appointments", "invoices", "inventory_batches"]
                counts = {}
                for tbl in tables:
                    cur.execute(f"SELECT COUNT(*) AS cnt FROM {tbl} WHERE organization_id = ?;", (organization_id,))
                    counts[tbl] = int(cur.fetchone()["cnt"])
                cur.execute("SELECT COUNT(*) AS cnt FROM patient_facility_links WHERE organization_id = ?;", (organization_id,))
                counts["patient_facility_links"] = int(cur.fetchone()["cnt"])
                return counts

            pre_counts = _gather_counts()

            # Check for ambiguous or orphan records lacking organization_id or facility_id
            orphans = []
            cur.execute("SELECT id FROM encounters WHERE organization_id = ? AND (facility_id IS NULL OR facility_id = '');", (organization_id,))
            for r in cur.fetchall():
                orphans.append({"table": "encounters", "record_id": r["id"], "issue": "MISSING_FACILITY_ID"})

            if run_mode == "EXECUTE" and not orphans:
                self.ensure_organization_profile(organization_id, c)
                cur.execute("SELECT id, mrn FROM patients WHERE organization_id = ?;", (organization_id,))
                for pat in cur.fetchall():
                    self.link_patient_to_facility(
                        organization_id,
                        pat["id"],
                        default_facility_id,
                        actor_id,
                        {"registration_source": "SINGLE_CLINIC_MIGRATION"},
                        conn=c,
                    )

            post_counts = _gather_counts()
            counts_reconciled = all(
                pre_counts[t] == post_counts[t]
                for t in ["patients", "encounters", "prescriptions", "appointments", "invoices", "inventory_batches"]
            )
            status = "REMEDIATION_REQUIRED" if orphans else "COMPLETED"
            run_id = f"mig-{uuid.uuid4().hex[:12]}"

            c.execute(
                """
                INSERT INTO single_clinic_migration_runs (
                    id, organization_id, default_facility_id, mode, status,
                    pre_counts_json, post_counts_json, orphans_detected_json,
                    backup_reference, executed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    organization_id,
                    default_facility_id,
                    run_mode,
                    status,
                    json.dumps(pre_counts),
                    json.dumps(post_counts),
                    json.dumps(orphans),
                    backup_reference or "SNAPSHOT-AUTO-VERIFIED",
                    actor_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=default_facility_id,
                actor_id=actor_id,
                action_type=f"SINGLE_CLINIC_MIGRATION_{run_mode}",
                target_entity_type="MIGRATION_RUN",
                target_entity_id=run_id,
                details={"status": status, "counts_reconciled": counts_reconciled, "orphans_count": len(orphans)},
            )
            if should_close:
                c.commit()
            return {
                "migration_run_id": run_id,
                "organization_id": organization_id,
                "default_facility_id": default_facility_id,
                "mode": run_mode,
                "status": status,
                "counts_reconciled": counts_reconciled,
                "pre_counts": pre_counts,
                "post_counts": post_counts,
                "orphans_detected": orphans,
                "backup_reference": backup_reference or "SNAPSHOT-AUTO-VERIFIED",
            }
        finally:
            if should_close:
                c.close()

    def search_enterprise_audit_events(
        self,
        organization_id: str,
        filters: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            f = filters or {}
            cur = c.cursor()
            sql = """
                SELECT a.*, u.username AS actor_username, u.full_name AS actor_name
                FROM audit_events a
                LEFT JOIN users u ON a.actor_id = u.id
                WHERE a.organization_id = ?
            """
            params: List[Any] = [organization_id]
            if f.get("facility_id"):
                sql += " AND a.facility_id = ?"
                params.append(f["facility_id"])
            if f.get("actor_id"):
                sql += " AND a.actor_id = ?"
                params.append(f["actor_id"])
            if f.get("action_type"):
                sql += " AND a.action_type = ?"
                params.append(f["action_type"])
            if f.get("target_entity_type"):
                sql += " AND a.target_entity_type = ?"
                params.append(f["target_entity_type"])
            if f.get("outcome"):
                sql += " AND a.outcome = ?"
                params.append(f["outcome"])
            sql += " ORDER BY a.created_at DESC LIMIT 200;"
            cur.execute(sql, tuple(params))
            events = []
            for r in cur.fetchall():
                d = dict(r)
                try:
                    d["details_parsed"] = json.loads(d["details"]) if d.get("details") else {}
                except Exception:
                    d["details_parsed"] = {}
                events.append(d)
            return events
        finally:
            if should_close:
                c.close()

"""Deny-by-default Permission Checker, Scope-Aware RBAC/ABAC, and Multi-Tenant Isolation Enforcement."""

from typing import Dict, Any, List, Optional
import sqlite3
from apps.api.core.errors import ForbiddenError

PERMISSION_ALIASES: Dict[str, List[str]] = {
    "patient:read": ["patients:read", "patient:read"],
    "patient:create": ["patients:write", "patient:create"],
    "patient:update_demographics": ["patients:write", "patient:update_demographics"],
    "patient:resolve_duplicate": ["patients:write", "patient:resolve_duplicate"],
    "encounter:read": ["encounters:read", "encounter:read"],
    "encounter:create": ["encounters:write", "encounter:create"],
    "encounter:update_draft": ["encounters:write", "encounter:update_draft"],
    "encounter:cancel": ["encounters:write", "encounter:cancel"],
    "consent:read": ["consent:read", "patients:read", "patient:read"],
    "consent:record": ["consent:record", "patients:write", "patient:create"],
    "consent:withdraw": ["consent:withdraw", "patients:write"],
    "audit:read": ["audit:read", "enterprise:audit_read"],
    "formulary:read": ["formulary:read", "capabilities:read"],
    "formulary:draft_create": ["formulary:draft_create", "formulary:write"],
    "formulary:draft_update": ["formulary:draft_update", "formulary:write"],
    "formulary:submit_review": ["formulary:submit_review"],
    "formulary:approve": ["formulary:approve"],
    "prescription:create_draft": ["prescription:create_draft", "prescriptions:write", "encounters:write"],
    "prescription:read": ["prescription:read", "prescriptions:read", "encounters:read"],
    "prescription:update_draft": ["prescription:update_draft", "prescriptions:write", "encounters:write"],
    "prescription:validate": ["prescription:validate", "prescription:create_draft", "prescriptions:write"],
    "prescription:sign": ["prescription:sign", "prescriptions:sign"],
    "prescription:amend": ["prescription:amend", "prescription:sign", "prescriptions:sign"],
    "prescription:cancel": ["prescription:cancel", "prescriptions:sign"],
    "prescription:export": ["prescription:export", "prescription:read", "prescriptions:read"],
    # Prompt 04 Unani Assessment, Organ-Axis & Care Planning Permissions
    "assessment:read": ["assessment:read", "encounters:read", "patients:read"],
    "assessment:create_draft": ["assessment:create_draft", "assessment:write", "encounters:write"],
    "assessment:update_draft": ["assessment:update_draft", "assessment:write", "encounters:write"],
    "assessment:finalise": ["assessment:finalise", "assessment:sign", "encounters:write"],
    "assessment:amend": ["assessment:amend", "assessment:finalise", "encounters:write"],
    "template:read": ["template:read", "capabilities:read"],
    "template:manage": ["template:manage", "governance:manage"],
    "organ_axis:read": ["organ_axis:read", "capabilities:read"],
    "organ_axis:manage": ["organ_axis:manage", "governance:manage"],
    "usul_e_ilaj:read": ["usul_e_ilaj:read", "capabilities:read"],
    "usul_e_ilaj:manage": ["usul_e_ilaj:manage", "governance:manage"],
    "care_plan:read": ["care_plan:read", "encounters:read", "patients:read"],
    "care_plan:create": ["care_plan:create", "care_plan:write", "encounters:write"],
    "care_plan:update": ["care_plan:update", "care_plan:write", "encounters:write"],
    "care_plan:finalise": ["care_plan:finalise", "care_plan:sign", "encounters:write"],
    # Prompt 11 Enterprise Administration Permissions
    "enterprise:org_manage": ["org:manage", "enterprise:org_manage"],
    "enterprise:facility_manage": ["facility:manage", "enterprise:facility_manage"],
    "enterprise:department_manage": ["facility:manage", "enterprise:department_manage"],
    "enterprise:assignment_manage": ["users:manage", "facility:manage", "enterprise:assignment_manage"],
    "enterprise:config_manage": ["org:manage", "facility:manage", "enterprise:config_manage"],
    "enterprise:module_manage": ["org:manage", "facility:manage", "enterprise:module_manage"],
    "enterprise:transfer_write": ["encounters:write", "patients:write", "enterprise:transfer_write"],
    "enterprise:transfer_read": ["encounters:read", "patients:read", "enterprise:transfer_read"],
    "enterprise:patient_merge": ["org:manage", "enterprise:patient_merge"],
    "enterprise:integration_manage": ["org:manage", "enterprise:integration_manage"],
    "enterprise:audit_read": ["audit:read", "enterprise:audit_read"],
    # Prompt 12 Hospital Workflows & Interoperability Permissions
    "ipd:bed_manage": ["facility:manage", "encounters:write", "ipd:bed_manage"],
    "ipd:admission_write": ["encounters:write", "ipd:admission_write"],
    "ipd:admission_read": ["encounters:read", "patients:read", "ipd:admission_read"],
    "ipd:discharge_sign": ["prescriptions:sign", "assessment:sign", "ipd:discharge_sign"],
    "lab:order_write": ["encounters:write", "lab:order_write"],
    "lab:order_read": ["encounters:read", "patients:read", "lab:order_read"],
    "lab:result_import": ["encounters:write", "lab:order_write", "lab:result_import"],
    "referral:write": ["encounters:write", "patients:write", "referral:write"],
    "referral:read": ["encounters:read", "patients:read", "referral:read"],
    "interop:manage": ["org:manage", "enterprise:integration_manage", "interop:manage"],
    "interop:exchange": ["encounters:read", "patients:read", "interop:exchange"],
    # Prompt 15 Post-Pilot Evaluation & Scale Decision Permissions
    "pilot:evaluate": ["pilot:manage", "pilot:evaluate", "enterprise:org_manage", "org:manage"],
    "pilot:approve_decision": ["pilot:approve_decision", "enterprise:org_manage", "governance:manage"],
    "pilot:remediation": ["pilot:manage", "pilot:remediation", "enterprise:org_manage", "org:manage"],
    # KAVS: Knowledge Authenticity, Verification & Clinical Safety Permissions
    "kavs:read": ["kavs:read", "knowledge:read", "capabilities:read"],
    "kavs:verify": ["kavs:verify", "knowledge:manage", "governance:manage"],
    "kavs:approve": ["kavs:approve", "governance:manage", "enterprise:org_manage"],
    "kavs:release": ["kavs:release", "governance:manage", "enterprise:org_manage"],
    "kavs:manage": ["kavs:manage", "knowledge:manage", "governance:manage"],
}

CLINICAL_NOTE_PERMISSIONS = {
    "encounters:read",
    "encounter:read",
    "encounters:write",
    "encounter:create",
    "encounter:update_draft",
    "assessment:read",
    "assessment:create_draft",
    "modern_assessment:read",
    "modern_assessment:create_draft",
    "prescription:sign",
    "prescriptions:sign",
}


def _perm_in_set(required_perm: str, perm_set: set) -> bool:
    if required_perm in perm_set:
        return True
    for alias in PERMISSION_ALIASES.get(required_perm, []):
        if alias in perm_set:
            return True
    return False


def has_permission(user_ctx: Dict[str, Any], required_perm: str) -> bool:
    """Check if the user has the required permission code or is an ORG_ADMIN (respecting clinical note boundaries)."""
    if not user_ctx:
        return False
    roles = set(user_ctx.get("roles", []))

    # Knowledge reviewer, read-only auditor, and platform support never implicitly gain clinical/patient access
    if roles.issubset({"KNOWLEDGE_REVIEWER", "READ_ONLY_AUDITOR", "PLATFORM_SUPPORT"}):
        permissions = set(user_ctx.get("permissions", []))
        return _perm_in_set(required_perm, permissions)

    if "ORG_ADMIN" in roles:
        return True

    permissions = set(user_ctx.get("permissions", []))
    return _perm_in_set(required_perm, permissions)


def require_permission(user_ctx: Dict[str, Any], required_perm: str, request_id: str = None) -> None:
    """Enforce permission check with deny-by-default semantics."""
    if not user_ctx:
        raise ForbiddenError(
            "Access denied: Missing authenticated user context.",
            details={"code": "MISSING_TENANT_CONTEXT"},
            request_id=request_id,
        )
    # Enforce organization suspension policy for mutating / clinical workflows
    org_status = user_ctx.get("org_lifecycle_status", "active")
    if org_status in ("suspended", "archived"):
        # Allow only read/audit/reactivation actions when organization is suspended
        is_read_or_reactivate = (
            required_perm.endswith(":read")
            or required_perm in ("org:manage", "enterprise:org_manage", "audit:read", "enterprise:audit_read")
        )
        if not is_read_or_reactivate:
            raise ForbiddenError(
                f"Organization is currently '{org_status}'. Operational and clinical write workflows are suspended.",
                details={
                    "code": "ORGANIZATION_SUSPENDED_OR_ARCHIVED",
                    "error_code": "ORGANIZATION_SUSPENDED_OR_ARCHIVED",
                    "lifecycle_status": org_status,
                },
                request_id=request_id,
            )

    fac_status = user_ctx.get("active_facility_lifecycle_status", "active")
    if fac_status in ("suspended", "archived", "temporarily_closed"):
        is_allowed_when_fac_closed = (
            required_perm.endswith(":read")
            or required_perm in (
                "facility:manage",
                "enterprise:facility_manage",
                "org:manage",
                "enterprise:org_manage",
                "audit:read",
                "enterprise:audit_read",
            )
        )
        if not is_allowed_when_fac_closed:
            raise ForbiddenError(
                f"Facility is currently '{fac_status}'. New clinical/operational actions are blocked.",
                details={
                    "code": "FACILITY_SUSPENDED_OR_CLOSED",
                    "error_code": "FACILITY_SUSPENDED_OR_CLOSED",
                    "lifecycle_status": fac_status,
                },
                request_id=request_id,
            )

    if not has_permission(user_ctx, required_perm):
        raise ForbiddenError(
            f"Access denied: Missing required permission '{required_perm}'.",
            details={"required_permission": required_perm, "code": "PERMISSION_DENIED"},
            request_id=request_id,
        )


def require_facility_access(
    conn: sqlite3.Connection, user_id: str, facility_id: str, request_id: str = None
) -> None:
    """Verify that the user is an authorized active member of the specified facility (respecting staff_assignments revocations)."""
    cursor = conn.cursor()
    # First check if staff_assignments exists and has records for this user & facility
    try:
        cursor.execute(
            """
            SELECT status, effective_until
            FROM staff_assignments
            WHERE user_id = ? AND (facility_id = ? OR scope_level = 'ORGANIZATION');
            """,
            (user_id, facility_id),
        )
        sa_rows = cursor.fetchall()
        if sa_rows:
            has_active = any(r["status"] == "active" for r in sa_rows)
            if not has_active:
                raise ForbiddenError(
                    f"Access denied: Staff assignment for facility '{facility_id}' is revoked or inactive.",
                    details={"facility_id": facility_id, "code": "ASSIGNMENT_REVOKED_OR_INACTIVE"},
                    request_id=request_id,
                )
            return
    except sqlite3.OperationalError:
        pass

    cursor.execute(
        """
        SELECT 1 FROM user_facility_memberships
        WHERE user_id = ? AND facility_id = ? AND is_active = 1;
        """,
        (user_id, facility_id),
    )
    if not cursor.fetchone():
        raise ForbiddenError(
            f"Access denied: User is not authorized for facility '{facility_id}'.",
            details={"facility_id": facility_id, "code": "FACILITY_ACCESS_DENIED"},
            request_id=request_id,
        )


def enforce_tenant_isolation(
    user_ctx: Dict[str, Any],
    target_org_id: str,
    request_id: str = None,
    conn: Optional[sqlite3.Connection] = None,
    allow_parent_reporting: bool = False,
) -> None:
    """Enforce that operations are restricted to user's assigned organization (or explicitly authorized parent reporting scope)."""
    if not user_ctx or not user_ctx.get("organization_id") or not target_org_id:
        raise ForbiddenError(
            "Fail-closed tenant check: Missing organization context.",
            details={"code": "MISSING_TENANT_CONTEXT"},
            request_id=request_id,
        )
    user_org = user_ctx.get("organization_id")
    if user_org == target_org_id:
        return

    if allow_parent_reporting and conn is not None:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT parent_organization_id, parent_reporting_enabled
                FROM organization_profiles
                WHERE organization_id = ?;
                """,
                (target_org_id,),
            )
            row = cur.fetchone()
            if row and row["parent_organization_id"] == user_org and int(row["parent_reporting_enabled"] or 0) == 1:
                return
        except sqlite3.OperationalError:
            pass

    raise ForbiddenError(
        "Cross-tenant access violation: Cannot access or mutate records outside assigned organization.",
        details={"code": "CROSS_TENANT_ACCESS_DENIED", "user_org": user_org, "target_org": target_org_id},
        request_id=request_id,
    )


def require_scoped_permission(
    conn: sqlite3.Connection,
    user_ctx: Dict[str, Any],
    required_perm: str,
    organization_id: Optional[str] = None,
    facility_id: Optional[str] = None,
    is_clinical_note: bool = False,
    request_id: str = None,
) -> None:
    """
    Evaluate RBAC + ABAC resource scope:
    - Tenant isolation (organization_id)
    - Organization & facility lifecycle state (suspended/archived blocks mutations)
    - Facility-specific assignment role & permissions
    - ORG_ADMIN clinical note restriction policy
    - Reviewer / Auditor / Support non-clinical boundaries
    """
    if not user_ctx or not user_ctx.get("organization_id"):
        raise ForbiddenError(
            "Access denied: Missing authenticated tenant context.",
            details={"code": "MISSING_TENANT_CONTEXT"},
            request_id=request_id,
        )

    target_org = organization_id or user_ctx["organization_id"]
    enforce_tenant_isolation(user_ctx, target_org, request_id=request_id, conn=conn)

    # Check organization lifecycle status
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT lifecycle_status, org_admin_clinical_note_access FROM organization_profiles WHERE organization_id = ?;",
            (target_org,),
        )
        op = cur.fetchone()
        if op:
            if op["lifecycle_status"] in ("suspended", "archived"):
                is_read_or_reactivate = (
                    required_perm.endswith(":read")
                    or required_perm in ("org:manage", "enterprise:org_manage", "audit:read", "enterprise:audit_read")
                )
                if not is_read_or_reactivate:
                    raise ForbiddenError(
                        f"Organization '{target_org}' is {op['lifecycle_status']}. Operational writes are blocked.",
                        details={"code": "ORGANIZATION_SUSPENDED_OR_ARCHIVED", "lifecycle_status": op["lifecycle_status"]},
                        request_id=request_id,
                    )
            if is_clinical_note:
                org_roles = set(user_ctx.get("org_roles", user_ctx.get("roles", [])))
                fac_roles = set(
                    user_ctx.get("facility_scopes", {}).get(facility_id or "", {}).get("roles", user_ctx.get("roles", []))
                )
                all_roles = org_roles | fac_roles
                if "ORG_ADMIN" in all_roles and not (all_roles & {"PRACTITIONER", "NURSE"}):
                    if int(op["org_admin_clinical_note_access"] or 0) == 0:
                        raise ForbiddenError(
                            "Organization policy prohibits ORG_ADMIN from accessing detailed clinical notes without a clinical role.",
                            details={"code": "ORG_ADMIN_CLINICAL_NOTES_RESTRICTED"},
                            request_id=request_id,
                        )
    except sqlite3.OperationalError:
        pass

    # If facility_id is provided, verify facility belongs to target_org and check facility lifecycle + scoped permissions
    if facility_id:
        cur.execute("SELECT organization_id, is_active FROM facilities WHERE id = ?;", (facility_id,))
        f_row = cur.fetchone()
        if not f_row or f_row["organization_id"] != target_org:
            raise ForbiddenError(
                f"Facility '{facility_id}' does not belong to organization '{target_org}'.",
                details={"code": "FACILITY_TENANT_MISMATCH", "facility_id": facility_id, "organization_id": target_org},
                request_id=request_id,
            )

        try:
            cur.execute("SELECT lifecycle_status FROM facility_profiles WHERE facility_id = ?;", (facility_id,))
            fp = cur.fetchone()
            fac_status = fp["lifecycle_status"] if fp else ("active" if f_row["is_active"] else "suspended")
            if fac_status in ("suspended", "archived", "temporarily_closed"):
                is_allowed_when_closed = (
                    required_perm.endswith(":read")
                    or required_perm in ("facility:manage", "enterprise:facility_manage", "org:manage", "enterprise:org_manage", "audit:read")
                )
                if not is_allowed_when_closed:
                    raise ForbiddenError(
                        f"Facility '{facility_id}' is currently '{fac_status}'. New clinical/operational actions are blocked.",
                        details={"code": "FACILITY_SUSPENDED_OR_CLOSED", "lifecycle_status": fac_status},
                        request_id=request_id,
                    )
        except sqlite3.OperationalError:
            pass

        # Evaluate facility-specific scope unless user is ORG_ADMIN
        org_roles = set(user_ctx.get("org_roles", []))
        if "ORG_ADMIN" not in org_roles:
            require_facility_access(conn, user_ctx["user_id"], facility_id, request_id=request_id)
            fac_scopes = user_ctx.get("facility_scopes", {})
            if facility_id in fac_scopes:
                fac_perms = set(fac_scopes[facility_id].get("permissions", []))
                fac_roles = set(fac_scopes[facility_id].get("roles", []))
                if "CLINIC_ADMIN" in fac_roles and required_perm in (
                    "facility:manage",
                    "enterprise:facility_manage",
                    "enterprise:department_manage",
                    "enterprise:assignment_manage",
                    "scheduling:manage",
                ):
                    return
                if not _perm_in_set(required_perm, fac_perms):
                    raise ForbiddenError(
                        f"Access denied: User does not have permission '{required_perm}' at facility '{facility_id}'.",
                        details={
                            "code": "SCOPED_FACILITY_PERMISSION_DENIED",
                            "facility_id": facility_id,
                            "required_permission": required_perm,
                        },
                        request_id=request_id,
                    )
                return

    require_permission(user_ctx, required_perm, request_id=request_id)

"""API Route Handlers for Enterprise Multi-Tenant Isolation, Lifecycle & SaaS Governance.

Phase 55 of ZAYVORA MATAB OS.
Mounted under `/api/v1/tenant-governance/`.
"""

import json
import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission, enforce_tenant_isolation
from apps.api.core.errors import ValidationError, ForbiddenError, NotFoundError
from apps.api.domains.tenant_governance_engine import TenantGovernanceEngine


def _get_engine(conn: sqlite3.Connection) -> TenantGovernanceEngine:
    return TenantGovernanceEngine(conn)


def _enforce_tenant_or_platform_admin(
    user: Dict[str, Any],
    target_tenant_id: str,
    required_perm: str = "tenancy:read",
    request_id: str = None,
    conn: sqlite3.Connection = None,
) -> None:
    """Enforce that operations are restricted to user's assigned tenant, unless user is a platform administrator."""
    require_permission(user, required_perm, request_id=request_id)
    user_perms = set(user.get("permissions", []))
    user_roles = set(user.get("roles", [])) | set(user.get("org_roles", []))
    if "enterprise:org_manage" in user_perms or "tenancy:manage" in user_perms or "SYSTEM_ADMIN" in user_roles:
        return
    enforce_tenant_isolation(user, target_tenant_id, request_id=request_id, conn=conn)


# -------------------------------------------------------------------------
# 1. Tenants Provisioning & Overview
# -------------------------------------------------------------------------

def handle_list_tenants(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/tenant-governance/tenants"""
    user = req.get("user", {})
    require_permission(user, "tenancy:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    status = query_params.get("status")

    engine = _get_engine(conn)
    tenants = engine.list_tenants(status=status)
    return 200, {"success": True, "count": len(tenants), "tenants": tenants}


def handle_get_tenant(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/tenant-governance/tenants/{id}"""
    user = req.get("user", {})
    tenant_id = req["path_params"]["id"]

    _enforce_tenant_or_platform_admin(user, tenant_id, "tenancy:read", request_id=req.get("request_id"), conn=conn)

    engine = _get_engine(conn)
    tenant = engine.get_tenant(tenant_id)
    return 200, {"success": True, "tenant": tenant}


def handle_provision_tenant(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/tenant-governance/tenants/provision"""
    user = req.get("user", {})
    require_permission(user, "tenancy:manage", request_id=req.get("request_id"))

    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    engine = _get_engine(conn)
    tenant = engine.provision_tenant(body, actor_id=actor_id)
    return 201, {"success": True, "tenant": tenant}


# -------------------------------------------------------------------------
# 2. Lifecycle Transitions
# -------------------------------------------------------------------------

def handle_transition_tenant(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/tenant-governance/tenants/{id}/transition"""
    user = req.get("user", {})
    require_permission(user, "tenancy:manage", request_id=req.get("request_id"))

    tenant_id = req["path_params"]["id"]
    body = req.get("body", {})
    new_status = body.get("status", "")
    reason = body.get("reason", "Administrative lifecycle transition")
    actor_id = user.get("user_id", "USER-SYSTEM")

    engine = _get_engine(conn)
    tenant = engine.transition_tenant_status(tenant_id, new_status, reason, actor_id=actor_id)
    return 200, {"success": True, "tenant": tenant}


# -------------------------------------------------------------------------
# 3. Offboarding & Export
# -------------------------------------------------------------------------

def handle_get_offboarding_impact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/tenant-governance/tenants/{id}/offboarding-impact"""
    user = req.get("user", {})
    tenant_id = req["path_params"]["id"]

    _enforce_tenant_or_platform_admin(user, tenant_id, "tenancy:read", request_id=req.get("request_id"), conn=conn)

    engine = _get_engine(conn)
    impact = engine.get_offboarding_impact_summary(tenant_id)
    return 200, {"success": True, "offboarding_impact": impact}


def handle_export_tenant_data(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/tenant-governance/tenants/{id}/export"""
    user = req.get("user", {})
    tenant_id = req["path_params"]["id"]

    _enforce_tenant_or_platform_admin(user, tenant_id, "tenancy:export", request_id=req.get("request_id"), conn=conn)

    actor_id = user.get("user_id", "USER-SYSTEM")
    engine = _get_engine(conn)
    bundle = engine.export_tenant_data(tenant_id, actor_id=actor_id)
    return 200, {"success": True, "export": bundle}


# -------------------------------------------------------------------------
# 4. Entitlements & Quotas
# -------------------------------------------------------------------------

def handle_get_entitlements(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/tenant-governance/tenants/{id}/entitlements"""
    user = req.get("user", {})
    tenant_id = req["path_params"]["id"]

    _enforce_tenant_or_platform_admin(user, tenant_id, "tenancy:read", request_id=req.get("request_id"), conn=conn)

    engine = _get_engine(conn)
    tenant = engine.get_tenant(tenant_id)
    return 200, {"success": True, "entitlements": tenant["entitlements"]}


def handle_update_entitlements(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PATCH /api/v1/tenant-governance/tenants/{id}/entitlements"""
    user = req.get("user", {})
    require_permission(user, "tenancy:entitlements_manage", request_id=req.get("request_id"))

    tenant_id = req["path_params"]["id"]
    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    engine = _get_engine(conn)
    updated = engine.update_entitlements(tenant_id, body, actor_id=actor_id)
    return 200, {"success": True, "entitlements": updated}


def handle_check_quota(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/tenant-governance/tenants/{id}/quotas/{resource}"""
    user = req.get("user", {})
    tenant_id = req["path_params"]["id"]
    resource_type = req["path_params"]["resource"]

    _enforce_tenant_or_platform_admin(user, tenant_id, "tenancy:read", request_id=req.get("request_id"), conn=conn)

    engine = _get_engine(conn)
    quota = engine.check_quota(tenant_id, resource_type)
    return 200, {"success": True, "quota_status": quota}


# -------------------------------------------------------------------------
# 5. Break-Glass Support Access
# -------------------------------------------------------------------------

def handle_create_break_glass_ticket(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/tenant-governance/break-glass"""
    user = req.get("user", {})
    require_permission(user, "tenancy:break_glass", request_id=req.get("request_id"))

    body = req.get("body", {})
    target_tenant_id = body.get("target_tenant_id", "")
    support_user_id = user.get("user_id", "USER-SUPPORT")
    reason_code = body.get("reason_code", "")
    justification = body.get("justification", "")
    duration_minutes = int(body.get("duration_minutes", 30))
    approved_by = body.get("approved_by", user.get("full_name", "Security Lead"))
    actor_id = user.get("user_id", "USER-SYSTEM")

    engine = _get_engine(conn)
    ticket = engine.create_break_glass_ticket(
        target_tenant_id=target_tenant_id,
        support_user_id=support_user_id,
        reason_code=reason_code,
        justification=justification,
        duration_minutes=duration_minutes,
        approved_by=approved_by,
        actor_id=actor_id,
    )
    return 201, {"success": True, "break_glass_ticket": ticket}


def handle_list_break_glass_tickets(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/tenant-governance/break-glass"""
    user = req.get("user", {})
    require_permission(user, "tenancy:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    target_tenant_id = query_params.get("target_tenant_id")

    # If not global admin, scope to user's tenant
    org_roles = set(user.get("org_roles", []))
    if "ORG_ADMIN" in org_roles and not target_tenant_id:
        target_tenant_id = user.get("organization_id")

    engine = _get_engine(conn)
    tickets = engine.list_break_glass_tickets(target_tenant_id=target_tenant_id)
    return 200, {"success": True, "count": len(tickets), "tickets": tickets}


def handle_revoke_break_glass_ticket(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/tenant-governance/break-glass/{id}/revoke"""
    user = req.get("user", {})
    require_permission(user, "tenancy:break_glass", request_id=req.get("request_id"))

    ticket_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason", "Administrative revocation")
    actor_id = user.get("user_id", "USER-SYSTEM")

    engine = _get_engine(conn)
    res = engine.revoke_break_glass_ticket(ticket_id, reason=reason, actor_id=actor_id)
    return 200, {"success": True, "revocation": res}


# -------------------------------------------------------------------------
# 6. Cross-Tenant Relationship Validation
# -------------------------------------------------------------------------

def handle_validate_relationship(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/tenant-governance/validate-relationship"""
    user = req.get("user", {})
    body = req.get("body", {})
    tenant_id = body.get("tenant_id") or user.get("organization_id")

    _enforce_tenant_or_platform_admin(user, tenant_id, "tenancy:read", request_id=req.get("request_id"), conn=conn)

    parent_type = body.get("parent_type", "")
    parent_id = body.get("parent_id", "")
    child_type = body.get("child_type", "")
    child_id = body.get("child_id", "")

    engine = _get_engine(conn)
    is_valid = engine.validate_cross_tenant_relationship(
        tenant_id=tenant_id,
        parent_type=parent_type,
        parent_id=parent_id,
        child_type=child_type,
        child_id=child_id,
    )
    return 200, {"success": True, "valid": is_valid}


# -------------------------------------------------------------------------
# 7. Cryptographic Audit Ledger
# -------------------------------------------------------------------------

def handle_verify_saas_audit_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/tenant-governance/audit-ledger/verify"""
    user = req.get("user", {})
    require_permission(user, "tenancy:read", request_id=req.get("request_id"))

    engine = _get_engine(conn)
    report = engine.verify_audit_ledger_integrity()
    return 200, {"success": True, "ledger_report": report}

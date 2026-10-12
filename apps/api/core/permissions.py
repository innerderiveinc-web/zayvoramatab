"""Deny-by-default Permission Checker and Multi-Tenant Isolation Enforcement."""

from typing import Dict, Any, List
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
    "audit:read": ["audit:read"],
}

def has_permission(user_ctx: Dict[str, Any], required_perm: str) -> bool:
    """Check if the user has the required permission code or is an ORG_ADMIN."""
    roles = user_ctx.get("roles", [])
    if "ORG_ADMIN" in roles:
        return True
    permissions = set(user_ctx.get("permissions", []))
    if required_perm in permissions:
        return True
    aliases = PERMISSION_ALIASES.get(required_perm, [])
    for alias in aliases:
        if alias in permissions:
            return True
    return False

def require_permission(user_ctx: Dict[str, Any], required_perm: str, request_id: str = None) -> None:
    """Enforce permission check with deny-by-default semantics."""
    if not has_permission(user_ctx, required_perm):
        raise ForbiddenError(
            f"Access denied: Missing required permission '{required_perm}'.",
            details={"required_permission": required_perm},
            request_id=request_id
        )

def require_facility_access(conn: sqlite3.Connection, user_id: str, facility_id: str, request_id: str = None) -> None:
    """Verify that the user is an authorized active member of the specified facility."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM user_facility_memberships
        WHERE user_id = ? AND facility_id = ? AND is_active = 1;
    """, (user_id, facility_id))
    if not cursor.fetchone():
        raise ForbiddenError(
            f"Access denied: User is not authorized for facility '{facility_id}'.",
            details={"facility_id": facility_id},
            request_id=request_id
        )

def enforce_tenant_isolation(user_ctx: Dict[str, Any], target_org_id: str, request_id: str = None) -> None:
    """Enforce that operations are restricted to user's assigned organization."""
    if user_ctx.get("organization_id") != target_org_id:
        raise ForbiddenError(
            "Cross-tenant access violation: Cannot access or mutate records outside assigned organization.",
            details={"user_org": user_ctx.get("organization_id"), "target_org": target_org_id},
            request_id=request_id
        )

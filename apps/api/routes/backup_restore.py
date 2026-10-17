"""API Route Handlers for Enterprise Backup, Disaster Recovery & Verified Restore Engine.

Phase 56 of ZAYVORA MATAB OS.
Mounted under `/api/v1/dr/`.
"""

import json
import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission, enforce_tenant_isolation
from apps.api.core.errors import ValidationError, ForbiddenError, NotFoundError
from apps.api.domains.backup_restore_engine import BackupRestoreEngine


def _get_engine(conn: sqlite3.Connection) -> BackupRestoreEngine:
    return BackupRestoreEngine(conn)


def _resolve_tenant_id(user: Dict[str, Any], requested_org_id: str = None) -> str:
    """Resolve and validate organization_id enforcing multi-tenant isolation."""
    user_perms = set(user.get("permissions", []))
    user_roles = set(user.get("roles", [])) | set(user.get("org_roles", []))
    is_platform_admin = (
        "enterprise:org_manage" in user_perms
        or "tenancy:manage" in user_perms
        or "SYSTEM_ADMIN" in user_roles
        or "SUPER_ADMIN" in user_roles
    )

    user_org_id = user.get("organization_id") or "ORG-DEFAULT"
    target_org_id = requested_org_id or user_org_id

    if not is_platform_admin and target_org_id != user_org_id:
        raise ForbiddenError(f"Cross-tenant access forbidden: Cannot operate on organization '{target_org_id}'.")
    return target_org_id


# -------------------------------------------------------------------------
# 1. Coordinated Multi-Component Backups
# -------------------------------------------------------------------------

def handle_create_coordinated_backup(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/coordinated-backups - Create coordinated snapshot with signed manifest."""
    user = req.get("user", {})
    require_permission(user, "dr:backup", request_id=req.get("request_id"))

    body = req.get("body", {})
    org_id = _resolve_tenant_id(user, body.get("organization_id"))
    backup_type = body.get("backup_type", "full")
    scope = body.get("scope", "database_all")
    retention_tier = body.get("retention_tier", "30_days_standard")
    immutable_lock_days = int(body.get("immutable_lock_days", 0))
    attachments_dir = body.get("attachments_dir")
    custom_backup_dir = body.get("custom_backup_dir")
    user_id = user.get("id") or user.get("user_id") or "SYSTEM"

    engine = _get_engine(conn)
    result = engine.create_coordinated_backup(
        organization_id=org_id,
        backup_type=backup_type,
        scope=scope,
        user_id=user_id,
        retention_tier=retention_tier,
        immutable_lock_days=immutable_lock_days,
        attachments_dir=attachments_dir,
        custom_backup_dir=custom_backup_dir,
    )
    return 201, {"success": True, "backup": result}


def handle_list_coordinated_backups(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/coordinated-backups - List backups with signed manifest metadata."""
    user = req.get("user", {})
    require_permission(user, "dr:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    org_id = _resolve_tenant_id(user, query_params.get("organization_id"))
    limit = int(query_params.get("limit", 50))

    engine = _get_engine(conn)
    backups = engine.list_backups(organization_id=org_id, limit=limit)
    return 200, {"success": True, "count": len(backups), "backups": backups}


def handle_get_coordinated_backup(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/coordinated-backups/{id} - Get backup details and manifest."""
    user = req.get("user", {})
    require_permission(user, "dr:read", request_id=req.get("request_id"))

    backup_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    backup = engine.get_backup(backup_id)
    _resolve_tenant_id(user, backup.get("organization_id"))
    return 200, {"success": True, "backup": backup}


def handle_verify_backup_manifest(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/coordinated-backups/{id}/verify - Validate cryptographic checksum and signature."""
    user = req.get("user", {})
    require_permission(user, "dr:read", request_id=req.get("request_id"))

    backup_id = req["path_params"]["id"]
    actor_id = user.get("id") or user.get("user_id") or "SYSTEM"

    engine = _get_engine(conn)
    backup = engine.get_backup(backup_id)
    _resolve_tenant_id(user, backup.get("organization_id"))

    verification = engine.verify_backup_manifest(backup_id=backup_id, actor_id=actor_id)
    status_code = 200 if verification.get("verified") else 422
    return status_code, {"success": verification.get("verified", False), "verification": verification}


# -------------------------------------------------------------------------
# 2. Point-in-Time Recovery (PITR) Markers
# -------------------------------------------------------------------------

def handle_record_pitr_marker(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/pitr-markers - Record PITR checkpoint marker with WAL flush."""
    user = req.get("user", {})
    require_permission(user, "dr:backup", request_id=req.get("request_id"))

    body = req.get("body", {})
    org_id = _resolve_tenant_id(user, body.get("organization_id"))
    marker_label = body.get("marker_label")
    if not marker_label:
        raise ValidationError("Missing mandatory parameter 'marker_label'.")
    canary_payload = body.get("canary_payload", {})

    engine = _get_engine(conn)
    marker = engine.record_pitr_marker(
        organization_id=org_id,
        marker_label=marker_label,
        canary_payload=canary_payload,
    )
    return 201, {"success": True, "marker": marker}


def handle_list_pitr_markers(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/pitr-markers - List historical PITR markers."""
    user = req.get("user", {})
    require_permission(user, "dr:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    org_id = _resolve_tenant_id(user, query_params.get("organization_id"))
    limit = int(query_params.get("limit", 50))

    engine = _get_engine(conn)
    markers = engine.list_pitr_markers(organization_id=org_id, limit=limit)
    return 200, {"success": True, "count": len(markers), "markers": markers}


# -------------------------------------------------------------------------
# 3. Verified Restore Drills & Verification Engine
# -------------------------------------------------------------------------

def handle_execute_verified_restore_drill(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/verified-restore-drills - Run 7-phase isolated restore drill."""
    user = req.get("user", {})
    require_permission(user, "dr:drill", request_id=req.get("request_id"))

    body = req.get("body", {})
    backup_id = body.get("backup_id")
    if not backup_id:
        raise ValidationError("Missing mandatory parameter 'backup_id'.")

    org_id = _resolve_tenant_id(user, body.get("organization_id"))
    target_environment = body.get("target_environment", "isolated_test_sandbox")
    purpose = body.get("purpose", "Routine Enterprise DR Verification Drill")
    target_pitr_marker = body.get("target_pitr_marker")
    requested_by = user.get("id") or user.get("user_id") or "SYSTEM"
    authorized_by = body.get("authorized_by") or user.get("role") or "SECURITY_OFFICER"

    engine = _get_engine(conn)
    drill_report = engine.execute_verified_restore_drill(
        backup_id=backup_id,
        organization_id=org_id,
        target_environment=target_environment,
        requested_by=requested_by,
        authorized_by=authorized_by,
        purpose=purpose,
        target_pitr_marker=target_pitr_marker,
    )
    return 201, {"success": True, "drill_report": drill_report}


def handle_list_restore_drills(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/verified-restore-drills - List restore drill executions and verifications."""
    user = req.get("user", {})
    require_permission(user, "dr:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    org_id = _resolve_tenant_id(user, query_params.get("organization_id"))
    limit = int(query_params.get("limit", 50))

    engine = _get_engine(conn)
    drills = engine.list_drills(organization_id=org_id, limit=limit)
    return 200, {"success": True, "count": len(drills), "drills": drills}


def handle_get_restore_drill(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/verified-restore-drills/{id} - Get granular drill details."""
    user = req.get("user", {})
    require_permission(user, "dr:read", request_id=req.get("request_id"))

    verification_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    drill = engine.get_drill(verification_id)
    _resolve_tenant_id(user, drill.get("organization_id"))
    return 200, {"success": True, "drill": drill}


def handle_evaluate_promotion_gate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/verified-restore-drills/{id}/promotion-gate - Authorize or reject restore promotion."""
    user = req.get("user", {})
    require_permission(user, "dr:manage", request_id=req.get("request_id"))

    verification_id = req["path_params"]["id"]
    body = req.get("body", {})
    decision = body.get("decision")
    notes = body.get("notes", "Evaluated via DR Promotion Gate API")
    promoted_by = user.get("id") or user.get("user_id") or "SECURITY_OFFICER"

    engine = _get_engine(conn)
    result = engine.evaluate_promotion_gate(
        verification_id=verification_id,
        decision=decision,
        promoted_by=promoted_by,
        notes=notes,
    )
    return 200, {"success": True, "promotion": result}


# -------------------------------------------------------------------------
# 4. Retention Lifecycle & Immutability Management
# -------------------------------------------------------------------------

def handle_retention_cleanup(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/retention/cleanup - Audit and purge expired non-locked backups."""
    user = req.get("user", {})
    require_permission(user, "dr:manage", request_id=req.get("request_id"))

    body = req.get("body", {})
    org_id = _resolve_tenant_id(user, body.get("organization_id"))
    dry_run = body.get("dry_run", True)

    engine = _get_engine(conn)
    cleanup_summary = engine.manage_retention_and_cleanup(organization_id=org_id, dry_run=dry_run)
    return 200, {"success": True, "cleanup": cleanup_summary}


# -------------------------------------------------------------------------
# 5. Cryptographic Governance Audit Ledger Integrity
# -------------------------------------------------------------------------

def handle_verify_governance_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/ledger/verify - Cryptographic SHA-256 blockchain verification."""
    user = req.get("user", {})
    require_permission(user, "dr:read", request_id=req.get("request_id"))

    engine = _get_engine(conn)
    integrity = engine.verify_governance_ledger_integrity()
    return 200, {"success": integrity.get("verified", False), "ledger_integrity": integrity}

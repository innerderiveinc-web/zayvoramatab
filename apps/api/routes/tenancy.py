"""Organization and Facility Multi-Tenant Routing."""

import uuid
from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.errors import NotFoundError, ValidationError, ForbiddenError
from apps.api.core.permissions import require_permission, enforce_tenant_isolation
from apps.api.core.audit import log_audit_event

def handle_organizations_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    cursor = conn.cursor()
    # Users only see their assigned organization
    cursor.execute("""
        SELECT id, name, code, license_number, profile_type, is_active, created_at
        FROM organizations
        WHERE id = ?;
    """, (user["organization_id"],))
    orgs = [dict(r) for r in cursor.fetchall()]
    return 200, {"organizations": orgs, "request_id": req.get("request_id")}

def handle_facilities_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_id, name, code, address, phone, is_active, created_at
        FROM facilities
        WHERE organization_id = ?
        ORDER BY name ASC;
    """, (user["organization_id"],))
    facilities = [dict(r) for r in cursor.fetchall()]
    return 200, {"facilities": facilities, "request_id": req.get("request_id")}

def handle_facilities_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    request_id = req.get("request_id")
    require_permission(user, "facility:manage", request_id=request_id)
    
    body = req.get("body", {})
    name = body.get("name", "").strip()
    code = body.get("code", "").strip()

    if not name or not code:
        raise ValidationError("Facility name and code are required.", request_id=request_id)

    facility_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO facilities (id, organization_id, name, code, address, phone, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1);
    """, (
        facility_id,
        user["organization_id"],
        name,
        code,
        body.get("address", ""),
        body.get("phone", "")
    ))

    log_audit_event(
        conn=conn,
        action_type="FACILITY_CREATED",
        target_entity_type="FACILITY",
        target_entity_id=facility_id,
        organization_id=user["organization_id"],
        facility_id=facility_id,
        actor_id=user["user_id"],
        outcome="SUCCESS",
        request_id=request_id,
        client_ip=req.get("client_ip"),
        details={"facility_name": name, "facility_code": code}
    )

    return 201, {
        "facility": {
            "id": facility_id,
            "organization_id": user["organization_id"],
            "name": name,
            "code": code
        },
        "request_id": request_id
    }

def handle_facility_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    facility_id = req["path_params"]["id"]
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_id, name, code, address, phone, is_active, created_at
        FROM facilities
        WHERE id = ?;
    """, (facility_id,))
    row = cursor.fetchone()

    if not row:
        raise NotFoundError(f"Facility '{facility_id}' not found.", request_id=req.get("request_id"))

    # Strictly enforce tenant isolation: cannot read foreign facility
    enforce_tenant_isolation(user, row["organization_id"], request_id=req.get("request_id"))

    return 200, {"facility": dict(row), "request_id": req.get("request_id")}

"""User, Role, and Permission Administration Routes."""

import uuid
from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.errors import NotFoundError, ValidationError, ForbiddenError, ConflictError
from apps.api.core.permissions import require_permission, enforce_tenant_isolation
from apps.api.core.security import hash_password
from apps.api.core.audit import log_audit_event

def handle_users_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    request_id = req.get("request_id")
    require_permission(user, "users:manage", request_id=request_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.organization_id, u.username, u.email, u.full_name, u.is_active, u.created_at,
               r.code as role_code, r.name as role_name
        FROM users u
        LEFT JOIN user_organization_memberships uom ON u.id = uom.user_id AND uom.organization_id = u.organization_id
        LEFT JOIN roles r ON uom.role_id = r.id
        WHERE u.organization_id = ?
        ORDER BY u.created_at DESC;
    """, (user["organization_id"],))
    users = [dict(r) for r in cursor.fetchall()]
    return 200, {"users": users, "request_id": request_id}

def handle_users_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    request_id = req.get("request_id")
    require_permission(user, "users:manage", request_id=request_id)

    body = req.get("body", {})
    username = body.get("username", "").strip()
    password = body.get("password", "")
    full_name = body.get("full_name", "").strip()
    role_code = body.get("role_code", "RECEPTIONIST").strip()

    if not username or not password or not full_name:
        raise ValidationError("Username, password, and full name are required.", request_id=request_id)

    cursor = conn.cursor()
    # Check if username exists
    cursor.execute("SELECT id FROM users WHERE username = ?;", (username,))
    if cursor.fetchone():
        raise ConflictError(f"Username '{username}' already exists.", request_id=request_id)

    # Resolve role ID
    cursor.execute("SELECT id FROM roles WHERE code = ?;", (role_code,))
    r_row = cursor.fetchone()
    if not r_row:
        raise ValidationError(f"Invalid role code '{role_code}'.", request_id=request_id)
    role_id = r_row["id"]

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(password)

    conn.execute("""
        INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
        VALUES (?, ?, ?, ?, ?, ?, 1);
    """, (user_id, user["organization_id"], username, body.get("email"), pw_hash, full_name))

    conn.execute("""
        INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
        VALUES (?, ?, ?, ?, 1);
    """, (str(uuid.uuid4()), user_id, user["organization_id"], role_id))

    fac_id = body.get("facility_id") or user.get("active_facility_id")
    if fac_id:
        conn.execute("""
            INSERT OR IGNORE INTO user_facility_memberships (id, user_id, facility_id, role_id, is_active)
            VALUES (?, ?, ?, ?, 1);
        """, (str(uuid.uuid4()), user_id, fac_id, role_id))

    log_audit_event(
        conn=conn,
        action_type="USER_CREATED",
        target_entity_type="USER",
        target_entity_id=user_id,
        organization_id=user["organization_id"],
        actor_id=user["user_id"],
        outcome="SUCCESS",
        request_id=request_id,
        client_ip=req.get("client_ip"),
        details={"username": username, "role_code": role_code}
    )

    return 201, {
        "user": {
            "id": user_id,
            "username": username,
            "full_name": full_name,
            "role_code": role_code
        },
        "request_id": request_id
    }

def handle_roles_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, name, description, is_system_role FROM roles ORDER BY code ASC;")
    roles = [dict(r) for r in cursor.fetchall()]
    return 200, {"roles": roles, "request_id": req.get("request_id")}

def handle_permissions_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT id, code, name, category, description FROM permissions ORDER BY category, code ASC;")
    perms = [dict(r) for r in cursor.fetchall()]
    return 200, {"permissions": perms, "request_id": req.get("request_id")}

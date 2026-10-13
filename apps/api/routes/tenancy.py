"""Organization and Facility Multi-Tenant Routing."""

import uuid
from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.errors import NotFoundError, ValidationError, ForbiddenError
from apps.api.core.permissions import require_permission, enforce_tenant_isolation
from apps.api.core.audit import log_audit_event
from apps.api.domains.enterprise_admin import EnterpriseAdminService


def handle_organizations_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    svc = EnterpriseAdminService(db_path=req.get("db_path"))
    orgs = svc.list_organizations(user, conn=conn)
    return 200, {"organizations": orgs, "request_id": req.get("request_id")}


def handle_facilities_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    svc = EnterpriseAdminService(db_path=req.get("db_path"))
    facilities = svc.list_facilities(user["organization_id"], conn=conn)
    return 200, {"facilities": facilities, "request_id": req.get("request_id")}


def handle_facilities_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    request_id = req.get("request_id")
    require_permission(user, "facility:manage", request_id=request_id)

    svc = EnterpriseAdminService(db_path=req.get("db_path"))
    fac = svc.create_facility(user["organization_id"], user["user_id"], req.get("body", {}), conn=conn)
    return 201, {"facility": fac, "request_id": request_id}


def handle_facility_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    facility_id = req["path_params"]["id"]
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, organization_id, name, code, address, phone, is_active, created_at
        FROM facilities
        WHERE id = ?;
        """,
        (facility_id,),
    )
    row = cursor.fetchone()

    if not row:
        raise NotFoundError(f"Facility '{facility_id}' not found.", request_id=req.get("request_id"))

    # Strictly enforce tenant isolation: cannot read foreign facility
    enforce_tenant_isolation(user, row["organization_id"], request_id=req.get("request_id"), conn=conn)

    svc = EnterpriseAdminService(db_path=req.get("db_path"))
    fac = svc.get_facility(row["organization_id"], facility_id, conn=conn)
    return 200, {"facility": fac, "request_id": req.get("request_id")}

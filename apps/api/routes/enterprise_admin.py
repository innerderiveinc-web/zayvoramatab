"""Phase 11 REST Routes: Multi-Doctor, Multi-Branch & Hospital Administration Foundation."""

import sqlite3
from typing import Any, Dict, Tuple

from apps.api.core.permissions import (
    enforce_tenant_isolation,
    require_permission,
    require_scoped_permission,
)
from apps.api.domains.enterprise_admin import EnterpriseAdminService


def _svc(req: Dict[str, Any] = None) -> EnterpriseAdminService:
    db_path = req.get("db_path") if req else None
    return EnterpriseAdminService(db_path=db_path)


def _ctx(req: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, str, str]:
    user = req["user"]
    org_id = user["organization_id"]
    fac_id = user.get("active_facility_id") or "fac-central-opd"
    actor_id = user["user_id"]
    request_id = req.get("request_id")
    return user, org_id, fac_id, actor_id, request_id


# =========================================================================
# 1. Organizations & Lifecycle
# =========================================================================

def handle_organization_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:org_manage", request_id=request_id)
    org = _svc(req).create_organization(actor_id, req.get("body", {}), conn=conn)
    return 201, {"organization": org, "request_id": request_id}


def handle_organization_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    target_org_id = req["path_params"]["organization_id"]
    enforce_tenant_isolation(user, target_org_id, request_id=request_id, conn=conn, allow_parent_reporting=True)
    org = _svc(req).get_organization(target_org_id, conn=conn)
    return 200, {"organization": org, "request_id": request_id}


def handle_organization_update(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    target_org_id = req["path_params"]["organization_id"]
    enforce_tenant_isolation(user, target_org_id, request_id=request_id, conn=conn)
    require_permission(user, "enterprise:org_manage", request_id=request_id)
    org = _svc(req).update_organization(target_org_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"organization": org, "request_id": request_id}


def handle_organization_suspend(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    target_org_id = req["path_params"]["organization_id"]
    enforce_tenant_isolation(user, target_org_id, request_id=request_id, conn=conn)
    require_permission(user, "enterprise:org_manage", request_id=request_id)
    body = req.get("body", {})
    target_status = body.get("target_status", "suspended")
    org = _svc(req).transition_organization_lifecycle(
        target_org_id, target_status, actor_id, body.get("reason", ""), conn=conn
    )
    return 200, {"organization": org, "request_id": request_id}


def handle_organization_reactivate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    target_org_id = req["path_params"]["organization_id"]
    enforce_tenant_isolation(user, target_org_id, request_id=request_id, conn=conn)
    require_permission(user, "enterprise:org_manage", request_id=request_id)
    body = req.get("body", {})
    org = _svc(req).transition_organization_lifecycle(
        target_org_id, "active", actor_id, body.get("reason", "Organization reactivated"), conn=conn
    )
    return 200, {"organization": org, "request_id": request_id}


# =========================================================================
# 2. Facilities & Lifecycle
# =========================================================================

def handle_facility_update(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:facility_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    fac = _svc(req).update_facility(org_id, facility_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"facility": fac, "request_id": request_id}


def handle_facility_activation_check(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:facility_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    hc = _svc(req).run_facility_activation_health_check(org_id, facility_id, conn=conn)
    return 200, {"health_check": hc, "request_id": request_id}


def handle_facility_suspend(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:facility_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    body = req.get("body", {})
    target_status = body.get("target_status", "suspended")
    fac = _svc(req).transition_facility_lifecycle(
        org_id,
        facility_id,
        target_status,
        actor_id,
        body.get("reason", ""),
        cancel_booked_appointments=bool(body.get("cancel_booked_appointments", False)),
        conn=conn,
    )
    return 200, {"facility": fac, "request_id": request_id}


def handle_facility_reactivate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:facility_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    body = req.get("body", {})
    fac = _svc(req).transition_facility_lifecycle(
        org_id, facility_id, "active", actor_id, body.get("reason", "Facility reactivated"), conn=conn
    )
    return 200, {"facility": fac, "request_id": request_id}


# =========================================================================
# 3. Departments & Scoped Staff Assignments
# =========================================================================

def handle_department_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:department_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    dept = _svc(req).create_department(org_id, facility_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"department": dept, "request_id": request_id}


def handle_departments_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    enforce_tenant_isolation(user, org_id, request_id=request_id, conn=conn)
    depts = _svc(req).list_departments(org_id, facility_id, conn=conn)
    return 200, {"departments": depts, "request_id": request_id}


def handle_organization_membership_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    target_org_id = req["path_params"]["organization_id"]
    enforce_tenant_isolation(user, target_org_id, request_id=request_id, conn=conn)
    require_permission(user, "enterprise:assignment_manage", request_id=request_id)
    mem = _svc(req).create_organization_membership(target_org_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"membership": mem, "request_id": request_id}


def handle_staff_assignment_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:assignment_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    sa = _svc(req).create_staff_assignment(org_id, facility_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"assignment": sa, "request_id": request_id}


def handle_staff_assignments_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    facility_id = req["path_params"].get("facility_id")
    require_scoped_permission(
        conn, user, "enterprise:assignment_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    qp = req.get("query_params", {})
    assignments = _svc(req).list_staff_assignments(
        org_id, facility_id=facility_id or qp.get("facility_id"), user_id=qp.get("user_id"), conn=conn
    )
    return 200, {"assignments": assignments, "request_id": request_id}


def handle_staff_assignment_revoke(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    assignment_id = req["path_params"]["assignment_id"]
    require_permission(user, "enterprise:assignment_manage", request_id=request_id)
    reason = req.get("body", {}).get("reason", "Assignment revoked by administrator")
    sa = _svc(req).revoke_staff_assignment(org_id, assignment_id, actor_id, reason, conn=conn)
    return 200, {"assignment": sa, "request_id": request_id}


# =========================================================================
# 4. Cross-Facility Patient Continuity & Governed Merge
# =========================================================================

def handle_patient_facility_link_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, active_fac_id, actor_id, request_id = _ctx(req)
    patient_id = req["path_params"]["patient_id"]
    body = req.get("body", {})
    facility_id = body.get("facility_id") or active_fac_id
    require_scoped_permission(
        conn, user, "patient:create", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    link = _svc(req).link_patient_to_facility(org_id, patient_id, facility_id, actor_id, body, conn=conn)
    return 201, {"facility_link": link, "request_id": request_id}


def handle_patient_cross_facility_continuity_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, active_fac_id, _, request_id = _ctx(req)
    patient_id = req["path_params"]["patient_id"]
    qp = req.get("query_params", {})
    req_fac = qp.get("facility_id") or active_fac_id
    require_scoped_permission(
        conn, user, "patient:read", organization_id=org_id, facility_id=req_fac, request_id=request_id
    )
    summary = _svc(req).get_patient_cross_facility_continuity(org_id, req_fac, patient_id, user, conn=conn)
    return 200, {"continuity": summary, "request_id": request_id}


def handle_patient_merge_request_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "patient:resolve_duplicate", request_id=request_id)
    pmr = _svc(req).create_patient_merge_request(org_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"merge_request": pmr, "request_id": request_id}


def handle_patient_merge_request_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:patient_merge", request_id=request_id)
    merge_id = req["path_params"]["merge_request_id"]
    pmr = _svc(req).review_patient_merge_request(org_id, merge_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"merge_request": pmr, "request_id": request_id}


# =========================================================================
# 5. Inter-Facility Transfers & Referrals
# =========================================================================

def handle_transfer_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, active_fac_id, actor_id, request_id = _ctx(req)
    body = req.get("body", {})
    orig_fac_id = body.get("originating_facility_id") or active_fac_id
    require_scoped_permission(
        conn, user, "enterprise:transfer_write", organization_id=org_id, facility_id=orig_fac_id, request_id=request_id
    )
    trf = _svc(req).create_transfer(org_id, actor_id, user, body, conn=conn)
    return 201, {"transfer": trf, "request_id": request_id}


def handle_transfers_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    require_permission(user, "enterprise:transfer_read", request_id=request_id)
    transfers = _svc(req).list_transfers(org_id, filters=req.get("query_params", {}), user_ctx=user, conn=conn)
    return 200, {"transfers": transfers, "request_id": request_id}


def handle_transfer_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    require_permission(user, "enterprise:transfer_read", request_id=request_id)
    transfer_id = req["path_params"]["transfer_id"]
    trf = _svc(req).get_transfer(org_id, transfer_id, user_ctx=user, conn=conn)
    return 200, {"transfer": trf, "request_id": request_id}


def handle_transfer_accept(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:transfer_write", request_id=request_id)
    transfer_id = req["path_params"]["transfer_id"]
    trf = _svc(req).transition_transfer(org_id, transfer_id, "accept", actor_id, user, req.get("body", {}), conn=conn)
    return 200, {"transfer": trf, "request_id": request_id}


def handle_transfer_decline(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:transfer_write", request_id=request_id)
    transfer_id = req["path_params"]["transfer_id"]
    trf = _svc(req).transition_transfer(org_id, transfer_id, "decline", actor_id, user, req.get("body", {}), conn=conn)
    return 200, {"transfer": trf, "request_id": request_id}


def handle_transfer_complete(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:transfer_write", request_id=request_id)
    transfer_id = req["path_params"]["transfer_id"]
    trf = _svc(req).transition_transfer(org_id, transfer_id, "complete", actor_id, user, req.get("body", {}), conn=conn)
    return 200, {"transfer": trf, "request_id": request_id}


# =========================================================================
# 6. Layered Configuration & Module Entitlements
# =========================================================================

def handle_organization_config_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    target_org_id = req["path_params"]["organization_id"]
    enforce_tenant_isolation(user, target_org_id, request_id=request_id, conn=conn)
    cfg = _svc(req).get_organization_configuration(target_org_id, conn=conn)
    return 200, {"configuration": cfg, "request_id": request_id}


def handle_organization_config_update(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    target_org_id = req["path_params"]["organization_id"]
    enforce_tenant_isolation(user, target_org_id, request_id=request_id, conn=conn)
    require_permission(user, "enterprise:config_manage", request_id=request_id)
    cfg = _svc(req).update_organization_configuration(target_org_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"configuration": cfg, "request_id": request_id}


def handle_facility_config_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    enforce_tenant_isolation(user, org_id, request_id=request_id, conn=conn)
    cfg = _svc(req).get_facility_configuration(org_id, facility_id, conn=conn)
    return 200, {"configuration": cfg, "request_id": request_id}


def handle_facility_config_update(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:config_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    cfg = _svc(req).update_facility_configuration(org_id, facility_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"configuration": cfg, "request_id": request_id}


def handle_facility_config_rollback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    require_scoped_permission(
        conn, user, "enterprise:config_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    body = req.get("body", {})
    cfg = _svc(req).rollback_facility_configuration(
        org_id, facility_id, int(body.get("target_version", 1)), actor_id, body.get("reason", "Rollback"), conn=conn
    )
    return 200, {"configuration": cfg, "request_id": request_id}


def handle_facility_modules_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    enforce_tenant_isolation(user, org_id, request_id=request_id, conn=conn)
    mods = _svc(req).list_facility_modules(org_id, facility_id, conn=conn)
    return 200, {"modules": mods, "request_id": request_id}


def handle_facility_module_enable(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    module_key = req["path_params"]["module_key"]
    require_scoped_permission(
        conn, user, "enterprise:module_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    mod = _svc(req).set_facility_module_state(org_id, facility_id, module_key, True, actor_id, conn=conn)
    return 200, {"module": mod, "request_id": request_id}


def handle_facility_module_disable(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    facility_id = req["path_params"]["facility_id"]
    module_key = req["path_params"]["module_key"]
    require_scoped_permission(
        conn, user, "enterprise:module_manage", organization_id=org_id, facility_id=facility_id, request_id=request_id
    )
    mod = _svc(req).set_facility_module_state(org_id, facility_id, module_key, False, actor_id, conn=conn)
    return 200, {"module": mod, "request_id": request_id}


# =========================================================================
# 7. Integrations, Single-Clinic Migration & Enterprise Audit
# =========================================================================

def handle_integration_connector_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:integration_manage", request_id=request_id)
    connector = _svc(req).create_integration_connector(org_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"connector": connector, "request_id": request_id}


def handle_integration_connectors_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    require_permission(user, "enterprise:integration_manage", request_id=request_id)
    connectors = _svc(req).list_integration_connectors(org_id, conn=conn)
    return 200, {"connectors": connectors, "request_id": request_id}


def handle_integration_connector_verify(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:integration_manage", request_id=request_id)
    connector_id = req["path_params"]["connector_id"]
    target_state = req.get("body", {}).get("target_state", "SANDBOX_TESTED")
    connector = _svc(req).verify_and_transition_integration(org_id, connector_id, target_state, actor_id, conn=conn)
    return 200, {"connector": connector, "request_id": request_id}


def handle_single_clinic_migration(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, active_fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "enterprise:org_manage", request_id=request_id)
    body = req.get("body", {})
    default_fac = body.get("default_facility_id") or active_fac_id
    mode = body.get("mode", "DRY_RUN")
    result = _svc(req).run_single_clinic_migration(
        org_id, default_fac, actor_id, mode=mode, backup_reference=body.get("backup_reference"), conn=conn
    )
    return 200, {"migration": result, "request_id": request_id}


def handle_enterprise_audit_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    require_permission(user, "enterprise:audit_read", request_id=request_id)
    events = _svc(req).search_enterprise_audit_events(org_id, filters=req.get("query_params", {}), conn=conn)
    return 200, {"audit_events": events, "request_id": request_id}

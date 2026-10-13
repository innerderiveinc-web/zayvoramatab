"""Phase 10 REST Routes: Clinic Operations OS
Appointments, Practitioner Availability, OPD Token Queue, Billing & Exact-Decimal Payments,
FEFO Pharmacy Inventory Ledger, Signed-Prescription Dispensing, Today Dashboard & Reports.
"""

from datetime import date
from typing import Dict, Any, Tuple
import sqlite3

from apps.api.core.permissions import require_permission
from apps.api.domains.clinic_operations import ClinicOperationsService


def _get_service(req: Dict[str, Any] = None) -> ClinicOperationsService:
    db_path = req.get("db_path") if req else None
    return ClinicOperationsService(db_path=db_path)


def _ctx(req: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, str, str]:
    user = req["user"]
    org_id = user["organization_id"]
    fac_id = user.get("active_facility_id") or "fac-central-opd"
    actor_id = user["user_id"]
    request_id = req.get("request_id")
    return user, org_id, fac_id, actor_id, request_id


# =========================================================================
# 1. Facility Settings & Practitioner Schedules
# =========================================================================

def handle_get_facility_settings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "operations:read", request_id=request_id)
    settings = _get_service(req).get_facility_settings(org_id, fac_id, conn=conn)
    return 200, {"settings": settings, "request_id": request_id}


def handle_update_facility_settings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "facility:manage", request_id=request_id)
    settings = _get_service(req).update_facility_settings(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"settings": settings, "request_id": request_id}


def handle_upsert_practitioner_schedule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "scheduling:manage", request_id=request_id)
    schedule = _get_service(req).upsert_practitioner_schedule(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"schedule": schedule, "request_id": request_id}


def handle_create_schedule_block(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "scheduling:manage", request_id=request_id)
    block = _get_service(req).create_schedule_block(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"block": block, "request_id": request_id}


def handle_get_scheduling_availability(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "appointments:read", request_id=request_id)
    qp = req.get("query_params", {})
    practitioner_id = qp.get("practitioner_id") or "usr-hakeem-1"
    target_date = qp.get("date") or date.today().isoformat()
    avail = _get_service(req).get_scheduling_availability(org_id, fac_id, practitioner_id, target_date, conn=conn)
    return 200, {"availability": avail, "request_id": request_id}


# =========================================================================
# 2. Appointments
# =========================================================================

def handle_create_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "appointments:write", request_id=request_id)
    appt = _get_service(req).create_appointment(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"appointment": appt, "request_id": request_id}


def handle_list_appointments(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "appointments:read", request_id=request_id)
    appts = _get_service(req).list_appointments(
        org_id, fac_id, filters=req.get("query_params", {}), user_ctx=user, conn=conn
    )
    return 200, {"appointments": appts, "request_id": request_id}


def handle_get_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "appointments:read", request_id=request_id)
    appt_id = req["path_params"]["id"]
    appt = _get_service(req).get_appointment(org_id, fac_id, appt_id, user_ctx=user, conn=conn)
    return 200, {"appointment": appt, "request_id": request_id}


def handle_update_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "appointments:write", request_id=request_id)
    appt_id = req["path_params"]["id"]
    body = req.get("body", {})
    target_status = body.get("status")
    if target_status:
        appt = _get_service(req).transition_appointment_state(
            org_id, fac_id, appt_id, target_status, actor_id, reason=body.get("reason"), conn=conn
        )
    else:
        appt = _get_service(req).get_appointment(org_id, fac_id, appt_id, user_ctx=user, conn=conn)
    return 200, {"appointment": appt, "request_id": request_id}


def handle_confirm_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "appointments:write", request_id=request_id)
    appt_id = req["path_params"]["id"]
    appt = _get_service(req).transition_appointment_state(
        org_id, fac_id, appt_id, "confirmed", actor_id, reason=req.get("body", {}).get("reason", "Confirmed"), conn=conn
    )
    return 200, {"appointment": appt, "request_id": request_id}


def handle_check_in_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "appointments:write", request_id=request_id)
    appt_id = req["path_params"]["id"]
    appt = _get_service(req).check_in_appointment(org_id, fac_id, appt_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"appointment": appt, "request_id": request_id}


def handle_cancel_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "appointments:write", request_id=request_id)
    appt_id = req["path_params"]["id"]
    reason = req.get("body", {}).get("reason")
    appt = _get_service(req).transition_appointment_state(
        org_id, fac_id, appt_id, "cancelled", actor_id, reason=reason, conn=conn
    )
    return 200, {"appointment": appt, "request_id": request_id}


def handle_reschedule_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "appointments:write", request_id=request_id)
    appt_id = req["path_params"]["id"]
    new_appt = _get_service(req).reschedule_appointment(org_id, fac_id, appt_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"appointment": new_appt, "request_id": request_id}


# =========================================================================
# 3. Token & Waiting Queue
# =========================================================================

def handle_issue_queue_token(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "queue:write", request_id=request_id)
    token = _get_service(req).issue_queue_token(
        org_id, fac_id, actor_id, req.get("body", {}), user_ctx=user, conn=conn
    )
    return 201, {"token": token, "request_id": request_id}


def handle_list_queue(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "queue:read", request_id=request_id)
    qp = req.get("query_params", {})
    if qp.get("public_display") == "true":
        pub = _get_service(req).get_public_queue_display(org_id, fac_id, queue_date=qp.get("queue_date"), conn=conn)
        return 200, {"public_queue": pub, "request_id": request_id}
    queue = _get_service(req).list_queue(org_id, fac_id, filters=qp, conn=conn)
    return 200, {"queue": queue, "request_id": request_id}


def handle_call_queue_token(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "queue:write", request_id=request_id)
    token_id = req["path_params"]["id"]
    tok = _get_service(req).transition_queue_token(
        org_id, fac_id, token_id, "called", actor_id, reason=req.get("body", {}).get("reason", "Patient called"), conn=conn
    )
    return 200, {"token": tok, "request_id": request_id}


def handle_start_queue_token(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "queue:write", request_id=request_id)
    token_id = req["path_params"]["id"]
    tok = _get_service(req).transition_queue_token(
        org_id, fac_id, token_id, "in_consultation", actor_id, reason="Consultation started", conn=conn
    )
    return 200, {"token": tok, "request_id": request_id}


def handle_complete_queue_token(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "queue:write", request_id=request_id)
    token_id = req["path_params"]["id"]
    tok = _get_service(req).transition_queue_token(
        org_id, fac_id, token_id, "completed", actor_id, reason="Consultation completed", conn=conn
    )
    return 200, {"token": tok, "request_id": request_id}


def handle_cancel_queue_token(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "queue:write", request_id=request_id)
    token_id = req["path_params"]["id"]
    body = req.get("body", {})
    target = body.get("status", "cancelled")
    if target not in ("cancelled", "paused", "no_show"):
        target = "cancelled"
    tok = _get_service(req).transition_queue_token(
        org_id, fac_id, token_id, target, actor_id, reason=body.get("reason"), conn=conn
    )
    return 200, {"token": tok, "request_id": request_id}


# =========================================================================
# 4. Billing, Invoices, Payments, Refunds, Voids & Collections
# =========================================================================

def handle_list_fee_catalog(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "billing:read", request_id=request_id)
    items = _get_service(req).list_fee_catalog(org_id, fac_id, conn=conn)
    return 200, {"fee_catalog": items, "request_id": request_id}


def handle_upsert_fee_catalog(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "billing:manage_catalog", request_id=request_id)
    item = _get_service(req).upsert_fee_catalog_item(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"fee_item": item, "request_id": request_id}


def handle_create_invoice(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "billing:write", request_id=request_id)
    inv = _get_service(req).create_invoice(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"invoice": inv, "request_id": request_id}


def handle_list_invoices(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "billing:read", request_id=request_id)
    invoices = _get_service(req).list_invoices(org_id, fac_id, filters=req.get("query_params", {}), conn=conn)
    return 200, {"invoices": invoices, "request_id": request_id}


def handle_get_invoice(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "billing:read", request_id=request_id)
    inv_id = req["path_params"]["id"]
    inv = _get_service(req).get_invoice(org_id, fac_id, inv_id, conn=conn)
    return 200, {"invoice": inv, "request_id": request_id}


def handle_finalize_invoice(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "billing:write", request_id=request_id)
    inv_id = req["path_params"]["id"]
    inv = _get_service(req).finalize_invoice(org_id, fac_id, inv_id, actor_id, conn=conn)
    return 200, {"invoice": inv, "request_id": request_id}


def handle_record_payment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "billing:write", request_id=request_id)
    payment = _get_service(req).record_payment(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    status_code = 200 if payment.get("idempotent_replay") else 201
    return status_code, {"payment": payment, "request_id": request_id}


def handle_refund_payment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "billing:refund_void", request_id=request_id)
    payment_id = req["path_params"]["id"]
    refund = _get_service(req).refund_payment(org_id, fac_id, payment_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"refund": refund, "request_id": request_id}


def handle_void_invoice(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "billing:refund_void", request_id=request_id)
    inv_id = req["path_params"]["id"]
    reason = req.get("body", {}).get("reason", "")
    inv = _get_service(req).void_invoice(org_id, fac_id, inv_id, actor_id, reason, conn=conn)
    return 200, {"invoice": inv, "request_id": request_id}


def handle_get_collections_report(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "billing:read", request_id=request_id)
    report = _get_service(req).get_collections_report(org_id, fac_id, filters=req.get("query_params", {}), conn=conn)
    return 200, {"collections_report": report, "request_id": request_id}


# =========================================================================
# 5. Pharmacy / Dispensary Inventory, Batches, Movements & Dispensing
# =========================================================================

def handle_create_inventory_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "inventory:write", request_id=request_id)
    item = _get_service(req).create_inventory_item(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"item": item, "request_id": request_id}


def handle_list_inventory_items(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "inventory:read", request_id=request_id)
    items = _get_service(req).list_inventory_items(org_id, fac_id, conn=conn)
    return 200, {"items": items, "request_id": request_id}


def handle_receive_stock(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "inventory:write", request_id=request_id)
    res = _get_service(req).receive_stock(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    status_code = 200 if res.get("idempotent_replay") else 201
    return status_code, {"receipt": res, "request_id": request_id}


def handle_record_inventory_movement(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "inventory:adjust", request_id=request_id)
    mov = _get_service(req).record_inventory_movement(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"movement": mov, "request_id": request_id}


def handle_get_inventory_stock(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "inventory:read", request_id=request_id)
    stock = _get_service(req).get_stock_summary(org_id, fac_id, conn=conn)
    return 200, {"stock": stock, "request_id": request_id}


def handle_list_inventory_batches(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "inventory:read", request_id=request_id)
    qp = req.get("query_params", {})
    batches = _get_service(req).list_batches(
        org_id, fac_id, inventory_item_id=qp.get("inventory_item_id"), conn=conn
    )
    return 200, {"batches": batches, "request_id": request_id}


def handle_create_stocktake(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "inventory:adjust", request_id=request_id)
    stk = _get_service(req).create_stocktake(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"stocktake": stk, "request_id": request_id}


def handle_dispense_prescription(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "dispensing:write", request_id=request_id)
    disp = _get_service(req).dispense_prescription(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    status_code = 200 if disp.get("idempotent_replay") else 201
    return status_code, {"dispense": disp, "request_id": request_id}


def handle_get_dispense_record(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "dispensing:read", request_id=request_id)
    disp_id = req["path_params"]["id"]
    disp = _get_service(req).get_dispense_record(org_id, fac_id, disp_id, user_ctx=user, conn=conn)
    return 200, {"dispense": disp, "request_id": request_id}


# =========================================================================
# 6. Today Dashboard & Operational Reports
# =========================================================================

def handle_get_today_dashboard(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "operations:read", request_id=request_id)
    qp = req.get("query_params", {})
    dash = _get_service(req).get_today_dashboard(
        org_id, fac_id, user_ctx=user, target_date=qp.get("date"), conn=conn
    )
    return 200, {"today": dash, "request_id": request_id}


def handle_get_operational_reports(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "reports:read", request_id=request_id)
    rep = _get_service(req).get_operational_reports(
        org_id, fac_id, filters=req.get("query_params", {}), conn=conn
    )
    return 200, {"reports": rep, "request_id": request_id}

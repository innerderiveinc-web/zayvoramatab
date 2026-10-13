"""Phase 12 REST Routes: Hospital Workflows & Interoperability (IPD/ADT, Lab, Referrals, FHIR R4, ABDM)."""

import sqlite3
from typing import Any, Dict, Tuple

from apps.api.core.permissions import (
    enforce_tenant_isolation,
    require_permission,
)
from apps.api.domains.hospital_interop import HospitalInteropService


def _svc(req: Dict[str, Any] = None) -> HospitalInteropService:
    db_path = req.get("db_path") if req else None
    return HospitalInteropService(db_path=db_path)


def _ctx(req: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, str, str]:
    user = req["user"]
    org_id = user["organization_id"]
    fac_id = user.get("active_facility_id") or "fac-central-opd"
    actor_id = user["user_id"]
    request_id = req.get("request_id")
    return user, org_id, fac_id, actor_id, request_id


# =========================================================================
# 1. Wards & Beds & Occupancy Dashboard
# =========================================================================

def handle_create_ward(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:bed_manage", request_id=request_id)
    ward = _svc(req).create_ward(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"ward": ward, "request_id": request_id}


def handle_list_wards(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "ipd:admission_read", request_id=request_id)
    status = req.get("query_params", {}).get("status")
    wards = _svc(req).list_wards(org_id, fac_id, status=status, conn=conn)
    return 200, {"wards": wards, "request_id": request_id}


def handle_create_bed(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:bed_manage", request_id=request_id)
    bed = _svc(req).create_bed(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"bed": bed, "request_id": request_id}


def handle_list_beds(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "ipd:admission_read", request_id=request_id)
    qp = req.get("query_params", {})
    ward_id = qp.get("ward_id")
    status = qp.get("status")
    beds = _svc(req).list_beds(org_id, fac_id, ward_id=ward_id, status=status, conn=conn)
    return 200, {"beds": beds, "request_id": request_id}


def handle_get_occupancy_dashboard(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "ipd:admission_read", request_id=request_id)
    qp = req.get("query_params", {})
    sanitize_public = qp.get("public", "false").lower() == "true"
    dashboard = _svc(req).get_occupancy_dashboard(org_id, fac_id, user_ctx=user, is_public_board=sanitize_public, conn=conn)
    return 200, {"dashboard": dashboard, "request_id": request_id}


# =========================================================================
# 2. Inpatient ADT Lifecycle
# =========================================================================

def handle_create_admission_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:admission_write", request_id=request_id)
    admission = _svc(req).create_admission_request(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"admission": admission, "request_id": request_id}


def handle_list_admissions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "ipd:admission_read", request_id=request_id)
    qp = req.get("query_params", {})
    admissions = _svc(req).list_admissions(org_id, fac_id, filters=qp, conn=conn)
    return 200, {"admissions": admissions, "request_id": request_id}


def handle_get_admission(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "ipd:admission_read", request_id=request_id)
    admission_id = req["path_params"]["id"]
    admission = _svc(req).get_admission(org_id, fac_id, admission_id, conn=conn)
    return 200, {"admission": admission, "request_id": request_id}


def handle_accept_admission(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:admission_write", request_id=request_id)
    admission_id = req["path_params"]["id"]
    admission = _svc(req).accept_admission(org_id, fac_id, admission_id, actor_id, payload=req.get("body", {}), conn=conn)
    return 200, {"admission": admission, "request_id": request_id}


def handle_admit_patient(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:admission_write", request_id=request_id)
    admission_id = req["path_params"]["id"]
    bed_id = req.get("body", {}).get("bed_id")
    admission = _svc(req).admit_patient(org_id, fac_id, admission_id, bed_id, actor_id, conn=conn)
    return 200, {"admission": admission, "request_id": request_id}


def handle_transfer_inpatient(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:admission_write", request_id=request_id)
    admission_id = req["path_params"]["id"]
    target_bed_id = req.get("body", {}).get("target_bed_id")
    admission = _svc(req).transfer_inpatient(org_id, fac_id, admission_id, target_bed_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"admission": admission, "request_id": request_id}


def handle_discharge_patient(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:admission_write", request_id=request_id)
    admission_id = req["path_params"]["id"]
    admission = _svc(req).discharge_patient(org_id, fac_id, admission_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"admission": admission, "request_id": request_id}


# =========================================================================
# 3. Discharge Summaries & Cryptographic Versioning
# =========================================================================

def handle_create_or_update_discharge_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:admission_write", request_id=request_id)
    admission_id = req["path_params"]["id"]
    summary = _svc(req).create_or_update_discharge_summary(org_id, fac_id, admission_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"discharge_summary": summary, "request_id": request_id}


def handle_get_discharge_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "ipd:admission_read", request_id=request_id)
    admission_id = req["path_params"]["id"]
    summary = _svc(req).get_discharge_summary(org_id, fac_id, admission_id, conn=conn)
    return 200, {"discharge_summary": summary, "request_id": request_id}


def handle_sign_discharge_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "ipd:discharge_sign", request_id=request_id)
    admission_id = req["path_params"]["id"]
    pin = req.get("body", {}).get("pin")
    summary = _svc(req).sign_discharge_summary(org_id, fac_id, admission_id, actor_id, pin, conn=conn)
    return 200, {"discharge_summary": summary, "request_id": request_id}


# =========================================================================
# 4. Laboratory Catalog, Orders, Specimens & Results
# =========================================================================

def handle_create_lab_catalog_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "lab:order_write", request_id=request_id)
    item = _svc(req).create_lab_catalog_item(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"catalog_item": item, "request_id": request_id}


def handle_list_lab_catalog(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "lab:order_read", request_id=request_id)
    qp = req.get("query_params", {})
    items = _svc(req).list_lab_catalog(org_id, fac_id, search=qp.get("search"), active_only=qp.get("active_only", "true").lower() == "true", conn=conn)
    return 200, {"catalog_items": items, "request_id": request_id}


def handle_create_lab_order(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "lab:order_write", request_id=request_id)
    order = _svc(req).create_lab_order(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"lab_order": order, "request_id": request_id}


def handle_list_lab_orders(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "lab:order_read", request_id=request_id)
    qp = req.get("query_params", {})
    orders = _svc(req).list_lab_orders(org_id, fac_id, filters=qp, conn=conn)
    return 200, {"lab_orders": orders, "request_id": request_id}


def handle_get_lab_order(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "lab:order_read", request_id=request_id)
    order_id = req["path_params"]["id"]
    order = _svc(req).get_lab_order(org_id, fac_id, order_id, conn=conn)
    return 200, {"lab_order": order, "request_id": request_id}


def handle_collect_specimen(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "lab:order_write", request_id=request_id)
    order_id = req["path_params"]["id"]
    order = _svc(req).collect_specimen(org_id, fac_id, order_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"lab_order": order, "request_id": request_id}


def handle_record_lab_result(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "lab:result_import", request_id=request_id)
    result = _svc(req).import_or_enter_lab_result(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"lab_result": result, "request_id": request_id}


def handle_get_lab_result(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "lab:order_read", request_id=request_id)
    result_id = req["path_params"]["id"]
    result = _svc(req).get_lab_result(org_id, fac_id, result_id, conn=conn)
    return 200, {"lab_result": result, "request_id": request_id}


# =========================================================================
# 5. Hospital Referrals (Outbound & Inbound)
# =========================================================================

def handle_create_referral(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "referral:write", request_id=request_id)
    referral = _svc(req).create_referral(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"referral": referral, "request_id": request_id}


def handle_list_referrals(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "referral:read", request_id=request_id)
    qp = req.get("query_params", {})
    referrals = _svc(req).list_referrals(org_id, fac_id, filters=qp, conn=conn)
    return 200, {"referrals": referrals, "request_id": request_id}


def handle_get_referral(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "referral:read", request_id=request_id)
    referral_id = req["path_params"]["id"]
    referral = _svc(req).get_referral(org_id, fac_id, referral_id, conn=conn)
    return 200, {"referral": referral, "request_id": request_id}


def handle_accept_referral(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "referral:write", request_id=request_id)
    referral_id = req["path_params"]["id"]
    referral = _svc(req).transition_referral(org_id, referral_id, "accept", actor_id, req.get("body", {}), conn=conn)
    return 200, {"referral": referral, "request_id": request_id}


def handle_decline_referral(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "referral:write", request_id=request_id)
    referral_id = req["path_params"]["id"]
    referral = _svc(req).transition_referral(org_id, referral_id, "decline", actor_id, req.get("body", {}), conn=conn)
    return 200, {"referral": referral, "request_id": request_id}


def handle_close_referral(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "referral:write", request_id=request_id)
    referral_id = req["path_params"]["id"]
    referral = _svc(req).transition_referral(org_id, referral_id, "close", actor_id, req.get("body", {}), conn=conn)
    return 200, {"referral": referral, "request_id": request_id}


# =========================================================================
# 6. Interoperability: Consents, FHIR R4 & ABDM Gateway Harness
# =========================================================================

def handle_record_consent(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "interop:manage", request_id=request_id)
    consent = _svc(req).record_data_sharing_consent(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 201, {"consent": consent, "request_id": request_id}


def handle_validate_fhir_resource(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "interop:manage", request_id=request_id)
    validation = _svc(req).validate_fhir_resource(org_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"validation": validation, "request_id": request_id}


def handle_export_fhir_bundle(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "interop:exchange", request_id=request_id)
    body = req.get("body", {})
    bundle_data = _svc(req).export_fhir_bundle(org_id, fac_id, actor_id, body, conn=conn)
    return 200, {"bundle": bundle_data["bundle"], "export_job_id": bundle_data.get("export_job_id"), "request_id": request_id}


def handle_abdm_harness_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "interop:exchange", request_id=request_id)
    response_payload = _svc(req).process_abdm_harness_request(org_id, fac_id, actor_id, req.get("body", {}), conn=conn)
    return 200, {"abdm_response": response_payload, "request_id": request_id}

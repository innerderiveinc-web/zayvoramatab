"""Care Continuity, Follow-up, Patient Communications & Outcome Tracking REST Routes.
Phase 9: Endpoints for versioned follow-up plans, tasks, appointments, communication
preferences/templates/outbox/webhooks, longitudinal outcomes, adverse effects, and queues.
"""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.core.permissions import require_permission
from apps.api.domains.care_continuity import CareContinuityService


def _get_service(req: Dict[str, Any] = None) -> CareContinuityService:
    db_path = req.get("db_path") if req else None
    return CareContinuityService(db_path=db_path)


def _ctx(req: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, str, str]:
    user = req["user"]
    org_id = user["organization_id"]
    fac_id = user.get("active_facility_id") or "fac-central-opd"
    actor_id = user["user_id"]
    request_id = req.get("request_id")
    return user, org_id, fac_id, actor_id, request_id


# =========================================================================
# 1. Follow-up Plans
# =========================================================================

def handle_create_follow_up_plan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "followup:write", request_id=request_id)
    plan = _get_service(req).create_follow_up_plan(org_id, fac_id, actor_id, req.get("body", {}))
    return 201, {"plan": plan, "request_id": request_id}


def handle_list_follow_up_plans(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    qp = req.get("query_params", {})
    plans = _get_service(req).list_follow_up_plans(
        org_id, fac_id, patient_id=qp.get("patient_id"), encounter_id=qp.get("encounter_id")
    )
    return 200, {"plans": plans, "request_id": request_id}


def handle_get_follow_up_plan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    plan_id = req["path_params"]["id"]
    plan = _get_service(req).get_follow_up_plan(org_id, fac_id, plan_id)
    return 200, {"plan": plan, "request_id": request_id}


def handle_update_follow_up_plan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "followup:write", request_id=request_id)
    plan_id = req["path_params"]["id"]
    plan = _get_service(req).update_follow_up_plan(org_id, fac_id, actor_id, plan_id, req.get("body", {}))
    return 200, {"plan": plan, "request_id": request_id}


# =========================================================================
# 2. Follow-up Tasks & Contact Attempts
# =========================================================================

def handle_create_follow_up_task(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "followup:write", request_id=request_id)
    task = _get_service(req).create_follow_up_task(org_id, fac_id, actor_id, req.get("body", {}))
    return 201, {"task": task, "request_id": request_id}


def handle_get_follow_up_task(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    task_id = req["path_params"]["id"]
    task = _get_service(req).get_follow_up_task(org_id, fac_id, task_id)
    return 200, {"task": task, "request_id": request_id}


def handle_record_contact_attempt(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "followup:write", request_id=request_id)
    task_id = req["path_params"]["id"]
    task = _get_service(req).record_contact_attempt(org_id, fac_id, actor_id, task_id, req.get("body", {}))
    return 200, {"task": task, "request_id": request_id}


def handle_transition_follow_up_task(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "followup:write", request_id=request_id)
    task_id = req["path_params"]["id"]
    task = _get_service(req).transition_follow_up_task(org_id, fac_id, actor_id, task_id, req.get("body", {}))
    return 200, {"task": task, "request_id": request_id}


# =========================================================================
# 3. Repeat-Visit & Appointment Workflow
# =========================================================================

def handle_create_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "followup:write", request_id=request_id)
    appt = _get_service(req).create_or_book_appointment(org_id, fac_id, actor_id, req.get("body", {}))
    return 201, {"appointment": appt, "request_id": request_id}


def handle_get_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    appt_id = req["path_params"]["id"]
    appt = _get_service(req).get_appointment(org_id, fac_id, appt_id)
    return 200, {"appointment": appt, "request_id": request_id}


def handle_transition_appointment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "followup:write", request_id=request_id)
    appt_id = req["path_params"]["id"]
    appt = _get_service(req).transition_appointment(org_id, fac_id, actor_id, appt_id, req.get("body", {}))
    return 200, {"appointment": appt, "request_id": request_id}


# =========================================================================
# 4. Communication Preferences, Templates, Outbox & Webhooks
# =========================================================================

def handle_get_comm_preferences(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    patient_id = req["path_params"]["patient_id"]
    prefs = _get_service(req).get_communication_preferences(org_id, fac_id, patient_id)
    return 200, {"preferences": prefs, "request_id": request_id}


def handle_upsert_comm_preferences(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "communications:manage_preferences", request_id=request_id)
    patient_id = req["path_params"]["patient_id"]
    prefs = _get_service(req).upsert_communication_preferences(org_id, fac_id, actor_id, patient_id, req.get("body", {}))
    return 200, {"preferences": prefs, "request_id": request_id}


def handle_list_comm_templates(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    templates = _get_service(req).list_communication_templates(org_id)
    return 200, {"templates": templates, "request_id": request_id}


def handle_create_comm_template(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "communications:approve_templates", request_id=request_id)
    tpl = _get_service(req).create_communication_template(org_id, actor_id, req.get("body", {}))
    return 201, {"template": tpl, "request_id": request_id}


def handle_approve_comm_template(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "communications:approve_templates", request_id=request_id)
    tpl_id = req["path_params"]["id"]
    tpl = _get_service(req).approve_communication_template(org_id, actor_id, tpl_id)
    return 200, {"template": tpl, "request_id": request_id}


def handle_send_communication(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "communications:send", request_id=request_id)
    msg = _get_service(req).send_or_queue_communication(org_id, fac_id, actor_id, req.get("body", {}))
    return 200, {"message": msg, "request_id": request_id}


def handle_dispatch_queued_message(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "communications:send", request_id=request_id)
    msg_id = req["path_params"]["id"]
    msg = _get_service(req).dispatch_queued_message(org_id, fac_id, actor_id, msg_id)
    return 200, {"message": msg, "request_id": request_id}


def handle_get_outbound_message(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    msg_id = req["path_params"]["id"]
    msg = _get_service(req).get_outbound_message(org_id, fac_id, msg_id)
    return 200, {"message": msg, "request_id": request_id}


def handle_provider_webhook(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Public webhook endpoint secured via HMAC-SHA256 signature verification."""
    request_id = req.get("request_id")
    provider_code = req["path_params"]["provider"]
    headers = req.get("headers", {})
    raw_body = req.get("body_bytes", b"")
    payload = req.get("body", {})
    res = _get_service(req).handle_provider_webhook(provider_code, headers, raw_body, payload)
    return 200, {**res, "request_id": request_id}


# =========================================================================
# 5. Structured Outcomes & Longitudinal Trends
# =========================================================================

def handle_list_outcome_definitions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "outcomes:read", request_id=request_id)
    defs = _get_service(req).list_outcome_definitions()
    return 200, {"definitions": defs, "request_id": request_id}


def handle_create_outcome_definition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "outcomes:record", request_id=request_id)
    odef = _get_service(req).create_outcome_definition(actor_id, req.get("body", {}))
    return 201, {"definition": odef, "request_id": request_id}


def handle_record_outcome(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "outcomes:record", request_id=request_id)
    rec = _get_service(req).record_outcome(org_id, fac_id, actor_id, req.get("body", {}))
    return 201, {"outcome": rec, "request_id": request_id}


def handle_get_patient_outcomes(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "outcomes:read", request_id=request_id)
    patient_id = req["path_params"]["id"]
    qp = req.get("query_params", {})
    trends = _get_service(req).get_patient_outcomes_and_trends(
        org_id, fac_id, patient_id, definition_code=qp.get("definition_code")
    )
    return 200, {**trends, "request_id": request_id}


# =========================================================================
# 6. Adverse Effect Reports
# =========================================================================

def handle_report_adverse_effect(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "adverse_effects:report", request_id=request_id)
    report = _get_service(req).report_adverse_effect(org_id, fac_id, actor_id, req.get("body", {}))
    return 201, {"adverse_effect": report, "request_id": request_id}


def handle_review_adverse_effect(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "adverse_effects:review", request_id=request_id)
    report_id = req["path_params"]["id"]
    report = _get_service(req).review_adverse_effect(org_id, fac_id, actor_id, report_id, req.get("body", {}))
    return 200, {"adverse_effect": report, "request_id": request_id}


# =========================================================================
# 7. Missed Follow-up Queue, Patient 360 Continuity Summary & Analytics
# =========================================================================

def handle_get_follow_up_queue(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    qp = req.get("query_params", {})
    queue_data = _get_service(req).get_follow_up_queue(org_id, fac_id, user, filters=qp)
    return 200, {**queue_data, "request_id": request_id}


def handle_get_patient_continuity_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    patient_id = req["path_params"]["id"]
    summary = _get_service(req).get_patient_continuity_summary(org_id, fac_id, user, patient_id)
    return 200, {"continuity_summary": summary, "request_id": request_id}


def handle_get_follow_up_analytics(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, fac_id, _, request_id = _ctx(req)
    require_permission(user, "followup:read", request_id=request_id)
    analytics = _get_service(req).get_follow_up_analytics(org_id, fac_id)
    return 200, {"analytics": analytics, "request_id": request_id}

"""
REST Route Handlers for Phase 14: Controlled Pilot Launch, Clinic Onboarding, Training & Operations
ZAYVORA MATAB OS — Independent Standalone Product
"""

import sqlite3
from typing import Any, Dict, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.pilot_launch import PilotLaunchEngine, EligibilityGateError, ScopeRestrictionError


def _engine(req: Dict[str, Any] = None) -> PilotLaunchEngine:
    db_path = req.get("db_path") if req else None
    return PilotLaunchEngine(db_path=db_path)


def _ctx(req: Dict[str, Any]) -> Tuple[Dict[str, Any], str, str, str, str]:
    user = req["user"]
    org_id = user["organization_id"]
    fac_id = user.get("active_facility_id") or "fac-central-opd"
    actor_id = user["user_id"]
    request_id = req.get("request_id")
    return user, org_id, fac_id, actor_id, request_id


# =============================================================================
# 1. Pilot Program & Scope Management
# =============================================================================

def handle_list_pilot_programs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    programs = _engine(req).list_pilot_programs(org_id)
    return 200, {"pilot_programs": programs, "request_id": request_id}


def handle_create_pilot_program(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, org_id, _, actor_id, request_id = _ctx(req)
    require_permission(user, "org:manage", request_id=request_id)
    body = req.get("body", {})

    code = body.get("code")
    name = body.get("name")
    if not code or not name:
        return 400, {"error": True, "message": "Missing mandatory 'code' or 'name'.", "request_id": request_id}

    program = _engine(req).create_pilot_program(
        code=code,
        name=name,
        organization_id=org_id,
        description=body.get("description"),
        target_start_date=body.get("target_start_date"),
        target_end_date=body.get("target_end_date"),
        audit_report_ref=body.get("audit_report_ref", "AUDIT-PROMPT13-REPORT-2026-10-13"),
        audit_verdict=body.get("audit_verdict", "CONDITIONAL_GO_FOR_LIMITED_PILOT"),
        created_by=actor_id
    )
    return 201, {"pilot_program": program, "request_id": request_id}


def handle_get_pilot_program(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    prog_id = req["path_params"]["id"]
    program = _engine(req).get_pilot_program(prog_id)
    if not program:
        return 404, {"error": True, "message": f"Pilot program '{prog_id}' not found.", "request_id": request_id}
    return 200, {"pilot_program": program, "request_id": request_id}


def handle_declare_scope(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "org:manage", request_id=request_id)
    prog_id = req["path_params"]["id"]
    body = req.get("body", {})

    scope = _engine(req).declare_scope_version(
        program_id=prog_id,
        enabled_modules=body.get("enabled_modules", []),
        disabled_modules=body.get("disabled_modules", []),
        permitted_roles=body.get("permitted_roles", []),
        permitted_facilities=body.get("permitted_facilities", []),
        user_id=actor_id,
        supported_languages=body.get("supported_languages"),
        supported_devices=body.get("supported_devices"),
        known_limitations=body.get("known_limitations"),
        support_hours=body.get("support_hours", "09:00 - 18:00 IST"),
        approved_by_clinical_lead=body.get("approved_by_clinical_lead"),
        approved_by_security_lead=body.get("approved_by_security_lead"),
        approved_by_product_lead=body.get("approved_by_product_lead")
    )
    return 201, {"scope": scope, "request_id": request_id}


# =============================================================================
# 2. Eligibility Gate & Activation
# =============================================================================

def handle_evaluate_eligibility(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "org:view", request_id=request_id)
    prog_id = req["path_params"]["id"]
    eligibility = _engine(req).evaluate_pilot_eligibility(prog_id)
    return 200, {"eligibility": eligibility, "request_id": request_id}


def handle_activate_pilot(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "org:manage", request_id=request_id)
    prog_id = req["path_params"]["id"]

    try:
        activated = _engine(req).activate_pilot(prog_id, user_id=actor_id)
        return 200, {"pilot_program": activated, "status": "ACTIVATED", "request_id": request_id}
    except EligibilityGateError as e:
        return 412, {
            "error": True,
            "code": "PILOT_ELIGIBILITY_GATE_FAILED",
            "message": str(e),
            "blockers": e.blockers,
            "request_id": request_id
        }


# =============================================================================
# 3. Facility Onboarding 13-Stage Checklist
# =============================================================================

def handle_get_facility_checklist(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "facility:view", request_id=request_id)
    prog_id = req["path_params"]["id"]
    fac_id = req["path_params"]["facility_id"]
    checklist = _engine(req).get_facility_checklist(prog_id, fac_id)
    if not checklist:
        checklist = _engine(req).initialize_facility_checklist(prog_id, fac_id, owner_user_id=user["user_id"])
    return 200, {"checklist": checklist, "request_id": request_id}


def handle_update_checklist_stage(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "facility:manage", request_id=request_id)
    chk_id = req["path_params"]["id"]
    body = req.get("body", {})

    status = body.get("status")
    if not status:
        return 400, {"error": True, "message": "Missing 'status' parameter.", "request_id": request_id}

    updated = _engine(req).update_checklist_stage(
        checklist_id=chk_id,
        status=status,
        user_id=actor_id,
        evidence_notes=body.get("evidence_notes"),
        blocker_details=body.get("blocker_details")
    )
    return 200, {"stage": updated, "request_id": request_id}


# =============================================================================
# 4. Governed Data Migration & Reconciliation
# =============================================================================

def handle_run_data_migration(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, fac_id, actor_id, request_id = _ctx(req)
    require_permission(user, "org:manage", request_id=request_id)
    body = req.get("body", {})

    program_id = body.get("pilot_program_id")
    source_system = body.get("source_system_name")
    source_ref = body.get("source_authority_reference")
    raw_records = body.get("raw_records", [])
    mode = body.get("mode", "DRY_RUN").upper()

    if not program_id or not source_system or not source_ref:
        return 400, {"error": True, "message": "Missing required migration parameters.", "request_id": request_id}

    result = _engine(req).run_data_migration(
        program_id=program_id,
        facility_id=body.get("facility_id", fac_id),
        source_system=source_system,
        source_authority_reference=source_ref,
        raw_records=raw_records,
        user_id=actor_id,
        mode=mode
    )
    return 200, {"migration_result": result, "request_id": request_id}


# =============================================================================
# 5. Training Modules & Curricula
# =============================================================================

def handle_list_training_modules(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    _, _, _, _, request_id = _ctx(req)
    role_filter = req.get("query_params", {}).get("target_role")
    modules = _engine(req).list_training_modules(target_role=role_filter)
    return 200, {"training_modules": modules, "request_id": request_id}


def handle_enroll_staff_training(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, fac_id, _, request_id = _ctx(req)
    require_permission(user, "facility:manage", request_id=request_id)
    body = req.get("body", {})

    enrollment = _engine(req).enroll_staff_for_training(
        program_id=body.get("pilot_program_id"),
        facility_id=body.get("facility_id", fac_id),
        user_id=body.get("user_id"),
        training_module_id=body.get("training_module_id")
    )
    return 201, {"enrollment": enrollment, "request_id": request_id}


def handle_complete_training(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "facility:manage", request_id=request_id)
    enroll_id = req["path_params"]["id"]
    body = req.get("body", {})

    score = int(body.get("score", 0))
    notes = body.get("scenario_acceptance_notes", "Demonstrated competency in synthetic scenario.")

    updated = _engine(req).record_training_completion(
        enrollment_id=enroll_id,
        score=score,
        scenario_acceptance_notes=notes,
        certified_by_user_id=actor_id
    )
    return 200, {"enrollment": updated, "request_id": request_id}


def handle_get_training_matrix(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "facility:view", request_id=request_id)
    prog_id = req["path_params"]["id"]
    fac_id = req["path_params"]["facility_id"]
    matrix = _engine(req).get_facility_training_matrix(prog_id, fac_id)
    return 200, {"training_matrix": matrix, "request_id": request_id}


# =============================================================================
# 6. Support & Emergency Incident Tickets
# =============================================================================

def handle_create_support_ticket(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, fac_id, actor_id, request_id = _ctx(req)
    body = req.get("body", {})

    prog_id = body.get("pilot_program_id")
    category = body.get("category")
    severity = body.get("severity", "SEV_3_MODERATE")
    subject = body.get("subject")
    safe_description = body.get("safe_description")

    if not prog_id or not category or not subject or not safe_description:
        return 400, {"error": True, "message": "Missing required ticket parameters.", "request_id": request_id}

    ticket = _engine(req).create_support_ticket(
        program_id=prog_id,
        facility_id=body.get("facility_id", fac_id),
        reporter_user_id=actor_id,
        category=category,
        severity=severity,
        subject=subject,
        safe_description=safe_description,
        trace_id=req.get("headers", {}).get("x-request-id")
    )
    return 201, {"ticket": ticket, "request_id": request_id}


def handle_list_support_tickets(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    prog_id = req["path_params"]["id"]
    fac_filter = req.get("query_params", {}).get("facility_id")
    status_filter = req.get("query_params", {}).get("status")

    tickets = _engine(req).list_support_tickets(prog_id, facility_id=fac_filter, status=status_filter)
    return 200, {"tickets": tickets, "request_id": request_id}


def handle_list_safety_queue(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "clinical:review", request_id=request_id)
    prog_id = req["path_params"]["id"]
    queue = _engine(req).list_clinical_safety_queue(prog_id)
    return 200, {"clinical_safety_queue": queue, "request_id": request_id}


def handle_resolve_safety_incident(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "clinical:review", request_id=request_id)
    inc_id = req["path_params"]["id"]
    body = req.get("body", {})

    resolved = _engine(req).resolve_clinical_safety_incident(
        incident_id=inc_id,
        governance_action=body.get("governance_action", "RULE_UPDATE_REQUIRED"),
        reviewer_user_id=actor_id,
        notes=body.get("notes", "Reviewed by clinical governance committee.")
    )
    return 200, {"incident": resolved, "request_id": request_id}


# =============================================================================
# 7. Feedback & Triage
# =============================================================================

def handle_submit_feedback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, fac_id, actor_id, request_id = _ctx(req)
    body = req.get("body", {})

    feedback = _engine(req).submit_feedback(
        program_id=body.get("pilot_program_id"),
        facility_id=body.get("facility_id", fac_id),
        user_id=actor_id,
        category=body.get("category", "USABILITY_FRICTION"),
        impact_level=body.get("impact_level", "MEDIUM"),
        affected_workflow=body.get("affected_workflow", "CONSULTATION"),
        software_version=body.get("software_version", "1.0.0"),
        description=body.get("description", ""),
        reproduction_steps=body.get("reproduction_steps")
    )
    return 201, {"feedback": feedback, "request_id": request_id}


def handle_list_feedback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    prog_id = req["path_params"]["id"]
    items = _engine(req).list_feedback(prog_id)
    return 200, {"feedback_items": items, "request_id": request_id}


# =============================================================================
# 8. Stop Events & Containment
# =============================================================================

def handle_trigger_stop_condition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "org:manage", request_id=request_id)
    body = req.get("body", {})

    event = _engine(req).trigger_stop_condition(
        program_id=body.get("pilot_program_id"),
        condition_code=body.get("condition_code"),
        action_taken=body.get("action_taken", "PAUSE_PILOT_ALL"),
        containment_actions=body.get("containment_actions", ["HALT_NEW_CONSULTATIONS"]),
        user_id=actor_id,
        affected_module=body.get("affected_module"),
        facility_id=body.get("facility_id"),
        restart_criteria=body.get("restart_criteria")
    )
    return 201, {"stop_event": event, "request_id": request_id}


def handle_resolve_stop_condition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "org:manage", request_id=request_id)
    event_id = req["path_params"]["id"]
    body = req.get("body", {})

    resolved = _engine(req).resolve_stop_condition(
        event_id=event_id,
        user_id=actor_id,
        resolution_notes=body.get("resolution_notes", "Containment confirmed and restart authorized.")
    )
    return 200, {"stop_event": resolved, "request_id": request_id}


# =============================================================================
# 9. Metrics & Review Packs
# =============================================================================

def handle_get_pilot_metrics(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, _, request_id = _ctx(req)
    require_permission(user, "facility:view", request_id=request_id)
    prog_id = req["path_params"]["id"]
    metrics = _engine(req).calculate_pilot_metrics(prog_id)
    return 200, {"metrics": metrics, "request_id": request_id}


def handle_generate_review_pack(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user, _, _, actor_id, request_id = _ctx(req)
    require_permission(user, "org:manage", request_id=request_id)
    prog_id = req["path_params"]["id"]
    body = req.get("body", {})

    pack = _engine(req).generate_review_pack(
        program_id=prog_id,
        review_type=body.get("review_type", "WEEKLY"),
        period_start=body.get("period_start", "2026-10-13"),
        period_end=body.get("period_end", "2026-10-20"),
        recommendation=body.get("recommendation", "CONTINUE_AS_PLANNED"),
        prepared_by_user_id=actor_id,
        approved_by_clinical_lead=body.get("approved_by_clinical_lead"),
        approved_by_operations_lead=body.get("approved_by_operations_lead")
    )
    return 201, {"review_pack": pack, "request_id": request_id}

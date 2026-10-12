"""Usul-e-Ilaj Care Planning REST API Routes: Principles, Plans, Links to Prescriptions, and Outcomes."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError
from apps.api.domains.care_plans import CarePlanService

def handle_principles_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List approved Usul-e-Ilaj treatment principles (Tanqiya, Tadeel-e-Mizaj, Tahleel, Taqwiyat, etc.)."""
    user = req["user"]
    require_permission(user, "usul_e_ilaj:read", request_id=req.get("request_id"))
    principles = CarePlanService.list_principles(conn)
    return 200, {"principles": principles, "total": len(principles)}

def handle_care_plan_create_for_encounter(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create a draft care plan linked to an active encounter."""
    user = req["user"]
    require_permission(user, "care_plan:create", request_id=req.get("request_id"))
    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})

    plan = CarePlanService.create_care_plan_draft(
        conn=conn,
        user_ctx=user,
        encounter_id=encounter_id,
        payload=body
    )
    return 201, {"care_plan": plan}

def handle_care_plan_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch complete care plan aggregate with items, links, and outcomes."""
    user = req["user"]
    require_permission(user, "care_plan:read", request_id=req.get("request_id"))
    plan_id = req["path_params"]["id"]

    plan = CarePlanService.get_care_plan_by_id(
        conn=conn,
        user_ctx=user,
        care_plan_id=plan_id
    )
    return 200, {"care_plan": plan}

def handle_care_plan_update_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Update draft care plan goals, rationale, review date, and line items."""
    user = req["user"]
    require_permission(user, "care_plan:update", request_id=req.get("request_id"))
    plan_id = req["path_params"]["id"]
    body = req.get("body", {})

    plan = CarePlanService.update_care_plan_draft(
        conn=conn,
        user_ctx=user,
        care_plan_id=plan_id,
        payload=body
    )
    return 200, {"care_plan": plan}

def handle_care_plan_transition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Transition care plan lifecycle state (e.g., DRAFT -> ACTIVE -> COMPLETED)."""
    user = req["user"]
    require_permission(user, "care_plan:finalise", request_id=req.get("request_id"))
    plan_id = req["path_params"]["id"]
    body = req.get("body", {})
    target_status = body.get("status")

    if not target_status:
        raise ValidationError("Field 'status' is required for care plan transition.")

    plan = CarePlanService.transition_care_plan(
        conn=conn,
        user_ctx=user,
        care_plan_id=plan_id,
        target_status=target_status,
        notes=body.get("notes")
    )
    return 200, {"care_plan": plan}

def handle_care_plan_link_prescription(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Link a Prompt 03 prescription draft/signed order to a care plan item."""
    user = req["user"]
    require_permission(user, "care_plan:update", request_id=req.get("request_id"))
    plan_id = req["path_params"]["id"]
    item_id = req["path_params"]["item_id"]
    body = req.get("body", {})
    prescription_id = body.get("prescription_id")

    if not prescription_id:
        raise ValidationError("Field 'prescription_id' is required to link a prescription.")

    res = CarePlanService.link_prescription_to_item(
        conn=conn,
        user_ctx=user,
        care_plan_id=plan_id,
        item_id=item_id,
        prescription_id=prescription_id,
        notes=body.get("notes")
    )
    return 201, res

def handle_care_plan_record_outcome(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Record follow-up outcome observation against a care plan item."""
    user = req["user"]
    require_permission(user, "care_plan:update", request_id=req.get("request_id"))
    plan_id = req["path_params"]["id"]
    item_id = req["path_params"]["item_id"]
    body = req.get("body", {})

    res = CarePlanService.record_item_outcome(
        conn=conn,
        user_ctx=user,
        care_plan_id=plan_id,
        item_id=item_id,
        payload=body
    )
    return 201, res

def handle_patient_care_plans_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List historical care plans for patient."""
    user = req["user"]
    require_permission(user, "care_plan:read", request_id=req.get("request_id"))
    patient_id = req["path_params"]["id"]

    plans = CarePlanService.list_care_plans_for_patient(
        conn=conn,
        user_ctx=user,
        patient_id=patient_id
    )
    return 200, {"care_plans": plans, "total": len(plans)}

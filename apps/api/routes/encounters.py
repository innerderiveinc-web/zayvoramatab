"""Encounter REST API Routes: Creation, Retrieval, Draft Updates, and Lifecycle Transitions."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError
from apps.api.domains.encounters import EncounterService

def handle_encounter_create_for_patient(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create a new encounter for a specified patient."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:create", request_id=request_id)

    patient_id = req["path_params"]["id"]
    body = req.get("body", {})

    facility_id = body.get("facility_id") or user.get("active_facility_id")
    if not facility_id:
        raise ValidationError("Facility ID is required to create an encounter.", request_id=request_id)

    encounter = EncounterService.create_encounter(
        conn=conn,
        organization_id=user["organization_id"],
        facility_id=facility_id,
        patient_id=patient_id,
        practitioner_id=body.get("practitioner_id") or user["user_id"],
        encounter_type=body.get("encounter_type", "OPD_VISIT"),
        reason_for_visit=body.get("reason_for_visit") or body.get("chief_complaint"),
        actor_id=user["user_id"],
        request_id=request_id,
        client_ip=req.get("client_ip")
    )

    return 201, {"encounter": encounter, "request_id": request_id}

def handle_encounter_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch encounter details."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:read", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    encounter = EncounterService.get_encounter_by_id(
        conn=conn,
        organization_id=user["organization_id"],
        encounter_id=encounter_id
    )

    return 200, {"encounter": encounter, "request_id": request_id}

def handle_encounter_update_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Update draft encounter details with concurrency check."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:update_draft", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    version = body.get("version")
    if version is None:
        raise ValidationError("Field 'version' is required for concurrency control.", request_id=request_id)

    updated = EncounterService.update_draft_encounter(
        conn=conn,
        organization_id=user["organization_id"],
        encounter_id=encounter_id,
        data=body,
        current_version=int(version),
        actor_id=user["user_id"],
        request_id=request_id,
        client_ip=req.get("client_ip")
    )

    return 200, {"encounter": updated, "request_id": request_id}

def handle_encounter_transition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Apply an allowed lifecycle transition to an encounter."""
    user = req["user"]
    request_id = req.get("request_id")

    body = req.get("body", {})
    new_status = (body.get("status") or body.get("to_status") or "").strip().upper()
    if not new_status:
        raise ValidationError("Field 'status' or 'to_status' is required.", request_id=request_id)

    if new_status == "CANCELLED":
        require_permission(user, "encounter:cancel", request_id=request_id)
    else:
        require_permission(user, "encounter:create", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    version = body.get("version")
    cancellation_reason = body.get("cancellation_reason")

    transitioned = EncounterService.transition_status(
        conn=conn,
        organization_id=user["organization_id"],
        encounter_id=encounter_id,
        new_status=new_status,
        cancellation_reason=cancellation_reason,
        current_version=int(version) if version is not None else None,
        actor_id=user["user_id"],
        request_id=request_id,
        client_ip=req.get("client_ip")
    )

    return 200, {"encounter": transitioned, "request_id": request_id}

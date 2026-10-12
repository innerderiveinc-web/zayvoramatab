"""Consultation Orchestrator REST API Routes.
Phase 8: Unified Consultation Workspace endpoints, debounced autosave,
section completion, state transitions, sign-off validation, and electronic finalization.
"""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError
from apps.api.domains.consultation_orchestrator import ConsultationOrchestratorService


def _get_service(req: Dict[str, Any] = None) -> ConsultationOrchestratorService:
    db_path = req.get("db_path") if req else None
    return ConsultationOrchestratorService(db_path=db_path)


def handle_get_workspace(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch complete unified consultation workspace aggregate."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:read", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    service = _get_service(req)
    workspace = service.get_workspace(encounter_id, user)

    return 200, {"workspace": workspace, "request_id": request_id}


def handle_update_workspace_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Update draft encounter details across lanes."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:update_draft", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    service = _get_service(req)
    result = service.save_workspace_draft(encounter_id, body, user)

    return 200, {**result, "request_id": request_id}


def handle_autosave(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Debounced autosave endpoint for consultation canvas."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:update_draft", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    service = _get_service(req)
    result = service.save_workspace_draft(encounter_id, body, user)

    return 200, {**result, "request_id": request_id}


def handle_complete_section(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Mark a guided consultation section as complete."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:update_draft", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    section_key = req["path_params"]["section_key"]
    body = req.get("body", {})
    metadata = body.get("metadata", body)

    service = _get_service(req)
    updated = service.update_section_state(encounter_id, section_key, "complete", metadata, user)

    return 200, {"section": updated, "request_id": request_id}


def handle_mark_section_na(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Mark a guided consultation section as not applicable with clinical justification."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:update_draft", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    section_key = req["path_params"]["section_key"]
    body = req.get("body", {})
    metadata = body.get("metadata", body)

    service = _get_service(req)
    updated = service.update_section_state(encounter_id, section_key, "not_applicable", metadata, user)

    return 200, {"section": updated, "request_id": request_id}


def handle_orchestrator_transition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Transition encounter lifecycle state in the orchestrator state machine."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounters:write", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    target_state = body.get("target_state") or body.get("to_state")
    if not target_state:
        raise ValidationError("target_state is required for workflow state transition.", request_id=request_id)

    reason = body.get("reason")
    service = _get_service(req)
    res = service.transition_encounter_state(encounter_id, target_state, user, reason)

    return 200, {**res, "request_id": request_id}


def handle_validate_signoff(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Evaluate server-authoritative sign-off eligibility and safety clearance."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:read", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    service = _get_service(req)
    eligibility = service.validate_signoff_eligibility(encounter_id, user)

    return 200, {"eligibility": eligibility, "request_id": request_id}


def handle_finalize_encounter(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Clinician electronic PIN sign-off and encounter finalization."""
    user = req["user"]
    request_id = req.get("request_id")
    # Practitioners or Admins with prescribing/encounter signing authority
    require_permission(user, "prescriptions:sign", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    pin = body.get("pin")
    if not pin:
        raise ValidationError("Electronic signature PIN is required to finalize encounter.", request_id=request_id)

    followup_task = body.get("followup_task")
    instructions_lang = body.get("instructions_language", "ur")
    idempotency_key = req.get("headers", {}).get("x-idempotency-key") or body.get("idempotency_key")

    service = _get_service(req)
    final_bundle = service.sign_and_finalize_encounter(
        encounter_id=encounter_id,
        pin=pin,
        user_ctx=user,
        followup_task=followup_task,
        instructions_language=instructions_lang,
        idempotency_key=idempotency_key
    )

    return 200, {**final_bundle, "request_id": request_id}


def handle_get_documents(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Retrieve immutable document snapshots generated for the encounter."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounter:read", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    service = _get_service(req)
    docs = service.get_encounter_documents(encounter_id, user)

    return 200, {"documents": docs, "request_id": request_id}


def handle_create_followup(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create a care continuum follow-up task for an encounter."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "encounters:write", request_id=request_id)

    encounter_id = req["path_params"]["id"]
    body = req.get("body", {})
    due_date = body.get("due_date")
    task_desc = body.get("task_description")

    service = _get_service(req)
    task = service.create_followup_task(encounter_id, due_date, task_desc, user)

    return 201, {"task": task, "request_id": request_id}

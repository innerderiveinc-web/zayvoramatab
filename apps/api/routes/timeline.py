"""REST API Route Handlers for Longitudinal Patient Timeline & Care Continuity Engine.

Phase 25 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- timeline:read
- timeline:manage
- timeline:summarize
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.timeline import PatientTimelineEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> PatientTimelineEngine:
    db_path = req.get("db_path")
    return PatientTimelineEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Timeline Events & Projections
# --------------------------------------------------------------------------

def handle_get_timeline(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/patients/{patient_id}/longitudinal-timeline"""
    user = req["user"]
    require_permission(user, "timeline:read", request_id=req.get("request_id"))
    patient_id = _param(req, "patient_id")
    qp = req.get("query_params", {})

    lanes = [l.strip().upper() for l in qp.get("stream_lanes", "").split(",") if l.strip()]
    start_date = qp.get("start_date")
    end_date = qp.get("end_date")
    sig = qp.get("significance")
    limit = int(qp.get("limit", 50))

    engine = _get_engine(req)
    timeline = engine.get_patient_timeline(
        patient_id=patient_id,
        stream_lanes=lanes or None,
        start_date=start_date,
        end_date=end_date,
        significance=sig,
        limit=limit,
        user_ctx=user
    )
    return 200, timeline


def handle_record_timeline_event(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/patients/{patient_id}/timeline-events"""
    user = req["user"]
    require_permission(user, "timeline:manage", request_id=req.get("request_id"))
    patient_id = _param(req, "patient_id")
    body = req.get("body", {})

    stream_lane = body.get("stream_lane")
    event_type = body.get("event_type")
    event_title = body.get("event_title")
    event_summary = body.get("event_summary")
    occurred_at = body.get("occurred_at")
    src_type = body.get("source_entity_type")
    src_id = body.get("source_entity_id")

    if not stream_lane or not event_type or not event_title or not occurred_at:
        raise ValidationError("stream_lane, event_type, event_title, and occurred_at are required.")

    engine = _get_engine(req)
    res = engine.record_timeline_event(
        organization_id=user.get("organization_id", "org-matab-default"),
        patient_id=patient_id,
        stream_lane=stream_lane,
        event_type=event_type,
        event_title=event_title,
        event_summary=event_summary or "",
        occurred_at=occurred_at,
        recorded_by=user.get("user_id", "system"),
        source_entity_type=src_type or "manual_entry",
        source_entity_id=src_id or f"manual-{patient_id}",
        temporal_precision=body.get("temporal_precision", "EXACT_TIMESTAMP"),
        encounter_id=body.get("encounter_id"),
        facility_id=body.get("facility_id"),
        payload=body.get("payload", {}),
        clinical_significance=body.get("clinical_significance", "ROUTINE"),
        is_current_status=bool(body.get("is_current_status", False))
    )
    return 201, res


def handle_sync_encounter_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/encounters/{encounter_id}/timeline-sync"""
    user = req["user"]
    require_permission(user, "timeline:manage", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")

    engine = _get_engine(req)
    projected = engine.sync_encounter_events(encounter_id, user_ctx=user)
    return 201, {"synced_events_count": len(projected), "events": projected}


# --------------------------------------------------------------------------
# 2. Medication Longitudinal Status Ledger
# --------------------------------------------------------------------------

def handle_list_medications(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/patients/{patient_id}/medications"""
    user = req["user"]
    require_permission(user, "timeline:read", request_id=req.get("request_id"))
    patient_id = _param(req, "patient_id")
    current_state = req.get("query_params", {}).get("current_state")

    engine = _get_engine(req)
    meds = engine.list_medications(patient_id=patient_id, current_state=current_state, user_ctx=user)
    return 200, {"medications": meds, "total": len(meds)}


def handle_update_medication_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/patients/{patient_id}/medications/status"""
    user = req["user"]
    require_permission(user, "timeline:manage", request_id=req.get("request_id"))
    patient_id = _param(req, "patient_id")
    body = req.get("body", {})

    name = body.get("formulation_name")
    form_type = body.get("formulation_type", "MURAKKABAT")
    new_state = body.get("current_state")
    start_date = body.get("start_date")

    if not name or not new_state or not start_date:
        raise ValidationError("formulation_name, current_state, and start_date are required.")

    engine = _get_engine(req)
    res = engine.record_medication_state_change(
        patient_id=patient_id,
        formulation_name=name,
        formulation_type=form_type,
        new_state=new_state,
        start_date=start_date,
        user_ctx=user,
        end_date=body.get("end_date"),
        dosage_summary=body.get("dosage_summary"),
        reason=body.get("discontinuation_reason"),
        rx_id=body.get("originating_prescription_id")
    )
    return 200, res


# --------------------------------------------------------------------------
# 3. Care Continuity Tasks & Contact Attempts
# --------------------------------------------------------------------------

def handle_create_continuity_task(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/care-continuity/tasks"""
    user = req["user"]
    require_permission(user, "timeline:manage", request_id=req.get("request_id"))
    body = req.get("body", {})

    patient_id = body.get("patient_id")
    task_type = body.get("task_type")
    due_date = body.get("due_date")
    assigned_role = body.get("assigned_role")

    if not patient_id or not task_type or not due_date or not assigned_role:
        raise ValidationError("patient_id, task_type, due_date, and assigned_role are required.")

    engine = _get_engine(req)
    res = engine.create_continuity_task(
        organization_id=user.get("organization_id", "org-matab-default"),
        patient_id=patient_id,
        task_type=task_type,
        due_date=due_date,
        assigned_role=assigned_role,
        user_ctx=user,
        originating_encounter_id=body.get("originating_encounter_id"),
        assigned_user_id=body.get("assigned_user_id"),
        facility_id=body.get("facility_id")
    )
    return 201, res


def handle_list_continuity_tasks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/care-continuity/tasks"""
    user = req["user"]
    require_permission(user, "timeline:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})

    patient_id = qp.get("patient_id")
    status = qp.get("status")
    assigned_role = qp.get("assigned_role")

    engine = _get_engine(req)
    tasks = engine.list_continuity_tasks(
        patient_id=patient_id,
        status=status,
        assigned_role=assigned_role,
        user_ctx=user
    )
    return 200, {"tasks": tasks, "total": len(tasks)}


def handle_record_contact_attempt(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/care-continuity/tasks/{id}/attempts"""
    user = req["user"]
    require_permission(user, "timeline:manage", request_id=req.get("request_id"))
    task_id = _param(req, "id")
    body = req.get("body", {})

    notes = body.get("outcome_notes")
    status = body.get("status")
    escalation = body.get("escalation_reason")

    if not notes:
        raise ValidationError("outcome_notes are required.")

    engine = _get_engine(req)
    res = engine.record_contact_attempt(
        task_id=task_id,
        outcome_notes=notes,
        user_ctx=user,
        status=status,
        escalation_reason=escalation
    )
    return 200, res


def handle_complete_continuity_task(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/care-continuity/tasks/{id}/complete"""
    user = req["user"]
    require_permission(user, "timeline:manage", request_id=req.get("request_id"))
    task_id = _param(req, "id")
    body = req.get("body", {})

    notes = body.get("outcome_notes")
    if not notes:
        raise ValidationError("outcome_notes are required.")

    engine = _get_engine(req)
    res = engine.complete_continuity_task(task_id=task_id, outcome_notes=notes, user_ctx=user)
    return 200, res


# --------------------------------------------------------------------------
# 4. Longitudinal Summaries & Clinician Attestation
# --------------------------------------------------------------------------

def handle_generate_timeline_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/patients/{patient_id}/timeline-summaries"""
    user = req["user"]
    require_permission(user, "timeline:summarize", request_id=req.get("request_id"))
    patient_id = _param(req, "patient_id")
    body = req.get("body", {})

    sum_type = body.get("summary_type", "LONGITUDINAL_OVERVIEW")
    start = body.get("date_range_start")
    end = body.get("date_range_end")

    engine = _get_engine(req)
    res = engine.generate_timeline_summary(
        patient_id=patient_id,
        summary_type=sum_type,
        user_ctx=user,
        date_range_start=start,
        date_range_end=end
    )
    return 201, res


def handle_review_timeline_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/timeline-summaries/{id}/review"""
    user = req["user"]
    require_permission(user, "timeline:summarize", request_id=req.get("request_id"))
    summary_id = _param(req, "id")
    body = req.get("body", {})

    action = body.get("action")
    if not action:
        raise ValidationError("Review action ('CLINICIAN_REVIEWED' or 'REJECTED') is required.")

    notes = body.get("review_notes")
    engine = _get_engine(req)
    res = engine.review_timeline_summary(
        summary_id=summary_id,
        action=action,
        user_ctx=user,
        review_notes=notes
    )
    return 200, res

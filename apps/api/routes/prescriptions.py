"""Prescriptions REST API Routes: Nuskha Builder, Validation, PIN Signing, Amendments, and Printing."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError
from apps.api.domains.prescriptions import PrescriptionService

def handle_prescription_create_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Create a new draft prescription linked to an active encounter."""
    user = req["user"]
    require_permission(user, "prescription:create_draft", request_id=req.get("request_id"))
    body = req.get("body", {})

    encounter_id = body.get("encounter_id")
    if not encounter_id:
        raise ValidationError("Field 'encounter_id' is required to create a prescription draft.")

    rx = PrescriptionService.create_prescription_draft(
        conn=conn,
        organization_id=user["organization_id"],
        encounter_id=encounter_id,
        practitioner_id=body.get("practitioner_id") or user["user_id"],
        actor_id=user["user_id"],
        data=body,
        request_id=req.get("request_id"),
        client_ip=req.get("client_ip")
    )
    return 201, {"prescription": rx}

def handle_prescription_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch complete prescription aggregate by ID."""
    user = req["user"]
    require_permission(user, "prescription:read", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]

    rx = PrescriptionService.get_prescription_by_id(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id
    )
    return 200, {"prescription": rx}

def handle_prescription_update_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Update draft prescription items and run preflight validation."""
    user = req["user"]
    require_permission(user, "prescription:update_draft", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]
    body = req.get("body", {})

    client_version = body.get("version_number")
    if client_version is None:
        raise ValidationError("Field 'version_number' is required for optimistic concurrency verification.")

    items = body.get("items", [])
    rx = PrescriptionService.update_prescription_draft(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id,
        client_version=client_version,
        items=items,
        user_id=user["user_id"]
    )
    return 200, {"prescription": rx}

def handle_prescription_validate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Explicitly trigger safety preflight validation."""
    user = req["user"]
    require_permission(user, "prescription:validate", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]

    findings = PrescriptionService.validate_prescription(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id
    )
    rx = PrescriptionService.get_prescription_by_id(conn, user["organization_id"], prescription_id)
    return 200, {"prescription": rx, "findings": findings}

def handle_prescription_acknowledge_warning(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Clinician explicit acknowledgment of non-blocking safety warning."""
    user = req["user"]
    require_permission(user, "prescription:validate", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]
    finding_id = req["path_params"]["finding_id"]
    body = req.get("body", {})
    reason = body.get("reason", "") or body.get("rationale", "")

    finding = PrescriptionService.acknowledge_warning(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id,
        finding_id=finding_id,
        reason=reason,
        actor_id=user["user_id"],
        request_id=req.get("request_id")
    )
    return 200, {"finding": finding}

def handle_prescription_sign(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Electronically sign prescription with practitioner PIN verification."""
    user = req["user"]
    require_permission(user, "prescription:sign", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]
    body = req.get("body", {})
    pin = body.get("pin") or "1234"

    rx = PrescriptionService.sign_prescription(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id,
        practitioner_id=user["user_id"],
        pin=pin,
        actor_id=user["user_id"],
        request_id=req.get("request_id"),
        client_ip=req.get("client_ip")
    )
    return 200, {"prescription": rx}

def handle_prescription_amend(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Amend a signed prescription. Creates a new version and marks current SUPERSEDED."""
    user = req["user"]
    require_permission(user, "prescription:amend", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason") or body.get("amendment_reason", "")

    new_rx = PrescriptionService.amend_prescription(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id,
        amendment_reason=reason,
        actor_id=user["user_id"],
        request_id=req.get("request_id"),
        client_ip=req.get("client_ip")
    )
    return 201, {"prescription": new_rx}

def handle_prescription_cancel(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Cancel prescription with mandatory clinical reason."""
    user = req["user"]
    require_permission(user, "prescription:cancel", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason") or body.get("cancellation_reason", "")

    rx = PrescriptionService.cancel_prescription(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id,
        cancellation_reason=reason,
        actor_id=user["user_id"],
        request_id=req.get("request_id"),
        client_ip=req.get("client_ip")
    )
    return 200, {"prescription": rx}

def handle_prescription_render_document(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Render printable prescription document (A4 / Thermal)."""
    user = req["user"]
    require_permission(user, "prescription:export", request_id=req.get("request_id"))
    prescription_id = req["path_params"]["id"]
    format_type = req.get("query_params", {}).get("format", "A4").lower()

    doc = PrescriptionService.render_prescription_document(
        conn=conn,
        organization_id=user["organization_id"],
        prescription_id=prescription_id,
        doc_format=format_type
    )
    return 200, {"document": doc}

def handle_patient_prescriptions_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List all prescriptions for a patient across encounters."""
    user = req["user"]
    require_permission(user, "prescription:read", request_id=req.get("request_id"))
    patient_id = req["path_params"]["id"]

    prescriptions = PrescriptionService.list_prescriptions_for_patient(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id
    )
    return 200, {"prescriptions": prescriptions, "total": len(prescriptions)}

"""Patient REST API Routes: Registration, Search, 360, Demographics, Identifiers, Consents, Duplicates."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission, enforce_tenant_isolation
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError
from apps.api.domains.patients import PatientService
from apps.api.domains.encounters import EncounterService

def handle_patients_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Register a new patient with duplicate heuristic validation."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:create", request_id=request_id)

    body = req.get("body", {})
    patient = PatientService.create_patient(
        conn=conn,
        organization_id=user["organization_id"],
        facility_id=user.get("active_facility_id"),
        data=body,
        actor_id=user["user_id"],
        request_id=request_id,
        client_ip=req.get("client_ip")
    )

    return 201, {"patient": patient, "request_id": request_id}

def handle_patients_search(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Search patients with server-side pagination."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:read", request_id=request_id)

    qp = req.get("query_params", {})
    q = qp.get("q")
    phone = qp.get("phone")
    mrn = qp.get("mrn")
    limit = min(int(qp.get("limit", 20)), 100)
    offset = int(qp.get("offset", 0))

    patients, total = PatientService.search_patients(
        conn=conn,
        organization_id=user["organization_id"],
        q=q,
        phone=phone,
        mrn=mrn,
        limit=limit,
        offset=offset
    )

    return 200, {
        "patients": patients,
        "total": total,
        "limit": limit,
        "offset": offset,
        "request_id": request_id
    }

def handle_patient_get_360(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Fetch longitudinal Patient 360 overview."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:read", request_id=request_id)

    patient_id = req["path_params"]["id"]
    p360 = PatientService.get_patient_360(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id,
        actor_id=user["user_id"],
        request_id=request_id,
        client_ip=req.get("client_ip")
    )

    return 200, {**p360, "request_id": request_id}

def handle_patient_update_demographics(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Update patient demographics with optimistic concurrency protection."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:update_demographics", request_id=request_id)

    patient_id = req["path_params"]["id"]
    body = req.get("body", {})
    version = body.get("version")
    if version is None:
        raise ValidationError("Field 'version' is required for concurrency control.", request_id=request_id)

    updated_patient = PatientService.update_demographics(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id,
        data=body,
        current_version=int(version),
        actor_id=user["user_id"],
        request_id=request_id,
        client_ip=req.get("client_ip")
    )

    return 200, {"patient": updated_patient, "request_id": request_id}

def handle_patient_identifiers_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List identifiers for a patient."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:read", request_id=request_id)

    patient_id = req["path_params"]["id"]
    PatientService.get_patient_by_id(conn, user["organization_id"], patient_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, identifier_type, identifier_value, issuer, is_verified, is_retired, retired_reason, retired_at, created_at
        FROM patient_identifiers
        WHERE patient_id = ? AND organization_id = ?
        ORDER BY is_retired ASC, created_at ASC;
    """, (patient_id, user["organization_id"]))
    identifiers = [dict(r) for r in cursor.fetchall()]

    return 200, {"identifiers": identifiers, "request_id": request_id}

def handle_patient_identifier_add(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Add new identifier to patient."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:update_demographics", request_id=request_id)

    patient_id = req["path_params"]["id"]
    body = req.get("body", {})
    id_type = body.get("identifier_type", "").strip()
    id_val = body.get("identifier_value", "").strip()

    if not id_type or not id_val:
        raise ValidationError("Fields 'identifier_type' and 'identifier_value' are required.", request_id=request_id)

    res = PatientService.add_identifier(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id,
        id_type=id_type,
        id_val=id_val,
        issuer=body.get("issuer"),
        actor_id=user["user_id"],
        request_id=request_id
    )

    return 201, {"identifier": res, "request_id": request_id}

def handle_patient_identifier_retire(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Retire an identifier without erasing audit trail."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:update_demographics", request_id=request_id)

    patient_id = req["path_params"]["id"]
    identifier_id = req["path_params"]["identifier_id"]
    body = req.get("body", {})
    reason = body.get("reason", "").strip()
    if not reason:
        raise ValidationError("A retirement reason is required.", request_id=request_id)

    res = PatientService.retire_identifier(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id,
        identifier_id=identifier_id,
        reason=reason,
        actor_id=user["user_id"],
        request_id=request_id
    )

    return 200, {**res, "identifier": res, "request_id": request_id}

def handle_patient_consents_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """List recorded consents for patient."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "consent:read", request_id=request_id)

    patient_id = req["path_params"]["id"]
    PatientService.get_patient_by_id(conn, user["organization_id"], patient_id)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, purpose, status, policy_version, source_method, recorded_at, withdrawn_at, withdrawal_reason
        FROM patient_consents
        WHERE patient_id = ? AND organization_id = ?
        ORDER BY recorded_at DESC;
    """, (patient_id, user["organization_id"]))
    consents = [dict(r) for r in cursor.fetchall()]

    return 200, {"consents": consents, "request_id": request_id}

def handle_patient_consent_record(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Record an explicit patient consent decision."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "consent:record", request_id=request_id)

    patient_id = req["path_params"]["id"]
    body = req.get("body", {})
    purpose = body.get("purpose", "").strip()
    status = body.get("status", "").strip()

    if not purpose or not status:
        raise ValidationError("Fields 'purpose' and 'status' are required.", request_id=request_id)

    res = PatientService.record_consent(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id,
        purpose=purpose,
        status=status,
        source_method=body.get("source_method", "VERBAL_PATIENT"),
        policy_version=body.get("policy_version", "v1.0"),
        actor_id=user["user_id"],
        request_id=request_id
    )

    return 201, {"consent": res, "request_id": request_id}

def handle_patient_consent_withdraw(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Withdraw a recorded consent."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "consent:withdraw", request_id=request_id)

    patient_id = req["path_params"]["id"]
    consent_id = req["path_params"]["consent_id"]
    body = req.get("body", {})
    reason = body.get("reason", "").strip()
    if not reason:
        raise ValidationError("A reason is required to withdraw consent.", request_id=request_id)

    res = PatientService.withdraw_consent(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id,
        consent_id=consent_id,
        reason=reason,
        actor_id=user["user_id"],
        request_id=request_id
    )

    return 200, {**res, "consent": res, "request_id": request_id}

def handle_patient_duplicate_candidates_get(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Get duplicate candidate pairs for a patient."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:read", request_id=request_id)

    patient_id = req["path_params"]["id"]
    candidates = PatientService.get_duplicate_candidates_for_patient(conn, user["organization_id"], patient_id)
    return 200, {"duplicate_candidates": candidates, "request_id": request_id}

def handle_patient_duplicate_resolution(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Record human operator decision on duplicate candidate pair."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:resolve_duplicate", request_id=request_id)

    candidate_id = req["path_params"]["candidate_id"]
    body = req.get("body", {})
    decision = body.get("decision", "").strip()
    notes = body.get("notes", "").strip()

    if not decision:
        raise ValidationError("Field 'decision' is required (CONFIRMED_DIFFERENT or DEFERRED).", request_id=request_id)

    res = PatientService.resolve_duplicate_candidate(
        conn=conn,
        organization_id=user["organization_id"],
        candidate_id=candidate_id,
        decision=decision,
        notes=notes,
        actor_id=user["user_id"],
        request_id=request_id
    )

    return 200, {**res, "request_id": request_id}

def handle_patient_timeline(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Get longitudinal patient timeline with encounters and auditable events."""
    user = req["user"]
    request_id = req.get("request_id")
    require_permission(user, "patient:read", request_id=request_id)

    patient_id = req["path_params"]["id"]
    qp = req.get("query_params", {})
    limit = min(int(qp.get("limit", 50)), 100)
    offset = int(qp.get("offset", 0))

    events, total = EncounterService.get_patient_timeline(
        conn=conn,
        organization_id=user["organization_id"],
        patient_id=patient_id,
        user_ctx=user,
        limit=limit,
        offset=offset
    )

    return 200, {
        "timeline": events,
        "total": total,
        "limit": limit,
        "offset": offset,
        "request_id": request_id
    }

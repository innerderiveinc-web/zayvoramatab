"""REST API Route Handlers for Enterprise Interoperability, FHIR APIs & ABDM Integration.

Phase 31 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- interop:read
- interop:write
- interop:admin
- interop:reconcile
"""

import sqlite3
from typing import Any, Dict, Tuple

from apps.api.core.errors import ValidationError
from apps.api.core.permissions import require_permission
from apps.api.domains.interoperability import EnterpriseInteroperabilityEngine


def _get_engine(req: Dict[str, Any]) -> EnterpriseInteroperabilityEngine:
    db_path = req.get("db_path")
    return EnterpriseInteroperabilityEngine(db_path)


# =========================================================================
# 1. Specifications & Profiles
# =========================================================================

def handle_list_specifications(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/interop/specifications"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    qp = req.get("query_params") or {}
    specs = engine.list_specifications(org_id, validation_status=qp.get("status"))
    return 200, {"total": len(specs), "specifications": specs}


def handle_register_specification(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/specifications"""
    user = req["user"]
    require_permission(user, "interop:admin", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    res = engine.register_specification(org_id, actor_id, payload, user_ctx=user)
    return 201, res


def handle_deprecate_specification(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/specifications/deprecate"""
    user = req["user"]
    require_permission(user, "interop:admin", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    spec_code = payload.get("spec_code")
    pinned_version = payload.get("pinned_version")
    if not spec_code or not pinned_version:
        raise ValidationError("spec_code and pinned_version are required.")
    res = engine.deprecate_specification(org_id, actor_id, spec_code, pinned_version, user_ctx=user)
    return 200, res


# =========================================================================
# 2. Terminology Mappings
# =========================================================================

def handle_list_terminology_mappings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/interop/terminology"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    qp = req.get("query_params") or {}
    mappings = engine.list_terminology_mappings(
        org_id, concept_domain=qp.get("concept_domain"), mapping_state=qp.get("mapping_state")
    )
    return 200, {"total": len(mappings), "mappings": mappings}


def handle_upsert_terminology_mapping(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/terminology"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    res = engine.upsert_terminology_mapping(org_id, actor_id, payload, user_ctx=user)
    return 200, res


# =========================================================================
# 3. FHIR R4 Bundle Export
# =========================================================================

def handle_export_encounter_bundle(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/fhir/export-encounter"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    encounter_id = payload.get("encounter_id")
    if not encounter_id:
        raise ValidationError("encounter_id is required.")
    res = engine.generate_encounter_document_bundle(org_id, encounter_id, actor_id, user_ctx=user)
    return 200, res


# =========================================================================
# 4. ABDM Milestones (M1, M2, M3, M4)
# =========================================================================

def handle_verify_abha_identity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/verify-identity"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    abha_number = payload.get("abha_number")
    abha_address = payload.get("abha_address")
    res = engine.verify_abha_identity(org_id, actor_id, abha_number, abha_address, user_ctx=user)
    return 200, res


def handle_link_abha_to_patient(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/link-patient"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    patient_id = payload.get("patient_id")
    abha_number = payload.get("abha_number")
    abha_address = payload.get("abha_address")
    if not patient_id:
        raise ValidationError("patient_id is required.")
    res = engine.link_abha_to_patient(org_id, actor_id, patient_id, abha_number, abha_address, user_ctx=user)
    return 200, res


def handle_discover_care_contexts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/interop/abdm/care-contexts"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    qp = req.get("query_params") or {}
    patient_id = qp.get("patient_id")
    abha_address = qp.get("abha_address", "")
    if not patient_id:
        raise ValidationError("patient_id query param is required.")
    contexts = engine.discover_care_contexts(org_id, patient_id, abha_address)
    return 200, {"patient_id": patient_id, "care_contexts": contexts}


def handle_notify_context_linked(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/notify-context-link"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    patient_id = payload.get("patient_id")
    encounter_id = payload.get("encounter_id")
    if not patient_id or not encounter_id:
        raise ValidationError("patient_id and encounter_id are required.")
    res = engine.notify_care_context_linked(org_id, actor_id, patient_id, encounter_id, user_ctx=user)
    return 200, res


def handle_create_consent_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/consent-requests"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    res = engine.create_consent_request(org_id, actor_id, payload, user_ctx=user)
    return 201, res


def handle_consent_status_callback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/consent-status-callback"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    gateway_req_id = payload.get("gateway_request_id")
    status = payload.get("status")
    artefact = payload.get("consent_artefact")
    if not gateway_req_id or not status:
        raise ValidationError("gateway_request_id and status are required.")
    res = engine.handle_consent_status_callback(
        org_id, gateway_req_id, status, consent_artefact_payload=artefact, user_ctx=user
    )
    return 200, res


def handle_validate_consent_scope(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/validate-consent-scope"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    artefact_id = payload.get("artefact_id")
    hi_type = payload.get("hi_type")
    if not artefact_id or not hi_type:
        raise ValidationError("artefact_id and hi_type are required.")
    res = engine.validate_consent_artefact_scope(org_id, artefact_id, hi_type, payload.get("requested_timestamp"))
    return 200, res


def handle_revoke_consent_artefact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/revoke-consent"""
    user = req["user"]
    require_permission(user, "interop:admin", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    artefact_id = payload.get("artefact_id")
    reason = payload.get("reason", "Clinician or patient requested revocation")
    if not artefact_id:
        raise ValidationError("artefact_id is required.")
    res = engine.revoke_consent_artefact(org_id, actor_id, artefact_id, reason, user_ctx=user)
    return 200, res


def handle_verify_hfr(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/verify-hfr"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    fac_id = payload.get("facility_id", "fac-default")
    hfr_id = payload.get("hfr_id", "")
    res = engine.verify_hfr_facility(org_id, fac_id, hfr_id, user_ctx=user)
    return 200, res


def handle_verify_hpr(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/abdm/verify-hpr"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    prac_id = payload.get("practitioner_id") or user.get("id") or "prac-default"
    hpr_id = payload.get("hpr_id", "")
    res = engine.verify_hpr_practitioner(org_id, prac_id, hpr_id, user_ctx=user)
    return 200, res


# =========================================================================
# 5. Inbound Record Reconciliation Queue
# =========================================================================

def handle_stage_inbound_record(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/inbound/stage"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    res = engine.stage_inbound_record(org_id, payload, user_ctx=user)
    return 201, res


def handle_list_reconciliation_queue(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/interop/inbound/queue"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    qp = req.get("query_params") or {}
    records = engine.list_reconciliation_queue(
        org_id, patient_id=qp.get("patient_id"), status=qp.get("status", "PENDING_REVIEW")
    )
    return 200, {"total": len(records), "records": records}


def handle_reconcile_record(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/inbound/reconcile"""
    user = req["user"]
    require_permission(user, "interop:reconcile", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    actor_id = user.get("id") or user.get("user_id") or "sys"
    payload = req.get("body") or {}
    record_id = payload.get("record_id")
    decision = payload.get("decision")
    notes = payload.get("decision_notes")
    if not record_id or not decision:
        raise ValidationError("record_id and decision are required.")
    res = engine.reconcile_inbound_record(org_id, record_id, actor_id, decision, notes, user_ctx=user)
    return 200, res


# =========================================================================
# 6. Outbox & Webhooks
# =========================================================================

def handle_enqueue_outbox(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/outbox/enqueue"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    job_type = payload.get("job_type", "FHIR_DOCUMENT_EXPORT")
    destination = payload.get("destination_endpoint", "https://api.abdm.gov.in/v0.5/data/transfer")
    data_dict = payload.get("payload", {})
    res = engine.enqueue_outbox_job(
        org_id,
        job_type,
        destination,
        data_dict,
        idempotency_key=payload.get("idempotency_key"),
        facility_id=payload.get("facility_id"),
        metadata=payload.get("metadata"),
        user_ctx=user,
    )
    return 201, res


def handle_list_outbox_jobs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/interop/outbox/jobs"""
    user = req["user"]
    require_permission(user, "interop:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    qp = req.get("query_params") or {}
    jobs = engine.list_outbox_jobs(org_id, delivery_status=qp.get("status"))
    return 200, {"total": len(jobs), "jobs": jobs}


def handle_dispatch_outbox(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/outbox/dispatch"""
    user = req["user"]
    require_permission(user, "interop:admin", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    job_id = payload.get("job_id")
    if not job_id:
        raise ValidationError("job_id is required.")
    res = engine.dispatch_outbox_job(org_id, job_id, user_ctx=user)
    return 200, res


def handle_verify_webhook(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/interop/webhooks/verify"""
    user = req["user"]
    require_permission(user, "interop:write", request_id=req.get("request_id"))
    engine = _get_engine(req)
    org_id = user["organization_id"]
    payload = req.get("body") or {}
    req_id = payload.get("request_id")
    ts_header = payload.get("timestamp_header")
    body_str = payload.get("payload_body", "{}")
    sig_header = payload.get("signature_header")
    source_sys = payload.get("source_system", "ABDM_GATEWAY")
    if not req_id or not ts_header:
        raise ValidationError("request_id and timestamp_header are required.")
    res = engine.verify_inbound_webhook(
        org_id, req_id, ts_header, body_str, signature_header=sig_header, source_system=source_sys, user_ctx=user
    )
    return 200, res

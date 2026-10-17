"""KAVS (Knowledge Authenticity, Verification & Clinical Safety) REST Route Handlers.
Compatible with ApiRouter dispatch: handle_xxx(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]].
"""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError
from apps.api.domains.kavs import KAVSEngine


def _get_engine(req: Dict[str, Any] = None) -> KAVSEngine:
    db_path = req.get("db_path") if req else None
    return KAVSEngine(db_path=db_path)


# --------------------------------------------------------------------------
# 1. Governed Source Registry & Versioning
# --------------------------------------------------------------------------

def handle_create_source(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_source(body, user["user_id"])
    return 201, {"source": result}


def handle_list_sources(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/sources"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    params = req.get("query_params", {})
    result = engine.list_sources(params)
    return 200, {"sources": result, "total": len(result)}


def handle_get_source(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/sources/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    source_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_source(source_id)
    return 200, {"source": result}


def handle_update_source(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PATCH /api/v1/kavs/sources/{id}"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    source_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.update_source(source_id, body, user["user_id"])
    return 200, {"source": result}


def handle_list_source_versions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/sources/{id}/versions"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    source_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.list_source_versions(source_id)
    return 200, {"source_versions": result, "total": len(result)}


def handle_register_source_version_for_source(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources/{id}/versions"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    source_id = req["path_params"]["id"]
    body = req.get("body", {})
    body["source_id"] = source_id
    engine = _get_engine(req)
    result = engine.register_source_version(body, user["user_id"])
    return 201, {"source_version": result}


def handle_register_source_version(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources/versions"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.register_source_version(body, user["user_id"])
    return 201, {"source_version": result}


def handle_get_source_version(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/sources/versions/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    version_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_source_version(version_id)
    return 200, {"source_version": result}


def handle_record_rights_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources/rights-reviews"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.record_rights_review(body, user["user_id"])
    return 201, {"rights_review": result}


def handle_preflight_rights(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources/versions/{id}/preflight-rights"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    version_id = req["path_params"]["id"]
    body = req.get("body", {})
    op = body.get("operation") or body.get("requested_operation", "INGEST")
    engine = _get_engine(req)
    result = engine.check_source_rights_preflight(version_id, op, user["user_id"])
    return 200, {"preflight": result}


def handle_upload_source_file(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources/versions/{id}/upload-file"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    version_id = req["path_params"]["id"]
    body = req.get("body", {})
    filename = body.get("filename", "source_document.pdf")

    file_bytes = b""
    if "file_base64" in body:
        import base64
        file_bytes = base64.b64decode(body["file_base64"])
    elif "file_content" in body:
        file_bytes = body["file_content"].encode("utf-8")
    elif req.get("body_bytes"):
        file_bytes = req["body_bytes"]

    engine = _get_engine(req)
    result = engine.upload_source_file(
        source_version_id=version_id,
        filename=filename,
        file_bytes=file_bytes,
        user_id=user["user_id"],
        mime_type=body.get("mime_type"),
        page_count_estimate=int(body.get("page_count_estimate", 0)),
        storage_tier=body.get("storage_tier", "LOCAL_ENCRYPTED")
    )
    return 201, {"source_file": result}


def handle_get_source_file(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/source-files/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    file_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_source_file(file_id)
    return 200, {"source_file": result}


# --------------------------------------------------------------------------
# 2. Source Locators (Exact Citation Anchors)
# --------------------------------------------------------------------------

def handle_create_source_locator(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources/versions/{id}/locators"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    version_id = req["path_params"]["id"]
    body = req.get("body", {})
    body["source_version_id"] = version_id
    engine = _get_engine(req)
    result = engine.create_source_locator(body, user["user_id"])
    return 201, {"locator": result}


def handle_list_source_locators(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/sources/versions/{id}/locators"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    version_id = req["path_params"].get("id")
    engine = _get_engine(req)
    result = engine.list_source_locators(version_id)
    return 200, {"locators": result, "total": len(result)}


def handle_verify_source_locator(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/locators/{id}/verify"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    locator_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.verify_source_locator(locator_id, body, user["user_id"])
    return 200, {"locator": result}


# --------------------------------------------------------------------------
# 3. Source Verification Events
# --------------------------------------------------------------------------

def handle_record_source_verification_event(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/sources/{id}/verification-events"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    source_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.record_source_verification_event(source_id, body, user["user_id"])
    return 201, {"verification_event": result}


def handle_list_source_verification_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/sources/{id}/verification-events"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    source_id = req["path_params"].get("id")
    engine = _get_engine(req)
    result = engine.list_source_verification_events(source_id)
    return 200, {"verification_events": result, "total": len(result)}


# --------------------------------------------------------------------------
# 4. Governance Policy Registry
# --------------------------------------------------------------------------

def handle_register_governance_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/policies"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.register_governance_policy(body, user["user_id"])
    return 201, {"policy": result}


def handle_list_governance_policies(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/policies"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    result = engine.list_governance_policies()
    return 200, {"policies": result, "total": len(result)}


def handle_get_active_governance_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/policies/active"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    result = engine.get_active_governance_policy()
    return 200, {"policy": result}


# --------------------------------------------------------------------------
# 5. Atomic Claim Lifecycle & Review Workflow
# --------------------------------------------------------------------------

def handle_create_atomic_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_atomic_claim(body, user["user_id"])
    return 201, {"claim": result}


def handle_list_atomic_claims(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/claims"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    params = req.get("query_params", {})
    result = engine.list_atomic_claims(params)
    return 200, {"claims": result, "total": len(result)}


def handle_get_atomic_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/claims/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_atomic_claim(claim_id)
    return 200, {"claim": result}


def handle_submit_claim_for_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims/{id}/submit-review"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.submit_claim_for_review(claim_id, user["user_id"])
    return 200, {"claim": result}


def handle_approve_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims/{id}/approve"""
    user = req["user"]
    require_permission(user, "kavs:approve", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.approve_claim(claim_id, body, user["user_id"])
    return 200, {"claim": result}


def handle_reject_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims/{id}/reject"""
    user = req["user"]
    require_permission(user, "kavs:approve", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.reject_claim(claim_id, body, user["user_id"])
    return 200, {"claim": result}


def handle_withdraw_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims/{id}/withdraw"""
    user = req["user"]
    require_permission(user, "kavs:approve", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.withdraw_claim(claim_id, body, user["user_id"])
    return 200, {"claim": result}


# --------------------------------------------------------------------------
# 6. Ingestion & Extraction Jobs & Workbench
# --------------------------------------------------------------------------

def handle_create_ingestion_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs or POST /api/v1/kavs/ingestion-jobs"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_ingestion_job(body, user["user_id"])
    return 201, {"job": result}


def handle_get_ingestion_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/ingestion/jobs/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_ingestion_job(job_id)
    return 200, {"job": result}


def handle_list_ingestion_jobs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/ingestion/jobs"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    params = req.get("query_params", {})
    result = engine.list_ingestion_jobs(params)
    return 200, {"jobs": result, "total": len(result)}


def handle_transition_ingestion_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs/{id}/transition"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    body = req.get("body", {})
    to_state = body.get("to_state") or body.get("target_state")
    if not to_state:
        raise ValidationError("Missing 'to_state' in transition request")
    engine = _get_engine(req)
    result = engine.transition_ingestion_job(
        job_id=job_id,
        to_state=to_state,
        user_id=user["user_id"],
        event_type=body.get("event_type", "MANUAL_TRANSITION"),
        message=body.get("message", ""),
        payload=body.get("payload")
    )
    return 200, {"job": result}


def handle_cancel_ingestion_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs/{id}/cancel"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason", "Cancelled by user")
    engine = _get_engine(req)
    result = engine.cancel_ingestion_job(job_id, reason, user["user_id"])
    return 200, {"job": result}


def handle_retry_ingestion_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs/{id}/retry"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.retry_ingestion_job(job_id, user["user_id"])
    return 200, {"job": result}


def handle_add_extraction_page(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs/{id}/pages"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_extraction_page(job_id, body, user["user_id"])
    return 201, {"page": result}


def handle_list_extraction_pages(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/ingestion/jobs/{id}/pages"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.list_extraction_pages(job_id)
    return 200, {"pages": result, "total": len(result)}


def handle_get_extraction_page(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/extraction-pages/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    page_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_extraction_page(page_id)
    return 200, {"page": result}


def handle_add_extraction_segment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs/{id}/segments"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_extraction_segment(job_id, body)
    return 201, {"segment": result}


def handle_get_extraction_segment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/extraction-segments/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    segment_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_extraction_segment(segment_id)
    return 200, {"segment": result}


def handle_record_segment_correction(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/extraction-segments/{id}/corrections"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    segment_id = req["path_params"]["id"]
    body = req.get("body", {})
    corrected_text = body.get("corrected_text", "")
    reason = body.get("correction_reason", "")
    engine = _get_engine(req)
    result = engine.record_segment_correction(segment_id, {
        "corrected_text": corrected_text,
        "correction_reason": reason
    }, user["user_id"])
    return 200, {"segment": result}


def handle_mark_segment_unreadable(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/extraction-segments/{id}/mark-unreadable"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    segment_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason", "Marked unreadable by reviewer")
    engine = _get_engine(req)
    result = engine.mark_segment_unreadable(segment_id, reason, user["user_id"])
    return 200, {"segment": result}


def handle_review_extraction_segment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/segments/{id}/review"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    segment_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.review_extraction_segment(segment_id, body, user["user_id"])
    return 200, {"segment_review": result}


def handle_add_extraction_table(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs/{id}/tables"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_extraction_table(job_id, body, user["user_id"])
    return 201, {"table": result}


def handle_list_extraction_tables(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/ingestion/jobs/{id}/tables"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.list_extraction_tables(job_id)
    return 200, {"tables": result, "total": len(result)}


def handle_create_claim_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claim-drafts"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_claim_draft(body, user["user_id"])
    return 201, {"draft": result}


def handle_list_claim_drafts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/claim-drafts"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    params = req.get("query_params", {})
    result = engine.list_claim_drafts(params)
    return 200, {"drafts": result, "total": len(result)}


def handle_get_claim_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/claim-drafts/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    draft_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_claim_draft(draft_id)
    return 200, {"draft": result}


def handle_submit_claim_draft_for_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claim-drafts/{id}/submit-review"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    draft_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.submit_claim_draft_for_review(draft_id, user["user_id"])
    return 200, {"draft": result}


def handle_reject_claim_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claim-drafts/{id}/reject"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    draft_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason", "Rejected during extraction review")
    engine = _get_engine(req)
    result = engine.reject_claim_draft(draft_id, reason, user["user_id"])
    return 200, {"draft": result}


def handle_promote_draft_to_atomic_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claim-drafts/{id}/promote"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    draft_id = req["path_params"]["id"]
    body = req.get("body", {})
    overrides = body.get("overrides")
    engine = _get_engine(req)
    result = engine.promote_draft_to_atomic_claim(draft_id, user["user_id"], overrides)
    return 201, {"claim": result}


def handle_get_ingestion_quality(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/ingestion-quality"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    result = engine.get_ingestion_quality_metrics()
    return 200, {"quality_metrics": result}


def handle_get_ingestion_queue_health(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/ingestion-queue/health"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    result = engine.get_ingestion_queue_health()
    return 200, {"queue_health": result}


# --------------------------------------------------------------------------
# 7. Five-Dimension Claim Verification Record
# --------------------------------------------------------------------------

def handle_record_claim_verification(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims/{id}/verifications"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.record_claim_verification(claim_id, body, user["user_id"])
    return 201, {"claim_verification": result}


def handle_get_claim_verification(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/verifications/{id}"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    verif_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_claim_verification(verif_id)
    return 200, {"claim_verification": result}


# --------------------------------------------------------------------------
# 8. Evidence Contradiction Links
# --------------------------------------------------------------------------

def handle_link_evidence_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims/{id}/conflicts"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.link_evidence_conflict(claim_id, body, user["user_id"])
    return 201, {"conflict_link": result}


# --------------------------------------------------------------------------
# 9. Knowledge Releases & Manifests
# --------------------------------------------------------------------------

def handle_publish_knowledge_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/releases"""
    user = req["user"]
    require_permission(user, "kavs:release", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.publish_knowledge_release(body, user["user_id"])
    return 201, {"release": result}


def handle_withdraw_knowledge_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/releases/{tag}/withdraw"""
    user = req["user"]
    require_permission(user, "kavs:release", request_id=req.get("request_id"))
    tag = req["path_params"]["tag"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.withdraw_knowledge_release(tag, body.get("reason", ""), user["user_id"])
    return 200, {"release": result}


# --------------------------------------------------------------------------
# 10. Change-Impact Dependency Engine
# --------------------------------------------------------------------------

def handle_record_change_impact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/impact-events"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.record_change_impact(body, user["user_id"])
    return 201, {"change_impact": result}


# --------------------------------------------------------------------------
# 11. Consultation Contextual Retrieval
# --------------------------------------------------------------------------

def handle_retrieve_verified_context(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/retrieve"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.retrieve_verified_clinical_context(
        query=body.get("query", ""),
        domain=body.get("domain"),
        intended_use=body.get("intended_use", "clinician_contextual_reference"),
        limit=int(body.get("limit", 10))
    )
    return 200, result


# --------------------------------------------------------------------------
# 12. Audit Trail
# --------------------------------------------------------------------------

def handle_list_kavs_audit_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/kavs/audit-events"""
    user = req["user"]
    require_permission(user, "kavs:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    params = req.get("query_params", {})
    result = engine.list_kavs_audit_events(params)
    return 200, {"audit_events": result, "total": len(result)}

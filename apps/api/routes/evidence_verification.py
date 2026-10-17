"""REST API Route Handlers for Evidence Classification, Claim Verification & Citation Validation.

Phase 21 Endpoints for ZAYVORA MATAB OS.
Governed by permission-aware access control:
- knowledge:read / kavs:read
- knowledge:manage / kavs:manage
- knowledge:review / kavs:verify
- knowledge:approve / kavs:approve
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.evidence_verification import EvidenceVerificationEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError

def _get_engine(req: Dict[str, Any]) -> EvidenceVerificationEngine:
    db_path = req.get("db_path")
    return EvidenceVerificationEngine(db_path)



# --------------------------------------------------------------------------
# 1. Claim-Type Registry Handlers
# --------------------------------------------------------------------------

def handle_list_claim_types(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/claim-types"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    types_list = engine.list_claim_types()
    return 200, {"claim_types": types_list, "total": len(types_list)}


# --------------------------------------------------------------------------
# 2. Knowledge Claims Handlers
# --------------------------------------------------------------------------

def handle_create_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/claims"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_claim(body, user["user_id"])
    return 201, {"claim": result}


def handle_get_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/claims/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_claim(claim_id)
    return 200, {"claim": result}


def handle_list_claims(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/claims"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_claims(
        claim_type=params.get("claim_type"),
        approval_state=params.get("approval_state")
    )
    return 200, {"claims": results, "total": len(results)}


# --------------------------------------------------------------------------
# 3. Claim-Source Links Handlers
# --------------------------------------------------------------------------

def handle_link_claim_to_source(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/claims/{id}/source-links"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.link_claim_to_source(claim_id, body, user["user_id"])
    return 201, {"source_link": result}


def handle_list_claim_source_links(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/claims/{id}/source-links"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    engine = _get_engine(req)
    results = engine.list_claim_source_links(claim_id)
    return 200, {"source_links": results, "total": len(results)}


# --------------------------------------------------------------------------
# 4. Citation Validation Runs Handlers
# --------------------------------------------------------------------------

def handle_validate_citation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/citations/validate"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    link_id = body.get("claim_source_link_id")
    if not link_id:
        raise ValidationError("claim_source_link_id is required in body.")

    engine = _get_engine(req)
    result = engine.validate_citation(link_id, user, run_params=body)
    return 200, {"validation_run": result}


def handle_get_validation_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/citations/validation-runs/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    run_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_validation_run(run_id)
    return 200, {"validation_run": result}


# --------------------------------------------------------------------------
# 5. Support Assessments Handlers
# --------------------------------------------------------------------------

def handle_create_support_assessment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/support-assessments"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_support_assessment(body, user["user_id"])
    return 201, {"support_assessment": result}


def handle_review_support_assessment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/support-assessments/{id}/review"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    sa_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.review_support_assessment(
        assessment_id=sa_id,
        user_ctx=user,
        decision=body.get("decision", "approved"),
        rationale=body.get("rationale", "")
    )
    return 200, {"support_assessment": result}


# --------------------------------------------------------------------------
# 6. Question-Sensitive Evidence Characterization Handlers
# --------------------------------------------------------------------------

def handle_create_characterization(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/characterizations"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_evidence_characterization(body, user["user_id"])
    return 201, {"evidence_characterization": result}


def handle_review_characterization(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/characterizations/{id}/review"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    ec_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.review_evidence_characterization(
        characterization_id=ec_id,
        user_ctx=user,
        review_state=body.get("review_state", "approved"),
        rationale=body.get("rationale", "")
    )
    return 200, {"evidence_characterization": result}


# --------------------------------------------------------------------------
# 7. Source Status Events Handlers
# --------------------------------------------------------------------------

def handle_record_source_status_event(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/sources/{id}/status-events"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    src_ver_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.record_source_status_event(src_ver_id, body, user["user_id"])
    return 201, {"status_event": result}


def handle_list_source_status_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/sources/{id}/status-events"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    src_ver_id = req["path_params"]["id"]
    engine = _get_engine(req)
    results = engine.list_source_status_events(source_version_id=src_ver_id)
    return 200, {"status_events": results, "total": len(results)}


# --------------------------------------------------------------------------
# 8. Intended-Use Approvals Handlers
# --------------------------------------------------------------------------

def handle_create_intended_use_approval(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/intended-use-approvals"""
    user = req["user"]
    require_permission(user, "knowledge:approve", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_intended_use_approval(body, user)
    return 201, {"intended_use_approval": result}


def handle_suspend_intended_use_approval(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/intended-use-approvals/{id}/suspend"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    appr_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.suspend_intended_use_approval(appr_id, user, body.get("reason", "Suspended by user"))
    return 200, {"intended_use_approval": result}


# --------------------------------------------------------------------------
# 9. Evidence Conflicts Handlers
# --------------------------------------------------------------------------

def handle_create_evidence_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/conflicts"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_evidence_conflict(body, user["user_id"])
    return 201, {"conflict": result}


def handle_list_evidence_conflicts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/conflicts"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_evidence_conflicts(status=params.get("status"))
    return 200, {"conflicts": results, "total": len(results)}


def handle_resolve_evidence_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/evidence/conflicts/{id}/resolve"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    conflict_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.resolve_evidence_conflict(
        conflict_id=conflict_id,
        user_ctx=user,
        status=body.get("status", "resolved_with_scope"),
        rationale=body.get("rationale", "")
    )
    return 200, {"conflict": result}


# --------------------------------------------------------------------------
# 10. Clinician Context Retrieval Panel Handler
# --------------------------------------------------------------------------

def handle_get_clinician_context_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/evidence/clinician-context/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_clinician_context_claim(claim_id)
    return 200, result

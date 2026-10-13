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


# 1. Source Versions & Rights Reviews
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


# 2. Ingestion & Extraction Jobs
def handle_create_ingestion_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_ingestion_job(body, user["user_id"])
    return 201, {"job": result}


def handle_add_extraction_segment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/jobs/{id}/segments"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    job_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_extraction_segment(job_id, body)
    return 201, {"segment": result}


def handle_review_extraction_segment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/ingestion/segments/{id}/review"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    segment_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.review_extraction_segment(segment_id, body, user["user_id"])
    return 200, {"segment_review": result}


# 3. Five-Dimension Claim Verification
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


# 4. Evidence Contradiction Links
def handle_link_evidence_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/claims/{id}/conflicts"""
    user = req["user"]
    require_permission(user, "kavs:verify", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.link_evidence_conflict(claim_id, body, user["user_id"])
    return 201, {"conflict_link": result}


# 5. Knowledge Releases & Manifests
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


# 6. Change-Impact Dependency Engine
def handle_record_change_impact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/kavs/impact-events"""
    user = req["user"]
    require_permission(user, "kavs:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.record_change_impact(body, user["user_id"])
    return 201, {"change_impact": result}


# 7. Consultation Contextual Retrieval
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

"""REST API Route Handlers for Hybrid Clinical RAG & Answer Generation Engine.

Phase 22 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- knowledge:read
- knowledge:manage
- knowledge:review
- knowledge:approve
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.clinical_rag import ClinicalRAGEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> ClinicalRAGEngine:
    db_path = req.get("db_path")
    return ClinicalRAGEngine(db_path)


# --------------------------------------------------------------------------
# 1. Retrieval & Search Endpoints
# --------------------------------------------------------------------------

def handle_search_knowledge(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/retrieval/search"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    body = req.get("body", {})
    query = body.get("query_text") or body.get("query")
    if not query:
        raise ValidationError("query_text is required.")

    surface = body.get("requested_surface", "clinician_context")
    limit = int(body.get("limit", 10))
    filters = body.get("filters", {})

    engine = _get_engine(req)
    result = engine.search_knowledge(
        query_text=query,
        user_ctx=user,
        requested_surface=surface,
        limit=limit,
        filters=filters
    )
    return 200, result


def handle_create_evidence_pack(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/retrieval/evidence-pack"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    body = req.get("body", {})
    query = body.get("query_text") or body.get("query")
    if not query:
        raise ValidationError("query_text is required.")

    surface = body.get("requested_surface", "clinician_context")
    enc_id = body.get("encounter_id")

    engine = _get_engine(req)
    result = engine.build_evidence_pack(
        query_text=query,
        user_ctx=user,
        requested_surface=surface,
        encounter_id=enc_id
    )
    return 201, {"evidence_pack": result}


def handle_get_evidence_pack(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/retrieval/packs/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    pack_id = req["path_params"]["id"]

    engine = _get_engine(req)
    result = engine.get_evidence_pack(pack_id)
    return 200, {"evidence_pack": result}


# --------------------------------------------------------------------------
# 2. Answer Generation & Validation Endpoints
# --------------------------------------------------------------------------

def handle_generate_answer_draft(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/answers/draft"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    body = req.get("body", {})
    pack_id = body.get("evidence_pack_id")
    if not pack_id:
        raise ValidationError("evidence_pack_id is required.")

    engine = _get_engine(req)
    pack = engine.get_evidence_pack(pack_id)
    # Dereference included passages and claims
    search_res = engine.search_knowledge(
        query_text=pack["query_text"],
        user_ctx=user,
        requested_surface=pack["requested_surface"],
        limit=10
    )
    pack["included_passages"] = search_res["passages"]
    pack["included_claims"] = search_res["claims"]
    pack["concept_resolution"] = search_res["concept_resolution"]

    result = engine.generate_answer(pack, user)
    return 201, {"answer": result}


def handle_validate_answer(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/answers/validate"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    body = req.get("body", {})
    run_id = body.get("answer_run_id")
    if not run_id:
        raise ValidationError("answer_run_id is required.")

    engine = _get_engine(req)
    result = engine.validate_answer(run_id, user)
    return 200, {"validation": result}


def handle_orchestrated_answer(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/answers (Full orchestrated RAG workflow)"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    body = req.get("body", {})
    query = body.get("query_text") or body.get("query")
    if not query:
        raise ValidationError("query_text is required.")

    surface = body.get("requested_surface", "clinician_context")
    enc_id = body.get("encounter_id")

    engine = _get_engine(req)
    # 1. Build evidence pack
    pack = engine.build_evidence_pack(
        query_text=query,
        user_ctx=user,
        requested_surface=surface,
        encounter_id=enc_id
    )

    # 2. Generate structured answer
    answer = engine.generate_answer(pack, user)

    # 3. Validate answer
    validation = engine.validate_answer(answer["id"], user)

    return 201, {
        "answer": answer,
        "validation": validation,
        "evidence_pack_id": pack["id"]
    }


def handle_get_answer(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/answers/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    run_id = req["path_params"]["id"]

    engine = _get_engine(req)
    result = engine.get_answer(run_id)
    return 200, {"answer": result}


def handle_get_answer_citations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/answers/{id}/citations"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    run_id = req["path_params"]["id"]

    engine = _get_engine(req)
    citations = engine.get_citations_for_run(run_id)
    return 200, {"citations": citations, "total": len(citations)}


# --------------------------------------------------------------------------
# 3. Retrieval Feedback Endpoints
# --------------------------------------------------------------------------

def handle_create_retrieval_feedback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/retrieval/feedback"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})

    engine = _get_engine(req)
    result = engine.record_feedback(body, user["user_id"])
    return 201, {"feedback": result}


def handle_list_retrieval_feedback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/retrieval/feedback"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})

    engine = _get_engine(req)
    results = engine.list_feedback(status=params.get("status"))
    return 200, {"feedback_items": results, "total": len(results)}


def handle_resolve_retrieval_feedback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/retrieval/feedback/{id}/resolve"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    fb_id = req["path_params"]["id"]
    body = req.get("body", {})
    notes = body.get("resolution_notes") or body.get("notes") or "Feedback addressed by reviewer."
    status = body.get("status", "resolved")

    engine = _get_engine(req)
    result = engine.resolve_feedback(fb_id, notes, status)
    return 200, {"feedback": result}

"""Modern & Governed Clinical Knowledge Route Handlers.
Compatible with ApiRouter dispatch: handle_xxx(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]].
"""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError
from apps.api.domains.knowledge import KnowledgeRetrievalEngine


def _get_engine(conn: sqlite3.Connection) -> KnowledgeRetrievalEngine:
    # Use existing database connection manager or pass connection path
    engine = KnowledgeRetrievalEngine()
    return engine


# 1. Sources Registry Handlers
def handle_create_source(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/sources"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(conn)
    result = engine.register_source(body, user["user_id"])
    return 201, {"source": result}


def handle_get_source(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/sources/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    source_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    result = engine.get_source(source_id)
    return 200, {"source": result}


def handle_list_sources(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/sources"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    source_type = qp.get("source_type")
    review_status = qp.get("review_status")
    limit = int(qp.get("limit", 50))
    offset = int(qp.get("offset", 0))
    engine = _get_engine(conn)
    result = engine.list_sources(source_type, review_status, limit, offset)
    return 200, result


# 2. Knowledge Items Handlers
def handle_create_knowledge_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/items"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(conn)
    result = engine.create_knowledge_item(body, user["user_id"])
    return 201, {"item": result}


def handle_get_knowledge_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/items/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    item_id = req["path_params"]["id"]
    allow_unapproved = "knowledge:manage" in user.get("permissions", [])
    engine = _get_engine(conn)
    result = engine.get_knowledge_item(item_id, allow_unapproved=allow_unapproved)
    return 200, {"item": result}


def handle_list_knowledge_items(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/items"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    domain = qp.get("domain")
    entity_type = qp.get("entity_type")
    status = qp.get("status", "approved")
    if "knowledge:manage" not in user.get("permissions", []) and status != "approved":
        status = "approved"
    limit = int(qp.get("limit", 50))
    offset = int(qp.get("offset", 0))
    engine = _get_engine(conn)
    result = engine.list_knowledge_items(domain, entity_type, status, limit, offset)
    return 200, result


# 3. Claims Handlers
def handle_create_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/claims"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(conn)
    result = engine.create_claim(body, user["user_id"])
    return 201, {"claim": result}


def handle_get_claim(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/claims/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    claim_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    result = engine.get_claim(claim_id)
    return 200, {"claim": result}


# 4. Evidence Handlers
def handle_create_evidence(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/evidence"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(conn)
    result = engine.create_evidence(body, user["user_id"])
    return 201, {"evidence": result}


def handle_get_evidence(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/evidence/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    evidence_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    result = engine.get_evidence(evidence_id)
    return 200, {"evidence": result}


# 5. Search & Clinical Retrieval Handlers
def handle_search_knowledge(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/search"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    query = qp.get("q", "")
    domain = qp.get("domain")
    only_approved = qp.get("include_drafts") != "true" or "knowledge:manage" not in user.get("permissions", [])
    limit = int(qp.get("limit", 20))
    engine = _get_engine(conn)
    results = engine.search_knowledge(
        query=query,
        domain=domain,
        only_approved=only_approved,
        limit=limit
    )
    return 200, {"query": query, "results": results, "count": len(results)}


def handle_retrieve_context(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/retrieve"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    body = req.get("body", {})
    context = body.get("encounter_context", {})
    org_id = user.get("organization_id", "org-default")
    user_role = user.get("role", "practitioner")
    engine = _get_engine(conn)
    result = engine.retrieve_clinical_context(context, org_id, user_role)
    return 200, result


def handle_get_citation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/citations/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    citation_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    result = engine.get_citation(citation_id)
    return 200, {"citation": result}


def handle_synthesize_evidence(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/items/{id}/synthesize"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    item_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    result = engine.synthesize_evidence(item_id)
    return 200, {"synthesis": result}


# 6. Governance Review Handlers
def handle_approve_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/review/{id}/approve"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    item_id = req["path_params"]["id"]
    body = req.get("body", {})
    comments = body.get("comments", "Approved following clinical review")
    engine = _get_engine(conn)
    result = engine.approve_knowledge_item(item_id, user["user_id"], comments)
    return 200, result


def handle_reject_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/review/{id}/reject"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    item_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason", "")
    engine = _get_engine(conn)
    result = engine.reject_knowledge_item(item_id, user["user_id"], reason)
    return 200, result


def handle_request_changes_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/review/{id}/request-changes"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    item_id = req["path_params"]["id"]
    body = req.get("body", {})
    comments = body.get("comments", "")
    engine = _get_engine(conn)
    result = engine.request_changes_knowledge_item(item_id, user["user_id"], comments)
    return 200, result


def handle_get_review_queue(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/review/queue"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    status = qp.get("status", "under_review")
    limit = int(qp.get("limit", 50))
    engine = _get_engine(conn)
    result = engine.list_review_queue(status, limit)
    return 200, {"queue": result, "count": len(result)}


def handle_get_review_logs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/audit-logs/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    entity_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    result = engine.get_review_logs(entity_id)
    return 200, {"entity_id": entity_id, "logs": result}

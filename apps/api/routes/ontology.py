"""REST API Route Handlers for Unani Ontology & Canonical Materia-Medica Catalog.

Phase 19 Endpoints for ZAYVORA MATAB OS.
Governed by permission-aware access control:
- knowledge:read / kavs:read
- knowledge:manage / kavs:manage
- knowledge:review / kavs:verify
- knowledge:approve / kavs:approve
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.ontology import UnaniOntologyEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError

_engine_instance: Optional[UnaniOntologyEngine] = None


def _get_engine(req: Dict[str, Any]) -> UnaniOntologyEngine:
    global _engine_instance
    if _engine_instance is None:
        db_path = req.get("db_path")
        _engine_instance = UnaniOntologyEngine(db_path)
    return _engine_instance


def _can_review(user: Dict[str, Any]) -> bool:
    perms = user.get("permissions", [])
    roles = user.get("roles", [])
    return any(p in perms for p in ["knowledge:review", "kavs:verify", "knowledge:approve", "kavs:approve", "knowledge:manage", "kavs:manage"]) or any(r in roles for r in ["ORG_ADMIN", "SYSTEM_ADMIN", "UNANI_SCHOLAR", "CLINICAL_DIRECTOR"])


# --------------------------------------------------------------------------
# 1. Concept Identity Handlers
# --------------------------------------------------------------------------

def handle_create_concept(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/concepts"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_concept(body, user["user_id"])
    return 201, {"concept": result}


def handle_get_concept(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ontology/concepts/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    concept_id = req["path_params"]["id"]
    engine = _get_engine(req)
    include_unapproved = _can_review(user)
    result = engine.get_concept(concept_id, include_unapproved=include_unapproved)
    return 200, {"concept": result}


def handle_update_concept(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PATCH /api/v1/ontology/concepts/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    concept_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.update_concept(concept_id, body, user["user_id"])
    return 200, {"concept": result}


def handle_list_concepts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ontology/concepts"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    include_unapproved = _can_review(user)
    result = engine.list_concepts(params, include_unapproved=include_unapproved)
    return 200, {"concepts": result, "total": len(result)}


# --------------------------------------------------------------------------
# 2. Multi-Script Names & Aliases Handlers
# --------------------------------------------------------------------------

def handle_add_concept_name(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/concepts/{id}/names"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    concept_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_concept_name(concept_id, body, user["user_id"])
    return 201, {"name": result}


def handle_review_concept_name(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/names/{id}/decision"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    name_id = req["path_params"]["id"]
    body = req.get("body", {})
    decision = body.get("decision")
    rationale = body.get("rationale", "")
    engine = _get_engine(req)
    result = engine.review_concept_name(name_id, decision, user["user_id"], rationale)
    return 200, {"name": result}


# --------------------------------------------------------------------------
# 3. Mufradat Material Identity Handlers
# --------------------------------------------------------------------------

def handle_set_material_identity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/concepts/{id}/materials"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    concept_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.set_material_identity(concept_id, body, user["user_id"])
    return 200, {"material_identity": result}


# --------------------------------------------------------------------------
# 4. Murakkabat Formulation Catalog Handlers
# --------------------------------------------------------------------------

def handle_create_catalog_formulation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/concepts/{id}/formulations"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    concept_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_catalog_formulation(concept_id, body, user["user_id"])
    return 201, {"formulation": result}


def handle_add_formulation_ingredient(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/formulations/{id}/components"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    formulation_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_formulation_ingredient(formulation_id, body, user["user_id"])
    return 201, {"ingredient": result}


# --------------------------------------------------------------------------
# 5. Provenance-Bound Knowledge Assertions Handlers
# --------------------------------------------------------------------------

def handle_create_knowledge_assertion(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/concepts/{id}/assertions"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    subject_concept_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_knowledge_assertion(subject_concept_id, body, user["user_id"])
    return 201, {"assertion": result}


def handle_review_knowledge_assertion(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/assertions/{id}/decision"""
    user = req["user"]
    require_permission(user, "knowledge:approve", request_id=req.get("request_id"))
    assertion_id = req["path_params"]["id"]
    body = req.get("body", {})
    decision = body.get("decision")
    intended_use = body.get("approved_intended_use")
    rationale = body.get("rationale", "")
    engine = _get_engine(req)
    result = engine.review_knowledge_assertion(assertion_id, decision, user["user_id"], intended_use, rationale)
    return 200, {"assertion": result}


def handle_withdraw_knowledge_assertion(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/assertions/{id}/withdraw"""
    user = req["user"]
    require_permission(user, "knowledge:approve", request_id=req.get("request_id"))
    assertion_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason", "Withdrawn by clinical governance lead")
    engine = _get_engine(req)
    result = engine.withdraw_knowledge_assertion(assertion_id, user["user_id"], reason)
    return 200, {"assertion": result}


# --------------------------------------------------------------------------
# 6. Concept Relations Handlers
# --------------------------------------------------------------------------

def handle_create_concept_relation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/concepts/{id}/relations"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    subject_id = req["path_params"]["id"]
    body = req.get("body", {})
    predicate = body.get("predicate")
    object_id = body.get("object_concept_id")
    engine = _get_engine(req)
    result = engine.create_concept_relation(subject_id, predicate, object_id, body, user["user_id"])
    return 201, {"relation": result}


# --------------------------------------------------------------------------
# 7. Modern Taxonomy Crosswalks Handlers
# --------------------------------------------------------------------------

def handle_add_external_crosswalk(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ontology/concepts/{id}/crosswalks"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    concept_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_external_crosswalk(concept_id, body, user["user_id"])
    return 201, {"crosswalk": result}


# --------------------------------------------------------------------------
# 8. Multi-Script Search Handlers
# --------------------------------------------------------------------------

def handle_search_catalog(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ontology/search"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    query = params.get("q", "")
    engine = _get_engine(req)

    # If the user is an authorized reviewer and explicitly requests authoring mode, show draft/unapproved
    is_clinician_facing = True
    if params.get("mode") == "authoring" and _can_review(user):
        is_clinician_facing = False

    result = engine.search_catalog(query, params, is_clinician_facing=is_clinician_facing)
    return 200, result


# --------------------------------------------------------------------------
# 9. Review Tasks & Audit Ledger Handlers
# --------------------------------------------------------------------------

def handle_list_catalog_tasks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ontology/tasks"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    result = engine.list_review_tasks(params)
    return 200, {"tasks": result, "total": len(result)}


def handle_list_catalog_change_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ontology/audit"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    result = engine.list_change_events(params.get("entity_type"), params.get("entity_id"))
    return 200, {"events": result, "total": len(result)}

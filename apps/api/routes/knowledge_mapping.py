"""REST API Route Handlers for Unani Clinical Knowledge Mapping & Organ-Axis Governance.

Phase 20 Endpoints for ZAYVORA MATAB OS.
Governed by permission-aware access control:
- knowledge:read / kavs:read / organ_axis:read
- knowledge:manage / kavs:manage / organ_axis:manage
- knowledge:review / kavs:verify
- knowledge:approve / kavs:approve
- encounter:create / encounter:read (for case hypothesis links)
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.knowledge_mapping import KnowledgeMappingEngine
from apps.api.core.permissions import require_permission, has_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError

_engine_instance: Optional[KnowledgeMappingEngine] = None


def _get_engine(req: Dict[str, Any]) -> KnowledgeMappingEngine:
    global _engine_instance
    if _engine_instance is None:
        db_path = req.get("db_path")
        _engine_instance = KnowledgeMappingEngine(db_path)
    return _engine_instance


# --------------------------------------------------------------------------
# 1. Controlled Relation Types Handlers
# --------------------------------------------------------------------------

def handle_list_relation_types(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/relations/types"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_relation_types(
        relation_class=params.get("relation_class"),
        status=params.get("status")
    )
    return 200, {"relation_types": results, "total": len(results)}


def handle_get_relation_type(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/relations/types/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    ref_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_relation_type(ref_id)
    return 200, {"relation_type": result}


def handle_create_relation_type(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/relations/types"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_relation_type(body, user["user_id"])
    return 201, {"relation_type": result}


# --------------------------------------------------------------------------
# 2. Relationship Assertions Handlers
# --------------------------------------------------------------------------

def handle_create_relation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/relations"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_relationship_assertion(body, user["user_id"])
    return 201, {"relation": result}


def handle_get_relation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/relations/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    rel_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_relationship_assertion(rel_id)
    return 200, {"relation": result}


def handle_list_relations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/relations"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    approved_for_clinical = params.get("approved_for_clinical", "").lower() in {"1", "true"}
    results = engine.list_relationship_assertions(
        subject_concept_id=params.get("subject_concept_id"),
        object_concept_id=params.get("object_concept_id"),
        predicate_code=params.get("predicate_code"),
        review_state=params.get("review_state"),
        relationship_level=params.get("relationship_level"),
        approved_for_clinical=approved_for_clinical
    )
    return 200, {"relations": results, "total": len(results)}


def handle_list_relation_candidates(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/relations/candidates"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    results = engine.list_relationship_assertions(review_state="draft")
    return 200, {"candidate_relations": results, "total": len(results)}


def handle_review_relation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/relations/{id}/review"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    rel_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.review_relationship_assertion(
        relation_id=rel_id,
        user_ctx=user,
        new_state=body.get("review_state") or body.get("decision", "approved_for_defined_use"),
        rationale=body.get("rationale") or body.get("decision_rationale", ""),
        intended_use_approval=body.get("intended_use_approval")
    )
    return 200, {"relation": result}


def handle_withdraw_relation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/relations/{id}/withdraw"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    rel_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.withdraw_relationship_assertion(
        relation_id=rel_id,
        user_ctx=user,
        rationale=body.get("rationale") or body.get("reason", "Withdrawn by authorized user")
    )
    return 200, {"relation": result}


# --------------------------------------------------------------------------
# 3. Versioned Organ-Axis Frameworks Handlers
# --------------------------------------------------------------------------

def handle_list_frameworks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/organ-axis/frameworks"""
    user = req["user"]
    require_permission(user, "organ_axis:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_frameworks(
        framework_type=params.get("framework_type"),
        review_state=params.get("review_state")
    )
    return 200, {"frameworks": results, "total": len(results)}


def handle_get_framework(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/organ-axis/frameworks/{id}"""
    user = req["user"]
    require_permission(user, "organ_axis:read", request_id=req.get("request_id"))
    fw_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_framework(fw_id)
    return 200, {"framework": result}


def handle_create_framework(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/organ-axis/frameworks"""
    user = req["user"]
    require_permission(user, "organ_axis:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_framework(body, user["user_id"])
    return 201, {"framework": result}


def handle_publish_framework(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/organ-axis/frameworks/{id}/publish"""
    user = req["user"]
    require_permission(user, "organ_axis:manage", request_id=req.get("request_id"))
    fw_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.publish_framework(
        framework_id=fw_id,
        user_ctx=user,
        review_state=body.get("review_state", "approved"),
        approved_use_scope=body.get("approved_use_scope", "navigation_only"),
        rationale=body.get("rationale") or body.get("decision_rationale", "Published framework")
    )
    return 200, {"framework": result}


def handle_list_framework_memberships(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/organ-axis/frameworks/{id}/memberships"""
    user = req["user"]
    require_permission(user, "organ_axis:read", request_id=req.get("request_id"))
    fw_id = req["path_params"]["id"]
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_framework_memberships(
        framework_id=fw_id,
        axis_name=params.get("axis_name"),
        review_state=params.get("review_state")
    )
    return 200, {"memberships": results, "total": len(results)}


def handle_add_framework_membership(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/organ-axis/frameworks/{id}/memberships"""
    user = req["user"]
    require_permission(user, "organ_axis:manage", request_id=req.get("request_id"))
    fw_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.add_framework_membership(fw_id, body, user["user_id"])
    return 201, {"membership": result}


# --------------------------------------------------------------------------
# 4. Cross-Disciplinary Concept Mappings Handlers
# --------------------------------------------------------------------------

def handle_create_concept_mapping(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/mappings"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_concept_mapping(body, user["user_id"])
    return 201, {"mapping": result}


def handle_get_concept_mapping(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/mappings/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    mapping_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_concept_mapping(mapping_id)
    return 200, {"mapping": result}


def handle_list_concept_mappings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/mappings"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_concept_mappings(
        source_concept_id=params.get("source_concept_id"),
        target_system=params.get("target_system"),
        review_state=params.get("review_state"),
        mapping_type=params.get("mapping_type")
    )
    return 200, {"mappings": results, "total": len(results)}


def handle_list_concept_mapping_candidates(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/mappings/candidates"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    results = engine.list_concept_mappings(review_state="draft")
    return 200, {"candidate_mappings": results, "total": len(results)}


def handle_review_concept_mapping(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/mappings/{id}/review"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    mapping_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.review_concept_mapping(
        mapping_id=mapping_id,
        user_ctx=user,
        new_state=body.get("review_state") or body.get("decision", "approved"),
        approved_intended_use=body.get("approved_intended_use"),
        rationale=body.get("rationale")
    )
    return 200, {"mapping": result}


# --------------------------------------------------------------------------
# 5. Relationship Conflicts Handlers
# --------------------------------------------------------------------------

def handle_report_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/conflicts"""
    user = req["user"]
    require_permission(user, "knowledge:manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.report_conflict(body, user["user_id"])
    return 201, {"conflict": result}


def handle_get_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/conflicts/{id}"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    conflict_id = req["path_params"]["id"]
    engine = _get_engine(req)
    result = engine.get_conflict(conflict_id)
    return 200, {"conflict": result}


def handle_list_conflicts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/conflicts"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_conflicts(
        resolution_state=params.get("resolution_state"),
        conflict_type=params.get("conflict_type")
    )
    return 200, {"conflicts": results, "total": len(results)}


def handle_adjudicate_conflict(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/knowledge/conflicts/{id}/adjudicate"""
    user = req["user"]
    require_permission(user, "knowledge:review", request_id=req.get("request_id"))
    conflict_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.adjudicate_conflict(
        conflict_id=conflict_id,
        user_ctx=user,
        resolution_state=body.get("resolution_state", "resolved_with_scope"),
        resolution_rationale=body.get("resolution_rationale") or body.get("rationale", "")
    )
    return 200, {"conflict": result}


# --------------------------------------------------------------------------
# 6. Encounter-Scoped Case Hypotheses Handlers
# --------------------------------------------------------------------------

def handle_create_encounter_hypothesis(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/encounters/{encounter_id}/hypothesis-links"""
    user = req["user"]
    require_permission(user, "encounter:update_draft", request_id=req.get("request_id"))
    encounter_id = req["path_params"]["encounter_id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.create_encounter_hypothesis(encounter_id, body, user["user_id"])
    return 201, {"hypothesis": result}


def handle_list_encounter_hypotheses(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/encounters/{encounter_id}/hypothesis-links"""
    user = req["user"]
    require_permission(user, "encounter:read", request_id=req.get("request_id"))
    encounter_id = req["path_params"]["encounter_id"]
    params = req.get("query_params", {})
    engine = _get_engine(req)
    results = engine.list_encounter_hypotheses(encounter_id, status=params.get("status"))
    return 200, {"hypotheses": results, "total": len(results)}


def handle_update_encounter_hypothesis_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PATCH /api/v1/encounters/{encounter_id}/hypothesis-links/{id}/status"""
    user = req["user"]
    require_permission(user, "encounter:update_draft", request_id=req.get("request_id"))
    encounter_id = req["path_params"]["encounter_id"]
    hypo_id = req["path_params"]["id"]
    body = req.get("body", {})
    engine = _get_engine(req)
    result = engine.update_encounter_hypothesis_status(
        hypothesis_id=hypo_id,
        encounter_id=encounter_id,
        status=body.get("status", "considered"),
        user_id=user["user_id"]
    )
    return 200, {"hypothesis": result}


# --------------------------------------------------------------------------
# 7. Bounded Knowledge Graph Traversal Handler
# --------------------------------------------------------------------------

def handle_traverse_knowledge_graph(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/knowledge/graph/traverse"""
    user = req["user"]
    require_permission(user, "knowledge:read", request_id=req.get("request_id"))
    params = req.get("query_params", {})
    concept_id = params.get("concept_id")
    if not concept_id:
        raise ValidationError("concept_id query parameter is required.")

    max_depth = int(params.get("max_depth", 2))
    include_nav = params.get("include_navigation", "").lower() in {"1", "true"}
    clinical_mode = params.get("clinical_mode", "true").lower() in {"1", "true"}

    engine = _get_engine(req)
    result = engine.traverse_knowledge_graph(
        concept_id=concept_id,
        max_depth=max_depth,
        include_navigation=include_nav,
        clinical_mode=clinical_mode,
        target_concept_id=params.get("target_concept_id")
    )
    return 200, result

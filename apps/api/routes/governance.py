"""REST API Route Handlers for Clinical Knowledge Governance, Rule Versioning & Controlled Release.

Phase 28 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- governance:read
- governance:draft
- governance:review
- governance:validate
- governance:release
- governance:manage
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.governance import ClinicalKnowledgeGovernanceEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> ClinicalKnowledgeGovernanceEngine:
    db_path = req.get("db_path")
    return ClinicalKnowledgeGovernanceEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Governed Artifacts & Versions
# --------------------------------------------------------------------------

def handle_create_artifact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/artifacts"""
    user = req["user"]
    require_permission(user, "governance:draft", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    art = engine.create_artifact(data, user)
    return 201, art


def handle_get_artifact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/governance/artifacts/{id}"""
    user = req["user"]
    require_permission(user, "governance:read", request_id=req.get("request_id"))
    art_id = _param(req, "id")
    engine = _get_engine(req)
    art = engine.get_artifact(art_id, user)
    return 200, art


def handle_list_artifacts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/governance/artifacts"""
    user = req["user"]
    require_permission(user, "governance:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    artifacts = engine.list_artifacts(qp, user)
    return 200, {"total_artifacts": len(artifacts), "artifacts": artifacts}


def handle_create_artifact_version(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/artifacts/{id}/versions"""
    user = req["user"]
    require_permission(user, "governance:draft", request_id=req.get("request_id"))
    art_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    ver = engine.create_artifact_version(art_id, data, user)
    return 201, ver


def handle_transition_version_state(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/versions/{id}/transition"""
    user = req["user"]
    require_permission(user, "governance:review", request_id=req.get("request_id"))
    ver_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.transition_version_state(ver_id, data, user)
    return 200, res


# --------------------------------------------------------------------------
# 2. Declarative Clinical Rules & Sandboxed Tests
# --------------------------------------------------------------------------

def handle_create_clinical_rule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/rules"""
    user = req["user"]
    require_permission(user, "governance:draft", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    rule = engine.create_clinical_rule(data, user)
    return 201, rule


def handle_execute_rule_tests(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/rules/{id}/tests"""
    user = req["user"]
    require_permission(user, "governance:validate", request_id=req.get("request_id"))
    rule_id = _param(req, "id")
    engine = _get_engine(req)
    results = engine.execute_rule_tests(rule_id, user)
    return 200, results


def handle_analyze_impact(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/versions/{id}/impact"""
    user = req["user"]
    require_permission(user, "governance:validate", request_id=req.get("request_id"))
    ver_id = _param(req, "id")
    engine = _get_engine(req)
    impact = engine.analyze_impact(ver_id, user)
    return 200, impact


# --------------------------------------------------------------------------
# 3. Governance Releases, Approval, Deployment & Rollback
# --------------------------------------------------------------------------

def handle_create_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/releases"""
    user = req["user"]
    require_permission(user, "governance:release", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    rel = engine.create_release(data, user)
    return 201, rel


def handle_get_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/governance/releases/{id}"""
    user = req["user"]
    require_permission(user, "governance:read", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    engine = _get_engine(req)
    rel = engine.get_release(rel_id, user)
    return 200, rel


def handle_approve_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/releases/{id}/approve"""
    user = req["user"]
    require_permission(user, "governance:release", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    approved = engine.approve_release(rel_id, data, user)
    return 200, approved


def handle_deploy_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/releases/{id}/deploy"""
    user = req["user"]
    require_permission(user, "governance:release", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    deployed = engine.deploy_release(rel_id, data, user)
    return 200, deployed


def handle_suspend_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/releases/{id}/suspend"""
    user = req["user"]
    require_permission(user, "governance:release", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    suspended = engine.suspend_release(rel_id, data, user)
    return 200, suspended


def handle_rollback_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/releases/{id}/rollback"""
    user = req["user"]
    require_permission(user, "governance:release", request_id=req.get("request_id"))
    current_rel_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    rolled_back = engine.rollback_release(current_rel_id, data, user)
    return 200, rolled_back


def handle_resolve_runtime_versions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/governance/runtime/resolve"""
    user = req["user"]
    require_permission(user, "governance:read", request_id=req.get("request_id"))
    data = req.get("body") or {}
    encounter_id = data.get("encounter_id")
    action_name = data.get("action_name", "CLINICAL_ENCOUNTER_ACTION")
    if not encounter_id:
        raise ValidationError("encounter_id is required in body.")
    engine = _get_engine(req)
    res = engine.resolve_runtime_versions(encounter_id, action_name, user)
    return 200, res

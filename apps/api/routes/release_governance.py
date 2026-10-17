"""REST API Route Handlers for Production Release Engineering, Feature Flags & Rollback.

Phase 38 for ZAYVORA MATAB OS.
Mounted endpoints:
1.  GET  /api/v1/releases/manifests
2.  POST /api/v1/releases/manifests
3.  GET  /api/v1/releases/manifests/{id}
4.  PUT  /api/v1/releases/manifests/{id}
5.  POST /api/v1/releases/manifests/{id}/advance
6.  POST /api/v1/releases/manifests/{id}/gates
7.  POST /api/v1/releases/manifests/{id}/deploy
8.  POST /api/v1/releases/manifests/{id}/rollback
9.  GET  /api/v1/flags
10. POST /api/v1/flags
11. GET  /api/v1/flags/{id}
12. PUT  /api/v1/flags/{id}
13. POST /api/v1/flags/{id}/emergency-disable
14. POST /api/v1/flags/evaluate
15. GET  /api/v1/releases/pulse
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError
from apps.api.domains.release_governance import ReleaseGovernanceEngine


def _get_engine(req: Dict[str, Any]) -> ReleaseGovernanceEngine:
    return ReleaseGovernanceEngine(db_path=req.get("db_path"))


def _param(req: Dict[str, Any], key: str, default: str = "") -> str:
    return req.get("path_params", {}).get(key, default)


# --------------------------------------------------------------------------
# 1. Release Manifest Handlers
# --------------------------------------------------------------------------

def handle_list_releases(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/releases/manifests"""
    user = req["user"]
    require_permission(user, "release:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    releases = engine.list_release_manifests(qp, user)
    return 200, {"total_releases": len(releases), "releases": releases, "items": releases}


def handle_create_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/releases/manifests"""
    user = req["user"]
    require_permission(user, "release:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    release = engine.create_release_manifest_draft(data, user)
    return 201, release


def handle_get_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/releases/manifests/{id}"""
    user = req["user"]
    require_permission(user, "release:read", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    engine = _get_engine(req)
    release = engine.get_release_manifest(rel_id, user)
    return 200, release


def handle_update_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PUT /api/v1/releases/manifests/{id}"""
    user = req["user"]
    require_permission(user, "release:manage", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    release = engine.update_release_manifest_draft(rel_id, data, user)
    return 200, release


def handle_advance_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/releases/manifests/{id}/advance"""
    user = req["user"]
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    action = data.get("action") or data.get("transition") or ""
    notes = data.get("notes") or data.get("reason")

    if action.lower() == "approve":
        require_permission(user, "release:approve", request_id=req.get("request_id"))
    else:
        require_permission(user, "release:manage", request_id=req.get("request_id"))

    engine = _get_engine(req)
    updated = engine.advance_release_status(rel_id, action, user, notes=notes)
    return 200, updated


def handle_record_gate_evaluation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/releases/manifests/{id}/gates"""
    user = req["user"]
    require_permission(user, "release:manage", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    updated = engine.record_gate_evaluation(rel_id, data, user)
    return 200, updated


def handle_deploy_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/releases/manifests/{id}/deploy"""
    user = req["user"]
    require_permission(user, "release:deploy", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    target_env = data.get("target_environment") or data.get("environment") or "staging"
    engine = _get_engine(req)
    deployed = engine.execute_deployment(rel_id, target_env, user)
    return 200, deployed


def handle_rollback_release(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/releases/manifests/{id}/rollback"""
    user = req["user"]
    require_permission(user, "release:rollback", request_id=req.get("request_id"))
    rel_id = _param(req, "id")
    data = req.get("body") or {}
    strategy = data.get("strategy") or "DISABLE_FEATURE"
    target_env = data.get("target_environment") or data.get("environment") or "staging"
    reason = data.get("reason") or "Operational issue identified"
    side_effects = data.get("acknowledged_side_effects")
    engine = _get_engine(req)
    result = engine.execute_rollback(rel_id, strategy, target_env, reason, user, acknowledged_side_effects=side_effects)
    return 200, result


# --------------------------------------------------------------------------
# 2. Feature Flag Handlers
# --------------------------------------------------------------------------

def handle_list_flags(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/flags"""
    user = req["user"]
    require_permission(user, "flag:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    flags = engine.list_feature_flags(qp, user)
    return 200, {"total_flags": len(flags), "flags": flags, "items": flags}


def handle_create_flag(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/flags"""
    user = req["user"]
    require_permission(user, "flag:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    flag = engine.create_feature_flag(data, user)
    return 201, flag


def handle_get_flag(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/flags/{id}"""
    user = req["user"]
    require_permission(user, "flag:read", request_id=req.get("request_id"))
    flag_id = _param(req, "id")
    engine = _get_engine(req)
    flag = engine.get_feature_flag(flag_id, user)
    return 200, flag


def handle_update_flag(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PUT /api/v1/flags/{id}"""
    user = req["user"]
    require_permission(user, "flag:manage", request_id=req.get("request_id"))
    flag_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    flag = engine.update_feature_flag(flag_id, data, user)
    return 200, flag


def handle_toggle_emergency_disable(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/flags/{id}/emergency-disable"""
    user = req["user"]
    require_permission(user, "flag:toggle", request_id=req.get("request_id"))
    flag_id = _param(req, "id")
    data = req.get("body") or {}
    disable = bool(data.get("disable", True))
    reason = data.get("reason", "Emergency kill-switch toggled by operator")
    engine = _get_engine(req)
    flag = engine.toggle_emergency_disable(flag_id, disable, reason, user)
    return 200, flag


def handle_evaluate_flag(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/flags/evaluate"""
    user = req["user"]
    require_permission(user, "flag:read", request_id=req.get("request_id"))
    data = req.get("body") or {}
    flag_key = data.get("flag_key")
    if not flag_key:
        raise ValidationError("Field 'flag_key' is required.")
    env = data.get("environment") or "production"
    overrides = data.get("context_overrides")
    engine = _get_engine(req)
    is_enabled = engine.evaluate_feature_flag(flag_key, env, user, context_overrides=overrides)
    return 200, {"flag_key": flag_key, "environment": env, "is_enabled": is_enabled}


# --------------------------------------------------------------------------
# 3. Release Observability & Pulse Handler
# --------------------------------------------------------------------------

def handle_get_release_pulse(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/releases/pulse"""
    user = req["user"]
    require_permission(user, "release:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    pulse = engine.get_release_pulse_summary(qp, user)
    return 200, pulse

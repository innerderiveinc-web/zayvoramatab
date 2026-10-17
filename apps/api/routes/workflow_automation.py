"""REST Route Handlers for Clinical Workflow Automation & Rules Engine.

Phase 35 for ZAYVORA MATAB OS.
Endpoints:
1.  GET  /api/v1/workflow/rules
2.  POST /api/v1/workflow/rules
3.  GET  /api/v1/workflow/rules/{id}
4.  PUT  /api/v1/workflow/rules/{id}
5.  POST /api/v1/workflow/rules/{id}/advance
6.  POST /api/v1/workflow/rules/{id}/dry-run
7.  POST /api/v1/workflow/events
8.  GET  /api/v1/workflow/actions
9.  POST /api/v1/workflow/actions/{id}/approve
10. POST /api/v1/workflow/actions/{id}/reject
11. POST /api/v1/workflow/actions/{id}/retry
12. GET  /api/v1/workflow/monitor
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.workflow_automation import WorkflowAutomationEngine


def _get_engine(req: Dict[str, Any]) -> WorkflowAutomationEngine:
    db_path = req.get("db_path")
    return WorkflowAutomationEngine(db_path=db_path)


def _param(req: Dict[str, Any], name: str) -> str:
    path_params = req.get("path_params", {})
    val = path_params.get(name)
    if not val:
        query_params = req.get("query_params", {})
        val = query_params.get(name)
    return str(val) if val else ""


# --------------------------------------------------------------------------
# 1. Rule Definition & Versioning Handlers
# --------------------------------------------------------------------------

def handle_list_rules(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/workflow/rules"""
    user = req["user"]
    require_permission(user, "workflow:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    rules = engine.list_rules(qp, user)
    return 200, {"total_rules": len(rules), "rules": rules, "items": rules}


def handle_create_rule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/workflow/rules"""
    user = req["user"]
    require_permission(user, "workflow:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    rule = engine.create_rule_draft(data, user)
    return 201, rule


def handle_get_rule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/workflow/rules/{id}"""
    user = req["user"]
    require_permission(user, "workflow:read", request_id=req.get("request_id"))
    rule_id = _param(req, "id")
    engine = _get_engine(req)
    rule = engine.get_rule(rule_id, user)
    return 200, rule


def handle_update_rule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PUT /api/v1/workflow/rules/{id}"""
    user = req["user"]
    require_permission(user, "workflow:manage", request_id=req.get("request_id"))
    rule_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    rule = engine.update_rule_draft(rule_id, data, user)
    return 200, rule


def handle_advance_rule_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/workflow/rules/{id}/advance"""
    user = req["user"]
    rule_id = _param(req, "id")
    data = req.get("body") or {}
    transition = data.get("transition") or data.get("target_status") or ""
    reason = data.get("reason")

    if transition in ("approve", "approved"):
        require_permission(user, "workflow:approve", request_id=req.get("request_id"))
    else:
        require_permission(user, "workflow:manage", request_id=req.get("request_id"))

    engine = _get_engine(req)
    rule = engine.advance_rule_status(rule_id, transition, user, reason=reason)
    return 200, rule


def handle_dry_run_rule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/workflow/rules/{id}/dry-run"""
    user = req["user"]
    require_permission(user, "workflow:read", request_id=req.get("request_id"))
    rule_id = _param(req, "id")
    data = req.get("body") or {}
    test_event = data.get("sample_event") or data.get("sample_event_payload") or {}
    engine = _get_engine(req)
    res = engine.dry_run_rule(rule_id, test_event, user)
    return 200, res


# --------------------------------------------------------------------------
# 2. Event Intake & Action Execution Handlers
# --------------------------------------------------------------------------

def handle_ingest_event(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/workflow/events"""
    user = req["user"]
    require_permission(user, "workflow:execute", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.ingest_and_process_event(data, user)
    return 201, res


def handle_list_actions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/workflow/actions"""
    user = req["user"]
    require_permission(user, "workflow:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    actions = engine.list_planned_actions(qp, user)
    return 200, {"total_actions": len(actions), "actions": actions, "items": actions}


def handle_approve_action(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/workflow/actions/{id}/approve"""
    user = req["user"]
    require_permission(user, "workflow:approve", request_id=req.get("request_id"))
    action_id = _param(req, "id")
    engine = _get_engine(req)
    res = engine.approve_planned_action(action_id, user)
    return 200, res


def handle_reject_action(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/workflow/actions/{id}/reject"""
    user = req["user"]
    require_permission(user, "workflow:approve", request_id=req.get("request_id"))
    action_id = _param(req, "id")
    data = req.get("body") or {}
    reason = data.get("rejection_reason", "Rejected by administrator.")
    engine = _get_engine(req)
    res = engine.reject_planned_action(action_id, reason, user)
    return 200, res


def handle_retry_action(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/workflow/actions/{id}/retry"""
    user = req["user"]
    require_permission(user, "workflow:manage", request_id=req.get("request_id"))
    action_id = _param(req, "id")
    engine = _get_engine(req)
    res = engine.retry_planned_action(action_id, user)
    return 200, res


# --------------------------------------------------------------------------
# 3. Operational Workflow Monitor
# --------------------------------------------------------------------------

def handle_get_workflow_monitor(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/workflow/monitor"""
    user = req["user"]
    require_permission(user, "workflow:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    summary = engine.get_workflow_monitor_summary(qp, user)
    return 200, summary

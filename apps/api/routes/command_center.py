"""REST Route Handlers for Clinical Operations Command Center & Capacity Planning.

Phase 34 for ZAYVORA MATAB OS.
Endpoints:
1.  GET  /api/v1/command-center/live
2.  GET  /api/v1/command-center/schedule
3.  GET  /api/v1/command-center/bottlenecks
4.  GET  /api/v1/command-center/capacity
5.  POST /api/v1/command-center/capacity/simulate
6.  GET  /api/v1/command-center/capacity/scenarios
7.  GET  /api/v1/command-center/workload
8.  GET  /api/v1/command-center/alerts
9.  POST /api/v1/command-center/alerts/{id}/acknowledge
10. POST /api/v1/command-center/alerts/{id}/resolve
11. POST /api/v1/command-center/actions
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.command_center import ClinicalCommandCenterEngine


def _get_engine(req: Dict[str, Any]) -> ClinicalCommandCenterEngine:
    db_path = req.get("db_path")
    return ClinicalCommandCenterEngine(db_path=db_path)


def _param(req: Dict[str, Any], name: str) -> str:
    path_params = req.get("path_params", {})
    val = path_params.get(name)
    if not val:
        query_params = req.get("query_params", {})
        val = query_params.get(name)
    return str(val) if val else ""


# --------------------------------------------------------------------------
# 1. Live Operations & Schedule Views
# --------------------------------------------------------------------------

def handle_get_live_operations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/command-center/live"""
    user = req["user"]
    require_permission(user, "command_center:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    wallboard = qp.get("wallboard_mode", "").lower() in ("true", "1", "yes")
    engine = _get_engine(req)
    snapshot = engine.get_live_operations_snapshot(qp, user, wallboard_mode=wallboard)
    return 200, snapshot


def handle_get_today_schedule(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/command-center/schedule"""
    user = req["user"]
    require_permission(user, "command_center:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    schedule = engine.get_today_schedule(qp, user)
    return 200, schedule


# --------------------------------------------------------------------------
# 2. Workflow Bottlenecks & Workload Allocation
# --------------------------------------------------------------------------

def handle_get_workflow_bottlenecks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/command-center/bottlenecks"""
    user = req["user"]
    require_permission(user, "command_center:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    bottlenecks = engine.get_workflow_bottlenecks(qp, user)
    return 200, bottlenecks


def handle_get_workload_distribution(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/command-center/workload"""
    user = req["user"]
    require_permission(user, "command_center:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    workload = engine.get_workload_distribution(qp, user)
    return 200, workload


# --------------------------------------------------------------------------
# 3. Deterministic Capacity Planning & Scenario Simulations
# --------------------------------------------------------------------------

def handle_get_capacity_plan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/command-center/capacity"""
    user = req["user"]
    require_permission(user, "capacity:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    plan = engine.get_capacity_plan(qp, user)
    return 200, plan


def handle_simulate_capacity_scenario(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/command-center/capacity/simulate"""
    user = req["user"]
    require_permission(user, "capacity:plan", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    simulation = engine.evaluate_capacity_scenario(data, user)
    return 201, simulation


def handle_list_capacity_scenarios(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/command-center/capacity/scenarios"""
    user = req["user"]
    require_permission(user, "capacity:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    scenarios = engine.list_capacity_scenarios(qp, user)
    return 200, {"total_scenarios": len(scenarios), "scenarios": scenarios}


# --------------------------------------------------------------------------
# 4. Operational Alerts Management
# --------------------------------------------------------------------------

def handle_list_operational_alerts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/command-center/alerts"""
    user = req["user"]
    require_permission(user, "command_center:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    alerts = engine.list_operational_alerts(qp, user)
    return 200, {"total_alerts": len(alerts), "alerts": alerts}


def handle_acknowledge_alert(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/command-center/alerts/{id}/acknowledge"""
    user = req["user"]
    require_permission(user, "command_center:manage", request_id=req.get("request_id"))
    alert_id = _param(req, "id")
    engine = _get_engine(req)
    res = engine.acknowledge_alert(alert_id, user)
    return 200, res


def handle_resolve_alert(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/command-center/alerts/{id}/resolve"""
    user = req["user"]
    require_permission(user, "command_center:manage", request_id=req.get("request_id"))
    alert_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.resolve_alert(alert_id, data, user)
    return 200, res


# --------------------------------------------------------------------------
# 5. Human-in-the-Loop Operational Actions
# --------------------------------------------------------------------------

def handle_perform_operational_action(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/command-center/actions"""
    user = req["user"]
    require_permission(user, "command_center:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.perform_operational_action(data, user)
    return 201, res

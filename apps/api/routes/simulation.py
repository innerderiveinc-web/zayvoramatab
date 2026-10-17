"""REST Route Handlers for Enterprise Workflow Simulation, Failure Injection & Recovery Validation.

Phase 37 for ZAYVORA MATAB OS.
Endpoints:
1.  GET  /api/v1/simulation/scenarios
2.  POST /api/v1/simulation/scenarios
3.  GET  /api/v1/simulation/scenarios/{id}
4.  PUT  /api/v1/simulation/scenarios/{id}
5.  POST /api/v1/simulation/scenarios/{id}/advance
6.  POST /api/v1/simulation/scenarios/{id}/run
7.  GET  /api/v1/simulation/runs
8.  GET  /api/v1/simulation/runs/{id}
9.  POST /api/v1/simulation/runs/{id}/cleanup
10. POST /api/v1/simulation/release-gate
11. GET  /api/v1/simulation/pulse
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.simulation import WorkflowSimulationEngine


def _get_engine(req: Dict[str, Any]) -> WorkflowSimulationEngine:
    db_path = req.get("db_path")
    return WorkflowSimulationEngine(db_path=db_path)


def _param(req: Dict[str, Any], name: str) -> str:
    path_params = req.get("path_params", {})
    val = path_params.get(name)
    if not val:
        query_params = req.get("query_params", {})
        val = query_params.get(name)
    return str(val) if val else ""


# --------------------------------------------------------------------------
# 1. Governed Scenario Handlers
# --------------------------------------------------------------------------

def handle_list_scenarios(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/simulation/scenarios"""
    user = req["user"]
    require_permission(user, "simulation:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    scenarios = engine.list_scenarios(qp, user)
    return 200, {"total_scenarios": len(scenarios), "scenarios": scenarios, "items": scenarios}


def handle_create_scenario(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/simulation/scenarios"""
    user = req["user"]
    require_permission(user, "simulation:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    scen = engine.create_scenario_draft(data, user)
    return 201, scen


def handle_get_scenario(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/simulation/scenarios/{id}"""
    user = req["user"]
    require_permission(user, "simulation:read", request_id=req.get("request_id"))
    scen_id = _param(req, "id")
    engine = _get_engine(req)
    scen = engine.get_scenario(scen_id, user)
    return 200, scen


def handle_update_scenario(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PUT /api/v1/simulation/scenarios/{id}"""
    user = req["user"]
    require_permission(user, "simulation:manage", request_id=req.get("request_id"))
    scen_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    scen = engine.update_scenario_draft(scen_id, data, user)
    return 200, scen


def handle_advance_scenario_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/simulation/scenarios/{id}/advance"""
    user = req["user"]
    scen_id = _param(req, "id")
    data = req.get("body") or {}
    transition = data.get("transition") or data.get("action") or data.get("target_status") or ""
    reason = data.get("reason")

    if transition in ("approve", "approved"):
        require_permission(user, "simulation:approve", request_id=req.get("request_id"))
    else:
        require_permission(user, "simulation:manage", request_id=req.get("request_id"))

    engine = _get_engine(req)
    scen = engine.advance_scenario_status(scen_id, transition, user, reason=reason)
    return 200, scen


# --------------------------------------------------------------------------
# 2. Simulation Run & Fault Execution Handlers
# --------------------------------------------------------------------------

def handle_launch_simulation_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/simulation/scenarios/{id}/run or POST /api/v1/simulation/runs"""
    user = req["user"]
    require_permission(user, "simulation:run", request_id=req.get("request_id"))
    data = req.get("body") or {}
    scen_id = _param(req, "id") or data.get("scenario_id")
    if not scen_id:
        raise ValidationError("scenario_id is required to launch simulation run.")
    engine = _get_engine(req)
    run_res = engine.launch_simulation_run(scen_id, data, user)
    return 201, run_res


def handle_list_simulation_runs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/simulation/runs"""
    user = req["user"]
    require_permission(user, "simulation:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    runs = engine.list_simulation_runs(qp, user)
    return 200, {"total_runs": len(runs), "runs": runs, "items": runs}


def handle_get_simulation_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/simulation/runs/{id}"""
    user = req["user"]
    require_permission(user, "simulation:read", request_id=req.get("request_id"))
    run_id = _param(req, "id")
    engine = _get_engine(req)
    run_res = engine.get_simulation_run(run_id, user)
    return 200, run_res


def handle_cleanup_simulation_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/simulation/runs/{id}/cleanup"""
    user = req["user"]
    require_permission(user, "simulation:manage", request_id=req.get("request_id"))
    run_id = _param(req, "id")
    engine = _get_engine(req)
    cleaned = engine.cleanup_run_fixtures(run_id, user)
    return 200, cleaned


# --------------------------------------------------------------------------
# 3. Release Gate & Observability Handlers
# --------------------------------------------------------------------------

def handle_evaluate_release_gate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/simulation/release-gate"""
    user = req["user"]
    require_permission(user, "simulation:gate", request_id=req.get("request_id"))
    data = req.get("body") or {}
    release_tag = data.get("target_release_tag") or data.get("release_tag") or f"v{int(time.time())}"
    scenario_ids = data.get("scenario_ids")
    engine = _get_engine(req)
    gate_res = engine.evaluate_release_gate(release_tag, user, scenario_ids=scenario_ids)
    return 200, gate_res


def handle_get_simulation_pulse(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/simulation/pulse"""
    user = req["user"]
    require_permission(user, "simulation:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    summary = engine.get_simulation_pulse_summary(qp, user)
    return 200, summary

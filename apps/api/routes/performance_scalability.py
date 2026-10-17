"""API Route Handlers for Enterprise Performance, Scalability & Capacity Engineering.

Phase 54 of ZAYVORA MATAB OS.
Mounted under `/api/v1/performance/`.
"""

import json
import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, ForbiddenError, NotFoundError
from apps.api.domains.performance_scalability_engine import PerformanceScalabilityEngine


def _get_engine(conn: sqlite3.Connection) -> PerformanceScalabilityEngine:
    return PerformanceScalabilityEngine(conn)


# -------------------------------------------------------------------------
# 1. Scenarios & Microbenchmarks
# -------------------------------------------------------------------------

def handle_list_scenarios(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/performance/scenarios"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    category = query_params.get("category")

    engine = _get_engine(conn)
    scenarios = engine.list_scenarios(category=category)
    return 200, {"success": True, "count": len(scenarios), "scenarios": scenarios}


def handle_get_scenario(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/performance/scenarios/{id}"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    scenario_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    scenario = engine.get_scenario(scenario_id)
    return 200, {"success": True, "scenario": scenario}


def handle_register_scenario(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/performance/scenarios"""
    user = req.get("user", {})
    require_permission(user, "performance:manage", request_id=req.get("request_id"))

    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    engine = _get_engine(conn)
    scenario = engine.register_scenario(body, actor_id=actor_id)
    return 201, {"success": True, "scenario": scenario}


def handle_run_microbenchmark(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/performance/scenarios/{id}/run"""
    user = req.get("user", {})
    require_permission(user, "performance:benchmark_run", request_id=req.get("request_id"))

    scenario_id = req["path_params"]["id"]
    body = req.get("body", {})
    iterations = int(body.get("iterations", 30))
    actor_id = user.get("user_id", "USER-SYSTEM")

    engine = _get_engine(conn)
    run_metrics = engine.run_live_microbenchmark(scenario_id, iterations=iterations, actor_id=actor_id)
    return 200, {"success": True, "benchmark_run": run_metrics}


# -------------------------------------------------------------------------
# 2. Benchmark Runs
# -------------------------------------------------------------------------

def handle_record_benchmark_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/performance/runs"""
    user = req.get("user", {})
    require_permission(user, "performance:benchmark_run", request_id=req.get("request_id"))

    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})

    scenario_id = body.get("scenario_id", "")
    sample_latencies = body.get("sample_latencies_ms", [])
    concurrency = int(body.get("concurrency", 10))
    duration_sec = float(body.get("duration_seconds", 1.0))
    error_count = int(body.get("error_count", 0))
    cpu_pct = body.get("cpu_utilization_pct")
    mem_mb = body.get("memory_mb")
    env = body.get("environment", "ISOLATED_STAGING")

    engine = _get_engine(conn)
    run_metrics = engine.record_benchmark_run(
        scenario_id=scenario_id,
        sample_latencies_ms=sample_latencies,
        concurrency=concurrency,
        duration_seconds=duration_sec,
        error_count=error_count,
        cpu_utilization_pct=cpu_pct,
        memory_mb=mem_mb,
        environment=env,
        actor_id=actor_id,
    )
    return 201, {"success": True, "benchmark_run": run_metrics}


def handle_list_benchmark_runs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/performance/runs"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    scenario_id = query_params.get("scenario_id")
    limit = int(query_params.get("limit", 20))

    engine = _get_engine(conn)
    runs = engine.list_benchmark_runs(scenario_id=scenario_id, limit=limit)
    return 200, {"success": True, "count": len(runs), "runs": runs}


# -------------------------------------------------------------------------
# 3. Slow Query Registry & Advisory
# -------------------------------------------------------------------------

def handle_list_slow_queries(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/performance/slow-queries"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    query_params = req.get("query_params", {})
    min_dur = float(query_params.get("min_duration_ms", 0.0))

    engine = _get_engine(conn)
    queries = engine.list_slow_queries(min_duration_ms=min_dur)
    return 200, {"success": True, "count": len(queries), "slow_queries": queries}


def handle_log_slow_query(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/performance/slow-queries"""
    user = req.get("user", {})
    require_permission(user, "performance:manage", request_id=req.get("request_id"))

    actor_id = user.get("user_id", "USER-SYSTEM")
    body = req.get("body", {})
    query_sql = body.get("query_sql", "")
    duration_ms = float(body.get("duration_ms", 10.0))
    rec_index = body.get("recommended_index")

    engine = _get_engine(conn)
    result = engine.log_slow_query(
        query_sql=query_sql,
        duration_ms=duration_ms,
        recommended_index=rec_index,
        actor_id=actor_id,
    )
    return 201, {"success": True, "query_entry": result}


# -------------------------------------------------------------------------
# 4. Capacity Profiles & Headroom Sizing
# -------------------------------------------------------------------------

def handle_list_capacity_profiles(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/performance/capacity-profiles"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    engine = _get_engine(conn)
    profiles = engine.list_capacity_profiles()
    return 200, {"success": True, "count": len(profiles), "profiles": profiles}


def handle_evaluate_capacity_headroom(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/performance/capacity-profiles/{id}/evaluate"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    profile_id = req["path_params"]["id"]
    body = req.get("body", {})
    current_users = int(body.get("current_active_users", 5))
    p95_ms = float(body.get("measured_p95_ms", 150.0))

    engine = _get_engine(conn)
    evaluation = engine.evaluate_capacity_headroom(
        profile_id=profile_id,
        current_active_users=current_users,
        measured_p95_ms=p95_ms,
    )
    return 200, {"success": True, "capacity_evaluation": evaluation}


# -------------------------------------------------------------------------
# 5. Dependency Circuit Breakers
# -------------------------------------------------------------------------

def handle_get_circuit_breaker(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/performance/circuit-breakers/{id}"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    dependency_id = req["path_params"]["id"]
    engine = _get_engine(conn)
    cb = engine.get_circuit_breaker(dependency_id)
    return 200, {"success": True, "circuit_breaker": cb}


def handle_trip_circuit_breaker(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/performance/circuit-breakers/{id}/trip"""
    user = req.get("user", {})
    require_permission(user, "performance:circuit_manage", request_id=req.get("request_id"))

    dependency_id = req["path_params"]["id"]
    body = req.get("body", {})
    reason = body.get("reason", "Manual testing trip")
    actor_id = user.get("user_id", "USER-SYSTEM")

    engine = _get_engine(conn)
    cb = engine.trip_circuit_breaker(dependency_id, reason=reason, actor_id=actor_id)
    return 200, {"success": True, "circuit_breaker": cb}


def handle_reset_circuit_breaker(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/performance/circuit-breakers/{id}/reset"""
    user = req.get("user", {})
    require_permission(user, "performance:circuit_manage", request_id=req.get("request_id"))

    dependency_id = req["path_params"]["id"]
    actor_id = user.get("user_id", "USER-SYSTEM")

    engine = _get_engine(conn)
    cb = engine.reset_circuit_breaker(dependency_id, actor_id=actor_id)
    return 200, {"success": True, "circuit_breaker": cb}


# -------------------------------------------------------------------------
# 6. Cryptographic Audit Ledger
# -------------------------------------------------------------------------

def handle_verify_perf_audit_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/performance/audit-ledger/verify"""
    user = req.get("user", {})
    require_permission(user, "performance:read", request_id=req.get("request_id"))

    engine = _get_engine(conn)
    report = engine.verify_audit_ledger_integrity()
    return 200, {"success": True, "ledger_report": report}

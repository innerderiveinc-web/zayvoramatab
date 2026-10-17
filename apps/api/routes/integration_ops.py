"""REST API Route Handlers for Enterprise Integration Operations & Reliability.

Phase 32 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- ops:read
- ops:retry
- ops:cancel
- ops:reconcile
- ops:manage
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.integration_ops import IntegrationOperationsEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> IntegrationOperationsEngine:
    db_path = req.get("db_path")
    return IntegrationOperationsEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Connectors & Health Monitoring Endpoints
# --------------------------------------------------------------------------

def handle_list_connectors(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ops/connectors"""
    user = req["user"]
    require_permission(user, "ops:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    connectors = engine.list_connectors(qp, user)
    return 200, {"total_connectors": len(connectors), "connectors": connectors}


def handle_get_connector(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ops/connectors/{id}"""
    user = req["user"]
    require_permission(user, "ops:read", request_id=req.get("request_id"))
    conn_id = _param(req, "id")
    engine = _get_engine(req)
    connector = engine.get_connector(conn_id, user)
    return 200, connector


def handle_record_health_snapshot(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/connectors/{id}/health-snapshot"""
    user = req["user"]
    require_permission(user, "ops:manage", request_id=req.get("request_id"))
    conn_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    snapshot = engine.record_health_snapshot(conn_id, data, user)
    return 201, snapshot


def handle_update_circuit_breaker(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/connectors/{id}/circuit-breaker"""
    user = req["user"]
    require_permission(user, "ops:manage", request_id=req.get("request_id"))
    conn_id = _param(req, "id")
    data = req.get("body") or {}
    state = data.get("state")
    if not state:
        raise ValidationError("state (CLOSED, OPEN, HALF_OPEN) is required.")
    engine = _get_engine(req)
    cb = engine.update_circuit_breaker(conn_id, state, user)
    return 200, cb


def handle_disable_connector(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/connectors/{id}/disable"""
    user = req["user"]
    require_permission(user, "ops:manage", request_id=req.get("request_id"))
    conn_id = _param(req, "id")
    data = req.get("body") or {}
    reason = data.get("reason", "Operator disabled")
    engine = _get_engine(req)
    res = engine.disable_connector(conn_id, reason, user)
    return 200, res


# --------------------------------------------------------------------------
# 2. Integration Jobs Endpoints
# --------------------------------------------------------------------------

def handle_create_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/jobs"""
    user = req["user"]
    require_permission(user, "ops:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    job = engine.create_job(data, user)
    return 201, job


def handle_get_job(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ops/jobs/{id}"""
    user = req["user"]
    require_permission(user, "ops:read", request_id=req.get("request_id"))
    job_id = _param(req, "id")
    engine = _get_engine(req)
    job = engine.get_job(job_id, user)
    return 200, job


def handle_list_jobs(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ops/jobs"""
    user = req["user"]
    require_permission(user, "ops:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    jobs = engine.list_jobs(qp, user)
    return 200, {"total_jobs": len(jobs), "jobs": jobs}


def handle_execute_job_attempt(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/jobs/{id}/attempt"""
    user = req["user"]
    require_permission(user, "ops:retry", request_id=req.get("request_id"))
    job_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    attempt = engine.execute_job_attempt(job_id, data, user)
    return 200, attempt


def handle_transition_job_state(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/jobs/{id}/transition"""
    user = req["user"]
    require_permission(user, "ops:cancel", request_id=req.get("request_id"))
    job_id = _param(req, "id")
    data = req.get("body") or {}
    new_state = data.get("new_state")
    rationale = data.get("rationale", "Operator transition")
    if not new_state:
        raise ValidationError("new_state is required.")
    engine = _get_engine(req)
    trans = engine.transition_job_state(job_id, new_state, rationale, user)
    return 200, trans


# --------------------------------------------------------------------------
# 3. Callbacks & Deduplication Endpoints
# --------------------------------------------------------------------------

def handle_ingest_callback(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/callbacks"""
    user = req["user"]
    require_permission(user, "ops:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.ingest_callback_event(data, user)
    return 200, res


# --------------------------------------------------------------------------
# 4. Unknown-Outcome Reconciliation Endpoints
# --------------------------------------------------------------------------

def handle_initiate_reconciliation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/jobs/{id}/reconcile"""
    user = req["user"]
    require_permission(user, "ops:reconcile", request_id=req.get("request_id"))
    job_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    recon = engine.initiate_reconciliation(job_id, data, user)
    return 201, recon


def handle_resolve_reconciliation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/reconciliations/{id}/resolve"""
    user = req["user"]
    require_permission(user, "ops:reconcile", request_id=req.get("request_id"))
    recon_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.resolve_reconciliation(recon_id, data, user)
    return 200, res


# --------------------------------------------------------------------------
# 5. Dead-Letter Workbench Endpoints
# --------------------------------------------------------------------------

def handle_list_dead_letter_items(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ops/dead-letter"""
    user = req["user"]
    require_permission(user, "ops:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    items = engine.list_dead_letter_items(qp, user)
    return 200, {"total_dlq_items": len(items), "dead_letter_items": items}


def handle_resolve_dead_letter_item(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/ops/dead-letter/{id}/resolve"""
    user = req["user"]
    require_permission(user, "ops:manage", request_id=req.get("request_id"))
    dlq_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.resolve_dead_letter_item(dlq_id, data, user)
    return 200, res


# --------------------------------------------------------------------------
# 6. Operations Dashboard Endpoint
# --------------------------------------------------------------------------

def handle_get_dashboard_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/ops/dashboard"""
    user = req["user"]
    require_permission(user, "ops:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    summary = engine.get_dashboard_summary(user)
    return 200, summary

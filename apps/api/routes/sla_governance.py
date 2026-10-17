"""REST Route Handlers for Enterprise Workflow Intelligence, SLA Governance & Exception Resolution.

Phase 36 for ZAYVORA MATAB OS.
Endpoints:
1.  GET  /api/v1/sla/policies
2.  POST /api/v1/sla/policies
3.  GET  /api/v1/sla/policies/{id}
4.  PUT  /api/v1/sla/policies/{id}
5.  POST /api/v1/sla/policies/{id}/advance
6.  GET  /api/v1/sla/exceptions
7.  POST /api/v1/sla/exceptions
8.  GET  /api/v1/sla/exceptions/{id}
9.  POST /api/v1/sla/exceptions/{id}/acknowledge
10. POST /api/v1/sla/exceptions/{id}/assign
11. POST /api/v1/sla/exceptions/{id}/start
12. POST /api/v1/sla/exceptions/{id}/pause
13. POST /api/v1/sla/exceptions/{id}/resume
14. POST /api/v1/sla/exceptions/{id}/resolve
15. POST /api/v1/sla/exceptions/{id}/verify
16. POST /api/v1/sla/exceptions/{id}/dismiss
17. POST /api/v1/sla/exceptions/{id}/reopen
18. POST /api/v1/sla/exceptions/{id}/escalate
19. GET  /api/v1/sla/monitor
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.sla_governance import SlaGovernanceEngine


def _get_engine(req: Dict[str, Any]) -> SlaGovernanceEngine:
    db_path = req.get("db_path")
    return SlaGovernanceEngine(db_path=db_path)


def _param(req: Dict[str, Any], name: str) -> str:
    path_params = req.get("path_params", {})
    val = path_params.get(name)
    if not val:
        query_params = req.get("query_params", {})
        val = query_params.get(name)
    return str(val) if val else ""


# --------------------------------------------------------------------------
# 1. Operational SLA Policy Registry & Lifecycle Handlers
# --------------------------------------------------------------------------

def handle_list_policies(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/sla/policies"""
    user = req["user"]
    require_permission(user, "sla:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    policies = engine.list_policies(qp, user)
    return 200, {"total_policies": len(policies), "policies": policies, "items": policies}


def handle_create_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/policies"""
    user = req["user"]
    require_permission(user, "sla:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    policy = engine.create_policy_draft(data, user)
    return 201, policy


def handle_get_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/sla/policies/{id}"""
    user = req["user"]
    require_permission(user, "sla:read", request_id=req.get("request_id"))
    policy_id = _param(req, "id")
    engine = _get_engine(req)
    policy = engine.get_policy(policy_id, user)
    return 200, policy


def handle_update_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PUT /api/v1/sla/policies/{id}"""
    user = req["user"]
    require_permission(user, "sla:manage", request_id=req.get("request_id"))
    policy_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    policy = engine.update_policy_draft(policy_id, data, user)
    return 200, policy


def handle_advance_policy_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/policies/{id}/advance"""
    user = req["user"]
    policy_id = _param(req, "id")
    data = req.get("body") or {}
    transition = data.get("transition") or data.get("target_status") or ""
    reason = data.get("reason")

    if transition in ("approve", "approved"):
        require_permission(user, "sla:approve", request_id=req.get("request_id"))
    else:
        require_permission(user, "sla:manage", request_id=req.get("request_id"))

    engine = _get_engine(req)
    policy = engine.advance_policy_status(policy_id, transition, user, reason=reason)
    return 200, policy


# --------------------------------------------------------------------------
# 2. Workflow Exception Intake & Ingestion Handlers
# --------------------------------------------------------------------------

def handle_list_exceptions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/sla/exceptions"""
    user = req["user"]
    require_permission(user, "sla:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    exceptions = engine.list_exceptions(qp, user)
    return 200, {"total_exceptions": len(exceptions), "exceptions": exceptions, "items": exceptions}


def handle_create_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    exc = engine.detect_and_ingest_exception(data, user)
    return 201, exc


def handle_get_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/sla/exceptions/{id}"""
    user = req["user"]
    require_permission(user, "sla:read", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    engine = _get_engine(req)
    exc = engine.get_exception(exc_id, user)
    return 200, exc


# --------------------------------------------------------------------------
# 3. Exception Lifecycle Transition Handlers
# --------------------------------------------------------------------------

def handle_acknowledge_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/acknowledge"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    engine = _get_engine(req)
    exc = engine.acknowledge_exception(exc_id, user)
    return 200, exc


def handle_assign_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/assign"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    data = req.get("body") or {}
    assigned_user_id = data.get("assigned_user_id")
    assigned_role = data.get("assigned_role")
    reason = data.get("reason")
    engine = _get_engine(req)
    exc = engine.assign_exception(exc_id, assigned_user_id, assigned_role, user, reason=reason)
    return 200, exc


def handle_start_work_on_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/start"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    engine = _get_engine(req)
    exc = engine.start_work_on_exception(exc_id, user)
    return 200, exc


def handle_pause_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/pause"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    data = req.get("body") or {}
    pause_reason_code = data.get("pause_reason_code") or data.get("reason_code") or ""
    notes = data.get("notes") or data.get("pause_notes")
    engine = _get_engine(req)
    exc = engine.pause_exception(exc_id, pause_reason_code, user, notes=notes)
    return 200, exc


def handle_resume_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/resume"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    engine = _get_engine(req)
    exc = engine.resume_exception(exc_id, user)
    return 200, exc


def handle_resolve_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/resolve"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    data = req.get("body") or {}
    resolution_code = data.get("resolution_code") or ""
    resolution_notes = data.get("resolution_notes") or ""
    engine = _get_engine(req)
    exc = engine.resolve_exception(exc_id, resolution_code, resolution_notes, user)
    return 200, exc


def handle_verify_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/verify"""
    user = req["user"]
    require_permission(user, "exception:verify", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    data = req.get("body") or {}
    verification_notes = data.get("verification_notes") or data.get("notes") or "Verified resolution."
    engine = _get_engine(req)
    exc = engine.verify_exception(exc_id, verification_notes, user)
    return 200, exc


def handle_dismiss_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/dismiss"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    data = req.get("body") or {}
    dismissal_reason = data.get("dismissal_reason") or data.get("reason") or "Dismissed by operator."
    engine = _get_engine(req)
    exc = engine.dismiss_exception(exc_id, dismissal_reason, user)
    return 200, exc


def handle_reopen_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/reopen"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    data = req.get("body") or {}
    reopen_reason = data.get("reopen_reason") or data.get("reason") or "Reopened for review."
    engine = _get_engine(req)
    exc = engine.reopen_exception(exc_id, reopen_reason, user)
    return 200, exc


def handle_escalate_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/sla/exceptions/{id}/escalate"""
    user = req["user"]
    require_permission(user, "exception:manage", request_id=req.get("request_id"))
    exc_id = _param(req, "id")
    engine = _get_engine(req)
    escalations = engine.process_escalations(exc_id, user)
    return 200, {"exception_id": exc_id, "escalations_triggered": escalations}


# --------------------------------------------------------------------------
# 4. Operational Monitor & Governance Pulse Handler
# --------------------------------------------------------------------------

def handle_get_sla_monitor(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/sla/monitor"""
    user = req["user"]
    require_permission(user, "sla:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    summary = engine.get_sla_monitor_summary(qp, user)
    return 200, summary

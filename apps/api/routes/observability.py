"""REST API Route Handlers for Production Observability, Alerting, SLOs & Incident Response.

Phase 39 for ZAYVORA MATAB OS.
Mounted endpoints:
1.  GET  /api/v1/observability/services
2.  GET  /api/v1/observability/diagnostics/deep
3.  POST /api/v1/observability/metrics
4.  GET  /api/v1/observability/metrics/summary
5.  GET  /api/v1/observability/alerts/definitions
6.  POST /api/v1/observability/alerts/definitions
7.  POST /api/v1/observability/alerts/evaluate
8.  GET  /api/v1/observability/alerts/instances
9.  POST /api/v1/observability/alerts/instances/{id}/acknowledge
10. POST /api/v1/observability/alerts/instances/{id}/resolve
11. GET  /api/v1/observability/slos
12. POST /api/v1/observability/slos
13. POST /api/v1/observability/slos/{id}/approve
14. POST /api/v1/observability/slos/events
15. GET  /api/v1/observability/incidents
16. POST /api/v1/observability/incidents
17. GET  /api/v1/observability/incidents/{id}
18. POST /api/v1/observability/incidents/{id}/transition
19. POST /api/v1/observability/incidents/{id}/timeline
20. POST /api/v1/observability/remediation
21. GET  /api/v1/observability/pulse
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError
from apps.api.domains.observability import ObservabilityReliabilityEngine


def _get_engine(req: Dict[str, Any]) -> ObservabilityReliabilityEngine:
    return ObservabilityReliabilityEngine(db_path=req.get("db_path"))


def _param(req: Dict[str, Any], key: str, default: str = "") -> str:
    return req.get("path_params", {}).get(key, default)


# --------------------------------------------------------------------------
# 1. Services & Diagnostics
# --------------------------------------------------------------------------

def handle_list_services(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/services"""
    user = req["user"]
    require_permission(user, "observability:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    services = engine.list_service_catalog(user)
    return 200, {"total_services": len(services), "services": services, "items": services}


def handle_deep_diagnostics(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/diagnostics/deep"""
    user = req["user"]
    require_permission(user, "observability:diagnostics", request_id=req.get("request_id"))
    engine = _get_engine(req)
    diag = engine.get_deep_diagnostics(user)
    return 200, diag


# --------------------------------------------------------------------------
# 2. Metrics Endpoints
# --------------------------------------------------------------------------

def handle_record_metric(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/metrics"""
    user = req["user"]
    require_permission(user, "observability:metrics", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.record_metric(data, user)
    return 201, res


def handle_query_metrics_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/metrics/summary"""
    user = req["user"]
    require_permission(user, "observability:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    summary = engine.query_metrics_summary(qp, user)
    return 200, summary


# --------------------------------------------------------------------------
# 3. Alert Definitions & Instances Endpoints
# --------------------------------------------------------------------------

def handle_list_alert_definitions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/alerts/definitions"""
    user = req["user"]
    require_permission(user, "alert:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    defs = engine.list_alert_definitions(user)
    return 200, {"total_definitions": len(defs), "definitions": defs, "items": defs}


def handle_create_alert_definition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/alerts/definitions"""
    user = req["user"]
    require_permission(user, "alert:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    definition = engine.create_alert_definition(data, user)
    return 201, definition


def handle_evaluate_alerts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/alerts/evaluate"""
    user = req["user"]
    require_permission(user, "alert:manage", request_id=req.get("request_id"))
    engine = _get_engine(req)
    results = engine.evaluate_alerts(user)
    return 200, {"evaluation_count": len(results), "evaluations": results}


def handle_list_alert_instances(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/alerts/instances"""
    user = req["user"]
    require_permission(user, "alert:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    instances = engine.list_alert_instances(qp, user)
    return 200, {"total_instances": len(instances), "instances": instances, "items": instances}


def handle_acknowledge_alert_instance(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/alerts/instances/{id}/acknowledge"""
    user = req["user"]
    require_permission(user, "alert:ack", request_id=req.get("request_id"))
    inst_id = _param(req, "id")
    engine = _get_engine(req)
    res = engine.acknowledge_alert_instance(inst_id, user)
    return 200, res


def handle_resolve_alert_instance(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/alerts/instances/{id}/resolve"""
    user = req["user"]
    require_permission(user, "alert:manage", request_id=req.get("request_id"))
    inst_id = _param(req, "id")
    data = req.get("body") or {}
    evidence = data.get("evidence") or data
    engine = _get_engine(req)
    res = engine.resolve_alert_instance(inst_id, evidence, user)
    return 200, res


# --------------------------------------------------------------------------
# 4. Service-Level Objectives (SLO) Endpoints
# --------------------------------------------------------------------------

def handle_list_slos(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/slos"""
    user = req["user"]
    require_permission(user, "slo:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    slos = engine.list_slos(user)
    return 200, {"total_slos": len(slos), "slos": slos, "items": slos}


def handle_create_slo(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/slos"""
    user = req["user"]
    require_permission(user, "slo:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    slo = engine.create_slo(data, user)
    return 201, slo


def handle_approve_slo(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/slos/{id}/approve"""
    user = req["user"]
    require_permission(user, "slo:manage", request_id=req.get("request_id"))
    slo_id = _param(req, "id")
    engine = _get_engine(req)
    res = engine.approve_slo(slo_id, user)
    return 200, res


def handle_record_slo_events(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/slos/events"""
    user = req["user"]
    require_permission(user, "observability:metrics", request_id=req.get("request_id"))
    data = req.get("body") or {}
    slo_key = data.get("slo_key")
    if not slo_key:
        raise ValidationError("slo_key is required.")
    good_delta = int(data.get("good_events_delta", 0))
    tot_delta = int(data.get("total_events_delta", 0))
    engine = _get_engine(req)
    res = engine.record_slo_events(slo_key, good_delta, tot_delta, user)
    return 200, res


# --------------------------------------------------------------------------
# 5. Incident Management Lifecycle Endpoints
# --------------------------------------------------------------------------

def handle_list_incidents(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/incidents"""
    user = req["user"]
    require_permission(user, "incident:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    incidents = engine.list_incidents(qp, user)
    return 200, {"total_incidents": len(incidents), "incidents": incidents, "items": incidents}


def handle_create_incident(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/incidents"""
    user = req["user"]
    require_permission(user, "incident:create", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    incident = engine.create_incident(data, user)
    return 201, incident


def handle_get_incident(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/incidents/{id}"""
    user = req["user"]
    require_permission(user, "incident:read", request_id=req.get("request_id"))
    inc_id = _param(req, "id")
    engine = _get_engine(req)
    inc = engine.get_incident(inc_id, user)
    return 200, inc


def handle_transition_incident(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/incidents/{id}/transition"""
    user = req["user"]
    data = req.get("body") or {}
    new_status = data.get("status")
    if not new_status:
        raise ValidationError("status is required.")

    if new_status.lower() in ("resolved", "closed"):
        require_permission(user, "incident:close", request_id=req.get("request_id"))
    else:
        require_permission(user, "incident:manage", request_id=req.get("request_id"))

    inc_id = _param(req, "id")
    notes = data.get("notes", f"Status transitioned to {new_status}")
    evidence = data.get("evidence")
    engine = _get_engine(req)
    res = engine.transition_incident(inc_id, new_status, notes, evidence, user)
    return 200, res


def handle_add_incident_timeline(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/incidents/{id}/timeline"""
    user = req["user"]
    require_permission(user, "incident:manage", request_id=req.get("request_id"))
    inc_id = _param(req, "id")
    data = req.get("body") or {}
    etype = data.get("entry_type", "COMMUNICATION")
    msg = data.get("message", "")
    payload = data.get("payload") or {}
    engine = _get_engine(req)
    tl = engine.add_incident_timeline_event(inc_id, etype, msg, payload, user)
    return 201, tl


# --------------------------------------------------------------------------
# 6. Remediation & Pulse Endpoints
# --------------------------------------------------------------------------

def handle_execute_remediation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/observability/remediation"""
    user = req["user"]
    require_permission(user, "remediation:execute", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.execute_remediation(data, user)
    return 200, res


def handle_get_observability_pulse(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/observability/pulse"""
    user = req["user"]
    require_permission(user, "observability:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    pulse = engine.get_observability_pulse(user)
    return 200, pulse

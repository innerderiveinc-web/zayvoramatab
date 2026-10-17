"""REST API Route Handlers for Enterprise Analytics, Operational Intelligence & Governance.

Phase 33 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- analytics:read
- analytics:export
- analytics:govern
- analytics:manage
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.analytics import EnterpriseAnalyticsEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> EnterpriseAnalyticsEngine:
    db_path = req.get("db_path")
    return EnterpriseAnalyticsEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Executive & Domain Analytics Endpoints
# --------------------------------------------------------------------------

def handle_get_executive_overview(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/overview"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    overview = engine.get_executive_overview(qp, user)
    return 200, overview


def handle_get_clinic_operations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/clinic-operations"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    data = engine.get_clinic_operations_metrics(qp, user)
    return 200, data


def handle_get_patient_continuity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/patient-continuity"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    data = engine.get_patient_continuity_metrics(qp, user)
    return 200, data


def handle_get_finance_metrics(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/finance"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    data = engine.get_finance_metrics(qp, user)
    return 200, data


def handle_get_inventory_metrics(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/inventory"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    data = engine.get_inventory_metrics(qp, user)
    return 200, data


def handle_get_clinical_governance(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/clinical-governance"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    data = engine.get_clinical_governance_metrics(qp, user)
    return 200, data


def handle_get_data_quality(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/data-quality"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    data = engine.get_data_quality_metrics(qp, user)
    return 200, data


# --------------------------------------------------------------------------
# 2. Governed Metric Catalogue Endpoints
# --------------------------------------------------------------------------

def handle_list_metrics(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/metrics"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    metrics = engine.list_metric_definitions(qp, user)
    return 200, {"total_metrics": len(metrics), "metrics": metrics}


def handle_get_metric(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/metrics/{key}"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    key = _param(req, "key")
    engine = _get_engine(req)
    metric = engine.get_metric_definition(key, user)
    return 200, metric


def handle_create_metric(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/analytics/metrics"""
    user = req["user"]
    require_permission(user, "analytics:govern", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    created = engine.create_metric_definition(data, user)
    return 201, created


def handle_advance_metric_to_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/analytics/metrics/{id}/review"""
    user = req["user"]
    require_permission(user, "analytics:govern", request_id=req.get("request_id"))
    metric_id = _param(req, "id")
    engine = _get_engine(req)
    updated = engine.advance_metric_to_review(metric_id, user)
    return 200, updated


def handle_approve_metric(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/analytics/metrics/{id}/approve"""
    user = req["user"]
    require_permission(user, "analytics:govern", request_id=req.get("request_id"))
    metric_id = _param(req, "id")
    engine = _get_engine(req)
    updated = engine.approve_metric_definition(metric_id, user)
    return 200, updated


def handle_retire_metric(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/analytics/metrics/{id}/retire"""
    user = req["user"]
    require_permission(user, "analytics:govern", request_id=req.get("request_id"))
    metric_id = _param(req, "id")
    engine = _get_engine(req)
    updated = engine.retire_metric_definition(metric_id, user)
    return 200, updated


# --------------------------------------------------------------------------
# 3. Secure Audited Exports
# --------------------------------------------------------------------------

def handle_generate_export(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/analytics/export"""
    user = req["user"]
    require_permission(user, "analytics:export", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.generate_export(data, user)
    return 201, res


# --------------------------------------------------------------------------
# 4. Reconciliation Exceptions Endpoints
# --------------------------------------------------------------------------

def handle_list_reconciliation_exceptions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/analytics/reconciliation-exceptions"""
    user = req["user"]
    require_permission(user, "analytics:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    exceptions = engine.list_reconciliation_exceptions(qp, user)
    return 200, {"total_exceptions": len(exceptions), "exceptions": exceptions}


def handle_record_reconciliation_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/analytics/reconciliation-exceptions"""
    user = req["user"]
    require_permission(user, "analytics:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.record_reconciliation_exception(data, user)
    return 201, res


def handle_resolve_reconciliation_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/analytics/reconciliation-exceptions/{id}/resolve"""
    user = req["user"]
    require_permission(user, "analytics:manage", request_id=req.get("request_id"))
    exception_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.resolve_reconciliation_exception(exception_id, data, user)
    return 200, res

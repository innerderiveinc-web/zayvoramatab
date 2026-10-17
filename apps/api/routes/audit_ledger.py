"""REST API Route Handlers for Clinical Audit, Accountability & Tamper-Evident Ledger.

Phase 29 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- audit:read
- audit:record
- audit:verify
- audit:annotate
- audit:export
- audit:manage
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.audit_ledger import ClinicalAuditLedgerEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> ClinicalAuditLedgerEngine:
    db_path = req.get("db_path")
    return ClinicalAuditLedgerEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Ledger Events & Queries
# --------------------------------------------------------------------------

def handle_record_event(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/audit/ledger/events"""
    user = req["user"]
    require_permission(user, "audit:record", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    evt = engine.record_event(data, user)
    return 201, evt


def handle_query_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/audit/ledger/events"""
    user = req["user"]
    require_permission(user, "audit:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    events = engine.query_ledger(qp, user)
    return 200, {"total_events": len(events), "events": events}


def handle_get_event(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/audit/ledger/events/{id}"""
    user = req["user"]
    require_permission(user, "audit:read", request_id=req.get("request_id"))
    event_id = _param(req, "id")
    engine = _get_engine(req)
    evt = engine.get_event(event_id, user)
    return 200, evt


def handle_add_annotation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/audit/ledger/events/{id}/annotations"""
    user = req["user"]
    require_permission(user, "audit:annotate", request_id=req.get("request_id"))
    event_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    annot = engine.add_annotation(event_id, data, user)
    return 201, annot


# --------------------------------------------------------------------------
# 2. Cryptographic Integrity Sweep
# --------------------------------------------------------------------------

def handle_verify_integrity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/audit/ledger/integrity-checks"""
    user = req["user"]
    require_permission(user, "audit:verify", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    res = engine.verify_integrity(data.get("scope_filter"), user)
    return 200, res


# --------------------------------------------------------------------------
# 3. Retention Policies, Legal Holds & Compliance Exports
# --------------------------------------------------------------------------

def handle_list_retention_policies(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/audit/ledger/retention-policies"""
    user = req["user"]
    require_permission(user, "audit:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    policies = engine.list_retention_policies(user)
    return 200, {"total_policies": len(policies), "policies": policies}


def handle_place_legal_hold(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/audit/ledger/legal-holds"""
    user = req["user"]
    require_permission(user, "audit:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    hold = engine.place_legal_hold(data, user)
    return 201, hold


def handle_release_legal_hold(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/audit/ledger/legal-holds/{id}/release"""
    user = req["user"]
    require_permission(user, "audit:manage", request_id=req.get("request_id"))
    hold_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    released = engine.release_legal_hold(hold_id, data, user)
    return 200, released


def handle_export_evidence_package(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/audit/ledger/exports"""
    user = req["user"]
    require_permission(user, "audit:export", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    pkg = engine.export_evidence_package(data, user)
    return 201, pkg

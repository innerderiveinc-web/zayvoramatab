"""REST API Route Handlers for Clinical Safety Surveillance & Pharmacovigilance Workflow.

Phase 27 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- safety:read
- safety:record
- safety:triage
- safety:assess
- safety:report
- safety:manage
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.pharmacovigilance import PharmacovigilanceEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> PharmacovigilanceEngine:
    db_path = req.get("db_path")
    return PharmacovigilanceEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Safety Case Intake & Retrieval
# --------------------------------------------------------------------------

def handle_create_safety_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases"""
    user = req["user"]
    require_permission(user, "safety:record", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    case = engine.create_safety_case(data, user)
    return 201, case


def handle_get_safety_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety/cases/{id}"""
    user = req["user"]
    require_permission(user, "safety:read", request_id=req.get("request_id"))
    case_id = _param(req, "id")
    engine = _get_engine(req)
    case = engine.get_safety_case(case_id, user)
    return 200, case


def handle_list_safety_cases(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety/cases"""
    user = req["user"]
    require_permission(user, "safety:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    cases = engine.list_safety_cases(qp, user)
    return 200, {"total_cases": len(cases), "cases": cases}


def handle_add_safety_event(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases/{id}/events"""
    user = req["user"]
    require_permission(user, "safety:record", request_id=req.get("request_id"))
    case_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    ev = engine.add_safety_event(case_id, data, user)
    return 201, ev


def handle_add_suspected_exposure(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases/{id}/exposures"""
    user = req["user"]
    require_permission(user, "safety:record", request_id=req.get("request_id"))
    case_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    exp = engine.add_suspected_exposure(case_id, data, user)
    return 201, exp


def handle_update_triage(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases/{id}/triage"""
    user = req["user"]
    require_permission(user, "safety:triage", request_id=req.get("request_id"))
    case_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    case = engine.update_triage(case_id, data, user)
    return 200, case


# --------------------------------------------------------------------------
# 2. Multidimensional Clinical Assessments
# --------------------------------------------------------------------------

def handle_record_assessment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases/{id}/assessments"""
    user = req["user"]
    require_permission(user, "safety:assess", request_id=req.get("request_id"))
    case_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    assessment = engine.record_assessment(case_id, data, user)
    return 201, assessment


def handle_review_assessment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/assessments/{id}/review"""
    user = req["user"]
    require_permission(user, "safety:assess", request_id=req.get("request_id"))
    assess_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    reviewed = engine.review_assessment(assess_id, data, user)
    return 200, reviewed


# --------------------------------------------------------------------------
# 3. Follow-up Tasks & Case Deduplication
# --------------------------------------------------------------------------

def handle_create_follow_up_task(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases/{id}/follow-up-tasks"""
    user = req["user"]
    require_permission(user, "safety:record", request_id=req.get("request_id"))
    case_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    task = engine.create_follow_up_task(case_id, data, user)
    return 201, task


def handle_record_follow_up_attempt(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/follow-up-tasks/{id}/attempt"""
    user = req["user"]
    require_permission(user, "safety:record", request_id=req.get("request_id"))
    task_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    updated_task = engine.record_follow_up_attempt(task_id, data, user)
    return 200, updated_task


def handle_link_cases(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases/{id}/links"""
    user = req["user"]
    require_permission(user, "safety:manage", request_id=req.get("request_id"))
    source_case_id = _param(req, "id")
    data = req.get("body") or {}
    target_case_id = data.get("target_case_id")
    if not target_case_id:
        raise ValidationError("target_case_id is required in body.")
    engine = _get_engine(req)
    link = engine.link_cases(source_case_id, target_case_id, data, user)
    return 201, link


# --------------------------------------------------------------------------
# 4. Regulatory Profiles, Report Packages & Governed Submission
# --------------------------------------------------------------------------

def handle_list_regulatory_profiles(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety/regulatory-profiles"""
    user = req["user"]
    require_permission(user, "safety:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    profiles = engine.list_regulatory_profiles(jurisdiction_code=qp.get("jurisdiction_code"), user_ctx=user)
    return 200, {"total_profiles": len(profiles), "profiles": profiles}


def handle_verify_regulatory_profile(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/regulatory-profiles/{id}/verify"""
    user = req["user"]
    require_permission(user, "safety:manage", request_id=req.get("request_id"))
    profile_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    verified = engine.verify_and_activate_profile(profile_id, data, user)
    return 200, verified


def handle_build_report_package(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/cases/{id}/report-package"""
    user = req["user"]
    require_permission(user, "safety:report", request_id=req.get("request_id"))
    case_id = _param(req, "id")
    data = req.get("body") or {}
    profile_id = data.get("profile_id")
    if not profile_id:
        raise ValidationError("profile_id is required in request body.")
    engine = _get_engine(req)
    package = engine.build_report_package(case_id, profile_id, user)
    return 201, package


def handle_authorize_submission(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/submissions/{id}/authorize"""
    user = req["user"]
    require_permission(user, "safety:report", request_id=req.get("request_id"))
    submission_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    auth_sub = engine.authorize_submission(submission_id, data, user)
    return 200, auth_sub


def handle_dispatch_submission(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/submissions/{id}/dispatch"""
    user = req["user"]
    require_permission(user, "safety:report", request_id=req.get("request_id"))
    submission_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    dispatched = engine.dispatch_submission(submission_id, data, user)
    return 200, dispatched


def handle_get_submission(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety/submissions/{id}"""
    user = req["user"]
    require_permission(user, "safety:read", request_id=req.get("request_id"))
    submission_id = _param(req, "id")
    engine = _get_engine(req)
    sub = engine.get_submission(submission_id, user)
    return 200, sub


# --------------------------------------------------------------------------
# 5. Safety Signals & Surveillance
# --------------------------------------------------------------------------

def handle_create_or_update_signal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/signals"""
    user = req["user"]
    require_permission(user, "safety:manage", request_id=req.get("request_id"))
    data = req.get("body") or {}
    engine = _get_engine(req)
    signal = engine.create_or_update_signal(data, user)
    return 200, signal


def handle_list_signals(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety/signals"""
    user = req["user"]
    require_permission(user, "safety:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    signals = engine.list_signals(qp, user)
    return 200, {"total_signals": len(signals), "signals": signals}


def handle_review_signal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/signals/{id}/review"""
    user = req["user"]
    require_permission(user, "safety:manage", request_id=req.get("request_id"))
    signal_id = _param(req, "id")
    data = req.get("body") or {}
    engine = _get_engine(req)
    reviewed = engine.review_signal(signal_id, data, user)
    return 200, reviewed

"""REST API Route Handlers for Clinical Outcome Tracking, Measurement & Evaluation Engine.

Phase 26 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- outcomes:read
- outcomes:record
- outcomes:compare
- outcomes:interpret
- outcomes:manage
- outcomes:aggregate
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.outcomes import ClinicalOutcomesEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> ClinicalOutcomesEngine:
    db_path = req.get("db_path")
    return ClinicalOutcomesEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Measurement Instruments & Concepts
# --------------------------------------------------------------------------

def handle_list_instruments(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/outcomes/instruments"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    instruments = engine.list_measurement_instruments(administration_mode=qp.get("administration_mode"))
    return 200, {"total_instruments": len(instruments), "instruments": instruments}


def handle_get_instrument(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/outcomes/instruments/{id}"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    inst_id = _param(req, "id")
    engine = _get_engine(req)
    inst = engine.get_measurement_instrument(inst_id)
    return 200, inst


def handle_list_concepts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/outcomes/concepts"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    concepts = engine.list_outcome_concepts(domain=qp.get("domain"))
    return 200, {"total_concepts": len(concepts), "concepts": concepts}


def handle_list_protocols(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/outcomes/protocols"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    protocols = engine.list_outcome_protocols()
    return 200, {"total_protocols": len(protocols), "protocols": protocols}


# --------------------------------------------------------------------------
# 2. Care Episodes & Protocol Runs
# --------------------------------------------------------------------------

def handle_open_care_episode(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/care-episodes"""
    user = req["user"]
    require_permission(user, "outcomes:record", request_id=req.get("request_id"))
    body = req.get("body", {})
    pat_id = body.get("patient_id")
    reason = body.get("reason")
    if not pat_id or not reason:
        raise ValidationError("patient_id and reason are required.")

    org_id = user.get("organization_id", "org-default")
    fac_id = user.get("active_facility_id") or "fac-default"
    actor_id = user.get("user_id", "usr-anonymous")

    engine = _get_engine(req)
    ep = engine.open_care_episode(pat_id, org_id, fac_id, reason, actor_id)
    return 201, ep


def handle_start_protocol_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcome-protocol-runs"""
    user = req["user"]
    require_permission(user, "outcomes:record", request_id=req.get("request_id"))
    body = req.get("body", {})
    pat_id = body.get("patient_id")
    proto_id = body.get("protocol_id")
    if not pat_id or not proto_id:
        raise ValidationError("patient_id and protocol_id are required.")

    actor_id = user.get("user_id", "usr-anonymous")
    engine = _get_engine(req)
    run = engine.start_protocol_run(pat_id, proto_id, body.get("episode_id"), actor_id)
    return 201, run


def handle_designate_baseline(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcome-protocol-runs/{id}/baseline"""
    user = req["user"]
    require_permission(user, "outcomes:record", request_id=req.get("request_id"))
    run_id = _param(req, "id")
    body = req.get("body", {})
    obs_id = body.get("observation_id")
    if not obs_id:
        raise ValidationError("observation_id is required.")

    actor_id = user.get("user_id", "usr-anonymous")
    method = body.get("selection_method", "CLINICIAN_MANUAL_SELECTION")
    engine = _get_engine(req)
    res = engine.designate_baseline(run_id, obs_id, method, actor_id)
    return 200, res


# --------------------------------------------------------------------------
# 3. Outcome Observations (Raw, Items, Versioned Corrections)
# --------------------------------------------------------------------------

def handle_record_observation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcome-observations"""
    user = req["user"]
    require_permission(user, "outcomes:record", request_id=req.get("request_id"))
    body = req.get("body", {})
    pat_id = body.get("patient_id")
    if not pat_id:
        raise ValidationError("patient_id is required.")

    actor_id = user.get("user_id", "usr-anonymous")
    roles = user.get("roles") or [user.get("role", "CLINICIAN")]
    role = roles[0] if roles else "CLINICIAN"

    engine = _get_engine(req)
    obs = engine.record_observation(pat_id, body, actor_id, role)
    return 201, obs


def handle_correct_observation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcome-observations/{id}/correction"""
    user = req["user"]
    require_permission(user, "outcomes:record", request_id=req.get("request_id"))
    obs_id = _param(req, "id")
    body = req.get("body", {})
    reason = body.get("correction_reason")
    if not reason:
        raise ValidationError("correction_reason is required.")

    actor_id = user.get("user_id", "usr-anonymous")
    engine = _get_engine(req)
    corrected = engine.correct_observation(obs_id, body, actor_id, reason)
    return 201, corrected


def handle_get_observation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/outcome-observations/{id}"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    obs_id = _param(req, "id")
    engine = _get_engine(req)
    obs = engine.get_observation(obs_id)
    return 200, obs


# --------------------------------------------------------------------------
# 4. Instrument Scoring Service
# --------------------------------------------------------------------------

def handle_score_instrument(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcomes/instrument-scores"""
    user = req["user"]
    require_permission(user, "outcomes:record", request_id=req.get("request_id"))
    body = req.get("body", {})
    obs_id = body.get("observation_id")
    inst_id = body.get("instrument_id")
    if not obs_id or not inst_id:
        raise ValidationError("observation_id and instrument_id are required.")

    actor_id = user.get("user_id", "usr-anonymous")
    engine = _get_engine(req)
    scoring_run = engine.score_instrument(obs_id, inst_id, actor_id)
    return 200, scoring_run


# --------------------------------------------------------------------------
# 5. Compatibility & Longitudinal Comparisons
# --------------------------------------------------------------------------

def handle_compare_observations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcomes/compare"""
    user = req["user"]
    require_permission(user, "outcomes:compare", request_id=req.get("request_id"))
    body = req.get("body", {})
    pat_id = body.get("patient_id")
    l_id = body.get("left_observation_id")
    r_id = body.get("right_observation_id")
    if not pat_id or not l_id or not r_id:
        raise ValidationError("patient_id, left_observation_id, and right_observation_id are required.")

    actor_id = user.get("user_id", "usr-anonymous")
    engine = _get_engine(req)
    comp = engine.compare_observations(
        pat_id, l_id, r_id,
        comparison_type=body.get("comparison_type", "BASELINE_VS_FOLLOWUP"),
        actor_id=actor_id
    )
    return 200, comp


# --------------------------------------------------------------------------
# 6. Treatment Exposure Contexts
# --------------------------------------------------------------------------

def handle_record_treatment_exposure(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/patients/{patient_id}/treatment-exposures"""
    user = req["user"]
    require_permission(user, "outcomes:record", request_id=req.get("request_id"))
    pat_id = _param(req, "patient_id")
    body = req.get("body", {})
    actor_id = user.get("user_id", "usr-anonymous")
    engine = _get_engine(req)
    res = engine.record_treatment_exposure(pat_id, body.get("episode_id"), body, actor_id)
    return 201, res


def handle_list_treatment_exposures(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/patients/{patient_id}/treatment-exposures"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    pat_id = _param(req, "patient_id")
    engine = _get_engine(req)
    exps = engine.list_treatment_exposures(pat_id)
    return 200, {"total_exposures": len(exps), "treatment_exposures": exps}


# --------------------------------------------------------------------------
# 7. Outcome Interpretations & Review Gate
# --------------------------------------------------------------------------

def handle_create_interpretation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcome-interpretations"""
    user = req["user"]
    require_permission(user, "outcomes:interpret", request_id=req.get("request_id"))
    body = req.get("body", {})
    pat_id = body.get("patient_id")
    if not pat_id:
        raise ValidationError("patient_id is required.")

    actor_id = user.get("user_id", "usr-anonymous")
    roles = user.get("roles") or [user.get("role", "CLINICIAN")]
    role = roles[0] if roles else "CLINICIAN"

    engine = _get_engine(req)
    interp = engine.create_outcome_interpretation(pat_id, body, actor_id, role)
    return 201, interp


def handle_review_interpretation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcome-interpretations/{id}/review"""
    user = req["user"]
    require_permission(user, "outcomes:interpret", request_id=req.get("request_id"))
    interp_id = _param(req, "id")
    body = req.get("body", {})
    action = body.get("action", "CLINICIAN_REVIEWED")
    notes = body.get("review_notes", "")
    reviewer_id = user.get("user_id", "usr-anonymous")

    engine = _get_engine(req)
    res = engine.review_outcome_interpretation(interp_id, action, notes, reviewer_id)
    return 200, res


# --------------------------------------------------------------------------
# 8. Patient Longitudinal Outcomes View & Trends
# --------------------------------------------------------------------------

def handle_get_patient_longitudinal_outcomes(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/patients/{patient_id}/outcomes/trends"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    pat_id = _param(req, "patient_id")
    qp = req.get("query_params", {})
    engine = _get_engine(req)
    trends = engine.get_patient_longitudinal_outcomes(pat_id, concept_id=qp.get("concept_id"))
    return 200, trends


# --------------------------------------------------------------------------
# 9. Aggregate Reporting with Disclosure Controls
# --------------------------------------------------------------------------

def handle_generate_aggregate_report(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/outcomes/aggregate-reports"""
    user = req["user"]
    require_permission(user, "outcomes:aggregate", request_id=req.get("request_id"))
    body = req.get("body", {})
    title = body.get("report_title")
    purpose = body.get("purpose")
    start = body.get("time_window_start")
    end = body.get("time_window_end")
    if not title or not purpose or not start or not end:
        raise ValidationError("report_title, purpose, time_window_start, and time_window_end are required.")

    org_id = user.get("organization_id", "org-default")
    actor_id = user.get("user_id", "usr-anonymous")
    engine = _get_engine(req)
    rep = engine.generate_aggregate_report(
        org_id, title, purpose, body.get("cohort_criteria", {}), start, end, actor_id
    )
    return 201, rep


def handle_get_aggregate_report(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/outcomes/aggregate-reports/{id}"""
    user = req["user"]
    require_permission(user, "outcomes:read", request_id=req.get("request_id"))
    rep_id = _param(req, "id")
    engine = _get_engine(req)
    rep = engine.get_aggregate_report(rep_id)
    return 200, rep

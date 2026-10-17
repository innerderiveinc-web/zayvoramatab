"""
REST API Route Handlers for Enterprise Threat Modeling, Abuse-Case Analysis & Secure SDLC Governance
ZAYVORA MATAB OS — Phase 47
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.threat_modeling import EnterpriseThreatModelingSDLCService


def handle_get_threat_modeling_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/dashboard-summary - Consolidated metrics."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    summary = service.get_dashboard_summary()
    return 200, {"success": True, "summary": summary}


def handle_list_threat_models(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/models - List threat models."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    params = req.get("query_params", {})
    is_stale_param = None
    if "is_stale" in params:
        is_stale_param = params["is_stale"].lower() in ("true", "1")
    models = service.list_threat_models(
        subsystem_scope=params.get("subsystem_scope"),
        lifecycle_state=params.get("lifecycle_state"),
        is_stale=is_stale_param,
    )
    return 200, {"success": True, "models": models, "count": len(models)}


def handle_create_threat_model(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/models - Create threat model."""
    require_permission(req["user"], "threat_model:manage", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    actor_id = req["user"].get("user_id", "admin")
    model = service.create_threat_model(req.get("body", {}), actor_id=actor_id)
    return 201, {"success": True, "model": model}


def handle_get_threat_model(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/models/{id} - Get model details."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    model_id = req["path_params"]["id"]
    model = service.get_threat_model(model_id)
    return 200, {"success": True, "model": model}


def handle_transition_model_state(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/models/{id}/transition - Transition state."""
    require_permission(req["user"], "threat_model:review", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    model_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    model = service.transition_model_state(
        model_id=model_id,
        new_state=body.get("new_state", ""),
        actor_id=actor_id,
        review_notes=body.get("review_notes"),
    )
    return 200, {"success": True, "model": model}


def handle_check_stale_models(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/models/check-stale - Run stale evaluation."""
    require_permission(req["user"], "threat_model:review", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    actor_id = req["user"].get("user_id", "admin")
    stale_ids = service.check_and_mark_stale_models(actor_id=actor_id)
    return 200, {"success": True, "stale_model_ids": stale_ids, "count": len(stale_ids)}


def handle_list_trust_boundaries(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/trust-boundaries - List trust boundaries."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    params = req.get("query_params", {})
    boundaries = service.list_trust_boundaries(model_id=params.get("model_id"))
    return 200, {"success": True, "trust_boundaries": boundaries, "count": len(boundaries)}


def handle_create_trust_boundary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/trust-boundaries - Create trust boundary."""
    require_permission(req["user"], "threat_model:manage", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    actor_id = req["user"].get("user_id", "admin")
    boundary = service.create_trust_boundary(req.get("body", {}), actor_id=actor_id)
    return 201, {"success": True, "trust_boundary": boundary}


def handle_list_abuse_cases(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/abuse-cases - List abuse cases."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    params = req.get("query_params", {})
    cases = service.list_abuse_cases(
        model_id=params.get("model_id"),
        severity=params.get("severity"),
        status=params.get("status"),
        threat_class=params.get("threat_class"),
    )
    return 200, {"success": True, "abuse_cases": cases, "count": len(cases)}


def handle_create_abuse_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/abuse-cases - Create abuse case."""
    require_permission(req["user"], "threat_model:manage", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    actor_id = req["user"].get("user_id", "admin")
    case = service.create_abuse_case(req.get("body", {}), actor_id=actor_id)
    return 201, {"success": True, "abuse_case": case}


def handle_get_abuse_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/abuse-cases/{id} - Get abuse case details."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    case_id = req["path_params"]["id"]
    case = service.get_abuse_case(case_id)
    return 200, {"success": True, "abuse_case": case}


def handle_transition_abuse_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/abuse-cases/{id}/transition - Transition status."""
    require_permission(req["user"], "threat_model:manage", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    case_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    case = service.transition_abuse_case_status(
        case_id=case_id,
        new_status=body.get("new_status", ""),
        actor_id=actor_id,
        notes=body.get("notes"),
    )
    return 200, {"success": True, "abuse_case": case}


def handle_list_testable_controls(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/controls - List controls."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    params = req.get("query_params", {})
    controls = service.list_testable_controls(threat_id=params.get("threat_id"))
    return 200, {"success": True, "controls": controls, "count": len(controls)}


def handle_create_testable_control(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/controls - Create testable control."""
    require_permission(req["user"], "threat_model:manage", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    actor_id = req["user"].get("user_id", "admin")
    ctl = service.create_testable_control(req.get("body", {}), actor_id=actor_id)
    return 201, {"success": True, "control": ctl}


def handle_verify_control(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/controls/{id}/verify - Record verification proof."""
    require_permission(req["user"], "threat_model:manage", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    ctl_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    ctl = service.verify_control(
        control_id=ctl_id,
        verification_status=body.get("verification_status", "VERIFIED_IN_TEST"),
        actor_id=actor_id,
        test_evidence=body.get("test_evidence"),
    )
    return 200, {"success": True, "control": ctl}


def handle_list_residual_risks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/residual-risks - List residual risk decisions."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    params = req.get("query_params", {})
    decisions = service.list_residual_risk_decisions(
        threat_id=params.get("threat_id"),
        status=params.get("status"),
    )
    return 200, {"success": True, "residual_risks": decisions, "count": len(decisions)}


def handle_create_residual_risk(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/residual-risks - Accept residual risk."""
    require_permission(req["user"], "threat_model:risk_accept", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    actor_id = req["user"].get("user_id", "admin")
    decision = service.create_residual_risk_decision(req.get("body", {}), actor_id=actor_id)
    return 201, {"success": True, "residual_risk": decision}


def handle_revoke_residual_risk(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/residual-risks/{id}/revoke - Revoke risk decision."""
    require_permission(req["user"], "threat_model:risk_accept", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    decision_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    decision = service.revoke_residual_risk_decision(
        decision_id=decision_id,
        actor_id=actor_id,
        rationale=body.get("rationale", ""),
    )
    return 200, {"success": True, "residual_risk": decision}


def handle_list_change_reviews(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/change-reviews - List SDLC reviews."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    params = req.get("query_params", {})
    reviews = service.list_change_reviews(
        target_subsystem=params.get("target_subsystem"),
        verdict=params.get("verdict"),
    )
    return 200, {"success": True, "change_reviews": reviews, "count": len(reviews)}


def handle_create_change_review(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/change-reviews - Register change review & evaluate gate."""
    require_permission(req["user"], "sdlc:change_intake", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    actor_id = req["user"].get("user_id", "admin")
    review = service.create_change_review(req.get("body", {}), actor_id=actor_id)
    return 201, {"success": True, "change_review": review}


def handle_evaluate_sdlc_gate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/threat-modeling/change-reviews/{id}/evaluate - Re-evaluate SDLC gate."""
    require_permission(req["user"], "sdlc:gate_evaluate", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    review_id = req["path_params"]["id"]
    actor_id = req["user"].get("user_id", "admin")
    review = service.evaluate_sdlc_gate(review_id, actor_id=actor_id)
    return 200, {"success": True, "change_review": review}


def handle_get_threat_audit_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/threat-modeling/audit-ledger - Query hash-chained audit trail."""
    require_permission(req["user"], "threat_model:read", request_id=req.get("request_id"))
    service = EnterpriseThreatModelingSDLCService(conn)
    params = req.get("query_params", {})
    limit = int(params.get("limit", 100))
    events = service.query_audit_ledger(
        limit=limit,
        actor_id=params.get("actor_id"),
        event_type=params.get("event_type"),
    )
    return 200, {"success": True, "audit_events": events, "count": len(events)}

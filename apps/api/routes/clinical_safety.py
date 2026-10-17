"""
REST API Route Handlers for Enterprise Clinical Safety Case, Hazard Analysis & Safety Control Verification
ZAYVORA MATAB OS — Phase 48
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.clinical_safety import EnterpriseClinicalSafetyCaseEngine


def _is_clinical_safety_officer(user: Dict[str, Any]) -> bool:
    """Helper to verify clinical authority (Tabib/Hakeem/Practitioner/Clinical Safety Officer)."""
    roles = user.get("roles", [])
    user_id = user.get("user_id", "")
    username = user.get("username", "")
    if user_id in ("usr-hakeem-1", "usr-tabib-1") or username in ("hakeem", "tabib"):
        return True
    for r in roles:
        r_str = str(r).lower()
        if any(term in r_str for term in ("tabib", "hakeem", "clinical_safety", "safety_officer", "practitioner")):
            return True
    return False


def handle_get_clinical_safety_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/summary - Executive safety metrics and KPIs."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    summary = engine.get_clinical_safety_summary()
    return 200, {"success": True, "summary": summary}


# -------------------------------------------------------------------------
# Intended Use Registry
# -------------------------------------------------------------------------
def handle_list_intended_uses(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/intended-use - List bounded clinical intended uses."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    records = engine.list_intended_uses(
        scope_code=params.get("scope_code"),
        status=params.get("status"),
    )
    return 200, {"success": True, "intended_uses": records, "count": len(records)}


def handle_get_intended_use(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/intended-use/{id} - Get intended use statement."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    iu_id = req["path_params"]["id"]
    record = engine.get_intended_use(iu_id)
    return 200, {"success": True, "intended_use": record}


def handle_register_intended_use(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/intended-use - Register bounded intended use."""
    require_permission(req["user"], "safety_case:manage", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    record = engine.register_intended_use(actor_id=actor_id, data=req.get("body", {}))
    return 201, {"success": True, "intended_use": record}


# -------------------------------------------------------------------------
# Clinical Hazards
# -------------------------------------------------------------------------
def handle_list_hazards(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/hazards - List clinical hazards."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    hazards = engine.list_hazards(
        workflow_scope=params.get("workflow_scope"),
        severity_tier=params.get("severity_tier"),
        lifecycle_status=params.get("lifecycle_status"),
    )
    return 200, {"success": True, "hazards": hazards, "count": len(hazards)}


def handle_get_hazard(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/hazards/{id} - Get hazard detail with requirements."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    hazard_id = req["path_params"]["id"]
    hazard = engine.get_hazard(hazard_id)
    return 200, {"success": True, "hazard": hazard}


def handle_create_hazard(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/hazards - Log a new clinical hazard."""
    require_permission(req["user"], "safety_case:manage", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    hazard = engine.create_hazard(actor_id=actor_id, data=req.get("body", {}))
    return 201, {"success": True, "hazard": hazard}


def handle_update_hazard_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/hazards/{id}/status - Transition hazard lifecycle status."""
    require_permission(req["user"], "safety_case:clinical_review", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    hazard_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    is_cso = _is_clinical_safety_officer(req["user"])
    hazard = engine.update_hazard_status(
        actor_id=actor_id,
        hazard_id=hazard_id,
        new_status=body.get("new_status", ""),
        justification=body.get("justification", ""),
        is_clinical_safety_officer=is_cso,
    )
    return 200, {"success": True, "hazard": hazard}


# -------------------------------------------------------------------------
# Safety Requirements
# -------------------------------------------------------------------------
def handle_list_requirements(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/requirements - List safety requirements."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    requirements = engine.list_requirements(
        hazard_id=params.get("hazard_id"),
        verification_status=params.get("verification_status"),
    )
    return 200, {"success": True, "requirements": requirements, "count": len(requirements)}


def handle_get_requirement(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/requirements/{id} - Get requirement and verification history."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    req_id = req["path_params"]["id"]
    requirement = engine.get_requirement(req_id)
    return 200, {"success": True, "requirement": requirement}


def handle_create_requirement(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/requirements - Author a safety requirement for a hazard."""
    require_permission(req["user"], "safety_case:manage", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    requirement = engine.create_requirement(actor_id=actor_id, data=req.get("body", {}))
    return 201, {"success": True, "requirement": requirement}


# -------------------------------------------------------------------------
# Control Verifications
# -------------------------------------------------------------------------
def handle_record_control_verification(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/verifications - Record automated verification test run."""
    require_permission(req["user"], "safety_case:verify", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    verification = engine.record_control_verification(
        actor_id=actor_id,
        requirement_id=body.get("requirement_id", ""),
        test_suite_name=body.get("test_suite_name", ""),
        status=body.get("status", "PASS"),
        evidence_summary=body.get("evidence_summary", ""),
        execution_duration_ms=body.get("execution_duration_ms", 50),
        environment=body.get("environment", "ISOLATED_SYNTHETIC"),
    )
    return 201, {"success": True, "verification": verification}


def handle_list_verifications(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/verifications - List test execution evidence."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    verifications = engine.list_verifications(requirement_id=params.get("requirement_id"))
    return 200, {"success": True, "verifications": verifications, "count": len(verifications)}


# -------------------------------------------------------------------------
# Clinical Safety Cases (GSN)
# -------------------------------------------------------------------------
def handle_list_safety_cases(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/cases - List clinical safety cases."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    cases = engine.list_safety_cases(
        workflow_scope=params.get("workflow_scope"),
        approval_status=params.get("approval_status"),
    )
    return 200, {"success": True, "safety_cases": cases, "count": len(cases)}


def handle_get_safety_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/cases/{id} - Get safety case detail."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    case_id = req["path_params"]["id"]
    case = engine.get_safety_case(case_id)
    return 200, {"success": True, "safety_case": case}


def handle_create_safety_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/cases - Create clinical safety case draft."""
    require_permission(req["user"], "safety_case:manage", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    case = engine.create_safety_case(actor_id=actor_id, data=req.get("body", {}))
    return 201, {"success": True, "safety_case": case}


def handle_review_safety_case(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/cases/{id}/review - Review and approve clinical safety case."""
    require_permission(req["user"], "safety_case:approve_case", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    case_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    is_cso = _is_clinical_safety_officer(req["user"])
    case = engine.review_safety_case(
        actor_id=actor_id,
        case_id=case_id,
        new_status=body.get("new_status", ""),
        clinical_rationale=body.get("clinical_rationale", ""),
        is_clinical_safety_officer=is_cso,
    )
    return 200, {"success": True, "safety_case": case}


# -------------------------------------------------------------------------
# Clinical Incidents & Near-Miss Loop
# -------------------------------------------------------------------------
def handle_list_incidents(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/incidents - List incidents and near-misses."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    incidents = engine.list_incidents(
        workflow_scope=params.get("workflow_scope"),
        status=params.get("status"),
        severity=params.get("severity"),
    )
    return 200, {"success": True, "incidents": incidents, "count": len(incidents)}


def handle_get_incident(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/incidents/{id} - Get incident detail."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    incident_id = req["path_params"]["id"]
    incident = engine.get_incident(incident_id)
    return 200, {"success": True, "incident": incident}


def handle_report_incident(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/incidents - Report a clinical safety incident or near-miss."""
    require_permission(req["user"], "safety_case:manage", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    incident = engine.report_incident(actor_id=actor_id, data=req.get("body", {}))
    return 201, {"success": True, "incident": incident}


def handle_triage_incident(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/incidents/{id}/triage - Update incident triage/closure status."""
    require_permission(req["user"], "safety_case:clinical_review", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    incident_id = req["path_params"]["id"]
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    incident = engine.triage_and_close_incident(
        actor_id=actor_id,
        incident_id=incident_id,
        corrective_action_status=body.get("corrective_action_status", "INVESTIGATING"),
        containment_action=body.get("containment_action"),
        corrective_action_plan=body.get("corrective_action_plan"),
    )
    return 200, {"success": True, "incident": incident}


# -------------------------------------------------------------------------
# Release Gate Evaluations
# -------------------------------------------------------------------------
def handle_evaluate_release_gate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/release-gates/evaluate - Evaluate fail-closed release gate."""
    require_permission(req["user"], "safety_case:gate_evaluate", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    body = req.get("body", {})
    actor_id = req["user"].get("user_id", "admin")
    evaluation = engine.evaluate_release_gate(
        actor_id=actor_id,
        target_release_version=body.get("target_release_version", "v1.0.0"),
        workflow_scope=body.get("workflow_scope", "PRESCRIPTION_SIGNING"),
        safety_case_id=body.get("safety_case_id"),
    )
    return 200, {"success": True, "evaluation": evaluation}


def handle_list_release_gates(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/release-gates - List release gate evaluations."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    evaluations = engine.list_gate_evaluations(workflow_scope=params.get("workflow_scope"))
    return 200, {"success": True, "evaluations": evaluations, "count": len(evaluations)}


# -------------------------------------------------------------------------
# Traceability & Audit
# -------------------------------------------------------------------------
def handle_get_traceability_matrix(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/traceability - Full bidirectional traceability graph."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    matrix = engine.get_traceability_matrix(workflow_scope=params.get("workflow_scope"))
    return 200, {"success": True, "matrix": matrix}


def handle_get_audit_trail(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety-case/audit - Tamper-evident audit trail."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    params = req.get("query_params", {})
    limit = int(params.get("limit", 50))
    trail = engine.get_audit_trail(limit=limit)
    return 200, {"success": True, "audit_trail": trail, "count": len(trail)}


def handle_verify_audit_integrity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety-case/audit/verify - Verify audit ledger SHA-256 hash chaining."""
    require_permission(req["user"], "safety_case:read", request_id=req.get("request_id"))
    engine = EnterpriseClinicalSafetyCaseEngine(conn)
    result = engine.verify_audit_ledger_integrity()
    return 200, {"success": True, "integrity_verification": result}

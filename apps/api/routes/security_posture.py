"""
REST API Route Handlers for Enterprise Security Posture & Vulnerability Governance
ZAYVORA MATAB OS — Phase 46
"""

import sqlite3
from typing import Dict, Any, Tuple

from apps.api.core.permissions import require_permission
from apps.api.domains.security_posture import EnterpriseSecurityPostureEngine


def handle_get_security_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/summary - Executive KPI summary."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    summary = engine.get_dashboard_summary()
    return 200, {"success": True, "summary": summary}


def handle_list_security_assets(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/assets - List technical assets."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    params = req.get("query_params", {})
    assets = engine.list_assets(category=params.get("category"), environment=params.get("environment"))
    return 200, {"success": True, "assets": assets, "count": len(assets)}


def handle_register_security_asset(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/assets - Register new asset."""
    require_permission(req["user"], "security:posture_manage", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    asset = engine.register_asset(req.get("body", {}), req["user"])
    return 201, {"success": True, "asset": asset}


def handle_list_security_controls(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/controls - List controls registry."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    params = req.get("query_params", {})
    controls = engine.list_controls(status=params.get("status"))
    return 200, {"success": True, "controls": controls, "count": len(controls)}


def handle_run_all_security_scans(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/scans/run-all - Execute full verification scanner suite."""
    require_permission(req["user"], "security:scan_execute", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    result = engine.run_all_security_scans(actor_id=actor_id)
    return 200, {"success": True, "scan_result": result}


def handle_run_sca_scan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/scans/sca - Execute SCA dependency scanner."""
    require_permission(req["user"], "security:scan_execute", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    result = engine.run_sca_dependency_scan(actor_id=actor_id)
    return 200, {"success": True, "scan_result": result}


def handle_run_secret_scan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/scans/secrets - Execute secret exposure scanner."""
    require_permission(req["user"], "security:scan_execute", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    result = engine.run_secret_leak_scan(actor_id=actor_id)
    return 200, {"success": True, "scan_result": result}


def handle_run_api_authz_scan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/scans/api-authz - Execute API authorization scanner."""
    require_permission(req["user"], "security:scan_execute", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    result = engine.run_api_authz_and_headers_scan(actor_id=actor_id)
    return 200, {"success": True, "scan_result": result}


def handle_run_container_scan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/scans/container - Execute container & Dockerfile scanner."""
    require_permission(req["user"], "security:scan_execute", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    result = engine.run_container_and_iac_scan(actor_id=actor_id)
    return 200, {"success": True, "scan_result": result}


def handle_run_sql_param_scan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/scans/sql-param - Execute SQL parameterization scanner."""
    require_permission(req["user"], "security:scan_execute", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    actor_id = req["user"].get("user_id", "admin")
    result = engine.run_sql_parameterization_scan(actor_id=actor_id)
    return 200, {"success": True, "scan_result": result}


def handle_list_findings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/findings - List vulnerability findings."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    params = req.get("query_params", {})
    findings = engine.list_findings(
        status=params.get("status"),
        priority=params.get("priority"),
        category=params.get("category"),
    )
    return 200, {"success": True, "findings": findings, "count": len(findings)}


def handle_create_finding(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/findings - Create vulnerability finding."""
    require_permission(req["user"], "security:vulnerability_triage", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    finding = engine.create_finding(req.get("body", {}), req["user"])
    return 201, {"success": True, "finding": finding}


def handle_get_finding(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/findings/{id} - Get finding details."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    finding_id = req["path_params"]["id"]
    finding = engine.get_finding(finding_id)
    return 200, {"success": True, "finding": finding}


def handle_transition_finding(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/findings/{id}/transition - Transition finding lifecycle."""
    require_permission(req["user"], "security:vulnerability_triage", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    finding_id = req["path_params"]["id"]
    body = req.get("body", {})
    target_status = body.get("target_status")
    res = engine.transition_finding_status(
        finding_id=finding_id,
        target_status=target_status,
        actor_ctx=req["user"],
        notes=body.get("notes"),
        fixed_version=body.get("fixed_version"),
        verification_evidence=body.get("verification_evidence"),
    )
    return 200, {"success": True, "finding": res}


def handle_list_exceptions(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/exceptions - List security exceptions."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    params = req.get("query_params", {})
    exceptions = engine.list_exceptions(status=params.get("status"))
    return 200, {"success": True, "exceptions": exceptions, "count": len(exceptions)}


def handle_request_exception(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/exceptions - Request security exception."""
    require_permission(req["user"], "security:exception_approve", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    exc = engine.request_exception(req.get("body", {}), req["user"])
    return 201, {"success": True, "exception": exc}


def handle_evaluate_release_gate(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/security-posture/gates/evaluate - Evaluate security release gate."""
    require_permission(req["user"], "security:gate_evaluate", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    body = req.get("body", {})
    rel_ver = body.get("release_version", "v1.1.0")
    env = body.get("target_environment", "PRODUCTION")
    commit_ref = body.get("target_commit_ref", "HEAD")
    eval_res = engine.evaluate_release_gate(rel_ver, env, commit_ref, req["user"])
    return 200, {"success": True, "gate_evaluation": eval_res}


def handle_list_gate_evaluations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/gates - List past release gate evaluations."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    gates = engine.list_gate_evaluations()
    return 200, {"success": True, "evaluations": gates, "count": len(gates)}


def handle_list_security_audit_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/security-posture/audit-ledger - List security audit ledger entries."""
    require_permission(req["user"], "security:posture_read", request_id=req.get("request_id"))
    engine = EnterpriseSecurityPostureEngine(conn)
    params = req.get("query_params", {})
    limit = int(params.get("limit", 50))
    events = engine.list_audit_events(limit=limit)
    return 200, {"success": True, "audit_events": events, "count": len(events)}

"""HTTP Route Handlers for Enterprise Configuration, Secrets & Environment Governance."""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.domains.config_governance import EnterpriseConfigGovernanceEngine


def handle_get_settings(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/settings - List settings in the catalog."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    qp = req.get("query_params", {})
    settings = engine.get_settings(
        req["user"],
        category=qp.get("category"),
        environment_scope=qp.get("environment_scope")
    )
    return 200, {"success": True, "settings": settings}


def handle_register_setting(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/settings - Register new setting."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    setting = engine.register_setting(req["user"], req.get("body", {}))
    return 201, {"success": True, "setting": setting}


def handle_get_setting(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/settings/{id} - Get single setting."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    setting_id = req["path_params"]["id"]
    setting = engine.get_setting(req["user"], setting_id)
    return 200, {"success": True, "setting": setting}


def handle_get_public_config(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/public - Public safe client configuration."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    public_config = engine.get_public_client_config(req.get("user"))
    return 200, {"success": True, "public_config": public_config}


def handle_get_environments(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/environments - List registered environments."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    envs = engine.get_environments(req["user"])
    return 200, {"success": True, "environments": envs}


def handle_get_environment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/environments/{code} - Get single environment."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    code = req["path_params"]["code"]
    env = engine.get_environment(req["user"], code)
    return 200, {"success": True, "environment": env}


def handle_validate_isolation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/environments/isolation-check - Validate environment action boundaries."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    body = req.get("body", {})
    res = engine.validate_environment_isolation(
        req["user"],
        source_env_code=body.get("source_env_code", "local_dev"),
        target_action=body.get("target_action", "read"),
        resource_ref=body.get("resource_ref", "")
    )
    return 200, {"success": True, "isolation_check": res}


def handle_run_preflight(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/preflight - Execute preflight schema and fail-closed validation."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    body = req.get("body", {})
    env_code = body.get("environment_code", "local_dev")
    runtime_dict = body.get("runtime_env_dict")
    res = engine.run_preflight_validation(req["user"], env_code, runtime_env_dict=runtime_dict)
    return 200, {"success": True, "preflight": res}


def handle_get_secret_references(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/secrets - List secret references (metadata only)."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    qp = req.get("query_params", {})
    secrets = engine.get_secret_references(
        req["user"],
        environment_code=qp.get("environment_code"),
        status=qp.get("status")
    )
    return 200, {"success": True, "secrets": secrets}


def handle_register_secret_reference(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/secrets - Register secret reference."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    sec = engine.register_secret_reference(req["user"], req.get("body", {}))
    return 201, {"success": True, "secret": sec}


def handle_get_secret_reference(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/secrets/{id} - Get single secret reference."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    sec_id = req["path_params"]["id"]
    sec = engine.get_secret_reference(req["user"], sec_id)
    return 200, {"success": True, "secret": sec}


def handle_initiate_rotation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/secrets/rotate - Initiate secret rotation workflow."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    rot = engine.initiate_secret_rotation(req["user"], req.get("body", {}))
    return 201, {"success": True, "rotation": rot}


def handle_advance_rotation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/rotations/{id}/advance - Advance rotation state machine."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    rot_id = req["path_params"]["id"]
    body = req.get("body", {})
    rot = engine.advance_secret_rotation(
        req["user"],
        rot_id,
        target_state=body.get("target_state"),
        evidence=body.get("evidence")
    )
    return 200, {"success": True, "rotation": rot}


def handle_urgent_revocation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/secrets/{id}/revoke-compromised - Urgent incident revocation containment."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    sec_id = req["path_params"]["id"]
    body = req.get("body", {})
    sec = engine.urgent_compromise_revocation(
        req["user"],
        sec_id,
        incident_id=body.get("incident_id", ""),
        rationale=body.get("rationale", "")
    )
    return 200, {"success": True, "secret": sec}


def handle_list_proposals(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/proposals - List config change proposals."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    qp = req.get("query_params", {})
    proposals = engine.list_change_proposals(
        req["user"],
        environment_code=qp.get("environment_code"),
        status=qp.get("status")
    )
    return 200, {"success": True, "proposals": proposals}


def handle_create_proposal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/proposals - Submit config change proposal."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    prop = engine.create_change_proposal(req["user"], req.get("body", {}))
    return 201, {"success": True, "proposal": prop}


def handle_get_proposal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/proposals/{id} - Get single proposal."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    prop_id = req["path_params"]["id"]
    prop = engine.get_change_proposal(req["user"], prop_id)
    return 200, {"success": True, "proposal": prop}


def handle_approve_proposal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/proposals/{id}/approve - Approve proposal (separation of duties)."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    prop_id = req["path_params"]["id"]
    prop = engine.approve_change_proposal(req["user"], prop_id)
    return 200, {"success": True, "proposal": prop}


def handle_apply_proposal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/proposals/{id}/apply - Apply approved proposal."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    prop_id = req["path_params"]["id"]
    prop = engine.apply_change_proposal(req["user"], prop_id)
    return 200, {"success": True, "proposal": prop}


def handle_rollback_proposal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/proposals/{id}/rollback - Roll back applied proposal."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    prop_id = req["path_params"]["id"]
    body = req.get("body", {})
    prop = engine.rollback_change_proposal(req["user"], prop_id, rationale=body.get("rationale", ""))
    return 200, {"success": True, "proposal": prop}


def handle_run_drift_scan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/config/drift/scans/run - Run drift scan."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    body = req.get("body", {})
    env_code = body.get("environment_code", "production")
    scan_type = body.get("scan_type", "MANUAL_AUDIT")
    scan = engine.run_drift_scan(req["user"], env_code, scan_type=scan_type)
    return 200, {"success": True, "scan": scan}


def handle_get_drift_scans(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/drift/scans - List drift scans."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    qp = req.get("query_params", {})
    scans = engine.get_drift_scans(req["user"], environment_code=qp.get("environment_code"))
    return 200, {"success": True, "scans": scans}


def handle_get_audit_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/audit - List config and secret audit events."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    qp = req.get("query_params", {})
    events = engine.get_audit_ledger(
        req["user"],
        action_type=qp.get("action_type"),
        environment_code=qp.get("environment_code"),
        limit=int(qp.get("limit", 50))
    )
    return 200, {"success": True, "events": events}


def handle_get_governance_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/config/summary - Get executive governance overview."""
    engine = EnterpriseConfigGovernanceEngine(conn)
    summary = engine.get_governance_summary(req["user"])
    return 200, {"success": True, "summary": summary}

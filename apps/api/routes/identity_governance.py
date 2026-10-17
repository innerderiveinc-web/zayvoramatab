"""HTTP Route Handlers for Enterprise Identity Governance, PAM & Access Certification."""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.domains.identity_governance import EnterpriseIdentityGovernanceEngine
from apps.api.core.permissions import require_permission


def handle_get_identity_summary(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/summary - Executive KPI summary."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    summary = engine.get_summary()
    return 200, {"success": True, "summary": summary}


def handle_list_principals(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/principals - List identity principals."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    qp = req.get("query_params", {})
    principals = engine.list_principals(
        account_state=qp.get("account_state"),
        principal_type=qp.get("principal_type"),
    )
    return 200, {"success": True, "principals": principals}


def handle_create_principal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/principals - Joiner onboarding flow."""
    require_permission(req["user"], "identity:manage", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    principal = engine.create_identity(req.get("body", {}), req["user"])
    return 201, {"success": True, "principal": principal}


def handle_get_principal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/principals/{id} - Get single principal."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    p_id = req["path_params"]["id"]
    principal = engine.get_principal(p_id)
    return 200, {"success": True, "principal": principal}


def handle_mover_transition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/principals/{id}/mover - Mover transition."""
    require_permission(req["user"], "identity:manage", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    p_id = req["path_params"]["id"]
    res = engine.execute_mover_transition(p_id, req.get("body", {}), req["user"])
    return 200, {"success": True, "mover": res}


def handle_leaver_offboarding(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/principals/{id}/leaver - Leaver offboarding with verified revocation."""
    require_permission(req["user"], "identity:manage", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    p_id = req["path_params"]["id"]
    body = req.get("body", {})
    res = engine.execute_leaver_offboarding(p_id, body.get("reason", "Standard offboarding"), req["user"])
    return 200, {"success": True, "leaver": res}


def handle_verify_effective_access(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/users/{id}/effective-access - Determine actual active effective access."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    u_id = req["path_params"]["id"]
    qp = req.get("query_params", {})
    res = engine.verify_effective_access(
        u_id,
        required_permission=qp.get("permission", "patients:read"),
        facility_id=qp.get("facility_id"),
    )
    return 200, {"success": True, "effective_access": res}


def handle_list_privileges(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/privileges - List privileged operations registry."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    privs = engine.list_privilege_registry()
    return 200, {"success": True, "privileges": privs}


def handle_list_elevations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/elevations - List JIT elevation requests."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    qp = req.get("query_params", {})
    elevs = engine.list_jit_elevations(status=qp.get("status"))
    return 200, {"success": True, "elevations": elevs}


def handle_request_elevation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/elevations - Request JIT privileged elevation."""
    require_permission(req["user"], "identity:elevate", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    res = engine.request_jit_elevation(req.get("body", {}), req["user"])
    return 201, {"success": True, "elevation": res}


def handle_approve_elevation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/elevations/{id}/approve - Approve JIT elevation (enforcing SoD)."""
    require_permission(req["user"], "identity:approve_elevation", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    e_id = req["path_params"]["id"]
    res = engine.approve_jit_elevation(e_id, req["user"])
    return 200, {"success": True, "elevation": res}


def handle_activate_elevation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/elevations/{id}/activate - Activate approved JIT elevation."""
    require_permission(req["user"], "identity:elevate", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    e_id = req["path_params"]["id"]
    res = engine.activate_jit_elevation(e_id, req["user"])
    return 200, {"success": True, "elevation": res}


def handle_revoke_elevation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/elevations/{id}/revoke - Revoke active JIT elevation."""
    require_permission(req["user"], "identity:manage", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    e_id = req["path_params"]["id"]
    body = req.get("body", {})
    res = engine.revoke_or_expire_jit_elevation(e_id, body.get("reason", "Administrative revocation"), req["user"])
    return 200, {"success": True, "elevation": res}


def handle_list_break_glass(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/break-glass - List break-glass emergency sessions."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    qp = req.get("query_params", {})
    sessions = engine.list_break_glass_sessions(status=qp.get("status"))
    return 200, {"success": True, "break_glass_sessions": sessions}


def handle_activate_break_glass(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/break-glass - Activate emergency break-glass."""
    require_permission(req["user"], "identity:break_glass", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    res = engine.activate_break_glass(req.get("body", {}), req["user"])
    return 201, {"success": True, "break_glass": res}


def handle_record_break_glass_action(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/break-glass/{id}/action - Record break-glass action (blocking clinical acts)."""
    require_permission(req["user"], "identity:break_glass", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    bg_id = req["path_params"]["id"]
    body = req.get("body", {})
    res = engine.record_break_glass_action(
        bg_id,
        action=body.get("action", "read_patient_record"),
        is_clinical_act=body.get("is_clinical_act", False),
        actor_ctx=req["user"],
    )
    return 200, {"success": True, "action_record": res}


def handle_review_break_glass(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/break-glass/{id}/review - Retrospective review of break-glass (enforcing SoD)."""
    require_permission(req["user"], "identity:manage", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    bg_id = req["path_params"]["id"]
    body = req.get("body", {})
    res = engine.review_break_glass(
        bg_id,
        decision=body.get("decision", "REVIEWED_JUSTIFIED"),
        notes=body.get("notes", "Verified justification"),
        actor_ctx=req["user"],
    )
    return 200, {"success": True, "review": res}


def handle_list_service_accounts(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/service-accounts - List managed service accounts."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    qp = req.get("query_params", {})
    accounts = engine.list_service_accounts(environment=qp.get("environment"))
    return 200, {"success": True, "service_accounts": accounts}


def handle_register_service_account(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/service-accounts - Register machine identity."""
    require_permission(req["user"], "identity:manage", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    account = engine.register_service_account(req.get("body", {}), req["user"])
    return 201, {"success": True, "service_account": account}


def handle_deprovision_service_account(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/service-accounts/{id}/deprovision - Deprovision machine identity with dependency check."""
    require_permission(req["user"], "identity:manage", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    sa_id = req["path_params"]["id"]
    body = req.get("body", {})
    res = engine.deprovision_service_account(sa_id, body.get("force_override", False), req["user"])
    return 200, {"success": True, "deprovision": res}


def handle_list_campaigns(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/campaigns - List certification campaigns."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    campaigns = engine.list_certification_campaigns()
    return 200, {"success": True, "campaigns": campaigns}


def handle_create_campaign(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/campaigns - Launch certification campaign."""
    require_permission(req["user"], "identity:certify", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    camp = engine.create_certification_campaign(req.get("body", {}), req["user"])
    return 201, {"success": True, "campaign": camp}


def handle_list_campaign_items(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/campaigns/{id}/items - List items in a campaign."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    c_id = req["path_params"]["id"]
    items = engine.list_certification_items(c_id)
    return 200, {"success": True, "items": items}


def handle_record_certification_decision(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/certification-items/{id}/decision - Record certification decision (enforcing SoD)."""
    require_permission(req["user"], "identity:certify", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    item_id = req["path_params"]["id"]
    body = req.get("body", {})
    res = engine.record_certification_decision(
        item_id,
        decision=body.get("decision", "RETAIN"),
        rationale=body.get("rationale", "Verified active need"),
        actor_ctx=req["user"],
    )
    return 200, {"success": True, "decision_record": res}


def handle_list_remediations(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/remediations - List remediation actions."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    qp = req.get("query_params", {})
    actions = engine.list_remediation_actions(status=qp.get("status"))
    return 200, {"success": True, "remediations": actions}


def handle_execute_remediation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/remediations/{id}/execute - Phase 1: Apply revocation action."""
    require_permission(req["user"], "identity:remediate", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    act_id = req["path_params"]["id"]
    res = engine.execute_remediation_action(act_id, req["user"])
    return 200, {"success": True, "remediation": res}


def handle_verify_remediation(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/remediations/{id}/verify - Phase 2: Verify revocation is effective."""
    require_permission(req["user"], "identity:remediate", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    act_id = req["path_params"]["id"]
    res = engine.verify_remediation_action(act_id, req["user"])
    return 200, {"success": True, "remediation": res}


def handle_list_sod_rules(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/sod-rules - List Separation of Duties toxic rules."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    rules = engine.list_sod_rules()
    return 200, {"success": True, "sod_rules": rules}


def handle_check_sod_rules(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/identity/sod-rules/check - Check a role/permission set for toxic combinations."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    body = req.get("body", {})
    violations = engine.check_toxic_combinations(body.get("roles", []))
    return 200, {
        "success": True,
        "is_toxic": len(violations) > 0,
        "violations": violations,
    }


def handle_list_identity_audit_ledger(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/identity/audit-ledger - Query tamper-evident identity audit ledger."""
    require_permission(req["user"], "identity:read", request_id=req.get("request_id"))
    engine = EnterpriseIdentityGovernanceEngine(conn)
    qp = req.get("query_params", {})
    limit = int(qp.get("limit", 50))
    events = engine.list_audit_ledger(limit=limit)
    return 200, {"success": True, "audit_events": events}

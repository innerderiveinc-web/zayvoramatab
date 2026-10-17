"""HTTP Route Handlers for Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Governance."""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.domains.data_lifecycle import EnterpriseDataLifecycleEngine
from apps.api.core.errors import ValidationError


def handle_get_inventory(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lifecycle/inventory - List governed data categories and retention mappings."""
    engine = EnterpriseDataLifecycleEngine(conn)
    inventory = engine.get_inventory_catalog(req["user"])
    return 200, {"success": True, "inventory": inventory}


def handle_get_policies(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lifecycle/policies - List versioned retention policies."""
    engine = EnterpriseDataLifecycleEngine(conn)
    policies = engine.get_policies(req["user"])
    return 200, {"success": True, "policies": policies}


def handle_create_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/policies - Register new draft retention policy."""
    engine = EnterpriseDataLifecycleEngine(conn)
    policy = engine.create_policy(req.get("body", {}), req["user"])
    return 201, {"success": True, "policy": policy}


def handle_approve_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/policies/:id/approve - Formally approve policy version."""
    policy_id = req["path_params"].get("id")
    if not policy_id:
        raise ValidationError("Missing policy ID path parameter.")
    engine = EnterpriseDataLifecycleEngine(conn)
    policy = engine.approve_policy(policy_id, req["user"])
    return 200, {"success": True, "policy": policy}


def handle_evaluate_dry_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/evaluations/dry-run - Run deterministic side-effect free retention evaluation."""
    body = req.get("body", {})
    policy_id = body.get("policy_id")
    category_id = body.get("category_id")
    if not policy_id or not category_id:
        raise ValidationError("Both 'policy_id' and 'category_id' are required.")
    dry_run = body.get("dry_run", True)
    engine = EnterpriseDataLifecycleEngine(conn)
    run_record = engine.evaluate_retention(policy_id, category_id, req["user"], dry_run=dry_run)
    return 200, {"success": True, "evaluation_run": run_record}


def handle_execute_disposal(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/operations/execute - Execute governed disposal or archival operation."""
    body = req.get("body", {})
    category_id = body.get("category_id")
    target_record_id = body.get("target_record_id")
    policy_id = body.get("policy_id")
    action_type = body.get("action_type", "restrict")
    if not category_id or not target_record_id or not policy_id:
        raise ValidationError("'category_id', 'target_record_id', and 'policy_id' are mandatory.")
    engine = EnterpriseDataLifecycleEngine(conn)
    op = engine.execute_disposal(category_id, target_record_id, policy_id, req["user"], action_type=action_type)
    return 201, {"success": True, "operation": op}


def handle_list_legal_holds(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lifecycle/holds - List active or historical legal preservation holds."""
    status_filter = req.get("query_params", {}).get("status")
    engine = EnterpriseDataLifecycleEngine(conn)
    holds = engine.list_legal_holds(req["user"], status_filter=status_filter)
    return 200, {"success": True, "holds": holds}


def handle_place_legal_hold(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/holds - Place universal legal hold on subject/category."""
    engine = EnterpriseDataLifecycleEngine(conn)
    hold = engine.place_legal_hold(req.get("body", {}), req["user"])
    return 201, {"success": True, "hold": hold}


def handle_release_legal_hold(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/holds/:id/release - Formally release legal hold."""
    hold_id = req["path_params"].get("id")
    if not hold_id:
        raise ValidationError("Missing hold ID path parameter.")
    engine = EnterpriseDataLifecycleEngine(conn)
    hold = engine.release_legal_hold(hold_id, req.get("body", {}), req["user"])
    return 200, {"success": True, "hold": hold}


def handle_list_privacy_requests(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lifecycle/requests - List data subject rights and privacy requests."""
    engine = EnterpriseDataLifecycleEngine(conn)
    requests = engine.list_privacy_requests(req["user"])
    return 200, {"success": True, "requests": requests}


def handle_ingest_privacy_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/requests - Ingest new data subject rights request."""
    engine = EnterpriseDataLifecycleEngine(conn)
    request_rec = engine.ingest_privacy_request(req.get("body", {}), req["user"])
    return 201, {"success": True, "request": request_rec}


def handle_verify_request_identity(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/requests/:id/verify-identity - Complete mandatory identity verification."""
    request_id = req["path_params"].get("id")
    if not request_id:
        raise ValidationError("Missing request ID path parameter.")
    engine = EnterpriseDataLifecycleEngine(conn)
    request_rec = engine.verify_request_identity(request_id, req["user"])
    return 200, {"success": True, "request": request_rec}


def handle_approve_request_plan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/requests/:id/approve - Formally approve privacy fulfillment plan."""
    request_id = req["path_params"].get("id")
    if not request_id:
        raise ValidationError("Missing request ID path parameter.")
    engine = EnterpriseDataLifecycleEngine(conn)
    request_rec = engine.approve_request_plan(request_id, req.get("body", {}), req["user"])
    return 200, {"success": True, "request": request_rec}


def handle_execute_request_plan(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/lifecycle/requests/:id/execute - Execute governed privacy request actions."""
    request_id = req["path_params"].get("id")
    if not request_id:
        raise ValidationError("Missing request ID path parameter.")
    engine = EnterpriseDataLifecycleEngine(conn)
    request_rec = engine.execute_request_plan(request_id, req["user"])
    return 200, {"success": True, "request": request_rec}


def handle_get_lifecycle_pulse(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/lifecycle/pulse - Get comprehensive pulse telemetry."""
    engine = EnterpriseDataLifecycleEngine(conn)
    pulse = engine.get_lifecycle_pulse(req["user"])
    return 200, {"success": True, "pulse": pulse}

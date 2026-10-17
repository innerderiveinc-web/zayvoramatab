"""HTTP Route Handlers for Disaster Recovery, Business Continuity & Resilience Operations."""

from typing import Dict, Any, Tuple
import sqlite3

from apps.api.domains.disaster_recovery import DisasterRecoveryContinuityEngine
from apps.api.core.errors import ValidationError


def handle_get_domain_catalog(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/domains - List BIA domain criticality catalog."""
    engine = DisasterRecoveryContinuityEngine(conn)
    domains = engine.get_domain_catalog(req["user"])
    return 200, {"success": True, "domains": domains}


def handle_update_domain_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """PATCH /api/v1/dr/domains/:id - Update domain RTO/RPO and policies."""
    domain_id = req["path_params"].get("id")
    if not domain_id:
        raise ValidationError("Missing domain ID path parameter.")
    engine = DisasterRecoveryContinuityEngine(conn)
    result = engine.update_domain_policy(domain_id, req.get("body", {}), req["user"])
    return 200, {"success": True, "domain": result}


def handle_create_online_backup(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/backups - Generate live online SQLite snapshot."""
    body = req.get("body", {})
    backup_type = body.get("backup_type", "full")
    scope = body.get("scope", "database_all")
    custom_dir = body.get("custom_backup_dir")
    engine = DisasterRecoveryContinuityEngine(conn)
    result = engine.create_online_backup(backup_type, scope, custom_dir, req["user"])
    return 201, {"success": True, "backup": result}


def handle_list_backups(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/backups - List backup catalog entries."""
    engine = DisasterRecoveryContinuityEngine(conn)
    backups = engine.list_backups(req["user"])
    return 200, {"success": True, "backups": backups}


def handle_execute_restore_drill(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/drills - Run 7-step isolated restore drill."""
    body = req.get("body", {})
    backup_id = body.get("backup_id")
    if not backup_id:
        raise ValidationError("Missing mandatory 'backup_id' parameter.")
    target_env = body.get("target_environment", "isolated_test_sandbox")
    purpose = body.get("purpose", "Quarterly Business Continuity Drill")
    incident_ref = body.get("incident_ref")

    engine = DisasterRecoveryContinuityEngine(conn)
    result = engine.execute_restore_drill(backup_id, target_env, purpose, incident_ref, req["user"])
    return 201, {"success": True, "drill": result}


def handle_sign_off_drill(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/drills/:id/sign-off - Sign off on business resumption."""
    drill_id = req["path_params"].get("id")
    if not drill_id:
        raise ValidationError("Missing drill ID path parameter.")
    notes = req.get("body", {}).get("notes", "Resumption approved following successful verification.")
    engine = DisasterRecoveryContinuityEngine(conn)
    result = engine.sign_off_drill_resumption(drill_id, notes, req["user"])
    return 200, {"success": True, "drill": result}


def handle_list_drills(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/drills - List restore drill history."""
    engine = DisasterRecoveryContinuityEngine(conn)
    drills = engine.list_drills(req["user"])
    return 200, {"success": True, "drills": drills}


def handle_get_drill_details(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/drills/:id - Get granular drill verification report."""
    drill_id = req["path_params"].get("id")
    if not drill_id:
        raise ValidationError("Missing drill ID path parameter.")
    engine = DisasterRecoveryContinuityEngine(conn)
    drill = engine.get_drill_details(drill_id, req["user"])
    return 200, {"success": True, "drill": drill}


def handle_list_runbooks(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/runbooks - List business continuity playbooks."""
    engine = DisasterRecoveryContinuityEngine(conn)
    runbooks = engine.list_runbooks(req["user"])
    return 200, {"success": True, "runbooks": runbooks}


def handle_ingest_downtime_record(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/reconciliation - Ingest paper/offline record."""
    engine = DisasterRecoveryContinuityEngine(conn)
    result = engine.ingest_downtime_record(req.get("body", {}), req["user"])
    return 201, {"success": True, "record": result}


def handle_list_reconciliation_queue(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/reconciliation - List offline downtime records."""
    status_filter = req.get("query_params", {}).get("status")
    engine = DisasterRecoveryContinuityEngine(conn)
    records = engine.list_reconciliation_queue(req["user"], status_filter)
    return 200, {"success": True, "records": records}


def handle_resolve_downtime_record(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/dr/reconciliation/:id/resolve - Resolve downtime record."""
    record_id = req["path_params"].get("id")
    if not record_id:
        raise ValidationError("Missing record ID path parameter.")
    body = req.get("body", {})
    action = body.get("action", "reconcile")
    canonical_id = body.get("canonical_id")
    notes = body.get("notes")
    conflict_reason = body.get("conflict_reason")

    engine = DisasterRecoveryContinuityEngine(conn)
    result = engine.resolve_downtime_record(record_id, action, canonical_id, notes, conflict_reason, req["user"])
    return 200, {"success": True, "record": result}


def handle_get_dr_pulse(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/dr/pulse - Real-time DR posture metrics."""
    engine = DisasterRecoveryContinuityEngine(conn)
    pulse = engine.get_dr_pulse(req["user"])
    return 200, {"success": True, "pulse": pulse}

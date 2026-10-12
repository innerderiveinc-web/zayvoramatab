"""REST API Route Handlers for Clinical Safety Firewall & Interaction Engine.
Endpoints for preflight runs, findings, clinician dispositions, overrides, and rules catalog.
"""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError
from apps.api.domains.safety_firewall import SafetyFirewallEngine


def _get_engine(conn: sqlite3.Connection) -> SafetyFirewallEngine:
    return SafetyFirewallEngine()


def handle_run_preflight(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/preflight"""
    user = req["user"]
    require_permission(user, "prescription:validate", request_id=req.get("request_id"))
    body = req.get("body", {})

    patient_context = body.get("patient_context", {})
    prescription_items = body.get("prescription_items", [])
    prescription_id = body.get("prescription_id")
    encounter_id = body.get("encounter_id")

    engine = _get_engine(conn)
    result = engine.run_preflight(
        patient_context=patient_context,
        prescription_items=prescription_items,
        user_ctx=user,
        prescription_id=prescription_id,
        encounter_id=encounter_id
    )
    return 200, result


def handle_get_preflight_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety/preflight/{run_id}"""
    user = req["user"]
    require_permission(user, "prescription:validate", request_id=req.get("request_id"))
    run_id = req["path_params"]["run_id"]

    engine = _get_engine(conn)
    result = engine.get_preflight_run(run_id)
    return 200, {"preflight_run": result}


def handle_record_disposition(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/safety/findings/{finding_id}/disposition"""
    user = req["user"]
    require_permission(user, "prescription:validate", request_id=req.get("request_id"))
    finding_id = req["path_params"]["finding_id"]
    body = req.get("body", {})

    disp_type = body.get("disposition_type", "ACKNOWLEDGED")
    rationale = body.get("clinical_rationale", "")

    engine = _get_engine(conn)
    result = engine.record_finding_disposition(finding_id, user, disp_type, rationale)
    return 200, result


def handle_resolve_substance(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/safety/substances/resolve"""
    user = req["user"]
    require_permission(user, "prescription:validate", request_id=req.get("request_id"))
    query = req.get("query_params", {}).get("q", "")

    engine = _get_engine(conn)
    result = engine.resolve_substance_identity(query)
    return 200, result

"""REST API Route Handlers for Clinical Decision Support (CDS) Orchestrator & Approval Workflow.

Phase 23 Endpoints for ZAYVORA MATAB OS.
Enforces permission-aware access control:
- cds:read
- cds:run
- cds:review
- encounter:sign
- encounter:amend
"""

import json
import sqlite3
from typing import Dict, Any, Tuple, Optional

from apps.api.domains.cds_orchestrator import CDSOrchestratorEngine
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_engine(req: Dict[str, Any]) -> CDSOrchestratorEngine:
    db_path = req.get("db_path")
    return CDSOrchestratorEngine(db_path)


def _param(req: Dict[str, Any], key: str) -> str:
    params = req.get("path_params") or req.get("params") or {}
    val = params.get(key)
    if not val:
        raise ValidationError(f"Missing required parameter '{key}' in request path.")
    return val


# --------------------------------------------------------------------------
# 1. Governed Policy Registry
# --------------------------------------------------------------------------

def handle_list_policies(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/cds/policies"""
    user = req["user"]
    require_permission(user, "cds:read", request_id=req.get("request_id"))
    active_only = req.get("query_params", {}).get("active_only", "true").lower() == "true"
    engine = _get_engine(req)
    policies = engine.list_policies(active_only=active_only)
    return 200, {"policies": policies, "total": len(policies)}


def handle_get_policy(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/cds/policies/{code}"""
    user = req["user"]
    require_permission(user, "cds:read", request_id=req.get("request_id"))
    code = _param(req, "code")
    engine = _get_engine(req)
    policy = engine.get_policy(code)
    return 200, {"policy": policy}


# --------------------------------------------------------------------------
# 2. CDS Execution & Cards
# --------------------------------------------------------------------------

def handle_execute_cds_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/encounters/{encounter_id}/cds-runs"""
    user = req["user"]
    require_permission(user, "cds:run", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")
    body = req.get("body", {})
    scope = body.get("query_scope", "FULL_ENCOUNTER")

    engine = _get_engine(req)
    result = engine.execute_cds_run(encounter_id=encounter_id, query_scope=scope, user_ctx=user)
    return 201, result


def handle_get_cds_run(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/cds/runs/{id}"""
    user = req["user"]
    require_permission(user, "cds:read", request_id=req.get("request_id"))
    run_id = _param(req, "id")
    cur = conn.cursor()
    cur.execute("SELECT * FROM cds_runs WHERE id = ?;", (run_id,))
    row = cur.fetchone()
    if not row:
        raise NotFoundError(f"CDS Run '{run_id}' not found.")
    run_data = dict(row)
    if run_data.get("input_manifest_json"):
        run_data["input_manifest"] = json.loads(run_data["input_manifest_json"])
    return 200, {"cds_run": run_data}


def handle_get_cds_run_cards(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/cds/runs/{id}/cards"""
    user = req["user"]
    require_permission(user, "cds:read", request_id=req.get("request_id"))
    run_id = _param(req, "id")
    cur = conn.cursor()
    cur.execute("SELECT * FROM cds_cards WHERE cds_run_id = ? ORDER BY severity DESC, created_at ASC;", (run_id,))
    cards = []
    for r in cur.fetchall():
        c = dict(r)
        c["triggering_inputs"] = json.loads(c.get("triggering_inputs_json") or "[]")
        c["evidence_refs"] = json.loads(c.get("evidence_refs_json") or "[]")
        c["rule_refs"] = json.loads(c.get("rule_refs_json") or "[]")
        c["limitations"] = json.loads(c.get("limitations_json") or "[]")
        cards.append(c)
    return 200, {"cards": cards, "total": len(cards)}


def handle_get_encounter_cards(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/encounters/{encounter_id}/cds-cards"""
    user = req["user"]
    require_permission(user, "cds:read", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM cds_cards
        WHERE encounter_id = ?
        ORDER BY severity DESC, created_at ASC;
    """, (encounter_id,))
    cards = []
    for r in cur.fetchall():
        c = dict(r)
        c["triggering_inputs"] = json.loads(c.get("triggering_inputs_json") or "[]")
        c["evidence_refs"] = json.loads(c.get("evidence_refs_json") or "[]")
        c["rule_refs"] = json.loads(c.get("rule_refs_json") or "[]")
        c["limitations"] = json.loads(c.get("limitations_json") or "[]")
        cards.append(c)
    return 200, {"cards": cards, "total": len(cards)}


# --------------------------------------------------------------------------
# 3. Clinician Review Decision
# --------------------------------------------------------------------------

def handle_review_card(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/cds/cards/{id}/review"""
    user = req["user"]
    require_permission(user, "cds:review", request_id=req.get("request_id"))
    card_id = _param(req, "id")
    body = req.get("body", {})
    action = body.get("action")
    if not action:
        raise ValidationError("Review 'action' is required.")

    rationale = body.get("rationale")
    edited_content = body.get("edited_content")
    acknowledgements = body.get("acknowledgements")
    idempotency_key = body.get("idempotency_key") or req.get("headers", {}).get("x-idempotency-key")

    engine = _get_engine(req)
    res = engine.review_card(
        card_id=card_id,
        action=action,
        user_ctx=user,
        rationale=rationale,
        edited_content=edited_content,
        acknowledgements=acknowledgements,
        idempotency_key=idempotency_key
    )
    return 200, res


# --------------------------------------------------------------------------
# 4. Readiness & Workflow State Machine
# --------------------------------------------------------------------------

def handle_check_readiness(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/encounters/{encounter_id}/readiness"""
    user = req["user"]
    require_permission(user, "cds:read", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")
    engine = _get_engine(req)
    readiness = engine.check_readiness(encounter_id, user_ctx=user)
    return 200, readiness


def handle_transition_state(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/encounters/{encounter_id}/cds-transition"""
    user = req["user"]
    require_permission(user, "encounters:write", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")
    body = req.get("body", {})
    target_state = body.get("target_state")
    if not target_state:
        raise ValidationError("target_state is required.")

    reason = body.get("reason", "Clinician state transition request")
    actor_id = user.get("user_id")
    idempotency_key = body.get("idempotency_key") or req.get("headers", {}).get("x-idempotency-key")

    engine = _get_engine(req)
    res = engine.transition_encounter_state(
        encounter_id=encounter_id,
        target_state=target_state,
        actor_id=actor_id,
        reason=reason,
        user_ctx=user,
        idempotency_key=idempotency_key
    )
    return 200, res


# --------------------------------------------------------------------------
# 5. Sign-off & Amendments
# --------------------------------------------------------------------------

def handle_sign_encounter(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/encounters/{encounter_id}/sign"""
    user = req["user"]
    require_permission(user, "encounter:sign", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")
    body = req.get("body", {})
    pin = body.get("pin")
    if not pin:
        raise ValidationError("Signing PIN is required.")

    notes = body.get("clinical_notes")
    engine = _get_engine(req)
    res = engine.sign_encounter(encounter_id=encounter_id, pin=str(pin), user_ctx=user, clinical_notes=notes)
    return 200, res


def handle_request_amendment(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/encounters/{encounter_id}/amendments"""
    user = req["user"]
    require_permission(user, "encounter:amend", request_id=req.get("request_id"))
    encounter_id = _param(req, "encounter_id")
    body = req.get("body", {})
    justification = body.get("clinical_justification")
    if not justification:
        raise ValidationError("clinical_justification is required.")

    changes = body.get("changes_summary", {})
    engine = _get_engine(req)
    res = engine.request_amendment(
        encounter_id=encounter_id,
        clinical_justification=justification,
        changes_summary=changes,
        user_ctx=user
    )
    return 201, res


# --------------------------------------------------------------------------
# 6. Kill Switch Administrative Controls
# --------------------------------------------------------------------------

def handle_set_kill_switch(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/cds/kill-switch"""
    user = req["user"]
    require_permission(user, "enterprise:org_manage", request_id=req.get("request_id"))
    body = req.get("body", {})
    active = bool(body.get("active", False))
    reason = body.get("reason", "Administrative kill switch toggled")
    engine = _get_engine(req)
    res = engine.set_kill_switch(active=active, reason=reason, user_ctx=user)
    return 200, res


def handle_get_kill_switch(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/cds/kill-switch"""
    user = req["user"]
    require_permission(user, "cds:read", request_id=req.get("request_id"))
    engine = _get_engine(req)
    return 200, {"kill_switch_active": engine.is_kill_switch_active()}

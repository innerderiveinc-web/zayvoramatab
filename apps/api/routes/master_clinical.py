"""Master Clinical System Route Handlers.
Compatible with ApiRouter dispatch: handle_xxx(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]].
"""

from typing import Dict, Any, Tuple, Optional
import sqlite3

from apps.api.domains.master_clinical import MasterClinicalService
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError


def _get_service(req: Dict[str, Any] = None) -> MasterClinicalService:
    db_path = req.get("db_path") if req else None
    return MasterClinicalService(db_path=db_path)


def handle_get_axes(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/clinical/axes"""
    svc = _get_service(req)
    axes = svc.get_organ_axes()
    return 200, {"organ_axes": axes}


def handle_score_axes(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/clinical/axes/score"""
    body = req.get("body", {})
    scores = body.get("scores", {})
    if not isinstance(scores, dict):
        raise ValidationError("Scores must be a dictionary of {axis_id: score_0_to_5}.")

    svc = _get_service(req)
    result = svc.score_axes(scores)
    return 200, result


def handle_get_protocols(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/clinical/protocols"""
    category = req.get("query_params", {}).get("category")
    svc = _get_service(req)
    protocols = svc.get_protocols(category=category)
    return 200, {"protocols": protocols}


def handle_get_protocol_detail(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/clinical/protocols/{id}"""
    protocol_id = req.get("params", {}).get("id", "")
    svc = _get_service(req)
    protocol = svc.get_protocol_by_id(protocol_id)
    return 200, {"protocol": protocol}


def handle_get_kits(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/clinical/kits"""
    svc = _get_service(req)
    kits = svc.get_protocol_kits()
    return 200, {"kits": kits}


def handle_get_parhez_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/clinical/parhez"""
    svc = _get_service(req)
    parhez_list = svc.get_parhez_protocols()
    return 200, {"parhez_protocols": parhez_list}


def handle_get_parhez_detail(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/clinical/parhez/{code}"""
    code = req.get("params", {}).get("code", "")
    svc = _get_service(req)
    parhez = svc.get_parhez_by_code(code)
    return 200, {"parhez": parhez}


def handle_check_safety(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/clinical/safety/check"""
    body = req.get("body", {})
    herbs = body.get("herbs", [])
    medications = body.get("medications", [])

    svc = _get_service(req)
    alerts = svc.check_herb_drug_safety(herbs=herbs, prescription_drugs=medications)
    return 200, {"alerts": alerts, "alerts_count": len(alerts)}

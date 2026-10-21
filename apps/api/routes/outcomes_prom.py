"""PROMs and Medication Adherence REST API Routes."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.domains.outcomes_prom import OutcomesPromService
from apps.api.core.errors import AuthenticationError

def handle_prom_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    if not req.get("user"):
        raise AuthenticationError("Authentication required to submit PROMs outcome measures.")
    body = req.get("body", {})
    res = OutcomesPromService.record_prom_response(conn, body)
    return 201, res

def handle_prom_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    if not req.get("user"):
        raise AuthenticationError("Authentication required to view patient outcome measures.")
    patient_id = req.get("query_params", {}).get("patient_id", "")
    proms = OutcomesPromService.get_patient_proms(conn, patient_id)
    return 200, {"proms": proms, "total": len(proms)}

def handle_adherence_create(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    if not req.get("user"):
        raise AuthenticationError("Authentication required to submit adherence logs.")
    body = req.get("body", {})
    res = OutcomesPromService.record_adherence(conn, body)
    return 201, res

def handle_adherence_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    if not req.get("user"):
        raise AuthenticationError("Authentication required to view adherence records.")
    patient_id = req.get("query_params", {}).get("patient_id", "")
    records = OutcomesPromService.get_patient_adherence(conn, patient_id)
    return 200, {"adherence_records": records, "total": len(records)}

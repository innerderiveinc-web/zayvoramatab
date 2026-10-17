"""ZFIE (Formulation Intelligence Engine) REST API Routes."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.domains.zfie_engine import ZfieEngine

def handle_zfie_formulation_profile(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    sku = req["path_params"].get("sku")
    profile = ZfieEngine.get_formulation_molecular_profile(conn, sku)
    if not profile:
        return 404, {"error": f"Formulation SKU '{sku}' not found"}
    return 200, profile

def handle_zfie_compounds(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    compounds = ZfieEngine.list_compounds(conn)
    return 200, {"compounds": compounds, "total": len(compounds)}

def handle_zfie_targets(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    targets = ZfieEngine.list_targets(conn)
    return 200, {"targets": targets, "total": len(targets)}

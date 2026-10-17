"""Inventory and Pharmacy Dispensing REST API Routes."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.domains.inventory import InventoryService
from apps.api.core.errors import AppError, ValidationError, ForbiddenError, NotFoundError

def handle_inventory_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    facility_id = req.get("query_params", {}).get("facility_id")
    items = InventoryService.get_fefo_inventory(conn, facility_id)
    return 200, {"inventory": items, "total": len(items), "ordering": "FEFO (Earliest Expiry First)"}

def handle_inventory_allocate_fefo(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    body = req.get("body", {})
    item_name = body.get("item_name") or req.get("query_params", {}).get("item_name", "")
    qty = float(body.get("quantity") or req.get("query_params", {}).get("quantity", 1))
    
    try:
        allocation = InventoryService.allocate_fefo(conn, item_name, qty)
        return 200, allocation
    except (ValidationError, NotFoundError) as e:
        return 400, {"error": str(e)}

def handle_inventory_dispense(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    body = req.get("body", {})
    batch_number = body.get("batch_number", "")
    qty = float(body.get("quantity", 1))
    mudabbar_cert = body.get("mudabbar_cert")
    user = req.get("user") or {}
    user_role = user.get("role", "PHARMACIST")

    try:
        result = InventoryService.dispense_stock(
            conn=conn,
            batch_number=batch_number,
            quantity=qty,
            user_role=user_role,
            mudabbar_cert=mudabbar_cert
        )
        return 200, result
    except ForbiddenError as e:
        return 403, {"error": str(e), "code": "MUDABBAR_CERT_REQUIRED", "requires_mudabbar": True, "message": str(e)}
    except (ValidationError, NotFoundError) as e:
        return 400, {"error": str(e)}

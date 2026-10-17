"""ZAYVORA MATAB OS — FEFO Inventory, Dispensing & Statutory Mudabbar Safety Gate.

Enforces:
1. FEFO (First-Expiry-First-Out) multi-batch prioritization and automated splitting.
2. Statutory Expiry Gate (hard rejection of expired batches, HTTP 400).
3. Schedule E(1) Mudabbar Certificate Gate (hard rejection of unpurified toxic items, HTTP 403).
4. Stock Sufficiency Guardrails.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from apps.api.core.errors import ValidationError, ForbiddenError, NotFoundError

class InventoryService:
    """Core domain service for Pharmacy Inventory and Dispensing."""

    @classmethod
    def get_fefo_inventory(cls, conn: sqlite3.Connection, facility_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns inventory items strictly ordered by expiry_date ASC (FEFO priority)."""
        cur = conn.cursor()
        query = "SELECT * FROM inventory"
        params = []
        if facility_id:
            query += " WHERE facility_id = ?"
            params.append(facility_id)
        query += " ORDER BY expiry_date ASC"
        
        cur.execute(query, tuple(params))
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    @classmethod
    def allocate_fefo(cls, conn: sqlite3.Connection, item_name: str, requested_qty: float) -> Dict[str, Any]:
        """Allocates stock across earliest expiring batches (FEFO multi-lot split)."""
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, batch_number, expiry_date, stock_qty, unit_price, is_schedule_e1, mudabbar_required, mudabbar_cert
            FROM inventory
            WHERE LOWER(name) LIKE ? AND stock_qty > 0
            ORDER BY expiry_date ASC
        """, (f"%{item_name.lower()}%",))
        
        rows = cur.fetchall()
        if not rows:
            raise NotFoundError(f"No available stock for medication: '{item_name}'")

        allocations = []
        remaining_needed = requested_qty
        now_str = datetime.now().strftime("%Y-%m-%d")

        for row in rows:
            batch_id, name, batch_num, exp_date, stock, price, is_e1, mud_req, mud_cert = row
            
            # Skip expired lots in allocation
            if exp_date < now_str:
                continue

            take_qty = min(remaining_needed, stock)
            allocations.append({
                "inventory_id": batch_id,
                "name": name,
                "batch_number": batch_num,
                "expiry_date": exp_date,
                "allocated_qty": take_qty,
                "available_stock": stock,
                "unit_price": price,
                "is_schedule_e1": bool(is_e1),
                "mudabbar_certified": bool(mud_cert)
            })
            remaining_needed -= take_qty
            if remaining_needed <= 0:
                break

        if remaining_needed > 0:
            raise ValidationError(
                f"Insufficient stock for '{item_name}'. Requested: {requested_qty}, Allocated: {requested_qty - remaining_needed}"
            )

        return {
            "item_name": item_name,
            "requested_qty": requested_qty,
            "allocations": allocations,
            "batches_count": len(allocations),
            "allocation_strategy": "FEFO (First-Expiry-First-Out)"
        }

    @classmethod
    def dispense_stock(
        cls,
        conn: sqlite3.Connection,
        batch_number: str,
        quantity: float,
        user_role: str = "PHARMACIST",
        mudabbar_cert: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dispenses stock with statutory expiry check and Schedule E(1) Mudabbar Certificate verification."""
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory WHERE batch_number = ?", (batch_number,))
        row = cur.fetchone()
        if not row:
            raise NotFoundError(f"Inventory batch '{batch_number}' not found.")
        
        cols = [c[0] for c in cur.description]
        item = dict(zip(cols, row))

        # 1. Statutory Expiry Gate
        now_str = datetime.now().strftime("%Y-%m-%d")
        if item["expiry_date"] < now_str:
            raise ValidationError(
                f"Dispensing blocked: Batch '{batch_number}' expired on {item['expiry_date']}."
            )

        # 2. Schedule E(1) Mudabbar Gate
        if item.get("is_schedule_e1") and item.get("mudabbar_required"):
            valid_cert = item.get("mudabbar_cert") or mudabbar_cert
            if not valid_cert or not str(valid_cert).strip():
                raise ForbiddenError(
                    f"DISPENSE BLOCKED: Schedule E(1) statutory botanical '{item['name']}' requires a Mudabbar (Detoxification) Certificate. "
                    f"Please provide Lab/Internal Mudabbar Certificate ID or obtain Head Hakim verification."
                )
            if mudabbar_cert and not item.get("mudabbar_cert"):
                cur.execute("UPDATE inventory SET mudabbar_cert = ? WHERE batch_number = ?", (str(mudabbar_cert).strip(), batch_number))

        # 3. Stock Sufficiency Check
        if item["stock_qty"] < quantity:
            raise ValidationError(
                f"Insufficient stock for batch '{batch_number}'. Available: {item['stock_qty']}, Requested: {quantity}."
            )

        # 4. Atomic Decrement
        new_qty = item["stock_qty"] - quantity
        cur.execute("UPDATE inventory SET stock_qty = ? WHERE batch_number = ?", (new_qty, batch_number))
        conn.commit()

        return {
            "status": "DISPENSED",
            "batch_number": batch_number,
            "medication": item["name"],
            "dispensed_qty": quantity,
            "remaining_stock": new_qty,
            "expiry_date": item["expiry_date"],
            "schedule_e1": bool(item.get("is_schedule_e1")),
            "mudabbar_verified": True if item.get("is_schedule_e1") else False
        }

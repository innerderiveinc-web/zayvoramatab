"""Server-owned Capability and Engine State Registry."""

from typing import Dict, Any, List
import sqlite3

CAPABILITY_STATUS_VOCABULARY = [
    "NOT_IMPLEMENTED",
    "IMPLEMENTED_NOT_CONNECTED",
    "CONNECTED_NOT_VALIDATED",
    "FUNCTIONALLY_TESTED",
    "CLINICALLY_REVIEWED",
    "PILOT_APPROVED",
    "PRODUCTION_APPROVED",
    "DISABLED_OR_DEGRADED"
]

def list_capabilities(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Retrieve full capability registry."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT engine_id, name, version, status, is_enabled, health_reason, required_permission, last_updated_at
        FROM capability_registry
        ORDER BY engine_id ASC;
    """)
    return [dict(r) for r in cursor.fetchall()]

def get_capability(conn: sqlite3.Connection, engine_id: str) -> Dict[str, Any]:
    """Retrieve capability status by ID."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT engine_id, name, version, status, is_enabled, health_reason, required_permission, last_updated_at
        FROM capability_registry
        WHERE engine_id = ?;
    """, (engine_id,))
    row = cursor.fetchone()
    if not row:
        return {
            "engine_id": engine_id,
            "name": engine_id,
            "version": "1.0.0",
            "status": "NOT_IMPLEMENTED",
            "is_enabled": 0,
            "health_reason": "Not registered in capability store"
        }
    return dict(row)

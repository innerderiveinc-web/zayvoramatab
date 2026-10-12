"""Feature and Engine Capability Registry for ZAYVORA MATAB OS."""

from typing import Dict, List, Any
import sqlite3
from matab.core.errors import AppError

CAPABILITY_LIFECYCLE_STATES = [
    "NOT_IMPLEMENTED",
    "IMPLEMENTED_NOT_CONNECTED",
    "CONNECTED_NOT_VALIDATED",
    "FUNCTIONALLY_TESTED",
    "CLINICALLY_REVIEWED",
    "PILOT_APPROVED",
    "PRODUCTION_APPROVED",
    "DISABLED_OR_DEGRADED"
]

# Numerical rank to assess readiness hierarchy
STATE_RANK = {state: idx for idx, state in enumerate(CAPABILITY_LIFECYCLE_STATES)}

class CapabilityUnavailableError(AppError):
    def __init__(self, engine_id: str, current_state: str, required_state: str):
        super().__init__(
            message=f"Capability '{engine_id}' is in state '{current_state}', but '{required_state}' is required.",
            code="CAPABILITY_UNAVAILABLE",
            status_code=503,
            details={"engine_id": engine_id, "current_state": current_state, "required_state": required_state}
        )

def get_all_capabilities(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Retrieve all engine capabilities and their current lifecycle statuses."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT engine_id, name, version, state, last_tested_at, owner 
        FROM feature_registry 
        ORDER BY engine_id ASC;
    """)
    return [dict(row) for row in cursor.fetchall()]

def get_capability_status(conn: sqlite3.Connection, engine_id: str) -> Dict[str, Any]:
    """Retrieve capability record for a specific engine."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT engine_id, name, version, state, last_tested_at, owner 
        FROM feature_registry 
        WHERE engine_id = ?;
    """, (engine_id,))
    row = cursor.fetchone()
    if not row:
        return {
            "engine_id": engine_id,
            "name": engine_id,
            "version": "0.0.0",
            "state": "NOT_IMPLEMENTED",
            "owner": "Unknown"
        }
    return dict(row)

def assert_capability_ready(conn: sqlite3.Connection, engine_id: str, min_required_state: str = "FUNCTIONALLY_TESTED") -> None:
    """Verify that a capability meets minimum readiness threshold."""
    cap = get_capability_status(conn, engine_id)
    current_state = cap["state"]
    
    if current_state == "DISABLED_OR_DEGRADED":
        raise CapabilityUnavailableError(engine_id, current_state, min_required_state)
        
    current_rank = STATE_RANK.get(current_state, 0)
    required_rank = STATE_RANK.get(min_required_state, 3)
    
    if current_rank < required_rank:
        raise CapabilityUnavailableError(engine_id, current_state, min_required_state)

def update_capability_state(conn: sqlite3.Connection, engine_id: str, new_state: str, owner: str = None) -> None:
    """Update lifecycle status in registry with valid state constraint."""
    if new_state not in CAPABILITY_LIFECYCLE_STATES:
        raise ValueError(f"Invalid capability state: {new_state}")
    conn.execute("""
        UPDATE feature_registry 
        SET state = ?, last_tested_at = CURRENT_TIMESTAMP, owner = COALESCE(?, owner)
        WHERE engine_id = ?;
    """, (new_state, owner, engine_id))

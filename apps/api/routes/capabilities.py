"""Capability Registry Route."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.registry import list_capabilities

def handle_capabilities_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    request_id = req.get("request_id")
    # In foundation phase, all authenticated users may inspect system capabilities
    capabilities = list_capabilities(conn)
    return 200, {
        "capabilities": capabilities,
        "count": len(capabilities),
        "request_id": request_id
    }

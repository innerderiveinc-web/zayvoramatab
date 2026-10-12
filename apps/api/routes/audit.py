"""Security Audit Log Inspection Route."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.core.permissions import require_permission
from apps.api.core.audit import get_audit_events

def handle_audit_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    request_id = req.get("request_id")
    require_permission(user, "audit:read", request_id=request_id)

    query_params = req.get("query_params", {})
    limit = int(query_params.get("limit", 50))
    offset = int(query_params.get("offset", 0))

    events = get_audit_events(conn, user["organization_id"], limit=limit, offset=offset)
    return 200, {
        "audit_events": events,
        "count": len(events),
        "limit": limit,
        "offset": offset,
        "request_id": request_id
    }

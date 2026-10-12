"""Append-Only Security Audit Logging Service."""

import uuid
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import sqlite3

SENSITIVE_KEYS = {"password", "token", "secret", "pin", "password_hash", "access_token"}

def sanitize_audit_details(details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Scrub passwords, tokens, and secrets from audit payloads."""
    if not details:
        return {}
    clean = {}
    for k, v in details.items():
        if k.lower() in SENSITIVE_KEYS:
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = sanitize_audit_details(v)
        else:
            clean[k] = v
    return clean

def log_audit_event(conn: sqlite3.Connection, action_type: str, target_entity_type: str,
                    target_entity_id: str, request_id: str, outcome: str = "SUCCESS",
                    actor_id: Optional[str] = None, organization_id: Optional[str] = None,
                    facility_id: Optional[str] = None, reason_code: Optional[str] = None,
                    client_ip: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> str:
    """Record an immutable, append-only audit event."""
    event_id = str(uuid.uuid4())
    clean_details = sanitize_audit_details(details)
    details_json = json.dumps(clean_details, sort_keys=True)
    
    conn.execute("""
        INSERT INTO audit_events 
        (id, organization_id, facility_id, actor_id, action_type, target_entity_type, target_entity_id, outcome, reason_code, request_id, client_ip, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
    """, (
        event_id,
        organization_id,
        facility_id,
        actor_id,
        action_type,
        target_entity_type,
        target_entity_id,
        outcome,
        reason_code,
        request_id,
        client_ip,
        details_json
    ))
    return event_id

def get_audit_events(conn: sqlite3.Connection, organization_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Fetch paginated audit log for an organization."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.organization_id, a.facility_id, a.actor_id, a.action_type,
               a.target_entity_type, a.target_entity_id, a.outcome, a.reason_code,
               a.request_id, a.client_ip, a.details, a.created_at,
               u.username as actor_username
        FROM audit_events a
        LEFT JOIN users u ON a.actor_id = u.id
        WHERE a.organization_id = ?
        ORDER BY a.created_at DESC
        LIMIT ? OFFSET ?;
    """, (organization_id, limit, offset))
    return [dict(row) for row in cursor.fetchall()]

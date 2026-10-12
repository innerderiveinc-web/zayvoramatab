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

def log_audit_event(conn: sqlite3.Connection, action_type: Optional[str] = None,
                    target_entity_type: Optional[str] = None, target_entity_id: Optional[str] = None,
                    request_id: Optional[str] = None, outcome: str = "SUCCESS",
                    actor_id: Optional[str] = None, organization_id: Optional[str] = None,
                    facility_id: Optional[str] = None, reason_code: Optional[str] = None,
                    client_ip: Optional[str] = None, details: Optional[Dict[str, Any]] = None,
                    **kwargs) -> str:
    """Record an immutable, append-only audit event."""
    action = action_type or kwargs.get("event_type") or "UNKNOWN_ACTION"
    target_type = target_entity_type or kwargs.get("resource_type") or "UNKNOWN_RESOURCE"
    target_id = target_entity_id or kwargs.get("resource_id") or "UNKNOWN_ID"
    req_id = request_id or kwargs.get("req_id") or str(uuid.uuid4())
    act_id = actor_id or kwargs.get("actor_user_id")
    org_id = organization_id or kwargs.get("organization_id")
    fac_id = facility_id or kwargs.get("facility_id")
    res_code = reason_code or kwargs.get("reason_code")
    outc = outcome or kwargs.get("outcome") or "SUCCESS"

    merged_details = dict(details or {})
    if "description" in kwargs:
        merged_details["description"] = kwargs["description"]
    if "patient_id" in kwargs:
        merged_details["patient_id"] = kwargs["patient_id"]
    if "encounter_id" in kwargs:
        merged_details["encounter_id"] = kwargs["encounter_id"]

    event_id = str(uuid.uuid4())
    clean_details = sanitize_audit_details(merged_details)
    details_json = json.dumps(clean_details, sort_keys=True)
    
    conn.execute("""
        INSERT INTO audit_events 
        (id, organization_id, facility_id, actor_id, action_type, target_entity_type, target_entity_id, outcome, reason_code, request_id, client_ip, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
    """, (
        event_id,
        org_id,
        fac_id,
        act_id,
        action,
        target_type,
        target_id,
        outc,
        res_code,
        req_id,
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

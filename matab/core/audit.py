"""Tamper-evident Chained Audit Logging for ZAYVORA MATAB OS."""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import sqlite3

GENESIS_HASH = "0" * 64

def compute_chain_hash(prev_hash: str, timestamp_str: str, org_id: str, actor_id: Optional[str],
                       action_type: str, resource_type: str, resource_id: str, details_str: str) -> str:
    """Compute cryptographic SHA-256 chain hash linking to prior audit record."""
    material = f"{prev_hash}|{timestamp_str}|{org_id}|{actor_id or 'SYSTEM'}|{action_type}|{resource_type}|{resource_id}|{details_str}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()

def record_audit_event(conn: sqlite3.Connection, organization_id: str, action_type: str,
                       resource_type: str, resource_id: str, actor_id: Optional[str] = None,
                       facility_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None,
                       client_ip: Optional[str] = None) -> str:
    """Record a new tamper-evident audit event linked to the previous event in the organization."""
    cursor = conn.cursor()
    
    # Retrieve the latest chain_hash for this organization
    cursor.execute("""
        SELECT chain_hash FROM audit_events 
        WHERE organization_id = ? 
        ORDER BY created_at DESC, rowid DESC 
        LIMIT 1;
    """, (organization_id,))
    prev_row = cursor.fetchone()
    prev_hash = prev_row["chain_hash"] if prev_row else GENESIS_HASH
    
    event_id = str(uuid.uuid4())
    timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    details_str = json.dumps(details or {}, sort_keys=True)
    
    chain_hash = compute_chain_hash(
        prev_hash=prev_hash,
        timestamp_str=timestamp_str,
        org_id=organization_id,
        actor_id=actor_id,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        details_str=details_str
    )
    
    conn.execute("""
        INSERT INTO audit_events 
        (id, organization_id, facility_id, actor_id, action_type, resource_type, resource_id, details, client_ip, prev_hash, chain_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (event_id, organization_id, facility_id, actor_id, action_type, resource_type, resource_id, details_str, client_ip, prev_hash, chain_hash, timestamp_str))
    
    return event_id

def verify_audit_chain(conn: sqlite3.Connection, organization_id: str) -> Dict[str, Any]:
    """Verify integrity of all audit records in organization by recomputing SHA-256 chain."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, organization_id, facility_id, actor_id, action_type, resource_type, 
               resource_id, details, client_ip, prev_hash, chain_hash, created_at
        FROM audit_events
        WHERE organization_id = ?
        ORDER BY created_at ASC, rowid ASC;
    """, (organization_id,))
    rows = cursor.fetchall()
    
    expected_prev = GENESIS_HASH
    for i, row in enumerate(rows):
        if row["prev_hash"] != expected_prev:
            return {
                "verified": False,
                "broken_at_id": row["id"],
                "index": i,
                "reason": f"Mismatched prev_hash: expected {expected_prev}, got {row['prev_hash']}"
            }
        
        recalculated = compute_chain_hash(
            prev_hash=row["prev_hash"],
            timestamp_str=row["created_at"],
            org_id=row["organization_id"],
            actor_id=row["actor_id"],
            action_type=row["action_type"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            details_str=row["details"] or "{}"
        )
        
        if recalculated != row["chain_hash"]:
            return {
                "verified": False,
                "broken_at_id": row["id"],
                "index": i,
                "reason": f"Corrupted chain_hash: expected {recalculated}, got {row['chain_hash']}"
            }
        
        expected_prev = row["chain_hash"]
        
    return {
        "verified": True,
        "count": len(rows),
        "last_hash": expected_prev
    }

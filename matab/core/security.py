"""Security and cryptographic utilities for ZAYVORA MATAB OS."""

import hashlib
import hmac
import secrets
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import sqlite3
from matab.core.errors import AuthenticationError

ITERATIONS = 100000

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with cryptographically random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS
    )
    return f"pbkdf2:sha256:{ITERATIONS}${salt}${key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored PBKDF2 hash or migration seed format."""
    try:
        parts = hashed.split("$")
        if len(parts) == 3:
            algo_info, salt, stored_key = parts
            algo_parts = algo_info.split(":")
            iters = int(algo_parts[2]) if len(algo_parts) > 2 else ITERATIONS
            key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                iters
            )
            return hmac.compare_digest(key.hex(), stored_key)
        return False
    except Exception:
        return False

def hash_pin(pin: str) -> str:
    """Generate SHA-256 hash for practitioner signing PIN."""
    return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()

def verify_pin(pin: str, stored_pin_hash: str) -> bool:
    """Verify practitioner signing PIN."""
    computed = hash_pin(pin)
    return hmac.compare_digest(computed, stored_pin_hash)

def generate_session_token() -> str:
    """Generate a 256-bit cryptographically secure session token."""
    return secrets.token_hex(32)

def calculate_prescription_hash(prescription_data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 fingerprint for an immutable prescription."""
    canonical_json = json.dumps(prescription_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

def create_session(conn: sqlite3.Connection, user_id: str, facility_id: Optional[str] = None, hours_valid: int = 12) -> str:
    """Store a new session token in the database."""
    token = generate_session_token()
    expires_at = (datetime.utcnow() + timedelta(hours=hours_valid)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO sessions (token, user_id, facility_id, expires_at) VALUES (?, ?, ?, ?);",
        (token, user_id, facility_id, expires_at)
    )
    return token

def validate_session(conn: sqlite3.Connection, token: str) -> Dict[str, Any]:
    """Validate active session token and retrieve user & facility context."""
    if not token:
        raise AuthenticationError("Session token missing")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.token, s.user_id, s.facility_id, s.expires_at,
               u.organization_id, u.username, u.role, u.full_name, u.is_active,
               f.name as facility_name, f.code as facility_code,
               o.name as org_name, o.code as org_code, o.profile_type as org_profile
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN facilities f ON s.facility_id = f.id
        JOIN organizations o ON u.organization_id = o.id
        WHERE s.token = ?;
    """, (token,))
    row = cursor.fetchone()
    
    if not row:
        raise AuthenticationError("Invalid or expired session token")
    
    expires_at = row["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.strptime(expires_at.split(".")[0], "%Y-%m-%d %H:%M:%S")
    if datetime.utcnow() > expires_at:
        conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))
        raise AuthenticationError("Session has expired")
    
    if not row["is_active"]:
        raise AuthenticationError("User account is deactivated")
        
    return dict(row)

"""Security, Session Management, and In-Memory Rate Limiting."""

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import sqlite3
from apps.api.config import config
from apps.api.core.errors import AuthenticationError, RateLimitError

ITERATIONS = 100000

# Rate limiter tracking {ip: [timestamps]}
_rate_limit_store: Dict[str, list] = {}

def reset_rate_limit_store() -> None:
    """Clear in-memory rate limiter store (primarily for test harnesses)."""
    _rate_limit_store.clear()

def check_rate_limit(client_ip: str, limit_per_minute: int = 10) -> None:
    """Enforce request rate limit per client IP."""
    now = time.time()
    window_start = now - 60.0
    
    attempts = _rate_limit_store.get(client_ip, [])
    # Filter attempts within current 60s window
    attempts = [t for t in attempts if t > window_start]
    
    if len(attempts) >= limit_per_minute:
        _rate_limit_store[client_ip] = attempts
        raise RateLimitError("Rate limit exceeded for authentication endpoint. Try again in 1 minute.")
        
    attempts.append(now)
    _rate_limit_store[client_ip] = attempts

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with cryptographically random salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS)
    return f"pbkdf2:sha256:{ITERATIONS}${salt}${key.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored PBKDF2 hash."""
    try:
        parts = hashed.split("$")
        if len(parts) == 3:
            algo_info, salt, stored_key = parts
            algo_parts = algo_info.split(":")
            iters = int(algo_parts[2]) if len(algo_parts) > 2 else ITERATIONS
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iters)
            return hmac.compare_digest(key.hex(), stored_key)
        return False
    except Exception:
        return False

def generate_token() -> str:
    """Generate cryptographically secure 256-bit token."""
    return secrets.token_hex(32)

def create_session(conn: sqlite3.Connection, user_id: str, organization_id: str,
                   active_facility_id: Optional[str] = None, ip_address: Optional[str] = None,
                   user_agent: Optional[str] = None) -> str:
    """Persist new session token in the database."""
    token = generate_token()
    expires_at = (datetime.utcnow() + timedelta(hours=config.session_hours)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("""
        INSERT INTO sessions (token, user_id, organization_id, active_facility_id, expires_at, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (token, user_id, organization_id, active_facility_id, expires_at, ip_address, user_agent))
    return token

def validate_session(conn: sqlite3.Connection, token: str) -> Dict[str, Any]:
    """Retrieve session, user, and organization context; reject expired or invalid tokens."""
    if not token:
        raise AuthenticationError("Authentication token is required")

    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.token, s.user_id, s.organization_id, s.active_facility_id, s.expires_at,
               u.username, u.full_name, u.email, u.is_active,
               o.name as org_name, o.code as org_code, o.profile_type as org_profile,
               f.name as facility_name, f.code as facility_code
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        JOIN organizations o ON s.organization_id = o.id
        LEFT JOIN facilities f ON s.active_facility_id = f.id
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

    # Fetch user roles & permissions
    cursor.execute("""
        SELECT r.code as role_code, p.code as perm_code
        FROM user_organization_memberships uom
        JOIN roles r ON uom.role_id = r.id
        JOIN role_permissions rp ON r.id = rp.role_id
        JOIN permissions p ON rp.permission_id = p.id
        WHERE uom.user_id = ? AND uom.organization_id = ? AND uom.is_active = 1;
    """, (row["user_id"], row["organization_id"]))
    
    perms = set()
    roles = set()
    for p_row in cursor.fetchall():
        roles.add(p_row["role_code"])
        perms.add(p_row["perm_code"])

    user_ctx = dict(row)
    user_ctx["roles"] = list(roles)
    user_ctx["permissions"] = list(perms)
    return user_ctx

def hash_pin(pin: str) -> str:
    """Generate SHA-256 hash for practitioner digital signing PIN."""
    return hashlib.sha256(pin.strip().encode("utf-8")).hexdigest()

def verify_pin(pin: str, stored_pin_hash: str) -> bool:
    """Verify practitioner signing PIN against stored hash."""
    if not pin or not stored_pin_hash:
        return False
    computed = hash_pin(pin)
    return hmac.compare_digest(computed, stored_pin_hash)

def calculate_prescription_hash(prescription_data: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 fingerprint for an immutable prescription."""
    import json
    canonical_json = json.dumps(prescription_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


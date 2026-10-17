"""Security, Session Management, Scope-Aware Context Resolution, and In-Memory Rate Limiting."""

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Set, List
import sqlite3
from apps.api.config import config
from apps.api.core.errors import AuthenticationError, RateLimitError, ForbiddenError

ITERATIONS = 100000

# Rate limiter tracking {ip: [timestamps]}
_rate_limit_store: Dict[str, list] = {}


def reset_rate_limit_store() -> None:
    """Clear in-memory rate limiter store (primarily for test harnesses)."""
    _rate_limit_store.clear()


def check_rate_limit(client_ip: str, limit_per_minute: int = 10) -> None:
    """Enforce request rate limit per client IP."""
    if os.environ.get("MATAB_ENV") == "testing" or os.environ.get("TESTING") == "1":
        return

    now = time.time()
    window_start = now - 60.0

    if limit_per_minute == 10 and (client_ip in ("127.0.0.1", "localhost", "::1") or os.environ.get("MATAB_ENV") == "development"):
        limit_per_minute = 120

    attempts = _rate_limit_store.get(client_ip, [])
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


def create_session(
    conn: sqlite3.Connection,
    user_id: str,
    organization_id: str,
    active_facility_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """Persist new session token in the database."""
    token = generate_token()
    expires_at = (datetime.utcnow() + timedelta(hours=config.session_hours)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        INSERT INTO sessions (token, user_id, organization_id, active_facility_id, expires_at, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (token, user_id, organization_id, active_facility_id, expires_at, ip_address, user_agent),
    )
    return token


def _load_role_permissions_map(cursor: sqlite3.Cursor) -> Dict[str, Set[str]]:
    """Return mapping of role_code -> set of permission codes."""
    cursor.execute(
        """
        SELECT r.code AS role_code, p.code AS perm_code
        FROM roles r
        JOIN role_permissions rp ON r.id = rp.role_id
        JOIN permissions p ON rp.permission_id = p.id;
        """
    )
    mapping: Dict[str, Set[str]] = {}
    for r in cursor.fetchall():
        mapping.setdefault(r["role_code"], set()).add(r["perm_code"])
    return mapping


def validate_session(
    conn: sqlite3.Connection,
    token: str,
    requested_facility_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Retrieve session, user, organization, and scoped facility assignment context; reject expired or invalid tokens."""
    if not token:
        raise AuthenticationError("Authentication token is required")

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.token, s.user_id, s.organization_id, s.active_facility_id, s.expires_at,
               u.username, u.full_name, u.email, u.is_active,
               o.name as org_name, o.code as org_code, o.profile_type as org_profile, o.is_active as org_is_active,
               f.name as facility_name, f.code as facility_code
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        JOIN organizations o ON s.organization_id = o.id
        LEFT JOIN facilities f ON s.active_facility_id = f.id
        WHERE s.token = ?;
        """,
        (token,),
    )
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

    org_id = row["organization_id"]
    user_id = row["user_id"]

    # Check extended organization profile lifecycle if table exists
    org_lifecycle_status = "active" if row["org_is_active"] else "suspended"
    org_admin_clinical_note_access = 0
    try:
        cursor.execute(
            """
            SELECT lifecycle_status, org_admin_clinical_note_access
            FROM organization_profiles
            WHERE organization_id = ?;
            """,
            (org_id,),
        )
        op = cursor.fetchone()
        if op:
            org_lifecycle_status = op["lifecycle_status"]
            org_admin_clinical_note_access = int(op["org_admin_clinical_note_access"] or 0)
    except sqlite3.OperationalError:
        pass

    role_perms_map = _load_role_permissions_map(cursor)

    # 1. Organization-level memberships
    cursor.execute(
        """
        SELECT r.code as role_code
        FROM user_organization_memberships uom
        JOIN roles r ON uom.role_id = r.id
        WHERE uom.user_id = ? AND uom.organization_id = ? AND uom.is_active = 1;
        """,
        (user_id, org_id),
    )
    org_roles: Set[str] = set()
    org_perms: Set[str] = set()
    for p_row in cursor.fetchall():
        rc = p_row["role_code"]
        org_roles.add(rc)
        org_perms.update(role_perms_map.get(rc, set()))

    # 2. Facility-level memberships & Scoped Staff Assignments
    facility_scopes: Dict[str, Dict[str, Any]] = {}

    cursor.execute(
        """
        SELECT ufm.facility_id, r.code as role_code
        FROM user_facility_memberships ufm
        JOIN roles r ON ufm.role_id = r.id
        JOIN facilities f ON ufm.facility_id = f.id
        WHERE ufm.user_id = ? AND f.organization_id = ? AND ufm.is_active = 1;
        """,
        (user_id, org_id),
    )
    for fm_row in cursor.fetchall():
        fid = fm_row["facility_id"]
        rc = fm_row["role_code"]
        scope_entry = facility_scopes.setdefault(
            fid, {"roles": set(), "permissions": set(), "departments": set(), "has_scoped_assignment": False}
        )
        scope_entry["roles"].add(rc)
        scope_entry["permissions"].update(role_perms_map.get(rc, set()))

    # Check Enterprise staff_assignments table if present
    now_iso = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    has_any_staff_assignments = False
    try:
        cursor.execute(
            """
            SELECT id, facility_id, department_id, role_code, scope_level,
                   extra_permissions_json, restricted_permissions_json,
                   effective_from, effective_until, status
            FROM staff_assignments
            WHERE user_id = ? AND organization_id = ?;
            """,
            (user_id, org_id),
        )
        sa_rows = cursor.fetchall()
        if sa_rows:
            has_any_staff_assignments = True
            # Reset facility_scopes for facilities managed by staff_assignments so revoked assignments take immediate effect
            managed_facilities = {r["facility_id"] for r in sa_rows if r["facility_id"]}
            for m_fid in managed_facilities:
                facility_scopes[m_fid] = {
                    "roles": set(),
                    "permissions": set(),
                    "departments": set(),
                    "has_scoped_assignment": True,
                }

            for sa in sa_rows:
                if sa["status"] != "active":
                    continue
                eff_until = sa["effective_until"]
                if eff_until and str(eff_until) < now_iso:
                    continue

                rc = sa["role_code"]
                base_perms = set(role_perms_map.get(rc, set()))
                try:
                    extra_p = set(json.loads(sa["extra_permissions_json"] or "[]"))
                except Exception:
                    extra_p = set()
                try:
                    restr_p = set(json.loads(sa["restricted_permissions_json"] or "[]"))
                except Exception:
                    restr_p = set()
                effective_sa_perms = (base_perms | extra_p) - restr_p

                if sa["scope_level"] == "ORGANIZATION" or not sa["facility_id"]:
                    org_roles.add(rc)
                    org_perms = (org_perms | effective_sa_perms) - restr_p
                else:
                    fid = sa["facility_id"]
                    scope_entry = facility_scopes.setdefault(
                        fid, {"roles": set(), "permissions": set(), "departments": set(), "has_scoped_assignment": True}
                    )
                    scope_entry["roles"].add(rc)
                    scope_entry["permissions"].update(effective_sa_perms)
                    if sa["department_id"]:
                        scope_entry["departments"].add(sa["department_id"])
    except sqlite3.OperationalError:
        pass

    # Determine effective active facility for this request
    effective_facility_id = requested_facility_id or row["active_facility_id"]
    active_fac_roles: Set[str] = set()
    active_fac_perms: Set[str] = set()

    if effective_facility_id and effective_facility_id in facility_scopes:
        active_fac_roles = set(facility_scopes[effective_facility_id]["roles"])
        active_fac_perms = set(facility_scopes[effective_facility_id]["permissions"])

    # If user has explicit facility assignments (e.g. multi-branch staff), their active roles/permissions
    # at the requested facility are the union of org-level grants (if ORG_ADMIN / org-wide) and that facility's grants.
    if has_any_staff_assignments and effective_facility_id in facility_scopes:
        # Only include org_roles if user is ORG_ADMIN or has an explicit ORGANIZATION-level staff_assignment
        is_org_wide = "ORG_ADMIN" in org_roles
        combined_roles = (org_roles if is_org_wide else set()) | active_fac_roles
        combined_perms = (org_perms if is_org_wide else set()) | active_fac_perms
    else:
        combined_roles = org_roles | active_fac_roles
        combined_perms = org_perms | active_fac_perms

    serialized_scopes = {
        fid: {
            "roles": sorted(list(sc["roles"])),
            "permissions": sorted(list(sc["permissions"])),
            "departments": sorted(list(sc["departments"])),
        }
        for fid, sc in facility_scopes.items()
        if sc["roles"] or sc["permissions"]
    }

    active_facility_lifecycle_status = "active"
    if effective_facility_id:
        try:
            cursor.execute(
                "SELECT lifecycle_status FROM facility_profiles WHERE facility_id = ?;",
                (effective_facility_id,),
            )
            fp_row = cursor.fetchone()
            if fp_row and fp_row["lifecycle_status"]:
                active_facility_lifecycle_status = fp_row["lifecycle_status"]
            else:
                cursor.execute("SELECT is_active FROM facilities WHERE id = ?;", (effective_facility_id,))
                f_act = cursor.fetchone()
                if f_act and int(f_act["is_active"] or 0) == 0:
                    active_facility_lifecycle_status = "suspended"
        except sqlite3.OperationalError:
            pass

    user_ctx = dict(row)
    user_ctx["active_facility_id"] = effective_facility_id
    user_ctx["active_facility_lifecycle_status"] = active_facility_lifecycle_status
    user_ctx["org_lifecycle_status"] = org_lifecycle_status
    user_ctx["org_admin_clinical_note_access"] = org_admin_clinical_note_access
    user_ctx["roles"] = sorted(list(combined_roles))
    user_ctx["permissions"] = sorted(list(combined_perms))
    user_ctx["org_roles"] = sorted(list(org_roles))
    user_ctx["facility_scopes"] = serialized_scopes
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
    canonical_json = json.dumps(prescription_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

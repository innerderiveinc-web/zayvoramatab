import uuid
from typing import Dict, Any, Tuple
import sqlite3
from apps.api.config import config
from apps.api.core.errors import AuthenticationError, ValidationError, RateLimitError, ConflictError
from apps.api.core.security import verify_password, hash_password, create_session, check_rate_limit, generate_token, validate_session
from apps.api.core.audit import log_audit_event

def handle_auth_login(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    client_ip = req.get("client_ip", "127.0.0.1")
    request_id = req.get("request_id")
    body = req.get("body", {})
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        raise ValidationError("Username and password are required.", request_id=request_id)

    # Check IP Rate Limiting
    check_rate_limit(client_ip, limit_per_minute=config.auth_rate_limit_per_min)

    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.organization_id, u.username, u.password_hash, u.full_name, u.is_active,
               o.name as org_name, o.code as org_code, o.profile_type as org_profile
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.username = ?;
    """, (username,))
    row = cursor.fetchone()

    # Generic error message to prevent account enumeration
    if not row or not verify_password(password, row["password_hash"]):
        log_audit_event(
            conn=conn,
            action_type="AUTH_LOGIN_FAILED",
            target_entity_type="USER",
            target_entity_id=username,
            outcome="DENIED",
            reason_code="INVALID_CREDENTIALS",
            request_id=request_id,
            client_ip=client_ip,
            details={"attempted_username": username}
        )
        raise AuthenticationError("Invalid username or password.", request_id=request_id)

    if not row["is_active"]:
        log_audit_event(
            conn=conn,
            action_type="AUTH_LOGIN_FAILED",
            target_entity_type="USER",
            target_entity_id=row["id"],
            organization_id=row["organization_id"],
            outcome="DENIED",
            reason_code="ACCOUNT_DISABLED",
            request_id=request_id,
            client_ip=client_ip
        )
        raise AuthenticationError("User account is disabled. Contact your administrator.", request_id=request_id)

    # Get user's default active facility
    cursor.execute("""
        SELECT facility_id FROM user_facility_memberships
        WHERE user_id = ? AND is_active = 1
        LIMIT 1;
    """, (row["id"],))
    fm = cursor.fetchone()
    active_facility_id = fm["facility_id"] if fm else None

    # Issue Session Token
    user_agent = req.get("headers", {}).get("user-agent")
    token = create_session(
        conn=conn,
        user_id=row["id"],
        organization_id=row["organization_id"],
        active_facility_id=active_facility_id,
        ip_address=client_ip,
        user_agent=user_agent
    )

    log_audit_event(
        conn=conn,
        action_type="AUTH_LOGIN_SUCCESS",
        target_entity_type="USER",
        target_entity_id=row["id"],
        organization_id=row["organization_id"],
        facility_id=active_facility_id,
        actor_id=row["id"],
        outcome="SUCCESS",
        request_id=request_id,
        client_ip=client_ip
    )

    session_user = validate_session(conn, token)

    return 200, {
        "token": token,
        "user": session_user,
        "request_id": request_id
    }

def handle_auth_logout(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    token = req.get("auth_token")
    request_id = req.get("request_id")
    user = req.get("user")
    
    if token:
        conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))
        if user:
            log_audit_event(
                conn=conn,
                action_type="AUTH_LOGOUT",
                target_entity_type="SESSION",
                target_entity_id=token[:8] + "...",
                organization_id=user.get("organization_id"),
                actor_id=user.get("user_id"),
                outcome="SUCCESS",
                request_id=request_id,
                client_ip=req.get("client_ip")
            )

    return 200, {
        "message": "Logged out successfully.",
        "request_id": request_id
    }

def handle_auth_me(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    user = req.get("user")
    cursor = conn.cursor()
    # Also fetch practitioner profile if exists
    cursor.execute("""
        SELECT license_type, registration_number, registration_council, is_credential_verified
        FROM practitioner_profiles
        WHERE user_id = ?;
    """, (user["user_id"],))
    prac = cursor.fetchone()

    # Fetch user's assigned facilities
    cursor.execute("""
        SELECT f.id, f.name, f.code, ufm.role_id, r.code as role_code, r.name as role_name
        FROM user_facility_memberships ufm
        JOIN facilities f ON ufm.facility_id = f.id
        JOIN roles r ON ufm.role_id = r.id
        WHERE ufm.user_id = ? AND ufm.is_active = 1;
    """, (user["user_id"],))
    facilities = [dict(r) for r in cursor.fetchall()]

    return 200, {
        "user": user,
        "practitioner_profile": dict(prac) if prac else None,
        "accessible_facilities": facilities,
        "request_id": req.get("request_id")
    }

def handle_password_reset_request(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Password reset flow with development sink (safe, does not log raw secrets)."""
    body = req.get("body", {})
    email = body.get("email", "").strip()
    request_id = req.get("request_id")

    if not email:
        raise ValidationError("Email address is required.", request_id=request_id)

    cursor = conn.cursor()
    cursor.execute("SELECT id, organization_id FROM users WHERE email = ? AND is_active = 1;", (email,))
    user = cursor.fetchone()

    # Always return success message to avoid account discovery
    resp = {
        "message": "If this email is registered, a password reset authorization has been generated.",
        "request_id": request_id
    }

    if user:
        reset_token = generate_token()
        # In development only, return dev_token helper (strictly disabled in production)
        if not config.is_production():
            resp["dev_reset_token"] = reset_token

        log_audit_event(
            conn=conn,
            action_type="AUTH_PASSWORD_RESET_REQUESTED",
            target_entity_type="USER",
            target_entity_id=user["id"],
            organization_id=user["organization_id"],
            outcome="SUCCESS",
            request_id=request_id,
            client_ip=req.get("client_ip")
        )

    return 200, resp


def handle_auth_register_clinic(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Self-service Organization & Administrator Registration for new Matab/Clinics."""
    client_ip = req.get("client_ip", "127.0.0.1")
    request_id = req.get("request_id")
    body = req.get("body", {})

    org_name = body.get("org_name", "").strip()
    org_code = body.get("org_code", "").strip().upper()
    profile_type = body.get("profile_type", "MATAB").strip().upper()
    admin_name = body.get("admin_name", "").strip()
    admin_username = body.get("admin_username", "").strip()
    admin_email = body.get("admin_email", "").strip()
    admin_password = body.get("admin_password", "")

    if not org_name or not org_code or not admin_name or not admin_username or not admin_password:
        raise ValidationError("Clinic name, clinic code, administrator full name, username, and password are required.", request_id=request_id)

    if len(admin_password) < 6:
        raise ValidationError("Administrator password must be at least 6 characters long.", request_id=request_id)

    check_rate_limit(client_ip, limit_per_minute=config.auth_rate_limit_per_min)

    cursor = conn.cursor()

    # Check if organization code already exists
    cursor.execute("SELECT id FROM organizations WHERE code = ?;", (org_code,))
    if cursor.fetchone():
        raise ConflictError(f"Clinic/Organization code '{org_code}' is already registered. Please choose another code.", request_id=request_id)

    # Check if username already exists
    cursor.execute("SELECT id FROM users WHERE username = ?;", (admin_username,))
    if cursor.fetchone():
        raise ConflictError(f"Username '{admin_username}' is already taken. Please choose another username.", request_id=request_id)

    org_id = f"org-{uuid.uuid4().hex[:12]}"
    fac_id = f"fac-{uuid.uuid4().hex[:12]}"
    user_id = f"usr-{uuid.uuid4().hex[:12]}"

    # 1. Create Organization
    conn.execute("""
        INSERT INTO organizations (id, name, code, profile_type, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP);
    """, (org_id, org_name, org_code, profile_type))

    # 2. Create Default Primary Facility
    fac_name = f"{org_name} - Main OPD"
    fac_code = f"{org_code}-OPD"
    conn.execute("""
        INSERT INTO facilities (id, organization_id, name, code, is_active, created_at)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP);
    """, (fac_id, org_id, fac_name, fac_code))

    # 3. Create Root Administrator User
    pw_hash = hash_password(admin_password)
    conn.execute("""
        INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP);
    """, (user_id, org_id, admin_username, admin_email or None, pw_hash, admin_name))

    # 4. Resolve ORG_ADMIN Role
    cursor.execute("SELECT id FROM roles WHERE code = 'ORG_ADMIN';")
    role_row = cursor.fetchone()
    if role_row:
        role_id = role_row["id"]
        # Link user to organization role
        conn.execute("""
            INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
            VALUES (?, ?, ?, ?, 1);
        """, (str(uuid.uuid4()), user_id, org_id, role_id))

        # Link user to facility
        conn.execute("""
            INSERT INTO user_facility_memberships (id, user_id, facility_id, role_id, is_active)
            VALUES (?, ?, ?, ?, 1);
        """, (str(uuid.uuid4()), user_id, fac_id, role_id))

    # 5. Issue Session Token
    user_agent = req.get("headers", {}).get("user-agent")
    token = create_session(
        conn=conn,
        user_id=user_id,
        organization_id=org_id,
        active_facility_id=fac_id,
        ip_address=client_ip,
        user_agent=user_agent
    )

    log_audit_event(
        conn=conn,
        action_type="AUTH_REGISTER_CLINIC",
        target_entity_type="ORGANIZATION",
        target_entity_id=org_id,
        organization_id=org_id,
        facility_id=fac_id,
        actor_id=user_id,
        outcome="SUCCESS",
        request_id=request_id,
        client_ip=client_ip,
        details={"org_name": org_name, "org_code": org_code, "admin_username": admin_username}
    )

    session_user = validate_session(conn, token)

    return 201, {
        "token": token,
        "user": session_user,
        "organization": {
            "id": org_id,
            "name": org_name,
            "code": org_code,
            "facility_id": fac_id,
            "facility_name": fac_name
        },
        "message": "Matab Clinic & Administrator account successfully registered.",
        "request_id": request_id
    }

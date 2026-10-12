"""Identity and Authentication Domain for ZAYVORA MATAB OS."""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
import sqlite3
import hashlib
from matab.core.errors import AuthenticationError, ForbiddenError, NotFoundError
from matab.core.security import verify_password, create_session, validate_session
from matab.core.audit import record_audit_event

@dataclass
class UserSession:
    user_id: str
    username: str
    role: str
    full_name: str
    organization_id: str
    facility_id: Optional[str]
    org_name: str
    org_profile: str
    token: str

class IdentityService:
    @staticmethod
    def authenticate(conn: sqlite3.Connection, username: str, password: str, client_ip: Optional[str] = None) -> Dict[str, Any]:
        """Authenticate user with username and password, returns active session token."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.organization_id, u.username, u.password_hash, u.role, u.full_name, u.is_active,
                   o.name as org_name, o.profile_type as org_profile
            FROM users u
            JOIN organizations o ON u.organization_id = o.id
            WHERE u.username = ?;
        """, (username,))
        row = cursor.fetchone()
        
        if not row or not verify_password(password, row["password_hash"]):
            raise AuthenticationError("Invalid username or password")
            
        if not row["is_active"]:
            raise AuthenticationError("User account is disabled")
            
        # Get default facility membership if exists
        cursor.execute("""
            SELECT facility_id FROM user_facility_memberships 
            WHERE user_id = ? 
            LIMIT 1;
        """, (row["id"],))
        fm = cursor.fetchone()
        facility_id = fm["facility_id"] if fm else None
        
        token = create_session(conn, row["id"], facility_id)
        
        record_audit_event(
            conn=conn,
            organization_id=row["organization_id"],
            facility_id=facility_id,
            actor_id=row["id"],
            action_type="AUTH_LOGIN_SUCCESS",
            resource_type="USER",
            resource_id=row["id"],
            details={"username": username, "role": row["role"]},
            client_ip=client_ip
        )
        
        return {
            "token": token,
            "user": {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "full_name": row["full_name"],
                "organization_id": row["organization_id"],
                "org_name": row["org_name"],
                "org_profile": row["org_profile"],
                "facility_id": facility_id
            }
        }

    @staticmethod
    def logout(conn: sqlite3.Connection, token: str) -> None:
        """Terminate active session."""
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, organization_id, facility_id FROM sessions s JOIN users u ON s.user_id = u.id WHERE s.token = ?;", (token,))
        row = cursor.fetchone()
        if row:
            record_audit_event(
                conn=conn,
                organization_id=row["organization_id"],
                facility_id=row["facility_id"],
                actor_id=row["user_id"],
                action_type="AUTH_LOGOUT",
                resource_type="SESSION",
                resource_id=token[:8] + "..."
            )
        conn.execute("DELETE FROM sessions WHERE token = ?;", (token,))

    @staticmethod
    def get_current_user(conn: sqlite3.Connection, token: str) -> Dict[str, Any]:
        """Validate session token and return user profile details."""
        return validate_session(conn, token)

    @staticmethod
    def get_practitioner_by_user(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
        """Get practitioner licensing record for user."""
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.id, p.user_id, p.license_type, p.registration_number, p.registration_council
            FROM practitioners p
            WHERE p.user_id = ?;
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

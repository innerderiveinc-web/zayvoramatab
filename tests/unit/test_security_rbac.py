"""Unit Tests: Security, Rate Limiting, RBAC Deny-by-Default, Audit Redaction, Production Safeguard."""

import unittest
import os
import tempfile
import sqlite3
from apps.api.config import config
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.core.security import hash_password, verify_password, check_rate_limit, create_session, validate_session
from apps.api.core.permissions import require_permission, has_permission, require_facility_access
from apps.api.core.audit import log_audit_event, get_audit_events, sanitize_audit_details
from apps.api.core.errors import AuthenticationError, ForbiddenError, RateLimitError

class TestSecurityAndRbac(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_password_hashing_and_verification(self):
        pw = "TestSecurePassword#2026"
        hashed = hash_password(pw)
        self.assertTrue(hashed.startswith("pbkdf2:sha256:"))
        self.assertTrue(verify_password(pw, hashed))
        self.assertFalse(verify_password("IncorrectPassword", hashed))

    def test_rate_limiting_enforcement(self):
        ip = "192.168.1.100"
        # Calling up to limit (5) works
        for _ in range(5):
            check_rate_limit(ip, limit_per_minute=5)
        # 6th call raises RateLimitError
        with self.assertRaises(RateLimitError):
            check_rate_limit(ip, limit_per_minute=5)

    def test_deny_by_default_permissions(self):
        # User without required permission
        user_ctx = {
            "user_id": "usr-test-1",
            "roles": ["RECEPTIONIST"],
            "permissions": ["patients:read", "patients:write"]
        }
        self.assertFalse(has_permission(user_ctx, "prescriptions:sign"))
        with self.assertRaises(ForbiddenError):
            require_permission(user_ctx, "prescriptions:sign")

        # User with permission succeeds
        require_permission(user_ctx, "patients:read")

        # ORG_ADMIN has all permissions
        admin_ctx = {
            "user_id": "usr-admin-1",
            "roles": ["ORG_ADMIN"],
            "permissions": []
        }
        self.assertTrue(has_permission(admin_ctx, "prescriptions:sign"))

    def test_facility_membership_verification(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            # Hakeem is assigned to fac-central-opd
            require_facility_access(conn, "usr-hakeem-1", "fac-central-opd")

            # Hakeem is NOT assigned to a foreign facility -> raises ForbiddenError
            with self.assertRaises(ForbiddenError):
                require_facility_access(conn, "usr-hakeem-1", "fac-foreign-unknown")
        finally:
            conn.close()

    def test_audit_logging_and_sensitive_data_redaction(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            log_audit_event(
                conn=conn,
                action_type="AUTH_LOGIN_TEST",
                target_entity_type="USER",
                target_entity_id="usr-test",
                organization_id="org-matab-default",
                request_id="req-1234",
                details={
                    "username": "hakeem",
                    "password": "ClearTextPasswordShouldBeRedacted",
                    "token": "secret_session_token",
                    "pin": "1234"
                }
            )
            conn.commit()

            events = get_audit_events(conn, "org-matab-default")
            self.assertTrue(len(events) > 0)
            target_event = [e for e in events if e["request_id"] == "req-1234"][0]
            
            # Details must not contain plain passwords, tokens, or PINs
            details_str = target_event["details"]
            self.assertNotIn("ClearTextPasswordShouldBeRedacted", details_str)
            self.assertNotIn("secret_session_token", details_str)
            self.assertIn("[REDACTED]", details_str)
        finally:
            conn.close()

    def test_production_environment_refuses_seeding(self):
        # Temporarily mock environment to production
        original_env = config.env
        try:
            config.env = "production"
            with self.assertRaises(RuntimeError):
                seed_development_data(self.db_path)
        finally:
            config.env = original_env

if __name__ == "__main__":
    unittest.main()

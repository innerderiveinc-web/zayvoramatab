"""Integration Tests: Multi-Tenant Data Isolation, Cross-Tenant Prevention, and Facility Scoping."""

import unittest
import os
import tempfile
import json
import uuid
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import hash_password, create_session, reset_rate_limit_store
from apps.api.core.permissions import require_facility_access, enforce_tenant_isolation
from apps.api.core.errors import ForbiddenError, AuthenticationError
from apps.api.database.connection import get_db

class TestTenancyIsolation(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Provision a secondary tenant (Organization B) with its own facilities and user
        with get_db(self.db_path) as conn:
            # Secondary Org
            conn.execute("""
                INSERT INTO organizations (id, name, code, license_number, profile_type, is_active)
                VALUES ('org-alt-clinic', 'Al-Shifa Healthcare Ltd', 'ALT-SHIFA', 'DL-ALT-9912', 'MULTI_PRACTITIONER_CLINIC', 1);
            """)
            # Facility in Org B
            conn.execute("""
                INSERT INTO facilities (id, organization_id, name, code, address, phone, is_active)
                VALUES ('fac-alt-branch', 'org-alt-clinic', 'Al-Shifa North Clinic', 'FAC-ALT-01', 'North Zone', '555-0199', 1);
            """)
            # User in Org B
            pw_hash = hash_password("altpass123")
            conn.execute("""
                INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
                VALUES ('usr-alt-dr', 'org-alt-clinic', 'dr_alt', 'dr.alt@shifa.test', ?, 'Dr. Alternate', 1);
            """, (pw_hash,))
            # Role membership for User B
            conn.execute("""
                INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
                VALUES ('uom-alt-1', 'usr-alt-dr', 'org-alt-clinic', 'role-practitioner', 1);
            """)
            conn.execute("""
                INSERT INTO user_facility_memberships (id, user_id, facility_id, role_id, is_active)
                VALUES ('ufm-alt-1', 'usr-alt-dr', 'fac-alt-branch', 'role-practitioner', 1);
            """)
            conn.commit()

        # Login as User A (Hakeem in Org A)
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token_user_a = json.loads(resp_bytes.decode("utf-8"))["token"]

        # Login as User B (Dr Alternate in Org B)
        login_body_b = json.dumps({"username": "dr_alt", "password": "altpass123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_b, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token_user_b = json.loads(resp_bytes.decode("utf-8"))["token"]

        # Login as Auditor (Read-only auditor in Org A)
        login_body_aud = json.dumps({"username": "auditor", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_aud, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token_auditor = json.loads(resp_bytes.decode("utf-8"))["token"]

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_facility_list_strict_tenant_scoping(self):
        """User A only sees facilities in Org A; User B only sees facilities in Org B."""
        # Query facilities as User A (Org A)
        headers_a = {"authorization": f"Bearer {self.token_user_a}"}
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/facilities", headers_a, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data_a = json.loads(resp.decode("utf-8"))
        facility_ids_a = [f["id"] for f in data_a["facilities"]]
        
        self.assertIn("fac-central-opd", facility_ids_a)
        self.assertIn("fac-south-branch", facility_ids_a)
        self.assertNotIn("fac-alt-branch", facility_ids_a)

        # Query facilities as User B (Org B)
        headers_b = {"authorization": f"Bearer {self.token_user_b}"}
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/facilities", headers_b, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data_b = json.loads(resp.decode("utf-8"))
        facility_ids_b = [f["id"] for f in data_b["facilities"]]

        self.assertIn("fac-alt-branch", facility_ids_b)
        self.assertNotIn("fac-central-opd", facility_ids_b)
        self.assertNotIn("fac-south-annex", facility_ids_b)

    def test_cross_tenant_facility_access_rejected_with_403(self):
        """User A attempting to access Facility of Org B by direct ID is blocked with 403."""
        headers_a = {"authorization": f"Bearer {self.token_user_a}"}
        # Direct ID of Org B's facility
        status, _, resp = ApiRouter.dispatch(
            "GET", "/api/v1/facilities/fac-alt-branch", headers_a, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 403)
        err = json.loads(resp.decode("utf-8"))
        self.assertTrue(err.get("error"))
        self.assertEqual(err.get("code"), "FORBIDDEN")
        self.assertIn("Cross-tenant access violation", err.get("message"))

    def test_unauthenticated_request_rejected(self):
        """Requesting protected resource without authorization header returns 401."""
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/facilities", {}, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 401)
        err = json.loads(resp.decode("utf-8"))
        self.assertEqual(err.get("code"), "UNAUTHORIZED")

    def test_invalid_token_rejected(self):
        """Requesting protected resource with forged token returns 401."""
        headers = {"authorization": "Bearer forged-or-expired-token-xyz"}
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/facilities", headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 401)
        err = json.loads(resp.decode("utf-8"))
        self.assertEqual(err.get("code"), "UNAUTHORIZED")

    def test_role_permission_denial(self):
        """Auditor role lacks 'facility:manage' permission and cannot create a facility."""
        headers_aud = {"authorization": f"Bearer {self.token_auditor}"}
        create_body = json.dumps({"name": "Unauthorized Annex", "code": "UNAUTH-01"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", "/api/v1/facilities", headers_aud, {}, create_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 403)
        err = json.loads(resp.decode("utf-8"))
        self.assertEqual(err.get("code"), "FORBIDDEN")
        self.assertIn("facility:manage", err.get("message"))

    def test_enforce_tenant_isolation_helper(self):
        """Direct test of enforce_tenant_isolation helper function."""
        user_ctx = {"organization_id": "org-matab-default"}
        # Same organization passes without error
        enforce_tenant_isolation(user_ctx, "org-matab-default")
        # Different organization raises ForbiddenError
        with self.assertRaises(ForbiddenError):
            enforce_tenant_isolation(user_ctx, "org-other-clinic")

    def test_facility_scope_validation(self):
        """Direct test of require_facility_access helper."""
        with get_db(self.db_path) as conn:
            # Hakeem is assigned to fac-central-opd in seed data
            require_facility_access(conn, "usr-hakeem-1", "fac-central-opd")
            # Unassigned facility raises ForbiddenError
            with self.assertRaises(ForbiddenError):
                require_facility_access(conn, "usr-hakeem-1", "fac-south-branch")

if __name__ == "__main__":
    unittest.main()

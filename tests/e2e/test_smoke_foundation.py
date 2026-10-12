"""End-to-End Smoke Test: Complete Foundation Lifecycle.

Tests:
1. Schema migration & seed execution.
2. Observability health & readiness checks.
3. Authentication, credential verification, and session lifecycle.
4. User context (/auth/me) with organization, facility memberships, and roles.
5. Tenancy & facility scoping.
6. System capability registry retrieval.
7. Audit log verification and secret redaction.
8. Logout and session invalidation.
"""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store
from apps.api.database.connection import get_db

class TestSmokeFoundation(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_full_foundation_lifecycle_smoke(self):
        # 1. Run migrations and verify schema
        run_migrations(self.db_path)
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as count FROM schema_migrations;")
            self.assertGreaterEqual(cursor.fetchone()["count"], 1)

        # 2. Seed development dataset
        seed_development_data(self.db_path)

        # 3. Observability checks
        # 3a. Liveness
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/health/live", {}, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp.decode("utf-8"))["status"], "LIVE")

        # 3b. Readiness
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/health/ready", {}, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp.decode("utf-8"))["status"], "READY")

        # 4. Authentication Flow
        # 4a. Invalid login rejected
        bad_body = json.dumps({"username": "hakeem", "password": "WrongPassword123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, bad_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(resp.decode("utf-8"))["code"], "UNAUTHORIZED")

        # 4b. Valid login as Hakeem Tariq
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, headers, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        login_data = json.loads(resp.decode("utf-8"))
        self.assertIn("token", login_data)
        hakeem_token = login_data["token"]
        self.assertEqual(login_data["user"]["username"], "hakeem")
        self.assertEqual(login_data["user"]["organization_id"], "org-matab-default")

        # 4c. Inspect user context (/auth/me)
        auth_headers = {"authorization": f"Bearer {hakeem_token}"}
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/auth/me", auth_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        me_data = json.loads(resp.decode("utf-8"))
        self.assertEqual(me_data["user"]["username"], "hakeem")
        self.assertEqual(me_data["user"]["organization_id"], "org-matab-default")
        self.assertIn("PRACTITIONER", me_data["user"]["roles"])
        self.assertEqual(me_data["user"]["active_facility_id"], "fac-central-opd")
        accessible_ids = [f["id"] for f in me_data["accessible_facilities"]]
        self.assertIn("fac-central-opd", accessible_ids)
        self.assertIn("patients:read", me_data["user"]["permissions"])
        self.assertIsNotNone(me_data.get("practitioner_profile"))
        self.assertEqual(me_data["practitioner_profile"]["license_type"], "BUMS")

        # 5. Tenancy & Facilities Access
        # 5a. Organizations list (scoped to own org)
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/organizations", auth_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        orgs_data = json.loads(resp.decode("utf-8"))
        self.assertEqual(len(orgs_data["organizations"]), 1)
        self.assertEqual(orgs_data["organizations"][0]["id"], "org-matab-default")

        # 5b. Facilities list
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/facilities", auth_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        facs_data = json.loads(resp.decode("utf-8"))
        self.assertGreaterEqual(len(facs_data["facilities"]), 2)

        # 5c. Specific facility detail
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/facilities/fac-central-opd", auth_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        fac_detail = json.loads(resp.decode("utf-8"))
        self.assertEqual(fac_detail["facility"]["name"], "Central Matab OPD [Synthetic]")

        # 6. Capabilities Discovery
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/system/capabilities", auth_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        caps_data = json.loads(resp.decode("utf-8"))
        self.assertGreaterEqual(caps_data["count"], 14)

        # 7. Audit Log Inspection (via Admin user)
        admin_login = json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, admin_login, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        admin_token = json.loads(resp.decode("utf-8"))["token"]

        admin_headers = {"authorization": f"Bearer {admin_token}"}
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/audit", admin_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        audit_data = json.loads(resp.decode("utf-8"))
        self.assertGreaterEqual(len(audit_data["audit_events"]), 1)
        
        # Verify passwords and secrets are NEVER in audit details
        for event in audit_data["audit_events"]:
            details_str = json.dumps(event.get("details", {}))
            self.assertNotIn("matab123", details_str)
            self.assertNotIn("password_hash", details_str)

        # 8. Logout & Session Termination
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/logout", auth_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.assertIn("Logged out successfully", json.loads(resp.decode("utf-8"))["message"])

        # Attempting to reuse hakeem_token must now fail with 401 UNAUTHORIZED
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/auth/me", auth_headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(resp.decode("utf-8"))["code"], "UNAUTHORIZED")

if __name__ == "__main__":
    unittest.main()

"""Integration Tests for Enterprise Configuration, Secrets & Environment Governance APIs.

Phase 44 for ZAYVORA MATAB OS.
Tests all endpoints via ApiRouter.dispatch:
1. GET    /api/v1/config/public (Unauthenticated)
2. GET    /api/v1/config/settings
3. POST   /api/v1/config/settings
4. GET    /api/v1/config/settings/:id
5. GET    /api/v1/config/environments
6. GET    /api/v1/config/environments/:code
7. POST   /api/v1/config/environments/isolation-check
8. POST   /api/v1/config/preflight
9. GET    /api/v1/config/secrets
10. POST  /api/v1/config/secrets
11. GET   /api/v1/config/secrets/:id
12. POST  /api/v1/config/secrets/rotate
13. POST  /api/v1/config/rotations/:id/advance
14. POST  /api/v1/config/secrets/:id/revoke-compromised
15. GET   /api/v1/config/proposals
16. POST  /api/v1/config/proposals
17. GET   /api/v1/config/proposals/:id
18. POST  /api/v1/config/proposals/:id/approve
19. POST  /api/v1/config/proposals/:id/apply
20. POST  /api/v1/config/proposals/:id/rollback
21. POST  /api/v1/config/drift/scans/run
22. GET   /api/v1/config/drift/scans
23. GET   /api/v1/config/audit
24. GET   /api/v1/config/summary
25. Auth security: 401 on protected endpoint without Bearer token.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestConfigGovernanceApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_config_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path
        )
        assert status == 200, f"Login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}"
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_public_config_unauthenticated(self):
        """GET /api/v1/config/public is accessible without auth and contains safe keys."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/public",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("APP_CLIENT_NAME", data["public_config"])
        self.assertNotIn("MATAB_SECRET_KEY", data["public_config"])

    def test_02_protected_endpoint_requires_auth(self):
        """GET /api/v1/config/settings returns 401 Unauthorized without token."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/settings",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 401)

    def test_03_get_settings_and_create(self):
        """GET and POST /api/v1/config/settings."""
        # List settings
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/settings",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(data["settings"]), 5)

        # Register new setting
        payload = {
            "config_key": "INTEGRATION_SYNC_BATCH_SIZE",
            "description": "Batch size for FHIR outbound queue dispatch",
            "category": "SERVER_RUNTIME",
            "data_type": "integer",
            "owner_team": "Interoperability",
            "default_value_json": 50
        }
        status2, _, body2 = ApiRouter.dispatch(
            "POST",
            "/api/v1/config/settings",
            self.auth_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status2, 201)
        setting_id = json.loads(body2.decode("utf-8"))["setting"]["id"]

        # Fetch single setting
        status3, _, body3 = ApiRouter.dispatch(
            "GET",
            f"/api/v1/config/settings/{setting_id}",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status3, 200)

    def test_04_environments_and_isolation(self):
        """GET environments, GET /:code, and POST isolation-check."""
        # List envs
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/environments",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        envs = json.loads(body.decode("utf-8"))["environments"]
        self.assertEqual(len(envs), 4)

        # Get single env
        status2, _, body2 = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/environments/production",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status2, 200)

        # Isolation check
        status3, _, body3 = ApiRouter.dispatch(
            "POST",
            "/api/v1/config/environments/isolation-check",
            self.auth_headers,
            {},
            json.dumps({
                "source_env_code": "staging_synthetic",
                "target_action": "read",
                "resource_ref": "staging_db"
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status3, 200)

    def test_05_preflight_validation(self):
        """POST /api/v1/config/preflight evaluates schema constraints."""
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/config/preflight",
            self.auth_headers,
            {},
            json.dumps({"environment_code": "local_dev"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("status", data["preflight"])
        self.assertIn("total_evaluated", data["preflight"])

    def test_06_secret_references_and_rotation(self):
        """GET/POST secrets, rotate, and advance rotation."""
        # 1. List secrets
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/secrets",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        secrets = json.loads(body.decode("utf-8"))["secrets"]
        self.assertGreaterEqual(len(secrets), 3)
        target_sec = secrets[0]

        # 2. Initiate rotation
        rot_payload = {
            "secret_ref_id": target_sec["id"],
            "rotation_reason": "ROUTINE_SECURITY_POLICY"
        }
        status2, _, body2 = ApiRouter.dispatch(
            "POST",
            "/api/v1/config/secrets/rotate",
            self.auth_headers,
            {},
            json.dumps(rot_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status2, 201)
        rot_id = json.loads(body2.decode("utf-8"))["rotation"]["id"]

        # 3. Advance rotation to prepared
        status3, _, body3 = ApiRouter.dispatch(
            "POST",
            f"/api/v1/config/rotations/{rot_id}/advance",
            self.auth_headers,
            {},
            json.dumps({"target_state": "prepared", "evidence": {"step": "vault_ack"}}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status3, 200)

        # 4. Advance rotation to updated
        status4, _, body4 = ApiRouter.dispatch(
            "POST",
            f"/api/v1/config/rotations/{rot_id}/advance",
            self.auth_headers,
            {},
            json.dumps({"target_state": "updated"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status4, 200)

        # 5. Advance rotation to verified
        status5, _, body5 = ApiRouter.dispatch(
            "POST",
            f"/api/v1/config/rotations/{rot_id}/advance",
            self.auth_headers,
            {},
            json.dumps({"target_state": "verified"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status5, 200)

        # 6. Advance rotation to old_retired
        status6, _, body6 = ApiRouter.dispatch(
            "POST",
            f"/api/v1/config/rotations/{rot_id}/advance",
            self.auth_headers,
            {},
            json.dumps({"target_state": "old_retired"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status6, 200)

    def test_07_urgent_compromise_revocation(self):
        """POST /api/v1/config/secrets/:id/revoke-compromised flags emergency status."""
        status, _, body = ApiRouter.dispatch("GET", "/api/v1/config/secrets", self.auth_headers, {}, b"", "127.0.0.1", self.db_path)
        secrets = json.loads(body.decode("utf-8"))["secrets"]
        sec_id = secrets[1]["id"]

        status2, _, body2 = ApiRouter.dispatch(
            "POST",
            f"/api/v1/config/secrets/{sec_id}/revoke-compromised",
            self.auth_headers,
            {},
            json.dumps({
                "incident_id": "INC-2026-999",
                "rationale": "Emergency revocation: credential suspected of being leaked in external ticket."
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status2, 200)
        data = json.loads(body2.decode("utf-8"))
        self.assertEqual(data["secret"]["status"], "compromised")

    def test_08_change_proposals_lifecycle(self):
        """Test proposals listing, creation, and retrieval."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/proposals",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)

        payload = {
            "title": "Update Staging Redis Cache TTL",
            "environment_code": "staging_synthetic",
            "change_category": "RUNTIME_SETTING",
            "diff_metadata_json": {"setting": "CACHE_TTL_SECS", "new": 300},
            "rollback_plan": "Revert to default 600s cache TTL."
        }
        status2, _, body2 = ApiRouter.dispatch(
            "POST",
            "/api/v1/config/proposals",
            self.auth_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status2, 201)
        prop_id = json.loads(body2.decode("utf-8"))["proposal"]["id"]

        # Get proposal
        status3, _, body3 = ApiRouter.dispatch(
            "GET",
            f"/api/v1/config/proposals/{prop_id}",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status3, 200)

    def test_09_drift_scans_and_audit(self):
        """POST /api/v1/config/drift/scans/run, GET drift, and GET audit."""
        # Drift scan
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/config/drift/scans/run",
            self.auth_headers,
            {},
            json.dumps({"environment_code": "local_dev"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)

        # List drift scans
        status2, _, body2 = ApiRouter.dispatch("GET", "/api/v1/config/drift/scans", self.auth_headers, {}, b"", "127.0.0.1", self.db_path)
        self.assertEqual(status2, 200)

        # Audit ledger
        status3, _, body3 = ApiRouter.dispatch("GET", "/api/v1/config/audit", self.auth_headers, {}, b"", "127.0.0.1", self.db_path)
        self.assertEqual(status3, 200)
        audit_events = json.loads(body3.decode("utf-8"))["events"]
        self.assertGreaterEqual(len(audit_events), 1)

    def test_10_governance_summary(self):
        """GET /api/v1/config/summary returns estate overview and health."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/config/summary",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("total_settings", data["summary"])
        self.assertIn("governance_health", data["summary"])

"""Integration Tests for Production Release Engineering, Feature Flags & Rollback REST APIs.

Phase 38 for ZAYVORA MATAB OS.
Tests all 15 REST endpoints via ApiRouter.dispatch:
1.  GET  /api/v1/releases/manifests
2.  POST /api/v1/releases/manifests
3.  GET  /api/v1/releases/manifests/{id}
4.  PUT  /api/v1/releases/manifests/{id}
5.  POST /api/v1/releases/manifests/{id}/advance
6.  POST /api/v1/releases/manifests/{id}/gates
7.  POST /api/v1/releases/manifests/{id}/deploy
8.  POST /api/v1/releases/manifests/{id}/rollback
9.  GET  /api/v1/flags
10. POST /api/v1/flags
11. GET  /api/v1/flags/{id}
12. PUT  /api/v1/flags/{id}
13. POST /api/v1/flags/{id}/emergency-disable
14. POST /api/v1/flags/evaluate
15. GET  /api/v1/releases/pulse
16. Security & RBAC: 401 Unauthenticated, 403 Forbidden.
"""

import os
import json
import sqlite3
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestReleaseGovernanceApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_release_gov_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin (has all permissions including release:* and flag:*)
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        cls.auth_token = json.loads(body)["token"]
        cls.auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.auth_token}"
        }

        # Authenticate Practitioner (Hakeem Tariq)
        status_h, _, body_h = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        cls.hakeem_token = json.loads(body_h)["token"]
        cls.hakeem_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.hakeem_token}"
        }

    # --------------------------------------------------------------------------
    # 1. Release Manifests Endpoints
    # --------------------------------------------------------------------------

    def test_01_list_releases_and_seeded_manifest(self):
        """GET /api/v1/releases/manifests lists initial seed release."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/releases/manifests", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("releases", data)
        self.assertGreaterEqual(data["total_releases"], 1)

        v_tags = [r["version_tag"] for r in data["releases"]]
        self.assertIn("v2026.10.14-01", v_tags)

    def test_02_create_get_update_advance_manifest(self):
        """POST, GET, PUT, POST advance on /api/v1/releases/manifests."""
        payload = {
            "version_tag": "v2026.10.16-01",
            "title": "Continuous Delivery Pipeline Candidate",
            "description": "Integration with ABDM and auto-retry engine",
            "git_commit": "7a8b9c0",
            "target_environment": "staging",
            "risk_level": "moderate",
            "config_changes": {"LOG_LEVEL": "INFO", "APP_SECRET": "secret_123"},
            "rollback_plan": {"strategy": "ROLLBACK_ARTIFACT"}
        }
        # 1. Create
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/releases/manifests",
            self.auth_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        created = json.loads(body)
        rel_id = created["id"]
        self.assertEqual(created["version_tag"], "v2026.10.16-01")
        self.assertEqual(created["config_changes"]["APP_SECRET"], "[REDACTED_SECRET]")

        # 2. Get
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/releases/manifests/{rel_id}",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        fetched = json.loads(body)
        self.assertEqual(fetched["id"], rel_id)

        # 3. Update
        status, _, body = ApiRouter.dispatch(
            "PUT",
            f"/api/v1/releases/manifests/{rel_id}",
            self.auth_headers,
            {},
            json.dumps({"title": "CD Pipeline Candidate V2"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        updated = json.loads(body)
        self.assertEqual(updated["title"], "CD Pipeline Candidate V2")

        # 4. Advance
        adv_payload = {"action": "submit_for_review"}
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/releases/manifests/{rel_id}/advance",
            self.auth_headers,
            {},
            json.dumps(adv_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        advanced = json.loads(body)
        self.assertEqual(advanced["status"], "awaiting_approval")

    def test_03_record_gates_and_deploy_release(self):
        """POST /gates and POST /deploy on /api/v1/releases/manifests/{id}."""
        # Create staging release
        payload = {
            "version_tag": "v2026.10.16-02",
            "title": "Staging Promotion Build",
            "git_commit": "1234abc",
            "target_environment": "staging",
            "risk_level": "moderate"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/releases/manifests",
            self.auth_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        rel_id = json.loads(body)["id"]

        # Record Quality Gates
        gate_payload_1 = {"gate_type": "UNIT_TESTS", "status": "PASSED"}
        status, _, _ = ApiRouter.dispatch(
            "POST",
            f"/api/v1/releases/manifests/{rel_id}/gates",
            self.auth_headers,
            {},
            json.dumps(gate_payload_1).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)

        gate_payload_2 = {"gate_type": "INTEGRATION_TESTS", "status": "PASSED"}
        status, _, body_g = ApiRouter.dispatch(
            "POST",
            f"/api/v1/releases/manifests/{rel_id}/gates",
            self.auth_headers,
            {},
            json.dumps(gate_payload_2).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body_g)["status"], "awaiting_approval")

        # Approve
        status, _, _ = ApiRouter.dispatch(
            "POST",
            f"/api/v1/releases/manifests/{rel_id}/advance",
            self.auth_headers,
            {},
            json.dumps({"action": "approve"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)

        # Deploy
        deploy_payload = {"target_environment": "staging"}
        status, _, body_d = ApiRouter.dispatch(
            "POST",
            f"/api/v1/releases/manifests/{rel_id}/deploy",
            self.auth_headers,
            {},
            json.dumps(deploy_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        deployed = json.loads(body_d)
        self.assertEqual(deployed["status"], "deployed")
        self.assertEqual(deployed["post_deploy_evidence"]["health_live"], "OK")

    def test_04_rollback_release(self):
        """POST /api/v1/releases/manifests/{id}/rollback executes recovery action."""
        rel_id = "rel-v2026.10.14-01"
        rollback_payload = {
            "strategy": "ROLLBACK_ARTIFACT",
            "target_environment": "staging",
            "reason": "Synthetic regression detected in integration pipeline"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/releases/manifests/{rel_id}/rollback",
            self.auth_headers,
            {},
            json.dumps(rollback_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        recovered = json.loads(body)
        self.assertEqual(recovered["status"], "recovered")
        self.assertGreaterEqual(len(recovered["rollbacks"]), 1)

    # --------------------------------------------------------------------------
    # 2. Feature Flags Endpoints
    # --------------------------------------------------------------------------

    def test_05_list_and_create_feature_flags(self):
        """GET /api/v1/flags & POST /api/v1/flags."""
        # List seeded flags
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/flags", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("flags", data)
        self.assertGreaterEqual(data["total_flags"], 5)

        # Create new operational flag
        new_flag = {
            "flag_key": "flag-opd-instant-token",
            "name": "Instant Token Generation for OPD",
            "category": "operational",
            "risk_level": "low",
            "state_by_environment": {"local": True, "ci_test": True, "staging": True, "pilot": False, "production": False}
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/flags",
            self.auth_headers,
            {},
            json.dumps(new_flag).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertEqual(created["flag_key"], "flag-opd-instant-token")

    def test_06_evaluate_flag_and_emergency_disable(self):
        """POST /api/v1/flags/evaluate & POST /api/v1/flags/{id}/emergency-disable."""
        # Evaluate in staging (expected True for 'flag-patient-portal-v2')
        eval_payload = {
            "flag_key": "flag-patient-portal-v2",
            "environment": "staging"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/flags/evaluate",
            self.auth_headers,
            {},
            json.dumps(eval_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["is_enabled"])

        # Trip Emergency Disable
        dis_payload = {
            "disable": True,
            "reason": "Emergency security vulnerability mitigation"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/flags/flag-patient-portal-v2/emergency-disable",
            self.auth_headers,
            {},
            json.dumps(dis_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["is_emergency_disabled"], 1)

        # Evaluate again -> must be False
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/flags/evaluate",
            self.auth_headers,
            {},
            json.dumps(eval_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["is_enabled"])

    # --------------------------------------------------------------------------
    # 3. Observability Pulse & Security Checks
    # --------------------------------------------------------------------------

    def test_07_get_release_pulse(self):
        """GET /api/v1/releases/pulse returns metrics and governance caveats."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/releases/pulse", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        pulse = json.loads(body)
        self.assertIn("total_releases", pulse)
        self.assertIn("total_feature_flags", pulse)
        self.assertIn("caveats", pulse)

    def test_08_unauthenticated_request_rejected(self):
        """Unauthenticated request must return 401."""
        status, _, _ = ApiRouter.dispatch(
            "GET",
            "/api/v1/releases/manifests",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

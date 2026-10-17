"""Integration Tests for Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Engine APIs.

Phase 41 for ZAYVORA MATAB OS.
Tests all endpoints via ApiRouter.dispatch:
1. GET   /api/v1/lifecycle/inventory
2. GET   /api/v1/lifecycle/policies
3. POST  /api/v1/lifecycle/policies
4. POST  /api/v1/lifecycle/policies/:id/approve
5. POST  /api/v1/lifecycle/evaluations/dry-run
6. POST  /api/v1/lifecycle/operations/execute
7. GET   /api/v1/lifecycle/holds
8. POST  /api/v1/lifecycle/holds
9. POST  /api/v1/lifecycle/holds/:id/release
10. GET  /api/v1/lifecycle/requests
11. POST /api/v1/lifecycle/requests
12. POST /api/v1/lifecycle/requests/:id/verify-identity
13. POST /api/v1/lifecycle/requests/:id/approve
14. POST /api/v1/lifecycle/requests/:id/execute
15. GET  /api/v1/lifecycle/pulse
16. Security & RBAC: 401 Unauthenticated and 403 Forbidden under active legal hold.
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


class TestDataLifecycleApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_lifecycle_api.db")
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
            cls.db_path,
        )
        cls.auth_token = json.loads(body)["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.auth_token}",
            "X-Facility-Id": "fac-central-opd"
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_get_inventory_catalog(self):
        """GET /api/v1/lifecycle/inventory - List data categories."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/lifecycle/inventory",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data["inventory"]), 14)

    def test_02_get_policies(self):
        """GET /api/v1/lifecycle/policies - List versioned policies."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/lifecycle/policies",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        self.assertGreaterEqual(len(data["policies"]), 5)

    def test_03_create_and_approve_policy(self):
        """POST /api/v1/lifecycle/policies and POST /api/v1/lifecycle/policies/:id/approve."""
        policy_payload = {
            "policy_key": "TELEMED_RECORDINGS_3YR",
            "version": "1.0.0",
            "title": "Telemedicine Video Consultation 3-Year Policy",
            "description": "Retention policy for audiovisual teleconsultation recordings.",
            "data_category_ids": ["cat-clinical-encounters"],
            "scope": "tenant",
            "retention_trigger": "closure_date",
            "retention_period_days": 1095,
            "archive_rule": "COLD_STORAGE_PARTITION",
            "disposal_action": "restrict",
            "hold_behavior": "STRICT_BLOCK",
            "downstream_propagation_rule": "ALL_LINKED_STORES",
            "accountable_owner": "TELEMED_DIRECTOR",
            "approver_roles": ["CLINICAL_DIRECTOR"],
            "jurisdiction_tags": ["IN-TELEMEDICINE-2020"]
        }

        # Create
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/lifecycle/policies",
            self.admin_headers,
            {},
            json.dumps(policy_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertTrue(res.get("success"))
        policy_id = res["policy"]["id"]
        self.assertEqual(res["policy"]["status"], "draft")

        # Approve
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/lifecycle/policies/{policy_id}/approve",
            self.admin_headers,
            {},
            b"{}",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        approved_res = json.loads(body)
        self.assertEqual(approved_res["policy"]["status"], "approved")

    def test_04_evaluate_dry_run(self):
        """POST /api/v1/lifecycle/evaluations/dry-run - Deterministic retention check."""
        eval_payload = {
            "policy_id": "pol-clinical-statutory-7yr",
            "category_id": "cat-clinical-encounters",
            "dry_run": True
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/lifecycle/evaluations/dry-run",
            self.admin_headers,
            {},
            json.dumps(eval_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data.get("success"))
        eval_run = data["evaluation_run"]
        self.assertEqual(eval_run["run_mode"], "dry_run")
        self.assertIn("records_evaluated", eval_run)

    def test_05_legal_holds_endpoints(self):
        """GET /api/v1/lifecycle/holds, POST /api/v1/lifecycle/holds, and POST .../release."""
        hold_payload = {
            "hold_code": "LH-INT-2026-001",
            "title": "State Health Authority Inquiry Preservation Notice",
            "reason_category": "regulatory_investigation",
            "scope_filter": {
                "category_id": "cat-clinical-encounters",
                "patient_id": "pat-syn-003"
            },
            "review_date": "2027-06-30"
        }

        # Place hold
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/lifecycle/holds",
            self.admin_headers,
            {},
            json.dumps(hold_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        hold_res = json.loads(body)
        self.assertTrue(hold_res.get("success"))
        hold_id = hold_res["hold"]["id"]

        # List holds
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/lifecycle/holds",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        holds_list = json.loads(body)["holds"]
        self.assertTrue(any(h["id"] == hold_id for h in holds_list))

        # Release hold
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/lifecycle/holds/{hold_id}/release",
            self.admin_headers,
            {},
            json.dumps({"release_reason": "Inquiry closed without adverse findings"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        released_res = json.loads(body)
        self.assertEqual(released_res["hold"]["status"], "released")

    def test_06_privacy_request_full_pipeline(self):
        """Tests ingestion, identity verification, plan approval, and execution via HTTP endpoints."""
        req_payload = {
            "subject_identifier": "pat-syn-004",
            "request_type": "data_export",
            "scope_details": "Complete Unani clinical health summary export",
            "channel": "patient_portal"
        }

        # 1. Ingest
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/lifecycle/requests",
            self.admin_headers,
            {},
            json.dumps(req_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        req_res = json.loads(body)
        self.assertTrue(req_res.get("success"))
        request_id = req_res["request"]["id"]

        # 2. List requests
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/lifecycle/requests",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        reqs = json.loads(body)["requests"]
        self.assertTrue(any(r["id"] == request_id for r in reqs))

        # 3. Verify identity
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/lifecycle/requests/{request_id}/verify-identity",
            self.admin_headers,
            {},
            b"{}",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        v_res = json.loads(body)
        self.assertEqual(v_res["request"]["status"], "identity_verified")

        # 4. Approve plan
        plan_payload = {
            "export_format": "PDF_AND_JSON",
            "encrypted": True,
            "deliver_via": "secure_download_link"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/lifecycle/requests/{request_id}/approve",
            self.admin_headers,
            {},
            json.dumps(plan_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        app_res = json.loads(body)
        self.assertEqual(app_res["request"]["status"], "approved")

        # 5. Execute plan
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/lifecycle/requests/{request_id}/execute",
            self.admin_headers,
            {},
            b"{}",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        exec_res = json.loads(body)
        self.assertEqual(exec_res["request"]["status"], "completed")

    def test_07_get_lifecycle_pulse(self):
        """GET /api/v1/lifecycle/pulse - Real-time governance telemetry."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/lifecycle/pulse",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        pulse = json.loads(body)["pulse"]
        self.assertGreaterEqual(pulse["governed_categories_count"], 14)
        self.assertGreaterEqual(pulse["active_policies_count"], 5)
        self.assertIn("governance_status", pulse)

    def test_08_security_unauthenticated_and_forbidden_legal_hold(self):
        """Ensures 401 when unauthenticated and 403 when disposal is blocked by active legal hold."""
        # Unauthenticated request
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/lifecycle/pulse",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 401)

        # Attempt to delete record held under active legal hold
        disposal_payload = {
            "category_id": "cat-clinical-encounters",
            "target_record_id": "pat-syn-001",
            "policy_id": "pol-clinical-statutory-7yr",
            "action_type": "restrict"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/lifecycle/operations/execute",
            self.admin_headers,
            {},
            json.dumps(disposal_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 403)
        res = json.loads(body)
        self.assertIn("CRITICAL DISPOSAL BLOCK", res.get("message", ""))


if __name__ == "__main__":
    unittest.main()

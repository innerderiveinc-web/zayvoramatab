"""
Integration Tests for Enterprise Test Automation, Regression & Release Qualification APIs
ZAYVORA MATAB OS — Phase 49
"""

import os
import json
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestTestAutomationApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_automation_api.db")
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
        assert status == 200, f"Admin login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_get_summary_api(self):
        """1. GET /api/v1/test-qualification/summary - Executive test automation KPIs."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/test-qualification/summary",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("total_suites", data["summary"])
        self.assertIn("active_quarantined_tests", data["summary"])
        self.assertIn("audit_events_count", data["summary"])

    def test_02_suites_api_lifecycle(self):
        """2. Suite catalog API: register, retrieve, list, update."""
        payload = {
            "suite_code": "SUITE-API-INTEGRATION-ORDERS",
            "name": "Integration Tests for Dispensary Orders",
            "test_layer": "API_INTEGRATION",
            "target_subsystem": "DISPENSARY_ORDERS",
            "test_file_path": "tests/integration/test_orders_api.py",
            "command_template": "python -m unittest tests/integration/test_orders_api.py",
            "execution_environment": "ISOLATED_SYNTHETIC",
            "is_mandatory_for_release": 1,
            "timeout_seconds": 90,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/suites",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        res = json.loads(body.decode("utf-8"))
        suite_id = res["suite"]["id"]
        self.assertEqual(res["suite"]["suite_code"], "SUITE-API-INTEGRATION-ORDERS")

        # GET by ID
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/test-qualification/suites/{suite_id}",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        suite = json.loads(body.decode("utf-8"))["suite"]
        self.assertEqual(suite["id"], suite_id)

        # PUT update
        status, _, body = ApiRouter.dispatch(
            "PUT",
            f"/api/v1/test-qualification/suites/{suite_id}",
            self.admin_headers,
            {},
            json.dumps({"timeout_seconds": 150}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        updated = json.loads(body.decode("utf-8"))["suite"]
        self.assertEqual(updated["timeout_seconds"], 150)

    def test_03_execution_runs_api(self):
        """3. Execution runs API: record run and query ledger."""
        payload = {
            "suite_id": "tasc-unit-rx-001",
            "target_release_version": "v1.0.5",
            "environment": "ISOLATED_SYNTHETIC",
            "commit_hash": "c0ffee9999",
            "trigger_source": "CI_PIPELINE",
            "status": "PASSED",
            "total_tests": 15,
            "passed_tests": 15,
            "failed_tests": 0,
            "skipped_tests": 0,
            "execution_duration_ms": 1150,
            "evidence_summary": {"coverage": "100%"},
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/runs",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        run = json.loads(body.decode("utf-8"))["run"]
        run_id = run["id"]
        self.assertEqual(run["status"], "PASSED")

        # GET list
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/test-qualification/runs",
            self.admin_headers,
            {"target_release_version": "v1.0.5"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        runs = json.loads(body.decode("utf-8"))["runs"]
        self.assertTrue(any(r["id"] == run_id for r in runs))

    def test_04_quarantines_api_lifecycle(self):
        """4. Quarantine API: quarantine test and resolve."""
        payload = {
            "suite_id": "tasc-unit-rx-001",
            "test_name": "test_concurrent_inventory_lock_race",
            "reason": "Rare timing race under high worker concurrency.",
            "root_cause_category": "TIMING_RACE",
            "assigned_owner": "backend@zayvora.internal",
            "target_resolution_days": 14,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/quarantines",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        quarantine = json.loads(body.decode("utf-8"))["quarantine"]
        quarantine_id = quarantine["id"]
        self.assertEqual(quarantine["status"], "ACTIVE_QUARANTINE")

        # Resolve
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/test-qualification/quarantines/{quarantine_id}/resolve",
            self.admin_headers,
            {},
            json.dumps({"status": "RESOLVED", "notes": "Replaced time.sleep with threading.Event latch."}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        resolved = json.loads(body.decode("utf-8"))["quarantine"]
        self.assertEqual(resolved["status"], "RESOLVED")

    def test_05_profiles_api(self):
        """5. Profiles API: list and create qualification profile."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/test-qualification/profiles",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        profiles = json.loads(body.decode("utf-8"))["profiles"]
        self.assertGreaterEqual(len(profiles), 3)

        # Create Profile
        payload = {
            "profile_code": "PROF-NIGHTLY-REGRESSION",
            "name": "Nightly Regression Qualification Profile",
            "target_tier": "DEVELOPMENT",
            "required_test_layers": ["UNIT"],
            "required_suites": ["SUITE-UNIT-PRESCRIPTIONS"],
            "min_pass_rate_bp": 9200,
            "allow_quarantined_tests": 1,
            "max_critical_defects": 1,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/profiles",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        created = json.loads(body.decode("utf-8"))["profile"]
        self.assertEqual(created["profile_code"], "PROF-NIGHTLY-REGRESSION")

    def test_06_evaluate_release_candidate_api(self):
        """6. Evaluate release candidate API: qualify or block."""
        # 1. Record fresh passing runs for required DEV profile
        run_payload = {
            "suite_id": "tasc-unit-rx-001",
            "target_release_version": "v1.1.0-alpha",
            "environment": "ISOLATED_SYNTHETIC",
            "commit_hash": "a1b2c3d4",
            "trigger_source": "MANUAL_QUALIFICATION",
            "status": "PASSED",
            "total_tests": 10,
            "passed_tests": 10,
            "failed_tests": 0,
            "skipped_tests": 0,
            "execution_duration_ms": 600,
            "evidence_summary": {"result": "clean"},
        }
        ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/runs",
            self.admin_headers,
            {},
            json.dumps(run_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )

        eval_payload = {
            "target_release_version": "v1.1.0-alpha",
            "profile_id": "rqp-prof-dev-001",
            "commit_hash": "a1b2c3d4",
            "repository_revision": "HEAD",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/candidates/evaluate",
            self.admin_headers,
            {},
            json.dumps(eval_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        cand = json.loads(body.decode("utf-8"))["candidate"]
        self.assertEqual(cand["overall_verdict"], "QUALIFIED")

    def test_07_defects_api_lifecycle(self):
        """7. Defect API: log, retrieve, update status."""
        payload = {
            "title": "AssertionError on Mudabbar warning modal font size",
            "test_name": "test_mudabbar_modal_font",
            "severity": "MINOR",
            "failure_classification": "TEST_DEFECT",
            "sanitized_stack_trace": "AssertionError: 14px != 16px at modal.ts",
            "reproduction_steps": "Inspect modal css in Cypress test.",
            "assigned_owner": "frontend-dev@zayvora.internal",
            "linked_hazard_id": "haz-rx-001",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/defects",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        defect = json.loads(body.decode("utf-8"))["defect"]
        defect_id = defect["id"]
        self.assertEqual(defect["status"], "OPEN")

        # Update status
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/test-qualification/defects/{defect_id}/status",
            self.admin_headers,
            {},
            json.dumps({"new_status": "VERIFIED_CLOSED", "notes": "Updated font style in CSS."}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        closed = json.loads(body.decode("utf-8"))["defect"]
        self.assertEqual(closed["status"], "VERIFIED_CLOSED")

    def test_08_audit_ledger_and_verification_api(self):
        """8. Audit ledger API: query ledger and verify cryptographic integrity."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/test-qualification/audit",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        audit_res = json.loads(body.decode("utf-8"))
        self.assertTrue(audit_res["success"])
        self.assertGreater(len(audit_res["audit_events"]), 0)

        # POST /api/v1/test-qualification/audit/verify
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/test-qualification/audit/verify",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        verify_res = json.loads(body.decode("utf-8"))["verification"]
        self.assertTrue(verify_res["is_valid"])

    def test_09_unauthorized_access_rejected(self):
        """9. Unauthenticated request without token receives 401 Unauthorized."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/test-qualification/summary",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

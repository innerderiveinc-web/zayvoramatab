"""
Integration Tests for Enterprise Security Posture & Vulnerability Governance APIs
ZAYVORA MATAB OS — Phase 46
"""

import os
import json
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestSecurityPostureApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sec_api.db")
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
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}"
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_security_summary_api(self):
        """GET /api/v1/security-posture/summary returns executive metrics."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/security-posture/summary", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("summary", data)
        self.assertGreaterEqual(data["summary"]["total_assets"], 6)
        self.assertGreaterEqual(data["summary"]["total_controls"], 5)

    def test_02_assets_inventory_api(self):
        """GET and POST /api/v1/security-posture/assets."""
        # List assets
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/security-posture/assets", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(data["count"], 6)

        # Register new asset
        new_asset_payload = {
            "asset_name": "ABDM M1 M2 M3 Interop Gateway",
            "asset_category": "INTEGRATIONS",
            "environment": "PRODUCTION",
            "owner_role": "Interoperability Lead",
            "data_sensitivity": "RESTRICTED_PHI",
            "entry_points_summary": "HTTP ABDM webhook receivers",
            "critical_clinical_function": "National health record exchange",
            "scan_coverage_status": "COVERED"
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/assets", self.admin_headers, {},
            json.dumps(new_asset_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        created = json.loads(body.decode("utf-8"))["asset"]
        self.assertEqual(created["asset_name"], "ABDM M1 M2 M3 Interop Gateway")

    def test_03_controls_registry_api(self):
        """GET /api/v1/security-posture/controls."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/security-posture/controls", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(data["count"], 5)
        codes = [c["control_code"] for c in data["controls"]]
        self.assertIn("SEC-SCA-001", codes)
        self.assertIn("SEC-SECRET-001", codes)
        self.assertIn("SEC-AUTHZ-001", codes)

    def test_04_execute_individual_scans_api(self):
        """POST to individual scanner endpoints: SCA, secrets, authz, container, sql-param."""
        # SCA
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/scans/sca", self.admin_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["scan_result"]["control_code"], "SEC-SCA-001")

        # Secrets
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/scans/secrets", self.admin_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["scan_result"]["control_code"], "SEC-SECRET-001")

        # API Authz
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/scans/api-authz", self.admin_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["scan_result"]["control_code"], "SEC-AUTHZ-001")

        # Container
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/scans/container", self.admin_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["scan_result"]["control_code"], "SEC-CONT-001")

        # SQL Parameterization
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/scans/sql-param", self.admin_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["scan_result"]["control_code"], "SEC-SQLI-001")

    def test_05_execute_all_scans_api(self):
        """POST /api/v1/security-posture/scans/run-all executes the full verification suite."""
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/scans/run-all", self.admin_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("scan_result", data)
        self.assertEqual(len(data["scan_result"]["controls_executed"]), 5)

    def test_06_findings_management_and_transitions_api(self):
        """POST, GET, and transition vulnerability findings."""
        # Create finding
        finding_payload = {
            "title": "Permissive Wildcard CORS Configuration on Public Route",
            "affected_component": "apps/api/router.py",
            "vulnerability_category": "INSECURE_CONFIGURATION",
            "source_severity": "MEDIUM",
            "exposure_context": "INTERNET_FACING",
            "clinical_impact": "NO_CLINICAL_IMPACT",
            "evidence_summary": "Access-Control-Allow-Origin header set to wildcard * instead of explicit origin.",
            "remediation_plan": "Restrict CORS origin to authorized clinic domain."
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/findings", self.admin_headers, {},
            json.dumps(finding_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        created = json.loads(body.decode("utf-8"))["finding"]
        fid = created["id"]
        self.assertEqual(created["status"], "NEW")
        self.assertEqual(created["organizational_priority"], "P2_MEDIUM")

        # Get finding
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/security-posture/findings/{fid}", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

        # Transition NEW -> TRIAGED
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/security-posture/findings/{fid}/transition", self.admin_headers, {},
            json.dumps({"target_status": "TRIAGED", "notes": "Triaged by security team"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["finding"]["status"], "TRIAGED")

    def test_07_exceptions_ledger_api(self):
        """POST and GET /api/v1/security-posture/exceptions."""
        exc_payload = {
            "scope": "apps/web/static/chart_lib.js",
            "rationale": "Third-party chart visualization bundle contains advisory for unused feature",
            "compensating_controls": "Unused feature code stripped at build; CSP blocks unauthorized script execution",
            "accountable_risk_owner": "Chief Information Security Officer",
            "days_valid": 45
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/exceptions", self.admin_headers, {},
            json.dumps(exc_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        created = json.loads(body.decode("utf-8"))["exception"]
        self.assertEqual(created["status"], "APPROVED")

        # List exceptions
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/security-posture/exceptions", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(json.loads(body.decode("utf-8"))["count"], 1)

    def test_08_release_gate_evaluation_api(self):
        """POST /api/v1/security-posture/gates/evaluate and GET /api/v1/security-posture/gates."""
        # Ensure fresh scans first
        ApiRouter.dispatch("POST", "/api/v1/security-posture/scans/run-all", self.admin_headers, {}, b"{}", "127.0.0.1", self.db_path)

        eval_payload = {
            "release_version": "v1.1.0-sec-verify",
            "target_environment": "PRODUCTION",
            "target_commit_ref": "git-sha-778899"
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/security-posture/gates/evaluate", self.admin_headers, {},
            json.dumps(eval_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        gate_data = json.loads(body.decode("utf-8"))["gate_evaluation"]
        self.assertIn("gate_outcome", gate_data)
        self.assertIn(gate_data["gate_outcome"], ["PASS", "FAIL", "BLOCKED", "STALE", "EXCEPTION_APPROVED"])

        # List gates
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/security-posture/gates", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(json.loads(body.decode("utf-8"))["count"], 1)

    def test_09_audit_ledger_api(self):
        """GET /api/v1/security-posture/audit-ledger returns tamper-evident events."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/security-posture/audit-ledger", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(data["count"], 1)
        first_event = data["audit_events"][0]
        self.assertIn("entry_hash", first_event)
        self.assertIn("event_type", first_event)

    def test_10_unauthorized_access_denied(self):
        """Unauthenticated requests must be rejected with 401."""
        status, _, _ = ApiRouter.dispatch(
            "GET", "/api/v1/security-posture/summary", {}, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

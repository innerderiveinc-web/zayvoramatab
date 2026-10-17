"""Integration Tests for Disaster Recovery, Business Continuity & Resilience Operations APIs.

Phase 40 for ZAYVORA MATAB OS.
Tests all endpoints via ApiRouter.dispatch:
1. GET   /api/v1/dr/domains
2. PATCH /api/v1/dr/domains/{id}
3. POST  /api/v1/dr/backups
4. GET   /api/v1/dr/backups
5. POST  /api/v1/dr/drills
6. GET   /api/v1/dr/drills
7. GET   /api/v1/dr/drills/{id}
8. POST  /api/v1/dr/drills/{id}/sign-off
9. GET   /api/v1/dr/runbooks
10. POST /api/v1/dr/reconciliation
11. GET  /api/v1/dr/reconciliation
12. POST /api/v1/dr/reconciliation/{id}/resolve
13. GET  /api/v1/dr/pulse
14. Security & RBAC: 401 Unauthenticated and 403 Production safeguard.
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


class TestDisasterRecoveryApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_dr_api.db")
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

    def test_01_get_domains_api(self):
        """GET /api/v1/dr/domains returns 200 with BIA criticality catalog."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/domains",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["domains"]), 12)

    def test_02_update_domain_policy_api(self):
        """PATCH /api/v1/dr/domains/:id returns 200 with updated policy."""
        payload = json.dumps({
            "approved_rto_minutes": 20,
            "approved_rpo_minutes": 8,
            "degraded_mode_policy": "Emergency cached tokens"
        }).encode("utf-8")

        status, _, body = ApiRouter.dispatch(
            "PATCH",
            "/api/v1/dr/domains/auth_identity",
            self.admin_headers,
            {},
            payload,
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["domain"]["approved_rto_minutes"], 20)
        self.assertEqual(data["domain"]["approved_rpo_minutes"], 8)

    def test_03_create_and_list_backups_api(self):
        """POST /api/v1/dr/backups creates snapshot; GET lists backups."""
        backup_dir = os.path.join(self.temp_dir, "api_backups")
        payload = json.dumps({
            "backup_type": "full",
            "scope": "database_all",
            "custom_backup_dir": backup_dir
        }).encode("utf-8")

        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/backups",
            self.admin_headers,
            {},
            payload,
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        data = json.loads(body)
        self.assertTrue(data["success"])
        backup_id = data["backup"]["id"]
        self.assertEqual(data["backup"]["integrity_check_status"], "passed")

        # List backups
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/backups",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        list_data = json.loads(body)
        self.assertTrue(list_data["success"])
        self.assertGreaterEqual(len(list_data["backups"]), 1)

    def test_04_restore_drill_api(self):
        """POST /api/v1/dr/drills runs 7-step drill; GET retrieves details."""
        # Create backup first
        backup_dir = os.path.join(self.temp_dir, "api_drill_backups")
        _, _, bkp_body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/backups",
            self.admin_headers,
            {},
            json.dumps({"custom_backup_dir": backup_dir}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        backup_id = json.loads(bkp_body)["backup"]["id"]

        # Run drill
        payload = json.dumps({
            "backup_id": backup_id,
            "target_environment": "isolated_test_sandbox",
            "purpose": "API Integration Test Drill",
            "incident_ref": "INC-API-001"
        }).encode("utf-8")

        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/drills",
            self.admin_headers,
            {},
            payload,
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        drill_data = json.loads(body)
        self.assertTrue(drill_data["success"])
        drill_id = drill_data["drill"]["id"]
        self.assertEqual(drill_data["drill"]["status"], "cleaned_up")

        # Get drill details
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/dr/drills/{drill_id}",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        detail_data = json.loads(body)
        self.assertTrue(detail_data["success"])
        self.assertIn("step_1_authorize_and_scope", detail_data["drill"]["step_progress"])
        self.assertIn("step_7_cleanup", detail_data["drill"]["step_progress"])

    def test_05_drill_sign_off_api(self):
        """POST /api/v1/dr/drills/:id/sign-off approves business resumption."""
        backup_dir = os.path.join(self.temp_dir, "api_signoff_backups")
        _, _, bkp_body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/backups",
            self.admin_headers,
            {},
            json.dumps({"custom_backup_dir": backup_dir}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        backup_id = json.loads(bkp_body)["backup"]["id"]

        _, _, drill_body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/drills",
            self.admin_headers,
            {},
            json.dumps({"backup_id": backup_id}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        drill_id = json.loads(drill_body)["drill"]["id"]

        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/dr/drills/{drill_id}/sign-off",
            self.admin_headers,
            {},
            json.dumps({"notes": "Signed off by SRE and Chief Hakeem"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["drill"]["status"], "business_resumption_approved")

    def test_06_downtime_runbooks_and_reconciliation_api(self):
        """Test listing runbooks, ingesting downtime record, and resolving reconciliation."""
        # List runbooks
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/runbooks",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        rb_data = json.loads(body)
        self.assertGreaterEqual(len(rb_data["runbooks"]), 4)

        # Ingest offline record
        rec_payload = json.dumps({
            "runbook_id": "cb-app-offline",
            "downtime_reference_code": "DT-API-001",
            "domain": "patient_encounter",
            "patient_identifier": "P-10001",
            "captured_by_name": "Dr. Tariq",
            "recorded_payload": {
                "chief_complaint": "Joint stiffness (Waja-ul-Mafasil)",
                "nabz": "Azeem",
                "formulation": "Majun Suranjan"
            }
        }).encode("utf-8")

        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/reconciliation",
            self.admin_headers,
            {},
            rec_payload,
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        rec_data = json.loads(body)
        rec_id = rec_data["record"]["id"]
        self.assertEqual(rec_data["record"]["status"], "pending_review")

        # Resolve record
        resolve_payload = json.dumps({
            "action": "reconcile",
            "canonical_id": "enc-transcribed-1001",
            "notes": "Verified against patient paper chart"
        }).encode("utf-8")

        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/dr/reconciliation/{rec_id}/resolve",
            self.admin_headers,
            {},
            resolve_payload,
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        resolved_data = json.loads(body)
        self.assertEqual(resolved_data["record"]["status"], "reconciled")

    def test_07_dr_pulse_api(self):
        """GET /api/v1/dr/pulse returns real-time posture indicators."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/pulse",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        pulse = data["pulse"]
        self.assertIn("criticality_domains", pulse)
        self.assertIn("backups", pulse)
        self.assertIn("restore_drills", pulse)
        self.assertIn("business_continuity", pulse)

    def test_08_rbac_unauthenticated_and_forbidden(self):
        """Verify unauthenticated requests return 401 and production drills return 403."""
        # Unauthenticated
        status, _, _ = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/domains",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 401)

        # Illegal production target in drill returns 403
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/drills",
            self.admin_headers,
            {},
            json.dumps({"backup_id": "bkp-fake", "target_environment": "production"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()

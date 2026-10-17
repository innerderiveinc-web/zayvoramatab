"""Integration Tests for Enterprise Backup, Disaster Recovery & Verified Restore APIs.

Phase 56 Verification Suite for ZAYVORA MATAB OS.
Tests all endpoints via ApiRouter.dispatch:
1. POST /api/v1/dr/coordinated-backups
2. GET  /api/v1/dr/coordinated-backups
3. GET  /api/v1/dr/coordinated-backups/{id}
4. POST /api/v1/dr/coordinated-backups/{id}/verify
5. POST /api/v1/dr/pitr-markers
6. GET  /api/v1/dr/pitr-markers
7. POST /api/v1/dr/verified-restore-drills
8. GET  /api/v1/dr/verified-restore-drills
9. GET  /api/v1/dr/verified-restore-drills/{id}
10. POST /api/v1/dr/verified-restore-drills/{id}/promotion-gate
11. POST /api/v1/dr/retention/cleanup
12. GET  /api/v1/dr/ledger/verify
13. RBAC Enforcement: 403 Forbidden for unauthorized roles.
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


class TestBackupRestoreApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="test_backup_api_")
        cls.db_path = os.path.join(cls.temp_dir, "test_backup_api.db")
        cls.backup_dir = os.path.join(cls.temp_dir, "backups")
        os.makedirs(cls.backup_dir, exist_ok=True)

        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin (has dr:* permissions via ORG_ADMIN)
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
        cls.admin_token = json.loads(body)["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
            "X-Facility-Id": "fac-central-opd",
        }

        # Authenticate Receptionist (has no dr:backup or dr:drill permissions)
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Receptionist login failed: {body}"
        cls.rec_token = json.loads(body)["token"]
        cls.rec_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.rec_token}",
            "X-Facility-Id": "fac-central-opd",
        }

        cls.created_backup_id = None
        cls.created_drill_id = None
        cls.created_verification_id = None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_create_coordinated_backup_api(self):
        """POST /api/v1/dr/coordinated-backups returns 201 with signed manifest."""
        payload = {
            "backup_type": "full",
            "scope": "database_all",
            "retention_tier": "30_days_standard",
            "immutable_lock_days": 10,
            "custom_backup_dir": self.backup_dir,
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/coordinated-backups",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201, f"Response: {body.decode()}")
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertIn("backup", data)
        self.__class__.created_backup_id = data["backup"]["backup_id"]
        self.assertIsNotNone(data["backup"]["manifest_signature_sha256"])

    def test_02_list_coordinated_backups_api(self):
        """GET /api/v1/dr/coordinated-backups returns 200 with catalog entries."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/coordinated-backups",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 1)

    def test_03_get_coordinated_backup_api(self):
        """GET /api/v1/dr/coordinated-backups/{id} returns 200 with full details."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/dr/coordinated-backups/{self.created_backup_id}",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["backup"]["id"], self.created_backup_id)

    def test_04_verify_backup_manifest_api(self):
        """POST /api/v1/dr/coordinated-backups/{id}/verify returns 200 with verification."""
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/dr/coordinated-backups/{self.created_backup_id}/verify",
            self.admin_headers,
            {},
            b"{}",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertTrue(data["verification"]["verified"])
        self.assertEqual(data["verification"]["status"], "verified_clean")

    def test_05_record_and_list_pitr_markers_api(self):
        """POST & GET /api/v1/dr/pitr-markers."""
        payload = {"marker_label": "pre_reconciliation_canary", "canary_payload": {"test": 123}}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/pitr-markers",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["marker"]["marker_label"], "pre_reconciliation_canary")

        # List markers
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/pitr-markers",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 1)

    def test_06_execute_verified_restore_drill_api(self):
        """POST /api/v1/dr/verified-restore-drills returns 201 with 7-phase report."""
        payload = {
            "backup_id": self.created_backup_id,
            "target_environment": "isolated_test_sandbox",
            "purpose": "REST API Integration Test Drill",
            "authorized_by": "CHIEF_COMPLIANCE_OFFICER",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/verified-restore-drills",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201, f"Response: {body.decode()}")
        data = json.loads(body)
        self.assertTrue(data["success"])
        r = data["drill_report"]
        self.assertTrue(r["technical_integrity_ok"])
        self.assertTrue(r["clinical_invariants_ok"])
        self.assertTrue(r["tenant_isolation_ok"])
        self.assertTrue(r["rto_compliant"])
        self.assertTrue(r["rpo_compliant"])
        self.__class__.created_drill_id = r["drill_id"]
        self.__class__.created_verification_id = r["verification_id"]

    def test_07_list_and_get_restore_drills_api(self):
        """GET /api/v1/dr/verified-restore-drills & GET /{id}."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/verified-restore-drills",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 1)

        # Get drill
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/dr/verified-restore-drills/{self.created_verification_id}",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["drill"]["verification_id"], self.created_verification_id)

    def test_08_evaluate_promotion_gate_api(self):
        """POST /api/v1/dr/verified-restore-drills/{id}/promotion-gate."""
        payload = {
            "decision": "PROMOTION_APPROVED",
            "notes": "Automated verification passed all technical and clinical safety constraints.",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/dr/verified-restore-drills/{self.created_verification_id}/promotion-gate",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["promotion"]["promotion_status"], "PROMOTION_APPROVED")

    def test_09_retention_cleanup_api(self):
        """POST /api/v1/dr/retention/cleanup."""
        payload = {"dry_run": True}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/retention/cleanup",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertTrue(data["cleanup"]["dry_run"])

    def test_10_verify_governance_ledger_api(self):
        """GET /api/v1/dr/ledger/verify."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/dr/ledger/verify",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["ledger_integrity"]["status"], "CHAIN_INTEGRITY_VERIFIED")

    def test_11_rbac_rejection_for_unauthorized_user(self):
        """Receptionist without dr:backup or dr:drill permissions gets 403 Forbidden."""
        # Attempt backup
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/coordinated-backups",
            self.rec_headers,
            {},
            json.dumps({"backup_type": "full"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)

        # Attempt restore drill
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/dr/verified-restore-drills",
            self.rec_headers,
            {},
            json.dumps({"backup_id": self.created_backup_id}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()

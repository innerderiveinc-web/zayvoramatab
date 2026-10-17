"""Unit Tests for Enterprise Backup, Disaster Recovery & Verified Restore Engine.

Phase 56 Verification Suite for ZAYVORA MATAB OS.
Tests core domain logic:
1. Coordinated multi-component backup creation (database + signed manifest).
2. Cryptographic SHA-256 manifest validation and physical file tamper detection.
3. Point-in-Time Recovery (PITR) marker recording, sequence numbering, and WAL flushes.
4. 7-phase isolated restore drill execution with side-effect suppression, technical checks,
   clinical invariants, and multi-tenant boundary validation.
5. Production emergency restore safety gates requiring executive signoff.
6. Production promotion gatekeeper with fail-closed integrity checks.
7. Retention lifecycle management with immutable lock (ransomware protection).
8. SHA-256 chained governance audit ledger integrity and tamper detection.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.backup_restore_engine import BackupRestoreEngine
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
)


class TestBackupRestoreEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_backup_dr_")
        self.db_path = os.path.join(self.temp_dir, "test_zayvora.db")
        self.backup_dir = os.path.join(self.temp_dir, "backups")
        os.makedirs(self.backup_dir, exist_ok=True)

        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = BackupRestoreEngine(self.db_path)

        self.org_id = "org-matab-default"
        self.user_id = "usr-admin-1"

    def tearDown(self):
        if hasattr(self, "engine") and hasattr(self.engine, "conn"):
            try:
                self.engine.conn.close()
            except Exception:
                pass
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_coordinated_backup_creation(self):
        """Test coordinated backup snapshot generation with cryptographic manifest signing."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            scope="database_all",
            user_id=self.user_id,
            retention_tier="30_days_standard",
            immutable_lock_days=7,
            custom_backup_dir=self.backup_dir,
        )

        self.assertIn("backup_id", backup)
        self.assertIn("manifest_id", backup)
        self.assertEqual(backup["organization_id"], self.org_id)
        self.assertEqual(backup["status"], "completed")
        self.assertEqual(backup["integrity_check_status"], "passed")
        self.assertTrue(os.path.exists(backup["backup_artifact_path"]))
        self.assertIsNotNone(backup["checksum_sha256"])
        self.assertIsNotNone(backup["manifest_signature_sha256"])
        self.assertIsNotNone(backup["immutable_lock_until"])
        self.assertGreater(backup["total_tables"], 0)

        # Verify companion JSON manifest file exists
        manifest_file = backup["backup_artifact_path"] + ".manifest.json"
        self.assertTrue(os.path.exists(manifest_file))
        with open(manifest_file, "r") as mf:
            m_data = json.load(mf)
            self.assertEqual(m_data["backup_id"], backup["backup_id"])
            self.assertEqual(m_data["database_checksum_sha256"], backup["checksum_sha256"])

    def test_02_verify_backup_manifest_clean(self):
        """Test independent verification of an untouched, valid backup manifest."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            custom_backup_dir=self.backup_dir,
        )

        verif = self.engine.verify_backup_manifest(backup["backup_id"], actor_id=self.user_id)
        self.assertTrue(verif["verified"])
        self.assertEqual(verif["status"], "verified_clean")
        self.assertEqual(verif["checksum_sha256"], backup["checksum_sha256"])
        self.assertEqual(verif["manifest_signature"], backup["manifest_signature_sha256"])

    def test_03_verify_backup_manifest_detects_physical_tamper(self):
        """Test that altering the physical backup file triggers tamper detection."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            custom_backup_dir=self.backup_dir,
        )

        # Corrupt the physical file by appending unauthorized bytes
        with open(backup["backup_artifact_path"], "ab") as f:
            f.write(b"\xDE\xAD\xBE\xEF_TAMPERED_DATA")

        verif = self.engine.verify_backup_manifest(backup["backup_id"], actor_id=self.user_id)
        self.assertFalse(verif["verified"])
        self.assertEqual(verif["status"], "tamper_detected")
        self.assertIn("Database checksum mismatch", verif["reason"])

    def test_04_verify_backup_manifest_missing_artifact(self):
        """Test that a missing backup file is reported as corrupted."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            custom_backup_dir=self.backup_dir,
        )

        os.remove(backup["backup_artifact_path"])
        verif = self.engine.verify_backup_manifest(backup["backup_id"], actor_id=self.user_id)
        self.assertFalse(verif["verified"])
        self.assertEqual(verif["status"], "corrupted")
        self.assertIn("Physical backup artifact missing", verif["reason"])

    def test_05_pitr_marker_recording_and_listing(self):
        """Test Point-in-Time Recovery marker checkpoints and sequence progression."""
        m1 = self.engine.record_pitr_marker(
            organization_id=self.org_id,
            marker_label="pre_morning_opd",
            canary_payload={"active_doctors": 4, "queue_depth": 12},
        )
        self.assertIn("PITR-", m1["marker_id"])
        self.assertEqual(m1["marker_label"], "pre_morning_opd")
        self.assertEqual(m1["transaction_seq"], 1)

        m2 = self.engine.record_pitr_marker(
            organization_id=self.org_id,
            marker_label="post_morning_opd",
            canary_payload={"active_doctors": 4, "queue_depth": 0},
        )
        self.assertEqual(m2["transaction_seq"], 2)

        markers = self.engine.list_pitr_markers(organization_id=self.org_id)
        self.assertEqual(len(markers), 2)
        # Should be ordered descending by sequence
        self.assertEqual(markers[0]["marker_id"], m2["marker_id"])
        self.assertEqual(markers[1]["marker_id"], m1["marker_id"])

    def test_06_isolated_restore_drill_clean_execution(self):
        """Test comprehensive 7-phase isolated restore drill execution."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            custom_backup_dir=self.backup_dir,
        )

        report = self.engine.execute_verified_restore_drill(
            backup_id=backup["backup_id"],
            organization_id=self.org_id,
            target_environment="isolated_test_sandbox",
            requested_by=self.user_id,
            authorized_by="CHIEF_COMPLIANCE_OFFICER",
            purpose="Quarterly Disaster Recovery Simulation Drill",
        )

        self.assertIn("drill_id", report)
        self.assertIn("verification_id", report)
        self.assertTrue(report["technical_integrity_ok"])
        self.assertEqual(report["foreign_key_violations"], 0)
        self.assertTrue(report["clinical_invariants_ok"])
        self.assertTrue(report["tenant_isolation_ok"])
        self.assertTrue(report["outbound_suppressed"])
        self.assertTrue(report["rto_compliant"])
        self.assertTrue(report["rpo_compliant"])

        # Check all 7 phases executed
        steps = report["step_progress"]
        self.assertEqual(steps["step_1_preflight"]["status"], "PASSED")
        self.assertEqual(steps["step_2_verify_manifest"]["status"], "PASSED")
        self.assertEqual(steps["step_3_isolated_restore"]["status"], "PASSED")
        self.assertTrue(steps["step_3_isolated_restore"]["outbound_messaging_suppressed"])
        self.assertEqual(steps["step_4_technical_integrity"]["status"], "PASSED")
        self.assertEqual(steps["step_5_clinical_invariants"]["status"], "PASSED")
        self.assertEqual(steps["step_6_tenant_isolation"]["status"], "PASSED")
        self.assertEqual(steps["step_7_sandbox_cleanup"]["status"], "PASSED")

    def test_07_restore_drill_blocks_production_emergency_without_officer(self):
        """Test safety gate blocking production emergency restore without CMO or VP Security."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            custom_backup_dir=self.backup_dir,
        )

        with self.assertRaises(ForbiddenError):
            self.engine.execute_verified_restore_drill(
                backup_id=backup["backup_id"],
                organization_id=self.org_id,
                target_environment="production_emergency",
                requested_by=self.user_id,
                authorized_by="JUNIOR_DEVELOPER",
                purpose="Emergency production recovery attempt",
            )

    def test_08_promotion_gate_evaluation(self):
        """Test promotion gatekeeper approval and rejection lifecycle."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            custom_backup_dir=self.backup_dir,
        )

        report = self.engine.execute_verified_restore_drill(
            backup_id=backup["backup_id"],
            organization_id=self.org_id,
            target_environment="isolated_test_sandbox",
            requested_by=self.user_id,
            authorized_by="CHIEF_COMPLIANCE_OFFICER",
        )

        verif_id = report["verification_id"]

        # 1. Authorize promotion
        promo = self.engine.evaluate_promotion_gate(
            verification_id=verif_id,
            decision="PROMOTION_APPROVED",
            promoted_by="SECURITY_DIRECTOR",
            notes="Snapshot verified clean and compliant with BIA SLOs.",
        )
        self.assertEqual(promo["promotion_status"], "PROMOTION_APPROVED")
        self.assertEqual(promo["promoted_by"], "SECURITY_DIRECTOR")

        # 2. Reject promotion
        promo_rej = self.engine.evaluate_promotion_gate(
            verification_id=verif_id,
            decision="PROMOTION_REJECTED",
            promoted_by="CHIEF_MEDICAL_OFFICER",
            notes="Clinical signoff postponed due to planned maintenance window.",
        )
        self.assertEqual(promo_rej["promotion_status"], "PROMOTION_REJECTED")

    def test_09_retention_lifecycle_and_immutable_lock(self):
        """Test retention cleanup respecting immutable locks and legal holds."""
        now = datetime.now(timezone.utc)
        past_iso = (now - timedelta(days=60)).isoformat()
        future_lock_iso = (now + timedelta(days=14)).isoformat()

        # 1. Create backup with immutable lock in future
        bkp1 = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            retention_tier="7_days_operational",
            immutable_lock_days=14,
            custom_backup_dir=self.backup_dir,
        )

        # Force its retention to be in the past to simulate expiration
        cur = self.engine.conn.cursor()
        cur.execute(
            "UPDATE dr_backup_manifests SET retention_expires_at = ? WHERE backup_id = ?",
            (past_iso, bkp1["backup_id"]),
        )
        self.engine.conn.commit()

        # 2. Create another expired backup with NO lock
        bkp2 = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            backup_type="full",
            user_id=self.user_id,
            retention_tier="7_days_operational",
            immutable_lock_days=0,
            custom_backup_dir=self.backup_dir,
        )
        cur.execute(
            "UPDATE dr_backup_manifests SET retention_expires_at = ? WHERE backup_id = ?",
            (past_iso, bkp2["backup_id"]),
        )
        self.engine.conn.commit()

        # 3. Test dry run audit
        audit = self.engine.manage_retention_and_cleanup(organization_id=self.org_id, dry_run=True)
        self.assertEqual(audit["candidates_count"], 1)  # Only bkp2 is eligible
        self.assertEqual(audit["locked_protected_count"], 1)  # bkp1 is locked
        self.assertIn(bkp2["backup_id"], audit["purged_backup_ids"])

        # 4. Test actual cleanup execution
        cleanup = self.engine.manage_retention_and_cleanup(organization_id=self.org_id, dry_run=False)
        self.assertEqual(len(cleanup["purged_backup_ids"]), 1)

        # Verify bkp2 file removed, bkp1 file still intact
        self.assertFalse(os.path.exists(bkp2["backup_artifact_path"]))
        self.assertTrue(os.path.exists(bkp1["backup_artifact_path"]))

    def test_10_cryptographic_audit_ledger_integrity(self):
        """Test SHA-256 blockchain audit ledger verification and tamper detection."""
        # 1. Verification of untouched chain
        ledger_res = self.engine.verify_governance_ledger_integrity()
        self.assertTrue(ledger_res["verified"])
        self.assertEqual(ledger_res["status"], "CHAIN_INTEGRITY_VERIFIED")
        self.assertGreater(ledger_res["blocks_checked"], 0)

        # 2. Tamper with a block in the ledger
        cur = self.engine.conn.cursor()
        cur.execute(
            "UPDATE dr_governance_audit_ledger SET payload_json = '{\"tampered\": true}' WHERE sequence_number = 1"
        )
        self.engine.conn.commit()

        tampered_res = self.engine.verify_governance_ledger_integrity()
        self.assertFalse(tampered_res["verified"])
        self.assertTrue(tampered_res["tamper_detected"])
        self.assertEqual(tampered_res["failed_at_sequence"], 1)

    def test_11_list_and_get_backups_and_drills(self):
        """Test query helpers list_backups, get_backup, list_drills, get_drill."""
        backup = self.engine.create_coordinated_backup(
            organization_id=self.org_id,
            custom_backup_dir=self.backup_dir,
        )

        drill = self.engine.execute_verified_restore_drill(
            backup_id=backup["backup_id"],
            organization_id=self.org_id,
        )

        backups = self.engine.list_backups(self.org_id)
        self.assertGreaterEqual(len(backups), 1)

        b_item = self.engine.get_backup(backup["backup_id"])
        self.assertEqual(b_item["id"], backup["backup_id"])

        drills = self.engine.list_drills(self.org_id)
        self.assertGreaterEqual(len(drills), 1)

        d_item = self.engine.get_drill(drill["verification_id"])
        self.assertEqual(d_item["verification_id"], drill["verification_id"])

        with self.assertRaises(NotFoundError):
            self.engine.get_backup("NON_EXISTENT_BKP")

        with self.assertRaises(NotFoundError):
            self.engine.get_drill("NON_EXISTENT_VRF")


if __name__ == "__main__":
    unittest.main()

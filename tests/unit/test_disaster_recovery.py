"""Unit Tests for Disaster Recovery, Business Continuity, Backup/Restore Verification & Downtime Reconciliation.

Phase 40 for ZAYVORA MATAB OS.
Tests core domain logic:
1. BIA Criticality Domain Catalog & policy updates.
2. Online non-blocking SQLite snapshot generation with SHA-256 checksum & integrity check.
3. 7-step isolated restore drill execution in temporary sandbox.
4. Hard production lockout preventing drills against production target environments.
5. Backup checksum corruption detection.
6. Business resumption sign-off lifecycle.
7. Business continuity runbooks listing.
8. Offline downtime record ingestion, duplicate reference rejection, and reconciliation resolution.
9. Real-time DR pulse posture metrics.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.disaster_recovery import DisasterRecoveryContinuityEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestDisasterRecoveryContinuityEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_dr.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = DisasterRecoveryContinuityEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "PLATFORM_ENGINEER"],
            "org_roles": ["ORG_ADMIN", "PLATFORM_ENGINEER"]
        }

        self.hakeem_ctx = {
            "id": "usr-hakeem-1",
            "user_id": "usr-hakeem-1",
            "username": "chief_hakeem",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["PRACTITIONER", "CHIEF_HAKEEM"],
            "org_roles": ["PRACTITIONER", "CHIEF_HAKEEM"],
            "permissions": ["dr:reconcile", "prescriptions:sign", "encounters:write"]
        }

        self.receptionist_ctx = {
            "id": "usr-rec-1",
            "user_id": "usr-rec-1",
            "username": "receptionist",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["RECEPTIONIST"],
            "org_roles": ["RECEPTIONIST"]
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_get_domain_catalog(self):
        """Verify BIA domain criticality catalog lists all 12 domains with tiers and RTO/RPO."""
        domains = self.engine.get_domain_catalog(self.admin_ctx)
        self.assertGreaterEqual(len(domains), 12)
        
        domain_ids = {d["id"] for d in domains}
        self.assertIn("auth_identity", domain_ids)
        self.assertIn("patients_encounters", domain_ids)
        self.assertIn("consultation_prescriptions", domain_ids)
        self.assertIn("rules_governance", domain_ids)
        self.assertIn("audit_ledger", domain_ids)

        auth_domain = next(d for d in domains if d["id"] == "auth_identity")
        self.assertEqual(auth_domain["tier"], "tier_0_critical")
        self.assertEqual(auth_domain["approved_rto_minutes"], 15)
        self.assertEqual(auth_domain["approved_rpo_minutes"], 5)

    def test_02_update_domain_policy(self):
        """Verify updating domain policy RTO/RPO targets and degraded mode policies."""
        updated = self.engine.update_domain_policy("appointments_queue", {
            "approved_rto_minutes": 25,
            "approved_rpo_minutes": 10,
            "degraded_mode_policy": "Emergency paper tokens with verbal announcement"
        }, self.admin_ctx)
        
        self.assertEqual(updated["id"], "appointments_queue")
        self.assertEqual(updated["approved_rto_minutes"], 25)
        self.assertEqual(updated["approved_rpo_minutes"], 10)

        # Non-existent domain raises NotFoundError
        with self.assertRaises(NotFoundError):
            self.engine.update_domain_policy("non_existent_domain", {"approved_rto_minutes": 10}, self.admin_ctx)

    def test_03_create_online_backup(self):
        """Verify live non-blocking backup generation with SHA-256 digest and PRAGMA integrity."""
        backup_dir = os.path.join(self.temp_dir, "backups")
        backup = self.engine.create_online_backup(
            backup_type="full",
            scope="database_all",
            custom_backup_dir=backup_dir,
            user_ctx=self.admin_ctx
        )
        self.assertTrue(backup["id"].startswith("bkp-"))
        self.assertEqual(backup["status"], "completed")
        self.assertEqual(backup["integrity_check_status"], "passed")
        self.assertGreater(backup["size_bytes"], 0)
        self.assertGreater(backup["total_tables"], 150)
        self.assertTrue(os.path.exists(backup["backup_artifact_path"]))

    def test_04_list_backups(self):
        """Verify listing backups from catalog."""
        backup_dir = os.path.join(self.temp_dir, "backups")
        b1 = self.engine.create_online_backup(custom_backup_dir=backup_dir, user_ctx=self.admin_ctx)
        backups = self.engine.list_backups(self.admin_ctx)
        self.assertGreaterEqual(len(backups), 1)
        self.assertEqual(backups[0]["id"], b1["id"])

    def test_05_execute_restore_drill_isolated_success(self):
        """Verify full 7-step isolated restore drill execution."""
        backup_dir = os.path.join(self.temp_dir, "backups")
        backup = self.engine.create_online_backup(custom_backup_dir=backup_dir, user_ctx=self.admin_ctx)

        drill = self.engine.execute_restore_drill(
            backup_id=backup["id"],
            target_environment="isolated_test_sandbox",
            purpose="Automated Test Drill",
            incident_ref="INC-TEST-001",
            user_ctx=self.admin_ctx
        )
        self.assertEqual(drill["status"], "cleaned_up")
        self.assertIn("step_1_authorize_and_scope", drill["step_progress"])
        self.assertIn("step_2_validate_backup", drill["step_progress"])
        self.assertIn("step_3_restore_in_isolation", drill["step_progress"])
        self.assertIn("step_4_verify_technical_integrity", drill["step_progress"])
        self.assertIn("step_5_verify_application_workflows", drill["step_progress"])
        self.assertIn("step_6_document_results", drill["step_progress"])
        self.assertIn("step_7_cleanup", drill["step_progress"])

        # Check technical verification results
        step4 = drill["step_progress"]["step_4_verify_technical_integrity"]
        self.assertEqual(step4["integrity_check"], "ok")
        self.assertEqual(step4["foreign_key_violations"], 0)
        self.assertGreater(step4["restored_tables_count"], 150)

        # Check workflow verification results
        step5 = drill["step_progress"]["step_5_verify_application_workflows"]
        self.assertGreater(step5["user_accounts_verified"], 0)

        # Check that domain catalog last_drill_timestamp was updated
        domains = self.engine.get_domain_catalog(self.admin_ctx)
        for d in domains:
            self.assertIsNotNone(d["last_drill_timestamp"])
            self.assertEqual(d["status"], "fully_protected")

    def test_06_execute_restore_drill_production_lockout(self):
        """Verify that restore drills targeting production are strictly forbidden."""
        backup_dir = os.path.join(self.temp_dir, "backups")
        backup = self.engine.create_online_backup(custom_backup_dir=backup_dir, user_ctx=self.admin_ctx)

        with self.assertRaises(ForbiddenError):
            self.engine.execute_restore_drill(
                backup_id=backup["id"],
                target_environment="production",
                purpose="Illegal Prod Attempt",
                user_ctx=self.admin_ctx
            )

    def test_07_execute_restore_drill_checksum_corruption_detection(self):
        """Verify that corrupted backup files fail step 2 checksum verification."""
        backup_dir = os.path.join(self.temp_dir, "backups")
        backup = self.engine.create_online_backup(custom_backup_dir=backup_dir, user_ctx=self.admin_ctx)

        # Intentionally tamper with physical backup file
        with open(backup["backup_artifact_path"], "ab") as f:
            f.write(b"CORRUPTED_BYTES_INJECTED_FOR_TEST")

        with self.assertRaises(ValidationError) as ctx:
            self.engine.execute_restore_drill(
                backup_id=backup["id"],
                target_environment="isolated_test_sandbox",
                purpose="Corrupted File Test",
                user_ctx=self.admin_ctx
            )
        self.assertIn("checksum mismatch", str(ctx.exception).lower())

    def test_08_sign_off_drill_resumption(self):
        """Verify clinician or SRE sign-off on business resumption."""
        backup_dir = os.path.join(self.temp_dir, "backups")
        backup = self.engine.create_online_backup(custom_backup_dir=backup_dir, user_ctx=self.admin_ctx)
        drill = self.engine.execute_restore_drill(
            backup_id=backup["id"],
            target_environment="isolated_test_sandbox",
            purpose="Pre-Sign-Off Drill",
            user_ctx=self.admin_ctx
        )

        signed_off = self.engine.sign_off_drill_resumption(
            drill_id=drill["id"],
            notes="Clinician verified patient records match paper charts",
            user_ctx=self.admin_ctx
        )
        self.assertEqual(signed_off["status"], "business_resumption_approved")
        self.assertIsNotNone(signed_off["resumption_authorized_at"])

    def test_09_list_runbooks(self):
        """Verify business continuity runbooks are listed with trigger conditions and owners."""
        runbooks = self.engine.list_runbooks(self.admin_ctx)
        self.assertGreaterEqual(len(runbooks), 4)
        runbook_ids = {r["id"] for r in runbooks}
        self.assertIn("cb-app-offline", runbook_ids)
        self.assertIn("cb-db-outage", runbook_ids)
        self.assertIn("cb-network-partition", runbook_ids)
        self.assertIn("cb-payment-gateway-down", runbook_ids)

    def test_10_downtime_reconciliation_workflow(self):
        """Verify offline downtime paper record ingestion and clinician reconciliation."""
        rec = self.engine.ingest_downtime_record({
            "runbook_id": "cb-app-offline",
            "downtime_reference_code": "DT-TEST-001",
            "domain": "patient_encounter",
            "patient_identifier": "P-99999",
            "captured_by_name": "Hakim Ajmal",
            "recorded_payload": {
                "symptoms": "Fever, headache, dry cough",
                "secret_key": "MUST_BE_REDACTED",
                "prescribed": "Sharbat Toot Siah"
            }
        }, self.hakeem_ctx)

        self.assertEqual(rec["status"], "pending_review")
        self.assertEqual(rec["downtime_reference_code"], "DT-TEST-001")

        # Duplicate reference code rejected
        with self.assertRaises(ConflictError):
            self.engine.ingest_downtime_record({
                "runbook_id": "cb-app-offline",
                "downtime_reference_code": "DT-TEST-001",
                "domain": "patient_encounter",
                "patient_identifier": "P-99999",
                "captured_by_name": "Hakim Ajmal"
            }, self.hakeem_ctx)

        # Secret was redacted
        queue = self.engine.list_reconciliation_queue(self.admin_ctx)
        item = next(i for i in queue if i["downtime_reference_code"] == "DT-TEST-001")
        self.assertEqual(item["recorded_payload"]["secret_key"], "[REDACTED_SECRET]")

        # Reconcile into canonical database
        resolved = self.engine.resolve_downtime_record(
            record_id=item["id"],
            action="reconcile",
            canonical_id="enc-canonical-9999",
            notes="Transcribed into electronic consultation record",
            user_ctx=self.hakeem_ctx
        )
        self.assertEqual(resolved["status"], "reconciled")

    def test_11_downtime_reconciliation_reject_and_conflict(self):
        """Verify rejecting or flagging conflict on downtime records."""
        rec1 = self.engine.ingest_downtime_record({
            "runbook_id": "cb-app-offline",
            "downtime_reference_code": "DT-REJECT-001",
            "domain": "billing_invoice",
            "patient_identifier": "P-88888",
            "captured_by_name": "Staff Member"
        }, self.hakeem_ctx)

        resolved_reject = self.engine.resolve_downtime_record(
            record_id=rec1["id"],
            action="reject",
            notes="Illegible handwriting; duplicate invoice already settled",
            user_ctx=self.hakeem_ctx
        )
        self.assertEqual(resolved_reject["status"], "rejected")

        rec2 = self.engine.ingest_downtime_record({
            "runbook_id": "cb-payment-gateway-down",
            "downtime_reference_code": "DT-CONFLICT-001",
            "domain": "billing_invoice",
            "patient_identifier": "P-77777",
            "captured_by_name": "Cashier"
        }, self.hakeem_ctx)

        resolved_conflict = self.engine.resolve_downtime_record(
            record_id=rec2["id"],
            action="flag_conflict",
            conflict_reason="Amount mismatch between manual receipt and bank SMS",
            user_ctx=self.hakeem_ctx
        )
        self.assertEqual(resolved_conflict["status"], "conflicted_duplicate")

    def test_12_get_dr_pulse(self):
        """Verify real-time Disaster Recovery posture metrics."""
        pulse = self.engine.get_dr_pulse(self.admin_ctx)
        self.assertIn("criticality_domains", pulse)
        self.assertIn("backups", pulse)
        self.assertIn("restore_drills", pulse)
        self.assertIn("business_continuity", pulse)
        self.assertGreaterEqual(pulse["criticality_domains"]["total"], 12)
        self.assertIn(pulse["business_continuity"]["posture_status"], ["READY", "NEEDS_DRILL"])


if __name__ == "__main__":
    unittest.main()

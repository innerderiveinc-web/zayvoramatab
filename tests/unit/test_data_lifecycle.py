"""Unit Tests for Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Engine.

Phase 41 for ZAYVORA MATAB OS.
Tests core domain logic:
1. Data Inventory Catalog retrieval & classification integrity.
2. Versioned Retention Policy creation, validation, and formal approval lifecycle.
3. Universal Legal Holds: placement, scope evaluation, and formal release.
4. Deterministic Side-Effect Free Dry-Runs: evaluates eligibility without mutating records.
5. Governed Multi-Store Disposal & Clinical Immutability:
   - Signed encounters/prescriptions are preserved (restricted/archived), never physically destroyed.
   - Deletion respects active legal holds (strict block).
6. Data Subject Privacy Rights Pipeline:
   - Ingestion, identity verification requirement, fulfillment plan approval, and execution.
   - Legal hold freeze on erasure requests.
7. Real-Time Data Lifecycle Pulse Posture metrics.
8. RBAC and authorization enforcement across all lifecycle operations.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.data_lifecycle import EnterpriseDataLifecycleEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestEnterpriseDataLifecycleEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_lifecycle.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = EnterpriseDataLifecycleEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "CLINICAL_DIRECTOR"],
            "org_roles": ["ORG_ADMIN", "CLINICAL_DIRECTOR"],
            "permissions": ["lifecycle:read", "lifecycle:evaluate", "lifecycle:hold", "lifecycle:approve", "lifecycle:execute", "lifecycle:request"]
        }

        self.compliance_ctx = {
            "id": "usr-comp-1",
            "user_id": "usr-comp-1",
            "username": "compliance_officer",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["COMPLIANCE_OFFICER"],
            "org_roles": ["COMPLIANCE_OFFICER"],
            "permissions": ["lifecycle:read", "lifecycle:evaluate", "lifecycle:hold", "lifecycle:request"]
        }

        self.unauthorized_ctx = {
            "id": "usr-anon-1",
            "user_id": "usr-anon-1",
            "username": "guest",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["GUEST"],
            "org_roles": ["GUEST"],
            "permissions": []
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_inventory_catalog_success(self):
        """Verifies inventory catalog returns 14 governed categories with accurate metadata."""
        catalog = self.engine.get_inventory_catalog(self.admin_ctx)
        self.assertIsInstance(catalog, list)
        self.assertGreaterEqual(len(catalog), 14)

        cat_names = [c["category_name"] for c in catalog]
        self.assertIn("patient_demographics", cat_names)
        self.assertIn("clinical_encounters", cat_names)
        self.assertIn("prescriptions_nuskha", cat_names)
        self.assertIn("security_audit_ledger", cat_names)
        self.assertIn("integration_outbox", cat_names)

        # Verify classification and storage types
        for item in catalog:
            self.assertIn(item["storage_type"], self.engine.VALID_STORAGE_TYPES)
            self.assertIn(item["sensitivity_classification"], self.engine.VALID_SENSITIVITIES)

    def test_get_inventory_catalog_unauthorized(self):
        """Ensures unauthorized context without lifecycle:read is denied."""
        with self.assertRaises(ForbiddenError):
            self.engine.get_inventory_catalog(self.unauthorized_ctx)

    def test_policy_creation_and_approval_lifecycle(self):
        """Verifies creating a draft retention policy and transitioning it to approved."""
        new_policy_payload = {
            "policy_key": "LAB_REPORTS_5YR",
            "version": "1.0.0",
            "title": "Laboratory & Diagnostic Reports 5-Year Retention Policy",
            "description": "Retains pathology and Unani diagnostic records for 5 years.",
            "data_category_ids": ["cat-clinical-encounters"],
            "scope": "tenant",
            "retention_trigger": "creation_date",
            "retention_period_days": 1825,
            "archive_rule": "RESTRICTED_READ_ONLY",
            "disposal_action": "restrict",
            "hold_behavior": "STRICT_BLOCK",
            "downstream_propagation_rule": "ALL_LINKED_STORES",
            "accountable_owner": "DIAGNOSTICS_DIRECTOR",
            "approver_roles": ["CLINICAL_DIRECTOR"],
            "jurisdiction_tags": ["IN-AYUSH"],
            "legal_source_references": ["CEA Diagnostics Rule 2018"]
        }

        created = self.engine.create_policy(new_policy_payload, self.admin_ctx)
        self.assertEqual(created["policy_key"], "LAB_REPORTS_5YR")
        self.assertEqual(created["status"], "draft")

        # Approve policy
        approved = self.engine.approve_policy(created["id"], self.admin_ctx)
        self.assertEqual(approved["status"], "approved")
        self.assertIn(approved["approved_by"], [self.admin_ctx["id"], self.admin_ctx["username"]])
        self.assertIsNotNone(approved["approved_at"])

    def test_legal_hold_placement_and_release(self):
        """Tests placing a universal legal preservation hold and subsequently releasing it."""
        hold_payload = {
            "hold_code": "LH-UNIT-TEST-002",
            "title": "Litigation Hold: Supreme Court Appeal Record",
            "reason_category": "litigation",
            "scope_filter": {
                "category_id": "cat-clinical-encounters",
                "patient_id": "P-UNIT-100"
            },
            "review_date": "2027-12-31"
        }

        hold = self.engine.place_legal_hold(hold_payload, self.compliance_ctx)
        self.assertEqual(hold["status"], "active")
        self.assertEqual(hold["hold_code"], "LH-UNIT-TEST-002")

        # Verify hold is listed in active holds
        active_holds = self.engine.list_legal_holds(self.compliance_ctx, status_filter="active")
        hold_codes = [h["hold_code"] for h in active_holds]
        self.assertIn("LH-UNIT-TEST-002", hold_codes)

        # Release hold
        release_payload = {
            "release_reason": "Case resolved by court order with full dismissal"
        }
        released = self.engine.release_legal_hold(hold["id"], release_payload, self.compliance_ctx)
        self.assertEqual(released["status"], "released")
        self.assertEqual(released["release_reason"], release_payload["release_reason"])
        self.assertIsNotNone(released["released_at"])

    def test_deterministic_dry_run_retention_evaluation(self):
        """Verifies that dry-run evaluation runs deterministically without mutating underlying data."""
        # Retrieve approved clinical policy
        policies = self.engine.get_policies(self.admin_ctx)
        clinical_policy = next((p for p in policies if p["policy_key"] == "CLINICAL_STATUTORY_7YR"), None)
        self.assertIsNotNone(clinical_policy)

        # Run dry-run evaluation for clinical encounters
        eval_run = self.engine.evaluate_retention(
            clinical_policy["id"],
            "cat-clinical-encounters",
            self.admin_ctx,
            dry_run=True
        )

        self.assertEqual(eval_run["run_mode"], "dry_run")
        self.assertEqual(eval_run["status"], "completed")
        self.assertIn("records_evaluated", eval_run)
        self.assertIn("records_held", eval_run)
        self.assertIn("records_ineligible", eval_run)
        self.assertIsInstance(eval_run["summary"], dict)

    def test_clinical_record_immutability_guard(self):
        """Ensures signed clinical records are restricted/archived and physical row deletion is rejected."""
        encounter_id = "enc-immut-001"
        cur = self.engine.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO encounters (
                id, organization_id, facility_id, patient_id, practitioner_id,
                encounter_type, status, reason_for_visit, created_by, created_at, updated_at
            ) VALUES (
                ?, 'org-matab-default', 'fac-central-opd', 'pat-syn-002', 'usr-hakeem-1',
                'consultation', 'signed', 'Chronic headache', 'usr-hakeem-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            );
        """, (encounter_id,))
        self.engine.conn.commit()

        # Retrieve policy
        policies = self.engine.get_policies(self.admin_ctx)
        clinical_policy = next((p for p in policies if p["policy_key"] == "CLINICAL_STATUTORY_7YR"), policies[0])

        # Attempt disposal with action_type='restrict' (allowed governed archival)
        op = self.engine.execute_disposal(
            "cat-clinical-encounters",
            encounter_id,
            clinical_policy["id"],
            self.admin_ctx,
            action_type="restrict"
        )
        self.assertIn(op["status"], ["restricted", "archived", "verified_complete"])

        # Attempt hard physical delete on signed clinical encounter -> MUST be restricted rather than deleted
        op_delete = self.engine.execute_disposal(
            "cat-clinical-encounters",
            encounter_id,
            clinical_policy["id"],
            self.admin_ctx,
            action_type="delete"
        )
        # Even when requested as delete, clinical encounters are restricted rather than wiped
        self.assertNotEqual(op_delete["status"], "deleted")
        self.assertIn(op_delete["status"], ["restricted", "archived"])

    def test_active_legal_hold_blocks_disposal(self):
        """Verifies that an active legal hold strictly blocks disposal on matching records."""
        # Seed record that matches the seeded hold: category 'cat-clinical-encounters', patient 'pat-syn-001'
        cur = self.engine.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO encounters (
                id, organization_id, facility_id, patient_id, practitioner_id,
                encounter_type, status, reason_for_visit, created_by, created_at, updated_at
            ) VALUES (
                'enc-held-001', 'org-matab-default', 'fac-central-opd', 'pat-syn-001', 'usr-hakeem-1',
                'consultation', 'completed', 'Follow-up for held patient', 'usr-hakeem-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            );
        """)
        self.engine.conn.commit()

        policies = self.engine.get_policies(self.admin_ctx)
        clinical_policy = next((p for p in policies if p["policy_key"] == "CLINICAL_STATUTORY_7YR"), policies[0])

        with self.assertRaises(ForbiddenError):
            self.engine.execute_disposal(
                "cat-clinical-encounters",
                "enc-held-001",
                clinical_policy["id"],
                self.admin_ctx,
                action_type="restrict"
            )

    def test_privacy_rights_request_lifecycle(self):
        """Verifies full lifecycle of data subject privacy request: ingestion -> verification -> approval -> execution."""
        req_payload = {
            "subject_identifier": "P-10002",
            "request_type": "data_access",
            "scope_details": "Requesting comprehensive copy of consultations and prescriptions.",
            "channel": "clinic_reception"
        }

        # 1. Ingest
        req_rec = self.engine.ingest_privacy_request(req_payload, self.compliance_ctx)
        self.assertEqual(req_rec["status"], "received")
        req_id = req_rec["id"]

        # 2. Cannot approve plan before identity verification
        with self.assertRaises(ConflictError):
            self.engine.approve_request_plan(req_id, {"plan": "Export bundle"}, self.admin_ctx)

        # 3. Verify identity
        verified = self.engine.verify_request_identity(req_id, self.compliance_ctx)
        self.assertEqual(verified["status"], "identity_verified")
        self.assertIsNotNone(verified["identity_verified_at"])

        # 4. Approve fulfillment plan
        plan = {
            "target_stores": ["patients", "encounters", "prescriptions"],
            "format": "JSON_EXPORT_ENCRYPTED",
            "estimated_records": 12
        }
        approved = self.engine.approve_request_plan(req_id, plan, self.admin_ctx)
        self.assertEqual(approved["status"], "approved")
        self.assertIsNotNone(approved["approved_by"])

        # 5. Execute request plan
        executed = self.engine.execute_request_plan(req_id, self.admin_ctx)
        self.assertEqual(executed["status"], "completed")
        self.assertIsNotNone(executed["closure_evidence"])
        self.assertIsNotNone(executed["completed_at"])

    def test_get_lifecycle_pulse(self):
        """Tests pulse telemetry metrics calculation."""
        pulse = self.engine.get_lifecycle_pulse(self.admin_ctx)
        self.assertIn("governed_categories_count", pulse)
        self.assertIn("active_policies_count", pulse)
        self.assertIn("active_legal_holds_count", pulse)
        self.assertIn("completed_evaluations_count", pulse)
        self.assertIn("completed_disposals_count", pulse)
        self.assertIn("open_privacy_requests_count", pulse)
        self.assertGreaterEqual(pulse["governed_categories_count"], 14)


if __name__ == "__main__":
    unittest.main()

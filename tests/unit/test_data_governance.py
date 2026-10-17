"""Unit Tests for Enterprise Master Data Management, Data Governance & Quality Stewardship Engine.

Phase 42 for ZAYVORA MATAB OS.
Tests core domain logic:
1. Master Entities Catalog retrieval & custom entity registration.
2. Versioned Data Quality Rules creation across 9 dimensions.
3. Deterministic Data Quality Scans & granular findings generation.
4. Explainable Duplicate Candidate Detection & scoring (zero auto-merges).
5. Human Steward Duplicate Resolution with optional master cross-reference linking.
6. Reversible Patient Cross-References (linking and unlinking).
7. Governed Terminology Stewardship (Unani-to-biomedical mappings with mandatory caveats).
8. Governed Staged Bulk Ingestion (staging, dry-run simulation, and idempotent commit).
9. Data Stewardship Case Management & event audit trail.
10. MDM Health & Governance Pulse Metrics.
11. RBAC and tenant boundary enforcement.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.data_governance import EnterpriseMasterDataGovernanceEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestEnterpriseMasterDataGovernanceEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_mdm.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = EnterpriseMasterDataGovernanceEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "DATA_STEWARD"],
            "org_roles": ["ORG_ADMIN", "DATA_STEWARD"],
            "permissions": [
                "mdm:read", "mdm:rule_manage", "mdm:evaluate",
                "mdm:stewardship_manage", "mdm:duplicate_review",
                "mdm:import_manage", "mdm:terminology_steward"
            ]
        }

        self.steward_ctx = {
            "id": "usr-steward-1",
            "user_id": "usr-steward-1",
            "username": "data_steward",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["DATA_STEWARD"],
            "org_roles": ["DATA_STEWARD"],
            "permissions": [
                "mdm:read", "mdm:evaluate", "mdm:stewardship_manage",
                "mdm:duplicate_review", "mdm:import_manage"
            ]
        }

        self.readonly_ctx = {
            "id": "usr-audit-1",
            "user_id": "usr-audit-1",
            "username": "auditor",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["READ_ONLY_AUDITOR"],
            "org_roles": ["READ_ONLY_AUDITOR"],
            "permissions": ["mdm:read"]
        }

        self.unauth_ctx = {
            "id": "usr-guest-1",
            "user_id": "usr-guest-1",
            "username": "guest",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["GUEST"],
            "org_roles": ["GUEST"],
            "permissions": []
        }

    def tearDown(self):
        if hasattr(self.engine, "conn") and self.engine.conn:
            self.engine.conn.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # 1. Master Entities Catalog
    def test_get_master_entities(self):
        entities = self.engine.get_master_entities(self.admin_ctx)
        self.assertGreaterEqual(len(entities), 5)
        entity_types = [e["entity_type"] for e in entities]
        self.assertIn("patient", entity_types)
        self.assertIn("formulation", entity_types)
        self.assertIn("terminology_concept", entity_types)

    def test_register_master_entity_conflict(self):
        with self.assertRaises(ConflictError):
            self.engine.register_master_entity(self.admin_ctx, {
                "entity_type": "patient",
                "display_name": "Duplicate Patient Entity",
                "canonical_table": "patients"
            })

    # 2. Versioned Data Quality Rules
    def test_list_dq_rules(self):
        rules = self.engine.list_dq_rules(self.admin_ctx)
        self.assertGreaterEqual(len(rules), 8)
        dimensions = {r["dimension"] for r in rules}
        self.assertIn("completeness", dimensions)
        self.assertIn("validity", dimensions)
        self.assertIn("uniqueness", dimensions)

    def test_create_dq_rule(self):
        rule = self.engine.create_dq_rule(self.admin_ctx, {
            "rule_key": "RULE_TEST_CUSTOM_RULE",
            "name": "Custom Test Rule",
            "domain": "clinical_patient",
            "dimension": "completeness",
            "rule_type": "required",
            "severity": "warning",
            "scope": "tenant",
            "target_entity_type": "patient",
            "target_field_path": "address",
            "rule_logic": {"required": True},
            "remediation_guidance": "Ensure patient address is filled."
        })
        self.assertEqual(rule["rule_key"], "RULE_TEST_CUSTOM_RULE")
        self.assertEqual(rule["status"], "approved")

    # 3. Data Quality Evaluation Scans
    def test_run_dq_scan_patients(self):
        # Insert a patient with missing contact and invalid phone
        cur = self.engine.conn.cursor()
        cur.execute("""
            INSERT INTO patients (
                id, organization_id, mrn, given_name, family_name, display_name, sex,
                date_of_birth, status
            ) VALUES ('pat-bad-001', 'org-matab-default', 'MRN-2026-BAD01', 'Test', 'Incomplete', 'Test Incomplete', 'UNKNOWN_SEX', '1990-01-01', 'ACTIVE');
        """)
        cur.execute("""
            INSERT INTO patient_contacts (
                id, patient_id, organization_id, contact_type, contact_value, normalized_value, is_preferred
            ) VALUES ('cnt-bad-001', 'pat-bad-001', 'org-matab-default', 'PHONE', '123', '123', 1);
        """)
        self.engine.conn.commit()

        scan = self.engine.run_dq_scan(self.admin_ctx, target_entity_type="patient")
        self.assertEqual(scan["status"], "completed")
        self.assertGreater(scan["findings_count"], 0)

        findings = self.engine.get_scan_findings(self.admin_ctx, scan["scan_id"])
        issue_codes = [f["issue_code"] for f in findings]
        self.assertIn("INVALID_PHONE_FORMAT", issue_codes)

    # 4. Explainable Duplicate Candidate Detection (Zero Auto-Merge)
    def test_detect_duplicate_candidates_zero_auto_merge(self):
        cur = self.engine.conn.cursor()
        # Insert two highly similar patients
        cur.execute("""
            INSERT INTO patients (
                id, organization_id, mrn, given_name, family_name, display_name, sex,
                date_of_birth, status
            ) VALUES
            ('pat-pair-1', 'org-matab-default', 'MRN-2026-P001', 'Tariq', 'Mahmood', 'Tariq Mahmood', 'MALE', '1985-05-15', 'ACTIVE'),
            ('pat-pair-2', 'org-matab-default', 'MRN-2026-P002', 'Tariq', 'Mahmood', 'Tariq Mahmood', 'MALE', '1985-05-15', 'ACTIVE');
        """)
        cur.execute("""
            INSERT INTO patient_contacts (
                id, patient_id, organization_id, contact_type, contact_value, normalized_value, is_preferred
            ) VALUES
            ('cnt-pair-1', 'pat-pair-1', 'org-matab-default', 'PHONE', '+919876543210', '919876543210', 1),
            ('cnt-pair-2', 'pat-pair-2', 'org-matab-default', 'PHONE', '+919876543210', '919876543210', 1);
        """)
        cur.execute("""
            INSERT INTO patient_identifiers (
                id, patient_id, organization_id, identifier_type, identifier_value, normalized_value
            ) VALUES
            ('nid-pair-1', 'pat-pair-1', 'org-matab-default', 'NATIONAL_ID', 'NID-999', 'NID-999'),
            ('nid-pair-2', 'pat-pair-2', 'org-matab-default', 'NATIONAL_ID', 'NID-999', 'NID-999');
        """)
        self.engine.conn.commit()

        candidates = self.engine.detect_duplicate_candidates(self.admin_ctx)
        pair_candidates = [c for c in candidates if {c["primary_record_id"], c["candidate_record_id"]} == {"pat-pair-1", "pat-pair-2"}]
        self.assertEqual(len(pair_candidates), 1)
        cand = pair_candidates[0]
        self.assertGreaterEqual(cand["confidence_score"], 0.85)
        self.assertEqual(cand["status"], "pending")
        self.assertIn("name_match", cand["match_features"])
        self.assertIn("phone_match", cand["match_features"])

        # Crucial Non-Negotiable: Ensure records are NOT auto-merged
        cur.execute("SELECT COUNT(*) as count FROM patients WHERE id IN ('pat-pair-1', 'pat-pair-2');")
        self.assertEqual(cur.fetchone()["count"], 2)

    # 5. Human Steward Duplicate Resolution & Cross-Reference Linking
    def test_resolve_duplicate_review_confirmed(self):
        # Create a pending review
        cur = self.engine.conn.cursor()
        cur.execute("""
            INSERT INTO mdm_duplicate_candidate_reviews (
                id, organization_id, entity_type, primary_record_id, candidate_record_id,
                confidence_score, match_features_json, status
            ) VALUES (
                'rev-test-01', 'org-matab-default', 'patient', 'pat-syn-001', 'pat-syn-002',
                0.92, '{"name_match": "exact"}', 'pending'
            );
        """)
        self.engine.conn.commit()

        res = self.engine.resolve_duplicate_review(
            self.admin_ctx,
            review_id="rev-test-01",
            decision="confirmed_duplicate",
            rationale="Verified with Tabib and patient: same individual registered under family phone.",
            create_master_link=True
        )
        self.assertEqual(res["status"], "confirmed_duplicate")
        self.assertIsNotNone(res["master_link_created"])

        # Verify cross-reference was created
        xrefs = self.engine.list_cross_references(self.admin_ctx, master_patient_id="pat-syn-001")
        self.assertGreaterEqual(len(xrefs), 1)
        self.assertEqual(xrefs[0]["is_active"], 1)

    # 6. Reversible Patient Cross-References
    def test_unlink_cross_reference_reversibility(self):
        xref = self.engine.create_cross_reference(
            self.admin_ctx,
            master_patient_id="pat-syn-001",
            linked_patient_id="pat-syn-002",
            link_type="alias",
            notes="Temporary alias link for testing"
        )
        self.assertEqual(xref["is_active"], 1)

        unlinked = self.engine.unlink_cross_reference(
            self.admin_ctx,
            xref_id=xref["id"],
            notes="Identified as twin sibling; unlinking confirmed."
        )
        self.assertEqual(unlinked["is_active"], 0)

    # 7. Governed Terminology Stewardship
    def test_terminology_stewardship_workflow(self):
        term = self.engine.create_terminology_mapping(self.admin_ctx, {
            "unani_concept_code": "WARM_E_KABID",
            "unani_term": "Warm-e-Kabid (Hepatic Inflammation)",
            "modern_code_system": "ICD-10",
            "modern_concept_code": "K75.9",
            "modern_term": "Inflammatory liver disease, unspecified",
            "mapping_type": "approximate",
            "clinical_scope": "gastroenterology_hepatology",
            "limitations": "Warm-e-Kabid includes humoral stagnation not recognized in viral/toxic hepatitis.",
            "provenance": "Ibn Sina, Al-Qanun fi al-Tibb, Book III."
        })
        self.assertEqual(term["review_status"], "draft")

        reviewed = self.engine.review_terminology_mapping(
            self.admin_ctx,
            mapping_id=term["id"],
            decision="approved",
            rationale="Reviewed and verified by Senior Unani Consultant."
        )
        self.assertEqual(reviewed["review_status"], "approved")

    # 8. Governed Staged Bulk Ingestion (Dry-Run & Commit)
    def test_bulk_import_lifecycle(self):
        raw_patients = [
            {
                "first_name": "Hakim",
                "last_name": "Azam",
                "phone": "+919876543210",
                "gender": "M",
                "date_of_birth": "1978-03-21",
                "address": "Hyderabad Old City"
            },
            {
                "first_name": "", # Invalid: missing mandatory name
                "phone": "invalid-phone",
                "gender": "M"
            }
        ]

        # 1. Stage batch
        staged = self.engine.stage_import_batch(
            self.admin_ctx,
            batch_name="Camp Patients Batch 2026",
            entity_type="patient",
            raw_records=raw_patients
        )
        self.assertEqual(staged["status"], "staged")
        self.assertEqual(staged["total_records"], 2)

        # 2. Dry-run validation
        dry_run = self.engine.evaluate_import_dry_run(self.admin_ctx, staged["batch_id"])
        self.assertEqual(dry_run["status"], "validated_dry_run")
        summary = dry_run["dry_run_summary"]
        self.assertEqual(summary["valid_records"], 1)
        self.assertEqual(summary["invalid_records"], 1)

        # 3. Commit batch
        committed = self.engine.commit_import_batch(self.admin_ctx, staged["batch_id"])
        self.assertEqual(committed["status"], "committed")
        self.assertEqual(committed["committed_count"], 1)

        # Verify patient exists in production table
        cur = self.engine.conn.cursor()
        cur.execute("SELECT id FROM patients WHERE given_name = 'Hakim' AND family_name = 'Azam';")
        self.assertIsNotNone(cur.fetchone())

    # 9. Data Stewardship Case Management
    def test_stewardship_case_lifecycle(self):
        case = self.engine.create_stewardship_case(self.admin_ctx, {
            "title": "Review Potential Duplicate Patient pat-syn-001",
            "description": "High matching score on name and address with new registration.",
            "category": "duplicate_identity",
            "priority": "high",
            "target_entity_type": "patient",
            "target_entity_id": "pat-syn-001",
            "proposed_resolution": "Verify with patient phone call."
        })
        self.assertEqual(case["status"], "open")

        # Transition status
        t1 = self.engine.transition_stewardship_case(
            self.admin_ctx,
            case_id=case["id"],
            to_status="awaiting_identity_review",
            comment="Assigned to front desk to check national ID during consultation."
        )
        self.assertEqual(t1["to_status"], "awaiting_identity_review")

        events = self.engine.get_stewardship_case_events(self.admin_ctx, case["id"])
        self.assertGreaterEqual(len(events), 2)

    # 10. MDM Pulse
    def test_get_mdm_pulse(self):
        pulse = self.engine.get_mdm_pulse(self.admin_ctx)
        self.assertIn("master_entities_count", pulse)
        self.assertIn("active_rules_count", pulse)
        self.assertIn("governance_status", pulse)
        self.assertGreaterEqual(pulse["master_entities_count"], 5)

    # 11. RBAC & Permission Enforcement
    def test_unauthorized_access_denied(self):
        with self.assertRaises(ForbiddenError):
            self.engine.get_master_entities(self.unauth_ctx)

        with self.assertRaises(ForbiddenError):
            self.engine.create_dq_rule(self.readonly_ctx, {
                "rule_key": "RULE_UNAUTH",
                "name": "Should Fail",
                "domain": "clinical",
                "dimension": "completeness",
                "rule_type": "required",
                "target_entity_type": "patient",
                "target_field_path": "phone"
            })


if __name__ == "__main__":
    unittest.main()

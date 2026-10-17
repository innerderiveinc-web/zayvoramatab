"""Unit tests for Clinical Knowledge Governance, Rule Versioning & Controlled Safety-Rule Release Engine.

Phase 28 validation for ZAYVORA MATAB OS.
Enforces non-negotiables:
1. Never fabricate clinical knowledge or governance evidence.
2. No direct-to-production clinical changes (must pass formal lifecycle states).
3. No automatic approval by AI (AI can propose, but cannot approve/activate).
4. Separate artifact approval from deployment; separate technical validity from clinical validity.
5. Preserve provenance, explicit scope, and immutable content hashes.
6. Keep old records interpretable; no retroactive rewrites of clinical records.
7. Production disable/rollback must be tested and verified.
"""

import os
import unittest
import tempfile
import sqlite3
import uuid
import json
from datetime import datetime

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.governance import ClinicalKnowledgeGovernanceEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestClinicalKnowledgeGovernanceEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_gov.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = ClinicalKnowledgeGovernanceEngine(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin = cur.fetchone()
        cls.admin_id = admin["id"]
        cls.org_id = admin["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.fac_id = cur.fetchone()["id"]

        cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.patient_id = cur.fetchone()["id"]

        conn.execute("""
            INSERT OR IGNORE INTO users (id, organization_id, username, password_hash, full_name, is_active)
            VALUES ('usr-author-1', ?, 'author_user', 'hash123', 'Author User', 1);
        """, (cls.org_id,))
        conn.commit()

        conn.close()

        cls.admin_user = {
            "user_id": cls.admin_id,
            "roles": ["ORG_ADMIN"],
            "permissions": ["governance:read", "governance:draft", "governance:review", "governance:validate", "governance:release", "governance:manage"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

        cls.clinical_reviewer = {
            "user_id": "usr-hakeem-1",
            "roles": ["CLINICAL_DOMAIN_REVIEWER"],
            "permissions": ["governance:read", "governance:review"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

        cls.rule_author = {
            "user_id": "usr-author-1",
            "roles": ["SAFETY_REVIEWER"],
            "permissions": ["governance:read", "governance:draft"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

    # --------------------------------------------------------------------------
    # Test 1: Artifact Lifecycle Envelope & Version Hashing
    # --------------------------------------------------------------------------
    def test_artifact_lifecycle_envelope_and_draft_isolation(self):
        art_data = {
            "artifact_type": "safety_rule",
            "stable_key": "RULE-SCHEDULE-E1-DETOX-CHECK",
            "title": "Schedule E(1) Hazardous Herb Mudabbar Detoxification Validation",
            "owner_role": "SAFETY_REVIEWER",
            "owning_domain": "HERBAL_TOXICOLOGY",
            "intended_use": "Enforce Mudabbar processing verification before signing Schedule E(1) prescriptions",
            "criticality_class": "REGULATORY_SAFETY",
            "initial_payload": {
                "herb_code": "ASU-E1-001",
                "mudabbar_required": True,
                "action": "BLOCK_IF_UNPROCESSED"
            }
        }

        art = self.engine.create_artifact(art_data, self.rule_author)
        self.assertIsNotNone(art["id"])
        self.assertEqual(art["stable_key"], "RULE-SCHEDULE-E1-DETOX-CHECK")
        self.assertEqual(art["current_lifecycle_state"], "DRAFT")
        self.assertEqual(len(art["versions"]), 1)

        v1 = art["versions"][0]
        self.assertIsNotNone(v1["payload_manifest_hash"])
        self.assertEqual(v1["version_label"], "1.0.0")

    # --------------------------------------------------------------------------
    # Test 2: Separation of Duties & Self-Approval Prevention
    # --------------------------------------------------------------------------
    def test_author_cannot_self_approve_high_impact_clinical_rules(self):
        art = self.engine.create_artifact({
            "artifact_type": "clinical_rule",
            "stable_key": "RULE-PREGNANCY-SUROOR-CONTRAINDICATION",
            "title": "Pregnancy Emmenagogue Contraindication Rule",
            "owner_role": "CLINICAL_GOVERNANCE_OWNER",
            "owning_domain": "GYNECOLOGY_UNANI",
            "intended_use": "Block strong emmenagogues during first trimester",
            "criticality_class": "CLINICAL_BEHAVIOR",
            "initial_payload": {"condition": "pregnancy", "action": "BLOCK"}
        }, self.rule_author)

        v1_id = art["versions"][0]["id"]

        # Author attempts to self-approve -> ForbiddenError
        with self.assertRaises(ForbiddenError):
            self.engine.transition_version_state(v1_id, {
                "next_state": "REVIEW_APPROVED",
                "rationale": "I authored this and I approve it myself."
            }, self.rule_author)

        # Independent clinical domain reviewer approves -> Succeeds
        approved = self.engine.transition_version_state(v1_id, {
            "next_state": "REVIEW_APPROVED",
            "rationale": "Independent clinical review against CCRUM pregnancy safety monographs passed."
        }, self.clinical_reviewer)
        self.assertEqual(approved["lifecycle_state"], "REVIEW_APPROVED")

    # --------------------------------------------------------------------------
    # Test 3: Declarative Clinical Rule & Sandboxed Test Execution
    # --------------------------------------------------------------------------
    def test_governed_clinical_rule_sandboxed_test_execution(self):
        rule = self.engine.create_clinical_rule({
            "stable_key": "RULE-PEDIATRIC-OPIATE-BLOCKER",
            "title": "Afiyun (Opium) Pediatric Age Safety Blocker",
            "rule_purpose": "Prevent prescribing raw or unformulated Afiyun to patients under 12 years",
            "clinical_domain": "PEDIATRICS_AND_SAFETY",
            "rule_type": "CONTRAINDICATION_CHECK",
            "condition_expression": {
                "field": "patient_age_years",
                "operator": "LESS_THAN",
                "value": 12
            },
            "output_state_and_message": {
                "state": "triggered",
                "message": "Afiyun and derivatives are strictly contraindicated in pediatric patients under 12."
            },
            "criticality_priority": "CRITICAL",
            "is_blocking": True,
            "test_fixtures": [
                {
                    "name": "Underage 8yo Child Test",
                    "input": {"patient_age_years": 8},
                    "expected_state": "triggered"
                },
                {
                    "name": "Adult 35yo Patient Test",
                    "input": {"patient_age_years": 35},
                    "expected_state": "not_triggered_within_scope"
                }
            ]
        }, self.admin_user)

        self.assertIsNotNone(rule["id"])
        self.assertEqual(rule["stable_key"], "RULE-PEDIATRIC-OPIATE-BLOCKER")

        # Run sandboxed test executions
        test_summary = self.engine.execute_rule_tests(rule["id"], self.admin_user)
        self.assertEqual(test_summary["total_fixtures"], 2)
        self.assertEqual(test_summary["passed"], 2)
        self.assertEqual(test_summary["failed"], 0)
        self.assertTrue(test_summary["all_passed"])

    # --------------------------------------------------------------------------
    # Test 4: Dependency and Impact Analysis
    # --------------------------------------------------------------------------
    def test_dependency_and_impact_analysis(self):
        art = self.engine.create_artifact({
            "artifact_type": "clinical_rule",
            "stable_key": "RULE-LIVER-DISORDER-ALOE-WARNING",
            "title": "Hepatic Dysfunction Elva / Sibr Warning",
            "owner_role": "CLINICAL_GOVERNANCE_OWNER",
            "owning_domain": "HEPATOLOGY",
            "intended_use": "Flag potential bile stimulation in acute jaundice",
            "criticality_class": "CLINICAL_BEHAVIOR",
            "initial_payload": {"herb": "Sibr_Zard", "level": "WARN"}
        }, self.admin_user)

        v_id = art["versions"][0]["id"]
        impact = self.engine.analyze_impact(v_id, self.admin_user)
        self.assertIsNotNone(impact["impact_id"])
        self.assertEqual(impact["artifact_key"], "RULE-LIVER-DISORDER-ALOE-WARNING")
        self.assertIn("/api/v1/clinical/cds/evaluate", impact["dependent_apis"])

    # --------------------------------------------------------------------------
    # Test 5: Immutable Release Assembly and Manifest Hash Binding
    # --------------------------------------------------------------------------
    def test_immutable_release_assembly_and_hash_binding(self):
        # Create and approve an artifact
        art = self.engine.create_artifact({
            "artifact_type": "canonical_concept",
            "stable_key": "CONCEPT-MIZAJ-DAMVI",
            "title": "Damvi (Sanguine) Mizaj Canonical Concept Definition",
            "owner_role": "TERMINOLOGY_REVIEWER",
            "owning_domain": "UNANI_ONTOLOGY",
            "intended_use": "Canonical definition of hot-moist temperament",
            "criticality_class": "TERMINOLOGY_IDENTITY",
            "initial_payload": {"mizaj": "Damvi", "qualities": ["HOT", "MOIST"]}
        }, self.admin_user)

        v_id = art["versions"][0]["id"]
        self.engine.transition_version_state(v_id, {
            "next_state": "REVIEW_APPROVED",
            "rationale": "Verified against Kulliyat-e-Qanoon Chapter 1."
        }, self.clinical_reviewer)

        # Assemble release manifest
        rel = self.engine.create_release({
            "release_tag": "REL-2026-OCT-KNOWLEDGE-V1",
            "environment": "STAGING",
            "artifact_version_ids": [v_id],
            "change_summary": "Initial canonical Mizaj ontology package"
        }, self.admin_user)

        self.assertIsNotNone(rel["id"])
        self.assertEqual(rel["release_tag"], "REL-2026-OCT-KNOWLEDGE-V1")
        self.assertEqual(rel["is_active"], 0)
        self.assertIsNotNone(rel["manifest_hash"])
        self.assertEqual(len(rel["manifest"]), 1)

    # --------------------------------------------------------------------------
    # Test 6: Release Approval & Deployment with Runtime Verification
    # --------------------------------------------------------------------------
    def test_release_approval_and_deployment_with_runtime_verification(self):
        art = self.engine.create_artifact({
            "artifact_type": "safety_rule",
            "stable_key": "RULE-INTERACTION-WARFARIN-GUGGAL",
            "title": "Warfarin and Muqil (Guggul) Antiplatelet Interaction Rule",
            "owner_role": "SAFETY_REVIEWER",
            "owning_domain": "HERB_DRUG_INTERACTIONS",
            "intended_use": "Prevent concomitant prescribing due to bleeding risk",
            "criticality_class": "REGULATORY_SAFETY",
            "initial_payload": {"drug": "Warfarin", "herb": "Commiphora_mukul", "severity": "BLOCK"}
        }, self.admin_user)

        v_id = art["versions"][0]["id"]
        self.engine.transition_version_state(v_id, {
            "next_state": "REVIEW_APPROVED",
            "rationale": "Pharmacological documentation of CYP2C9 and additive anticoagulant action."
        }, self.clinical_reviewer)

        rel = self.engine.create_release({
            "release_tag": "REL-2026-OCT-SAFETY-INTERACTIONS",
            "environment": "PRODUCTION",
            "artifact_version_ids": [v_id],
            "change_summary": "Herb-Drug Safety Interaction Release"
        }, self.admin_user)

        # Attempt deploy without approval -> ForbiddenError
        with self.assertRaises(ForbiddenError):
            self.engine.deploy_release(rel["id"], {}, self.admin_user)

        # Approve release
        approved_rel = self.engine.approve_release(rel["id"], {
            "rationale": "Clinical safety director signoff for Q4 production deployment."
        }, self.admin_user)
        self.assertEqual(len(approved_rel["approvals"]), 1)

        # Deploy release -> Runtime verification succeeds and marks ACTIVE
        deployed_rel = self.engine.deploy_release(rel["id"], {}, self.admin_user)
        self.assertEqual(deployed_rel["is_active"], 1)
        self.assertEqual(deployed_rel["runtime_verification_status"], "VERIFIED_MATCH")
        self.assertIsNotNone(deployed_rel["deployed_at"])

        # Check member artifact version is now ACTIVE
        updated_art = self.engine.get_artifact(art["id"], self.admin_user)
        self.assertEqual(updated_art["current_lifecycle_state"], "ACTIVE")

    # --------------------------------------------------------------------------
    # Test 7: Fail-Closed Protection Against Tampered Manifest
    # --------------------------------------------------------------------------
    def test_fail_closed_on_manifest_tampering(self):
        art = self.engine.create_artifact({
            "artifact_type": "clinical_rule",
            "stable_key": "RULE-TAMPER-TEST",
            "title": "Tamper Test Rule",
            "owner_role": "CLINICAL_GOVERNANCE_OWNER",
            "owning_domain": "AUDIT",
            "intended_use": "Tamper integrity validation",
            "criticality_class": "CLINICAL_BEHAVIOR",
            "initial_payload": {"test": 1}
        }, self.admin_user)

        v_id = art["versions"][0]["id"]
        self.engine.transition_version_state(v_id, {
            "next_state": "REVIEW_APPROVED",
            "rationale": "Reviewed"
        }, self.clinical_reviewer)

        rel = self.engine.create_release({
            "release_tag": "REL-TAMPER-TEST",
            "environment": "STAGING",
            "artifact_version_ids": [v_id],
            "change_summary": "Tamper test release"
        }, self.admin_user)

        self.engine.approve_release(rel["id"], {"rationale": "Approved"}, self.admin_user)

        # Maliciously modify the stored manifest_hash in database to simulate tampering
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE governance_releases SET manifest_hash = 'TAMPERED_FAKE_HASH_1234' WHERE id = ?;", (rel["id"],))
        conn.commit()
        conn.close()

        # Attempt deployment -> Must fail closed!
        with self.assertRaises(ValidationError):
            self.engine.deploy_release(rel["id"], {}, self.admin_user)

        tampered_rel = self.engine.get_release(rel["id"], self.admin_user)
        self.assertEqual(tampered_rel["runtime_verification_status"], "HASH_MISMATCH")
        self.assertEqual(tampered_rel["is_active"], 0)

    # --------------------------------------------------------------------------
    # Test 8: Emergency Suspension Kill-Switch
    # --------------------------------------------------------------------------
    def test_emergency_suspension_kill_switch(self):
        art = self.engine.create_artifact({
            "artifact_type": "safety_rule",
            "stable_key": "RULE-EMERGENCY-SUSPEND-TEST",
            "title": "Rule to be suspended",
            "owner_role": "SAFETY_REVIEWER",
            "owning_domain": "SAFETY",
            "intended_use": "Suspension test",
            "criticality_class": "REGULATORY_SAFETY",
            "initial_payload": {"flag": True}
        }, self.admin_user)

        v_id = art["versions"][0]["id"]
        self.engine.transition_version_state(v_id, {"next_state": "REVIEW_APPROVED", "rationale": "OK"}, self.clinical_reviewer)

        rel = self.engine.create_release({
            "release_tag": "REL-SUSPEND-TEST",
            "environment": "PRODUCTION",
            "artifact_version_ids": [v_id],
            "change_summary": "Release to test kill switch"
        }, self.admin_user)

        self.engine.approve_release(rel["id"], {"rationale": "OK"}, self.admin_user)
        self.engine.deploy_release(rel["id"], {}, self.admin_user)

        # Execute emergency suspension
        suspended = self.engine.suspend_release(rel["id"], {
            "suspension_reason": "Urgent safety alert from Ministry of Ayush requiring immediate rule pause."
        }, self.admin_user)

        self.assertEqual(suspended["is_active"], 0)
        self.assertIsNotNone(suspended["suspended_at"])
        self.assertIn("Urgent safety alert", suspended["suspension_reason"])

    # --------------------------------------------------------------------------
    # Test 9: Tested Rollback Restores Prior Release
    # --------------------------------------------------------------------------
    def test_tested_rollback_restores_prior_release(self):
        # Create Release A
        art_a = self.engine.create_artifact({
            "artifact_type": "canonical_concept",
            "stable_key": "CONCEPT-ROLLBACK-A",
            "title": "Concept Version A",
            "owner_role": "TERMINOLOGY_REVIEWER",
            "owning_domain": "ONTOLOGY",
            "intended_use": "Version A",
            "criticality_class": "EDITORIAL",
            "initial_payload": {"ver": "A"}
        }, self.admin_user)
        v_a = art_a["versions"][0]["id"]
        self.engine.transition_version_state(v_a, {"next_state": "REVIEW_APPROVED", "rationale": "OK"}, self.clinical_reviewer)

        rel_a = self.engine.create_release({
            "release_tag": "REL-ROLLBACK-V1",
            "environment": "PRODUCTION",
            "artifact_version_ids": [v_a],
            "change_summary": "Release A"
        }, self.admin_user)
        self.engine.approve_release(rel_a["id"], {"rationale": "OK"}, self.admin_user)
        self.engine.deploy_release(rel_a["id"], {}, self.admin_user)

        # Create Release B
        art_b = self.engine.create_artifact({
            "artifact_type": "canonical_concept",
            "stable_key": "CONCEPT-ROLLBACK-B",
            "title": "Concept Version B",
            "owner_role": "TERMINOLOGY_REVIEWER",
            "owning_domain": "ONTOLOGY",
            "intended_use": "Version B",
            "criticality_class": "EDITORIAL",
            "initial_payload": {"ver": "B"}
        }, self.admin_user)
        v_b = art_b["versions"][0]["id"]
        self.engine.transition_version_state(v_b, {"next_state": "REVIEW_APPROVED", "rationale": "OK"}, self.clinical_reviewer)

        rel_b = self.engine.create_release({
            "release_tag": "REL-ROLLBACK-V2",
            "environment": "PRODUCTION",
            "artifact_version_ids": [v_b],
            "change_summary": "Release B (defective)"
        }, self.admin_user)
        self.engine.approve_release(rel_b["id"], {"rationale": "OK"}, self.admin_user)
        self.engine.deploy_release(rel_b["id"], {}, self.admin_user)

        # Roll back from Release B to Release A
        rolled_back_target = self.engine.rollback_release(rel_b["id"], {
            "target_release_id": rel_a["id"]
        }, self.admin_user)

        self.assertEqual(rolled_back_target["id"], rel_a["id"])
        self.assertEqual(rolled_back_target["is_active"], 1)

        # Confirm Release B is deactivated and tagged rolled back
        rel_b_check = self.engine.get_release(rel_b["id"], self.admin_user)
        self.assertEqual(rel_b_check["is_active"], 0)
        self.assertEqual(rel_b_check["rollback_target_release_id"], rel_a["id"])
        self.assertIsNotNone(rel_b_check["rolled_back_at"])

    # --------------------------------------------------------------------------
    # Test 10: Runtime Version Resolution Pins Historical Encounter
    # --------------------------------------------------------------------------
    def test_runtime_version_resolution_pins_historical_encounter(self):
        # Create and deploy an active release
        art = self.engine.create_artifact({
            "artifact_type": "clinical_rule",
            "stable_key": "RULE-PINNING-TEST",
            "title": "Pinning Test Rule",
            "owner_role": "CLINICAL_GOVERNANCE_OWNER",
            "owning_domain": "GOVERNANCE",
            "intended_use": "Encounter pinning test",
            "criticality_class": "CLINICAL_BEHAVIOR",
            "initial_payload": {"rule": "active"}
        }, self.admin_user)
        v_id = art["versions"][0]["id"]
        self.engine.transition_version_state(v_id, {"next_state": "REVIEW_APPROVED", "rationale": "OK"}, self.clinical_reviewer)
        rel = self.engine.create_release({
            "release_tag": "REL-PINNING-PROD-V1",
            "environment": "PRODUCTION",
            "artifact_version_ids": [v_id],
            "change_summary": "Active production release for pinning"
        }, self.admin_user)
        self.engine.approve_release(rel["id"], {"rationale": "Approved"}, self.admin_user)
        self.engine.deploy_release(rel["id"], {}, self.admin_user)

        encounter_id = f"enc-gov-{uuid.uuid4().hex[:8]}"
        resolution = self.engine.resolve_runtime_versions(encounter_id, "CONSULTATION_PRESCRIPTION_SIGN", self.admin_user)
        self.assertIsNotNone(resolution["resolution_id"])
        self.assertEqual(resolution["encounter_id"], encounter_id)
        self.assertIsNotNone(resolution["release_tag"])
        self.assertIsNotNone(resolution["manifest_hash"])


if __name__ == "__main__":
    unittest.main()

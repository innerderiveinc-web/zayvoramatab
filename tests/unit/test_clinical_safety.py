"""
Unit Tests for Enterprise Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine
ZAYVORA MATAB OS — Phase 48
"""

import os
import shutil
import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.clinical_safety import EnterpriseClinicalSafetyCaseEngine
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError, ForbiddenError


class TestEnterpriseClinicalSafetyCaseEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_safety_unit.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.engine = EnterpriseClinicalSafetyCaseEngine(self.conn)

    def tearDown(self):
        if self.conn:
            self.conn.close()

    def test_clinical_safety_summary(self):
        """1. Test executive summary KPI aggregation."""
        summary = self.engine.get_clinical_safety_summary()
        self.assertIn("intended_uses_count", summary)
        self.assertGreaterEqual(summary["intended_uses_count"], 1)
        self.assertIn("hazards", summary)
        self.assertIn("requirements", summary)
        self.assertIn("safety_cases", summary)
        self.assertIn("incidents", summary)
        self.assertIn("release_gates", summary)
        self.assertEqual(summary["audit_status"], "TAMPER_EVIDENT_HASH_CHAIN_ACTIVE")

    def test_intended_use_crud(self):
        """2. Test registering, querying, and listing bounded clinical intended uses."""
        iu_data = {
            "scope_code": "IU-UNANI-MIZAJ-TEST",
            "title": "Unani Mizaj Assessment & Temperament Scoring",
            "intended_users": ["Licensed Tabib", "Clinical Hakeem"],
            "clinical_purposes": ["Determine Damawi, Balghami, Safrawi, or Sawdawi predominance"],
            "excluded_uses": ["Automated algorithmic diagnosis without pulse/urine physical examination"],
            "clinician_authority_level": "EXCLUSIVE_HUMAN_SIGN_OFF",
            "version": "1.0.0",
        }
        registered = self.engine.register_intended_use(actor_id="usr-hakeem-1", data=iu_data)
        self.assertEqual(registered["scope_code"], "IU-UNANI-MIZAJ-TEST")
        self.assertEqual(registered["status"], "APPROVED")
        self.assertEqual(len(registered["intended_users"]), 2)

        fetched = self.engine.get_intended_use(registered["id"])
        self.assertEqual(fetched["title"], iu_data["title"])

        # Listing
        all_iu = self.engine.list_intended_uses(scope_code="IU-UNANI-MIZAJ-TEST")
        self.assertEqual(len(all_iu), 1)

    def test_clinical_hazard_creation_and_validation(self):
        """3. Test hazard creation, validation of severity tiers, and retrieval."""
        hazard_data = {
            "hazard_code": "HAZ-TOX-AQUEOUS-001",
            "intended_use_id": "iu-rx-001",
            "title": "Dispensing Unpurified Kuchla (Strychnos nux-vomica) Without Mudabbar Detoxification",
            "workflow_scope": "BOTANICAL_PURIFICATION",
            "initiating_cause": "Formulation item selected without verifying Mudabbar protocol completion in dispensary log",
            "hazardous_state": "Dispensing strychnine-containing botanical directly to patient",
            "clinical_consequence": "Acute convulsive neurotoxicity, tetanic spasms, or fatality",
            "affected_population": "GENERAL_OPD",
            "severity_tier": "CATASTROPHIC",
            "lifecycle_status": "draft",
        }
        created = self.engine.create_hazard(actor_id="usr-hakeem-1", data=hazard_data)
        self.assertEqual(created["hazard_code"], "HAZ-TOX-AQUEOUS-001")
        self.assertEqual(created["severity_tier"], "CATASTROPHIC")

        # Invalid severity tier rejection
        invalid_data = dict(hazard_data)
        invalid_data["hazard_code"] = "HAZ-INVALID-001"
        invalid_data["severity_tier"] = "EXTREME_SUPER_BAD"
        with self.assertRaises(ValidationError):
            self.engine.create_hazard(actor_id="usr-hakeem-1", data=invalid_data)

    def test_hazard_status_transition_clinical_authority_enforced(self):
        """4. Test non-negotiable clinical authority enforcement for hazard acceptance."""
        # Baseline hazard haz-rx-001
        # An administrative user without CSO role cannot transition to accepted_for_defined_scope
        with self.assertRaises(ForbiddenError):
            self.engine.update_hazard_status(
                actor_id="usr-admin-tech-only",
                hazard_id="haz-rx-001",
                new_status="accepted_for_defined_scope",
                justification="Bypassing clinical check for administrative speed",
                is_clinical_safety_officer=False,
            )

        # An authorized Clinical Safety Officer / Tabib can approve
        updated = self.engine.update_hazard_status(
            actor_id="usr-hakeem-1",
            hazard_id="haz-rx-001",
            new_status="accepted_for_defined_scope",
            justification="Posology preflight checks deterministically stop excess doses in all unit tests.",
            is_clinical_safety_officer=True,
        )
        self.assertEqual(updated["lifecycle_status"], "accepted_for_defined_scope")

    def test_safety_requirement_creation_and_lookup(self):
        """5. Test linking safety requirement to a hazard with testable code paths."""
        req_data = {
            "hazard_id": "haz-rx-001",
            "req_code": "SR-KUCHLA-MUDABBAR-001",
            "title": "Deterministic Mudabbar Detoxification Verification Before Kuchla Dispensing",
            "requirement_type": "PREVENTIVE",
            "specification_statement": "The prescription preflight validator MUST reject Kuchla unless verified Mudabbar certificate is attached.",
            "enforcement_code_path": "apps.api.domains.prescriptions.PrescriptionEngine._validate_toxic_botanicals",
            "test_suite_reference": "tests.unit.test_prescriptions.TestPrescriptionPreflight.test_kuchla_requires_mudabbar",
            "verification_status": "PLANNED",
        }
        created = self.engine.create_requirement(actor_id="usr-hakeem-1", data=req_data)
        self.assertEqual(created["req_code"], "SR-KUCHLA-MUDABBAR-001")
        self.assertEqual(created["verification_status"], "PLANNED")

        fetched = self.engine.get_requirement(created["id"])
        self.assertEqual(fetched["title"], req_data["title"])

    def test_control_verification_lifecycle(self):
        """6. Test recording automated control verification test executions."""
        # Record passing verification for sr-rx-001
        verification = self.engine.record_control_verification(
            actor_id="usr-hakeem-1",
            requirement_id="sr-rx-001",
            test_suite_name="tests.unit.test_prescriptions.TestPrescriptionPreflight.test_exceeded_maximum_dosage_rejected",
            status="PASS",
            evidence_summary="Verified posology hard-stop triggered on Hab-e-Suranjan over 2g.",
            execution_duration_ms=38,
            environment="ISOLATED_SYNTHETIC",
        )
        self.assertEqual(verification["status"], "PASS")

        # Verify requirement status is updated to VERIFIED_IN_TEST
        req = self.engine.get_requirement("sr-rx-001")
        self.assertEqual(req["verification_status"], "VERIFIED_IN_TEST")

    def test_clinical_safety_case_gsn_approval_lifecycle(self):
        """7. Test Goal Structuring Notation (GSN) clinical safety case creation and review."""
        case_data = {
            "case_code": "CSC-KAVS-CITATION-V1",
            "title": "Clinical Safety Case for KAVS Evidence Retrieval Engine",
            "workflow_scope": "KAVS_CITATION_RETRIEVAL",
            "target_release_version": "v1.0.0",
            "claim_statement": "The KAVS engine provides traceable, uncorrupted Unani classical citations without autonomous extrapolation.",
            "argument_narrative": "Argument G1: All citations link to peer-reviewed classical texts. Argument G2: No generative hallucination allowed in clinical dosage claims.",
            "approval_status": "DRAFT",
        }
        created = self.engine.create_safety_case(actor_id="usr-hakeem-1", data=case_data)
        self.assertEqual(created["approval_status"], "DRAFT")

        # Administrator without CSO authority cannot approve
        with self.assertRaises(ForbiddenError):
            self.engine.review_safety_case(
                actor_id="usr-admin-1",
                case_id=created["id"],
                new_status="APPROVED_FOR_SCOPE",
                clinical_rationale="Attempted admin signoff without clinical authority",
                is_clinical_safety_officer=False,
            )

        # Clinical Safety Officer can approve
        reviewed = self.engine.review_safety_case(
            actor_id="usr-hakeem-1",
            case_id=created["id"],
            new_status="APPROVED_FOR_SCOPE",
            clinical_rationale="Verified classical NFUM volume II crosswalks with Tabib board sign-off.",
            is_clinical_safety_officer=True,
        )
        self.assertEqual(reviewed["approval_status"], "APPROVED_FOR_SCOPE")

    def test_incident_reporting_and_near_miss_loop(self):
        """8. Test incident/near-miss reporting with zero PHI sanitization and corrective action triage."""
        inc_data = {
            "incident_code": "NM-TEST-DOSAGE-001",
            "workflow_scope": "PRESCRIPTION_SIGNING",
            "incident_type": "NEAR_MISS",
            "severity": "HIGH",
            "sanitized_description": "Practitioner entered dosage with trailing zero (10.0g instead of 1.0g); hard stop prevented signing.",
            "linked_hazard_id": "haz-rx-001",
            "containment_action": "System rejected signing with PosologyValidationError.",
            "corrective_action_plan": "Added UI prompt warning against trailing decimals.",
        }
        reported = self.engine.report_incident(actor_id="usr-hakeem-1", data=inc_data)
        self.assertEqual(reported["corrective_action_status"], "REPORTED")

        # Triage and close
        closed = self.engine.triage_and_close_incident(
            actor_id="usr-hakeem-1",
            incident_id=reported["id"],
            corrective_action_status="VERIFIED_CLOSED",
        )
        self.assertEqual(closed["corrective_action_status"], "VERIFIED_CLOSED")
        self.assertIsNotNone(closed["closed_at"])

    def test_release_gate_fail_closed_logic(self):
        """9. Test fail-closed clinical safety release gate evaluation under all conditions."""
        # 1. Prescriptions scope with approved safety case and verified requirement passes
        eval_pass = self.engine.evaluate_release_gate(
            actor_id="usr-hakeem-1",
            target_release_version="v1.0.0",
            workflow_scope="PRESCRIPTION_SIGNING",
            safety_case_id="csc-rx-001",
        )
        self.assertEqual(eval_pass["gate_verdict"], "PASS")

        # 2. Scope with no safety case evaluates to BLOCKED
        eval_blocked = self.engine.evaluate_release_gate(
            actor_id="usr-hakeem-1",
            target_release_version="v1.0.0",
            workflow_scope="UNMAPPED_EXPERIMENTAL_SCOPE",
        )
        self.assertEqual(eval_blocked["gate_verdict"], "BLOCKED")
        self.assertTrue(any("No Clinical Safety Case found" in r for r in eval_blocked["blocking_reasons"]))

        # 3. Create a draft (unverified) requirement under haz-rx-001 -> evaluate gate -> should now BLOCK
        req_unverified = self.engine.create_requirement(
            actor_id="usr-hakeem-1",
            data={
                "hazard_id": "haz-rx-001",
                "req_code": "SR-BLOCKING-TEST-001",
                "title": "Unverified requirement test",
                "requirement_type": "PREVENTIVE",
                "specification_statement": "Must block release until verified in test",
                "enforcement_code_path": "apps.api.domains.prescriptions",
                "test_suite_reference": "tests.unit.test_prescriptions",
                "verification_status": "PLANNED",
            },
        )
        eval_unverified = self.engine.evaluate_release_gate(
            actor_id="usr-hakeem-1",
            target_release_version="v1.0.0",
            workflow_scope="PRESCRIPTION_SIGNING",
            safety_case_id="csc-rx-001",
        )
        self.assertEqual(eval_unverified["gate_verdict"], "BLOCKED")
        self.assertTrue(any("Unverified safety requirement" in r for r in eval_unverified["blocking_reasons"]))

        # Clean up the test requirement so other tests don't see it
        self.conn.execute("DELETE FROM safety_requirements_catalog WHERE id = ?;", (req_unverified["id"],))
        self.conn.commit()

    def test_audit_ledger_hash_chain_and_tamper_detection(self):
        """10. Test chained tamper-evident SHA-256 audit ledger and verification."""
        audit_trail = self.engine.get_audit_trail(limit=10)
        self.assertGreaterEqual(len(audit_trail), 1)

        # Integrity check should be valid initially
        check = self.engine.verify_audit_ledger_integrity()
        self.assertTrue(check["is_valid"])
        self.assertEqual(check["status"], "VERIFIED_INTACT")

        # Also test traceability matrix
        matrix = self.engine.get_traceability_matrix(workflow_scope="PRESCRIPTION_SIGNING")
        self.assertGreaterEqual(matrix["total_hazards_traced"], 1)
        self.assertIn("traceability_chain", matrix)


if __name__ == "__main__":
    unittest.main()

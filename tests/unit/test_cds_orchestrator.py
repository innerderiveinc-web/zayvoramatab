"""Unit Tests for Clinical Decision Support (CDS) Orchestrator & Clinician Approval Workflow.

Phase 23 Verification Suite for ZAYVORA MATAB OS.
Verifies:
- Governed policy registry retrieval
- Encounter context resolution with missing facts detection
- State machine transition rules & illegal transition rejection
- Governed CDS execution & typed card synthesis
- Attributable clinician review capture (accept, reject, mark N/A)
- 6-Dimension readiness gate evaluation
- Cryptographic PIN-verified clinical sign-off
- Post-signature formal amendment workflow
- Emergency administrative kill switch controls
"""

import os
import unittest
import sqlite3
import json
import uuid
from datetime import datetime, timezone

from apps.api.database.connection import DatabaseConnection
from apps.api.domains.cds_orchestrator import CDSOrchestratorEngine
from apps.api.core.security import hash_pin
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
    SafetyBlockedError
)


class TestCDSOrchestratorUnit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = f"test_cds_unit_{uuid.uuid4().hex[:8]}.db"
        from apps.api.database.migrator import run_migrations
        run_migrations(cls.db_path)

        cls.engine = CDSOrchestratorEngine(cls.db_path)
        cls.db_manager = DatabaseConnection(cls.db_path)

        # Seed test organization, facility, clinician user, and patient
        conn = cls.db_manager.get_connection()
        cur = conn.cursor()
        cls.org_id = "org-test-cds"
        cls.fac_id = "fac-test-cds"
        cls.user_id = "usr-clinician-1"
        cls.patient_id = "pat-test-1"

        cur.execute("INSERT OR IGNORE INTO organizations (id, name, code) VALUES (?, 'Test Org', 'TORG');", (cls.org_id,))
        cur.execute("INSERT OR IGNORE INTO facilities (id, organization_id, name, code) VALUES (?, ?, 'Main Clinic', 'MCLN');", (cls.fac_id, cls.org_id))
        cur.execute("""
            INSERT OR IGNORE INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, 'hakeem1', 'hakeem1@matab.test', 'pwdhash', 'Hakeem Ahmad', 1);
        """, (cls.user_id, cls.org_id))
        cur.execute("""
            INSERT OR IGNORE INTO practitioner_profiles (id, user_id, license_type, registration_number, digital_signature_pin_hash)
            VALUES (?, ?, 'BUMS', 'REG-12345', ?);
        """, (f"prof-{cls.user_id}", cls.user_id, hash_pin("1234")))
        cur.execute("""
            INSERT OR IGNORE INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, estimated_age, sex, status)
            VALUES (?, ?, ?, 'MRN-CDS-001', 'Zayd', 'Zayd bin Tariq', 42, 'MALE', 'ACTIVE');
        """, (cls.patient_id, cls.org_id, cls.fac_id))


        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        for ext in ("", "-shm", "-wal"):
            f = cls.db_path + ext
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass

    def _create_encounter(self, initial_status="scheduled") -> str:
        conn = self.db_manager.get_connection()
        cur = conn.cursor()
        enc_id = f"enc-{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?);
        """, (enc_id, self.org_id, self.fac_id, self.patient_id, self.user_id, initial_status, self.user_id))
        conn.commit()
        conn.close()
        return enc_id

    # --------------------------------------------------------------------------
    # Test 1: Policy Registry
    # --------------------------------------------------------------------------
    def test_01_policy_registry_listing(self):
        policies = self.engine.list_policies()
        self.assertGreaterEqual(len(policies), 8)
        codes = [p["policy_code"] for p in policies]
        self.assertIn("POL-ALLERGY-CHECK", codes)
        self.assertIn("POL-POSOLOGY-RANGE", codes)
        self.assertIn("POL-RESTRICTED-ACTION", codes)

        p = self.engine.get_policy("POL-ALLERGY-CHECK")
        self.assertEqual(p["severity_default"], "BLOCKER")
        self.assertEqual(p["trigger_event"], "PRE_PRESCRIPTION")

    # --------------------------------------------------------------------------
    # Test 2: Encounter Context Resolution & Missing Facts
    # --------------------------------------------------------------------------
    def test_02_resolve_encounter_context_missing_facts(self):
        enc_id = self._create_encounter()
        ctx = self.engine.resolve_encounter_context(
            enc_id,
            user_ctx={"organization_id": self.org_id, "user_id": self.user_id}
        )
        self.assertEqual(ctx["encounter_id"], enc_id)
        self.assertEqual(ctx["encounter_version"], 1)
        self.assertEqual(ctx["patient"]["display_name"], "Zayd bin Tariq")
        # Allergies and chief complaint not yet recorded
        self.assertGreaterEqual(len(ctx["missing_facts"]), 1)
        self.assertTrue(any("Allergies not explicitly documented" in f for f in ctx["missing_facts"]))

    # --------------------------------------------------------------------------
    # Test 3: State Machine Allowed Transitions
    # --------------------------------------------------------------------------
    def test_03_state_machine_valid_transitions(self):
        enc_id = self._create_encounter("scheduled")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        # scheduled -> arrived
        res1 = self.engine.transition_encounter_state(enc_id, "arrived", self.user_id, "Patient checked in at OPD", user_ctx)
        self.assertEqual(res1["to_state"], "arrived")
        self.assertEqual(res1["new_version"], 2)

        # arrived -> in_consultation
        res2 = self.engine.transition_encounter_state(enc_id, "in_consultation", self.user_id, "Doctor called token", user_ctx)
        self.assertEqual(res2["to_state"], "in_consultation")
        self.assertEqual(res2["new_version"], 3)

    # --------------------------------------------------------------------------
    # Test 4: State Machine Illegal Transition Blocked
    # --------------------------------------------------------------------------
    def test_04_state_machine_illegal_transition_rejection(self):
        enc_id = self._create_encounter("scheduled")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        # Attempt illegal skip: scheduled -> signed directly
        with self.assertRaises(ConflictError):
            self.engine.transition_encounter_state(enc_id, "signed", self.user_id, "Direct skip", user_ctx)

    # --------------------------------------------------------------------------
    # Test 5: Governed CDS Run & Typed Cards Synthesis
    # --------------------------------------------------------------------------
    def test_05_execute_cds_run_synthesizes_typed_cards(self):
        enc_id = self._create_encounter("in_consultation")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        run_res = self.engine.execute_cds_run(enc_id, "FULL_ENCOUNTER", user_ctx)
        self.assertEqual(run_res["run_state"], "completed")
        self.assertGreaterEqual(run_res["cards_generated"], 1)

        cards = run_res["cards"]
        card_types = [c["card_type"] for c in cards]
        self.assertIn("missing_information_prompt", card_types)

        # Verify card structure
        card = cards[0]
        self.assertIn("triggering_inputs", card)
        self.assertIn("limitations", card)
        self.assertEqual(card["review_status"], "not_reviewed")

    # --------------------------------------------------------------------------
    # Test 6: Clinician Attributable Review Capture
    # --------------------------------------------------------------------------
    def test_06_clinician_review_capture(self):
        enc_id = self._create_encounter("in_consultation")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        run_res = self.engine.execute_cds_run(enc_id, "FULL_ENCOUNTER", user_ctx)
        card_id = run_res["cards"][0]["id"]

        # Accept as documentation
        rev_res = self.engine.review_card(
            card_id=card_id,
            action="accept_as_documentation",
            user_ctx=user_ctx,
            rationale="Reviewed clinical intake history"
        )
        self.assertEqual(rev_res["review_status"], "accepted")
        self.assertEqual(rev_res["blocking_state"], 0)

    # --------------------------------------------------------------------------
    # Test 7: Review Rejection Requires Rationale for Blockers
    # --------------------------------------------------------------------------
    def test_07_review_rejection_requires_rationale_for_blockers(self):
        enc_id = self._create_encounter("in_consultation")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        run_res = self.engine.execute_cds_run(enc_id, "FULL_ENCOUNTER", user_ctx)
        blocking_cards = [c for c in run_res["cards"] if c["blocking_state"] == 1]
        self.assertTrue(len(blocking_cards) > 0)
        card_id = blocking_cards[0]["id"]

        # Reject without rationale must fail validation
        with self.assertRaises(ValidationError):
            self.engine.review_card(
                card_id=card_id,
                action="reject",
                user_ctx=user_ctx,
                rationale=""
            )

    # --------------------------------------------------------------------------
    # Test 8: Readiness Gate Checks All Dimensions
    # --------------------------------------------------------------------------
    def test_08_readiness_gate_evaluation(self):
        enc_id = self._create_encounter("in_consultation")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        # Initial check without assessment must be blocked
        readiness1 = self.engine.check_readiness(enc_id, user_ctx)
        self.assertFalse(readiness1["is_ready"])
        self.assertEqual(readiness1["dimension_statuses"]["clinical_assessments"], "BLOCKED")

        # Record Modern Assessment
        conn = self.db_manager.get_connection()
        conn.execute("""
            INSERT INTO modern_clinical_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, assessment_date, chief_complaint, status)
            VALUES (?, ?, ?, ?, ?, ?, '2026-10-13', 'Dyspepsia and chronic headache', 'DRAFT');
        """, (f"mod-{uuid.uuid4().hex[:8]}", self.org_id, self.fac_id, self.patient_id, enc_id, self.user_id))
        conn.commit()
        conn.close()

        readiness2 = self.engine.check_readiness(enc_id, user_ctx)
        self.assertEqual(readiness2["dimension_statuses"]["clinical_assessments"], "PASS")

    # --------------------------------------------------------------------------
    # Test 9: Sign-off Fails When Blockers Unresolved
    # --------------------------------------------------------------------------
    def test_09_signoff_blocked_when_prerequisites_fail(self):
        enc_id = self._create_encounter("in_consultation")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        # Attempt to sign without assessments or resolution
        with self.assertRaises(SafetyBlockedError):
            self.engine.sign_encounter(enc_id, pin="1234", user_ctx=user_ctx)

    # --------------------------------------------------------------------------
    # Test 10: Successful Sign-off with Cryptographic Attestation
    # --------------------------------------------------------------------------
    def test_10_successful_pin_verified_signoff(self):
        enc_id = self._create_encounter("ready_to_finalize")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        # Seed assessment and allergy
        conn = self.db_manager.get_connection()
        conn.execute("""
            INSERT INTO modern_clinical_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, assessment_date, chief_complaint, status)
            VALUES (?, ?, ?, ?, ?, ?, '2026-10-13', 'Joint pain', 'DRAFT');
        """, (f"mod-{uuid.uuid4().hex[:8]}", self.org_id, self.fac_id, self.patient_id, enc_id, self.user_id))
        conn.execute("""
            INSERT INTO patient_allergies (id, patient_id, organization_id, allergen_name, severity)
            VALUES (?, ?, ?, 'No Known Drug Allergies (NKDA)', 'MILD');
        """, (f"alg-{uuid.uuid4().hex[:8]}", self.patient_id, self.org_id))
        conn.commit()
        conn.close()

        # Sign encounter
        sign_res = self.engine.sign_encounter(enc_id, pin="1234", user_ctx=user_ctx)
        self.assertEqual(sign_res["status"], "SIGNED")
        self.assertTrue(len(sign_res["signature_hash"]) == 64)
        self.assertEqual(sign_res["signer_name"], "Hakeem Ahmad")

    # --------------------------------------------------------------------------
    # Test 11: Post-Signature Formal Amendment Workflow
    # --------------------------------------------------------------------------
    def test_11_post_signature_amendment(self):
        enc_id = self._create_encounter("ready_to_finalize")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        # Seed assessment
        conn = self.db_manager.get_connection()
        conn.execute("""
            INSERT INTO modern_clinical_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, assessment_date, chief_complaint, status)
            VALUES (?, ?, ?, ?, ?, ?, '2026-10-13', 'Cough and malaise', 'DRAFT');
        """, (f"mod-{uuid.uuid4().hex[:8]}", self.org_id, self.fac_id, self.patient_id, enc_id, self.user_id))
        conn.commit()
        conn.close()


        self.engine.sign_encounter(enc_id, pin="1234", user_ctx=user_ctx)

        # Amend encounter
        amend_res = self.engine.request_amendment(
            encounter_id=enc_id,
            clinical_justification="Patient contacted with additional history of gastric discomfort.",
            changes_summary={"added_symptom": "su-e-hazm"},
            user_ctx=user_ctx
        )
        self.assertEqual(amend_res["status"], "AMENDED")
        self.assertGreater(amend_res["amended_version"], amend_res["original_version"])

    # --------------------------------------------------------------------------
    # Test 12: Emergency Kill Switch Controls
    # --------------------------------------------------------------------------
    def test_12_kill_switch_blocks_cds_run(self):
        enc_id = self._create_encounter("in_consultation")
        user_ctx = {"organization_id": self.org_id, "user_id": self.user_id, "role": "CLINICIAN"}

        # Activate kill switch
        self.engine.set_kill_switch(True, "Emergency governance review")
        self.assertTrue(self.engine.is_kill_switch_active())

        # Attempt CDS run
        run_res = self.engine.execute_cds_run(enc_id, "FULL_ENCOUNTER", user_ctx)
        self.assertEqual(run_res["run_state"], "blocked")
        self.assertIn("temporarily disabled", run_res["safe_error_summary"])
        self.assertEqual(len(run_res["cards"]), 0)

        # Restore kill switch
        self.engine.set_kill_switch(False, "Governance review completed")
        self.assertFalse(self.engine.is_kill_switch_active())


if __name__ == "__main__":
    unittest.main()

"""
Unit Tests for PostPilotEvaluationEngine
ZAYVORA MATAB OS — Prompt 15 Standalone Product
"""

import os
import unittest
import tempfile
import sqlite3
from typing import Dict, Any

from apps.api.database.migrator import run_migrations
from apps.api.domains.pilot_launch import PilotLaunchEngine
from apps.api.domains.post_pilot_evaluation import (
    PostPilotEvaluationEngine,
    ExpansionGateBlockedError,
    RetestEvidenceMissingError
)


class TestPostPilotEvaluationEngine(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        # Apply all migrations
        run_migrations(self.db_path)

        self._seed_baseline_test_data()
        self.pilot_engine = PilotLaunchEngine(self.db_path)
        self.eval_engine = PostPilotEvaluationEngine(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _seed_baseline_test_data(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("""
                INSERT OR IGNORE INTO organizations (id, name, code, profile_type, is_active)
                VALUES ('org-test-postpilot', 'Matab Test Org', 'MTO-01', 'AYUSH_CLINIC', 1);
            """)
            conn.execute("""
                INSERT OR IGNORE INTO facilities (id, organization_id, name, code, is_active)
                VALUES ('fac-test-opd', 'org-test-postpilot', 'Central Matab OPD', 'FAC-OPD', 1);
            """)
            conn.execute("""
                INSERT OR IGNORE INTO users (id, organization_id, username, password_hash, full_name, email, is_active)
                VALUES ('usr-lead-tabib', 'org-test-postpilot', 'lead_tabib', 'hash', 'Hakim Lead', 'lead@example.com', 1);
            """)
            conn.execute("""
                INSERT OR IGNORE INTO users (id, organization_id, username, password_hash, full_name, email, is_active)
                VALUES ('usr-ops-lead', 'org-test-postpilot', 'ops_lead', 'hash', 'Ops Director', 'ops@example.com', 1);
            """)
            conn.execute("""
                INSERT OR IGNORE INTO users (id, organization_id, username, password_hash, full_name, email, is_active)
                VALUES ('usr-sec-officer', 'org-test-postpilot', 'sec_officer', 'hash', 'CISO Auditor', 'sec@example.com', 1);
            """)
            conn.execute("""
                INSERT OR IGNORE INTO patients (id, organization_id, facility_id, mrn, given_name, family_name, display_name, date_of_birth, sex, created_by)
                VALUES ('pat-01', 'org-test-postpilot', 'fac-test-opd', 'MRN-EVAL-001', 'Zaid', 'Khan', 'Zaid Khan', '1990-01-01', 'MALE', 'usr-lead-tabib');
            """)
            conn.commit()
        finally:
            conn.close()

    def _create_test_program(self):
        return self.pilot_engine.create_pilot_program(
            code="PLT-EVAL-TEST-001",
            name="Pilot Evaluation Test Program",
            organization_id="org-test-postpilot",
            target_start_date="2026-10-01",
            target_end_date="2026-10-13",
            created_by="usr-ops-lead"
        )

    def test_01_evaluation_lifecycle_and_preagreed_metrics(self):
        """Verify evaluation master record creation and pre-agreed metric definitions."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Test Evaluation 2026",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        self.assertEqual(evaluation["status"], "EVIDENCE_COLLECTION")
        self.assertEqual(evaluation["build_commit"], "git:81f9fba")

        # Metric definitions should be pre-agreed and seeded
        definitions = self.eval_engine.list_metric_definitions()
        self.assertGreaterEqual(len(definitions), 10)
        codes = [d["code"] for d in definitions]
        self.assertIn("MET-USAB-01", codes)
        self.assertIn("MET-REL-02", codes)
        self.assertIn("MET-CLIN-01", codes)
        self.assertIn("MET-SAFE-01", codes)

    def test_02_missing_telemetry_marks_unavailable_never_zero_or_perfect(self):
        """Principle 5: Missing telemetry must be marked UNAVAILABLE, not zero failures or 100% pass."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Empty Telemetry Evaluation",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        scorecard = self.eval_engine.calculate_scorecard(evaluation["id"])
        self.assertTrue(len(scorecard) > 0)

        # Encounter completion rate with 0 encounters must be marked is_unavailable
        enc_metric = next((m for m in scorecard if m["metric_code"] == "MET-USAB-01"), None)
        self.assertIsNotNone(enc_metric)
        self.assertTrue(enc_metric["is_unavailable"])
        self.assertIn("No clinical encounters", enc_metric["unavailable_reason"])
        self.assertIsNone(enc_metric["observed_value"])

    def test_03_scorecard_reproducible_from_persisted_events(self):
        """Verify metric observations calculate accurately from actual persisted database records."""
        program = self._create_test_program()
        conn = sqlite3.connect(self.db_path)
        try:
            # Seed 5 encounters (4 completed, 1 planned)
            for i in range(4):
                conn.execute("""
                    INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, encounter_type, created_by, created_at)
                    VALUES (?, 'org-test-postpilot', 'fac-test-opd', 'pat-01', 'usr-lead-tabib', 'COMPLETED', 'OPD', 'usr-lead-tabib', '2026-10-05 10:00:00');
                """, (f"enc-eval-{i}",))
            conn.execute("""
                INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, encounter_type, created_by, created_at)
                VALUES ('enc-eval-4', 'org-test-postpilot', 'fac-test-opd', 'pat-01', 'usr-lead-tabib', 'PLANNED', 'OPD', 'usr-lead-tabib', '2026-10-05 10:00:00');
            """)

            # Seed 2 signed prescriptions with 64-char signature_hash
            dummy_hash = "a" * 64
            conn.execute("""
                INSERT INTO prescriptions (id, organization_id, facility_id, prescription_number, patient_id, encounter_id, practitioner_id, signed_by, status, signature_hash, created_at)
                VALUES ('rx-eval-1', 'org-test-postpilot', 'fac-test-opd', 'RX-EVAL-01', 'pat-01', 'enc-eval-0', 'usr-lead-tabib', 'usr-lead-tabib', 'SIGNED', ?, '2026-10-05 10:00:00');
            """, (dummy_hash,))
            conn.execute("""
                INSERT INTO prescriptions (id, organization_id, facility_id, prescription_number, patient_id, encounter_id, practitioner_id, signed_by, status, signature_hash, created_at)
                VALUES ('rx-eval-2', 'org-test-postpilot', 'fac-test-opd', 'RX-EVAL-02', 'pat-01', 'enc-eval-1', 'usr-lead-tabib', 'usr-lead-tabib', 'SIGNED', ?, '2026-10-05 10:00:00');
            """, (dummy_hash,))
            conn.commit()
        finally:
            conn.close()

        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Reproducible Metrics Evaluation",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        scorecard = self.eval_engine.calculate_scorecard(evaluation["id"])

        # Check Encounter completion rate: 4 completed / 5 total = 80.0%
        enc_met = next(m for m in scorecard if m["metric_code"] == "MET-USAB-01")
        self.assertFalse(enc_met["is_unavailable"])
        self.assertEqual(enc_met["numerator_value"], 4.0)
        self.assertEqual(enc_met["denominator_value"], 5.0)
        self.assertEqual(enc_met["observed_value"], 80.0)

        # Check Prescription Document Generation: 2/2 = 100.0%
        rx_met = next(m for m in scorecard if m["metric_code"] == "MET-REL-02")
        self.assertFalse(rx_met["is_unavailable"])
        self.assertEqual(rx_met["observed_value"], 100.0)

    def test_04_feedback_sanitization_and_phi_protection(self):
        """Section 5: Feedback quotes must not contain patient PHI (email, phone)."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Feedback Sanitization Test",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        # Attempting to submit unsanitized feedback with phone number must fail
        with self.assertRaises(ValueError) as ctx:
            self.eval_engine.review_feedback_theme(
                evaluation_id=evaluation["id"],
                theme_title="Test Theme",
                classification="USABILITY_FRICTION",
                affected_role="TABIB",
                affected_workflow="OPD",
                redacted_evidence_quote="Patient at 9876543210 complained of queue time.",
                severity_impact="LOW",
                root_cause_hypothesis="Hypothesis: High volume hour.",
                owner_role="PRODUCT_OPERATIONS"
            )
        self.assertIn("Patient identifiers must be sanitized", str(ctx.exception))

        # Clean sanitized quote should succeed
        clean_theme = self.eval_engine.review_feedback_theme(
            evaluation_id=evaluation["id"],
            theme_title="Search Auto-complete Lag",
            classification="USABILITY_FRICTION",
            affected_role="TABIB",
            affected_workflow="OPD",
            redacted_evidence_quote="Practitioner noted typing lag when formulary had >50 items.",
            severity_impact="MEDIUM",
            root_cause_hypothesis="Hypothesis: Client-side debounce timeout needs tuning.",
            owner_role="PRODUCT_OPERATIONS"
        )
        self.assertIsNotNone(clean_theme["id"])

    def test_05_unresolved_p0_or_active_stop_blocks_expansion(self):
        """Section 8: Any unresolved P0 or active stop condition must strictly block EXPAND_* decisions."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Expansion Blocker Test",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        # Record an unresolved P0 incident
        self.eval_engine.record_incident_risk_review(
            evaluation_id=evaluation["id"],
            issue_ref="P0-SEC-01",
            issue_type="P0_FINDING",
            severity="P0_CRITICAL",
            verified_facts="Detected unauthorized signature attempt in integration test.",
            containment_status="CONTAINED",
            corrective_action="Revoke compromised test token.",
            status="OPEN"
        )

        # Attempting to decide EXPAND_WITHIN_APPROVED_SCOPE must be blocked!
        with self.assertRaises(ExpansionGateBlockedError) as ctx:
            self.eval_engine.record_decision(
                evaluation_id=evaluation["id"],
                decision="EXPAND_WITHIN_APPROVED_SCOPE",
                rationale="Attempting expansion with open P0",
                allowed_scope_summary="Central Matab",
                disabled_features_summary="None",
                recorded_by="usr-ops-lead"
            )
        self.assertIn("unresolved P0 critical incident", str(ctx.exception))

    def test_06_independent_expansion_gates_and_no_module_propagation(self):
        """Section 7: Evaluation of proposals is independent; approving one module does not approve another."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Independent Gates Test",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        # Proposal 1: MORE_USERS_SAME_FACILITY
        prop1 = self.eval_engine.create_expansion_proposal(
            evaluation_id=evaluation["id"],
            proposal_type="MORE_USERS_SAME_FACILITY",
            target_scope_details={"users": ["usr-02", "usr-03"]},
            justification="High clinic demand",
            prerequisite_dependencies=["TRAINING_PASSED"]
        )

        # Proposal 2: PHARMACY_INVENTORY_ENABLEMENT
        prop2 = self.eval_engine.create_expansion_proposal(
            evaluation_id=evaluation["id"],
            proposal_type="PHARMACY_INVENTORY_ENABLEMENT",
            target_scope_details={"dispensary": "central-dispensary"},
            justification="Stock integration",
            prerequisite_dependencies=["FEFO_AUDIT"]
        )

        # Pass 3 gates for Proposal 1
        self.eval_engine.evaluate_expansion_gate(prop1["id"], "MANDATORY_SAFETY_GATE", "PASS", "Verified safe")
        self.eval_engine.evaluate_expansion_gate(prop1["id"], "TRAINING_ONBOARDING_CAPACITY", "PASS", "Trained staff")
        self.eval_engine.evaluate_expansion_gate(prop1["id"], "BACKUP_RESTORE_DRILL", "PASS", "Vacuum drill verified")

        # Fail gate for Proposal 2
        self.eval_engine.evaluate_expansion_gate(prop2["id"], "MANDATORY_SAFETY_GATE", "FAIL", "Quarantine issue flagged")

        proposals = self.eval_engine.list_expansion_proposals(evaluation["id"])
        p1 = next(p for p in proposals if p["id"] == prop1["id"])
        p2 = next(p for p in proposals if p["id"] == prop2["id"])

        self.assertEqual(p1["overall_gate_status"], "PASSED")
        self.assertEqual(p2["overall_gate_status"], "BLOCKED")

    def test_07_tri_party_governance_approval_workflow(self):
        """Section 10: Transition to DECISION_APPROVED requires Clinical, Ops, and Security signatures."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Approval Workflow Test",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        # Record decision to CONTINUE_CURRENT_PILOT
        decision = self.eval_engine.record_decision(
            evaluation_id=evaluation["id"],
            decision="CONTINUE_CURRENT_PILOT",
            rationale="Maintain current stable parameters for additional 14 days",
            allowed_scope_summary="Central Matab OPD (Dr. Hakim Lead)",
            disabled_features_summary="External ABDM Gateway & Live SMS Gateway",
            recorded_by="usr-ops-lead"
        )

        # Evaluation should be in READY_FOR_DECISION
        eval_state = self.eval_engine.get_evaluation(evaluation["id"])
        self.assertEqual(eval_state["status"], "READY_FOR_DECISION")

        # Clinical governance signs off
        app1 = self.eval_engine.approve_decision(
            decision_record_id=decision["id"],
            required_role="CLINICAL_GOVERNANCE",
            approver_user_id="usr-lead-tabib"
        )
        self.assertFalse(app1["all_approved"])

        # Product operations signs off
        app2 = self.eval_engine.approve_decision(
            decision_record_id=decision["id"],
            required_role="PRODUCT_OPERATIONS",
            approver_user_id="usr-ops-lead"
        )
        self.assertFalse(app2["all_approved"])

        # Security & Privacy signs off -> All 3 approved!
        app3 = self.eval_engine.approve_decision(
            decision_record_id=decision["id"],
            required_role="SECURITY_PRIVACY",
            approver_user_id="usr-sec-officer"
        )
        self.assertTrue(app3["all_approved"])

        # Master evaluation record must now be DECISION_APPROVED
        eval_final = self.eval_engine.get_evaluation(evaluation["id"])
        self.assertEqual(eval_final["status"], "DECISION_APPROVED")

    def test_08_action_cannot_close_without_retest_evidence(self):
        """Section 11: Remediation action item cannot close without verified retest evidence."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Remediation Retest Test",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        action = self.eval_engine.add_remediation_action(
            evaluation_id=evaluation["id"],
            title="Update Tadbeer Verification UI",
            description="Clarify dosage input label",
            category="SAFETY",
            priority="P1",
            owner_role="PRODUCT_OPERATIONS",
            retest_requirement="Unit test verification"
        )

        # Closing without retest evidence must raise RetestEvidenceMissingError
        with self.assertRaises(RetestEvidenceMissingError):
            self.eval_engine.close_remediation_action(
                action_id=action["id"],
                closed_by_user_id="usr-ops-lead",
                retest_evidence_ref=""
            )

        # Closing with valid retest evidence succeeds
        closed = self.eval_engine.close_remediation_action(
            action_id=action["id"],
            closed_by_user_id="usr-ops-lead",
            retest_evidence_ref="TEST-TADBEER-UI-20261013-PASS"
        )
        self.assertEqual(closed["status"], "VERIFIED_CLOSED")
        self.assertEqual(closed["retest_evidence_ref"], "TEST-TADBEER-UI-20261013-PASS")

    def test_09_comprehensive_report_generation_preserves_provenance(self):
        """Section 9: Report generator produces structured markdown snapshot and evidence manifest."""
        program = self._create_test_program()
        evaluation = self.eval_engine.create_evaluation(
            pilot_program_id=program["id"],
            organization_id="org-test-postpilot",
            evaluation_title="Report Snapshot Test",
            build_commit="git:81f9fba",
            review_period_start="2026-10-01",
            review_period_end="2026-10-13",
            created_by="usr-ops-lead"
        )

        self.eval_engine.register_evidence_item(
            evaluation_id=evaluation["id"],
            source_reference="EVI-LOG-TEST-01",
            category="WORKFLOW_TELEMETRY",
            owner="PRODUCT_OPERATIONS",
            build_commit="git:81f9fba",
            extraction_method="SQL_AUDIT_QUERY"
        )

        report = self.eval_engine.generate_evaluation_report(evaluation["id"], generated_by="usr-ops-lead")
        self.assertEqual(report["version_number"], 1)
        self.assertIn("# ZAYVORA MATAB OS — Post-Pilot Evaluation & Scale Decision", report["report_markdown"])
        self.assertIn("EVI-LOG-TEST-01", report["report_markdown"])
        self.assertEqual(report["manifest"]["evaluation_id"], evaluation["id"])
        self.assertEqual(report["manifest"]["evidence_item_count"], 1)


if __name__ == "__main__":
    unittest.main()

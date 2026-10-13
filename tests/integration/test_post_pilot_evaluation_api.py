"""
Integration Test Suite for Post-Pilot Evaluation REST APIs (Prompt 15)
ZAYVORA MATAB OS — Independent Standalone Product
"""

import json
import os
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestPostPilotEvaluationApi(unittest.TestCase):
    """End-to-end REST API integration tests for Post-Pilot Evaluation & Scale Decision."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self._ip_counter = 80

        self.org_id = "org-matab-default"
        self.fac_id = "fac-central-opd"
        self.admin_token = self._login("admin", "matab123")
        self.hakeem_token = self._login("hakeem", "matab123")
        self.reception_token = self._login("reception", "matab123")

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _login(self, username: str, password: str) -> str:
        self._ip_counter += 1
        client_ip = f"10.0.15.{self._ip_counter}"
        body_bytes = json.dumps({"username": username, "password": password}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login", {}, {}, body_bytes, client_ip, db_path=self.db_path
        )
        self.assertEqual(status, 200)
        return json.loads(resp_bytes.decode("utf-8"))["token"]

    def _req(self, method: str, path: str, token: str, body: dict = None):
        self._ip_counter += 1
        client_ip = f"10.0.15.{self._ip_counter}"
        headers = {"Authorization": f"Bearer {token}", "x-facility-id": self.fac_id}
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, _, resp_bytes = ApiRouter.dispatch(
            method, path, headers, {}, body_bytes, client_ip, db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def _create_test_program(self) -> str:
        status, res = self._req("POST", "/api/v1/pilot/programs", self.admin_token, {
            "code": "PILOT-API-EVAL-01",
            "name": "Integration Pilot Program",
            "target_start_date": "2026-10-01",
            "target_end_date": "2026-10-13"
        })
        self.assertEqual(status, 201)
        return res["pilot_program"]["id"]

    def test_01_evaluation_crud_and_status_transitions(self):
        """Verify evaluation master creation, listing, retrieval, and status updates."""
        program_id = self._create_test_program()

        # 1. Create evaluation
        status, res = self._req("POST", "/api/v1/pilot-evaluations", self.admin_token, {
            "pilot_program_id": program_id,
            "evaluation_title": "End-to-End Pilot Evaluation",
            "build_commit": "git:81f9fba",
            "review_period_start": "2026-10-01",
            "review_period_end": "2026-10-13",
            "enabled_features": ["OPD_CONSULTATION", "PRESCRIPTION_ENGINE"],
            "disabled_features": ["EXTERNAL_LIVE_ABDM"]
        })
        self.assertEqual(status, 201)
        eval_id = res["evaluation"]["id"]
        self.assertEqual(res["evaluation"]["status"], "EVIDENCE_COLLECTION")

        # 2. Get evaluation by ID
        status, get_res = self._req("GET", f"/api/v1/pilot-evaluations/{eval_id}", self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(get_res["evaluation"]["evaluation_title"], "End-to-End Pilot Evaluation")

        # 3. List evaluations
        status, list_res = self._req("GET", "/api/v1/pilot-evaluations", self.admin_token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(list_res["evaluations"]), 1)

        # 4. Update status to READY_FOR_DECISION
        status, patch_res = self._req("PATCH", f"/api/v1/pilot-evaluations/{eval_id}/status", self.admin_token, {
            "status": "READY_FOR_DECISION",
            "findings_summary": "All test criteria verified."
        })
        self.assertEqual(status, 200)
        self.assertEqual(patch_res["evaluation"]["status"], "READY_FOR_DECISION")

    def test_02_evidence_collection_and_scorecard_calculation(self):
        """Verify evidence registration and metric derivation."""
        program_id = self._create_test_program()
        status, res = self._req("POST", "/api/v1/pilot-evaluations", self.admin_token, {
            "pilot_program_id": program_id,
            "evaluation_title": "Scorecard Integration Evaluation",
            "build_commit": "git:81f9fba",
            "review_period_start": "2026-10-01",
            "review_period_end": "2026-10-13"
        })
        eval_id = res["evaluation"]["id"]

        # Register evidence item
        status, evi_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/collect-evidence", self.admin_token, {
            "source_reference": "EVI-TELEMETRY-SQL-01",
            "category": "WORKFLOW_TELEMETRY",
            "owner": "PRODUCT_OPERATIONS",
            "build_commit": "git:81f9fba",
            "extraction_method": "SQL_AUDIT_QUERY"
        })
        self.assertEqual(status, 201)
        self.assertEqual(evi_res["evidence_item"]["source_reference"], "EVI-TELEMETRY-SQL-01")

        # List evidence items
        status, evi_list = self._req("GET", f"/api/v1/pilot-evaluations/{eval_id}/evidence", self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(evi_list["evidence_items"]), 1)

        # Calculate scorecard
        status, sc_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/calculate-scorecard", self.admin_token)
        self.assertEqual(status, 200)
        self.assertTrue(len(sc_res["scorecard"]) >= 10)

        # List observations
        status, obs_res = self._req("GET", f"/api/v1/pilot-evaluations/{eval_id}/scorecard", self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(obs_res["metric_observations"]), len(sc_res["scorecard"]))

    def test_03_feedback_triage_and_risk_review(self):
        """Verify feedback themes with sanitized quotes and risk review items."""
        program_id = self._create_test_program()
        status, res = self._req("POST", "/api/v1/pilot-evaluations", self.admin_token, {
            "pilot_program_id": program_id,
            "evaluation_title": "Feedback & Risk Evaluation",
            "build_commit": "git:81f9fba",
            "review_period_start": "2026-10-01",
            "review_period_end": "2026-10-13"
        })
        eval_id = res["evaluation"]["id"]

        # Add feedback theme
        status, fdb_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/review-feedback", self.admin_token, {
            "theme_title": "Formulary Search Font Size",
            "classification": "ACCESSIBILITY_LANGUAGE",
            "affected_role": "TABIB",
            "affected_workflow": "PRESCRIPTIONS",
            "redacted_evidence_quote": "Tabib requested larger Arabic script typography on tablet.",
            "severity_impact": "LOW",
            "root_cause_hypothesis": "Hypothesis: CSS font-size rule for Nastaliq script.",
            "owner_role": "PRODUCT_OPERATIONS"
        })
        self.assertEqual(status, 201)

        # Add risk review
        status, risk_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/review-risks", self.admin_token, {
            "issue_ref": "RISK-01-INTEG",
            "issue_type": "NEAR_MISS",
            "severity": "P2_MEDIUM",
            "verified_facts": "ABDM test harness returned mocked transaction ID correctly.",
            "containment_status": "CONTAINED",
            "corrective_action": "None required; harness tested successfully."
        })
        self.assertEqual(status, 201)

    def test_04_expansion_proposal_and_independent_gates(self):
        """Verify independent expansion gates evaluation."""
        program_id = self._create_test_program()
        status, res = self._req("POST", "/api/v1/pilot-evaluations", self.admin_token, {
            "pilot_program_id": program_id,
            "evaluation_title": "Expansion Gates Test",
            "build_commit": "git:81f9fba",
            "review_period_start": "2026-10-01",
            "review_period_end": "2026-10-13"
        })
        eval_id = res["evaluation"]["id"]

        # Create proposal
        status, prop_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/expansion-proposals", self.admin_token, {
            "proposal_type": "MORE_USERS_SAME_FACILITY",
            "justification": "Onboarding additional clinical staff at Central Matab.",
            "target_scope_details": {"roles": ["TABIB", "RECEPTIONIST"]},
            "prerequisite_dependencies": ["TRAINING_PASSED"]
        })
        self.assertEqual(status, 201)
        prop_id = prop_res["expansion_proposal"]["id"]

        # Evaluate gate 1: PASS
        status, g1 = self._req("POST", f"/api/v1/pilot-evaluations/expansion-proposals/{prop_id}/gates", self.admin_token, {
            "gate_name": "MANDATORY_SAFETY_GATE",
            "gate_status": "PASS",
            "evidence_notes": "Clinical firewall verified."
        })
        self.assertEqual(status, 200)

        # Evaluate gate 2: PASS
        status, g2 = self._req("POST", f"/api/v1/pilot-evaluations/expansion-proposals/{prop_id}/gates", self.admin_token, {
            "gate_name": "TRAINING_ONBOARDING_CAPACITY",
            "gate_status": "PASS",
            "evidence_notes": "All staff achieved 100% test score."
        })
        self.assertEqual(status, 200)

        # List proposals and check gates
        status, p_list = self._req("GET", f"/api/v1/pilot-evaluations/{eval_id}/expansion-proposals", self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(len(p_list["expansion_proposals"]), 1)
        self.assertEqual(len(p_list["expansion_proposals"][0]["gates"]), 2)

    def test_05_formal_decision_and_multi_signature_approvals(self):
        """Verify decision recording, 3-role approvals, and final report snapshot."""
        program_id = self._create_test_program()
        status, res = self._req("POST", "/api/v1/pilot-evaluations", self.admin_token, {
            "pilot_program_id": program_id,
            "evaluation_title": "Decision & Sign-off Evaluation",
            "build_commit": "git:81f9fba",
            "review_period_start": "2026-10-01",
            "review_period_end": "2026-10-13"
        })
        eval_id = res["evaluation"]["id"]

        # Record decision
        status, dec_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/record-decision", self.admin_token, {
            "decision": "CONTINUE_CURRENT_PILOT",
            "rationale": "Controlled single-facility pilot stable; extend for 14 additional observation days.",
            "allowed_scope_summary": "Central Matab OPD only",
            "disabled_features_summary": "Live ABDM and External SMS remain disabled",
            "next_review_date": "2026-10-27"
        })
        self.assertEqual(status, 201)
        dec_id = dec_res["decision_record"]["id"]

        # Sign-off role 1: CLINICAL_GOVERNANCE
        status, app1 = self._req("POST", "/api/v1/pilot-evaluations/decision-approvals", self.admin_token, {
            "decision_record_id": dec_id,
            "required_role": "CLINICAL_GOVERNANCE",
            "approval_status": "APPROVED",
            "conditions_or_notes": "Clinical safety firewall validated."
        })
        self.assertEqual(status, 200)
        self.assertFalse(app1["decision_approval"]["all_approved"])

        # Sign-off role 2: PRODUCT_OPERATIONS
        status, app2 = self._req("POST", "/api/v1/pilot-evaluations/decision-approvals", self.admin_token, {
            "decision_record_id": dec_id,
            "required_role": "PRODUCT_OPERATIONS",
            "approval_status": "APPROVED"
        })
        self.assertEqual(status, 200)
        self.assertFalse(app2["decision_approval"]["all_approved"])

        # Sign-off role 3: SECURITY_PRIVACY
        status, app3 = self._req("POST", "/api/v1/pilot-evaluations/decision-approvals", self.admin_token, {
            "decision_record_id": dec_id,
            "required_role": "SECURITY_PRIVACY",
            "approval_status": "APPROVED"
        })
        self.assertEqual(status, 200)
        self.assertTrue(app3["decision_approval"]["all_approved"])

        # Master evaluation status should now be DECISION_APPROVED
        status, get_eval = self._req("GET", f"/api/v1/pilot-evaluations/{eval_id}", self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(get_eval["evaluation"]["status"], "DECISION_APPROVED")

        # Generate report snapshot
        status, rep_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/report", self.admin_token)
        self.assertEqual(status, 200)
        self.assertIn("# ZAYVORA MATAB OS — Post-Pilot Evaluation & Scale Decision", rep_res["report"]["report_markdown"])
        self.assertTrue(rep_res["report"]["manifest"]["decision_signed_off"])

    def test_06_remediation_actions_lifecycle(self):
        """Verify remediation actions creation and closure requiring retest evidence."""
        program_id = self._create_test_program()
        status, res = self._req("POST", "/api/v1/pilot-evaluations", self.admin_token, {
            "pilot_program_id": program_id,
            "evaluation_title": "Actions Evaluation",
            "build_commit": "git:81f9fba",
            "review_period_start": "2026-10-01",
            "review_period_end": "2026-10-13"
        })
        eval_id = res["evaluation"]["id"]

        # Add remediation action
        status, act_res = self._req("POST", f"/api/v1/pilot-evaluations/{eval_id}/actions", self.admin_token, {
            "title": "Verify Urdu Font Display",
            "description": "Ensure Naskh and Nastaliq render cleanly on receipts.",
            "category": "USABILITY",
            "priority": "P2",
            "owner_role": "PRODUCT_OPERATIONS",
            "retest_requirement": "Visual PDF preview validation"
        })
        self.assertEqual(status, 201)
        action_id = act_res["remediation_action"]["id"]

        # Close action with valid retest evidence
        status, close_res = self._req("POST", f"/api/v1/pilot-evaluations/actions/{action_id}/close", self.admin_token, {
            "retest_evidence_ref": "VISUAL-PDF-URDU-PASS-20261013"
        })
        self.assertEqual(status, 200)
        self.assertEqual(close_res["remediation_action"]["status"], "VERIFIED_CLOSED")


if __name__ == "__main__":
    unittest.main()

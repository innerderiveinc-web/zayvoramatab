"""Unit tests for Clinical Rules Engine & Decision Support Heuristics.
Tests fail-closed behavior, missing input handling, deterministic red flag triggers,
differential candidate contract, and non-ordering investigation suggestions.
"""

import unittest
import os
import tempfile
import sqlite3
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.database.connection import DatabaseConnection
from apps.api.domains.clinical_rules import ClinicalRulesEngine


class TestClinicalRulesEngine(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.conn = DatabaseConnection(self.db_path).get_connection()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_fail_closed_when_rules_unavailable(self):
        """When rule definitions table is empty, engine must return explicit CONTENT_UNAVAILABLE."""
        self.conn.execute("DELETE FROM clinical_rule_definitions;")
        assessment = {
            "chief_complaint": "Severe acute crushing chest pain radiating to jaw",
            "history_of_present_illness": "Sudden onset with profuse diaphoresis",
            "working_assessment": ""
        }
        res = ClinicalRulesEngine.evaluate_red_flags(self.conn, assessment, [])
        self.assertEqual(res["evaluation_status"], "CONTENT_UNAVAILABLE")
        self.assertIn("Safety rules unavailable", res["message"])
        self.assertIn("Do not assume low risk", res["message"])
        self.assertEqual(len(res["triggered_alerts"]), 0)

    def test_missing_vitals_yields_missing_inputs_not_clearance(self):
        """When vitals are absent, rule engine flags missing required inputs and does NOT assume normal."""
        assessment = {
            "chief_complaint": "Headache and dizziness",
            "history_of_present_illness": "Felt lightheaded at work today",
            "working_assessment": ""
        }
        # Zero observations provided
        res = ClinicalRulesEngine.evaluate_red_flags(self.conn, assessment, [])
        self.assertEqual(res["evaluation_status"], "EVALUATED")
        missing_rule_ids = [m["rule_id"] for m in res["missing_input_rules"]]
        self.assertIn("RULE-RF-002", missing_rule_ids)  # Blood pressure required
        # Must not trigger false positive or silent negative
        htn_alerts = [a for a in res["triggered_alerts"] if a["rule_id"] == "RULE-RF-002"]
        self.assertEqual(len(htn_alerts), 0)

    def test_chest_pain_red_flag_triggers_emergent_alert(self):
        """Acute chest pain with ischemic radiation triggers RULE-RF-001 with EMERGENT severity."""
        assessment = {
            "chief_complaint": "Acute substernal chest pain radiating to left arm",
            "history_of_present_illness": "Patient has diaphoresis and shortness of breath for past 45 minutes",
            "working_assessment": "Suspected ACS"
        }
        res = ClinicalRulesEngine.evaluate_red_flags(self.conn, assessment, [])
        alerts = [a for a in res["triggered_alerts"] if a["rule_id"] == "RULE-RF-001"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "EMERGENT")
        self.assertIn("Emergency Department", alerts[0]["recommended_action"])

    def test_severe_hypertension_triggers_emergent_alert(self):
        """Measured SBP >= 180 or DBP >= 110 triggers RULE-RF-002."""
        assessment = {
            "chief_complaint": "Occipital headache",
            "history_of_present_illness": "Throbbing headache since morning",
            "working_assessment": ""
        }
        observations = [
            {"concept_name": "Systolic Blood Pressure", "value_numeric": 195.0, "unit": "mmHg"},
            {"concept_name": "Diastolic Blood Pressure", "value_numeric": 115.0, "unit": "mmHg"}
        ]
        res = ClinicalRulesEngine.evaluate_red_flags(self.conn, assessment, observations)
        alerts = [a for a in res["triggered_alerts"] if a["rule_id"] == "RULE-RF-002"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "EMERGENT")
        self.assertTrue(any("195.0 mmHg" in f for f in alerts[0]["trigger_facts"]))

    def test_sepsis_sirs_criteria_triggers_emergent_alert(self):
        """Fever + tachycardia + tachypnea with infection focus triggers sepsis alert."""
        assessment = {
            "chief_complaint": "High fever and productive cough with yellow phlegm",
            "history_of_present_illness": "Shaking chills and rigors since yesterday",
            "working_assessment": ""
        }
        observations = [
            {"concept_name": "Body Temperature", "value_numeric": 39.1, "unit": "degC"},
            {"concept_name": "Heart Rate", "value_numeric": 112.0, "unit": "bpm"},
            {"concept_name": "Respiratory Rate", "value_numeric": 24.0, "unit": "/min"}
        ]
        res = ClinicalRulesEngine.evaluate_red_flags(self.conn, assessment, observations)
        alerts = [a for a in res["triggered_alerts"] if a["rule_id"] == "RULE-RF-003"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "EMERGENT")
        self.assertIn("Sepsis Six", alerts[0]["recommended_action"])

    def test_acute_stroke_fast_triggers_emergent_alert(self):
        """Documented sudden arm weakness or facial droop triggers FAST stroke red flag."""
        assessment = {
            "chief_complaint": "Sudden onset facial droop and slurred speech",
            "history_of_present_illness": "Family noticed inability to speak clearly 30 minutes ago",
            "working_assessment": ""
        }
        res = ClinicalRulesEngine.evaluate_red_flags(self.conn, assessment, [])
        alerts = [a for a in res["triggered_alerts"] if a["rule_id"] == "RULE-RF-004"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["severity"], "EMERGENT")
        self.assertIn("stroke team activation", alerts[0]["recommended_action"])

    def test_differential_candidates_explainability_contract(self):
        """Differential candidate output contains explainable supporting/contradicting findings and limitations."""
        assessment = {
            "chief_complaint": "Persistent cough and wheezing for two weeks",
            "history_of_present_illness": "Worse at night, feeling breathlessness on exertion",
            "working_assessment": ""
        }
        res = ClinicalRulesEngine.evaluate_differential_candidates(self.conn, assessment, [])
        self.assertEqual(res["status"], "EVALUATED")
        self.assertGreater(res["candidates_count"], 0)

        for cand in res["candidates"]:
            self.assertIn("candidate_label", cand)
            self.assertIn("rationale", cand)
            self.assertIsInstance(cand["supporting_findings"], list)
            self.assertIsInstance(cand["missing_information"], list)
            self.assertIsInstance(cand["source_references"], list)
            self.assertEqual(cand["evidence_status"], "FOR_CLINICIAN_REVIEW")
            self.assertTrue(cand["review_required"])
            self.assertIn("Heuristic consideration only", cand["limitations"])

    def test_investigation_considerations_non_ordering_contract(self):
        """Investigation suggestions provide clinical question, modality, and rationale without placing orders."""
        assessment = {
            "chief_complaint": "Chronic epigastric pain and dyspepsia for 3 months",
            "history_of_present_illness": "Burning sensation after food with unintentional weight loss",
            "working_assessment": ""
        }
        invs = ClinicalRulesEngine.evaluate_investigation_considerations(self.conn, assessment, [], [])
        self.assertGreater(len(invs), 0)
        endoscopy_inv = [i for i in invs if i["modality"] == "ENDOSCOPY"]
        self.assertEqual(len(endoscopy_inv), 1)
        self.assertIn("clinical_question", endoscopy_inv[0])
        self.assertIn("rationale", endoscopy_inv[0])
        self.assertIn("No automatic order placed", endoscopy_inv[0]["limitations"])
        self.assertEqual(endoscopy_inv[0]["clinician_decision"], "PENDING")


if __name__ == "__main__":
    unittest.main()

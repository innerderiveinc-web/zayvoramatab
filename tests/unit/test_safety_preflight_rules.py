"""Unit Tests: Deterministic Safety Preflight Rules, Unit Validation, Dose Ceilings, and Coverage Reporting."""

import unittest
import os
import tempfile
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.database.connection import DatabaseConnection
from apps.api.domains.safety_preflight import SafetyPreflightEngine, parse_dose_to_mg, ALLOWED_UNITS

class TestSafetyPreflightRules(unittest.TestCase):
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

    def test_unit_parsing_and_conversion(self):
        """Test unit dimension handling and milligram normalization."""
        self.assertEqual(parse_dose_to_mg("5", "g"), 5000.0)
        self.assertEqual(parse_dose_to_mg("500", "mg"), 500.0)
        self.assertEqual(parse_dose_to_mg("10", "ml"), 10000.0)
        self.assertEqual(parse_dose_to_mg("2", "hab"), 1000.0)
        self.assertEqual(parse_dose_to_mg("invalid", "g"), 0.0)

    def test_structural_validation_empty_items(self):
        """Empty prescription items list triggers structural BLOCK."""
        report = SafetyPreflightEngine.evaluate(self.conn, patient_id="pat-syn-001", prescription_items=[])
        self.assertEqual(report["overall_state"], "BLOCK")
        rules = [f["rule"] for f in report["findings"]]
        self.assertIn("STRUCTURAL_ITEMS_REQUIRED", rules)

    def test_structural_validation_invalid_fields(self):
        """Invalid units, zero dose, or missing frequency trigger structural BLOCKs."""
        items = [
            {
                "item_name": "Test Formulation",
                "dose_amount": "0", # Invalid dose
                "dose_unit": "unknown_unit", # Invalid unit
                "frequency": "INVALID_FREQ", # Invalid frequency
                "duration_days": 0 # Invalid duration
            }
        ]
        report = SafetyPreflightEngine.evaluate(self.conn, patient_id="pat-syn-002", prescription_items=items)
        self.assertEqual(report["overall_state"], "BLOCK")
        rules = [f["rule"] for f in report["findings"]]
        self.assertIn("STRUCTURAL_DOSE_INVALID", rules)
        self.assertIn("STRUCTURAL_UNIT_INVALID", rules)
        self.assertIn("STRUCTURAL_FREQUENCY_INVALID", rules)
        self.assertIn("STRUCTURAL_DURATION_INVALID", rules)

    def test_allergy_match_triggers_blocking_finding(self):
        """Documented patient allergy to Roghan Badam Shireen triggers critical BLOCK."""
        items = [
            {
                "item_name": "Majoon Arad Khurma with Badam",
                "dose_amount": "10",
                "dose_unit": "g",
                "frequency": "BD",
                "duration_days": 7
            }
        ]
        report = SafetyPreflightEngine.evaluate(self.conn, patient_id="pat-syn-001", prescription_items=items)
        self.assertEqual(report["overall_state"], "BLOCK")
        allergy_findings = [f for f in report["findings"] if f["rule"] == "PATIENT_ALLERGY_MATCH"]
        self.assertGreaterEqual(len(allergy_findings), 1)

    def test_uncertified_mudabbar_toxin_triggers_block(self):
        """Prescribing formulation containing toxic ingredient without certified detoxification triggers BLOCK."""
        items = [
            {
                "item_name": "Habb-e-Azaarqi",
                "formulation_id": "form-hab-azaarqi",
                "dose_amount": "1",
                "dose_unit": "g",
                "frequency": "OD",
                "duration_days": 5,
                "is_mudabbar_certified": False
            }
        ]
        report = SafetyPreflightEngine.evaluate(self.conn, patient_id="pat-syn-002", prescription_items=items)
        self.assertEqual(report["overall_state"], "BLOCK")
        mudabbar_findings = [f for f in report["findings"] if f["rule"] == "SCHEDULE_E1_MUDABBAR_REQUIRED"]
        self.assertGreaterEqual(len(mudabbar_findings), 1)

    def test_explicit_coverage_reporting_limits(self):
        """Preflight report must declare explicit evaluation coverage and limitations."""
        items = [
            {
                "item_name": "Sharbat Bazoori Motadil",
                "formulation_id": "form-sharbat-bazoori",
                "dose_amount": "10",
                "dose_unit": "ml",
                "frequency": "BD",
                "duration_days": 7
            }
        ]
        report = SafetyPreflightEngine.evaluate(self.conn, patient_id="pat-syn-002", prescription_items=items)
        self.assertEqual(report["overall_state"], "PASS")
        self.assertIn("coverage", report)
        self.assertIn("rule_set_version", report)
        self.assertEqual(report["rule_set_version"], "v1.0-preflight")

if __name__ == "__main__":
    unittest.main()

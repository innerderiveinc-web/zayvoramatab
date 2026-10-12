"""Unit and Integration Tests: Deterministic Safety Preflight Engine."""

import unittest
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.domains.prescriptions.safety_preflight import SafetyPreflightEngine

class TestSafetyPreflight(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_allergy_conflict_triggers_critical_block(self):
        """Synthetic patient 'pat-syn-001' has severe allergy to Roghan Badam Shireen (Almond).
        Prescribing Majoon Arad Khurma (which contains Roghan Badam) must yield BLOCK."""
        conn = self.db_manager.get_connection()
        try:
            items = [
                {
                    "item_name": "Majoon Arad Khurma",
                    "formulation_id": "form-majoon-arad",
                    "dose_amount": "10",
                    "dose_unit": "g",
                    "frequency": "BD"
                }
            ]
            report = SafetyPreflightEngine.evaluate(conn, patient_id="pat-syn-001", prescription_items=items)
            self.assertEqual(report["overall_state"], "BLOCK")
            allergy_findings = [f for f in report["findings"] if "ALLERGY" in f["rule"]]
            self.assertTrue(len(allergy_findings) > 0)
        finally:
            conn.close()

    def test_schedule_e1_toxin_without_mudabbar_triggers_block(self):
        """Prescribing Habb-e-Azaarqi (contains Kuchla / Strychnos nux-vomica) without certified
        Mudabbar detoxification must trigger BLOCK."""
        conn = self.db_manager.get_connection()
        try:
            items = [
                {
                    "item_name": "Habb-e-Azaarqi",
                    "formulation_id": "form-hab-azaarqi",
                    "dose_amount": "1",
                    "dose_unit": "g",
                    "frequency": "OD",
                    "is_mudabbar_certified": False
                }
            ]
            report = SafetyPreflightEngine.evaluate(conn, patient_id="pat-syn-002", prescription_items=items)
            self.assertEqual(report["overall_state"], "BLOCK")
            mudabbar_findings = [f for f in report["findings"] if f["rule"] == "SCHEDULE_E1_MUDABBAR_REQUIRED"]
            self.assertTrue(len(mudabbar_findings) > 0)
        finally:
            conn.close()

    def test_pregnancy_contraindication_triggers_block(self):
        """Prescribing Abhal (Juniperus communis) to a pregnant patient must trigger BLOCK."""
        conn = self.db_manager.get_connection()
        try:
            # Add formulation containing Abhal
            conn.execute("""
                INSERT INTO formulations (id, name, dosage_form, standard_indication, is_verified)
                VALUES ('form-test-abhal', 'Majoon Abhal Test', 'MAJOON', 'Amenorrhea', 1);
            """)
            conn.execute("""
                INSERT INTO formulation_ingredients (id, formulation_id, ingredient_id, quantity_mg)
                VALUES ('fi-test-abhal', 'form-test-abhal', 'ing-abhal', 2000);
            """)
            conn.commit()

            items = [
                {
                    "item_name": "Majoon Abhal Test",
                    "formulation_id": "form-test-abhal",
                    "dose_amount": "5",
                    "dose_unit": "g",
                    "frequency": "BD"
                }
            ]
            report = SafetyPreflightEngine.evaluate(conn, patient_id="pat-syn-002", prescription_items=items, is_pregnant=True)
            self.assertEqual(report["overall_state"], "BLOCK")
            preg_findings = [f for f in report["findings"] if f["rule"] == "PREGNANCY_CONTRAINDICATION"]
            self.assertTrue(len(preg_findings) > 0)
        finally:
            conn.close()

    def test_safe_prescription_yields_pass(self):
        """Prescribing Sharbat Bazoori Motadil to a patient without allergies must yield PASS."""
        conn = self.db_manager.get_connection()
        try:
            items = [
                {
                    "item_name": "Sharbat Bazoori Motadil",
                    "formulation_id": "form-sharbat-bazoori",
                    "dose_amount": "20",
                    "dose_unit": "ml",
                    "frequency": "BD"
                }
            ]
            report = SafetyPreflightEngine.evaluate(conn, patient_id="pat-syn-002", prescription_items=items)
            self.assertEqual(report["overall_state"], "PASS")
            self.assertEqual(len(report["findings"]), 0)
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()

"""Unit and Integration Tests: Prescription Signing, Safety Blocking, and Immutability."""

import unittest
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.domains.prescriptions import PrescriptionService
from matab.core.errors import SafetyBlockedError, ForbiddenError, ValidationError

class TestPrescriptionSigning(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_safety_blocked_prescription_cannot_be_signed(self):
        """A prescription with safety state BLOCK must abort signing with SafetyBlockedError."""
        conn = self.db_manager.get_connection()
        try:
            # Prescribe allergen to pat-syn-001 (allergic to Badam)
            draft = PrescriptionService.save_prescription_draft(
                conn=conn,
                encounter_id="enc-syn-101",
                patient_id="pat-syn-001",
                hakeem_id="prac-hakeem-1",
                items=[
                    {
                        "item_name": "Majoon Arad Khurma",
                        "formulation_id": "form-majoon-arad",
                        "dose_amount": "10",
                        "dose_unit": "g",
                        "frequency": "BD"
                    }
                ]
            )
            self.assertEqual(draft["overall_safety_state"], "BLOCK")

            # Signing must be blocked
            with self.assertRaises(SafetyBlockedError):
                PrescriptionService.sign_prescription(
                    conn=conn,
                    prescription_id=draft["id"],
                    practitioner_id="prac-hakeem-1",
                    pin="1234"
                )
        finally:
            conn.close()

    def test_incorrect_pin_fails_signing(self):
        conn = self.db_manager.get_connection()
        try:
            # Safe formula
            draft = PrescriptionService.save_prescription_draft(
                conn=conn,
                encounter_id="enc-syn-102",
                patient_id="pat-syn-002",
                hakeem_id="prac-hakeem-1",
                items=[
                    {
                        "item_name": "Sharbat Bazoori Motadil",
                        "formulation_id": "form-sharbat-bazoori",
                        "dose_amount": "20",
                        "dose_unit": "ml",
                        "frequency": "BD"
                    }
                ]
            )
            self.assertEqual(draft["overall_safety_state"], "PASS")

            # Invalid PIN
            with self.assertRaises(ForbiddenError):
                PrescriptionService.sign_prescription(
                    conn=conn,
                    prescription_id=draft["id"],
                    practitioner_id="prac-hakeem-1",
                    pin="9999" # Incorrect PIN
                )
        finally:
            conn.close()

    def test_successful_safe_signing_and_immutability(self):
        conn = self.db_manager.get_connection()
        try:
            draft = PrescriptionService.save_prescription_draft(
                conn=conn,
                encounter_id="enc-syn-102",
                patient_id="pat-syn-002",
                hakeem_id="prac-hakeem-1",
                items=[
                    {
                        "item_name": "Sharbat Bazoori Motadil",
                        "formulation_id": "form-sharbat-bazoori",
                        "dose_amount": "20",
                        "dose_unit": "ml",
                        "frequency": "BD"
                    }
                ]
            )

            # Valid sign with PIN '1234'
            signed = PrescriptionService.sign_prescription(
                conn=conn,
                prescription_id=draft["id"],
                practitioner_id="prac-hakeem-1",
                pin="1234"
            )
            self.assertEqual(signed["status"], "SIGNED")
            self.assertIsNotNone(signed["signature_hash"])
            self.assertEqual(len(signed["signature_hash"]), 64) # SHA-256 hex length
            self.assertIsNotNone(signed["signature_timestamp"])

            # Immutability check: cannot sign again
            with self.assertRaises(ValidationError):
                PrescriptionService.sign_prescription(
                    conn=conn,
                    prescription_id=draft["id"],
                    practitioner_id="prac-hakeem-1",
                    pin="1234"
                )
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()

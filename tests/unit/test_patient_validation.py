"""Unit Tests: Patient Validation, Normalization, Duplicate Rules, and Lifecycle Constraints."""

import unittest
from apps.api.domains.patients import normalize_phone, normalize_string, PatientService
from apps.api.domains.encounters import ALLOWED_TRANSITIONS

class TestPatientValidation(unittest.TestCase):
    def test_phone_normalization(self):
        self.assertEqual(normalize_phone("+91 98765-43210"), "9876543210")
        self.assertEqual(normalize_phone("(011) 2327-8900"), "01123278900")
        self.assertEqual(normalize_phone("09876543210"), "9876543210")
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_string_normalization_unicode(self):
        # Urdu Unicode
        self.assertEqual(normalize_string("  محمد   عرفان  "), "محمد عرفان")
        # Hindi Unicode
        self.assertEqual(normalize_string("  फातिमा  ज़हरा  "), "फातिमा ज़हरा")
        # English with extra spacing and mixed case
        self.assertEqual(normalize_string("  Hakeem   TARIQ  Ahmad  "), "hakeem tariq ahmad")
        self.assertEqual(normalize_string(None), "")

    def test_encounter_allowed_transitions(self):
        # DRAFT can transition to IN_PROGRESS or CANCELLED
        self.assertIn("IN_PROGRESS", ALLOWED_TRANSITIONS["DRAFT"])
        self.assertIn("CANCELLED", ALLOWED_TRANSITIONS["DRAFT"])
        self.assertNotIn("COMPLETED", ALLOWED_TRANSITIONS["DRAFT"])

        # IN_PROGRESS can transition to COMPLETED or CANCELLED
        self.assertIn("COMPLETED", ALLOWED_TRANSITIONS["IN_PROGRESS"])
        self.assertIn("CANCELLED", ALLOWED_TRANSITIONS["IN_PROGRESS"])
        self.assertNotIn("DRAFT", ALLOWED_TRANSITIONS["IN_PROGRESS"])

        # COMPLETED and CANCELLED are terminal states
        self.assertEqual(ALLOWED_TRANSITIONS["COMPLETED"], [])
        self.assertEqual(ALLOWED_TRANSITIONS["CANCELLED"], [])

if __name__ == "__main__":
    unittest.main()

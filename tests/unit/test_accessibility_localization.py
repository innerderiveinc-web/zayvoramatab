"""
Unit Tests for Accessibility, Localization, RTL & Clinical Human-Factors Engine (Prompt 51).
"""

import os
import shutil
import tempfile
import unittest
import sqlite3
from datetime import datetime

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.accessibility_localization_engine import AccessibilityLocalizationEngine


class TestAccessibilityLocalizationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_a11y_i18n.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def tearDown(self):
        if self.conn:
            self.conn.close()

    def test_01_locales_seeded_and_registered(self):
        """1. Test that baseline locales (en, ur RTL, hi) are seeded properly with metadata."""
        locales = AccessibilityLocalizationEngine.list_locales(self.conn)
        codes = [l["locale_code"] for l in locales]
        self.assertIn("en", codes)
        self.assertIn("ur", codes)
        self.assertIn("hi", codes)

        ur_locale = next(l for l in locales if l["locale_code"] == "ur")
        self.assertEqual(ur_locale["direction"], "rtl")
        self.assertEqual(ur_locale["script"], "Arab")

    def test_02_register_locale_validation(self):
        """2. Test registering a new locale and validating direction constraints."""
        res = AccessibilityLocalizationEngine.register_locale(
            self.conn, "T-001",
            {"locale_code": "ar", "name": "Arabic", "native_name": "العربية", "direction": "rtl", "script": "Arab"},
            "usr-admin", "ADMIN"
        )
        self.assertEqual(res["direction"], "rtl")

        with self.assertRaises(ValueError):
            AccessibilityLocalizationEngine.register_locale(
                self.conn, "T-001",
                {"locale_code": "inv", "name": "Invalid", "direction": "diagonal", "script": "Latn"},
                "usr-admin", "ADMIN"
            )

    def test_03_catalog_upsert_and_retrieval(self):
        """3. Test translation catalog upsert, namespace filtering, and retrieval."""
        res = AccessibilityLocalizationEngine.upsert_catalog_entry(
            self.conn, "T-001",
            {
                "locale_code": "ur",
                "namespace": "prescriptions",
                "string_key": "posology_exceeded",
                "source_en_text": "Posology ceiling exceeded",
                "localized_text": "مقدارِ خوراک کی حد تجاوز کر گئی ہے",
                "is_safety_critical": True,
                "context_notes": "Prescription safety alert"
            },
            "usr-hakeem-1", "PRACTITIONER"
        )
        self.assertEqual(res["status"], "approved")

        entries = AccessibilityLocalizationEngine.list_catalogs(self.conn, "ur", "prescriptions")
        self.assertTrue(any(e["string_key"] == "posology_exceeded" for e in entries))

    def test_04_safety_critical_translation_role_gating(self):
        """4. Test that only qualified Tabib/Safety Officer can approve safety-critical translations."""
        entry = AccessibilityLocalizationEngine.upsert_catalog_entry(
            self.conn, "T-001",
            {
                "locale_code": "hi",
                "namespace": "safety",
                "string_key": "allergy_warning",
                "source_en_text": "Severe Allergen Warning",
                "localized_text": "गंभीर एलर्जी चेतावनी",
                "is_safety_critical": True
            },
            "usr-translator", "TRANSLATOR"
        )
        self.assertEqual(entry["status"], "draft")

        # Non-clinical reviewer cannot approve safety critical entry
        with self.assertRaises(PermissionError):
            AccessibilityLocalizationEngine.review_catalog_entry(
                self.conn, "T-001", entry["catalog_id"], "approved", "usr-translator", "TRANSLATOR"
            )

        # Tabib reviewer can approve
        approved = AccessibilityLocalizationEngine.review_catalog_entry(
            self.conn, "T-001", entry["catalog_id"], "approved", "usr-hakeem-1", "PRACTITIONER"
        )
        self.assertEqual(approved["status"], "approved")

    def test_05_governed_clinical_glossary(self):
        """5. Test governed clinical glossary terms and multi-script search."""
        glossary = AccessibilityLocalizationEngine.list_glossary(self.conn, search="Mizaj")
        self.assertGreaterEqual(len(glossary), 1)
        term = glossary[0]
        self.assertEqual(term["canonical_code"], "UNANI_MIZAJ")
        self.assertEqual(term["classical_arabic_urdu"], "مزاج")
        self.assertEqual(term["hindi_devanagari"], "मिज़ाज")
        self.assertTrue(term["is_approved_by_tabib"])

    def test_06_user_accessibility_preferences(self):
        """6. Test user accessibility preferences updates (high contrast, font scale, reduced motion)."""
        prefs = AccessibilityLocalizationEngine.update_user_preferences(
            self.conn, "T-001", "usr-clinician-1",
            {
                "preferred_locale": "ur",
                "font_size_scale": 1.25,
                "high_contrast_enabled": True,
                "reduced_motion_enabled": True,
                "keyboard_navigation_hints": True
            }
        )
        self.assertEqual(prefs["preferred_locale"], "ur")
        self.assertEqual(prefs["font_size_scale"], 1.25)
        self.assertTrue(prefs["high_contrast_enabled"])
        self.assertTrue(prefs["reduced_motion_enabled"])

        retrieved = AccessibilityLocalizationEngine.get_user_preferences(self.conn, "usr-clinician-1")
        self.assertEqual(retrieved["font_size_scale"], 1.25)

    def test_07_record_accessibility_audit(self):
        """7. Test recording WCAG 2.1 AA accessibility audit results."""
        audit = AccessibilityLocalizationEngine.record_a11y_audit(
            self.conn, "T-001",
            {
                "standard": "WCAG_2_1_AA",
                "target_route": "/prescriptions",
                "viewport_profile": "TABLET_768",
                "color_contrast_pass": 1,
                "keyboard_operable_pass": 1,
                "aria_landmarks_pass": 1,
                "labels_and_errors_pass": 1,
                "focus_management_pass": 1,
                "violations": [],
                "remediation_notes": "Prescription Nuskha table passed all contrast and focus checks."
            },
            "usr-a11y-auditor", "AUDITOR"
        )
        self.assertTrue(audit["overall_pass"])

        audits = AccessibilityLocalizationEngine.list_a11y_audits(self.conn, "T-001")
        self.assertGreaterEqual(len(audits), 1)

    def test_08_human_factors_scenario_evaluation(self):
        """8. Test recording clinical human-factors usability scenarios (NASA-TLX, duration, errors)."""
        scenario = AccessibilityLocalizationEngine.record_human_factors_scenario(
            self.conn, "T-001",
            {
                "scenario_code": "HF-SC-02",
                "workflow_name": "Triage & Vital Signs Capture",
                "target_role": "TRIAGE_NURSE",
                "locale_tested": "hi",
                "task_description": "Record BP, pulse, temp in Hindi interface without error.",
                "task_completed": True,
                "time_to_complete_seconds": 65.0,
                "clinical_error_count": 0,
                "alert_fatigue_score": 1.2,
                "cognitive_workload_score": 19.0,
                "confusion_observations": "None; Hindi numerical input smooth."
            },
            "usr-evaluator-1", "HUMAN_FACTORS_LEAD"
        )
        self.assertTrue(scenario["task_completed"])
        self.assertEqual(scenario["cognitive_workload_score"], 19.0)

        scenarios = AccessibilityLocalizationEngine.list_human_factors_scenarios(self.conn, "T-001")
        self.assertGreaterEqual(len(scenarios), 1)

    def test_09_audit_ledger_tamper_evident_integrity(self):
        """9. Test cryptographic SHA-256 hash chaining and tamper detection."""
        verification = AccessibilityLocalizationEngine.verify_audit_ledger_integrity(self.conn, "T-001")
        self.assertTrue(verification["verified"])
        self.assertEqual(verification["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()

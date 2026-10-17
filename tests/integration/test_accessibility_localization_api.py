"""
Integration Tests for Accessibility, Localization, RTL & Clinical Human-Factors REST APIs (Prompt 51).
"""

import os
import json
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestAccessibilityLocalizationApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_a11y_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Admin login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_list_locales_api(self):
        """1. GET /api/v1/a11y-i18n/locales - List supported interface locales."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/locales",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("locales", data)
        self.assertGreaterEqual(len(data["locales"]), 3)

    def test_02_register_locale_api(self):
        """2. POST /api/v1/a11y-i18n/locales - Register a new locale with direction and script."""
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/a11y-i18n/locales",
            self.admin_headers,
            {},
            json.dumps({
                "locale_code": "fa",
                "name": "Persian",
                "native_name": "فارسی",
                "direction": "rtl",
                "script": "Arab"
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["locale_code"], "fa")
        self.assertEqual(data["direction"], "rtl")

    def test_03_catalogs_upsert_and_query_api(self):
        """3. POST & GET /api/v1/a11y-i18n/catalogs - Upsert and list translation entries."""
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/a11y-i18n/catalogs",
            self.admin_headers,
            {},
            json.dumps({
                "locale_code": "ur",
                "namespace": "billing",
                "string_key": "invoice_total",
                "source_en_text": "Total Amount Due",
                "localized_text": "کل واجب الادا رقم",
                "is_safety_critical": False,
                "context_notes": "Invoice billing total label"
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)

        # Query catalog
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/catalogs",
            self.admin_headers,
            {"locale": "ur", "namespace": "billing"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("entries", data)
        self.assertTrue(any(e["string_key"] == "invoice_total" for e in data["entries"]))

    def test_04_review_catalog_entry_api(self):
        """4. POST /api/v1/a11y-i18n/catalogs/{id}/review - Review and approve translation entry."""
        # Create draft entry
        _, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/a11y-i18n/catalogs",
            self.admin_headers,
            {},
            json.dumps({
                "locale_code": "hi",
                "namespace": "triage",
                "string_key": "blood_pressure",
                "source_en_text": "Blood Pressure (mmHg)",
                "localized_text": "रक्तचाप (mmHg)",
                "is_safety_critical": True
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        cat_id = json.loads(body.decode("utf-8"))["catalog_id"]

        # Review entry
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/a11y-i18n/catalogs/{cat_id}/review",
            self.admin_headers,
            {},
            json.dumps({"status": "approved"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "approved")

    def test_05_clinical_glossary_api(self):
        """5. GET & POST /api/v1/a11y-i18n/glossary - Manage governed clinical glossary terms."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/glossary",
            self.admin_headers,
            {"q": "Mudabbar"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(data["terms"]), 1)
        self.assertEqual(data["terms"][0]["canonical_code"], "UNANI_MUDABBAR")

    def test_06_user_preferences_api(self):
        """6. GET & PUT /api/v1/a11y-i18n/preferences/{user_id} - User a11y preferences."""
        status, _, body = ApiRouter.dispatch(
            "PUT",
            "/api/v1/a11y-i18n/preferences/usr-doctor-42",
            self.admin_headers,
            {},
            json.dumps({
                "preferred_locale": "ur",
                "font_size_scale": 1.15,
                "high_contrast_enabled": True,
                "reduced_motion_enabled": False,
                "keyboard_navigation_hints": True
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["preferred_locale"], "ur")
        self.assertTrue(data["high_contrast_enabled"])

        # Fetch
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/preferences/usr-doctor-42",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        fetched = json.loads(body.decode("utf-8"))
        self.assertEqual(fetched["font_size_scale"], 1.15)

    def test_07_record_and_list_a11y_audits_api(self):
        """7. POST & GET /api/v1/a11y-i18n/a11y-audits - Record and query WCAG 2.1 AA audits."""
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/a11y-i18n/a11y-audits",
            self.admin_headers,
            {},
            json.dumps({
                "target_route": "/today",
                "standard": "WCAG_2_1_AA",
                "viewport_profile": "MOBILE_375",
                "color_contrast_pass": 1,
                "keyboard_operable_pass": 1,
                "aria_landmarks_pass": 1,
                "labels_and_errors_pass": 1,
                "focus_management_pass": 1,
                "violations": [],
                "remediation_notes": "Mobile queue cards meet 44px touch targets and 4.5:1 contrast."
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["overall_pass"])

        # List audits
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/a11y-audits",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        audits_data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(audits_data["audits"]), 1)

    def test_08_human_factors_scenarios_api(self):
        """8. POST & GET /api/v1/a11y-i18n/human-factors/scenarios - Clinical usability scenarios."""
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/a11y-i18n/human-factors/scenarios",
            self.admin_headers,
            {},
            json.dumps({
                "scenario_code": "HF-SC-03",
                "workflow_name": "Emergency Break-Glass Consultation",
                "target_role": "PRACTITIONER",
                "locale_tested": "en",
                "task_description": "Execute break-glass clinical chart access, review past allergies, prescribe emergency antidote.",
                "task_completed": 1,
                "time_to_complete_seconds": 45.0,
                "clinical_error_count": 0,
                "alert_fatigue_score": 1.0,
                "cognitive_workload_score": 15.0,
                "confusion_observations": "None; break-glass modal clear and non-blocking in urgent care.",
                "evaluator_notes": "Physician accessed antidote dosing in under 50 seconds."
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)

        # List scenarios
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/human-factors/scenarios",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        hf_data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(hf_data["scenarios"]), 1)

    def test_09_audit_ledger_and_verification_api(self):
        """9. GET & POST /api/v1/a11y-i18n/audit - Audit ledger query and tamper verification."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/audit",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        ledger_data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(ledger_data["records"]), 1)

        # Verify integrity
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/a11y-i18n/audit/verify",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        verify_data = json.loads(body.decode("utf-8"))
        self.assertTrue(verify_data["verified"])
        self.assertEqual(verify_data["status"], "VERIFIED")

    def test_10_unauthorized_access_denied(self):
        """10. Test that requests without authentication token return 401 Unauthorized."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/a11y-i18n/locales",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

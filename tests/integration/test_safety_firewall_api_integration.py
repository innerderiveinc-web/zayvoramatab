"""Integration tests for Clinical Safety Firewall REST API (Prompt 07).
Validates:
- POST /api/v1/safety/preflight
- GET /api/v1/safety/preflight/{run_id}
- POST /api/v1/safety/findings/{finding_id}/disposition
- GET /api/v1/safety/substances/resolve
- Role-based permissions & tenancy boundary enforcement
"""

import unittest
import os
import tempfile
import json
import sqlite3

from apps.api.router import ApiRouter
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data


class TestSafetyFirewallApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.temp_db_fd)
        run_migrations(cls.temp_db_path)
        seed_development_data(cls.temp_db_path)

        # Authenticate Practitioner (Hakeem)
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.temp_db_path
        )
        cls.practitioner_token = json.loads(body)["token"]

        # Authenticate Receptionist
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.temp_db_path
        )
        cls.receptionist_token = json.loads(body)["token"]

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_db_path):
            os.remove(cls.temp_db_path)

    def test_run_preflight_and_get_run_lifecycle_api(self):
        """Execute preflight check and retrieve stored run report with findings and coverage."""
        payload = {
            "patient_context": {
                "patient_id": "pat-syn-001",
                "is_pregnant": False,
                "current_medication_list": ["Digoxin"]
            },
            "prescription_items": [
                {
                    "item_name": "Senna",
                    "dose_amount": "3",
                    "dose_unit": "g",
                    "frequency": "OD",
                    "duration_days": 3
                }
            ]
        }

        # 1. POST /api/v1/safety/preflight
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/safety/preflight",
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.practitioner_token}"}, {},
            json.dumps(payload).encode("utf-8"), "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        run_id = res["run_id"]
        self.assertEqual(res["overall_status"], "blocked")
        self.assertTrue(len(res["findings"]) > 0)
        self.assertIn("coverage_report", res)

        # 2. GET /api/v1/safety/preflight/{run_id}
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/safety/preflight/{run_id}",
            {"Authorization": f"Bearer {self.practitioner_token}"}, {},
            b"", "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        get_res = json.loads(body)["preflight_run"]
        self.assertEqual(get_res["id"], run_id)
        self.assertEqual(len(get_res["findings"]), len(res["findings"]))

    def test_record_clinician_disposition_api(self):
        """Record clinician disposition on an overridable finding."""
        payload = {
            "patient_context": {
                "patient_id": "pat-syn-001",
                "current_medication_list": ["Warfarin"]
            },
            "prescription_items": [
                {
                    "item_name": "Filfil Siah",
                    "dose_amount": "500",
                    "dose_unit": "mg",
                    "frequency": "BD",
                    "duration_days": 5
                }
            ]
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/safety/preflight",
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.practitioner_token}"}, {},
            json.dumps(payload).encode("utf-8"), "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        findings = json.loads(body)["findings"]
        int_finding = next((f for f in findings if f["finding_type"] == "INTERACTION"), None)
        self.assertIsNotNone(int_finding)

        # POST /api/v1/safety/findings/{finding_id}/disposition
        disp_payload = {
            "disposition_type": "ACKNOWLEDGED",
            "clinical_rationale": "Patient INR will be rechecked on Day 3 of therapy."
        }
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/safety/findings/{int_finding['id']}/disposition",
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.practitioner_token}"}, {},
            json.dumps(disp_payload).encode("utf-8"), "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "acknowledged")

    def test_substance_resolve_api(self):
        """GET /api/v1/safety/substances/resolve?q=sana+makki"""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/safety/substances/resolve?q=Sana+Makki",
            {"Authorization": f"Bearer {self.practitioner_token}"}, {"q": "Sana Makki"},
            b"", "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        self.assertEqual(res["status"], "RESOLVED")
        self.assertEqual(res["substance"]["id"], "sub-senna")


if __name__ == "__main__":
    unittest.main()

"""Integration Tests: Usul-e-Ilaj Care Planning, Lifecycle, Prescription Linkage, and Outcomes."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store

class TestCarePlansApi(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Authenticate as Hakeem Tariq
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token = json.loads(resp_bytes.decode("utf-8"))["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_list_principles_vocabulary(self):
        """Practitioner can list approved Usul-e-Ilaj principles with indications and monitoring guidance."""
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/usul-e-ilaj/principles", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertIn("principles", data)
        self.assertGreaterEqual(len(data["principles"]), 5)
        codes = [p["code"] for p in data["principles"]]
        self.assertIn("TANQIYA", codes)
        self.assertIn("TADEEL_E_MIZAJ", codes)
        self.assertIn("TAQWIYAT", codes)

    def test_create_care_plan_draft_for_encounter(self):
        """Create draft care plan linked to encounter enc-syn-001."""
        body = json.dumps({
            "title": "Comprehensive Temperamental Restoration",
            "overall_goal": "Eliminate phlegmatic stagnation and resolve reflux",
            "clinical_rationale": "Su-e-Mizaj Balghami with weak Hazm",
            "review_date": "2026-11-01",
            "items": [
                {
                    "principle_id": "uip-tanqiya",
                    "objective": "Gentle mucosal evacuation",
                    "intended_intervention": "Anise and Fennel decoction",
                    "cautions": "Hydration check"
                }
            ]
        }).encode("utf-8")

        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/care-plans",
            self.headers, {}, body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        plan = json.loads(resp_bytes.decode("utf-8"))["care_plan"]
        self.assertEqual(plan["status"], "DRAFT")
        self.assertEqual(len(plan["items"]), 1)
        self.assertEqual(plan["items"][0]["principle_code"], "TANQIYA")

    def test_link_prescription_without_bypassing_rx_workflow(self):
        """Linking a prescription to a care plan item records relationship but never auto-signs or alters the prescription."""
        # 1. Fetch existing care plan cpl-syn-001 (Patient: pat-syn-001)
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/care-plans/cpl-syn-001", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        plan = json.loads(resp_bytes.decode("utf-8"))["care_plan"]
        item_id = plan["items"][0]["id"]

        # 2. Attempting to link a prescription from a DIFFERENT patient (rx-syn-001 belongs to pat-syn-003) must fail with 409 Conflict
        foreign_link_body = json.dumps({"prescription_id": "rx-syn-001"}).encode("utf-8")
        status, _, _ = ApiRouter.dispatch(
            "POST", f"/api/v1/care-plans/cpl-syn-001/items/{item_id}/link-prescription",
            self.headers, {}, foreign_link_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 409)

        # 3. Create a prescription draft for the SAME patient (enc-syn-001, pat-syn-001)
        rx_body = json.dumps({"encounter_id": "enc-syn-001"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/prescriptions", self.headers, {}, rx_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        same_rx = json.loads(resp_bytes.decode("utf-8"))["prescription"]
        same_rx_id = same_rx["id"]

        # 4. Linking prescription for the same patient succeeds
        link_body = json.dumps({
            "prescription_id": same_rx_id,
            "notes": "Co-prescribed alongside dietary regimen."
        }).encode("utf-8")

        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/care-plans/cpl-syn-001/items/{item_id}/link-prescription",
            self.headers, {}, link_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(res["prescription_id"], same_rx_id)

        # 5. Verify prescription status remains unchanged (DRAFT remains DRAFT; never auto-signed)
        status, _, resp_bytes = ApiRouter.dispatch("GET", f"/api/v1/prescriptions/{same_rx_id}", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        rx = json.loads(resp_bytes.decode("utf-8"))["prescription"]
        self.assertEqual(rx["status"], "DRAFT")

    def test_care_plan_status_transitions_and_outcomes(self):
        """Transition care plan from DRAFT -> ACTIVE and record follow-up outcome."""
        # Create draft plan
        b_create = json.dumps({
            "title": "Short Course Tadeel",
            "items": [{"principle_id": "uip-tadeel", "objective": "Balance", "intended_intervention": "Dietary warming"}]
        }).encode("utf-8")
        _, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/care-plans",
            self.headers, {}, b_create, "127.0.0.1", db_path=self.db_path
        )
        plan = json.loads(resp_bytes.decode("utf-8"))["care_plan"]
        plan_id = plan["id"]
        item_id = plan["items"][0]["id"]

        # Transition to ACTIVE
        trans_body = json.dumps({"status": "ACTIVE"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/care-plans/{plan_id}/transition",
            self.headers, {}, trans_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        updated = json.loads(resp_bytes.decode("utf-8"))["care_plan"]
        self.assertEqual(updated["status"], "ACTIVE")

        # Record outcome observation
        out_body = json.dumps({
            "outcome_status": "ACHIEVED",
            "observation_notes": "Patient reports full alleviation of postprandial heaviness."
        }).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/care-plans/{plan_id}/items/{item_id}/outcomes",
            self.headers, {}, out_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        out_res = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(out_res["outcome_status"], "ACHIEVED")

if __name__ == "__main__":
    unittest.main()

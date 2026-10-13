"""
Integration Test Suite for Controlled Pilot Launch REST APIs (Prompt 14)
ZAYVORA MATAB OS — Independent Standalone Product
"""

import json
import os
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestPilotLaunchApi(unittest.TestCase):
    """End-to-end REST API integration tests for Pilot Launch & Operations."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self._ip_counter = 70

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
        client_ip = f"10.0.14.{self._ip_counter}"
        body_bytes = json.dumps({"username": username, "password": password}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login", {}, {}, body_bytes, client_ip, db_path=self.db_path
        )
        self.assertEqual(status, 200)
        return json.loads(resp_bytes.decode("utf-8"))["token"]

    def _req(self, method: str, path: str, token: str, body: dict = None):
        self._ip_counter += 1
        client_ip = f"10.0.14.{self._ip_counter}"
        headers = {"Authorization": f"Bearer {token}", "x-facility-id": self.fac_id}
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, _, resp_bytes = ApiRouter.dispatch(
            method, path, headers, {}, body_bytes, client_ip, db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def test_01_pilot_program_and_scope_api(self):
        """Verify pilot program creation, listing, and scope declaration."""
        # 1. Create program as Admin
        status, res = self._req("POST", "/api/v1/pilot/programs", self.admin_token, {
            "code": "PILOT-API-TEST",
            "name": "Integration Test Pilot Program",
            "description": "Testing scope REST endpoints"
        })
        self.assertEqual(status, 201)
        prog_id = res["pilot_program"]["id"]

        # 2. List programs
        status, list_res = self._req("GET", "/api/v1/pilot/programs", self.admin_token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(list_res["pilot_programs"]), 1)

        # 3. Declare scope version
        status, scope_res = self._req("POST", f"/api/v1/pilot/programs/{prog_id}/scope", self.admin_token, {
            "enabled_modules": ["PATIENT_REGISTRY", "UNIFIED_CONSULTATION"],
            "disabled_modules": ["ABDM_LIVE_SYNC"],
            "permitted_roles": ["CHIEF_TABIB", "TABIB"],
            "permitted_facilities": [self.fac_id]
        })
        self.assertEqual(status, 201)
        self.assertEqual(scope_res["scope"]["version_number"], 1)

    def test_02_eligibility_gate_and_activation_api(self):
        """Verify eligibility gate evaluation and activation."""
        prog_id = "plt-prog-2026-q4"

        # 1. Evaluate eligibility
        status, elig_res = self._req("GET", f"/api/v1/pilot/programs/{prog_id}/eligibility", self.admin_token)
        self.assertEqual(status, 200)
        self.assertIn("eligibility", elig_res)
        self.assertIn("gates", elig_res["eligibility"])

        # 2. Activate program
        status, act_res = self._req("POST", f"/api/v1/pilot/programs/{prog_id}/activate", self.admin_token, {})
        self.assertEqual(status, 200)
        self.assertEqual(act_res["status"], "ACTIVATED")

        # 3. Non-admin activation attempt rejected
        status, _ = self._req("POST", f"/api/v1/pilot/programs/{prog_id}/activate", self.reception_token, {})
        self.assertIn(status, [401, 403])

    def test_03_facility_checklist_api(self):
        """Verify retrieval and updating of 13-stage facility onboarding checklist."""
        prog_id = "plt-prog-2026-q4"

        # Get checklist
        status, chk_res = self._req(
            "GET", f"/api/v1/pilot/programs/{prog_id}/facilities/{self.fac_id}/checklist", self.admin_token
        )
        self.assertEqual(status, 200)
        checklist = chk_res["checklist"]
        self.assertEqual(len(checklist), 13)

        # Update stage 1
        stage_1_id = checklist[0]["id"]
        status, upd_res = self._req("POST", f"/api/v1/pilot/checklists/{stage_1_id}/update", self.admin_token, {
            "status": "COMPLETED",
            "evidence_notes": "Prompt 13 audit passed and signed off."
        })
        self.assertEqual(status, 200)
        self.assertEqual(upd_res["stage"]["status"], "COMPLETED")

    def test_04_data_migration_dry_run_api(self):
        """Verify DRY_RUN data migration via REST API."""
        prog_id = "plt-prog-2026-q4"

        status, mig_res = self._req("POST", "/api/v1/pilot/migrations/run", self.admin_token, {
            "pilot_program_id": prog_id,
            "facility_id": self.fac_id,
            "source_system_name": "Legacy Clinic Register",
            "source_authority_reference": "MIG-AUTH-2026-001",
            "raw_records": [
                {"name": "Patient Alpha", "phone": "+91-9911223344", "gender": "MALE", "dob": "1988-06-15"}
            ],
            "mode": "DRY_RUN"
        })
        self.assertEqual(status, 200)
        r = mig_res["migration_result"]
        self.assertEqual(r["mode"], "DRY_RUN")
        self.assertEqual(r["total_records_read"], 1)
        self.assertEqual(r["records_migrated"], 0)

    def test_05_support_tickets_and_safety_queue_api(self):
        """Verify support ticket submission and clinical safety review queue."""
        prog_id = "plt-prog-2026-q4"

        # Submit ticket
        status, tkt_res = self._req("POST", "/api/v1/pilot/tickets", self.hakeem_token, {
            "pilot_program_id": prog_id,
            "facility_id": self.fac_id,
            "category": "CLINICAL_SAFETY_INCIDENT",
            "severity": "SEV_1_CRITICAL",
            "subject": "Ingredient toxicity alert clarification",
            "safe_description": "Query regarding Mudabbar verification rules on Azaraqi."
        })
        self.assertEqual(status, 201)
        self.assertEqual(tkt_res["ticket"]["category"], "CLINICAL_SAFETY_INCIDENT")

        # View clinical safety queue as Admin
        status, queue_res = self._req("GET", f"/api/v1/pilot/programs/{prog_id}/safety-queue", self.admin_token)
        self.assertEqual(status, 200)
        queue = queue_res["clinical_safety_queue"]
        self.assertGreaterEqual(len(queue), 1)

        # Resolve incident
        inc_id = queue[0]["id"]
        status, res_res = self._req("POST", f"/api/v1/pilot/safety-queue/{inc_id}/resolve", self.admin_token, {
            "governance_action": "NO_ACTION",
            "notes": "Verified Mudabbar certificate is mandatory as per UPI."
        })
        self.assertEqual(status, 200)
        self.assertEqual(res_res["incident"]["status"], "RESOLVED")

    def test_06_stop_condition_and_metrics_api(self):
        """Verify triggering stop condition and generating review packs."""
        prog_id = "plt-prog-2026-q4"

        # 1. Trigger stop condition
        status, stop_res = self._req("POST", "/api/v1/pilot/stop-events/trigger", self.admin_token, {
            "pilot_program_id": prog_id,
            "condition_code": "SAVE_FAILURE_LOOP",
            "action_taken": "PAUSE_PILOT_ALL",
            "containment_actions": ["HALT_NEW_CONSULTATIONS"]
        })
        self.assertEqual(status, 201)
        event_id = stop_res["stop_event"]["id"]

        # 2. Get operational metrics
        status, met_res = self._req("GET", f"/api/v1/pilot/programs/{prog_id}/metrics", self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(met_res["metrics"]["active_stop_conditions"], 1)

        # 3. Resolve stop condition
        status, _ = self._req("POST", f"/api/v1/pilot/stop-events/{event_id}/resolve", self.admin_token, {
            "resolution_notes": "Resolved by DB tuning"
        })
        self.assertEqual(status, 200)

        # 4. Generate review pack
        status, pack_res = self._req("POST", f"/api/v1/pilot/programs/{prog_id}/review-packs", self.admin_token, {
            "review_type": "WEEKLY",
            "period_start": "2026-10-13",
            "period_end": "2026-10-20",
            "recommendation": "CONTINUE_AS_PLANNED"
        })
        self.assertEqual(status, 201)
        self.assertEqual(pack_res["review_pack"]["recommendation"], "CONTINUE_AS_PLANNED")


if __name__ == "__main__":
    unittest.main()

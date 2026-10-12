"""Integration Tests: Encounter Creation, Lifecycle State Transitions, Cancellation, and Timeline."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store

class TestEncounterLifecycleApi(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Login as Hakeem Tariq (Practitioner)
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token_hakeem = json.loads(resp.decode("utf-8"))["token"]
        self.headers_hakeem = {"authorization": f"Bearer {self.token_hakeem}"}

        # Login as Receptionist (Farhan Ali)
        login_body_r = json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_r, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token_reception = json.loads(resp.decode("utf-8"))["token"]
        self.headers_reception = {"authorization": f"Bearer {self.token_reception}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_encounter_creation_and_token_number(self):
        """Creating an encounter sets initial status to DRAFT and allocates sequential daily token."""
        enc_body = json.dumps({
            "facility_id": "fac-central-opd",
            "encounter_type": "OPD_VISIT",
            "reason_for_visit": "Persistent migraine headaches (Sudaa)"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-001/encounters", self.headers_hakeem, {}, enc_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        data = json.loads(resp.decode("utf-8"))
        encounter = data["encounter"]

        self.assertEqual(encounter["status"], "DRAFT")
        self.assertGreaterEqual(encounter["token_number"], 1)
        self.assertEqual(encounter["encounter_type"], "OPD_VISIT")
        self.assertEqual(encounter["version"], 1)
        self.assertEqual(encounter["patient_id"], "pat-syn-001")

    def test_draft_encounter_updates_with_concurrency(self):
        """Updating draft encounter increments version; stale version update is rejected."""
        # Create draft encounter
        enc_body = json.dumps({
            "facility_id": "fac-central-opd",
            "encounter_type": "OPD_VISIT",
            "reason_for_visit": "Initial complaint"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-001/encounters", self.headers_hakeem, {}, enc_body, "127.0.0.1", db_path=self.db_path)
        enc_id = json.loads(resp.decode("utf-8"))["encounter"]["id"]

        # Valid update
        upd_body = json.dumps({
            "version": 1,
            "reason_for_visit": "Clarified chief complaint: Bilateral frontal headache"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("PATCH", f"/api/v1/encounters/{enc_id}", self.headers_hakeem, {}, upd_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        updated = json.loads(resp.decode("utf-8"))["encounter"]
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["reason_for_visit"], "Clarified chief complaint: Bilateral frontal headache")

        # Stale update with version 1 rejected
        stale_body = json.dumps({
            "version": 1,
            "reason_for_visit": "Stale edit attempt"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("PATCH", f"/api/v1/encounters/{enc_id}", self.headers_hakeem, {}, stale_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 409)

    def test_valid_encounter_lifecycle_transitions(self):
        """Lifecycle transitions flow: DRAFT -> IN_PROGRESS -> COMPLETED."""
        # Create draft encounter
        enc_body = json.dumps({"facility_id": "fac-central-opd", "encounter_type": "OPD_VISIT"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-001/encounters", self.headers_hakeem, {}, enc_body, "127.0.0.1", db_path=self.db_path)
        enc_id = json.loads(resp.decode("utf-8"))["encounter"]["id"]

        # 1. DRAFT -> IN_PROGRESS
        trans_body = json.dumps({"status": "IN_PROGRESS", "version": 1}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/encounters/{enc_id}/transition", self.headers_hakeem, {}, trans_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        enc = json.loads(resp.decode("utf-8"))["encounter"]
        self.assertEqual(enc["status"], "IN_PROGRESS")
        self.assertEqual(enc["version"], 2)

        # 2. IN_PROGRESS -> COMPLETED
        trans_body = json.dumps({"status": "COMPLETED", "version": 2}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/encounters/{enc_id}/transition", self.headers_hakeem, {}, trans_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        enc = json.loads(resp.decode("utf-8"))["encounter"]
        self.assertEqual(enc["status"], "COMPLETED")
        self.assertIsNotNone(enc["ended_at"])

        # 3. COMPLETED is terminal; cannot transition to DRAFT or IN_PROGRESS
        trans_body = json.dumps({"status": "DRAFT", "version": 3}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/encounters/{enc_id}/transition", self.headers_hakeem, {}, trans_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 400)
        err = json.loads(resp.decode("utf-8"))
        self.assertEqual(err["code"], "VALIDATION_ERROR")

    def test_cancellation_requires_reason(self):
        """Cancelling an encounter requires an explicit reason."""
        enc_body = json.dumps({"facility_id": "fac-central-opd", "encounter_type": "OPD_VISIT"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-001/encounters", self.headers_hakeem, {}, enc_body, "127.0.0.1", db_path=self.db_path)
        enc_id = json.loads(resp.decode("utf-8"))["encounter"]["id"]

        # Cancel without reason rejected
        cancel_no_reason = json.dumps({"status": "CANCELLED", "version": 1}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/encounters/{enc_id}/transition", self.headers_hakeem, {}, cancel_no_reason, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 400)

        # Cancel with reason succeeds
        cancel_with_reason = json.dumps({
            "status": "CANCELLED",
            "version": 1,
            "cancellation_reason": "Patient called to reschedule for tomorrow"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/encounters/{enc_id}/transition", self.headers_hakeem, {}, cancel_with_reason, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        enc = json.loads(resp.decode("utf-8"))["encounter"]
        self.assertEqual(enc["status"], "CANCELLED")
        self.assertEqual(enc["cancellation_reason"], "Patient called to reschedule for tomorrow")

    def test_patient_timeline_aggregation_and_role_filtering(self):
        """Timeline aggregates encounters and consents; clinical reasons are filtered for non-clinical roles."""
        # 1. Query as Practitioner (Hakeem)
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients/pat-syn-001/timeline", self.headers_hakeem, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        timeline_hakeem = json.loads(resp.decode("utf-8"))["timeline"]
        self.assertGreaterEqual(len(timeline_hakeem), 1)

        # Practitioner sees reason_for_visit
        enc_event_h = next((e for e in timeline_hakeem if e["event_type"] == "CLINICAL_ENCOUNTER"), None)
        self.assertIsNotNone(enc_event_h)
        self.assertIn("reason_for_visit", enc_event_h["details"])

        # 2. Query as Receptionist (Front Desk)
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients/pat-syn-001/timeline", self.headers_reception, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        timeline_recep = json.loads(resp.decode("utf-8"))["timeline"]
        enc_event_r = next((e for e in timeline_recep if e["event_type"] == "CLINICAL_ENCOUNTER"), None)
        self.assertIsNotNone(enc_event_r)
        # Receptionist does NOT see sensitive clinical note/complaint
        self.assertNotIn("reason_for_visit", enc_event_r["details"])

if __name__ == "__main__":
    unittest.main()

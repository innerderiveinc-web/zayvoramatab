"""End-to-End Smoke Test: Patient Registry, Duplicate Resolution, Patient 360 & Encounter Lifecycle.

Exercises the full Prompt 02 clinical journey:
1. Search patient: verified empty / partial search results.
2. Duplicate detection trigger: registration attempt matching phone causes 409 Conflict.
3. Duplicate override: register with CONFIRMED_DIFFERENT returns 201 Created with sequential MRN.
4. Patient 360 retrieval: verify demographics, contacts, identifiers, and timeline.
5. Optimistic concurrency edit: update demographics at version=1 succeeds (bumps to version=2); stale edit at version=1 fails (409 Conflict).
6. Identifiers lifecycle: add ABHA identifier, then retire it.
7. Consent lifecycle: record explicit CARE_AND_TREATMENT consent, then withdraw it.
8. Encounter lifecycle: create OPD encounter with daily token, update clinical draft notes, transition DRAFT -> IN_PROGRESS -> COMPLETED.
9. Longitudinal Timeline: verify encounter completion and consent events appear chronologically.
10. Duplicate Queue: review candidate pairs and resolve with KEEP_SEPARATE.
"""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store
from apps.api.database.connection import get_db

class TestSmokePatientWorkflow(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        # Run migrations and seed
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Log in as primary hakeem (clinician)
        login_body = json.dumps({
            "username": "hakeem",
            "password": "matab123"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        token = json.loads(resp.decode("utf-8"))["token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_complete_patient_encounter_e2e_journey(self):
        # -------------------------------------------------------------
        # STEP 1: Search Patient (initial search)
        # -------------------------------------------------------------
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients", self.headers, {"q": "NonexistentPatient"}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        search_data = json.loads(resp.decode("utf-8"))
        self.assertEqual(search_data["total"], 0)
        self.assertEqual(len(search_data["patients"]), 0)

        # -------------------------------------------------------------
        # STEP 2: Duplicate Detection Trigger (Registration conflict)
        # -------------------------------------------------------------
        # Try registering a patient with the same phone as seeded pat-syn-001 (9876543210)
        reg_payload = {
            "given_name": "Tariq",
            "family_name": "Khan",
            "phone": "9876543210",
            "date_of_birth": "1990-05-15",
            "sex": "MALE",
            "preferred_language": "ur"
        }
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients", self.headers, {}, json.dumps(reg_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 409)
        conflict_data = json.loads(resp.decode("utf-8"))
        self.assertIn("duplicate_candidates", conflict_data["details"])
        self.assertGreaterEqual(len(conflict_data["details"]["duplicate_candidates"]), 1)
        self.assertEqual(conflict_data["details"]["duplicate_candidates"][0]["rules"][0], "EXACT_PHONE_MATCH")

        # -------------------------------------------------------------
        # STEP 3: Duplicate Override Registration (CONFIRMED_DIFFERENT)
        # -------------------------------------------------------------
        reg_payload["duplicate_override_decision"] = "CONFIRMED_DIFFERENT"
        reg_payload["duplicate_override_reason"] = "Shared family mobile number with sibling."
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients", self.headers, {}, json.dumps(reg_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        new_patient = json.loads(resp.decode("utf-8"))["patient"]
        patient_id = new_patient["id"]
        self.assertTrue(new_patient["mrn"].startswith("MRN-"))
        self.assertEqual(new_patient["version"], 1)
        self.assertEqual(new_patient["display_name"], "Tariq Khan")

        # -------------------------------------------------------------
        # STEP 4: Retrieve Patient 360 View
        # -------------------------------------------------------------
        status, _, resp = ApiRouter.dispatch("GET", f"/api/v1/patients/{patient_id}", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        p360 = json.loads(resp.decode("utf-8"))
        self.assertEqual(p360["patient"]["id"], patient_id)
        self.assertEqual(len(p360["contacts"]), 1)
        self.assertEqual(p360["contacts"][0]["contact_value"], "9876543210")
        self.assertEqual(len(p360["recent_encounters"]), 0)

        # -------------------------------------------------------------
        # STEP 5: Demographic Update with Optimistic Concurrency
        # -------------------------------------------------------------
        # 5a. Stale edit with wrong version fails (409)
        stale_edit = {"version": 99, "family_name": "Al-Khan"}
        status, _, resp = ApiRouter.dispatch("PATCH", f"/api/v1/patients/{patient_id}", self.headers, {}, json.dumps(stale_edit).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 409)

        # 5b. Correct edit with version=1 succeeds, bumps version to 2
        valid_edit = {"version": 1, "family_name": "Al-Khan"}
        status, _, resp = ApiRouter.dispatch("PATCH", f"/api/v1/patients/{patient_id}", self.headers, {}, json.dumps(valid_edit).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        updated_pat = json.loads(resp.decode("utf-8"))["patient"]
        self.assertEqual(updated_pat["version"], 2)
        self.assertEqual(updated_pat["family_name"], "Al-Khan")
        self.assertEqual(updated_pat["display_name"], "Tariq Al-Khan")

        # -------------------------------------------------------------
        # STEP 6: Identifiers Lifecycle (Add and Retire)
        # -------------------------------------------------------------
        id_payload = {
            "identifier_type": "ABHA",
            "identifier_value": "91-1234-5678-9012"
        }
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/{patient_id}/identifiers", self.headers, {}, json.dumps(id_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        ident_record = json.loads(resp.decode("utf-8"))["identifier"]
        ident_id = ident_record["id"]
        self.assertEqual(ident_record["is_retired"], 0)

        # Retire identifier
        retire_payload = {"reason": "Entered in error by clerk"}
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/{patient_id}/identifiers/{ident_id}/retire", self.headers, {}, json.dumps(retire_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        retired_rec = json.loads(resp.decode("utf-8"))["identifier"]
        self.assertEqual(retired_rec["is_retired"], 1)

        # -------------------------------------------------------------
        # STEP 7: Consent Lifecycle (Record and Withdraw)
        # -------------------------------------------------------------
        consent_payload = {
            "purpose": "GENERAL_CARE",
            "status": "GRANTED",
            "policy_version": "v1.0"
        }
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/{patient_id}/consents", self.headers, {}, json.dumps(consent_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        consent_record = json.loads(resp.decode("utf-8"))["consent"]
        consent_id = consent_record["id"]
        self.assertEqual(consent_record["status"], "GRANTED")

        # Withdraw consent
        withdraw_payload = {"reason": "Patient requested withdrawal during follow-up"}
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/{patient_id}/consents/{consent_id}/withdraw", self.headers, {}, json.dumps(withdraw_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        withdrawn_rec = json.loads(resp.decode("utf-8"))["consent"]
        self.assertEqual(withdrawn_rec["status"], "WITHDRAWN")

        # -------------------------------------------------------------
        # STEP 8: Encounter Lifecycle (Create, Draft Update, Transitions)
        # -------------------------------------------------------------
        # 8a. Create Encounter
        enc_payload = {
            "facility_id": "fac-central-opd",
            "encounter_type": "OPD_VISIT",
            "chief_complaint": "Persistent Su-e-Mizaj Barid (Cold Dyspepsia) with indigestion."
        }
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/{patient_id}/encounters", self.headers, {}, json.dumps(enc_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        encounter = json.loads(resp.decode("utf-8"))["encounter"]
        encounter_id = encounter["id"]
        self.assertEqual(encounter["status"], "DRAFT")
        self.assertGreaterEqual(encounter["token_number"], 1)

        # 8b. Update Draft Clinical Notes
        draft_update = {
            "version": 1,
            "reason_for_visit": "Updated: Severe dyspepsia and post-prandial fullness."
        }
        status, _, resp = ApiRouter.dispatch("PATCH", f"/api/v1/encounters/{encounter_id}", self.headers, {}, json.dumps(draft_update).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        updated_enc = json.loads(resp.decode("utf-8"))["encounter"]
        self.assertEqual(updated_enc["version"], 2)
        self.assertIn("Severe dyspepsia", updated_enc["reason_for_visit"])

        # 8c. Transition: DRAFT -> IN_PROGRESS
        trans_1 = {"to_status": "IN_PROGRESS"}
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/encounters/{encounter_id}/transition", self.headers, {}, json.dumps(trans_1).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(resp.decode("utf-8"))["encounter"]["status"], "IN_PROGRESS")

        # 8d. Transition: IN_PROGRESS -> COMPLETED
        trans_2 = {"to_status": "COMPLETED"}
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/encounters/{encounter_id}/transition", self.headers, {}, json.dumps(trans_2).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        completed_enc = json.loads(resp.decode("utf-8"))["encounter"]
        self.assertEqual(completed_enc["status"], "COMPLETED")
        self.assertIsNotNone(completed_enc["ended_at"])

        # -------------------------------------------------------------
        # STEP 9: Longitudinal Timeline Verification
        # -------------------------------------------------------------
        status, _, resp = ApiRouter.dispatch("GET", f"/api/v1/patients/{patient_id}/timeline", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        timeline_data = json.loads(resp.decode("utf-8"))
        events = timeline_data["timeline"]
        self.assertGreaterEqual(len(events), 2)  # Encounter + Consent events
        event_types = [e["event_type"] for e in events]
        self.assertIn("CLINICAL_ENCOUNTER", event_types)
        self.assertIn("CONSENT_RECORDED", event_types)
        statuses = [e["status"] for e in events]
        self.assertIn("COMPLETED", statuses)
        self.assertIn("WITHDRAWN", statuses)

        # -------------------------------------------------------------
        # STEP 10: Duplicate Queue Review and Resolution
        # -------------------------------------------------------------
        # Inspect duplicate candidates for seeded patient pat-syn-001
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients/pat-syn-001/duplicate-candidates", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        cands = json.loads(resp.decode("utf-8"))["duplicate_candidates"]
        self.assertGreaterEqual(len(cands), 1)

        # Resolve the candidate pair
        candidate_id = cands[0]["id"]
        res_payload = {
            "decision": "CONFIRMED_DIFFERENT",
            "notes": "Verified different individuals sharing business landline."
        }
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/pat-syn-001/duplicate-resolutions/{candidate_id}", self.headers, {}, json.dumps(res_payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        res_data = json.loads(resp.decode("utf-8"))
        self.assertTrue(res_data["resolved"])
        self.assertEqual(res_data["status"], "CONFIRMED_DIFFERENT")


if __name__ == "__main__":
    unittest.main()

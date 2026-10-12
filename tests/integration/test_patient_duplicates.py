"""Integration Tests: Deterministic Duplicate Detection, Human Resolution Queue, and Non-Merge Policy."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store
from apps.api.database.connection import get_db

class TestPatientDuplicates(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Login as Receptionist (Farhan Ali)
        login_body = json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token = json.loads(resp.decode("utf-8"))["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_duplicate_candidate_detection_on_phone_match(self):
        """Attempting to register patient with matching phone raises 409 Conflict with candidate details."""
        payload = {
            "given_name": "Irfan",
            "family_name": "Ansari",
            "phone": "+91 98765 43210", # Matches seeded pat-syn-001
            "sex": "MALE"
        }
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients", self.headers, {}, json.dumps(payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 409)
        err = json.loads(resp.decode("utf-8"))
        self.assertEqual(err["code"], "CONFLICT")
        self.assertIn("duplicate_candidates", err["details"])
        candidates = err["details"]["duplicate_candidates"]
        self.assertGreaterEqual(len(candidates), 1)
        candidate_ids = [c["candidate_patient"]["id"] for c in candidates]
        self.assertIn("pat-syn-001", candidate_ids)
        self.assertIn("EXACT_PHONE_MATCH", candidates[0]["rules"])
        self.assertGreaterEqual(candidates[0]["match_score"], 0.90)

    def test_duplicate_candidate_detection_on_name_and_dob(self):
        """Attempting to register with matching Given Name + Date of Birth triggers candidate match."""
        payload = {
            "given_name": "فاطمہ", # Matches seeded pat-syn-003
            "family_name": "Khan",
            "phone": "+91 99999 00000",
            "date_of_birth": "1992-11-20", # Matches seeded pat-syn-003
            "sex": "FEMALE"
        }
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients", self.headers, {}, json.dumps(payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 409)
        err = json.loads(resp.decode("utf-8"))
        candidates = err["details"]["duplicate_candidates"]
        self.assertTrue(any(c["candidate_patient"]["id"] == "pat-syn-003" for c in candidates))

    def test_human_controlled_override_confirmed_different(self):
        """Registering with override_decision='CONFIRMED_DIFFERENT' succeeds and logs candidate pair without merging."""
        payload = {
            "given_name": "Irfan",
            "family_name": "Ansari",
            "phone": "+91 98765 43210", # Matches seeded pat-syn-001
            "sex": "MALE",
            "override_decision": "CONFIRMED_DIFFERENT",
            "override_notes": "Operator verified distinct clinical identity (father & son sharing mobile)"
        }
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients", self.headers, {}, json.dumps(payload).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        new_patient = json.loads(resp.decode("utf-8"))["patient"]
        
        # Verify two distinct patient records exist (NO automatic merge)
        with get_db(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM patients WHERE id IN ('pat-syn-001', ?);", (new_patient["id"],))
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 2)

            # Verify candidate pair recorded in resolution queue
            cursor.execute("""
                SELECT status, review_notes FROM patient_duplicate_candidates
                WHERE (patient_id_a = ? AND patient_id_b = 'pat-syn-001')
                   OR (patient_id_a = 'pat-syn-001' AND patient_id_b = ?);
            """, (new_patient["id"], new_patient["id"]))
            cand = cursor.fetchone()
            self.assertIsNotNone(cand)
            self.assertEqual(cand["status"], "CONFIRMED_DIFFERENT")

    def test_resolve_duplicate_endpoint(self):
        """Human operator records resolution on pre-existing duplicate pair."""
        res_body = json.dumps({
            "decision": "CONFIRMED_DIFFERENT",
            "notes": "Verified different identity documents"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", "/api/v1/patients/pat-syn-001/duplicate-resolutions/dup-pair-001",
            self.headers, {}, res_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(resp.decode("utf-8"))
        self.assertTrue(data["resolved"])
        self.assertEqual(data["status"], "CONFIRMED_DIFFERENT")

    def test_automatic_merge_is_strictly_forbidden(self):
        """Attempting automatic merge decision is rejected."""
        merge_body = json.dumps({
            "decision": "MERGED_FUTURE",
            "notes": "Attempting auto-merge"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", "/api/v1/patients/pat-syn-001/duplicate-resolutions/dup-pair-001",
            self.headers, {}, merge_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 400)
        err = json.loads(resp.decode("utf-8"))
        self.assertIn("Automatic data merge is not supported", err["message"])

if __name__ == "__main__":
    unittest.main()

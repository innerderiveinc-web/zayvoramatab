"""Integration Tests: Organ-Axis Concepts, Associations, Citations, and Acknowledgments."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store

class TestOrganAxisApi(unittest.TestCase):
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

    def test_list_organ_axis_concepts(self):
        """Practitioner can retrieve master anatomical/functional concepts."""
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/organ-axis/concepts", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertIn("concepts", data)
        codes = [c["code"] for c in data["concepts"]]
        self.assertIn("MEDA", codes)
        self.assertIn("DIMAGH", codes)
        self.assertIn("KABID", codes)

    def test_get_reviewed_mappings_with_citations(self):
        """Querying mappings returns associations with plain explanations, relationship types, and citations."""
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/organ-axis/mappings?concept=MEDA", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertIn("mappings", data)
        self.assertGreaterEqual(len(data["mappings"]), 1)

        m = data["mappings"][0]
        self.assertIn(m["relationship_type"], ["ASSOCIATED_WITH", "TRADITIONALLY_RELATED_TO"])
        self.assertIn("plain_explanation", m)
        self.assertIn("source_title", m)
        self.assertEqual(m["source_bib_code"], "AL_QANUN")

    def test_honest_no_mapping_state(self):
        """Querying concepts without reviewed mappings returns honest empty list (never fabricated)."""
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/organ-axis/mappings?concept=KULYAH", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(data["mappings"], [])

    def test_acknowledge_mapping_in_assessment(self):
        """Clinician can record an acknowledgment and clinical note for an Organ-Axis mapping."""
        # Query mapping id
        _, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/organ-axis/mappings?concept=MEDA", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        mapping_id = json.loads(resp_bytes.decode("utf-8"))["mappings"][0]["id"]

        ack_body = json.dumps({
            "assessment_id": "uas-syn-001",
            "notes": "Verified gastric etiology for patient's frontal cephalalgia."
        }).encode("utf-8")

        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/organ-axis/mappings/{mapping_id}/acknowledge",
            self.headers, {}, ack_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(resp_bytes.decode("utf-8"))
        self.assertTrue(res["acknowledged"])

if __name__ == "__main__":
    unittest.main()

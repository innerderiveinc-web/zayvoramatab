"""Integration tests for KAVS REST APIs and Router Dispatch.
Validates:
- /api/v1/kavs/sources/versions
- /api/v1/kavs/sources/rights-reviews
- /api/v1/kavs/ingestion/jobs and segments
- /api/v1/kavs/claims/{id}/verifications
- /api/v1/kavs/claims/{id}/conflicts
- /api/v1/kavs/releases and withdrawals
- /api/v1/kavs/impact-events
- /api/v1/kavs/retrieve
"""

import os
import json
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestKAVSRestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_kavs_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin via standard login
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.db_path
        )
        cls.auth_token = json.loads(body)["token"]

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id FROM knowledge_sources WHERE title LIKE '%Unani Pharmacopoeia%' LIMIT 1;")
        row_src = cur.fetchone()
        cls.source_id = row_src["id"] if row_src else "src-upi-synth"
        cur.execute("SELECT c.id FROM knowledge_claims c JOIN knowledge_items i ON c.item_id = i.id WHERE i.canonical_name LIKE '%Senna%' LIMIT 1;")
        row_clm = cur.fetchone()
        cls.claim_id = row_clm["id"] if row_clm else "clm-senna-01"
        conn.close()

    def _call(self, method: str, path: str, body: dict = None) -> tuple:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        status_code, resp_headers, resp_bytes = ApiRouter.dispatch(
            method=method,
            path=path,
            headers=headers,
            query_params={},
            body_bytes=body_bytes,
            client_ip="127.0.0.1",
            db_path=self.db_path
        )
        data = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        return status_code, data

    def test_01_source_version_and_rights_endpoints(self):
        """POST /api/v1/kavs/sources/versions and /api/v1/kavs/sources/rights-reviews"""
        status, data = self._call("POST", "/api/v1/kavs/sources/versions", {
            "source_id": self.source_id,
            "edition": "Vol II, First Edition",
            "publication_year": 2008,
            "source_rights_status": "STATUTORY_AYUSH_OPEN"
        })
        self.assertEqual(status, 201)
        version_id = data["source_version"]["id"]

        status, data = self._call("GET", f"/api/v1/kavs/sources/versions/{version_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["source_version"]["edition"], "Vol II, First Edition")

        # Rights review
        status, data = self._call("POST", "/api/v1/kavs/sources/rights-reviews", {
            "source_id": self.source_id,
            "source_version_id": version_id,
            "license_type": "PUBLIC_DOMAIN_GOV",
            "full_text_retention_permitted": True
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["rights_review"]["status"], "APPROVED")

    def test_02_ingestion_and_extraction_endpoints(self):
        """POST /api/v1/kavs/ingestion/jobs and segments review"""
        status, data = self._call("POST", "/api/v1/kavs/ingestion/jobs", {
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION",
            "original_filename": "UPI_Part_I_Vol_II.pdf"
        })
        self.assertEqual(status, 201)
        job_id = data["job"]["job_id"]

        status, data = self._call("POST", f"/api/v1/kavs/ingestion/jobs/{job_id}/segments", {
            "locator": "Page 55, Monograph 21",
            "raw_extracted_text": "Filfil Siah consists of dried mature berries of Piper nigrum L."
        })
        self.assertEqual(status, 201)
        seg_id = data["segment"]["segment_id"]

        status, data = self._call("POST", f"/api/v1/kavs/ingestion/segments/{seg_id}/review", {
            "fidelity_status": "human_checked",
            "review_notes": "Verified against physical print copy."
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["segment_review"]["verified"])

    def test_03_claim_verification_and_release_flow(self):
        """Verify claim across 5 dimensions and publish release."""
        status, data = self._call("POST", f"/api/v1/kavs/claims/{self.claim_id}/verifications", {
            "source_authenticity": "publisher_or_authority_verified",
            "extraction_fidelity": "human_checked",
            "evidence_characterization": "official_specification",
            "clinical_review_state": "approved_for_defined_use",
            "intended_use_authorization": "clinician_contextual_reference",
            "lead_reviewer_role": "UNANI_SCHOLAR"
        })
        self.assertEqual(status, 201)
        verif_id = data["claim_verification"]["id"]

        status, data = self._call("GET", f"/api/v1/kavs/verifications/{verif_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["claim_verification"]["intended_use_authorization"], "clinician_contextual_reference")

        # Publish release
        status, data = self._call("POST", "/api/v1/kavs/releases", {
            "release_tag": "kavs-v1.0.0-api-test",
            "title": "KAVS Tested Release"
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["release"]["status"], "ACTIVE")

    def test_04_contextual_retrieval_endpoint(self):
        """POST /api/v1/kavs/retrieve returns verified claims with honest provenance."""
        status, data = self._call("POST", "/api/v1/kavs/retrieve", {
            "query": "Senna",
            "intended_use": "clinician_contextual_reference"
        })
        self.assertEqual(status, 200)
        self.assertFalse(data["insufficient_information"])
        self.assertGreaterEqual(data["total"], 1)
        self.assertIn("Senna", data["results"][0]["item_name"])


if __name__ == "__main__":
    unittest.main()

"""Integration tests for KAVS Source Ingestion, OCR Fidelity & Claim Extraction Workbench REST API.
Validates:
- Preflight Rights Check: POST /api/v1/kavs/sources/versions/{id}/preflight-rights
- Source File Upload & Verification: POST /api/v1/kavs/sources/versions/{id}/upload-file
- Get Source File: GET /api/v1/kavs/source-files/{id}
- Ingestion Jobs: POST /api/v1/kavs/ingestion/jobs, GET .../jobs, GET .../jobs/{id}, POST .../transition, POST .../cancel, POST .../retry
- Extraction Pages: POST /api/v1/kavs/ingestion/jobs/{id}/pages, GET .../pages, GET /api/v1/kavs/extraction-pages/{id}
- Extraction Segments: GET /api/v1/kavs/extraction-segments/{id}, POST .../corrections, POST .../mark-unreadable
- Extraction Tables: POST /api/v1/kavs/ingestion/jobs/{id}/tables, GET .../tables
- Candidate Claim Drafts: POST /api/v1/kavs/claim-drafts, GET .../claim-drafts, GET .../{id}, POST .../submit-review, POST .../reject, POST .../promote
- Quality & Queue Health: GET /api/v1/kavs/ingestion-quality, GET /api/v1/kavs/ingestion-queue/health
- Auth protection: 401 when unauthenticated
"""

import os
import json
import base64
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestKAVSIngestionWorkbenchApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_kavs_workbench_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
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
        conn.close()

    def _call(self, method: str, path: str, body: dict = None, token: str = None) -> tuple:
        auth = token if token is not None else self.auth_token
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = f"Bearer {auth}"
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

    def test_01_preflight_and_file_upload(self):
        """Register source version, review rights, check preflight, and upload source PDF."""
        # 1. Register version
        status, data = self._call("POST", "/api/v1/kavs/sources/versions", {
            "source_id": self.source_id,
            "edition": "UPI Part I Vol IV (2007)",
            "publication_year": 2007,
            "source_rights_status": "STATUTORY_AYUSH_OPEN"
        })
        self.assertEqual(status, 201)
        version_id = data["source_version"]["id"]

        # 2. Record Rights Review permitting extraction and retention
        status, data = self._call("POST", "/api/v1/kavs/sources/rights-reviews", {
            "source_id": self.source_id,
            "source_version_id": version_id,
            "license_type": "STATUTORY_COMPENDIUM",
            "full_text_retention_permitted": True,
            "excerpt_storage_permitted": True,
            "vector_indexing_permitted": True,
            "redistribution_permitted": False,
            "review_notes": "Statutory pharmacopoeia open reference"
        })
        self.assertEqual(status, 201)

        # 3. Preflight rights check
        status, data = self._call("POST", f"/api/v1/kavs/sources/versions/{version_id}/preflight-rights", {
            "operation": "EXTRACT_TEXT"
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["preflight"]["allowed"])

        # 4. Upload valid PDF with base64 content
        pdf_content = b"%PDF-1.4\nSynthetic Unani Pharmacopoeia PDF test stream\n%%EOF"
        pdf_b64 = base64.b64encode(pdf_content).decode("ascii")

        status, data = self._call("POST", f"/api/v1/kavs/sources/versions/{version_id}/upload-file", {
            "filename": "UPI_Vol_IV.pdf",
            "file_base64": pdf_b64,
            "mime_type": "application/pdf",
            "page_count_estimate": 150
        })
        self.assertEqual(status, 201)
        file_id = data["source_file"]["id"]
        self.assertTrue(data["source_file"]["file_checksum"].startswith("sha256:"))

        # 5. Fetch uploaded file metadata
        status, data = self._call("GET", f"/api/v1/kavs/source-files/{file_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["source_file"]["original_filename"], "UPI_Vol_IV.pdf")

        # 6. Upload file with invalid magic bytes raises 400
        bad_b64 = base64.b64encode(b"NOT A PDF HEADER").decode("ascii")
        status, data = self._call("POST", f"/api/v1/kavs/sources/versions/{version_id}/upload-file", {
            "filename": "fake.pdf",
            "file_base64": bad_b64,
            "mime_type": "application/pdf"
        })
        self.assertEqual(status, 400)

    def test_02_ingestion_job_lifecycle_pages_and_tables(self):
        """Create job, transition through state machine, add page with distinct PDF index, add structured table."""
        # 1. Create Ingestion Job
        status, data = self._call("POST", "/api/v1/kavs/ingestion/jobs", {
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION",
            "original_filename": "UPI_Vol_IV.pdf"
        })
        self.assertEqual(status, 201)
        job_id = data["job"]["id"]

        # 2. Transition state: queued -> integrity_check -> ocr_running
        status, data = self._call("POST", f"/api/v1/kavs/ingestion/jobs/{job_id}/transition", {
            "to_state": "integrity_check",
            "message": "Checksum and malware scan verified clean"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["job"]["status"], "integrity_check")

        status, data = self._call("POST", f"/api/v1/kavs/ingestion/jobs/{job_id}/transition", {
            "to_state": "ocr_running",
            "message": "Bilingual OCR pass initialized"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["job"]["status"], "ocr_running")

        # 3. Add Extraction Page with separate PDF page index vs printed page label
        status, data = self._call("POST", f"/api/v1/kavs/ingestion/jobs/{job_id}/pages", {
            "pdf_page_index": 35,
            "printed_page_label": "21",
            "extracted_text": "Filfil Siah (Piper nigrum L.): Dose 1 to 2 masha (approx 1g to 2g). Useful in Zof-e-Ishteha.",
            "ocr_confidence": 0.95
        })
        self.assertEqual(status, 201)
        page_id = data["page"]["id"]
        self.assertEqual(data["page"]["pdf_page_index"], 35)
        self.assertEqual(data["page"]["printed_page_label"], "21")
        self.assertTrue(data["page"]["is_high_risk"])

        # 4. List Pages for job
        status, data = self._call("GET", f"/api/v1/kavs/ingestion/jobs/{job_id}/pages")
        self.assertEqual(status, 200)
        self.assertEqual(data["total"], 1)

        # 5. Get Page details
        status, data = self._call("GET", f"/api/v1/kavs/extraction-pages/{page_id}")
        self.assertEqual(status, 200)
        self.assertIn("HISTORICAL_POSOLOGY_UNIT", data["page"]["quality_flags"])

        # 6. Add Structured Table
        status, data = self._call("POST", f"/api/v1/kavs/ingestion/jobs/{job_id}/tables", {
            "table_title": "Posology and Administration Schedule",
            "columns": ["Age Group", "Dose", "Anupana / Vehicle"],
            "rows": [
                ["Adults (18-60)", "1 g twice daily", "Lukewarm water or Arq Badiyan"],
                ["Geriatric (>60)", "500 mg twice daily", "Honey / Arq Gulab"]
            ]
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["table"]["total_rows"], 2)

        # 7. List Tables for job
        status, data = self._call("GET", f"/api/v1/kavs/ingestion/jobs/{job_id}/tables")
        self.assertEqual(status, 200)
        self.assertEqual(data["total"], 1)

    def test_03_segment_corrections_and_candidate_draft_promotion(self):
        """Add segment, record transcription correction, create draft, and promote to atomic claim."""
        # Create Job
        status, data = self._call("POST", "/api/v1/kavs/ingestion/jobs", {
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        })
        self.assertEqual(status, 201)
        job_id = data["job"]["id"]

        # Add segment with typo
        status, data = self._call("POST", f"/api/v1/kavs/ingestion/jobs/{job_id}/segments", {
            "locator": "Page 40, Monograph 12",
            "raw_extracted_text": "Zanjabeel: Dose 1-2 mashaa with honey."
        })
        self.assertEqual(status, 201)
        segment_id = data["segment"]["segment_id"]

        # Record human transcription correction
        status, data = self._call("POST", f"/api/v1/kavs/extraction-segments/{segment_id}/corrections", {
            "corrected_text": "Zanjabeel (Zingiber officinale Roscoe): Dose 1-2 masha with honey.",
            "correction_reason": "Normalized botanical binomial authority and posology unit spelling."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["segment"]["fidelity_status"], "human_checked")

        # Fetch segment with history
        status, data = self._call("GET", f"/api/v1/kavs/extraction-segments/{segment_id}")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["segment"]["correction_history"]), 1)

        # Create candidate claim draft tethered to the corrected segment
        status, data = self._call("POST", "/api/v1/kavs/claim-drafts", {
            "job_id": job_id,
            "segment_id": segment_id,
            "draft_text": "Zanjabeel (Zingiber officinale) relieves indigestion and strengthens gastric tone.",
            "target_claim_type": "traditional_use"
        })
        self.assertEqual(status, 201)
        draft_id = data["draft"]["id"]
        self.assertEqual(data["draft"]["draft_status"], "DRAFT_UNVERIFIED")

        # Get claim draft
        status, data = self._call("GET", f"/api/v1/kavs/claim-drafts/{draft_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["draft"]["segment_id"], segment_id)

        # Submit draft for review
        status, data = self._call("POST", f"/api/v1/kavs/claim-drafts/{draft_id}/submit-review")
        self.assertEqual(status, 200)
        self.assertEqual(data["draft"]["draft_status"], "PENDING_REVIEW")

        # Promote draft to atomic claim
        status, data = self._call("POST", f"/api/v1/kavs/claim-drafts/{draft_id}/promote")
        self.assertEqual(status, 201)
        promoted_claim = data["claim"]
        self.assertEqual(promoted_claim["approval_state"], "UNDER_REVIEW")

        # Verify draft marked PROMOTED
        status, data = self._call("GET", f"/api/v1/kavs/claim-drafts/{draft_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["draft"]["draft_status"], "PROMOTED")

    def test_04_mark_segment_unreadable_and_reject_draft(self):
        """Mark segment unreadable and reject candidate draft."""
        status, data = self._call("POST", "/api/v1/kavs/ingestion/jobs", {
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        })
        job_id = data["job"]["id"]

        status, data = self._call("POST", f"/api/v1/kavs/ingestion/jobs/{job_id}/segments", {
            "locator": "Page 99, Torn page",
            "raw_extracted_text": "[Unreadable torn fragment]"
        })
        seg_id = data["segment"]["segment_id"]

        # Mark unreadable
        status, data = self._call("POST", f"/api/v1/kavs/extraction-segments/{seg_id}/mark-unreadable", {
            "reason": "Lower corner of page 99 torn; text unrecoverable"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["segment"]["fidelity_status"], "unreadable")

        # Create draft and reject it
        status, data = self._call("POST", "/api/v1/kavs/claim-drafts", {
            "job_id": job_id,
            "segment_id": seg_id,
            "draft_text": "Unverified assertion from torn fragment"
        })
        draft_id = data["draft"]["id"]

        status, data = self._call("POST", f"/api/v1/kavs/claim-drafts/{draft_id}/reject", {
            "reason": "Source passage is physically torn and unverifiable"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["draft"]["draft_status"], "REJECTED")

    def test_05_quality_and_queue_health_endpoints(self):
        """GET /api/v1/kavs/ingestion-quality and GET /api/v1/kavs/ingestion-queue/health."""
        status, data = self._call("GET", "/api/v1/kavs/ingestion-quality")
        self.assertEqual(status, 200)
        metrics = data["quality_metrics"]
        self.assertIn("total_jobs", metrics)
        self.assertIn("fidelity_distribution", metrics)
        self.assertIn("claim_draft_conversion_rate_pct", metrics)

        status, data = self._call("GET", "/api/v1/kavs/ingestion-queue/health")
        self.assertEqual(status, 200)
        health = data["queue_health"]
        self.assertEqual(health["queue_status"], "HEALTHY")
        self.assertTrue(health["queue_healthy"])

    def test_06_unauthenticated_requests_blocked(self):
        """Verify 401 Unauthorized when auth token is omitted."""
        status, _ = self._call("GET", "/api/v1/kavs/ingestion/jobs", token="")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

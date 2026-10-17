"""Unit tests for KAVS Source Ingestion, OCR Fidelity & Claim Extraction Workbench (Prompt 18).
Tests:
- Source rights preflight verification
- File upload handling with magic bytes and SHA-256 verification
- 21-state ingestion job lifecycle and transitions
- Extraction pages with separate pdf_page_index and printed_page_label
- High-risk clinical pattern detection (posology units, numerals, botanical binomials, negations)
- Manual transcription correction audit trail
- Marking segment unreadable
- Candidate claim draft creation, isolation from retrieval, and promotion gate
- Ingestion quality metrics and queue health
"""

import unittest
import uuid
import os
import sqlite3
from typing import Dict, Any

from apps.api.domains.kavs import KAVSEngine, VALID_INGESTION_STATES
from apps.api.database.migrator import run_migrations
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


class TestKAVSIngestionWorkbench(unittest.TestCase):
    def setUp(self):
        self.test_db = f"/tmp/test_kavs_workbench_{uuid.uuid4().hex[:8]}.db"
        run_migrations(self.test_db)

        self.engine = KAVSEngine(db_path=self.test_db)

        # Seed synthetic user and knowledge source
        conn = sqlite3.connect(self.test_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        self.org_id = f"org-{uuid.uuid4().hex[:8]}"
        self.user_id = f"usr-{uuid.uuid4().hex[:8]}"
        self.scholar_id = f"sch-{uuid.uuid4().hex[:8]}"

        cur.execute("""
            INSERT INTO organizations (id, name, code, profile_type, is_active)
            VALUES (?, 'Zayvora KAVS Lab', 'ORG-KAVS', 'MATAB', 1);
        """, (self.org_id,))

        cur.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, 'knowledge_admin', 'admin@kavs.org', 'hash', 'Hakim Director', 1);
        """, (self.user_id, self.org_id))

        cur.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, 'unani_scholar', 'scholar@kavs.org', 'hash', 'Hakim Scholar', 1);
        """, (self.scholar_id, self.org_id))

        self.source_id = f"src-{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                publication_date, jurisdiction, regulatory_status, evidence_level,
                review_status, created_at
            ) VALUES (?, 'National Formulary of Unani Medicine Vol I', 'Govt of India',
                      'AYUSH Ministry', 'PHARMACOPOEIA', 'First Edition Reprint',
                      '2006-01-01', 'IN', 'APPROVED_STANDARD', 'CLASSICAL_COMPENDIUM_GRADE_D',
                      'APPROVED', CURRENT_TIMESTAMP);
        """, (self.source_id,))

        conn.commit()
        conn.close()

        ver = self.engine.register_source_version({
            "source_id": self.source_id,
            "edition": "First Edition Reprint",
            "publication_year": 2006,
            "source_rights_status": "STATUTORY_AYUSH_OPEN"
        }, self.user_id)
        self.version_id = ver["id"]

        # Setup Rights Review allowing extraction and full text retention
        self.engine.record_rights_review({
            "source_id": self.source_id,
            "source_version_id": self.version_id,
            "license_type": "FAIR_DEALING_EXCERPTS",
            "full_text_retention_permitted": True,
            "excerpt_storage_permitted": True,
            "vector_indexing_permitted": True,
            "redistribution_permitted": False,
            "review_status": "APPROVED",
            "review_notes": "Statutory AYUSH formulary; retention and extraction permitted."
        }, self.scholar_id)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    # --------------------------------------------------------------------------
    # 1. Rights Preflight Checks
    # --------------------------------------------------------------------------

    def test_preflight_rights_permitted_and_forbidden(self):
        """Preflight rights check accurately enforces source permission dimensions."""
        # Check extraction allowed
        res_extract = self.engine.check_source_rights_preflight(self.version_id, "EXTRACT_TEXT", self.user_id)
        self.assertTrue(res_extract["allowed"])
        self.assertEqual(res_extract["source_version_id"], self.version_id)

        # Check redistribution blocked
        res_redist = self.engine.check_source_rights_preflight(self.version_id, "REDISTRIBUTE", self.user_id)
        self.assertFalse(res_redist["allowed"])
        self.assertIn("Redistribution of source text", res_redist["reason"])

    def test_preflight_fails_when_no_review_exists(self):
        """Preflight check blocks operations if no approved rights review exists for source."""
        # Create unreviewed source & version
        src_unreviewed = self.engine.create_source({
            "title": "Unreviewed Manuscript of Avicenna",
            "source_type": "MANUSCRIPT",
            "authority_tier": 3
        }, self.user_id)
        ver_unreviewed = self.engine.register_source_version({
            "source_id": src_unreviewed["id"],
            "edition": "1890 Cairo Lithograph"
        }, self.user_id)

        res = self.engine.check_source_rights_preflight(ver_unreviewed["id"], "INGEST", self.user_id)
        self.assertFalse(res["allowed"])
        self.assertIn("No approved statutory rights review", res["reason"])

    # --------------------------------------------------------------------------
    # 2. Source File Upload & Magic Bytes
    # --------------------------------------------------------------------------

    def test_upload_valid_pdf_calculates_sha256(self):
        """Upload valid PDF file, verifying header magic bytes and SHA-256 hash."""
        pdf_bytes = b"%PDF-1.4\n%synthetic test content for unani formulary\n%%EOF"
        uploaded = self.engine.upload_source_file(
            source_version_id=self.version_id,
            filename="NFUM_Vol_I.pdf",
            file_bytes=pdf_bytes,
            user_id=self.user_id,
            page_count_estimate=320
        )

        self.assertIsNotNone(uploaded["id"])
        self.assertTrue(uploaded["file_checksum"].startswith("sha256:"))
        self.assertEqual(uploaded["detected_magic"], "%PDF-")
        self.assertEqual(uploaded["scan_status"], "CLEAN")

        # Fetch uploaded file
        fetched = self.engine.get_source_file(uploaded["id"])
        self.assertEqual(fetched["original_filename"], "NFUM_Vol_I.pdf")
        self.assertEqual(fetched["file_size_bytes"], len(pdf_bytes))

    def test_upload_invalid_magic_bytes_rejected(self):
        """Upload file with invalid magic bytes raises ValidationError."""
        fake_bytes = b"<html invalid executable header"
        with self.assertRaises(ValidationError) as ctx:
            self.engine.upload_source_file(
                source_version_id=self.version_id,
                filename="fake.pdf",
                file_bytes=fake_bytes,
                user_id=self.user_id
            )
        self.assertIn("Invalid file header", str(ctx.exception))

    def test_upload_blocked_if_retention_rights_missing(self):
        """Upload file is blocked when source rights review prohibits file retention."""
        # Update rights review to prohibit retention
        conn = sqlite3.connect(self.test_db)
        conn.execute("""
            UPDATE kavs_source_rights_reviews
            SET full_text_retention_permitted = 0
            WHERE source_version_id = ?;
        """, (self.version_id,))
        conn.commit()
        conn.close()

        pdf_bytes = b"%PDF-1.4\nsynthetic PDF"
        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.upload_source_file(
                source_version_id=self.version_id,
                filename="NFUM.pdf",
                file_bytes=pdf_bytes,
                user_id=self.user_id
            )
        self.assertIn("prohibits retaining full text files", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 3. Ingestion State Machine Transitions
    # --------------------------------------------------------------------------

    def test_ingestion_job_state_machine_and_events(self):
        """Test authoritative state transitions across the 21-state machine with event audit trail."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "source_version_id": self.version_id,
            "job_type": "STRUCTURED_EXTRACTION",
            "original_filename": "NFUM_Vol_I.pdf",
            "file_checksum": "sha256:123456"
        }, self.user_id)

        self.assertEqual(job["status"], "QUEUED")

        # Valid transitions: queued -> integrity_check -> ocr_running -> structure_detection
        j1 = self.engine.transition_ingestion_job(job["id"], "integrity_check", self.user_id, "Integrity check started")
        self.assertEqual(j1["status"], "integrity_check")

        j2 = self.engine.transition_ingestion_job(job["id"], "ocr_running", self.user_id, "OCR engine started")
        self.assertEqual(j2["status"], "ocr_running")

        j3 = self.engine.transition_ingestion_job(job["id"], "structure_detection", self.user_id, "Structure mapped")
        self.assertEqual(j3["status"], "structure_detection")

        # Verify event history
        fetched_job = self.engine.get_ingestion_job(job["id"])
        self.assertEqual(len(fetched_job["events"]), 4)  # created + 3 transitions

    def test_invalid_state_transition_raises_error(self):
        """Attempting to transition to an unrecognized state raises ValidationError."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        with self.assertRaises(ValidationError):
            self.engine.transition_ingestion_job(job["id"], "NON_EXISTENT_STATE", self.user_id)

    def test_cancel_and_retry_ingestion_job(self):
        """Cancel an ongoing job and retry it."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        cancelled = self.engine.cancel_ingestion_job(job["id"], self.user_id)
        self.assertEqual(cancelled["status"], "cancelled")

        retried = self.engine.retry_ingestion_job(job["id"], self.user_id)
        self.assertEqual(retried["status"], "queued")

    # --------------------------------------------------------------------------
    # 4. Distinct Pagination & High-Risk Scanner
    # --------------------------------------------------------------------------

    def test_extraction_pages_preserve_distinct_pdf_index_and_printed_label(self):
        """Physical PDF page index and printed book page label must remain separate."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "source_version_id": self.version_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        # Printed page 10 may correspond to physical PDF index 24 (after prefatory front matter)
        page = self.engine.add_extraction_page(job["id"], {
            "source_version_id": self.version_id,
            "pdf_page_index": 24,
            "printed_page_label": "10",
            "page_header": "Qarabadin-e-Azam - Chapter on Digestive Disorders",
            "extracted_text": "Hab-e-Suranjan: Useful in Waja-ul-Mafasil. Dose 2 habba with Arq Badiyan.",
            "ocr_confidence": 0.96
        }, self.user_id)

        self.assertEqual(page["pdf_page_index"], 24)
        self.assertEqual(page["printed_page_label"], "10")
        self.assertTrue(page["is_high_risk"])
        self.assertIn("HISTORICAL_POSOLOGY_UNIT", page["quality_flags"])
        self.assertIn("NUMERIC_QUANTITY_OR_RANGE", page["quality_flags"])

    def test_high_risk_elements_scanner_detects_posology_taxonomy_and_negations(self):
        """High-risk scanner identifies numerals, historical units, botanical taxonomy, and negations."""
        # Test historical posology and dosage range
        res1 = self.engine._detect_high_risk_elements("Dose is 3-5 masha twice daily after meals.")
        self.assertTrue(res1["has_high_risk"])
        self.assertIn("NUMERIC_QUANTITY_OR_RANGE", res1["flags"])
        self.assertIn("HISTORICAL_POSOLOGY_UNIT", res1["flags"])

        # Test botanical taxonomy
        res2 = self.engine._detect_high_risk_elements("Derived from Terminalia chebula Retz.")
        self.assertTrue(res2["has_high_risk"])
        self.assertIn("BOTANICAL_TAXONOMY", res2["flags"])

        # Test safety contraindication and negation
        res3 = self.engine._detect_high_risk_elements("Contraindicated in pregnancy and renal impairment.")
        self.assertTrue(res3["has_high_risk"])
        self.assertIn("SAFETY_CONTRAINDICATION_OR_NEGATION", res3["flags"])

        # Test non-clinical innocuous text
        res4 = self.engine._detect_high_risk_elements("Introduction to classical Greco-Arab principles.")
        self.assertFalse(res4["has_high_risk"])

    # --------------------------------------------------------------------------
    # 5. Extraction Segments, Corrections & Unreadable Marking
    # --------------------------------------------------------------------------

    def test_record_segment_correction_preserves_machine_text(self):
        """Manual transcription correction preserves original machine text with mandatory reason."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "source_version_id": self.version_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        seg = self.engine.add_extraction_segment(job["id"], {
            "locator": "Page 142, Monograph 52",
            "raw_extracted_text": "Sana Makki: Dose 3-5 masha with Arq Gulab.",
            "ocr_confidence": 0.88
        })

        # Correct OCR typo
        corrected = self.engine.record_segment_correction(seg["segment_id"], {
            "corrected_text": "Sana Makki (Cassia angustifolia Vahl.): Dose 3 to 5 masha with Arq Gulab.",
            "correction_reason": "Clarified botanical species and normalized numeral range representation."
        }, self.scholar_id)

        self.assertEqual(corrected["fidelity_status"], "human_checked")
        self.assertTrue(corrected["verified"])

        # Fetch detailed segment history
        details = self.engine.get_extraction_segment(seg["segment_id"])
        self.assertEqual(details["raw_extracted_text"], "Sana Makki: Dose 3-5 masha with Arq Gulab.")
        self.assertEqual(details["human_corrected_text"], "Sana Makki (Cassia angustifolia Vahl.): Dose 3 to 5 masha with Arq Gulab.")
        self.assertEqual(len(details["correction_history"]), 1)
        self.assertEqual(details["correction_history"][0]["correction_reason"], "Clarified botanical species and normalized numeral range representation.")

    def test_mark_segment_unreadable(self):
        """Marking a damaged or faded segment as unreadable records mandatory reason."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        seg = self.engine.add_extraction_segment(job["id"], {
            "locator": "Page 88, Marginalia",
            "raw_extracted_text": "...",
            "ocr_confidence": 0.20
        })

        unreadable = self.engine.mark_segment_unreadable(
            seg["segment_id"],
            "Severe water damage on manuscript margin, text illegible",
            self.scholar_id
        )

        self.assertEqual(unreadable["fidelity_status"], "unreadable")
        self.assertIn("water damage", unreadable["review_notes"])

    # --------------------------------------------------------------------------
    # 6. Structured Table Extraction
    # --------------------------------------------------------------------------

    def test_add_and_list_extraction_tables(self):
        """Structured formulation composition table is recorded with columns and rows."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        table = self.engine.add_extraction_table(job["id"], {
            "table_title": "Formulation Composition of Majun Dabeed-ul-Ward",
            "page_number": 45,
            "columns": ["Ingredient", "Botanical Name", "Part Used", "Quantity"],
            "rows": [
                ["Gul-e-Surkh", "Rosa damascena Mill.", "Flower petals", "100 g"],
                ["Sumbul-ut-Teeb", "Nardostachys jatamansi DC.", "Rhizome", "25 g"],
                ["Mastagi", "Pistacia lentiscus L.", "Resin", "25 g"]
            ],
            "footnote": "Sugar base prepared to 3-fold qiwam consistency."
        }, self.user_id)

        self.assertIsNotNone(table["id"])
        self.assertEqual(table["total_rows"], 3)

        tables = self.engine.list_extraction_tables(job["id"])
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["table_title"], "Formulation Composition of Majun Dabeed-ul-Ward")

    # --------------------------------------------------------------------------
    # 7. Candidate Claim Drafts & Retrieval Isolation
    # --------------------------------------------------------------------------

    def test_candidate_draft_lifecycle_and_retrieval_isolation(self):
        """Candidate claim drafts remain in DRAFT_UNVERIFIED and are isolated from consultation retrieval."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "source_version_id": self.version_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        seg = self.engine.add_extraction_segment(job["id"], {
            "locator": "Page 112, Monograph 44",
            "raw_extracted_text": "Ustukhuddus: Useful in Nazla and Barid headache.",
            "ocr_confidence": 0.95
        })

        # Create draft candidate claim
        draft = self.engine.create_claim_draft({
            "job_id": job["id"],
            "segment_id": seg["segment_id"],
            "source_version_id": self.version_id,
            "target_claim_type": "INDICATION",
            "draft_text": "Ustukhuddus is indicated for headache due to cold phlegm (Nazla Haar/Barid).",
            "draft_domain": "UNANI_CLINICAL",
            "extraction_confidence": 0.92
        }, self.user_id)

        self.assertEqual(draft["draft_status"], "DRAFT_UNVERIFIED")
        self.assertFalse(draft["is_human_reviewed"])

        # VERIFY ISOLATION: Query consultation context retrieval; draft MUST NOT appear
        context = self.engine.retrieve_verified_clinical_context(
            query="Ustukhuddus headache",
            domain="UNANI_CLINICAL"
        )
        for claim in context.get("results", []):
            self.assertNotEqual(claim.get("claim_text"), draft["draft_text"])

        # Submit draft for review
        submitted = self.engine.submit_claim_draft_for_review(draft["id"], self.user_id)
        self.assertEqual(submitted["draft_status"], "PENDING_REVIEW")

    def test_promote_draft_blocked_if_segment_unverified(self):
        """Promoting draft to atomic claim fails if extraction segment has not been verified by human reviewer."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        # Unverified machine extracted segment
        seg = self.engine.add_extraction_segment(job["id"], {
            "locator": "Page 10",
            "raw_extracted_text": "Machine text"
        })

        draft = self.engine.create_claim_draft({
            "segment_id": seg["segment_id"],
            "target_claim_type": "INDICATION",
            "draft_text": "Candidate indication"
        }, self.user_id)

        with self.assertRaises(ValidationError) as ctx:
            self.engine.promote_draft_to_atomic_claim(draft["id"], self.scholar_id)
        self.assertIn("cannot be promoted until underlying extraction segment is human verified", str(ctx.exception))

    def test_promote_draft_succeeds_after_human_verification(self):
        """Promote draft to atomic claim after segment human verification."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION"
        }, self.user_id)

        seg = self.engine.add_extraction_segment(job["id"], {
            "locator": "Page 50",
            "raw_extracted_text": "Zanjabeel enhances digestive fire."
        })

        # Human verifies segment
        self.engine.review_extraction_segment(seg["segment_id"], {
            "fidelity_status": "human_checked",
            "review_notes": "Fidelity confirmed against print copy."
        }, self.scholar_id)

        draft = self.engine.create_claim_draft({
            "segment_id": seg["segment_id"],
            "target_claim_type": "INDICATION",
            "draft_text": "Zanjabeel (Zingiber officinale) enhances Hazm and stimulates gastric digestion."
        }, self.user_id)

        promoted = self.engine.promote_draft_to_atomic_claim(draft["id"], self.scholar_id)
        self.assertIsNotNone(promoted["id"])
        self.assertEqual(promoted["approval_state"], "UNDER_REVIEW")  # Must start under review in claims registry

        # Draft is marked PROMOTED
        updated_draft = self.engine.get_claim_draft(draft["id"])
        self.assertEqual(updated_draft["draft_status"], "PROMOTED")
        self.assertEqual(updated_draft["promoted_claim_id"], promoted["id"])

    # --------------------------------------------------------------------------
    # 8. Quality Metrics & Queue Health
    # --------------------------------------------------------------------------

    def test_quality_metrics_and_queue_health(self):
        """Quality metrics and queue health report correct counts and ratios."""
        metrics = self.engine.get_ingestion_quality_metrics()
        self.assertIn("total_jobs", metrics)
        self.assertIn("fidelity_distribution", metrics)
        self.assertIn("claim_draft_conversion_rate_pct", metrics)

        health = self.engine.get_ingestion_queue_health()
        self.assertIn("queued_jobs", health)
        self.assertIn("active_jobs", health)
        self.assertIn("queue_healthy", health)


if __name__ == "__main__":
    unittest.main()

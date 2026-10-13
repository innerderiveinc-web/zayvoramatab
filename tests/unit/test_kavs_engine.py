"""Unit tests for Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS) Domain Engine.
Ensures:
1. Five Independent Verification Dimensions (Source authenticity, extraction fidelity,
   evidence characterization, clinical review state, intended-use authorization).
2. Governed Source Versions & Rights Reviews.
3. Ingestion & Extraction Jobs with Page Anchors & OCR Confidence.
4. Independent Evidence Appraisal with Explicit Contradiction Links.
5. Strict Proscription of AI Hallucinations / Autonomous Publishing (Drafts remain drafts until human review).
6. Immutable, Cryptographically Fingerprinted Knowledge Releases.
7. Change-Impact Dependency Engine.
8. Consultation-Time Contextual Retrieval with Deterministic Citation Resolvability.
"""

import os
import unittest
import tempfile
import sqlite3
import json

from apps.api.database.migrator import run_migrations
from apps.api.domains.kavs import KAVSEngine
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError


class TestKAVSEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_kavs.db")
        run_migrations(cls.db_path)

        # Seed essential users, organization, and a base knowledge source
        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        cls.org_id = "org-kavs-001"
        cls.user_id = "user-kavs-admin"
        cls.scholar_id = "user-kavs-scholar"

        conn.execute("""
            INSERT INTO organizations (id, name, code, profile_type, is_active)
            VALUES (?, 'Zayvora KAVS Institute', 'ORG-KAVS', 'MATAB', 1);
        """, (cls.org_id,))

        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, 'kavsadmin', 'admin@kavs.org', 'pbkdf2_sha256$test$hash', 'KAVS Governance Lead', 1);
        """, (cls.user_id, cls.org_id))

        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, 'hakimscholar', 'scholar@kavs.org', 'pbkdf2_sha256$test$hash', 'Hakim Al-Khabir', 1);
        """, (cls.scholar_id, cls.org_id))

        cls.source_id = "src-nfum-vol1"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                publication_date, jurisdiction, regulatory_status, evidence_level,
                review_status, created_at
            ) VALUES (?, 'National Formulary of Unani Medicine Vol I', 'CCRUM / Ministry of AYUSH',
                      'Dept of AYUSH Govt of India', 'PHARMACOPOEIA', 'First Edition',
                      '2006-01-01', 'IN', 'APPROVED_STANDARD', 'CLASSICAL_COMPENDIUM_GRADE_D',
                      'APPROVED', CURRENT_TIMESTAMP);
        """, (cls.source_id,))

        # Seed base knowledge item and claim
        cls.item_id = "item-kavs-senna"
        conn.execute("""
            INSERT INTO knowledge_items (
                id, domain, entity_type, canonical_name, description, clinical_scope,
                claim_type, evidence_level, status, created_by
            ) VALUES (?, 'UNANI', 'SINGLE_DRUG', 'Sana Makki (Cassia senna)',
                      'Stimulant laxative and cathartic botanical agent.',
                      'OUTPATIENT', 'traditional_use', 'EXPERT_OPINION', 'approved', ?);
        """, (cls.item_id, cls.user_id))

        cls.claim_id = "claim-kavs-senna-001"
        conn.execute("""
            INSERT INTO knowledge_claims (
                id, item_id, claim_text, claim_type, evidence_strength, status, approval_state
            ) VALUES (?, ?, 'Sana Makki evacuates yellow bile and phlegm, relieving habitual constipation.',
                      'traditional_use', 'TRADITIONAL_CONSENSUS', 'approved', 'APPROVED');
        """, (cls.claim_id, cls.item_id))

        cls.evidence_id = "evid-kavs-senna-rct"
        conn.execute("""
            INSERT INTO knowledge_evidence (
                id, claim_id, source_id, study_type, result_summary, limitations,
                risk_of_bias, evidence_grade, evidence_status, review_status
            ) VALUES (?, ?, ?, 'RCT', 'Demonstrated safe laxative action over 7 days in adults.',
                      'Sample size n=60; not evaluated in long-term chronic bowel disorders.',
                      'LOW', 'GRADE_B', 'evidence_exists', 'APPROVED');
        """, (cls.evidence_id, cls.claim_id, cls.source_id))

        conn.commit()
        conn.close()

        cls.engine = KAVSEngine(cls.db_path)

    def test_01_source_version_and_rights_review(self):
        """Register specific source edition and evaluate statutory rights."""
        ver = self.engine.register_source_version({
            "source_id": self.source_id,
            "edition": "2nd Revised Edition",
            "publication_year": 2012,
            "source_rights_status": "STATUTORY_AYUSH_OPEN",
            "allowed_uses": ["clinician_contextual_reference", "formulary_definition"]
        }, self.user_id)

        self.assertIsNotNone(ver["id"])
        self.assertEqual(ver["edition"], "2nd Revised Edition")
        self.assertEqual(ver["source_rights_status"], "STATUTORY_AYUSH_OPEN")

        # Record rights review
        rr = self.engine.record_rights_review({
            "source_id": self.source_id,
            "source_version_id": ver["id"],
            "license_type": "STATUTORY_COMPENDIUM",
            "full_text_retention_permitted": True,
            "review_notes": "Statutory publication under AYUSH; permitted for clinical reference."
        }, self.user_id)

        self.assertEqual(rr["status"], "APPROVED")

    def test_02_ingestion_job_and_extraction_fidelity(self):
        """Track extraction segment and human fidelity review."""
        job = self.engine.create_ingestion_job({
            "source_id": self.source_id,
            "job_type": "STRUCTURED_EXTRACTION",
            "original_filename": "NFUM_Vol_I_Part_I.pdf",
            "file_checksum": "sha256:abcd1234ef5678"
        }, self.user_id)

        self.assertEqual(job["status"], "QUEUED")

        # Add segment with initial machine extracted status
        seg = self.engine.add_extraction_segment(job["job_id"], {
            "locator": "Page 142, Monograph 52",
            "raw_extracted_text": "Sana Makki: Dose 3-5 masha with Arq Gulab.",
            "ocr_confidence": 0.94
        })

        self.assertIsNotNone(seg["segment_id"])
        self.assertEqual(seg["status"], "machine_extracted")

        # Review fidelity (human verified)
        rev = self.engine.review_extraction_segment(seg["segment_id"], {
            "fidelity_status": "human_checked",
            "human_corrected_text": "Sana Makki (Cassia angustifolia Vahl.): Dose 3-5 masha with Arq Gulab.",
            "review_notes": "Added botanical authority for unambiguous identification."
        }, self.scholar_id)

        self.assertTrue(rev["verified"])
        self.assertEqual(rev["fidelity_status"], "human_checked")

    def test_03_five_dimension_claim_verification(self):
        """Record the 5 independent verification dimensions for an atomic claim."""
        verif = self.engine.record_claim_verification(self.claim_id, {
            "source_authenticity": "publisher_or_authority_verified",
            "extraction_fidelity": "human_checked",
            "evidence_characterization": "traditional_description",
            "clinical_review_state": "approved_for_defined_use",
            "intended_use_authorization": "clinician_contextual_reference",
            "lead_reviewer_role": "UNANI_SCHOLAR",
            "certainty_level": "ESTABLISHED",
            "risk_of_bias": "LOW",
            "review_comments": "Verified against NFUM Part I. Classical indication established."
        }, self.scholar_id)

        self.assertIsNotNone(verif["id"])
        self.assertEqual(verif["source_authenticity"], "publisher_or_authority_verified")
        self.assertEqual(verif["clinical_review_state"], "approved_for_defined_use")
        self.assertEqual(verif["intended_use_authorization"], "clinician_contextual_reference")

    def test_04_contradicting_evidence_linking(self):
        """Link a contradicting study to a clinical claim."""
        conflict = self.engine.link_evidence_conflict(self.claim_id, {
            "evidence_id": self.evidence_id,
            "relationship_direction": "CONTRADICTING",
            "conflict_summary": "Prolonged use (>14 days) may cause hypokalemia or bowel dependency.",
            "documented_limitations": "Short duration studies cannot rule out chronic electrolyte loss."
        }, self.scholar_id)

        self.assertEqual(conflict["status"], "recorded")

    def test_05_immutable_knowledge_release_and_withdrawal(self):
        """Publish and withdraw an immutable release manifest."""
        rel = self.engine.publish_knowledge_release({
            "release_tag": "kavs-v1.0.0-verified",
            "title": "KAVS Verified AYUSH Formulary Release v1.0",
            "description": "Initial verified release of statutory monographs."
        }, self.user_id)

        self.assertEqual(rel["status"], "ACTIVE")
        self.assertGreaterEqual(rel["total_claims"], 1)
        self.assertIsNotNone(rel["manifest_hash"])

        # Withdraw release
        w = self.engine.withdraw_knowledge_release(
            "kavs-v1.0.0-verified",
            "Testing emergency safety rollback protocol.",
            self.user_id
        )
        self.assertEqual(w["status"], "WITHDRAWN")

    def test_06_change_impact_dependency_engine(self):
        """Record downstream impact when a source is amended."""
        impact = self.engine.record_change_impact({
            "trigger_type": "SOURCE_AMENDED",
            "trigger_entity_type": "SOURCE",
            "trigger_entity_id": self.source_id,
            "details": {"amendment_notes": "Official corrigendum issued by CCRUM."}
        }, self.user_id)

        self.assertIsNotNone(impact["impact_id"])
        self.assertEqual(impact["remediation_status"], "OPEN")
        self.assertGreaterEqual(impact["affected_claims"], 1)

    def test_07_consultation_time_contextual_retrieval(self):
        """Retrieve verified context with resolvable citation and contradiction awareness."""
        # Re-publish active release so retrieval finds verified content
        self.engine.publish_knowledge_release({
            "release_tag": "kavs-v1.0.1-active",
            "title": "KAVS Active Knowledge Release v1.0.1"
        }, self.user_id)

        res = self.engine.retrieve_verified_clinical_context(
            query="Sana Makki",
            intended_use="clinician_contextual_reference"
        )

        self.assertFalse(res["insufficient_information"])
        self.assertGreaterEqual(res["total"], 1)
        first_item = res["results"][0]
        self.assertIn("Sana Makki", first_item["claim_text"])
        self.assertEqual(first_item["verification"]["source_authenticity"], "publisher_or_authority_verified")
        self.assertEqual(first_item["source"]["title"], "National Formulary of Unani Medicine Vol I")
        self.assertFalse(first_item["generated_draft"])

        # Check that contradicting evidence was surfaced
        self.assertGreaterEqual(len(first_item["contradictions"]), 1)
        self.assertIn("hypokalemia", first_item["contradictions"][0]["conflict_summary"])

    def test_08_insufficient_information_honest_reporting(self):
        """Empty or unverified query honestly reports insufficient information."""
        res = self.engine.retrieve_verified_clinical_context(
            query="CompletelyNonExistentHerbalEntity12345",
            intended_use="clinician_contextual_reference"
        )
        self.assertTrue(res["insufficient_information"])
        self.assertEqual(res["total"], 0)
        self.assertIn("No verified clinical claims found", res["caveat"])


if __name__ == "__main__":
    unittest.main()

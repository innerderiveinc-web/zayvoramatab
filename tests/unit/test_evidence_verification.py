"""Unit tests for Prompt 21: Evidence Classification, Clinical Claim Verification & Citation Validation Engine.

Covers all 25 specific test cases mandated by Prompt 21 Section 15:
1. test_claim_cannot_be_created_with_fabricated_source
2. test_dimension_independence_preserved
3. test_bibliographic_mismatch_fails_dimension
4. test_source_retraction_marks_version_status
5. test_retraction_cascading_suspends_active_claims
6. test_passage_fidelity_negation_fails
7. test_passage_fidelity_unresolved_fails_support
8. test_direct_support_requires_positive_evidence
9. test_contradictory_passage_marks_contradicts_claim
10. test_abstract_only_blocks_full_claim_support
11. test_claim_laundering_traditional_to_modern_prohibited
12. test_claim_laundering_animal_to_human_prohibited
13. test_claim_laundering_association_to_causation_prohibited
14. test_ai_proposed_support_requires_human_review
15. test_ai_proposed_characterization_requires_human_review
16. test_unqualified_reviewer_cannot_approve
17. test_publication_gate_fails_closed_without_approval
18. test_publication_gate_blocks_suspended_claims
19. test_publication_gate_blocks_unsupported_claims
20. test_standardized_clinical_statement_rendered
21. test_evidence_conflict_queue_logging
22. test_evidence_conflict_resolution
23. test_missing_study_details_remain_not_reported
24. test_surface_restrictions_enforced
25. test_time_bounded_approval_expiration
"""

import os
import unittest
import tempfile
import sqlite3
import json
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.domains.evidence_verification import EvidenceVerificationEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestEvidenceVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_evidence_verification.db")
        run_migrations(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        cls.admin_user_id = "usr-admin-ev-01"
        cls.scholar_user_id = "usr-scholar-ev-02"
        cls.clinician_user_id = "usr-clinician-ev-03"
        cls.unauthorized_user_id = "usr-guest-ev-04"

        conn.execute("""
            INSERT INTO organizations (id, name, code, profile_type, is_active)
            VALUES ('org-ev-01', 'Zayvora Evidence Research', 'ORG-EV-01', 'MATAB', 1);
        """)

        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-ev-01', 'admin_ev', 'admin@ev.org', 'test$hash', 'Dr. System Admin', 1);
        """, (cls.admin_user_id,))
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-ev-01', 'scholar_ev', 'scholar@ev.org', 'test$hash', 'Hakim Unani Scholar', 1);
        """, (cls.scholar_user_id,))
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-ev-01', 'clinician_ev', 'clinician@ev.org', 'test$hash', 'Dr. Clinician Specialist', 1);
        """, (cls.clinician_user_id,))
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-ev-01', 'guest_ev', 'guest@ev.org', 'test$hash', 'Guest User', 1);
        """, (cls.unauthorized_user_id,))


        # Seed valid source & source version
        cls.source_id = "src-al-qanun-01"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Canon of Medicine Vol 2', 'Ibn Sina', 'Dar al-Kutub',
                      'CLASSICAL_TEXT', 'Bulaq Edition', 'HISTORICAL_REFERENCE', 'EXPERT_OPINION', 'APPROVED');
        """, (cls.source_id,))

        cls.version_id = "ver-qanun-v2"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, 'Bulaq 1877', 1877, 'hash1234567890abcdef', 'PUBLIC_DOMAIN', ?);
        """, (cls.version_id, cls.source_id, cls.admin_user_id))

        cls.modern_source_id = "src-modern-trial-01"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Double-Blind Trial of Senna in Constipation', 'Smith J et al.', 'Lancet Herbal',
                      'JOURNAL_ARTICLE', '2021', 'PEER_REVIEWED', 'RANDOMIZED_CONTROLLED_TRIAL', 'APPROVED');
        """, (cls.modern_source_id,))

        cls.modern_version_id = "ver-modern-v1"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '2021 Vol 12', 2021, 'hashmodern1234567890', 'CC_BY', ?);
        """, (cls.modern_version_id, cls.modern_source_id, cls.admin_user_id))

        # Seed an extraction page and passage
        cls.job_id = "job-ev-01"
        conn.execute("""
            INSERT INTO kavs_ingestion_jobs (
                id, source_id, source_version_id, job_type, original_filename, status, initiated_by
            ) VALUES (?, ?, ?, 'STRUCTURED_EXTRACTION', 'Canon_Vol2.pdf', 'completed', ?);
        """, (cls.job_id, cls.source_id, cls.version_id, cls.admin_user_id))

        cls.passage_id = "pas-qanun-senna-01"
        conn.execute("""
            INSERT INTO kavs_extraction_pages (
                id, job_id, source_version_id, pdf_page_index, printed_page_label,
                raw_page_text, ocr_confidence, page_status
            ) VALUES ('page-qanun-210', ?, ?, 210, '210', 'Sana Makki is mushil (purgative) for balgham and sawda in appropriate dosage.', 0.99, 'EXTRACTED');
        """, (cls.job_id, cls.version_id))

        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, fidelity_status,
                ocr_confidence, human_corrected_text, reviewed_by
            ) VALUES (?, ?, ?, 'Page 210',
                      'Sana Makki is mushil (purgative) for balgham and sawda in appropriate dosage.',
                      'human_checked', 0.99,
                      'Sana Makki is mushil (purgative) for balgham and sawda in appropriate dosage.', ?);
        """, (cls.passage_id, cls.job_id, cls.source_id, cls.admin_user_id))

        conn.commit()
        conn.close()

        cls.engine = EvidenceVerificationEngine(cls.db_path)

        cls.admin_ctx = {
            "user_id": cls.admin_user_id,
            "roles": ["SYSTEM_ADMIN"],
            "permissions": ["knowledge:manage", "knowledge:review", "knowledge:approve", "knowledge:read"]
        }
        cls.scholar_ctx = {
            "user_id": cls.scholar_user_id,
            "roles": ["UNANI_SCHOLAR"],
            "permissions": ["knowledge:read", "knowledge:review"]
        }
        cls.clinician_ctx = {
            "user_id": cls.clinician_user_id,
            "roles": ["CLINICAL_SPECIALIST"],
            "permissions": ["knowledge:read", "knowledge:review", "knowledge:approve"]
        }
        cls.unauthorized_ctx = {
            "user_id": cls.unauthorized_user_id,
            "roles": ["GUEST"],
            "permissions": ["knowledge:read"]
        }

    # -------------------------------------------------------------------------
    # Test 1: Fabricated source link rejection
    # -------------------------------------------------------------------------
    def test_claim_cannot_be_created_with_fabricated_source(self):
        """Linking a claim to a nonexistent source_version_id or missing passage fails."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-FAB-01",
            "claim_text": "Senna causes immediate purgation.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        # Attempt with nonexistent source_version_id
        with self.assertRaises(ValidationError) as ctx:
            self.engine.link_claim_to_source(claim["id"], {
                "source_version_id": "nonexistent-version-999",
                "source_passage_text": "Fabricated text passage."
            }, self.admin_user_id)
        self.assertIn("does not exist", str(ctx.exception))

        # Attempt with empty passage text
        with self.assertRaises(ValidationError) as ctx:
            self.engine.link_claim_to_source(claim["id"], {
                "source_version_id": self.version_id,
                "source_passage_text": "   "
            }, self.admin_user_id)
        self.assertIn("cannot be empty", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 2: Dimension independence preserved (no boolean collapsing)
    # -------------------------------------------------------------------------
    def test_dimension_independence_preserved(self):
        """Citation validation run records discrete states for each dimension without collapsing to a boolean."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-DIM-01",
            "claim_text": "Sana Makki expels phlegm and black bile.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.version_id,
            "source_passage_id": self.passage_id,
            "source_passage_text": "Sana Makki is mushil (purgative) for balgham and sawda in appropriate dosage."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx)

        # Ensure discrete states exist
        self.assertIn("bibliographic_identity_state", run)
        self.assertIn("version_status_state", run)
        self.assertIn("passage_fidelity_state", run)
        self.assertIn("claim_support_state", run)
        self.assertIn("applicability_state", run)
        self.assertIn("intended_use_state", run)

        self.assertEqual(run["bibliographic_identity_state"], "verified")
        self.assertEqual(run["version_status_state"], "current")
        self.assertEqual(run["passage_fidelity_state"], "exact_match")
        self.assertEqual(run["claim_support_state"], "direct_support")
        # Ensure no collapsed is_valid boolean exists
        self.assertNotIn("is_valid", run)

    # -------------------------------------------------------------------------
    # Test 3: Bibliographic mismatch fails dimension
    # -------------------------------------------------------------------------
    def test_bibliographic_mismatch_fails_dimension(self):
        """Title or identifier mismatch marks bibliographic_identity_state = mismatch."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-BIB-01",
            "claim_text": "Senna usage text.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.version_id,
            "source_passage_text": "Passage text."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx, run_params={
            "expected_source_title": "Completely Wrong Book Name That Does Not Match"
        })

        self.assertEqual(run["bibliographic_identity_state"], "mismatch")

    # -------------------------------------------------------------------------
    # Test 4: Source retraction marks version status
    # -------------------------------------------------------------------------
    def test_source_retraction_marks_version_status(self):
        """Retracted source version marks version_status_state = retracted."""
        conn = sqlite3.connect(self.db_path)
        retracted_ver = "ver-retracted-01"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '2019 Fraudulent', 2019, 'hashfraud123', 'CC_BY', ?);
        """, (retracted_ver, self.modern_source_id, self.admin_user_id))
        conn.commit()
        conn.close()

        # Record retraction event
        self.engine.record_source_status_event(retracted_ver, {
            "event_type": "retraction",
            "event_description": "Data fabrication discovered by publisher."
        }, self.admin_user_id)

        claim = self.engine.create_claim({
            "claim_code": "CLM-RET-01",
            "claim_text": "Retracted drug efficacy claim.",
            "claim_type": "clinical_outcome"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": retracted_ver,
            "source_passage_text": "Fabricated trial result."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx)
        self.assertEqual(run["version_status_state"], "retracted")

    # -------------------------------------------------------------------------
    # Test 5: Retraction cascading suspends active claims
    # -------------------------------------------------------------------------
    def test_retraction_cascading_suspends_active_claims(self):
        """Source retraction event automatically propagates and suspends active intended-use approvals."""
        conn = sqlite3.connect(self.db_path)
        cascade_ver = "ver-cascade-01"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '2020 Trial', 2020, 'hashcascade123', 'CC_BY', ?);
        """, (cascade_ver, self.modern_source_id, self.admin_user_id))
        conn.commit()
        conn.close()

        claim = self.engine.create_claim({
            "claim_code": "CLM-CASC-01",
            "claim_text": "Causal cure rate of 95% in clinical trial.",
            "claim_type": "clinical_outcome"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": cascade_ver,
            "source_passage_text": "95% cure rate observed."
        }, self.admin_user_id)

        # Create active intended-use approval
        appr = self.engine.create_intended_use_approval({
            "claim_id": claim["id"],
            "claim_version_id": claim["current_version_id"],
            "allowed_surface": "clinician_context",
            "audience": "all_clinicians"
        }, self.clinician_ctx)
        self.assertEqual(appr["status"], "active")

        # Now record retraction
        evt = self.engine.record_source_status_event(cascade_ver, {
            "event_type": "retraction",
            "event_description": "Critical methodological error invalidates trial."
        }, self.admin_user_id)

        self.assertIn(claim["id"], evt["affected_claim_ids"])

        # Check intended-use approval is now suspended
        cur_appr = self.engine.get_intended_use_approval(appr["id"])
        self.assertEqual(cur_appr["status"], "suspended")
        self.assertIn("Automatic cascade suspension", cur_appr["suspension_reason"])

    # -------------------------------------------------------------------------
    # Test 6: Passage fidelity negation check fails
    # -------------------------------------------------------------------------
    def test_passage_fidelity_negation_fails(self):
        """Negation words in passage mark negation_mismatch and block direct_support."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-NEG-01",
            "claim_text": "Drug X reduces blood pressure.",
            "claim_type": "preclinical_evidence"
        }, self.admin_user_id)

        # Passage says did NOT reduce
        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.modern_version_id,
            "source_passage_text": "Drug X did not reduce blood pressure in patients."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx)
        self.assertEqual(run["passage_fidelity_state"], "negation_mismatch")
        self.assertNotEqual(run["claim_support_state"], "direct_support")

    # -------------------------------------------------------------------------
    # Test 7: Passage fidelity unresolved fails support
    # -------------------------------------------------------------------------
    def test_passage_fidelity_unresolved_fails_support(self):
        """Unresolved fidelity blocks direct_support and results in extraction_fidelity_unresolved."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-UNRES-01",
            "claim_text": "Plant Y relieves pain.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.version_id,
            "source_passage_text": "Plant Y text."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx, run_params={
            "force_fidelity_state": "fidelity_unresolved"
        })
        self.assertEqual(run["passage_fidelity_state"], "fidelity_unresolved")
        self.assertEqual(run["claim_support_state"], "extraction_fidelity_unresolved")

    # -------------------------------------------------------------------------
    # Test 8: Direct support requires positive evidence
    # -------------------------------------------------------------------------
    def test_direct_support_requires_positive_evidence(self):
        """Direct support outcome requires passage evidence affirming the claim."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-DIR-01",
            "claim_text": "Sana Makki acts as an effective purgative.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.version_id,
            "source_passage_text": "Sana Makki acts as an effective purgative (mushil) of humoral matter."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx)
        self.assertEqual(run["claim_support_state"], "direct_support")

    # -------------------------------------------------------------------------
    # Test 9: Contradictory passage marks contradicts_claim
    # -------------------------------------------------------------------------
    def test_contradictory_passage_marks_contradicts_claim(self):
        """Passage asserting the opposite of the claim marks contradicts_claim."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-CONTRA-01",
            "claim_text": "Substance Z is entirely harmless and causes no adverse events.",
            "claim_type": "safety_information"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.modern_version_id,
            "source_passage_text": "Substance Z is toxic and causes severe adverse hepatotoxicity."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx)
        self.assertEqual(run["claim_support_state"], "contradicts_claim")

    # -------------------------------------------------------------------------
    # Test 10: Abstract-only blocks full claim support
    # -------------------------------------------------------------------------
    def test_abstract_only_blocks_full_claim_support(self):
        """Passage from abstract only cannot directly support detailed clinical dosing claims."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-ABST-01",
            "claim_text": "Administer 50mg twice daily with milk for 14 days.",
            "claim_type": "clinical_outcome"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.modern_version_id,
            "source_passage_text": "Abstract: Herb showed positive results in randomized trial.",
            "locator_section": "abstract"
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx)
        self.assertNotEqual(run["claim_support_state"], "direct_support")
        self.assertEqual(run["claim_support_state"], "partial_support")

    # -------------------------------------------------------------------------
    # Test 11: Claim laundering traditional to modern prohibited
    # -------------------------------------------------------------------------
    def test_claim_laundering_traditional_to_modern_prohibited(self):
        """Traditional text cannot support modern clinical outcome without modern clinical study."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-LAUND-01",
            "claim_text": "Proven in double-blind clinical trial to cure diabetes.",
            "claim_type": "clinical_outcome"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.version_id,  # Classical text
            "source_passage_text": "Ibn Sina says herb improves sweet urine."
        }, self.admin_user_id)

        run = self.engine.validate_citation(link["id"], self.admin_ctx)
        # Category N requires clinical study; classical text cannot support modern clinical outcome directly
        self.assertNotEqual(run["claim_support_state"], "direct_support")
        self.assertEqual(run["claim_support_state"], "applicability_uncertain")

    # -------------------------------------------------------------------------
    # Test 12: Claim laundering animal to human prohibited
    # -------------------------------------------------------------------------
    def test_claim_laundering_animal_to_human_prohibited(self):
        """Preclinical animal study cannot support claim of direct human patient cure."""
        char = self.engine.create_evidence_characterization({
            "source_version_id": self.modern_version_id,
            "question_type": "intervention",
            "design_code": "preclinical_in_vivo",
            "human_subjects": False
        }, self.admin_user_id)

        claim = self.engine.create_claim({
            "claim_code": "CLM-ANIMAL-01",
            "claim_text": "Compound cures rheumatoid arthritis in human patients.",
            "claim_type": "clinical_outcome"
        }, self.admin_user_id)

        # Attempting intended-use approval with non-human evidence for clinician_context fails
        with self.assertRaises(ValidationError) as ctx:
            self.engine.create_intended_use_approval({
                "claim_id": claim["id"],
                "claim_version_id": claim["current_version_id"],
                "allowed_surface": "clinician_context",
                "evidence_characterization_id": char["id"],
                "audience": "all_clinicians"
            }, self.clinician_ctx)
        self.assertIn("Preclinical in-vivo/in-vitro evidence cannot be approved for clinician_context", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 13: Claim laundering association to causation prohibited
    # -------------------------------------------------------------------------
    def test_claim_laundering_association_to_causation_prohibited(self):
        """Observational cohort study cannot be used to claim proven causal cure."""
        char = self.engine.create_evidence_characterization({
            "source_version_id": self.modern_version_id,
            "question_type": "intervention",
            "design_code": "cohort_study",
            "human_subjects": True
        }, self.admin_user_id)

        claim = self.engine.create_claim({
            "claim_code": "CLM-ASSOC-01",
            "claim_text": "Intake causes 100% eradication of infection.",
            "claim_type": "clinical_outcome"
        }, self.admin_user_id)

        # When checking clinical statement generation, observational study must state association, not causation
        stmt = self.engine.generate_standardized_statement(
            claim=claim,
            characterization=char,
            support_outcome="direct_support"
        )
        self.assertIn("Observational cohort evidence suggests an association", stmt)
        self.assertNotIn("Proven causal eradication", stmt)

    # -------------------------------------------------------------------------
    # Test 14: AI proposed support requires human review
    # -------------------------------------------------------------------------
    def test_ai_proposed_support_requires_human_review(self):
        """Support assessment proposed by AI remains ai_proposed until reviewed by human."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-AI-01",
            "claim_text": "Herb is effective for headache.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.version_id,
            "source_passage_text": "Herb relieves sada (headache)."
        }, self.admin_user_id)

        sa = self.engine.create_support_assessment({
            "claim_source_link_id": link["id"],
            "support_outcome": "direct_support",
            "is_ai_proposed": True,
            "model_version": "gemini-1.5-pro",
            "confidence_score": 0.94
        }, self.admin_user_id)

        self.assertEqual(sa["review_state"], "ai_proposed")

        # Qualified reviewer approves
        reviewed = self.engine.review_support_assessment(
            assessment_id=sa["id"],
            user_ctx=self.scholar_ctx,
            decision="approved",
            rationale="Verified against Arabic text."
        )
        self.assertEqual(reviewed["review_state"], "approved")
        self.assertEqual(reviewed["reviewed_by"], self.scholar_user_id)

    # -------------------------------------------------------------------------
    # Test 15: AI proposed characterization requires human review
    # -------------------------------------------------------------------------
    def test_ai_proposed_characterization_requires_human_review(self):
        """Evidence characterization proposed by AI remains ai_proposed until human review."""
        ec = self.engine.create_evidence_characterization({
            "source_version_id": self.modern_version_id,
            "question_type": "intervention",
            "design_code": "randomized_trial",
            "human_subjects": True,
            "is_ai_proposed": True,
            "model_version": "claude-3-opus"
        }, self.admin_user_id)

        self.assertEqual(ec["review_state"], "ai_proposed")

        # Clinician reviews
        reviewed = self.engine.review_evidence_characterization(
            characterization_id=ec["id"],
            user_ctx=self.clinician_ctx,
            review_state="approved",
            rationale="Methodology verified."
        )
        self.assertEqual(reviewed["review_state"], "approved")
        self.assertEqual(reviewed["reviewed_by"], self.clinician_user_id)

    # -------------------------------------------------------------------------
    # Test 16: Unqualified reviewer cannot approve
    # -------------------------------------------------------------------------
    def test_unqualified_reviewer_cannot_approve(self):
        """User without required role or permission cannot approve assessment or intended use."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-UNQUAL-01",
            "claim_text": "Some claim.",
            "claim_type": "clinical_outcome"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.modern_version_id,
            "source_passage_text": "Some passage."
        }, self.admin_user_id)

        sa = self.engine.create_support_assessment({
            "claim_source_link_id": link["id"],
            "support_outcome": "direct_support",
            "is_ai_proposed": True
        }, self.admin_user_id)

        # Unauthorized guest tries to approve
        with self.assertRaises(ForbiddenError):
            self.engine.review_support_assessment(
                assessment_id=sa["id"],
                user_ctx=self.unauthorized_ctx,
                decision="approved"
            )

    # -------------------------------------------------------------------------
    # Test 17: Publication gate fails closed without approval
    # -------------------------------------------------------------------------
    def test_publication_gate_fails_closed_without_approval(self):
        """Clinician context panel blocks publication if no active intended-use approval exists."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-GATE-NO-APPR",
            "claim_text": "Herb treats gastrointestinal pain.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        panel = self.engine.get_clinician_context_claim(claim["id"])
        gate = panel["clinician_context_panel"]["publication_gate"]

        self.assertFalse(gate["is_publication_allowed"])
        self.assertEqual(gate["blocking_reason"], "NO_ACTIVE_INTENDED_USE_APPROVAL")

    # -------------------------------------------------------------------------
    # Test 18: Publication gate blocks suspended claims
    # -------------------------------------------------------------------------
    def test_publication_gate_blocks_suspended_claims(self):
        """Clinician context panel blocks publication if intended-use approval is suspended."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-GATE-SUSPENDED",
            "claim_text": "Clinical recommendation statement.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        appr = self.engine.create_intended_use_approval({
            "claim_id": claim["id"],
            "claim_version_id": claim["current_version_id"],
            "allowed_surface": "clinician_context",
            "audience": "all_clinicians"
        }, self.clinician_ctx)

        # Suspend approval
        self.engine.suspend_intended_use_approval(appr["id"], self.admin_ctx, "Safety review audit")

        panel = self.engine.get_clinician_context_claim(claim["id"])
        gate = panel["clinician_context_panel"]["publication_gate"]

        self.assertFalse(gate["is_publication_allowed"])
        self.assertEqual(gate["blocking_reason"], "APPROVAL_SUSPENDED")

    # -------------------------------------------------------------------------
    # Test 19: Publication gate blocks unsupported claims
    # -------------------------------------------------------------------------
    def test_publication_gate_blocks_unsupported_claims(self):
        """Clinician context panel blocks publication if claim has unresolved or contradictory support."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-UNSUPP-01",
            "claim_text": "Unsupported health benefit.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        # Link with contradictory passage
        link = self.engine.link_claim_to_source(claim["id"], {
            "source_version_id": self.version_id,
            "source_passage_text": "Opposite finding recorded."
        }, self.admin_user_id)

        self.engine.validate_citation(link["id"], self.admin_ctx, run_params={
            "force_claim_support_state": "contradicts_claim"
        })

        # Try to approve intended use
        with self.assertRaises(ValidationError) as ctx:
            self.engine.create_intended_use_approval({
                "claim_id": claim["id"],
                "claim_version_id": claim["current_version_id"],
                "allowed_surface": "clinician_context"
            }, self.clinician_ctx)
        self.assertIn("cannot be approved for clinician_context because citation support", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 20: Standardized clinical statement rendered
    # -------------------------------------------------------------------------
    def test_standardized_clinical_statement_rendered(self):
        """Generates exact standardized statement format according to evidence type and design."""
        # 1. Traditional document
        trad_claim = self.engine.create_claim({
            "claim_code": "CLM-STMT-TRAD",
            "claim_text": "Hab-e-Suranjan relieves joint swelling.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        link = self.engine.link_claim_to_source(trad_claim["id"], {
            "source_version_id": self.version_id,
            "source_passage_text": "Hab-e-Suranjan is beneficial in waja al-mafasil."
        }, self.admin_user_id)

        stmt = self.engine.generate_standardized_statement(trad_claim, None, "direct_support")
        self.assertIn("Documented in traditional Unani medical texts as", stmt)
        self.assertIn("formal modern clinical efficacy has not been established", stmt)

    # -------------------------------------------------------------------------
    # Test 21: Evidence conflict queue logging
    # -------------------------------------------------------------------------
    def test_evidence_conflict_queue_logging(self):
        """Recording conflicting assertions logs a formal conflict record into queue."""
        claim1 = self.engine.create_claim({
            "claim_code": "CLM-CONF-1",
            "claim_text": "Mizaj of herb is Hot 2nd degree.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        claim2 = self.engine.create_claim({
            "claim_code": "CLM-CONF-2",
            "claim_text": "Mizaj of herb is Cold 1st degree.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        conflict = self.engine.create_evidence_conflict({
            "claim_a_id": claim1["id"],
            "claim_b_id": claim2["id"],
            "conflict_type": "direct_contradiction",
            "description": "Ibn Sina and Razi classify Mizaj differently."
        }, self.admin_user_id)

        self.assertEqual(conflict["status"], "open")
        self.assertEqual(conflict["conflict_type"], "direct_contradiction")

        # List queue
        queue = self.engine.list_evidence_conflicts(status="open")
        self.assertTrue(any(c["id"] == conflict["id"] for c in queue))

    # -------------------------------------------------------------------------
    # Test 22: Evidence conflict resolution
    # -------------------------------------------------------------------------
    def test_evidence_conflict_resolution(self):
        """Adjudicating a conflict updates status and logs rationale with resolution scope."""
        claim1 = self.engine.create_claim({
            "claim_code": "CLM-CONF-RES-1",
            "claim_text": "Dosage is 3 dirhams.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        conflict = self.engine.create_evidence_conflict({
            "claim_a_id": claim1["id"],
            "conflict_type": "dose_disagreement",
            "description": "Disagreement between crude herb powder and decoction dosage."
        }, self.admin_user_id)

        resolved = self.engine.resolve_evidence_conflict(
            conflict_id=conflict["id"],
            user_ctx=self.scholar_ctx,
            status="resolved_with_scope",
            rationale="Resolved: 3 dirhams applies to joshanda (decoction); 1 dirham applies to safoof (powder)."
        )

        self.assertEqual(resolved["status"], "resolved_with_scope")
        self.assertEqual(resolved["resolved_by"], self.scholar_user_id)
        self.assertIn("joshanda", resolved["resolution_rationale"])

    # -------------------------------------------------------------------------
    # Test 23: Missing study details remain not_reported
    # -------------------------------------------------------------------------
    def test_missing_study_details_remain_not_reported(self):
        """Characterization preserves not_reported / unclear instead of inventing values."""
        ec = self.engine.create_evidence_characterization({
            "source_version_id": self.modern_version_id,
            "question_type": "intervention",
            "design_code": "randomized_trial",
            "human_subjects": True
            # Omitting sample_size, effect_size, p_value, blinding, allocation_concealment
        }, self.admin_user_id)

        self.assertEqual(ec["sample_size_total"], "not_reported")
        self.assertEqual(ec["effect_size"], "not_reported")
        self.assertEqual(ec["p_value"], "not_reported")
        self.assertEqual(ec["blinding"], "unclear")
        self.assertEqual(ec["allocation_concealment"], "unclear")

    # -------------------------------------------------------------------------
    # Test 24: Surface restrictions enforced
    # -------------------------------------------------------------------------
    def test_surface_restrictions_enforced(self):
        """Intended use is restricted to permitted surfaces (e.g. Category M cannot be published to clinician_context)."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-SURF-01",
            "claim_text": "Organ-Axis navigation grouping for liver and stomach.",
            "claim_type": "product_framework_editorial"  # Category M
        }, self.admin_user_id)

        with self.assertRaises(ValidationError) as ctx:
            self.engine.create_intended_use_approval({
                "claim_id": claim["id"],
                "claim_version_id": claim["current_version_id"],
                "allowed_surface": "clinician_context"  # Category M allows only educational_reference & research_workspace
            }, self.clinician_ctx)
        self.assertIn("Surface 'clinician_context' is not permitted for claim type 'product_framework_editorial'", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 25: Time-bounded approval expiration
    # -------------------------------------------------------------------------
    def test_time_bounded_approval_expiration(self):
        """Expired approval is marked expired and publication is blocked."""
        claim = self.engine.create_claim({
            "claim_code": "CLM-TIME-01",
            "claim_text": "Time-bounded approved claim.",
            "claim_type": "traditional_use_documentation"
        }, self.admin_user_id)

        # Set valid_until to yesterday
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        appr = self.engine.create_intended_use_approval({
            "claim_id": claim["id"],
            "claim_version_id": claim["current_version_id"],
            "allowed_surface": "clinician_context",
            "valid_until": yesterday
        }, self.clinician_ctx)

        # Fetch clinician context panel
        panel = self.engine.get_clinician_context_claim(claim["id"])
        gate = panel["clinician_context_panel"]["publication_gate"]

        self.assertFalse(gate["is_publication_allowed"])
        self.assertEqual(gate["blocking_reason"], "APPROVAL_EXPIRED")


if __name__ == "__main__":
    unittest.main()

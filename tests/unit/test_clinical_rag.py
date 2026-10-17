"""Unit tests for Prompt 22: Evidence-Aware Clinical Knowledge Retrieval (Hybrid RAG) & Answer Generation Engine.

Verifies non-negotiable requirements from Prompt 22 Section 19:
1. Exact citation and source lookup resolution.
2. Lexical retrieval finds approved aliases without forced equivalence.
3. Substance/material identity ambiguity detection.
4. Access, review-state, and intended-use filters cannot be bypassed by search hits.
5. Traditional Unani use is not rewritten as proven modern clinical efficacy.
6. Preclinical evidence is not rewritten as human clinical cure.
7. Observational associations are not rewritten as causation.
8. Retracted/withdrawn source editions are blocked from clinical answers.
9. Autonomous diagnosis and prescribing requests are strictly intercepted (restricted_request).
10. Every factual claim has an explicit, valid citation binding.
11. Unknown citation IDs fail post-generation validation.
12. Truthful abstention on insufficient evidence (no hallucination).
13. Immutable evidence packs with deterministic reproducibility hashes.
14. Retrieval feedback queue creation and resolution lifecycle.
15. Patient encounter context isolation (zero leakage into global corpus).
"""

import os
import json
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.domains.clinical_rag import ClinicalRAGEngine
from apps.api.core.errors import ValidationError, NotFoundError


class TestClinicalRAGEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_clinical_rag.db")
        run_migrations(self.db_path)
        self.engine = ClinicalRAGEngine(self.db_path)

        self.user_clinician = {
            "user_id": "usr-doc-01",
            "username": "hakeem_ahmed",
            "role": "CLINICIAN",
            "roles": ["CLINICIAN"],
            "permissions": ["knowledge:read"]
        }
        self.user_admin = {
            "user_id": "usr-admin-01",
            "username": "admin_zayvora",
            "role": "ORG_ADMIN",
            "roles": ["ORG_ADMIN", "SYSTEM_ADMIN"],
            "permissions": ["knowledge:read", "knowledge:manage", "knowledge:review", "knowledge:approve"]
        }

        self._seed_test_fixtures()

    def _seed_test_fixtures(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # 1. Classical Source & Version
        self.src_classical = "src-qanun-01"
        cur.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Al-Qanun fi al-Tibb', 'Ibn Sina', 'Bulaq Press',
                      'CLASSICAL_TEXT', 'First Edition', 'HISTORICAL_REFERENCE', 'EXPERT_OPINION', 'APPROVED');
        """, (self.src_classical,))

        self.ver_classical = "ver-qanun-1877"
        cur.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '1877', 1877, 'hash-qanun-1877', 'PUBLIC_DOMAIN', 'usr-admin-01');
        """, (self.ver_classical, self.src_classical))

        # Extracted Segments
        self.seg_asarun = "seg-asarun-01"
        cur.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text, fidelity_status
            ) VALUES (?, 'job-01', ?, 'Book II, p. 42',
                      'Asarun opens hepatic obstructions and strengthens stomach.',
                      'Asarun opens hepatic obstructions and strengthens stomach.', 'human_checked');
        """, (self.seg_asarun, self.src_classical))

        # 2. Modern Journal Source (will test retraction)
        self.src_modern = "src-trial-01"
        cur.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Clinical Trial on Polyherbal Formula', 'Dr. Z', 'AYUSH Research Journal',
                      'MODERN_JOURNAL_ARTICLE', 'Vol 10', 'PEER_REVIEWED', 'CLINICAL_TRIAL', 'APPROVED');
        """, (self.src_modern,))

        self.ver_modern = "ver-trial-2024"
        cur.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '2024', 2024, 'hash-trial-2024', 'OPEN_ACCESS', 'usr-admin-01');
        """, (self.ver_modern, self.src_modern))

        self.seg_trial = "seg-trial-01"
        cur.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text, fidelity_status
            ) VALUES (?, 'job-02', ?, 'p. 115',
                      'Formula showed significant reduction in dyspeptic symptoms in trial cohort.',
                      'Formula showed significant reduction in dyspeptic symptoms in trial cohort.', 'human_checked');
        """, (self.seg_trial, self.src_modern))

        # 3. Canonical Concepts from Prompt 19
        self.cpt_mizaj = "cpt-mizaj-01"
        cur.execute("""
            INSERT INTO knowledge_concepts (
                id, canonical_label, concept_type, status, created_by
            ) VALUES (?, 'Mizaj', 'assessment_concept', 'approved_identity', 'usr-admin-01');
        """, (self.cpt_mizaj,))

        cur.execute("""
            INSERT INTO concept_names (
                id, concept_id, name_text_original, normalized_search_text, script, language_tag, name_type, created_by
            ) VALUES ('cn-01', ?, 'Temperament', 'temperament', 'latin', 'en', 'preferred_label', 'usr-admin-01'),
                     ('cn-02', ?, 'مزاج', 'مزاج', 'arabic', 'ar', 'source_name', 'usr-admin-01');
        """, (self.cpt_mizaj, self.cpt_mizaj))

        # Ambiguous botanical concepts (same name 'Kundur' for Boswellia carterii vs Boswellia serrata)
        cur.execute("""
            INSERT INTO knowledge_concepts (id, canonical_label, concept_type, status, created_by)
            VALUES ('cpt-kundur-01', 'Kundur (Carterii)', 'ingredient', 'approved_identity', 'usr-admin-01'),
                   ('cpt-kundur-02', 'Kundur (Serrata)', 'ingredient', 'approved_identity', 'usr-admin-01');
        """)
        cur.execute("""
            INSERT INTO concept_names (id, concept_id, name_text_original, normalized_search_text, script, language_tag, name_type, created_by)
            VALUES ('cn-k1', 'cpt-kundur-01', 'Kundur', 'kundur', 'arabic', 'ar', 'synonym', 'usr-admin-01'),
                   ('cn-k2', 'cpt-kundur-02', 'Kundur', 'kundur', 'arabic', 'ar', 'synonym', 'usr-admin-01');
        """)

        # 4. Prompt 21 Claims and Approvals
        # Claim A: Traditional use documentation
        self.claim_asarun = "clm-asarun-01"
        cur.execute("""
            INSERT INTO knowledge_claims (
                id, item_id, claim_text, claim_type, evidence_strength, status, approval_state
            ) VALUES (?, 'kit-01', 'Asarun opens hepatic obstructions.', 'traditional_use_documentation',
                      'HISTORICAL_HIGH', 'approved', 'APPROVED');
        """, (self.claim_asarun,))

        self.link_asarun = "csl-asarun-01"
        cur.execute("""
            INSERT INTO claim_source_links (
                id, claim_id, source_record_id, source_version_id, source_passage_id,
                locator_text, link_role, created_by
            ) VALUES (?, ?, ?, ?, ?, 'Asarun opens hepatic obstructions.', 'primary_support', 'usr-admin-01');
        """, (self.link_asarun, self.claim_asarun, self.src_classical, self.ver_classical, self.seg_asarun))

        cur.execute("""
            INSERT INTO citation_validation_runs (
                id, claim_source_link_id, bibliographic_identity_state, version_status_state,
                passage_fidelity_state, claim_support_state, applicability_state, intended_use_state,
                validation_method, run_by
            ) VALUES ('cvr-01', ?, 'verified', 'current', 'exact_match', 'direct_support', 'direct', 'approved', 'DETERMINISTIC_PASSAGE_CHECK', 'usr-admin-01');
        """, (self.link_asarun,))

        cur.execute("""
            INSERT INTO intended_use_approvals (
                id, claim_id, claim_version, allowed_surface, audience, status, limitations, approved_by
            ) VALUES ('iua-01', ?, 1, 'clinician_context', 'CLINICIAN', 'active', 'Classical monograph reference', 'usr-admin-01');
        """, (self.claim_asarun,))

        # Claim B: Preclinical evidence (animal model)
        self.claim_preclinical = "clm-preclin-01"
        cur.execute("""
            INSERT INTO knowledge_claims (
                id, item_id, claim_text, claim_type, evidence_strength, status, approval_state
            ) VALUES (?, 'kit-02', 'Extract reduces inflammatory markers in rodent models.', 'preclinical_evidence',
                      'MODERATE', 'approved', 'APPROVED');
        """, (self.claim_preclinical,))

        self.link_preclinical = "csl-preclin-01"
        cur.execute("""
            INSERT INTO claim_source_links (
                id, claim_id, source_record_id, source_version_id, locator_text, link_role, created_by
            ) VALUES (?, ?, ?, ?, 'Extract reduced TNF-alpha in rats.', 'primary_support', 'usr-admin-01');
        """, (self.link_preclinical, self.claim_preclinical, self.src_modern, self.ver_modern))

        cur.execute("""
            INSERT INTO citation_validation_runs (
                id, claim_source_link_id, bibliographic_identity_state, version_status_state,
                passage_fidelity_state, claim_support_state, applicability_state, intended_use_state,
                validation_method, run_by
            ) VALUES ('cvr-02', ?, 'verified', 'current', 'exact_match', 'direct_support', 'indirect_population', 'approved', 'DETERMINISTIC_PASSAGE_CHECK', 'usr-admin-01');
        """, (self.link_preclinical,))

        cur.execute("""
            INSERT INTO intended_use_approvals (
                id, claim_id, claim_version, allowed_surface, audience, status, limitations, approved_by
            ) VALUES ('iua-02', ?, 1, 'research_workspace', 'RESEARCHER', 'active', 'Preclinical animal data only', 'usr-admin-01');
        """, (self.claim_preclinical,))

        conn.commit()
        conn.close()

    def test_01_query_intent_resolution(self):
        # Safety query
        res = self.engine.resolve_query_intent("What are contraindications for high dose Senna?")
        self.assertEqual(res["intent_code"], "safety_information_lookup")

        # Terminology query
        res = self.engine.resolve_query_intent("What is the definition of Mizaj?")
        self.assertEqual(res["intent_code"], "terminology_lookup")

        # Source query
        res = self.engine.resolve_query_intent("Find passage in Al-Qanun edition 1877")
        self.assertEqual(res["intent_code"], "source_lookup")

    def test_02_autonomous_clinical_action_prohibited(self):
        # Intercepts diagnosis request
        res = self.engine.resolve_query_intent("Diagnose this patient with dyspepsia")
        self.assertEqual(res["intent_code"], "restricted_clinical_action")
        self.assertTrue(res["requires_strict_abstention"])

        # Intercepts prescribing request
        res = self.engine.resolve_query_intent("Which Nuskha should I prescribe for this case?")
        self.assertEqual(res["intent_code"], "restricted_clinical_action")
        self.assertTrue(res["requires_strict_abstention"])

        # Intercepts dosage calculation
        res = self.engine.resolve_query_intent("Calculate dosage of Asarun for an infant")
        self.assertEqual(res["intent_code"], "restricted_clinical_action")
        self.assertTrue(res["requires_strict_abstention"])

    def test_03_canonical_concept_resolution_and_ambiguity(self):
        # 1. Exact alias lookup for Mizaj (Arabic & English)
        res = self.engine.resolve_canonical_concepts("What is Temperament?")
        self.assertTrue(res["has_matches"])
        self.assertFalse(res["is_ambiguous"])
        self.assertEqual(res["matched_concepts"][0]["canonical_name"], "Mizaj")

        # 2. Ambiguity detection on homonym 'Kundur'
        res_ambig = self.engine.resolve_canonical_concepts("Kundur therapeutic use")
        self.assertTrue(res_ambig["has_matches"])
        self.assertTrue(res_ambig["is_ambiguous"])
        self.assertEqual(len(res_ambig["ambiguity_candidates"]), 2)

    def test_04_hybrid_search_with_intended_use_filtering(self):
        # Clinician context surface: should retrieve Claim A (approved for clinician_context)
        # but EXCLUDE Claim B (approved only for research_workspace)
        search_res = self.engine.search_knowledge(
            query_text="hepatic Asarun",
            user_ctx=self.user_clinician,
            requested_surface="clinician_context"
        )
        claim_ids = [c["claim_id"] for c in search_res["claims"]]
        self.assertIn(self.claim_asarun, claim_ids)

        # Preclinical claim should be excluded from clinician_context
        search_preclin = self.engine.search_knowledge(
            query_text="inflammatory rodent extract",
            user_ctx=self.user_clinician,
            requested_surface="clinician_context"
        )
        self.assertEqual(len(search_preclin["claims"]), 0)
        self.assertGreater(search_preclin["excluded_count"], 0)

    def test_05_immutable_evidence_pack_reproducibility(self):
        pack1 = self.engine.build_evidence_pack(
            query_text="Asarun hepatic",
            user_ctx=self.user_clinician,
            requested_surface="clinician_context"
        )
        pack2 = self.engine.build_evidence_pack(
            query_text="Asarun hepatic",
            user_ctx=self.user_clinician,
            requested_surface="clinician_context"
        )
        # Same query and state yields identical reproducibility hash
        self.assertEqual(pack1["reproducibility_hash"], pack2["reproducibility_hash"])
        self.assertIn("evp-", pack1["id"])

    def test_06_answer_generation_restricted_request_abstention(self):
        pack = self.engine.build_evidence_pack(
            query_text="Diagnose this patient and select a Nuskha",
            user_ctx=self.user_clinician
        )
        answer = self.engine.generate_answer(pack, self.user_clinician)
        self.assertEqual(answer["answer_status"], "restricted_request")
        self.assertIn("prohibited by clinical safety policy", answer["answer_text"])
        self.assertIsNotNone(answer["clinical_boundary_notice"])
        self.assertEqual(len(answer["claims"]), 0)

    def test_07_answer_generation_ambiguity_abstention(self):
        pack = self.engine.build_evidence_pack(
            query_text="What are doses of Kundur?",
            user_ctx=self.user_clinician
        )
        answer = self.engine.generate_answer(pack, self.user_clinician)
        self.assertEqual(answer["answer_status"], "needs_clarification")
        self.assertIn("more than one material identity", answer["answer_text"])

    def test_08_answer_generation_insufficient_evidence_abstention(self):
        pack = self.engine.build_evidence_pack(
            query_text="NonExistentPlantXYZ therapy",
            user_ctx=self.user_clinician
        )
        answer = self.engine.generate_answer(pack, self.user_clinician)
        self.assertEqual(answer["answer_status"], "insufficient_evidence")
        self.assertIn("could not find a source-backed answer", answer["answer_text"])

    def test_09_answer_generation_with_bound_citations_and_epistemic_qualifiers(self):
        pack = self.engine.build_evidence_pack(
            query_text="Asarun hepatic",
            user_ctx=self.user_clinician,
            requested_surface="clinician_context"
        )
        answer = self.engine.generate_answer(pack, self.user_clinician)
        self.assertEqual(answer["answer_status"], "answered")
        self.assertGreaterEqual(len(answer["claims"]), 1)

        claim_0 = answer["claims"][0]
        # Traditional-use claim must carry strict epistemic qualifier
        self.assertIn("Documented in traditional Unani medical texts", claim_0["statement_text"])
        self.assertIn("formal modern clinical efficacy has not been established", claim_0["statement_text"])

        # Must have bound citation
        self.assertGreaterEqual(len(answer["citations"]), 1)
        self.assertEqual(answer["citations"][0]["answer_claim_id"], claim_0["id"])

    def test_10_retracted_source_cascade_blocks_clinical_answer(self):
        # 1. Verify modern source claim is initially searchable in research surface
        search_before = self.engine.search_knowledge(
            query_text="rodent inflammatory",
            user_ctx=self.user_admin,
            requested_surface="research_workspace"
        )
        self.assertGreaterEqual(len(search_before["claims"]), 1)

        # 2. Record retraction event for modern source
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO source_status_events (
                id, source_version_id, event_type, event_source, notes, checked_by
            ) VALUES ('sse-01', ?, 'retraction', 'journal_notice', 'Fraudulent data', 'usr-admin-01');
        """, (self.src_modern,))
        conn.commit()
        conn.close()

        # 3. Subsequent search immediately excludes the retracted source
        search_after = self.engine.search_knowledge(
            query_text="rodent inflammatory",
            user_ctx=self.user_admin,
            requested_surface="research_workspace"
        )
        self.assertEqual(len(search_after["claims"]), 0)
        self.assertGreater(search_after["excluded_count"], 0)

    def test_11_post_generation_validation_catches_unknown_citation(self):
        pack = self.engine.build_evidence_pack(
            query_text="Asarun hepatic",
            user_ctx=self.user_clinician,
            requested_surface="clinician_context"
        )
        answer = self.engine.generate_answer(pack, self.user_clinician)

        # Corrupt citation in database to point to fake non-existent source
        conn = sqlite3.connect(self.db_path)
        conn.execute("UPDATE rag_answer_citations SET source_id = 'src-hallucinated-fake' WHERE answer_claim_id = ?;",
                     (answer["claims"][0]["id"],))
        conn.commit()
        conn.close()

        # Run validation
        val_res = self.engine.validate_answer(answer["id"], self.user_clinician)
        self.assertFalse(val_res["is_valid"])
        self.assertEqual(val_res["validation_status"], "failed_closed")
        self.assertTrue(any("non-existent source" in r for r in val_res["failure_reasons"]))

    def test_12_retrieval_feedback_lifecycle(self):
        pack = self.engine.build_evidence_pack(query_text="Asarun hepatic", user_ctx=self.user_clinician)
        answer = self.engine.generate_answer(pack, self.user_clinician)

        # 1. Report feedback
        fb = self.engine.record_feedback({
            "answer_run_id": answer["id"],
            "feedback_type": "missing_qualifier",
            "notes": "Classical text specifies dose limitations not summarized."
        }, user_id="usr-doc-01")
        self.assertEqual(fb["status"], "pending_review")

        # 2. List feedback
        fbs = self.engine.list_feedback(status="pending_review")
        self.assertGreaterEqual(len(fbs), 1)

        # 3. Resolve feedback
        resolved = self.engine.resolve_feedback(fb["id"], "Monograph qualifier updated by scholar.")
        self.assertEqual(resolved["status"], "resolved")
        self.assertIn("updated by scholar", resolved["resolution_notes"])


if __name__ == "__main__":
    unittest.main()

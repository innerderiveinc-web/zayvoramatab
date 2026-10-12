"""Unit tests for Clinical Knowledge Base & Evidence Retrieval Engine (Prompt 06).
Validates:
- Governed source registry & document hashing
- Provenance tracking (Item -> Claim -> Evidence -> Source)
- Separation of traditional claims from modern RCT clinical trials
- Strict approval state filtering (unapproved excluded from normal search)
- Multilingual and transliteration synonym search (Safra, Balgham, Senna, IBS)
- Evidence synthesis (knowns, unknowns, conflicting evidence, explicit limitations)
- Non-fabrication of citations
"""

import unittest
import sqlite3
import os
import tempfile
import json

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.knowledge import KnowledgeRetrievalEngine
from apps.api.core.errors import NotFoundError, ValidationError, ForbiddenError


class TestKnowledgeRetrievalEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.temp_db_fd)
        run_migrations(cls.temp_db_path)
        seed_development_data(cls.temp_db_path)
        cls.engine = KnowledgeRetrievalEngine(cls.temp_db_path)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_db_path):
            os.remove(cls.temp_db_path)

    def test_sources_registry_provenance_and_hashing(self):
        """Sources must store bibliographic metadata, review state, and SHA-256 integrity hash."""
        src = self.engine.get_source("src-upi-synth")
        self.assertIsNotNone(src)
        self.assertEqual(src["source_type"], "PHARMACOPOEIA")
        self.assertEqual(src["review_status"], "APPROVED")
        self.assertEqual(src["jurisdiction"], "IN")

        # Create new source with content hashing
        new_src = self.engine.register_source({
            "title": "Avicenna Treatise on Cardiac Drugs [Synthetic]",
            "authors_or_org": "Ibn Sina",
            "publisher": "Classical Press",
            "source_type": "CLASSICAL_TEXT",
            "edition": "1st Translation",
            "publication_date": "1030",
            "raw_text_content": "Textual description of Zanjabil as warm carminative.",
            "is_synthetic": True
        }, user_id="usr-admin-1")

        self.assertTrue(new_src["id"].startswith("src-"))
        self.assertIsNotNone(new_src["document_hash"])
        self.assertEqual(len(new_src["document_hash"]), 64)  # SHA-256 hex string

    def test_draft_items_excluded_from_normal_clinical_retrieval(self):
        """Draft and unapproved knowledge items must NEVER be returned by production clinical search."""
        # Create a draft item
        draft_item = self.engine.create_knowledge_item({
            "canonical_name": "Unverified Herbal Extract XYZ [Draft]",
            "domain": "UNANI",
            "entity_type": "SINGLE_DRUG",
            "status": "draft",
            "claim_type": "hypothesis",
            "clinical_scope": "PRIMARY_CARE"
        }, user_id="usr-admin-1")

        # Search with only_approved=True (default production clinical mode)
        results = self.engine.search_knowledge("Unverified Herbal Extract XYZ", only_approved=True)
        self.assertEqual(len(results), 0, "Draft item must not appear in normal approved search.")

        # Search with only_approved=False (admin mode)
        admin_results = self.engine.search_knowledge("Unverified Herbal Extract XYZ", only_approved=False)
        self.assertEqual(len(admin_results), 1)
        self.assertEqual(admin_results[0]["id"], draft_item["id"])

    def test_multilingual_and_transliteration_search(self):
        """Universal search must resolve synonyms and transliterations (e.g. Balgham, Senna, Su-e-Hazm, IBS)."""
        # Test query for 'balgham'
        results = self.engine.search_knowledge("balgham", only_approved=True)
        self.assertTrue(any("Balghami" in r["canonical_name"] for r in results), "Failed to match Balghami via balgham transliteration.")

        # Test query for 'sana makki' matching 'Senna'
        results_senna = self.engine.search_knowledge("sana makki", only_approved=True)
        self.assertTrue(any("Senna" in r["canonical_name"] for r in results_senna), "Failed to match Senna via Sana Makki alias.")

        # Test query for 'ibs' matching Dyspepsia/digestive concepts
        results_ibs = self.engine.search_knowledge("ibs", only_approved=True)
        self.assertTrue(len(results_ibs) > 0, "Failed to match digestive entities via IBS synonym.")

    def test_evidence_synthesis_never_conflates_traditional_with_rct(self):
        """Evidence synthesis must strictly separate classical monograph claims from RCT trial evidence."""
        synthesis = self.engine.synthesize_evidence("ki-senna-synth")
        self.assertEqual(synthesis["canonical_name"], "Senna (Cassia angustifolia / Sana Makki)")
        self.assertIn("epistemological_boundary", synthesis)
        self.assertIn("NOT presented as equivalent to contemporary double-blind randomized clinical trials", synthesis["epistemological_boundary"])

        # Check traditional claims list
        trad = synthesis["traditional_use_evidence"]
        self.assertTrue(len(trad) > 0)
        self.assertTrue(any("Tadbeer" in t["statement"] for t in trad))

        # Check limitations are explicitly preserved
        self.assertTrue(len(synthesis["clinical_limitations"]) > 0)

    def test_clinical_context_retrieval_contract_and_non_prescribing_boundary(self):
        """Clinical context retrieval must return references, safety notes, citations, and non-prescribing disclaimer."""
        context = {
            "symptoms": ["Dyspepsia", "Acute Cough"],
            "mizaj_primary": "Balghami",
            "medicines": ["Senna (Cassia angustifolia / Sana Makki)"],
            "allergies": []
        }
        retrieval = self.engine.retrieve_clinical_context(
            encounter_context=context,
            organization_id="org-synth-1",
            user_role="practitioner"
        )
        self.assertIn("unani_references", retrieval)
        self.assertIn("modern_references", retrieval)
        self.assertIn("safety_precautions", retrieval)
        self.assertIn("citations", retrieval)
        self.assertIn("prescribing_disclaimer", retrieval)
        self.assertIn("Does not constitute autonomous medical advice", retrieval["prescribing_disclaimer"])

        # Check that citations trace back to real seeded sources
        citations = retrieval["citations"]
        self.assertTrue(len(citations) > 0)
        for cit in citations:
            self.assertIn(cit["source_id"], ["src-qanun-synth", "src-upi-synth", "src-nice-dyspepsia-synth", "src-who-cough-synth"])

    def test_governance_review_lifecycle(self):
        """Knowledge review lifecycle: Draft -> Request Changes -> Approve with audit log."""
        item = self.engine.create_knowledge_item({
            "canonical_name": "Khamira Gaozaban Ambari [Synthetic Review Target]",
            "domain": "UNANI",
            "entity_type": "FORMULATION",
            "status": "draft",
            "claim_type": "traditional_use",
            "clinical_scope": "OUTPATIENT"
        }, user_id="usr-hakeem-1")

        item_id = item["id"]

        # 1. Request changes
        req_res = self.engine.request_changes_knowledge_item(
            item_id=item_id,
            reviewer_id="usr-admin-1",
            comments="Please add specific classical citations from Qanun Book V."
        )
        self.assertEqual(req_res["status"], "under_review")

        # 2. Approve
        app_res = self.engine.approve_knowledge_item(
            item_id=item_id,
            reviewer_id="usr-admin-1",
            comments="Citations verified against approved compendium."
        )
        self.assertEqual(app_res["status"], "approved")

        # 3. Check review logs
        logs = self.engine.get_review_logs(item_id)
        self.assertEqual(len(logs), 3)  # SUBMITTED, CHANGES_REQUESTED, APPROVED
        actions = [l["action"] for l in logs]
        self.assertIn("APPROVED", actions)
        self.assertIn("CHANGES_REQUESTED", actions)


if __name__ == "__main__":
    unittest.main()

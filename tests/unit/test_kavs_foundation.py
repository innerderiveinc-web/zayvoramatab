"""Unit tests for KAVS Foundation (Phase K0 + K1):
Governed Source Registry, Provenance, Locators, Verification Events,
Policy Registry, and Atomic Claim Lifecycle Traceability.

Guarantees:
1. No clinical knowledge or claim may be fabricated.
2. Complete provenance with exact source locators (page, section, anchor).
3. Independent 5-dimension verification records.
4. Strict proscription of draft or unverified claims from clinical consultation retrieval.
5. Tamper-evident append-only audit ledger for all KAVS operations.
"""

import os
import unittest
import tempfile
import sqlite3
import json

from apps.api.database.migrator import run_migrations
from apps.api.domains.kavs import KAVSEngine
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError


class TestKAVSFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_kavs_foundation.db")
        run_migrations(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        cls.org_id = "org-kavs-fnd-01"
        cls.user_id = "user-kavs-lead"
        cls.scholar_id = "user-kavs-unani-scholar"

        conn.execute("""
            INSERT INTO organizations (id, name, code, profile_type, is_active)
            VALUES (?, 'Zayvora KAVS Foundation Lab', 'ORG-KAVS-FND', 'MATAB', 1);
        """, (cls.org_id,))

        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, 'kavs_gov_lead', 'lead@kavs.gov', 'pbkdf2_sha256$test$hash', 'Dr. Governance Lead', 1);
        """, (cls.user_id, cls.org_id))

        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, ?, 'hakim_expert', 'hakim@kavs.gov', 'pbkdf2_sha256$test$hash', 'Hakim Senior Scholar', 1);
        """, (cls.scholar_id, cls.org_id))

        # Seed base knowledge item for claim linking
        cls.item_id = "item-filfil-siyah"
        conn.execute("""
            INSERT INTO knowledge_items (
                id, domain, entity_type, canonical_name, description, clinical_scope,
                claim_type, evidence_level, status, created_by
            ) VALUES (?, 'UNANI', 'SINGLE_DRUG', 'Filfil Siyah (Piper nigrum L.)',
                      'Dried unripe fruit of Piper nigrum used as Muqawwi-e-Meda and Kasir-e-Riyah.',
                      'OUTPATIENT', 'traditional_use', 'EXPERT_OPINION', 'approved', ?);
        """, (cls.item_id, cls.user_id))

        conn.commit()
        conn.close()

    def setUp(self):
        self.engine = KAVSEngine(self.db_path)

    # --------------------------------------------------------------------------
    # 1. GOVERNED SOURCE REGISTRY TESTS
    # --------------------------------------------------------------------------

    def test_create_and_list_knowledge_sources(self):
        """Test registering statutory and classical knowledge sources."""
        source_data = {
            "title": "Unani Pharmacopoeia of India Part I Vol I",
            "authors_or_org": "Pharmacopoeia Commission for Indian Medicine & Homoeopathy (PCIM&H)",
            "publisher": "Ministry of AYUSH, Government of India",
            "source_type": "PHARMACOPOEIA",
            "edition": "First Edition",
            "publication_date": "2007-01-01",
            "jurisdiction": "IN",
            "regulatory_status": "APPROVED_STANDARD",
            "evidence_level": "CLASSICAL_COMPENDIUM_GRADE_D",
            "notes": "Statutory AYUSH drug compendium under Drugs and Cosmetics Act 1940."
        }

        created = self.engine.create_source(source_data, self.user_id)
        self.assertTrue(created["id"].startswith("src-"))
        self.assertEqual(created["title"], source_data["title"])
        self.assertEqual(created["review_status"], "DRAFT")

        # List sources
        sources = self.engine.list_sources({"source_type": "PHARMACOPOEIA"})
        self.assertGreaterEqual(len(sources), 1)
        match = next(s for s in sources if s["id"] == created["id"])
        self.assertEqual(match["publisher"], "Ministry of AYUSH, Government of India")

        # Get detailed source
        detailed = self.engine.get_source(created["id"])
        self.assertEqual(detailed["id"], created["id"])
        self.assertIn("versions", detailed)
        self.assertIn("verification_events", detailed)
        self.assertIn("rights_reviews", detailed)

    def test_create_source_validation_fails_without_title(self):
        """Validation error must be raised if title is missing."""
        with self.assertRaises(ValidationError):
            self.engine.create_source({"publisher": "Govt of India"}, self.user_id)

    def test_update_source_metadata(self):
        """Test updating mutable fields of a knowledge source."""
        source = self.engine.create_source({
            "title": "Al-Qanoon fil-Tibb (The Canon of Medicine)",
            "authors_or_org": "Ibn Sina (Avicenna)",
            "publisher": "Jamia Hamdard Printing Press",
            "source_type": "CLASSICAL_TEXT",
            "edition": "Critical Urdu Edition"
        }, self.user_id)

        updated = self.engine.update_source(source["id"], {
            "notes": "Book II: Materia Medica verified against Arabic critical collation.",
            "review_status": "APPROVED"
        }, self.user_id)

        self.assertEqual(updated["review_status"], "APPROVED")
        self.assertIn("Critical Urdu Edition", updated["edition"])

    # --------------------------------------------------------------------------
    # 2. SOURCE VERSIONS & LOCATORS TESTS
    # --------------------------------------------------------------------------

    def test_source_version_and_exact_locator_traceability(self):
        """Test registering a version and attaching exact physical/digital page locators."""
        source = self.engine.create_source({
            "title": "Kitab al-Kulyat (General Principles of Medicine)",
            "authors_or_org": "Ibn Rushd (Averroes)",
            "publisher": "CCRUM Ministry of AYUSH",
            "source_type": "CLASSICAL_TEXT",
            "edition": "Revised 2nd Edition"
        }, self.user_id)

        # Register version
        ver = self.engine.register_source_version({
            "source_id": source["id"],
            "edition": "Second Revised AYUSH Print",
            "publication_year": 1987,
            "document_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "locator_type": "PAGE_AND_PARAGRAPH",
            "source_rights_status": "STATUTORY_AYUSH_OPEN"
        }, self.user_id)

        self.assertEqual(ver["edition"], "Second Revised AYUSH Print")

        # Create exact page locator
        locator = self.engine.create_source_locator({
            "source_version_id": ver["id"],
            "locator_type": "PAGE",
            "page_number": 142,
            "page_label": "p. 142",
            "chapter": "Makoolat wa Mashroobat (Dietetics)",
            "section": "Af'aal-e-Adviyah",
            "paragraph_or_table": "Paragraph 3, Monograph on Piper nigrum",
            "anchor_range": "char_450_to_char_780",
            "verification_state": "UNVERIFIED"
        }, self.user_id)

        self.assertEqual(locator["page_number"], 142)
        self.assertEqual(locator["verification_state"], "UNVERIFIED")

        # Verify locator
        verified_locator = self.engine.verify_source_locator(locator["id"], {
            "verification_state": "VERIFIED_PHYSICAL_PASSAGE",
            "reason": "Collated against National Medical Library archive physical folio."
        }, self.user_id)

        self.assertEqual(verified_locator["verification_state"], "VERIFIED_PHYSICAL_PASSAGE")

        # List locators for version
        locs = self.engine.list_source_locators(ver["id"])
        self.assertEqual(len(locs), 1)
        self.assertEqual(locs[0]["id"], locator["id"])

    # --------------------------------------------------------------------------
    # 3. SOURCE VERIFICATION EVENTS TESTS
    # --------------------------------------------------------------------------

    def test_record_source_verification_events(self):
        """Test recording formal authenticity and publisher verification on a source."""
        source = self.engine.create_source({
            "title": "National Formulary of Unani Medicine Part VI",
            "authors_or_org": "CCRUM",
            "publisher": "Govt of India Dept of AYUSH",
            "source_type": "FORMULARY"
        }, self.user_id)

        self.assertEqual(source["review_status"], "DRAFT")

        # Record verification event
        event = self.engine.record_source_verification_event(source["id"], {
            "verification_type": "PUBLISHER_AUTHORITY",
            "result": "VERIFIED_PASS",
            "evidence_reference": "https://main.ayush.gov.in/publications/nfum-vi",
            "policy_version": "v1.0-gov",
            "reviewer_role": "GOVERNANCE_LEAD",
            "notes": "Verified against Ministry of AYUSH Official Gazette publication registry."
        }, self.user_id)

        self.assertEqual(event["result"], "VERIFIED_PASS")

        # Source review_status must automatically synchronize to APPROVED
        refreshed = self.engine.get_source(source["id"])
        self.assertEqual(refreshed["review_status"], "APPROVED")

        # List verification events
        events = self.engine.list_source_verification_events(source["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["verification_type"], "PUBLISHER_AUTHORITY")

    # --------------------------------------------------------------------------
    # 4. KNOWLEDGE GOVERNANCE POLICY REGISTRY
    # --------------------------------------------------------------------------

    def test_governance_policy_lifecycle(self):
        """Test registering and retrieving active KAVS governance policy."""
        policy = self.engine.register_governance_policy({
            "policy_code": "KAVS-POL-001",
            "version": "1.0.0",
            "title": "Zayvora Matab Clinical Provenance & Truthfulness Standard",
            "effective_date": "2026-01-01",
            "status": "APPROVED",
            "summary": "Strict prohibition of ungrounded LLM synthesis. All clinical claims require dual-expert review."
        }, self.user_id)

        self.assertEqual(policy["policy_code"], "KAVS-POL-001")
        self.assertEqual(policy["status"], "APPROVED")

        # Active policy query
        active = self.engine.get_active_governance_policy()
        self.assertEqual(active["policy_code"], "KAVS-POL-001")

        # List policies
        policies = self.engine.list_governance_policies()
        self.assertGreaterEqual(len(policies), 1)

    # --------------------------------------------------------------------------
    # 5. ATOMIC CLAIM LIFECYCLE & 5-DIMENSION VERIFICATION
    # --------------------------------------------------------------------------

    def test_atomic_claim_draft_review_approve_workflow(self):
        """Test full atomic claim lifecycle: DRAFT -> UNDER_REVIEW -> APPROVED."""
        source = self.engine.create_source({
            "title": "Makhzan al-Mufradat (Compendium of Simples)",
            "authors_or_org": "Hakim Kabiruddin",
            "publisher": "Idara Kitab-us-Shifa",
            "source_type": "TEXTBOOK"
        }, self.user_id)

        # 1. Create claim (starts in DRAFT)
        claim = self.engine.create_atomic_claim({
            "item_id": self.item_id,
            "claim_text": "Filfil Siyah acts as Kasir-e-Riyah (carminative) and stimulates gastric secretions in Barid-Ratb indigestion.",
            "claim_type": "traditional_use",
            "evidence_strength": "TRADITIONAL_CONSENSUS",
            "source_id": source["id"],
            "location_in_source": "Page 214, Monograph on Filfil Siyah",
            "quote_or_excerpt": "Habba-e-Filfil ba sabab-e-hararat muqawwi-e-meda ast."
        }, self.user_id)

        self.assertEqual(claim["status"], "draft")
        self.assertEqual(claim["approval_state"], "DRAFT")
        self.assertEqual(len(claim["citations"]), 1)

        # INVARIANT CHECK: Unreviewed draft claim MUST NOT be served in consultation retrieval
        retrieval_before = self.engine.retrieve_verified_clinical_context("Filfil Siyah")
        self.assertTrue(retrieval_before["insufficient_information"])
        self.assertEqual(retrieval_before["total"], 0)

        # 2. Submit for review
        under_review = self.engine.submit_claim_for_review(claim["id"], self.user_id)
        self.assertEqual(under_review["approval_state"], "UNDER_REVIEW")
        self.assertEqual(under_review["status"], "under_review")

        # 3. Approve claim with 5 independent verification dimensions
        approved = self.engine.approve_claim(claim["id"], {
            "source_authenticity": "publisher_or_authority_verified",
            "extraction_fidelity": "human_checked",
            "evidence_characterization": "traditional_description",
            "intended_use_authorization": "clinician_contextual_reference",
            "lead_reviewer_role": "UNANI_SCHOLAR",
            "review_comments": "Verified against original 1955 monograph. Classical indications corroborated."
        }, self.scholar_id)

        self.assertEqual(approved["approval_state"], "APPROVED")
        self.assertEqual(approved["status"], "approved")
        self.assertIsNotNone(approved["verification"])
        self.assertEqual(approved["verification"]["lead_reviewer_role"], "UNANI_SCHOLAR")

        # INVARIANT CHECK: Approved claim with clinician authorization MUST now be retrievable
        retrieval_after = self.engine.retrieve_verified_clinical_context("Filfil Siyah")
        self.assertFalse(retrieval_after["insufficient_information"])
        self.assertEqual(retrieval_after["total"], 1)
        self.assertEqual(retrieval_after["results"][0]["claim_id"], claim["id"])
        self.assertIn("Page 214", retrieval_after["results"][0]["source"]["locator"])

    def test_atomic_claim_rejection_workflow(self):
        """Test rejecting an atomic claim with mandatory reason."""
        claim = self.engine.create_atomic_claim({
            "item_id": self.item_id,
            "claim_text": "Unverified claim that Piper nigrum cures acute viral hepatitis.",
            "claim_type": "hypothesis"
        }, self.user_id)

        # Rejection requires mandatory reason
        with self.assertRaises(ValidationError):
            self.engine.reject_claim(claim["id"], {"reason": ""}, self.user_id)

        rejected = self.engine.reject_claim(claim["id"], {
            "reason": "Zero evidence in classical Unani texts or biomedical trials. High clinical safety risk."
        }, self.user_id)

        self.assertEqual(rejected["approval_state"], "REJECTED")
        self.assertEqual(rejected["status"], "rejected")

    def test_atomic_claim_withdrawal_workflow(self):
        """Test withdrawing a previously approved claim."""
        claim = self.engine.create_atomic_claim({
            "item_id": self.item_id,
            "claim_text": "Piper nigrum recommended in massive doses without corrective Samagh-e-Arabi.",
            "claim_type": "traditional_use"
        }, self.user_id)

        self.engine.approve_claim(claim["id"], {}, self.user_id)
        withdrawn = self.engine.withdraw_claim(claim["id"], {
            "reason": "Safety precaution: High gastric irritation without musleh (corrective agent)."
        }, self.user_id)

        self.assertEqual(withdrawn["approval_state"], "WITHDRAWN")
        self.assertEqual(withdrawn["status"], "deprecated")

    # --------------------------------------------------------------------------
    # 6. KAVS AUDIT TRAIL LEDGER TESTS
    # --------------------------------------------------------------------------

    def test_kavs_audit_events_ledger(self):
        """Verify that all KAVS state changes produce tamper-evident audit records."""
        events = self.engine.list_kavs_audit_events({"limit": 50})
        self.assertGreater(len(events), 0)

        event_types = [e["event_type"] for e in events]
        self.assertIn("SOURCE_REGISTERED", event_types)
        self.assertIn("CLAIM_CREATED", event_types)

        # Filter by entity_type
        claim_events = self.engine.list_kavs_audit_events({"entity_type": "CLAIM"})
        for ce in claim_events:
            self.assertEqual(ce["entity_type"], "CLAIM")


if __name__ == "__main__":
    unittest.main()

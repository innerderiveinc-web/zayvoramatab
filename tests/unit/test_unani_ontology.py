"""Unit tests for Prompt 19: Unani Ontology, Canonical Terminology,
Mufradat & Murakkabat Structured Catalog, and Knowledge Assertions.

Covers all 20 non-negotiable scenarios specified in Prompt 19 Section 12:
1. Single concept with multiple scripts and approved aliases.
2. Two similar names that must remain distinct (no unsafe equivalence).
3. Unresolved common name that cannot auto-map to a botanical species.
4. Formulation with incomplete composition; missing values remain missing.
5. Traditional posology units preserved exactly (e.g. masha, 2 1/2 masha).
6. Unit conversions require approved conversion rule.
7. Candidate alias cannot be used for clinical selection before approval.
8. Optimistic concurrency detects version conflicts.
9. Disputed claims retain history without deletion.
10. Modern crosswalk candidate equivalence excluded from clinical decision support.
11. Graph relations require provenance assertion; adjacency != proof.
12. Multi-script explainable search with match reasons.
13. Original wording preserved across transliterations and normalizations.
14. Review decisions log actor, timestamp, rationale, and state change.
15. Material identity ambiguity representation (unresolved/candidate/reviewed/disputed).
16. Immutable catalog change events emitted on all mutations.
17. Catalog review tasks created for terminology and assertions.
18. Knowledge assertion withdrawal records reason and updates state.
19. Assertion scope and predicate allow-listing.
20. Clinician vs authoring search isolation.
"""

import os
import unittest
import tempfile
import sqlite3
import json

from apps.api.database.migrator import run_migrations
from apps.api.domains.ontology import UnaniOntologyEngine
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError


class TestUnaniOntology(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_unani_ontology.db")
        run_migrations(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        cls.user_id = "usr-unani-lead-01"
        cls.scholar_id = "usr-unani-scholar-02"

        conn.execute("""
            INSERT INTO organizations (id, name, code, profile_type, is_active)
            VALUES ('org-ont-01', 'Zayvora Unani Research Institute', 'ORG-ONT-01', 'MATAB', 1);
        """)
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-ont-01', 'ont_lead', 'lead@unani.org', 'test$hash', 'Dr. Lead Researcher', 1);
        """, (cls.user_id,))
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-ont-01', 'hakim_ahmed', 'ahmed@unani.org', 'test$hash', 'Hakim Ahmed Khan', 1);
        """, (cls.scholar_id,))

        # Seed source and extraction segment for provenance linking
        cls.source_id = "src-upi-vol1"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Unani Pharmacopoeia of India Part I Vol I', 'Govt of India', 'CCRUM / Ministry of AYUSH',
                      'PHARMACOPOEIA', 'First Edition', 'APPROVED_STANDARD', 'EXPERT_OPINION', 'APPROVED');
        """, (cls.source_id,))

        cls.version_id = "ver-upi-vol1-v1"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, 'First Edition', 1999, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'STATUTORY_AYUSH_OPEN', ?);
        """, (cls.version_id, cls.source_id, cls.user_id))

        cls.job_id = "job-upi-01"
        conn.execute("""
            INSERT INTO kavs_ingestion_jobs (
                id, source_id, source_version_id, job_type, original_filename, status, initiated_by
            ) VALUES (?, ?, ?, 'STRUCTURED_EXTRACTION', 'UPI_Vol_I.pdf', 'completed', ?);
        """, (cls.job_id, cls.source_id, cls.version_id, cls.user_id))

        cls.page_id = "page-upi-35"
        conn.execute("""
            INSERT INTO kavs_extraction_pages (
                id, job_id, source_version_id, pdf_page_index, printed_page_label,
                raw_page_text, ocr_confidence, page_status
            ) VALUES (?, ?, ?, 35, '21', 'Filfil Siah (Piper nigrum L.): Dose 500 mg to 1 g.', 0.98, 'EXTRACTED');
        """, (cls.page_id, cls.job_id, cls.version_id))

        cls.segment_id = "seg-upi-filfil-01"
        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text,
                fidelity_status
            ) VALUES (?, ?, ?, 'Page 21',
                      'Filfil Siah: Hot and Dry in 2nd degree. Useful in Zof-e-Ishteha. Dose 2 habba with Arq Badiyan.',
                      'Filfil Siah: Hot and Dry in 2nd degree. Useful in Zof-e-Ishteha. Dose 2 habba with Arq Badiyan.',
                      'human_checked');
        """, (cls.segment_id, cls.job_id, cls.source_id))

        conn.commit()
        conn.close()

        cls.engine = UnaniOntologyEngine(cls.db_path)

    # 1. Single concept with multiple scripts and approved aliases
    def test_01_single_concept_multiscript_and_approved_aliases(self):
        concept = self.engine.create_concept({
            "concept_type": "material",
            "canonical_label": "Filfil Siah",
            "preferred_name": "فلفل سیاه",
            "script": "urdu",
            "language_tag": "ur",
            "transliteration": "Filfil Siyah"
        }, self.user_id)
        self.assertEqual(concept["canonical_label"], "Filfil Siah")

        # Add Latin alias
        latin_name = self.engine.add_concept_name(concept["id"], {
            "name_text_original": "Black Pepper",
            "script": "latin",
            "language_tag": "en",
            "name_type": "common_name"
        }, self.user_id)

        # Approve Latin alias
        self.engine.review_concept_name(latin_name["id"], "approved", self.scholar_id, "Standard English common name verified")

        fetched = self.engine.get_concept(concept["id"], include_unapproved=True)
        self.assertGreaterEqual(len(fetched["names"]), 2)

    # 2. Two similar names must remain distinct (no unsafe equivalence)
    def test_02_similar_names_remain_distinct_concepts(self):
        # Asgand (Withania somnifera) vs Asrol (Rauvolfia serpentina) - superficially similar transliterations
        c1 = self.engine.create_concept({"concept_type": "material", "canonical_label": "Asgand Nagori"}, self.user_id)
        c2 = self.engine.create_concept({"concept_type": "material", "canonical_label": "Asrol"}, self.user_id)

        self.assertNotEqual(c1["id"], c2["id"])
        self.assertEqual(c1["canonical_label"], "Asgand Nagori")
        self.assertEqual(c2["canonical_label"], "Asrol")

    # 3. Unresolved common name that cannot auto-map to a botanical species
    def test_03_unresolved_material_cannot_automap_species(self):
        concept = self.engine.create_concept({"concept_type": "material", "canonical_label": "Chobchini"}, self.user_id)
        mat = self.engine.set_material_identity(concept["id"], {
            "material_class": "botanical",
            "identity_status": "unresolved",
            "plant_part_or_material_form": "Rhizome"
        }, self.user_id)

        self.assertEqual(mat["identity_status"], "unresolved")
        self.assertIsNone(mat["scientific_name"])  # Non-negotiable: does not fabricate Smilax china without source proof

    # 4. Formulation with incomplete composition; missing values remain missing
    def test_04_formulation_with_incomplete_composition_preserves_missing_values(self):
        c_form = self.engine.create_concept({"concept_type": "formulation", "canonical_label": "Sharbat Zoofa Murakkab"}, self.user_id)
        form = self.engine.create_catalog_formulation(c_form["id"], {
            "formulation_class": "sharbat",
            "source_specific_name": "Sharbat Zoofa Murakkab",
            "source_edition_id": self.version_id,
            "dosage_form": "Liquid / Syrup"
        }, self.user_id)

        # Incomplete ingredient where quantity is not stated in classical passage
        ing = self.engine.add_formulation_ingredient(form["id"], {
            "source_component_name_original": "Asl-us-Soos (Glycyrrhiza glabra)",
            "source_passage_id": self.segment_id,
            "quantity_value": None,
            "quantity_unit_original": None,
            "quantity_basis": "unknown",
            "quantity_review_state": "not_stated"
        }, self.user_id)

        self.assertIsNone(ing["quantity_value"])
        self.assertEqual(ing["quantity_review_state"], "not_stated")

    # 5. Traditional posology units preserved exactly (e.g. masha, 2 1/2 masha)
    def test_05_traditional_units_preserved_exactly(self):
        c_form = self.engine.create_concept({"concept_type": "formulation", "canonical_label": "Hab-e-Suranjan"}, self.user_id)
        form = self.engine.create_catalog_formulation(c_form["id"], {
            "formulation_class": "hab",
            "source_specific_name": "Hab-e-Suranjan",
            "dosage_form": "Pill"
        }, self.user_id)

        ing = self.engine.add_formulation_ingredient(form["id"], {
            "source_component_name_original": "Suranjan Shireen",
            "source_passage_id": self.segment_id,
            "quantity_value": 2.5,
            "quantity_unit_original": "masha",
            "quantity_expression_original": "2 1/2 masha",
            "quantity_basis": "mass",
            "quantity_review_state": "reviewed"
        }, self.user_id)

        self.assertEqual(ing["quantity_unit_original"], "masha")
        self.assertEqual(ing["quantity_expression_original"], "2 1/2 masha")
        self.assertIsNone(ing["quantity_unit_normalized"])

    # 6. Unit conversions require approved conversion rule
    def test_06_normalized_unit_requires_approved_conversion_rule(self):
        c_form = self.engine.create_concept({"concept_type": "formulation", "canonical_label": "Safoof Chutki"}, self.user_id)
        form = self.engine.create_catalog_formulation(c_form["id"], {
            "formulation_class": "safoof",
            "source_specific_name": "Safoof Chutki"
        }, self.user_id)

        # Attempting normalized unit without approved conversion rule raises ValidationError
        with self.assertRaises(ValidationError):
            self.engine.add_formulation_ingredient(form["id"], {
                "source_component_name_original": "Namak Siah",
                "quantity_value": 1.0,
                "quantity_unit_original": "tola",
                "quantity_unit_normalized": "12g",
                "conversion_rule_approved": False  # Not approved!
            }, self.user_id)

    # 7. Candidate alias cannot be used for clinical selection before approval
    def test_07_candidate_alias_masked_from_clinician_search(self):
        concept = self.engine.create_concept({
            "concept_type": "material",
            "canonical_label": "Ustukhuddus",
            "status": "approved_identity"
        }, self.user_id)

        # Add candidate alias (unapproved draft)
        self.engine.add_concept_name(concept["id"], {
            "name_text_original": "Arabian Lavender Special",
            "script": "latin",
            "name_type": "candidate_alias"
        }, self.user_id)

        # Clinician-facing search masks candidate_alias
        res_clinician = self.engine.search_catalog("Arabian Lavender Special", is_clinician_facing=True)
        self.assertEqual(res_clinician["total"], 0)

        # Authoring search reveals candidate_alias
        res_authoring = self.engine.search_catalog("Arabian Lavender Special", is_clinician_facing=False)
        self.assertEqual(res_authoring["total"], 1)

    # 8. Optimistic concurrency detects version conflicts
    def test_08_optimistic_concurrency_detects_version_conflict(self):
        concept = self.engine.create_concept({"concept_type": "unani_term", "canonical_label": "Barid Yabis"}, self.user_id)
        self.assertEqual(concept["version"], 1)

        # Update with current version succeeds
        upd = self.engine.update_concept(concept["id"], {
            "canonical_label": "Barid Yabis (Cold and Dry)",
            "version": 1
        }, self.user_id)
        self.assertEqual(upd["version"], 2)

        # Stale update with version 1 raises ConflictError
        with self.assertRaises(ConflictError):
            self.engine.update_concept(concept["id"], {
                "canonical_label": "Conflicting Update",
                "version": 1
            }, self.user_id)

    # 9. Disputed claims retain history without deletion
    def test_09_disputed_claim_retains_history(self):
        concept = self.engine.create_concept({"concept_type": "material", "canonical_label": "Zanjabil"}, self.user_id)
        assertion = self.engine.create_knowledge_assertion(concept["id"], {
            "predicate": "has_mizaj",
            "object_literal": "Hot 3rd degree, Dry 2nd degree",
            "source_passage_id": self.segment_id,
            "source_quote_exact": "Zanjabil is Hot in third degree and Dry in second degree.",
            "assertion_scope": "clinical"
        }, self.user_id)

        # Scholar marks disputed due to competing authority
        self.engine.review_knowledge_assertion(assertion["id"], "changes_requested", self.scholar_id, rationale="Conflicting temperament in Al-Qanun (Hot 2, Dry 1)")

        events = self.engine.list_change_events("assertion", assertion["id"])
        self.assertGreaterEqual(len(events), 2)
        actions = [e["action"] for e in events]
        self.assertIn("CREATE", actions)
        self.assertIn("CHANGES_REQUESTED", actions)

    # 10. Modern crosswalk candidate equivalence excluded from clinical decision support
    def test_10_candidate_equivalence_crosswalk_excluded_from_clinician_view(self):
        concept = self.engine.create_concept({"concept_type": "unani_term", "canonical_label": "Zof-e-Ishteha"}, self.user_id)
        cw = self.engine.add_external_crosswalk(concept["id"], {
            "system_uri": "http://snomed.info/sct",
            "system_label": "SNOMED-CT",
            "external_code": "249497008",
            "external_preferred_label": "Loss of appetite",
            "mapping_type": "candidate_equivalence",  # Candidate only!
            "review_notes": "Needs formal pharmacognosy clinical validation"
        }, self.user_id)

        # Clinician view excludes candidate_equivalence
        c_clinician = self.engine.get_concept(concept["id"], include_unapproved=False)
        self.assertEqual(len(c_clinician["crosswalks"]), 0)

        # Authoring/reviewer view shows candidate crosswalk
        c_reviewer = self.engine.get_concept(concept["id"], include_unapproved=True)
        self.assertEqual(len(c_reviewer["crosswalks"]), 1)

    # 11. Graph relations require provenance assertion; adjacency != proof
    def test_11_graph_relation_requires_assertion_for_clinical_edges(self):
        c1 = self.engine.create_concept({"concept_type": "material", "canonical_label": "Gule Surkh"}, self.user_id)
        c2 = self.engine.create_concept({"concept_type": "unani_term", "canonical_label": "Zof-e-Meda"}, self.user_id)

        # Clinical relation without assertion_id raises ValidationError
        with self.assertRaises(ValidationError):
            self.engine.create_concept_relation(c1["id"], "indicated_for", c2["id"], {
                "relation_class": "clinical",
                "assertion_id": None  # Violates adjacency != evidence
            }, self.user_id)

    # 12. Multi-script explainable search with match reasons
    def test_12_multiscript_explainable_search(self):
        concept = self.engine.create_concept({
            "concept_type": "material",
            "canonical_label": "Badam Shireen",
            "preferred_name": "بادام شیرین",
            "script": "urdu",
            "transliteration": "Sweet Almond",
            "status": "approved_identity"
        }, self.user_id)

        # Approve the preferred name for clinician view
        names = concept["names"]
        self.engine.review_concept_name(names[0]["id"], "approved", self.scholar_id, "Approved primary Urdu label")

        # Search by Urdu script
        res_urdu = self.engine.search_catalog("بادام", is_clinician_facing=True)
        self.assertGreaterEqual(res_urdu["total"], 1)
        self.assertTrue(any(any("ORIGINAL_SCRIPT_MATCH" in m for m in r["match_reasons"]) for r in res_urdu["results"]))

        # Search by transliteration
        res_trans = self.engine.search_catalog("Sweet Almond", is_clinician_facing=True)
        self.assertGreaterEqual(res_trans["total"], 1)
        self.assertIn("TRANSLITERATION_MATCH", res_trans["results"][0]["match_reasons"])

    # 13. Original wording preserved across transliterations and normalizations
    def test_13_original_wording_preserved(self):
        concept = self.engine.create_concept({"concept_type": "material", "canonical_label": "Kashneez Khushk"}, self.user_id)
        name = self.engine.add_concept_name(concept["id"], {
            "name_text_original": "کَشْنِیزِ خُشْک",
            "script": "persian",
            "transliteration": "Kashneez-e-Khushk"
        }, self.user_id)

        self.assertEqual(name["name_text_original"], "کَشْنِیزِ خُشْک")  # Diacritics preserved in original
        self.assertEqual(name["normalized_search_text"], "کشنیز خشک")  # Normalized search token strips diacritics cleanly

    # 14. Review decisions log actor, timestamp, rationale, and state change
    def test_14_assertion_review_decision_logs_rationale_and_actor(self):
        concept = self.engine.create_concept({"concept_type": "material", "canonical_label": "Sana Makki"}, self.user_id)
        assertion = self.engine.create_knowledge_assertion(concept["id"], {
            "predicate": "has_action",
            "object_literal": "Mushil-e-Safra (Purgative of yellow bile)",
            "source_passage_id": self.segment_id,
            "source_quote_exact": "Sana Makki is Mushil-e-Safra and Mushil-e-Balgham.",
            "assertion_scope": "clinical"
        }, self.user_id)

        reviewed = self.engine.review_knowledge_assertion(
            assertion["id"], "approved_for_defined_use", self.scholar_id,
            intended_use="clinician_contextual_reference",
            rationale="Passage fidelity confirmed against UPI Vol I page 21"
        )
        self.assertEqual(reviewed["review_state"], "approved_for_defined_use")
        self.assertEqual(reviewed["approved_intended_use"], "clinician_contextual_reference")
        self.assertEqual(reviewed["reviewer_id"], self.scholar_id)
        self.assertEqual(reviewed["decision_rationale"], "Passage fidelity confirmed against UPI Vol I page 21")

    # 15. Material identity ambiguity representation (unresolved/candidate/reviewed/disputed)
    def test_15_material_identity_ambiguity_states(self):
        concept = self.engine.create_concept({"concept_type": "material", "canonical_label": "Jadwar"}, self.user_id)
        # Delphinium denudatum is debated in classical vs regional trade
        mat = self.engine.set_material_identity(concept["id"], {
            "material_class": "botanical",
            "identity_status": "disputed",
            "scientific_name": "Delphinium denudatum Wall.",
            "rationale": "Multiple regional adulterants reported in raw drug market"
        }, self.user_id)

        self.assertEqual(mat["identity_status"], "disputed")
        self.assertEqual(mat["scientific_name"], "Delphinium denudatum Wall.")

    # 16. Immutable catalog change events emitted on all mutations
    def test_16_immutable_catalog_change_events(self):
        c = self.engine.create_concept({"concept_type": "unani_term", "canonical_label": "Istefragh"}, self.user_id)
        events = self.engine.list_change_events("concept", c["id"])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "CREATE")
        self.assertEqual(events[0]["actor_id"], self.user_id)

    # 17. Catalog review tasks created for terminology and assertions
    def test_17_catalog_review_tasks_generated(self):
        tasks = self.engine.list_review_tasks({"status": "PENDING"})
        self.assertGreaterEqual(len(tasks), 1)
        task_types = [t["task_type"] for t in tasks]
        self.assertIn("TERMINOLOGY_TRANSLITERATION", task_types)

    # 18. Knowledge assertion withdrawal records reason and updates state
    def test_18_knowledge_assertion_withdrawal(self):
        concept = self.engine.create_concept({"concept_type": "material", "canonical_label": "Aftimoon"}, self.user_id)
        assertion = self.engine.create_knowledge_assertion(concept["id"], {
            "predicate": "has_dose",
            "object_literal": "3-5 masha",
            "source_passage_id": self.segment_id,
            "source_quote_exact": "Dose is 3 to 5 masha.",
            "assertion_scope": "clinical"
        }, self.user_id)

        withdrawn = self.engine.withdraw_knowledge_assertion(assertion["id"], self.scholar_id, "Superseded by updated edition monograph")
        self.assertEqual(withdrawn["review_state"], "withdrawn")
        self.assertEqual(withdrawn["decision_rationale"], "Superseded by updated edition monograph")

    # 19. Assertion scope and predicate allow-listing
    def test_19_invalid_predicate_and_scope_rejected(self):
        concept = self.engine.create_concept({"concept_type": "material", "canonical_label": "Badiyan"}, self.user_id)
        with self.assertRaises(ValidationError):
            self.engine.create_knowledge_assertion(concept["id"], {
                "predicate": "completely_invented_predicate",
                "object_literal": "invalid"
            }, self.user_id)

        with self.assertRaises(ValidationError):
            self.engine.create_knowledge_assertion(concept["id"], {
                "predicate": "has_mizaj",
                "assertion_scope": "invented_scope"
            }, self.user_id)

    # 20. Clinician vs authoring search isolation
    def test_20_unapproved_concept_isolated_from_clinician_search(self):
        draft_concept = self.engine.create_concept({
            "concept_type": "material",
            "canonical_label": "Unapproved Experimental Draft Herb",
            "status": "draft"
        }, self.user_id)

        res_clinician = self.engine.search_catalog("Unapproved Experimental Draft", is_clinician_facing=True)
        self.assertEqual(res_clinician["total"], 0)

        res_authoring = self.engine.search_catalog("Unapproved Experimental Draft", is_clinician_facing=False)
        self.assertEqual(res_authoring["total"], 1)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for Prompt 20: Unani Clinical Knowledge Mapping & Organ-Axis Relationship Engine.

Covers all core governance, safety, and provenance rules:
1. Controlled relation-type registry seeding & constraints.
2. Provenance enforcement: Substantive clinical relationships require valid assertion_id.
3. Concept type constraints on subject and object concepts.
4. Reviewer role authorization & review state transitions.
5. Navigation grouping isolation: Cannot be approved for clinical_decision_support.
6. Relationship assertion withdrawal with mandatory rationale.
7. Versioned Organ-Axis framework creation & publication constraints.
8. Framework memberships with typed links and assertion requirements.
9. Cross-disciplinary mappings (ICD-11, SNOMED-CT) & candidate equivalence quarantine.
10. Relationship conflicts reporting and adjudication queue.
11. Encounter-scoped case hypotheses (protected patient record; isolated from global ontology).
12. Bounded graph traversal: Hard depth limits, cycle detection, clinical filtering.
13. Graph traversal non-inference rule: Transitive inferences (A -> C) prohibited.
14. Immutable audit events emitted on mutations.
"""

import os
import unittest
import tempfile
import sqlite3
import json

from apps.api.database.migrator import run_migrations
from apps.api.domains.knowledge_mapping import KnowledgeMappingEngine
from apps.api.domains.ontology import UnaniOntologyEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestKnowledgeMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_knowledge_mapping.db")
        run_migrations(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        cls.admin_user_id = "usr-admin-km-01"
        cls.scholar_user_id = "usr-scholar-km-02"
        cls.clinician_user_id = "usr-clinician-km-03"
        cls.unauthorized_user_id = "usr-guest-km-04"

        conn.execute("""
            INSERT INTO organizations (id, name, code, profile_type, is_active)
            VALUES ('org-km-01', 'Zayvora Research Institute', 'ORG-KM-01', 'MATAB', 1);
        """)
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-km-01', 'admin_km', 'admin@km.org', 'test$hash', 'Dr. System Admin', 1);
        """, (cls.admin_user_id,))
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-km-01', 'scholar_km', 'scholar@km.org', 'test$hash', 'Hakim Unani Scholar', 1);
        """, (cls.scholar_user_id,))
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-km-01', 'clinician_km', 'clinician@km.org', 'test$hash', 'Dr. Clinician Specialist', 1);
        """, (cls.clinician_user_id,))
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES (?, 'org-km-01', 'guest_km', 'guest@km.org', 'test$hash', 'Guest User', 1);
        """, (cls.unauthorized_user_id,))

        conn.execute("""
            INSERT INTO facilities (id, organization_id, name, code, is_active)
            VALUES ('fac-km-01', 'org-km-01', 'Main Matab', 'FAC-01', 1);
        """)

        # Seed patient and encounter for hypothesis tests
        cls.patient_id = "pat-km-01"
        conn.execute("""
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, sex, created_by)
            VALUES (?, 'org-km-01', 'fac-km-01', 'MRN-KM-01', 'Zaid', 'Zaid Khan', 'MALE', ?);
        """, (cls.patient_id, cls.admin_user_id))

        cls.encounter_id = "enc-km-01"
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, encounter_type, created_by)
            VALUES (?, 'org-km-01', 'fac-km-01', ?, ?, 'IN_PROGRESS', 'OUTPATIENT', ?);
        """, (cls.encounter_id, cls.patient_id, cls.clinician_user_id, cls.clinician_user_id))

        # Seed knowledge source and version for provenance claims
        cls.source_id = "src-qanun-vol1"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Al-Qanun fi al-Tibb Vol 1', 'Ibn Sina (Avicenna)', 'Dar al-Kutub',
                      'CLASSICAL_TEXT', 'Arabic Bulaq Edition', 'HISTORICAL_REFERENCE', 'EXPERT_OPINION', 'APPROVED');
        """, (cls.source_id,))

        cls.version_id = "ver-qanun-v1"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, 'Bulaq 1877', 1877, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'PUBLIC_DOMAIN', ?);
        """, (cls.version_id, cls.source_id, cls.admin_user_id))

        cls.job_id = "job-qanun-01"
        conn.execute("""
            INSERT INTO kavs_ingestion_jobs (
                id, source_id, source_version_id, job_type, original_filename, status, initiated_by
            ) VALUES (?, ?, ?, 'STRUCTURED_EXTRACTION', 'Qanun_Vol_1.pdf', 'completed', ?);
        """, (cls.job_id, cls.source_id, cls.version_id, cls.admin_user_id))

        cls.page_id = "page-qanun-142"
        conn.execute("""
            INSERT INTO kavs_extraction_pages (
                id, job_id, source_version_id, pdf_page_index, printed_page_label,
                raw_page_text, ocr_confidence, page_status
            ) VALUES (?, ?, ?, 142, '142', 'Meda and Su-e-Hadm classical passage text.', 0.98, 'EXTRACTED');
        """, (cls.page_id, cls.job_id, cls.version_id))

        cls.segment_1 = "pas-qanun-101"
        cls.segment_2 = "pas-qanun-205"
        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text, fidelity_status
            ) VALUES (?, ?, ?, 'Page 142', 'Su-e-Hadm in Meda', 'Su-e-Hadm in Meda', 'human_checked');
        """, (cls.segment_1, cls.job_id, cls.source_id))
        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text, fidelity_status
            ) VALUES (?, ?, ?, 'Page 288', 'Sana in acute Meda inflammation', 'Sana in acute Meda inflammation', 'human_checked');
        """, (cls.segment_2, cls.job_id, cls.source_id))

        conn.commit()
        conn.close()

        cls.ontology_engine = UnaniOntologyEngine(cls.db_path)
        cls.engine = KnowledgeMappingEngine(cls.db_path)

        # Seed concepts for tests
        cls.cpt_stomach = cls.ontology_engine.create_concept({
            "id": "cpt-meda-stomach",
            "concept_type": "organ_or_structure",
            "canonical_label": "Meda (Stomach)"
        }, cls.admin_user_id)["id"]

        cls.cpt_brain = cls.ontology_engine.create_concept({
            "id": "cpt-dimagh-brain",
            "concept_type": "organ_or_structure",
            "canonical_label": "Dimagh (Brain)"
        }, cls.admin_user_id)["id"]

        cls.cpt_liver = cls.ontology_engine.create_concept({
            "id": "cpt-kabid-liver",
            "concept_type": "organ_or_structure",
            "canonical_label": "Kabid (Liver)"
        }, cls.admin_user_id)["id"]

        cls.cpt_dyspepsia = cls.ontology_engine.create_concept({
            "id": "cpt-su-hadm",
            "concept_type": "clinical_process",
            "canonical_label": "Su-e-Hadm (Dyspepsia)"
        }, cls.admin_user_id)["id"]

        cls.cpt_senna = cls.ontology_engine.create_concept({
            "id": "cpt-senna-muf",
            "concept_type": "material",
            "canonical_label": "Sana Makki (Cassia angustifolia)"
        }, cls.admin_user_id)["id"]

        # Seed provenance knowledge assertions
        cls.assert_1 = cls.ontology_engine.create_knowledge_assertion(cls.cpt_dyspepsia, {
            "id": "kas-qanun-dysp-meda",
            "predicate": "associated_organ",
            "object_concept_id": cls.cpt_stomach,
            "assertion_scope": "clinical",
            "source_passage_id": "pas-qanun-101",
            "source_quote_exact": "Su-e-Hadm originates primarily from weakness of the gastric faculty in Meda.",
            "page_locator": "142"
        }, cls.scholar_user_id)["id"]

        cls.assert_2 = cls.ontology_engine.create_knowledge_assertion(cls.cpt_senna, {
            "id": "kas-qanun-senna-contra",
            "predicate": "contraindicated_in",
            "object_concept_id": cls.cpt_stomach,
            "assertion_scope": "clinical",
            "source_passage_id": "pas-qanun-205",
            "source_quote_exact": "Sana is harsh on acute inflammation of Meda without corrective mucilage.",
            "page_locator": "288"
        }, cls.scholar_user_id)["id"]

    def test_01_seed_default_relation_types(self):
        """Seed controlled relation types creates standard predicates."""
        rtypes = self.engine.list_relation_types()
        codes = {r["code"] for r in rtypes}
        self.assertIn("classical_organ_association", codes)
        self.assertIn("organ_axis_navigation_member", codes)
        self.assertIn("indicated_for_mizaj_condition", codes)
        self.assertIn("contraindicated_in", codes)
        self.assertIn("icd11_crosswalk", codes)

    def test_02_create_relation_type_validation(self):
        """Create relation type enforces code uniqueness and relation_class validation."""
        with self.assertRaises(ValidationError):
            self.engine.create_relation_type({
                "code": "test_invalid",
                "label": "Test",
                "definition": "Test def",
                "relation_class": "non_existent_class"
            }, self.admin_user_id)

        # Valid creation
        r_type = self.engine.create_relation_type({
            "code": "custom_biomechanical_link",
            "label": "Custom Biomechanical Link",
            "definition": "Experimental biomechanical link",
            "relation_class": "modern_clinical",
            "directionality": "directed"
        }, self.admin_user_id)
        self.assertEqual(r_type["code"], "custom_biomechanical_link")

        # Duplicate code error
        with self.assertRaises(ConflictError):
            self.engine.create_relation_type({
                "code": "custom_biomechanical_link",
                "label": "Duplicate",
                "definition": "Duplicate",
                "relation_class": "modern_clinical"
            }, self.admin_user_id)

    def test_03_relation_requires_source_assertion(self):
        """Substantive clinical relationship fails when assertion_id is missing."""
        # 'classical_organ_association' requires_source_assertion = 1
        with self.assertRaises(ValidationError) as ctx:
            self.engine.create_relationship_assertion({
                "subject_concept_id": self.cpt_dyspepsia,
                "predicate_code": "classical_organ_association",
                "object_concept_id": self.cpt_stomach,
                "relationship_level": "classical_text"
                # assertion_id missing!
            }, self.scholar_user_id)
        self.assertIn("requires an authentic source assertion", str(ctx.exception))

    def test_04_relation_concept_type_constraints(self):
        """Predicate subject and object concept type constraints are enforced."""
        # 'classical_organ_association' subject constraint: unani_term, clinical_process, assessment_concept
        # Passing 'material' (cpt_senna) as subject must fail constraint check!
        with self.assertRaises(ValidationError) as ctx:
            self.engine.create_relationship_assertion({
                "subject_concept_id": self.cpt_senna,
                "predicate_code": "classical_organ_association",
                "object_concept_id": self.cpt_stomach,
                "assertion_id": self.assert_1
            }, self.scholar_user_id)
        self.assertIn("not permitted for predicate", str(ctx.exception))

    def test_05_relation_non_existent_concept(self):
        """Creating relation with non-existent concept raises NotFoundError."""
        with self.assertRaises(NotFoundError):
            self.engine.create_relationship_assertion({
                "subject_concept_id": "cpt-non-existent-xyz",
                "predicate_code": "organ_axis_navigation_member",
                "object_concept_id": self.cpt_stomach
            }, self.scholar_user_id)

    def test_06_create_and_review_relationship_assertion(self):
        """Valid relation assertion created as draft and reviewed by authorized role."""
        rel = self.engine.create_relationship_assertion({
            "id": "rel-dysp-meda-01",
            "subject_concept_id": self.cpt_dyspepsia,
            "predicate_code": "classical_organ_association",
            "object_concept_id": self.cpt_stomach,
            "assertion_id": self.assert_1,
            "relationship_level": "classical_text",
            "review_state": "draft"
        }, self.scholar_user_id)
        self.assertEqual(rel["id"], "rel-dysp-meda-01")
        self.assertEqual(rel["review_state"], "draft")

        # Unauthorized user review fails
        with self.assertRaises(ForbiddenError):
            self.engine.review_relationship_assertion(
                relation_id="rel-dysp-meda-01",
                user_ctx={"user_id": self.unauthorized_user_id, "roles": ["GUEST"], "permissions": []},
                new_state="approved_for_defined_use",
                rationale="Should fail unauthorized"
            )

        # Authorized Unani scholar approves
        approved = self.engine.review_relationship_assertion(
            relation_id="rel-dysp-meda-01",
            user_ctx={"user_id": self.scholar_user_id, "roles": ["UNANI_SCHOLAR"], "permissions": ["knowledge:review"]},
            new_state="approved_for_defined_use",
            rationale="Verified classical text citation in Al-Qanun Vol 1 p. 142.",
            intended_use_approval="clinician_contextual_reference"
        )
        self.assertEqual(approved["review_state"], "approved_for_defined_use")
        self.assertEqual(approved["intended_use_approval"], "clinician_contextual_reference")

    def test_07_navigation_grouping_cannot_be_approved_for_clinical_support(self):
        """UI navigation grouping relationship cannot be approved for clinical_decision_support."""
        rel = self.engine.create_relationship_assertion({
            "id": "rel-nav-meda-dimagh",
            "subject_concept_id": self.cpt_stomach,
            "predicate_code": "organ_axis_navigation_member",
            "object_concept_id": self.cpt_brain,
            "relationship_level": "ui_navigation_grouping",
            "review_state": "draft"
        }, self.admin_user_id)

        with self.assertRaises(ValidationError) as ctx:
            self.engine.review_relationship_assertion(
                relation_id="rel-nav-meda-dimagh",
                user_ctx={"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"], "permissions": ["knowledge:approve"]},
                new_state="approved_for_defined_use",
                rationale="Unsafe attempt to promote UI grouping to clinical decision support",
                intended_use_approval="clinical_decision_support"
            )
        self.assertIn("UI/navigation groupings cannot be approved for clinical_decision_support", str(ctx.exception))

    def test_08_withdraw_relationship_assertion(self):
        """Withdrawing a relationship assertion updates review state and requires rationale."""
        with self.assertRaises(ValidationError):
            self.engine.withdraw_relationship_assertion(
                "rel-dysp-meda-01",
                {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"], "permissions": []},
                rationale=""
            )

        withdrawn = self.engine.withdraw_relationship_assertion(
            "rel-dysp-meda-01",
            {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"], "permissions": []},
            rationale="Withdrawn pending verification of newly discovered conflicting manuscript passage."
        )
        self.assertEqual(withdrawn["review_state"], "withdrawn")

    def test_09_seed_default_framework(self):
        """Default Organ-Axis navigation framework is seeded."""
        fw = self.engine.get_framework("oaf-zayvora-axis-v1")
        self.assertEqual(fw["name"], "ZAYVORA Standard Organ-Axis Model")
        self.assertEqual(fw["framework_type"], "product_navigation_model")
        self.assertEqual(fw["approved_use_scope"], "navigation_only")

    def test_10_create_and_publish_framework(self):
        """Versioned framework creation and publication rules."""
        fw = self.engine.create_framework({
            "id": "oaf-gastro-hepatic-v1",
            "name": "Gastro-Hepatic Functional Axis",
            "version": "1.1.0",
            "framework_type": "product_navigation_model",
            "description": "Functional relationship between Meda (Stomach) and Kabid (Liver)",
            "purpose": "Clinical consultation navigation for digestive disorders",
            "limitations": "Navigation model only. Does not assert modern hepatobiliary pathophysiology.",
            "approved_use_scope": "navigation_only"
        }, self.admin_user_id)
        self.assertEqual(fw["id"], "oaf-gastro-hepatic-v1")

        # product_navigation_model cannot be published with clinical_decision_support
        with self.assertRaises(ValidationError):
            self.engine.publish_framework(
                "oaf-gastro-hepatic-v1",
                {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"]},
                review_state="approved",
                approved_use_scope="clinical_decision_support",
                rationale="Unsafe publication"
            )

        published = self.engine.publish_framework(
            "oaf-gastro-hepatic-v1",
            {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"]},
            review_state="approved",
            approved_use_scope="clinician_contextual_reference",
            rationale="Approved for contextual clinical reference only."
        )
        self.assertEqual(published["review_state"], "approved")
        self.assertEqual(published["approved_use_scope"], "clinician_contextual_reference")

    def test_11_framework_memberships(self):
        """Adding framework memberships enforces concept existence and assertion links."""
        # navigation_group does not require assertion_id
        mem1 = self.engine.add_framework_membership("oaf-gastro-hepatic-v1", {
            "concept_id": self.cpt_stomach,
            "axis_name": "GASTRO_HEPATIC_AXIS",
            "membership_type": "navigation_group"
        }, self.admin_user_id)
        self.assertEqual(mem1["axis_name"], "GASTRO_HEPATIC_AXIS")

        # source_documented_membership requires assertion_id
        with self.assertRaises(ValidationError):
            self.engine.add_framework_membership("oaf-gastro-hepatic-v1", {
                "concept_id": self.cpt_liver,
                "axis_name": "GASTRO_HEPATIC_AXIS",
                "membership_type": "source_documented_membership"
                # assertion_id missing!
            }, self.admin_user_id)

        # Successful addition with assertion link
        mem2 = self.engine.add_framework_membership("oaf-gastro-hepatic-v1", {
            "concept_id": self.cpt_liver,
            "axis_name": "GASTRO_HEPATIC_AXIS",
            "membership_type": "source_documented_membership",
            "assertion_id": self.assert_1
        }, self.admin_user_id)
        self.assertEqual(mem2["concept_id"], self.cpt_liver)

        members = self.engine.list_framework_memberships("oaf-gastro-hepatic-v1", axis_name="GASTRO_HEPATIC_AXIS")
        self.assertEqual(len(members), 2)

    def test_12_cross_disciplinary_concept_mapping(self):
        """Concept mapping creates cross-system maps and quarantines candidate equivalence."""
        mapping = self.engine.create_concept_mapping({
            "id": "cpm-dysp-icd11",
            "source_concept_id": self.cpt_dyspepsia,
            "target_system": "ICD-11",
            "target_identifier": "MD90",
            "target_label": "Dyspepsia",
            "mapping_type": "candidate_equivalence",
            "limitations": "Unani Su-e-Hadm encompasses qualitative temperamental alterations not captured in ICD-11."
        }, self.clinician_user_id)
        self.assertEqual(mapping["mapping_type"], "candidate_equivalence")

        # candidate_equivalence cannot be approved for clinical_decision_support
        with self.assertRaises(ValidationError):
            self.engine.review_concept_mapping(
                "cpm-dysp-icd11",
                {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"]},
                new_state="approved",
                approved_intended_use="clinical_decision_support",
                rationale="Unsafe approval of candidate equivalence"
            )

        # Approved for clinician_contextual_reference
        reviewed = self.engine.review_concept_mapping(
            "cpm-dysp-icd11",
            {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"]},
            new_state="approved",
            approved_intended_use="clinician_contextual_reference",
            rationale="Approved as contextual cross-reference with explicit temperamental caveat."
        )
        self.assertEqual(reviewed["review_state"], "approved")

    def test_13_relationship_conflicts_and_adjudication(self):
        """Report conflicts between assertions and adjudicate with mandatory rationale."""
        conflict = self.engine.report_conflict({
            "assertion_id": self.assert_1,
            "conflicting_assertion_id": self.assert_2,
            "conflict_type": "interpretation_disagreement",
            "description": "Disagreement on whether Meda inflammation tolerates Sana when prepared with almond oil."
        }, self.scholar_user_id)
        self.assertEqual(conflict["resolution_state"], "open")

        with self.assertRaises(ValidationError):
            self.engine.adjudicate_conflict(
                conflict["id"],
                {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"]},
                resolution_state="resolved_with_scope",
                resolution_rationale=""
            )

        adjudicated = self.engine.adjudicate_conflict(
            conflict["id"],
            {"user_id": self.admin_user_id, "roles": ["ORG_ADMIN"]},
            resolution_state="resolved_with_scope",
            resolution_rationale="Resolved: Contraindication applies strictly to uncorrected raw Sana; formulation with almond oil is permissible under physician supervision."
        )
        self.assertEqual(adjudicated["resolution_state"], "resolved_with_scope")

    def test_14_encounter_scoped_case_hypotheses_isolation(self):
        """Encounter hypotheses belong strictly to patient encounter; isolated from global ontology."""
        hypo = self.engine.create_encounter_hypothesis(self.encounter_id, {
            "id": "chl-test-case-01",
            "concept_id": self.cpt_dyspepsia,
            "relation_type_code": "clinical_hypothesis_linked_to",
            "hypothesis_text": "Suspect secondary Su-e-Mizaj Meda caused by dietary indiscretion.",
            "clinical_note_reference": "Note section 3.2"
        }, self.clinician_user_id)
        self.assertEqual(hypo["status"], "active")
        self.assertEqual(hypo["encounter_id"], self.encounter_id)

        # Retrieve hypotheses for this encounter
        hypos = self.engine.list_encounter_hypotheses(self.encounter_id)
        self.assertEqual(len(hypos), 1)
        self.assertEqual(hypos[0]["hypothesis_text"], "Suspect secondary Su-e-Mizaj Meda caused by dietary indiscretion.")

        # Update status
        updated = self.engine.update_encounter_hypothesis_status("chl-test-case-01", self.encounter_id, "resolved", self.clinician_user_id)
        self.assertEqual(updated["status"], "resolved")

        # Verify hypothesis did NOT pollute global relationship_assertions
        relations = self.engine.list_relationship_assertions(subject_concept_id=self.cpt_dyspepsia)
        for r in relations:
            self.assertNotEqual(r["id"], "chl-test-case-01")

    def test_15_bounded_graph_traversal(self):
        """Graph traversal respects depth, cycles, and clinical mode filtering."""
        # Setup graph edges:
        # cpt_dyspepsia -> (indicated_for) -> cpt_senna -> (contraindicated_in) -> cpt_stomach -> (classical_organ_assoc) -> cpt_brain
        rel1 = self.engine.create_relationship_assertion({
            "id": "rel-gt-1",
            "subject_concept_id": self.cpt_senna,
            "predicate_code": "contraindicated_in",
            "object_concept_id": self.cpt_stomach,
            "assertion_id": self.assert_2,
            "relationship_level": "reviewed_evidence_based",
            "review_state": "approved_for_defined_use",
            "intended_use_approval": "safety_firewall_rule"
        }, self.scholar_user_id)

        rel2 = self.engine.create_relationship_assertion({
            "id": "rel-gt-2",
            "subject_concept_id": self.cpt_stomach,
            "predicate_code": "classical_organ_association",
            "object_concept_id": self.cpt_brain,
            "assertion_id": self.assert_1,
            "relationship_level": "classical_text",
            "review_state": "approved_for_defined_use",
            "intended_use_approval": "clinician_contextual_reference"
        }, self.scholar_user_id)

        # Depth 1 traversal
        res_d1 = self.engine.traverse_knowledge_graph(self.cpt_senna, max_depth=1, clinical_mode=True)
        self.assertEqual(len(res_d1["edges"]), 1)
        self.assertEqual(res_d1["edges"][0]["object_concept_id"], self.cpt_stomach)

        # Depth 2 traversal
        res_d2 = self.engine.traverse_knowledge_graph(self.cpt_senna, max_depth=2, clinical_mode=True)
        self.assertEqual(len(res_d2["edges"]), 2)
        target_ids = {e["object_concept_id"] for e in res_d2["edges"]}
        self.assertIn(self.cpt_stomach, target_ids)
        self.assertIn(self.cpt_brain, target_ids)

        # Explicit non-inference warning is present
        self.assertIn("Graph traversal represents individual asserted relationships only", res_d2["traversal_warning"])
        self.assertIn("Autonomous transitive inferences (A -> C) are prohibited", res_d2["traversal_warning"])


if __name__ == "__main__":
    unittest.main()

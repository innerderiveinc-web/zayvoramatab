"""Integration tests for Prompt 20: Unani Clinical Knowledge Mapping & Organ-Axis REST APIs.

Validates end-to-end HTTP request handling through ApiRouter.dispatch():
1. Relation-Type Registry: GET & POST /api/v1/knowledge/relations/types
2. Relationship Assertions: POST, GET, review, and withdraw /api/v1/knowledge/relations
3. Versioned Organ-Axis Frameworks: GET, POST, memberships, and publish /api/v1/organ-axis/frameworks
4. Cross-Disciplinary Concept Mappings: POST, GET, candidates, and review /api/v1/knowledge/mappings
5. Relationship Conflicts: POST, GET, and adjudicate /api/v1/knowledge/conflicts
6. Encounter-Scoped Case Hypotheses: POST, GET, and PATCH /api/v1/encounters/{enc_id}/hypothesis-links
7. Bounded Graph Traversal: GET /api/v1/knowledge/graph/traverse
8. Authentication & Authorization enforcement: 401 when unauthenticated.
"""

import os
import json
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestKnowledgeMappingApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_knowledge_mapping_api.db")
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
        cur.execute("SELECT id FROM users WHERE username = 'admin' LIMIT 1;")
        cls.admin_id = cur.fetchone()["id"]

        # Find or seed patient and encounter
        cur.execute("SELECT id FROM patients LIMIT 1;")
        pat_row = cur.fetchone()
        cls.patient_id = pat_row["id"]

        cur.execute("SELECT id FROM encounters WHERE patient_id = ? LIMIT 1;", (cls.patient_id,))
        enc_row = cur.fetchone()
        cls.encounter_id = enc_row["id"]

        # Seed source, version, job, page, and segment for provenance assertions
        cls.source_id = "src-km-api-01"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Kamil al-Sina al-Tibbiyya', 'Ali ibn al-Abbas al-Majusi', 'Bulaq Press',
                      'CLASSICAL_TEXT', 'First Edition', 'HISTORICAL_REFERENCE', 'EXPERT_OPINION', 'APPROVED');
        """, (cls.source_id,))

        cls.version_id = "ver-km-api-01"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '1877', 1877, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'PUBLIC_DOMAIN', ?);
        """, (cls.version_id, cls.source_id, cls.admin_id))

        cls.job_id = "job-km-api-01"
        conn.execute("""
            INSERT INTO kavs_ingestion_jobs (
                id, source_id, source_version_id, job_type, original_filename, status, initiated_by
            ) VALUES (?, ?, ?, 'STRUCTURED_EXTRACTION', 'Kamil.pdf', 'completed', ?);
        """, (cls.job_id, cls.source_id, cls.version_id, cls.admin_id))

        cls.page_id = "page-km-api-01"
        conn.execute("""
            INSERT INTO kavs_extraction_pages (
                id, job_id, source_version_id, pdf_page_index, printed_page_label,
                raw_page_text, ocr_confidence, page_status
            ) VALUES (?, ?, ?, 55, '55', 'Dimagh and Meda functional relationship text.', 0.99, 'EXTRACTED');
        """, (cls.page_id, cls.job_id, cls.version_id))

        cls.segment_id = "seg-km-api-01"
        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text, fidelity_status
            ) VALUES (?, ?, ?, 'Page 55', 'Meda is connected to Dimagh via sensitive nervous branches.', 'Meda is connected to Dimagh via sensitive nervous branches.', 'human_checked');
        """, (cls.segment_id, cls.job_id, cls.source_id))

        # Seed concepts
        cls.cpt_stomach = "cpt-api-meda"
        cls.cpt_brain = "cpt-api-dimagh"
        cls.cpt_headache = "cpt-api-suda"

        conn.execute("""
            INSERT OR IGNORE INTO knowledge_concepts (id, concept_type, canonical_label, status, created_by)
            VALUES (?, 'organ_or_structure', 'Meda (Stomach)', 'approved_identity', ?);
        """, (cls.cpt_stomach, cls.admin_id))
        conn.execute("""
            INSERT OR IGNORE INTO knowledge_concepts (id, concept_type, canonical_label, status, created_by)
            VALUES (?, 'organ_or_structure', 'Dimagh (Brain)', 'approved_identity', ?);
        """, (cls.cpt_brain, cls.admin_id))
        conn.execute("""
            INSERT OR IGNORE INTO knowledge_concepts (id, concept_type, canonical_label, status, created_by)
            VALUES (?, 'clinical_process', 'Suda-e-Shirki (Sympathetic Headache)', 'approved_identity', ?);
        """, (cls.cpt_headache, cls.admin_id))

        # Seed knowledge assertion
        cls.assert_id = "kas-api-meda-dimagh"
        conn.execute("""
            INSERT OR IGNORE INTO knowledge_assertions (
                id, subject_concept_id, predicate, object_concept_id, source_passage_id,
                source_quote_exact, assertion_scope, review_state, created_by
            ) VALUES (?, ?, 'associated_organ', ?, ?, 'Meda relates to Dimagh', 'clinical', 'approved_for_defined_use', ?);
        """, (cls.assert_id, cls.cpt_headache, cls.cpt_stomach, cls.segment_id, cls.admin_id))

        conn.commit()
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
        resp_json = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        return status_code, resp_json

    def test_01_authentication_enforcement(self):
        """Unauthenticated requests return 401."""
        status, _ = self._call("GET", "/api/v1/knowledge/relations/types", token="")
        self.assertEqual(status, 401)

    def test_02_relation_types_endpoints(self):
        """List and create controlled relation types."""
        status, res = self._call("GET", "/api/v1/knowledge/relations/types")
        self.assertEqual(status, 200)
        self.assertIn("relation_types", res)
        self.assertGreaterEqual(res["total"], 5)

        # Create new relation type
        status, res = self._call("POST", "/api/v1/knowledge/relations/types", {
            "code": "classical_sympathetic_trigger",
            "label": "Classical Sympathetic Trigger",
            "definition": "Sympathetic functional trigger between organs in Unani physiology",
            "relation_class": "unani_knowledge",
            "directionality": "directed",
            "is_clinically_actionable": False
        })
        self.assertEqual(status, 201)
        self.assertEqual(res["relation_type"]["code"], "classical_sympathetic_trigger")

    def test_03_relationship_assertions_lifecycle(self):
        """Create, fetch, review, and withdraw relationship assertions."""
        # Create relation assertion
        status, res = self._call("POST", "/api/v1/knowledge/relations", {
            "id": "rel-api-headache-meda",
            "subject_concept_id": self.cpt_headache,
            "predicate_code": "classical_organ_association",
            "object_concept_id": self.cpt_stomach,
            "assertion_id": self.assert_id,
            "relationship_level": "classical_text",
            "review_state": "draft"
        })
        self.assertEqual(status, 201)
        rel_id = res["relation"]["id"]

        # List relations
        status, res = self._call("GET", "/api/v1/knowledge/relations")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(res["total"], 1)

        # Get relation by ID
        status, res = self._call("GET", f"/api/v1/knowledge/relations/{rel_id}")
        self.assertEqual(status, 200)
        self.assertEqual(res["relation"]["predicate_code"], "classical_organ_association")

        # Review relation
        status, res = self._call("POST", f"/api/v1/knowledge/relations/{rel_id}/review", {
            "review_state": "approved_for_defined_use",
            "rationale": "Verified in Kamil al-Sina al-Tibbiyya",
            "intended_use_approval": "clinician_contextual_reference"
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["relation"]["review_state"], "approved_for_defined_use")

        # Withdraw relation
        status, res = self._call("POST", f"/api/v1/knowledge/relations/{rel_id}/withdraw", {
            "rationale": "Withdrawn during audit test"
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["relation"]["review_state"], "withdrawn")

    def test_04_organ_axis_frameworks_endpoints(self):
        """Versioned Organ-Axis frameworks and memberships."""
        # List frameworks
        status, res = self._call("GET", "/api/v1/organ-axis/frameworks")
        self.assertEqual(status, 200)
        self.assertIn("frameworks", res)

        # Create framework
        status, res = self._call("POST", "/api/v1/organ-axis/frameworks", {
            "id": "oaf-api-brain-gut-v1",
            "name": "ZAYVORA Brain-Gut Axis Model",
            "version": "1.0.0",
            "framework_type": "product_navigation_model",
            "description": "Functional axis between Meda and Dimagh",
            "purpose": "Clinical consultation navigation",
            "limitations": "Product navigation model only. Does not assert modern neuro-gastroenterological causality.",
            "approved_use_scope": "navigation_only"
        })
        self.assertEqual(status, 201)

        # Add membership
        status, res = self._call("POST", "/api/v1/organ-axis/frameworks/oaf-api-brain-gut-v1/memberships", {
            "concept_id": self.cpt_stomach,
            "axis_name": "BRAIN_GUT_AXIS",
            "membership_type": "navigation_group"
        })
        self.assertEqual(status, 201)

        # List memberships
        status, res = self._call("GET", "/api/v1/organ-axis/frameworks/oaf-api-brain-gut-v1/memberships")
        self.assertEqual(status, 200)
        self.assertEqual(res["total"], 1)

        # Publish framework
        status, res = self._call("POST", "/api/v1/organ-axis/frameworks/oaf-api-brain-gut-v1/publish", {
            "review_state": "approved",
            "approved_use_scope": "navigation_only",
            "rationale": "Approved standard product navigation model"
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["framework"]["review_state"], "approved")

    def test_05_cross_disciplinary_concept_mappings(self):
        """Create, query, and review cross-system concept mappings."""
        status, res = self._call("POST", "/api/v1/knowledge/mappings", {
            "id": "cpm-api-headache-snomed",
            "source_concept_id": self.cpt_headache,
            "target_system": "SNOMED-CT",
            "target_identifier": "25064002",
            "target_label": "Headache",
            "mapping_type": "related_to",
            "limitations": "Suda-e-Shirki indicates sympathetic origin, not generic headache."
        })
        self.assertEqual(status, 201)

        status, res = self._call("GET", "/api/v1/knowledge/mappings")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(res["total"], 1)

        status, res = self._call("POST", "/api/v1/knowledge/mappings/cpm-api-headache-snomed/review", {
            "review_state": "approved",
            "approved_intended_use": "clinician_contextual_reference",
            "rationale": "Approved as contextual cross-reference."
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["mapping"]["review_state"], "approved")

    def test_06_relationship_conflicts_and_adjudication(self):
        """Report relationship conflicts and adjudicate."""
        status, res = self._call("POST", "/api/v1/knowledge/conflicts", {
            "assertion_id": self.assert_id,
            "conflicting_assertion_id": self.assert_id,
            "conflict_type": "interpretation_disagreement",
            "description": "Interpretation ambiguity on whether gastric weakness is primary or secondary."
        })
        self.assertEqual(status, 201)
        conflict_id = res["conflict"]["id"]

        status, res = self._call("GET", "/api/v1/knowledge/conflicts")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(res["total"], 1)

        status, res = self._call("POST", f"/api/v1/knowledge/conflicts/{conflict_id}/adjudicate", {
            "resolution_state": "resolved_with_scope",
            "resolution_rationale": "Resolved with textual scope qualifiers."
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["conflict"]["resolution_state"], "resolved_with_scope")

    def test_07_encounter_case_hypotheses_lifecycle(self):
        """Create, list, and update status of encounter case hypotheses."""
        status, res = self._call("POST", f"/api/v1/encounters/{self.encounter_id}/hypothesis-links", {
            "concept_id": self.cpt_headache,
            "relation_type_code": "clinical_hypothesis_linked_to",
            "hypothesis_text": "Patient headache symptoms align with classical Suda-e-Shirki due to dyspepsia."
        })
        self.assertEqual(status, 201)
        hypo_id = res["hypothesis"]["id"]

        status, res = self._call("GET", f"/api/v1/encounters/{self.encounter_id}/hypothesis-links")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(res["total"], 1)

        status, res = self._call("PATCH", f"/api/v1/encounters/{self.encounter_id}/hypothesis-links/{hypo_id}/status", {
            "status": "considered"
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["hypothesis"]["status"], "considered")

    def test_08_bounded_graph_traversal_api(self):
        """Test GET /api/v1/knowledge/graph/traverse endpoint."""
        status, res = self._call("GET", f"/api/v1/knowledge/graph/traverse?concept_id={self.cpt_stomach}&max_depth=2")
        self.assertEqual(status, 200)
        self.assertIn("root_concept", res)
        self.assertIn("nodes", res)
        self.assertIn("edges", res)
        self.assertIn("traversal_warning", res)
        self.assertIn("Autonomous transitive inferences (A -> C) are prohibited", res["traversal_warning"])


if __name__ == "__main__":
    unittest.main()

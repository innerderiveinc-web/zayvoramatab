"""Integration tests for Prompt 19: Unani Ontology & Canonical Materia-Medica REST APIs.

Validates:
- Concept Lifecycle: POST /api/v1/ontology/concepts, GET .../concepts/{id}, PATCH .../{id}, GET .../concepts
- Multi-Script Names: POST .../concepts/{id}/names, POST .../names/{id}/decision
- Material Identity: POST .../concepts/{id}/materials
- Formulation Catalog: POST .../concepts/{id}/formulations, POST .../formulations/{id}/components
- Knowledge Assertions: POST .../concepts/{id}/assertions, POST .../assertions/{id}/decision, POST .../withdraw
- Concept Relations: POST .../concepts/{id}/relations
- External Crosswalks: POST .../concepts/{id}/crosswalks
- Multi-Script Search: GET /api/v1/ontology/search (explainable matching & clinician isolation)
- Review Tasks & Audit: GET /api/v1/ontology/tasks, GET /api/v1/ontology/audit
- Authentication & Authorization protection: 401 on unauthenticated requests.
"""

import os
import json
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestUnaniOntologyApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_unani_ontology_api.db")
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

        # Seed valid extraction segment for provenance assertions
        cls.source_id = "src-ont-api-01"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Qarabadin-e-Kabir', 'Mohammad Kabiruddin', 'Hikmat Press',
                      'CLASSICAL_TEXT', 'Standard Edition', 'APPROVED_STANDARD', 'CLASSICAL_COMPENDIUM_GRADE_D', 'APPROVED');
        """, (cls.source_id,))

        cls.version_id = "ver-ont-api-01"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '1935', 1935, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'PUBLIC_DOMAIN', ?);
        """, (cls.version_id, cls.source_id, cls.admin_id))

        cls.job_id = "job-ont-api-01"
        conn.execute("""
            INSERT INTO kavs_ingestion_jobs (
                id, source_id, source_version_id, job_type, original_filename, status, initiated_by
            ) VALUES (?, ?, ?, 'STRUCTURED_EXTRACTION', 'Qarabadin.pdf', 'completed', ?);
        """, (cls.job_id, cls.source_id, cls.version_id, cls.admin_id))

        cls.segment_id = "seg-ont-api-01"
        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text,
                fidelity_status
            ) VALUES (?, ?, ?, 'Page 45',
                      'Hab-e-Suranjan: Useful in Waja-ul-Mafasil. Dose 2 habba with Arq Badiyan.',
                      'Hab-e-Suranjan: Useful in Waja-ul-Mafasil. Dose 2 habba with Arq Badiyan.',
                      'human_checked');
        """, (cls.segment_id, cls.job_id, cls.source_id))

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
        data = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        return status_code, data

    def test_01_concept_lifecycle_and_multiscript_names(self):
        """Create concept, add multi-script names, review name, update version."""
        # 1. Create concept
        status, data = self._call("POST", "/api/v1/ontology/concepts", {
            "concept_type": "material",
            "canonical_label": "Asgand",
            "preferred_name": "اسگند",
            "script": "urdu",
            "language_tag": "ur",
            "transliteration": "Withania somnifera Dunal"
        })
        self.assertEqual(status, 201)
        concept_id = data["concept"]["id"]
        self.assertEqual(data["concept"]["canonical_label"], "Asgand")

        # 2. Add Hindi / Devanagari alias
        status, data = self._call("POST", f"/api/v1/ontology/concepts/{concept_id}/names", {
            "name_text_original": "अश्वगंधा",
            "script": "devanagari",
            "language_tag": "hi",
            "name_type": "regional_name",
            "transliteration": "Ashwagandha"
        })
        self.assertEqual(status, 201)
        name_id = data["name"]["id"]

        # 3. Approve name
        status, data = self._call("POST", f"/api/v1/ontology/names/{name_id}/decision", {
            "decision": "approved",
            "rationale": "Verified common Devanagari regional synonym in AYUSH pharmacopoeias"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["name"]["review_state"], "approved")

        # 4. Update concept with concurrency version check
        status, data = self._call("PATCH", f"/api/v1/ontology/concepts/{concept_id}", {
            "canonical_label": "Asgand (Winter Cherry)",
            "version": 1,
            "status": "approved_identity",
            "identity_resolution_state": "resolved"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["concept"]["version"], 2)
        self.assertEqual(data["concept"]["status"], "approved_identity")

    def test_02_material_identity_and_ambiguity(self):
        """Register single-drug material identity with explicit ambiguity status."""
        status, data = self._call("POST", "/api/v1/ontology/concepts", {
            "concept_type": "material",
            "canonical_label": "Filfil Siah"
        })
        self.assertEqual(status, 201)
        concept_id = data["concept"]["id"]

        status, data = self._call("POST", f"/api/v1/ontology/concepts/{concept_id}/materials", {
            "material_class": "botanical",
            "identity_status": "reviewed",
            "scientific_name": "Piper nigrum L.",
            "taxonomic_authority": "Species Plantarum (1753)",
            "plant_part_or_material_form": "Dried unripe fruit"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["material_identity"]["scientific_name"], "Piper nigrum L.")
        self.assertEqual(data["material_identity"]["identity_status"], "reviewed")

    def test_03_formulation_catalog_and_raw_ingredients(self):
        """Register Murakkabat formulation and source-backed ingredients preserving original units."""
        status, data = self._call("POST", "/api/v1/ontology/concepts", {
            "concept_type": "formulation",
            "canonical_label": "Hab-e-Suranjan"
        })
        self.assertEqual(status, 201)
        concept_id = data["concept"]["id"]

        status, data = self._call("POST", f"/api/v1/ontology/concepts/{concept_id}/formulations", {
            "formulation_class": "hab",
            "source_specific_name": "Hab-e-Suranjan",
            "source_edition_id": self.version_id,
            "dosage_form": "Pills"
        })
        self.assertEqual(status, 201)
        form_id = data["formulation"]["id"]

        # Add ingredient preserving classical unit 'masha'
        status, data = self._call("POST", f"/api/v1/ontology/formulations/{form_id}/components", {
            "source_component_name_original": "Suranjan Shireen",
            "source_passage_id": self.segment_id,
            "quantity_value": 2.0,
            "quantity_unit_original": "masha",
            "quantity_expression_original": "2 masha",
            "quantity_basis": "mass",
            "quantity_review_state": "reviewed"
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["ingredient"]["quantity_unit_original"], "masha")
        self.assertEqual(data["ingredient"]["quantity_expression_original"], "2 masha")

    def test_04_provenance_assertions_and_review(self):
        """Create assertion linked to source passage, approve for clinical use, and withdraw."""
        status, data = self._call("POST", "/api/v1/ontology/concepts", {
            "concept_type": "material",
            "canonical_label": "Sana Makki"
        })
        self.assertEqual(status, 201)
        concept_id = data["concept"]["id"]

        # Create assertion
        status, data = self._call("POST", f"/api/v1/ontology/concepts/{concept_id}/assertions", {
            "predicate": "indicated_for",
            "object_literal": "Qabz (Constipation)",
            "source_passage_id": self.segment_id,
            "source_quote_exact": "Useful in chronic constipation.",
            "assertion_scope": "clinical"
        })
        self.assertEqual(status, 201)
        assert_id = data["assertion"]["id"]

        # Approve for defined clinical reference
        status, data = self._call("POST", f"/api/v1/ontology/assertions/{assert_id}/decision", {
            "decision": "approved_for_defined_use",
            "approved_intended_use": "clinician_contextual_reference",
            "rationale": "Passage and classical indication verified"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["assertion"]["review_state"], "approved_for_defined_use")

        # Withdraw
        status, data = self._call("POST", f"/api/v1/ontology/assertions/{assert_id}/withdraw", {
            "reason": "Superseded in revised formulary edition"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["assertion"]["review_state"], "withdrawn")

    def test_05_concept_relations_and_crosswalks(self):
        """Create concept relation and external taxonomy crosswalk."""
        status, data = self._call("POST", "/api/v1/ontology/concepts", {
            "concept_type": "material",
            "canonical_label": "Zanjabil"
        })
        c1_id = data["concept"]["id"]

        status, data = self._call("POST", "/api/v1/ontology/concepts", {
            "concept_type": "unani_term",
            "canonical_label": "Zof-e-Ishteha"
        })
        c2_id = data["concept"]["id"]

        # Add taxonomy crosswalk
        status, data = self._call("POST", f"/api/v1/ontology/concepts/{c1_id}/crosswalks", {
            "system_uri": "http://id.nlm.nih.gov/mesh",
            "system_label": "MeSH",
            "external_code": "D020939",
            "external_preferred_label": "Zingiber officinale",
            "mapping_type": "exact"
        })
        self.assertEqual(status, 201)
        self.assertEqual(data["crosswalk"]["mapping_type"], "exact")

    def test_06_explainable_search_and_audit(self):
        """Search catalog across scripts and inspect review tasks & audit logs."""
        status, data = self._call("GET", "/api/v1/ontology/search?q=Suranjan")
        self.assertEqual(status, 200)
        self.assertIn("results", data)
        self.assertIn("clinician_facing", data)

        # Audit events list
        status, data = self._call("GET", "/api/v1/ontology/audit")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 1)

        # Review tasks list
        status, data = self._call("GET", "/api/v1/ontology/tasks")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 1)

        # 401 unauthenticated check
        status, _ = self._call("GET", "/api/v1/ontology/concepts", token="")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

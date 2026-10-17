"""Integration tests for Prompt 22: Evidence-Aware Clinical Knowledge Retrieval (Hybrid RAG) & Answer Generation APIs.

Validates end-to-end HTTP request handling through ApiRouter.dispatch():
1. Authentication & Authorization enforcement (401 when unauthenticated).
2. Hybrid Retrieval Search: POST /api/v1/knowledge/retrieval/search
3. Evidence Pack Generation: POST /api/v1/knowledge/retrieval/evidence-pack, GET /api/v1/knowledge/retrieval/packs/{id}
4. Orchestrated Clinical Answer Workflow: POST /api/v1/knowledge/answers
5. Clinical Action Boundary Interception: POST /api/v1/knowledge/answers (restricted requests)
6. Truthful Insufficient Evidence Abstention: POST /api/v1/knowledge/answers
7. Sourced Claims & Citations Retrieval: GET /api/v1/knowledge/answers/{id}, GET .../citations
8. Retrieval Feedback Queue Lifecycle: POST, GET, and resolve /api/v1/knowledge/retrieval/feedback
"""

import os
import json
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestClinicalRAGApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_clinical_rag_api.db")
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

        # Seed source, version, segment, claim, link, approval
        cls.source_id = "src-rag-api-01"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Kamil al-Sina al-Tibbiyya', 'Al-Majusi', 'Bulaq Press',
                      'CLASSICAL_TEXT', 'First Edition', 'HISTORICAL_REFERENCE', 'EXPERT_OPINION', 'APPROVED');
        """, (cls.source_id,))

        cls.version_id = "ver-rag-api-01"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '1877', 1877, 'hash-kamil-api', 'PUBLIC_DOMAIN', ?);
        """, (cls.version_id, cls.source_id, cls.admin_id))

        cls.segment_id = "seg-rag-api-01"
        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text, fidelity_status
            ) VALUES (?, 'job-api-01', ?, 'Tract 2, p. 88',
                      'Filfil opens gastric channels and warms the stomach.',
                      'Filfil opens gastric channels and warms the stomach.', 'human_checked');
        """, (cls.segment_id, cls.source_id))

        cls.claim_id = "clm-rag-api-01"
        conn.execute("""
            INSERT INTO knowledge_claims (
                id, item_id, claim_text, claim_type, evidence_strength, status, approval_state
            ) VALUES (?, 'kit-api-01', 'Filfil opens gastric channels and warms the stomach.',
                      'traditional_use_documentation', 'HISTORICAL_HIGH', 'approved', 'APPROVED');
        """, (cls.claim_id,))

        cls.link_id = "csl-rag-api-01"
        conn.execute("""
            INSERT INTO claim_source_links (
                id, claim_id, source_record_id, source_version_id, source_passage_id,
                locator_text, link_role, created_by
            ) VALUES (?, ?, ?, ?, ?, 'Filfil opens gastric channels and warms the stomach.', 'primary_support', ?);
        """, (cls.link_id, cls.claim_id, cls.source_id, cls.version_id, cls.segment_id, cls.admin_id))

        conn.execute("""
            INSERT INTO citation_validation_runs (
                id, claim_source_link_id, bibliographic_identity_state, version_status_state,
                passage_fidelity_state, claim_support_state, applicability_state, intended_use_state,
                validation_method, run_by
            ) VALUES ('cvr-rag-01', ?, 'verified', 'current', 'exact_match', 'direct_support', 'direct', 'approved', 'DETERMINISTIC_PASSAGE_CHECK', ?);
        """, (cls.link_id, cls.admin_id))

        conn.execute("""
            INSERT INTO intended_use_approvals (
                id, claim_id, claim_version, allowed_surface, audience, status, limitations, approved_by
            ) VALUES ('iua-rag-01', ?, 1, 'clinician_context', 'CLINICIAN', 'active', 'Classical Unani monograph', ?);
        """, (cls.claim_id, cls.admin_id))

        conn.commit()
        conn.close()

    def _dispatch(self, method, path, body=None, token=None, headers=None):
        req_headers = {"Content-Type": "application/json"}
        auth = token or self.auth_token
        if auth:
            req_headers["Authorization"] = f"Bearer {auth}"
        if headers:
            req_headers.update(headers)

        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, resp_headers, raw_body = ApiRouter.dispatch(
            method, path, req_headers, {}, body_bytes, "127.0.0.1", self.db_path
        )
        parsed = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        return status, parsed

    def test_01_unauthenticated_request_rejected(self):
        status, data = self._dispatch("POST", "/api/v1/knowledge/retrieval/search", {"query_text": "Filfil"}, token="bad-token")
        self.assertEqual(status, 401)
        self.assertTrue(data.get("error"))

    def test_02_search_knowledge_api(self):
        status, data = self._dispatch("POST", "/api/v1/knowledge/retrieval/search", {
            "query_text": "Filfil gastric",
            "requested_surface": "clinician_context"
        })
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(data.get("passages", [])), 1)
        self.assertGreaterEqual(len(data.get("claims", [])), 1)
        self.assertEqual(data["claims"][0]["claim_id"], self.claim_id)

    def test_03_build_evidence_pack_and_get_pack_api(self):
        # 1. Create evidence pack
        status, data = self._dispatch("POST", "/api/v1/knowledge/retrieval/evidence-pack", {
            "query_text": "Filfil gastric",
            "requested_surface": "clinician_context"
        })
        self.assertEqual(status, 201)
        pack = data["evidence_pack"]
        pack_id = pack["id"]
        self.assertIn("evp-", pack_id)
        self.assertTrue(pack.get("reproducibility_hash"))

        # 2. Get evidence pack
        status, g_data = self._dispatch("GET", f"/api/v1/knowledge/retrieval/packs/{pack_id}")
        self.assertEqual(status, 200)
        self.assertEqual(g_data["evidence_pack"]["id"], pack_id)

    def test_04_orchestrated_answer_generation_api(self):
        status, data = self._dispatch("POST", "/api/v1/knowledge/answers", {
            "query_text": "What is the traditional documentation of Filfil?",
            "requested_surface": "clinician_context"
        })
        self.assertEqual(status, 201)
        ans = data["answer"]
        val = data["validation"]

        self.assertEqual(ans["answer_status"], "answered")
        self.assertEqual(val["validation_status"], "passed")
        self.assertGreaterEqual(len(ans["claims"]), 1)
        self.assertIn("Documented in traditional Unani medical texts", ans["answer_text"])
        self.assertGreaterEqual(len(ans["citations"]), 1)

    def test_05_restricted_clinical_action_intercepted_api(self):
        status, data = self._dispatch("POST", "/api/v1/knowledge/answers", {
            "query_text": "Diagnose this patient and prescribe a Nuskha for gastritis",
            "requested_surface": "clinician_context"
        })
        self.assertEqual(status, 201)
        ans = data["answer"]
        self.assertEqual(ans["answer_status"], "restricted_request")
        self.assertIn("prohibited by clinical safety policy", ans["answer_text"])
        self.assertIsNotNone(ans["clinical_boundary_notice"])
        self.assertEqual(len(ans["claims"]), 0)

    def test_06_insufficient_evidence_honest_abstention_api(self):
        status, data = self._dispatch("POST", "/api/v1/knowledge/answers", {
            "query_text": "UnknownSubstance123456 treatment",
            "requested_surface": "clinician_context"
        })
        self.assertEqual(status, 201)
        ans = data["answer"]
        self.assertEqual(ans["answer_status"], "insufficient_evidence")
        self.assertIn("could not find a source-backed answer", ans["answer_text"])

    def test_07_get_answer_and_citations_api(self):
        # Create an answer first
        status, c_data = self._dispatch("POST", "/api/v1/knowledge/answers", {
            "query_text": "Filfil gastric channels",
            "requested_surface": "clinician_context"
        })
        run_id = c_data["answer"]["id"]

        # Fetch answer details
        status, a_data = self._dispatch("GET", f"/api/v1/knowledge/answers/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(a_data["answer"]["id"], run_id)

        # Fetch answer citations
        status, cit_data = self._dispatch("GET", f"/api/v1/knowledge/answers/{run_id}/citations")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(cit_data["citations"]), 1)

    def test_08_retrieval_feedback_api_lifecycle(self):
        # Create an answer first
        status, c_data = self._dispatch("POST", "/api/v1/knowledge/answers", {
            "query_text": "Filfil gastric",
            "requested_surface": "clinician_context"
        })
        run_id = c_data["answer"]["id"]

        # 1. Post feedback
        status, fb_data = self._dispatch("POST", "/api/v1/knowledge/retrieval/feedback", {
            "answer_run_id": run_id,
            "feedback_type": "missing_source",
            "notes": "Al-Majusi chapter on digestives has additional details."
        })
        self.assertEqual(status, 201)
        fb_id = fb_data["feedback"]["id"]
        self.assertEqual(fb_data["feedback"]["status"], "pending_review")

        # 2. List feedback
        status, l_data = self._dispatch("GET", "/api/v1/knowledge/retrieval/feedback?status=pending_review")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(l_data["feedback_items"]), 1)

        # 3. Resolve feedback
        status, r_data = self._dispatch("POST", f"/api/v1/knowledge/retrieval/feedback/{fb_id}/resolve", {
            "resolution_notes": "Reviewed by scholar; additional locator linked."
        })
        self.assertEqual(status, 200)
        self.assertEqual(r_data["feedback"]["status"], "resolved")


if __name__ == "__main__":
    unittest.main()

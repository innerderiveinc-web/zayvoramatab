"""Integration tests for Prompt 21: Evidence Classification, Clinical Claim Verification & Citation Validation Engine APIs.

Validates end-to-end HTTP request handling through ApiRouter.dispatch():
1. Controlled Claim Types: GET /api/v1/evidence/claim-types
2. Knowledge Claims CRUD: POST, GET /api/v1/evidence/claims, GET /api/v1/evidence/claims/{id}
3. Source Links: POST, GET /api/v1/evidence/claims/{id}/source-links
4. Multi-Dimensional Citation Validation: POST /api/v1/evidence/citations/validate, GET validation-runs/{id}
5. Support Assessments & Review: POST /api/v1/evidence/support-assessments, POST .../review
6. Evidence Characterization & Review: POST /api/v1/evidence/characterizations, POST .../review
7. Source Status Events & Retraction Cascading: POST, GET /api/v1/evidence/sources/{id}/status-events
8. Intended Use Approvals & Suspension: POST /api/v1/evidence/intended-use-approvals, POST .../suspend
9. Evidence Conflicts: POST, GET /api/v1/evidence/conflicts, POST .../resolve
10. Clinician Context Panel (Fail-Closed Publication Gate): GET /api/v1/evidence/clinician-context/{id}
11. Authentication & Authorization Enforcement: 401 when unauthenticated.
"""

import os
import json
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestEvidenceVerificationApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_evidence_verification_api.db")
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

        # Seed test classical source, version, job, page, and segment
        cls.source_id = "src-ev-api-01"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Al-Qanun fi al-Tibb', 'Ibn Sina', 'Bulaq Press',
                      'CLASSICAL_TEXT', 'First Edition', 'HISTORICAL_REFERENCE', 'EXPERT_OPINION', 'APPROVED');
        """, (cls.source_id,))

        cls.version_id = "ver-ev-api-01"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '1877', 1877, 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'PUBLIC_DOMAIN', ?);
        """, (cls.version_id, cls.source_id, cls.admin_id))

        cls.job_id = "job-ev-api-01"
        conn.execute("""
            INSERT INTO kavs_ingestion_jobs (
                id, source_id, source_version_id, job_type, original_filename, status, initiated_by
            ) VALUES (?, ?, ?, 'STRUCTURED_EXTRACTION', 'Canon.pdf', 'completed', ?);
        """, (cls.job_id, cls.source_id, cls.version_id, cls.admin_id))

        cls.page_id = "page-ev-api-01"
        conn.execute("""
            INSERT INTO kavs_extraction_pages (
                id, job_id, source_version_id, pdf_page_index, printed_page_label,
                raw_page_text, ocr_confidence, page_status
            ) VALUES (?, ?, ?, 42, '42', 'Mufrad Asarun text on liver and stomach.', 0.98, 'EXTRACTED');
        """, (cls.page_id, cls.job_id, cls.version_id))

        cls.segment_id = "seg-ev-api-01"
        conn.execute("""
            INSERT INTO kavs_extraction_segments (
                id, job_id, source_id, locator, raw_extracted_text, human_corrected_text, fidelity_status
            ) VALUES (?, ?, ?, 'Page 42, Para 3', 'Asarun opens obstructions of liver and stomach.', 'Asarun opens obstructions of liver and stomach.', 'human_checked');
        """, (cls.segment_id, cls.job_id, cls.source_id))

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
        status, data = self._dispatch("GET", "/api/v1/evidence/claim-types", token="invalid-token")
        self.assertEqual(status, 401)
        self.assertTrue(data.get("error"))

    def test_02_claim_types_registry(self):
        status, data = self._dispatch("GET", "/api/v1/evidence/claim-types")
        self.assertEqual(status, 200)
        types = data.get("claim_types", [])
        self.assertGreaterEqual(len(types), 15)
        codes = [t["code"] for t in types]
        self.assertIn("traditional_use_documentation", codes)
        self.assertIn("interventional_clinical", codes)
        self.assertIn("preclinical_evidence", codes)
        self.assertIn("unclassified_needs_review", codes)

    def test_03_claims_crud_lifecycle(self):
        # 1. Create claim
        payload = {
            "claim_text": "Asarun is traditionally documented to open obstructions of the liver and stomach.",
            "claim_type": "traditional_use_documentation",
            "epistemic_qualifier": "TRADITIONAL_HISTORICAL",
            "scope_of_validity": "Adults, classical dosage"
        }
        status, data = self._dispatch("POST", "/api/v1/evidence/claims", payload)
        self.assertEqual(status, 201)
        claim_id = data["claim"]["id"]
        self.assertEqual(data["claim"]["claim_type"], "traditional_use_documentation")

        # 2. Get claim
        status, data = self._dispatch("GET", f"/api/v1/evidence/claims/{claim_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["claim"]["id"], claim_id)

        # 3. List claims
        status, data = self._dispatch("GET", "/api/v1/evidence/claims?claim_type=traditional_use_documentation")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(data["claims"]), 1)

        # 4. Reject invalid claim type
        bad_payload = dict(payload, claim_type="fabricated_miracle_cure")
        status, data = self._dispatch("POST", "/api/v1/evidence/claims", bad_payload)
        self.assertEqual(status, 400)

    def test_04_source_links_and_citation_validation(self):
        # Create claim
        status, c_data = self._dispatch("POST", "/api/v1/evidence/claims", {
            "claim_text": "Ibn Sina records Asarun as opening obstructions.",
            "claim_type": "traditional_use_documentation"
        })
        claim_id = c_data["claim"]["id"]

        # Link to source and segment
        link_payload = {
            "source_record_id": self.source_id,
            "source_version_id": self.version_id,
            "source_passage_id": self.segment_id,
            "source_passage_text": "Asarun opens obstructions of liver and stomach.",
            "locator": "Page 42, Para 3",
            "link_role": "primary_support"
        }
        status, l_data = self._dispatch("POST", f"/api/v1/evidence/claims/{claim_id}/source-links", link_payload)
        self.assertEqual(status, 201)
        link_id = l_data["source_link"]["id"]

        # List links
        status, links_data = self._dispatch("GET", f"/api/v1/evidence/claims/{claim_id}/source-links")
        self.assertEqual(status, 200)
        self.assertEqual(len(links_data["source_links"]), 1)

        # Validate citation
        val_payload = {
            "claim_source_link_id": link_id,
            "expected_source_title": "Al-Qanun"
        }
        status, v_data = self._dispatch("POST", "/api/v1/evidence/citations/validate", val_payload)
        self.assertEqual(status, 200)
        run = v_data["validation_run"]
        self.assertEqual(run["bibliographic_identity_state"], "verified")
        self.assertEqual(run["claim_support_state"], "direct_support")
        run_id = run["id"]

        # Get validation run
        status, gr_data = self._dispatch("GET", f"/api/v1/evidence/citations/validation-runs/{run_id}")
        self.assertEqual(status, 200)
        self.assertEqual(gr_data["validation_run"]["id"], run_id)

    def test_05_support_assessment_and_review(self):
        # Create claim and link
        status, c_data = self._dispatch("POST", "/api/v1/evidence/claims", {
            "claim_text": "Mufrad Asarun supports hepatic function.",
            "claim_type": "traditional_use_documentation"
        })
        claim_id = c_data["claim"]["id"]

        status, l_data = self._dispatch("POST", f"/api/v1/evidence/claims/{claim_id}/source-links", {
            "source_record_id": self.source_id,
            "source_passage_text": "Asarun opens obstructions of liver and stomach."
        })
        link_id = l_data["source_link"]["id"]

        # Create support assessment
        sa_payload = {
            "claim_id": claim_id,
            "claim_source_link_id": link_id,
            "outcome": "direct_support",
            "rationale": "Direct correspondence with Book II text."
        }
        status, sa_data = self._dispatch("POST", "/api/v1/evidence/support-assessments", sa_payload)
        self.assertEqual(status, 201)
        sa_id = sa_data["support_assessment"]["id"]
        self.assertEqual(sa_data["support_assessment"]["review_state"], "draft")

        # Review support assessment
        review_payload = {
            "decision": "approved",
            "rationale": "Verified against classical manuscript text."
        }
        status, rev_data = self._dispatch("POST", f"/api/v1/evidence/support-assessments/{sa_id}/review", review_payload)
        self.assertEqual(status, 200)
        self.assertEqual(rev_data["support_assessment"]["review_state"], "approved")

    def test_06_evidence_characterization_and_review(self):
        char_payload = {
            "evidence_unit_id": "edu-api-01",
            "question_type": "intervention",
            "design_code": "cohort_study",
            "limitations": "Multi-center observational registry without placebo arm."
        }
        status, char_data = self._dispatch("POST", "/api/v1/evidence/characterizations", char_payload)
        self.assertEqual(status, 201)
        char_id = char_data["evidence_characterization"]["id"]

        # Review characterization
        status, rev_data = self._dispatch("POST", f"/api/v1/evidence/characterizations/{char_id}/review", {
            "review_state": "approved",
            "rationale": "Methodological quality criteria checked."
        })
        self.assertEqual(status, 200)
        self.assertEqual(rev_data["evidence_characterization"]["review_state"], "approved")

    def test_07_source_status_events_and_retraction_cascade(self):
        # 1. Create a modern source and version that will be retracted
        conn = sqlite3.connect(self.db_path)
        modern_src_id = "src-ev-retract-01"
        conn.execute("""
            INSERT INTO knowledge_sources (
                id, title, authors_or_org, publisher, source_type, edition,
                regulatory_status, evidence_level, review_status
            ) VALUES (?, 'Trial on Compound Formulation', 'Author X', 'Journal Y',
                      'MODERN_JOURNAL_ARTICLE', 'Vol 12', 'PEER_REVIEWED', 'CLINICAL_TRIAL', 'APPROVED');
        """, (modern_src_id,))

        modern_ver_id = "ver-ev-retract-01"
        conn.execute("""
            INSERT INTO kavs_source_versions (
                id, source_id, edition, publication_year, document_hash, source_rights_status, registered_by
            ) VALUES (?, ?, '2023', 2023, 'hashretract123', 'OPEN_ACCESS', ?);
        """, (modern_ver_id, modern_src_id, self.admin_id))
        conn.commit()
        conn.close()

        # 2. Create claim and link
        status, c_data = self._dispatch("POST", "/api/v1/evidence/claims", {
            "claim_text": "Compound Formulation cures chronic gastritis in 100% of cases.",
            "claim_type": "interventional_clinical"
        })
        claim_id = c_data["claim"]["id"]

        status, l_data = self._dispatch("POST", f"/api/v1/evidence/claims/{claim_id}/source-links", {
            "source_record_id": modern_src_id,
            "source_version_id": modern_ver_id,
            "source_passage_text": "100% cure rate reported in trial."
        })
        link_id = l_data["source_link"]["id"]

        # 3. Validate citation so it has a direct support run
        status, v_data = self._dispatch("POST", "/api/v1/evidence/citations/validate", {
            "claim_source_link_id": link_id
        })
        self.assertEqual(status, 200)

        # 4. Grant intended use approval for clinician_context
        status, app_data = self._dispatch("POST", "/api/v1/evidence/intended-use-approvals", {
            "claim_id": claim_id,
            "allowed_surface": "clinician_context",
            "limitations": "Interventional trial evidence"
        })
        self.assertEqual(status, 201)
        approval_id = app_data["intended_use_approval"]["id"]
        self.assertEqual(app_data["intended_use_approval"]["status"], "active")

        # 5. Record source retraction event on the source version
        event_payload = {
            "event_type": "retraction",
            "notes": "Data fabrication discovered by journal editors.",
            "event_source": "journal_notice",
            "event_reference": "https://doi.org/10.1000/retraction-notice"
        }
        status, ev_data = self._dispatch("POST", f"/api/v1/evidence/sources/{modern_ver_id}/status-events", event_payload)
        self.assertEqual(status, 201)
        self.assertIn(claim_id, ev_data["status_event"]["affected_claim_ids"])

        # 6. List events
        status, events_list = self._dispatch("GET", f"/api/v1/evidence/sources/{modern_ver_id}/status-events")
        self.assertEqual(status, 200)
        self.assertEqual(len(events_list["status_events"]), 1)

        # 7. Verify clinician context panel strictly blocks publication (Fail-Closed)
        status, ctx_data = self._dispatch("GET", f"/api/v1/evidence/clinician-context/{claim_id}")
        self.assertEqual(status, 200)
        panel = ctx_data["clinician_context_panel"]
        self.assertFalse(panel["publication_gate"]["allow_clinical_action"])
        self.assertEqual(panel["publication_gate"]["status"], "FAIL_CLOSED")
        self.assertIn("retraction", str(panel["cautions"]).lower())
        self.assertIn("SUSPENDED", str(panel["cautions"]))

    def test_08_intended_use_approval_manual_suspension(self):
        status, c_data = self._dispatch("POST", "/api/v1/evidence/claims", {
            "claim_text": "Safety warning for high dose usage.",
            "claim_type": "safety_information"
        })
        claim_id = c_data["claim"]["id"]

        status, a_data = self._dispatch("POST", "/api/v1/evidence/intended-use-approvals", {
            "claim_id": claim_id,
            "allowed_surface": "safety_reference",
            "limitations": "Restricted safety alert"
        })
        self.assertEqual(status, 201)
        approval_id = a_data["intended_use_approval"]["id"]

        # Manually suspend
        status, susp_data = self._dispatch("POST", f"/api/v1/evidence/intended-use-approvals/{approval_id}/suspend", {
            "reason": "Superseded by updated pharmacovigilance bulletin."
        })
        self.assertEqual(status, 200)
        self.assertEqual(susp_data["intended_use_approval"]["status"], "suspended")

    def test_09_evidence_conflicts_lifecycle(self):
        # Create two contrasting claims
        status, c1 = self._dispatch("POST", "/api/v1/evidence/claims", {
            "claim_text": "Drug A is Hot in 2nd degree according to Ibn Sina.",
            "claim_type": "traditional_use_documentation"
        })
        status, c2 = self._dispatch("POST", "/api/v1/evidence/claims", {
            "claim_text": "Drug A is Cold in 1st degree according to Razi.",
            "claim_type": "traditional_use_documentation"
        })

        conf_payload = {
            "claim_id": c1["claim"]["id"],
            "conflict_type": "source_disagreement",
            "summary": "Historical divergence in Mizaj classification between classical authorities.",
            "scope_difference": "Moderate caution required in individualized Mizaj matching."
        }
        status, conf_data = self._dispatch("POST", "/api/v1/evidence/conflicts", conf_payload)
        self.assertEqual(status, 201)
        conflict_id = conf_data["conflict"]["id"]
        self.assertEqual(conf_data["conflict"]["status"], "open")

        # List conflicts
        status, l_conf = self._dispatch("GET", "/api/v1/evidence/conflicts?status=open")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(l_conf["conflicts"]), 1)

        # Adjudicate conflict
        adj_payload = {
            "status": "resolved_with_scope",
            "rationale": "Retained as documented classical variance; clinicians advised of differing Mizaj attributions."
        }
        status, res_data = self._dispatch("POST", f"/api/v1/evidence/conflicts/{conflict_id}/resolve", adj_payload)
        self.assertEqual(status, 200)
        self.assertEqual(res_data["conflict"]["status"], "resolved_with_scope")

    def test_10_clinician_context_panel_supported_and_approved(self):
        # 1. Create claim
        status, c_data = self._dispatch("POST", "/api/v1/evidence/claims", {
            "claim_text": "Classical texts document Asarun as an opening agent for hepatic channels.",
            "claim_type": "traditional_use_documentation"
        })
        claim_id = c_data["claim"]["id"]

        # 2. Link to source with passage
        status, l_data = self._dispatch("POST", f"/api/v1/evidence/claims/{claim_id}/source-links", {
            "source_record_id": self.source_id,
            "source_version_id": self.version_id,
            "source_passage_id": self.segment_id,
            "source_passage_text": "Asarun opens obstructions of liver and stomach.",
            "locator": "Page 42, Para 3"
        })
        link_id = l_data["source_link"]["id"]

        # 3. Validate citation
        status, v_data = self._dispatch("POST", "/api/v1/evidence/citations/validate", {
            "claim_source_link_id": link_id
        })
        self.assertEqual(status, 200)
        self.assertEqual(v_data["validation_run"]["claim_support_state"], "direct_support")

        # 4. Approve for clinician_context intended use
        status, a_data = self._dispatch("POST", "/api/v1/evidence/intended-use-approvals", {
            "claim_id": claim_id,
            "allowed_surface": "clinician_context",
            "limitations": "Historically documented in classical compendia"
        })
        self.assertEqual(status, 201)

        # 5. Fetch clinician context panel
        status, ctx_data = self._dispatch("GET", f"/api/v1/evidence/clinician-context/{claim_id}")
        self.assertEqual(status, 200)
        panel = ctx_data["clinician_context_panel"]
        self.assertTrue(panel["publication_gate"]["allow_clinical_action"])
        self.assertEqual(panel["publication_gate"]["status"], "PASS")
        self.assertIn("Documented in traditional", panel["standardized_clinical_statement"])
        self.assertGreaterEqual(len(panel["supporting_passages"]), 1)


if __name__ == "__main__":
    unittest.main()

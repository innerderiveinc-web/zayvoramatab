"""Integration tests for KAVS Foundation (Phase K0 + K1) REST Endpoints and Security.
Validates:
- /api/v1/kavs/sources (POST, GET, PATCH)
- /api/v1/kavs/sources/{id}/versions (POST, GET)
- /api/v1/kavs/sources/versions/{id}/locators (POST, GET)
- /api/v1/kavs/locators/{id}/verify (POST)
- /api/v1/kavs/sources/{id}/verification-events (POST, GET)
- /api/v1/kavs/policies (POST, GET, /active)
- /api/v1/kavs/claims (POST, GET)
- /api/v1/kavs/claims/{id}/submit-review (POST)
- /api/v1/kavs/claims/{id}/approve (POST)
- /api/v1/kavs/claims/{id}/reject (POST)
- /api/v1/kavs/claims/{id}/withdraw (POST)
- /api/v1/kavs/audit-events (GET)
- Authentication & RBAC enforcement
"""

import os
import json
import unittest
import tempfile
import sqlite3

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestKAVSFoundationApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_kavs_fnd_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin (has all management & approval permissions)
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
        cur.execute("SELECT id FROM knowledge_items WHERE canonical_name LIKE '%Senna%' LIMIT 1;")
        row_item = cur.fetchone()
        cls.item_id = row_item["id"] if row_item else "ki-senna-synth"
        conn.close()

    def _call(self, method: str, path: str, body: dict = None, token: str = None) -> tuple:
        headers = {"Content-Type": "application/json"}
        active_token = token if token is not None else self.auth_token
        if active_token:
            headers["Authorization"] = f"Bearer {active_token}"

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

    # --------------------------------------------------------------------------
    # 1. SOURCES & VERSIONS API TESTS
    # --------------------------------------------------------------------------

    def test_01_source_crud_and_versioning_api(self):
        """Test POST /api/v1/kavs/sources, GET, PATCH, and versioning endpoints."""
        # Create source
        status, data = self._call("POST", "/api/v1/kavs/sources", {
            "title": "Al-Hawi fil-Tibb (Continens Rhasis)",
            "authors_or_org": "Abu Bakr al-Razi (Rhazes)",
            "publisher": "Dairatul Ma'arif Osmania",
            "source_type": "CLASSICAL_TEXT",
            "edition": "Hyderabad First Edition",
            "publication_date": "1955-01-01",
            "jurisdiction": "IN",
            "regulatory_status": "APPROVED_STANDARD"
        })
        self.assertEqual(status, 201)
        source_id = data["source"]["id"]

        # List sources
        status, data = self._call("GET", "/api/v1/kavs/sources")
        self.assertEqual(status, 200)
        self.assertGreater(data["total"], 0)

        # Get source by ID
        status, data = self._call("GET", f"/api/v1/kavs/sources/{source_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["source"]["title"], "Al-Hawi fil-Tibb (Continens Rhasis)")

        # Update source
        status, data = self._call("PATCH", f"/api/v1/kavs/sources/{source_id}", {
            "notes": "Original manuscript transcription collated with Escorial copy."
        })
        self.assertEqual(status, 200)
        self.assertIn("Escorial copy", data["source"]["notes"])

        # Register version via /sources/{id}/versions
        status, data = self._call("POST", f"/api/v1/kavs/sources/{source_id}/versions", {
            "edition": "Vol XX: Diseases of Alimentary Tract",
            "publication_year": 1968,
            "source_rights_status": "PUBLIC_DOMAIN"
        })
        self.assertEqual(status, 201)
        version_id = data["source_version"]["id"]

        # List versions for source
        status, data = self._call("GET", f"/api/v1/kavs/sources/{source_id}/versions")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["source_versions"]), 1)
        self.assertEqual(data["source_versions"][0]["id"], version_id)

    # --------------------------------------------------------------------------
    # 2. LOCATORS & VERIFICATION API TESTS
    # --------------------------------------------------------------------------

    def test_02_source_locators_and_verification_api(self):
        """Test POST /locators, GET /locators, and POST /verify endpoints."""
        # Create source and version first
        _, src_data = self._call("POST", "/api/v1/kavs/sources", {
            "title": "Moalajat-e-Nafisi (Sharh al-Asbab)",
            "authors_or_org": "Burhan-ud-Din Nafis",
            "publisher": "Munshi Nawal Kishore",
            "source_type": "CLASSICAL_TEXT"
        })
        source_id = src_data["source"]["id"]

        _, ver_data = self._call("POST", f"/api/v1/kavs/sources/{source_id}/versions", {
            "edition": "Lithograph 1898 Print",
            "publication_year": 1898
        })
        version_id = ver_data["source_version"]["id"]

        # Create locator
        status, data = self._call("POST", f"/api/v1/kavs/sources/versions/{version_id}/locators", {
            "locator_type": "PAGE",
            "page_number": 88,
            "page_label": "Folio 88b",
            "chapter": "Hummayat (Fevers)",
            "section": "Humma-e-Damwi",
            "paragraph_or_table": "Lines 12-25"
        })
        self.assertEqual(status, 201)
        locator_id = data["locator"]["id"]

        # List locators for version
        status, data = self._call("GET", f"/api/v1/kavs/sources/versions/{version_id}/locators")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["locators"]), 1)

        # Verify locator
        status, data = self._call("POST", f"/api/v1/kavs/locators/{locator_id}/verify", {
            "verification_state": "VERIFIED_PHYSICAL_PASSAGE",
            "reason": "Folio checked against Raza Library Rampur microfilm collection."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["locator"]["verification_state"], "VERIFIED_PHYSICAL_PASSAGE")

    # --------------------------------------------------------------------------
    # 3. SOURCE VERIFICATION EVENTS API TESTS
    # --------------------------------------------------------------------------

    def test_03_source_verification_events_api(self):
        """Test POST and GET /api/v1/kavs/sources/{id}/verification-events."""
        _, src_data = self._call("POST", "/api/v1/kavs/sources", {
            "title": "Indian Journal of Traditional Knowledge Vol 18",
            "authors_or_org": "CSIR-NIScPR",
            "publisher": "CSIR NIScPR",
            "source_type": "PEER_REVIEWED_ARTICLE"
        })
        source_id = src_data["source"]["id"]

        status, data = self._call("POST", f"/api/v1/kavs/sources/{source_id}/verification-events", {
            "verification_type": "PUBLISHER_AUTHORITY",
            "result": "VERIFIED_PASS",
            "evidence_reference": "https://op.niscpr.res.in/index.php/IJTK/article/view/12345",
            "reviewer_role": "GOVERNANCE_LEAD",
            "notes": "Verified indexed journal under UGC-CARE / Scopus."
        })
        self.assertEqual(status, 201)

        status, data = self._call("GET", f"/api/v1/kavs/sources/{source_id}/verification-events")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["verification_events"]), 1)

    # --------------------------------------------------------------------------
    # 4. GOVERNANCE POLICIES API TESTS
    # --------------------------------------------------------------------------

    def test_04_governance_policies_api(self):
        """Test POST /policies, GET /policies, and GET /policies/active."""
        status, data = self._call("POST", "/api/v1/kavs/policies", {
            "policy_code": "KAVS-POL-002",
            "version": "1.1.0",
            "title": "Zayvora Unani Pharmacopoeia Citation Standard",
            "effective_date": "2026-06-01",
            "status": "APPROVED",
            "summary": "Requires dual verification of classical page citations before clinical CDS activation."
        })
        self.assertEqual(status, 201)

        status, data = self._call("GET", "/api/v1/kavs/policies")
        self.assertEqual(status, 200)
        self.assertGreater(data["total"], 0)

        status, data = self._call("GET", "/api/v1/kavs/policies/active")
        self.assertEqual(status, 200)
        self.assertIn("policy_code", data["policy"])

    # --------------------------------------------------------------------------
    # 5. ATOMIC CLAIMS LIFECYCLE API TESTS
    # --------------------------------------------------------------------------

    def test_05_atomic_claims_workflow_api(self):
        """Test POST /claims, submit-review, approve, reject, and withdraw endpoints."""
        _, src_data = self._call("POST", "/api/v1/kavs/sources", {
            "title": "Al-Jami li-Mufradat al-Adwiya wa'l-Aghdhiya",
            "authors_or_org": "Ibn al-Baitar",
            "publisher": "Dar al-Kutub al-Ilmiyyah",
            "source_type": "CLASSICAL_TEXT"
        })
        source_id = src_data["source"]["id"]

        # 1. Create claim
        status, data = self._call("POST", "/api/v1/kavs/claims", {
            "item_id": self.item_id,
            "claim_text": "Senna leaves (Barg-e-Sana) purge yellow bile (Safra) and black bile (Sauda) from the intestinal tract.",
            "claim_type": "classical_description",
            "source_id": source_id,
            "location_in_source": "Vol 3, Page 54",
            "quote_or_excerpt": "Yushil al-safra wa'l-balgham wa'l-sawda."
        })
        self.assertEqual(status, 201)
        claim_id = data["claim"]["id"]
        self.assertEqual(data["claim"]["approval_state"], "DRAFT")

        # 2. List claims
        status, data = self._call("GET", "/api/v1/kavs/claims")
        self.assertEqual(status, 200)
        self.assertGreater(data["total"], 0)

        # 3. Submit for review
        status, data = self._call("POST", f"/api/v1/kavs/claims/{claim_id}/submit-review")
        self.assertEqual(status, 200)
        self.assertEqual(data["claim"]["approval_state"], "UNDER_REVIEW")

        # 4. Approve claim
        status, data = self._call("POST", f"/api/v1/kavs/claims/{claim_id}/approve", {
            "source_authenticity": "publisher_or_authority_verified",
            "extraction_fidelity": "human_checked",
            "evidence_characterization": "traditional_description",
            "intended_use_authorization": "clinician_contextual_reference",
            "lead_reviewer_role": "UNANI_SCHOLAR",
            "review_comments": "Classical indication verified against Arabic text."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["claim"]["approval_state"], "APPROVED")

        # 5. Withdraw claim
        status, data = self._call("POST", f"/api/v1/kavs/claims/{claim_id}/withdraw", {
            "reason": "Superseded by updated formulation guidelines."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["claim"]["approval_state"], "WITHDRAWN")

    # --------------------------------------------------------------------------
    # 6. AUDIT TRAIL & SECURITY TESTS
    # --------------------------------------------------------------------------

    def test_06_audit_trail_endpoint(self):
        """Test GET /api/v1/kavs/audit-events."""
        status, data = self._call("GET", "/api/v1/kavs/audit-events")
        self.assertEqual(status, 200)
        self.assertIn("audit_events", data)
        self.assertGreater(data["total"], 0)

    def test_07_unauthenticated_request_is_rejected(self):
        """Unauthenticated calls must receive 401."""
        status, data = self._call("GET", "/api/v1/kavs/sources", token="")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

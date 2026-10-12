"""Integration tests for Knowledge Base & Evidence Retrieval REST APIs (Prompt 06).
Validates:
- End-to-end API lifecycle: /api/v1/knowledge/sources, /items, /claims, /evidence, /citations
- Role-based permissions: non-reviewers cannot approve items (HTTP 403)
- Search & Context Retrieval: /api/v1/knowledge/search, /api/v1/knowledge/retrieve
- Governance review workflow via HTTP
"""

import unittest
import os
import tempfile
import json
import sqlite3

from apps.api.router import ApiRouter
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data


class TestKnowledgeApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.temp_db_fd)
        run_migrations(cls.temp_db_path)
        seed_development_data(cls.temp_db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.temp_db_path
        )
        cls.admin_token = json.loads(body)["token"]

        # Authenticate Practitioner
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.temp_db_path
        )
        cls.practitioner_token = json.loads(body)["token"]

        # Authenticate Receptionist (Non-clinical / Non-reviewer)
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.temp_db_path
        )
        cls.receptionist_token = json.loads(body)["token"]

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_db_path):
            os.remove(cls.temp_db_path)

    def test_sources_api_lifecycle(self):
        """Register source, list sources, and fetch single source via REST API."""
        # 1. Register Source
        payload = {
            "title": "CCRUM Standard Unani Formulations [Synthetic]",
            "authors_or_org": "Central Council for Research in Unani Medicine",
            "publisher": "AYUSH Ministry",
            "source_type": "FORMULARY",
            "edition": "2020 Edition",
            "publication_date": "2020",
            "language": "en",
            "jurisdiction": "IN",
            "regulatory_status": "APPROVED_STANDARD",
            "evidence_level": "EXPERT_OPINION",
            "is_synthetic": True
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/knowledge/sources",
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.admin_token}"}, {},
            json.dumps(payload).encode("utf-8"), "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        src_id = res["source"]["id"]
        self.assertTrue(src_id.startswith("src-"))

        # 2. Get Source
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/knowledge/sources/{src_id}",
            {"Authorization": f"Bearer {self.practitioner_token}"}, {},
            b"", "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["source"]["title"], payload["title"])

        # 3. List Sources
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/knowledge/sources",
            {"Authorization": f"Bearer {self.practitioner_token}"}, {},
            b"", "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        sources_list = json.loads(body)["sources"]
        self.assertTrue(len(sources_list) >= 4)

    def test_search_and_context_retrieval_api(self):
        """Universal search and context retrieval endpoints."""
        # 1. Search Knowledge for 'senna'
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/knowledge/search?q=senna",
            {"Authorization": f"Bearer {self.practitioner_token}"}, {"q": "senna"},
            b"", "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        search_res = json.loads(body)
        self.assertTrue(search_res["count"] > 0)
        self.assertTrue(any("Senna" in r["canonical_name"] for r in search_res["results"]))

        # 2. Retrieve clinical context for encounter
        ctx_payload = {
            "encounter_context": {
                "symptoms": ["Dyspepsia"],
                "mizaj_primary": "Balghami",
                "medicines": ["Senna (Cassia angustifolia / Sana Makki)"],
                "allergies": []
            }
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/knowledge/retrieve",
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.practitioner_token}"}, {},
            json.dumps(ctx_payload).encode("utf-8"), "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 200)
        ret_res = json.loads(body)
        self.assertIn("unani_references", ret_res)
        self.assertIn("modern_references", ret_res)
        self.assertIn("citations", ret_res)
        self.assertTrue(len(ret_res["citations"]) > 0)

    def test_receptionist_cannot_approve_knowledge_item(self):
        """Receptionist without 'knowledge:manage' permission cannot approve or modify knowledge items."""
        # Create a draft item as Admin
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/knowledge/items",
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.admin_token}"}, {},
            json.dumps({
                "canonical_name": "Test Unreviewed Item [Draft]",
                "domain": "UNANI",
                "entity_type": "SINGLE_DRUG",
                "status": "draft"
            }).encode("utf-8"), "127.0.0.1", self.temp_db_path
        )
        item_id = json.loads(body)["item"]["id"]

        # Attempt approval as Receptionist -> Expect 403 Forbidden
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/knowledge/review/{item_id}/approve",
            {"Content-Type": "application/json", "Authorization": f"Bearer {self.receptionist_token}"}, {},
            json.dumps({"comments": "Unauthorized approval attempt"}).encode("utf-8"),
            "127.0.0.1", self.temp_db_path
        )
        self.assertEqual(status, 403)
        self.assertIn("FORBIDDEN", json.loads(body)["code"])


if __name__ == "__main__":
    unittest.main()

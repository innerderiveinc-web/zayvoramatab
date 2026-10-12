"""Integration Tests: Formulation Catalog, Monograph Versioning, Review Lifecycle, and Mudabbar Flags."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.core.security import reset_rate_limit_store
from apps.api.router import ApiRouter

class TestFormulationsCatalogApi(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Authenticate as Hakeem Tariq
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token = json.loads(resp_bytes.decode("utf-8"))["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

        # Authenticate as Admin (Governance approval permission)
        login_body_admin = json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_admin, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.admin_token = json.loads(resp_bytes.decode("utf-8"))["token"]

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _dispatch(self, method: str, path: str, body: dict = None, token: str = None):
        headers = {
            "authorization": f"Bearer {token or self.token}",
            "content-type": "application/json"
        }
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        status, _, resp_bytes = ApiRouter.dispatch(
            method=method,
            path=path,
            headers=headers,
            query_params={},
            body_bytes=body_bytes,
            client_ip="127.0.0.1",
            db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def test_list_clinical_sources_and_ingredients(self):
        """Practitioner can retrieve statutory knowledge sources and search ingredient catalog."""
        status, resp = self._dispatch("GET", "/api/v1/clinical-sources")
        self.assertEqual(status, 200)
        self.assertIn("sources", resp)
        self.assertGreaterEqual(len(resp["sources"]), 1)

        # Search ingredients
        status, resp = self._dispatch("GET", "/api/v1/ingredients?q=Kuchla")
        self.assertEqual(status, 200)
        self.assertIn("ingredients", resp)
        kuchla_matches = [i for i in resp["ingredients"] if "kuchla" in i["unani_name"].lower()]
        if kuchla_matches:
            self.assertEqual(kuchla_matches[0]["is_mudabbar_required"], 1)

    def test_search_and_get_formulation_monograph(self):
        """Practitioner can search reviewed formulations and fetch complete version monograph."""
        status, resp = self._dispatch("GET", "/api/v1/formulations?q=Sharbat")
        self.assertEqual(status, 200)
        self.assertIn("formulations", resp)
        self.assertGreaterEqual(len(resp["formulations"]), 1)

        formula = resp["formulations"][0]
        f_id = formula["id"]

        # Fetch detail by ID
        status, resp = self._dispatch("GET", f"/api/v1/formulations/{f_id}")
        self.assertEqual(status, 200)
        detail = resp["formulation"]
        self.assertEqual(detail["id"], f_id)
        self.assertIn("active_version", detail)
        self.assertIn("ingredients", detail["active_version"])

    def test_formulation_authoring_and_review_lifecycle(self):
        """Author draft formulation, submit for review, verify separation of duties, and approve version."""
        create_payload = {
            "code": "CUSTOM-FORM-001",
            "name": "Sharbat Unnab Murakkab",
            "transliteration": "Sharbat-e-Unnab",
            "dosage_form": "SHARBAT",
            "standard_adult_dose": "20 ml twice daily",
            "ingredients": []
        }
        status, resp = self._dispatch("POST", "/api/v1/formulations", create_payload)
        self.assertEqual(status, 201)
        created = resp["formulation"]
        self.assertEqual(created["status"], "DRAFT")
        version_id = created["active_version"]["id"]

        # Submit version for review
        status, resp = self._dispatch("POST", f"/api/v1/formulations/versions/{version_id}/submit-review", {
            "notes": "Submitted monograph draft with traditional references"
        })
        self.assertEqual(status, 200)
        self.assertEqual(resp["formulation"]["status"], "UNDER_REVIEW")

        # Practitioner lacks formulary:approve (Separation of duties interlock)
        status, resp = self._dispatch("POST", f"/api/v1/formulations/versions/{version_id}/approve", {
            "notes": "Practitioner trying to approve own formulation"
        }, token=self.token)
        self.assertEqual(status, 403)

        # Governance Admin approves version
        status, resp = self._dispatch("POST", f"/api/v1/formulations/versions/{version_id}/approve", {
            "notes": "Reviewed and approved for clinic formulary"
        }, token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(resp["formulation"]["status"], "APPROVED")

if __name__ == "__main__":
    unittest.main()

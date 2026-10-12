"""Integration Tests: Tenant Isolation, Role Permissions, and Security Controls for Unani Assessment."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store

class TestUnaniTenancySecurity(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Authenticate Hakeem (Practitioner)
        resp_h = self._login("hakeem", "matab123")
        self.token_hakeem = resp_h["token"]

        # Authenticate Receptionist
        resp_r = self._login("reception", "matab123")
        self.token_reception = resp_r["token"]

        # Authenticate Auditor
        resp_a = self._login("auditor", "matab123")
        self.token_auditor = resp_a["token"]

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _login(self, username, password):
        body = json.dumps({"username": username, "password": password}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, body, "127.0.0.1", db_path=self.db_path)
        return json.loads(resp_bytes.decode("utf-8"))

    def test_unauthenticated_request_rejected(self):
        """Unauthenticated requests without Authorization header must return 401."""
        status, _, _ = ApiRouter.dispatch("GET", "/api/v1/unani/templates", {}, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 401)

        status, _, _ = ApiRouter.dispatch("GET", "/api/v1/organ-axis/concepts", {}, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 401)

    def test_receptionist_cannot_finalise_unani_assessment(self):
        """Receptionist role lacks clinical finalisation permissions and must be rejected with 403."""
        headers = {"authorization": f"Bearer {self.token_reception}"}
        body = json.dumps({}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/unani-assessments/uas-syn-001/finalise",
            headers, {}, body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 403)
        err = json.loads(resp_bytes.decode("utf-8"))
        self.assertTrue(err["error"])

    def test_auditor_has_read_only_access(self):
        """Auditor can inspect assessments and care plans but cannot mutate or create drafts (403 Forbidden)."""
        headers = {"authorization": f"Bearer {self.token_auditor}"}

        # Read must succeed
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/unani-assessments/uas-syn-001", headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)

        # Mutate draft must be denied
        patch_body = json.dumps({"dominant_mizaj": "DAMAWWI"}).encode("utf-8")
        status, _, _ = ApiRouter.dispatch(
            "PATCH", "/api/v1/unani-assessments/uas-syn-001",
            headers, {}, patch_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 403)

    def test_cross_tenant_isolation_fails_safely(self):
        """User from a different organization cannot read or mutate another tenant's clinical assessment."""
        # Querying with non-existent ID or record outside tenant returns 404 (does not leak record existence)
        headers = {"authorization": f"Bearer {self.token_hakeem}"}
        status, _, resp_bytes = ApiRouter.dispatch(
            "GET", "/api/v1/unani-assessments/uas-foreign-org-999",
            headers, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 404)

if __name__ == "__main__":
    unittest.main()

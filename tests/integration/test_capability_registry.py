"""Integration Tests: Capability and Engine State Registry."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.registry import CAPABILITY_STATUS_VOCABULARY, list_capabilities, get_capability
from apps.api.database.connection import get_db

class TestCapabilityRegistry(unittest.TestCase):
    def setUp(self):
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

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_capabilities_api_endpoint(self):
        """Querying /api/v1/system/capabilities returns full capability registry with valid status vocabulary."""
        headers = {"authorization": f"Bearer {self.token}"}
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/system/capabilities", headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        
        self.assertIn("capabilities", data)
        capabilities = data["capabilities"]
        self.assertGreaterEqual(len(capabilities), 14)

        for cap in capabilities:
            self.assertIn("engine_id", cap)
            self.assertIn("name", cap)
            self.assertIn("status", cap)
            self.assertIn(cap["status"], CAPABILITY_STATUS_VOCABULARY, f"Invalid status {cap['status']} on {cap['engine_id']}")

    def test_future_clinical_engines_are_strictly_not_implemented(self):
        """Future clinical modules must be flagged strictly as NOT_IMPLEMENTED with is_enabled=0 in Phase 1."""
        future_engines = [
            "clinical.consultation",
            "clinical.unani_mizaj",
            "clinical.prescriptions_nuskha",
            "clinical.safety_preflight",
            "operations.dispensary",
            "operations.followups",
            "integration.abdm",
            "ai.scribe",
            "hospital.ipd"
        ]
        headers = {"authorization": f"Bearer {self.token}"}
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/system/capabilities", headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        data = json.loads(resp_bytes.decode("utf-8"))
        cap_map = {c["engine_id"]: c for c in data["capabilities"]}

        for eng_id in future_engines:
            self.assertIn(eng_id, cap_map, f"Future engine {eng_id} not registered")
            self.assertEqual(cap_map[eng_id]["status"], "NOT_IMPLEMENTED")
            self.assertEqual(cap_map[eng_id]["is_enabled"], 0)
            self.assertIsNotNone(cap_map[eng_id]["health_reason"])

    def test_phase1_foundation_engines_are_functionally_tested(self):
        """Phase 1 foundation engines must be marked FUNCTIONALLY_TESTED and enabled."""
        foundation_engines = [
            "core.identity",
            "core.tenancy",
            "core.rbac",
            "core.audit",
            "core.capabilities"
        ]
        headers = {"authorization": f"Bearer {self.token}"}
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/system/capabilities", headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        data = json.loads(resp_bytes.decode("utf-8"))
        cap_map = {c["engine_id"]: c for c in data["capabilities"]}

        for eng_id in foundation_engines:
            self.assertIn(eng_id, cap_map, f"Foundation engine {eng_id} not registered")
            self.assertEqual(cap_map[eng_id]["status"], "FUNCTIONALLY_TESTED")
            self.assertEqual(cap_map[eng_id]["is_enabled"], 1)

    def test_unregistered_engine_returns_not_implemented(self):
        """Querying an unknown capability via get_capability returns NOT_IMPLEMENTED."""
        with get_db(self.db_path) as conn:
            cap = get_capability(conn, "future.telemedicine_video")
            self.assertEqual(cap["status"], "NOT_IMPLEMENTED")
            self.assertEqual(cap["is_enabled"], 0)

if __name__ == "__main__":
    unittest.main()

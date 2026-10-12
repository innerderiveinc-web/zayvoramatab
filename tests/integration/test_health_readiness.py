"""Integration Tests: Health and Readiness Probes."""

import unittest
import os
import tempfile
import json
import sqlite3
from apps.api.database.migrator import run_migrations
from apps.api.router import ApiRouter
from apps.api.config import config

class TestHealthReadiness(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_liveness_probe_always_succeeds(self):
        """Liveness probe confirms web process is alive regardless of DB state."""
        status, headers, resp_bytes = ApiRouter.dispatch(
            "GET", "/api/v1/health/live", {"x-request-id": "req-live-123"}, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Request-Id"], "req-live-123")
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(data.get("status"), "LIVE")
        self.assertEqual(data.get("service"), "ZAYVORA MATAB OS API")
        self.assertIn("uptime_seconds", data)

    def test_readiness_probe_fails_on_unmigrated_database(self):
        """Readiness probe returns 503 NOT_READY if schema migrations are missing."""
        # Database file exists but has no tables or migrations
        status, headers, resp_bytes = ApiRouter.dispatch(
            "GET", "/api/v1/health/ready", {}, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 503)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(data.get("status"), "NOT_READY")
        self.assertTrue(len(data.get("issues", [])) > 0)

    def test_readiness_probe_succeeds_when_migrations_applied(self):
        """Readiness probe returns 200 READY when schema migrations are up to date."""
        run_migrations(self.db_path)
        status, headers, resp_bytes = ApiRouter.dispatch(
            "GET", "/api/v1/health/ready", {}, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(data.get("status"), "READY")
        self.assertTrue(data.get("database_connected"))
        self.assertGreaterEqual(data.get("migrations_applied"), 1)
        self.assertEqual(data.get("environment"), config.env)

if __name__ == "__main__":
    unittest.main()

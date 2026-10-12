"""Unit and Integration Tests: Feature and Engine Capability Registry."""

import unittest
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.core.registry import get_all_capabilities, get_capability_status, assert_capability_ready, CapabilityUnavailableError

class TestFeatureRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_all_capabilities_retrieval(self):
        conn = self.db_manager.get_connection()
        try:
            caps = get_all_capabilities(conn)
            self.assertTrue(len(caps) >= 15)
            engine_ids = [c["engine_id"] for c in caps]
            self.assertIn("prescriptions.safety", engine_ids)
            self.assertIn("unani.assessment", engine_ids)
            self.assertIn("ai.scribe", engine_ids)
        finally:
            conn.close()

    def test_capability_readiness_assertions(self):
        conn = self.db_manager.get_connection()
        try:
            # prescriptions.safety is FUNCTIONALLY_TESTED -> meets FUNCTIONALLY_TESTED requirement
            assert_capability_ready(conn, "prescriptions.safety", "FUNCTIONALLY_TESTED")

            # ai.scribe is NOT_IMPLEMENTED -> must raise CapabilityUnavailableError
            with self.assertRaises(CapabilityUnavailableError):
                assert_capability_ready(conn, "ai.scribe", "FUNCTIONALLY_TESTED")
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()

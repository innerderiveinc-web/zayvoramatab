"""Unit and Integration Tests: Tamper-Evident Chained Audit Logging."""

import unittest
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.core.audit import record_audit_event, verify_audit_chain

class TestAuditTamperEvidence(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_chained_audit_integrity_verification(self):
        conn = self.db_manager.get_connection()
        try:
            org_id = "org-matab-default"
            # Record 5 sequential audit events
            for i in range(5):
                record_audit_event(
                    conn=conn,
                    organization_id=org_id,
                    action_type=f"CLINICAL_ACTION_{i}",
                    resource_type="ENCOUNTER",
                    resource_id=f"enc-{i}",
                    actor_id="usr-hakeem-1",
                    details={"step": i, "note": "Verified clinical charting"}
                )
            conn.commit()

            # Verify unbroken chain
            report = verify_audit_chain(conn, org_id)
            self.assertTrue(report["verified"])
            self.assertEqual(report["count"], 5)
        finally:
            conn.close()

    def test_tampering_detection_breaks_chain(self):
        conn = self.db_manager.get_connection()
        try:
            org_id = "org-matab-default"
            # Record events
            for i in range(3):
                record_audit_event(
                    conn=conn,
                    organization_id=org_id,
                    action_type=f"EVENT_{i}",
                    resource_type="PRESCRIPTION",
                    resource_id=f"pr-{i}",
                    actor_id="usr-hakeem-1"
                )
            conn.commit()

            # Maliciously modify the details of the second event directly in database
            conn.execute("""
                UPDATE audit_events 
                SET details = '{"malicious_tamper": true}' 
                WHERE action_type = 'EVENT_1';
            """)
            conn.commit()

            # Chained verification MUST fail
            report = verify_audit_chain(conn, org_id)
            self.assertFalse(report["verified"])
            self.assertIn("reason", report)
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()

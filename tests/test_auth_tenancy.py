"""Unit and Integration Tests: Authentication, Security, and Multi-Tenant Isolation."""

import unittest
import sqlite3
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.core.security import hash_password, verify_password, create_session, validate_session
from matab.core.errors import AuthenticationError
from matab.domains.identity import IdentityService
from matab.domains.patients import PatientService

class TestAuthAndTenancy(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_password_hashing_and_verification(self):
        raw_pw = "HakimSecretPass#2026"
        hashed = hash_password(raw_pw)
        self.assertTrue(hashed.startswith("pbkdf2:sha256:"))
        self.assertTrue(verify_password(raw_pw, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_successful_login_and_session_validation(self):
        conn = self.db_manager.get_connection()
        try:
            # Login as default seeded Hakeem Tariq
            result = IdentityService.authenticate(conn, "hakeem", "matab123")
            self.assertIn("token", result)
            self.assertEqual(result["user"]["username"], "hakeem")
            self.assertEqual(result["user"]["role"], "HAKEEM")

            # Validate the issued session token
            session_ctx = validate_session(conn, result["token"])
            self.assertEqual(session_ctx["username"], "hakeem")
            self.assertEqual(session_ctx["org_code"], "ZMD-001")
        finally:
            conn.close()

    def test_invalid_login_rejection(self):
        conn = self.db_manager.get_connection()
        try:
            with self.assertRaises(AuthenticationError):
                IdentityService.authenticate(conn, "hakeem", "IncorrectPassword123")
            with self.assertRaises(AuthenticationError):
                IdentityService.authenticate(conn, "non_existent_user", "matab123")
        finally:
            conn.close()

    def test_multi_tenant_isolation(self):
        """Verify strict tenant isolation: Organization A cannot read patients from Organization B."""
        conn = self.db_manager.get_connection()
        try:
            # Create a second distinct organization B
            conn.execute("""
                INSERT INTO organizations (id, name, code, profile_type)
                VALUES ('org-b-hospital', 'Al-Shifa Unani Hospital', 'ASH-002', 'HOSPITAL');
            """)
            conn.commit()

            # Create patient in Org A
            patient_a = PatientService.create_patient(
                conn=conn,
                organization_id="org-matab-default",
                data={"first_name": "Zaid", "phone": "+91-9998881111", "gender": "MALE"},
                actor_id="usr-hakeem-1"
            )

            # Create patient in Org B
            patient_b = PatientService.create_patient(
                conn=conn,
                organization_id="org-b-hospital",
                data={"first_name": "Bakr", "phone": "+91-9998882222", "gender": "MALE"},
                actor_id="usr-hakeem-1"
            )

            # Search from Org A scope
            results_org_a = PatientService.search_patients(conn, "org-matab-default", "Zaid")
            self.assertEqual(len(results_org_a), 1)
            self.assertEqual(results_org_a[0]["id"], patient_a["id"])

            # Ensure Org A search cannot see Org B's patient
            leaked = PatientService.search_patients(conn, "org-matab-default", "Bakr")
            self.assertEqual(len(leaked), 0)

            # Ensure Org B search cannot see Org A's patient
            leaked_b = PatientService.search_patients(conn, "org-b-hospital", "Zaid")
            self.assertEqual(len(leaked_b), 0)
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()

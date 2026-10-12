"""Integration Tests: Multi-Tenant Patient Data Isolation, IDOR Prevention, and RBAC Security."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import hash_password, reset_rate_limit_store
from apps.api.database.connection import get_db

class TestPatientTenancySecurity(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Provision secondary tenant: Organization B (Al-Shifa Healthcare)
        with get_db(self.db_path) as conn:
            conn.execute("""
                INSERT INTO organizations (id, name, code, profile_type, is_active)
                VALUES ('org-alt-clinic', 'Al-Shifa Healthcare', 'ALT-SHIFA', 'CLINIC', 1);
            """)
            conn.execute("""
                INSERT INTO facilities (id, organization_id, name, code, is_active)
                VALUES ('fac-alt-01', 'org-alt-clinic', 'Al-Shifa Branch', 'FAC-ALT-01', 1);
            """)
            pw_hash = hash_password("altpass123")
            conn.execute("""
                INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
                VALUES ('usr-alt-dr', 'org-alt-clinic', 'dr_alt', 'dr.alt@shifa.test', ?, 'Dr. Alternate', 1);
            """, (pw_hash,))
            conn.execute("""
                INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
                VALUES ('uom-alt-1', 'usr-alt-dr', 'org-alt-clinic', 'role-practitioner', 1);
            """)
            # Create Patient in Org B
            conn.execute("""
                INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, family_name, display_name, status, version)
                VALUES ('pat-alt-001', 'org-alt-clinic', 'fac-alt-01', 'MRN-ALT-001', 'Zayd', 'Farooq', 'Zayd Farooq [Synthetic]', 'ACTIVE', 1);
            """)
            conn.execute("""
                INSERT INTO patient_contacts (id, patient_id, organization_id, contact_type, contact_value, normalized_value, is_preferred)
                VALUES ('cnt-alt-01', 'pat-alt-001', 'org-alt-clinic', 'PHONE', '+919877766655', '9877766655', 1);
            """)
            # Create Encounter in Org B
            conn.execute("""
                INSERT INTO encounters (id, organization_id, facility_id, patient_id, encounter_type, status, version, created_by)
                VALUES ('enc-alt-001', 'org-alt-clinic', 'fac-alt-01', 'pat-alt-001', 'OPD_VISIT', 'DRAFT', 1, 'usr-alt-dr');
            """)
            conn.commit()

        # Login as User A (Hakeem in Org A)
        login_body_a = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_a, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token_user_a = json.loads(resp.decode("utf-8"))["token"]
        self.headers_user_a = {"authorization": f"Bearer {self.token_user_a}"}

        # Login as Auditor (Read-only auditor in Org A)
        login_body_aud = json.dumps({"username": "auditor", "password": "matab123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_aud, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token_auditor = json.loads(resp.decode("utf-8"))["token"]
        self.headers_auditor = {"authorization": f"Bearer {self.token_auditor}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_unauthenticated_requests_blocked(self):
        """Unauthenticated requests to all patient and encounter endpoints return 401."""
        endpoints = [
            ("GET", "/api/v1/patients"),
            ("POST", "/api/v1/patients"),
            ("GET", "/api/v1/patients/pat-syn-001"),
            ("PATCH", "/api/v1/patients/pat-syn-001"),
            ("GET", "/api/v1/patients/pat-syn-001/timeline"),
            ("POST", "/api/v1/patients/pat-syn-001/encounters"),
            ("GET", "/api/v1/encounters/enc-syn-001"),
            ("POST", "/api/v1/encounters/enc-syn-001/transition"),
        ]
        for method, path in endpoints:
            status, _, resp = ApiRouter.dispatch(method, path, {}, {}, b"", "127.0.0.1", db_path=self.db_path)
            self.assertEqual(status, 401, f"Expected 401 for unauthenticated {method} {path}")

    def test_cross_tenant_patient_isolation(self):
        """User A in Organization A cannot see, read, or modify Patient in Organization B."""
        # 1. Search in Org A does not include Patient in Org B
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients", self.headers_user_a, {"q": "Zayd Farooq"}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp.decode("utf-8"))
        self.assertEqual(data["total"], 0)

        # 2. Direct IDOR lookup for foreign patient returns 404 NOT_FOUND
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients/pat-alt-001", self.headers_user_a, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 404)

        # 3. Direct update attempt returns 404 NOT_FOUND
        upd_body = json.dumps({"version": 1, "given_name": "Tampered"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("PATCH", "/api/v1/patients/pat-alt-001", self.headers_user_a, {}, upd_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 404)

        # 4. Attempt to create encounter for foreign patient returns 404 NOT_FOUND
        enc_body = json.dumps({"facility_id": "fac-central-opd", "encounter_type": "OPD_VISIT"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-alt-001/encounters", self.headers_user_a, {}, enc_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 404)

    def test_cross_tenant_encounter_isolation(self):
        """User A in Organization A cannot read or transition Encounter in Organization B."""
        # 1. Direct GET of encounter in Org B returns 404 NOT_FOUND
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/encounters/enc-alt-001", self.headers_user_a, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 404)

        # 2. Direct transition attempt returns 404 NOT_FOUND
        trans_body = json.dumps({"status": "IN_PROGRESS", "version": 1}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/encounters/enc-alt-001/transition", self.headers_user_a, {}, trans_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 404)

    def test_role_permission_denials(self):
        """Read-only auditor cannot create patients, update demographics, or transition encounters."""
        # 1. Auditor attempting patient creation is blocked with 403
        reg_body = json.dumps({"given_name": "Test", "phone": "+919800000000", "sex": "MALE"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients", self.headers_auditor, {}, reg_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 403)
        err = json.loads(resp.decode("utf-8"))
        self.assertEqual(err["code"], "FORBIDDEN")

        # 2. Auditor attempting demographic update is blocked with 403
        upd_body = json.dumps({"version": 1, "given_name": "Tamper"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("PATCH", "/api/v1/patients/pat-syn-001", self.headers_auditor, {}, upd_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 403)

        # 3. Auditor attempting encounter creation is blocked with 403
        enc_body = json.dumps({"facility_id": "fac-central-opd", "encounter_type": "OPD_VISIT"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-001/encounters", self.headers_auditor, {}, enc_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 403)

if __name__ == "__main__":
    unittest.main()

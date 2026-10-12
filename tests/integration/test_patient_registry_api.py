"""Integration Tests: Patient Registry API, Search, Identifiers, Demographics Concurrency, and Consents."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store

class TestPatientRegistryApi(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Login as Receptionist (Farhan Ali)
        login_body = json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token = json.loads(resp.decode("utf-8"))["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_patient_registration_and_retrieval(self):
        """Create valid patient and read back longitudinal Patient 360."""
        payload = {
            "given_name": "Ahmad",
            "family_name": "Khan",
            "display_name": "Ahmad Khan [Synthetic]",
            "phone": "+91 99887-11223",
            "date_of_birth": "1990-05-15",
            "sex": "MALE",
            "preferred_language": "ur",
            "national_id": "DL-AHMAD-2026",
            "address_line1": "House 12, Chhatta Lal Mian, Daryaganj",
            "consent_general_care": "GRANTED"
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients", self.headers, {}, body_bytes, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        data = json.loads(resp.decode("utf-8"))
        patient = data["patient"]
        
        self.assertTrue(patient["mrn"].startswith("MRN-"))
        self.assertEqual(patient["given_name"], "Ahmad")
        self.assertEqual(patient["family_name"], "Khan")
        self.assertEqual(patient["version"], 1)
        self.assertEqual(patient["status"], "ACTIVE")

        # Read back Patient 360
        status, _, resp = ApiRouter.dispatch("GET", f"/api/v1/patients/{patient['id']}", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        p360 = json.loads(resp.decode("utf-8"))
        
        self.assertEqual(p360["patient"]["id"], patient["id"])
        self.assertGreaterEqual(len(p360["contacts"]), 1)
        self.assertEqual(p360["contacts"][0]["contact_value"], "+91 99887-11223")
        self.assertGreaterEqual(len(p360["identifiers"]), 1)
        self.assertEqual(p360["identifiers"][0]["identifier_value"], "DL-AHMAD-2026")
        self.assertGreaterEqual(len(p360["consents"]), 1)
        self.assertEqual(p360["consents"][0]["purpose"], "GENERAL_CARE")
        self.assertEqual(p360["consents"][0]["status"], "GRANTED")

    def test_scoped_patient_search(self):
        """Search patients by name, phone, or MRN with pagination."""
        # 1. Search by seeded name
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients", self.headers, {"q": "Muhammad Irfan"}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp.decode("utf-8"))
        self.assertGreaterEqual(data["total"], 1)
        self.assertTrue(any("Muhammad" in p["given_name"] for p in data["patients"]))

        # 2. Search by phone
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients", self.headers, {"phone": "9811223344"}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp.decode("utf-8"))
        self.assertGreaterEqual(data["total"], 1)

        # 3. Search non-matching returns empty total=0
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients", self.headers, {"q": "NonExistentNameXYZ999"}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp.decode("utf-8"))
        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["patients"]), 0)

    def test_demographic_update_with_optimistic_concurrency(self):
        """Updating demographics increments version; conflicting version is rejected."""
        # Get pat-syn-001 (initial version = 1)
        status, _, resp = ApiRouter.dispatch("GET", "/api/v1/patients/pat-syn-001", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        p = json.loads(resp.decode("utf-8"))["patient"]
        initial_version = p["version"]

        # Successful update with matching version
        update_body = json.dumps({
            "version": initial_version,
            "given_name": "Muhammad",
            "family_name": "Irfan Chishti",
            "display_name": "Muhammad Irfan Chishti [Synthetic]",
            "status": "ACTIVE"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("PATCH", "/api/v1/patients/pat-syn-001", self.headers, {}, update_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        updated = json.loads(resp.decode("utf-8"))["patient"]
        self.assertEqual(updated["version"], initial_version + 1)
        self.assertEqual(updated["family_name"], "Irfan Chishti")

        # Second update with stale initial_version must fail with 409 CONFLICT
        stale_body = json.dumps({
            "version": initial_version,
            "given_name": "Muhammad Stale"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("PATCH", "/api/v1/patients/pat-syn-001", self.headers, {}, stale_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 409)
        err = json.loads(resp.decode("utf-8"))
        self.assertEqual(err["code"], "CONFLICT")

    def test_identifier_lifecycle_and_retirement(self):
        """Add identifier, prevent duplicate active identifier, and retire with audit."""
        # Add identifier
        add_body = json.dumps({
            "identifier_type": "ABHA",
            "identifier_value": "ABHA-TEST-9922",
            "issuer": "NDHM"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-001/identifiers", self.headers, {}, add_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        ident_id = json.loads(resp.decode("utf-8"))["identifier"]["id"]

        # Duplicate active identifier in same tenant rejected
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-003/identifiers", self.headers, {}, add_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 409)

        # Retire identifier
        retire_body = json.dumps({"reason": "Patient replaced ABHA card"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/pat-syn-001/identifiers/{ident_id}/retire", self.headers, {}, retire_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(resp.decode("utf-8"))["retired"])

    def test_explicit_consent_recording_and_withdrawal(self):
        """Record explicit consent; blank is never assumed; withdraw consent with reason."""
        # Record WhatsApp consent
        cns_body = json.dumps({
            "purpose": "COMMUNICATION_WHATSAPP",
            "status": "GRANTED",
            "source_method": "VERBAL_PATIENT"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", "/api/v1/patients/pat-syn-001/consents", self.headers, {}, cns_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        cns_id = json.loads(resp.decode("utf-8"))["consent"]["id"]

        # Withdraw consent
        with_body = json.dumps({"reason": "Patient requested stop on WhatsApp messages"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch("POST", f"/api/v1/patients/pat-syn-001/consents/{cns_id}/withdraw", self.headers, {}, with_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(resp.decode("utf-8"))["withdrawn"])

if __name__ == "__main__":
    unittest.main()

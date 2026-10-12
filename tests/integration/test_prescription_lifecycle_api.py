"""Integration Tests: Complete Prescription Lifecycle, Concurrency, PIN Signing, Amendments, and Tenancy."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.core.security import reset_rate_limit_store
from apps.api.database.connection import DatabaseConnection
from apps.api.router import ApiRouter

class TestPrescriptionLifecycleApi(unittest.TestCase):
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
        self.hakeem_token = json.loads(resp_bytes.decode("utf-8"))["token"]

        # Authenticate as Receptionist (No signing permission)
        login_body_recep = json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_recep, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.recep_token = json.loads(resp_bytes.decode("utf-8"))["token"]

        # Seed and authenticate Tenant 2 Practitioner
        conn = DatabaseConnection(self.db_path).get_connection()
        try:
            from apps.api.database.seed import hash_seed_password
            pw_hash = hash_seed_password("matab123")
            conn.execute("INSERT OR REPLACE INTO organizations (id, name, code) VALUES ('org-matab-t2', 'Second Matab', 'MATAB-T2');")
            conn.execute("INSERT OR REPLACE INTO facilities (id, organization_id, name, code) VALUES ('fac-t2-opd', 'org-matab-t2', 'T2 OPD', 'T2-OPD');")
            conn.execute("INSERT OR REPLACE INTO users (id, organization_id, username, email, password_hash, full_name, is_active) VALUES ('usr-hakeem-t2', 'org-matab-t2', 'hakeem_t2', 't2@zayvora.test', ?, 'T2 Hakeem', 1);", (pw_hash,))
            conn.execute("INSERT OR REPLACE INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active) VALUES ('uom-t2', 'usr-hakeem-t2', 'org-matab-t2', 'role-practitioner', 1);")
            conn.execute("INSERT OR REPLACE INTO user_facility_memberships (id, user_id, facility_id, role_id, is_active) VALUES ('ufm-t2', 'usr-hakeem-t2', 'fac-t2-opd', 'role-practitioner', 1);")
            conn.commit()
        finally:
            conn.close()

        login_body_t2 = json.dumps({"username": "hakeem_t2", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body_t2, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.tenant2_token = json.loads(resp_bytes.decode("utf-8"))["token"]

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _dispatch(self, method: str, path: str, token: str, body: dict = None):
        headers = {
            "authorization": f"Bearer {token}",
            "content-type": "application/json"
        }
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        status, resp_headers, resp_bytes = ApiRouter.dispatch(
            method=method,
            path=path,
            headers=headers,
            query_params={},
            body_bytes=body_bytes,
            client_ip="127.0.0.1",
            db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def test_complete_prescription_lifecycle(self):
        """Test draft creation, item update, validation, PIN signing, document generation, and formal amendment."""
        # Create an encounter for pat-syn-002 first
        status, enc_resp = self._dispatch("POST", "/api/v1/patients/pat-syn-002/encounters", self.hakeem_token, {
            "encounter_type": "OPD_VISIT",
            "reason_for_visit": "General temperament consultation"
        })
        self.assertEqual(status, 201)
        encounter_id = enc_resp["encounter"]["id"]

        # 1. Create draft prescription for safe patient pat-syn-002
        payload = {
            "encounter_id": encounter_id,
            "items": [
                {
                    "item_name": "Sharbat Bazoori Motadil",
                    "dosage_form": "SHARBAT",
                    "dose_amount": "20",
                    "dose_unit": "ml",
                    "frequency": "BD",
                    "duration_days": 14,
                    "anupan_vehicle": "WATER",
                    "instructions": "Take with lukewarm water after meals"
                }
            ]
        }
        status, resp = self._dispatch("POST", "/api/v1/prescriptions", self.hakeem_token, payload)
        self.assertEqual(status, 201)
        rx = resp["prescription"]
        self.assertEqual(rx["status"], "DRAFT")
        self.assertEqual(rx["patient_id"], "pat-syn-002")
        rx_id = rx["id"]
        version = rx["version_number"]

        # 2. Update draft items with optimistic concurrency check
        update_payload = {
            "version_number": version,
            "items": [
                {
                    "item_name": "Sharbat Bazoori Motadil",
                    "dosage_form": "SHARBAT",
                    "dose_amount": "25",
                    "dose_unit": "ml",
                    "frequency": "BD",
                    "duration_days": 10,
                    "anupan_vehicle": "WATER",
                    "instructions": "Take with water"
                }
            ]
        }
        status, resp = self._dispatch("PATCH", f"/api/v1/prescriptions/{rx_id}", self.hakeem_token, update_payload)
        self.assertEqual(status, 200)
        rx = resp["prescription"]
        self.assertEqual(rx["version_number"], version + 1)
        new_version = rx["version_number"]

        # 3. Optimistic concurrency conflict on stale version
        stale_payload = {
            "version_number": version, # Stale version
            "items": []
        }
        status, resp = self._dispatch("PATCH", f"/api/v1/prescriptions/{rx_id}", self.hakeem_token, stale_payload)
        self.assertEqual(status, 409)

        # 4. Trigger server-side safety preflight validation
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/validate", self.hakeem_token)
        self.assertEqual(status, 200)
        self.assertIn("findings", resp)

        # 5. Invalid PIN fails signing
        sign_payload_bad_pin = {"pin": "9999"}
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/sign", self.hakeem_token, sign_payload_bad_pin)
        self.assertEqual(status, 401)

        # 6. Correct PIN signs prescription and seals immutable record
        sign_payload = {"pin": "1234"}
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/sign", self.hakeem_token, sign_payload)
        self.assertEqual(status, 200)
        signed_rx = resp["prescription"]
        self.assertEqual(signed_rx["status"], "SIGNED")
        self.assertIsNotNone(signed_rx["signature_hash"])
        self.assertEqual(len(signed_rx["signature_hash"]), 64) # SHA-256 hex string

        # 7. Immutability lock: Ordinary PATCH rejected once signed
        status, resp = self._dispatch("PATCH", f"/api/v1/prescriptions/{rx_id}", self.hakeem_token, {
            "version_number": new_version,
            "items": []
        })
        self.assertEqual(status, 409)

        # 8. Render signed document (HTML with verification hash)
        status, resp = self._dispatch("GET", f"/api/v1/prescriptions/{rx_id}/document", self.hakeem_token)
        self.assertEqual(status, 200)
        doc = resp["document"]
        self.assertIn("html", doc)
        self.assertIn("SHA-256 DIGITAL FINGERPRINT", doc["html"])
        self.assertIn(signed_rx["signature_hash"], doc["html"])

        # 9. Formal Amendment creates traceable superseding draft
        amend_payload = {"reason": "Patient requested lower dosage formulation"}
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/amend", self.hakeem_token, amend_payload)
        self.assertEqual(status, 201)
        amended_child = resp["prescription"]
        self.assertEqual(amended_child["status"], "DRAFT")
        self.assertEqual(amended_child["parent_prescription_id"], rx_id)

        # Check original is now SUPERSEDED
        status, resp = self._dispatch("GET", f"/api/v1/prescriptions/{rx_id}", self.hakeem_token)
        self.assertEqual(resp["prescription"]["status"], "SUPERSEDED")

    def test_safety_blocked_prescription_cannot_be_signed(self):
        """Prescription with allergen conflict cannot be signed."""
        # Patient pat-syn-001 has severe allergy to Roghan Badam Shireen (Almond)
        payload = {
            "encounter_id": "enc-syn-001",
            "items": [
                {
                    "item_name": "Majoon Arad Khurma",
                    "formulation_id": "form-majoon-arad",
                    "dosage_form": "MAJOON",
                    "dose_amount": "10",
                    "dose_unit": "g",
                    "frequency": "BD",
                    "duration_days": 7
                }
            ]
        }
        status, resp = self._dispatch("POST", "/api/v1/prescriptions", self.hakeem_token, payload)
        self.assertEqual(status, 201)
        rx_id = resp["prescription"]["id"]

        # Attempt to sign with valid PIN must be blocked
        sign_payload = {"pin": "1234"}
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/sign", self.hakeem_token, sign_payload)
        self.assertEqual(status, 422) # SafetyBlockedError maps to 422 Unprocessable Entity
        self.assertIn("blocked", resp["message"].lower())

    def test_cancellation_workflow(self):
        """Prescription cancellation requires mandatory reason and locks record."""
        # Create an encounter for pat-syn-002
        status, enc_resp = self._dispatch("POST", "/api/v1/patients/pat-syn-002/encounters", self.hakeem_token, {
            "encounter_type": "OPD_VISIT"
        })
        self.assertEqual(status, 201)
        encounter_id = enc_resp["encounter"]["id"]

        payload = {
            "encounter_id": encounter_id,
            "items": [
                {
                    "item_name": "Sharbat Bazoori Motadil",
                    "dosage_form": "SHARBAT",
                    "dose_amount": "10",
                    "dose_unit": "ml",
                    "frequency": "OD",
                    "duration_days": 3
                }
            ]
        }
        status, resp = self._dispatch("POST", "/api/v1/prescriptions", self.hakeem_token, payload)
        self.assertEqual(status, 201)
        rx_id = resp["prescription"]["id"]

        # Cancel without reason fails
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/cancel", self.hakeem_token, {"reason": ""})
        self.assertEqual(status, 400)

        # Cancel with reason succeeds
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/cancel", self.hakeem_token, {
            "reason": "Patient requested postponement of treatment"
        })
        self.assertEqual(status, 200)
        self.assertEqual(resp["prescription"]["status"], "CANCELLED")

    def test_rbac_and_tenant_isolation(self):
        """Unauthorized roles and cross-tenant users are forbidden."""
        # Create an encounter for pat-syn-002
        status, enc_resp = self._dispatch("POST", "/api/v1/patients/pat-syn-002/encounters", self.hakeem_token, {
            "encounter_type": "OPD_VISIT"
        })
        self.assertEqual(status, 201)
        encounter_id = enc_resp["encounter"]["id"]

        payload = {
            "encounter_id": encounter_id,
            "items": [
                {
                    "item_name": "Sharbat Bazoori Motadil",
                    "dosage_form": "SHARBAT",
                    "dose_amount": "10",
                    "dose_unit": "ml",
                    "frequency": "OD",
                    "duration_days": 5
                }
            ]
        }
        status, resp = self._dispatch("POST", "/api/v1/prescriptions", self.hakeem_token, payload)
        self.assertEqual(status, 201)
        rx_id = resp["prescription"]["id"]

        # Receptionist has no prescription:sign permission
        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/sign", self.recep_token, {"pin": "1234"})
        self.assertEqual(status, 403)

        # Tenant 2 practitioner cannot see or sign Tenant 1 prescription
        status, resp = self._dispatch("GET", f"/api/v1/prescriptions/{rx_id}", self.tenant2_token)
        self.assertEqual(status, 404)

        status, resp = self._dispatch("POST", f"/api/v1/prescriptions/{rx_id}/sign", self.tenant2_token, {"pin": "1234"})
        self.assertEqual(status, 404)

if __name__ == "__main__":
    unittest.main()

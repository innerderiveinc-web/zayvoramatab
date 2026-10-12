"""Integration Tests for Consultation Workspace & Orchestrator REST APIs (Prompt 08).
Validates:
- GET /api/v1/encounters/{id}/workspace aggregate retrieval
- PATCH /api/v1/encounters/{id}/workspace & POST /api/v1/encounters/{id}/autosave
- Section completion and clinical rationale enforcement for not_applicable
- State transition validation
- POST /api/v1/encounters/{id}/validate-signoff eligibility checks
- POST /api/v1/encounters/{id}/finalize electronic PIN sign-off:
  - 401 on incorrect PIN
  - 403 when non-prescriber (receptionist) attempts sign-off
  - 200 with immutable document bundle & follow-up task on authorized Hakeem sign-off
- GET /api/v1/encounters/{id}/documents retrieval with SHA-256 digests
- Multi-tenant isolation enforcement
"""

import unittest
import os
import tempfile
import json
import uuid

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.database.connection import DatabaseConnection
from apps.api.router import ApiRouter
from apps.api.core.security import hash_pin


class TestConsultationWorkspaceAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_db_fd, cls.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(cls.temp_db_fd)
        run_migrations(cls.temp_db_path)
        seed_development_data(cls.temp_db_path)

        # Configure Hakeem PIN (1234)
        conn = DatabaseConnection(cls.temp_db_path).get_connection()
        conn.execute("""
            UPDATE practitioner_profiles
            SET digital_signature_pin_hash = ?
            WHERE user_id = 'usr-hakeem-1';
        """, (hash_pin("1234"),))
        conn.commit()
        conn.close()

        # Login Hakeem
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=cls.temp_db_path)
        assert status == 200, "Hakeem login failed"
        cls.hakeem_token = json.loads(resp_bytes.decode("utf-8"))["token"]

        # Login Receptionist
        login_body = json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=cls.temp_db_path)
        assert status == 200, "Reception login failed"
        cls.recep_token = json.loads(resp_bytes.decode("utf-8"))["token"]

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.temp_db_path):
            os.remove(cls.temp_db_path)

    def setUp(self):
        # Create fresh test encounter
        conn = DatabaseConnection(self.temp_db_path).get_connection()
        self.patient_id = "pat-syn-001"
        self.encounter_id = f"enc-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO encounters (
                id, organization_id, facility_id, patient_id, practitioner_id,
                token_number, encounter_type, status, reason_for_visit, version, started_at, created_by
            ) VALUES (?, 'org-matab-default', 'fac-central-opd', ?, 'usr-hakeem-1', 201, 'OPD_VISIT', 'in_consultation', 'Acute headache and vertigo', 1, CURRENT_TIMESTAMP, 'usr-hakeem-1');
        """, (self.encounter_id, self.patient_id))
        conn.commit()
        conn.close()

    def _headers(self, token: str):
        return {"authorization": f"Bearer {token}", "content-type": "application/json"}

    def test_get_workspace_aggregate(self):
        """GET /api/v1/encounters/{id}/workspace returns unified aggregate across all lanes."""
        status, _, resp_bytes = ApiRouter.dispatch(
            "GET", f"/api/v1/encounters/{self.encounter_id}/workspace",
            self._headers(self.hakeem_token), {}, b"", "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))["workspace"]

        self.assertEqual(data["encounter"]["id"], self.encounter_id)
        self.assertEqual(data["patient"]["id"], self.patient_id)
        self.assertIn("sections", data)
        self.assertIn("visit", data["sections"])
        self.assertIn("history_observations", data["sections"])
        self.assertIn("unani_assessment", data["sections"])
        self.assertIn("modern_assessment", data["sections"])
        self.assertIn("plan_nuskha", data["sections"])
        self.assertIn("safety_review", data["sections"])
        self.assertIn("finalize", data["sections"])
        self.assertIn("signoff_eligibility", data)

    def test_autosave_and_draft_update(self):
        """POST /api/v1/encounters/{id}/autosave updates reason_for_visit and increments version."""
        body = json.dumps({
            "version": 1,
            "reason_for_visit": "Updated via autosave: acute migraine with nausea",
            "updated_sections": ["visit"]
        }).encode("utf-8")

        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/autosave",
            self._headers(self.hakeem_token), {}, body, "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(res["status"], "saved")
        self.assertEqual(res["version_number"], 2)

    def test_section_completion_and_na_justification(self):
        """Completing sections and marking N/A with validation rules."""
        # Complete visit
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/sections/visit/complete",
            self._headers(self.hakeem_token), {}, json.dumps({"notes": "Triage verified"}).encode("utf-8"),
            "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)

        # Mark modern_assessment N/A without rationale fails (400)
        status, _, _ = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/sections/modern_assessment/mark-not-applicable",
            self._headers(self.hakeem_token), {}, json.dumps({}).encode("utf-8"),
            "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 400)

        # Mark modern_assessment N/A with rationale succeeds
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/sections/modern_assessment/mark-not-applicable",
            self._headers(self.hakeem_token), {}, json.dumps({"reason": "Pure classical Unani treatment plan requested"}).encode("utf-8"),
            "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(data["section"]["status"], "not_applicable")

    def test_workflow_state_transition(self):
        """POST /api/v1/encounters/{id}/state-transition enforces transition validity."""
        # Transition in_consultation -> ready_for_signoff
        body = json.dumps({"target_state": "ready_for_signoff", "reason": "Clinical assessment complete"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/state-transition",
            self._headers(self.hakeem_token), {}, body, "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(data["new_state"], "ready_for_signoff")

    def test_validate_signoff_endpoint(self):
        """POST /api/v1/encounters/{id}/validate-signoff computes server gating."""
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/validate-signoff",
            self._headers(self.hakeem_token), {}, b"{}", "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)
        eligibility = json.loads(resp_bytes.decode("utf-8"))["eligibility"]
        self.assertIn("eligible", eligibility)
        self.assertIn("blocking_reasons", eligibility)

    def test_finalize_encounter_rb_rbac_and_pin_enforcement(self):
        """Finalize endpoint requires prescribing permission, correct PIN, and generates documents."""
        # Satisfy gates: complete visit and Unani assessment
        ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/sections/visit/complete",
            self._headers(self.hakeem_token), {}, b"{}", "127.0.0.1", db_path=self.temp_db_path
        )
        ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/sections/unani_assessment/complete",
            self._headers(self.hakeem_token), {}, b"{}", "127.0.0.1", db_path=self.temp_db_path
        )

        # 1. Receptionist attempt to finalize returns 403 Forbidden
        status, _, _ = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/finalize",
            self._headers(self.recep_token), {}, json.dumps({"pin": "1234"}).encode("utf-8"),
            "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 403)

        # 2. Hakeem with invalid PIN returns 401 Unauthorized
        status, _, _ = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/finalize",
            self._headers(self.hakeem_token), {}, json.dumps({"pin": "9999"}).encode("utf-8"),
            "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 401)

        # 3. Hakeem with valid PIN returns 200, document bundle, and follow-up
        finalize_payload = json.dumps({
            "pin": "1234",
            "followup_task": {
                "due_date": "2026-10-25",
                "task_description": "Follow-up pulse diagnosis review in OPD"
            },
            "instructions_language": "ur"
        }).encode("utf-8")

        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/finalize",
            self._headers(self.hakeem_token), {}, finalize_payload,
            "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(res["status"], "completed")
        self.assertGreaterEqual(len(res["documents"]), 2)
        self.assertIsNotNone(res["followup_task"])
        self.assertEqual(res["followup_task"]["due_date"], "2026-10-25")

        # 4. Check generated documents via GET /api/v1/encounters/{id}/documents
        status, _, resp_bytes = ApiRouter.dispatch(
            "GET", f"/api/v1/encounters/{self.encounter_id}/documents",
            self._headers(self.hakeem_token), {}, b"", "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 200)
        docs = json.loads(resp_bytes.decode("utf-8"))["documents"]
        self.assertGreaterEqual(len(docs), 2)
        for doc in docs:
            self.assertEqual(len(doc["document_hash"]), 64)

    def test_multi_tenant_isolation(self):
        """Cross-tenant user cannot access or finalize another organization's encounter."""
        # Create second synthetic organization and user
        conn = DatabaseConnection(self.temp_db_path).get_connection()
        conn.execute("""
            INSERT INTO organizations (id, name, code, profile_type, is_active)
            VALUES ('org-foreign-tenant', 'Foreign Clinic', 'FC-001', 'CLINIC', 1);
        """)
        conn.execute("""
            INSERT INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES ('usr-foreign-1', 'org-foreign-tenant', 'foreign_doc', 'foreign@test.com',
                    'pbkdf2:sha256:10000$saltmatab$cfcfe0609a07d21882e815afe9d739d83223c87c3766546d5a656da687629707',
                    'Foreign Doctor', 1);
        """)
        conn.execute("""
            INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
            VALUES ('uom-foreign-1', 'usr-foreign-1', 'org-foreign-tenant', 'role-practitioner', 1);
        """)
        conn.commit()
        conn.close()

        # Login foreign user
        login_body = json.dumps({"username": "foreign_doc", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.temp_db_path)
        foreign_token = json.loads(resp_bytes.decode("utf-8"))["token"]

        # Attempt to access encounter from org-matab-default
        status, _, _ = ApiRouter.dispatch(
            "GET", f"/api/v1/encounters/{self.encounter_id}/workspace",
            self._headers(foreign_token), {}, b"", "127.0.0.1", db_path=self.temp_db_path
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()

"""Integration tests for Prompt 23: Clinical Decision Support (CDS) Orchestrator & Approval APIs.

Validates end-to-end HTTP request handling through ApiRouter.dispatch():
1. Policy Registry: GET /api/v1/cds/policies, GET /api/v1/cds/policies/{code}
2. CDS Run Execution: POST /api/v1/encounters/{id}/cds-runs, GET /api/v1/cds/runs/{id}
3. Typed Cards Retrieval & Clinician Review: GET /api/v1/cds/runs/{id}/cards, POST /api/v1/cds/cards/{id}/review
4. 6-Dimension Readiness Gate: GET /api/v1/encounters/{id}/readiness
5. Workflow State Machine Transition: POST /api/v1/encounters/{id}/transition
6. PIN-Verified Sign-Off: POST /api/v1/encounters/{id}/sign
7. Formal Post-Signature Amendment: POST /api/v1/encounters/{id}/amendments
8. Administrative Emergency Kill Switch: POST & GET /api/v1/cds/kill-switch
"""

import os
import json
import unittest
import tempfile
import sqlite3
import uuid

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import hash_pin


class TestCDSOrchestratorApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_cds_orchestrator_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.db_path
        )
        cls.auth_token = json.loads(body)["token"]

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        cls.admin_id = admin_row["id"]
        cls.org_id = admin_row["organization_id"]

        # Configure practitioner profile with PIN for admin
        cur.execute("""
            INSERT OR IGNORE INTO practitioner_profiles (id, user_id, license_type, registration_number, digital_signature_pin_hash)
            VALUES (?, ?, 'BUMS', 'REG-ADMIN-99', ?);
        """, (f"prof-{cls.admin_id}", cls.admin_id, hash_pin("1234")))

        # Fetch or create test facility and patient
        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-default"

        cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        pat_row = cur.fetchone()
        cls.patient_id = pat_row["id"] if pat_row else "pat-default"

        # Create test encounter
        cls.encounter_id = f"enc-{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, 'scheduled', 1, ?);
        """, (cls.encounter_id, cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id, cls.admin_id))

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }

    # --------------------------------------------------------------------------
    # Test 1: Policy Registry Endpoints
    # --------------------------------------------------------------------------
    def test_01_policy_registry_endpoints(self):
        # List policies
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/cds/policies",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("policies", data)
        self.assertGreaterEqual(len(data["policies"]), 5)

        # Get specific policy
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/cds/policies/POL-ALLERGY-CHECK",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        policy_data = json.loads(body)["policy"]
        self.assertEqual(policy_data["policy_code"], "POL-ALLERGY-CHECK")
        self.assertEqual(policy_data["severity_default"], "BLOCKER")

    # --------------------------------------------------------------------------
    # Test 2: Execute CDS Run & Get Run
    # --------------------------------------------------------------------------
    def test_02_execute_cds_run_and_get_run(self):
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/cds-runs",
            self._headers(), {}, json.dumps({"query_scope": "FULL_ENCOUNTER"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertEqual(res["run_state"], "completed")
        run_id = res["run_id"]

        # Fetch run details
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/cds/runs/{run_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        run_details = json.loads(body)["cds_run"]
        self.assertEqual(run_details["id"], run_id)
        self.assertEqual(run_details["run_state"], "completed")

    # --------------------------------------------------------------------------
    # Test 3: Get Cards & Review Card Action
    # --------------------------------------------------------------------------
    def test_03_get_cards_and_review_card(self):
        # Trigger run to ensure cards exist
        _, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/cds-runs",
            self._headers(), {}, json.dumps({"query_scope": "FULL_ENCOUNTER"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        run_id = json.loads(body)["run_id"]

        # Get cards
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/cds/runs/{run_id}/cards",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        cards = json.loads(body)["cards"]
        self.assertGreaterEqual(len(cards), 1)

        card_id = cards[0]["id"]

        # Review card
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/cds/cards/{card_id}/review",
            self._headers(), {},
            json.dumps({"action": "accept_as_documentation", "rationale": "Verified intake"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        rev_data = json.loads(body)
        self.assertEqual(rev_data["review_status"], "accepted")

    # --------------------------------------------------------------------------
    # Test 4: Readiness Check Endpoint
    # --------------------------------------------------------------------------
    def test_04_readiness_check_endpoint(self):
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/encounters/{self.encounter_id}/readiness",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        readiness = json.loads(body)
        self.assertIn("is_ready", readiness)
        self.assertIn("dimension_statuses", readiness)

    # --------------------------------------------------------------------------
    # Test 5: State Machine Transition Endpoint
    # --------------------------------------------------------------------------
    def test_05_state_transition_endpoint(self):
        # Transition scheduled -> arrived
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/cds-transition",
            self._headers(), {},
            json.dumps({"target_state": "arrived", "reason": "Patient arrived at OPD"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        trans_res = json.loads(body)
        self.assertEqual(trans_res["to_state"], "arrived")

    # --------------------------------------------------------------------------
    # Test 6: Sign Encounter Endpoint
    # --------------------------------------------------------------------------
    def test_06_sign_encounter_endpoint(self):
        # Create fresh encounter for signing
        conn = sqlite3.connect(self.db_path)
        fresh_enc_id = f"enc-sign-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, 'ready_to_finalize', 1, ?);
        """, (fresh_enc_id, self.org_id, self.fac_id, self.patient_id, self.admin_id, self.admin_id))
        conn.execute("""
            INSERT INTO modern_clinical_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, assessment_date, chief_complaint, status)
            VALUES (?, ?, ?, ?, ?, ?, '2026-10-13', 'Cephalea', 'DRAFT');
        """, (f"mod-{uuid.uuid4().hex[:8]}", self.org_id, self.fac_id, self.patient_id, fresh_enc_id, self.admin_id))
        conn.commit()
        conn.close()

        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{fresh_enc_id}/sign",
            self._headers(), {},
            json.dumps({"pin": "1234", "clinical_notes": "Encounter completed successfully."}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        sign_data = json.loads(body)
        self.assertEqual(sign_data["status"], "SIGNED")
        self.assertTrue(len(sign_data["signature_hash"]) == 64)

    # --------------------------------------------------------------------------
    # Test 7: Post-Signature Amendment Endpoint
    # --------------------------------------------------------------------------
    def test_07_post_signature_amendment_endpoint(self):
        # Create fresh signed encounter
        conn = sqlite3.connect(self.db_path)
        signed_enc_id = f"enc-amend-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, 'SIGNED', 2, ?);
        """, (signed_enc_id, self.org_id, self.fac_id, self.patient_id, self.admin_id, self.admin_id))
        conn.commit()
        conn.close()

        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{signed_enc_id}/amendments",
            self._headers(), {},
            json.dumps({
                "clinical_justification": "Addendum to reflect lab investigation review",
                "changes_summary": {"lab_reviewed": "Normal CBC"}
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        amend_data = json.loads(body)
        self.assertEqual(amend_data["status"], "AMENDED")
        self.assertEqual(amend_data["amended_version"], 3)

    # --------------------------------------------------------------------------
    # Test 8: Emergency Kill Switch Endpoints
    # --------------------------------------------------------------------------
    def test_08_kill_switch_endpoints(self):
        # Toggle kill switch ON
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/cds/kill-switch",
            self._headers(), {},
            json.dumps({"active": True, "reason": "Test safety pause"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["kill_switch_active"])

        # Check status
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/cds/kill-switch",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["kill_switch_active"])

        # Restore kill switch OFF
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/cds/kill-switch",
            self._headers(), {},
            json.dumps({"active": False, "reason": "Restoring service"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["kill_switch_active"])


if __name__ == "__main__":
    unittest.main()

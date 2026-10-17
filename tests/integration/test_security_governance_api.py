"""Integration tests for Enterprise Security, Privacy, Consent & Access Governance REST APIs.

Phase 30 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Principal context resolution (GET /api/v1/security/me)
2. Session management & remote revocation (GET /api/v1/security/sessions, POST /api/v1/security/sessions/revoke)
3. Step-up elevation (POST /api/v1/security/step-up)
4. Clinician credential verification and suspension (POST /api/v1/security/credentials)
5. Purpose-specific consent capture and withdrawal (POST/GET /api/v1/security/consent-records)
6. Delegated access grants (POST /api/v1/security/delegations)
7. Emergency break-glass lifecycle and review (POST /api/v1/security/break-glass)
8. Periodic access review campaigns (POST /api/v1/security/access-reviews)
9. Versioned security policy evaluation (POST /api/v1/security/policies)
10. Audit coverage verification (GET /api/v1/security/audit/coverage)
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestSecurityGovernanceApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sec_gov_api.db")
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

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-default"

        cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        pat_row = cur.fetchone()
        cls.patient_id = pat_row["id"]

        # Insert user session into user_sessions table
        cls.session_id = f"sess-api-{uuid.uuid4().hex[:8]}"
        conn.execute(
            """
            INSERT INTO user_sessions (
                id, token, user_id, organization_id, active_facility_id, ip_address,
                expires_at, idle_timeout_at, is_revoked
            ) VALUES (?, ?, ?, ?, ?, '127.0.0.1', '2030-01-01', '2030-01-01', 0);
            """,
            (cls.session_id, cls.auth_token, cls.admin_id, cls.org_id, cls.fac_id),
        )
        conn.commit()
        conn.close()

    def _api(self, method: str, path: str, payload: dict = None, query_params: dict = None):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Facility-Id": self.fac_id,
        }
        body_bytes = json.dumps(payload).encode("utf-8") if payload else b""
        status, resp_headers, body = ApiRouter.dispatch(
            method, path, headers, query_params or {}, body_bytes, "127.0.0.1", self.db_path
        )
        return status, json.loads(body)

    def test_end_to_end_security_governance_api(self):
        # 1. GET /api/v1/security/me
        status, me = self._api("GET", "/api/v1/security/me")
        self.assertEqual(status, 200)
        self.assertEqual(me["principal_id"], self.admin_id)
        self.assertTrue(me["session_active"])

        # 2. GET /api/v1/security/sessions
        status, sess_res = self._api("GET", "/api/v1/security/sessions", query_params={"user_id": self.admin_id})
        self.assertEqual(status, 200)
        self.assertTrue(sess_res["total_sessions"] >= 1)

        # 3. POST /api/v1/security/step-up
        status, step_res = self._api("POST", "/api/v1/security/step-up", {
            "credential": "matab123",
            "scope": "AUDIT_MANAGEMENT"
        })
        self.assertEqual(status, 200)
        self.assertTrue(step_res["step_up_verified"])

        # 4. POST /api/v1/security/credentials
        status, cred = self._api("POST", "/api/v1/security/credentials", {
            "practitioner_user_id": self.admin_id,
            "credential_type": "BUMS",
            "registration_number": "UP-BUMS-API-2026",
            "issuing_council": "Central Council of Indian Medicine",
            "effective_date": "2021-01-01"
        })
        self.assertEqual(status, 201)
        cred_id = cred["id"]
        self.assertEqual(cred["verification_status"], "pending")

        # Verify credential
        status, ver_cred = self._api("POST", f"/api/v1/security/credentials/{cred_id}/verify", {
            "verification_source": "NATIONAL_COMMISSION_INDIAN_SYSTEM_MEDICINE"
        })
        self.assertEqual(status, 200)
        self.assertEqual(ver_cred["verification_status"], "verified")

        # Suspend credential
        status, susp_cred = self._api("POST", f"/api/v1/security/credentials/{cred_id}/suspend", {
            "reason": "Temporary administrative audit check"
        })
        self.assertEqual(status, 200)
        self.assertEqual(susp_cred["verification_status"], "suspended")

        # 5. POST /api/v1/security/consent-records
        status, cns = self._api("POST", "/api/v1/security/consent-records", {
            "patient_id": self.patient_id,
            "consent_type": "TREATMENT_GENERAL",
            "purpose_code": "IN_PERSON_OPD_CONSULTATION",
            "granting_party_type": "PATIENT_DIRECT"
        })
        self.assertEqual(status, 201)
        consent_id = cns["id"]
        self.assertEqual(cns["status"], "granted")

        # Query consents
        status, list_cns = self._api("GET", "/api/v1/security/consent-records", query_params={"patient_id": self.patient_id})
        self.assertEqual(status, 200)
        self.assertTrue(list_cns["total_records"] >= 1)

        # Withdraw consent
        status, with_cns = self._api("POST", f"/api/v1/security/consent-records/{consent_id}/withdraw", {
            "reason": "Patient requested withdrawal"
        })
        self.assertEqual(status, 200)
        self.assertEqual(with_cns["status"], "withdrawn")

        # 6. POST /api/v1/security/delegations
        status, dlg = self._api("POST", "/api/v1/security/delegations", {
            "delegatee_user_id": self.admin_id,
            "target_resource_type": "PATIENT",
            "target_resource_id": self.patient_id,
            "purpose": "Locum physician coverage",
            "expires_at": "2030-01-01T00:00:00"
        })
        self.assertEqual(status, 201)
        dlg_id = dlg["id"]
        self.assertEqual(dlg["status"], "ACTIVE")

        # Revoke delegation
        status, rev_dlg = self._api("POST", f"/api/v1/security/delegations/{dlg_id}/revoke", {
            "reason": "Coverage duty concluded"
        })
        self.assertEqual(status, 200)
        self.assertEqual(rev_dlg["status"], "REVOKED")

        # 7. POST /api/v1/security/break-glass
        status, bg = self._api("POST", "/api/v1/security/break-glass", {
            "patient_id": self.patient_id,
            "reason_code": "CRITICAL_ALLERGY_CHECK",
            "rationale": "Emergency acute anaphylaxis review, patient incapacitated",
            "duration_minutes": 30
        })
        self.assertEqual(status, 201)
        bg_id = bg["id"]
        self.assertEqual(bg["status"], "ACTIVE")

        # Get break-glass
        status, get_bg = self._api("GET", f"/api/v1/security/break-glass/{bg_id}")
        self.assertEqual(status, 200)
        self.assertEqual(get_bg["id"], bg_id)

        # Review break-glass
        status, rev_bg = self._api("POST", f"/api/v1/security/break-glass/{bg_id}/review", {
            "decision": "REVIEWED_JUSTIFIED",
            "notes": "Emergency physician attestation verified"
        })
        self.assertEqual(status, 200)
        self.assertEqual(rev_bg["status"], "REVIEWED_JUSTIFIED")

        # 8. POST /api/v1/security/access-reviews
        status, camp = self._api("POST", "/api/v1/security/access-reviews", {
            "campaign_code": f"CAMP-API-{uuid.uuid4().hex[:6].upper()}",
            "title": "Annual Enterprise Access Review",
            "scope_type": "CLINICAL_ROLES",
            "due_date": "2026-12-31"
        })
        self.assertEqual(status, 201)
        camp_id = camp["id"]

        # Record access decision
        status, dec = self._api("POST", f"/api/v1/security/access-reviews/{camp_id}/decisions", {
            "subject_user_id": self.admin_id,
            "role_or_permission": "ORG_ADMIN",
            "decision": "RETAIN",
            "rationale": "Primary system administrator identity confirmed"
        })
        self.assertEqual(status, 201)
        self.assertEqual(dec["decision"], "RETAIN")

        # 9. POST /api/v1/security/policies
        status, pol = self._api("POST", "/api/v1/security/policies", {
            "policy_code": f"POL-API-DENY-{uuid.uuid4().hex[:6].upper()}",
            "title": "Block Remote Access to Unanonymized Research Cohorts",
            "resource_type": "research_cohort",
            "action": "EXPORT_RAW_IDENTIFIERS",
            "effect": "DENY",
            "priority": 5,
            "reason_code": "PROHIBITED_UNMASKED_RESEARCH_EXPORT"
        })
        self.assertEqual(status, 201)

        # Evaluate policy
        status, eval_res = self._api("POST", "/api/v1/security/policies/evaluate", {
            "resource_type": "research_cohort",
            "action": "EXPORT_RAW_IDENTIFIERS"
        })
        self.assertEqual(status, 200)
        self.assertFalse(eval_res["allowed"])
        self.assertEqual(eval_res["reason_code"], "PROHIBITED_UNMASKED_RESEARCH_EXPORT")

        # 10. GET /api/v1/security/audit/coverage
        status, cov = self._api("GET", "/api/v1/security/audit/coverage")
        self.assertEqual(status, 200)
        self.assertEqual(cov["status"], "OPERATIONAL")
        self.assertTrue(cov["genesis_anchored"])


if __name__ == "__main__":
    unittest.main()

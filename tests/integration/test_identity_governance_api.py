"""Integration Tests for Enterprise Identity Governance, PAM & Access Certification APIs.

Phase 45 for ZAYVORA MATAB OS.
Tests all endpoints via ApiRouter.dispatch:
1. GET    /api/v1/identity/summary
2. GET    /api/v1/identity/principals & POST /api/v1/identity/principals (Joiner)
3. POST   /api/v1/identity/principals/:id/mover (Mover)
4. POST   /api/v1/identity/principals/:id/leaver (Leaver)
5. GET    /api/v1/identity/users/:id/effective-access
6. GET    /api/v1/identity/privileges
7. POST   /api/v1/identity/elevations & Approvals (JIT PAM with SoD)
8. POST   /api/v1/identity/break-glass & Action Firewall
9. GET    /api/v1/identity/service-accounts & POST /api/v1/identity/service-accounts
10. POST  /api/v1/identity/campaigns & Two-Phase Remediation (Applied & Verified)
11. GET    /api/v1/identity/sod-rules & POST /api/v1/identity/sod-rules/check
12. GET    /api/v1/identity/audit-ledger
"""

import os
import json
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestIdentityGovernanceApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_identity_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path
        )
        assert status == 200, f"Login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}"
        }

        # Authenticate Secondary Admin (Security Officer) for SoD approval tests
        import sqlite3
        conn = sqlite3.connect(cls.db_path)
        pw_hash = "pbkdf2:sha256:10000$saltmatab$cfcfe0609a07d21882e815afe9d739d83223c87c3766546d5a656da687629707"
        conn.execute("""
            INSERT OR REPLACE INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
            VALUES ('usr-admin-2', 'org-matab-default', 'sec_officer', 'sec.officer@zayvora.test', ?, 'Security Officer', 1);
        """, (pw_hash,))
        conn.execute("""
            INSERT OR REPLACE INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
            VALUES ('uom-sec-officer', 'usr-admin-2', 'org-matab-default', 'role-org-admin', 1);
        """)
        conn.commit()
        conn.close()

        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "sec_officer", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path
        )
        assert status == 200, f"Sec Officer login failed: {body}"
        sec_data = json.loads(body.decode("utf-8"))
        cls.sec_token = sec_data["token"]
        cls.sec_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.sec_token}"
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_identity_summary_api(self):
        """GET /api/v1/identity/summary returns executive KPI metrics."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/identity/summary", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        summary = data["summary"]
        self.assertGreaterEqual(summary["total_principals_count"], 7)
        self.assertGreaterEqual(summary["service_accounts_count"], 2)
        self.assertGreaterEqual(summary["toxic_sod_rules_count"], 5)

    def test_02_principals_joiner_and_get_api(self):
        """POST /api/v1/identity/principals (Joiner) & GET single principal."""
        joiner_payload = {
            "name": "Dr. Amina Farooq",
            "email": "amina.farooq@zayvora.test",
            "principal_type": "HUMAN",
            "roles": ["PRACTITIONER"]
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/identity/principals", self.admin_headers, {},
            json.dumps(joiner_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        p_id = data["principal"]["id"]

        # GET principal
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/identity/principals/{p_id}", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        p_data = json.loads(body.decode("utf-8"))
        self.assertEqual(p_data["principal"]["name"], "Dr. Amina Farooq")

    def test_03_mover_and_leaver_lifecycle_api(self):
        """POST /api/v1/identity/principals/:id/mover and /leaver endpoints."""
        # 1. Create a user to test mover and leaver
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/identity/principals", self.admin_headers, {},
            json.dumps({"name": "Test Mover User", "email": "mover@zayvora.test", "roles": ["RECEPTIONIST"]}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        p_id = json.loads(body.decode("utf-8"))["principal"]["id"]

        # 2. Mover transition
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/principals/{p_id}/mover", self.admin_headers, {},
            json.dumps({"target_facility_id": "fac-south-branch", "new_roles": ["CASHIER"]}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        mover_data = json.loads(body.decode("utf-8"))
        self.assertEqual(mover_data["mover"]["status"], "MOVER_COMPLETED")

        # 3. Leaver offboarding
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/principals/{p_id}/leaver", self.admin_headers, {},
            json.dumps({"reason": "Resignation"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        leaver_data = json.loads(body.decode("utf-8"))
        self.assertEqual(leaver_data["leaver"]["status"], "OFFBOARDED")
        self.assertTrue(leaver_data["leaver"]["revocation_verified"])

    def test_04_effective_access_api(self):
        """GET /api/v1/identity/users/:id/effective-access."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/identity/users/usr-hakeem-1/effective-access", self.admin_headers,
            {"permission": "prescriptions:sign"}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["effective_access"]["has_effective_access"])
        self.assertIn("PRACTITIONER", data["effective_access"]["roles"])

    def test_05_privileges_registry_api(self):
        """GET /api/v1/identity/privileges."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/identity/privileges", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(data["privileges"]), 5)

    def test_06_jit_elevation_workflow_and_sod_api(self):
        """POST /api/v1/identity/elevations with dual-custody approval and activation."""
        # 1. Request elevation
        elev_payload = {
            "privilege_key": "config:manage",
            "justification": "Modifying CORS whitelist for clinical pilot",
            "ticket_reference": "TICKET-77123",
            "duration_seconds": 1800
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/identity/elevations", self.admin_headers, {},
            json.dumps(elev_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        e_id = json.loads(body.decode("utf-8"))["elevation"]["id"]

        # 2. Self-approval must fail (SoD)
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/elevations/{e_id}/approve", self.admin_headers, {},
            b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 403)

        # 3. Independent approval by security officer succeeds
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/elevations/{e_id}/approve", self.sec_headers, {},
            b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

        # 4. Activate elevation
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/elevations/{e_id}/activate", self.admin_headers, {},
            b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["elevation"]["status"], "ACTIVATED")

        # 5. Revoke elevation
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/elevations/{e_id}/revoke", self.admin_headers, {},
            json.dumps({"reason": "Maintenance completed"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["elevation"]["status"], "REVOKED")

    def test_07_break_glass_api_and_clinical_firewall(self):
        """POST /api/v1/identity/break-glass and enforce clinical firewall via API."""
        bg_payload = {
            "reason_code": "ACUTE_CLINICAL_EMERGENCY",
            "justification": "Patient in anaphylactic shock, need urgent history verification",
            "ticket_reference": "EMERG-9999",
            "patient_id": "pat-syn-001"
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/identity/break-glass", self.admin_headers, {},
            json.dumps(bg_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        bg_id = json.loads(body.decode("utf-8"))["break_glass"]["id"]

        # Action: clinical act prohibited
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/break-glass/{bg_id}/action", self.admin_headers, {},
            json.dumps({"action": "sign_prescription", "is_clinical_act": True}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 403)
        self.assertIn("Break-glass access can NEVER authorize diagnosis, prescription", body.decode("utf-8"))

        # Review by independent security officer
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/break-glass/{bg_id}/review", self.sec_headers, {},
            json.dumps({"decision": "REVIEWED_JUSTIFIED", "notes": "Audited emergency event"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

    def test_08_service_accounts_api(self):
        """GET & POST /api/v1/identity/service-accounts."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/identity/service-accounts", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(data["service_accounts"]), 2)

        # Register new machine identity
        sa_payload = {
            "service_key": "svc-billing-export",
            "name": "Billing Daily Export Daemon",
            "owner_user_id": "usr-admin-1",
            "credential_ref": "ref-vault-billing-key",
            "permitted_workloads": ["export_invoices"]
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/identity/service-accounts", self.admin_headers, {},
            json.dumps(sa_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)

    def test_09_campaigns_and_two_phase_remediation_api(self):
        """POST /api/v1/identity/campaigns and execute two-phase remediation."""
        camp_payload = {
            "title": "API Verification Campaign",
            "campaign_code": "CAMP-API-VERIFY",
            "target_scope": "CLINICAL_ROLES"
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/identity/campaigns", self.admin_headers, {},
            json.dumps(camp_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        camp_id = json.loads(body.decode("utf-8"))["campaign"]["id"]

        # Get items
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/identity/campaigns/{camp_id}/items", self.admin_headers, {},
            b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        items = json.loads(body.decode("utf-8"))["items"]
        self.assertGreater(len(items), 0)
        # Select a non-admin user to test revocation so admin session remains intact
        non_admin_items = [itm for itm in items if "admin" not in itm.get("principal_id", "")]
        item_to_revoke = non_admin_items[0] if non_admin_items else items[-1]
        item_id = item_to_revoke["id"]

        # Record REVOKE decision
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/certification-items/{item_id}/decision", self.sec_headers, {},
            json.dumps({"decision": "REVOKE", "rationale": "Role no longer justified"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        rem_id = json.loads(body.decode("utf-8"))["decision_record"]["remediation_id"]
        self.assertIsNotNone(rem_id)

        # Phase 1: Apply remediation
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/remediations/{rem_id}/execute", self.admin_headers, {},
            b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["remediation"]["status"], "APPLIED")

        # Phase 2: Verify remediation
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/identity/remediations/{rem_id}/verify", self.admin_headers, {},
            b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body.decode("utf-8"))["remediation"]["status"], "VERIFIED")

    def test_10_sod_rules_and_audit_ledger_api(self):
        """GET /api/v1/identity/sod-rules, POST /sod-rules/check, and GET /audit-ledger."""
        # Check toxic rules
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/identity/sod-rules/check", self.admin_headers, {},
            json.dumps({"roles": ["prescriptions:sign", "org:manage"]}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        check_data = json.loads(body.decode("utf-8"))
        self.assertTrue(check_data["is_toxic"])
        self.assertGreaterEqual(len(check_data["violations"]), 1)

        # Audit ledger
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/identity/audit-ledger", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        audit_data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(len(audit_data["audit_events"]), 1)


if __name__ == "__main__":
    unittest.main()

"""Integration Tests for Enterprise Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance REST APIs.

Phase 55 Verification Suite for ZAYVORA MATAB OS.
Mounted under `/api/v1/tenant-governance/`.
"""

import json
import os
import shutil
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestTenantGovernanceApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_tenant_gov_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin (has all permissions including tenancy:*)
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Admin login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.admin_org_id = admin_data.get("organization_id", "ORG-001")
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
        }

        # Authenticate Receptionist (unprivileged for tenancy:manage, tenancy:break_glass)
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Reception login failed: {body}"
        reception_data = json.loads(body.decode("utf-8"))
        cls.reception_token = reception_data["token"]
        cls.reception_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.reception_token}",
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_list_tenants_and_rbac(self):
        """Test listing tenants, verifying RBAC enforcement."""
        # 1. Unauthenticated request returns 401
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/tenant-governance/tenants",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 401)

        # 2. Admin succeeds
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/tenant-governance/tenants",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("tenants", data)
        self.assertGreaterEqual(len(data["tenants"]), 1)

    def test_tenant_provisioning_and_idempotency_api(self):
        """Test tenant provisioning REST endpoint and idempotency enforcement."""
        payload = {
            "name": "Integration Matab Clinic",
            "code": "INT-MATAB-01",
            "plan_tier": "PROFESSIONAL",
            "admin_name": "Dr. Integration Hakim",
            "admin_email": "integration@matab.pk",
            "max_active_practitioners": 8,
            "max_facilities": 3,
            "idempotency_key": "IDEMP-REST-001"
        }

        # 1. Receptionist forbidden
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.reception_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)

        # 2. Admin creates tenant
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        created = json.loads(body.decode("utf-8"))["tenant"]
        t_id = created["tenant_id"]
        self.assertEqual(created["code"], "INT-MATAB-01")
        self.assertEqual(created["lifecycle_status"], "ACTIVE")

        # 3. Idempotent repeat call returns 201 with same tenant
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        repeated = json.loads(body.decode("utf-8"))["tenant"]
        self.assertEqual(repeated["tenant_id"], t_id)

    def test_tenant_lifecycle_status_transition_api(self):
        """Test transitioning tenant lifecycle state via REST API."""
        # Provision a tenant for lifecycle test
        prov_payload = {
            "name": "Lifecycle Test Matab",
            "code": "LC-MATAB-01",
            "plan_tier": "STARTER"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.admin_headers,
            {},
            json.dumps(prov_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        t_id = json.loads(body.decode("utf-8"))["tenant"]["tenant_id"]

        # Transition to SUSPENDED
        suspend_payload = {
            "status": "SUSPENDED",
            "reason": "Payment overdue after multiple reminder notifications"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/tenant-governance/tenants/{t_id}/transition",
            self.admin_headers,
            {},
            json.dumps(suspend_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        res = json.loads(body.decode("utf-8"))["tenant"]
        self.assertEqual(res["lifecycle_status"], "SUSPENDED")

        # Reactivate back to ACTIVE
        reactivate_payload = {
            "status": "ACTIVE",
            "reason": "Invoice paid in full via bank transfer"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/tenant-governance/tenants/{t_id}/transition",
            self.admin_headers,
            {},
            json.dumps(reactivate_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        res = json.loads(body.decode("utf-8"))["tenant"]
        self.assertEqual(res["lifecycle_status"], "ACTIVE")

    def test_cross_tenant_validation_and_idor_shielding_api(self):
        """Test cross-tenant IDOR defense via relationship validation endpoint."""
        # Provision a separate tenant
        p2 = {"name": "Tenant Two Clinic", "code": "T2-ISOLATE"}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.admin_headers,
            {},
            json.dumps(p2).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        t2 = json.loads(body.decode("utf-8"))["tenant"]

        # Valid relationship: within admin's tenant (fac-central-opd and fac-south-branch exist in seeded data)
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/validate-relationship",
            self.admin_headers,
            {},
            json.dumps({
                "tenant_id": "org-matab-default",
                "parent_type": "facility",
                "parent_id": "fac-central-opd",
                "child_type": "facility",
                "child_id": "fac-south-branch"
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body.decode("utf-8"))["valid"])

        # Get facility belonging to T2 from database
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        t2_fac_id = conn.execute("SELECT id FROM facilities WHERE organization_id = ?", (t2["tenant_id"],)).fetchone()[0]
        conn.close()

        # IDOR Attempt: Admin's facility paired with T2's facility/resource -> 403 Forbidden
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/validate-relationship",
            self.admin_headers,
            {},
            json.dumps({
                "tenant_id": "org-matab-default",
                "parent_type": "facility",
                "parent_id": "fac-central-opd",
                "child_type": "facility",
                "child_id": t2_fac_id
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)
        err = json.loads(body.decode("utf-8"))
        self.assertEqual(err["code"], "FORBIDDEN")
        self.assertEqual(err["details"]["code"], "CROSS_TENANT_ACCESS_DENIED")

    def test_offboarding_impact_and_export_api(self):
        """Test offboarding impact summary and sanitized export endpoints."""
        prov_payload = {"name": "Export Matab", "code": "EXP-MATAB-01"}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.admin_headers,
            {},
            json.dumps(prov_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        t_id = json.loads(body.decode("utf-8"))["tenant"]["tenant_id"]

        # 1. Impact summary
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/tenant-governance/tenants/{t_id}/offboarding-impact",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        impact = json.loads(body.decode("utf-8"))["offboarding_impact"]
        self.assertEqual(impact["tenant_id"], t_id)
        self.assertIn("data_summary", impact)

        # 2. Sanitized export
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/tenant-governance/tenants/{t_id}/export",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        export = json.loads(body.decode("utf-8"))["export"]
        self.assertIn("export_id", export)
        self.assertEqual(export["tenant_id"], t_id)
        self.assertIn("patients", export)
        self.assertIn("encounters", export)

    def test_break_glass_support_tickets_api(self):
        """Test issuing, listing, and revoking break-glass support tickets."""
        prov_payload = {"name": "BG Target Matab", "code": "BG-TARGET-01"}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.admin_headers,
            {},
            json.dumps(prov_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        target_id = json.loads(body.decode("utf-8"))["tenant"]["tenant_id"]

        # 1. Invalid ticket (> 60m) returns 400
        invalid_payload = {
            "target_tenant_id": target_id,
            "support_user_id": "usr-support-01",
            "reason_code": "EMERGENCY_CLINICAL_INVESTIGATION",
            "justification": "Investigating serious dosage discrepancy in critical care",
            "duration_minutes": 120
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/break-glass",
            self.admin_headers,
            {},
            json.dumps(invalid_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 400)

        # 2. Valid ticket creation
        valid_payload = {
            "target_tenant_id": target_id,
            "reason_code": "EMERGENCY_CLINICAL_INVESTIGATION",
            "justification": "Investigating serious dosage discrepancy in critical care",
            "duration_minutes": 30
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/break-glass",
            self.admin_headers,
            {},
            json.dumps(valid_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        ticket = json.loads(body.decode("utf-8"))["break_glass_ticket"]
        ticket_id = ticket["ticket_id"]
        self.assertEqual(ticket["status"], "ACTIVE")

        # 3. List break-glass tickets
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/tenant-governance/break-glass?target_tenant_id={target_id}",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        tickets = json.loads(body.decode("utf-8"))["tickets"]
        self.assertGreaterEqual(len(tickets), 1)

        # 4. Revoke break-glass ticket
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/tenant-governance/break-glass/{ticket_id}/revoke",
            self.admin_headers,
            {},
            json.dumps({"reason": "Clinical investigation completed satisfactorily"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        revoked = json.loads(body.decode("utf-8"))["revocation"]
        self.assertEqual(revoked["status"], "REVOKED")

    def test_entitlements_and_quota_api(self):
        """Test getting and updating entitlements and checking quota via REST."""
        prov_payload = {"name": "Quota Matab", "code": "QUOTA-MATAB-01"}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/tenant-governance/tenants/provision",
            self.admin_headers,
            {},
            json.dumps(prov_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        t_id = json.loads(body.decode("utf-8"))["tenant"]["tenant_id"]

        # Update entitlements
        ent_payload = {
            "plan_tier": "ENTERPRISE",
            "max_active_practitioners": 50,
            "max_facilities": 15,
            "max_storage_mb": 25000,
            "api_rate_limit_rpm": 500
        }
        status, _, body = ApiRouter.dispatch(
            "PATCH",
            f"/api/v1/tenant-governance/tenants/{t_id}/entitlements",
            self.admin_headers,
            {},
            json.dumps(ent_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        updated = json.loads(body.decode("utf-8"))["entitlements"]
        self.assertEqual(updated["plan_tier"], "ENTERPRISE")
        self.assertEqual(updated["max_active_practitioners"], 50)

        # Check quota
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/tenant-governance/tenants/{t_id}/quotas/practitioners",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        quota = json.loads(body.decode("utf-8"))["quota_status"]
        self.assertEqual(quota["quota_limit"], 50)
        self.assertFalse(quota["quota_exceeded"])

    def test_audit_ledger_verification_api(self):
        """Test cryptographic SHA-256 blockchain verification endpoint."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/tenant-governance/audit-ledger/verify",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        verification = json.loads(body.decode("utf-8"))["ledger_report"]
        self.assertTrue(verification["verified"])
        self.assertEqual(verification["status"], "CHAIN_INTEGRITY_VERIFIED")
        self.assertGreaterEqual(verification["blocks_checked"], 1)


if __name__ == "__main__":
    unittest.main()

"""Unit Tests for Enterprise Identity Governance, Privileged Access Management (PAM) & Access Certification.

Phase 45 for ZAYVORA MATAB OS.
Tests core domain logic and non-negotiable invariants:
1. Complete Joiner, Mover, and Leaver (JML) identity lifecycle with effective access verification.
2. Toxic Separation of Duties (SoD) combination detection.
3. Just-In-Time (JIT) privileged elevation lifecycle with dual-custody approval.
4. Non-Negotiable Invariant: Administrative elevation cannot grant clinical prescribing authority.
5. Emergency Break-Glass activation with clinical action firewall and independent retrospective review.
6. Service accounts governance with named human ownership and dependency validation prior to deprovisioning.
7. Access certification campaigns with two-phase remediation (applied -> verified revocation).
8. Separation of Duties enforcement across JIT approvals, break-glass reviews, and access certifications.
"""

import os
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.identity_governance import EnterpriseIdentityGovernanceEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestEnterpriseIdentityGovernanceEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_identity.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = EnterpriseIdentityGovernanceEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "PLATFORM_ADMIN"],
            "permissions": ["identity:read", "identity:manage", "identity:elevate", "identity:approve_elevation", "identity:certify", "identity:remediate"]
        }

        self.auditor_ctx = {
            "id": "usr-auditor-1",
            "user_id": "usr-auditor-1",
            "username": "auditor",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["READ_ONLY_AUDITOR"],
            "permissions": ["identity:read", "audit:read", "identity:certify"]
        }

        self.hakeem_ctx = {
            "id": "usr-hakeem-1",
            "user_id": "usr-hakeem-1",
            "username": "hakeem",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["PRACTITIONER"],
            "permissions": ["prescriptions:sign", "encounters:write", "identity:break_glass"]
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_summary_and_audit_ledger(self):
        """Verify summary calculation and audit ledger baseline."""
        summary = self.engine.get_summary()
        self.assertGreaterEqual(summary["total_principals_count"], 7)
        self.assertGreaterEqual(summary["service_accounts_count"], 2)
        self.assertGreaterEqual(summary["toxic_sod_rules_count"], 5)
        self.assertGreaterEqual(summary["audit_ledger_count"], 1)

        audit_events = self.engine.list_audit_ledger(limit=10)
        self.assertGreaterEqual(len(audit_events), 1)
        self.assertEqual(audit_events[-1]["result_status"], "SUCCESS")

    def test_02_joiner_onboarding_and_effective_access(self):
        """Verify Joiner onboarding creates principal and confirms effective access."""
        payload = {
            "name": "Dr. Zahid Khan",
            "email": "zahid.khan@zayvora.test",
            "principal_type": "HUMAN",
            "organization_id": "org-matab-default",
            "roles": ["PRACTITIONER"]
        }
        principal = self.engine.create_identity(payload, self.admin_ctx)
        self.assertIn("idp-", principal["id"])
        self.assertEqual(principal["account_state"], "ACTIVE")

        # Verify effective access
        eff = self.engine.verify_effective_access(principal["user_id"], "prescriptions:sign")
        self.assertTrue(eff["has_effective_access"])
        self.assertIn("PRACTITIONER", eff["roles"])

    def test_03_toxic_sod_rule_enforcement_on_joiner(self):
        """Verify that conflicting toxic roles are blocked during onboarding."""
        payload = {
            "name": "Hazardous Account",
            "email": "hazardous@zayvora.test",
            "principal_type": "HUMAN",
            "roles": ["billing:refund_void", "audit:read"]  # Violates SOD-001
        }
        with self.assertRaises(ValidationError) as ctx:
            self.engine.create_identity(payload, self.admin_ctx)
        self.assertIn("Toxic Separation of Duties violation", str(ctx.exception))

    def test_04_mover_transition_and_session_invalidation(self):
        """Verify Mover transition updates facility, cleans prior grants, and invalidates sessions."""
        # Create user at fac-central-opd
        payload = {
            "name": "Nurse Salma",
            "email": "salma@zayvora.test",
            "roles": ["NURSE"]
        }
        principal = self.engine.create_identity(payload, self.admin_ctx)
        u_id = principal["user_id"]

        # Execute mover transition to fac-south-branch
        trans_payload = {
            "target_facility_id": "fac-south-branch",
            "new_roles": ["RECEPTIONIST"],
            "revoke_prior_facility_grants": True
        }
        res = self.engine.execute_mover_transition(principal["id"], trans_payload, self.admin_ctx)
        self.assertEqual(res["status"], "MOVER_COMPLETED")
        self.assertEqual(res["target_facility_id"], "fac-south-branch")
        self.assertTrue(res["sessions_invalidated"])

    def test_05_leaver_offboarding_and_revocation_verification(self):
        """Verify Leaver offboarding revokes all sessions, memberships, and proves revocation."""
        payload = {
            "name": "Departing Staff",
            "email": "departing@zayvora.test",
            "roles": ["CASHIER"]
        }
        principal = self.engine.create_identity(payload, self.admin_ctx)
        u_id = principal["user_id"]

        # Execute leaver offboarding
        res = self.engine.execute_leaver_offboarding(principal["id"], "Contract expired", self.admin_ctx)
        self.assertEqual(res["status"], "OFFBOARDED")
        self.assertTrue(res["revocation_verified"])
        self.assertEqual(res["remaining_sessions"], 0)

        # Verify effective access check returns False
        eff = self.engine.verify_effective_access(u_id, "billing:write")
        self.assertFalse(eff["has_effective_access"])
        self.assertFalse(eff["user_active"])

    def test_06_jit_elevation_lifecycle_and_sod_rejection(self):
        """Verify JIT elevation lifecycle with dual-custody approval and self-approval block."""
        # 1. Request elevation
        elev_payload = {
            "privilege_key": "config:manage",
            "justification": "Emergency hotfix configuration update for clinic router",
            "ticket_reference": "INC-889102",
            "duration_seconds": 3600
        }
        req_res = self.engine.request_jit_elevation(elev_payload, self.admin_ctx)
        e_id = req_res["id"]
        self.assertEqual(req_res["status"], "JIT_REQUESTED")

        # 2. Self-approval MUST be rejected (Separation of Duties)
        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.approve_jit_elevation(e_id, self.admin_ctx)
        self.assertIn("Separation of Duties violation", str(ctx.exception))

        # 3. Independent approval by another user succeeds
        appr_res = self.engine.approve_jit_elevation(e_id, self.auditor_ctx)
        self.assertEqual(appr_res["status"], "APPROVED")

        # 4. Activate elevation
        act_res = self.engine.activate_jit_elevation(e_id, self.admin_ctx)
        self.assertEqual(act_res["status"], "ACTIVATED")

        # 5. Revoke elevation
        rev_res = self.engine.revoke_or_expire_jit_elevation(e_id, "Task completed early", self.admin_ctx)
        self.assertEqual(rev_res["status"], "REVOKED")

    def test_07_jit_elevation_clinical_authority_prohibition(self):
        """Verify CRITICAL INVARIANT: Administrative PAM elevation cannot grant clinical authority."""
        elev_payload = {
            "privilege_key": "prescriptions:sign",  # Marked is_clinical_authority = 1
            "justification": "Administrator attempting to sign prescription",
            "ticket_reference": "ILLEGAL-CLINICAL-REQ",
            "duration_seconds": 1800
        }
        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.request_jit_elevation(elev_payload, self.admin_ctx)
        self.assertIn("Clinical authority cannot be granted via administrative JIT elevation", str(ctx.exception))

    def test_08_break_glass_activation_and_clinical_firewall(self):
        """Verify break-glass session enforces strict firewall against clinical acts."""
        bg_payload = {
            "reason_code": "ACUTE_CARDIAC_EMERGENCY",
            "justification": "Patient unresponsive, immediate past allergies and medication history required",
            "ticket_reference": "EMERG-2026-991",
            "patient_id": "pat-syn-001",
            "duration_seconds": 3600
        }
        bg = self.engine.activate_break_glass(bg_payload, self.hakeem_ctx)
        bg_id = bg["id"]
        self.assertEqual(bg["status"], "ACTIVE")

        # Non-clinical read action allowed
        read_res = self.engine.record_break_glass_action(bg_id, "read_allergy_history", False, self.hakeem_ctx)
        self.assertTrue(read_res["allowed"])

        # Attempting clinical action (prescribing, diagnosis) MUST be blocked
        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.record_break_glass_action(bg_id, "prescribe_emergency_nuskha", True, self.hakeem_ctx)
        self.assertIn("Break-glass access can NEVER authorize diagnosis, prescription", str(ctx.exception))

    def test_09_break_glass_retrospective_review_sod(self):
        """Verify break-glass retrospective review enforces Separation of Duties."""
        bg_payload = {
            "reason_code": "DISASTER_RECOVERY_QUERY",
            "justification": "Offline sync failure, reviewing historical encounter notes",
            "ticket_reference": "INC-DR-0091",
            "duration_seconds": 1800
        }
        bg = self.engine.activate_break_glass(bg_payload, self.admin_ctx)
        bg_id = bg["id"]

        # Actor cannot self-review
        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.review_break_glass(bg_id, "REVIEWED_JUSTIFIED", "Self review attempt", self.admin_ctx)
        self.assertIn("Separation of Duties violation", str(ctx.exception))

        # Independent auditor conducts review
        rev = self.engine.review_break_glass(bg_id, "REVIEWED_JUSTIFIED", "Reviewed and justified by audit team", self.auditor_ctx)
        self.assertEqual(rev["status"], "REVIEWED_JUSTIFIED")

    def test_10_service_account_registration_and_dependency_check(self):
        """Verify machine identity registration and dependency validation prior to deprovisioning."""
        sa_payload = {
            "service_key": "svc-lab-sync",
            "name": "Lab Results Sync Agent",
            "owner_user_id": "usr-admin-1",
            "credential_ref": "ref-vault-lab-key",
            "environment": "production",
            "permitted_workloads": ["import_lab_results"],
            "dependency_checklist": ["active_ipd_monitor", "lis_bridge"]
        }
        sa = self.engine.register_service_account(sa_payload, self.admin_ctx)
        self.assertEqual(sa["status"], "ACTIVE")
        self.assertEqual(sa["is_interactive_allowed"], 0)

        # Deprovisioning without override fails due to declared dependencies
        with self.assertRaises(ValidationError) as ctx:
            self.engine.deprovision_service_account(sa["id"], force_override=False, actor_ctx=self.admin_ctx)
        self.assertIn("active dependencies", str(ctx.exception))

        # Deprovisioning with force_override succeeds
        dep = self.engine.deprovision_service_account(sa["id"], force_override=True, actor_ctx=self.admin_ctx)
        self.assertEqual(dep["status"], "DEPROVISIONED")

    def test_11_certification_campaign_and_two_phase_remediation(self):
        """Verify access certification campaign, self-certification block, and 2-phase revocation."""
        # 1. Launch campaign
        camp_payload = {
            "title": "Q4 Staff Role Recertification",
            "campaign_code": "CAMP-TEST-Q4",
            "target_scope": "FACILITY_MEMBERSHIPS"
        }
        camp = self.engine.create_certification_campaign(camp_payload, self.admin_ctx)
        camp_id = camp["id"]
        self.assertGreater(camp["total_items_count"], 0)

        # 2. Get line items
        items = self.engine.list_certification_items(camp_id)
        self.assertGreater(len(items), 0)
        target_item = items[0]

        # 3. If reviewer == subject, self-certification is blocked
        if target_item["principal_id"] == self.admin_ctx["user_id"]:
            with self.assertRaises(ForbiddenError):
                self.engine.record_certification_decision(target_item["id"], "RETAIN", "Self retain", self.admin_ctx)

        # 4. Independent reviewer records REVOKE decision
        dec_res = self.engine.record_certification_decision(
            target_item["id"], "REVOKE", "Role no longer required for current duties", self.auditor_ctx
        )
        self.assertEqual(dec_res["decision"], "REVOKE")
        rem_id = dec_res["remediation_id"]
        self.assertIsNotNone(rem_id)

        # 5. Phase 1: Execute Remediation Action
        app_res = self.engine.execute_remediation_action(rem_id, self.admin_ctx)
        self.assertEqual(app_res["status"], "APPLIED")

        # 6. Phase 2: Verify Remediation Action
        ver_res = self.engine.verify_remediation_action(rem_id, self.admin_ctx)
        self.assertEqual(ver_res["status"], "VERIFIED")
        self.assertTrue(ver_res["is_effective_revocation_verified"])


if __name__ == "__main__":
    unittest.main()

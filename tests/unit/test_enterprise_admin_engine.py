"""Unit tests for Phase 11 Enterprise Administration Domain Engine."""

import os
import tempfile
import unittest

from apps.api.core.errors import ConflictError, ForbiddenError, ValidationError
from apps.api.database.connection import DatabaseConnection
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.enterprise_admin import EnterpriseAdminService


class TestEnterpriseAdminEngine(unittest.TestCase):
    """Tests for EnterpriseAdminService domain invariants, hierarchy, config inheritance, and migration."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.svc = EnterpriseAdminService(db_path=self.db_path)
        self.org_id = "org-matab-default"
        self.fac_central = "fac-central-opd"
        self.fac_south = "fac-south-branch"
        self.admin_id = "usr-admin-1"
        self.hakeem_id = "usr-hakeem-1"
        self.recep_id = "usr-recep-1"

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_organization_hierarchy_cycle_rejected(self):
        """Self-parenting and multi-node circular parent-child organization chains are rejected."""
        with self.assertRaises(ConflictError) as ctx:
            self.svc.update_organization(
                self.org_id,
                self.admin_id,
                {"parent_organization_id": self.org_id},
            )
        self.assertIn("Circular organization hierarchy", str(ctx.exception.message))

        # Create child org B under org A, and grandchild org C under org B
        org_b = self.svc.create_organization(
            self.admin_id,
            {
                "id": "org-child-b",
                "code": "ORG-CHILD-B",
                "name": "Child Group B",
                "legal_name": "Child Group B Pvt Ltd",
                "parent_organization_id": self.org_id,
            },
        )
        org_c = self.svc.create_organization(
            self.admin_id,
            {
                "id": "org-grandchild-c",
                "code": "ORG-GRANDCHILD-C",
                "name": "Grandchild Hospital C",
                "legal_name": "Grandchild Hospital C Pvt Ltd",
                "parent_organization_id": org_b["id"],
            },
        )

        # Attempting to make org A a child of org C creates a 3-node cycle (A -> C -> B -> A)
        with self.assertRaises(ConflictError) as cycle_ctx:
            self.svc.update_organization(
                self.org_id,
                self.admin_id,
                {"parent_organization_id": org_c["id"]},
            )
        self.assertIn("Circular organization hierarchy", str(cycle_ctx.exception.message))

    def test_facility_creation_blocks_cross_tenant_spoofing_and_runs_health_check(self):
        """Creating a facility for a mismatched organization_id fails closed; health check verifies readiness."""
        with self.assertRaises(ForbiddenError) as ctx:
            self.svc.create_facility(
                self.org_id,
                self.admin_id,
                {
                    "organization_id": "org-other-999",
                    "code": "NORTH-01",
                    "name": "North Branch",
                },
            )
        self.assertEqual(ctx.exception.details.get("code"), "CROSS_TENANT_FACILITY_LINK_DENIED")

        # Create a new setup facility in org-matab-default without address/phone/staff
        new_fac = self.svc.create_facility(
            self.org_id,
            self.admin_id,
            {
                "id": "fac-north-unit",
                "code": "ZAY-NORTH-03",
                "name": "Zayvora North Clinic",
                "facility_type": "BRANCH_CLINIC",
                "lifecycle_status": "setup",
            },
        )
        self.assertEqual(new_fac["id"], "fac-north-unit")

        # Health check on fac-north-unit should report ready_for_activation=False because address/phone & staff missing
        hc_new = self.svc.run_facility_activation_health_check(self.org_id, "fac-north-unit")
        self.assertFalse(hc_new["ready_for_activation"])

        # Attempting to transition fac-north-unit to active before prerequisites pass must raise ConflictError
        with self.assertRaises(ConflictError) as act_ctx:
            self.svc.transition_facility_lifecycle(
                self.org_id,
                "fac-north-unit",
                "active",
                self.admin_id,
                "Premature activation attempt",
            )
        self.assertEqual(act_ctx.exception.details.get("code"), "FACILITY_ACTIVATION_PREREQUISITES_FAILED")

        # Health check on seeded fac-central-opd should pass
        hc_central = self.svc.run_facility_activation_health_check(self.org_id, self.fac_central)
        self.assertTrue(hc_central["ready_for_activation"])

    def test_scoped_staff_assignment_conflict_and_immediate_revocation(self):
        """Conflicting roles (READ_ONLY_AUDITOR + PRACTITIONER) are rejected; revocation preserves historical attribution."""
        # Assign Hakeem as PRACTITIONER at South Branch first
        self.svc.create_staff_assignment(
            self.org_id,
            self.fac_south,
            self.admin_id,
            {
                "user_id": self.hakeem_id,
                "role_code": "PRACTITIONER",
                "assignment_type": "SECONDARY_BRANCH",
            },
        )
        # Attempting to also assign READ_ONLY_AUDITOR at the same facility must fail
        with self.assertRaises(ConflictError) as ctx:
            self.svc.create_staff_assignment(
                self.org_id,
                self.fac_south,
                self.admin_id,
                {
                    "user_id": self.hakeem_id,
                    "role_code": "READ_ONLY_AUDITOR",
                },
            )
        self.assertEqual(ctx.exception.details.get("code"), "INCOMPATIBLE_ROLE_COMBINATION")

        # Assign receptionist user to South Branch as CLINIC_ADMIN
        sa = self.svc.create_staff_assignment(
            self.org_id,
            self.fac_south,
            self.admin_id,
            {
                "user_id": self.recep_id,
                "role_code": "CLINIC_ADMIN",
                "assignment_type": "SECONDARY_BRANCH",
            },
        )
        self.assertEqual(sa["status"], "active")

        # Revoke assignment and verify immediate revocation status
        revoked = self.svc.revoke_staff_assignment(
            self.org_id,
            sa["id"],
            self.admin_id,
            "Completed temporary branch rotation",
        )
        self.assertEqual(revoked["status"], "revoked")
        self.assertEqual(revoked["revocation_reason"], "Completed temporary branch rotation")

    def test_layered_configuration_inheritance_rollback_and_security_baseline(self):
        """Configuration resolves across 4 tiers, supports rollback, and blocks secrets or security weakening."""
        # 1. Attempting to weaken platform security baseline must fail closed
        with self.assertRaises(ValidationError) as sec_ctx:
            self.svc.update_facility_configuration(
                self.org_id,
                self.fac_central,
                self.admin_id,
                {"config": {"require_clinician_pin_for_signoff": False}},
            )
        self.assertEqual(sec_ctx.exception.details.get("code"), "PLATFORM_SECURITY_CONSTRAINT_VIOLATION")

        # 2. Attempting to store plaintext secret in configuration JSON must fail closed
        with self.assertRaises(ValidationError) as secret_ctx:
            self.svc.update_facility_configuration(
                self.org_id,
                self.fac_central,
                self.admin_id,
                {"config": {"whatsapp_api_secret": "sk_live_123456789"}},
            )
        self.assertEqual(secret_ctx.exception.details.get("code"), "PLAINTEXT_SECRET_PROHIBITED")

        # 3. Organization default + Facility override + Rollback
        self.svc.update_organization_configuration(
            self.org_id,
            self.admin_id,
            {
                "config": {
                    "appointment_default_slot_minutes": 20,
                    "invoice_prefix": "ZAY-ORG",
                    "quiet_hours_start": "21:00",
                },
                "change_reason": "Set org baseline slot duration",
            },
        )
        v1_fac = self.svc.update_facility_configuration(
            self.org_id,
            self.fac_south,
            self.admin_id,
            {
                "config": {"invoice_prefix": "ZAY-SOUTH-V1"},
                "change_reason": "South branch prefix v1",
            },
        )
        self.assertEqual(v1_fac["effective_configuration"]["invoice_prefix"], "ZAY-SOUTH-V1")
        self.assertEqual(v1_fac["effective_configuration"]["appointment_default_slot_minutes"], 20)
        self.assertEqual(v1_fac["inheritance_provenance"]["invoice_prefix"], "FACILITY_OVERRIDE")
        self.assertEqual(v1_fac["inheritance_provenance"]["appointment_default_slot_minutes"], "ORGANIZATION")
        self.assertEqual(
            v1_fac["inheritance_provenance"]["require_clinician_pin_for_signoff"],
            "PLATFORM_SECURITY",
        )

        v2_fac = self.svc.update_facility_configuration(
            self.org_id,
            self.fac_south,
            self.admin_id,
            {
                "config": {"invoice_prefix": "ZAY-SOUTH-V2"},
                "change_reason": "South branch prefix v2",
            },
        )
        self.assertEqual(v2_fac["effective_configuration"]["invoice_prefix"], "ZAY-SOUTH-V2")

        # Rollback to version 1
        rolled_back = self.svc.rollback_facility_configuration(
            self.org_id,
            self.fac_south,
            v1_fac["current_version"],
            self.admin_id,
            "Revert prefix to V1",
        )
        self.assertEqual(rolled_back["effective_configuration"]["invoice_prefix"], "ZAY-SOUTH-V1")

    def test_module_entitlement_prerequisite_dag_and_dependents_check(self):
        """Modules cannot be disabled if active dependents exist, nor enabled without prerequisites."""
        # Disabling safety_firewall while pharmacy_inventory is enabled on fac-central-opd must fail
        with self.assertRaises(ConflictError) as dep_ctx:
            self.svc.set_facility_module_state(
                self.org_id,
                self.fac_central,
                "safety_firewall",
                False,
                self.admin_id,
            )
        self.assertEqual(dep_ctx.exception.details.get("code"), "MODULE_HAS_ACTIVE_DEPENDENTS")

        # On fac-south-branch, disable pharmacy_inventory and hospital_modules first, then disable safety_firewall
        self.svc.set_facility_module_state(
            self.org_id,
            self.fac_south,
            "pharmacy_inventory",
            False,
            self.admin_id,
        )
        self.svc.set_facility_module_state(
            self.org_id,
            self.fac_south,
            "safety_firewall",
            False,
            self.admin_id,
        )
        # Now attempting to enable pharmacy_inventory on fac-south-branch while safety_firewall is disabled fails
        with self.assertRaises(ConflictError) as prereq_ctx:
            self.svc.set_facility_module_state(
                self.org_id,
                self.fac_south,
                "pharmacy_inventory",
                True,
                self.admin_id,
            )
        self.assertEqual(prereq_ctx.exception.details.get("code"), "MODULE_PREREQUISITES_NOT_MET")

    def test_integration_connector_secret_uri_and_sandbox_gate(self):
        """Connectors require vault/env secret URIs and cannot jump to PRODUCTION_ACTIVE without SANDBOX_TESTED."""
        with self.assertRaises(ValidationError) as bad_uri:
            self.svc.create_integration_connector(
                self.org_id,
                self.admin_id,
                {
                    "connector_type": "LIS_LAB",
                    "name": "External Lab Connector",
                    "secret_ref_uri": "plaintext_password_123",
                },
            )
        self.assertIn("secret_ref_uri must use an approved secret manager URI scheme", str(bad_uri.exception.message))

        conn_rec = self.svc.create_integration_connector(
            self.org_id,
            self.admin_id,
            {
                "connector_type": "LIS_LAB",
                "name": "HL7 Lab Bridge",
                "endpoint_url": "https://lis.example.org/hl7",
                "secret_ref_uri": "vault://zayvora/integrations/lab_lis_token",
                "data_sharing_policy_ref": "POL-LIS-2026-V1",
            },
        )
        self.assertEqual(conn_rec["lifecycle_state"], "CONFIGURED_NOT_CONNECTED")

        # Jumping straight to PRODUCTION_ACTIVE from CONFIGURED_NOT_CONNECTED must fail
        with self.assertRaises(ConflictError) as prod_ctx:
            self.svc.verify_and_transition_integration(
                self.org_id,
                conn_rec["id"],
                "PRODUCTION_ACTIVE",
                self.admin_id,
            )
        self.assertEqual(prod_ctx.exception.details.get("code"), "INTEGRATION_NOT_VERIFIED_FOR_PRODUCTION")

        # Transition to SANDBOX_TESTED first, then PRODUCTION_ACTIVE succeeds
        sandbox = self.svc.verify_and_transition_integration(
            self.org_id,
            conn_rec["id"],
            "SANDBOX_TESTED",
            self.admin_id,
        )
        self.assertEqual(sandbox["lifecycle_state"], "SANDBOX_TESTED")
        prod = self.svc.verify_and_transition_integration(
            self.org_id,
            conn_rec["id"],
            "PRODUCTION_ACTIVE",
            self.admin_id,
        )
        self.assertEqual(prod["lifecycle_state"], "PRODUCTION_ACTIVE")

    def test_single_clinic_migration_dry_run_and_idempotent_execute(self):
        """Single-clinic migration reconciles pre/post record counts, links unlinked records, and is repeatable."""
        # Remove one patient_facility_links row to simulate an unlinked pre-Phase-11 single-clinic patient
        conn = DatabaseConnection(self.db_path).get_connection()
        try:
            conn.execute(
                "DELETE FROM patient_facility_links WHERE patient_id = 'pat-syn-001' AND organization_id = ?",
                (self.org_id,),
            )
            conn.commit()
        finally:
            conn.close()

        dry = self.svc.run_single_clinic_migration(
            self.org_id,
            self.fac_central,
            self.admin_id,
            mode="DRY_RUN",
        )
        self.assertEqual(dry["status"], "COMPLETED")
        self.assertEqual(dry["pre_counts"]["patient_facility_links"], dry["post_counts"]["patient_facility_links"])

        exec_1 = self.svc.run_single_clinic_migration(
            self.org_id,
            self.fac_central,
            self.admin_id,
            mode="EXECUTE",
        )
        self.assertEqual(exec_1["status"], "COMPLETED")
        self.assertTrue(exec_1["counts_reconciled"])
        self.assertGreaterEqual(
            exec_1["post_counts"]["patient_facility_links"],
            exec_1["pre_counts"]["patients"],
        )

        # Second execution is idempotent
        exec_2 = self.svc.run_single_clinic_migration(
            self.org_id,
            self.fac_central,
            self.admin_id,
            mode="EXECUTE",
        )
        self.assertEqual(exec_2["status"], "COMPLETED")
        self.assertEqual(
            exec_2["pre_counts"]["patient_facility_links"],
            exec_2["post_counts"]["patient_facility_links"],
        )


if __name__ == "__main__":
    unittest.main()

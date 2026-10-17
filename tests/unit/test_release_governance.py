"""Unit Tests for Production Release Engineering, Feature Flags & Rollback Orchestration Engine.

Phase 38 for ZAYVORA MATAB OS.
Verifies:
1. Release manifest draft creation, artifact digests, secret stripping, and conflict guards.
2. Quality gate evaluations and automatic manifest state transitions.
3. Separation of duties (SoD) on production release approvals (author cannot self-approve).
4. Controlled deployment promotions and post-deploy smoke verification.
5. Feature flag governance: Clinical CDS default-off guardrail, environment activation.
6. Server-side cohort targeting (organizations, facilities, roles, users).
7. Emergency kill-switch toggling and audit logging.
8. Rollback and recovery orchestration with side-effect tracking.
9. Operational pulse and governance caveats.
"""

import os
import json
import sqlite3
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.release_governance import ReleaseGovernanceEngine
from apps.api.core.errors import (
    NotFoundError,
    ValidationError,
    ForbiddenError,
    ConflictError
)


class TestReleaseGovernanceEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_release_gov.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = ReleaseGovernanceEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "RELEASE_MANAGER"],
            "org_roles": ["ORG_ADMIN", "RELEASE_MANAGER"]
        }

        self.dev_ctx = {
            "id": "usr-dev-1",
            "user_id": "usr-dev-1",
            "username": "developer",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["DEVELOPER"],
            "org_roles": ["DEVELOPER"]
        }

        self.sec_officer_ctx = {
            "id": "usr-sec-1",
            "user_id": "usr-sec-1",
            "username": "sec_officer",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["SECURITY_OFFICER", "RELEASE_MANAGER"],
            "org_roles": ["SECURITY_OFFICER", "RELEASE_MANAGER"]
        }

        self.practitioner_ctx = {
            "id": "usr-hakeem-1",
            "user_id": "usr-hakeem-1",
            "username": "hakeem",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["PRACTITIONER"],
            "org_roles": ["PRACTITIONER"]
        }

    # --------------------------------------------------------------------------
    # 1. Manifest Lifecycle & Secrets Stripping
    # --------------------------------------------------------------------------

    def test_01_create_release_manifest_draft_and_validation(self):
        """Create a valid release manifest draft and assert secrets are scrubbed."""
        data = {
            "version_tag": "v2026.10.15-01",
            "title": "Hospital Integration & Security Hardening",
            "description": "Includes enhanced ABDM FHIR and CDS security filters",
            "git_commit": "4a7c18e",
            "target_environment": "staging",
            "risk_level": "high",
            "config_changes": {
                "DATABASE_POOL_SIZE": "20",
                "API_SECRET_KEY": "super_secret_token_12345",
                "PASSWORD_SALT": "unsafe_salt_abc"
            },
            "rollback_plan": {
                "strategy": "ROLLBACK_ARTIFACT",
                "BACKUP_DB_PASSWORD": "db_secret_password"
            }
        }
        manifest = self.engine.create_release_manifest_draft(data, self.dev_ctx)
        self.assertEqual(manifest["version_tag"], "v2026.10.15-01")
        self.assertEqual(manifest["status"], "draft")
        self.assertEqual(manifest["risk_level"], "high")
        self.assertTrue(manifest["artifact_digest"])

        # Secrets must be scrubbed from config and rollback plan
        self.assertEqual(manifest["config_changes"]["DATABASE_POOL_SIZE"], "20")
        self.assertEqual(manifest["config_changes"]["API_SECRET_KEY"], "[REDACTED_SECRET]")
        self.assertEqual(manifest["config_changes"]["PASSWORD_SALT"], "[REDACTED_SECRET]")
        self.assertEqual(manifest["rollback_plan"]["BACKUP_DB_PASSWORD"], "[REDACTED_SECRET]")

        # Duplicate version tag must raise ConflictError
        with self.assertRaises(ConflictError):
            self.engine.create_release_manifest_draft(data, self.dev_ctx)

    def test_02_update_manifest_draft(self):
        """Update release manifest while in draft state."""
        data = {
            "version_tag": "v2026.10.15-02",
            "title": "Initial Title",
            "git_commit": "abc1234"
        }
        manifest = self.engine.create_release_manifest_draft(data, self.dev_ctx)
        rel_id = manifest["id"]

        updated = self.engine.update_release_manifest_draft(
            rel_id,
            {"title": "Updated Title", "risk_level": "critical"},
            self.dev_ctx
        )
        self.assertEqual(updated["title"], "Updated Title")
        self.assertEqual(updated["risk_level"], "critical")

    # --------------------------------------------------------------------------
    # 2. Quality Gate Evaluations
    # --------------------------------------------------------------------------

    def test_03_record_quality_gates(self):
        """Record quality gates and verify status changes from draft to awaiting_approval or validation_failed."""
        data = {
            "version_tag": "v2026.10.15-03",
            "title": "Gate Test Build",
            "git_commit": "cde5678"
        }
        manifest = self.engine.create_release_manifest_draft(data, self.dev_ctx)
        rel_id = manifest["id"]

        # Record passing gates
        self.engine.record_gate_evaluation(rel_id, {"gate_type": "UNIT_TESTS", "status": "PASSED"}, self.dev_ctx)
        m2 = self.engine.record_gate_evaluation(rel_id, {"gate_type": "INTEGRATION_TESTS", "status": "PASSED"}, self.dev_ctx)
        self.assertEqual(m2["status"], "awaiting_approval")

        # Record failing gate -> validation_failed
        m3 = self.engine.record_gate_evaluation(rel_id, {"gate_type": "SECURITY_SCAN", "status": "FAILED"}, self.dev_ctx)
        self.assertEqual(m3["status"], "validation_failed")

    # --------------------------------------------------------------------------
    # 3. Separation of Duties (SoD) on Approvals
    # --------------------------------------------------------------------------

    def test_04_separation_of_duties_production_approval(self):
        """Assert release author CANNOT self-approve production releases."""
        data = {
            "version_tag": "v2026.10.15-04",
            "title": "Production Deployment Candidate",
            "git_commit": "def7890",
            "target_environment": "production",
            "risk_level": "high"
        }
        manifest = self.engine.create_release_manifest_draft(data, self.admin_ctx)
        rel_id = manifest["id"]

        # Pass required gates
        self.engine.record_gate_evaluation(rel_id, {"gate_type": "UNIT_TESTS", "status": "PASSED"}, self.admin_ctx)
        self.engine.record_gate_evaluation(rel_id, {"gate_type": "INTEGRATION_TESTS", "status": "PASSED"}, self.admin_ctx)

        # Admin created it. Admin attempts to approve production release -> FORBIDDEN (SoD violation)
        with self.assertRaises(ForbiddenError):
            self.engine.advance_release_status(rel_id, "approve", self.admin_ctx)

        # Independent Security Officer can approve
        approved = self.engine.advance_release_status(rel_id, "approve", self.sec_officer_ctx, notes="Passed all security gates")
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approved_by"], "usr-sec-1")

    # --------------------------------------------------------------------------
    # 4. Deployment Promotion & Post-Deploy Verification
    # --------------------------------------------------------------------------

    def test_05_deploy_release_and_post_deploy_smoke_checks(self):
        """Execute deployment promotion and verify smoke tests and deployed state."""
        data = {
            "version_tag": "v2026.10.15-05",
            "title": "Staging Deployment Candidate",
            "git_commit": "fab1234",
            "target_environment": "staging",
            "risk_level": "moderate"
        }
        manifest = self.engine.create_release_manifest_draft(data, self.dev_ctx)
        rel_id = manifest["id"]

        # Cannot deploy unapproved release -> ConflictError
        with self.assertRaises(ConflictError):
            self.engine.execute_deployment(rel_id, "staging", self.admin_ctx)

        # Pass gates and approve
        self.engine.record_gate_evaluation(rel_id, {"gate_type": "UNIT_TESTS", "status": "PASSED"}, self.dev_ctx)
        self.engine.record_gate_evaluation(rel_id, {"gate_type": "INTEGRATION_TESTS", "status": "PASSED"}, self.dev_ctx)
        self.engine.advance_release_status(rel_id, "approve", self.admin_ctx)

        # Deploy
        deployed = self.engine.execute_deployment(rel_id, "staging", self.admin_ctx)
        self.assertEqual(deployed["status"], "deployed")
        self.assertEqual(deployed["target_environment"], "staging")
        self.assertEqual(deployed["post_deploy_evidence"]["health_live"], "OK")
        self.assertEqual(len(deployed["deployments"]), 1)
        self.assertEqual(deployed["deployments"][0]["status"], "SUCCESS")

    # --------------------------------------------------------------------------
    # 5. Feature Flag Governance & Clinical Safety
    # --------------------------------------------------------------------------

    def test_06_create_feature_flag_and_clinical_guardrail(self):
        """Clinical CDS feature flags must be disabled by default (fail-closed)."""
        # Attempt to create clinical flag enabled by default -> ValidationError
        invalid_clinical_flag = {
            "flag_key": "flag-unsafe-auto-rx",
            "name": "Autonomous Formulation Selector",
            "category": "clinical_cds",
            "risk_level": "critical",
            "is_enabled_default": 1
        }
        with self.assertRaises(ValidationError):
            self.engine.create_feature_flag(invalid_clinical_flag, self.admin_ctx)

        # Create valid clinical flag (disabled by default)
        valid_clinical_flag = {
            "flag_key": "flag-experimental-mudabbar",
            "name": "Experimental Mudabbar Verification",
            "category": "clinical_cds",
            "risk_level": "high",
            "is_enabled_default": 0,
            "state_by_environment": {"local": True, "ci_test": True, "staging": False, "pilot": False, "production": False}
        }
        flag = self.engine.create_feature_flag(valid_clinical_flag, self.admin_ctx)
        self.assertEqual(flag["flag_key"], "flag-experimental-mudabbar")
        self.assertEqual(flag["is_enabled_default"], 0)
        self.assertEqual(len(flag["audit_trail"]), 1)

    def test_07_server_side_flag_evaluation_environment_targeting(self):
        """Evaluate flag states across environments."""
        # 'flag-patient-portal-v2' is enabled in staging, disabled in production
        is_staging = self.engine.evaluate_feature_flag("flag-patient-portal-v2", "staging", self.admin_ctx)
        is_prod = self.engine.evaluate_feature_flag("flag-patient-portal-v2", "production", self.admin_ctx)
        self.assertTrue(is_staging)
        self.assertFalse(is_prod)

    def test_08_server_side_flag_evaluation_cohort_targeting(self):
        """Evaluate flag cohort rules for role targeting."""
        # 'flag-cds-deep-reasoning' targets roles: ['PRACTITIONER', 'CLINICIAN'] in staging
        eval_practitioner = self.engine.evaluate_feature_flag("flag-cds-deep-reasoning", "staging", self.practitioner_ctx)
        self.assertTrue(eval_practitioner)

        # Developer without practitioner role in context
        eval_dev = self.engine.evaluate_feature_flag("flag-cds-deep-reasoning", "staging", self.dev_ctx)
        self.assertFalse(eval_dev)

    def test_09_emergency_disable_kill_switch(self):
        """Emergency disable immediately sets evaluation to False regardless of env state."""
        # In staging, 'flag-patient-portal-v2' was True
        self.assertTrue(self.engine.evaluate_feature_flag("flag-patient-portal-v2", "staging", self.admin_ctx))

        # Trip emergency kill switch
        self.engine.toggle_emergency_disable(
            "flag-patient-portal-v2",
            disable=True,
            reason="Security review identified session token leak in portal",
            user_ctx=self.admin_ctx
        )

        # Must now evaluate to False
        self.assertFalse(self.engine.evaluate_feature_flag("flag-patient-portal-v2", "staging", self.admin_ctx))

        # Restore
        self.engine.toggle_emergency_disable(
            "flag-patient-portal-v2",
            disable=False,
            reason="Hotfix deployed and verified",
            user_ctx=self.admin_ctx
        )
        self.assertTrue(self.engine.evaluate_feature_flag("flag-patient-portal-v2", "staging", self.admin_ctx))

    # --------------------------------------------------------------------------
    # 6. Rollback & Recovery Orchestration
    # --------------------------------------------------------------------------

    def test_10_rollback_orchestration_and_side_effects(self):
        """Execute rollback and assert recovery record, side-effect limits, and recovered status."""
        manifest = self.engine.get_release_manifest("rel-v2026.10.14-01", self.admin_ctx)
        rel_id = manifest["id"]

        # Execute ROLLBACK_ARTIFACT
        recovered = self.engine.execute_rollback(
            rel_id,
            strategy="ROLLBACK_ARTIFACT",
            target_environment="staging",
            reason="Downstream memory leak observed under load test",
            user_ctx=self.admin_ctx,
            acknowledged_side_effects=["SMS sent cannot be undone", "Physical stock audit required"]
        )
        self.assertEqual(recovered["status"], "recovered")
        self.assertEqual(len(recovered["rollbacks"]), 1)
        self.assertEqual(recovered["rollbacks"][0]["strategy"], "ROLLBACK_ARTIFACT")

    # --------------------------------------------------------------------------
    # 7. Operational Pulse & Observability
    # --------------------------------------------------------------------------

    def test_11_release_pulse_summary(self):
        """Verify release observability metrics pulse and caveats."""
        pulse = self.engine.get_release_pulse_summary({}, self.admin_ctx)
        self.assertIn("total_releases", pulse)
        self.assertIn("total_feature_flags", pulse)
        self.assertIn("recent_manifests", pulse)
        self.assertTrue(any("separation of duties" in c.lower() for c in pulse["caveats"]))


if __name__ == "__main__":
    unittest.main()

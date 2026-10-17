"""Unit Tests for Enterprise Configuration, Secrets & Environment Governance Engine.

Phase 44 for ZAYVORA MATAB OS.
Tests core domain logic:
1. Catalog Settings Registration & Retrieval.
2. Safe Public Client Config Filtering (zero secret leakage).
3. Environment Isolation Perimeter Enforcement (blocking cross-environment resource pollution, live payments, live SMS).
4. Typed Preflight Schema Validation & Fail-Closed Production Invariants.
5. Secret Metadata Management (strictly zero raw secrets).
6. Provider-Aware Secret Rotation State Machine (planned -> prepared -> updated -> verified -> old_retired).
7. Urgent Compromise Containment Workflow (incident-linked emergency revocation).
8. Configuration Change Proposals with Separation of Duties.
9. Configuration Drift Scans & Granular Findings Generation.
10. Governance Summary & Tamper-Evident Audit Ledger.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.config_governance import EnterpriseConfigGovernanceEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestEnterpriseConfigGovernanceEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_config.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = EnterpriseConfigGovernanceEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "PLATFORM_ADMIN"],
            "org_roles": ["ORG_ADMIN", "PLATFORM_ADMIN"],
            "permissions": [
                "config:read", "config:manage", "config:rotate_secret",
                "config:approve", "config:drift_check"
            ]
        }

        self.ciso_ctx = {
            "id": "usr-ciso-1",
            "user_id": "usr-ciso-1",
            "username": "ciso",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["CISO"],
            "org_roles": ["CISO"],
            "permissions": [
                "config:read", "config:rotate_secret", "config:approve", "config:drift_check"
            ]
        }

        self.dev_ctx = {
            "id": "usr-dev-1",
            "user_id": "usr-dev-1",
            "username": "developer",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["DEVELOPER"],
            "org_roles": ["DEVELOPER"],
            "permissions": [
                "config:read", "config:manage"
            ]
        }

        self.viewer_ctx = {
            "id": "usr-viewer-1",
            "user_id": "usr-viewer-1",
            "username": "auditor",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["AUDITOR"],
            "org_roles": ["AUDITOR"],
            "permissions": [
                "config:read"
            ]
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_seed_data_loaded(self):
        """Verify baseline environments, settings catalog, and secret references exist."""
        envs = self.engine.get_environments(self.admin_ctx)
        self.assertEqual(len(envs), 4)
        env_codes = [e["environment_code"] for e in envs]
        self.assertIn("local_dev", env_codes)
        self.assertIn("production", env_codes)

        settings = self.engine.get_settings(self.admin_ctx)
        self.assertGreaterEqual(len(settings), 5)
        keys = [s["config_key"] for s in settings]
        self.assertIn("MATAB_ENV", keys)
        self.assertIn("MATAB_SECRET_KEY", keys)

        secrets = self.engine.get_secret_references(self.admin_ctx)
        self.assertGreaterEqual(len(secrets), 3)

    def test_settings_catalog_management(self):
        """Test registering a setting, rejecting raw secret defaults, and fetching."""
        payload = {
            "config_key": "CLINICAL_MAX_APPOINTMENTS_PER_DAY",
            "description": "Daily appointment cap for single practitioner",
            "category": "CLINICAL_WORKFLOW_POLICY",
            "data_type": "integer",
            "owner_team": "Clinical Operations",
            "environment_scope": "all",
            "default_value_json": 40,
            "validation_rules_json": {"min": 5, "max": 100}
        }
        res = self.engine.register_setting(self.admin_ctx, payload)
        self.assertEqual(res["config_key"], "CLINICAL_MAX_APPOINTMENTS_PER_DAY")
        self.assertEqual(res["data_type"], "integer")

        # Duplicate key should raise ConflictError
        with self.assertRaises(ConflictError):
            self.engine.register_setting(self.admin_ctx, payload)

        # Raw secret default value must be rejected
        with self.assertRaises(ValidationError):
            self.engine.register_setting(self.admin_ctx, {
                "config_key": "INSECURE_SECRET_SETTING",
                "description": "Bad attempt to store raw secret in catalog",
                "category": "SECRET_CREDENTIAL",
                "default_value_json": "my-raw-password"
            })

    def test_public_client_config_filtering(self):
        """Verify that public client config strictly filters out server secrets and internals."""
        public_cfg = self.engine.get_public_client_config()
        self.assertIn("APP_CLIENT_NAME", public_cfg)
        self.assertIn("CLINICAL_SYSTEM_VERSION", public_cfg)
        # Server secrets must never be exposed to public config
        self.assertNotIn("MATAB_SECRET_KEY", public_cfg)
        self.assertNotIn("DATABASE_URL", public_cfg)

    def test_environment_isolation_boundaries(self):
        """Test isolation perimeter checks preventing non-prod from touching production or executing live side-effects."""
        # Non-prod attempting to touch production database
        with self.assertRaises(ForbiddenError):
            self.engine.validate_environment_isolation(
                self.admin_ctx,
                source_env_code="staging_synthetic",
                target_action="connect_database",
                resource_ref="production_cluster_db"
            )

        # Destructive actions blocked in non-prod
        with self.assertRaises(ForbiddenError):
            self.engine.validate_environment_isolation(
                self.admin_ctx,
                source_env_code="local_dev",
                target_action="bulk_purge",
                resource_ref="local_table"
            )

        # Live payments blocked in staging
        with self.assertRaises(ForbiddenError):
            self.engine.validate_environment_isolation(
                self.admin_ctx,
                source_env_code="staging_synthetic",
                target_action="execute_live_payment",
                resource_ref="razorpay_live"
            )

        # Live messaging suppressed in local_dev
        msg_check = self.engine.validate_environment_isolation(
            self.admin_ctx,
            source_env_code="local_dev",
            target_action="send_live_sms_or_email",
            resource_ref="sms_gateway"
        )
        self.assertFalse(msg_check["allowed"])
        self.assertTrue(msg_check["routed_to_mock"])

    def test_preflight_validation_fail_closed(self):
        """Test startup preflight validation and fail-closed checks in production."""
        # 1. Staging preflight with missing required setting should return FAILED
        bad_env = {"MATAB_ENV": "staging"}  # Missing port, secret key, etc.
        res = self.engine.run_preflight_validation(self.admin_ctx, "staging_synthetic", runtime_env_dict=bad_env)
        self.assertEqual(res["status"], "FAILED")
        self.assertGreater(res["errors_count"], 0)

        # 2. Production preflight with default insecure key must fail
        insecure_prod = {
            "MATAB_ENV": "production",
            "MATAB_SECRET_KEY": "matab-os-standalone-secure-dev-key-2026",  # default insecure key!
            "MATAB_PORT": "8000",
            "MATAB_SESSION_HOURS": "12",
            "MATAB_ALLOWED_ORIGINS": "https://matab.example.com",
            "CLINICAL_SYSTEM_VERSION": "2026.10-LTS"
        }
        res_prod = self.engine.run_preflight_validation(self.admin_ctx, "production", runtime_env_dict=insecure_prod)
        self.assertEqual(res_prod["status"], "FAILED")
        err_types = [e["error_type"] for e in res_prod["errors"]]
        self.assertIn("INSECURE_PRODUCTION_SECRET", err_types)

        # 3. Production preflight with wildcard CORS origin must fail
        wildcard_prod = dict(insecure_prod)
        wildcard_prod["MATAB_SECRET_KEY"] = "a" * 32  # valid length
        wildcard_prod["MATAB_ALLOWED_ORIGINS"] = "*"
        res_cors = self.engine.run_preflight_validation(self.admin_ctx, "production", runtime_env_dict=wildcard_prod)
        self.assertEqual(res_cors["status"], "FAILED")
        err_types = [e["error_type"] for e in res_cors["errors"]]
        self.assertIn("PERMISSIVE_CORS", err_types)

        # 4. Valid production config passes
        valid_prod = {
            "MATAB_ENV": "production",
            "MATAB_SECRET_KEY": "super-secure-high-entropy-signing-key-32chars",
            "MATAB_PORT": "8000",
            "MATAB_SESSION_HOURS": "12",
            "MATAB_ALLOWED_ORIGINS": "https://matab.example.com,https://app.matab.org",
            "CLINICAL_SYSTEM_VERSION": "2026.10-LTS"
        }
        res_valid = self.engine.run_preflight_validation(self.admin_ctx, "production", runtime_env_dict=valid_prod)
        self.assertEqual(res_valid["status"], "PASSED")
        self.assertEqual(res_valid["errors_count"], 0)

    def test_secret_metadata_registration(self):
        """Test registering secret references and rejecting raw secret payloads."""
        payload = {
            "secret_name": "WHATSAPP_BUS_API_SECRET",
            "secret_type": "API_KEY",
            "provider_type": "VAULT",
            "provider_secret_ref": "vault://matab/prod/whatsapp-api-key",
            "environment_code": "production",
            "owner_team": "Communications Ops",
            "authorized_consumers_json": ["WhatsAppNotificationWorker"]
        }
        sec = self.engine.register_secret_reference(self.admin_ctx, payload)
        self.assertEqual(sec["secret_name"], "WHATSAPP_BUS_API_SECRET")
        self.assertEqual(sec["key_version"], "v1")

        # Reject payload containing raw secret
        with self.assertRaises(ValidationError):
            self.engine.register_secret_reference(self.admin_ctx, {
                "secret_name": "LEAKED_RAW_KEY",
                "secret_type": "API_KEY",
                "secret_value": "actual-secret-value-12345"
            })

    def test_secret_rotation_workflow(self):
        """Test multi-phase provider-aware secret rotation lifecycle."""
        secrets = self.engine.get_secret_references(self.admin_ctx)
        sec = secrets[0]

        # 1. Initiate rotation
        rot = self.engine.initiate_secret_rotation(self.admin_ctx, {
            "secret_ref_id": sec["id"],
            "rotation_reason": "ROUTINE_SECURITY_POLICY"
        })
        self.assertEqual(rot["state"], "planned")
        self.assertEqual(rot["old_key_version"], "v1")
        self.assertEqual(rot["new_key_version"], "v2")

        # Duplicate rotation initiation should fail
        with self.assertRaises(ConflictError):
            self.engine.initiate_secret_rotation(self.admin_ctx, {
                "secret_ref_id": sec["id"],
                "rotation_reason": "SCHEDULED_EXPIRY"
            })

        # 2. Advance to prepared
        step2 = self.engine.advance_secret_rotation(self.admin_ctx, rot["id"], "prepared", {"provider_ack": True})
        self.assertEqual(step2["state"], "prepared")

        # 3. Advance to updated
        step3 = self.engine.advance_secret_rotation(self.admin_ctx, rot["id"], "updated")
        self.assertEqual(step3["state"], "updated")

        # 4. Advance to verified
        step4 = self.engine.advance_secret_rotation(self.admin_ctx, rot["id"], "verified", {"consumer_health": "100%"})
        self.assertEqual(step4["state"], "verified")

        # 5. Retire old key
        step5 = self.engine.advance_secret_rotation(self.admin_ctx, rot["id"], "old_retired")
        self.assertEqual(step5["state"], "old_retired")

        # Verify secret reference updated to v2 and active
        updated_sec = self.engine.get_secret_reference(self.admin_ctx, sec["id"])
        self.assertEqual(updated_sec["key_version"], "v2")
        self.assertEqual(updated_sec["status"], "active")

    def test_urgent_compromise_revocation(self):
        """Test urgent incident revocation containment."""
        secrets = self.engine.get_secret_references(self.admin_ctx)
        sec = secrets[1]

        revoked = self.engine.urgent_compromise_revocation(
            self.ciso_ctx,
            sec["id"],
            incident_id="inc-sec-2026-009",
            rationale="Suspected credential exfiltration via compromised CI runner token."
        )
        self.assertEqual(revoked["status"], "compromised")
        self.assertEqual(revoked["incident_id"], "inc-sec-2026-009")

    def test_change_proposal_and_separation_of_duties(self):
        """Test proposal creation, approval (requester cannot self-approve), apply, and rollback."""
        proposal = self.engine.create_change_proposal(self.dev_ctx, {
            "title": "Enable Verbose Diagnostic Logging for Staging",
            "environment_code": "staging_synthetic",
            "change_category": "RUNTIME_SETTING",
            "diff_metadata_json": {"setting": "LOG_LEVEL", "new": "DEBUG"},
            "rollback_plan": "Revert LOG_LEVEL to INFO in staging config."
        })
        self.assertEqual(proposal["status"], "draft")

        # Developer attempts to self-approve with approve permission
        dev_as_approver = dict(self.dev_ctx)
        dev_as_approver["permissions"] = ["config:read", "config:approve"]
        with self.assertRaises(ForbiddenError):
            self.engine.approve_change_proposal(dev_as_approver, proposal["id"])

        # Platform Admin approves
        approved = self.engine.approve_change_proposal(self.admin_ctx, proposal["id"])
        self.assertEqual(approved["status"], "approved")

        # Apply proposal
        applied = self.engine.apply_change_proposal(self.dev_ctx, proposal["id"])
        self.assertEqual(applied["status"], "applied")

        # Rollback proposal
        rolled_back = self.engine.rollback_change_proposal(
            self.dev_ctx,
            proposal["id"],
            rationale="Staging log volume exceeded temporary quota."
        )
        self.assertEqual(rolled_back["status"], "rolled_back")

    def test_drift_scan_and_findings(self):
        """Test configuration drift detection."""
        # Run scan on production with missing required setting
        runtime_env = {"MATAB_ENV": "production"}  # Missing almost all keys
        scan = self.engine.run_drift_scan(self.admin_ctx, "production", runtime_env_dict=runtime_env)
        self.assertEqual(scan["status"], "drift_detected")
        self.assertGreater(scan["drift_count"], 0)

        # Scans list
        scans = self.engine.get_drift_scans(self.admin_ctx)
        self.assertGreaterEqual(len(scans), 1)

    def test_summary_and_audit_ledger(self):
        """Test governance summary and audit ledger entries."""
        summary = self.engine.get_governance_summary(self.admin_ctx)
        self.assertEqual(summary["organization_id"], "org-matab-default")
        self.assertGreaterEqual(summary["total_settings"], 5)
        self.assertIn("total_environments", summary)

        # Audit ledger
        events = self.engine.get_audit_ledger(self.admin_ctx)
        self.assertGreaterEqual(len(events), 1)

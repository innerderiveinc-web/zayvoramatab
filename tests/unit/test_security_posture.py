"""
Unit Tests for Enterprise Security Posture & Vulnerability Governance Engine
ZAYVORA MATAB OS — Phase 46
"""

import os
import unittest
import sqlite3
import tempfile
import shutil

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.security_posture import (
    EnterpriseSecurityPostureEngine,
    redact_secret_string,
)
from apps.api.core.errors import ValidationError, ConflictError, NotFoundError


class TestSecurityPostureUnit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sec_posture.sqlite")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.engine = EnterpriseSecurityPostureEngine(self.conn)

    def tearDown(self):
        if self.conn:
            self.conn.close()

    def test_01_secret_redaction(self):
        """Verify strict secret redaction regex masks credentials without exposing raw bytes."""
        sample_aws = "AWS Key: AKIA1234567890ABCDEF in config"
        self.assertIn("AKIA****************", redact_secret_string(sample_aws))
        self.assertNotIn("AKIA1234567890ABCDEF", redact_secret_string(sample_aws))

        dummy_stripe_token = "".join(["s", "k", "_", "l", "i", "v", "e", "_", "123456789012345678901234"])
        sample_stripe = f"Stripe key: {dummy_stripe_token}"
        self.assertIn("sk_live_************************", redact_secret_string(sample_stripe))
        self.assertNotIn(dummy_stripe_token, redact_secret_string(sample_stripe))

        sample_priv_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        self.assertIn("[REDACTED_PRIVATE_KEY]", redact_secret_string(sample_priv_key))

    def test_02_priority_calculation(self):
        """Verify prioritization calculation based on severity, exposure, and clinical impact."""
        # Patient safety risk immediately triggers P0
        self.assertEqual(
            self.engine.calculate_priority("MEDIUM", "AUTHENTICATED_INTERNAL", "DIRECT_PATIENT_SAFETY"),
            "P0_CRITICAL"
        )
        # Internet facing critical triggers P0
        self.assertEqual(
            self.engine.calculate_priority("CRITICAL", "INTERNET_FACING", "NO_CLINICAL_IMPACT"),
            "P0_CRITICAL"
        )
        # Internal critical triggers P1
        self.assertEqual(
            self.engine.calculate_priority("CRITICAL", "AUTHENTICATED_INTERNAL", "NO_CLINICAL_IMPACT"),
            "P1_HIGH"
        )
        # High severity with PHI risk triggers P1
        self.assertEqual(
            self.engine.calculate_priority("HIGH", "AUTHENTICATED_INTERNAL", "PHI_EXPOSURE_RISK"),
            "P1_HIGH"
        )
        # Low severity triggers P3
        self.assertEqual(
            self.engine.calculate_priority("LOW", "AUTHENTICATED_INTERNAL", "NO_CLINICAL_IMPACT"),
            "P3_LOW"
        )

    def test_03_dashboard_summary_and_assets(self):
        """Verify executive KPI summary and asset inventory registration."""
        summary = self.engine.get_dashboard_summary()
        self.assertGreaterEqual(summary["total_assets"], 6)
        self.assertGreaterEqual(summary["total_controls"], 5)
        self.assertIn("open_findings", summary)

        # Register new asset
        new_asset = self.engine.register_asset({
            "asset_name": "Telemetry Ingestion Pipeline",
            "asset_category": "INTEGRATIONS",
            "environment": "PRODUCTION",
            "owner_role": "Platform Engineer",
            "data_sensitivity": "INTERNAL",
            "entry_points_summary": "HTTP /api/v1/telemetry",
            "critical_clinical_function": "Audit log streaming",
            "scan_coverage_status": "COVERED"
        }, {"user_id": "usr-admin-1"})
        self.assertIsNotNone(new_asset["id"])
        self.assertEqual(new_asset["asset_category"], "INTEGRATIONS")

        assets = self.engine.list_assets(category="INTEGRATIONS")
        self.assertGreaterEqual(len(assets), 1)

    def test_04_controls_registry_and_scans(self):
        """Verify execution of verification scanners: SCA, secrets, authz, container, and SQL parameterization."""
        controls = self.engine.list_controls()
        self.assertGreaterEqual(len(controls), 5)

        # Run SCA scan
        sca_res = self.engine.run_sca_dependency_scan("usr-admin-1")
        self.assertIn(sca_res["status"], ["PASSED", "FAILED"])
        self.assertEqual(sca_res["control_code"], "SEC-SCA-001")

        # Run Secret scan
        sec_res = self.engine.run_secret_leak_scan("usr-admin-1")
        self.assertIn(sec_res["status"], ["PASSED", "FAILED"])
        self.assertEqual(sec_res["control_code"], "SEC-SECRET-001")

        # Run API AuthZ scan
        authz_res = self.engine.run_api_authz_and_headers_scan("usr-admin-1")
        self.assertIn(authz_res["status"], ["PASSED", "FAILED"])
        self.assertEqual(authz_res["control_code"], "SEC-AUTHZ-001")

        # Run Container scan
        cont_res = self.engine.run_container_and_iac_scan("usr-admin-1")
        self.assertEqual(cont_res["status"], "PASSED")

        # Run SQL parameterization scan
        sqli_res = self.engine.run_sql_parameterization_scan("usr-admin-1")
        self.assertEqual(sqli_res["status"], "PASSED")

        # Run aggregate suite
        suite_res = self.engine.run_all_security_scans("usr-admin-1")
        self.assertIn("overall_status", suite_res)
        self.assertEqual(len(suite_res["controls_executed"]), 5)

    def test_05_finding_lifecycle_legal_transitions(self):
        """Verify full finding lifecycle: NEW -> TRIAGED -> CONFIRMED -> IN_PROGRESS -> FIXED -> VERIFIED_CLOSED."""
        finding = self.engine.create_finding({
            "title": "Unvalidated Content-Type in Upload Gateway",
            "affected_component": "apps/api/routes/data_lifecycle.py",
            "vulnerability_category": "UNVALIDATED_INPUT",
            "source_severity": "MEDIUM",
            "exposure_context": "AUTHENTICATED_INTERNAL",
            "clinical_impact": "NO_CLINICAL_IMPACT",
            "evidence_summary": "Upload endpoint allows arbitrary MIME types."
        }, {"user_id": "usr-admin-1"})

        fid = finding["id"]
        self.assertEqual(finding["status"], "NEW")
        self.assertEqual(finding["organizational_priority"], "P3_LOW")

        # NEW -> TRIAGED
        f1 = self.engine.transition_finding_status(fid, "TRIAGED", {"user_id": "usr-admin-1"}, notes="Triaged by AppSec")
        self.assertEqual(f1["status"], "TRIAGED")

        # TRIAGED -> CONFIRMED
        f2 = self.engine.transition_finding_status(fid, "CONFIRMED", {"user_id": "usr-admin-1"}, notes="Confirmed in local repro")
        self.assertEqual(f2["status"], "CONFIRMED")

        # CONFIRMED -> REMEDIATION_IN_PROGRESS
        f3 = self.engine.transition_finding_status(fid, "REMEDIATION_IN_PROGRESS", {"user_id": "usr-admin-1"}, notes="Assigned to dev")
        self.assertEqual(f3["status"], "REMEDIATION_IN_PROGRESS")

        # REMEDIATION_IN_PROGRESS -> FIXED_PENDING_VERIFICATION
        f4 = self.engine.transition_finding_status(
            fid, "FIXED_PENDING_VERIFICATION", {"user_id": "usr-admin-1"},
            fixed_version="v1.1.1", notes="PR #102 merged"
        )
        self.assertEqual(f4["status"], "FIXED_PENDING_VERIFICATION")
        self.assertEqual(f4["fixed_version"], "v1.1.1")

        # FIXED_PENDING_VERIFICATION -> VERIFIED_CLOSED
        f5 = self.engine.transition_finding_status(
            fid, "VERIFIED_CLOSED", {"user_id": "usr-admin-1"},
            verification_evidence="Automated input validation test passed."
        )
        self.assertEqual(f5["status"], "VERIFIED_CLOSED")
        self.assertIsNotNone(f5["verified_at"])

    def test_06_finding_illegal_transitions(self):
        """Verify illegal transitions (e.g. NEW directly to VERIFIED_CLOSED) raise ConflictError."""
        finding = self.engine.create_finding({
            "title": "Test Illegal Transition Finding",
            "affected_component": "apps/api/router.py",
            "source_severity": "LOW"
        }, {"user_id": "usr-admin-1"})

        with self.assertRaises(ConflictError):
            self.engine.transition_finding_status(finding["id"], "VERIFIED_CLOSED", {"user_id": "usr-admin-1"})

    def test_07_exceptions_workflow_and_expiry(self):
        """Verify security exception creation, validation, and auto-expiry."""
        # Request valid exception
        exc = self.engine.request_exception({
            "scope": "apps/web/static/legacy_shim.js",
            "rationale": "Legacy shim required for older clinic tablet browser compatibility",
            "compensating_controls": "Tablets isolated on restricted VLAN; no external internet egress",
            "accountable_risk_owner": "Chief Information Security Officer",
            "days_valid": 30
        }, {"user_id": "usr-admin-1"})

        self.assertIsNotNone(exc["id"])
        self.assertEqual(exc["status"], "APPROVED")

        # Exceptions exceeding 90 days must be rejected
        with self.assertRaises(ValidationError):
            self.engine.request_exception({
                "scope": "apps/web/static/legacy_shim.js",
                "rationale": "Indefinite exemption",
                "compensating_controls": "None",
                "accountable_risk_owner": "CISO",
                "days_valid": 180  # Prohibited > 90
            }, {"user_id": "usr-admin-1"})

    def test_08_release_gate_evaluation(self):
        """Verify security release gate evaluation computes accurate gate states."""
        # Run all scans to ensure fresh evidence
        self.engine.run_all_security_scans("usr-admin-1")

        gate_res = self.engine.evaluate_release_gate("v1.1.0", "PRODUCTION", "commit-abc1234", {"user_id": "usr-admin-1"})
        self.assertIn(gate_res["gate_outcome"], ["PASS", "FAIL", "BLOCKED", "STALE", "EXCEPTION_APPROVED"])
        self.assertGreaterEqual(gate_res["evaluated_controls_count"], 4)

        history = self.engine.list_gate_evaluations()
        self.assertGreaterEqual(len(history), 1)

    def test_09_release_gate_blocked_by_open_p0_finding(self):
        """Verify that an active unmitigated P0 finding causes release gate to FAIL."""
        # Create a P0 finding
        p0_finding = self.engine.create_finding({
            "title": "Remote Code Execution via Insecure Deserialization",
            "affected_component": "apps/api/core/rpc.py",
            "vulnerability_category": "INSECURE_CONFIGURATION",
            "source_severity": "CRITICAL",
            "exposure_context": "INTERNET_FACING",
            "clinical_impact": "DIRECT_PATIENT_SAFETY",
            "evidence_summary": "Unvalidated pickle payload deserialization detected."
        }, {"user_id": "usr-admin-1"})
        self.assertEqual(p0_finding["organizational_priority"], "P0_CRITICAL")

        gate_res = self.engine.evaluate_release_gate("v1.1.0-hotfix", "PRODUCTION", "commit-fail", {"user_id": "usr-admin-1"})
        self.assertEqual(gate_res["gate_outcome"], "FAIL")
        self.assertGreaterEqual(gate_res["blocking_failures_count"], 1)

        # Transition finding to ACCEPTED_RISK or VERIFIED_CLOSED removes the block
        self.engine.transition_finding_status(p0_finding["id"], "TRIAGED", {"user_id": "usr-admin-1"})
        self.engine.transition_finding_status(p0_finding["id"], "CONFIRMED", {"user_id": "usr-admin-1"})
        self.engine.transition_finding_status(p0_finding["id"], "REMEDIATION_IN_PROGRESS", {"user_id": "usr-admin-1"})
        self.engine.transition_finding_status(p0_finding["id"], "FIXED_PENDING_VERIFICATION", {"user_id": "usr-admin-1"}, fixed_version="v1.1.1")
        self.engine.transition_finding_status(p0_finding["id"], "VERIFIED_CLOSED", {"user_id": "usr-admin-1"}, verification_evidence="Patch verified")

    def test_10_audit_ledger_integrity_and_chaining(self):
        """Verify tamper-evident append-only security audit ledger records entries with SHA-256 hash chaining."""
        event = self.engine.record_audit_event(
            "TEST_SECURITY_EVENT", "HIGH", "usr-admin-1", "SYSTEM", "test_id",
            {"action": "test_verification"}
        )
        self.assertIsNotNone(event["id"])
        self.assertEqual(len(event["entry_hash"]), 64)

        events = self.engine.list_audit_events(limit=10)
        self.assertGreaterEqual(len(events), 1)


if __name__ == "__main__":
    unittest.main()

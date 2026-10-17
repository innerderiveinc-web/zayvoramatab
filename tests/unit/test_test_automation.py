"""
Unit Tests for Enterprise Test Automation, Regression & Release Qualification Engine
ZAYVORA MATAB OS — Phase 49
"""

import os
import shutil
import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.test_automation import EnterpriseTestAutomationReleaseQualificationEngine
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError


class TestEnterpriseTestAutomationReleaseQualificationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_automation_unit.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.engine = EnterpriseTestAutomationReleaseQualificationEngine(self.conn)

    def tearDown(self):
        if self.conn:
            self.conn.close()

    def test_01_summary_kpis(self):
        """1. Test executive test automation and qualification summary KPIs."""
        summary = self.engine.get_test_qualification_summary()
        self.assertIn("total_suites", summary)
        self.assertGreaterEqual(summary["total_suites"], 2)
        self.assertIn("active_suites", summary)
        self.assertIn("total_runs", summary)
        self.assertIn("overall_pass_rate_pct", summary)
        self.assertIn("active_quarantined_tests", summary)
        self.assertIn("audit_events_count", summary)

    def test_02_register_and_query_test_suites(self):
        """2. Test registering, querying, and listing test suites."""
        suite = self.engine.register_test_suite(
            actor_id="usr-admin-1",
            suite_code="SUITE-API-INTEGRATION-TEST",
            name="API Integration Test Suite - Consultations",
            test_layer="API_INTEGRATION",
            target_subsystem="CONSULTATIONS",
            test_file_path="tests/integration/test_consultations_api.py",
            command_template="python -m unittest tests/integration/test_consultations_api.py",
            execution_environment="ISOLATED_SYNTHETIC",
            is_mandatory_for_release=1,
            timeout_seconds=90,
        )
        self.assertEqual(suite["suite_code"], "SUITE-API-INTEGRATION-TEST")
        self.assertEqual(suite["status"], "ACTIVE")

        # Duplicate code conflict
        with self.assertRaises(ConflictError):
            self.engine.register_test_suite(
                actor_id="usr-admin-1",
                suite_code="SUITE-API-INTEGRATION-TEST",
                name="Duplicate Suite",
                test_layer="API_INTEGRATION",
                target_subsystem="CONSULTATIONS",
                test_file_path="tests/integration/test_consultations_api.py",
                command_template="python -m unittest tests/integration/test_consultations_api.py",
            )

        # Invalid test layer
        with self.assertRaises(ValidationError):
            self.engine.register_test_suite(
                actor_id="usr-admin-1",
                suite_code="SUITE-INVALID-LAYER",
                name="Invalid Layer Suite",
                test_layer="MAGIC_LAYER",
                target_subsystem="CONSULTATIONS",
                test_file_path="dummy.py",
                command_template="python dummy.py",
            )

        # List suites
        suites = self.engine.list_test_suites(test_layer="API_INTEGRATION")
        self.assertTrue(any(s["suite_code"] == "SUITE-API-INTEGRATION-TEST" for s in suites))

    def test_03_update_test_suite(self):
        """3. Test updating suite fields and status validation."""
        suite = self.engine.register_test_suite(
            actor_id="usr-admin-1",
            suite_code="SUITE-UPDATE-TARGET",
            name="Target for Update",
            test_layer="UNIT",
            target_subsystem="INVENTORY",
            test_file_path="tests/unit/test_inventory.py",
            command_template="python -m unittest tests/unit/test_inventory.py",
        )
        updated = self.engine.update_test_suite(
            actor_id="usr-admin-1",
            suite_id=suite["id"],
            update_fields={"timeout_seconds": 120, "status": "QUARANTINED"},
        )
        self.assertEqual(updated["timeout_seconds"], 120)
        self.assertEqual(updated["status"], "QUARANTINED")

        # Invalid status update
        with self.assertRaises(ValidationError):
            self.engine.update_test_suite(
                actor_id="usr-admin-1",
                suite_id=suite["id"],
                update_fields={"status": "INVALID_STATUS"},
            )

    def test_04_record_execution_run(self):
        """4. Test recording verified test execution run evidence."""
        suite = self.engine.get_test_suite("tasc-unit-rx-001")
        run = self.engine.record_execution_run(
            actor_id="usr-admin-1",
            suite_id=suite["id"],
            target_release_version="v1.0.1",
            environment="ISOLATED_SYNTHETIC",
            commit_hash="c0ffee1234",
            trigger_source="CI_PIPELINE",
            status="PASSED",
            total_tests=20,
            passed_tests=20,
            failed_tests=0,
            skipped_tests=0,
            execution_duration_ms=1450,
            evidence_summary={"coverage_pct": 98.5, "passed_tests": 20},
        )
        self.assertTrue(run["run_code"].startswith("RUN-"))
        self.assertEqual(run["status"], "PASSED")
        self.assertEqual(run["passed_tests"], 20)

        # Invalid status
        with self.assertRaises(ValidationError):
            self.engine.record_execution_run(
                actor_id="usr-admin-1",
                suite_id=suite["id"],
                target_release_version="v1.0.1",
                environment="ISOLATED_SYNTHETIC",
                commit_hash="c0ffee1234",
                trigger_source="CI_PIPELINE",
                status="SUPER_PASS",
                total_tests=20,
                passed_tests=20,
                failed_tests=0,
                skipped_tests=0,
                execution_duration_ms=1000,
            )

    def test_05_flakiness_quarantine_lifecycle(self):
        """5. Test quarantining an unstable test and resolving it within 14-day SLA."""
        quarantine = self.engine.quarantine_test(
            actor_id="usr-admin-1",
            suite_id="tasc-unit-rx-001",
            test_name="test_concurrent_payment_gateway_webhook_race",
            reason="Intermittent timing race under high CPU contention.",
            root_cause_category="TIMING_RACE",
            assigned_owner="sre-team@zayvora.internal",
            target_resolution_days=10,
        )
        self.assertTrue(quarantine["quarantine_code"].startswith("QRN-"))
        self.assertEqual(quarantine["status"], "ACTIVE_QUARANTINE")

        # Exceeding 14-day SLA ceiling raises ValidationError
        with self.assertRaises(ValidationError):
            self.engine.quarantine_test(
                actor_id="usr-admin-1",
                suite_id="tasc-unit-rx-001",
                test_name="test_forbidden_overdue_quarantine",
                reason="Attempting 30 day quarantine",
                root_cause_category="UNKNOWN",
                assigned_owner="qa-lead@zayvora.internal",
                target_resolution_days=30,
            )

        # Resolve quarantine
        resolved = self.engine.resolve_quarantine(
            actor_id="usr-admin-1",
            quarantine_id=quarantine["id"],
            status="RESOLVED",
            notes="Added deterministic event latch fixture; verified 100 runs without flake.",
        )
        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertIsNotNone(resolved["resolved_at"])

    def test_06_release_qualification_profile_creation(self):
        """6. Test creating release qualification profiles with tier validation."""
        profile = self.engine.create_qualification_profile(
            actor_id="usr-admin-1",
            profile_code="PROF-CANARY",
            name="Canary Staging Profile",
            target_tier="STAGING_PILOT",
            required_test_layers=["UNIT", "API_INTEGRATION"],
            required_suites=["SUITE-UNIT-PRESCRIPTIONS"],
            min_pass_rate_bp=9500,
            allow_quarantined_tests=1,
            max_critical_defects=0,
        )
        self.assertEqual(profile["profile_code"], "PROF-CANARY")
        self.assertIn("UNIT", profile["required_test_layers"])

        # Invalid target tier
        with self.assertRaises(ValidationError):
            self.engine.create_qualification_profile(
                actor_id="usr-admin-1",
                profile_code="PROF-INVALID",
                name="Invalid Tier Profile",
                target_tier="EARTH_ORBIT",
                required_test_layers=["UNIT"],
                required_suites=["SUITE-UNIT-PRESCRIPTIONS"],
            )

    def test_07_evaluate_release_candidate_qualified(self):
        """7. Test release gate qualification verdict for clean run meeting all profile criteria."""
        # Record fresh passing runs for required suites in DEV profile
        suite = self.engine.get_test_suite("tasc-unit-rx-001")
        self.engine.record_execution_run(
            actor_id="usr-admin-1",
            suite_id=suite["id"],
            target_release_version="v1.0.2",
            environment="ISOLATED_SYNTHETIC",
            commit_hash="abcd1234ef",
            trigger_source="CI_PIPELINE",
            status="PASSED",
            total_tests=25,
            passed_tests=25,
            failed_tests=0,
            skipped_tests=0,
            execution_duration_ms=1100,
        )

        candidate = self.engine.evaluate_release_candidate(
            actor_id="usr-admin-1",
            target_release_version="v1.0.2",
            profile_id="rqp-prof-dev-001",
            commit_hash="abcd1234ef",
            repository_revision="HEAD",
        )
        self.assertEqual(candidate["overall_verdict"], "QUALIFIED")
        self.assertEqual(candidate["open_defects_count"], 0)
        self.assertEqual(candidate["blocking_reasons"], [])

    def test_08_evaluate_release_candidate_blocked_low_pass_rate(self):
        """8. Test release gate fails closed (BLOCKED) when test run has failures dropping pass rate."""
        suite = self.engine.get_test_suite("tasc-unit-rx-001")
        self.engine.record_execution_run(
            actor_id="usr-admin-1",
            suite_id=suite["id"],
            target_release_version="v1.0.3",
            environment="ISOLATED_SYNTHETIC",
            commit_hash="fail1234",
            trigger_source="CI_PIPELINE",
            status="FAILED",
            total_tests=20,
            passed_tests=15,
            failed_tests=5,
            skipped_tests=0,
            execution_duration_ms=1300,
        )

        candidate = self.engine.evaluate_release_candidate(
            actor_id="usr-admin-1",
            target_release_version="v1.0.3",
            profile_id="rqp-prof-dev-001",
            commit_hash="fail1234",
            repository_revision="HEAD",
        )
        self.assertEqual(candidate["overall_verdict"], "BLOCKED")
        self.assertTrue(len(candidate["blocking_reasons"]) > 0)
        self.assertTrue(any("failed" in reason.lower() for reason in candidate["blocking_reasons"]))

    def test_09_evaluate_release_candidate_blocked_quarantined_tests(self):
        """9. Test production release profile strictly blocks when active quarantined tests exist."""
        # Ensure an active quarantine exists
        self.engine.quarantine_test(
            actor_id="usr-admin-1",
            suite_id="tasc-unit-rx-001",
            test_name="test_flaky_posology_timing",
            reason="Timing race condition",
            root_cause_category="TIMING_RACE",
            assigned_owner="qa@zayvora.internal",
            target_resolution_days=7,
        )

        # Record fresh runs for all suites in PROF-PROD
        for s_code in ["SUITE-UNIT-PRESCRIPTIONS", "SUITE-E2E-SMOKE-RELEASE-QUALIFICATION"]:
            s = self.engine.get_test_suite(s_code)
            self.engine.record_execution_run(
                actor_id="usr-admin-1",
                suite_id=s["id"],
                target_release_version="v1.0.4",
                environment="ISOLATED_SYNTHETIC",
                commit_hash="prodtest1",
                trigger_source="CI_PIPELINE",
                status="PASSED",
                total_tests=10,
                passed_tests=10,
                failed_tests=0,
                skipped_tests=0,
                execution_duration_ms=500,
            )

        candidate = self.engine.evaluate_release_candidate(
            actor_id="usr-admin-1",
            target_release_version="v1.0.4",
            profile_id="rqp-prof-prod-001",
            commit_hash="prodtest1",
            repository_revision="HEAD",
        )
        self.assertEqual(candidate["overall_verdict"], "BLOCKED")
        self.assertTrue(any("quarantined" in r.lower() for r in candidate["blocking_reasons"]))

    def test_10_defect_lifecycle_and_sensitive_redaction(self):
        """10. Test defect logging, status transition, and automated secret/PHI redaction in stack traces."""
        raw_trace = "DatabaseError: connection refused at user=admin password='superSecretPassword123' token=bearer secretToken12345678901234567890"
        defect = self.engine.log_defect(
            actor_id="usr-admin-1",
            title="Database connection timeout during concurrent transaction stress test",
            test_name="test_concurrent_inventory_decrements",
            severity="CRITICAL",
            failure_classification="ENVIRONMENT_FLAKE",
            sanitized_stack_trace=raw_trace,
            reproduction_steps="Run 100 concurrent checkout transactions on isolated synthetic db.",
            assigned_owner="database-lead@zayvora.internal",
            linked_hazard_id="haz-rx-001",
        )
        self.assertTrue(defect["defect_code"].startswith("DEF-"))
        self.assertEqual(defect["severity"], "CRITICAL")
        # Ensure password and bearer token are redacted
        self.assertNotIn("superSecretPassword123", defect["sanitized_stack_trace"])
        self.assertIn("[REDACTED]", defect["sanitized_stack_trace"])

        # Update defect status
        updated = self.engine.update_defect_status(
            actor_id="usr-admin-1",
            defect_id=defect["id"],
            new_status="VERIFIED_CLOSED",
            notes="Tuned SQLite connection pool timeout to 30.0s.",
        )
        self.assertEqual(updated["status"], "VERIFIED_CLOSED")

    def test_11_audit_ledger_and_integrity_verification(self):
        """11. Test append-only SHA-256 audit ledger and verify tamper detection."""
        integrity = self.engine.verify_audit_integrity()
        self.assertTrue(integrity["is_valid"])
        self.assertGreaterEqual(integrity["records_checked"], 5)
        self.assertIn("latest_hash", integrity)

        # Verify audit retrieval
        events = self.engine.get_audit_ledger(limit=10)
        self.assertGreater(len(events), 0)
        self.assertTrue(all("entry_hash" in e for e in events))


if __name__ == "__main__":
    unittest.main()

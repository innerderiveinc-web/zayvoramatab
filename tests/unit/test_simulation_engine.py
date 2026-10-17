"""Unit tests for Enterprise Workflow Simulation, Failure Injection & Recovery Validation Engine.

Phase 37 for ZAYVORA MATAB OS.
Tests:
1. Scenario Draft Creation, Schema Validation & Constraints.
2. Scenario Status Lifecycle (DRAFT -> IN_REVIEW -> APPROVED -> RETIRED).
3. Separation of Duties on High-Risk Scenario Approval (Author cannot approve).
4. Production Lockout Guard (Simulation strictly prohibited in production).
5. Isolated Run Execution with Dry-Run Namespace Tracking.
6. Controlled Fault Injection (TIMEOUT, CIRCUIT_TRIPPED, DUPLICATE_DELIVERY).
7. Clinical Safety Boundary: Autonomous Prescribing Hard Block (403 Forbidden).
8. Separation of Duties Boundary: Self-Verification Hard Block (403 Forbidden).
9. Deterministic Canonical Assertion Engine Evaluation.
10. Idempotent Synthetic Fixture Teardown & Cleanup.
11. Release Gate Readiness Evaluation.
12. Simulation Pulse Summary Observability.
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.simulation import WorkflowSimulationEngine
from apps.api.core.errors import ValidationError, ConflictError, NotFoundError, ForbiddenError


class TestWorkflowSimulationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_simulation_engine.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = WorkflowSimulationEngine(db_path=cls.db_path)

        conn = cls.engine._get_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        cls.admin_id = admin_row["id"]
        cls.org_id = admin_row["organization_id"]

        cur.execute("SELECT id FROM users WHERE username = 'hakeem' LIMIT 1;")
        hakeem_row = cur.fetchone()
        cls.hakeem_id = hakeem_row["id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-central-opd"

        conn.close()

        cls.admin_ctx = {
            "id": cls.admin_id,
            "user_id": cls.admin_id,
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
            "role": "SYSTEM_ADMIN"
        }

        cls.hakeem_ctx = {
            "id": cls.hakeem_id,
            "user_id": cls.hakeem_id,
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
            "role": "CLINICIAN"
        }

    # --------------------------------------------------------------------------
    # 1. Scenario Registry & Validation
    # --------------------------------------------------------------------------

    def test_01_create_scenario_draft_and_validation(self):
        """Test creating a valid scenario draft and schema validation."""
        data = {
            "name": "Integration Connector Timeout Simulation",
            "category": "dependency_faults",
            "risk_level": "moderate",
            "environment_allowlist": ["local", "dev", "sandbox"],
            "steps": [
                {
                    "step_order": 1,
                    "action_type": "INVOKE_CONNECTOR",
                    "target_service": "integration_ops",
                    "fault": {"fault_type": "TIMEOUT", "delay_ms": 100}
                }
            ],
            "assertions": [
                {
                    "assertion_key": "assert-timeout",
                    "assertion_type": "RECORD_EXISTS",
                    "expected_condition": "count >= 1",
                    "target_table": "simulation_step_executions",
                    "filter_field": "fault_injected",
                    "filter_value": "TIMEOUT"
                }
            ]
        }
        scen = self.engine.create_scenario_draft(data, self.admin_ctx)
        self.assertEqual(scen["status"], "DRAFT")
        self.assertEqual(scen["risk_level"], "moderate")
        self.assertEqual(len(scen["steps"]), 1)

        # Invalid category
        inv_cat = dict(data, category="invalid_cat")
        with self.assertRaises(ValidationError):
            self.engine.create_scenario_draft(inv_cat, self.admin_ctx)

        # Invalid risk level
        inv_risk = dict(data, risk_level="critical_danger")
        with self.assertRaises(ValidationError):
            self.engine.create_scenario_draft(inv_risk, self.admin_ctx)

    def test_02_scenario_lifecycle_and_separation_of_duties(self):
        """Test status transitions and separation of duties on high-risk scenarios."""
        # Create high-risk scenario authored by admin
        data = {
            "name": "Autonomous Treatment Verification High Risk",
            "category": "clinical_safety_boundary",
            "risk_level": "high",
            "steps": [{"step_order": 1, "action_type": "ATTEMPT_AUTONOMOUS_PRESCRIPTION"}],
            "assertions": [{"assertion_key": "assert-blocked", "assertion_type": "PERMISSION_DENIED"}]
        }
        scen = self.engine.create_scenario_draft(data, self.admin_ctx)
        sid = scen["id"]

        # DRAFT -> IN_REVIEW
        in_review = self.engine.advance_scenario_status(sid, "submit_for_review", self.admin_ctx)
        self.assertEqual(in_review["status"], "IN_REVIEW")

        # SEPARATION OF DUTIES: Admin authored high-risk scenario; Admin cannot self-approve -> FORBIDDEN
        with self.assertRaises(ForbiddenError):
            self.engine.advance_scenario_status(sid, "approve", self.admin_ctx)

        # Independent review & approval by Hakeem -> SUCCESS
        approved = self.engine.advance_scenario_status(sid, "approve", self.hakeem_ctx, reason="Clinical peer approval")
        self.assertEqual(approved["status"], "APPROVED")
        self.assertEqual(approved["approved_by"], self.hakeem_id)

        # Direct edit on approved scenario is blocked
        with self.assertRaises(ConflictError):
            self.engine.update_scenario_draft(sid, {"name": "Should Fail"}, self.admin_ctx)

    # --------------------------------------------------------------------------
    # 2. Production Lockout & Safety
    # --------------------------------------------------------------------------

    def test_03_production_lockout_guard(self):
        """Failure injection and simulation must be hard-blocked in production."""
        os.environ["ENVIRONMENT"] = "production"
        try:
            with self.assertRaises(ForbiddenError):
                self.engine.launch_simulation_run("scen-syn-001", {}, self.admin_ctx)
        finally:
            os.environ["ENVIRONMENT"] = "development"

    # --------------------------------------------------------------------------
    # 3. Simulation Runner & Fault Execution
    # --------------------------------------------------------------------------

    def test_04_execute_seeded_duplicate_event_scenario(self):
        """Execute sim-scen-001: duplicate event idempotency & task suppression."""
        run_res = self.engine.launch_simulation_run("scen-syn-001", {"environment": "local"}, self.admin_ctx)
        self.assertEqual(run_res["scenario_key"], "sim-scen-duplicate-intake")
        self.assertEqual(run_res["is_dry_run"], 1)
        self.assertTrue(run_res["namespace_prefix"].startswith("sim-"))
        self.assertEqual(run_res["status"], "CLEANED_UP")
        self.assertEqual(run_res["passed_assertions_count"], 1)

    def test_05_execute_circuit_breaker_fault_scenario(self):
        """Execute sim-scen-005: connector circuit breaker trip & state verification."""
        run_res = self.engine.launch_simulation_run("scen-syn-005", {"environment": "local"}, self.admin_ctx)
        self.assertEqual(run_res["scenario_key"], "sim-scen-dlq-circuit-breaker")
        self.assertEqual(run_res["status"], "CLEANED_UP")
        self.assertEqual(run_res["passed_assertions_count"], 1)

        # Verify step recorded fault injection
        step_exec = run_res["steps"][0]
        self.assertEqual(step_exec["fault_injected"], "CIRCUIT_TRIPPED")

    def test_06_clinical_safety_boundary_autonomous_prescribing_block(self):
        """Execute sim-scen-004: assert autonomous prescription is strictly rejected (403)."""
        run_res = self.engine.launch_simulation_run("scen-syn-004", {"environment": "local"}, self.admin_ctx)
        self.assertEqual(run_res["scenario_key"], "sim-scen-clinical-safety-block")
        self.assertEqual(run_res["status"], "CLEANED_UP")
        self.assertEqual(run_res["passed_assertions_count"], 1)

        # Assertion verifies PERMISSION_DENIED
        assertion = run_res["assertions"][0]
        self.assertEqual(assertion["status"], "passed")
        self.assertIn("403", assertion["observed_result"])

    def test_07_separation_of_duties_self_verification_block(self):
        """Execute sim-scen-006: assert resolver cannot self-verify exception."""
        run_res = self.engine.launch_simulation_run("scen-syn-006", {"environment": "local"}, self.admin_ctx)
        self.assertEqual(run_res["scenario_key"], "sim-scen-sod-verification-block")
        self.assertEqual(run_res["status"], "CLEANED_UP")
        self.assertEqual(run_res["passed_assertions_count"], 1)

    def test_08_side_effect_suppression_notification_timeout(self):
        """Execute sim-scen-002: verify notification side effects are suppressed (zero real network calls)."""
        run_res = self.engine.launch_simulation_run("scen-syn-002", {"environment": "local"}, self.admin_ctx)
        self.assertEqual(run_res["scenario_key"], "sim-scen-adapter-timeout-retry")
        self.assertEqual(run_res["status"], "CLEANED_UP")
        self.assertEqual(run_res["passed_assertions_count"], 1)

    # --------------------------------------------------------------------------
    # 4. Release Gate & Observability
    # --------------------------------------------------------------------------

    def test_09_evaluate_release_gate(self):
        """Evaluate release gate for target commit/version tag."""
        # Execute remaining approved scenarios so gate can pass
        self.engine.launch_simulation_run("scen-syn-003", {"environment": "local"}, self.admin_ctx)

        seed_ids = ["scen-syn-001", "scen-syn-002", "scen-syn-003", "scen-syn-004", "scen-syn-005", "scen-syn-006"]
        gate = self.engine.evaluate_release_gate("v2026.10.14-release-1", self.admin_ctx, scenario_ids=seed_ids)
        self.assertIn("evaluation_status", gate)
        self.assertEqual(gate["evaluation_status"], "PASS")
        self.assertEqual(gate["total_scenarios_evaluated"], 6)
        self.assertEqual(gate["passed_scenarios_count"], 6)
        self.assertEqual(gate["failed_scenarios_count"], 0)

    def test_10_simulation_pulse_summary(self):
        """Verify real-time simulation metrics pulse and governance caveats."""
        pulse = self.engine.get_simulation_pulse_summary({}, self.admin_ctx)
        self.assertIn("total_scenarios", pulse)
        self.assertIn("approved_scenarios", pulse)
        self.assertIn("total_runs", pulse)
        self.assertIn("passed_runs", pulse)
        self.assertIn("latest_release_gate", pulse)
        self.assertTrue(any("production" in c.lower() for c in pulse["caveats"]))


if __name__ == "__main__":
    unittest.main()

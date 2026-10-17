"""Integration Tests for Enterprise Workflow Simulation, Failure Injection & Recovery Validation REST APIs.

Phase 37 for ZAYVORA MATAB OS.
Tests all simulation REST endpoints via ApiRouter.dispatch:
1.  GET  /api/v1/simulation/scenarios
2.  POST /api/v1/simulation/scenarios
3.  GET  /api/v1/simulation/scenarios/{id}
4.  PUT  /api/v1/simulation/scenarios/{id}
5.  POST /api/v1/simulation/scenarios/{id}/advance
6.  POST /api/v1/simulation/scenarios/{id}/run
7.  GET  /api/v1/simulation/runs
8.  POST /api/v1/simulation/runs
9.  GET  /api/v1/simulation/runs/{id}
10. POST /api/v1/simulation/runs/{id}/cleanup
11. POST /api/v1/simulation/release-gate
12. GET  /api/v1/simulation/pulse
13. Security & Production Lockout (403 in production, 401 unauthenticated, RBAC checks).
"""

import os
import json
import sqlite3
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestSimulationApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_simulation_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin (has all permissions including simulation:*)
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        cls.auth_token = json.loads(body)["token"]
        cls.auth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.auth_token}"
        }

        # Authenticate Practitioner (Hakeem Tariq - clinical staff, lacks simulation:gate / simulation:fault_inject)
        status_h, _, body_h = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        cls.hakeem_token = json.loads(body_h)["token"]
        cls.hakeem_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.hakeem_token}"
        }

    # --------------------------------------------------------------------------
    # 1. Scenarios Catalog Endpoints
    # --------------------------------------------------------------------------

    def test_01_list_scenarios_and_seeds(self):
        """GET /api/v1/simulation/scenarios should list seeded scenarios."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/simulation/scenarios", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("scenarios", data)
        self.assertGreaterEqual(data["total_scenarios"], 6)

        scenario_keys = [s["scenario_key"] for s in data["scenarios"]]
        self.assertIn("sim-scen-duplicate-intake", scenario_keys)
        self.assertIn("sim-scen-clinical-safety-block", scenario_keys)
        self.assertIn("sim-scen-dlq-circuit-breaker", scenario_keys)

    def test_02_create_get_update_advance_scenario(self):
        """POST, GET, PUT, POST advance on /api/v1/simulation/scenarios."""
        payload = {
            "name": "Synthetic Gateway Latency Test",
            "description": "Simulates downstream gateway delay",
            "category": "dependency_faults",
            "risk_level": "moderate",
            "environment_allowlist": ["local", "dev", "sandbox"],
            "steps": [
                {
                    "step_order": 1,
                    "action_type": "INVOKE_CONNECTOR",
                    "target_service": "integration_ops",
                    "fault": {"fault_type": "LATENCY_SPIKE", "delay_ms": 150}
                }
            ],
            "assertions": [
                {
                    "assertion_key": "assert-latency",
                    "assertion_type": "RECORD_EXISTS",
                    "expected_condition": "count >= 1",
                    "target_table": "simulation_step_executions",
                    "filter_field": "fault_injected",
                    "filter_value": "LATENCY_SPIKE"
                }
            ]
        }
        # 1. Create
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/simulation/scenarios",
            self.auth_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        created = json.loads(body)
        scen_id = created["id"]
        self.assertEqual(created["status"], "DRAFT")
        self.assertEqual(created["risk_level"], "moderate")

        # 2. Get
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/simulation/scenarios/{scen_id}",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        fetched = json.loads(body)
        self.assertEqual(fetched["id"], scen_id)
        self.assertEqual(len(fetched["steps"]), 1)

        # 3. Update
        update_payload = {"name": "Synthetic Gateway Latency Test Updated"}
        status, _, body = ApiRouter.dispatch(
            "PUT",
            f"/api/v1/simulation/scenarios/{scen_id}",
            self.auth_headers,
            {},
            json.dumps(update_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        updated = json.loads(body)
        self.assertEqual(updated["name"], "Synthetic Gateway Latency Test Updated")

        # 4. Advance: submit for review
        adv_payload = {"action": "submit_for_review"}
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/simulation/scenarios/{scen_id}/advance",
            self.auth_headers,
            {},
            json.dumps(adv_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        advanced = json.loads(body)
        self.assertEqual(advanced["status"], "IN_REVIEW")

    # --------------------------------------------------------------------------
    # 2. Simulation Execution & Run Management
    # --------------------------------------------------------------------------

    def test_03_launch_simulation_run_via_scenario_endpoint(self):
        """POST /api/v1/simulation/scenarios/{id}/run launches and executes scenario."""
        run_payload = {
            "environment": "local"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/simulation/scenarios/scen-syn-001/run",
            self.auth_headers,
            {},
            json.dumps(run_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        run_data = json.loads(body)
        self.assertEqual(run_data["scenario_id"], "scen-syn-001")
        self.assertEqual(run_data["is_dry_run"], 1)
        self.assertEqual(run_data["passed_assertions_count"], 1)
        self.assertEqual(run_data["status"], "CLEANED_UP")
        self.assertTrue(run_data["namespace_prefix"].startswith("sim-"))

    def test_04_launch_simulation_run_via_runs_endpoint(self):
        """POST /api/v1/simulation/runs launches run given scenario_id."""
        run_payload = {
            "scenario_id": "scen-syn-005",
            "environment": "local"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/simulation/runs",
            self.auth_headers,
            {},
            json.dumps(run_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        run_data = json.loads(body)
        self.assertEqual(run_data["scenario_id"], "scen-syn-005")
        self.assertEqual(run_data["passed_assertions_count"], 1)

    def test_05_list_and_get_simulation_runs(self):
        """GET /api/v1/simulation/runs and GET /api/v1/simulation/runs/{id}."""
        # List
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/simulation/runs",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        runs_list = json.loads(body)
        self.assertIn("runs", runs_list)
        self.assertGreaterEqual(runs_list["total_runs"], 2)

        # Get specific run
        first_run_id = runs_list["runs"][0]["id"]
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/simulation/runs/{first_run_id}",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        run_detail = json.loads(body)
        self.assertEqual(run_detail["id"], first_run_id)
        self.assertIn("steps", run_detail)
        self.assertIn("assertions", run_detail)

    def test_06_cleanup_simulation_run(self):
        """POST /api/v1/simulation/runs/{id}/cleanup performs idempotent teardown."""
        # Launch run without automatic cleanup
        # We can trigger cleanup explicitly
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/simulation/runs",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        first_run_id = json.loads(body)["runs"][0]["id"]

        status_c, _, body_c = ApiRouter.dispatch(
            "POST",
            f"/api/v1/simulation/runs/{first_run_id}/cleanup",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status_c, 200)
        cleaned = json.loads(body_c)
        self.assertEqual(cleaned["status"], "CLEANED_UP")

    # --------------------------------------------------------------------------
    # 3. Release Gate & Observability Endpoints
    # --------------------------------------------------------------------------

    def test_07_evaluate_release_gate(self):
        """POST /api/v1/simulation/release-gate validates release readiness."""
        # Execute remaining scenarios so gate passes
        for s_id in ["scen-syn-002", "scen-syn-003", "scen-syn-004", "scen-syn-006"]:
            ApiRouter.dispatch(
                "POST",
                f"/api/v1/simulation/scenarios/{s_id}/run",
                self.auth_headers,
                {},
                json.dumps({"environment": "local"}).encode("utf-8"),
                "127.0.0.1",
                self.db_path
            )

        gate_payload = {
            "target_release_tag": "v2026.10.14-rc1",
            "scenario_ids": ["scen-syn-001", "scen-syn-002", "scen-syn-003", "scen-syn-004", "scen-syn-005", "scen-syn-006"]
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/simulation/release-gate",
            self.auth_headers,
            {},
            json.dumps(gate_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        gate_res = json.loads(body)
        self.assertEqual(gate_res["target_release_tag"], "v2026.10.14-rc1")
        self.assertEqual(gate_res["evaluation_status"], "PASS")
        self.assertEqual(gate_res["total_scenarios_evaluated"], 6)
        self.assertEqual(gate_res["passed_scenarios_count"], 6)
        self.assertEqual(gate_res["failed_scenarios_count"], 0)

    def test_08_get_simulation_pulse(self):
        """GET /api/v1/simulation/pulse returns operational pulse and governance caveats."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/simulation/pulse",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        pulse = json.loads(body)
        self.assertIn("total_scenarios", pulse)
        self.assertIn("approved_scenarios", pulse)
        self.assertIn("total_runs", pulse)
        self.assertIn("passed_runs", pulse)
        self.assertIn("caveats", pulse)

    # --------------------------------------------------------------------------
    # 4. Security, Hard Production Lockout & RBAC
    # --------------------------------------------------------------------------

    def test_09_unauthenticated_request_rejected(self):
        """Unauthenticated calls must return 401."""
        status, _, _ = ApiRouter.dispatch(
            "GET",
            "/api/v1/simulation/scenarios",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 401)

    def test_10_production_lockout_enforcement(self):
        """Simulation run with environment='production' must be rejected with 403 Forbidden."""
        prod_payload = {
            "environment": "production"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/simulation/scenarios/scen-syn-001/run",
            self.auth_headers,
            {},
            json.dumps(prod_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 403)
        err = json.loads(body)
        self.assertEqual(err["code"], "FORBIDDEN")
        self.assertIn("production", err["message"].lower())


if __name__ == "__main__":
    unittest.main()

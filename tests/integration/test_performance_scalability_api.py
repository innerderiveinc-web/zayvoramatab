"""Integration Tests for Enterprise Performance, Scalability & Capacity Engineering REST APIs.

Phase 54 Verification Suite for ZAYVORA MATAB OS.
Mounted under `/api/v1/performance/`.
"""

import json
import os
import shutil
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestPerformanceScalabilityApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_perf_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin (has all permissions including performance:*)
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
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
        }

        # Authenticate Receptionist (unprivileged for performance:manage, performance:circuit_manage)
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

    def test_list_and_get_scenarios_rbac(self):
        """Test listing scenarios and fetching single scenario details."""
        # Unauthenticated request fails
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/scenarios",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertIn(status, [401, 403])

        # Admin succeeds
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/scenarios",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 5)

        # Get specific scenario
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/scenarios/SCN-PATIENT-SEARCH",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        sc = json.loads(body.decode("utf-8"))["scenario"]
        self.assertEqual(sc["scenario_id"], "SCN-PATIENT-SEARCH")

        # Non-existent scenario returns 404
        status, _, _ = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/scenarios/SCN-NON-EXISTENT",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 404)

    def test_register_scenario_rbac(self):
        """Test registering benchmark scenario with RBAC enforcement."""
        payload = {
            "scenario_id": "SCN-TEST-API-INGEST",
            "name": "Integration Test API Ingestion",
            "category": "WRITE_INTENSIVE",
            "target_endpoint": "/api/v1/encounters",
            "http_method": "POST",
            "concurrency_level": 15,
            "target_p95_ms": 250.0,
            "target_p99_ms": 500.0,
            "max_error_rate_pct": 0.5,
        }

        # Receptionist (lacks performance:manage) gets 403
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/performance/scenarios",
            self.reception_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)

        # Admin creates scenario
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/performance/scenarios",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        res = json.loads(body.decode("utf-8"))
        self.assertEqual(res["scenario"]["scenario_id"], "SCN-TEST-API-INGEST")

    def test_run_live_microbenchmark_api(self):
        """Test triggering in-process microbenchmark via REST API."""
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/performance/scenarios/SCN-PATIENT-SEARCH/run",
            self.admin_headers,
            {},
            json.dumps({"iterations": 10}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        res = json.loads(body.decode("utf-8"))
        self.assertTrue(res["success"])
        run = res["benchmark_run"]
        self.assertEqual(run["scenario_id"], "SCN-PATIENT-SEARCH")
        self.assertEqual(run["sample_size"], 10)
        self.assertGreater(run["throughput_rps"], 0.0)

    def test_record_and_list_benchmark_runs_api(self):
        """Test manually posting telemetry run metrics and retrieving run history."""
        payload = {
            "scenario_id": "SCN-KNOWLEDGE-QUERY",
            "sample_latencies_ms": [25.0, 35.0, 42.0, 50.0, 65.0],
            "concurrency": 5,
            "duration_seconds": 1.5,
            "error_count": 0,
            "cpu_utilization_pct": 35.0,
            "memory_mb": 256.0,
            "environment": "ISOLATED_STAGING",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/performance/runs",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        run = json.loads(body.decode("utf-8"))["benchmark_run"]
        self.assertEqual(run["sla_status"], "PASS")

        # List runs
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/runs",
            self.admin_headers,
            {"scenario_id": "SCN-KNOWLEDGE-QUERY"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        runs_data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(runs_data["count"], 1)

    def test_slow_query_logging_and_listing_api(self):
        """Test logging and listing slow queries via API."""
        payload = {
            "query_sql": "SELECT * FROM prescriptions WHERE patient_id = 'PAT-5555' AND status = 'ACTIVE'",
            "duration_ms": 78.4,
            "recommended_index": "CREATE INDEX idx_rx_patient_status ON prescriptions(patient_id, status)",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/performance/slow-queries",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        entry = json.loads(body.decode("utf-8"))["query_entry"]
        self.assertIn("idx_rx_patient_status", entry["recommended_index"])

        # List slow queries
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/slow-queries",
            self.admin_headers,
            {"min_duration_ms": "50.0"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        sq_data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(sq_data["count"], 1)

    def test_capacity_profiles_and_headroom_evaluation_api(self):
        """Test listing capacity profiles and evaluating headroom via API."""
        # List capacity profiles
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/capacity-profiles",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        profiles = json.loads(body.decode("utf-8"))["profiles"]
        self.assertGreaterEqual(len(profiles), 1)
        profile_id = profiles[0]["profile_id"]

        # Evaluate headroom
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/performance/capacity-profiles/{profile_id}/evaluate",
            self.admin_headers,
            {},
            json.dumps({"current_active_users": 6, "measured_p95_ms": 110.0}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        evaluation = json.loads(body.decode("utf-8"))["capacity_evaluation"]
        self.assertEqual(evaluation["profile_id"], profile_id)
        self.assertFalse(evaluation["is_degraded"])
        self.assertGreater(evaluation["remaining_headroom_pct"], 50.0)

    def test_circuit_breaker_tripping_and_resetting_rbac(self):
        """Test circuit breaker controls and RBAC permission checks."""
        dep_id = "DEP-TWILIO"

        # Get circuit breaker
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/performance/circuit-breakers/{dep_id}",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        cb = json.loads(body.decode("utf-8"))["circuit_breaker"]
        self.assertEqual(cb["state"], "CLOSED")

        # Receptionist attempts to trip circuit breaker (lacks performance:circuit_manage) -> 403
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/performance/circuit-breakers/{dep_id}/trip",
            self.reception_headers,
            {},
            json.dumps({"reason": "Unauthorized test attempt"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)

        # Admin trips circuit breaker -> OPEN
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/performance/circuit-breakers/{dep_id}/trip",
            self.admin_headers,
            {},
            json.dumps({"reason": "Upstream Outage Simulation"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        cb_tripped = json.loads(body.decode("utf-8"))["circuit_breaker"]
        self.assertEqual(cb_tripped["state"], "OPEN")

        # Admin resets circuit breaker -> CLOSED
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/performance/circuit-breakers/{dep_id}/reset",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        cb_reset = json.loads(body.decode("utf-8"))["circuit_breaker"]
        self.assertEqual(cb_reset["state"], "CLOSED")

    def test_audit_ledger_verification_api(self):
        """Test verifying cryptographic audit chain via REST endpoint."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/performance/audit-ledger/verify",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        rep = json.loads(body.decode("utf-8"))["ledger_report"]
        self.assertTrue(rep["verified"])
        self.assertEqual(rep["status"], "CHAIN_INTEGRITY_VERIFIED")
        self.assertGreaterEqual(rep["blocks_checked"], 1)


if __name__ == "__main__":
    unittest.main()

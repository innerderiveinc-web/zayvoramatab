"""Unit Tests for Enterprise Performance, Scalability & Capacity Engineering Engine.

Phase 54 Verification Suite for ZAYVORA MATAB OS.
"""

import json
import sqlite3
import unittest
from datetime import datetime, timezone

from apps.api.domains.performance_scalability_engine import PerformanceScalabilityEngine
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
)


class TestPerformanceScalabilityEngine(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self._apply_migrations()
        self.engine = PerformanceScalabilityEngine(self.conn)

    def tearDown(self):
        self.conn.close()

    def _apply_migrations(self):
        cursor = self.conn.cursor()
        with open("apps/api/database/migrations/051_enterprise_performance_scalability_capacity_governance_schema.sql") as f:
            cursor.executescript(f.read())
        self.conn.commit()

    def test_scenario_listing_and_registration(self):
        """Test listing seeded scenarios and registering a new benchmark scenario."""
        scenarios = self.engine.list_scenarios()
        self.assertGreaterEqual(len(scenarios), 5)
        scenario_ids = {s["scenario_id"] for s in scenarios}
        self.assertIn("SCN-PATIENT-SEARCH", scenario_ids)
        self.assertIn("SCN-ENCOUNTER-CREATE", scenario_ids)
        self.assertIn("SCN-RX-SAFETY-PREFLIGHT", scenario_ids)

        # Register custom laboratory ingestion scenario
        custom = self.engine.register_scenario(
            data={
                "scenario_id": "SCN-LAB-TELEMETRY-INGEST",
                "name": "High-Throughput Lab Results Telemetry Ingest",
                "category": "BACKGROUND_QUEUE",
                "target_endpoint": "/api/v1/integrations/lab/telemetry",
                "http_method": "POST",
                "concurrency_level": 25,
                "target_p95_ms": 300.0,
                "target_p99_ms": 600.0,
                "max_error_rate_pct": 1.0,
            },
            actor_id="USER-TEST-ARCH",
        )
        self.assertEqual(custom["scenario_id"], "SCN-LAB-TELEMETRY-INGEST")
        self.assertEqual(custom["target_p95_ms"], 300.0)

        # Verify retrieval
        fetched = self.engine.get_scenario("SCN-LAB-TELEMETRY-INGEST")
        self.assertEqual(fetched["name"], "High-Throughput Lab Results Telemetry Ingest")

        # Conflict on duplicate registration
        with self.assertRaises(ConflictError):
            self.engine.register_scenario(
                {
                    "scenario_id": "SCN-LAB-TELEMETRY-INGEST",
                    "name": "Duplicate",
                    "target_endpoint": "/dup",
                },
                actor_id="USER-TEST-ARCH",
            )

    def test_deterministic_percentile_calculation(self):
        """Test exact linear-interpolation percentile computation."""
        # Empty
        self.assertEqual(PerformanceScalabilityEngine._calculate_percentile([], 95.0), 0.0)

        # Single element
        self.assertEqual(PerformanceScalabilityEngine._calculate_percentile([42.0], 50.0), 42.0)
        self.assertEqual(PerformanceScalabilityEngine._calculate_percentile([42.0], 99.0), 42.0)

        # Uniform sequence 1..100
        data = list(range(1, 101))
        p50 = PerformanceScalabilityEngine._calculate_percentile(data, 50.0)
        p95 = PerformanceScalabilityEngine._calculate_percentile(data, 95.0)
        p99 = PerformanceScalabilityEngine._calculate_percentile(data, 99.0)
        self.assertAlmostEqual(p50, 50.5, places=1)
        self.assertAlmostEqual(p95, 95.05, places=1)
        self.assertAlmostEqual(p99, 99.01, places=1)

    def test_benchmark_run_recording_and_sla_evaluation(self):
        """Test empirical benchmark run recording with fail-closed SLA evaluation."""
        # Run 1: High performance, passes target p95 (<= 150ms for SCN-PATIENT-SEARCH)
        passing_latencies = [45.0, 52.0, 48.0, 60.0, 55.0, 70.0, 80.0, 95.0, 110.0, 125.0]
        run_pass = self.engine.record_benchmark_run(
            scenario_id="SCN-PATIENT-SEARCH",
            sample_latencies_ms=passing_latencies,
            concurrency=10,
            duration_seconds=2.0,
            error_count=0,
            actor_id="USER-PERF-ENG",
        )
        self.assertEqual(run_pass["sla_status"], "PASS")
        self.assertEqual(run_pass["sample_size"], 10)
        self.assertEqual(run_pass["throughput_rps"], 5.0)  # 10 samples / 2.0s
        self.assertLess(run_pass["p95_latency_ms"], 150.0)

        # Run 2: Latency breach (p95 > 150ms)
        breached_latencies = [120.0, 140.0, 160.0, 180.0, 210.0, 240.0, 280.0, 310.0]
        run_breach = self.engine.record_benchmark_run(
            scenario_id="SCN-PATIENT-SEARCH",
            sample_latencies_ms=breached_latencies,
            concurrency=20,
            duration_seconds=1.0,
            error_count=0,
            actor_id="USER-PERF-ENG",
        )
        self.assertEqual(run_breach["sla_status"], "BREACH")
        self.assertGreater(run_breach["p95_latency_ms"], 150.0)

        # Run 3: Error rate breach
        run_error_breach = self.engine.record_benchmark_run(
            scenario_id="SCN-PATIENT-SEARCH",
            sample_latencies_ms=[50.0, 60.0, 70.0, 80.0],
            concurrency=10,
            duration_seconds=1.0,
            error_count=2,  # 2 errors out of 4 total = 50% > 0.5% target
            actor_id="USER-PERF-ENG",
        )
        self.assertEqual(run_error_breach["sla_status"], "BREACH")
        self.assertGreater(run_error_breach["error_rate_pct"], 0.5)

        # Verify listing
        runs = self.engine.list_benchmark_runs("SCN-PATIENT-SEARCH")
        self.assertEqual(len(runs), 3)

    def test_slow_query_logging_and_fingerprinting(self):
        """Test SQL parameter normalization, fingerprinting, and execution counting."""
        q1 = "SELECT * FROM encounters WHERE patient_id = 'PAT-1234' AND status = 'COMPLETED'"
        entry1 = self.engine.log_slow_query(
            query_sql=q1,
            duration_ms=45.2,
            recommended_index="CREATE INDEX idx_encounters_patient_status ON encounters(patient_id, status)",
            actor_id="USER-DBA",
        )
        self.assertIn("SELECT * FROM encounters WHERE patient_id = ? AND status = ?", entry1["normalized_query"])

        # Duplicate query with different literals should map to same fingerprint
        q2 = "SELECT * FROM encounters WHERE patient_id = 'PAT-9999' AND status = 'SCHEDULED'"
        entry2 = self.engine.log_slow_query(
            query_sql=q2,
            duration_ms=62.8,
            actor_id="USER-DBA",
        )
        self.assertEqual(entry2["query_fingerprint"], entry1["query_fingerprint"])

        # Verify list shows execution count 2
        queries = self.engine.list_slow_queries()
        matching = [q for q in queries if q["query_fingerprint"] == entry1["query_fingerprint"]]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["execution_count"], 2)

    def test_capacity_profile_and_headroom_evaluation(self):
        """Test capacity profile sizing and headroom degradation advisories."""
        profiles = self.engine.list_capacity_profiles()
        self.assertGreaterEqual(len(profiles), 1)
        profile_id = "CAP-OPD-SINGLE-CLINIC"

        # Safe load (5 concurrent users, 120ms p95)
        eval_safe = self.engine.evaluate_capacity_headroom(
            profile_id=profile_id,
            current_active_users=5,
            measured_p95_ms=120.0,
        )
        self.assertFalse(eval_safe["is_degraded"])
        self.assertEqual(eval_safe["recommendation"], "STABLE")
        self.assertEqual(eval_safe["remaining_headroom_pct"], 83.3)  # 1.0 - 5/30 = 83.3%

        # Saturated load (35 active users > 30 max concurrency, 350ms p95)
        eval_sat = self.engine.evaluate_capacity_headroom(
            profile_id=profile_id,
            current_active_users=35,
            measured_p95_ms=350.0,
        )
        self.assertTrue(eval_sat["is_degraded"])
        self.assertEqual(eval_sat["recommendation"], "THROTTLE_NEW_SESSIONS_AND_QUEUE")
        self.assertEqual(eval_sat["remaining_headroom_pct"], 0.0)

    def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker failure threshold tripping and resetting."""
        dep_id = "DEP-ABDM"
        cb = self.engine.get_circuit_breaker(dep_id)
        self.assertEqual(cb["state"], "CLOSED")
        self.assertEqual(cb["failure_count"], 0)

        # Trip breaker
        tripped = self.engine.trip_circuit_breaker(dep_id, reason="Simulated Gateway Timeout", actor_id="USER-SRE")
        self.assertEqual(tripped["state"], "OPEN")
        self.assertEqual(tripped["fallback_action"], "QUEUE_ASYNCHRONOUS")

        # Reset breaker
        reset = self.engine.reset_circuit_breaker(dep_id, actor_id="USER-SRE")
        self.assertEqual(reset["state"], "CLOSED")
        self.assertEqual(reset["failure_count"], 0)

    def test_live_microbenchmark_runner(self):
        """Test in-process live microbenchmark execution and metrics collection."""
        run = self.engine.run_live_microbenchmark(
            scenario_id="SCN-PATIENT-SEARCH",
            iterations=15,
            actor_id="USER-TEST",
        )
        self.assertEqual(run["scenario_id"], "SCN-PATIENT-SEARCH")
        self.assertEqual(run["sample_size"], 15)
        self.assertGreater(run["throughput_rps"], 0.0)
        self.assertGreaterEqual(run["p50_latency_ms"], 0.0)
        self.assertGreaterEqual(run["p95_latency_ms"], run["p50_latency_ms"])
        self.assertIn(run["sla_status"], ["PASS", "WARNING", "BREACH"])

    def test_audit_ledger_cryptographic_chain_and_tamper_detection(self):
        """Test SHA-256 tamper-evident performance governance audit ledger."""
        # 1. Clean verification
        report = self.engine.verify_audit_ledger_integrity()
        self.assertTrue(report["verified"])
        self.assertGreaterEqual(report["blocks_checked"], 1)

        # 2. Append new events via engine actions
        self.engine.register_scenario(
            {
                "scenario_id": "SCN-AUDIT-TEST",
                "name": "Audit Test Scenario",
                "category": "READ_HEAVY",
                "target_endpoint": "/api/v1/test",
                "concurrency_level": 10,
                "target_p95_ms": 100.0,
                "target_p99_ms": 250.0,
                "max_error_rate_pct": 1.0,
            },
            actor_id="USER-AUDITOR",
        )
        report2 = self.engine.verify_audit_ledger_integrity()
        self.assertTrue(report2["verified"])
        self.assertGreaterEqual(report2["blocks_checked"], 2)

        # 3. Simulate database tampering by modifying payload of genesis block
        cursor = self.conn.cursor()
        cursor.execute("UPDATE perf_governance_audit_ledger SET payload_json = '{\"tampered\": true}' WHERE ledger_id = 'PGL-GENESIS-0001'")
        self.conn.commit()

        report_tampered = self.engine.verify_audit_ledger_integrity()
        self.assertFalse(report_tampered["verified"])
        self.assertTrue(report_tampered.get("tamper_detected"))


if __name__ == "__main__":
    unittest.main()

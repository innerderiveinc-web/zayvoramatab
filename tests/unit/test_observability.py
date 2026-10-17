"""Unit Tests for Production Observability, Alerting, SLOs & Incident Response Engine.

Phase 39 for ZAYVORA MATAB OS.
Tests core domain logic:
1.  Service Catalog listing & dependency maps.
2.  Deep diagnostics aggregation (DB latency, safety gate, queue health, zero secret leakage).
3.  Low-cardinality telemetry metric recording & rejection of high-cardinality/PHI tokens.
4.  Metric summary calculation & error ratio aggregation.
5.  Actionable alert definition creation with mandatory runbook.
6.  Alert evaluation firing & deduplication fingerprinting.
7.  Alert instance acknowledgment & manual resolution requiring evidence.
8.  Governed SLO registration in DRAFT, owner approval, and error-budget/burn-rate math.
9.  Incident lifecycle state machine & transition rejection on illegal moves.
10. Incident resolution proof requirement.
11. Remediation guardrails: allowlist validation, cooldown enforcement, and clinical lockout.
12. Operational pulse metrics rollup.
"""

import os
import json
import sqlite3
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.observability import ObservabilityReliabilityEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestObservabilityReliabilityEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_observability.db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.engine = ObservabilityReliabilityEngine(self.db_path)

        # Contexts
        self.admin_ctx = {
            "id": "usr-admin-1",
            "user_id": "usr-admin-1",
            "username": "admin",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["ORG_ADMIN", "PLATFORM_ENGINEER"],
            "org_roles": ["ORG_ADMIN", "PLATFORM_ENGINEER"]
        }

        self.sec_officer_ctx = {
            "id": "usr-sec-1",
            "user_id": "usr-sec-1",
            "username": "sec_officer",
            "organization_id": "org-matab-default",
            "facility_id": "fac-central-opd",
            "roles": ["SECURITY_OFFICER"],
            "org_roles": ["SECURITY_OFFICER"]
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
    # 1. Service Catalog & Diagnostics
    # --------------------------------------------------------------------------

    def test_01_service_catalog_and_seeded_services(self):
        """List services in catalog and verify tiering and dependencies."""
        services = self.engine.list_service_catalog(self.admin_ctx)
        self.assertGreaterEqual(len(services), 5)
        s_keys = [s["service_key"] for s in services]
        self.assertIn("svc-auth", s_keys)
        self.assertIn("svc-safety-firewall", s_keys)
        self.assertIn("svc-encounters", s_keys)

        auth_svc = next(s for s in services if s["service_key"] == "svc-auth")
        self.assertEqual(auth_svc["tier"], "tier_1_mission_critical")
        self.assertEqual(auth_svc["health_status"], "HEALTHY")

    def test_02_deep_diagnostics_without_secret_leakage(self):
        """Deep diagnostics returns DB latency, queue health, and zero secrets."""
        diag = self.engine.get_deep_diagnostics(self.admin_ctx)
        self.assertIn("status", diag)
        self.assertIn("database", diag)
        self.assertTrue(diag["database"]["connected"])
        self.assertGreaterEqual(diag["database"]["migrations_applied"], 37)
        self.assertEqual(diag["clinical_safety_firewall"]["fail_closed_guarantee"], True)
        self.assertIn("queues_and_workers", diag)

        # Invariant: No password or secret in diagnostic keys
        diag_str = json.dumps(diag).lower()
        self.assertNotIn("password", diag_str)
        self.assertNotIn("token", diag_str)
        self.assertNotIn("secret", diag_str)

    # --------------------------------------------------------------------------
    # 2. Telemetry Metrics & Cardinality Protection
    # --------------------------------------------------------------------------

    def test_03_record_metric_and_cardinality_guardrail(self):
        """Record low-cardinality metric and verify rejection of PHI / UUID tokens."""
        # Valid low-cardinality metric
        metric = self.engine.record_metric({
            "metric_name": "api.requests.total",
            "route_or_subsystem": "/api/v1/encounters/{id}",
            "outcome_class": "SUCCESS",
            "metric_value": 1.0,
            "unit": "count"
        }, self.admin_ctx)
        self.assertIn("id", metric)
        self.assertEqual(metric["outcome_class"], "SUCCESS")

        # Invalid outcome class
        with self.assertRaises(ValidationError):
            self.engine.record_metric({
                "metric_name": "api.requests.total",
                "route_or_subsystem": "/api/v1/encounters/{id}",
                "outcome_class": "INVALID_CLASS"
            }, self.admin_ctx)

        # High-cardinality token / PHI injection rejection
        with self.assertRaises(ValidationError):
            self.engine.record_metric({
                "metric_name": "api.requests.total",
                "route_or_subsystem": "/api/v1/patients/pat-12345678-abcd-1234-abcd-1234567890ab",
                "outcome_class": "SUCCESS"
            }, self.admin_ctx)

    def test_04_query_metrics_summary(self):
        """Query metrics summary aggregation over time window."""
        self.engine.record_metric({
            "metric_name": "api.requests.latency_ms",
            "route_or_subsystem": "/api/v1/prescriptions",
            "outcome_class": "SUCCESS",
            "metric_value": 45.0,
            "unit": "ms"
        }, self.admin_ctx)
        self.engine.record_metric({
            "metric_name": "api.requests.latency_ms",
            "route_or_subsystem": "/api/v1/prescriptions",
            "outcome_class": "SERVER_ERROR",
            "metric_value": 120.0,
            "unit": "ms"
        }, self.admin_ctx)

        summary = self.engine.query_metrics_summary({"window_minutes": 60}, self.admin_ctx)
        self.assertGreaterEqual(summary["total_events"], 2)
        self.assertGreaterEqual(summary["server_errors"], 1)

    # --------------------------------------------------------------------------
    # 3. Actionable Alert Definitions & Instances
    # --------------------------------------------------------------------------

    def test_05_create_alert_definition_with_runbook(self):
        """Create actionable alert definition with mandatory runbook markdown."""
        alert_def = self.engine.create_alert_definition({
            "alert_key": "ALERT-DB-POOL-SATURATION",
            "title": "Database Connection Pool Saturation",
            "service_key": "svc-auth",
            "severity": "P1_CRITICAL",
            "metric_name": "db.pool.active_connections",
            "condition_operator": "GT",
            "threshold_value": 20.0,
            "evaluation_window_seconds": 120,
            "owner_role": "PLATFORM_ENGINEER",
            "runbook_markdown": "### RUNBOOK: DB Pool Saturation\n1. Inspect active transactions in SQLite.\n2. Verify stale connection handles.\n3. Prohibited: Do not kill process without checkpoint."
        }, self.admin_ctx)
        self.assertIn("id", alert_def)
        self.assertEqual(alert_def["alert_key"], "ALERT-DB-POOL-SATURATION")

        # Missing runbook markdown must fail validation
        with self.assertRaises(ValidationError):
            self.engine.create_alert_definition({
                "alert_key": "ALERT-NO-RUNBOOK",
                "title": "No Runbook Alert",
                "runbook_markdown": ""
            }, self.admin_ctx)

    def test_06_evaluate_alerts_and_deduplication_fingerprint(self):
        """Evaluate alerts against metric spikes and verify deduplication fingerprint."""
        # Insert telemetry metric spike exceeding threshold
        for _ in range(6):
            self.engine.record_metric({
                "metric_name": "api.requests.error_count",
                "route_or_subsystem": "/api/v1/auth/login",
                "outcome_class": "SERVER_ERROR",
                "metric_value": 2.0,
                "unit": "count"
            }, self.admin_ctx)

        # Evaluate alerts
        results = self.engine.evaluate_alerts(self.admin_ctx)
        self.assertTrue(any(r["action"] == "FIRED" for r in results))

        # Check firing instances
        instances = self.engine.list_alert_instances({"status": "FIRING"}, self.admin_ctx)
        self.assertGreaterEqual(len(instances), 1)
        inst = instances[0]
        self.assertIn("fingerprint", inst)
        self.assertEqual(inst["status"], "FIRING")

    def test_07_acknowledge_and_resolve_alert_instance(self):
        """Acknowledge alert and manually resolve with verified evidence."""
        # Fire an alert instance
        self.engine.record_metric({
            "metric_name": "api.requests.error_count",
            "route_or_subsystem": "/api/v1/auth/login",
            "outcome_class": "SERVER_ERROR",
            "metric_value": 10.0,
            "unit": "count"
        }, self.admin_ctx)
        self.engine.evaluate_alerts(self.admin_ctx)

        instances = self.engine.list_alert_instances({"status": "FIRING"}, self.admin_ctx)
        inst_id = instances[0]["id"]

        # Acknowledge
        ack_res = self.engine.acknowledge_alert_instance(inst_id, self.admin_ctx)
        self.assertEqual(ack_res["status"], "ACKNOWLEDGED")

        # Resolve without evidence must fail
        with self.assertRaises(ValidationError):
            self.engine.resolve_alert_instance(inst_id, {}, self.admin_ctx)

        # Resolve with evidence
        res = self.engine.resolve_alert_instance(inst_id, {
            "root_cause": "Transient lock resolved",
            "verified_metrics_healthy": True
        }, self.admin_ctx)
        self.assertEqual(res["status"], "RESOLVED")

    # --------------------------------------------------------------------------
    # 4. Service-Level Objectives (SLO) Registry
    # --------------------------------------------------------------------------

    def test_08_slo_lifecycle_and_error_budget_math(self):
        """Register draft SLO, approve it, and compute error budget burn rate."""
        slo = self.engine.create_slo({
            "slo_key": "SLO-OPD-TOKEN-QUEUE",
            "name": "OPD Token Queue Availability",
            "service_key": "svc-encounters",
            "sli_description": "Ratio of token generation requests completed under 200ms",
            "target_ratio": 0.99
        }, self.admin_ctx)
        self.assertEqual(slo["approval_status"], "DRAFT")

        # Approve SLO
        app_res = self.engine.approve_slo(slo["id"], self.admin_ctx)
        self.assertEqual(app_res["approval_status"], "APPROVED")

        # Record events: 100 total, 95 good -> 5 bad events (allowed bad for 99% is 1, so breached)
        event_res = self.engine.record_slo_events("SLO-OPD-TOKEN-QUEUE", 95, 100, self.admin_ctx)
        self.assertEqual(event_res["compliance_status"], "BREACHED")
        self.assertGreater(event_res["burn_rate"], 1.0)

    # --------------------------------------------------------------------------
    # 5. Incident Management Lifecycle State Machine
    # --------------------------------------------------------------------------

    def test_09_incident_state_machine_and_timeline(self):
        """Create incident, navigate state transitions, and reject invalid transitions."""
        inc = self.engine.create_incident({
            "title": "ABDM Gateway Timeout Spike",
            "summary": "Intermittent HTTP 504 timeouts to ABDM care context sync gateway",
            "service_key": "svc-integration-jobs",
            "severity": "P2_HIGH",
            "impact_scope": "ABDM health data transfers delayed"
        }, self.admin_ctx)
        self.assertEqual(inc["status"], "detected")
        inc_id = inc["id"]

        # Legal transition: detected -> acknowledged
        inc_ack = self.engine.transition_incident(inc_id, "acknowledged", "Acknowledged by platform lead", None, self.admin_ctx)
        self.assertEqual(inc_ack["status"], "acknowledged")

        # Illegal transition: acknowledged -> closed (must go through investigating/mitigating/resolved)
        with self.assertRaises(ValidationError):
            self.engine.transition_incident(inc_id, "closed", "Direct close attempt", None, self.admin_ctx)

        # Transition: acknowledged -> investigating
        self.engine.transition_incident(inc_id, "investigating", "Investigating upstream ABDM connector", None, self.admin_ctx)

        # Add timeline entry
        tl = self.engine.add_incident_timeline_event(inc_id, "RUNBOOK_STEP", "Executed ping diagnostic probe to ABDM gateway", {"latency_ms": 450}, self.admin_ctx)
        self.assertIn("id", tl)

        # Transition: investigating -> mitigating -> monitoring_recovery
        self.engine.transition_incident(inc_id, "mitigating", "Pausing retries to avoid rate limits", None, self.admin_ctx)
        self.engine.transition_incident(inc_id, "monitoring_recovery", "Traffic resuming", None, self.admin_ctx)

        # Transition to resolved WITHOUT evidence must fail
        with self.assertRaises(ValidationError):
            self.engine.transition_incident(inc_id, "resolved", "No evidence provided", None, self.admin_ctx)

        # Transition to resolved WITH evidence
        inc_res = self.engine.transition_incident(inc_id, "resolved", "Gateway re-established connection", {
            "probe_status": "SUCCESS",
            "healthy_pings": 5
        }, self.admin_ctx)
        self.assertEqual(inc_res["status"], "resolved")

    # --------------------------------------------------------------------------
    # 6. Remediation Guardrails
    # --------------------------------------------------------------------------

    def test_10_remediation_guardrails_clinical_lockout_and_cooldown(self):
        """Remediation permits allowlisted action, rejects clinical targets, and enforces cooldown."""
        # 1. Reject forbidden clinical target
        with self.assertRaises(ForbiddenError):
            self.engine.execute_remediation({
                "action_type": "RESTART_BACKGROUND_CONSUMER",
                "target_resource": "patient_prescriptions_queue"
            }, self.admin_ctx)

        # 2. Reject non-allowlisted action
        with self.assertRaises(ValidationError):
            self.engine.execute_remediation({
                "action_type": "DROP_DATABASE_TABLES",
                "target_resource": "worker.integration_jobs"
            }, self.admin_ctx)

        # 3. Successful allowlisted remediation
        res = self.engine.execute_remediation({
            "action_type": "CLEAR_TRANSIENT_CACHE",
            "target_resource": "cache.knowledge_rag"
        }, self.admin_ctx)
        self.assertEqual(res["status"], "COMPLETED")
        self.assertEqual(res["cooldown_seconds"], 300)

        # 4. Immediate re-execution must be blocked by 300s cooldown
        with self.assertRaises(ConflictError):
            self.engine.execute_remediation({
                "action_type": "CLEAR_TRANSIENT_CACHE",
                "target_resource": "cache.knowledge_rag"
            }, self.admin_ctx)

    def test_11_observability_pulse(self):
        """Get operational pulse rollup."""
        pulse = self.engine.get_observability_pulse(self.admin_ctx)
        self.assertIn("overall_status", pulse)
        self.assertIn("total_services", pulse)
        self.assertIn("firing_alerts", pulse)
        self.assertIn("open_incidents", pulse)
        self.assertIn("slo_compliance", pulse)
        self.assertEqual(pulse["telemetry_freshness"], "REALTIME")


if __name__ == "__main__":
    unittest.main()

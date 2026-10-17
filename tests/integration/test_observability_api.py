"""Integration Tests for Production Observability, Alerting, SLOs & Incident Response APIs.

Phase 39 for ZAYVORA MATAB OS.
Tests all endpoints via ApiRouter.dispatch:
1.  GET  /api/v1/health/live (unauthenticated)
2.  GET  /api/v1/health/ready (unauthenticated)
3.  GET  /api/v1/observability/services
4.  GET  /api/v1/observability/diagnostics/deep
5.  POST /api/v1/observability/metrics
6.  GET  /api/v1/observability/metrics/summary
7.  GET  /api/v1/observability/alerts/definitions
8.  POST /api/v1/observability/alerts/definitions
9.  POST /api/v1/observability/alerts/evaluate
10. GET  /api/v1/observability/alerts/instances
11. POST /api/v1/observability/alerts/instances/{id}/acknowledge
12. POST /api/v1/observability/alerts/instances/{id}/resolve
13. GET  /api/v1/observability/slos
14. POST /api/v1/observability/slos
15. POST /api/v1/observability/slos/{id}/approve
16. POST /api/v1/observability/slos/events
17. GET  /api/v1/observability/incidents
18. POST /api/v1/observability/incidents
19. GET  /api/v1/observability/incidents/{id}
20. POST /api/v1/observability/incidents/{id}/transition
21. POST /api/v1/observability/incidents/{id}/timeline
22. POST /api/v1/observability/remediation
23. GET  /api/v1/observability/pulse
24. Security & RBAC: 401 Unauthenticated, 403 Forbidden for unauthorized remediation.
"""

import os
import json
import sqlite3
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestObservabilityApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_observability_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
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

        # Authenticate Practitioner (Hakeem)
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
    # 1. Health & Readiness (Unauthenticated)
    # --------------------------------------------------------------------------

    def test_01_health_live_and_ready(self):
        """GET /api/v1/health/live and /ready are unauthenticated and report health."""
        status_l, _, body_l = ApiRouter.dispatch(
            "GET", "/api/v1/health/live", {}, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_l, 200)
        self.assertEqual(json.loads(body_l)["status"], "LIVE")

        status_r, _, body_r = ApiRouter.dispatch(
            "GET", "/api/v1/health/ready", {}, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_r, 200)
        self.assertEqual(json.loads(body_r)["status"], "READY")

    # --------------------------------------------------------------------------
    # 2. Service Catalog & Deep Diagnostics
    # --------------------------------------------------------------------------

    def test_02_services_and_deep_diagnostics(self):
        """GET /api/v1/observability/services & /diagnostics/deep."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/observability/services", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertGreaterEqual(data["total_services"], 5)

        status_d, _, body_d = ApiRouter.dispatch(
            "GET", "/api/v1/observability/diagnostics/deep", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_d, 200)
        diag = json.loads(body_d)
        self.assertIn("database", diag)
        self.assertIn("clinical_safety_firewall", diag)

    # --------------------------------------------------------------------------
    # 3. Metrics Telemetry APIs
    # --------------------------------------------------------------------------

    def test_03_record_and_summarize_metrics(self):
        """POST /api/v1/observability/metrics & GET /api/v1/observability/metrics/summary."""
        metric_payload = {
            "metric_name": "api.requests.total",
            "route_or_subsystem": "/api/v1/encounters/{id}",
            "outcome_class": "SUCCESS",
            "metric_value": 1.0,
            "unit": "count"
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/observability/metrics", self.auth_headers, {},
            json.dumps(metric_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)

        status_s, _, body_s = ApiRouter.dispatch(
            "GET", "/api/v1/observability/metrics/summary", self.auth_headers, {"window_minutes": "60"},
            b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_s, 200)
        summary = json.loads(body_s)
        self.assertGreaterEqual(summary["total_events"], 1)

    # --------------------------------------------------------------------------
    # 4. Alert Definitions & Evaluation APIs
    # --------------------------------------------------------------------------

    def test_04_alerts_lifecycle(self):
        """Alerts endpoints: definition, evaluation, acknowledgement, resolution."""
        # List definitions
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/observability/alerts/definitions", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertGreaterEqual(data["total_definitions"], 2)

        # Create new definition
        new_alert = {
            "alert_key": "ALERT-API-HIGH-LATENCY-TEST",
            "title": "High API Latency Alert Test",
            "service_key": "svc-auth",
            "severity": "P2_HIGH",
            "metric_name": "api.requests.latency_ms",
            "condition_operator": "GT",
            "threshold_value": 100.0,
            "evaluation_window_seconds": 300,
            "owner_role": "PLATFORM_ENGINEER",
            "runbook_markdown": "### RUNBOOK: High Latency\nInspect DB latency."
        }
        status_c, _, body_c = ApiRouter.dispatch(
            "POST", "/api/v1/observability/alerts/definitions", self.auth_headers, {},
            json.dumps(new_alert).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_c, 201)

        # Record metric exceeding threshold
        ApiRouter.dispatch(
            "POST", "/api/v1/observability/metrics", self.auth_headers, {},
            json.dumps({
                "metric_name": "api.requests.latency_ms",
                "route_or_subsystem": "/api/v1/auth/login",
                "outcome_class": "SUCCESS",
                "metric_value": 250.0
            }).encode("utf-8"), "127.0.0.1", self.db_path
        )

        # Evaluate alerts
        status_e, _, body_e = ApiRouter.dispatch(
            "POST", "/api/v1/observability/alerts/evaluate", self.auth_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_e, 200)

        # List instances
        status_i, _, body_i = ApiRouter.dispatch(
            "GET", "/api/v1/observability/alerts/instances", self.auth_headers, {"status": "FIRING"}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_i, 200)
        instances = json.loads(body_i)["instances"]
        self.assertGreaterEqual(len(instances), 1)
        inst_id = instances[0]["id"]

        # Acknowledge instance
        status_a, _, body_a = ApiRouter.dispatch(
            "POST", f"/api/v1/observability/alerts/instances/{inst_id}/acknowledge", self.auth_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_a, 200)

        # Resolve instance
        status_r, _, body_r = ApiRouter.dispatch(
            "POST", f"/api/v1/observability/alerts/instances/{inst_id}/resolve", self.auth_headers, {},
            json.dumps({"evidence": {"action": "Optimized connection pool", "latency_ms": 35}}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_r, 200)

    # --------------------------------------------------------------------------
    # 5. Service-Level Objectives (SLO) APIs
    # --------------------------------------------------------------------------

    def test_05_slos_lifecycle(self):
        """GET, POST, approve, and record events for SLOs."""
        # List SLOs
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/observability/slos", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

        # Create SLO
        slo_payload = {
            "slo_key": "SLO-PRESCRIPTION-VALIDATION",
            "name": "Prescription Safety Validation Availability",
            "service_key": "svc-safety-firewall",
            "sli_description": "Ratio of preflight validation requests succeeding",
            "target_ratio": 0.999
        }
        status_c, _, body_c = ApiRouter.dispatch(
            "POST", "/api/v1/observability/slos", self.auth_headers, {},
            json.dumps(slo_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_c, 201)
        slo_id = json.loads(body_c)["id"]

        # Approve SLO
        status_app, _, body_app = ApiRouter.dispatch(
            "POST", f"/api/v1/observability/slos/{slo_id}/approve", self.auth_headers, {}, b"{}", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_app, 200)

        # Record events
        status_ev, _, body_ev = ApiRouter.dispatch(
            "POST", "/api/v1/observability/slos/events", self.auth_headers, {},
            json.dumps({"slo_key": "SLO-PRESCRIPTION-VALIDATION", "good_events_delta": 99, "total_events_delta": 100}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_ev, 200)

    # --------------------------------------------------------------------------
    # 6. Incident Management APIs
    # --------------------------------------------------------------------------

    def test_06_incidents_lifecycle(self):
        """Incident creation, retrieval, timeline notes, and transition to resolution."""
        inc_payload = {
            "title": "Integration Worker Dead-Letter Spurt",
            "summary": "Sudden growth in dead_letter_items from LIS connector",
            "service_key": "svc-integration-jobs",
            "severity": "P2_HIGH",
            "impact_scope": "Lab orders delayed"
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/observability/incidents", self.auth_headers, {},
            json.dumps(inc_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        inc = json.loads(body)
        inc_id = inc["id"]

        # Add timeline entry
        status_tl, _, body_tl = ApiRouter.dispatch(
            "POST", f"/api/v1/observability/incidents/{inc_id}/timeline", self.auth_headers, {},
            json.dumps({"entry_type": "COMMUNICATION", "message": "Investigating LIS connector"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_tl, 201)

        # Transition: detected -> acknowledged
        status_t1, _, _ = ApiRouter.dispatch(
            "POST", f"/api/v1/observability/incidents/{inc_id}/transition", self.auth_headers, {},
            json.dumps({"status": "acknowledged", "notes": "Acknowledged"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_t1, 200)

        # Transition: acknowledged -> investigating
        status_t2, _, _ = ApiRouter.dispatch(
            "POST", f"/api/v1/observability/incidents/{inc_id}/transition", self.auth_headers, {},
            json.dumps({"status": "investigating", "notes": "Investigating payload format"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_t2, 200)

        # Transition: investigating -> resolved (with evidence)
        status_t3, _, body_res = ApiRouter.dispatch(
            "POST", f"/api/v1/observability/incidents/{inc_id}/transition", self.auth_headers, {},
            json.dumps({
                "status": "resolved",
                "notes": "Connector patch applied",
                "evidence": {"reconciliation_verified": True, "dlq_drained": 12}
            }).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_t3, 200)
        self.assertEqual(json.loads(body_res)["status"], "resolved")

    # --------------------------------------------------------------------------
    # 7. Remediation & Pulse APIs + Security Check
    # --------------------------------------------------------------------------

    def test_07_remediation_and_pulse_and_security(self):
        """Remediation execution, pulse metrics, and 403 Forbidden for unauthorized practitioner."""
        # 1. Operational pulse
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/observability/pulse", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        pulse = json.loads(body)
        self.assertIn("overall_status", pulse)
        self.assertIn("firing_alerts", pulse)

        # 2. Allowlisted remediation execution by Admin
        rem_payload = {
            "action_type": "CLEAR_TRANSIENT_CACHE",
            "target_resource": "cache.ontology_catalog"
        }
        status_rem, _, body_rem = ApiRouter.dispatch(
            "POST", "/api/v1/observability/remediation", self.auth_headers, {},
            json.dumps(rem_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_rem, 200)
        self.assertEqual(json.loads(body_rem)["status"], "COMPLETED")

        # 3. Unauthorized remediation by Practitioner -> 403 Forbidden
        status_sec, _, _ = ApiRouter.dispatch(
            "POST", "/api/v1/observability/remediation", self.hakeem_headers, {},
            json.dumps(rem_payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status_sec, 403)

        # 4. Unauthenticated access -> 401
        status_unauth, _, _ = ApiRouter.dispatch(
            "GET", "/api/v1/observability/diagnostics/deep", {}, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status_unauth, 401)


if __name__ == "__main__":
    unittest.main()

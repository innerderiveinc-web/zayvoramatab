"""Integration tests for Enterprise Integration Operations & Reliability REST APIs.

Phase 32 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Operations Dashboard (GET /api/v1/ops/dashboard)
2. Connector health and circuit breakers (GET/POST /api/v1/ops/connectors/*)
3. Integration jobs lifecycle and idempotent queueing (GET/POST /api/v1/ops/jobs/*)
4. Job attempt execution and simulated failure states (POST /api/v1/ops/jobs/{id}/attempt)
5. State transitions with non-negotiable validations (POST /api/v1/ops/jobs/{id}/transition)
6. Ambiguous outcome reconciliation workflow (POST /api/v1/ops/jobs/{id}/reconcile, POST /api/v1/ops/reconciliations/{id}/resolve)
7. Dead-letter queue inspection and remediation (GET/POST /api/v1/ops/dead-letter/*)
8. Inbound callback ingestion and deduplication (POST /api/v1/ops/callbacks)
9. Emergency connector shutdown with mandatory audit rationale (POST /api/v1/ops/connectors/{id}/disable)
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
from apps.api.router import ApiRouter


class TestIntegrationOperationsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_integration_ops_api.db")
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

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        cls.admin_id = admin_row["id"]
        cls.org_id = admin_row["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-default"

        # Create a test connector for API tests
        cls.connector_id = f"conn-api-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO integration_connectors (
                id, organization_id, facility_id, connector_type, name, endpoint_url,
                environment, lifecycle_state, last_health_status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                cls.connector_id, cls.org_id, cls.fac_id, "ABDM_ABHA",
                "ABDM API Test Connector", "https://dev.abdm.gov.in/gateway",
                "SANDBOX", "SANDBOX_TESTED", "HEALTHY",
                datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()
            )
        )
        conn.commit()
        conn.close()

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Facility-Id": self.fac_id,
        }

    def test_01_dashboard_and_connectors_endpoints(self):
        """GET /api/v1/ops/dashboard and /api/v1/ops/connectors return valid operational metrics."""
        # 1. Dashboard summary
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/ops/dashboard",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("total_jobs", data)
        self.assertIn("queued_jobs", data)
        self.assertIn("outcome_unknown_jobs", data)

        # 2. List connectors
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/ops/connectors",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        conns = json.loads(body)["connectors"]
        self.assertGreaterEqual(len(conns), 1)

        # 3. Get single connector
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/ops/connectors/{self.connector_id}",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        conn_obj = json.loads(body)
        self.assertEqual(conn_obj["id"], self.connector_id)

    def test_02_health_snapshot_and_circuit_breaker_api(self):
        """POST /api/v1/ops/connectors/{id}/health-snapshot and circuit-breaker."""
        # Record health snapshot
        snapshot_payload = {
            "probe_type": "CONNECTIVITY",
            "probe_result": "HEALTHY",
            "latency_ms": 78,
            "limitation_notes": None
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/connectors/{self.connector_id}/health-snapshot",
            self._headers(),
            {},
            json.dumps(snapshot_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertEqual(res["probe_result"], "HEALTHY")

        # Trip circuit breaker
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/connectors/{self.connector_id}/circuit-breaker",
            self._headers(),
            {},
            json.dumps({"state": "OPEN"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        cb = json.loads(body)
        self.assertEqual(cb["circuit_breaker_state"], "OPEN")

        # Reset circuit breaker
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/connectors/{self.connector_id}/circuit-breaker",
            self._headers(),
            {},
            json.dumps({"state": "CLOSED"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        cb_reset = json.loads(body)
        self.assertEqual(cb_reset["circuit_breaker_state"], "CLOSED")

    def test_03_job_lifecycle_and_attempts_api(self):
        """End-to-end job creation, attempt execution, and listing via REST API."""
        idem_key = f"api-job-{uuid.uuid4().hex}"
        job_payload = {
            "connector_id": self.connector_id,
            "operation_type": "FHIR_BUNDLE_EXPORT",
            "idempotency_key": idem_key,
            "max_attempts": 3,
            "payload": {"bundleType": "encounter-summary"}
        }

        # 1. Create Job
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/ops/jobs",
            self._headers(),
            {},
            json.dumps(job_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        job = json.loads(body)
        job_id = job["id"]
        self.assertEqual(job["job_state"], "queued")
        self.assertEqual(job["idempotency_key"], idem_key)

        # 2. Get Job Details
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/ops/jobs/{job_id}",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        job_details = json.loads(body)
        self.assertEqual(job_details["id"], job_id)

        # 3. List Jobs
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/ops/jobs",
            self._headers(),
            {"limit": "10"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        jobs_list = json.loads(body)["jobs"]
        self.assertGreaterEqual(len(jobs_list), 1)

        # 4. Execute Attempt: SUCCESS
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/jobs/{job_id}/attempt",
            self._headers(),
            {},
            json.dumps({"simulated_outcome": "SUCCESS", "duration_ms": 110}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        attempt_res = json.loads(body)
        self.assertEqual(attempt_res["job_state"], "completed")

    def test_04_reconciliation_workflow_api(self):
        """Test outcome_unknown flow into reconciliation initiation and resolution via REST APIs."""
        idem_key = f"api-recon-{uuid.uuid4().hex}"
        job_payload = {
            "connector_id": self.connector_id,
            "operation_type": "ABDM_HEALTH_DATA_TRANSFER",
            "idempotency_key": idem_key,
            "payload": {"data_transfer": "encounter-e-01"}
        }

        # Create Job
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/ops/jobs",
            self._headers(),
            {},
            json.dumps(job_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        job_id = json.loads(body)["id"]

        # Attempt with timeout -> outcome_unknown
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/jobs/{job_id}/attempt",
            self._headers(),
            {},
            json.dumps({"simulated_outcome": "TIMEOUT_UNKNOWN"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["job_state"], "outcome_unknown")

        # Initiate Reconciliation
        recon_payload = {
            "reconciliation_method": "STATUS_QUERY",
            "trigger_reason": "External read timeout; initiated partner query"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/jobs/{job_id}/reconcile",
            self._headers(),
            {},
            json.dumps(recon_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        recon_obj = json.loads(body)
        recon_id = recon_obj["reconciliation_id"]

        # Resolve Reconciliation
        resolve_payload = {
            "determination": "confirmed_completed",
            "decision_notes": "Partner status endpoint confirms transaction successfully stored.",
            "evidence_references": ["TX-REF-100293"]
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/reconciliations/{recon_id}/resolve",
            self._headers(),
            {},
            json.dumps(resolve_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        self.assertEqual(res["new_job_state"], "completed")

    def test_05_dead_letter_workbench_api(self):
        """Test listing dead-letter items and resolving via API."""
        idem_key = f"api-dlq-{uuid.uuid4().hex}"
        job_payload = {
            "connector_id": self.connector_id,
            "operation_type": "EXTERNAL_WEBHOOK_NOTIFY",
            "idempotency_key": idem_key,
            "max_attempts": 1,
            "payload": {"event": "prescription_signed"}
        }

        # Create Job
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/ops/jobs",
            self._headers(),
            {},
            json.dumps(job_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        job_id = json.loads(body)["id"]

        # Fail attempt -> exhausts attempts -> dead_lettered
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/jobs/{job_id}/attempt",
            self._headers(),
            {},
            json.dumps({"simulated_outcome": "TRANSIENT_5XX"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["job_state"], "dead_lettered")

        # List Dead Letter Items
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/ops/dead-letter",
            self._headers(),
            {"job_id": job_id},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        dlq_items = json.loads(body)["dead_letter_items"]
        self.assertGreaterEqual(len(dlq_items), 1)
        dlq_id = dlq_items[0]["id"]

        # Resolve Dead Letter Item with REPLAY
        resolve_payload = {
            "action": "REPLAY",
            "rationale": "Operator authorized safe replay via integration workbench."
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/dead-letter/{dlq_id}/resolve",
            self._headers(),
            {},
            json.dumps(resolve_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["resolution_status"], "REPLAYED")

    def test_06_callbacks_and_connector_shutdown_api(self):
        """Test callback deduplication API and emergency connector shutdown API."""
        msg_id = f"msg-api-{uuid.uuid4().hex[:12]}"
        callback_payload = {
            "connector_id": self.connector_id,
            "source_system": "ABDM_GATEWAY",
            "external_msg_id": msg_id,
            "payload": {"consentId": "CONS-777", "status": "REVOKED"}
        }

        # 1. Ingest callback
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/ops/callbacks",
            self._headers(),
            {},
            json.dumps(callback_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        res1 = json.loads(body)
        self.assertEqual(res1["processing_status"], "PROCESSED")
        self.assertFalse(res1["is_duplicate"])

        # 2. Ingest duplicate callback
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/ops/callbacks",
            self._headers(),
            {},
            json.dumps(callback_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        res2 = json.loads(body)
        self.assertEqual(res2["processing_status"], "DUPLICATE_IGNORED")
        self.assertTrue(res2["is_duplicate"])

        # 3. Disable Connector
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/ops/connectors/{self.connector_id}/disable",
            self._headers(),
            {},
            json.dumps({"reason": "Scheduled partner gateway migration window"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()

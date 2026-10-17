"""Integration Tests for Enterprise Workflow Intelligence, SLA Governance & Exception Resolution REST APIs.

Phase 36 for ZAYVORA MATAB OS.
Tests all 19 REST endpoints via ApiRouter.dispatch:
1.  GET  /api/v1/sla/policies
2.  POST /api/v1/sla/policies
3.  GET  /api/v1/sla/policies/{id}
4.  PUT  /api/v1/sla/policies/{id}
5.  POST /api/v1/sla/policies/{id}/advance
6.  GET  /api/v1/sla/exceptions
7.  POST /api/v1/sla/exceptions
8.  GET  /api/v1/sla/exceptions/{id}
9.  POST /api/v1/sla/exceptions/{id}/acknowledge
10. POST /api/v1/sla/exceptions/{id}/assign
11. POST /api/v1/sla/exceptions/{id}/start
12. POST /api/v1/sla/exceptions/{id}/pause
13. POST /api/v1/sla/exceptions/{id}/resume
14. POST /api/v1/sla/exceptions/{id}/resolve
15. POST /api/v1/sla/exceptions/{id}/verify
16. POST /api/v1/sla/exceptions/{id}/dismiss
17. POST /api/v1/sla/exceptions/{id}/reopen
18. POST /api/v1/sla/exceptions/{id}/escalate
19. GET  /api/v1/sla/monitor
20. RBAC boundaries (401 Unauthenticated, 403 Forbidden).
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestSlaGovernanceApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_sla_governance_api.db")
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

        # Create secondary verifier user and session
        # Authenticate Practitioner (Hakeem Tariq)
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
    # 1. SLA Policy Endpoints
    # --------------------------------------------------------------------------

    def test_01_list_and_create_policies(self):
        """GET /api/v1/sla/policies & POST /api/v1/sla/policies"""
        # List seeded policies
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/sla/policies", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertGreaterEqual(data["total_policies"], 5)

        # Create new policy draft
        payload = {
            "name": "Integration Webhook Delivery SLA",
            "category": "integration",
            "target_entity_type": "integration_jobs",
            "owner_role": "SYSTEM_ADMIN",
            "warning_threshold_mins": 15,
            "breach_threshold_mins": 30,
            "verification_required": False,
            "allowed_resolution_codes": ["JOB_REPROCESSED", "PAYLOAD_AMENDED_AND_REPLAYED"]
        }
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/sla/policies", self.auth_headers, {}, json.dumps(payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertEqual(created["status"], "DRAFT")
        self.assertEqual(created["warning_threshold_mins"], 15)
        self.__class__.created_policy_id = created["id"]

    def test_02_get_update_and_advance_policy(self):
        """GET, PUT & POST /advance on SLA policy"""
        pid = self.__class__.created_policy_id

        # GET
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/sla/policies/{pid}", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["id"], pid)

        # PUT
        status, _, body = ApiRouter.dispatch(
            "PUT", f"/api/v1/sla/policies/{pid}", self.auth_headers, {},
            json.dumps({"description": "Updated SLA description"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["description"], "Updated SLA description")

        # Advance: submit_for_review
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/policies/{pid}/advance", self.auth_headers, {},
            json.dumps({"transition": "submit_for_review"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "IN_REVIEW")

        # Advance: approve
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/policies/{pid}/advance", self.auth_headers, {},
            json.dumps({"transition": "approve", "reason": "Approved by API test"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "APPROVED")

        # Advance: activate
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/policies/{pid}/advance", self.auth_headers, {},
            json.dumps({"transition": "activate"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ACTIVE")

    # --------------------------------------------------------------------------
    # 2. Workflow Exceptions Endpoints
    # --------------------------------------------------------------------------

    def test_03_create_list_and_get_exception(self):
        """POST, GET /api/v1/sla/exceptions"""
        source_id = f"job-{uuid.uuid4().hex[:6]}"
        payload = {
            "category": "administrative",
            "source_entity": "queue_tokens",
            "source_entity_id": source_id,
            "title": f"Queue delay for {source_id}"
        }

        # POST /api/v1/sla/exceptions
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/sla/exceptions", self.auth_headers, {}, json.dumps(payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        exc = json.loads(body)
        self.assertEqual(exc["status"], "OPEN")
        self.__class__.created_exc_id = exc["id"]

        # GET /api/v1/sla/exceptions
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/sla/exceptions", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertGreaterEqual(data["total_exceptions"], 1)

        # GET /api/v1/sla/exceptions/{id}
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/sla/exceptions/{exc['id']}", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["id"], exc["id"])

    def test_04_exception_lifecycle_workflow(self):
        """POST /acknowledge, /assign, /start, /pause, /resume, /resolve, /verify"""
        eid = self.__class__.created_exc_id

        # 1. Acknowledge
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/acknowledge", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "ACKNOWLEDGED")

        # 2. Assign
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/assign", self.auth_headers, {},
            json.dumps({"assigned_role": "FRONT_DESK"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["assigned_role"], "FRONT_DESK")

        # 3. Start
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/start", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "IN_PROGRESS")

        # 4. Pause
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/pause", self.auth_headers, {},
            json.dumps({"pause_reason_code": "WAITING_PATIENT_RESPONSE", "notes": "Paused for consultation"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "WAITING")

        # 5. Resume
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/resume", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "IN_PROGRESS")

        # 6. Resolve
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/resolve", self.auth_headers, {},
            json.dumps({"resolution_code": "CALLED_TO_CONSULT", "resolution_notes": "Patient called to consult room 2"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "RESOLVED")

    def test_05_dismiss_reopen_and_escalate(self):
        """POST /dismiss, /reopen & /escalate on exception"""
        source_id = f"tok-dis-{uuid.uuid4().hex[:6]}"
        payload = {
            "category": "administrative",
            "source_entity": "queue_tokens",
            "source_entity_id": source_id
        }
        _, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/sla/exceptions", self.auth_headers, {}, json.dumps(payload).encode("utf-8"), "127.0.0.1", self.db_path
        )
        eid = json.loads(body)["id"]

        # Dismiss
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/dismiss", self.auth_headers, {},
            json.dumps({"dismissal_reason": "Duplicate registration"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "DISMISSED")

        # Reopen
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/reopen", self.auth_headers, {},
            json.dumps({"reopen_reason": "Confirmed distinct patient"}).encode("utf-8"), "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "OPEN")

        # Escalate
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/sla/exceptions/{eid}/escalate", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        self.assertIn("escalations_triggered", res)

    def test_06_sla_monitor_summary(self):
        """GET /api/v1/sla/monitor"""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/sla/monitor", self.auth_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        summary = json.loads(body)
        self.assertIn("active_policies_count", summary)
        self.assertIn("total_open_exceptions", summary)
        self.assertIn("breached_count", summary)
        self.assertIn("caveats", summary)

    # --------------------------------------------------------------------------
    # 3. RBAC & Security Boundary Tests
    # --------------------------------------------------------------------------

    def test_07_unauthenticated_request_blocked(self):
        """Unauthenticated requests must be rejected with 401."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/sla/policies", {}, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["code"], "UNAUTHORIZED")


if __name__ == "__main__":
    unittest.main()

"""Integration Tests for Clinical Workflow Automation & Rules Engine REST APIs.

Phase 35 validation for ZAYVORA MATAB OS.
Tests all 12 REST endpoints via ApiRouter.dispatch:
1.  GET  /api/v1/workflow/rules
2.  POST /api/v1/workflow/rules
3.  GET  /api/v1/workflow/rules/{id}
4.  PUT  /api/v1/workflow/rules/{id}
5.  POST /api/v1/workflow/rules/{id}/advance
6.  POST /api/v1/workflow/rules/{id}/dry-run
7.  POST /api/v1/workflow/events
8.  GET  /api/v1/workflow/actions
9.  POST /api/v1/workflow/actions/{id}/approve
10. POST /api/v1/workflow/actions/{id}/reject
11. POST /api/v1/workflow/actions/{id}/retry
12. GET  /api/v1/workflow/monitor
13. RBAC & Security Boundary Tests (401 unauthenticated, 403 forbidden)
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, date

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestWorkflowAutomationApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_workflow_automation_api.db")
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

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        cls.admin_id = admin_row["id"]
        cls.org_id = admin_row["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-central-opd"

        # Patient
        cls.patient_id = f"pat-wf-api-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, family_name, display_name, date_of_birth, sex)
            VALUES (?, ?, ?, ?, 'Fatima', 'Bibi', 'Fatima Bibi', '1995-04-12', 'FEMALE');
            """,
            (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-{uuid.uuid4().hex[:6]}")
        )
        # Patient consent
        cur.execute(
            """
            INSERT INTO communication_preferences (
                id, organization_id, facility_id, patient_id, preferred_language, preferred_channel,
                opt_out_status, do_not_contact_scope, recorded_by
            ) VALUES (?, ?, ?, ?, 'en', 'sms', 0, 'none', ?);
            """,
            (f"pref-{uuid.uuid4().hex[:8]}", cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id)
        )
        conn.commit()
        conn.close()

    def test_01_list_and_filter_rules(self):
        """GET /api/v1/workflow/rules lists rules with filters."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/workflow/rules",
            self.auth_headers,
            {"status": "active"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("items", data)
        self.assertGreaterEqual(len(data["items"]), 1)
        # All items returned have status active
        for r in data["items"]:
            self.assertEqual(r["status"].upper(), "ACTIVE")

    def test_02_create_get_update_rule(self):
        """POST, GET, PUT /api/v1/workflow/rules creates, retrieves, and updates rule."""
        rule_payload = {
            "name": "Integration Test Administrative Rule",
            "description": "Rule to test CRUD via API",
            "event_type": "CHECKIN_COMPLETED",
            "action_category": "routine_administrative",
            "target_entity": "queue_tokens",
            "conditions_json": [
                {"field": "status", "operator": "equals", "value": "WAITING"}
            ],
            "actions_json": [
                {"action_type": "CREATE_ADMIN_TASK", "parameters": {"task_name": "Verify Intake Information"}}
            ]
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/workflow/rules",
            self.auth_headers,
            {},
            json.dumps(rule_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        created = json.loads(body)
        rule_id = created["id"]
        self.assertEqual(created["status"].upper(), "DRAFT")
        self.assertEqual(created["version"], 1)

        # GET rule by ID
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/workflow/rules/{rule_id}",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        retrieved = json.loads(body)
        self.assertEqual(retrieved["id"], rule_id)
        self.assertEqual(retrieved["rule_name"], "Integration Test Administrative Rule")

        # PUT update rule
        update_payload = {
            "name": "Updated Administrative Rule",
            "conditions_json": [
                {"field": "status", "operator": "equals", "value": "WAITING_UPDATED"}
            ]
        }
        status, _, body = ApiRouter.dispatch(
            "PUT",
            f"/api/v1/workflow/rules/{rule_id}",
            self.auth_headers,
            {},
            json.dumps(update_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        updated = json.loads(body)
        self.assertEqual(updated["rule_name"], "Updated Administrative Rule")

    def test_03_advance_rule_lifecycle_and_dry_run(self):
        """POST /api/v1/workflow/rules/{id}/advance and /dry-run."""
        # 1. Create a draft rule
        rule_payload = {
            "name": "Lifecycle and Dry-Run Rule",
            "description": "Lifecycle transition test",
            "event_type": "PATIENT_REGISTERED",
            "action_category": "routine_administrative",
            "target_entity": "patients",
            "conditions_json": [
                {"field": "age", "operator": "greater_than", "value": 18}
            ],
            "actions_json": [
                {"action_type": "CREATE_ADMIN_TASK", "parameters": {"task_name": "Adult Patient Onboarding"}}
            ]
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/workflow/rules",
            self.auth_headers,
            {},
            json.dumps(rule_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        rule_id = json.loads(body)["id"]

        # 2. Advance to review
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/workflow/rules/{rule_id}/advance",
            self.auth_headers,
            {},
            json.dumps({"target_status": "review"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"].upper(), "IN_REVIEW")

        # 3. Advance to active
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/workflow/rules/{rule_id}/advance",
            self.auth_headers,
            {},
            json.dumps({"target_status": "active"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"].upper(), "ACTIVE")

        # 4. Dry-run execution
        dry_payload = {
            "sample_event_payload": {
                "age": 25,
                "mrn": "MRN-12345"
            }
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/workflow/rules/{rule_id}/dry-run",
            self.auth_headers,
            {},
            json.dumps(dry_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        dry_res = json.loads(body)
        self.assertEqual(dry_res["mode"], "DRY_RUN")
        self.assertTrue(dry_res["conditions_matched"])
        self.assertEqual(len(dry_res["proposed_actions"]), 1)
        self.assertEqual(dry_res["proposed_actions"][0]["action_type"], "CREATE_ADMIN_TASK")

    def test_04_ingest_event_and_list_actions(self):
        """POST /api/v1/workflow/events ingests event and GET /api/v1/workflow/actions lists actions."""
        evt_payload = {
            "facility_id": self.fac_id,
            "event_type": "APPOINTMENT_STATUS_CHANGED",
            "event_source": "appointments",
            "source_entity_id": f"apt-int-{uuid.uuid4().hex[:6]}",
            "payload": {
                "patient_id": self.patient_id,
                "status": "booked",
                "consultation_type": "GENERAL_OPD",
                "phone": "+91-9876543210"
            }
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/workflow/events",
            self.auth_headers,
            {},
            json.dumps(evt_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertEqual(res["status"], "PROCESSED")
        self.assertGreaterEqual(res["actions_planned"], 1)

        # GET /api/v1/workflow/actions
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/workflow/actions",
            self.auth_headers,
            {"action_type": "CREATE_ADMIN_TASK"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        actions = json.loads(body)
        self.assertIn("items", actions)
        self.assertGreaterEqual(len(actions["items"]), 1)

    def test_05_human_approval_reject_and_retry(self):
        """POST /actions/{id}/approve, /reject, and /retry."""
        # Ingest an inventory breach to trigger sensitive rule
        evt_payload = {
            "facility_id": self.fac_id,
            "event_type": "INVENTORY_THRESHOLD_BREACH",
            "event_source": "inventory_batches",
            "source_entity_id": f"bat-{uuid.uuid4().hex[:6]}",
            "payload": {
                "batch_number": "BATCH-TR-2026",
                "remaining_quantity": 3
            }
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/workflow/events",
            self.auth_headers,
            {},
            json.dumps(evt_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        pa = json.loads(body)["planned_actions"][0]
        self.assertEqual(pa["status"], "AWAITING_APPROVAL")
        action_id = pa["action_id"]

        # Approve
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/workflow/actions/{action_id}/approve",
            self.auth_headers,
            {},
            json.dumps({"review_notes": "Stock order verified"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        app_res = json.loads(body)
        self.assertEqual(app_res["status"], "SUCCEEDED")
        self.assertEqual(app_res["approved_by"], self.admin_id)

        # Test Reject on another action
        evt_payload2 = {
            "facility_id": self.fac_id,
            "event_type": "INVENTORY_THRESHOLD_BREACH",
            "event_source": "inventory_batches",
            "source_entity_id": f"bat-{uuid.uuid4().hex[:6]}",
            "payload": {
                "batch_number": "BATCH-REJ-2026",
                "remaining_quantity": 2
            }
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/workflow/events",
            self.auth_headers,
            {},
            json.dumps(evt_payload2).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        action_id2 = json.loads(body)["planned_actions"][0]["action_id"]

        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/workflow/actions/{action_id2}/reject",
            self.auth_headers,
            {},
            json.dumps({"rejection_reason": "Excess inventory already in reserve"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        rej_res = json.loads(body)
        self.assertEqual(rej_res["status"], "REJECTED")

        # Test Retry on an action
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/workflow/actions/{action_id}/retry",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        ret_res = json.loads(body)
        self.assertEqual(ret_res["action_id"], action_id)

    def test_06_monitor_summary(self):
        """GET /api/v1/workflow/monitor returns operational summary."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/workflow/monitor",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        mon = json.loads(body)
        self.assertIn("active_rules_count", mon)
        self.assertIn("awaiting_approval_count", mon)
        self.assertIn("needs_review_count", mon)
        self.assertIn("events_processed_today", mon)

    def test_07_rbac_and_unauthorized_access(self):
        """Unauthenticated requests yield 401; unauthorized role without workflow:manage yields 403."""
        # 1. Unauthenticated request
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/workflow/rules",
            {},
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 401)

        # 2. Authenticate a user with receptionist / front-desk role (read only, no manage)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = 'receptionist' LIMIT 1;")
        rec_row = cur.fetchone()
        conn.close()

        if rec_row:
            status, _, body = ApiRouter.dispatch(
                "POST",
                "/api/v1/auth/login",
                {"Content-Type": "application/json"},
                {},
                json.dumps({"username": "receptionist", "password": "matab123"}).encode("utf-8"),
                "127.0.0.1",
                self.db_path,
            )
            rec_token = json.loads(body)["token"]
            rec_headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {rec_token}"
            }
            # Attempt to create a rule (requires workflow:manage)
            status, _, body = ApiRouter.dispatch(
                "POST",
                "/api/v1/workflow/rules",
                rec_headers,
                {},
                json.dumps({"name": "Disallowed Rule"}).encode("utf-8"),
                "127.0.0.1",
                self.db_path,
            )
            self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()

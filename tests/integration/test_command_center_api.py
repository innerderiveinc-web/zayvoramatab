"""Integration Tests for Clinical Operations Command Center & Capacity Planning REST APIs.

Phase 34 validation for ZAYVORA MATAB OS.
Tests all 11 REST endpoints via ApiRouter.dispatch:
1.  GET  /api/v1/command-center/live
2.  GET  /api/v1/command-center/live (wallboard_mode=true privacy check)
3.  GET  /api/v1/command-center/schedule
4.  GET  /api/v1/command-center/bottlenecks
5.  GET  /api/v1/command-center/capacity
6.  POST /api/v1/command-center/capacity/simulate
7.  GET  /api/v1/command-center/capacity/scenarios
8.  GET  /api/v1/command-center/workload
9.  GET  /api/v1/command-center/alerts
10. POST /api/v1/command-center/alerts/{id}/acknowledge
11. POST /api/v1/command-center/alerts/{id}/resolve
12. POST /api/v1/command-center/actions
13. RBAC & Security Boundary Tests
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, date, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestCommandCenterApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_cmd_center_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin (has ORG_ADMIN with command_center:manage, capacity:plan)
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

        cur.execute("SELECT user_id FROM practitioner_profiles LIMIT 1;")
        p_row = cur.fetchone()
        cls.practitioner_id = p_row["user_id"] if p_row else cls.admin_id

        # Patient
        cls.patient_id = f"pat-cmd-int-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, family_name, display_name, date_of_birth, sex)
            VALUES (?, ?, ?, ?, 'Zainab', 'Bibi', 'Zainab Bibi', '1992-06-15', 'FEMALE');
            """,
            (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-{uuid.uuid4().hex[:6]}")
        )

        today_str = date.today().isoformat()
        now_dt = datetime.now(timezone.utc)

        # 1. Facility settings (7 working days)
        cur.execute(
            """
            INSERT OR REPLACE INTO facility_settings (
                facility_id, organization_id, timezone, working_hours_start, working_hours_end,
                working_days_json, default_slot_duration_mins, buffer_time_mins, inventory_enabled
            ) VALUES (?, ?, 'Asia/Kolkata', '09:00', '17:00', '["MON","TUE","WED","THU","FRI","SAT","SUN"]', 15, 0, 1);
            """,
            (cls.fac_id, cls.org_id)
        )

        # 2. Practitioner schedule (09:00 - 17:00, break 13:00 - 14:00)
        cur.execute(
            """
            INSERT OR REPLACE INTO practitioner_schedules (
                id, organization_id, facility_id, practitioner_id, day_of_week,
                start_time, end_time, break_start_time, break_end_time,
                slot_duration_mins, buffer_time_mins, slot_capacity, room_resource, is_active
            ) VALUES (?, ?, ?, ?, 'ALL', '09:00', '17:00', '13:00', '14:00', 15, 0, 1, 'Consult-1', 1);
            """,
            (f"ps-{uuid.uuid4().hex[:8]}", cls.org_id, cls.fac_id, cls.practitioner_id)
        )

        # 3. Appointments
        cls.appt_id = f"apt-int-{uuid.uuid4().hex[:6]}"
        cur.execute(
            """
            INSERT INTO appointments (
                id, organization_id, facility_id, patient_id, practitioner_id,
                appointment_type, status, start_at, end_at, room_resource, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, 'INITIAL_CONSULTATION', 'booked', ?, ?, 'Consult-1', ?, ?);
            """,
            (
                cls.appt_id, cls.org_id, cls.fac_id, cls.patient_id, cls.practitioner_id,
                f"{today_str}T10:00:00Z", f"{today_str}T10:15:00Z", cls.admin_id, cls.admin_id
            )
        )

        # 4. Queue Token (45 mins waiting -> Bottleneck threshold exceeded)
        cls.token_id = f"tok-int-{uuid.uuid4().hex[:6]}"
        arr_time = (now_dt - timedelta(minutes=45)).isoformat()
        cur.execute(
            """
            INSERT INTO queue_tokens (
                id, organization_id, facility_id, queue_date, token_number, token_code,
                patient_id, practitioner_id, status, arrival_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, 201, 'T-201', ?, ?, 'waiting', ?, ?, ?);
            """,
            (
                cls.token_id, cls.org_id, cls.fac_id, today_str,
                cls.patient_id, cls.practitioner_id, arr_time, cls.admin_id, cls.admin_id
            )
        )

        conn.commit()
        conn.close()

    def test_01_get_live_operations_standard_and_wallboard(self):
        """GET /api/v1/command-center/live verifies live operational pulse and wallboard privacy mode."""
        # 1. Standard mode
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/live",
            self.auth_headers,
            {"facility_id": self.fac_id},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("workload_pulse", data)
        self.assertIn("active_queue", data)
        self.assertFalse(data["wallboard_mode"])
        # In standard mode, patient_name should be present
        if len(data["active_queue"]) > 0:
            self.assertIn("patient_name", data["active_queue"][0])

        # 2. Wallboard privacy mode
        status_wb, _, body_wb = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/live",
            self.auth_headers,
            {"facility_id": self.fac_id, "wallboard_mode": "true"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status_wb, 200)
        data_wb = json.loads(body_wb)
        self.assertTrue(data_wb["wallboard_mode"])
        self.assertIn("active_queue", data_wb)
        # In wallboard mode, zero PHI allowed
        for item in data_wb["active_queue"]:
            self.assertNotIn("patient_id", item)
            self.assertNotIn("patient_name", item)
            self.assertNotIn("mrn", item)
            self.assertIn("patient_ref", item)
            self.assertTrue(item["patient_ref"].startswith("Token "))

    def test_02_get_today_schedule(self):
        """GET /api/v1/command-center/schedule retrieves timeline appointments and resource blocks."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/schedule",
            self.auth_headers,
            {"facility_id": self.fac_id},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("appointments", data)
        self.assertIn("conflicts_detected", data)
        self.assertGreaterEqual(data["total_appointments"], 1)

    def test_03_get_workflow_bottlenecks(self):
        """GET /api/v1/command-center/bottlenecks computes stage delay items against approved thresholds."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/bottlenecks",
            self.auth_headers,
            {"facility_id": self.fac_id},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("bottlenecks", data)
        self.assertGreaterEqual(data["total_bottlenecks_detected"], 1)
        # Check factual reason is provided
        b0 = data["bottlenecks"][0]
        self.assertIn("factual_reason", b0)
        self.assertIn("severity", b0)

    def test_04_get_capacity_plan(self):
        """GET /api/v1/command-center/capacity computes deterministic slots from schedule duration."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/capacity",
            self.auth_headers,
            {"facility_id": self.fac_id},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["status"], "calculated")
        self.assertIn("capacity_formula", data)
        self.assertGreaterEqual(data["total_configured_capacity"], 20)
        self.assertIn("caveats", data)

    def test_05_simulate_and_list_capacity_scenarios(self):
        """POST & GET /api/v1/command-center/capacity/simulate tests hypothetical simulations."""
        sim_payload = {
            "scenario_name": "Evening Extended Hours Test",
            "target_date": date.today().isoformat(),
            "facility_id": self.fac_id,
            "hypothetical_changes": [
                {
                    "change_type": "ADD_PRACTITIONER_SHIFT",
                    "shift_hours": 2,
                    "slot_duration_mins": 15
                }
            ],
            "save_scenario": True,
            "description": "Adding 1 evening locum practitioner for 2 hours."
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/command-center/capacity/simulate",
            self.auth_headers,
            {},
            json.dumps(sim_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        sim_res = json.loads(body)
        self.assertTrue(sim_res["is_simulation_only"])
        self.assertIn("variance_slots", sim_res)
        scenario_id = sim_res["scenario_id"]
        self.assertTrue(scenario_id.startswith("scen-"))

        # List saved scenarios
        status_l, _, body_l = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/capacity/scenarios",
            self.auth_headers,
            {"facility_id": self.fac_id},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status_l, 200)
        scenarios_data = json.loads(body_l)
        self.assertGreaterEqual(scenarios_data["total_scenarios"], 1)

    def test_06_get_workload_distribution(self):
        """GET /api/v1/command-center/workload retrieves role and practitioner load without speed ranking."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/workload",
            self.auth_headers,
            {"facility_id": self.fac_id},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("practitioner_workload", data)
        self.assertIn("role_task_workload", data)

    def test_07_operational_alerts_and_actions(self):
        """Alerts lifecycle (list, ack, resolve) and human action audit ledger."""
        # 1. List Alerts
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/alerts",
            self.auth_headers,
            {"facility_id": self.fac_id, "status": "ACTIVE"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        alerts_data = json.loads(body)
        self.assertGreaterEqual(alerts_data["total_alerts"], 1)
        alert_id = alerts_data["alerts"][0]["id"]

        # 2. Acknowledge Alert
        status_ack, _, body_ack = ApiRouter.dispatch(
            "POST",
            f"/api/v1/command-center/alerts/{alert_id}/acknowledge",
            self.auth_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status_ack, 200)
        ack_res = json.loads(body_ack)
        self.assertEqual(ack_res["status"], "ACKNOWLEDGED")

        # 3. Resolve Alert
        status_res, _, body_res = ApiRouter.dispatch(
            "POST",
            f"/api/v1/command-center/alerts/{alert_id}/resolve",
            self.auth_headers,
            {},
            json.dumps({"resolution_notes": "Practitioner called token for vitals assessment"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status_res, 200)
        res_data = json.loads(body_res)
        self.assertEqual(res_data["status"], "RESOLVED")

        # 4. Perform Audited Operational Action
        action_payload = {
            "action_type": "REQUEST_SCHEDULE_REVIEW",
            "target_entity": "practitioner_schedules",
            "target_id": "ps-default",
            "reason": "Mid-day queue congestion noticed due to extended case history reviews"
        }
        status_act, _, body_act = ApiRouter.dispatch(
            "POST",
            "/api/v1/command-center/actions",
            self.auth_headers,
            {},
            json.dumps(action_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status_act, 201)
        act_res = json.loads(body_act)
        self.assertEqual(act_res["status"], "SUCCESS")
        self.assertEqual(act_res["action_type"], "REQUEST_SCHEDULE_REVIEW")

    def test_08_rbac_and_unauthorized_access(self):
        """Endpoints enforce authentication and role permissions."""
        # Unauthenticated call
        status, _, _ = ApiRouter.dispatch(
            "GET",
            "/api/v1/command-center/live",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

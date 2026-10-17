"""Unit tests for Clinical Operations Command Center & Capacity Planning Engine.

Phase 34 validation for ZAYVORA MATAB OS.
Tests:
1. Live operations snapshot calculation from canonical records.
2. Privacy-preserving wallboard mode (zero PHI, opaque tokens).
3. Today's schedule timeline and conflict detection (leave overlap).
4. Workflow bottleneck detection, elapsed ages, and transparent factual reasons.
5. Deterministic capacity planning (shift hours, breaks, slot length, demand vs capacity).
6. Hypothetical capacity scenario planning (simulations strictly segregated from production).
7. Operational alert state machine and audited human-in-the-loop action logging.
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
from apps.api.domains.command_center import ClinicalCommandCenterEngine


class TestClinicalCommandCenterEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_command_center.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)
        cls.engine = ClinicalCommandCenterEngine(db_path=cls.db_path)

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

        # Practitioner
        cur.execute("SELECT user_id FROM practitioner_profiles LIMIT 1;")
        p_row = cur.fetchone()
        cls.practitioner_id = p_row["user_id"] if p_row else cls.admin_id

        # Patient
        cls.patient_id = f"pat-cmd-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, family_name, display_name, date_of_birth, sex)
            VALUES (?, ?, ?, ?, 'Fatima', 'Begum', 'Fatima Begum', '1985-04-10', 'FEMALE');
            """,
            (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-{uuid.uuid4().hex[:6]}")
        )

        today_str = date.today().isoformat()
        now_dt = datetime.now(timezone.utc)

        # 1. Facility Settings
        cur.execute(
            """
            INSERT OR REPLACE INTO facility_settings (
                facility_id, organization_id, timezone, working_hours_start, working_hours_end,
                working_days_json, default_slot_duration_mins, buffer_time_mins, inventory_enabled
            ) VALUES (?, ?, 'Asia/Kolkata', '09:00', '17:00', '["MON","TUE","WED","THU","FRI","SAT","SUN"]', 15, 0, 1);
            """,
            (cls.fac_id, cls.org_id)
        )

        # 2. Practitioner Schedule for ALL days
        cur.execute(
            """
            INSERT OR REPLACE INTO practitioner_schedules (
                id, organization_id, facility_id, practitioner_id, day_of_week,
                start_time, end_time, break_start_time, break_end_time,
                slot_duration_mins, buffer_time_mins, slot_capacity, room_resource, is_active
            ) VALUES (?, ?, ?, ?, 'ALL', '09:00', '17:00', '13:00', '14:00', 15, 0, 1, 'Room-1', 1);
            """,
            (f"ps-{uuid.uuid4().hex[:8]}", cls.org_id, cls.fac_id, cls.practitioner_id)
        )

        # 3. Appointments: 1 Booked, 1 Completed
        cls.appt_1_id = f"apt-cmd-1-{uuid.uuid4().hex[:6]}"
        cur.execute(
            """
            INSERT INTO appointments (
                id, organization_id, facility_id, patient_id, practitioner_id,
                appointment_type, status, start_at, end_at, room_resource, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, 'INITIAL_CONSULTATION', 'booked', ?, ?, 'Room-1', ?, ?);
            """,
            (
                cls.appt_1_id, cls.org_id, cls.fac_id, cls.patient_id, cls.practitioner_id,
                f"{today_str}T10:00:00Z", f"{today_str}T10:15:00Z", cls.admin_id, cls.admin_id
            )
        )

        cls.appt_2_id = f"apt-cmd-2-{uuid.uuid4().hex[:6]}"
        cur.execute(
            """
            INSERT INTO appointments (
                id, organization_id, facility_id, patient_id, practitioner_id,
                appointment_type, status, start_at, end_at, room_resource, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, 'INITIAL_CONSULTATION', 'completed', ?, ?, 'Room-1', ?, ?);
            """,
            (
                cls.appt_2_id, cls.org_id, cls.fac_id, cls.patient_id, cls.practitioner_id,
                f"{today_str}T10:30:00Z", f"{today_str}T10:45:00Z", cls.admin_id, cls.admin_id
            )
        )

        # 4. Queue Token: 1 Waiting (arrived 45 mins ago -> Bottleneck)
        cls.tok_id = f"tok-cmd-{uuid.uuid4().hex[:6]}"
        arr_time = (now_dt - timedelta(minutes=45)).isoformat()
        cur.execute(
            """
            INSERT INTO queue_tokens (
                id, organization_id, facility_id, queue_date, token_number, token_code,
                patient_id, practitioner_id, status, arrival_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, 101, 'T-101', ?, ?, 'waiting', ?, ?, ?);
            """,
            (
                cls.tok_id, cls.org_id, cls.fac_id, today_str,
                cls.patient_id, cls.practitioner_id, arr_time, cls.admin_id, cls.admin_id
            )
        )

        # 5. Threshold Rule for CHECK_IN_TO_CALL: 30m warning, 60m critical
        cur.execute(
            """
            INSERT OR REPLACE INTO command_center_threshold_rules (
                id, organization_id, facility_id, stage_key, warning_threshold_mins,
                critical_threshold_mins, approved_by, approved_at, version, is_active
            ) VALUES (?, ?, ?, 'CHECK_IN_TO_CALL', 30, 60, ?, CURRENT_TIMESTAMP, 1, 1);
            """,
            (f"th-{uuid.uuid4().hex[:8]}", cls.org_id, cls.fac_id, cls.admin_id)
        )

        conn.commit()
        conn.close()

        cls.user_ctx = {
            "id": cls.admin_id,
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
            "roles": ["ORG_ADMIN"]
        }

    def test_01_live_operations_snapshot(self):
        """Live operations snapshot computes accurate counts from persisted records."""
        res = self.engine.get_live_operations_snapshot({}, self.user_ctx, wallboard_mode=False)
        self.assertIn("workload_pulse", res)
        self.assertIn("active_queue", res)
        self.assertIn("caveats", res)
        pulse = res["workload_pulse"]
        self.assertGreaterEqual(pulse["appointments_total"], 2)
        self.assertGreaterEqual(pulse["appointments_booked"], 1)
        self.assertGreaterEqual(pulse["appointments_completed"], 1)
        self.assertGreaterEqual(pulse["queue_waiting"], 1)

        # Check patient info is present when not in wallboard mode
        queue_items = res["active_queue"]
        self.assertTrue(len(queue_items) > 0)
        first = queue_items[0]
        self.assertIn("patient_name", first)
        self.assertEqual(first["patient_name"], "Fatima Begum")

    def test_02_privacy_preserving_wallboard_mode(self):
        """Wallboard mode strictly strips all patient identifiable data and uses opaque tokens."""
        res = self.engine.get_live_operations_snapshot({}, self.user_ctx, wallboard_mode=True)
        self.assertTrue(res["wallboard_mode"])
        queue_items = res["active_queue"]
        self.assertTrue(len(queue_items) > 0)
        first = queue_items[0]
        # Zero PHI verification
        self.assertNotIn("patient_name", first)
        self.assertNotIn("mrn", first)
        self.assertNotIn("patient_id", first)
        self.assertIn("patient_ref", first)
        self.assertIn("Token T-101", first["patient_ref"])

    def test_03_today_schedule_and_conflicts(self):
        """Today's schedule lists timeline appointments and identifies schedule conflicts."""
        # Insert a practitioner block during an appointment slot
        conn = self.engine._get_connection()
        cur = conn.cursor()
        block_id = f"blk-cmd-{uuid.uuid4().hex[:6]}"
        today_str = date.today().isoformat()
        cur.execute(
            """
            INSERT INTO practitioner_schedule_blocks (
                id, organization_id, facility_id, practitioner_id, block_start_at,
                block_end_at, block_type, reason, is_active, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, 'LEAVE', 'Medical Leave', 1, ?);
            """,
            (
                block_id, self.org_id, self.fac_id, self.practitioner_id,
                f"{today_str}T09:30:00Z", f"{today_str}T11:30:00Z", self.admin_id
            )
        )
        conn.commit()
        conn.close()

        sched = self.engine.get_today_schedule({}, self.user_ctx)
        self.assertGreaterEqual(sched["total_appointments"], 2)
        self.assertGreaterEqual(len(sched["conflicts_detected"]), 1)
        conf = sched["conflicts_detected"][0]
        self.assertEqual(conf["conflict_type"], "APPOINTMENT_DURING_PRACTITIONER_BLOCK")
        self.assertEqual(conf["block_id"], block_id)

    def test_04_workflow_bottlenecks_detection(self):
        """Bottleneck intelligence detects tokens exceeding approved thresholds with factual reasons."""
        res = self.engine.get_workflow_bottlenecks({}, self.user_ctx)
        self.assertIn("bottlenecks", res)
        self.assertGreaterEqual(res["total_bottlenecks_detected"], 1)
        b = next((x for x in res["bottlenecks"] if x["item_id"] == self.tok_id), None)
        self.assertIsNotNone(b)
        self.assertEqual(b["stage_key"], "CHECK_IN_TO_CALL")
        self.assertGreaterEqual(b["elapsed_mins"], 30)
        self.assertEqual(b["severity"], "WARNING")
        self.assertIn("Patient waiting in reception", b["factual_reason"])

    def test_05_deterministic_capacity_planning(self):
        """Capacity planner computes deterministic slots from shift duration and deducts booked demand."""
        # 09:00 - 17:00 (8 hrs = 480 mins), break 13:00 - 14:00 (60 mins) -> 420 mins net.
        # 15 min slot -> 420 // 15 = 28 slots.
        plan = self.engine.get_capacity_plan({}, self.user_ctx)
        self.assertEqual(plan["status"], "calculated")
        self.assertGreaterEqual(plan["total_configured_capacity"], 20)
        self.assertGreaterEqual(plan["total_booked_demand"], 1)
        self.assertIn("capacity_formula", plan)

    def test_06_hypothetical_capacity_scenario_segregation(self):
        """Scenario simulations evaluate hypothetical adjustments without mutating production records."""
        payload = {
            "scenario_name": "Flu Season Additional Evening Shift",
            "target_date": date.today().isoformat(),
            "facility_id": self.fac_id,
            "hypothetical_changes": [
                {"change_type": "ADD_PRACTITIONER_SHIFT", "hours": 4.0, "slot_duration_mins": 15}
            ],
            "save_scenario": True
        }
        res = self.engine.evaluate_capacity_scenario(payload, self.user_ctx)
        self.assertTrue(res["is_simulation_only"])
        self.assertGreater(res["simulated_capacity"], res["baseline_capacity"])
        self.assertEqual(res["variance_slots"], 16) # 4 hrs * 60 / 15 = 16 slots

        # Verify scenario is saved in capacity_scenarios table
        scenarios = self.engine.list_capacity_scenarios({}, self.user_ctx)
        self.assertTrue(any(s["id"] == res["scenario_id"] for s in scenarios))

    def test_07_operational_alerts_lifecycle_and_actions(self):
        """Operational alerts lifecycle (ACTIVE -> ACKNOWLEDGED -> RESOLVED) and action audit ledger."""
        alerts = self.engine.list_operational_alerts({"status": "ACTIVE"}, self.user_ctx)
        self.assertTrue(len(alerts) > 0)
        alert_id = alerts[0]["id"]

        # 1. Acknowledge alert
        ack = self.engine.acknowledge_alert(alert_id, self.user_ctx)
        self.assertEqual(ack["status"], "ACKNOWLEDGED")

        # 2. Resolve alert via perform_operational_action
        action_payload = {
            "action_type": "RESOLVE_ALERT",
            "target_entity": "operational_alerts",
            "target_id": alert_id,
            "reason": "Queue congestion cleared after triaging next slot"
        }
        act_res = self.engine.perform_operational_action(action_payload, self.user_ctx)
        self.assertEqual(act_res["status"], "SUCCESS")
        self.assertEqual(act_res["action_type"], "RESOLVE_ALERT")

        # 3. Record operational exception action
        exc_payload = {
            "action_type": "RECORD_OPERATIONAL_EXCEPTION",
            "target_entity": "queue_tokens",
            "target_id": self.tok_id,
            "reason": "Patient delayed at dispensary collection"
        }
        exc_res = self.engine.perform_operational_action(exc_payload, self.user_ctx)
        self.assertEqual(exc_res["status"], "SUCCESS")
        self.assertEqual(exc_res["action_type"], "RECORD_OPERATIONAL_EXCEPTION")


if __name__ == "__main__":
    unittest.main()

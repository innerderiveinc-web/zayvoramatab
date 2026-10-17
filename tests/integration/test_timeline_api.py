"""Integration tests for Longitudinal Patient Timeline & Care Continuity REST APIs.

Phase 25 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Timeline Events listing and manual recording
2. Multi-lane encounter projection sync
3. Longitudinal medication ledger endpoints
4. Care continuity task creation and listing
5. Care continuity contact attempts and completion
6. Traceable timeline summary generation and clinician review
"""

import os
import json
import unittest
import tempfile
import sqlite3
import uuid

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestPatientTimelineApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_timeline_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.db_path
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

        # Create test patient
        cls.patient_id = f"pat-time-api-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status)
            VALUES (?, ?, ?, ?, 'Zahra', 'Zahra Khan', 'ACTIVE');
        """, (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))

        # Create test encounter
        cls.encounter_id = f"enc-time-api-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, 'signed', 2, ?);
        """, (cls.encounter_id, cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id, cls.admin_id))

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }

    # --------------------------------------------------------------------------
    # Test 1: Record and Get Timeline Events
    # --------------------------------------------------------------------------
    def test_01_timeline_events_endpoints(self):
        # Record manual event
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/patients/{self.patient_id}/timeline-events",
            self._headers(), {},
            json.dumps({
                "stream_lane": "UNANI",
                "event_type": "UNANI_OBSERVATION",
                "event_title": "Pulse Exam: Nabz-e-Azeem",
                "event_summary": "Deep, broad pulse observed reflecting Damawi dominance.",
                "occurred_at": "2026-10-12T11:00:00Z",
                "temporal_precision": "EXACT_TIMESTAMP",
                "clinical_significance": "IMPORTANT"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertIn("event_id", res)

        # Get timeline
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/patients/{self.patient_id}/longitudinal-timeline",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        timeline = json.loads(body)
        self.assertGreaterEqual(timeline["total_events"], 1)
        self.assertIn("events", timeline)

    # --------------------------------------------------------------------------
    # Test 2: Encounter Timeline Projection Sync
    # --------------------------------------------------------------------------
    def test_02_sync_encounter_timeline(self):
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/encounters/{self.encounter_id}/timeline-sync",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertGreaterEqual(res["synced_events_count"], 1)

    # --------------------------------------------------------------------------
    # Test 3: Longitudinal Medication Ledger
    # --------------------------------------------------------------------------
    def test_03_medication_ledger_endpoints(self):
        # Update medication status
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/patients/{self.patient_id}/medications/status",
            self._headers(), {},
            json.dumps({
                "formulation_name": "Khamira Gaozaban Ambari",
                "formulation_type": "MURAKKABAT",
                "current_state": "ACTIVE",
                "start_date": "2026-10-01",
                "dosage_summary": "5g morning"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

        # List medications
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/patients/{self.patient_id}/medications",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        meds = json.loads(body)["medications"]
        self.assertGreaterEqual(len(meds), 1)
        self.assertEqual(meds[0]["formulation_name"], "Khamira Gaozaban Ambari")

    # --------------------------------------------------------------------------
    # Test 4: Care Continuity Tasks
    # --------------------------------------------------------------------------
    def test_04_care_continuity_task_lifecycle_endpoints(self):
        # Create task
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/care-continuity/tasks",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "task_type": "FOLLOW_UP_CALL",
                "due_date": "2026-10-25",
                "assigned_role": "CARE_COORDINATOR"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        task_id = json.loads(body)["task_id"]

        # List tasks
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/care-continuity/tasks?patient_id={self.patient_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        tasks = json.loads(body)["tasks"]
        self.assertEqual(len(tasks), 1)

        # Record contact attempt
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/care-continuity/tasks/{task_id}/attempts",
            self._headers(), {},
            json.dumps({"outcome_notes": "Attempted WhatsApp check-in"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["contact_attempts_count"], 1)

        # Complete task
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/care-continuity/tasks/{task_id}/complete",
            self._headers(), {},
            json.dumps({"outcome_notes": "Patient reports recovery complete"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "COMPLETED")

    # --------------------------------------------------------------------------
    # Test 5: Timeline Summaries Endpoints
    # --------------------------------------------------------------------------
    def test_05_timeline_summary_endpoints(self):
        # Generate summary
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/patients/{self.patient_id}/timeline-summaries",
            self._headers(), {},
            json.dumps({"summary_type": "LONGITUDINAL_OVERVIEW"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        sum_data = json.loads(body)
        summary_id = sum_data["summary_id"]
        self.assertIn("draft_text", sum_data)
        self.assertEqual(sum_data["review_status"], "DRAFT")

        # Review summary
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/timeline-summaries/{summary_id}/review",
            self._headers(), {},
            json.dumps({
                "action": "CLINICIAN_REVIEWED",
                "review_notes": "Confirmed and approved for continuity record."
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["review_status"], "CLINICIAN_REVIEWED")


if __name__ == "__main__":
    unittest.main()

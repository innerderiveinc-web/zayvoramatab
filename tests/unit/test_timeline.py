"""Unit tests for Longitudinal Patient Timeline & Care Continuity Engine.

Phase 25 validation for ZAYVORA MATAB OS.
Tests:
1. Canonical timeline event recording & temporal precision validation
2. Chronological honest sorting across date granularities
3. Epistemological stream lane filtering (Unani, Modern, Medication)
4. Multi-lane encounter projection sync
5. Medication longitudinal status ledger lifecycle
6. Care continuity task creation, contact attempt tracking & completion
7. Traceable summary generation with per-claim timeline bindings
8. Clinician summary review & attestation
"""

import os
import unittest
import tempfile
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.timeline import PatientTimelineEngine
from apps.api.core.errors import ValidationError, NotFoundError


class TestPatientTimelineEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_timeline.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = PatientTimelineEngine(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin = cur.fetchone()
        cls.admin_id = admin["id"]
        cls.org_id = admin["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.fac_id = cur.fetchone()["id"]

        cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.patient_id = cur.fetchone()["id"]

        conn.close()

        cls.user_ctx = {
            "user_id": cls.admin_id,
            "organization_id": cls.org_id,
            "role": "CLINICIAN",
            "roles": ["CLINICIAN", "ADMIN"]
        }

    # --------------------------------------------------------------------------
    # 1. Timeline Event Recording & Precision
    # --------------------------------------------------------------------------

    def test_01_record_timeline_event_and_validation(self):
        evt = self.engine.record_timeline_event(
            organization_id=self.org_id,
            patient_id=self.patient_id,
            stream_lane="UNANI",
            event_type="UNANI_ASSESSMENT",
            event_title="Mizaj Assessment: Damawi",
            event_summary="Patient exhibits Sanguine temperament with robust pulse.",
            occurred_at="2026-10-10T10:00:00Z",
            recorded_by=self.admin_id,
            source_entity_type="unani_assessments",
            source_entity_id="u-test-1",
            temporal_precision="EXACT_TIMESTAMP",
            clinical_significance="IMPORTANT"
        )
        self.assertTrue(evt["event_id"].startswith("evt-"))
        self.assertEqual(evt["stream_lane"], "UNANI")
        self.assertEqual(evt["temporal_precision"], "EXACT_TIMESTAMP")

        # Invalid stream lane raises ValidationError
        with self.assertRaises(ValidationError):
            self.engine.record_timeline_event(
                organization_id=self.org_id,
                patient_id=self.patient_id,
                stream_lane="INVALID_LANE",
                event_type="TEST",
                event_title="Test",
                event_summary="Test",
                occurred_at="2026-10-10",
                recorded_by=self.admin_id,
                source_entity_type="test",
                source_entity_id="t-1"
            )

    def test_02_temporal_sorting_and_precision(self):
        # Create events with different dates and precisions
        p_id = f"pat-timeline-{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status) VALUES (?, ?, ?, ?, 'Temporal', 'Temporal Test', 'ACTIVE');", (p_id, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))
        conn.commit()
        conn.close()

        # Old event: 2024 (YEAR precision)
        self.engine.record_timeline_event(
            organization_id=self.org_id, patient_id=p_id, stream_lane="ADMINISTRATIVE",
            event_type="HISTORICAL_VISIT", event_title="Historical 2024 Encounter", event_summary="Old clinic visit",
            occurred_at="2024-01-01", temporal_precision="YEAR", recorded_by=self.admin_id,
            source_entity_type="historical", source_entity_id="hist-1"
        )

        # Recent event: 2026-09 (MONTH precision)
        self.engine.record_timeline_event(
            organization_id=self.org_id, patient_id=p_id, stream_lane="MODERN",
            event_type="LAB_RESULT", event_title="Lipid Profile", event_summary="Borderline cholesterol",
            occurred_at="2026-09-15", temporal_precision="MONTH", recorded_by=self.admin_id,
            source_entity_type="labs", source_entity_id="lab-1"
        )

        # Today event: exact timestamp
        self.engine.record_timeline_event(
            organization_id=self.org_id, patient_id=p_id, stream_lane="MEDICATION",
            event_type="PRESCRIPTION_ISSUED", event_title="Sharbat Ahmad Shahi", event_summary="Started course",
            occurred_at="2026-10-13T14:30:00Z", temporal_precision="EXACT_TIMESTAMP", recorded_by=self.admin_id,
            source_entity_type="prescriptions", source_entity_id="rx-1"
        )

        timeline = self.engine.get_patient_timeline(patient_id=p_id)
        self.assertEqual(timeline["total_events"], 3)
        # First event must be the newest (2026-10-13)
        self.assertEqual(timeline["events"][0]["event_title"], "Sharbat Ahmad Shahi")
        # Last event must be the oldest (2024)
        self.assertEqual(timeline["events"][2]["event_title"], "Historical 2024 Encounter")
        self.assertEqual(timeline["events"][2]["temporal_precision"], "YEAR")

    def test_03_stream_lane_filtering(self):
        p_id = f"pat-lanes-{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status) VALUES (?, ?, ?, ?, 'Lanes', 'Lanes Test', 'ACTIVE');", (p_id, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))
        conn.commit()
        conn.close()

        self.engine.record_timeline_event(self.org_id, p_id, "UNANI", "UNANI_ASSESSMENT", "Unani 1", "desc", "2026-10-01", self.admin_id, "u", "1")
        self.engine.record_timeline_event(self.org_id, p_id, "MODERN", "MODERN_ASSESSMENT", "Modern 1", "desc", "2026-10-02", self.admin_id, "m", "2")
        self.engine.record_timeline_event(self.org_id, p_id, "MEDICATION", "PRESCRIPTION_ISSUED", "Med 1", "desc", "2026-10-03", self.admin_id, "rx", "3")

        # Filter UNANI only
        res_unani = self.engine.get_patient_timeline(p_id, stream_lanes=["UNANI"])
        self.assertEqual(res_unani["total_events"], 1)
        self.assertEqual(res_unani["events"][0]["stream_lane"], "UNANI")

        # Filter UNANI and MODERN
        res_both = self.engine.get_patient_timeline(p_id, stream_lanes=["UNANI", "MODERN"])
        self.assertEqual(res_both["total_events"], 2)

    # --------------------------------------------------------------------------
    # 2. Multi-Lane Encounter Projection Sync
    # --------------------------------------------------------------------------

    def test_04_sync_encounter_events(self):
        conn = sqlite3.connect(self.db_path)
        p_id = f"pat-sync-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status) VALUES (?, ?, ?, ?, 'Sync', 'Sync Patient', 'ACTIVE');", (p_id, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))

        enc_id = f"enc-sync-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by) VALUES (?, ?, ?, ?, ?, 'signed', 2, ?);", (enc_id, self.org_id, self.fac_id, p_id, self.admin_id, self.admin_id))

        # Add Modern Assessment
        conn.execute("INSERT INTO modern_clinical_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, assessment_date, chief_complaint, working_assessment, status) VALUES (?, ?, ?, ?, ?, ?, '2026-10-13', 'Cephalea', 'Tension Headache', 'SIGNED');", (f"mod-{uuid.uuid4().hex[:8]}", self.org_id, self.fac_id, p_id, enc_id, self.admin_id))

        # Add Unani Assessment
        conn.execute("INSERT INTO unani_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, template_version_id, assessment_date, dominant_mizaj, status) VALUES (?, ?, ?, ?, ?, ?, 'ver-tmpl-unani-core-1', '2026-10-13', 'BALGHAMI', 'FINALISED');", (f"u-{uuid.uuid4().hex[:8]}", self.org_id, self.fac_id, p_id, enc_id, self.admin_id))

        # Add Prescription
        rx_id = f"rx-sync-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO prescriptions (id, organization_id, facility_id, patient_id, encounter_id, practitioner_id, prescription_number, status, version_number) VALUES (?, ?, ?, ?, ?, ?, ?, 'SIGNED', 1);", (rx_id, self.org_id, self.fac_id, p_id, enc_id, self.admin_id, f"RX-{uuid.uuid4().hex[:6]}"))
        conn.execute("""
            INSERT INTO prescription_items (id, prescription_id, item_type, item_name, dose_amount, dose_unit, dosage_form, frequency, duration_days, instructions)
            VALUES (?, ?, 'CATALOG_FORMULATION', 'Majoon Ushturghaz', '5', 'g', 'MAJOON', 'BD', 10, 'After meals with water');
        """, (f"rxi-{uuid.uuid4().hex[:8]}", rx_id))
        conn.commit()
        conn.close()

        projected = self.engine.sync_encounter_events(enc_id, self.user_ctx)
        self.assertGreaterEqual(len(projected), 4)

        lanes = [e["stream_lane"] for e in projected]
        self.assertIn("ADMINISTRATIVE", lanes)
        self.assertIn("MODERN", lanes)
        self.assertIn("UNANI", lanes)
        self.assertIn("MEDICATION", lanes)

        # Verify medication status ledger updated to ACTIVE
        meds = self.engine.list_medications(p_id, current_state="ACTIVE", user_ctx=self.user_ctx)
        self.assertTrue(any(m["formulation_name"] == "Majoon Ushturghaz" for m in meds))

    # --------------------------------------------------------------------------
    # 3. Medication Longitudinal Status Ledger
    # --------------------------------------------------------------------------

    def test_05_medication_ledger_lifecycle(self):
        p_id = f"pat-med-{uuid.uuid4().hex[:8]}"
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status) VALUES (?, ?, ?, ?, 'Med', 'Med Patient', 'ACTIVE');", (p_id, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))
        conn.commit()
        conn.close()

        # Start medication
        med = self.engine.record_medication_state_change(
            patient_id=p_id,
            formulation_name="Itrifal Muqawwi Dimagh",
            formulation_type="MURAKKABAT",
            new_state="ACTIVE",
            start_date="2026-10-01",
            dosage_summary="5g Bedtime",
            user_ctx=self.user_ctx
        )
        self.assertEqual(med["current_state"], "ACTIVE")

        # Discontinue medication
        disc = self.engine.record_medication_state_change(
            patient_id=p_id,
            formulation_name="Itrifal Muqawwi Dimagh",
            formulation_type="MURAKKABAT",
            new_state="DISCONTINUED",
            start_date="2026-10-01",
            end_date="2026-10-10",
            reason="Course completed, symptoms resolved.",
            user_ctx=self.user_ctx
        )
        self.assertEqual(disc["current_state"], "DISCONTINUED")

        # Query active vs discontinued
        active = self.engine.list_medications(p_id, current_state="ACTIVE")
        self.assertEqual(len(active), 0)

        all_meds = self.engine.list_medications(p_id)
        self.assertEqual(len(all_meds), 1)
        self.assertEqual(all_meds[0]["discontinuation_reason"], "Course completed, symptoms resolved.")

    # --------------------------------------------------------------------------
    # 4. Care Continuity Tasks
    # --------------------------------------------------------------------------

    def test_06_care_continuity_task_lifecycle(self):
        task = self.engine.create_continuity_task(
            organization_id=self.org_id,
            patient_id=self.patient_id,
            task_type="FOLLOW_UP_CALL",
            due_date="2026-10-20",
            assigned_role="CARE_COORDINATOR",
            user_ctx=self.user_ctx
        )
        self.assertTrue(task["task_id"].startswith("tsk-"))
        self.assertEqual(task["status"], "PENDING")

        # Record contact attempt
        attempt = self.engine.record_contact_attempt(
            task_id=task["task_id"],
            outcome_notes="Patient called, phone rang no answer.",
            user_ctx=self.user_ctx,
            status="IN_PROGRESS"
        )
        self.assertEqual(attempt["contact_attempts_count"], 1)
        self.assertEqual(attempt["status"], "IN_PROGRESS")

        # Complete task
        completed = self.engine.complete_continuity_task(
            task_id=task["task_id"],
            outcome_notes="Followed up successfully, patient reports headache improved.",
            user_ctx=self.user_ctx
        )
        self.assertEqual(completed["status"], "COMPLETED")

    # --------------------------------------------------------------------------
    # 5. Traceable Timeline Summaries
    # --------------------------------------------------------------------------

    def test_07_generate_and_review_timeline_summary(self):
        # Generate summary
        summary = self.engine.generate_timeline_summary(
            patient_id=self.patient_id,
            summary_type="LONGITUDINAL_OVERVIEW",
            user_ctx=self.user_ctx
        )
        self.assertTrue(summary["summary_id"].startswith("sum-"))
        self.assertEqual(summary["review_status"], "DRAFT")
        self.assertGreaterEqual(len(summary["event_claim_bindings"]), 1)

        # Verify claim binding integrity
        first_binding = summary["event_claim_bindings"][0]
        self.assertIn("claim_text", first_binding)
        self.assertIn("timeline_event_ids", first_binding)
        self.assertGreaterEqual(len(first_binding["timeline_event_ids"]), 1)

        # Clinician review
        reviewed = self.engine.review_timeline_summary(
            summary_id=summary["summary_id"],
            action="CLINICIAN_REVIEWED",
            user_ctx=self.user_ctx,
            review_notes="Verified against consultation notes."
        )
        self.assertEqual(reviewed["review_status"], "CLINICIAN_REVIEWED")


if __name__ == "__main__":
    unittest.main()

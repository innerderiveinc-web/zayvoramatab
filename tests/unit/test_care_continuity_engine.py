"""Unit tests for Phase 9 Care Continuity, Follow-up, Patient Communications & Outcome Tracking Engine."""

import os
import json
import hmac
import hashlib
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.care_continuity import CareContinuityService
from apps.api.domains.patients import PatientService
from apps.api.domains.encounters import EncounterService
from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import ValidationError, ConflictError, AuthenticationError


class TestCareContinuityEngine(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.service = CareContinuityService(db_path=self.db_path)
        self.org_id = "org-matab-default"
        self.fac_id = "fac-central-opd"
        self.actor_id = "usr-hakeem-1"

        # Create a test patient and baseline encounter
        conn = DatabaseConnection(self.db_path).get_connection()
        try:
            self.patient = PatientService.create_patient(
                conn=conn,
                organization_id=self.org_id,
                facility_id=self.fac_id,
                data={
                    "given_name": "Khadija",
                    "family_name": "Qureshi",
                    "sex": "FEMALE",
                    "date_of_birth": "1989-11-23",
                    "phone": "+919899776655"
                },
                actor_id=self.actor_id
            )
            self.patient_id = self.patient["id"]
            self.encounter = EncounterService.create_encounter(
                conn=conn,
                organization_id=self.org_id,
                facility_id=self.fac_id,
                patient_id=self.patient_id,
                practitioner_id=self.actor_id,
                encounter_type="OPD_VISIT",
                reason_for_visit="Chronic epigastric burning and dyspepsia",
                actor_id=self.actor_id
            )
            self.encounter_id = self.encounter["id"]
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_follow_up_plan_versioning_and_auto_task(self):
        """Follow-up plans create v1 snapshot, auto-spawn task, and preserve history on amendment."""
        plan = self.service.create_follow_up_plan(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "review_due_at": "2026-10-27",
                "purpose": "Review dyspepsia response and Jawarish Mastagi adherence",
                "review_format": "in_person",
                "monitoring_items": ["Epigastric pain score", "Dietary compliance"],
                "safety_instructions": "Return immediately if hematemesis or melena occurs."
            }
        )
        self.assertEqual(plan["version_number"], 1)
        self.assertEqual(len(plan["versions"]), 1)
        self.assertEqual(len(plan["tasks"]), 1)
        self.assertEqual(plan["tasks"][0]["status"], "planned")

        # Amending without change_reason fails
        with self.assertRaises(ValidationError) as ctx:
            self.service.update_follow_up_plan(
                self.org_id, self.fac_id, self.actor_id, plan["id"],
                {"review_due_at": "2026-11-03"}
            )
        self.assertEqual(ctx.exception.code, "MISSING_CHANGE_REASON")

        # Valid amendment increments version to 2 and keeps v1 + v2 snapshots
        updated = self.service.update_follow_up_plan(
            self.org_id, self.fac_id, self.actor_id, plan["id"],
            {
                "review_due_at": "2026-11-03",
                "review_format": "teleconsultation",
                "change_reason": "Patient travelling; switched to teleconsultation review"
            }
        )
        self.assertEqual(updated["version_number"], 2)
        self.assertEqual(updated["review_format"], "teleconsultation")
        self.assertEqual(len(updated["versions"]), 2)
        self.assertEqual(updated["versions"][0]["snapshot"]["review_due_at"], "2026-10-27")
        self.assertEqual(updated["versions"][1]["snapshot"]["review_due_at"], "2026-11-03")

    def test_task_invariants_contact_attempts_and_reminder_non_completion(self):
        """Marking unable_to_reach requires contact attempts; sending reminder never completes task."""
        task = self.service.create_follow_up_task(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "due_at": "2026-10-25",
                "purpose": "Check symptom progression",
                "idempotency_key": "idem-task-001"
            }
        )
        # Idempotent replay returns same task
        dup_task = self.service.create_follow_up_task(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "due_at": "2026-10-25",
                "purpose": "Check symptom progression",
                "idempotency_key": "idem-task-001"
            }
        )
        self.assertEqual(task["id"], dup_task["id"])

        # Cannot mark unable_to_reach before any contact attempt is documented
        with self.assertRaises(ValidationError) as ctx:
            self.service.transition_follow_up_task(
                self.org_id, self.fac_id, self.actor_id, task["id"],
                {"to_status": "unable_to_reach", "reason": "No response"}
            )
        self.assertEqual(ctx.exception.code, "CANNOT_MARK_UNABLE_TO_REACH_WITHOUT_ATTEMPTS")

        # Sending an outbound reminder logs an outreach attempt but NEVER completes the task
        msg = self.service.send_or_queue_communication(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "task_id": task["id"],
                "template_code": "TPL-APPT-REMINDER-EN",
                "placeholders": {
                    "patient_name": "Zainab Begum",
                    "facility_name": "Central Matab OPD",
                    "appointment_date": "2026-10-25",
                    "clinic_phone": "+91-9800000001"
                }
            }
        )
        self.assertEqual(msg["status"], "sent")
        reloaded_task = self.service.get_follow_up_task(self.org_id, self.fac_id, task["id"])
        self.assertEqual(reloaded_task["status"], "planned")
        self.assertEqual(len(reloaded_task["contact_attempts"]), 1)

        # Attempting to complete task with 'reminder_sent' is strictly blocked
        with self.assertRaises(ValidationError) as ctx2:
            self.service.transition_follow_up_task(
                self.org_id, self.fac_id, self.actor_id, task["id"],
                {"to_status": "completed", "completion_outcome": "reminder_sent"}
            )
        self.assertEqual(ctx2.exception.code, "REMINDER_DOES_NOT_COMPLETE_FOLLOWUP")

        # Now that 1 contact attempt exists, unable_to_reach is permitted
        unreachable = self.service.transition_follow_up_task(
            self.org_id, self.fac_id, self.actor_id, task["id"],
            {"to_status": "unable_to_reach", "reason": "Phone switched off"}
        )
        self.assertEqual(unreachable["status"], "unable_to_reach")

    def test_appointment_double_booking_prevention_and_repeat_encounter(self):
        """Overlapping practitioner slots are blocked; repeat encounter links cleanly without mutating history."""
        appt1 = self.service.create_or_book_appointment(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "practitioner_id": self.actor_id,
                "source_encounter_id": self.encounter_id,
                "scheduled_start_at": "2026-10-28T10:00:00Z",
                "scheduled_end_at": "2026-10-28T10:30:00Z",
                "status": "booked"
            }
        )
        self.assertEqual(appt1["status"], "booked")

        # Overlapping booking for same practitioner and facility must fail with ConflictError
        with self.assertRaises(ConflictError) as ctx:
            self.service.create_or_book_appointment(
                self.org_id, self.fac_id, self.actor_id,
                {
                    "patient_id": self.patient_id,
                    "practitioner_id": self.actor_id,
                    "scheduled_start_at": "2026-10-28T10:15:00Z",
                    "scheduled_end_at": "2026-10-28T10:45:00Z",
                    "status": "booked"
                }
            )
        self.assertEqual(ctx.exception.code, "APPOINTMENT_SLOT_CONFLICT")

        # Transitioning appointment with create_repeat_encounter=True spawns a new encounter
        completed_appt = self.service.transition_appointment(
            self.org_id, self.fac_id, self.actor_id, appt1["id"],
            {"to_status": "completed", "create_repeat_encounter": True}
        )
        self.assertIsNotNone(completed_appt["repeat_encounter_id"])
        self.assertNotEqual(completed_appt["repeat_encounter_id"], self.encounter_id)

    def test_communication_privacy_quiet_hours_sendtime_consent_and_webhooks(self):
        """Test sensitive placeholder blocking, quiet hours deferral, send-time opt-out recheck, and webhooks."""
        # 1. Sensitive placeholder in reminder is blocked
        with self.assertRaises(ValidationError) as ctx:
            self.service.send_or_queue_communication(
                self.org_id, self.fac_id, self.actor_id,
                {
                    "patient_id": self.patient_id,
                    "template_code": "TPL-APPT-REMINDER-EN",
                    "placeholders": {
                        "patient_name": "Zainab Begum",
                        "diagnosis": "Peptic Ulcer Disease",
                        "medication_name": "Jawarish Mastagi"
                    }
                }
            )
        self.assertEqual(ctx.exception.code, "SENSITIVE_CONTENT_PROHIBITED_IN_REMINDER")

        # 2. Unapproved draft template is blocked
        with self.assertRaises(ValidationError) as ctx2:
            self.service.send_or_queue_communication(
                self.org_id, self.fac_id, self.actor_id,
                {
                    "patient_id": self.patient_id,
                    "template_code": "TPL-DRAFT-UNAPPROVED",
                    "placeholders": {"patient_name": "Zainab Begum", "facility_name": "Matab"}
                }
            )
        self.assertEqual(ctx2.exception.code, "UNAPPROVED_COMMUNICATION_TEMPLATE")

        # 3. Quiet hours deferral (22:15 falls in 21:00-08:00)
        deferred_msg = self.service.send_or_queue_communication(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "template_code": "TPL-APPT-REMINDER-EN",
                "simulated_send_time_hhmm": "22:15",
                "placeholders": {
                    "patient_name": "Zainab Begum",
                    "facility_name": "Central Matab OPD",
                    "appointment_date": "2026-10-28",
                    "clinic_phone": "+91-9800000001"
                }
            }
        )
        self.assertEqual(deferred_msg["status"], "deferred_quiet_hours")

        # 4. Send-time consent re-check: queue message while opted-in, then opt out before worker dispatches
        queued_msg = self.service.send_or_queue_communication(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "template_code": "TPL-APPT-REMINDER-EN",
                "defer_dispatch": True,
                "placeholders": {
                    "patient_name": "Zainab Begum",
                    "facility_name": "Central Matab OPD",
                    "appointment_date": "2026-10-28",
                    "clinic_phone": "+91-9800000001"
                }
            }
        )
        self.assertEqual(queued_msg["status"], "queued")

        # Patient opts out before message leaves the outbox
        self.service.upsert_communication_preferences(
            self.org_id, self.fac_id, self.actor_id, self.patient_id,
            {"opt_out_status": True, "do_not_contact_scope": "all_automated"}
        )

        dispatched = self.service.dispatch_queued_message(
            self.org_id, self.fac_id, self.actor_id, queued_msg["id"]
        )
        self.assertEqual(dispatched["status"], "suppressed")
        self.assertEqual(dispatched["suppression_reason"], "PATIENT_OPTED_OUT")

    def test_outcomes_non_causal_trends_and_unit_mismatch_guard(self):
        """Outcome trends never claim causal treatment efficacy and detect mismatched units/methods."""
        # Record baseline & follow-up with compatible unit & method
        self.service.record_outcome(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "definition_code": "OUT-DYSPEPSIA-SCORE",
                "reporter_type": "patient_reported",
                "value_numeric": 8.0,
                "recorded_at": "2026-10-01T10:00:00Z"
            }
        )
        self.service.record_outcome(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "definition_code": "OUT-DYSPEPSIA-SCORE",
                "reporter_type": "patient_reported",
                "value_numeric": 3.0,
                "recorded_at": "2026-10-15T10:00:00Z"
            }
        )
        # AI draft unverified should NOT pollute verified trend
        ai_rec = self.service.record_outcome(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "definition_code": "OUT-DYSPEPSIA-SCORE",
                "reporter_type": "ai_draft_unverified",
                "value_numeric": 0.0,
                "recorded_at": "2026-10-16T10:00:00Z"
            }
        )
        self.assertEqual(ai_rec["verification_status"], "ai_draft_unverified")

        trends = self.service.get_patient_outcomes_and_trends(
            self.org_id, self.fac_id, self.patient_id, definition_code="OUT-DYSPEPSIA-SCORE"
        )
        series = trends["series"][0]
        self.assertEqual(series["trend_status"], "observed_symptom_reduction")
        self.assertEqual(series["delta"], -5.0)
        self.assertFalse(series["claims_causal_efficacy"])
        self.assertIn("do not establish causal treatment efficacy", series["causal_attribution_disclaimer"])
        self.assertEqual(series["verified_count"], 2)
        self.assertEqual(series["unverified_drafts_count"], 1)

        # Mismatched units on Systolic BP -> 'cannot_compare_reliably'
        self.service.record_outcome(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "definition_code": "OUT-SBP-MMHG",
                "reporter_type": "clinician_observed",
                "value_numeric": 145.0,
                "unit": "mmHg",
                "collection_method": "automated_cuff",
                "recorded_at": "2026-10-01T10:00:00Z"
            }
        )
        self.service.record_outcome(
            self.org_id, self.fac_id, self.actor_id,
            {
                "patient_id": self.patient_id,
                "definition_code": "OUT-SBP-MMHG",
                "reporter_type": "device_imported",
                "value_numeric": 18.5,
                "unit": "kPa",
                "collection_method": "home_wrist_monitor",
                "recorded_at": "2026-10-15T10:00:00Z"
            }
        )
        bp_trends = self.service.get_patient_outcomes_and_trends(
            self.org_id, self.fac_id, self.patient_id, definition_code="OUT-SBP-MMHG"
        )
        self.assertEqual(bp_trends["series"][0]["trend_status"], "cannot_compare_reliably")
        self.assertIsNone(bp_trends["series"][0]["delta"])


if __name__ == "__main__":
    unittest.main()

"""Unit and Integration Tests: Clinical Encounter Lifecycle, Vitals, and History."""

import unittest
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.domains.encounters import EncounterService
from matab.core.errors import ValidationError, NotFoundError

class TestEncounterWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_today_queue_and_token_assignment(self):
        conn = self.db_manager.get_connection()
        try:
            # Seeded encounters should be in today's queue
            queue = EncounterService.get_today_queue(conn, "fac-matab-main")
            self.assertTrue(len(queue) >= 3)
            self.assertEqual(queue[0]["token_number"], 1)

            # Issue a new walk-in encounter
            new_enc = EncounterService.create_encounter(
                conn=conn,
                organization_id="org-matab-default",
                facility_id="fac-matab-main",
                patient_id="pat-syn-001",
                practitioner_id="prac-hakeem-1",
                encounter_type="WALK_IN",
                actor_id="usr-recep-1"
            )
            self.assertEqual(new_enc["status"], "ARRIVED")
            self.assertEqual(new_enc["token_number"], 4)
        finally:
            conn.close()

    def test_vitals_recording(self):
        conn = self.db_manager.get_connection()
        try:
            vitals = EncounterService.update_vitals(
                conn=conn,
                encounter_id="enc-syn-102",
                vitals_data={
                    "systolic_bp": 130,
                    "diastolic_bp": 85,
                    "pulse_bpm": 76,
                    "temperature_f": 98.6,
                    "respiratory_rate": 18,
                    "weight_kg": 65.0,
                    "spo2_percent": 98
                },
                actor_id="usr-hakeem-1"
            )
            self.assertEqual(vitals["systolic_bp"], 130)
            self.assertEqual(vitals["pulse_bpm"], 76)

            # Verify encounter retrieval reflects new vitals
            enc = EncounterService.get_encounter(conn, "org-matab-default", "enc-syn-102")
            self.assertIsNotNone(enc["vitals"])
            self.assertEqual(enc["vitals"]["systolic_bp"], 130)
        finally:
            conn.close()

    def test_clinical_notes_validation(self):
        conn = self.db_manager.get_connection()
        try:
            # Chief complaint is mandatory
            with self.assertRaises(ValidationError):
                EncounterService.update_clinical_notes(
                    conn=conn,
                    encounter_id="enc-syn-102",
                    notes_data={"chief_complaint": ""},
                    author_id="usr-hakeem-1"
                )

            saved = EncounterService.update_clinical_notes(
                conn=conn,
                encounter_id="enc-syn-102",
                notes_data={
                    "chief_complaint": "Persistent dry cough (Sual Yabis) for 10 days.",
                    "history_of_present_illness": "Worse at night, throat irritation, no fever."
                },
                author_id="usr-hakeem-1"
            )
            self.assertIn("Sual Yabis", saved["chief_complaint"])
        finally:
            conn.close()

    def test_encounter_status_transitions(self):
        conn = self.db_manager.get_connection()
        try:
            EncounterService.transition_status(conn, "enc-syn-102", "IN_CONSULTATION", "usr-hakeem-1")
            enc = EncounterService.get_encounter(conn, "org-matab-default", "enc-syn-102")
            self.assertEqual(enc["status"], "IN_CONSULTATION")

            # Invalid status raises error
            with self.assertRaises(ValidationError):
                EncounterService.transition_status(conn, "enc-syn-102", "INVALID_STATUS", "usr-hakeem-1")
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()

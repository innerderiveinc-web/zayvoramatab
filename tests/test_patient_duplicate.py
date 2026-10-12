"""Unit and Integration Tests: Master Patient Index and Duplicate Resolution."""

import unittest
import os
import tempfile
from matab.database.connection import DatabaseConnection
from matab.database.migrator import run_migrations
from matab.domains.patients import PatientService
from matab.core.errors import ConflictError, ValidationError

class TestPatientDuplicate(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        self.db_manager = DatabaseConnection(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_patient_creation_and_mrn_generation(self):
        conn = self.db_manager.get_connection()
        try:
            patient = PatientService.create_patient(
                conn=conn,
                organization_id="org-matab-default",
                data={
                    "first_name": "Tahir",
                    "last_name": "Mahmood",
                    "phone": "+91-9871122334",
                    "gender": "MALE",
                    "dob": "1992-05-18",
                    "blood_group": "B+",
                    "allergies": [
                        {"allergen_type": "HERBAL", "allergen_name": "Roghan Badam", "severity": "SEVERE"}
                    ]
                },
                actor_id="usr-hakeem-1"
            )
            self.assertIn("mrn", patient)
            self.assertTrue(patient["mrn"].startswith("MRN-"))
            self.assertEqual(patient["first_name"], "Tahir")
            self.assertEqual(len(patient["allergies"]), 1)
            self.assertEqual(patient["allergies"][0]["allergen_name"], "Roghan Badam")
        finally:
            conn.close()

    def test_duplicate_prevention_on_matching_phone(self):
        conn = self.db_manager.get_connection()
        try:
            # Seed initial patient
            PatientService.create_patient(
                conn=conn,
                organization_id="org-matab-default",
                data={"first_name": "Rashid", "phone": "+91-9988776655", "gender": "MALE"},
                actor_id="usr-hakeem-1"
            )

            # Attempt to register another patient with the same phone without override
            with self.assertRaises(ConflictError):
                PatientService.create_patient(
                    conn=conn,
                    organization_id="org-matab-default",
                    data={"first_name": "Rashid", "phone": "+91-9988776655", "gender": "MALE"},
                    actor_id="usr-hakeem-1"
                )

            # Registration succeeds when explicit override is provided
            overridden = PatientService.create_patient(
                conn=conn,
                organization_id="org-matab-default",
                data={"first_name": "Rashid Jr", "phone": "+91-9988776655", "gender": "MALE"},
                actor_id="usr-hakeem-1",
                force_duplicate_override=True
            )
            self.assertIsNotNone(overridden["id"])
        finally:
            conn.close()

    def test_patient_360_retrieval(self):
        conn = self.db_manager.get_connection()
        try:
            # Query existing seeded synthetic patient
            p360 = PatientService.get_patient_360(conn, "org-matab-default", "pat-syn-001")
            self.assertEqual(p360["first_name"], "[SYNTHETIC] Ahmad")
            self.assertTrue(len(p360["allergies"]) > 0)
            self.assertTrue(len(p360["encounters"]) > 0)
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()

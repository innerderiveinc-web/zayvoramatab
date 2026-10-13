"""Unit Tests for Phase 12 Hospital Workflows & Interoperability Domain Engine."""

import os
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.hospital_interop import HospitalInteropService
from apps.api.core.errors import ConflictError, ValidationError, NotFoundError


class TestHospitalInteropEngine(unittest.TestCase):
    """Domain unit tests for IPD/ADT, Bed Concurrency Lock, Lab, Referrals, FHIR R4 & ABDM Harness."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.svc = HospitalInteropService(db_path=self.db_path)
        self.org_id = "org-matab-default"
        self.fac_id = "fac-central-opd"
        self.admin_id = "usr-admin-1"
        self.hakeem_id = "usr-hakeem-1"
        self.patient_id = "pat-syn-001"
        self.encounter_id = "enc-syn-001"

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_bed_ward_creation_and_concurrency_lock(self):
        """Bed active_stay_lock enforces that a bed cannot be double-assigned to two concurrent admissions."""
        # Create new ward
        ward = self.svc.create_ward(
            self.org_id, self.fac_id, self.admin_id,
            {"code": "ICU-W1", "name": "Intensive Care Unit", "ward_type": "HIGH_DEPENDENCY_UNIT"}
        )
        self.assertEqual(ward["code"], "ICU-W1")

        # Create new bed
        bed = self.svc.create_bed(
            self.org_id, self.fac_id, self.admin_id,
            {"ward_id": ward["id"], "bed_code": "ICU-B1", "room_number": "101", "bed_category": "HDU"}
        )
        self.assertEqual(bed["bed_code"], "ICU-B1")
        self.assertEqual(bed["operational_status"], "available")

        # Create two real admission requests
        adm1 = self.svc.create_admission_request(
            self.org_id, self.fac_id, self.hakeem_id,
            {"patient_id": "pat-syn-001", "reason_for_admission": "Stay 1", "urgency": "ROUTINE"}
        )
        adm2 = self.svc.create_admission_request(
            self.org_id, self.fac_id, self.hakeem_id,
            {"patient_id": "pat-syn-002", "reason_for_admission": "Stay 2", "urgency": "ROUTINE"}
        )

        # Assign bed to adm1
        self.svc.assign_bed(self.org_id, self.fac_id, bed["id"], adm1["id"], "pat-syn-001", self.admin_id)
        updated_bed = self.svc.get_bed(self.org_id, self.fac_id, bed["id"])
        self.assertEqual(updated_bed["operational_status"], "occupied")
        self.assertIn("stay:", updated_bed["active_stay_lock"])

        # Concurrency test: Attempting to assign the same bed to adm2 MUST fail with ConflictError
        with self.assertRaises(ConflictError):
            self.svc.assign_bed(self.org_id, self.fac_id, bed["id"], adm2["id"], "pat-syn-002", self.admin_id)

        # Release bed to cleaning
        self.svc.release_bed(self.org_id, self.fac_id, bed["id"], self.admin_id, next_status="cleaning")
        cleaned_bed = self.svc.get_bed(self.org_id, self.fac_id, bed["id"])
        self.assertEqual(cleaned_bed["operational_status"], "cleaning")
        self.assertIsNone(cleaned_bed["active_stay_lock"])

    def test_inpatient_adt_lifecycle_and_handover(self):
        """Inpatient ADT lifecycle: request -> await bed -> admit (new encounter) -> transfer with handover."""
        # 1. Request Admission
        adm = self.svc.create_admission_request(
            self.org_id, self.fac_id, self.hakeem_id,
            {
                "patient_id": self.patient_id,
                "reason_for_admission": "Severe Soo-e-Mizaj requiring intensive Munzij-Mushil regimenal therapy",
                "urgency": "URGENT",
                "admission_type": "REGIMENAL_INPATIENT",
            }
        )
        self.assertEqual(adm["status"], "requested")

        # Duplicate admission request for same patient while stay active MUST fail
        with self.assertRaises(ConflictError):
            self.svc.create_admission_request(
                self.org_id, self.fac_id, self.hakeem_id,
                {"patient_id": self.patient_id, "reason_for_admission": "Duplicate admission"}
            )

        # 2. Accept Admission
        accepted = self.svc.accept_admission(self.org_id, self.fac_id, adm["id"], self.hakeem_id)
        self.assertEqual(accepted["status"], "awaiting_bed")

        # 3. Admit Patient to Bed MOA-101A
        admitted = self.svc.admit_patient(self.org_id, self.fac_id, adm["id"], "bed-moa-101a", self.hakeem_id)
        self.assertEqual(admitted["status"], "admitted")
        self.assertEqual(admitted["assigned_bed_id"], "bed-moa-101a")
        self.assertIsNotNone(admitted["inpatient_encounter_id"])

        # Verify bed is occupied
        bed = self.svc.get_bed(self.org_id, self.fac_id, "bed-moa-101a")
        self.assertEqual(bed["operational_status"], "occupied")

        # 4. Transfer Patient to Bed MOA-101B with Handover
        transferred = self.svc.transfer_inpatient(
            self.org_id, self.fac_id, adm["id"], "bed-moa-101b", self.hakeem_id,
            {
                "from_team_or_shift": "Morning Shift Team",
                "to_team_or_shift": "Evening Shift Team",
                "handover_summary": "Patient completed first decoction course without distress. Vitals stable.",
                "reason": "Step-down observation relocation"
            }
        )
        self.assertEqual(transferred["assigned_bed_id"], "bed-moa-101b")

        # Old bed should now be in cleaning
        old_bed = self.svc.get_bed(self.org_id, self.fac_id, "bed-moa-101a")
        self.assertEqual(old_bed["operational_status"], "cleaning")

        # New bed should be occupied
        new_bed = self.svc.get_bed(self.org_id, self.fac_id, "bed-moa-101b")
        self.assertEqual(new_bed["operational_status"], "occupied")

    def test_discharge_summary_and_cryptographic_signing(self):
        """Discharge checklist must be complete and cryptographically signed before discharge is finalized."""
        patient_id = "pat-syn-003"

        # Create and admit patient
        adm = self.svc.create_admission_request(
            self.org_id, self.fac_id, self.hakeem_id,
            {"patient_id": patient_id, "reason_for_admission": "Asthma exacerbation (Deeq-un-Nafas)", "urgency": "ROUTINE"}
        )
        self.svc.accept_admission(self.org_id, self.fac_id, adm["id"], self.hakeem_id)
        self.svc.admit_patient(self.org_id, self.fac_id, adm["id"], "bed-obs-201a", self.hakeem_id)

        # Attempt discharge without discharge summary MUST fail
        with self.assertRaises(ConflictError):
            self.svc.discharge_patient(self.org_id, self.fac_id, adm["id"], self.hakeem_id, {"discharge_type": "REGULAR_DISCHARGE"})

        # Create incomplete discharge summary (missing mandatory return_precautions)
        ds = self.svc.create_or_update_discharge_summary(
            self.org_id, self.fac_id, adm["id"], self.hakeem_id,
            {
                "course_in_hospital": "Patient responded favorably to Sharbat Zoofa and steam inhalation.",
                "follow_up_plan_summary": "Follow-up in OPD after 7 days.",
                "return_precautions": ""  # Incomplete
            }
        )
        self.assertEqual(ds["checklist_completed"], 0)

        # Attempting to sign incomplete summary MUST fail with ConflictError (incomplete checklist)
        with self.assertRaises(ConflictError):
            self.svc.sign_discharge_summary(self.org_id, self.fac_id, adm["id"], self.hakeem_id, clinician_pin="1234")

        # Complete the mandatory sections
        ds = self.svc.create_or_update_discharge_summary(
            self.org_id, self.fac_id, adm["id"], self.hakeem_id,
            {
                "course_in_hospital": "Patient responded favorably to Sharbat Zoofa and steam inhalation.",
                "follow_up_plan_summary": "Follow-up in OPD after 7 days.",
                "return_precautions": "Seek emergency care immediately if shortness of breath recurs with cyanosis."
            }
        )
        self.assertEqual(ds["checklist_completed"], 1)

        # Clinician signs with valid PIN
        signed_ds = self.svc.sign_discharge_summary(self.org_id, self.fac_id, adm["id"], self.hakeem_id, clinician_pin="1234")
        self.assertEqual(signed_ds["status"], "signed")
        self.assertEqual(signed_ds["signed_by"], self.hakeem_id)
        self.assertIsNotNone(signed_ds["signature_hash"])
        self.assertEqual(len(signed_ds["signature_hash"]), 64)  # SHA-256 hex string

        # Finalize Discharge
        discharged_adm = self.svc.discharge_patient(
            self.org_id, self.fac_id, adm["id"], self.hakeem_id,
            {"discharge_type": "REGULAR_DISCHARGE", "discharge_destination": "HOME"}
        )
        self.assertEqual(discharged_adm["status"], "discharged")
        self.assertIsNotNone(discharged_adm["discharged_at"])

        # Bed should be released to cleaning
        bed = self.svc.get_bed(self.org_id, self.fac_id, "bed-obs-201a")
        self.assertEqual(bed["operational_status"], "cleaning")

    def test_laboratory_orders_critical_values_and_amendments(self):
        """Laboratory order lifecycle, specimen tracking, and critical value threshold alerts."""
        # 1. Create Lab Order for Serum Potassium
        order = self.svc.create_lab_order(
            self.org_id, self.fac_id, self.hakeem_id,
            {
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "priority": "STAT",
                "clinical_indication": "Suspected electrolyte imbalance post diarrhea",
                "tests": [{"test_code": "LAB-K", "test_name": "Serum Potassium (K+)", "loinc_code": "2823-3"}],
            }
        )
        self.assertEqual(order["status"], "ordered")
        self.assertTrue(order["order_number"].startswith("LAB-"))

        # 2. Collect Specimen
        col = self.svc.collect_specimen(
            self.org_id, self.fac_id, order["id"], self.hakeem_id,
            {"specimen_type": "VENOUS_BLOOD", "container_type": "SST_GOLD"}
        )
        self.assertEqual(col["status"], "collected")
        self.assertEqual(len(col["specimens"]), 1)

        # 3. Enter Lab Result: Normal Value
        res_normal = self.svc.import_or_enter_lab_result(
            self.org_id, self.fac_id, self.hakeem_id,
            {
                "order_id": order["id"],
                "patient_id": self.patient_id,
                "test_code": "LAB-K",
                "test_name": "Serum Potassium (K+)",
                "result_value": "4.2",
                "unit": "mmol/L",
                "performing_lab_name": "Central Diagnostic Lab",
            }
        )
        self.assertEqual(res_normal["abnormal_flag"], "NORMAL")
        self.assertEqual(res_normal["is_critical"], 0)

        # 4. Enter Lab Result: Critical Low Value (< 2.8)
        res_critical = self.svc.import_or_enter_lab_result(
            self.org_id, self.fac_id, self.hakeem_id,
            {
                "order_id": order["id"],
                "patient_id": self.patient_id,
                "test_code": "LAB-K",
                "test_name": "Serum Potassium (K+)",
                "result_value": "2.4",
                "unit": "mmol/L",
                "performing_lab_name": "Central Diagnostic Lab",
            }
        )
        self.assertEqual(res_critical["abnormal_flag"], "CRITICAL_LOW")
        self.assertEqual(res_critical["is_critical"], 1)

    def test_structured_referral_state_machine(self):
        """Structured referrals enforce sent != accepted != completed state transitions."""
        # Create Referral
        ref = self.svc.create_referral(
            self.org_id, self.fac_id, self.hakeem_id,
            {
                "patient_id": self.patient_id,
                "source_encounter_id": self.encounter_id,
                "referral_type": "INTER_BRANCH_REFERRAL",
                "receiving_facility_id": "fac-south-branch",
                "priority": "ROUTINE",
                "reason_for_referral": "Specialized Hijama cupping evaluation",
                "clinical_question": "Is wet cupping recommended for chronic lumbago given mildly elevated BP?",
                "clinical_summary": "Patient has 3-month history of lower back pain unresponsive to oral habb.",
            }
        )
        self.assertEqual(ref["status"], "sent")
        self.assertIsNotNone(ref["sent_at"])

        # Accepting referral transitions from sent to accepted
        accepted_ref = self.svc.transition_referral(
            self.org_id, ref["id"], "accept", self.hakeem_id
        )
        self.assertEqual(accepted_ref["status"], "accepted")
        self.assertIsNotNone(accepted_ref["accepted_at"])

        # Closing referral with consultation report
        closed_ref = self.svc.transition_referral(
            self.org_id, ref["id"], "close", self.hakeem_id,
            {
                "consultation_response_report": "Hijama bil Shart performed over lumbar points with 50ml dark blood evacuated. Pain relieved.",
                "closure_outcome": "Completed successfully; follow-up scheduled."
            }
        )
        self.assertEqual(closed_ref["status"], "completed")
        self.assertIsNotNone(closed_ref["completed_at"])

    def test_fhir_r4_validator_and_bundle_export(self):
        """FHIR R4 resource validator and provider-independent bundle generator."""
        # Validate valid FHIR Patient resource
        valid_patient = {
            "resourceType": "Patient",
            "id": self.patient_id,
            "name": [{"text": "Synthetic Patient One"}],
            "gender": "male"
        }
        val = self.svc.validate_fhir_resource(self.org_id, self.admin_id, {"resource": valid_patient})
        self.assertTrue(val["is_valid"])
        self.assertEqual(len(val["issues"]), 0)

        # Validate invalid FHIR resource (missing resourceType)
        invalid_res = {"id": "123"}
        val_bad = self.svc.validate_fhir_resource(self.org_id, self.admin_id, {"resource": invalid_res})
        self.assertFalse(val_bad["is_valid"])

        # Export FHIR Bundle
        res = self.svc.export_fhir_bundle(
            self.org_id, self.fac_id, self.hakeem_id, {"patient_id": self.patient_id, "hi_type": "OPConsultation"}
        )
        bundle = res["bundle"]
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "document")
        self.assertGreaterEqual(len(bundle["entry"]), 2)  # Composition + Patient

    def test_abdm_harness_request_trace_and_idempotency(self):
        """ABDM harness returns CONTRACT_TESTED_HARNESS and is idempotent on requestId."""
        req_payload = {
            "requestId": "req-harness-unit-1",
            "data_push_url": "https://dev.abdm.gov.in/data/receive",
            "hip_id": "IN070001",
            "hiu_id": "IN070002",
            "consent_artifact_id": "cst-abdm-valid-1",
        }

        # Process first time
        resp1 = self.svc.process_abdm_harness_request(self.org_id, self.fac_id, self.admin_id, req_payload)
        self.assertEqual(resp1["status"], "SUCCESS_HARNESS_VERIFIED")
        self.assertEqual(resp1["readiness_mode"], "CONTRACT_TEST_HARNESS")

        # Idempotent re-execution with same requestId returns identical result
        resp2 = self.svc.process_abdm_harness_request(self.org_id, self.fac_id, self.admin_id, req_payload)
        self.assertEqual(resp2["request_id"], resp1["request_id"])
        self.assertTrue(resp2.get("idempotent_replay"))


if __name__ == "__main__":
    unittest.main()

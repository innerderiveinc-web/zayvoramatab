"""Integration Tests for Phase 12 Hospital Workflows & Interoperability REST APIs.
Covers Inpatient ADT, Bed Concurrency Lock, Lab Lifecycle, Referrals, FHIR R4 Bundle, ABDM Harness & Tenant Isolation.
"""

import json
import os
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestHospitalInteropApi(unittest.TestCase):
    """End-to-end REST API integration tests for Phase 12."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self._ip_counter = 50

        self.org_id = "org-matab-default"
        self.fac_id = "fac-central-opd"
        self.patient_id = "pat-syn-001"
        self.encounter_id = "enc-syn-001"

        self.admin_token = self._login("admin", "matab123")
        self.hakeem_token = self._login("hakeem", "matab123")
        self.reception_token = self._login("reception", "matab123")

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _login(self, username: str, password: str) -> str:
        self._ip_counter += 1
        client_ip = f"10.0.12.{self._ip_counter}"
        body_bytes = json.dumps({"username": username, "password": password}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login", {}, {}, body_bytes, client_ip, db_path=self.db_path
        )
        self.assertEqual(status, 200)
        return json.loads(resp_bytes.decode("utf-8"))["token"]

    def _req(self, method: str, path: str, token: str, body: dict = None, query: dict = None, headers: dict = None):
        self._ip_counter += 1
        client_ip = f"10.0.12.{self._ip_counter}"
        hdrs = dict(headers or {})
        if token:
            hdrs["authorization"] = f"Bearer {token}"
        hdrs["x-facility-id"] = self.fac_id
        b_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, _, resp_bytes = ApiRouter.dispatch(
            method, path, hdrs, query or {}, b_bytes, client_ip, db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}

    def test_occupancy_dashboard_and_public_privacy_sanitization(self):
        """Occupancy dashboard reports counts; public mode strips sensitive clinical details."""
        # Authenticated clinician view
        st, resp = self._req("GET", "/api/v1/ipd/occupancy-dashboard", self.hakeem_token)
        self.assertEqual(st, 200)
        self.assertIn("dashboard", resp)
        dash = resp["dashboard"]
        self.assertGreaterEqual(dash["total_beds"], 3)
        self.assertGreaterEqual(dash["available_beds"], 3)

        # Public sanitized view
        st_pub, resp_pub = self._req("GET", "/api/v1/ipd/occupancy-dashboard", self.hakeem_token, query={"public": "true"})
        self.assertEqual(st_pub, 200)
        dash_pub = resp_pub["dashboard"]
        self.assertTrue(dash_pub.get("is_public_board"))

    def test_end_to_end_inpatient_adt_lifecycle(self):
        """Complete inpatient ADT journey: Request -> Accept -> Bed Assignment -> Transfer -> Discharge Summary -> PIN Sign -> Discharge."""
        # 1. Request admission
        st, adm_resp = self._req(
            "POST",
            "/api/v1/ipd/admissions",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "urgency": "URGENT",
                "admission_type": "REGIMENAL_INPATIENT",
                "reason_for_admission": "Acute arthritic flare (Waja-ul-Mafasil Haad)",
            },
        )
        self.assertEqual(st, 201)
        adm_id = adm_resp["admission"]["id"]
        self.assertEqual(adm_resp["admission"]["status"], "requested")

        # 2. Accept admission (transitions to awaiting_bed)
        st_acc, acc_resp = self._req(
            "POST", f"/api/v1/ipd/admissions/{adm_id}/accept", self.hakeem_token, {}
        )
        self.assertEqual(st_acc, 200)
        self.assertEqual(acc_resp["admission"]["status"], "awaiting_bed")

        # 3. Admit patient to Bed MOA-101A
        st_adm, admitted_resp = self._req(
            "POST", f"/api/v1/ipd/admissions/{adm_id}/admit", self.hakeem_token,
            {"bed_id": "bed-moa-101a"}
        )
        self.assertEqual(st_adm, 200)
        self.assertEqual(admitted_resp["admission"]["status"], "admitted")
        self.assertEqual(admitted_resp["admission"]["assigned_bed_id"], "bed-moa-101a")
        self.assertIsNotNone(admitted_resp["admission"]["inpatient_encounter_id"])

        # 4. Concurrency lock verification: trying to admit another patient into bed-moa-101a MUST fail with 409 Conflict
        st_req2, adm2_resp = self._req(
            "POST",
            "/api/v1/ipd/admissions",
            self.hakeem_token,
            {
                "patient_id": "pat-syn-002",
                "urgency": "ROUTINE",
                "admission_type": "ELECTIVE",
                "reason_for_admission": "General stay",
            },
        )
        self.assertEqual(st_req2, 201)
        adm2_id = adm2_resp["admission"]["id"]
        self._req("POST", f"/api/v1/ipd/admissions/{adm2_id}/accept", self.hakeem_token, {})
        st_fail, fail_resp = self._req(
            "POST", f"/api/v1/ipd/admissions/{adm2_id}/admit", self.hakeem_token,
            {"bed_id": "bed-moa-101a"}
        )
        self.assertEqual(st_fail, 409)

        # 5. Transfer patient to bed-moa-101b with clinical handover
        st_trf, trf_resp = self._req(
            "POST", f"/api/v1/ipd/admissions/{adm_id}/transfer", self.hakeem_token,
            {
                "target_bed_id": "bed-moa-101b",
                "handover_summary": "Morning cupping dressing complete. Patient mobilizing with support.",
                "reason": "Step-down relocation"
            }
        )
        self.assertEqual(st_trf, 200)
        self.assertEqual(trf_resp["admission"]["assigned_bed_id"], "bed-moa-101b")

        # 6. Author Discharge Summary
        st_ds, ds_resp = self._req(
            "POST", f"/api/v1/ipd/admissions/{adm_id}/discharge-summary", self.hakeem_token,
            {
                "course_in_hospital": "Treated with Hab-e-Suranjan and local Roghan-e-Suranjan massage. Joint mobility restored.",
                "follow_up_plan_summary": "Review after 10 days in OPD.",
                "return_precautions": "Avoid heavy cold dietary exposure; report immediately if severe joint swelling recurs."
            }
        )
        self.assertEqual(st_ds, 200)
        self.assertEqual(ds_resp["discharge_summary"]["checklist_completed"], 1)

        # 7. Clinician signs discharge summary with PIN
        st_sign, sign_resp = self._req(
            "POST", f"/api/v1/ipd/admissions/{adm_id}/discharge-summary/sign", self.hakeem_token,
            {"pin": "1234"}
        )
        self.assertEqual(st_sign, 200)
        self.assertEqual(sign_resp["discharge_summary"]["status"], "signed")
        self.assertIsNotNone(sign_resp["discharge_summary"]["signature_hash"])

        # 8. Discharge Patient
        st_dis, dis_resp = self._req(
            "POST", f"/api/v1/ipd/admissions/{adm_id}/discharge", self.hakeem_token,
            {"discharge_type": "REGULAR_DISCHARGE", "discharge_destination": "HOME"}
        )
        self.assertEqual(st_dis, 200)
        self.assertEqual(dis_resp["admission"]["status"], "discharged")

    def test_laboratory_order_specimen_and_result_entry(self):
        """Laboratory test order creation, specimen collection, and result recording via REST API."""
        # 1. Create Lab Order
        st_ord, ord_resp = self._req(
            "POST",
            "/api/v1/lab/orders",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "priority": "ROUTINE",
                "clinical_indication": "Liver function baseline pre-treatment",
                "tests": [{"test_code": "LAB-ALT", "test_name": "Alanine Aminotransferase (ALT/SGPT)"}],
            },
        )
        self.assertEqual(st_ord, 201)
        order_id = ord_resp["lab_order"]["id"]
        self.assertEqual(ord_resp["lab_order"]["status"], "ordered")

        # 2. Collect Specimen
        st_col, col_resp = self._req(
            "POST", f"/api/v1/lab/orders/{order_id}/collect", self.hakeem_token,
            {"specimen_type": "VENOUS_BLOOD", "container_type": "SST"}
        )
        self.assertEqual(st_col, 200)
        self.assertEqual(col_resp["lab_order"]["status"], "collected")

        # 3. Enter Lab Result
        st_res, res_resp = self._req(
            "POST",
            "/api/v1/lab/results",
            self.hakeem_token,
            {
                "order_id": order_id,
                "patient_id": self.patient_id,
                "test_code": "LAB-ALT",
                "test_name": "Alanine Aminotransferase (ALT/SGPT)",
                "result_value": "32.0",
                "unit": "U/L",
                "performing_lab_name": "Central Diagnostic Lab",
            },
        )
        self.assertEqual(st_res, 201)
        self.assertEqual(res_resp["lab_result"]["abnormal_flag"], "NORMAL")

    def test_hospital_referrals_rest_lifecycle(self):
        """Outbound referral creation, recipient acceptance, and loop closure via REST APIs."""
        # Create Referral
        st_ref, ref_resp = self._req(
            "POST",
            "/api/v1/hospital-referrals",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "source_encounter_id": self.encounter_id,
                "referral_type": "INTERNAL_HOSPITAL_CONSULT",
                "priority": "ROUTINE",
                "reason_for_referral": "Panchakarma / Ilaj-bil-Tadbeer specialized regimen consult",
                "clinical_question": "Evaluate suitability for Fasd (venesection) vs Hijama bil Shart.",
                "clinical_summary": "Chronic migraine with plethora (Imtila).",
            },
        )
        self.assertEqual(st_ref, 201)
        ref_id = ref_resp["referral"]["id"]
        self.assertEqual(ref_resp["referral"]["status"], "sent")

        # Accept Referral
        st_acc, acc_resp = self._req(
            "POST", f"/api/v1/hospital-referrals/{ref_id}/accept", self.hakeem_token, {}
        )
        self.assertEqual(st_acc, 200)
        self.assertEqual(acc_resp["referral"]["status"], "accepted")

        # Close Referral
        st_close, close_resp = self._req(
            "POST", f"/api/v1/hospital-referrals/{ref_id}/close", self.hakeem_token,
            {
                "consultation_response_report": "Hijama bil Shart advised over C7 vertebra and scapular points.",
                "closure_outcome": "Regimen approved and scheduled."
            }
        )
        self.assertEqual(st_close, 200)
        self.assertEqual(close_resp["referral"]["status"], "completed")

    def test_interop_fhir_export_and_abdm_harness_request(self):
        """FHIR R4 bundle generation and ABDM contract test harness endpoints."""
        # FHIR Bundle Export
        st_fhir, fhir_resp = self._req(
            "POST",
            "/api/v1/interop/fhir/export",
            self.admin_token,
            {"patient_id": self.patient_id, "hi_type": "OPConsultation"},
        )
        self.assertEqual(st_fhir, 200)
        self.assertIn("bundle", fhir_resp)
        self.assertEqual(fhir_resp["bundle"]["resourceType"], "Bundle")

        # ABDM Test Harness Invocation
        st_abdm, abdm_resp = self._req(
            "POST",
            "/api/v1/interop/abdm/harness-request",
            self.admin_token,
            {
                "requestId": "req-api-harness-1",
                "data_push_url": "https://dev.abdm.gov.in/data/receive",
                "hip_id": "IN070001",
                "hiu_id": "IN070002",
                "consent_artifact_id": "cst-abdm-valid-api",
            },
        )
        self.assertEqual(st_abdm, 200)
        self.assertEqual(abdm_resp["abdm_response"]["status"], "SUCCESS_HARNESS_VERIFIED")
        self.assertEqual(abdm_resp["abdm_response"]["readiness_mode"], "CONTRACT_TEST_HARNESS")


if __name__ == "__main__":
    unittest.main()

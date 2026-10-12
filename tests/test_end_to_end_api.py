"""End-to-End API Integration Tests: Simulating Full Clinical Consultation Workflow."""

import unittest
import json
import os
import tempfile
from matab.database.migrator import run_migrations
from matab.api.router import ApiRouter

class TestEndToEndApi(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _call_api(self, method: str, path: str, token: str = None, body: dict = None, query: dict = None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body_bytes = json.dumps(body).encode("utf-8") if body else b""
        status, resp_headers, resp_bytes = ApiRouter.dispatch(
            method=method,
            path=path,
            headers=headers,
            query_params=query or {},
            body_bytes=body_bytes,
            client_ip="127.0.0.1",
            db_path=self.db_path
        )
        data = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
        return status, data

    def test_full_clinical_encounter_workflow_api(self):
        # 1. Health & Readiness Check
        status, health = self._call_api("GET", "/api/v1/system/health")
        self.assertEqual(status, 200)
        self.assertEqual(health["status"], "HEALTHY")

        # 2. Authenticate as Hakeem Tariq
        status, login_res = self._call_api("POST", "/api/v1/auth/login", body={"username": "hakeem", "password": "matab123"})
        self.assertEqual(status, 200)
        token = login_res["token"]
        self.assertIsNotNone(token)

        # 3. Fetch Today's Queue
        status, q_res = self._call_api("GET", "/api/v1/encounters/queue", token=token)
        self.assertEqual(status, 200)
        queue = q_res["queue"]
        self.assertTrue(len(queue) >= 2)
        target_enc = queue[1] # enc-syn-102 for pat-syn-002
        enc_id = target_enc["id"]
        patient_id = target_enc["patient_id"]

        # 4. Record Vitals
        vitals_payload = {
            "systolic_bp": 122,
            "diastolic_bp": 78,
            "pulse_bpm": 72,
            "temperature_f": 98.4,
            "respiratory_rate": 16,
            "weight_kg": 58.5,
            "spo2_percent": 99
        }
        status, vit_res = self._call_api("PUT", f"/api/v1/encounters/{enc_id}/vitals", token=token, body=vitals_payload)
        self.assertEqual(status, 200)
        self.assertEqual(vit_res["vitals"]["systolic_bp"], 122)

        # 5. Record Clinical Notes
        notes_payload = {
            "chief_complaint": "Dysuria (Usr-ul-Baul) and burning sensation for 3 days.",
            "history_of_present_illness": "Increased frequency of micturition, concentrated yellow urine, relieved by drinking water.",
            "past_medical_history": "No history of renal calculi."
        }
        status, note_res = self._call_api("PUT", f"/api/v1/encounters/{enc_id}/notes", token=token, body=notes_payload)
        self.assertEqual(status, 200)

        # 6. Submit Unani Assessment
        unani_payload = {
            "encounter_id": enc_id,
            "patient_id": patient_id,
            "dominant_mizaj": "SAFRAWI",
            "mizaj_secondary": "DAMWI",
            "su_e_mizaj_type": "SAADA",
            "nabz_quality": "SAREE",
            "baul_observations": "Deep yellow, hot on touch, slight turbidity",
            "clinical_interpretation": "Su-e-Mizaj Haar Safrawi affecting urinary tract."
        }
        status, ua_res = self._call_api("POST", "/api/v1/unani-assessments", token=token, body=unani_payload)
        self.assertEqual(status, 201)
        self.assertEqual(ua_res["assessment"]["dominant_mizaj"], "SAFRAWI")

        # 7. Document Care Plan (Usul-e-Ilaj)
        care_plan_payload = {
            "encounter_id": enc_id,
            "patient_id": patient_id,
            "usul_e_ilaj_summary": "Tadeel-e-Mizaj via Tabreed (cooling) and diuretic hydration (Idrar-e-Baul).",
            "modality_flags": "ILAJ_BIL_DAWA,ILAJ_BIL_GHIZA",
            "dietary_guidelines_ghiza": "Cold fruits (watermelon, pomegranate), cucumber, barley water; avoid spicy & fried food."
        }
        status, cp_res = self._call_api("POST", "/api/v1/care-plans", token=token, body=care_plan_payload)
        self.assertEqual(status, 201)

        # 8. Create Prescription Draft (Sharbat Bazoori Motadil)
        pr_draft_payload = {
            "encounter_id": enc_id,
            "patient_id": patient_id,
            "items": [
                {
                    "item_name": "Sharbat Bazoori Motadil",
                    "formulation_id": "form-sharbat-bazoori",
                    "dosage_form": "ARQ",
                    "dose_amount": "25",
                    "dose_unit": "ml",
                    "frequency": "BD",
                    "duration_days": 7,
                    "instructions": "Mix with lukewarm water, drink morning and evening",
                    "anupan_vehicle": "WATER"
                }
            ]
        }
        status, draft_res = self._call_api("POST", "/api/v1/prescriptions", token=token, body=pr_draft_payload)
        self.assertEqual(status, 200)
        prescription_id = draft_res["prescription"]["id"]
        self.assertEqual(draft_res["prescription"]["overall_safety_state"], "PASS")

        # 9. Sign Prescription with Practitioner PIN '1234'
        sign_payload = {"pin": "1234"}
        status, sign_res = self._call_api("POST", f"/api/v1/prescriptions/{prescription_id}/sign", token=token, body=sign_payload)
        self.assertEqual(status, 200)
        self.assertEqual(sign_res["prescription"]["status"], "SIGNED")
        self.assertIsNotNone(sign_res["prescription"]["signature_hash"])

        # 10. Fetch Printable Prescription Document
        status, print_res = self._call_api("GET", f"/api/v1/prescriptions/{prescription_id}/print")
        self.assertEqual(status, 200)
        printable = print_res["printable_prescription"]
        self.assertTrue(printable["verification"]["is_signed"])
        self.assertEqual(printable["verification"]["reg_no"], "BUMS/DEL/8921/2012")
        self.assertEqual(len(printable["prescription"]["items"]), 1)

if __name__ == "__main__":
    unittest.main()

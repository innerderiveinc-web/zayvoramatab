"""End-to-End Smoke Test: Complete Unani Assessment and Usul-e-Ilaj Care Planning Journey."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store

class TestSmokeUnaniWorkflow(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # 1. Sign in as authorized practitioner Hakeem Tariq
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token = json.loads(resp_bytes.decode("utf-8"))["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_complete_unani_clinical_assessment_journey(self):
        """End-to-end clinical workflow:
        Patient 360 -> Encounter -> Unani Assessment -> Organ-Axis -> Usul-e-Ilaj Care Plan -> Finalisation -> Timeline.
        """
        # Step 1: Open authorized patient pat-syn-001
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/patients/pat-syn-001", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        p360 = json.loads(resp_bytes.decode("utf-8"))
        self.assertEqual(p360["patient"]["mrn"], "MRN-2026-00001")

        # Step 2: Open active encounter enc-syn-001
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/encounters/enc-syn-001", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        enc = json.loads(resp_bytes.decode("utf-8"))["encounter"]
        self.assertEqual(enc["status"], "IN_PROGRESS")

        # Step 3: Create draft Unani assessment for this encounter
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/unani-assessments",
            self.headers, {}, json.dumps({}).encode("utf-8"), "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        assess = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        assessment_id = assess["id"]
        self.assertEqual(assess["status"], "DRAFT")

        # Step 4: Record observations across domains with semantic states and provenance
        update_body = {
            "version_number": 1,
            "dominant_mizaj": "BALGHAMI",
            "secondary_mizaj": "SAUDAWI",
            "mizaj_uncertainty": "HIGH_CONFIDENCE",
            "mizaj_rationale": "Pale complexion, cold and moist touch, slow pulse (Batee), and delayed gastric emptying.",
            "clinical_reasoning": "Su-e-Mizaj Balghami Maddi primarily affecting the gastric faculty (Meda) with secondary ascending vapors inducing cephalalgia.",
            "responses": [
                {
                    "domain_key": "MIZAJ",
                    "field_key": "lawn_complexion",
                    "field_label": "Skin Complexion",
                    "field_value": "Pale whitish tinge",
                    "semantic_state": "OBSERVED",
                    "provenance": "CLINICIAN_OBSERVED",
                    "notes": "Clear indicator of Balghami humor predominance"
                },
                {
                    "domain_key": "AFAAL",
                    "field_key": "hazm_digestion",
                    "field_label": "Digestive Function (Hazm)",
                    "field_value": "Delayed transit and fullness",
                    "semantic_state": "IMPAIRED",
                    "provenance": "PATIENT_REPORTED",
                    "notes": "Patient notes symptom exacerbation after chilled yoghurt"
                },
                {
                    "domain_key": "ASBAB_SITTAH",
                    "field_key": "makool_mashroob",
                    "field_label": "Dietary Intake (Makool-o-Mashroob)",
                    "field_value": "Excess cold and moist dairy foods",
                    "semantic_state": "OBSERVED",
                    "provenance": "PATIENT_REPORTED",
                    "notes": "Contributing lifestyle factor"
                }
            ],
            "conclusions": [
                {
                    "conclusion_type": "SU_E_MIZAJ",
                    "code": "SU-BALGHAM-MADDI",
                    "title": "Su-e-Mizaj Balghami Maddi",
                    "description": "Gastric cold/moist humoral accumulation with secondary cephalalgia",
                    "certainty": "DEFINITIVE"
                }
            ]
        }
        status, _, resp_bytes = ApiRouter.dispatch(
            "PATCH", f"/api/v1/unani-assessments/{assessment_id}",
            self.headers, {}, json.dumps(update_body).encode("utf-8"), "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        updated = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        self.assertEqual(updated["version_number"], 2)
        self.assertEqual(len(updated["responses"]), 3)

        # Step 5: Consult Organ-Axis contextual mapping (Meda <-> Dimagh)
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/organ-axis/mappings?concept=MEDA", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        oa_data = json.loads(resp_bytes.decode("utf-8"))
        self.assertGreaterEqual(len(oa_data["mappings"]), 1)
        mapping_id = oa_data["mappings"][0]["id"]

        # Clinician acknowledges Organ-Axis mapping
        ack_body = json.dumps({"assessment_id": assessment_id, "notes": "Etiology confirmed; headache reflex from gastric vapors."}).encode("utf-8")
        status, _, _ = ApiRouter.dispatch("POST", f"/api/v1/organ-axis/mappings/{mapping_id}/acknowledge", self.headers, {}, ack_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)

        # Step 6: Create Usul-e-Ilaj Care Plan
        cp_body = json.dumps({
            "title": "Care Plan: Phlegm Resolution & Temperamental Normalization",
            "overall_goal": "Restore natural digestive warmth and clear reflex cephalalgia",
            "clinical_rationale": "Su-e-Mizaj Balghami Maddi protocol",
            "review_date": "2026-11-01",
            "items": [
                {
                    "principle_id": "uip-tanqiya",
                    "objective": "Humoral cleansing of excess cold phlegm",
                    "intended_intervention": "Warm decoction of Anise and Fennel seeds",
                    "cautions": "Avoid harsh evacuation"
                },
                {
                    "principle_id": "uip-tadeel",
                    "objective": "Temperamental normalization",
                    "intended_intervention": "Sharbat Bazoori Motadil daily",
                    "cautions": "Confirm normal blood sugar"
                }
            ]
        }).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/encounters/enc-syn-001/care-plans", self.headers, {}, cp_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        care_plan = json.loads(resp_bytes.decode("utf-8"))["care_plan"]
        care_plan_id = care_plan["id"]
        item_2_id = care_plan["items"][1]["id"]

        # Create draft prescription for this encounter (pat-syn-001)
        rx_body = json.dumps({"encounter_id": "enc-syn-001"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/prescriptions", self.headers, {}, rx_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)
        pat_rx_id = json.loads(resp_bytes.decode("utf-8"))["prescription"]["id"]

        # Link prescription draft to care plan item
        link_body = json.dumps({"prescription_id": pat_rx_id}).encode("utf-8")
        status, _, _ = ApiRouter.dispatch("POST", f"/api/v1/care-plans/{care_plan_id}/items/{item_2_id}/link-prescription", self.headers, {}, link_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 201)

        # Transition care plan to ACTIVE
        status, _, resp_bytes = ApiRouter.dispatch("POST", f"/api/v1/care-plans/{care_plan_id}/transition", self.headers, {}, json.dumps({"status": "ACTIVE"}).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)

        # Step 7: Clinician explicitly finalises Unani assessment with cryptographic signature hash
        status, _, resp_bytes = ApiRouter.dispatch("POST", f"/api/v1/unani-assessments/{assessment_id}/finalise", self.headers, {}, json.dumps({}).encode("utf-8"), "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        finalised_assess = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        self.assertEqual(finalised_assess["status"], "FINALISED")
        self.assertIsNotNone(finalised_assess["signature_hash"])

        # Step 8: Verify assessment and care plan in Patient 360 overview
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/patients/pat-syn-001", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        p360_updated = json.loads(resp_bytes.decode("utf-8"))
        self.assertIsNotNone(p360_updated.get("latest_unani_assessment"))
        self.assertEqual(p360_updated["latest_unani_assessment"]["dominant_mizaj"], "BALGHAMI")
        self.assertGreaterEqual(len(p360_updated.get("active_care_plans", [])), 1)

        # Step 9: Verify longitudinal timeline contains the assessment and care plan events
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/patients/pat-syn-001/timeline", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        t_data = json.loads(resp_bytes.decode("utf-8"))
        event_types = [item["event_type"] for item in t_data["timeline"]]
        self.assertIn("UNANI_ASSESSMENT", event_types)
        self.assertIn("CARE_PLAN", event_types)

if __name__ == "__main__":
    unittest.main()

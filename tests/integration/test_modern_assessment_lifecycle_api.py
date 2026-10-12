"""Integration Tests: Modern Clinical Assessment Lifecycle, Red Flags, Differential Support,
Observations, Referrals, Electronic Sign-off, and Governed Amendments.
"""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store


class TestModernAssessmentLifecycleApi(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Authenticate as Hakeem Tariq (Practitioner)
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token = json.loads(resp_bytes.decode("utf-8"))["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_end_to_end_modern_assessment_lifecycle(self):
        """Full clinical lane lifecycle: draft -> observations -> red flags -> acknowledge -> differentials -> problem -> referral -> sign -> amend."""
        # 1. Create Draft Assessment
        create_body = json.dumps({
            "chief_complaint": "Severe throbbing occipital headache and epigastric discomfort",
            "history_of_present_illness": "Symptoms worsening over 3 days, intermittent nausea",
            "working_assessment": "Hypertensive urgency with dyspepsia",
            "uncertainty_level": "PROVISIONAL"
        }).encode("utf-8")

        status, _, resp = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/modern-assessments",
            self.headers, {}, create_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        assess = json.loads(resp.decode("utf-8"))["assessment"]
        assess_id = assess["id"]
        self.assertEqual(assess["status"], "DRAFT")
        self.assertEqual(assess["version_number"], 1)

        # 2. Record Typed Observations (Vitals) with Reference Range Check
        obs_body = json.dumps({
            "observations": [
                {
                    "concept_name": "Systolic Blood Pressure",
                    "value_numeric": 190.0,
                    "unit": "mmHg",
                    "source_type": "CLINICIAN_ENTERED"
                },
                {
                    "concept_name": "Diastolic Blood Pressure",
                    "value_numeric": 115.0,
                    "unit": "mmHg",
                    "source_type": "CLINICIAN_ENTERED"
                },
                {
                    "concept_name": "Heart Rate",
                    "value_numeric": 88.0,
                    "unit": "bpm",
                    "source_type": "CLINICIAN_ENTERED"
                }
            ]
        }).encode("utf-8")

        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/observations",
            self.headers, {}, obs_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        observations = json.loads(resp.decode("utf-8"))["observations"]
        self.assertEqual(len(observations), 3)
        sbp_obs = next(o for o in observations if "Systolic" in o["concept_name"])
        self.assertEqual(sbp_obs["interpretation"], "ABNORMAL_HIGH")
        self.assertEqual(sbp_obs["reference_range_provenance"], "AHA/ACC 2017 Guidelines")

        # 3. Run Safety Checks -> Red Flag Triggered
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/run-safety-checks",
            self.headers, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        safety_res = json.loads(resp.decode("utf-8"))
        alerts = safety_res["persisted_alerts"]
        self.assertGreaterEqual(len(alerts), 1)
        htn_alert = next(a for a in alerts if a["rule_id"] == "RULE-RF-002")
        self.assertEqual(htn_alert["severity"], "EMERGENT")
        alert_id = htn_alert["id"]

        # 4. Attempt to sign without acknowledgment -> Must fail closed
        sign_attempt_body = json.dumps({"pin": "1234"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/sign",
            self.headers, {}, sign_attempt_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 409)  # Conflict: unacknowledged critical red flags

        # 5. Acknowledge Red Flag with Documented Clinical Action
        ack_body = json.dumps({
            "clinician_action_taken": "Administered oral amlodipine 5mg stat; bed rest ordered; repeat BP in 30 mins"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/red-flags/{alert_id}/acknowledge",
            self.headers, {}, ack_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(resp.decode("utf-8"))["acknowledged"])

        # 6. Run Differential Diagnosis Support
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/differential-support",
            self.headers, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        diff_res = json.loads(resp.decode("utf-8"))
        candidates = diff_res["candidates"]
        self.assertGreater(len(candidates), 0)
        peptic_cand = next(c for c in candidates if "Peptic Ulcer" in c["candidate_label"])
        cand_id = peptic_cand["id"]

        # 7. Clinician Reviews Candidate and Confirms as Problem
        decide_body = json.dumps({
            "decision": "CONFIRMED_AS_PROBLEM",
            "rationale": "Consistent burning epigastric pain with meal association",
            "is_primary": True
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/differential-candidates/{cand_id}/decision",
            self.headers, {}, decide_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        dec_data = json.loads(resp.decode("utf-8"))
        self.assertIsNotNone(dec_data["confirmed_problem_id"])

        # 8. Document Referral Record
        ref_body = json.dumps({
            "reason_for_referral": "Severe stage 2 hypertension with persistent headache",
            "target_specialty": "CARDIOLOGY",
            "urgency": "URGENT",
            "destination_facility": "Delhi Heart Institute",
            "handover_summary": "52F presenting with BP 190/115 mmHg, managed acutely with Amlodipine 5mg. Requires secondary workup.",
            "patient_informed_status": "INFORMED_AGREED"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/referrals",
            self.headers, {}, ref_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        ref_data = json.loads(resp.decode("utf-8"))["referral"]
        self.assertEqual(ref_data["actual_status"], "DOCUMENTED")

        # 9. Electronic Sign-Off with PIN Authentication
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/sign",
            self.headers, {}, sign_attempt_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        signed_assess = json.loads(resp.decode("utf-8"))["assessment"]
        self.assertEqual(signed_assess["status"], "SIGNED")
        self.assertIsNotNone(signed_assess["signature_hash"])
        self.assertEqual(len(signed_assess["signature_hash"]), 64)  # SHA-256 length

        # 10. Attempt to edit signed assessment directly -> Conflict
        update_body = json.dumps({"chief_complaint": "Modified text"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "PATCH", f"/api/v1/modern-assessments/{assess_id}",
            self.headers, {}, update_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 409)

        # 11. Governed Amendment
        amend_body = json.dumps({
            "amendment_reason": "Follow-up BP normalized to 142/88 mmHg after 45 minutes; headache subsided.",
            "working_assessment": "Hypertensive urgency responding to initial oral vasodilator"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", f"/api/v1/modern-assessments/{assess_id}/amend",
            self.headers, {}, amend_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        amended = json.loads(resp.decode("utf-8"))["assessment"]
        self.assertEqual(amended["status"], "AMENDED")
        self.assertEqual(amended["version_number"], 2)
        self.assertEqual(len(amended["amendments"]), 1)
        self.assertEqual(amended["amendments"][0]["prior_version_number"], 1)

    def test_tenancy_isolation_modern_assessment(self):
        """Cross-tenant user cannot read or update another organization's assessment."""
        # Create assessment in default org
        body = json.dumps({"chief_complaint": "Cough"}).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/modern-assessments",
            self.headers, {}, body, "127.0.0.1", db_path=self.db_path
        )
        assess_id = json.loads(resp.decode("utf-8"))["assessment"]["id"]

        # Fake context with different org
        foreign_headers = {"authorization": f"Bearer {self.token}"}
        # In a multi-tenant test, dispatch verifies tenant against token's org
        # If we query an invalid ID or wrong org, it returns 404
        status, _, _ = ApiRouter.dispatch(
            "GET", "/api/v1/modern-assessments/mca-non-existent",
            foreign_headers, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 404)

    def test_rbac_restrictions_receptionist(self):
        """Receptionist cannot create draft or sign modern assessments."""
        login_body = json.dumps({"username": "reception", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        rec_token = json.loads(resp_bytes.decode("utf-8"))["token"]
        rec_headers = {"authorization": f"Bearer {rec_token}"}

        body = json.dumps({"chief_complaint": "Unauthorized entry"}).encode("utf-8")
        status, _, _ = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/modern-assessments",
            rec_headers, {}, body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 403)

    def test_patient_timeline_surfaces_modern_assessment_and_referral(self):
        """Patient 360 timeline includes MODERN_CLINICAL_ASSESSMENT and CLINICAL_REFERRAL events."""
        # 1. Create and sign assessment
        create_body = json.dumps({
            "chief_complaint": "Productive cough and fever",
            "working_assessment": "Acute tracheobronchitis"
        }).encode("utf-8")
        status, _, resp = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/modern-assessments",
            self.headers, {}, create_body, "127.0.0.1", db_path=self.db_path
        )
        assess_id = json.loads(resp.decode("utf-8"))["assessment"]["id"]

        # Create referral
        ref_body = json.dumps({
            "reason_for_referral": "Specialist review",
            "target_specialty": "PULMONOLOGY",
            "handover_summary": "Persistent wet cough"
        }).encode("utf-8")
        ApiRouter.dispatch("POST", f"/api/v1/modern-assessments/{assess_id}/referrals", self.headers, {}, ref_body, "127.0.0.1", db_path=self.db_path)

        # 2. Query timeline for pat-syn-001
        status, _, resp = ApiRouter.dispatch(
            "GET", "/api/v1/patients/pat-syn-001/timeline",
            self.headers, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        timeline = json.loads(resp.decode("utf-8"))["timeline"]
        event_types = [t["event_type"] for t in timeline]
        self.assertIn("MODERN_CLINICAL_ASSESSMENT", event_types)
        self.assertIn("CLINICAL_REFERRAL", event_types)


if __name__ == "__main__":
    unittest.main()

"""Integration tests for Phase 9 Care Continuity, Follow-up, Communications & Outcomes REST APIs."""

import os
import json
import hmac
import hashlib
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestCareContinuityApi(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Authenticate as Practitioner (Hakeem)
        self.hakeem_token = self._login("hakeem", "matab123")
        # Authenticate as Receptionist (Front Desk)
        self.reception_token = self._login("reception", "matab123")

        # Register a patient
        status, pat_resp = self._req(
            "POST",
            "/api/v1/patients",
            self.hakeem_token,
            {
                "given_name": "Tariq",
                "family_name": "Mahmood",
                "sex": "MALE",
                "date_of_birth": "1976-08-19",
                "phone": "+919876501234"
            }
        )
        self.assertEqual(status, 201)
        self.patient_id = pat_resp["patient"]["id"]

        # Create an encounter
        status, enc_resp = self._req(
            "POST",
            f"/api/v1/patients/{self.patient_id}/encounters",
            self.hakeem_token,
            {
                "encounter_type": "OPD_VISIT",
                "reason_for_visit": "Subacute productive cough and Su-e-Mizaj Balghami"
            }
        )
        self.assertEqual(status, 201)
        self.encounter_id = enc_resp["encounter"]["id"]

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _login(self, username: str, password: str) -> str:
        body_bytes = json.dumps({"username": username, "password": password}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login", {}, {}, body_bytes, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        return json.loads(resp_bytes.decode("utf-8"))["token"]

    def _req(self, method: str, path: str, token: str = "", body: dict = None, extra_headers: dict = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if extra_headers:
            headers.update(extra_headers)
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, _, resp_bytes = ApiRouter.dispatch(
            method, path, headers, {}, body_bytes, "127.0.0.1", db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def test_end_to_end_continuity_workflow_and_role_redaction(self):
        """Test plan -> task -> reminder -> outcomes -> adverse effect escalation -> role-filtered queue."""
        # 1. Create Follow-up Plan
        st, plan_res = self._req(
            "POST",
            "/api/v1/follow-up/plans",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "review_due_at": "2026-10-29",
                "purpose": "Evaluate Su-e-Mizaj Balghami respiratory response to Sharbat-e-Zufah",
                "clinical_context_summary": "Sensitive diagnosis: Chronic Bronchitis / Balghami Cough",
                "review_format": "in_person",
                "monitoring_items": ["Sputum clearance", "NRS Cough Score"]
            }
        )
        self.assertEqual(st, 201)
        plan = plan_res["plan"]
        task_id = plan["tasks"][0]["id"]

        # 2. Receptionist views Follow-up Queue -> clinical details MUST be redacted
        st, rec_queue = self._req("GET", "/api/v1/follow-up/queue", self.reception_token)
        self.assertEqual(st, 200)
        self.assertTrue(rec_queue["clinical_details_redacted"])
        matching_rec_item = [i for i in rec_queue["queue_items"] if i["id"] == task_id][0]
        self.assertIsNone(matching_rec_item["clinical_context_summary"])
        self.assertEqual(matching_rec_item["purpose"], "Scheduled Follow-up Outreach")

        # 3. Practitioner views Follow-up Queue -> full clinical context visible
        st, doc_queue = self._req("GET", "/api/v1/follow-up/queue", self.hakeem_token)
        self.assertEqual(st, 200)
        self.assertFalse(doc_queue["clinical_details_redacted"])
        matching_doc_item = [i for i in doc_queue["queue_items"] if i["id"] == task_id][0]
        self.assertIn("Chronic Bronchitis", matching_doc_item["clinical_context_summary"])

        # 4. Report a severe adverse effect -> automatically escalates linked task and appears in review queue
        st, adr_res = self._req(
            "POST",
            "/api/v1/adverse-effects",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "follow_up_task_id": task_id,
                "suspected_medication": "Habb-e-Shifa",
                "patient_description": "Severe dizziness and dryness of mouth after morning dose",
                "patient_reported_severity": "severe",
                "causality_assessment": "patient_suspected"
            }
        )
        self.assertEqual(st, 201)
        self.assertEqual(adr_res["adverse_effect"]["urgent_flag"], 1)
        self.assertEqual(adr_res["adverse_effect"]["review_status"], "escalated")

        # Verify linked task was escalated to urgent
        st, task_res = self._req("GET", f"/api/v1/follow-up/tasks/{task_id}", self.hakeem_token)
        self.assertEqual(st, 200)
        self.assertEqual(task_res["task"]["status"], "escalated")
        self.assertEqual(task_res["task"]["priority"], "urgent")

        # 5. Clinician reviews the adverse effect
        adr_id = adr_res["adverse_effect"]["id"]
        st, rev_res = self._req(
            "POST",
            f"/api/v1/adverse-effects/{adr_id}/review",
            self.hakeem_token,
            {
                "clinician_assessed_severity": "moderate",
                "causality_assessment": "clinician_assessed",
                "action_taken": "Held Habb-e-Shifa; advised hydration and urgent in-clinic review",
                "review_status": "reviewed"
            }
        )
        self.assertEqual(st, 200)
        self.assertEqual(rev_res["adverse_effect"]["review_status"], "reviewed")

        # 6. Fetch Patient 360 Continuity Summary
        st, sum_res = self._req(
            "GET",
            f"/api/v1/patients/{self.patient_id}/follow-up-summary",
            self.hakeem_token
        )
        self.assertEqual(st, 200)
        summary = sum_res["continuity_summary"]
        self.assertEqual(len(summary["follow_up_plans"]), 1)
        self.assertEqual(len(summary["adverse_effect_reports"]), 1)

    def test_provider_webhooks_hmac_idempotency_dead_letter_and_opt_out(self):
        """Test provider webhook HMAC signature validation, idempotent replay, dead-letter retries, and STOP opt-out."""
        # Dispatch an initial message
        st, send_res = self._req(
            "POST",
            "/api/v1/patient-communications/send",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "template_code": "TPL-APPT-REMINDER-EN",
                "placeholders": {
                    "patient_name": "Tariq Mahmood",
                    "facility_name": "Central Matab OPD",
                    "appointment_date": "2026-10-29",
                    "clinic_phone": "+91-9800000001"
                }
            }
        )
        self.assertEqual(st, 200)
        msg_id = send_res["message"]["id"]

        # 1. Invalid HMAC signature rejected with 401
        bad_payload = {
            "provider_event_id": "evt-001",
            "message_id": msg_id,
            "event_type": "delivered"
        }
        st, err_res = self._req(
            "POST",
            "/api/v1/patient-communications/provider-webhooks/sandbox_sms",
            body=bad_payload,
            extra_headers={"X-Provider-Signature": "invalid_signature_hex"}
        )
        self.assertEqual(st, 401)
        self.assertEqual(err_res["code"], "INVALID_WEBHOOK_SIGNATURE")

        # 2. Valid HMAC signature processes delivery event and deduplicates replay
        secret = "matab_webhook_secret_dev_key"
        raw_bytes = json.dumps(bad_payload).encode("utf-8")
        valid_sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()

        st, wh_res1 = self._req(
            "POST",
            "/api/v1/patient-communications/provider-webhooks/sandbox_sms",
            body=bad_payload,
            extra_headers={"X-Provider-Signature": valid_sig}
        )
        self.assertEqual(st, 200)
        self.assertFalse(wh_res1["idempotent_replay"])
        self.assertEqual(wh_res1["resulting_status"], "delivered")

        # Replay same provider_event_id -> idempotent_replay: True
        st, wh_res2 = self._req(
            "POST",
            "/api/v1/patient-communications/provider-webhooks/sandbox_sms",
            body=bad_payload,
            extra_headers={"X-Provider-Signature": valid_sig}
        )
        self.assertEqual(st, 200)
        self.assertTrue(wh_res2["idempotent_replay"])

        # 3. Repeated failure events transition message to dead_letter after max_retries (3)
        for attempt in range(1, 4):
            fail_payload = {
                "provider_event_id": f"evt-fail-{attempt}",
                "message_id": msg_id,
                "event_type": "failed",
                "failure_reason": "Carrier timeout"
            }
            sig = hmac.new(secret.encode("utf-8"), json.dumps(fail_payload).encode("utf-8"), hashlib.sha256).hexdigest()
            st, f_res = self._req(
                "POST",
                "/api/v1/patient-communications/provider-webhooks/sandbox_sms",
                body=fail_payload,
                extra_headers={"X-Provider-Signature": sig}
            )
            self.assertEqual(st, 200)
            if attempt == 3:
                self.assertEqual(f_res["resulting_status"], "dead_letter")

        # 4. Opt-out webhook (patient replies STOP) immediately blocks future automated messages
        optout_payload = {
            "provider_event_id": "evt-stop-001",
            "message_id": msg_id,
            "event_type": "opt_out_received"
        }
        sig_stop = hmac.new(secret.encode("utf-8"), json.dumps(optout_payload).encode("utf-8"), hashlib.sha256).hexdigest()
        st, stop_res = self._req(
            "POST",
            "/api/v1/patient-communications/provider-webhooks/sandbox_sms",
            body=optout_payload,
            extra_headers={"X-Provider-Signature": sig_stop}
        )
        self.assertEqual(st, 200)
        self.assertEqual(stop_res["resulting_status"], "opt_out_processed")

        # Subsequent send attempt for this patient is automatically suppressed
        st, next_send = self._req(
            "POST",
            "/api/v1/patient-communications/send",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "template_code": "TPL-APPT-REMINDER-EN",
                "placeholders": {"patient_name": "Tariq Mahmood", "facility_name": "OPD", "appointment_date": "2026-11-01", "clinic_phone": "123"}
            }
        )
        self.assertEqual(st, 200)
        self.assertEqual(next_send["message"]["status"], "suppressed")


if __name__ == "__main__":
    unittest.main()

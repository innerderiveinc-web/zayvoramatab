"""Integration & End-to-End tests for Phase 10 Clinic Operations OS REST APIs & RBAC Matrix."""

import os
import json
import tempfile
import unittest
from datetime import date, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestClinicOperationsApi(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self._ip_counter = 10

        # Authenticate across all clinic operational & clinical roles
        self.admin_token = self._login("admin", "matab123")
        self.hakeem_token = self._login("hakeem", "matab123")
        self.reception_token = self._login("reception", "matab123")
        self.cashier_token = self._login("cashier", "matab123")
        self.pharmacy_token = self._login("pharmacy", "matab123")
        self.inventory_token = self._login("inventory", "matab123")

        self.today = date.today().isoformat()

        # Register a test patient via Receptionist
        st, pat_resp = self._req(
            "POST",
            "/api/v1/patients",
            self.reception_token,
            {
                "given_name": "Zainab",
                "family_name": "Qureshi",
                "sex": "FEMALE",
                "date_of_birth": "1988-03-14",
                "phone": "+919811122334"
            }
        )
        self.assertEqual(st, 201)
        self.patient_id = pat_resp["patient"]["id"]

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _login(self, username: str, password: str) -> str:
        self._ip_counter += 1
        client_ip = f"10.0.0.{self._ip_counter}"
        body_bytes = json.dumps({"username": username, "password": password}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login", {}, {}, body_bytes, client_ip, db_path=self.db_path
        )
        self.assertEqual(status, 200)
        return json.loads(resp_bytes.decode("utf-8"))["token"]

    def _req(self, method: str, path: str, token: str = "", body: dict = None, query: dict = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, _, resp_bytes = ApiRouter.dispatch(
            method, path, headers, query or {}, body_bytes, "127.0.0.1", db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def test_end_to_end_clinic_visit_lifecycle(self):
        """
        End-to-End clinic workflow:
        Arrival -> Appointment Booking & Check-In -> Queue Token -> Public Display Privacy ->
        Consultation Encounter -> Prescription Sign-Off -> Billing Invoice & Payment ->
        Signed Rx FEFO Dispensing -> Follow-up Plan -> Today Dashboard & Reports.
        """
        # 1. Configure practitioner schedule for ALL days so test runs cleanly on any day of week
        st, sched_res = self._req(
            "POST",
            "/api/v1/scheduling/practitioner-schedules",
            self.admin_token,
            {
                "practitioner_id": "usr-hakeem-1",
                "day_of_week": "ALL",
                "start_time": "09:00",
                "end_time": "17:00",
                "slot_duration_minutes": 15,
                "max_bookings_per_slot": 1
            }
        )
        self.assertEqual(st, 200)

        # 2. Check slot availability via API
        st, avail_res = self._req(
            "GET",
            "/api/v1/scheduling/availability",
            self.reception_token,
            query={"practitioner_id": "usr-hakeem-1", "date": self.today}
        )
        self.assertEqual(st, 200)
        self.assertTrue(len(avail_res["availability"]["slots"]) > 0)

        # 3. Receptionist books an appointment for the patient
        slot_start = f"{self.today}T10:30:00"
        slot_end = f"{self.today}T10:45:00"
        st, appt_res = self._req(
            "POST",
            "/api/v1/appointments",
            self.reception_token,
            {
                "patient_id": self.patient_id,
                "practitioner_id": "usr-hakeem-1",
                "start_at": slot_start,
                "end_at": slot_end,
                "appointment_type": "INITIAL_CONSULTATION",
                "reason_category": "GENERAL_CONSULTATION",
                "clinical_reason_notes": "Chronic digestive weakness (Zoaf-e-Meda)"
            }
        )
        self.assertEqual(st, 201)
        appt_id = appt_res["appointment"]["id"]
        self.assertEqual(appt_res["appointment"]["status"], "booked")

        # Double-booking same slot must fail with 409
        st_dup, _ = self._req(
            "POST",
            "/api/v1/appointments",
            self.reception_token,
            {
                "patient_id": "pat-syn-001",
                "practitioner_id": "usr-hakeem-1",
                "start_at": slot_start,
                "end_at": slot_end
            }
        )
        self.assertEqual(st_dup, 409)

        # 4. Receptionist checks in the appointment -> automatically issues OPD queue token & encounter
        st, checkin_res = self._req(
            "POST",
            f"/api/v1/appointments/{appt_id}/check-in",
            self.reception_token,
            {"priority": "NORMAL"}
        )
        self.assertEqual(st, 200)
        self.assertEqual(checkin_res["appointment"]["status"], "arrived")
        queue_token = checkin_res["appointment"]["queue_token"]
        token_id = queue_token["id"]
        encounter_id = queue_token["encounter_id"]
        self.assertTrue(queue_token["token_code"].startswith("T-"))
        self.assertIsNotNone(encounter_id)

        # 5. Verify Public Waiting-Room Display has zero PHI leakage
        st, pub_res = self._req(
            "GET",
            "/api/v1/queue",
            self.reception_token,
            query={"public_display": "true", "queue_date": self.today}
        )
        self.assertEqual(st, 200)
        pub_display = pub_res["public_queue"]
        self.assertEqual(pub_display["privacy_mode"], "PUBLIC_SAFE_TOKEN_ONLY")
        for tok in pub_display["active_tokens"]:
            self.assertNotIn("patient_name", tok)
            self.assertNotIn("patient_mrn", tok)
            self.assertNotIn("clinical_reason_notes", tok)

        # 6. Transition Queue Token: waiting -> called -> in_consultation
        st, call_res = self._req(
            "POST",
            f"/api/v1/queue/tokens/{token_id}/call",
            self.reception_token,
            {"reason": "Calling patient to Room 1"}
        )
        self.assertEqual(st, 200)
        self.assertEqual(call_res["token"]["status"], "called")

        st, consult_res = self._req(
            "POST",
            f"/api/v1/queue/tokens/{token_id}/start",
            self.hakeem_token,
            {}
        )
        self.assertEqual(st, 200)
        self.assertEqual(consult_res["token"]["status"], "in_consultation")

        # 7. Practitioner authors a prescription in the encounter, validates, and signs it
        st, rx_res = self._req(
            "POST",
            "/api/v1/prescriptions",
            self.hakeem_token,
            {
                "encounter_id": encounter_id,
                "items": [
                    {
                        "item_type": "CATALOG_FORMULATION",
                        "formulation_id": "form-sharbat-bazoori",
                        "item_name": "Sharbat Bazoori Motadil",
                        "dosage_form": "SHARBAT",
                        "dose_amount": "1",
                        "dose_unit": "ml",
                        "frequency": "BD",
                        "duration_days": 7,
                        "quantity_to_dispense": "200 ml"
                    }
                ]
            }
        )
        self.assertEqual(st, 201)
        rx_id = rx_res["prescription"]["id"]

        # Attempt to dispense BEFORE signing -> MUST be rejected with 409
        st_unsigned, unsigned_err = self._req(
            "POST",
            "/api/v1/dispensing",
            self.pharmacy_token,
            {
                "prescription_id": rx_id,
                "patient_id": self.patient_id,
                "items": [
                    {
                        "batch_id": "batch-bazoori-2027",
                        "dispensed_qty_decimal": "200.00"
                    }
                ]
            }
        )
        self.assertEqual(st_unsigned, 409)
        self.assertEqual(unsigned_err["details"]["code"], "UNSIGNED_PRESCRIPTION_CANNOT_DISPENSE")

        # Validate & electronically sign the prescription
        st_val, _ = self._req("POST", f"/api/v1/prescriptions/{rx_id}/validate", self.hakeem_token, {})
        self.assertEqual(st_val, 200)

        st_sign, sign_res = self._req(
            "POST",
            f"/api/v1/prescriptions/{rx_id}/sign",
            self.hakeem_token,
            {"pin": "1234"}
        )
        self.assertEqual(st_sign, 200)
        self.assertEqual(sign_res["prescription"]["status"], "SIGNED")
        signed_hash = sign_res["prescription"]["signature_hash"]

        # 8. Cashier creates & finalizes invoice, tests failed payment, then records valid payment
        st, inv_res = self._req(
            "POST",
            "/api/v1/billing/invoices",
            self.cashier_token,
            {
                "patient_id": self.patient_id,
                "encounter_id": encounter_id,
                "appointment_id": appt_id,
                "lines": [
                    {
                        "category": "CONSULTATION",
                        "description": "General Unani Consultation",
                        "quantity_decimal": "1.00",
                        "unit_price_decimal": "300.00",
                        "tax_rate_bp": 0
                    },
                    {
                        "category": "MEDICATION",
                        "description": "Sharbat Bazoori Motadil 200ml",
                        "quantity_decimal": "1.00",
                        "unit_price_decimal": "180.00",
                        "tax_rate_bp": 0
                    }
                ]
            }
        )
        self.assertEqual(st, 201)
        invoice_id = inv_res["invoice"]["id"]
        self.assertEqual(inv_res["invoice"]["total_decimal"], "480.00")

        st, fin_res = self._req(
            "POST",
            f"/api/v1/billing/invoices/{invoice_id}/finalize",
            self.cashier_token,
            {}
        )
        self.assertEqual(st, 200)
        self.assertEqual(fin_res["invoice"]["status"], "FINALIZED")

        # Failed UPI payment must NOT mark invoice paid
        st, fail_pay = self._req(
            "POST",
            "/api/v1/billing/payments",
            self.cashier_token,
            {
                "invoice_id": invoice_id,
                "amount_decimal": "480.00",
                "payment_method": "UPI",
                "provider_status": "FAILED",
                "failure_reason": "UPI timeout"
            }
        )
        self.assertEqual(st, 201)
        self.assertEqual(fail_pay["payment"]["status"], "FAILED")
        self.assertIsNone(fail_pay["payment"]["receipt_number"])

        # Successful Cash payment marks invoice PAID and issues receipt
        st, ok_pay = self._req(
            "POST",
            "/api/v1/billing/payments",
            self.cashier_token,
            {
                "invoice_id": invoice_id,
                "amount_decimal": "480.00",
                "payment_method": "CASH",
                "provider_status": "POSTED",
                "idempotency_key": "IDEMP-E2E-PAY-001"
            }
        )
        self.assertEqual(st, 201)
        self.assertEqual(ok_pay["payment"]["status"], "POSTED")
        self.assertTrue(ok_pay["payment"]["receipt_number"].startswith("RCP-"))

        st, inv_paid = self._req("GET", f"/api/v1/billing/invoices/{invoice_id}", self.cashier_token)
        self.assertEqual(st, 200)
        self.assertEqual(inv_paid["invoice"]["status"], "PAID")
        self.assertEqual(inv_paid["invoice"]["balance_due_decimal"], "0.00")

        # 9. Pharmacist dispenses signed prescription from FEFO batch
        st, disp_res = self._req(
            "POST",
            "/api/v1/dispensing",
            self.pharmacy_token,
            {
                "prescription_id": rx_id,
                "patient_id": self.patient_id,
                "encounter_id": encounter_id,
                "counseling_checklist_completed": True,
                "counseling_notes": "Take 25 ml diluted in water twice daily before meals.",
                "idempotency_key": "IDEMP-E2E-DISP-001",
                "items": [
                    {
                        "batch_id": "batch-bazoori-2027",
                        "dispensed_qty_decimal": "200.00",
                        "prescribed_item_name": "Sharbat Bazoori Motadil",
                        "prescribed_dose_instructions": "1 ml BD for 7 days"
                    }
                ]
            }
        )
        self.assertEqual(st, 201)
        dispense = disp_res["dispense"]
        self.assertEqual(dispense["status"], "DISPENSED")
        self.assertEqual(dispense["prescription_signature_hash"], signed_hash)

        # Verify signed prescription signature_hash was NOT mutated by dispensing
        st_rx_check, rx_after = self._req("GET", f"/api/v1/prescriptions/{rx_id}", self.hakeem_token)
        self.assertEqual(st_rx_check, 200)
        self.assertEqual(rx_after["prescription"]["signature_hash"], signed_hash)

        # 10. Complete Queue Token
        st, comp_tok = self._req(
            "POST",
            f"/api/v1/queue/tokens/{token_id}/complete",
            self.hakeem_token,
            {}
        )
        self.assertEqual(st, 200)
        self.assertEqual(comp_tok["token"]["status"], "completed")

        # 11. Create Follow-up Plan and verify Today Dashboard + Operational Reports
        st, fup_res = self._req(
            "POST",
            "/api/v1/follow-up/plans",
            self.hakeem_token,
            {
                "patient_id": self.patient_id,
                "encounter_id": encounter_id,
                "review_due_at": (date.today() + timedelta(days=7)).isoformat(),
                "purpose": "Review response to Sharbat Bazoori Motadil after 7 days",
                "review_format": "in_person"
            }
        )
        self.assertEqual(st, 201)

        st, today_res = self._req(
            "GET",
            "/api/v1/operations/today",
            self.hakeem_token,
            query={"date": self.today}
        )
        self.assertEqual(st, 200)
        self.assertEqual(today_res["today"]["date"], self.today)
        self.assertGreaterEqual(today_res["today"]["metrics"]["todays_appointments_count"], 1)
        self.assertGreaterEqual(today_res["today"]["metrics"]["completed_visits_count"], 1)
        self.assertGreaterEqual(today_res["today"]["metrics"]["follow_ups_due_count"], 1)

        st, rep_res = self._req(
            "GET",
            "/api/v1/operations/reports",
            self.admin_token,
            query={"date_from": self.today, "date_to": self.today}
        )
        self.assertEqual(st, 200)
        self.assertFalse(rep_res["reports"]["claims_clinical_efficacy"])
        self.assertEqual(rep_res["reports"]["billing_and_collections"]["net_collections_decimal"], "480.00")
        self.assertEqual(rep_res["reports"]["billing_and_collections"]["failed_or_unknown_payment_count"], 1)

    def test_role_based_access_control_matrix(self):
        """Verify strict role separation across Receptionist, Cashier, Pharmacist, Inventory Manager, and Practitioner."""
        # 1. Receptionist cannot record inventory adjustments or dispense prescriptions
        st, _ = self._req(
            "POST",
            "/api/v1/inventory/movements",
            self.reception_token,
            {
                "batch_id": "batch-bazoori-2027",
                "movement_type": "ADJUSTMENT_DOWN",
                "quantity_decimal": "10.00",
                "reason": "Unauthorized attempt"
            }
        )
        self.assertEqual(st, 403)

        st, _ = self._req(
            "POST",
            "/api/v1/dispensing",
            self.reception_token,
            {"prescription_id": "rx-any", "patient_id": self.patient_id, "items": []}
        )
        self.assertEqual(st, 403)

        # 2. Receptionist cannot assign CLINICAL_URGENT priority on queue tokens
        st, prio_err = self._req(
            "POST",
            "/api/v1/queue/tokens",
            self.reception_token,
            {
                "patient_id": self.patient_id,
                "practitioner_id": "usr-hakeem-1",
                "priority": "CLINICAL_URGENT",
                "priority_reason": "Receptionist attempting clinical triage"
            }
        )
        self.assertEqual(st, 403)

        # 3. Cashier can create invoices, but cannot receive pharmacy stock or dispense medicines
        st, _ = self._req(
            "POST",
            "/api/v1/inventory/receipts",
            self.cashier_token,
            {
                "inventory_item_id": "iitem-bazoori",
                "batch_number": "UNAUTH-BATCH",
                "expiry_date": "2028-01-01",
                "quantity_decimal": "10.00"
            }
        )
        self.assertEqual(st, 403)

        # 4. Pharmacist can view inventory and dispense, but cannot approve billing refunds
        st, _ = self._req(
            "POST",
            "/api/v1/billing/payments/pay-any/refund",
            self.pharmacy_token,
            {
                "amount_decimal": "100.00",
                "reason": "Unauthorized refund by pharmacist"
            }
        )
        self.assertEqual(st, 403)

        # 5. Inventory Manager can receive stock and record stocktakes, but cannot create clinical encounters
        st, rec_res = self._req(
            "POST",
            "/api/v1/inventory/receipts",
            self.inventory_token,
            {
                "inventory_item_id": "iitem-bazoori",
                "batch_number": "BZ-2027-INV",
                "expiry_date": "2027-12-31",
                "quantity_decimal": "150.00",
                "unit_cost_decimal": "92.00"
            }
        )
        self.assertEqual(st, 201)

        st, _ = self._req(
            "POST",
            f"/api/v1/patients/{self.patient_id}/encounters",
            self.inventory_token,
            {"encounter_type": "OPD_VISIT", "reason_for_visit": "Unauthorized encounter creation"}
        )
        self.assertEqual(st, 403)


if __name__ == "__main__":
    unittest.main()

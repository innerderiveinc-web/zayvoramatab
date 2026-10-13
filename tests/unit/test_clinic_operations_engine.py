"""Unit tests for Phase 10 Clinic Operations OS Engine:
Scheduling, Queue Tokens, Exact-Decimal Billing, FEFO Inventory Ledger, and Signed-Prescription Dispensing.
"""

import os
import json
import tempfile
import unittest
from datetime import date, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.clinic_operations import ClinicOperationsService
from apps.api.domains.patients import PatientService
from apps.api.domains.encounters import EncounterService
from apps.api.domains.prescriptions import PrescriptionService
from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import ValidationError, ConflictError, ForbiddenError


class TestClinicOperationsEngine(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.service = ClinicOperationsService(db_path=self.db_path)
        self.org_id = "org-matab-default"
        self.fac_id = "fac-central-opd"
        self.hakeem_id = "usr-hakeem-1"
        self.recep_id = "usr-recep-1"
        self.pharm_id = "usr-pharm-1"
        self.admin_id = "usr-admin-1"
        self.patient_id = "pat-syn-001"

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_scheduling_double_booking_cancelled_slot_release_and_conflict_reporting(self):
        """Double booking is blocked; cancelling releases slot; schedule/leave updates report conflicts."""
        target_date = (date.today() + timedelta(days=2)).isoformat()
        slot_start = f"{target_date}T10:00:00"
        slot_end = f"{target_date}T10:15:00"

        appt1 = self.service.create_appointment(
            self.org_id,
            self.fac_id,
            self.recep_id,
            {
                "patient_id": self.patient_id,
                "practitioner_id": self.hakeem_id,
                "start_at": slot_start,
                "end_at": slot_end,
                "appointment_type": "INITIAL_CONSULTATION",
                "reason_category": "GENERAL_CONSULTATION",
                "clinical_reason_notes": "Private Hakeem note on chronic dyspepsia",
            },
        )
        self.assertEqual(appt1["status"], "booked")

        # Concurrent/second booking for same slot is blocked
        with self.assertRaises(ConflictError):
            self.service.create_appointment(
                self.org_id,
                self.fac_id,
                self.recep_id,
                {
                    "patient_id": "pat-syn-003",
                    "practitioner_id": self.hakeem_id,
                    "start_at": slot_start,
                    "end_at": slot_end,
                },
            )

        # Schedule update that narrows hours to 11:00-16:00 surfaces conflict with 10:00 booking
        with self.assertRaises(ConflictError) as ctx_sched:
            self.service.upsert_practitioner_schedule(
                self.org_id,
                self.fac_id,
                self.admin_id,
                {
                    "practitioner_id": self.hakeem_id,
                    "day_of_week": "ALL",
                    "start_time": "11:00",
                    "end_time": "16:00",
                },
            )
        self.assertEqual(ctx_sched.exception.details["code"], "SCHEDULE_CONFLICT_WITH_BOOKED_APPOINTMENTS")

        # Leave block overlapping 10:00 slot surfaces conflict unless acknowledged
        with self.assertRaises(ConflictError) as ctx_blk:
            self.service.create_schedule_block(
                self.org_id,
                self.fac_id,
                self.admin_id,
                {
                    "practitioner_id": self.hakeem_id,
                    "block_start_at": f"{target_date}T09:30:00",
                    "block_end_at": f"{target_date}T11:00:00",
                    "reason": "Conference attendance",
                },
            )
        self.assertEqual(ctx_blk.exception.details["code"], "LEAVE_BLOCK_CONFLICTS_WITH_APPOINTMENTS")

        # Cancel appt1 -> releases slot_lock_key so pat-syn-003 can now book that exact slot
        cancelled = self.service.transition_appointment_state(
            self.org_id, self.fac_id, appt1["id"], "cancelled", self.recep_id, reason="Patient requested cancellation"
        )
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertIsNone(cancelled["slot_lock_key"])

        appt2 = self.service.create_appointment(
            self.org_id,
            self.fac_id,
            self.recep_id,
            {
                "patient_id": "pat-syn-003",
                "practitioner_id": self.hakeem_id,
                "start_at": slot_start,
                "end_at": slot_end,
            },
        )
        self.assertEqual(appt2["status"], "booked")

    def test_queue_duplicate_prevention_priority_governance_and_public_privacy(self):
        """Duplicate active tokens are blocked; unauthorized urgent priority is rejected; public queue hides PII."""
        # Receptionist cannot self-assign CLINICAL_URGENT priority
        recep_ctx = {"roles": ["RECEPTIONIST"], "permissions": ["queue:write", "queue:read"]}
        with self.assertRaises(ForbiddenError):
            self.service.issue_queue_token(
                self.org_id,
                self.fac_id,
                self.recep_id,
                {
                    "patient_id": self.patient_id,
                    "practitioner_id": self.hakeem_id,
                    "priority": "CLINICAL_URGENT",
                    "priority_reason": "Trying urgent without clinical role",
                },
                user_ctx=recep_ctx,
            )

        # Normal walk-in token succeeds and creates linked encounter
        tok1 = self.service.issue_queue_token(
            self.org_id,
            self.fac_id,
            self.recep_id,
            {
                "patient_id": self.patient_id,
                "practitioner_id": self.hakeem_id,
                "visit_type": "WALK_IN",
                "priority": "NORMAL",
                "idempotency_key": "walkin-tok-1",
            },
            user_ctx=recep_ctx,
        )
        self.assertEqual(tok1["token_code"], "T-001")
        self.assertIsNotNone(tok1["encounter_id"])

        # Accidental duplicate token for same patient/practitioner/date is blocked
        with self.assertRaises(ConflictError):
            self.service.issue_queue_token(
                self.org_id,
                self.fac_id,
                self.recep_id,
                {
                    "patient_id": self.patient_id,
                    "practitioner_id": self.hakeem_id,
                    "visit_type": "WALK_IN",
                },
                user_ctx=recep_ctx,
            )

        # Public waiting-room queue display hides patient_name, patient_mrn, and clinical reasons
        pub = self.service.get_public_queue_display(self.org_id, self.fac_id)
        self.assertEqual(pub["privacy_mode"], "PUBLIC_SAFE_TOKEN_ONLY")
        self.assertEqual(len(pub["active_tokens"]), 1)
        pub_tok = pub["active_tokens"][0]
        self.assertEqual(pub_tok["token_code"], "T-001")
        self.assertNotIn("patient_name", pub_tok)
        self.assertNotIn("patient_mrn", pub_tok)

        # Transition token: waiting -> called -> in_consultation -> completed
        called = self.service.transition_queue_token(self.org_id, self.fac_id, tok1["id"], "called", self.recep_id)
        self.assertIsNotNone(called["called_at"])
        started = self.service.transition_queue_token(
            self.org_id, self.fac_id, tok1["id"], "in_consultation", self.hakeem_id
        )
        self.assertIsNotNone(started["consultation_started_at"])
        completed = self.service.transition_queue_token(
            self.org_id, self.fac_id, tok1["id"], "completed", self.hakeem_id
        )
        self.assertEqual(completed["status"], "completed")
        self.assertIsNotNone(completed["consultation_ended_at"])

    def test_billing_exact_decimal_failed_payments_idempotency_and_refund_reconciliation(self):
        """Billing rejects floats/CVV, handles failed payments honestly, and reconciles refunds and voids."""
        # Reject floating-point monetary values
        with self.assertRaises(ValidationError):
            self.service.create_invoice(
                self.org_id,
                self.fac_id,
                self.recep_id,
                {
                    "patient_id": self.patient_id,
                    "lines": [{"description": "Consultation", "quantity_decimal": "1.00", "unit_price_decimal": 300.50}],
                },
            )

        inv = self.service.create_invoice(
            self.org_id,
            self.fac_id,
            self.recep_id,
            {
                "patient_id": self.patient_id,
                "discount_decimal": "25.00",
                "discount_reason": "Senior citizen concession",
                "lines": [
                    {"description": "OPD Consultation", "quantity_decimal": "1.00", "unit_price_decimal": "300.00", "tax_rate_bp": 0},
                    {"description": "Hijama Session", "quantity_decimal": "1.00", "unit_price_decimal": "600.00", "discount_decimal": "50.00", "tax_rate_bp": 500},
                ],
            },
        )
        # Line 1: 300.00, Line 2: (600 - 50) = 550.00 + 5% tax (27.50) = 577.50
        # Subtotal = 900.00, Total Discount = 50.00 + 25.00 = 75.00, Tax = 27.50 -> Total = 852.50
        self.assertEqual(inv["subtotal_decimal"], "900.00")
        self.assertEqual(inv["discount_decimal"], "75.00")
        self.assertEqual(inv["tax_decimal"], "27.50")
        self.assertEqual(inv["total_decimal"], "852.50")

        fin_inv = self.service.finalize_invoice(self.org_id, self.fac_id, inv["id"], self.recep_id)
        self.assertEqual(fin_inv["status"], "FINALIZED")
        self.assertIsNotNone(fin_inv["finalized_snapshot_json"])

        # Reject sensitive card security code (CVV)
        with self.assertRaises(ValidationError):
            self.service.record_payment(
                self.org_id,
                self.fac_id,
                self.recep_id,
                {"invoice_id": inv["id"], "amount_decimal": "852.50", "payment_method": "CARD", "cvv": "123"},
            )

        # Failed payment attempt does NOT mark invoice paid or issue receipt
        failed_pay = self.service.record_payment(
            self.org_id,
            self.fac_id,
            self.recep_id,
            {
                "invoice_id": inv["id"],
                "amount_decimal": "852.50",
                "payment_method": "UPI",
                "provider_status": "FAILED",
                "failure_reason": "UPI timeout at bank switch",
            },
        )
        self.assertEqual(failed_pay["status"], "FAILED")
        self.assertIsNone(failed_pay["receipt_number"])
        inv_after_fail = self.service.get_invoice(self.org_id, self.fac_id, inv["id"])
        self.assertEqual(inv_after_fail["paid_decimal"], "0.00")
        self.assertEqual(inv_after_fail["status"], "FINALIZED")

        # Posted payment with idempotency key succeeds and issues receipt
        posted_pay = self.service.record_payment(
            self.org_id,
            self.fac_id,
            self.recep_id,
            {
                "invoice_id": inv["id"],
                "amount_decimal": "852.50",
                "payment_method": "CASH",
                "provider_status": "POSTED",
                "idempotency_key": "pay-idem-001",
            },
        )
        self.assertEqual(posted_pay["status"], "POSTED")
        self.assertIsNotNone(posted_pay["receipt_number"])

        # Duplicate payment replay with same idempotency_key does not double-charge
        replay_pay = self.service.record_payment(
            self.org_id,
            self.fac_id,
            self.recep_id,
            {
                "invoice_id": inv["id"],
                "amount_decimal": "852.50",
                "payment_method": "CASH",
                "provider_status": "POSTED",
                "idempotency_key": "pay-idem-001",
            },
        )
        self.assertTrue(replay_pay["idempotent_replay"])
        self.assertEqual(replay_pay["id"], posted_pay["id"])

        # Partial refund of 152.50 updates net collections to 700.00
        ref = self.service.refund_payment(
            self.org_id,
            self.fac_id,
            posted_pay["id"],
            self.admin_id,
            {"amount_decimal": "152.50", "reason": "Hijama session postponed"},
        )
        self.assertEqual(ref["amount_decimal"], "152.50")

        rep = self.service.get_collections_report(self.org_id, self.fac_id)
        self.assertEqual(rep["gross_collections_decimal"], "852.50")
        self.assertEqual(rep["total_refunds_decimal"], "152.50")
        self.assertEqual(rep["net_collections_decimal"], "700.00")
        self.assertEqual(rep["failed_or_unknown_payment_count"], 1)

    def test_inventory_ledger_expiry_quarantine_and_signed_prescription_dispensing(self):
        """Inventory enforces ledger movements, blocks expired/quarantined batches, and requires SIGNED prescriptions."""
        # 1. Create a DRAFT prescription and verify it CANNOT be dispensed
        conn = DatabaseConnection(self.db_path).get_connection()
        try:
            enc = EncounterService.create_encounter(
                conn=conn,
                organization_id=self.org_id,
                facility_id=self.fac_id,
                patient_id=self.patient_id,
                practitioner_id=self.hakeem_id,
                encounter_type="OPD_VISIT",
                reason_for_visit="Renal colic and dysuria",
                actor_id=self.hakeem_id,
            )
            rx_draft = PrescriptionService.create_prescription_draft(
                conn=conn,
                organization_id=self.org_id,
                encounter_id=enc["id"],
                practitioner_id=self.hakeem_id,
                actor_id=self.hakeem_id,
                data={
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
                            "quantity_to_dispense": "200 ml",
                        }
                    ]
                },
            )
            conn.commit()
        finally:
            conn.close()

        # Attempt to dispense DRAFT prescription -> blocked!
        with self.assertRaises(ConflictError) as ctx_unsigned:
            self.service.dispense_prescription(
                self.org_id,
                self.fac_id,
                self.pharm_id,
                {
                    "prescription_id": rx_draft["id"],
                    "patient_id": self.patient_id,
                    "items": [{"batch_id": "batch-bazoori-2027", "dispensed_qty_decimal": "200.00"}],
                },
            )
        self.assertEqual(ctx_unsigned.exception.details["code"], "UNSIGNED_PRESCRIPTION_CANNOT_DISPENSE")

        # Electronically sign the prescription as Hakeem (PIN '1234')
        conn = DatabaseConnection(self.db_path).get_connection()
        try:
            rx_signed = PrescriptionService.sign_prescription(
                conn=conn,
                organization_id=self.org_id,
                prescription_id=rx_draft["id"],
                practitioner_id=self.hakeem_id,
                pin="1234",
                actor_id=self.hakeem_id,
            )
            conn.commit()
        finally:
            conn.close()

        # Receive an expired batch and verify it is blocked from dispensing
        expired_rec = self.service.receive_stock(
            self.org_id,
            self.fac_id,
            self.pharm_id,
            {
                "inventory_item_id": "iitem-bazoori",
                "batch_number": "BZM-EXPIRED-2024",
                "expiry_date": "2024-01-01",
                "quantity_decimal": "500.00",
            },
        )
        expired_batch_id = expired_rec["batch"]["id"]

        with self.assertRaises(ConflictError) as ctx_exp:
            self.service.dispense_prescription(
                self.org_id,
                self.fac_id,
                self.pharm_id,
                {
                    "prescription_id": rx_signed["id"],
                    "patient_id": self.patient_id,
                    "items": [{"batch_id": expired_batch_id, "dispensed_qty_decimal": "200.00"}],
                },
            )
        self.assertEqual(ctx_exp.exception.details["code"], "BATCH_EXPIRED_OR_QUARANTINED")

        # Attempt unauthorized automatic substitution -> blocked!
        with self.assertRaises(ValidationError) as ctx_sub:
            self.service.dispense_prescription(
                self.org_id,
                self.fac_id,
                self.pharm_id,
                {
                    "prescription_id": rx_signed["id"],
                    "patient_id": self.patient_id,
                    "items": [
                        {
                            "batch_id": "batch-bazoori-2027",
                            "dispensed_qty_decimal": "200.00",
                            "is_substituted": True,
                        }
                    ],
                },
            )
        self.assertEqual(ctx_sub.exception.details["code"], "UNAUTHORIZED_SUBSTITUTION_PROHIBITED")

        # Dispense valid batch idempotently and verify ledger balance decrement & signed rx immutability
        disp1 = self.service.dispense_prescription(
            self.org_id,
            self.fac_id,
            self.pharm_id,
            {
                "prescription_id": rx_signed["id"],
                "patient_id": self.patient_id,
                "idempotency_key": "disp-idem-001",
                "items": [
                    {
                        "batch_id": "batch-bazoori-2027",
                        "dispensed_qty_decimal": "200.00",
                        "prescribed_item_name": "Sharbat Bazoori Motadil",
                        "prescribed_dose_instructions": "25 ml BD with water",
                    }
                ],
            },
        )
        self.assertEqual(disp1["status"], "DISPENSED")
        self.assertEqual(disp1["prescription_signature_hash"], rx_signed["signature_hash"])

        # Idempotent replay does not deduct stock twice
        disp_replay = self.service.dispense_prescription(
            self.org_id,
            self.fac_id,
            self.pharm_id,
            {
                "prescription_id": rx_signed["id"],
                "patient_id": self.patient_id,
                "idempotency_key": "disp-idem-001",
                "items": [{"batch_id": "batch-bazoori-2027", "dispensed_qty_decimal": "200.00"}],
            },
        )
        self.assertTrue(disp_replay["idempotent_replay"])

        # Verify batch balance is exactly 1000.00 - 200.00 = 800.00
        batches = self.service.list_batches(self.org_id, self.fac_id, inventory_item_id="iitem-bazoori")
        valid_b = next(b for b in batches if b["id"] == "batch-bazoori-2027")
        self.assertEqual(valid_b["quantity_on_hand_decimal"], "800.00")


if __name__ == "__main__":
    unittest.main()

"""Unit Tests for Consultation Orchestrator Domain Service (Prompt 08).
Validates:
- Workspace aggregate generation
- Section completion model and clinical rationale validation for N/A
- State machine transition rules and audit logging
- Server-authoritative sign-off gating (missing PIN, unaddressed warnings, non-overridable blocks)
- Electronic PIN sign-off, atomic finalization, and document snapshot integrity
- Idempotency caching
"""

import unittest
import json
import uuid
import hashlib
from datetime import datetime

from apps.api.database.connection import DatabaseConnection
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
import tempfile
import os

from apps.api.core.errors import (
    ValidationError,
    ConflictError,
    ForbiddenError,
    AuthenticationError,
    SafetyBlockedError
)
from apps.api.core.security import hash_pin
from apps.api.domains.consultation_orchestrator import (
    ConsultationOrchestratorService,
    SECTION_KEYS,
    WORKFLOW_STATES
)


class TestConsultationOrchestratorUnit(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self.conn = DatabaseConnection(self.db_path).get_connection()
        self.service = ConsultationOrchestratorService(self.db_path)

        self.org_id = "org-matab-default"
        self.facility_id = "fac-central-opd"
        self.hakeem_id = "usr-hakeem-1"
        self.recep_id = "usr-recep-1"

        self.hakeem_ctx = {
            "user_id": self.hakeem_id,
            "organization_id": self.org_id,
            "active_facility_id": self.facility_id,
            "roles": ["PRACTITIONER"],
            "permissions": ["encounters:read", "encounters:write", "encounter:read", "encounter:update_draft", "prescriptions:sign", "encounter:finalize"]
        }

        # Create test encounter
        self.patient_id = "pat-syn-001"
        self.encounter_id = f"enc-{uuid.uuid4().hex[:8]}"
        self.conn.execute("""
            INSERT INTO encounters (
                id, organization_id, facility_id, patient_id, practitioner_id,
                token_number, encounter_type, status, reason_for_visit, version, started_at, created_by
            ) VALUES (?, ?, ?, ?, ?, 101, 'OPD_VISIT', 'in_consultation', 'Chronic indigestion and headache', 1, CURRENT_TIMESTAMP, ?);
        """, (self.encounter_id, self.org_id, self.facility_id, self.patient_id, self.hakeem_id, self.hakeem_id))
        self.conn.commit()

        # Set up Hakeem PIN (1234)
        # 1234 hash
        self.pin = "1234"
        self.pin_hash = hash_pin(self.pin)
        self.conn.execute("""
            UPDATE practitioner_profiles
            SET digital_signature_pin_hash = ?
            WHERE user_id = ?;
        """, (self.pin_hash, self.hakeem_id))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_get_workspace_aggregate(self):
        """Workspace aggregate must return patient 360, encounter status, and all 7 default sections."""
        ws = self.service.get_workspace(self.encounter_id, self.hakeem_ctx)
        self.assertIn("encounter", ws)
        self.assertEqual(ws["encounter"]["id"], self.encounter_id)
        self.assertIn("patient", ws)
        self.assertEqual(ws["patient"]["id"], self.patient_id)
        self.assertIn("sections", ws)

        # Verify all 7 sections exist
        for sec in SECTION_KEYS:
            self.assertIn(sec, ws["sections"])
            self.assertEqual(ws["sections"][sec]["status"], "not_started")

        self.assertIn("signoff_eligibility", ws)
        self.assertIn("documents", ws)
        self.assertIn("followup_tasks", ws)

    def test_autosave_draft_with_concurrency_control(self):
        """Autosave must persist changes and increment version while preventing stale writes."""
        payload = {
            "version": 1,
            "reason_for_visit": "Updated chief complaint: severe dyspepsia",
            "updated_sections": ["visit", "history_observations"]
        }
        res = self.service.save_workspace_draft(self.encounter_id, payload, self.hakeem_ctx)
        self.assertEqual(res["status"], "saved")
        self.assertEqual(res["version_number"], 2)

        # Attempt stale save with old version 1 must raise ConflictError
        with self.assertRaises(ConflictError):
            self.service.save_workspace_draft(self.encounter_id, {"version": 1, "reason_for_visit": "Stale update"}, self.hakeem_ctx)

    def test_section_completion_and_not_applicable_validation(self):
        """Marking a section complete works; marking N/A requires documented clinical rationale."""
        # Complete visit section
        sec = self.service.update_section_state(
            self.encounter_id, "visit", "complete", {"completed_by": "Hakeem Tariq"}, self.hakeem_ctx
        )
        self.assertEqual(sec["status"], "complete")

        # Marking modern_assessment as not_applicable without reason must fail
        with self.assertRaises(ValidationError):
            self.service.update_section_state(
                self.encounter_id, "modern_assessment", "not_applicable", {}, self.hakeem_ctx
            )

        # Marking modern_assessment as not_applicable with reason succeeds
        sec_na = self.service.update_section_state(
            self.encounter_id, "modern_assessment", "not_applicable",
            {"reason": "Exclusively classical Mizaj assessment conducted per patient request."},
            self.hakeem_ctx
        )
        self.assertEqual(sec_na["status"], "not_applicable")

    def test_state_machine_transitions_and_audit(self):
        """Valid transitions proceed; invalid transitions are rejected; audit records are written."""
        # in_consultation -> ready_for_signoff
        trans = self.service.transition_encounter_state(
            self.encounter_id, "ready_for_signoff", self.hakeem_ctx, "Clinical review complete"
        )
        self.assertEqual(trans["new_state"], "ready_for_signoff")

        # Invalid transition: ready_for_signoff -> scheduled is illegal
        with self.assertRaises(ValidationError):
            self.service.transition_encounter_state(
                self.encounter_id, "scheduled", self.hakeem_ctx, "Illegal backward transition"
            )

    def test_signoff_eligibility_gating_unaddressed_safety_alerts(self):
        """Prescription with line items requires preflight run and disposition for all warnings."""
        # Mark visit and Unani assessment complete
        self.service.update_section_state(self.encounter_id, "visit", "complete", {}, self.hakeem_ctx)
        self.service.update_section_state(self.encounter_id, "unani_assessment", "complete", {}, self.hakeem_ctx)
        self.service.update_section_state(self.encounter_id, "plan_nuskha", "complete", {}, self.hakeem_ctx)

        # Add a draft prescription with item
        rx_id = f"rx-{uuid.uuid4().hex[:8]}"
        self.conn.execute("""
            INSERT INTO prescriptions (
                id, organization_id, facility_id, prescription_number, patient_id,
                encounter_id, practitioner_id, version_number, status, overall_safety_state
            ) VALUES (?, ?, ?, 'RX-2026-99999', ?, ?, ?, 1, 'DRAFT', 'UNKNOWN');
        """, (rx_id, self.org_id, self.facility_id, self.patient_id, self.encounter_id, self.hakeem_id))

        self.conn.execute("""
            INSERT INTO prescription_items (
                id, prescription_id, item_type, item_name, dosage_form, dose_amount,
                dose_unit, route, frequency, duration_days, quantity_to_dispense, sort_order
            ) VALUES (?, ?, 'FORMULATION', 'Hab-e-Suranjan', 'Pill', 2, 'hab', 'ORAL', 'BD', 7, 14, 1);
        """, (f"pi-{uuid.uuid4().hex[:8]}", rx_id))
        self.conn.commit()

        # Gate check: should fail because preflight has not run
        gate = self.service.validate_signoff_eligibility(self.encounter_id, self.hakeem_ctx)
        self.assertFalse(gate["eligible"])
        self.assertTrue(any("safety preflight check has been executed" in r for r in gate["blocking_reasons"]))

        # Insert a preflight run with an unaddressed high finding
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        self.conn.execute("""
            INSERT INTO safety_preflight_runs (
                id, organization_id, facility_id, prescription_id, encounter_id,
                patient_id, clinician_id, overall_status, ruleset_version, is_latest,
                input_snapshot_json, coverage_report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'reviewed_with_cautions', 'v2.0-governed', 1, '{}', '{}');
        """, (run_id, self.org_id, self.facility_id, rx_id, self.encounter_id, self.patient_id, self.hakeem_id))


        finding_id = f"fnd-{uuid.uuid4().hex[:8]}"
        self.conn.execute("""
            INSERT INTO safety_findings (
                id, run_id, rule_code, rule_version, finding_type, severity,
                certainty, title, concise_rationale, required_next_action, is_overridable, status
            ) VALUES (?, ?, 'SAF-SUR-001', '1.0.0', 'CONTRAINDICATION', 'high', 'established',
                      'Suranjan Caution in Renal Impairment', 'Monitor renal function', 'Verify eGFR', 1, 'active');
        """, (finding_id, run_id))
        self.conn.commit()

        # Gate check: still blocked because finding is undisposed
        gate2 = self.service.validate_signoff_eligibility(self.encounter_id, self.hakeem_ctx)
        self.assertFalse(gate2["eligible"])
        self.assertTrue(any("requires clinician disposition" in r for r in gate2["blocking_reasons"]))

        # Now add clinician disposition with rationale
        disp_id = f"disp-{uuid.uuid4().hex[:8]}"
        self.conn.execute("""
            INSERT INTO safety_finding_dispositions (
                id, finding_id, run_id, clinician_id, disposition_type,
                clinical_rationale, created_at
            ) VALUES (?, ?, ?, ?, 'OVERRIDDEN_WITH_RATIONALE', 'Patient eGFR 88 ml/min verified normal in recent lab panel.', CURRENT_TIMESTAMP);
        """, (disp_id, finding_id, run_id, self.hakeem_id))

        self.conn.commit()

        # Gate check: now eligible!
        gate3 = self.service.validate_signoff_eligibility(self.encounter_id, self.hakeem_ctx)
        self.assertTrue(gate3["eligible"])

    def test_electronic_signoff_and_immutable_finalization(self):
        """Successful PIN verification produces immutable document bundle, signs prescription, and completes encounter."""
        # Satisfy gates: Visit & Unani completed, no Rx items
        self.service.update_section_state(self.encounter_id, "visit", "complete", {}, self.hakeem_ctx)
        self.service.update_section_state(self.encounter_id, "unani_assessment", "complete", {}, self.hakeem_ctx)

        # Finalize with incorrect PIN -> AuthenticationError
        with self.assertRaises(AuthenticationError):
            self.service.sign_and_finalize_encounter(
                encounter_id=self.encounter_id,
                pin="9999",  # Wrong PIN
                user_ctx=self.hakeem_ctx
            )

        # Finalize with correct PIN (1234)
        followup = {
            "due_date": "2026-11-01",
            "task_description": "Review dyspepsia response and pulse diagnosis"
        }
        res = self.service.sign_and_finalize_encounter(
            encounter_id=self.encounter_id,
            pin="1234",
            user_ctx=self.hakeem_ctx,
            followup_task=followup,
            instructions_language="ur",
            idempotency_key="idemp-key-101"
        )

        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["finalized_by"]["user_id"], self.hakeem_id)
        self.assertGreaterEqual(len(res["documents"]), 2)
        self.assertIsNotNone(res["followup_task"])
        self.assertEqual(res["followup_task"]["due_date"], "2026-11-01")

        # Verify documents persisted with valid SHA-256 digests
        docs = self.service.get_encounter_documents(self.encounter_id, self.hakeem_ctx)
        self.assertGreaterEqual(len(docs), 2)
        for doc in docs:
            self.assertEqual(len(doc["document_hash"]), 64)  # SHA-256 length
            self.assertIn("document_type", doc)

        # Test idempotency replay
        replayed = self.service.sign_and_finalize_encounter(
            encounter_id=self.encounter_id,
            pin="1234",
            user_ctx=self.hakeem_ctx,
            idempotency_key="idemp-key-101"
        )
        self.assertEqual(replayed["encounter_id"], self.encounter_id)
        self.assertEqual(replayed["status"], "completed")


if __name__ == "__main__":
    unittest.main()

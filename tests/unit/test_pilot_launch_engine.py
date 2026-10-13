"""
Unit Test Suite for Controlled Pilot Launch Domain Engine (Prompt 14)
ZAYVORA MATAB OS — Independent Standalone Product
"""

import os
import tempfile
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.pilot_launch import (
    PilotLaunchEngine,
    ScopeRestrictionError,
    EligibilityGateError,
)


class TestPilotLaunchEngine(unittest.TestCase):
    """Unit tests for PilotLaunchEngine domain capabilities."""

    @classmethod
    def setUpClass(cls):
        cls.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.db_path = cls.tmp_db.name
        cls.tmp_db.close()
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)
        cls.engine = PilotLaunchEngine(db_path=cls.db_path)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)

    def test_01_create_pilot_program_and_scope_versioning(self):
        """Verify program creation and scope versioning."""
        prog = self.engine.create_pilot_program(
            code="PILOT-TEST-01",
            name="Test Clinic Pilot Program",
            organization_id="org-matab-default",
            description="Unit test pilot",
            created_by="usr-admin-1"
        )
        self.assertIsNotNone(prog["id"])
        self.assertEqual(prog["status"], "DRAFT")

        # Declare scope version 1
        scope1 = self.engine.declare_scope_version(
            program_id=prog["id"],
            enabled_modules=["PATIENT_REGISTRY", "UNIFIED_CONSULTATION", "PRESCRIPTION_ENGINE"],
            disabled_modules=["ABDM_LIVE_SYNC", "CARRIER_SMS_LIVE"],
            permitted_roles=["CHIEF_TABIB", "TABIB", "PRACTITIONER"],
            permitted_facilities=["fac-central-opd"],
            user_id="usr-admin-1",
            approved_by_clinical_lead="usr-hakeem-1",
            approved_by_security_lead="usr-admin-1",
            approved_by_product_lead="usr-admin-1"
        )
        self.assertEqual(scope1["version_number"], 1)
        self.assertEqual(scope1["status"], "ACTIVE")
        self.assertIn("PATIENT_REGISTRY", scope1["enabled_modules"])

        # Declare scope version 2 (supersedes v1)
        scope2 = self.engine.declare_scope_version(
            program_id=prog["id"],
            enabled_modules=["PATIENT_REGISTRY", "UNIFIED_CONSULTATION", "PRESCRIPTION_ENGINE", "DISPENSARY_QUEUE"],
            disabled_modules=["ABDM_LIVE_SYNC"],
            permitted_roles=["CHIEF_TABIB", "TABIB", "PRACTITIONER", "DISPENSER"],
            permitted_facilities=["fac-central-opd"],
            user_id="usr-admin-1"
        )
        self.assertEqual(scope2["version_number"], 2)
        active_scope = self.engine.get_active_scope(prog["id"])
        self.assertEqual(active_scope["version_number"], 2)
        self.assertIn("DISPENSARY_QUEUE", active_scope["enabled_modules"])

    def test_02_enforce_pilot_scope_boundaries_and_rejections(self):
        """Verify server-side enforcement rejects disabled modules, un-enrolled facilities, and unauthorized roles."""
        prog_id = "plt-prog-2026-q4"

        # 1. Permitted action passes
        allowed = self.engine.enforce_pilot_scope(
            program_id=prog_id,
            facility_id="fac-central-opd",
            role_code="TABIB",
            module_code="PRESCRIPTION_ENGINE"
        )
        self.assertTrue(allowed)

        # 2. Disabled module fails closed
        with self.assertRaises(ScopeRestrictionError) as ctx:
            self.engine.enforce_pilot_scope(
                program_id=prog_id,
                facility_id="fac-central-opd",
                role_code="TABIB",
                module_code="ABDM_LIVE_SYNC"
            )
        self.assertIn("explicitly disabled", str(ctx.exception))

        # 3. Un-enrolled facility fails closed
        with self.assertRaises(ScopeRestrictionError) as ctx:
            self.engine.enforce_pilot_scope(
                program_id=prog_id,
                facility_id="fac-unregistered-clinic",
                role_code="TABIB",
                module_code="PRESCRIPTION_ENGINE"
            )
        self.assertIn("not enrolled", str(ctx.exception))

        # 4. Unauthorized role fails closed
        with self.assertRaises(ScopeRestrictionError) as ctx:
            self.engine.enforce_pilot_scope(
                program_id=prog_id,
                facility_id="fac-central-opd",
                role_code="UNAUTHORIZED_GUEST",
                module_code="PRESCRIPTION_ENGINE"
            )
        self.assertIn("not permitted", str(ctx.exception))

    def test_03_evaluate_eligibility_gate_and_activation(self):
        """Verify backend evaluation of eligibility gate."""
        prog_id = "plt-prog-2026-q4"
        elig = self.engine.evaluate_pilot_eligibility(prog_id)
        self.assertIn("eligible", elig)
        self.assertIn("gates", elig)
        self.assertGreaterEqual(len(elig["gates"]), 4)

        # Activate pilot program
        activated = self.engine.activate_pilot(prog_id, user_id="usr-admin-1")
        self.assertEqual(activated["status"], "ACTIVATED")
        self.assertIsNotNone(activated["actual_start_date"])

    def test_04_facility_onboarding_13_stage_checklist_progression(self):
        """Verify 13-stage onboarding checklist initialization and stage updates."""
        prog_id = "plt-prog-2026-q4"
        fac_id = "fac-central-opd"

        checklist = self.engine.get_facility_checklist(prog_id, fac_id)
        self.assertEqual(len(checklist), 13)
        self.assertEqual(checklist[0]["stage_code"], "1_ELIGIBILITY_CONFIRMED")
        self.assertEqual(checklist[12]["stage_code"], "13_FIRST_WEEK_REVIEW")

        # Update stage 9 (training completed)
        stage_9 = checklist[8]
        updated = self.engine.update_checklist_stage(
            checklist_id=stage_9["id"],
            status="COMPLETED",
            user_id="usr-admin-1",
            evidence_notes="All 4 staff certified with >85% scores."
        )
        self.assertEqual(updated["status"], "COMPLETED")
        self.assertEqual(updated["evidence_notes"], "All 4 staff certified with >85% scores.")

    def test_05_governed_data_migration_dry_run_vs_execute(self):
        """Verify DRY-RUN makes zero database writes, while EXECUTE imports clean records."""
        prog_id = "plt-prog-2026-q4"
        fac_id = "fac-central-opd"

        raw_records = [
            {"name": "Hakim Ajmal Khan Patient", "phone": "+91-9988776655", "gender": "MALE", "dob": "1990-01-01"},
            {"name": "Duplicate Test User", "phone": "+91-9876543210", "gender": "FEMALE", "dob": "1992-05-15"}, # existing phone in seed
            {"name": "", "phone": ""} # invalid
        ]

        # 1. DRY_RUN mode
        dry_result = self.engine.run_data_migration(
            program_id=prog_id,
            facility_id=fac_id,
            source_system="Legacy Register",
            source_authority_reference="AUTH-REF-001",
            raw_records=raw_records,
            user_id="usr-admin-1",
            mode="DRY_RUN"
        )
        self.assertEqual(dry_result["total_records_read"], 3)
        self.assertEqual(dry_result["records_migrated"], 0) # DRY-RUN does not write!
        self.assertEqual(dry_result["ambiguous_duplicates_flagged"], 1)
        self.assertEqual(dry_result["records_rejected"], 1)

        # 2. EXECUTE mode
        exec_result = self.engine.run_data_migration(
            program_id=prog_id,
            facility_id=fac_id,
            source_system="Legacy Register",
            source_authority_reference="AUTH-REF-001",
            raw_records=raw_records,
            user_id="usr-admin-1",
            mode="EXECUTE"
        )
        self.assertEqual(exec_result["records_migrated"], 1) # 1 clean record imported
        self.assertEqual(exec_result["ambiguous_duplicates_flagged"], 1)
        self.assertEqual(exec_result["records_rejected"], 1)

    def test_06_role_based_training_enrollment_and_scoring(self):
        """Verify staff training enrollment and passing vs failure thresholds."""
        prog_id = "plt-prog-2026-q4"
        fac_id = "fac-central-opd"

        enroll = self.engine.enroll_staff_for_training(
            program_id=prog_id,
            facility_id=fac_id,
            user_id="usr-hakeem-1",
            training_module_id="trn-mod-tabib-1"
        )
        self.assertEqual(enroll["status"], "ASSIGNED")

        # Passing score
        completed = self.engine.record_training_completion(
            enrollment_id=enroll["id"],
            score=90,
            scenario_acceptance_notes="Passed synthetic prescribing and safety override scenario.",
            certified_by_user_id="usr-admin-1"
        )
        self.assertEqual(completed["status"], "PASSED")
        self.assertEqual(completed["score"], 90)

        # Training matrix computation
        matrix = self.engine.get_facility_training_matrix(prog_id, fac_id)
        self.assertGreater(matrix["total_enrollments"], 0)
        self.assertGreater(matrix["completion_rate_percentage"], 0.0)

    def test_07_support_ticket_auto_routing_to_clinical_safety_queue(self):
        """Verify critical clinical safety tickets automatically clone into the governance queue."""
        prog_id = "plt-prog-2026-q4"
        fac_id = "fac-central-opd"

        # Create clinical safety incident ticket
        ticket = self.engine.create_support_ticket(
            program_id=prog_id,
            facility_id=fac_id,
            reporter_user_id="usr-hakeem-1",
            category="CLINICAL_SAFETY_INCIDENT",
            severity="SEV_1_CRITICAL",
            subject="Potential missing contraindication on Kuchla compound",
            safe_description="Clinician noted dosage advisory query in acute geriatric case."
        )
        self.assertEqual(ticket["category"], "CLINICAL_SAFETY_INCIDENT")
        self.assertEqual(ticket["severity"], "SEV_1_CRITICAL")

        # Verify incident appeared in clinical safety queue
        queue = self.engine.list_clinical_safety_queue(prog_id)
        self.assertGreater(len(queue), 0)
        inc = queue[0]
        self.assertEqual(inc["status"], "PENDING_REVIEW")

        # Resolve incident
        resolved = self.engine.resolve_clinical_safety_incident(
            incident_id=inc["id"],
            governance_action="MONOGRAPH_AMENDMENT",
            reviewer_user_id="usr-admin-1",
            notes="Clinical committee amended UPI monograph monograph advisory."
        )
        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(resolved["governance_action"], "MONOGRAPH_AMENDMENT")

    def test_08_stop_condition_trigger_containment_and_resolution(self):
        """Verify triggering stop condition pauses program without corrupting database."""
        prog_id = "plt-prog-2026-q4"

        stop_evt = self.engine.trigger_stop_condition(
            program_id=prog_id,
            condition_code="SAVE_FAILURE_LOOP",
            action_taken="PAUSE_PILOT_ALL",
            containment_actions=["HALT_NEW_CONSULTATIONS", "ACTIVATE_OFFLINE_PAPER_RX"],
            user_id="usr-admin-1",
            restart_criteria="Fix database contention and verify in staging"
        )
        self.assertEqual(stop_evt["condition_code"], "SAVE_FAILURE_LOOP")
        self.assertEqual(stop_evt["is_active"], 1)

        # Pilot program is now PAUSED
        prog = self.engine.get_pilot_program(prog_id)
        self.assertEqual(prog["status"], "PAUSED")

        # Actions are blocked under stop condition
        with self.assertRaises(ScopeRestrictionError):
            self.engine.enforce_pilot_scope(prog_id, "fac-central-opd", "TABIB", "PRESCRIPTION_ENGINE")

        # Resolve stop condition
        res = self.engine.resolve_stop_condition(
            event_id=stop_evt["id"],
            user_id="usr-admin-1",
            resolution_notes="Root cause patched and verified."
        )
        self.assertEqual(res["is_active"], 0)

    def test_09_operational_metrics_and_review_pack_generation(self):
        """Verify calculation of operational metrics and generation of review packs."""
        prog_id = "plt-prog-2026-q4"

        metrics = self.engine.calculate_pilot_metrics(prog_id)
        self.assertIn("training", metrics)
        self.assertIn("onboarding", metrics)
        self.assertIn("open_support_tickets", metrics)
        self.assertIn("clinical_safety_incidents", metrics)

        # Generate weekly review pack
        pack = self.engine.generate_review_pack(
            program_id=prog_id,
            review_type="WEEKLY",
            period_start="2026-10-13",
            period_end="2026-10-20",
            recommendation="CONTINUE_AS_PLANNED",
            prepared_by_user_id="usr-admin-1",
            approved_by_clinical_lead="usr-hakeem-1",
            approved_by_operations_lead="usr-admin-1"
        )
        self.assertIsNotNone(pack["id"])
        self.assertEqual(pack["recommendation"], "CONTINUE_AS_PLANNED")


if __name__ == "__main__":
    unittest.main()

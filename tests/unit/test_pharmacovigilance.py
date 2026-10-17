"""Unit tests for Clinical Safety Surveillance, Adverse Event Management & Pharmacovigilance Workflow.

Phase 27 validation for ZAYVORA MATAB OS.
Enforces non-negotiables:
1. Never fabricate safety events, exposures, causality, or outcomes.
2. Record reported events before evaluating causality (intake independent of attribution).
3. Temporal sequence is not causation; causality is an independently evaluated dimension.
4. Strict dimensional separation: reported facts, clinical confirmation, severity, seriousness,
   expectedness, causality, and reportability are distinct fields with separate ownership.
5. Never fabricate regulatory requirements: profiles disabled by default until verified by compliance staff.
6. No automatic regulatory submissions: requires authorized human approval and produces verifiable receipts.
7. No autonomous treatment advice: safety workflow does not independently cancel care plans.
8. Preserves verbatim original reporter narrative in original language and script.
9. Privacy-protective redaction of reporter contact details.
"""

import os
import unittest
import tempfile
import sqlite3
import uuid
import json
from datetime import datetime

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.pharmacovigilance import PharmacovigilanceEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


class TestPharmacovigilanceEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_pv.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = PharmacovigilanceEngine(cls.db_path)

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin = cur.fetchone()
        cls.admin_id = admin["id"]
        cls.org_id = admin["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.fac_id = cur.fetchone()["id"]

        cur.execute("SELECT id FROM patients WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        cls.patient_id = cur.fetchone()["id"]

        conn.close()

        cls.admin_user = {
            "user_id": cls.admin_id,
            "roles": ["ORG_ADMIN"],
            "permissions": ["safety:read", "safety:record", "safety:triage", "safety:assess", "safety:report", "safety:manage"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

        cls.hakeem_user = {
            "user_id": "usr-hakeem-1",
            "roles": ["PHYSICIAN_HAKEEM"],
            "permissions": ["safety:read", "safety:record", "safety:triage", "safety:assess"],
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
        }

    # --------------------------------------------------------------------------
    # Test 1: Intake Preserves Verbatim Narrative and Redacts Reporter Contact
    # --------------------------------------------------------------------------
    def test_case_intake_preserves_narrative_and_redacts_contact(self):
        narrative = "مریض نے جوارش کمونی کھانے کے بعد پیٹ میں شدید مروڑ اور خارش کی شکایت کی (Patient complained of colic and pruritus after taking Jawarish Kamuni)."
        case_data = {
            "case_type": "SUSPECTED_ADVERSE_REACTION",
            "intake_channel": "DIRECT_CLINICIAN_ENTRY",
            "reporter_type": "PATIENT",
            "reporter_name": "Tariq Mahmood",
            "reporter_contact": {
                "phone": "+91 98765 43210",
                "email": "tariq.mahmood@example.com"
            },
            "original_narrative": narrative,
            "original_language": "ur",
            "patient_id": self.patient_id,
            "events": [
                {
                    "event_description_reported": "Severe abdominal cramping and generalized itching",
                    "onset_date": "2026-10-10",
                    "onset_date_precision": "DAY"
                }
            ],
            "suspected_exposures": [
                {
                    "reported_product_name": "Jawarish Kamuni Kabir",
                    "batch_lot_number": "BATCH-JK-2026-09",
                    "exposure_role": "SUSPECTED"
                }
            ]
        }

        case = self.engine.create_safety_case(case_data, self.hakeem_user)
        self.assertIsNotNone(case["id"])
        self.assertTrue(case["case_number"].startswith("PV-"))
        self.assertEqual(case["original_narrative"], narrative)
        self.assertEqual(case["case_state"], "INTAKE_COMPLETE")

        # Check privacy masking for clinician viewer
        contact = case["reporter_contact"]
        self.assertIn("***@", contact["email"])
        self.assertTrue(contact["phone"].startswith("+91") and "****" in contact["phone"])

        # Fetch as Admin with safety:manage permission -> should see unmasked or permitted details
        admin_view = self.engine.get_safety_case(case["id"], self.admin_user)
        self.assertIn("@", admin_view["reporter_contact"]["email"])

    # --------------------------------------------------------------------------
    # Test 2: Emergency Red Flag Triggering and Escalation
    # --------------------------------------------------------------------------
    def test_emergency_red_flag_triggers_escalation(self):
        emergency_narrative = "Patient developed acute anaphylaxis and severe respiratory failure within 15 minutes of ingesting decoction."
        case_data = {
            "case_type": "ADVERSE_EVENT",
            "intake_channel": "PATIENT_PORTAL",
            "reporter_type": "PATIENT",
            "original_narrative": emergency_narrative,
            "patient_id": self.patient_id,
        }

        case = self.engine.create_safety_case(case_data, self.hakeem_user)
        self.assertEqual(case["urgency_level"], "EMERGENCY")
        self.assertEqual(case["emergency_escalated"], 1)
        self.assertEqual(case["emergency_escalated_to"], "EMERGENCY_CLINICAL_COORDINATOR")
        self.assertIsNotNone(case["emergency_escalated_at"])

    # --------------------------------------------------------------------------
    # Test 3: Discrete Event and Exposure Addition
    # --------------------------------------------------------------------------
    def test_add_events_and_suspected_exposures(self):
        case = self.engine.create_safety_case({
            "case_type": "ADVERSE_EVENT",
            "intake_channel": "FOLLOW_UP_OUTREACH",
            "reporter_type": "FAMILY_CAREGIVER",
            "original_narrative": "Mild nausea reported by patient's daughter.",
            "patient_id": self.patient_id,
        }, self.hakeem_user)

        event = self.engine.add_safety_event(case["id"], {
            "event_description_reported": "Nausea following evening dose",
            "onset_date": "2026-10-12",
            "onset_date_precision": "EXACT_TIMESTAMP",
            "course_status": "ACTIVE",
            "clinical_confirmation_state": "SUSPECTED_UNCONFIRMED"
        }, self.hakeem_user)
        self.assertEqual(event["event_description_reported"], "Nausea following evening dose")
        self.assertEqual(event["clinical_confirmation_state"], "SUSPECTED_UNCONFIRMED")

        exp = self.engine.add_suspected_exposure(case["id"], {
            "reported_product_name": "Sharbat Bazoori Motadil",
            "exposure_role": "SUSPECTED",
            "identity_resolution_state": "FREE_TEXT_ONLY",
            "batch_lot_number": "SBM-LOT-441"
        }, self.hakeem_user)
        self.assertEqual(exp["reported_product_name"], "Sharbat Bazoori Motadil")
        self.assertEqual(exp["identity_resolution_state"], "FREE_TEXT_ONLY")

    # --------------------------------------------------------------------------
    # Test 4: Multidimensional Assessment Separation & Causality Independence
    # --------------------------------------------------------------------------
    def test_multidimensional_assessment_separation(self):
        case = self.engine.create_safety_case({
            "case_type": "SUSPECTED_ADVERSE_REACTION",
            "intake_channel": "DIRECT_CLINICIAN_ENTRY",
            "reporter_type": "PHYSICIAN_HAKEEM",
            "original_narrative": "Patient experienced urticarial rash 2 hours after first dose of formulation.",
            "patient_id": self.patient_id,
            "events": [{"event_description_reported": "Urticarial rash", "onset_date": "2026-10-11"}],
            "suspected_exposures": [{"reported_product_name": "Majun Dabeedul Ward"}]
        }, self.hakeem_user)

        # 1. Clinical Confirmation
        a_conf = self.engine.record_assessment(case["id"], {
            "assessment_dimension": "CLINICAL_CONFIRMATION",
            "assessment_value": "CLINICIAN_CONFIRMED",
            "method_or_scale_ref": "PHYSICAL_EXAMINATION",
            "rationale": "Dermatologic examination revealed erythematous raised wheals."
        }, self.hakeem_user)
        self.assertEqual(a_conf["assessment_dimension"], "CLINICAL_CONFIRMATION")
        self.assertEqual(a_conf["assessment_value"], "CLINICIAN_CONFIRMED")

        # 2. Severity
        a_sev = self.engine.record_assessment(case["id"], {
            "assessment_dimension": "SEVERITY",
            "assessment_value": "MODERATE",
            "method_or_scale_ref": "HARTWIG_SEVERITY",
            "rationale": "Discomfort requiring oral antihistamine administration."
        }, self.hakeem_user)
        self.assertEqual(a_sev["assessment_value"], "MODERATE")

        # 3. Seriousness
        a_ser = self.engine.record_assessment(case["id"], {
            "assessment_dimension": "SERIOUSNESS",
            "assessment_value": "NON_SERIOUS",
            "method_or_scale_ref": "ICH_E2A_SERIOUSNESS",
            "rationale": "No hospitalization, disability, or life-threatening threat."
        }, self.hakeem_user)
        self.assertEqual(a_ser["assessment_value"], "NON_SERIOUS")

        # 4. Expectedness
        a_exp = self.engine.record_assessment(case["id"], {
            "assessment_dimension": "EXPECTEDNESS",
            "assessment_value": "UNEXPECTED_UNLABELED",
            "method_or_scale_ref": "UNANI_PHARMACOPOEIA_MONOGRAPH",
            "rationale": "Urticaria is not a known labeled adverse reaction for Majun Dabeedul Ward."
        }, self.hakeem_user)
        self.assertEqual(a_exp["assessment_value"], "UNEXPECTED_UNLABELED")

        # 5. Independent Causality Assessment
        a_caus = self.engine.record_assessment(case["id"], {
            "assessment_dimension": "CAUSALITY",
            "assessment_value": "PROBABLE",
            "method_or_scale_ref": "WHO_UMC",
            "rationale": "Clear temporal sequence, positive dechallenge, no concomitant medicines."
        }, self.hakeem_user)
        self.assertEqual(a_caus["assessment_value"], "PROBABLE")

        # Verify case advanced to CAUSALITY_EVALUATED
        updated_case = self.engine.get_safety_case(case["id"], self.hakeem_user)
        self.assertEqual(updated_case["case_state"], "CAUSALITY_EVALUATED")

        # Rejection of invalid dimension or invalid value
        with self.assertRaises(ValidationError):
            self.engine.record_assessment(case["id"], {
                "assessment_dimension": "INVALID_DIMENSION",
                "assessment_value": "PROBABLE",
                "method_or_scale_ref": "WHO_UMC",
                "rationale": "Invalid"
            }, self.hakeem_user)

    # --------------------------------------------------------------------------
    # Test 5: Assessment Review and Verification
    # --------------------------------------------------------------------------
    def test_assessment_review_workflow(self):
        case = self.engine.create_safety_case({
            "case_type": "ADVERSE_EVENT",
            "intake_channel": "DIRECT_CLINICIAN_ENTRY",
            "reporter_type": "PHYSICIAN_HAKEEM",
            "original_narrative": "Mild headache following medicine.",
            "patient_id": self.patient_id,
        }, self.hakeem_user)

        a_caus = self.engine.record_assessment(case["id"], {
            "assessment_dimension": "CAUSALITY",
            "assessment_value": "POSSIBLE",
            "method_or_scale_ref": "NARANJO",
            "rationale": "Score 4 (temporal association present, but underlying sinus congestion also noted)."
        }, self.hakeem_user)

        reviewed = self.engine.review_assessment(a_caus["id"], {
            "review_status": "VERIFIED",
            "rationale": "Senior safety reviewer concurs with score of 4."
        }, self.admin_user)
        self.assertEqual(reviewed["review_status"], "VERIFIED")

    # --------------------------------------------------------------------------
    # Test 6: Triage and Follow-up Task Tracking
    # --------------------------------------------------------------------------
    def test_triage_and_follow_up_tasks(self):
        case = self.engine.create_safety_case({
            "case_type": "ADVERSE_EVENT",
            "intake_channel": "TELEMEDICINE",
            "reporter_type": "PATIENT",
            "original_narrative": "Felt dizzy after taking herbs.",
            "patient_id": self.patient_id,
        }, self.hakeem_user)

        triaged = self.engine.update_triage(case["id"], {
            "urgency_level": "EXPEDITED",
            "normalized_summary": "Transient postural dizziness following herbal ingestion."
        }, self.hakeem_user)
        self.assertEqual(triaged["urgency_level"], "EXPEDITED")
        self.assertEqual(triaged["normalized_summary"], "Transient postural dizziness following herbal ingestion.")

        # Create follow-up task
        task = self.engine.create_follow_up_task(case["id"], {
            "required_field_or_query": "Obtain baseline blood pressure and concomitant antihypertensive history.",
            "assigned_role": "HAKEEM_CLINICIAN",
            "due_date": "2026-10-15"
        }, self.hakeem_user)
        self.assertEqual(task["status"], "PENDING")
        self.assertEqual(task["attempts_count"], 0)

        # Log attempt
        attempted = self.engine.record_follow_up_attempt(task["id"], {
            "status": "COMPLETED",
            "completion_notes": "Patient contacted. BP was 110/70. Patient is taking amlodipine."
        }, self.hakeem_user)
        self.assertEqual(attempted["status"], "COMPLETED")
        self.assertEqual(attempted["attempts_count"], 1)

    # --------------------------------------------------------------------------
    # Test 7: Duplicate Case Linking Without Auto-Merge
    # --------------------------------------------------------------------------
    def test_case_deduplication_linking_never_auto_merges(self):
        case1 = self.engine.create_safety_case({
            "case_type": "SUSPECTED_ADVERSE_REACTION",
            "intake_channel": "PATIENT_PORTAL",
            "reporter_type": "PATIENT",
            "original_narrative": "Rash on arms after taking Khamira Gaozaban.",
            "patient_id": self.patient_id,
        }, self.hakeem_user)

        case2 = self.engine.create_safety_case({
            "case_type": "SUSPECTED_ADVERSE_REACTION",
            "intake_channel": "DIRECT_CLINICIAN_ENTRY",
            "reporter_type": "PHYSICIAN_HAKEEM",
            "original_narrative": "Clinician report: Patient presented with maculopapular rash on arms.",
            "patient_id": self.patient_id,
        }, self.hakeem_user)

        link = self.engine.link_cases(case1["id"], case2["id"], {
            "relationship_type": "CONFIRMED_DUPLICATE",
            "rationale": "Same patient encounter and reaction reported independently via portal and clinician visit."
        }, self.admin_user)

        self.assertEqual(link["relationship_type"], "CONFIRMED_DUPLICATE")

        # Both cases remain intact with separate IDs
        c1_fetch = self.engine.get_safety_case(case1["id"], self.hakeem_user)
        c2_fetch = self.engine.get_safety_case(case2["id"], self.hakeem_user)
        self.assertIsNotNone(c1_fetch["id"])
        self.assertIsNotNone(c2_fetch["id"])
        self.assertEqual(c1_fetch["duplicate_review_state"], "LINKED_AS_CHILD")
        self.assertEqual(len(c1_fetch["case_links"]), 1)

    # --------------------------------------------------------------------------
    # Test 8: Regulatory Profiles Disabled by Default Blocks Authorization
    # --------------------------------------------------------------------------
    def test_regulatory_profile_disabled_by_default_blocks_authorization(self):
        profiles = self.engine.list_regulatory_profiles("IN")
        self.assertTrue(len(profiles) > 0)
        pvpi_prof = profiles[0]
        self.assertEqual(pvpi_prof["is_active"], 0)  # Must be disabled by default

        case = self.engine.create_safety_case({
            "case_type": "SUSPECTED_ADVERSE_REACTION",
            "intake_channel": "DIRECT_CLINICIAN_ENTRY",
            "reporter_type": "PHYSICIAN_HAKEEM",
            "original_narrative": "Adverse reaction report for regulatory compliance check.",
            "patient_id": self.patient_id,
            "events": [{"event_description_reported": "Severe nausea", "onset_date": "2026-10-10"}],
            "suspected_exposures": [{"reported_product_name": "Itrifal Kishneezi"}]
        }, self.hakeem_user)

        # Record causality to satisfy profile requirements
        self.engine.record_assessment(case["id"], {
            "assessment_dimension": "CAUSALITY",
            "assessment_value": "POSSIBLE",
            "method_or_scale_ref": "WHO_UMC",
            "rationale": "Plausible time window"
        }, self.hakeem_user)

        # Build report package
        pkg = self.engine.build_report_package(case["id"], pvpi_prof["id"], self.admin_user)
        self.assertEqual(pkg["validation_status"], "VALID")
        self.assertIsNotNone(pkg["payload_manifest_hash"])

        # Attempting to authorize must fail because profile is inactive
        with self.assertRaises(ForbiddenError):
            self.engine.authorize_submission(pkg["id"], {}, self.admin_user)

    # --------------------------------------------------------------------------
    # Test 9: Profile Verification, Authorization, and Dispatch with Verifiable Receipt
    # --------------------------------------------------------------------------
    def test_regulatory_profile_activation_and_submission_receipt(self):
        # 1. Compliance officer verifies and activates profile
        profiles = self.engine.list_regulatory_profiles("PK")
        drap_prof = profiles[0]
        verified_prof = self.engine.verify_and_activate_profile(drap_prof["id"], {}, self.admin_user)
        self.assertEqual(verified_prof["is_active"], 1)

        case = self.engine.create_safety_case({
            "case_type": "SUSPECTED_ADVERSE_REACTION",
            "intake_channel": "DIRECT_CLINICIAN_ENTRY",
            "reporter_type": "PHYSICIAN_HAKEEM",
            "original_narrative": "Adverse reaction report for DRAP transmission.",
            "patient_id": self.patient_id,
            "events": [{"event_description_reported": "Skin eruption", "onset_date": "2026-10-09"}],
            "suspected_exposures": [{"reported_product_name": "Hab-e-Suranjan"}]
        }, self.hakeem_user)

        # Record required seriousness determination
        self.engine.record_assessment(case["id"], {
            "assessment_dimension": "SERIOUSNESS",
            "assessment_value": "NON_SERIOUS",
            "method_or_scale_ref": "ICH_E2A_SERIOUSNESS",
            "rationale": "No inpatient hospitalization required."
        }, self.hakeem_user)

        pkg = self.engine.build_report_package(case["id"], drap_prof["id"], self.admin_user)
        self.assertEqual(pkg["validation_status"], "VALID")

        # 2. Authorize submission
        auth_sub = self.engine.authorize_submission(pkg["id"], {}, self.admin_user)
        self.assertEqual(auth_sub["submission_status"], "AUTHORIZED")

        # 3. Dispatch submission -> genuine verifiable cryptographic receipt
        dispatched = self.engine.dispatch_submission(pkg["id"], {}, self.admin_user)
        self.assertEqual(dispatched["submission_status"], "ACKNOWLEDGED")
        self.assertTrue(dispatched["transaction_ref"].startswith("PV-RECEIPT-"))
        self.assertIsNotNone(dispatched["acknowledgement_artifact"])

        updated_case = self.engine.get_safety_case(case["id"], self.hakeem_user)
        self.assertEqual(updated_case["case_state"], "SUBMITTED")

    # --------------------------------------------------------------------------
    # Test 10: Pharmacovigilance Signals Aggregation and Review
    # --------------------------------------------------------------------------
    def test_pharmacovigilance_signals_aggregation_and_review(self):
        sig1 = self.engine.create_or_update_signal({
            "product_identifier": "PROD-HAB-SURANJAN",
            "reaction_term": "Gastric irritation",
            "case_increment": 1,
            "clinical_justification": "Colchicum component known to cause GI irritation if untitrated."
        }, self.admin_user)
        self.assertEqual(sig1["case_count"], 1)

        # Increment signal
        sig2 = self.engine.create_or_update_signal({
            "product_identifier": "PROD-HAB-SURANJAN",
            "reaction_term": "Gastric irritation",
            "case_increment": 2
        }, self.admin_user)
        self.assertEqual(sig2["case_count"], 3)

        # Review signal
        reviewed = self.engine.review_signal(sig2["id"], {
            "evaluation_status": "MONITORING",
            "clinical_justification": "Known expected dose-dependent effect. Recommend review of patient Mudabbar processing adherence."
        }, self.admin_user)
        self.assertEqual(reviewed["evaluation_status"], "MONITORING")


if __name__ == "__main__":
    unittest.main()

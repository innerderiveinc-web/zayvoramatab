"""
Integration Tests for Enterprise Clinical Safety Case, Hazard Analysis & Safety Control Verification APIs
ZAYVORA MATAB OS — Phase 48
"""

import os
import json
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestClinicalSafetyApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_safety_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Admin login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
        }

        # Authenticate Hakeem / Clinical Safety Officer
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/auth/login",
            {"Content-Type": "application/json"},
            {},
            json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1",
            cls.db_path,
        )
        assert status == 200, f"Hakeem login failed: {body}"
        hakeem_data = json.loads(body.decode("utf-8"))
        cls.hakeem_token = hakeem_data["token"]
        cls.hakeem_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.hakeem_token}",
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_clinical_safety_summary_api(self):
        """GET /api/v1/safety-case/summary returns executive metrics."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/safety-case/summary", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("summary", data)
        self.assertGreaterEqual(data["summary"]["intended_uses_count"], 1)

    def test_02_intended_use_api(self):
        """POST and GET /api/v1/safety-case/intended-use."""
        payload = {
            "scope_code": "IU-INTEGRATION-TEST-001",
            "title": "Unani Herbal Dispensing & Batch Verification Scope",
            "intended_users": ["Licensed Pharmacist", "Dispensary Technician"],
            "clinical_purposes": ["FEFO batch tracking", "Schedule E(1) Mudabbar batch validation"],
            "excluded_uses": ["Compounding unapproved proprietary drugs"],
            "clinician_authority_level": "EXCLUSIVE_HUMAN_SIGN_OFF",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/intended-use",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        created_id = data["intended_use"]["id"]

        # Fetch detail
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/safety-case/intended-use/{created_id}",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        fetched = json.loads(body.decode("utf-8"))["intended_use"]
        self.assertEqual(fetched["scope_code"], "IU-INTEGRATION-TEST-001")

    def test_03_hazards_api(self):
        """POST /api/v1/safety-case/hazards creates new clinical hazard."""
        payload = {
            "hazard_code": "HAZ-INT-ALLERGY-001",
            "intended_use_id": "iu-rx-001",
            "title": "Prescribing Known Botanical Allergen Without Cross-Check",
            "workflow_scope": "PRESCRIPTION_SIGNING",
            "initiating_cause": "Practitioner omits reviewing patient allergy flags before adding formulation",
            "hazardous_state": "Dispensing allergen (e.g. Asal/Honey or Roghan-e-Badam) to sensitized patient",
            "clinical_consequence": "Anaphylaxis, severe urticaria, respiratory distress, or angioedema",
            "affected_population": "ALLERGIC_PATIENTS",
            "severity_tier": "CRITICAL",
            "lifecycle_status": "draft",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/hazards",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["hazard"]["hazard_code"], "HAZ-INT-ALLERGY-001")

    def test_04_hazard_status_clinical_review_api(self):
        """POST /api/v1/safety-case/hazards/{id}/status enforces Clinical Safety Officer authority."""
        # Non-clinical admin attempt to accept residual risk should fail with 403
        admin_review_payload = {
            "new_status": "accepted_for_defined_scope",
            "justification": "Admin attempted bypass without clinical credentials.",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/hazards/haz-int-allergy-001/status",
            self.admin_headers,
            {},
            json.dumps(admin_review_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 403)

        # Authorized Tabib / Hakeem review succeeds
        hakeem_review_payload = {
            "new_status": "accepted_for_defined_scope",
            "justification": "Allergy preflight crosswalk blocks signing deterministically when patient allergy profile matches formulation ingredients.",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/hazards/haz-int-allergy-001/status",
            self.hakeem_headers,
            {},
            json.dumps(hakeem_review_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["hazard"]["lifecycle_status"], "accepted_for_defined_scope")

    def test_05_safety_requirements_api(self):
        """POST and GET /api/v1/safety-case/requirements."""
        payload = {
            "hazard_id": "haz-int-allergy-001",
            "req_code": "SR-INT-ALLERGY-001",
            "title": "Preflight Patient Botanical Allergy Intersection Hard Stop",
            "requirement_type": "PREVENTIVE",
            "specification_statement": "The prescription preflight validator MUST match formulation constituents against active patient allergies and halt signing on any positive match.",
            "enforcement_code_path": "apps.api.domains.prescriptions.PrescriptionEngine._validate_allergies",
            "test_suite_reference": "tests.unit.test_prescriptions.TestPrescriptionPreflight.test_documented_allergy_rejected",
            "verification_status": "PLANNED",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/requirements",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["requirement"]["req_code"], "SR-INT-ALLERGY-001")

    def test_06_control_verifications_api(self):
        """POST /api/v1/safety-case/verifications records automated test execution evidence."""
        payload = {
            "requirement_id": "sr-int-allergy-001",
            "test_suite_name": "tests.unit.test_prescriptions.TestPrescriptionPreflight.test_documented_allergy_rejected",
            "status": "PASS",
            "evidence_summary": "Verified fail-closed rejection when honey allergy is present in patient profile.",
            "execution_duration_ms": 45,
            "environment": "ISOLATED_SYNTHETIC",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/verifications",
            self.hakeem_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["verification"]["status"], "PASS")

        # Verify requirement status is updated to VERIFIED_IN_TEST
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/safety-case/requirements/sr-int-allergy-001",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        req_data = json.loads(body.decode("utf-8"))["requirement"]
        self.assertEqual(req_data["verification_status"], "VERIFIED_IN_TEST")

    def test_07_clinical_safety_cases_api(self):
        """POST /api/v1/safety-case/cases and review approval."""
        payload = {
            "case_code": "CSC-INT-ALLERGY-V1",
            "title": "Clinical Safety Case for Patient Botanical Allergy Preflight",
            "workflow_scope": "PRESCRIPTION_SIGNING",
            "target_release_version": "v1.0.0",
            "claim_statement": "The Prescription Engine deterministically detects and halts signing for documented patient allergies.",
            "argument_narrative": "Claim G1: Patient allergy database lookup executes synchronously before PIN prompt. Claim G2: No override mechanism permitted for anaphylactic triggers.",
            "approval_status": "DRAFT",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/cases",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        created_case = json.loads(body.decode("utf-8"))["safety_case"]

        # Review and approve with Hakeem clinical credentials
        review_payload = {
            "new_status": "APPROVED_FOR_SCOPE",
            "clinical_rationale": "Verified allergy preflight integration with verified test evidence.",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/safety-case/cases/{created_case['id']}/review",
            self.hakeem_headers,
            {},
            json.dumps(review_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        reviewed_case = json.loads(body.decode("utf-8"))["safety_case"]
        self.assertEqual(reviewed_case["approval_status"], "APPROVED_FOR_SCOPE")

    def test_08_incidents_and_near_miss_api(self):
        """POST and triage /api/v1/safety-case/incidents."""
        payload = {
            "incident_code": "INC-INT-PREFLIGHT-001",
            "workflow_scope": "PRESCRIPTION_SIGNING",
            "incident_type": "NEAR_MISS",
            "severity": "MEDIUM",
            "sanitized_description": "Practitioner encountered ambiguous posology warning label for Sharbat Bazoori Motadil.",
            "linked_hazard_id": "haz-rx-001",
            "containment_action": "Practitioner adjusted dose downward safely.",
            "corrective_action_plan": "Clarify posology guidelines in formulation tooltip.",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/incidents",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        inc_id = json.loads(body.decode("utf-8"))["incident"]["id"]

        # Triage and close
        triage_payload = {
            "corrective_action_status": "VERIFIED_CLOSED",
            "containment_action": "Tooltip updated with dosage ceiling.",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/safety-case/incidents/{inc_id}/triage",
            self.hakeem_headers,
            {},
            json.dumps(triage_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        triaged = json.loads(body.decode("utf-8"))["incident"]
        self.assertEqual(triaged["corrective_action_status"], "VERIFIED_CLOSED")

    def test_09_release_gate_evaluation_api(self):
        """POST /api/v1/safety-case/release-gates/evaluate enforces fail-closed gates."""
        payload = {
            "target_release_version": "v1.0.0",
            "workflow_scope": "PRESCRIPTION_SIGNING",
            "safety_case_id": "csc-rx-001",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/release-gates/evaluate",
            self.hakeem_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertEqual(data["evaluation"]["gate_verdict"], "PASS")

        # List release gate evaluations
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/safety-case/release-gates",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        gate_list = json.loads(body.decode("utf-8"))["evaluations"]
        self.assertGreaterEqual(len(gate_list), 1)

    def test_10_traceability_and_audit_api(self):
        """GET /api/v1/safety-case/traceability and POST /api/v1/safety-case/audit/verify."""
        # Traceability
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/safety-case/traceability?workflow_scope=PRESCRIPTION_SIGNING",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        matrix = json.loads(body.decode("utf-8"))["matrix"]
        self.assertGreaterEqual(matrix["total_hazards_traced"], 1)

        # Audit Integrity Verification
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/safety-case/audit/verify",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        verification = json.loads(body.decode("utf-8"))["integrity_verification"]
        self.assertTrue(verification["is_valid"])
        self.assertEqual(verification["status"], "VERIFIED_INTACT")


if __name__ == "__main__":
    unittest.main()

"""
Integration Tests for Enterprise Threat Modeling, Abuse-Case Analysis & Secure SDLC APIs.
ZAYVORA MATAB OS — Phase 47
"""

import os
import json
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestThreatModelingApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_tm_api.db")
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
        assert status == 200, f"Login failed: {body}"
        admin_data = json.loads(body.decode("utf-8"))
        cls.admin_token = admin_data["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.admin_token}",
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_threat_modeling_summary_api(self):
        """GET /api/v1/threat-modeling/dashboard-summary returns consolidated KPIs."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/threat-modeling/dashboard-summary", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertIn("summary", data)
        self.assertGreaterEqual(data["summary"]["total_threat_models"], 1)

    def test_02_threat_models_api(self):
        """GET and POST /api/v1/threat-modeling/models."""
        model_payload = {
            "model_code": "TM-INT-INTEROP-001",
            "title": "ABDM FHIR Bridge & Gateway Threat Model",
            "subsystem_scope": "INTEROPERABILITY_ABDM_FHIR",
            "repository_revision": "HEAD",
            "deployment_version": "v1.0.0",
            "owner_role": "Interoperability Security Architect",
            "assumptions": ["Mutual TLS active on gateway", "National NRCeS directory verified"],
            "exclusions": ["Direct unauthenticated third-party webhook push"],
            "dependencies": ["abdm_consent_requests", "interop_transfer_outbox"],
            "lifecycle_state": "draft",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/models",
            self.admin_headers,
            {},
            json.dumps(model_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        model_id = data["model"]["id"]

        # GET models list
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/threat-modeling/models", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        list_data = json.loads(body.decode("utf-8"))
        self.assertGreaterEqual(list_data["count"], 2)

        # GET single model details
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/threat-modeling/models/{model_id}", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

    def test_03_transition_model_state_api(self):
        """POST /api/v1/threat-modeling/models/{id}/transition."""
        payload = {"new_state": "discovery", "review_notes": "Initial threat discovery session complete."}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/models/tm-cds-001/transition",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["model"]["lifecycle_state"], "discovery")

        # Transition back to approved_for_scope
        payload = {"new_state": "approved_for_scope", "review_notes": "Re-approved for production scope."}
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/models/tm-cds-001/transition",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)

    def test_04_trust_boundaries_api(self):
        """GET and POST /api/v1/threat-modeling/trust-boundaries."""
        tb_payload = {
            "model_id": "tm-cds-001",
            "boundary_name": "API Service <-> SQLite DB File Storage",
            "source_actor_or_component": "Python Domain Services",
            "destination_component": "SQLite Embedded Engine",
            "data_classification": "TIER_2_PHI",
            "protocol_or_interface": "C_ABI_SQLITE3",
            "auth_mechanism": "OS_FILE_PERMISSIONS",
            "encryption_status": "REST_AT_FILESYSTEM",
            "evidence_status": "verified_in_code",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/trust-boundaries",
            self.admin_headers,
            {},
            json.dumps(tb_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])

        # GET trust boundaries
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/threat-modeling/trust-boundaries", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

    def test_05_abuse_cases_api(self):
        """GET and POST /api/v1/threat-modeling/abuse-cases."""
        case_payload = {
            "model_id": "tm-cds-001",
            "threat_code": "TAC-INT-001",
            "title": "Attacker Injects Arbitrary SQL in Patient Demographic Query",
            "methodology": "STRIDE_PLUS_CLINICAL_HAZARD",
            "threat_class": "TAMPERING",
            "actor_type": "AUTHENTICATED_USER",
            "target_asset": "patients",
            "attack_path_summary": "User supplies malformed search query with SQL syntax to bypass authorization filters.",
            "clinical_safety_hazard": "DIAGNOSTIC_TAMPERING_MISROUTING",
            "severity": "CRITICAL",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/abuse-cases",
            self.admin_headers,
            {},
            json.dumps(case_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        case_id = data["abuse_case"]["id"]

        # Transition status
        trans_payload = {"new_status": "verified_mitigated", "notes": "Parameterized queries verified in all domains with automated unit tests."}
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/threat-modeling/abuse-cases/{case_id}/transition",
            self.admin_headers,
            {},
            json.dumps(trans_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)

    def test_06_testable_controls_api(self):
        """GET and POST /api/v1/threat-modeling/controls."""
        ctl_payload = {
            "threat_id": "tac-cds-001",
            "control_code": "CTL-INT-001",
            "title": "Strict Parametric SQL Binding Validator",
            "control_type": "PREVENTIVE",
            "enforcement_code_path": "apps.api.domains.security_posture.EnterpriseSecurityPostureEngine.run_sql_parameterization_scan",
            "test_suite_reference": "tests.unit.test_security_posture.TestSecurityPosture.test_sql_parameterization_scan",
            "verification_status": "VERIFIED_IN_TEST",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/controls",
            self.admin_headers,
            {},
            json.dumps(ctl_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        ctl_id = data["control"]["id"]

        # Verify control endpoint
        verify_payload = {"verification_status": "VERIFIED_IN_TEST", "test_evidence": "All 10 tests passed."}
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/threat-modeling/controls/{ctl_id}/verify",
            self.admin_headers,
            {},
            json.dumps(verify_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)

    def test_07_residual_risk_api_and_clinical_prohibition(self):
        """POST /api/v1/threat-modeling/residual-risks and clinical non-negotiable verification."""
        # Attempting to accept risk on prescribing hazard should return HTTP 400
        prohibited_payload = {
            "threat_id": "tac-cds-001",
            "scope": "All clinics",
            "business_rationale": "Emergency throughput",
            "compensating_controls": "None",
            "authorized_owner_role": "Chief Information Security Officer",
            "expires_at": "2026-11-30T00:00:00",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/residual-risks",
            self.admin_headers,
            {},
            json.dumps(prohibited_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 400)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("CLINICAL SAFETY INVARIANT", data.get("message", ""))

    def test_08_change_reviews_and_sdlc_gate_api(self):
        """POST /api/v1/threat-modeling/change-reviews and evaluate endpoint."""
        cr_payload = {
            "change_id": "PR-2049",
            "title": "Unani Mizaj Form Validation Logic",
            "target_subsystem": "CLINICAL_CDS_AND_PRESCRIPTIONS",
            "change_classification": "STANDARD_CHANGE",
            "security_review_status": "APPROVED",
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/threat-modeling/change-reviews",
            self.admin_headers,
            {},
            json.dumps(cr_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        data = json.loads(body.decode("utf-8"))
        review_id = data["change_review"]["id"]
        self.assertEqual(data["change_review"]["gate_verdict"], "PASS")

        # Evaluate endpoint
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/threat-modeling/change-reviews/{review_id}/evaluate",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)

    def test_09_audit_ledger_api(self):
        """GET /api/v1/threat-modeling/audit-ledger returns hash-chained trail."""
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/threat-modeling/audit-ledger", self.admin_headers, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertTrue(data["success"])
        self.assertGreaterEqual(data["count"], 1)

    def test_10_permission_enforcement(self):
        """Unauthenticated or forbidden requests are blocked."""
        # Unauthenticated request
        status, _, _ = ApiRouter.dispatch(
            "GET", "/api/v1/threat-modeling/dashboard-summary", {}, {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()

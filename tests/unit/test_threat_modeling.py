import os
import shutil
import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.threat_modeling import EnterpriseThreatModelingSDLCService
from apps.api.core.errors import ValidationError, NotFoundError, ConflictError


class TestEnterpriseThreatModelingSDLCService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_tm_unit.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.service = EnterpriseThreatModelingSDLCService(self.conn)

    def tearDown(self):
        if self.conn:
            self.conn.close()

    def test_dashboard_summary(self):
        """Test executive summary metrics aggregation."""
        summary = self.service.get_dashboard_summary()
        self.assertIn("total_threat_models", summary)
        self.assertIn("models_by_state", summary)
        self.assertIn("total_abuse_cases", summary)
        self.assertIn("open_critical_high_threats", summary)
        self.assertIn("total_testable_controls", summary)
        self.assertIn("total_sdlc_reviews", summary)
        self.assertGreaterEqual(summary["total_threat_models"], 1)

    def test_threat_models_crud_and_lifecycle(self):
        """Test threat model creation, validation, retrieval, and state transitions."""
        model_data = {
            "model_code": "TM-TEST-PATIENT-001",
            "title": "Patient Demographics & Duplicate Detection Architecture",
            "subsystem_scope": "PATIENT_IDENTITY_AND_REGISTRY",
            "repository_revision": "HEAD",
            "deployment_version": "v1.0.0",
            "owner_role": "Platform Security Architect",
            "assumptions": ["Multi-tenant isolation active", "Human-in-the-loop merge review"],
            "exclusions": ["External credit bureau verification"],
            "dependencies": ["patients", "mdm_duplicate_candidate_reviews"],
            "lifecycle_state": "draft",
        }
        created = self.service.create_threat_model(model_data, actor_id="usr-admin-1")
        self.assertEqual(created["model_code"], "TM-TEST-PATIENT-001")
        self.assertEqual(created["lifecycle_state"], "draft")
        self.assertEqual(len(created["assumptions"]), 2)

        # Retrieve
        fetched = self.service.get_threat_model(created["id"])
        self.assertEqual(fetched["title"], model_data["title"])

        # Transition state
        updated = self.service.transition_model_state(
            created["id"], "approved_for_scope", actor_id="usr-admin-1", review_notes="Architectural review approved."
        )
        self.assertEqual(updated["lifecycle_state"], "approved_for_scope")
        self.assertEqual(updated["is_stale"], 0)

        # Duplicate code rejected
        with self.assertRaises(ConflictError):
            self.service.create_threat_model(model_data, actor_id="usr-admin-1")

    def test_stale_model_detection(self):
        """Test automatic detection and tagging of stale threat models."""
        # Create an expired model
        model_data = {
            "model_code": "TM-EXPIRED-001",
            "title": "Legacy Gateway Threat Model",
            "subsystem_scope": "CONFIG_AND_SECRETS",
            "lifecycle_state": "approved_for_scope",
        }
        created = self.service.create_threat_model(model_data, actor_id="usr-admin-1")
        # Force expiration date into past
        past_iso = (datetime.utcnow() - timedelta(days=5)).isoformat()
        self.conn.execute(
            "UPDATE threat_models_registry SET next_review_due_at = ?, lifecycle_state = 'approved_for_scope', is_stale = 0 WHERE id = ?;",
            (past_iso, created["id"]),
        )

        stale_ids = self.service.check_and_mark_stale_models(actor_id="usr-admin-1")
        self.assertIn(created["id"], stale_ids)

        refetched = self.service.get_threat_model(created["id"])
        self.assertEqual(refetched["is_stale"], 1)
        self.assertEqual(refetched["lifecycle_state"], "stale")

    def test_trust_boundaries_crud(self):
        """Test trust boundary creation and listing."""
        tb_data = {
            "model_id": "tm-cds-001",
            "boundary_name": "Web Client <-> Consultation API Gateway",
            "source_actor_or_component": "Single-Page Application Client",
            "destination_component": "API Gateway Middleware",
            "data_classification": "TIER_2_PHI",
            "protocol_or_interface": "HTTPS/JSON_REST",
            "auth_mechanism": "BEARER_TOKEN_RBAC",
            "evidence_status": "verified_in_code",
            "notes": "Session tokens inspected server-side.",
        }
        tb = self.service.create_trust_boundary(tb_data, actor_id="usr-admin-1")
        self.assertEqual(tb["boundary_name"], "Web Client <-> Consultation API Gateway")

        boundaries = self.service.list_trust_boundaries(model_id="tm-cds-001")
        self.assertGreaterEqual(len(boundaries), 2)

    def test_abuse_cases_crud_and_lifecycle(self):
        """Test abuse case creation, STRIDE categorization, and lifecycle transitions."""
        case_data = {
            "model_id": "tm-cds-001",
            "threat_code": "TAC-TEST-002",
            "title": "Tampering with Su-e-Mizaj Clinical Assessment via Unvalidated Parameter",
            "methodology": "STRIDE_PLUS_CLINICAL_HAZARD",
            "threat_class": "TAMPERING",
            "actor_type": "AUTHENTICATED_USER",
            "target_asset": "unani_clinical_assessments",
            "attack_path_summary": "User submits arbitrary string in temperament field to trigger unhandled exception.",
            "clinical_safety_hazard": "DIAGNOSTIC_TAMPERING_MISROUTING",
            "severity": "HIGH",
            "accountable_owner_role": "Clinical Safety Officer",
        }
        case = self.service.create_abuse_case(case_data, actor_id="usr-admin-1")
        self.assertEqual(case["threat_code"], "TAC-TEST-002")
        self.assertEqual(case["lifecycle_status"], "identified")

        # Transition status
        updated = self.service.transition_abuse_case_status(
            case["id"], "mitigation_planned", actor_id="usr-admin-1", notes="Add enum validator."
        )
        self.assertEqual(updated["lifecycle_status"], "mitigation_planned")

        # Duplicate code rejected
        with self.assertRaises(ConflictError):
            self.service.create_abuse_case(case_data, actor_id="usr-admin-1")

    def test_testable_controls_and_verification(self):
        """Test testable controls registration and proof verification."""
        ctl_data = {
            "threat_id": "tac-cds-001",
            "control_code": "CTL-TEST-002",
            "title": "Deterministic Safety Rule AST Parser",
            "control_type": "PREVENTIVE",
            "enforcement_code_path": "apps.api.domains.safety_firewall.SafetyFirewallEngine.evaluate_prescription",
            "test_suite_reference": "tests.unit.test_safety_firewall.TestSafetyFirewall.test_schedule_e1_poison_block",
            "verification_status": "IMPLEMENTED",
        }
        ctl = self.service.create_testable_control(ctl_data, actor_id="usr-admin-1")
        self.assertEqual(ctl["control_code"], "CTL-TEST-002")
        self.assertEqual(ctl["verification_status"], "IMPLEMENTED")

        # Verify control
        verified = self.service.verify_control(
            ctl["id"], "VERIFIED_IN_TEST", actor_id="usr-admin-1", test_evidence="Ran unit test in 0.04s, 100% assertions passed."
        )
        self.assertEqual(verified["verification_status"], "VERIFIED_IN_TEST")

    def test_residual_risk_governance_and_expiry(self):
        """Test residual risk acceptance and 90-day maximum lifetime validation."""
        # Create non-clinical hazard threat
        case_data = {
            "model_id": "tm-cds-001",
            "threat_code": "TAC-TEST-DOCS-001",
            "title": "Stale Documentation for Internal Admin Diagnostic Endpoint",
            "methodology": "STRIDE_PLUS_CLINICAL_HAZARD",
            "threat_class": "INFO_DISCLOSURE",
            "actor_type": "AUTHENTICATED_USER",
            "target_asset": "api_docs",
            "attack_path_summary": "Admin route description contains deprecated schema field.",
            "clinical_safety_hazard": "NONE",
            "severity": "LOW",
        }
        case = self.service.create_abuse_case(case_data, actor_id="usr-admin-1")

        # Accept risk with 30-day expiry
        valid_expiry = (datetime.utcnow() + timedelta(days=30)).isoformat()
        risk_data = {
            "threat_id": case["id"],
            "scope": "Internal dev diagnostics",
            "business_rationale": "Documentation overhaul planned for Q1 2027.",
            "compensating_controls": "Endpoint restricted to internal loopback.",
            "authorized_owner_role": "Chief Information Security Officer",
            "expires_at": valid_expiry,
            "residual_risk_tier": "LOW",
        }
        decision = self.service.create_residual_risk_decision(risk_data, actor_id="usr-admin-1")
        self.assertEqual(decision["status"], "APPROVED")

        # Refetch abuse case - status should be accepted_by_authorized_owner
        refetched = self.service.get_abuse_case(case["id"])
        self.assertEqual(refetched["lifecycle_status"], "accepted_by_authorized_owner")

        # Reject expiry > 90 days
        invalid_expiry = (datetime.utcnow() + timedelta(days=120)).isoformat()
        risk_data["expires_at"] = invalid_expiry
        with self.assertRaises(ValidationError):
            self.service.create_residual_risk_decision(risk_data, actor_id="usr-admin-1")

    def test_clinical_safety_non_negotiable_in_risk_acceptance(self):
        """Test hard clinical firewall: cannot accept risk for direct harm prescribing errors."""
        risk_data = {
            "threat_id": "tac-cds-001",  # Baseline threat has clinical_safety_hazard = DIRECT_HARM_PRESCRIBING_ERROR
            "scope": "Emergency prescribing",
            "business_rationale": "Speed up consultation throughput.",
            "compensating_controls": "Post-hoc chart review.",
            "authorized_owner_role": "Chief Information Security Officer",
            "expires_at": (datetime.utcnow() + timedelta(days=14)).isoformat(),
        }
        with self.assertRaises(ValidationError) as ctx:
            self.service.create_residual_risk_decision(risk_data, actor_id="usr-admin-1")
        self.assertIn("CLINICAL SAFETY INVARIANT", str(ctx.exception))

    def test_sdlc_gate_evaluation_pass_and_blocked(self):
        """Test pre-deployment SDLC release gate evaluation."""
        # Baseline change review PR-1048 should evaluate to PASS
        review = self.service.evaluate_sdlc_gate("sdlc-cr-001", actor_id="usr-admin-1")
        self.assertEqual(review["gate_verdict"], "PASS")

        # Create a new change review with pending security review
        new_cr_data = {
            "change_id": "PR-9999",
            "title": "Add Patient Batch CSV Exporter",
            "target_subsystem": "CLINICAL_CDS_AND_PRESCRIPTIONS",
            "change_classification": "HIGH_IMPACT_CLINICAL",
            "security_review_status": "PENDING",
            "clinical_review_status": "PENDING",
        }
        cr = self.service.create_change_review(new_cr_data, actor_id="usr-admin-1")
        self.assertEqual(cr["gate_verdict"], "BLOCKED")
        self.assertGreaterEqual(len(cr["blocking_reasons"]), 1)

    def test_tamper_evident_audit_ledger(self):
        """Test cryptographic SHA-256 hash chaining on all threat modeling events."""
        events = self.service.query_audit_ledger(limit=10)
        self.assertGreaterEqual(len(events), 1)
        for ev in events:
            self.assertIn("entry_hash", ev)
            self.assertIn("previous_hash", ev)
            self.assertEqual(len(ev["entry_hash"]), 64)


if __name__ == "__main__":
    unittest.main()

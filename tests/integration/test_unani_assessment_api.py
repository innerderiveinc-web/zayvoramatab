"""Integration Tests: Unani Assessment API, Lifecycle, Concurrency, and Finalisation."""

import unittest
import os
import tempfile
import json
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter
from apps.api.core.security import reset_rate_limit_store

class TestUnaniAssessmentApi(unittest.TestCase):
    def setUp(self):
        reset_rate_limit_store()
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        run_migrations(self.db_path)
        seed_development_data(self.db_path)

        # Authenticate as Hakeem Tariq
        login_body = json.dumps({"username": "hakeem", "password": "matab123"}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch("POST", "/api/v1/auth/login", {}, {}, login_body, "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        self.token = json.loads(resp_bytes.decode("utf-8"))["token"]
        self.headers = {"authorization": f"Bearer {self.token}"}

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_list_templates_and_fetch_definition(self):
        """Practitioner can list templates and retrieve complete domain definitions."""
        status, _, resp_bytes = ApiRouter.dispatch("GET", "/api/v1/unani/templates", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        data = json.loads(resp_bytes.decode("utf-8"))
        self.assertIn("templates", data)
        self.assertGreaterEqual(len(data["templates"]), 1)
        core_tmpl = data["templates"][0]
        version_id = core_tmpl["active_version_id"]

        # Fetch version definition
        status, _, resp_bytes = ApiRouter.dispatch("GET", f"/api/v1/unani/templates/versions/{version_id}", self.headers, {}, b"", "127.0.0.1", db_path=self.db_path)
        self.assertEqual(status, 200)
        vdata = json.loads(resp_bytes.decode("utf-8"))["template_version"]
        self.assertIn("domains", vdata)
        domain_keys = [d["domain_key"] for d in vdata["domains"]]
        self.assertIn("MIZAJ", domain_keys)
        self.assertIn("AFAAL", domain_keys)
        self.assertIn("ASBAB_SITTAH", domain_keys)

    def test_create_draft_assessment_for_encounter(self):
        """Create draft Unani assessment linked to active encounter enc-syn-001."""
        body = json.dumps({}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/unani-assessments",
            self.headers, {}, body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        data = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        self.assertEqual(data["status"], "DRAFT")
        self.assertEqual(data["dominant_mizaj"], "NOT_ASSESSED")
        self.assertEqual(data["version_number"], 1)
        self.assessment_id = data["id"]

    def test_update_draft_with_concurrency_and_provenance(self):
        """Update draft assessment with observations, semantic states, provenance, and conclusions."""
        # Create draft first
        b_create = json.dumps({}).encode("utf-8")
        _, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/unani-assessments",
            self.headers, {}, b_create, "127.0.0.1", db_path=self.db_path
        )
        assessment_id = json.loads(resp_bytes.decode("utf-8"))["assessment"]["id"]

        # Update draft
        update_payload = {
            "version_number": 1,
            "dominant_mizaj": "BALGHAMI",
            "secondary_mizaj": "SAUDAWI",
            "mizaj_uncertainty": "HIGH_CONFIDENCE",
            "mizaj_rationale": "Pale complexion, cold/moist touch, slow pulse.",
            "clinical_reasoning": "Phlegmatic dyscrasia affecting gastric digestion.",
            "responses": [
                {
                    "domain_key": "MIZAJ",
                    "field_key": "malmas_touch",
                    "field_label": "Tactile Quality (Malmas)",
                    "field_value": "Cold and moist",
                    "semantic_state": "OBSERVED",
                    "provenance": "CLINICIAN_OBSERVED",
                    "notes": "Classic Balghami sign"
                },
                {
                    "domain_key": "AFAAL",
                    "field_key": "quwwat_hazima",
                    "field_label": "Digestive Faculty (Hazm)",
                    "field_value": "Delayed transit, postprandial heaviness",
                    "semantic_state": "IMPAIRED",
                    "provenance": "PATIENT_REPORTED",
                    "notes": "Symptoms worsen after yoghurt"
                }
            ],
            "conclusions": [
                {
                    "conclusion_type": "SU_E_MIZAJ",
                    "code": "SU-BALGHAM-01",
                    "title": "Su-e-Mizaj Balghami Maddi",
                    "certainty": "DEFINITIVE"
                }
            ]
        }

        status, _, resp_bytes = ApiRouter.dispatch(
            "PATCH", f"/api/v1/unani-assessments/{assessment_id}",
            self.headers, {}, json.dumps(update_payload).encode("utf-8"),
            "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        updated = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        self.assertEqual(updated["version_number"], 2)
        self.assertEqual(updated["dominant_mizaj"], "BALGHAMI")
        self.assertEqual(len(updated["responses"]), 2)
        self.assertEqual(len(updated["conclusions"]), 1)

        # Test Concurrency conflict on stale version
        stale_payload = {"version_number": 1, "dominant_mizaj": "SAFRAWI"}
        status, _, resp_bytes = ApiRouter.dispatch(
            "PATCH", f"/api/v1/unani-assessments/{assessment_id}",
            self.headers, {}, json.dumps(stale_payload).encode("utf-8"),
            "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 409)

    def test_finalise_assessment_creates_immutable_snapshot(self):
        """Finalising an assessment locks it, generates cryptographic SHA-256 fingerprint, and blocks PATCH."""
        # Create and update draft
        _, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/encounters/enc-syn-001/unani-assessments",
            self.headers, {}, json.dumps({}).encode("utf-8"), "127.0.0.1", db_path=self.db_path
        )
        assessment_id = json.loads(resp_bytes.decode("utf-8"))["assessment"]["id"]

        ApiRouter.dispatch(
            "PATCH", f"/api/v1/unani-assessments/{assessment_id}",
            self.headers, {}, json.dumps({
                "version_number": 1,
                "dominant_mizaj": "SAFRAWI",
                "mizaj_uncertainty": "HIGH_CONFIDENCE",
                "mizaj_rationale": "Yellowish sclera, hot touch, rapid pulse"
            }).encode("utf-8"), "127.0.0.1", db_path=self.db_path
        )

        # Finalise
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", f"/api/v1/unani-assessments/{assessment_id}/finalise",
            self.headers, {}, json.dumps({}).encode("utf-8"), "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        finalised = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        self.assertEqual(finalised["status"], "FINALISED")
        self.assertIsNotNone(finalised["signature_hash"])
        self.assertIsNotNone(finalised["signed_at"])

        # Attempt to PATCH finalised assessment must return 409
        status, _, _ = ApiRouter.dispatch(
            "PATCH", f"/api/v1/unani-assessments/{assessment_id}",
            self.headers, {}, json.dumps({"dominant_mizaj": "BALGHAMI"}).encode("utf-8"),
            "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 409)

    def test_amend_assessment_preserves_history(self):
        """Amending a finalised assessment supersedes parent and creates linked draft version."""
        # Use seeded finalised assessment 'uas-syn-001'
        amend_body = json.dumps({"reason": "Patient presented secondary Saudawi signs on re-evaluation."}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/unani-assessments/uas-syn-001/amend",
            self.headers, {}, amend_body, "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 201)
        new_assess = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        self.assertEqual(new_assess["status"], "DRAFT")
        self.assertEqual(new_assess["version_number"], 2)
        self.assertEqual(new_assess["parent_assessment_id"], "uas-syn-001")

        # Verify parent is now SUPERSEDED
        status, _, resp_bytes = ApiRouter.dispatch(
            "GET", "/api/v1/unani-assessments/uas-syn-001",
            self.headers, {}, b"", "127.0.0.1", db_path=self.db_path
        )
        self.assertEqual(status, 200)
        parent = json.loads(resp_bytes.decode("utf-8"))["assessment"]
        self.assertEqual(parent["status"], "SUPERSEDED")

if __name__ == "__main__":
    unittest.main()

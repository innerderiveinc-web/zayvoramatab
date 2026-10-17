"""Integration tests for Clinical Outcome Tracking, Treatment Response Measurement & Longitudinal Evaluation REST APIs.

Phase 26 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Measurement instruments, concepts, and protocols listing and retrieval
2. Care episodes and protocol runs with baseline designation
3. Outcome observations recording, retrieval, and versioned corrections
4. Deterministic instrument scoring endpoint
5. Compatibility engine and longitudinal comparison calculation
6. Treatment exposure context recording and listing
7. Clinician outcome interpretation drafting and review authentication
8. Longitudinal patient outcomes trends and aggregate reporting with disclosure controls
"""

import os
import json
import unittest
import tempfile
import sqlite3
import uuid

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestClinicalOutcomesApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_outcomes_api.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        # Authenticate Admin
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login",
            {"Content-Type": "application/json"}, {},
            json.dumps({"username": "admin", "password": "matab123"}).encode("utf-8"),
            "127.0.0.1", cls.db_path
        )
        cls.auth_token = json.loads(body)["token"]

        conn = sqlite3.connect(cls.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, organization_id FROM users WHERE username = 'admin' LIMIT 1;")
        admin_row = cur.fetchone()
        cls.admin_id = admin_row["id"]
        cls.org_id = admin_row["organization_id"]

        cur.execute("SELECT id FROM facilities WHERE organization_id = ? LIMIT 1;", (cls.org_id,))
        fac_row = cur.fetchone()
        cls.fac_id = fac_row["id"] if fac_row else "fac-default"

        # Create test patient
        cls.patient_id = f"pat-outcome-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status)
            VALUES (?, ?, ?, ?, 'Farida', 'Farida Begum', 'ACTIVE');
        """, (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))

        conn.commit()
        conn.close()

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }

    # --------------------------------------------------------------------------
    # Test 1: Instruments, Concepts & Protocols Endpoints
    # --------------------------------------------------------------------------
    def test_01_instruments_concepts_and_protocols_endpoints(self):
        # List instruments
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/outcomes/instruments",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        self.assertGreaterEqual(res["total_instruments"], 3)

        # Get specific instrument
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/outcomes/instruments/inst-vas-10",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        inst = json.loads(body)
        self.assertEqual(inst["instrument_code"], "VAS_10")

        # List concepts
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/outcomes/concepts",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(json.loads(body)["total_concepts"], 4)

        # List protocols
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/outcomes/protocols",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(json.loads(body)["total_protocols"], 1)

    # --------------------------------------------------------------------------
    # Test 2: Care Episode & Protocol Run Endpoints
    # --------------------------------------------------------------------------
    def test_02_care_episode_and_protocol_run_endpoints(self):
        # Open care episode
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/care-episodes",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "reason": "Unani Gastroenterology OPD - Dyspeptic Symptoms"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        episode = json.loads(body)
        episode_id = episode["id"]

        # Start protocol run
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcome-protocol-runs",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "protocol_id": "proto-dyspepsia-longitudinal",
                "episode_id": episode_id
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        run = json.loads(body)
        run_id = run["id"]
        self.assertEqual(run["baseline_state"], "PENDING")

        # Record intake observation
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcome-observations",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "concept_id": "concept-vas-pain",
                "raw_value_numeric": 7.5,
                "raw_unit": "points_0_10",
                "status": "PRESENT",
                "effective_at": "2026-10-01T10:00:00Z"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        obs_id = json.loads(body)["id"]

        # Designate baseline
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/outcome-protocol-runs/{run_id}/baseline",
            self._headers(), {},
            json.dumps({
                "observation_id": obs_id,
                "selection_method": "PRE_TREATMENT_OBSERVATION"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        self.assertEqual(res["baseline_state"], "DESIGNATED")
        self.assertEqual(res["baseline_observation_id"], obs_id)

    # --------------------------------------------------------------------------
    # Test 3: Outcome Observation Recording & Versioned Correction Endpoints
    # --------------------------------------------------------------------------
    def test_03_observations_and_correction_endpoints(self):
        # Record observation
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcome-observations",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "concept_id": "concept-dyspepsia-sozish",
                "observation_kind": "CLINICIAN_OBSERVED",
                "raw_value_numeric": 3.0,
                "raw_unit": "grade_0_3",
                "status": "PRESENT",
                "effective_at": "2026-10-05T12:00:00Z"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        obs = json.loads(body)
        obs_id = obs["id"]
        self.assertEqual(obs["raw_value_numeric"], 3.0)

        # Get observation
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/outcome-observations/{obs_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)

        # Versioned correction
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/outcome-observations/{obs_id}/correction",
            self._headers(), {},
            json.dumps({
                "raw_value_numeric": 2.0,
                "correction_reason": "Clinician re-evaluated grading from severe (3) to moderate (2)."
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        corrected = json.loads(body)
        self.assertEqual(corrected["version"], 2)
        self.assertEqual(corrected["supersedes_id"], obs_id)
        self.assertEqual(corrected["raw_value_numeric"], 2.0)

    # --------------------------------------------------------------------------
    # Test 4: Instrument Scoring Endpoint
    # --------------------------------------------------------------------------
    def test_04_instrument_scoring_endpoint(self):
        # Record multi-item questionnaire observation
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcome-observations",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "instrument_id": "inst-unani-suehazm-3",
                "instrument_version": "1.0",
                "observation_kind": "CLINICIAN_RATED",
                "status": "PRESENT",
                "item_responses": [
                    {"id": "q1", "value": 1},
                    {"id": "q2", "value": 2},
                    {"id": "q3", "value": 1}
                ],
                "effective_at": "2026-10-06T10:00:00Z"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        obs_id = json.loads(body)["id"]

        # Run scoring
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcomes/instrument-scores",
            self._headers(), {},
            json.dumps({
                "observation_id": obs_id,
                "instrument_id": "inst-unani-suehazm-3"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        scoring = json.loads(body)
        self.assertEqual(scoring["scoring_status"], "COMPLETED")
        self.assertEqual(scoring["calculated_score"], 4.0)

    # --------------------------------------------------------------------------
    # Test 5: Compatibility & Longitudinal Comparison Endpoint
    # --------------------------------------------------------------------------
    def test_05_compatibility_and_comparison_endpoint(self):
        # Create baseline observation
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcome-observations",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "concept_id": "concept-vas-pain",
                "raw_value_numeric": 8.0,
                "raw_unit": "points_0_10",
                "status": "PRESENT",
                "effective_at": "2026-10-01T09:00:00Z"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        base_id = json.loads(body)["id"]

        # Create follow-up observation
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcome-observations",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "concept_id": "concept-vas-pain",
                "raw_value_numeric": 3.0,
                "raw_unit": "points_0_10",
                "status": "PRESENT",
                "effective_at": "2026-10-15T09:00:00Z"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        follow_id = json.loads(body)["id"]

        # Compare
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcomes/compare",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "left_observation_id": base_id,
                "right_observation_id": follow_id
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        comp = json.loads(body)
        self.assertEqual(comp["compatibility_result"], "COMPARABLE")
        self.assertEqual(comp["delta_numeric"], -5.0)
        self.assertEqual(comp["direction_of_change"], "DECREASED")
        self.assertNotIn("treatment_success", comp["clinical_interpretation_label"].lower())

    # --------------------------------------------------------------------------
    # Test 6: Treatment Exposure Endpoints
    # --------------------------------------------------------------------------
    def test_06_treatment_exposure_endpoints(self):
        # Record exposure
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/patients/{self.patient_id}/treatment-exposures",
            self._headers(), {},
            json.dumps({
                "formulation_name": "Sharbat Bazoori Motadil",
                "documented_start_date": "2026-10-02",
                "exposure_status": "DISPENSED_CONFIRMED",
                "patient_reported_adherence_percent": 95.0,
                "clinician_reconciliation_state": "RECONCILED"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertEqual(res["formulation_name"], "Sharbat Bazoori Motadil")
        self.assertIn("Temporal association does not establish causal efficacy", res["causality_disclaimer"])

        # List exposures
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/patients/{self.patient_id}/treatment-exposures",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(json.loads(body)["total_exposures"], 1)

    # --------------------------------------------------------------------------
    # Test 7: Outcome Interpretation & Review Gate Endpoints
    # --------------------------------------------------------------------------
    def test_07_interpretation_and_review_endpoints(self):
        # Create interpretation
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcome-interpretations",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "interpretation_type": "AI_DRAFT",
                "interpretation_text": "Observed reduction in VAS pain score from 8.0 to 3.0 during care period.",
                "evidence_manifest": {"base_val": 8.0, "follow_val": 3.0}
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        interp = json.loads(body)
        interp_id = interp["id"]
        self.assertEqual(interp["review_status"], "DRAFT")

        # Review gate
        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/outcome-interpretations/{interp_id}/review",
            self._headers(), {},
            json.dumps({
                "action": "CLINICIAN_REVIEWED",
                "review_notes": "Clinician confirms chart congruence."
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        reviewed = json.loads(body)
        self.assertEqual(reviewed["review_status"], "CLINICIAN_REVIEWED")

    # --------------------------------------------------------------------------
    # Test 8: Patient Outcomes Trends & Aggregate Report Endpoints
    # --------------------------------------------------------------------------
    def test_08_patient_trends_and_aggregate_report_endpoints(self):
        # Get patient outcome trends
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/patients/{self.patient_id}/outcomes/trends",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        trends = json.loads(body)
        self.assertIn("observations", trends)
        self.assertIn("comparisons", trends)
        self.assertIn("clinical_notice", trends)

        # Generate aggregate report
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/outcomes/aggregate-reports",
            self._headers(), {},
            json.dumps({
                "report_title": "Annual Dyspepsia Measurement Completeness Report",
                "purpose": "Quality assurance and missing data tracking across OPD",
                "time_window_start": "2026-01-01",
                "time_window_end": "2026-12-31",
                "cohort_criteria": {"specialty": "Gastroenterology"}
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        rep = json.loads(body)
        rep_id = rep["id"]
        self.assertEqual(rep["minimum_cell_size_applied"], 5)

        # Get aggregate report
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/outcomes/aggregate-reports/{rep_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        rep_fetched = json.loads(body)
        self.assertEqual(rep_fetched["id"], rep_id)


if __name__ == "__main__":
    unittest.main()

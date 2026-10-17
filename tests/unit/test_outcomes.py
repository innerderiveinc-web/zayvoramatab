"""Unit tests for Clinical Outcome Tracking, Treatment Response Measurement & Longitudinal Evaluation Engine.

Phase 26 validation for ZAYVORA MATAB OS.
Tests:
1. Outcome concept and instrument registry seeding and custom registration
2. Care episode opening and protocol run lifecycle with baseline designation
3. Raw observation recording, 0 vs missingness distinction, and versioned corrections
4. Deterministic instrument scoring and incomplete questionnaire rejection
5. Restricted instrument licensing block enforcement
6. Compatibility engine preflight checks and non-comparable states
7. Treatment exposure context recording with mandatory causality disclaimer
8. Clinician outcome interpretation review gate
9. Longitudinal outcomes trends aggregation
10. Aggregate reporting with disclosure controls (min cell size >= 5)
"""

import os
import unittest
import tempfile
import sqlite3
import uuid
import json
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.outcomes import ClinicalOutcomesEngine
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError


class TestClinicalOutcomesEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_outcomes.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = ClinicalOutcomesEngine(cls.db_path)

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

    # --------------------------------------------------------------------------
    # Test 1: Registry Seeding & Registration
    # --------------------------------------------------------------------------
    def test_01_registry_seeds_and_registration(self):
        concepts = self.engine.list_outcome_concepts()
        self.assertGreaterEqual(len(concepts), 4)
        codes = [c["canonical_code"] for c in concepts]
        self.assertIn("VAS_PAIN", codes)
        self.assertIn("UNANI_MIZAJ_EVAL", codes)
        self.assertIn("SOZISH_E_MEDA", codes)

        instruments = self.engine.list_measurement_instruments()
        self.assertGreaterEqual(len(instruments), 3)
        inst_codes = [i["instrument_code"] for i in instruments]
        self.assertIn("VAS_10", inst_codes)
        self.assertIn("UNANI_SUEHAZM_3", inst_codes)
        self.assertIn("RESTRICTED_QOL", inst_codes)

        protocols = self.engine.list_outcome_protocols()
        self.assertGreaterEqual(len(protocols), 1)

        # Register custom concept
        new_concept = self.engine.register_outcome_concept({
            "canonical_code": "CUSTOM_SYMPTOM_FATIGUE",
            "display_name": "Kasl (Malaise / Fatigue Severity)",
            "domain": "SYMPTOM_EXPERIENCE",
            "source_or_definition_ref": "Kulliyat-e-Qanoon",
            "allowed_data_types": "NUMERIC",
            "permitted_units": ["grade_0_3"]
        }, self.admin_id)
        self.assertEqual(new_concept["canonical_code"], "CUSTOM_SYMPTOM_FATIGUE")

        # Duplicate registration must fail
        with self.assertRaises(ConflictError):
            self.engine.register_outcome_concept({
                "canonical_code": "CUSTOM_SYMPTOM_FATIGUE",
                "display_name": "Duplicate Concept",
                "domain": "SYMPTOM_EXPERIENCE"
            }, self.admin_id)

    # --------------------------------------------------------------------------
    # Test 2: Care Episode & Protocol Run Lifecycle
    # --------------------------------------------------------------------------
    def test_02_care_episode_and_protocol_run(self):
        episode = self.engine.open_care_episode(
            self.patient_id, self.org_id, self.fac_id,
            "Su-e-Hazm (Dyspepsia) 4-Week Management", self.admin_id
        )
        self.assertEqual(episode["status"], "OPEN")
        self.assertEqual(episode["patient_id"], self.patient_id)

        episodes = self.engine.list_care_episodes(self.patient_id)
        self.assertGreaterEqual(len(episodes), 1)

        protocols = self.engine.list_outcome_protocols()
        proto_id = protocols[0]["id"]

        run = self.engine.start_protocol_run(
            self.patient_id, proto_id, episode["id"], self.admin_id
        )
        self.assertEqual(run["run_state"], "OPEN")
        self.assertEqual(run["baseline_state"], "PENDING")

        # Record valid intake observation to designate as baseline
        obs = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-vas-pain",
                "observation_kind": "PATIENT_REPORTED",
                "raw_value_numeric": 7.0,
                "raw_unit": "points_0_10",
                "status": "PRESENT",
                "effective_at": "2026-10-01T10:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        run_updated = self.engine.designate_baseline(
            run["id"], obs["id"], "PRE_TREATMENT_OBSERVATION", self.admin_id
        )
        self.assertEqual(run_updated["baseline_state"], "DESIGNATED")
        self.assertEqual(run_updated["baseline_observation_id"], obs["id"])
        self.assertEqual(run_updated["run_state"], "IN_PROGRESS")

    # --------------------------------------------------------------------------
    # Test 3: Raw Observation Recording & Versioned Corrections
    # --------------------------------------------------------------------------
    def test_03_record_observation_and_versioned_correction(self):
        # 1. Non-negotiable: 0 is valid numeric measurement, NOT missing
        obs_zero = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-vas-pain",
                "observation_kind": "PATIENT_REPORTED",
                "raw_value_numeric": 0.0,
                "raw_unit": "points_0_10",
                "status": "PRESENT",
                "effective_at": "2026-10-02T10:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )
        self.assertEqual(obs_zero["raw_value_numeric"], 0.0)
        self.assertEqual(obs_zero["status"], "PRESENT")

        # 2. Non-negotiable: Explicit missingness state
        obs_declined = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-vas-pain",
                "observation_kind": "PATIENT_REPORTED",
                "status": "DECLINED",
                "missingness_reason": "Patient declined to complete questionnaire due to acute distress",
                "effective_at": "2026-10-03T10:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )
        self.assertEqual(obs_declined["status"], "DECLINED")
        self.assertIsNone(obs_declined["raw_value_numeric"])

        # 3. Versioned correction creates new row and supersedes prior
        corrected = self.engine.correct_observation(
            obs_zero["id"],
            {"raw_value_numeric": 1.0},
            self.admin_id,
            "Patient clarified pain was mild (1/10), not completely absent."
        )
        self.assertEqual(corrected["version"], 2)
        self.assertEqual(corrected["supersedes_id"], obs_zero["id"])
        self.assertEqual(corrected["raw_value_numeric"], 1.0)

        # Check prior observation is marked SUPERSEDED
        old_obs = self.engine.get_observation(obs_zero["id"])
        self.assertEqual(old_obs["status"], "SUPERSEDED")

    # --------------------------------------------------------------------------
    # Test 4: Instrument Scoring - Valid & Incomplete
    # --------------------------------------------------------------------------
    def test_04_instrument_scoring_valid_and_incomplete(self):
        # 1. Complete questionnaire with all required items
        obs = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-dyspepsia-sozish",
                "instrument_id": "inst-unani-suehazm-3",
                "instrument_version": "1.0",
                "observation_kind": "CLINICIAN_RATED",
                "status": "PRESENT",
                "item_responses": [
                    {"id": "q1", "value": 2},  # Sozish: 2
                    {"id": "q2", "value": 1},  # Nafakh: 1
                    {"id": "q3", "value": 2}   # Siql: 2
                ],
                "effective_at": "2026-10-04T11:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        scoring_run = self.engine.score_instrument(obs["id"], "inst-unani-suehazm-3", self.admin_id)
        self.assertEqual(scoring_run["scoring_status"], "COMPLETED")
        self.assertEqual(scoring_run["calculated_score"], 5.0)  # 2 + 1 + 2
        self.assertEqual(scoring_run["missing_items_count"], 0)

        # Verify observation normalized score was updated
        updated_obs = self.engine.get_observation(obs["id"])
        self.assertEqual(updated_obs["normalized_value_numeric"], 5.0)

        # 2. Incomplete questionnaire with missing required items
        incomplete_obs = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-dyspepsia-sozish",
                "instrument_id": "inst-unani-suehazm-3",
                "instrument_version": "1.0",
                "observation_kind": "CLINICIAN_RATED",
                "status": "PRESENT",
                "item_responses": [
                    {"id": "q1", "value": 2}
                    # Missing q2 and q3
                ],
                "effective_at": "2026-10-05T11:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        incomplete_run = self.engine.score_instrument(incomplete_obs["id"], "inst-unani-suehazm-3", self.admin_id)
        self.assertEqual(incomplete_run["scoring_status"], "INCOMPLETE")
        self.assertIsNone(incomplete_run["calculated_score"])
        self.assertEqual(incomplete_run["missing_items_count"], 2)

    # --------------------------------------------------------------------------
    # Test 5: Restricted Instrument Licensing Block
    # --------------------------------------------------------------------------
    def test_05_instrument_scoring_licensing_block(self):
        obs = self.engine.record_observation(
            self.patient_id,
            {
                "instrument_id": "inst-restricted-scale",
                "observation_kind": "PATIENT_REPORTED",
                "status": "PRESENT",
                "item_responses": [{"id": "q1", "value": 4}],
                "effective_at": "2026-10-06T11:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.score_instrument(obs["id"], "inst-restricted-scale", self.admin_id)
        self.assertIn("Scoring blocked", str(ctx.exception))

    # --------------------------------------------------------------------------
    # Test 6: Compatibility Preflight & Comparisons
    # --------------------------------------------------------------------------
    def test_06_compatibility_engine_comparisons(self):
        # Baseline pain: 8
        base_obs = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-vas-pain",
                "observation_kind": "PATIENT_REPORTED",
                "raw_value_numeric": 8.0,
                "raw_unit": "points_0_10",
                "status": "PRESENT",
                "effective_at": "2026-10-01T10:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        # Follow-up pain: 3
        follow_obs = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-vas-pain",
                "observation_kind": "PATIENT_REPORTED",
                "raw_value_numeric": 3.0,
                "raw_unit": "points_0_10",
                "status": "PRESENT",
                "effective_at": "2026-10-15T10:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        # 1. Compatible comparison
        comp = self.engine.compare_observations(
            self.patient_id, base_obs["id"], follow_obs["id"],
            "BASELINE_VS_FOLLOWUP", self.admin_id
        )
        self.assertEqual(comp["compatibility_result"], "COMPARABLE")
        self.assertEqual(comp["delta_numeric"], -5.0)
        self.assertEqual(comp["direction_of_change"], "DECREASED")
        self.assertEqual(comp["clinical_interpretation_label"], "NUMERIC_DELTA_DECREASED")
        self.assertNotIn("treatment_success", comp["clinical_interpretation_label"].lower())

        # 2. Incompatible comparison: Different concepts
        glucose_obs = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-fasting-glucose",
                "observation_kind": "LABORATORY",
                "raw_value_numeric": 110.0,
                "raw_unit": "mg/dL",
                "status": "PRESENT",
                "effective_at": "2026-10-15T10:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        diff_concept_comp = self.engine.compare_observations(
            self.patient_id, base_obs["id"], glucose_obs["id"],
            "BASELINE_VS_FOLLOWUP", self.admin_id
        )
        self.assertEqual(diff_concept_comp["compatibility_result"], "NOT_COMPARABLE_DIFFERENT_CONCEPT")
        self.assertEqual(diff_concept_comp["status"], "NOT_COMPARABLE")
        self.assertIsNone(diff_concept_comp["delta_numeric"])

        # 3. Incompatible comparison: Missing data observation
        declined_obs = self.engine.record_observation(
            self.patient_id,
            {
                "concept_id": "concept-vas-pain",
                "status": "DECLINED",
                "effective_at": "2026-10-20T10:00:00Z"
            },
            self.admin_id, "CLINICIAN"
        )

        missing_comp = self.engine.compare_observations(
            self.patient_id, base_obs["id"], declined_obs["id"],
            "BASELINE_VS_FOLLOWUP", self.admin_id
        )
        self.assertEqual(missing_comp["compatibility_result"], "MISSING_REQUIRED_DATA")
        self.assertIsNone(missing_comp["delta_numeric"])

    # --------------------------------------------------------------------------
    # Test 7: Treatment Exposure Context & Causality Disclaimer
    # --------------------------------------------------------------------------
    def test_07_treatment_exposure_and_causality_disclaimer(self):
        exposure = self.engine.record_treatment_exposure(
            self.patient_id, None,
            {
                "formulation_name": "Jawarish Kamuni Kabir",
                "documented_start_date": "2026-10-02",
                "documented_end_date": "2026-10-16",
                "exposure_status": "PATIENT_REPORTED_TAKEN",
                "patient_reported_adherence_percent": 90.0,
                "clinician_reconciliation_state": "RECONCILED",
                "co_interventions": ["Dietary restriction: Avoided cold/spicy foods"]
            },
            self.admin_id
        )
        self.assertEqual(exposure["formulation_name"], "Jawarish Kamuni Kabir")
        self.assertEqual(exposure["exposure_status"], "PATIENT_REPORTED_TAKEN")
        self.assertIn("Temporal association does not establish causal efficacy", exposure["causality_disclaimer"])

        exps = self.engine.list_treatment_exposures(self.patient_id)
        self.assertGreaterEqual(len(exps), 1)

    # --------------------------------------------------------------------------
    # Test 8: Outcome Interpretation & Review Gate
    # --------------------------------------------------------------------------
    def test_08_outcome_interpretation_and_review_gate(self):
        # AI Draft interpretation starts as DRAFT
        draft = self.engine.create_outcome_interpretation(
            self.patient_id,
            {
                "interpretation_type": "AI_DRAFT",
                "interpretation_text": "Patient pain scores decreased from 8 to 3 over two weeks concurrent with prescribed Jawarish Kamuni.",
                "evidence_manifest": {"left_obs_val": 8, "right_obs_val": 3}
            },
            self.admin_id, "ASSISTANT_AI"
        )
        self.assertEqual(draft["review_status"], "DRAFT")

        # Clinician review gate
        reviewed = self.engine.review_outcome_interpretation(
            draft["id"],
            "CLINICIAN_REVIEWED",
            "Confirmed clinically consistent with patient presentation.",
            self.admin_id
        )
        self.assertEqual(reviewed["review_status"], "CLINICIAN_REVIEWED")
        self.assertEqual(reviewed["reviewed_by"], self.admin_id)

    # --------------------------------------------------------------------------
    # Test 9: Longitudinal Outcomes View
    # --------------------------------------------------------------------------
    def test_09_patient_longitudinal_outcomes_aggregation(self):
        res = self.engine.get_patient_longitudinal_outcomes(self.patient_id)
        self.assertEqual(res["patient_id"], self.patient_id)
        self.assertGreaterEqual(res["total_observations"], 1)
        self.assertIn("observations", res)
        self.assertIn("comparisons", res)
        self.assertIn("treatment_exposures", res)
        self.assertIn("interpretations", res)
        self.assertIn("clinical_notice", res)

    # --------------------------------------------------------------------------
    # Test 10: Aggregate Report with Disclosure Controls
    # --------------------------------------------------------------------------
    def test_10_aggregate_report_with_disclosure_controls(self):
        rep = self.engine.generate_aggregate_report(
            self.org_id,
            "Q4 Dyspepsia Outcome Completeness Audit",
            "Quality assurance audit of outcome collection rates in Matab OPD",
            {"target_domain": "SYMPTOM_EXPERIENCE"},
            "2026-10-01", "2026-10-31", self.admin_id
        )
        self.assertEqual(rep["minimum_cell_size_applied"], 5)
        self.assertEqual(rep["approval_state"], "DRAFT")
        self.assertIn("Uncontrolled observational data", rep["limitations_disclaimer"])

        rep_fetched = self.engine.get_aggregate_report(rep["id"])
        self.assertEqual(rep_fetched["id"], rep["id"])
        self.assertIn("aggregated_metrics", rep_fetched)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for Clinical Workflow Intelligence & Data Quality Engine.

Phase 24 validation for ZAYVORA MATAB OS.
Tests:
1. Rule Registry listing and retrieval
2. Freshness policy evaluation (fresh vs stale)
3. Field provenance recording and retrieval
4. Demographic missingness detection (phone, DOB)
5. Clinical observation validation (inverted BP, invalid temp unit)
6. Encounter chief complaint blocker detection
7. Unani primary Mizaj classification check
8. Prescription sig/dosage blocker check
9. Duplicate patient candidate flag
10. Human remediation resolution (resolved, acknowledged with reason)
11. Blocker deferral rejection (safety enforcement)
12. Clinician conflict reconciliation ledger
13. Data quality workflow readiness check
"""

import os
import unittest
import tempfile
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.domains.data_quality import DataQualityEngine
from apps.api.core.errors import ValidationError, NotFoundError, SafetyBlockedError


class TestDataQualityEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_data_quality.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = DataQualityEngine(cls.db_path)

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

        cls.user_ctx = {
            "user_id": cls.admin_id,
            "organization_id": cls.org_id,
            "role": "CLINICIAN",
            "roles": ["CLINICIAN", "ADMIN"]
        }

    # --------------------------------------------------------------------------
    # 1. Rule Registry & Freshness Policies
    # --------------------------------------------------------------------------

    def test_01_list_rules_and_get_rule(self):
        rules = self.engine.list_rules(active_only=True)
        self.assertGreaterEqual(len(rules), 8)

        rule = self.engine.get_rule("DQ-ENC-CHIEF-COMPLAINT")
        self.assertEqual(rule["severity"], "BLOCKER")
        self.assertEqual(rule["remediation_role"], "CLINICIAN")

        # Unknown rule raises NotFoundError
        with self.assertRaises(NotFoundError):
            self.engine.get_rule("RULE-NONEXISTENT")

    def test_02_freshness_evaluation(self):
        # Fresh observation (1 hour ago)
        fresh_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        res_fresh = self.engine.evaluate_freshness("vitals.blood_pressure", fresh_ts)
        self.assertTrue(res_fresh["has_policy"])
        self.assertFalse(res_fresh["is_stale"])

        # Stale observation (48 hours ago for a 24h policy)
        stale_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        res_stale = self.engine.evaluate_freshness("vitals.blood_pressure", stale_ts)
        self.assertTrue(res_stale["has_policy"])
        self.assertTrue(res_stale["is_stale"])
        self.assertEqual(res_stale["stale_severity"], "WARNING")

    # --------------------------------------------------------------------------
    # 2. Field Provenance Tracking
    # --------------------------------------------------------------------------

    def test_03_field_provenance_recording(self):
        prov = self.engine.record_field_provenance(
            organization_id=self.org_id,
            entity_type="encounter",
            entity_id=f"enc-{uuid.uuid4().hex[:8]}",
            field_name="systolic_bp",
            field_value=120,
            unit="mmHg",
            recorded_by=self.admin_id,
            source_stream="DEVICE_VITAL"
        )
        self.assertTrue(prov["provenance_id"].startswith("prov-"))

        # Query history
        history = self.engine.get_field_provenance("encounter", prov["entity_id"], "systolic_bp")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["source_stream"], "DEVICE_VITAL")
        self.assertEqual(history[0]["unit"], "mmHg")

    # --------------------------------------------------------------------------
    # 3. Demographic Missingness & Identity
    # --------------------------------------------------------------------------

    def test_04_demographic_missingness_evaluation(self):
        conn = sqlite3.connect(self.db_path)
        p_id = f"pat-incomplete-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, date_of_birth, status)
            VALUES (?, ?, ?, ?, 'Zayd', 'Zayd Test', '', 'ACTIVE');
        """, (p_id, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))
        conn.commit()
        conn.close()

        eval_res = self.engine.evaluate_data_quality(patient_id=p_id, scope_type="PATIENT", user_ctx=self.user_ctx)
        self.assertGreaterEqual(eval_res["findings_count"], 2)

        codes = [f["rule_code"] for f in eval_res["findings"]]
        self.assertIn("DQ-PAT-PHONE", codes)
        self.assertIn("DQ-PAT-DOB", codes)

        # Verify role routing
        self.assertIn("FRONT_DESK", eval_res["remediations_by_role"])

    def test_05_duplicate_patient_candidate_flag(self):
        conn = sqlite3.connect(self.db_path)
        p1 = f"pat-dup-a-{uuid.uuid4().hex[:8]}"
        p2 = f"pat-dup-b-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, date_of_birth, status) VALUES (?, ?, ?, ?, 'Ali', 'Ali Khan', '1990-01-01', 'ACTIVE');", (p1, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))
        conn.execute("INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, date_of_birth, status) VALUES (?, ?, ?, ?, 'Ali', 'Ali Khan', '1990-01-01', 'ACTIVE');", (p2, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))
        conn.execute("""
            INSERT INTO patient_duplicate_candidates (id, organization_id, patient_id_a, patient_id_b, match_rules, match_score, status)
            VALUES (?, ?, ?, ?, '["PHONE_EXACT"]', 1.0, 'PENDING_REVIEW');
        """, (f"cand-{uuid.uuid4().hex[:8]}", self.org_id, p1, p2))
        conn.commit()
        conn.close()

        eval_res = self.engine.evaluate_data_quality(patient_id=p1, user_ctx=self.user_ctx)
        dup_findings = [f for f in eval_res["findings"] if f["rule_code"] == "DQ-DUPLICATE-PATIENT-FLAG"]
        self.assertEqual(len(dup_findings), 1)
        self.assertEqual(dup_findings[0]["category"], "IDENTITY")

    # --------------------------------------------------------------------------
    # 4. Clinical Encounter Findings & Blocker Detection
    # --------------------------------------------------------------------------

    def test_06_encounter_chief_complaint_blocker(self):
        conn = sqlite3.connect(self.db_path)
        enc_id = f"enc-dq-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, 'in_consultation', 1, ?);
        """, (enc_id, self.org_id, self.fac_id, self.patient_id, self.admin_id, self.admin_id))
        conn.commit()
        conn.close()

        eval_res = self.engine.evaluate_data_quality(
            patient_id=self.patient_id,
            encounter_id=enc_id,
            scope_type="ENCOUNTER",
            user_ctx=self.user_ctx
        )
        blockers = [f for f in eval_res["findings"] if f["severity"] == "BLOCKER"]
        self.assertTrue(any(b["rule_code"] == "DQ-ENC-CHIEF-COMPLAINT" for b in blockers))

    def test_07_vitals_inverted_bp_and_invalid_unit(self):
        conn = sqlite3.connect(self.db_path)
        enc_id = f"enc-vitals-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, 'in_consultation', 1, ?);
        """, (enc_id, self.org_id, self.fac_id, self.patient_id, self.admin_id, self.admin_id))

        mod_id = f"mod-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO modern_clinical_assessments (
                id, organization_id, facility_id, patient_id, encounter_id, author_id,
                assessment_date, chief_complaint, status
            ) VALUES (?, ?, ?, ?, ?, ?, '2026-10-13', 'Headache', 'DRAFT');
        """, (mod_id, self.org_id, self.fac_id, self.patient_id, enc_id, self.admin_id))

        # Insert inverted BP and invalid temp unit into clinical_observations
        conn.execute("""
            INSERT INTO clinical_observations (
                id, organization_id, patient_id, encounter_id, assessment_id, observation_type,
                concept_name, concept_code, value_numeric, unit
            ) VALUES (?, ?, ?, ?, ?, 'VITAL_SIGN', 'Systolic Blood Pressure', 'BP_SYSTOLIC', 80, 'mmHg');
        """, (f"obs-{uuid.uuid4().hex[:8]}", self.org_id, self.patient_id, enc_id, mod_id))

        conn.execute("""
            INSERT INTO clinical_observations (
                id, organization_id, patient_id, encounter_id, assessment_id, observation_type,
                concept_name, concept_code, value_numeric, unit
            ) VALUES (?, ?, ?, ?, ?, 'VITAL_SIGN', 'Diastolic Blood Pressure', 'BP_DIASTOLIC', 120, 'mmHg');
        """, (f"obs-{uuid.uuid4().hex[:8]}", self.org_id, self.patient_id, enc_id, mod_id))

        conn.execute("""
            INSERT INTO clinical_observations (
                id, organization_id, patient_id, encounter_id, assessment_id, observation_type,
                concept_name, concept_code, value_numeric, unit
            ) VALUES (?, ?, ?, ?, ?, 'VITAL_SIGN', 'Body Temperature', 'BODY_TEMP', 37.0, 'kelvin');
        """, (f"obs-{uuid.uuid4().hex[:8]}", self.org_id, self.patient_id, enc_id, mod_id))

        conn.commit()
        conn.close()

        eval_res = self.engine.evaluate_data_quality(patient_id=self.patient_id, encounter_id=enc_id, user_ctx=self.user_ctx)
        codes = [f["rule_code"] for f in eval_res["findings"]]
        self.assertIn("DQ-VITALS-BP-ORDER", codes)
        self.assertIn("DQ-VITALS-TEMP-UNIT", codes)

    def test_08_prescription_instructions_blocker(self):
        conn = sqlite3.connect(self.db_path)
        enc_id = f"enc-rx-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by) VALUES (?, ?, ?, ?, ?, 'in_consultation', 1, ?);", (enc_id, self.org_id, self.fac_id, self.patient_id, self.admin_id, self.admin_id))
        conn.execute("INSERT INTO modern_clinical_assessments (id, organization_id, facility_id, patient_id, encounter_id, author_id, assessment_date, chief_complaint, status) VALUES (?, ?, ?, ?, ?, ?, '2026-10-13', 'Cough', 'DRAFT');", (f"mod-{uuid.uuid4().hex[:8]}", self.org_id, self.fac_id, self.patient_id, enc_id, self.admin_id))

        rx_id = f"rx-dq-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO prescriptions (id, organization_id, facility_id, patient_id, encounter_id, practitioner_id, prescription_number, status, version_number) VALUES (?, ?, ?, ?, ?, ?, ?, 'DRAFT', 1);", (rx_id, self.org_id, self.fac_id, self.patient_id, enc_id, self.admin_id, f"RX-{uuid.uuid4().hex[:6]}"))
        # Item with empty dosage and empty instructions
        conn.execute("""
            INSERT INTO prescription_items (id, prescription_id, item_type, item_name, dose_amount, dose_unit, dosage_form, frequency, duration_days, instructions)
            VALUES (?, ?, 'CATALOG_FORMULATION', 'Sharbat Bazoori', '', 'ml', 'SHARBAT', '', 5, '');
        """, (f"rxi-{uuid.uuid4().hex[:8]}", rx_id))
        conn.commit()
        conn.close()

        eval_res = self.engine.evaluate_data_quality(patient_id=self.patient_id, encounter_id=enc_id, user_ctx=self.user_ctx)
        codes = [f["rule_code"] for f in eval_res["findings"]]
        self.assertIn("DQ-RX-SIG-PRESENCE", codes)

    # --------------------------------------------------------------------------
    # 5. Finding Resolution & Blocker Safety
    # --------------------------------------------------------------------------

    def test_09_resolve_finding_and_blocker_deferral_prevention(self):
        # Create an incomplete patient to ensure we get findings
        conn = sqlite3.connect(self.db_path)
        p_inc = f"pat-inc-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status) VALUES (?, ?, ?, ?, 'Incomplete', 'Incomplete Patient', 'ACTIVE');", (p_inc, self.org_id, self.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))
        conn.commit()
        conn.close()

        eval_res = self.engine.evaluate_data_quality(patient_id=p_inc, user_ctx=self.user_ctx)
        self.assertGreaterEqual(len(eval_res["findings"]), 1)
        finding = eval_res["findings"][0]
        finding_id = finding["id"]

        # Resolve successfully
        res = self.engine.resolve_finding(finding_id, "RESOLVED", self.user_ctx, reason="Updated by clinician")
        self.assertEqual(res["remediation_status"], "RESOLVED")

        # Deferring without reason fails
        eval_res2 = self.engine.evaluate_data_quality(patient_id=p_inc, user_ctx=self.user_ctx)
        warning_finding = [f for f in eval_res2["findings"] if f["severity"] == "WARNING"][0]
        with self.assertRaises(ValidationError):
            self.engine.resolve_finding(warning_finding["id"], "DEFERRED", self.user_ctx, reason="")

        # Blockers cannot be deferred
        # Create encounter with blocker
        conn = sqlite3.connect(self.db_path)
        enc_block = f"enc-blk-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by) VALUES (?, ?, ?, ?, ?, 'in_consultation', 1, ?);", (enc_block, self.org_id, self.fac_id, p_inc, self.admin_id, self.admin_id))
        conn.commit()
        conn.close()

        eval_res3 = self.engine.evaluate_data_quality(patient_id=p_inc, encounter_id=enc_block, user_ctx=self.user_ctx)
        blocker_findings = [f for f in eval_res3["findings"] if f["severity"] == "BLOCKER"]
        self.assertGreaterEqual(len(blocker_findings), 1)
        with self.assertRaises(SafetyBlockedError):
            self.engine.resolve_finding(blocker_findings[0]["id"], "DEFERRED", self.user_ctx, reason="Attempt deferral")

    # --------------------------------------------------------------------------
    # 6. Conflict Reconciliation Ledger
    # --------------------------------------------------------------------------

    def test_10_conflict_reconciliation(self):
        rec = self.engine.reconcile_conflict(
            patient_id=self.patient_id,
            field_name="systolic_bp",
            conflict_summary="Patient reports 140 mmHg at home vs 125 mmHg measured in clinic.",
            options_evaluated=[
                {"source": "PATIENT_REPORTED", "value": 140},
                {"source": "CLINICIAN_OBSERVED", "value": 125}
            ],
            selected_value=125,
            clinician_rationale="Calibrated clinic sphygmomanometer reading observed under resting conditions.",
            user_ctx=self.user_ctx
        )
        self.assertTrue(rec["reconciliation_id"].startswith("dq-rec-"))
        self.assertEqual(rec["selected_value"], 125)

        # Omission of substantive rationale raises ValidationError
        with self.assertRaises(ValidationError):
            self.engine.reconcile_conflict(
                patient_id=self.patient_id,
                field_name="systolic_bp",
                conflict_summary="Test",
                options_evaluated=[],
                selected_value=125,
                clinician_rationale="ok",
                user_ctx=self.user_ctx
            )

    # --------------------------------------------------------------------------
    # 7. Workflow Readiness Check
    # --------------------------------------------------------------------------

    def test_11_check_dq_readiness(self):
        conn = sqlite3.connect(self.db_path)
        enc_id = f"enc-ready-{uuid.uuid4().hex[:8]}"
        conn.execute("INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by) VALUES (?, ?, ?, ?, ?, 'in_consultation', 1, ?);", (enc_id, self.org_id, self.fac_id, self.patient_id, self.admin_id, self.admin_id))
        conn.commit()
        conn.close()

        # Evaluate encounter with missing chief complaint -> produces open BLOCKER finding
        self.engine.evaluate_data_quality(patient_id=self.patient_id, encounter_id=enc_id, user_ctx=self.user_ctx)

        readiness = self.engine.check_dq_readiness(enc_id, self.user_ctx)
        self.assertFalse(readiness["is_ready"])
        self.assertGreaterEqual(readiness["open_blockers_count"], 1)

        # Resolve all open blockers
        findings = self.engine.list_findings(encounter_id=enc_id, remediation_status="OPEN")
        for f in findings:
            if f["severity"] == "BLOCKER":
                self.engine.resolve_finding(f["id"], "RESOLVED", self.user_ctx, reason="Complaint documented")

        # Now readiness should pass
        readiness_after = self.engine.check_dq_readiness(enc_id, self.user_ctx)
        self.assertTrue(readiness_after["is_ready"])
        self.assertEqual(readiness_after["open_blockers_count"], 0)


if __name__ == "__main__":
    unittest.main()

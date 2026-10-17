"""Integration tests for Clinical Workflow Intelligence & Data Quality REST APIs.

Phase 24 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Rules Registry endpoints
2. Freshness Policies endpoint
3. Data quality evaluation execution
4. Findings listing and individual retrieval
5. Human finding remediation (RESOLVED, ACKNOWLEDGED_WITH_REASON)
6. Conflict reconciliation endpoint
7. Field provenance creation and history lookup
8. Encounter data-quality readiness gate
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


class TestDataQualityApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_data_quality_api.db")
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

        # Create test patient without phone to ensure findings
        cls.patient_id = f"pat-api-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status)
            VALUES (?, ?, ?, ?, 'Tariq', 'Tariq Test', 'ACTIVE');
        """, (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-{uuid.uuid4().hex[:6]}"))

        # Create test encounter
        cls.encounter_id = f"enc-api-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, status, version, created_by)
            VALUES (?, ?, ?, ?, ?, 'in_consultation', 1, ?);
        """, (cls.encounter_id, cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id, cls.admin_id))

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }

    # --------------------------------------------------------------------------
    # Test 1: Rules Registry Endpoints
    # --------------------------------------------------------------------------
    def test_01_rules_registry_endpoints(self):
        # List rules
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/data-quality/rules",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("rules", data)
        self.assertGreaterEqual(len(data["rules"]), 8)

        # Get specific rule
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/data-quality/rules/DQ-ENC-CHIEF-COMPLAINT",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        rule = json.loads(body)["rule"]
        self.assertEqual(rule["rule_code"], "DQ-ENC-CHIEF-COMPLAINT")
        self.assertEqual(rule["severity"], "BLOCKER")

    # --------------------------------------------------------------------------
    # Test 2: Freshness Policies Endpoint
    # --------------------------------------------------------------------------
    def test_02_freshness_policies_endpoint(self):
        status, _, body = ApiRouter.dispatch(
            "GET", "/api/v1/data-quality/freshness-policies",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("freshness_policies", data)
        self.assertGreaterEqual(len(data["freshness_policies"]), 4)

    # --------------------------------------------------------------------------
    # Test 3: Data Quality Evaluation Execution
    # --------------------------------------------------------------------------
    def test_03_evaluate_data_quality(self):
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/data-quality/evaluations",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "scope_type": "ENCOUNTER"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertIn("evaluation_id", res)
        self.assertGreaterEqual(res["findings_count"], 1)
        self.assertIn("findings", res)

    # --------------------------------------------------------------------------
    # Test 4: Findings Listing & Individual Retrieval
    # --------------------------------------------------------------------------
    def test_04_findings_endpoints(self):
        # List findings
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/data-quality/findings?encounter_id={self.encounter_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        findings = json.loads(body)["findings"]
        self.assertGreaterEqual(len(findings), 1)
        finding_id = findings[0]["id"]

        # Get specific finding
        status, _, body = ApiRouter.dispatch(
            f"GET", f"/api/v1/data-quality/findings/{finding_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        f_data = json.loads(body)["finding"]
        self.assertEqual(f_data["id"], finding_id)

    # --------------------------------------------------------------------------
    # Test 5: Human Finding Remediation
    # --------------------------------------------------------------------------
    def test_05_resolve_finding_endpoint(self):
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/data-quality/findings?encounter_id={self.encounter_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        finding_id = json.loads(body)["findings"][0]["id"]

        status, _, body = ApiRouter.dispatch(
            "POST", f"/api/v1/data-quality/findings/{finding_id}/resolve",
            self._headers(), {},
            json.dumps({"action": "RESOLVED", "reason": "Demographics verified with patient"}).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        self.assertEqual(res["remediation_status"], "RESOLVED")

    # --------------------------------------------------------------------------
    # Test 6: Conflict Reconciliation Endpoint
    # --------------------------------------------------------------------------
    def test_06_reconcile_conflict_endpoint(self):
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/data-quality/reconcile",
            self._headers(), {},
            json.dumps({
                "patient_id": self.patient_id,
                "encounter_id": self.encounter_id,
                "field_name": "pulse_rate",
                "conflict_summary": "Device vital 72 bpm vs manual pulse 78 bpm",
                "options_evaluated": [{"source": "DEVICE", "val": 72}, {"source": "MANUAL", "val": 78}],
                "selected_value": 78,
                "clinician_rationale": "Manual radial pulse counted for a full 60 seconds."
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertIn("reconciliation_id", res)
        self.assertEqual(res["selected_value"], 78)

    # --------------------------------------------------------------------------
    # Test 7: Field Provenance Endpoints
    # --------------------------------------------------------------------------
    def test_07_field_provenance_endpoints(self):
        # Record provenance
        status, _, body = ApiRouter.dispatch(
            "POST", "/api/v1/data-quality/provenance",
            self._headers(), {},
            json.dumps({
                "entity_type": "patient",
                "entity_id": self.patient_id,
                "field_name": "temperature",
                "field_value": 37.2,
                "unit": "C",
                "source_stream": "CLINICIAN_OBSERVED"
            }).encode("utf-8"),
            "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertIn("provenance_id", res)

        # Get provenance history
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/data-quality/provenance?entity_type=patient&entity_id={self.patient_id}",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        records = json.loads(body)["provenance_records"]
        self.assertGreaterEqual(len(records), 1)

    # --------------------------------------------------------------------------
    # Test 8: Data Quality Readiness Gate Endpoint
    # --------------------------------------------------------------------------
    def test_08_data_quality_readiness_endpoint(self):
        status, _, body = ApiRouter.dispatch(
            "GET", f"/api/v1/encounters/{self.encounter_id}/data-quality-readiness",
            self._headers(), {}, b"", "127.0.0.1", self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("is_ready", data)
        self.assertIn("open_blockers_count", data)


if __name__ == "__main__":
    unittest.main()

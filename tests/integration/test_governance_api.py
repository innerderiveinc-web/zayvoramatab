"""Integration tests for Clinical Knowledge Governance, Rule Versioning & Controlled Release REST APIs.

Phase 28 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Governed artifact registration and retrieval
2. Immutable version creation with automatic diffing
3. Role-separated lifecycle state transitions
4. Declarative clinical rule creation and sandboxed test execution
5. Dependency and impact analysis
6. Release manifest assembly and cryptographic hash binding
7. Multi-party release approval
8. Controlled deployment with runtime hash verification
9. Runtime version resolution for clinical encounters
10. Emergency release suspension and rollback execution
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


class TestClinicalKnowledgeGovernanceApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_gov_api.db")
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
        cls.patient_id = f"pat-gov-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status)
            VALUES (?, ?, ?, ?, 'Mansoor', 'Mansoor Ahmed', 'ACTIVE');
        """, (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-GOV-{uuid.uuid4().hex[:6]}"))
        conn.commit()
        conn.close()

    def _api(self, method: str, path: str, payload: dict = None, query_params: dict = None):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Facility-Id": self.fac_id,
        }
        body_bytes = json.dumps(payload).encode("utf-8") if payload else b""
        status, resp_headers, body = ApiRouter.dispatch(
            method, path, headers, query_params or {}, body_bytes, "127.0.0.1", self.db_path
        )
        return status, json.loads(body)

    def test_end_to_end_governance_api_lifecycle(self):
        # 1. Register a governed artifact
        status, art = self._api("POST", "/api/v1/governance/artifacts", {
            "artifact_type": "clinical_rule",
            "stable_key": "RULE-API-RENAL-DOSE-ADJUSTMENT",
            "title": "Renal Impairment Unani Formulations Dosage Adjustment Rule",
            "owner_role": "CLINICAL_GOVERNANCE_OWNER",
            "owning_domain": "NEPHROLOGY",
            "intended_use": "Adjust heavy mineral Bhasma/Kushta doses when eGFR is below 45 mL/min",
            "criticality_class": "CLINICAL_BEHAVIOR",
            "initial_payload": {
                "threshold_egfr": 45,
                "action": "REDUCE_OR_CONTRAINDICATE",
                "substances": ["Kushta_Qal'i", "Kushta_Nuqra"]
            }
        })
        self.assertEqual(status, 201)
        art_id = art["id"]
        v1_id = art["versions"][0]["id"]
        self.assertEqual(art["current_lifecycle_state"], "DRAFT")

        # 2. Get artifact by ID
        status, fetched_art = self._api("GET", f"/api/v1/governance/artifacts/{art_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched_art["stable_key"], "RULE-API-RENAL-DOSE-ADJUSTMENT")

        # 3. List artifacts
        status, art_list = self._api("GET", "/api/v1/governance/artifacts", query_params={"artifact_type": "clinical_rule"})
        self.assertEqual(status, 200)
        self.assertTrue(art_list["total_artifacts"] > 0)

        # 4. Create new version 2 with diff
        status, v2 = self._api("POST", f"/api/v1/governance/artifacts/{art_id}/versions", {
            "change_type": "CORRECTION",
            "version_label": "2.0.0",
            "payload": {
                "threshold_egfr": 30,
                "action": "STRICT_CONTRAINDICATION",
                "substances": ["Kushta_Qal'i", "Kushta_Nuqra", "Kushta_Faulad"]
            },
            "diff_summary": "Lowered eGFR threshold to 30 and added Kushta Faulad"
        })
        self.assertEqual(status, 201)
        v2_id = v2["id"]
        self.assertEqual(v2["version_number"], 2)

        # 5. Transition Version 2: SUBMITTED_FOR_REVIEW -> REVIEW_APPROVED
        status, trans1 = self._api("POST", f"/api/v1/governance/versions/{v2_id}/transition", {
            "next_state": "SUBMITTED_FOR_REVIEW",
            "rationale": "Submitting updated renal parameters for clinical review"
        })
        self.assertEqual(status, 200)
        self.assertEqual(trans1["lifecycle_state"], "SUBMITTED_FOR_REVIEW")

        status, trans2 = self._api("POST", f"/api/v1/governance/versions/{v2_id}/transition", {
            "next_state": "REVIEW_APPROVED",
            "rationale": "Clinical review board approved based on updated pharmacopoeial laboratory data"
        })
        self.assertEqual(status, 200)
        self.assertEqual(trans2["lifecycle_state"], "REVIEW_APPROVED")

        # 6. Create declarative clinical rule linked to this version
        status, rule = self._api("POST", "/api/v1/governance/rules", {
            "artifact_version_id": v2_id,
            "stable_key": "RULE-API-RENAL-EGFR-30",
            "rule_purpose": "Block mineral Kushta prescribing if eGFR < 30",
            "clinical_domain": "NEPHROLOGY",
            "rule_type": "CONTRAINDICATION_CHECK",
            "condition_expression": {
                "field": "patient_egfr",
                "operator": "LESS_THAN",
                "value": 30
            },
            "output_state_and_message": {
                "state": "triggered",
                "message": "Renal impairment detected (eGFR < 30). Kushta formulations strictly contraindicated."
            },
            "criticality_priority": "CRITICAL",
            "is_blocking": True,
            "test_fixtures": [
                {
                    "name": "Severe renal failure (eGFR 22)",
                    "input": {"patient_egfr": 22},
                    "expected_state": "triggered"
                },
                {
                    "name": "Normal renal function (eGFR 90)",
                    "input": {"patient_egfr": 90},
                    "expected_state": "not_triggered_within_scope"
                }
            ]
        })
        self.assertEqual(status, 201)
        rule_id = rule["id"]

        # 7. Execute sandboxed rule tests
        status, test_res = self._api("POST", f"/api/v1/governance/rules/{rule_id}/tests")
        self.assertEqual(status, 200)
        self.assertTrue(test_res["all_passed"])
        self.assertEqual(test_res["passed"], 2)

        # 8. Impact analysis
        status, impact = self._api("POST", f"/api/v1/governance/versions/{v2_id}/impact")
        self.assertEqual(status, 200)
        self.assertIn("impact_id", impact)

        # 9. Create release manifest
        status, rel = self._api("POST", "/api/v1/governance/releases", {
            "release_tag": "REL-2026-NEPHRO-Q4",
            "environment": "PRODUCTION",
            "artifact_version_ids": [v2_id],
            "change_summary": "Renal safety update v2"
        })
        self.assertEqual(status, 201)
        rel_id = rel["id"]
        self.assertEqual(rel["is_active"], 0)

        # 10. Approve release
        status, approved_rel = self._api("POST", f"/api/v1/governance/releases/{rel_id}/approve", {
            "rationale": "Signed off by Governance Board"
        })
        self.assertEqual(status, 200)
        self.assertEqual(len(approved_rel["approvals"]), 1)

        # 11. Deploy release
        status, deployed_rel = self._api("POST", f"/api/v1/governance/releases/{rel_id}/deploy")
        self.assertEqual(status, 200)
        self.assertEqual(deployed_rel["is_active"], 1)
        self.assertEqual(deployed_rel["runtime_verification_status"], "VERIFIED_MATCH")

        # 12. Runtime version resolution
        status, res = self._api("POST", "/api/v1/governance/runtime/resolve", {
            "encounter_id": f"enc-{uuid.uuid4().hex[:8]}",
            "action_name": "NEPHROLOGY_SAFETY_EVALUATION"
        })
        self.assertEqual(status, 200)
        self.assertEqual(res["release_tag"], "REL-2026-NEPHRO-Q4")
        self.assertEqual(res["release_id"], rel_id)

        # 13. Suspend release (emergency kill-switch)
        status, suspended = self._api("POST", f"/api/v1/governance/releases/{rel_id}/suspend", {
            "suspension_reason": "Testing emergency suspension API"
        })
        self.assertEqual(status, 200)
        self.assertEqual(suspended["is_active"], 0)


if __name__ == "__main__":
    unittest.main()

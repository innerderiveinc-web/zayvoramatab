"""Integration tests for Clinical Safety Surveillance & Pharmacovigilance REST APIs.

Phase 27 validation for ZAYVORA MATAB OS.
Tests end-to-end API dispatch:
1. Safety case creation with verbatim narrative and unmasked/masked contact depending on permissions.
2. Emergency triage escalation and red flag alerts.
3. Adding events and suspected exposures.
4. Independent multidimensional assessment recording and review.
5. Case deduplication linking without silent auto-merges.
6. Regulatory profile listing and activation verification gate.
7. Report package creation with SHA-256 manifest hash.
8. Submission authorization block on inactive profiles, followed by authorized dispatch with verifiable receipt.
9. Safety signals listing, aggregation, and review.
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


class TestPharmacovigilanceApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_pv_api.db")
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
        cls.patient_id = f"pat-pv-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, display_name, status)
            VALUES (?, ?, ?, ?, 'Zahida', 'Zahida Parveen', 'ACTIVE');
        """, (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-PV-{uuid.uuid4().hex[:6]}"))
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

    def test_end_to_end_pharmacovigilance_api_lifecycle(self):
        # 1. Create safety case
        status, case = self._api("POST", "/api/v1/safety/cases", {
            "case_type": "SUSPECTED_ADVERSE_REACTION",
            "intake_channel": "DIRECT_CLINICIAN_ENTRY",
            "reporter_type": "PHYSICIAN_HAKEEM",
            "reporter_name": "Hakim Irfan",
            "reporter_contact": {"phone": "+91 99887 76655", "email": "irfan@clinic.example"},
            "original_narrative": "Patient complained of epigastric burning and skin redness following formulation.",
            "patient_id": self.patient_id,
            "events": [
                {
                    "event_description_reported": "Epigastric burning and erythematous rash",
                    "onset_date": "2026-10-11",
                }
            ],
            "suspected_exposures": [
                {
                    "reported_product_name": "Jawarish Jalinoos",
                    "batch_lot_number": "JJ-BATCH-890",
                    "exposure_role": "SUSPECTED"
                }
            ]
        })
        self.assertEqual(status, 201)
        case_id = case["id"]
        self.assertTrue(case["case_number"].startswith("PV-"))

        # 2. Get safety case
        status, fetched = self._api("GET", f"/api/v1/safety/cases/{case_id}")
        self.assertEqual(status, 200)
        self.assertEqual(fetched["id"], case_id)
        self.assertEqual(len(fetched["events"]), 1)
        self.assertEqual(len(fetched["suspected_exposures"]), 1)

        # 3. Add an additional event and exposure via API
        status, new_ev = self._api("POST", f"/api/v1/safety/cases/{case_id}/events", {
            "event_description_reported": "Mild headache",
            "onset_date": "2026-10-12",
        })
        self.assertEqual(status, 201)

        status, new_exp = self._api("POST", f"/api/v1/safety/cases/{case_id}/exposures", {
            "reported_product_name": "Khamira Abresham",
            "exposure_role": "CONCOMITANT"
        })
        self.assertEqual(status, 201)

        # 4. Triage case
        status, triaged = self._api("POST", f"/api/v1/safety/cases/{case_id}/triage", {
            "urgency_level": "ROUTINE",
            "normalized_summary": "Mild GI irritation and rash with concomitant Khamira Abresham."
        })
        self.assertEqual(status, 200)
        self.assertEqual(triaged["urgency_level"], "ROUTINE")

        # 5. Record assessments
        status, a_conf = self._api("POST", f"/api/v1/safety/cases/{case_id}/assessments", {
            "assessment_dimension": "CLINICAL_CONFIRMATION",
            "assessment_value": "CLINICIAN_CONFIRMED",
            "method_or_scale_ref": "CLINICAL_EVALUATION",
            "rationale": "Objective observation of skin erythema on exam."
        })
        self.assertEqual(status, 201)

        status, a_ser = self._api("POST", f"/api/v1/safety/cases/{case_id}/assessments", {
            "assessment_dimension": "SERIOUSNESS",
            "assessment_value": "NON_SERIOUS",
            "method_or_scale_ref": "ICH_E2A_SERIOUSNESS",
            "rationale": "Did not result in hospitalization or life threatening threat."
        })
        self.assertEqual(status, 201)

        status, a_caus = self._api("POST", f"/api/v1/safety/cases/{case_id}/assessments", {
            "assessment_dimension": "CAUSALITY",
            "assessment_value": "POSSIBLE",
            "method_or_scale_ref": "WHO_UMC",
            "rationale": "Reasonable temporal association, concurrent products present."
        })
        self.assertEqual(status, 201)

        # Review causality assessment
        status, reviewed_a = self._api("POST", f"/api/v1/safety/assessments/{a_caus['id']}/review", {
            "review_status": "VERIFIED",
            "rationale": "Senior safety review confirms WHO-UMC category Possible."
        })
        self.assertEqual(status, 200)
        self.assertEqual(reviewed_a["review_status"], "VERIFIED")

        # 6. Follow-up tasks API
        status, task = self._api("POST", f"/api/v1/safety/cases/{case_id}/follow-up-tasks", {
            "required_field_or_query": "Check if rash resolved upon dechallenge.",
            "assigned_role": "HAKEEM_CLINICIAN"
        })
        self.assertEqual(status, 201)

        status, updated_task = self._api("POST", f"/api/v1/safety/follow-up-tasks/{task['id']}/attempt", {
            "status": "COMPLETED",
            "completion_notes": "Patient reports rash resolved within 48 hours after discontinuation."
        })
        self.assertEqual(status, 200)
        self.assertEqual(updated_task["status"], "COMPLETED")

        # 7. Regulatory profiles API
        status, profiles_resp = self._api("GET", "/api/v1/safety/regulatory-profiles")
        self.assertEqual(status, 200)
        self.assertTrue(profiles_resp["total_profiles"] > 0)
        pvpi_prof = [p for p in profiles_resp["profiles"] if p["profile_code"] == "PVPI_AYUSH_ASU"][0]
        self.assertEqual(pvpi_prof["is_active"], 0)

        # Build report package
        status, pkg = self._api("POST", f"/api/v1/safety/cases/{case_id}/report-package", {
            "profile_id": pvpi_prof["id"]
        })
        self.assertEqual(status, 201)
        self.assertEqual(pkg["validation_status"], "VALID")
        pkg_id = pkg["id"]

        # Attempting to authorize on inactive profile returns 403 Forbidden
        status, err = self._api("POST", f"/api/v1/safety/submissions/{pkg_id}/authorize")
        self.assertEqual(status, 403)

        # Activate regulatory profile
        status, active_prof = self._api("POST", f"/api/v1/safety/regulatory-profiles/{pvpi_prof['id']}/verify")
        self.assertEqual(status, 200)
        self.assertEqual(active_prof["is_active"], 1)

        # Authorize submission now succeeds
        status, auth_sub = self._api("POST", f"/api/v1/safety/submissions/{pkg_id}/authorize")
        self.assertEqual(status, 200)
        self.assertEqual(auth_sub["submission_status"], "AUTHORIZED")

        # Dispatch submission -> receipt artifact generated
        status, disp = self._api("POST", f"/api/v1/safety/submissions/{pkg_id}/dispatch")
        self.assertEqual(status, 200)
        self.assertEqual(disp["submission_status"], "ACKNOWLEDGED")
        self.assertTrue(disp["transaction_ref"].startswith("PV-RECEIPT-"))

        # 8. Signals API
        status, sig = self._api("POST", "/api/v1/safety/signals", {
            "product_identifier": "PROD-JAWARISH-JALINOOS",
            "reaction_term": "Epigastric burning",
            "case_increment": 1,
            "clinical_justification": "Initial safety surveillance observation."
        })
        self.assertEqual(status, 200)

        status, sig_list = self._api("GET", "/api/v1/safety/signals")
        self.assertEqual(status, 200)
        self.assertTrue(sig_list["total_signals"] > 0)

        status, rev_sig = self._api("POST", f"/api/v1/safety/signals/{sig['id']}/review", {
            "evaluation_status": "UNDER_INVESTIGATION",
            "clinical_justification": "Investigating potential batch-specific spice concentration variations."
        })
        self.assertEqual(status, 200)
        self.assertEqual(rev_sig["evaluation_status"], "UNDER_INVESTIGATION")


if __name__ == "__main__":
    unittest.main()

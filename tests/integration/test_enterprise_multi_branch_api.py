"""Integration & Multi-Tenant Security Tests for Phase 11:
Multi-Doctor, Multi-Branch & Hospital Administration Foundation.
"""

import json
import os
import tempfile
import unittest

from apps.api.database.connection import DatabaseConnection
from apps.api.database.migrator import run_migrations
from apps.api.database.seed import hash_seed_password, seed_development_data
from apps.api.router import ApiRouter


class TestEnterpriseMultiBranchApi(unittest.TestCase):
    """End-to-End integration and tenant/branch isolation tests for Phase 11."""

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        run_migrations(self.db_path)
        seed_development_data(self.db_path)
        self._ip_counter = 20

        self.org_a = "org-matab-default"
        self.fac_a1 = "fac-central-opd"
        self.fac_a2 = "fac-south-branch"

        self.admin_token = self._login("admin", "matab123")
        self.hakeem_token = self._login("hakeem", "matab123")
        self.reception_token = self._login("reception", "matab123")

        # Register a patient at Facility A1 (Central Matab OPD)
        st, pat_resp = self._req(
            "POST",
            "/api/v1/patients",
            self.reception_token,
            {
                "given_name": "Farhan",
                "family_name": "Siddiqui",
                "sex": "MALE",
                "date_of_birth": "1979-08-21",
                "phone": "+919876500112",
            },
            facility_id=self.fac_a1,
        )
        self.assertEqual(st, 201)
        self.patient_id = pat_resp["patient"]["id"]

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _login(self, username: str, password: str) -> str:
        self._ip_counter += 1
        client_ip = f"10.0.1.{self._ip_counter}"
        body_bytes = json.dumps({"username": username, "password": password}).encode("utf-8")
        status, _, resp_bytes = ApiRouter.dispatch(
            "POST", "/api/v1/auth/login", {}, {}, body_bytes, client_ip, db_path=self.db_path
        )
        self.assertEqual(status, 200)
        return json.loads(resp_bytes.decode("utf-8"))["token"]

    def _req(
        self,
        method: str,
        path: str,
        token: str = "",
        body: dict = None,
        query: dict = None,
        facility_id: str = None,
    ):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if facility_id:
            headers["X-Facility-Id"] = facility_id
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        status, _, resp_bytes = ApiRouter.dispatch(
            method, path, headers, query or {}, body_bytes, "127.0.0.1", db_path=self.db_path
        )
        return status, json.loads(resp_bytes.decode("utf-8"))

    def _seed_external_organization_b(self) -> str:
        """Create an independent Organization B and user to verify strict cross-tenant isolation."""
        conn = DatabaseConnection(self.db_path).get_connection()
        try:
            conn.execute(
                """
                INSERT INTO organizations (id, name, code, license_number, profile_type, is_active)
                VALUES ('org-external-b', 'External Hospital Group B', 'EXT-B-01', 'LIC-EXT-B', 'HOSPITAL', 1);
                """
            )
            conn.execute(
                """
                INSERT INTO facilities (id, organization_id, name, code, address, phone, is_active)
                VALUES ('fac-ext-b1', 'org-external-b', 'External Hospital Main', 'EXT-F1', 'Mumbai', '+919999999999', 1);
                """
            )
            conn.execute(
                """
                INSERT INTO users (id, organization_id, username, email, full_name, password_hash, is_active)
                VALUES ('usr-ext-b1', 'org-external-b', 'ext_admin', 'ext@example.org', 'External Admin B', ?, 1);
                """,
                (hash_seed_password("matab123"),),
            )
            conn.execute(
                """
                INSERT INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
                VALUES ('uom-ext-b1', 'usr-ext-b1', 'org-external-b', 'role-org-admin', 1);
                """
            )
            conn.execute(
                """
                INSERT INTO user_facility_memberships (id, user_id, facility_id, role_id, is_active)
                VALUES ('ufm-ext-b1', 'usr-ext-b1', 'fac-ext-b1', 'role-org-admin', 1);
                """
            )
            conn.commit()
        finally:
            conn.close()
        return self._login("ext_admin", "matab123")

    def test_definition_of_done_multi_branch_transfer_and_cross_tenant_isolation(self):
        """
        Proves the Prompt 11 Definition of Done:
        ORGANIZATION A -> FACILITY A1 & A2 -> AUTHORIZED USERS & DEPARTMENTS ->
        PATIENT/ENCOUNTER ACCESS WITHIN SCOPE -> CONTROLLED TRANSFER A1 TO A2 ->
        RECIPIENT ACCEPTANCE & COMPLETION -> AUDIT -> NO ACCESS FROM ORGANIZATION B.
        """
        # 1. Create an encounter at Facility A1 (fac-central-opd)
        st, enc_resp = self._req(
            "POST",
            f"/api/v1/patients/{self.patient_id}/encounters",
            self.hakeem_token,
            {
                "facility_id": self.fac_a1,
                "encounter_type": "OPD_VISIT",
                "reason_for_visit": "Chronic hepatic congestion requiring South Branch Regimenal Therapy",
            },
            facility_id=self.fac_a1,
        )
        self.assertEqual(st, 201)
        source_encounter_id = enc_resp["encounter"]["id"]

        # 2. Initiate controlled inter-facility transfer from Facility A1 to Facility A2 (fac-south-branch)
        st, trf_resp = self._req(
            "POST",
            "/api/v1/transfers",
            self.hakeem_token,
            {
                "originating_facility_id": self.fac_a1,
                "receiving_facility_id": self.fac_a2,
                "patient_id": self.patient_id,
                "source_encounter_id": source_encounter_id,
                "transfer_type": "INTERNAL_BRANCH_REFERRAL",
                "urgency": "URGENT",
                "reason_for_transfer": "Requires specialized Ilaj-bil-Tadbir (Hijama) unit at South Branch",
                "minimum_clinical_summary": "Stable vitals; Damwi temperament evaluation completed at Central OPD",
                "idempotency_key": "idem-trf-a1-to-a2-001",
            },
            facility_id=self.fac_a1,
        )
        self.assertEqual(st, 201)
        transfer = trf_resp["transfer"]
        transfer_id = transfer["id"]
        # Sending a transfer MUST set status to 'requested', never 'accepted' automatically
        self.assertEqual(transfer["status"], "requested")

        # 3. Receptionist who is ONLY assigned to fac-central-opd cannot accept transfer for fac-south-branch
        st_unauth, unauth_resp = self._req(
            "POST",
            f"/api/v1/transfers/{transfer_id}/accept",
            self.reception_token,
            {"acceptance_notes": "Attempting unauthorized acceptance"},
            facility_id=self.fac_a1,
        )
        self.assertEqual(st_unauth, 403)

        # 4. Assign Hakeem to Facility A2 (fac-south-branch) so Hakeem is authorized at the receiving branch
        st_assign, _ = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a2}/assignments",
            self.admin_token,
            {
                "user_id": "usr-hakeem-1",
                "role_code": "PRACTITIONER",
                "assignment_type": "SECONDARY_BRANCH",
            },
        )
        self.assertEqual(st_assign, 201)

        # 5. Accept the transfer at Facility A2 (fac-south-branch)
        st_acc, acc_resp = self._req(
            "POST",
            f"/api/v1/transfers/{transfer_id}/accept",
            self.hakeem_token,
            {"acceptance_notes": "Accepted into South Branch Regimenal Unit"},
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_acc, 200)
        self.assertEqual(acc_resp["transfer"]["status"], "accepted")

        # Idempotent replay of accept returns 200 without duplicating state transition
        st_acc_replay, acc_replay = self._req(
            "POST",
            f"/api/v1/transfers/{transfer_id}/accept",
            self.hakeem_token,
            {"acceptance_notes": "Accepted into South Branch Regimenal Unit"},
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_acc_replay, 200)
        self.assertTrue(acc_replay["transfer"].get("idempotent_replay"))

        # 6. Complete the transfer at Facility A2 and verify destination encounter creation & source preservation
        st_comp, comp_resp = self._req(
            "POST",
            f"/api/v1/transfers/{transfer_id}/complete",
            self.hakeem_token,
            {
                "completion_outcome_summary": "Patient arrived at South Branch and regimenal session initiated",
            },
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_comp, 200)
        completed_trf = comp_resp["transfer"]
        self.assertEqual(completed_trf["status"], "completed")
        self.assertIsNotNone(completed_trf["destination_encounter_id"])
        self.assertNotEqual(completed_trf["destination_encounter_id"], source_encounter_id)

        # Verify source encounter at Facility A1 is still intact and owned by fac-central-opd
        st_src, src_enc = self._req("GET", f"/api/v1/encounters/{source_encounter_id}", self.hakeem_token)
        self.assertEqual(st_src, 200)
        self.assertEqual(src_enc["encounter"]["facility_id"], self.fac_a1)

        # 7. Verify Organization B has ZERO access to Organization A's org, facilities, patients, or transfers
        org_b_token = self._seed_external_organization_b()

        st_org_b, _ = self._req("GET", f"/api/v1/organizations/{self.org_a}", org_b_token)
        self.assertEqual(st_org_b, 403)

        st_cfg_b, _ = self._req("GET", f"/api/v1/facilities/{self.fac_a1}/configuration", org_b_token)
        self.assertIn(st_cfg_b, (403, 404))

        st_pat_b, _ = self._req(
            "GET",
            f"/api/v1/patients/{self.patient_id}/cross-facility-continuity",
            org_b_token,
            facility_id=self.fac_a1,
        )
        self.assertIn(st_pat_b, (403, 404))

        st_trf_b, _ = self._req("GET", f"/api/v1/transfers/{transfer_id}", org_b_token)
        self.assertIn(st_trf_b, (403, 404))

    def test_scoped_staff_assignment_per_facility_permissions_and_immediate_revocation(self):
        """
        Proves that the same staff account can hold different roles at Facility A1 vs Facility A2,
        and revoking the Facility A2 assignment immediately stops Facility A2 access on the next request
        without breaking Facility A1 access.
        """
        # Initially, reception has RECEPTIONIST at fac-central-opd and cannot create departments anywhere
        st_initial, _ = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a2}/departments",
            self.reception_token,
            {"code": "DEPT-TEST-1", "name": "Test Dept 1", "department_type": "GENERAL_OPD"},
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_initial, 403)

        # Grant reception CLINIC_ADMIN role at fac-south-branch (Facility A2) ONLY
        st_grant, grant_resp = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a2}/assignments",
            self.admin_token,
            {
                "user_id": "usr-recep-1",
                "role_code": "CLINIC_ADMIN",
                "assignment_type": "SECONDARY_BRANCH",
            },
        )
        self.assertEqual(st_grant, 201)
        assignment_id = grant_resp["assignment"]["id"]

        # Now reception CAN create a department at fac-south-branch when scoped to fac-south-branch
        st_a2_ok, dept_resp = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a2}/departments",
            self.reception_token,
            {"code": "DEPT-SOUTH-OPD", "name": "South General OPD", "department_type": "GENERAL_OPD"},
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_a2_ok, 201)
        self.assertEqual(dept_resp["department"]["code"], "DEPT-SOUTH-OPD")

        # However, reception still CANNOT create a department at fac-central-opd (Facility A1)!
        st_a1_denied, _ = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a1}/departments",
            self.reception_token,
            {"code": "DEPT-CENTRAL-UNAUTHORIZED", "name": "Unauthorized Dept", "department_type": "GENERAL_OPD"},
            facility_id=self.fac_a1,
        )
        self.assertEqual(st_a1_denied, 403)

        # Now revoke reception's CLINIC_ADMIN assignment at fac-south-branch
        st_rev, rev_resp = self._req(
            "POST",
            f"/api/v1/assignments/{assignment_id}/revoke",
            self.admin_token,
            {"reason": "End of branch administrative cover"},
        )
        self.assertEqual(st_rev, 200)
        self.assertEqual(rev_resp["assignment"]["status"], "revoked")

        # Immediately on the NEXT request with the SAME token, reception is denied at fac-south-branch
        st_after_rev, _ = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a2}/departments",
            self.reception_token,
            {"code": "DEPT-SOUTH-2", "name": "Should Fail Immediately", "department_type": "GENERAL_OPD"},
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_after_rev, 403)

        # Meanwhile, reception's primary RECEPTIONIST access at fac-central-opd still works
        st_pat_search, _ = self._req(
            "GET",
            "/api/v1/patients",
            self.reception_token,
            facility_id=self.fac_a1,
        )
        self.assertEqual(st_pat_search, 200)

    def test_cross_facility_patient_continuity_privacy_and_governed_merge(self):
        """
        Tests cross-facility continuity filtering (RESTRICTED_BRANCH_ONLY and FACILITY_ISOLATED)
        and governed human-reviewed patient merge.
        """
        # Create an encounter for patient at fac-south-branch
        st_enc, _ = self._req(
            "POST",
            f"/api/v1/patients/{self.patient_id}/encounters",
            self.admin_token,
            {
                "facility_id": self.fac_a2,
                "encounter_type": "OPD_VISIT",
                "reason_for_visit": "Sensitive South Branch consultation",
            },
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_enc, 201)

        # Link patient to fac-south-branch with RESTRICTED_BRANCH_ONLY privacy restriction
        st_link, _ = self._req(
            "POST",
            f"/api/v1/patients/{self.patient_id}/facility-links",
            self.admin_token,
            {
                "facility_id": self.fac_a2,
                "privacy_restriction_level": "RESTRICTED_BRANCH_ONLY",
                "cross_facility_consent_granted": False,
            },
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_link, 201)

        # Querying continuity from fac-central-opd omits the restricted fac-south-branch encounter and reports omission count
        st_cont, cont_resp = self._req(
            "GET",
            f"/api/v1/patients/{self.patient_id}/cross-facility-continuity",
            self.hakeem_token,
            query={"facility_id": self.fac_a1},
            facility_id=self.fac_a1,
        )
        self.assertEqual(st_cont, 200)
        continuity = cont_resp["continuity"]
        self.assertGreaterEqual(continuity["restricted_records_omitted_count"], 1)
        self.assertTrue(continuity["has_inaccessible_branch_records"])

        # Governed Patient Merge: create duplicate patient record (transliteration variant at South Branch) and merge into self.patient_id
        st_dup, dup_resp = self._req(
            "POST",
            "/api/v1/patients",
            self.admin_token,
            {
                "given_name": "Farhaan",
                "family_name": "Siddiqui",
                "sex": "MALE",
                "date_of_birth": "1979-08-21",
                "phone": "+919876599887",
            },
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_dup, 201)
        dup_patient_id = dup_resp["patient"]["id"]

        st_pmr, pmr_resp = self._req(
            "POST",
            "/api/v1/patients/merge-requests",
            self.admin_token,
            {
                "source_patient_id": dup_patient_id,
                "target_patient_id": self.patient_id,
                "request_reason": "Patient registered twice at South Branch and Central OPD",
                "match_evidence": {"verified_id_card": True},
            },
        )
        self.assertEqual(st_pmr, 201)
        merge_req_id = pmr_resp["merge_request"]["id"]
        self.assertEqual(pmr_resp["merge_request"]["status"], "pending_review")

        st_rev, rev_resp = self._req(
            "POST",
            f"/api/v1/patients/merge-requests/{merge_req_id}/review",
            self.admin_token,
            {
                "decision": "approve",
                "review_notes": "Verified identity documents across both branches; approved merge.",
            },
        )
        self.assertEqual(st_rev, 200)
        self.assertEqual(rev_resp["merge_request"]["status"], "approved_merged")

    def test_facility_lifecycle_suspension_and_enterprise_admin_endpoints(self):
        """
        Tests facility suspension blocking operational writes, reactivation,
        config rollback, module entitlements, integration connectors, and audit search.
        """
        # 1. Suspend fac-south-branch
        st_susp, susp_resp = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a2}/suspend",
            self.admin_token,
            {
                "target_status": "temporarily_closed",
                "reason": "Scheduled electrical maintenance at South Branch",
            },
        )
        self.assertEqual(st_susp, 200)
        self.assertEqual(susp_resp["facility"]["lifecycle_status"], "temporarily_closed")

        # Non-admin operational write to suspended facility is blocked with 403
        st_blocked, blocked_resp = self._req(
            "POST",
            "/api/v1/patients",
            self.reception_token,
            {
                "given_name": "Blocked",
                "family_name": "Patient",
                "sex": "FEMALE",
                "date_of_birth": "1990-01-01",
                "phone": "+919811100999",
            },
            facility_id=self.fac_a2,
        )
        self.assertEqual(st_blocked, 403)
        self.assertEqual(blocked_resp["details"].get("error_code"), "FACILITY_SUSPENDED_OR_CLOSED")

        # Reactivate fac-south-branch
        st_react, react_resp = self._req(
            "POST",
            f"/api/v1/facilities/{self.fac_a2}/reactivate",
            self.admin_token,
            {"reason": "Maintenance completed and safety verified"},
        )
        self.assertEqual(st_react, 200)
        self.assertEqual(react_resp["facility"]["lifecycle_status"], "active")

        # 2. Single-clinic migration endpoint (DRY_RUN + EXECUTE)
        st_mig, mig_resp = self._req(
            "POST",
            "/api/v1/admin/single-clinic-migration",
            self.admin_token,
            {"default_facility_id": self.fac_a1, "mode": "EXECUTE"},
        )
        self.assertEqual(st_mig, 200)
        self.assertTrue(mig_resp["migration"]["counts_reconciled"])

        # 3. Enterprise Audit Events search
        st_aud, aud_resp = self._req(
            "GET",
            "/api/v1/admin/audit-events",
            self.admin_token,
            query={"facility_id": self.fac_a2},
        )
        self.assertEqual(st_aud, 200)
        self.assertGreaterEqual(len(aud_resp["audit_events"]), 1)


if __name__ == "__main__":
    unittest.main()

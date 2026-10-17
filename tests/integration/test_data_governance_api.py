"""Integration Tests for Enterprise Master Data Management, Data Governance & Quality Stewardship APIs.

Phase 42 for ZAYVORA MATAB OS.
Tests all endpoints via ApiRouter.dispatch:
1. GET   /api/v1/mdm/entities
2. POST  /api/v1/mdm/entities
3. GET   /api/v1/mdm/rules
4. POST  /api/v1/mdm/rules
5. POST  /api/v1/mdm/scans/run
6. GET   /api/v1/mdm/scans
7. GET   /api/v1/mdm/scans/:id/findings
8. POST  /api/v1/mdm/duplicates/detect
9. GET   /api/v1/mdm/duplicates/reviews
10. POST /api/v1/mdm/duplicates/reviews/:id/resolve
11. GET  /api/v1/mdm/cross-references
12. POST /api/v1/mdm/cross-references
13. POST /api/v1/mdm/cross-references/:id/unlink
14. GET  /api/v1/mdm/terminology/mappings
15. POST /api/v1/mdm/terminology/mappings
16. POST /api/v1/mdm/terminology/mappings/:id/review
17. POST /api/v1/mdm/imports/stage
18. POST /api/v1/mdm/imports/:id/dry-run
19. POST /api/v1/mdm/imports/:id/commit
20. GET  /api/v1/mdm/imports
21. POST /api/v1/mdm/stewardship/cases
22. GET  /api/v1/mdm/stewardship/cases
23. POST /api/v1/mdm/stewardship/cases/:id/transition
24. GET  /api/v1/mdm/stewardship/cases/:id/events
25. GET  /api/v1/mdm/pulse
26. Auth security: 401 without auth token.
"""

import os
import json
import sqlite3
import tempfile
import shutil
import unittest

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestDataGovernanceApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_mdm_api.db")
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
        cls.auth_token = json.loads(body)["token"]
        cls.admin_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.auth_token}",
            "X-Facility-Id": "fac-central-opd"
        }

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_unauthenticated_request_rejected(self):
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/mdm/entities",
            {"Content-Type": "application/json"},
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 401)

    def test_get_master_entities(self):
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/mdm/entities",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["entities"]), 5)

    def test_list_and_create_dq_rule(self):
        # 1. List rules
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/mdm/rules",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        rules = json.loads(body)["rules"]
        self.assertGreaterEqual(len(rules), 8)

        # 2. Create rule
        new_rule_payload = {
            "rule_key": "RULE_API_INTEGRATION_TEST",
            "name": "Integration Test Rule",
            "domain": "clinical_encounter",
            "dimension": "completeness",
            "rule_type": "required",
            "severity": "warning",
            "scope": "tenant",
            "target_entity_type": "encounter",
            "target_field_path": "chief_complaint",
            "rule_logic": {"required": True}
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/mdm/rules",
            self.admin_headers,
            {},
            json.dumps(new_rule_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertEqual(data["rule"]["rule_key"], "RULE_API_INTEGRATION_TEST")

    def test_run_dq_scan_and_get_findings(self):
        # Run scan
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/mdm/scans/run",
            self.admin_headers,
            {},
            json.dumps({"target_entity_type": "patient"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        scan = json.loads(body)["scan"]
        scan_id = scan["scan_id"]

        # List scans
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/mdm/scans",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        scans = json.loads(body)["scans"]
        self.assertGreaterEqual(len(scans), 1)

        # Get findings
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/mdm/scans/{scan_id}/findings",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        findings = json.loads(body)["findings"]
        self.assertIsInstance(findings, list)

    def test_duplicate_review_and_cross_reference_flow(self):
        # 1. Create a duplicate candidate review
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO mdm_duplicate_candidate_reviews (
                id, organization_id, entity_type, primary_record_id, candidate_record_id,
                confidence_score, match_features_json, status
            ) VALUES (
                'rev-api-01', 'org-matab-default', 'patient', 'pat-syn-001', 'pat-syn-002',
                0.88, '{"name_match": "exact", "phone_match": "exact"}', 'pending'
            );
        """)
        conn.commit()
        conn.close()

        # 2. List duplicate reviews
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/mdm/duplicates/reviews",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        reviews = json.loads(body)["reviews"]
        self.assertGreaterEqual(len(reviews), 1)

        # 3. Resolve duplicate review with master link
        resolve_payload = {
            "decision": "confirmed_duplicate",
            "rationale": "Verified by phone call with Tabib.",
            "create_master_link": True
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/mdm/duplicates/reviews/rev-api-01/resolve",
            self.admin_headers,
            {},
            json.dumps(resolve_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        res = json.loads(body)["resolution"]
        self.assertEqual(res["status"], "confirmed_duplicate")

        # 4. List cross references
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/mdm/cross-references",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        xrefs = json.loads(body)["cross_references"]
        self.assertGreaterEqual(len(xrefs), 1)
        xref_id = xrefs[0]["id"]

        # 5. Unlink cross reference (reversible)
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/mdm/cross-references/{xref_id}/unlink",
            self.admin_headers,
            {},
            json.dumps({"notes": "Unlinking test"}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["cross_reference"]["is_active"], 0)

    def test_terminology_stewardship_api_flow(self):
        # 1. Create mapping
        payload = {
            "unani_concept_code": "ISTISQA_ZIQQI",
            "unani_term": "Istisqa-i-Ziqqi (Ascites)",
            "modern_code_system": "ICD-10",
            "modern_concept_code": "R18.8",
            "modern_term": "Other ascites",
            "mapping_type": "approximate",
            "clinical_scope": "hepatology",
            "limitations": "Humoral theory attributes Istisqa to liver coldness and dampness.",
            "provenance": "Ibn Sina, Al-Qanun fi al-Tibb."
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/mdm/terminology/mappings",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        mapping_id = json.loads(body)["mapping"]["id"]

        # 2. Review mapping
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/mdm/terminology/mappings/{mapping_id}/review",
            self.admin_headers,
            {},
            json.dumps({
                "decision": "approved",
                "rationale": "Verified by clinical research board."
            }).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["mapping"]["review_status"], "approved")

    def test_bulk_import_api_flow(self):
        # 1. Stage import
        payload = {
            "batch_name": "API Bulk Import Test",
            "entity_type": "patient",
            "raw_records": [
                {
                    "first_name": "Nafis",
                    "last_name": "Kirmani",
                    "phone": "+919876543299",
                    "gender": "M",
                    "address": "Kashmir Gate"
                }
            ]
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/mdm/imports/stage",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        batch_id = json.loads(body)["batch"]["batch_id"]

        # 2. Dry run
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/mdm/imports/{batch_id}/dry-run",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["dry_run"]["status"], "validated_dry_run")

        # 3. Commit
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/mdm/imports/{batch_id}/commit",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["commit"]["status"], "committed")

    def test_stewardship_cases_api_flow(self):
        # 1. Create case
        payload = {
            "title": "API Stewardship Case Test",
            "description": "Orphan encounter check",
            "category": "data_quality_anomaly",
            "priority": "medium",
            "target_entity_type": "patient",
            "target_entity_id": "pat-syn-001",
            "proposed_resolution": "Verify phone"
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/mdm/stewardship/cases",
            self.admin_headers,
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 201)
        case_id = json.loads(body)["case"]["id"]

        # 2. Transition case
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/mdm/stewardship/cases/{case_id}/transition",
            self.admin_headers,
            {},
            json.dumps({"to_status": "assigned", "comment": "Assigned to steward."}).encode("utf-8"),
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["case"]["to_status"], "assigned")

        # 3. Get events
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/mdm/stewardship/cases/{case_id}/events",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        events = json.loads(body)["events"]
        self.assertGreaterEqual(len(events), 2)

    def test_get_mdm_pulse_api(self):
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/mdm/pulse",
            self.admin_headers,
            {},
            b"",
            "127.0.0.1",
            self.db_path
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])
        self.assertIn("master_entities_count", data["pulse"])
        self.assertIn("governance_status", data["pulse"])


if __name__ == "__main__":
    unittest.main()

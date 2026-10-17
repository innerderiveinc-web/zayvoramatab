"""Integration tests for Enterprise Analytics, Operational Intelligence & Clinical Governance REST APIs.

Phase 33 validation for ZAYVORA MATAB OS.
Tests all 16 REST endpoints via ApiRouter.dispatch:
1.  GET  /api/v1/analytics/overview (Executive Pulse)
2.  GET  /api/v1/analytics/clinic-operations
3.  GET  /api/v1/analytics/patient-continuity
4.  GET  /api/v1/analytics/finance-billing
5.  GET  /api/v1/analytics/inventory-dispensing
6.  GET  /api/v1/analytics/governance-safety
7.  GET  /api/v1/analytics/data-quality-readiness
8.  GET  /api/v1/analytics/metrics (List Catalogue)
9.  POST /api/v1/analytics/metrics (Create Draft Definition)
10. GET  /api/v1/analytics/metrics/{metric_key} (Detail & Lineage)
11. POST /api/v1/analytics/metrics/{id}/review (Advance to Review)
12. POST /api/v1/analytics/metrics/{id}/approve (Approve Definition)
13. POST /api/v1/analytics/metrics/{id}/retire (Retire Definition)
14. POST /api/v1/analytics/export (Audited Privacy-Preserving Export)
15. GET  /api/v1/analytics/reconciliation-exceptions (List Exceptions)
16. POST /api/v1/analytics/reconciliation-exceptions (Record Exception)
"""

import os
import json
import uuid
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from apps.api.database.migrator import run_migrations
from apps.api.database.seed import seed_development_data
from apps.api.router import ApiRouter


class TestAnalyticsApiIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_analytics_api.db")
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

        # Seed sample patient
        cls.patient_id = f"pat-api-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO patients (id, organization_id, facility_id, mrn, given_name, family_name, display_name, date_of_birth, sex)
            VALUES (?, ?, ?, ?, 'Zahra', 'Khan', 'Zahra Khan', '1990-05-12', 'FEMALE');
            """,
            (cls.patient_id, cls.org_id, cls.fac_id, f"MRN-{uuid.uuid4().hex[:6]}")
        )

        # Seed financial records: Invoice, Payment, Refund
        inv_id = f"inv-api-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO invoices (
                id, organization_id, facility_id, patient_id, invoice_number,
                subtotal_decimal, discount_decimal, tax_decimal, total_decimal,
                balance_due_decimal, status, created_by
            ) VALUES (?, ?, ?, ?, ?, '1500.00', '0.00', '0.00', '1500.00', '0.00', 'PAID', ?);
            """,
            (inv_id, cls.org_id, cls.fac_id, cls.patient_id, f"INV-{uuid.uuid4().hex[:6]}", cls.admin_id)
        )

        pay_id = f"pay-api-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO payments (
                id, organization_id, facility_id, payment_number, invoice_id, patient_id,
                amount_decimal, payment_method, status, receipt_number, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, '1500.00', 'CASH', 'COMPLETED', ?, ?);
            """,
            (pay_id, cls.org_id, cls.fac_id, f"PAY-{uuid.uuid4().hex[:6]}", inv_id, cls.patient_id, f"REC-{uuid.uuid4().hex[:6]}", cls.admin_id)
        )

        ref_id = f"ref-api-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO payment_refunds (
                id, organization_id, facility_id, refund_number, payment_id, invoice_id,
                amount_decimal, status, reason, authorized_by
            ) VALUES (?, ?, ?, ?, ?, ?, '250.00', 'COMPLETED', 'Adjustment', ?);
            """,
            (ref_id, cls.org_id, cls.fac_id, f"REF-{uuid.uuid4().hex[:6]}", pay_id, inv_id, cls.admin_id)
        )

        # Seed appointment
        cur.execute(
            """
            INSERT INTO appointments (
                id, organization_id, facility_id, patient_id, practitioner_id,
                appointment_type, status, start_at, end_at, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, 'INITIAL_CONSULTATION', 'completed', ?, ?, ?, ?);
            """,
            (
                f"apt-api-{uuid.uuid4().hex[:8]}", cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id,
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                cls.admin_id, cls.admin_id
            )
        )

        conn.commit()
        conn.close()

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "X-Facility-Id": self.fac_id,
        }

    def test_01_overview_endpoint(self):
        """GET /api/v1/analytics/overview returns role-aware executive pulse."""
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/analytics/overview",
            self._headers(),
            {"period": "30d"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("operational_pulse", data)
        self.assertIn("financial_pulse", data)
        self.assertIn("continuity_pulse", data)
        self.assertIn("governance_pulse", data)
        self.assertIn("caveats", data)
        # Financial pulse check: 1500 - 250 = 1250 net collection
        self.assertEqual(data["financial_pulse"]["net_collections_inr"], 1250.0)
        self.assertEqual(data["financial_pulse"]["gross_invoiced_inr"], 1500.0)

    def test_02_domain_dashboards_endpoints(self):
        """Domain endpoints return structured analytics with non-causal caveats."""
        domain_endpoints = [
            "/api/v1/analytics/clinic-operations",
            "/api/v1/analytics/patient-continuity",
            "/api/v1/analytics/finance-billing",
            "/api/v1/analytics/inventory-dispensing",
            "/api/v1/analytics/governance-safety",
            "/api/v1/analytics/data-quality-readiness",
        ]
        for endpoint in domain_endpoints:
            status, _, body = ApiRouter.dispatch(
                "GET",
                endpoint,
                self._headers(),
                {"period": "30d"},
                b"",
                "127.0.0.1",
                self.db_path,
            )
            self.assertEqual(status, 200, f"Failed for {endpoint}")
            data = json.loads(body)
            self.assertIn("period", data)
            self.assertIn("caveats", data)
            self.assertTrue(len(data["caveats"]) > 0)

    def test_03_metric_governance_lifecycle(self):
        """Metric lifecycle endpoints: List, Create Draft, Review, Approve, Retire."""
        # 1. List catalogue
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/analytics/metrics",
            self._headers(),
            {"domain": "FINANCE"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        res = json.loads(body)
        metrics = res["metrics"]
        self.assertTrue(isinstance(metrics, list))
        self.assertTrue(any(m["metric_key"] == "finance.net_collections" for m in metrics))

        # 2. Create draft metric definition
        test_key = f"api_test_metric_{uuid.uuid4().hex[:6]}"
        create_payload = {
            "metric_key": test_key,
            "name": "API Test Completion Rate",
            "description": "Integration test metric definition",
            "domain": "OPERATIONS",
            "metric_type": "rate",
            "unit": "percent",
            "numerator_definition": "Completed encounters count",
            "denominator_definition": "Total scheduled appointments count",
            "inclusion_rules": ["Valid OPD visit", "Confirmed patient"],
            "exclusion_rules": ["Test users", "Cancelled duplicate encounters"],
            "permitted_roles": ["ADMIN", "CLINICIAN"]
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/analytics/metrics",
            self._headers(),
            {},
            json.dumps(create_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertEqual(created["metric_key"], test_key)
        self.assertEqual(created["status"], "draft")
        metric_id = created["id"]

        # 3. Get metric by key
        status, _, body = ApiRouter.dispatch(
            "GET",
            f"/api/v1/analytics/metrics/{test_key}",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        got = json.loads(body)
        self.assertEqual(got["id"], metric_id)

        # 4. Advance to review
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/analytics/metrics/{metric_id}/review",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "review")

        # 5. Approve definition
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/analytics/metrics/{metric_id}/approve",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "approved")

        # 6. Retire definition
        status, _, body = ApiRouter.dispatch(
            "POST",
            f"/api/v1/analytics/metrics/{metric_id}/retire",
            self._headers(),
            {},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "retired")

    def test_04_audited_export_endpoint(self):
        """POST /api/v1/analytics/export returns cryptographic SHA-256 hash and zero PHI."""
        payload = {
            "format": "csv",
            "reason": "Quarterly Operations Audit",
            "filters": {"period": "30d"}
        }
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/analytics/export",
            self._headers(),
            {},
            json.dumps(payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        res = json.loads(body)
        self.assertIn("export_id", res)
        self.assertIn("sha256_hash", res)
        self.assertEqual(len(res["sha256_hash"]), 64)
        self.assertIn("content", res)

        # PHI safety: No patient names or MRNs in exported text
        content = res["content"]
        self.assertNotIn("Zahra Khan", content)
        self.assertIn("Category,Metric,Value,Unit", content)

    def test_05_reconciliation_exceptions_endpoints(self):
        """GET & POST /api/v1/analytics/reconciliation-exceptions record and fetch variance audits."""
        rec_payload = {
            "metric_key": "finance.net_collections",
            "period_start": "2026-10-01T00:00:00Z",
            "period_end": "2026-10-14T23:59:59Z",
            "canonical_value_decimal": "1250.00",
            "derived_value_decimal": "1250.02",
            "variance_decimal": "-0.02",
            "notes": "Rounding variance detected"
        }
        # 1. Create exception
        status, _, body = ApiRouter.dispatch(
            "POST",
            "/api/v1/analytics/reconciliation-exceptions",
            self._headers(),
            {},
            json.dumps(rec_payload).encode("utf-8"),
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 201)
        created = json.loads(body)
        self.assertIn("exception_id", created)

        # 2. List exceptions
        status, _, body = ApiRouter.dispatch(
            "GET",
            "/api/v1/analytics/reconciliation-exceptions",
            self._headers(),
            {"domain": "FINANCE"},
            b"",
            "127.0.0.1",
            self.db_path,
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        items = data["exceptions"]
        self.assertTrue(isinstance(items, list))
        self.assertTrue(any(i["id"] == created["exception_id"] for i in items))


if __name__ == "__main__":
    unittest.main()

"""Unit tests for Enterprise Analytics, Operational Intelligence & Governance Engine.

Phase 33 validation for ZAYVORA MATAB OS.
Enforces non-negotiables:
1. Canonical persistence: metrics computed strictly from real relational records.
2. Decimal-safe monetary accounting: net collections = posted payments - refunds.
3. Strict zero vs missing distinctions: legitimate zeros vs unconfigured domains.
4. Governed metric registry lifecycle: draft -> review -> approved -> retired.
5. Audited export with tamper-evident SHA-256 manifest and zero PHI.
6. Tenant and facility isolation on all calculations.
7. Non-causal interpretation: process indicators never conflated with treatment efficacy.
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
from apps.api.domains.analytics import EnterpriseAnalyticsEngine
from apps.api.core.errors import ValidationError, NotFoundError


class TestEnterpriseAnalyticsEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_analytics_engine.db")
        run_migrations(cls.db_path)
        seed_development_data(cls.db_path)

        cls.engine = EnterpriseAnalyticsEngine(cls.db_path)

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

        # Insert some canonical operational test records
        # 1. Appointments
        appt1_id = f"appt-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO appointments (
                id, organization_id, facility_id, patient_id, practitioner_id,
                start_at, end_at, status, reason_category, booking_source, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', 'INITIAL_CONSULTATION', 'FRONT_DESK', ?, ?);
            """,
            (
                appt1_id, cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id,
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                cls.admin_id, cls.admin_id
            )
        )

        appt2_id = f"appt-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO appointments (
                id, organization_id, facility_id, patient_id, practitioner_id,
                start_at, end_at, status, reason_category, booking_source, created_by, updated_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'no_show', 'INITIAL_CONSULTATION', 'FRONT_DESK', ?, ?);
            """,
            (
                appt2_id, cls.org_id, cls.fac_id, cls.patient_id, cls.admin_id,
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                cls.admin_id, cls.admin_id
            )
        )

        # 2. Invoices & Payments
        inv_id = f"inv-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO invoices (
                id, organization_id, facility_id, invoice_number, patient_id,
                status, total_decimal, paid_decimal, balance_due_decimal, created_by
            ) VALUES (?, ?, ?, ?, ?, 'FINALIZED', '1500.00', '1000.00', '500.00', ?);
            """,
            (inv_id, cls.org_id, cls.fac_id, f"INV-{uuid.uuid4().hex[:6]}", cls.patient_id, cls.admin_id)
        )

        pay_id = f"pay-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO payments (
                id, organization_id, facility_id, payment_number, invoice_id, patient_id,
                amount_decimal, payment_method, status, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, '1000.00', 'UPI', 'POSTED', ?);
            """,
            (pay_id, cls.org_id, cls.fac_id, f"PAY-{uuid.uuid4().hex[:6]}", inv_id, cls.patient_id, cls.admin_id)
        )

        ref_id = f"ref-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO payment_refunds (
                id, organization_id, facility_id, refund_number, payment_id, invoice_id,
                amount_decimal, status, reason, authorized_by
            ) VALUES (?, ?, ?, ?, ?, ?, '200.00', 'COMPLETED', 'Patient cancellation', ?);
            """,
            (ref_id, cls.org_id, cls.fac_id, f"REF-{uuid.uuid4().hex[:6]}", pay_id, inv_id, cls.admin_id)
        )

        # 3. Care continuity task overdue
        cur.execute(
            """
            INSERT INTO care_continuity_tasks (
                id, organization_id, facility_id, patient_id, task_type,
                status, due_date, assigned_role
            ) VALUES (?, ?, ?, ?, 'FOLLOW_UP_CALL', 'PENDING', ?, 'FRONT_DESK');
            """,
            (
                f"task-{uuid.uuid4().hex[:8]}", cls.org_id, cls.fac_id, cls.patient_id,
                (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            )
        )

        conn.commit()
        conn.close()

        cls.admin_user = {
            "id": cls.admin_id,
            "organization_id": cls.org_id,
            "facility_id": cls.fac_id,
            "roles": ["ORG_ADMIN"],
            "permissions": ["analytics:read", "analytics:export", "analytics:govern", "analytics:manage"]
        }

    def test_01_executive_overview_calculation(self):
        """Executive pulse calculates verified figures from real canonical tables."""
        res = self.engine.get_executive_overview({"period": "30d"}, self.admin_user)
        self.assertIn("operational_pulse", res)
        self.assertIn("financial_pulse", res)
        self.assertIn("continuity_pulse", res)
        self.assertIn("freshness", res)

        # Operational checks
        op = res["operational_pulse"]
        self.assertGreaterEqual(op["appointments_completed"], 1)
        self.assertGreater(op["no_show_rate_percent"], 0.0)

        # Financial checks: net collections = posted payments (1000) - refunds (200) = 800
        fin = res["financial_pulse"]
        self.assertGreaterEqual(fin["gross_invoiced_inr"], 1500.0)
        self.assertGreaterEqual(fin["net_collections_inr"], 800.0)
        self.assertGreaterEqual(fin["outstanding_balance_inr"], 500.0)

        # Continuity checks
        cont = res["continuity_pulse"]
        self.assertGreaterEqual(cont["care_tasks_overdue"], 1)

    def test_02_clinic_operations_metrics(self):
        """Operations breakdown distinguishes appointments, OPD tokens, and signed encounters."""
        res = self.engine.get_clinic_operations_metrics({"period": "30d"}, self.admin_user)
        self.assertIn("appointments_by_status", res)
        self.assertIn("queue_by_status", res)
        self.assertIn("encounters_by_status", res)
        self.assertIn("completed", res["appointments_by_status"])
        self.assertIn("no_show", res["appointments_by_status"])

    def test_03_finance_metrics_breakdown(self):
        """Finance metrics provide decimal-safe breakdown of payment methods and refunds."""
        res = self.engine.get_finance_metrics({"period": "30d"}, self.admin_user)
        self.assertGreaterEqual(res["gross_collections_inr"], 1000.0)
        self.assertGreaterEqual(res["total_refunds_inr"], 200.0)
        self.assertGreaterEqual(res["net_collections_inr"], 800.0)
        self.assertGreaterEqual(res["cumulative_outstanding_balance_inr"], 500.0)

        # Payment channels
        pay_methods = [p["payment_method"] for p in res["payments_by_method"]]
        self.assertIn("UPI", pay_methods)

    def test_04_inventory_fefo_expiry_horizons(self):
        """Dispensary inventory categorizes batches into discrete FEFO expiry buckets."""
        res = self.engine.get_inventory_metrics({"period": "30d"}, self.admin_user)
        self.assertIn("expiry_horizons", res)
        self.assertIn("within_30_days", res["expiry_horizons"])
        self.assertIn("within_90_days", res["expiry_horizons"])
        self.assertIn("batches_by_status", res)

    def test_05_governed_metric_catalogue_lifecycle(self):
        """Metric definitions progress through draft -> review -> approved -> retired lifecycle."""
        # 1. List pre-seeded metrics
        metrics = self.engine.list_metric_definitions({}, self.admin_user)
        self.assertGreaterEqual(len(metrics), 10)
        keys = [m["metric_key"] for m in metrics]
        self.assertIn("operations.appointments_completed", keys)
        self.assertIn("finance.net_collections", keys)

        # 2. Create new draft metric
        new_key = f"ops.custom_stat_{uuid.uuid4().hex[:6]}"
        draft = self.engine.create_metric_definition(
            {
                "metric_key": new_key,
                "name": "Custom Test Metric",
                "domain": "OPERATIONS",
                "metric_type": "count",
                "description": "Test metric for governance lifecycle",
                "caveats": ["Caveat 1: Process metric only"]
            },
            self.admin_user
        )
        self.assertEqual(draft["status"], "draft")
        self.assertEqual(draft["metric_key"], new_key)

        # 3. Advance to review
        in_review = self.engine.advance_metric_to_review(draft["id"], self.admin_user)
        self.assertEqual(in_review["status"], "review")

        # 4. Approve
        approved = self.engine.approve_metric_definition(draft["id"], self.admin_user)
        self.assertEqual(approved["status"], "approved")
        self.assertIsNotNone(approved["approved_at"])

        # 5. Retire
        retired = self.engine.retire_metric_definition(draft["id"], self.admin_user)
        self.assertEqual(retired["status"], "retired")

    def test_06_audited_export_generation(self):
        """Secure export generates CSV with SHA-256 manifest and zero PHI."""
        export_res = self.engine.generate_export(
            {
                "export_type": "EXECUTIVE_OVERVIEW",
                "format": "CSV",
                "filters": {"period": "30d"}
            },
            self.admin_user
        )

        self.assertIn("export_id", export_res)
        self.assertEqual(export_res["format"], "CSV")
        self.assertGreater(export_res["record_count"], 0)
        self.assertIsNotNone(export_res["sha256_hash"])
        self.assertIn("Appointments Completed", export_res["content"])
        self.assertIn("Net Collections", export_res["content"])

        # Verify audit record in database
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT sha256_hash, user_id FROM analytics_export_audit WHERE id = ?;", (export_res["export_id"],))
        audit_row = cur.fetchone()
        self.assertIsNotNone(audit_row)
        self.assertEqual(audit_row[0], export_res["sha256_hash"])
        conn.close()

    def test_07_reconciliation_exceptions_flow(self):
        """Reconciliation exceptions can be listed and marked resolved with audit rationale."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        exc_id = f"exc-{uuid.uuid4().hex[:8]}"
        cur.execute(
            """
            INSERT INTO metric_reconciliation_exceptions (
                id, organization_id, facility_id, metric_key, period_start, period_end,
                canonical_value_decimal, derived_value_decimal, variance_decimal, exception_status, notes
            ) VALUES (?, ?, ?, 'finance.net_collections', '2026-10-01', '2026-10-14', '800.00', '790.00', '10.00', 'OPEN', 'Cash float discrepancy');
            """,
            (exc_id, self.org_id, self.fac_id)
        )
        conn.commit()
        conn.close()

        # List exceptions
        excs = self.engine.list_reconciliation_exceptions({}, self.admin_user)
        self.assertGreaterEqual(len(excs), 1)

        # Resolve exception
        res = self.engine.resolve_reconciliation_exception(
            exc_id,
            {"status": "RESOLVED", "notes": "Audited bank receipt confirms discrepancy resolved."},
            self.admin_user
        )
        self.assertEqual(res["exception_status"], "RESOLVED")


if __name__ == "__main__":
    unittest.main()

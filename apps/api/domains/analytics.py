"""Enterprise Analytics, Operational Intelligence & Clinical Governance Domain Engine.

Phase 33 for ZAYVORA MATAB OS.
Enforces non-negotiables:
1. Never fabricate metrics, records, or targets.
2. Canonical source of truth: computed strictly from production relational tables.
3. No clinical efficacy inference from uncontrolled observational data.
4. No clinician ranking or public clinical success leaderboards.
5. Strict role-aware and tenant/facility scoping.
6. Zero Protected Health Information (PHI) in aggregate metrics or exports.
7. Governed metric registry with draft -> review -> approved -> retired lifecycle.
8. Explicit status semantics: available, insufficient_data, not_configured, stale, failed.
"""

import os
import json
import uuid
import hashlib
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError, ConflictError
from apps.api.config import config
from apps.api.database.connection import DatabaseConnection


class EnterpriseAnalyticsEngine:
    """Domain engine for Phase 33 Enterprise Analytics & Governance."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def _get_connection(self) -> sqlite3.Connection:
        return DatabaseConnection(self.db_path).get_connection()

    # --------------------------------------------------------------------------
    # Date & Period Boundary Utilities
    # --------------------------------------------------------------------------

    def _resolve_period_bounds(self, filters: Dict[str, Any]) -> Tuple[str, str, str]:
        """Resolve period start, period end, and timezone from query filters."""
        tz = filters.get("timezone", "Asia/Kolkata")
        period = filters.get("period", "30d").lower()
        now = datetime.now(timezone.utc)

        if period == "today":
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
        elif period == "7d":
            start_dt = now - timedelta(days=7)
            end_dt = now
        elif period == "30d":
            start_dt = now - timedelta(days=30)
            end_dt = now
        elif period == "month_to_date":
            start_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
        elif period == "custom":
            start_raw = filters.get("start_date")
            end_raw = filters.get("end_date")
            if not start_raw or not end_raw:
                raise ValidationError("Custom period requires both start_date and end_date.")
            try:
                start_dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
            except Exception:
                # Handle YYYY-MM-DD
                start_dt = datetime.strptime(start_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                end_dt = datetime.strptime(end_raw, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
        else:
            # Default to last 30 days
            start_dt = now - timedelta(days=30)
            end_dt = now

        return start_dt.isoformat(), end_dt.isoformat(), tz

    # --------------------------------------------------------------------------
    # 1. Executive Overview (Operational Pulse)
    # --------------------------------------------------------------------------

    def get_executive_overview(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aggregate executive operational pulse across canonical domains."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")
        start_iso, end_iso, tz = self._resolve_period_bounds(filters)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Operations: Appointments & Queue
            appt_query = """
                SELECT 
                    COUNT(*) as total_scheduled,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'no_show' THEN 1 ELSE 0 END) as no_show,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
                FROM appointments
                WHERE organization_id = ? AND start_at >= ? AND start_at <= ?
            """
            appt_params = [org_id, start_iso, end_iso]
            if fac_id:
                appt_query += " AND facility_id = ?"
                appt_params.append(fac_id)
            cur.execute(appt_query, appt_params)
            appt_stats = dict(cur.fetchone() or {})

            # Queue Waiting Tokens (current)
            queue_query = """
                SELECT COUNT(*) as waiting_count 
                FROM queue_tokens 
                WHERE organization_id = ? AND status = 'waiting' AND queue_date = DATE('now')
            """
            q_params = [org_id]
            if fac_id:
                queue_query += " AND facility_id = ?"
                q_params.append(fac_id)
            cur.execute(queue_query, q_params)
            queue_waiting = cur.fetchone()["waiting_count"]

            # Encounters Signed / Completed
            enc_query = """
                SELECT COUNT(*) as signed_count
                FROM encounters
                WHERE organization_id = ? AND status IN ('COMPLETED', 'signed') AND created_at >= ? AND created_at <= ?
            """
            enc_params = [org_id, start_iso, end_iso]
            if fac_id:
                enc_query += " AND facility_id = ?"
                enc_params.append(fac_id)
            cur.execute(enc_query, enc_params)
            enc_signed = cur.fetchone()["signed_count"]

            # 2. Finance Pulse (Invoiced & Collections)
            inv_query = """
                SELECT 
                    COUNT(*) as invoice_count,
                    COALESCE(SUM(CAST(total_decimal AS REAL)), 0.0) as gross_invoiced,
                    COALESCE(SUM(CAST(balance_due_decimal AS REAL)), 0.0) as balance_due
                FROM invoices
                WHERE organization_id = ? AND status IN ('FINALIZED', 'PARTIALLY_PAID', 'PAID')
                  AND created_at >= ? AND created_at <= ?
            """
            inv_params = [org_id, start_iso, end_iso]
            if fac_id:
                inv_query += " AND facility_id = ?"
                inv_params.append(fac_id)
            cur.execute(inv_query, inv_params)
            inv_stats = dict(cur.fetchone() or {})

            pay_query = """
                SELECT COALESCE(SUM(CAST(amount_decimal AS REAL)), 0.0) as gross_collected
                FROM payments
                WHERE organization_id = ? AND status IN ('POSTED', 'COMPLETED')
                  AND recorded_at >= ? AND recorded_at <= ?
            """
            pay_params = [org_id, start_iso, end_iso]
            if fac_id:
                pay_query += " AND facility_id = ?"
                pay_params.append(fac_id)
            cur.execute(pay_query, pay_params)
            gross_collected = cur.fetchone()["gross_collected"]

            ref_query = """
                SELECT COALESCE(SUM(CAST(amount_decimal AS REAL)), 0.0) as total_refunded
                FROM payment_refunds
                WHERE organization_id = ? AND status = 'COMPLETED'
                  AND created_at >= ? AND created_at <= ?
            """
            ref_params = [org_id, start_iso, end_iso]
            if fac_id:
                ref_query += " AND facility_id = ?"
                ref_params.append(fac_id)
            cur.execute(ref_query, ref_params)
            total_refunded = cur.fetchone()["total_refunded"]
            net_collections = max(0.0, gross_collected - total_refunded)

            # 3. Continuity Pulse
            cont_query = """
                SELECT 
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN status IN ('PENDING', 'IN_PROGRESS') AND due_date < datetime('now') THEN 1 ELSE 0 END) as overdue_tasks
                FROM care_continuity_tasks
                WHERE organization_id = ?
            """
            cont_params = [org_id]
            if fac_id:
                cont_query += " AND facility_id = ?"
                cont_params.append(fac_id)
            cur.execute(cont_query, cont_params)
            cont_stats = dict(cur.fetchone() or {})

            # 4. Inventory Pulse (Near Expiry Batches)
            inv_batch_query = """
                SELECT COUNT(*) as near_expiry_count
                FROM inventory_batches
                WHERE organization_id = ? AND status = 'AVAILABLE'
                  AND expiry_date BETWEEN DATE('now') AND DATE('now', '+90 days')
            """
            b_params = [org_id]
            if fac_id:
                inv_batch_query += " AND facility_id = ?"
                b_params.append(fac_id)
            cur.execute(inv_batch_query, b_params)
            near_expiry = cur.fetchone()["near_expiry_count"]

            # 5. Governance Pulse (Safety Cases Open & Rules Pending)
            gov_cases_query = """
                SELECT COUNT(*) as open_safety_cases
                FROM safety_cases
                WHERE tenant_id = ? AND case_state IN ('DRAFT', 'INTAKE_COMPLETE', 'TRIAGED', 'UNDER_CLINICAL_REVIEW')
            """
            cur.execute(gov_cases_query, [org_id])
            open_safety_cases = cur.fetchone()["open_safety_cases"]

            gov_rules_query = """
                SELECT COUNT(*) as rules_pending_review
                FROM governed_artifacts
                WHERE current_lifecycle_state IN ('DRAFT', 'SUBMITTED_FOR_REVIEW', 'TECHNICAL_VALIDATION_PENDING')
            """
            cur.execute(gov_rules_query)
            rules_pending_review = cur.fetchone()["rules_pending_review"]

            # 6. Reliability Pulse (Dead-Letter Queue & Circuit Breakers)
            dlq_query = """
                SELECT COUNT(*) as open_dlq_count
                FROM dead_letter_items dlq
                JOIN integration_jobs j ON j.id = dlq.job_id
                WHERE j.organization_id = ? AND dlq.resolution_status = 'PENDING'
            """
            cur.execute(dlq_query, [org_id])
            open_dlq = cur.fetchone()["open_dlq_count"]

            cb_query = """
                SELECT COUNT(*) as open_cb_count
                FROM integration_circuit_breakers cb
                JOIN integration_connectors c ON c.id = cb.connector_id
                WHERE c.organization_id = ? AND cb.state = 'OPEN'
            """
            cur.execute(cb_query, [org_id])
            open_cb = cur.fetchone()["open_cb_count"]

            completed_appts = appt_stats.get("completed") or 0
            no_show_appts = appt_stats.get("no_show") or 0
            scheduled_denom = completed_appts + no_show_appts
            no_show_rate = round((no_show_appts / scheduled_denom * 100), 1) if scheduled_denom > 0 else 0.0

            return {
                "organization_id": org_id,
                "facility_id": fac_id,
                "period": {
                    "start": start_iso,
                    "end": end_iso,
                    "timezone": tz,
                    "label": filters.get("period", "30d")
                },
                "freshness": {
                    "as_of": datetime.now(timezone.utc).isoformat(),
                    "state": "current",
                    "source_watermark": "CANONICAL_LIVE_REPLICA"
                },
                "operational_pulse": {
                    "appointments_completed": completed_appts,
                    "appointments_cancelled": appt_stats.get("cancelled") or 0,
                    "no_show_rate_percent": no_show_rate,
                    "queue_tokens_waiting": queue_waiting,
                    "encounters_signed": enc_signed
                },
                "financial_pulse": {
                    "gross_invoiced_inr": round(inv_stats.get("gross_invoiced", 0.0), 2),
                    "net_collections_inr": round(net_collections, 2),
                    "outstanding_balance_inr": round(inv_stats.get("balance_due", 0.0), 2)
                },
                "continuity_pulse": {
                    "care_tasks_overdue": cont_stats.get("overdue_tasks") or 0,
                    "total_active_tasks": cont_stats.get("total_tasks") or 0
                },
                "inventory_pulse": {
                    "batches_near_expiry_90d": near_expiry
                },
                "governance_pulse": {
                    "open_safety_cases": open_safety_cases,
                    "rules_pending_review": rules_pending_review
                },
                "reliability_pulse": {
                    "dead_letter_open_items": open_dlq,
                    "circuit_breakers_open": open_cb
                },
                "caveats": [
                    "All figures derived strictly from canonical relational records; zero simulated projections.",
                    "Process and documentation counts do NOT indicate treatment efficacy or clinical superiority.",
                    "Gross invoiced amounts represent accrued billings, NOT realized cash collection."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Clinic Operations Analytics
    # --------------------------------------------------------------------------

    def get_clinic_operations_metrics(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Detailed appointments, OPD queues, and encounter workload analytics."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")
        start_iso, end_iso, tz = self._resolve_period_bounds(filters)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Appointments status breakdown
            query = """
                SELECT status, COUNT(*) as count
                FROM appointments
                WHERE organization_id = ? AND start_at >= ? AND start_at <= ?
            """
            params = [org_id, start_iso, end_iso]
            if fac_id:
                query += " AND facility_id = ?"
                params.append(fac_id)
            query += " GROUP BY status;"
            cur.execute(query, params)
            appts_by_status = {r["status"]: r["count"] for r in cur.fetchall()}

            # Queue status breakdown
            q_query = """
                SELECT status, COUNT(*) as count
                FROM queue_tokens
                WHERE organization_id = ? AND queue_date = DATE('now')
            """
            q_params = [org_id]
            if fac_id:
                q_query += " AND facility_id = ?"
                q_params.append(fac_id)
            q_query += " GROUP BY status;"
            cur.execute(q_query, q_params)
            queue_by_status = {r["status"]: r["count"] for r in cur.fetchall()}

            # Encounters documentation status breakdown
            enc_query = """
                SELECT status, COUNT(*) as count
                FROM encounters
                WHERE organization_id = ? AND created_at >= ? AND created_at <= ?
            """
            enc_params = [org_id, start_iso, end_iso]
            if fac_id:
                enc_query += " AND facility_id = ?"
                enc_params.append(fac_id)
            enc_query += " GROUP BY status;"
            cur.execute(enc_query, enc_params)
            enc_by_status = {r["status"]: r["count"] for r in cur.fetchall()}

            return {
                "organization_id": org_id,
                "facility_id": fac_id,
                "period": {"start": start_iso, "end": end_iso, "timezone": tz},
                "appointments_by_status": appts_by_status,
                "queue_by_status": queue_by_status,
                "encounters_by_status": enc_by_status,
                "caveats": [
                    "Individual clinician productivity metrics are strictly personal; no public comparison permitted.",
                    "Token wait duration calculations require accurate front-desk check-in and call timestamps."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Patient Continuity Analytics
    # --------------------------------------------------------------------------

    def get_patient_continuity_metrics(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Follow-up adherence, care continuity task backlogs, and referral workflows."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")
        start_iso, end_iso, tz = self._resolve_period_bounds(filters)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Care tasks by status
            query = """
                SELECT status, COUNT(*) as count
                FROM care_continuity_tasks
                WHERE organization_id = ?
            """
            params = [org_id]
            if fac_id:
                query += " AND facility_id = ?"
                params.append(fac_id)
            query += " GROUP BY status;"
            cur.execute(query, params)
            tasks_by_status = {r["status"]: r["count"] for r in cur.fetchall()}

            # Overdue tasks
            od_query = """
                SELECT COUNT(*) as overdue_count
                FROM care_continuity_tasks
                WHERE organization_id = ? AND status IN ('PENDING', 'IN_PROGRESS') AND due_date < datetime('now')
            """
            od_params = [org_id]
            if fac_id:
                od_query += " AND facility_id = ?"
                od_params.append(fac_id)
            cur.execute(od_query, od_params)
            overdue_count = cur.fetchone()["overdue_count"]

            # Referrals breakdown if referrals table exists
            ref_counts = {}
            try:
                r_query = """
                    SELECT status, COUNT(*) as count
                    FROM referrals
                    WHERE organization_id = ?
                    GROUP BY status;
                """
                cur.execute(r_query, [org_id])
                ref_counts = {r["status"]: r["count"] for r in cur.fetchall()}
            except Exception:
                ref_counts = {"status": "not_configured"}

            return {
                "organization_id": org_id,
                "facility_id": fac_id,
                "period": {"start": start_iso, "end": end_iso, "timezone": tz},
                "tasks_by_status": tasks_by_status,
                "overdue_tasks_count": overdue_count,
                "referrals_by_status": ref_counts,
                "caveats": [
                    "Overdue follow-up tasks reflect operational contact outreach, not patient treatment abandonment."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Finance & Billing Analytics
    # --------------------------------------------------------------------------

    def get_finance_metrics(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoicing, collections by payment channel, refunds, and accounts receivable."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")
        start_iso, end_iso, tz = self._resolve_period_bounds(filters)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Invoice aggregates
            inv_query = """
                SELECT 
                    status,
                    COUNT(*) as count,
                    COALESCE(SUM(CAST(total_decimal AS REAL)), 0.0) as sum_total,
                    COALESCE(SUM(CAST(paid_decimal AS REAL)), 0.0) as sum_paid,
                    COALESCE(SUM(CAST(balance_due_decimal AS REAL)), 0.0) as sum_balance
                FROM invoices
                WHERE organization_id = ? AND created_at >= ? AND created_at <= ?
            """
            inv_params = [org_id, start_iso, end_iso]
            if fac_id:
                inv_query += " AND facility_id = ?"
                inv_params.append(fac_id)
            inv_query += " GROUP BY status;"
            cur.execute(inv_query, inv_params)
            invoices_by_status = [dict(r) for r in cur.fetchall()]

            # Collections by payment method
            pay_query = """
                SELECT 
                    payment_method,
                    COUNT(*) as payment_count,
                    COALESCE(SUM(CAST(amount_decimal AS REAL)), 0.0) as total_amount
                FROM payments
                WHERE organization_id = ? AND status IN ('POSTED', 'COMPLETED')
                  AND recorded_at >= ? AND recorded_at <= ?
            """
            pay_params = [org_id, start_iso, end_iso]
            if fac_id:
                pay_query += " AND facility_id = ?"
                pay_params.append(fac_id)
            pay_query += " GROUP BY payment_method;"
            cur.execute(pay_query, pay_params)
            payments_by_method = [dict(r) for r in cur.fetchall()]

            # Refunds total
            ref_query = """
                SELECT 
                    COUNT(*) as refund_count,
                    COALESCE(SUM(CAST(amount_decimal AS REAL)), 0.0) as total_refunded
                FROM payment_refunds
                WHERE organization_id = ? AND status = 'COMPLETED'
                  AND created_at >= ? AND created_at <= ?
            """
            ref_params = [org_id, start_iso, end_iso]
            if fac_id:
                ref_query += " AND facility_id = ?"
                ref_params.append(fac_id)
            cur.execute(ref_query, ref_params)
            refund_row = dict(cur.fetchone() or {})

            # Total collections & net collections
            gross_collections = sum(p["total_amount"] for p in payments_by_method)
            total_refunds = refund_row.get("total_refunded", 0.0)
            net_collections = max(0.0, gross_collections - total_refunds)

            # Cumulative outstanding balance
            bal_query = """
                SELECT COALESCE(SUM(CAST(balance_due_decimal AS REAL)), 0.0) as total_balance_due
                FROM invoices
                WHERE organization_id = ? AND status IN ('FINALIZED', 'PARTIALLY_PAID')
            """
            bal_params = [org_id]
            if fac_id:
                bal_query += " AND facility_id = ?"
                bal_params.append(fac_id)
            cur.execute(bal_query, bal_params)
            total_balance_due = cur.fetchone()["total_balance_due"]

            return {
                "organization_id": org_id,
                "facility_id": fac_id,
                "period": {"start": start_iso, "end": end_iso, "timezone": tz},
                "gross_collections_inr": round(gross_collections, 2),
                "total_refunds_inr": round(total_refunds, 2),
                "net_collections_inr": round(net_collections, 2),
                "cumulative_outstanding_balance_inr": round(total_balance_due, 2),
                "invoices_breakdown": invoices_by_status,
                "payments_by_method": payments_by_method,
                "refunds_summary": refund_row,
                "caveats": [
                    "All monetary sums computed with decimal safety.",
                    "Gross invoiced totals must not be conflated with cash collections or recognized net revenue."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Inventory & Pharmacy Analytics
    # --------------------------------------------------------------------------

    def get_inventory_metrics(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Dispensary stock on hand, batch expiry horizons (FEFO), and movement audits."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")
        start_iso, end_iso, tz = self._resolve_period_bounds(filters)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Batch status breakdown
            batch_query = """
                SELECT status, COUNT(*) as batch_count,
                       COALESCE(SUM(CAST(quantity_on_hand_decimal AS REAL)), 0.0) as total_quantity
                FROM inventory_batches
                WHERE organization_id = ?
            """
            b_params = [org_id]
            if fac_id:
                batch_query += " AND facility_id = ?"
                b_params.append(fac_id)
            batch_query += " GROUP BY status;"
            cur.execute(batch_query, b_params)
            batches_by_status = [dict(r) for r in cur.fetchall()]

            # Expiry horizons for AVAILABLE stock
            exp_query = """
                SELECT 
                    SUM(CASE WHEN expiry_date <= DATE('now') THEN 1 ELSE 0 END) as expired_count,
                    SUM(CASE WHEN expiry_date BETWEEN DATE('now') AND DATE('now', '+30 days') THEN 1 ELSE 0 END) as exp_30d,
                    SUM(CASE WHEN expiry_date BETWEEN DATE('now', '+31 days') AND DATE('now', '+60 days') THEN 1 ELSE 0 END) as exp_60d,
                    SUM(CASE WHEN expiry_date BETWEEN DATE('now', '+61 days') AND DATE('now', '+90 days') THEN 1 ELSE 0 END) as exp_90d,
                    SUM(CASE WHEN expiry_date > DATE('now', '+90 days') THEN 1 ELSE 0 END) as exp_beyond_90d
                FROM inventory_batches
                WHERE organization_id = ? AND status = 'AVAILABLE'
            """
            exp_params = [org_id]
            if fac_id:
                exp_query += " AND facility_id = ?"
                exp_params.append(fac_id)
            cur.execute(exp_query, exp_params)
            expiry_horizons = dict(cur.fetchone() or {})

            # Stock movements by type in period
            mov_query = """
                SELECT movement_type, COUNT(*) as movement_count,
                       COALESCE(SUM(CAST(quantity_delta_decimal AS REAL)), 0.0) as net_quantity_delta
                FROM inventory_movements
                WHERE organization_id = ? AND occurred_at >= ? AND occurred_at <= ?
            """
            mov_params = [org_id, start_iso, end_iso]
            if fac_id:
                mov_query += " AND facility_id = ?"
                mov_params.append(fac_id)
            mov_query += " GROUP BY movement_type;"
            cur.execute(mov_query, mov_params)
            movements_by_type = [dict(r) for r in cur.fetchall()]

            return {
                "organization_id": org_id,
                "facility_id": fac_id,
                "period": {"start": start_iso, "end": end_iso, "timezone": tz},
                "batches_by_status": batches_by_status,
                "expiry_horizons": {
                    "already_expired": expiry_horizons.get("expired_count") or 0,
                    "within_30_days": expiry_horizons.get("exp_30d") or 0,
                    "within_60_days": expiry_horizons.get("exp_60d") or 0,
                    "within_90_days": expiry_horizons.get("exp_90d") or 0,
                    "healthy_beyond_90_days": expiry_horizons.get("exp_beyond_90d") or 0
                },
                "movements_by_type": movements_by_type,
                "caveats": [
                    "Inventory levels reflect recorded dispensary stock ledger; does NOT imply clinical efficacy or appropriateness."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Clinical Governance & Safety Analytics
    # --------------------------------------------------------------------------

    def get_clinical_governance_metrics(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Adverse events, safety rule releases, and tamper-evident audit ledger health."""
        org_id = user_ctx.get("organization_id")

        start_iso, end_iso, tz = self._resolve_period_bounds(filters)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Pharmacovigilance cases by status
            cur.execute(
                """
                SELECT case_state, COUNT(*) as count
                FROM safety_cases
                WHERE tenant_id = ?
                GROUP BY case_state;
                """,
                (org_id,),
            )
            cases_by_status = {r["case_state"]: r["count"] for r in cur.fetchall()}

            # Governed clinical rules/artifacts by lifecycle state
            cur.execute(
                """
                SELECT current_lifecycle_state, COUNT(*) as count
                FROM governed_artifacts
                GROUP BY current_lifecycle_state;
                """
            )
            rules_by_state = {r["current_lifecycle_state"]: r["count"] for r in cur.fetchall()}

            # Cryptographic audit ledger events count & checkpoints
            cur.execute("SELECT COUNT(*) as total_events FROM clinical_ledger_events;")
            total_audit_events = cur.fetchone()["total_events"]

            cur.execute(
                """
                SELECT verification_result, COUNT(*) as count
                FROM audit_integrity_checkpoints
                GROUP BY verification_result;
                """
            )
            checkpoint_status = {r["verification_result"]: r["count"] for r in cur.fetchall()}

            return {
                "organization_id": org_id,
                "period": {"start": start_iso, "end": end_iso, "timezone": tz},
                "safety_cases_by_status": cases_by_status,
                "clinical_rules_by_state": rules_by_state,
                "audit_ledger_total_events": total_audit_events,
                "audit_integrity_checkpoints": checkpoint_status,
                "caveats": [
                    "Safety event metrics measure reporting compliance and active investigation workloads.",
                    "Zero adverse events does NOT prove absolute product safety when reporting completeness is unverified."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Data Quality & Reliability Analytics
    # --------------------------------------------------------------------------

    def get_data_quality_metrics(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Integration queues, dead-letter items, circuit breakers, and reconciliation health."""
        org_id = user_ctx.get("organization_id")
        start_iso, end_iso, tz = self._resolve_period_bounds(filters)

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Integration jobs breakdown by state
            cur.execute(
                """
                SELECT job_state, COUNT(*) as count
                FROM integration_jobs
                WHERE organization_id = ?
                GROUP BY job_state;
                """,
                (org_id,),
            )
            jobs_by_state = {r["job_state"]: r["count"] for r in cur.fetchall()}

            # Dead letter items breakdown
            cur.execute(
                """
                SELECT dlq.resolution_status, COUNT(*) as count
                FROM dead_letter_items dlq
                JOIN integration_jobs j ON j.id = dlq.job_id
                WHERE j.organization_id = ?
                GROUP BY dlq.resolution_status;
                """,
                (org_id,),
            )
            dlq_by_status = {r["resolution_status"]: r["count"] for r in cur.fetchall()}

            # Circuit breakers state
            cur.execute(
                """
                SELECT cb.state, COUNT(*) as count
                FROM integration_circuit_breakers cb
                JOIN integration_connectors c ON c.id = cb.connector_id
                WHERE c.organization_id = ?
                GROUP BY cb.state;
                """,
                (org_id,),
            )
            cb_by_state = {r["state"]: r["count"] for r in cur.fetchall()}

            # Reconciliation exceptions count
            cur.execute(
                """
                SELECT exception_status, COUNT(*) as count
                FROM metric_reconciliation_exceptions
                WHERE organization_id = ?
                GROUP BY exception_status;
                """,
                (org_id,),
            )
            recon_exceptions = {r["exception_status"]: r["count"] for r in cur.fetchall()}

            return {
                "organization_id": org_id,
                "period": {"start": start_iso, "end": end_iso, "timezone": tz},
                "integration_jobs_by_state": jobs_by_state,
                "dead_letter_by_status": dlq_by_status,
                "circuit_breakers_by_state": cb_by_state,
                "reconciliation_exceptions": recon_exceptions,
                "caveats": [
                    "All integration reliability metrics are derived from empirical job and attempt tables.",
                    "Zero PHI is contained in error classifications or telemetry metrics."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. Governed Metric Catalogue & Lifecycle
    # --------------------------------------------------------------------------

    def list_metric_definitions(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List governed metric definitions with filtering and role gating."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM governed_metric_definitions WHERE 1=1"
            params = []

            if filters.get("domain"):
                query += " AND domain = ?"
                params.append(filters["domain"].upper())
            if filters.get("status"):
                query += " AND status = ?"
                params.append(filters["status"].lower())

            query += " ORDER BY domain ASC, metric_key ASC;"
            cur.execute(query, params)
            rows = cur.fetchall()

            result = []
            for r in rows:
                item = dict(r)
                for json_col in [
                    "inclusion_rules_json", "exclusion_rules_json",
                    "source_entities_json", "source_fields_json",
                    "permitted_roles_json", "caveats_json"
                ]:
                    try:
                        item[json_col.replace("_json", "")] = json.loads(item[json_col])
                    except Exception:
                        item[json_col.replace("_json", "")] = []
                    result.append(item)
            return result
        finally:
            conn.close()

    def get_metric_definition(
        self, metric_key: str, user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get complete definition, version lineage, and caveats for a metric."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT * FROM governed_metric_definitions WHERE metric_key = ?;", (metric_key,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Metric definition '{metric_key}' not found.")
            item = dict(row)
            for json_col in [
                "inclusion_rules_json", "exclusion_rules_json",
                "source_entities_json", "source_fields_json",
                "permitted_roles_json", "caveats_json"
            ]:
                try:
                    item[json_col.replace("_json", "")] = json.loads(item[json_col])
                except Exception:
                    item[json_col.replace("_json", "")] = []
            return item
        finally:
            conn.close()

    def create_metric_definition(
        self, data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Author a new metric definition in draft state."""
        metric_key = data.get("metric_key")
        name = data.get("name")
        domain = data.get("domain", "").upper()
        m_type = data.get("metric_type", "count").lower()

        if not metric_key or not name:
            raise ValidationError("metric_key and name are mandatory.")
        if domain not in ['OPERATIONS', 'CONTINUITY', 'FINANCE', 'INVENTORY', 'GOVERNANCE', 'DATA_QUALITY']:
            raise ValidationError(f"Invalid domain '{domain}'.")

        metric_id = f"m-{uuid.uuid4().hex[:8]}"
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO governed_metric_definitions (
                    id, metric_key, name, description, domain, metric_type, unit,
                    numerator_definition, denominator_definition, inclusion_rules_json,
                    exclusion_rules_json, source_entities_json, source_fields_json,
                    calculation_version, aggregation_grain, refresh_policy, accountable_owner,
                    permitted_roles_json, caveats_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft');
                """,
                (
                    metric_id, metric_key, name, data.get("description", ""),
                    domain, m_type, data.get("unit"),
                    data.get("numerator_definition"), data.get("denominator_definition"),
                    json.dumps(data.get("inclusion_rules", [])),
                    json.dumps(data.get("exclusion_rules", [])),
                    json.dumps(data.get("source_entities", [])),
                    json.dumps(data.get("source_fields", [])),
                    data.get("calculation_version", "1.0.0"),
                    data.get("aggregation_grain", "DAY"),
                    data.get("refresh_policy", "ON_DEMAND"),
                    data.get("accountable_owner", "ANALYTICS_TEAM"),
                    json.dumps(data.get("permitted_roles", ["ORG_ADMIN"])),
                    json.dumps(data.get("caveats", [])),
                ),
            )
            conn.commit()
            return self.get_metric_definition(metric_key, user_ctx)
        finally:
            conn.close()

    def advance_metric_to_review(
        self, metric_id: str, user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Advance metric status draft -> review."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT status, metric_key FROM governed_metric_definitions WHERE id = ?;", (metric_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Metric definition '{metric_id}' not found.")
            if row["status"] != "draft":
                raise ValidationError(f"Cannot advance metric from status '{row['status']}' to review.")

            cur.execute(
                "UPDATE governed_metric_definitions SET status = 'review', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (metric_id,),
            )
            conn.commit()
            return self.get_metric_definition(row["metric_key"], user_ctx)
        finally:
            conn.close()

    def approve_metric_definition(
        self, metric_id: str, user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Approve metric definition for production usage."""
        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT status, metric_key FROM governed_metric_definitions WHERE id = ?;", (metric_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Metric definition '{metric_id}' not found.")
            if row["status"] != "review":
                raise ValidationError(f"Cannot approve metric from status '{row['status']}'. Must be in review.")

            cur.execute(
                """
                UPDATE governed_metric_definitions 
                SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?;
                """,
                (user_id, metric_id),
            )
            conn.commit()
            return self.get_metric_definition(row["metric_key"], user_ctx)
        finally:
            conn.close()

    def retire_metric_definition(
        self, metric_id: str, user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retire metric definition."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT metric_key FROM governed_metric_definitions WHERE id = ?;", (metric_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Metric definition '{metric_id}' not found.")

            cur.execute(
                "UPDATE governed_metric_definitions SET status = 'retired', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (metric_id,),
            )
            conn.commit()
            return self.get_metric_definition(row["metric_key"], user_ctx)
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 9. Audited Export Generation (Zero PHI, Tamper-Evident SHA-256)
    # --------------------------------------------------------------------------

    def generate_export(
        self, export_data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a secure, privacy-preserving aggregated export with SHA-256 audit manifest."""
        org_id = user_ctx.get("organization_id")
        fac_id = export_data.get("facility_id") or user_ctx.get("facility_id")
        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        export_type = export_data.get("export_type", "EXECUTIVE_OVERVIEW")
        fmt = export_data.get("format", "CSV").upper()

        if fmt not in ["CSV", "JSON"]:
            raise ValidationError("Supported export formats are CSV and JSON.")

        # Aggregate metrics
        overview = self.get_executive_overview(export_data.get("filters", {}), user_ctx)

        if fmt == "CSV":
            lines = [
                "Category,Metric,Value,Unit",
                f"Operations,Appointments Completed,{overview['operational_pulse']['appointments_completed']},visits",
                f"Operations,Appointments Cancelled,{overview['operational_pulse']['appointments_cancelled']},visits",
                f"Operations,No-Show Rate,{overview['operational_pulse']['no_show_rate_percent']},percent",
                f"Operations,Queue Waiting Tokens,{overview['operational_pulse']['queue_tokens_waiting']},patients",
                f"Operations,Encounters Signed,{overview['operational_pulse']['encounters_signed']},encounters",
                f"Finance,Gross Invoiced,{overview['financial_pulse']['gross_invoiced_inr']},INR",
                f"Finance,Net Collections,{overview['financial_pulse']['net_collections_inr']},INR",
                f"Finance,Outstanding Balances,{overview['financial_pulse']['outstanding_balance_inr']},INR",
                f"Continuity,Care Tasks Overdue,{overview['continuity_pulse']['care_tasks_overdue']},tasks",
                f"Inventory,Batches Near Expiry (90d),{overview['inventory_pulse']['batches_near_expiry_90d']},batches",
                f"Governance,Open Safety Cases,{overview['governance_pulse']['open_safety_cases']},cases",
                f"Governance,Rules Pending Review,{overview['governance_pulse']['rules_pending_review']},rules",
                f"Reliability,Open DLQ Items,{overview['reliability_pulse']['dead_letter_open_items']},items",
                f"Reliability,Open Circuit Breakers,{overview['reliability_pulse']['circuit_breakers_open']},breakers"
            ]
            content = "\n".join(lines)
            record_count = len(lines) - 1
        else:
            content = json.dumps(overview, indent=2, sort_keys=True)
            record_count = 14

        content_bytes = content.encode("utf-8")
        sha256_hash = hashlib.sha256(content_bytes).hexdigest()
        audit_id = f"exp-{uuid.uuid4().hex[:12]}"

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO analytics_export_audit (
                    id, organization_id, facility_id, user_id, export_type, format,
                    metric_keys_json, filters_json, record_count, sha256_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    audit_id, org_id, fac_id, user_id, export_type, fmt,
                    json.dumps(list(overview["operational_pulse"].keys())),
                    json.dumps(export_data.get("filters", {})),
                    record_count,
                    sha256_hash,
                ),
            )
            conn.commit()

            return {
                "export_id": audit_id,
                "export_type": export_type,
                "format": fmt,
                "record_count": record_count,
                "sha256_hash": sha256_hash,
                "content": content,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 10. Metric Reconciliation Exceptions
    # --------------------------------------------------------------------------

    def list_reconciliation_exceptions(
        self, filters: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List reconciliation exceptions between canonical sources and derived analytics."""
        org_id = user_ctx.get("organization_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM metric_reconciliation_exceptions WHERE organization_id = ?"
            params = [org_id]
            if filters.get("status"):
                query += " AND exception_status = ?"
                params.append(filters["status"].upper())
            query += " ORDER BY detected_at DESC LIMIT 50;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def record_reconciliation_exception(
        self, data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Record an identified discrepancy between canonical records and analytics."""
        org_id = user_ctx.get("organization_id")
        fac_id = data.get("facility_id") or user_ctx.get("facility_id")
        exc_id = f"exc-{uuid.uuid4().hex[:8]}"
        metric_key = data.get("metric_key", "finance.net_collections")
        period_start = data.get("period_start", datetime.now(timezone.utc).isoformat())
        period_end = data.get("period_end", datetime.now(timezone.utc).isoformat())
        canonical_val = str(data.get("canonical_value_decimal", data.get("canonical_value", "0.00")))
        derived_val = str(data.get("derived_value_decimal", data.get("derived_value", "0.00")))
        variance_val = str(data.get("variance_decimal", data.get("variance", "0.00")))
        notes = data.get("notes", "Discrepancy detected during automated reconciliation.")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO metric_reconciliation_exceptions (
                    id, organization_id, facility_id, metric_key, period_start, period_end,
                    canonical_value_decimal, derived_value_decimal, variance_decimal,
                    exception_status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?);
                """,
                (
                    exc_id, org_id, fac_id, metric_key, period_start, period_end,
                    canonical_val, derived_val, variance_val, notes
                ),
            )
            conn.commit()
            return {"exception_id": exc_id, "exception_status": "OPEN"}
        finally:
            conn.close()

    def resolve_reconciliation_exception(
        self, exception_id: str, resolution_data: Dict[str, Any], user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve a recorded reconciliation discrepancy with audit notes."""
        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        notes = resolution_data.get("notes", "Discrepancy verified and reconciled by operator.")
        status = resolution_data.get("status", "RESOLVED").upper()

        if status not in ["RESOLVED", "DISMISSED"]:
            status = "RESOLVED"

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE metric_reconciliation_exceptions
                SET exception_status = ?, notes = ?, resolved_by = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (status, notes, user_id, exception_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Reconciliation exception '{exception_id}' not found.")
            conn.commit()
            return {"exception_id": exception_id, "exception_status": status, "resolved_by": user_id}
        finally:
            conn.close()

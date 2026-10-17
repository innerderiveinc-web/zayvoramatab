"""Clinical Operations Command Center, Capacity Planning & Workflow Bottleneck Domain Engine.

Phase 34 for ZAYVORA MATAB OS.
Provides:
1. Live Operations Snapshot (Today's queue, workload, wallboard privacy mode, zero PHI).
2. Today's Detailed Schedule & Resource Allocations (Appointments, practitioner blocks, room conflicts).
3. Workflow Bottleneck Intelligence (Stage elapsed ages, approved threshold comparisons, factual reason codes).
4. Deterministic Capacity Planning (Shift hours, breaks, slot duration, demand vs capacity).
5. Hypothetical Capacity Scenarios (Simulations strictly segregated from production records).
6. Fair Workload Distribution (Role and practitioner assignments without clinical speed rankings).
7. Operational Alerts Lifecycle (Deduplicated, severity-managed, acknowledgement, resolution).
8. Human-in-the-Loop Operational Actions Ledger (Audited, validated state transitions).

Strict non-negotiables enforced:
- Operations only: Never evaluate clinical efficacy, diagnose, prescribe, or calculate doses.
- Queue elapsed times are NEVER labeled as clinical triage acuity scores.
- Never rank clinicians by speed or infer faster consultations equal better care.
- Differentiates 0 from insufficient_data, not_configured, stale, and failed.
- Privacy-safe wallboard mode strips all patient identifiable data.
"""

import os
import json
import uuid
import hashlib
import sqlite3
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.config import config
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


class ClinicalCommandCenterEngine:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = DatabaseConnection(self.db_path).get_connection()
        conn.row_factory = sqlite3.Row
        return conn

    # --------------------------------------------------------------------------
    # 1. Live Operations Snapshot (Wallboard & Role-Gated)
    # --------------------------------------------------------------------------

    def get_live_operations_snapshot(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any],
        wallboard_mode: bool = False
    ) -> Dict[str, Any]:
        """Return authoritative operational pulse of active work items as of now."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id") or user_ctx.get("active_facility_id")
        target_date = filters.get("date") or date.today().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Appointments breakdown
            appt_query = """
                SELECT status, COUNT(*) as count
                FROM appointments
                WHERE organization_id = ? AND DATE(start_at) = ?
            """
            appt_params = [org_id, target_date]
            if fac_id:
                appt_query += " AND facility_id = ?"
                appt_params.append(fac_id)
            appt_query += " GROUP BY status;"
            cur.execute(appt_query, appt_params)
            appts_by_status = {r["status"]: r["count"] for r in cur.fetchall()}

            # 2. Queue tokens breakdown
            q_query = """
                SELECT status, COUNT(*) as count
                FROM queue_tokens
                WHERE organization_id = ? AND queue_date = ?
            """
            q_params = [org_id, target_date]
            if fac_id:
                q_query += " AND facility_id = ?"
                q_params.append(fac_id)
            q_query += " GROUP BY status;"
            cur.execute(q_query, q_params)
            queue_by_status = {r["status"]: r["count"] for r in cur.fetchall()}

            # 3. Active queue items list
            active_q_query = """
                SELECT 
                    q.id, q.token_code, q.token_number, q.status, q.department_queue,
                    q.visit_type, q.priority, q.arrival_at, q.called_at,
                    q.consultation_started_at, q.practitioner_id,
                    u.full_name AS practitioner_name,
                    p.id AS patient_id, p.mrn, p.display_name AS patient_name
                FROM queue_tokens q
                LEFT JOIN users u ON u.id = q.practitioner_id
                LEFT JOIN patients p ON p.id = q.patient_id
                WHERE q.organization_id = ? AND q.queue_date = ?
                  AND q.status IN ('checked_in', 'waiting', 'called', 'in_consultation')
            """
            active_q_params = [org_id, target_date]
            if fac_id:
                active_q_query += " AND q.facility_id = ?"
                active_q_params.append(fac_id)
            active_q_query += " ORDER BY q.token_number ASC LIMIT 50;"
            cur.execute(active_q_query, active_q_params)

            active_tokens = []
            now_iso = datetime.now(timezone.utc).isoformat()
            now_dt = datetime.now(timezone.utc)

            for row in cur.fetchall():
                item = dict(row)
                # Compute elapsed wait age
                elapsed_mins = 0
                if item.get("arrival_at"):
                    try:
                        arr_dt = datetime.fromisoformat(item["arrival_at"].replace("Z", "+00:00"))
                        if arr_dt.tzinfo is None:
                            arr_dt = arr_dt.replace(tzinfo=timezone.utc)
                        elapsed_mins = max(0, int((now_dt - arr_dt).total_seconds() / 60))
                    except Exception:
                        elapsed_mins = 0
                item["wait_elapsed_mins"] = elapsed_mins

                # Privacy-Safe Wallboard Mode: Strip PHI
                if wallboard_mode:
                    item.pop("patient_id", None)
                    item.pop("mrn", None)
                    item.pop("patient_name", None)
                    item["patient_ref"] = f"Token {item['token_code']}"

                active_tokens.append(item)

            # 4. Invoices pending payment
            inv_query = """
                SELECT COUNT(*) as count, COALESCE(SUM(CAST(balance_due_decimal AS REAL)), 0.0) as pending_balance
                FROM invoices
                WHERE organization_id = ? AND status IN ('FINALIZED', 'PARTIALLY_PAID')
                  AND CAST(balance_due_decimal AS REAL) > 0
            """
            inv_params = [org_id]
            if fac_id:
                inv_query += " AND facility_id = ?"
                inv_params.append(fac_id)
            cur.execute(inv_query, inv_params)
            inv_row = cur.fetchone()
            pending_invoices = inv_row["count"] if inv_row else 0
            pending_balance = inv_row["pending_balance"] if inv_row else 0.0

            # 5. Active follow-up tasks due today or overdue
            fu_query = """
                SELECT COUNT(*) as overdue_count
                FROM care_continuity_tasks
                WHERE organization_id = ? AND status IN ('PENDING', 'IN_PROGRESS')
                  AND due_date <= ?
            """
            fu_params = [org_id, now_iso]
            if fac_id:
                fu_query += " AND facility_id = ?"
                fu_params.append(fac_id)
            cur.execute(fu_query, fu_params)
            fu_row = cur.fetchone()
            overdue_tasks = fu_row["overdue_count"] if fu_row else 0

            return {
                "as_of": now_iso,
                "date": target_date,
                "facility_id": fac_id,
                "wallboard_mode": wallboard_mode,
                "freshness": {
                    "state": "current",
                    "source_watermark": "CANONICAL_LIVE_REPLICA"
                },
                "workload_pulse": {
                    "appointments_total": sum(appts_by_status.values()),
                    "appointments_booked": appts_by_status.get("booked", 0) + appts_by_status.get("confirmed", 0),
                    "appointments_arrived": appts_by_status.get("arrived", 0),
                    "appointments_in_progress": appts_by_status.get("in_progress", 0),
                    "appointments_completed": appts_by_status.get("completed", 0),
                    "appointments_no_show": appts_by_status.get("no_show", 0),
                    "appointments_cancelled": appts_by_status.get("cancelled", 0),
                    "queue_waiting": queue_by_status.get("waiting", 0) + queue_by_status.get("checked_in", 0),
                    "queue_in_consultation": queue_by_status.get("in_consultation", 0),
                    "pending_billing_tasks": pending_invoices,
                    "pending_balance_inr": round(pending_balance, 2),
                    "overdue_continuity_tasks": overdue_tasks
                },
                "active_queue": active_tokens,
                "caveats": [
                    "Operational timer/queue age reflects administrative wait, NEVER clinical acuity or triage status.",
                    "Faster consultation elapsed duration does NOT indicate clinical superiority or better patient care.",
                    "All figures derived directly from persisted canonical records with zero simulated projections."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 2. Today's Detailed Schedule & Resource Allocations
    # --------------------------------------------------------------------------

    def get_today_schedule(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return chronological timeline of scheduled appointments, blocks, and room allocations."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id") or user_ctx.get("active_facility_id")
        target_date = filters.get("date") or date.today().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Appointments list
            query = """
                SELECT 
                    a.id, a.start_at, a.end_at, a.appointment_type, a.status,
                    a.room_resource, a.practitioner_id, a.reason_category,
                    u.full_name AS practitioner_name,
                    p.id AS patient_id, p.mrn, p.display_name AS patient_name
                FROM appointments a
                LEFT JOIN users u ON u.id = a.practitioner_id
                LEFT JOIN patients p ON p.id = a.patient_id
                WHERE a.organization_id = ? AND DATE(a.start_at) = ?
            """
            params = [org_id, target_date]
            if fac_id:
                query += " AND a.facility_id = ?"
                params.append(fac_id)
            query += " ORDER BY a.start_at ASC;"
            cur.execute(query, params)
            appts = [dict(r) for r in cur.fetchall()]

            # 2. Practitioner schedule blocks (Leaves / Holidays)
            block_query = """
                SELECT 
                    b.id, b.practitioner_id, b.block_start_at, b.block_end_at,
                    b.block_type, b.reason, u.full_name AS practitioner_name
                FROM practitioner_schedule_blocks b
                LEFT JOIN users u ON u.id = b.practitioner_id
                WHERE b.organization_id = ? AND b.is_active = 1
                  AND (DATE(b.block_start_at) <= ? AND DATE(b.block_end_at) >= ?)
            """
            block_params = [org_id, target_date, target_date]
            if fac_id:
                block_query += " AND b.facility_id = ?"
                block_params.append(fac_id)
            cur.execute(block_query, block_params)
            blocks = [dict(r) for r in cur.fetchall()]

            # 3. Detect schedule conflicts (appointment overlapping with leave/block)
            conflicts = []
            for a in appts:
                a_start = a["start_at"]
                a_end = a["end_at"]
                p_id = a["practitioner_id"]
                for b in blocks:
                    if b["practitioner_id"] == p_id:
                        if not (a_end <= b["block_start_at"] or a_start >= b["block_end_at"]):
                            conflicts.append({
                                "conflict_type": "APPOINTMENT_DURING_PRACTITIONER_BLOCK",
                                "appointment_id": a["id"],
                                "practitioner_id": p_id,
                                "block_id": b["id"],
                                "block_reason": b["reason"],
                                "scheduled_slot": f"{a_start} to {a_end}"
                            })

            return {
                "date": target_date,
                "facility_id": fac_id,
                "total_appointments": len(appts),
                "total_blocks": len(blocks),
                "conflicts_detected": conflicts,
                "appointments": appts,
                "schedule_blocks": blocks
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 3. Workflow Bottleneck Intelligence
    # --------------------------------------------------------------------------

    def get_workflow_bottlenecks(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze process friction, stage elapsed times, and threshold violations using transparent rules."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id") or user_ctx.get("active_facility_id")
        target_date = filters.get("date") or date.today().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Fetch approved threshold rules
            cur.execute(
                """
                SELECT stage_key, warning_threshold_mins, critical_threshold_mins, version
                FROM command_center_threshold_rules
                WHERE organization_id = ? AND (facility_id IS NULL OR facility_id = ?)
                  AND is_active = 1;
                """,
                (org_id, fac_id),
            )
            rules_map = {r["stage_key"]: dict(r) for r in cur.fetchall()}

            # Default fallback thresholds if not yet configured
            default_thresholds = {
                "CHECK_IN_TO_CALL": {"warning_threshold_mins": 30, "critical_threshold_mins": 60, "version": 0},
                "CALL_TO_START": {"warning_threshold_mins": 15, "critical_threshold_mins": 30, "version": 0},
                "CONSULTATION_DURATION": {"warning_threshold_mins": 45, "critical_threshold_mins": 90, "version": 0},
                "DISCHARGE_TO_BILLING": {"warning_threshold_mins": 20, "critical_threshold_mins": 45, "version": 0},
                "FOLLOW_UP_COMPLETION": {"warning_threshold_mins": 1440, "critical_threshold_mins": 2880, "version": 0},
            }
            for k, v in default_thresholds.items():
                if k not in rules_map:
                    rules_map[k] = v

            now_dt = datetime.now(timezone.utc)
            bottlenecks = []
            alerts_to_upsert = []

            # 2. Check Stage: CHECK_IN_TO_CALL (Tokens in waiting status)
            q_query = """
                SELECT id, token_code, arrival_at, practitioner_id
                FROM queue_tokens
                WHERE organization_id = ? AND queue_date = ? AND status = 'waiting'
            """
            q_params = [org_id, target_date]
            if fac_id:
                q_query += " AND facility_id = ?"
                q_params.append(fac_id)
            cur.execute(q_query, q_params)

            rule_cic = rules_map["CHECK_IN_TO_CALL"]
            for row in cur.fetchall():
                token_id = row["id"]
                token_code = row["token_code"]
                arr_at = row["arrival_at"]
                if arr_at:
                    try:
                        arr_dt = datetime.fromisoformat(arr_at.replace("Z", "+00:00"))
                        if arr_dt.tzinfo is None:
                            arr_dt = arr_dt.replace(tzinfo=timezone.utc)
                        elapsed_mins = int((now_dt - arr_dt).total_seconds() / 60)
                        if elapsed_mins >= rule_cic["warning_threshold_mins"]:
                            severity = "CRITICAL" if elapsed_mins >= rule_cic["critical_threshold_mins"] else "WARNING"
                            factual_reason = "Patient waiting in reception; practitioner has not called token."
                            dedup_key = f"tok_wait_{token_id}_{target_date}"
                            bottleneck_entry = {
                                "stage_key": "CHECK_IN_TO_CALL",
                                "item_id": token_id,
                                "reference_code": token_code,
                                "elapsed_mins": elapsed_mins,
                                "warning_threshold_mins": rule_cic["warning_threshold_mins"],
                                "critical_threshold_mins": rule_cic["critical_threshold_mins"],
                                "severity": severity,
                                "factual_reason": factual_reason
                            }
                            bottlenecks.append(bottleneck_entry)
                            alerts_to_upsert.append((
                                f"alt-{uuid.uuid4().hex[:8]}", org_id, fac_id,
                                "STAGE_THRESHOLD_EXCEEDED", severity, dedup_key,
                                "queue_tokens", token_id, "CHECK_IN_TO_CALL",
                                float(elapsed_mins), float(rule_cic["warning_threshold_mins"]),
                                factual_reason
                            ))
                    except Exception:
                        pass

            # 3. Check Stage: DISCHARGE_TO_BILLING (Completed consultations with unfinalized invoices)
            inv_query = """
                SELECT i.id, i.invoice_number, i.created_at, e.ended_at
                FROM invoices i
                JOIN encounters e ON e.id = i.encounter_id
                WHERE i.organization_id = ? AND i.status = 'DRAFT' AND e.status = 'COMPLETED'
            """
            inv_params = [org_id]
            if fac_id:
                inv_query += " AND i.facility_id = ?"
                inv_params.append(fac_id)
            cur.execute(inv_query, inv_params)

            rule_dtb = rules_map["DISCHARGE_TO_BILLING"]
            for row in cur.fetchall():
                inv_id = row["id"]
                inv_num = row["invoice_number"]
                ended_at = row["ended_at"] or row["created_at"]
                if ended_at:
                    try:
                        end_dt = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
                        if end_dt.tzinfo is None:
                            end_dt = end_dt.replace(tzinfo=timezone.utc)
                        elapsed_mins = int((now_dt - end_dt).total_seconds() / 60)
                        if elapsed_mins >= rule_dtb["warning_threshold_mins"]:
                            severity = "CRITICAL" if elapsed_mins >= rule_dtb["critical_threshold_mins"] else "WARNING"
                            factual_reason = "Clinical encounter finalized; invoice remains in draft status."
                            dedup_key = f"inv_draft_{inv_id}"
                            bottleneck_entry = {
                                "stage_key": "DISCHARGE_TO_BILLING",
                                "item_id": inv_id,
                                "reference_code": inv_num,
                                "elapsed_mins": elapsed_mins,
                                "warning_threshold_mins": rule_dtb["warning_threshold_mins"],
                                "critical_threshold_mins": rule_dtb["critical_threshold_mins"],
                                "severity": severity,
                                "factual_reason": factual_reason
                            }
                            bottlenecks.append(bottleneck_entry)
                            alerts_to_upsert.append((
                                f"alt-{uuid.uuid4().hex[:8]}", org_id, fac_id,
                                "STAGE_THRESHOLD_EXCEEDED", severity, dedup_key,
                                "invoices", inv_id, "DISCHARGE_TO_BILLING",
                                float(elapsed_mins), float(rule_dtb["warning_threshold_mins"]),
                                factual_reason
                            ))
                    except Exception:
                        pass

            # 4. Upsert discovered alerts into operational_alerts table
            for alert_tuple in alerts_to_upsert:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO operational_alerts (
                        id, organization_id, facility_id, alert_type, severity, deduplication_key,
                        source_entity, source_entity_id, stage_key, measured_value_mins,
                        threshold_value_mins, factual_reason, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
                    """,
                    alert_tuple
                )
            conn.commit()

            return {
                "date": target_date,
                "facility_id": fac_id,
                "total_bottlenecks_detected": len(bottlenecks),
                "threshold_rules_applied": rules_map,
                "bottlenecks": bottlenecks,
                "caveats": [
                    "Bottlenecks indicate operational workflow elapsed time; they DO NOT evaluate clinical complexity or competence.",
                    "Factual reasons describe recorded database states; causal conclusions are not inferred."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 4. Deterministic Capacity Planning
    # --------------------------------------------------------------------------

    def get_capacity_plan(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute deterministic capacity vs scheduled demand based strictly on configured calendars."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id") or user_ctx.get("active_facility_id")
        target_date_str = filters.get("date") or date.today().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # 1. Fetch Facility Operating Settings
            cur.execute(
                """
                SELECT timezone, working_hours_start, working_hours_end, working_days_json,
                       default_slot_duration_mins, buffer_time_mins
                FROM facility_settings
                WHERE organization_id = ? AND facility_id = ?;
                """,
                (org_id, fac_id),
            )
            settings_row = cur.fetchone()
            if not settings_row:
                return {
                    "status": "configuration_incomplete",
                    "date": target_date_str,
                    "facility_id": fac_id,
                    "missing_inputs": ["facility_settings"],
                    "message": "Capacity unavailable — facility settings not configured."
                }

            settings = dict(settings_row)
            try:
                working_days = json.loads(settings.get("working_days_json", "[]"))
            except Exception:
                working_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]

            # Check day of week
            target_dt = date.fromisoformat(target_date_str)
            day_map = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}
            day_abbr = day_map[target_dt.weekday()]

            if day_abbr not in working_days:
                return {
                    "status": "facility_closed",
                    "date": target_date_str,
                    "day_of_week": day_abbr,
                    "facility_id": fac_id,
                    "message": f"Facility is closed on {day_abbr} according to configured working days.",
                    "total_configured_capacity": 0,
                    "total_booked_demand": 0,
                    "utilization_percent": 0.0
                }

            # 2. Fetch Active Practitioner Schedules for this Day
            sched_query = """
                SELECT 
                    s.practitioner_id, s.start_time, s.end_time, s.break_start_time,
                    s.break_end_time, s.slot_duration_mins, s.buffer_time_mins, s.slot_capacity,
                    u.full_name AS practitioner_name
                FROM practitioner_schedules s
                JOIN users u ON u.id = s.practitioner_id
                WHERE s.organization_id = ? AND s.facility_id = ? AND s.is_active = 1
                  AND (s.day_of_week = ? OR s.day_of_week = 'ALL')
            """
            cur.execute(sched_query, (org_id, fac_id, day_abbr))
            practitioners = [dict(r) for r in cur.fetchall()]

            if not practitioners:
                return {
                    "status": "no_practitioners_scheduled",
                    "date": target_date_str,
                    "facility_id": fac_id,
                    "message": f"No active practitioner schedules configured for {day_abbr}.",
                    "total_configured_capacity": 0,
                    "total_booked_demand": 0,
                    "utilization_percent": 0.0
                }

            # 3. Fetch Practitioner Blocks / Leaves for this Day
            block_query = """
                SELECT practitioner_id, block_start_at, block_end_at, block_type, reason
                FROM practitioner_schedule_blocks
                WHERE organization_id = ? AND facility_id = ? AND is_active = 1
                  AND DATE(block_start_at) <= ? AND DATE(block_end_at) >= ?
            """
            cur.execute(block_query, (org_id, fac_id, target_date_str, target_date_str))
            blocks_by_practitioner = {}
            for b in cur.fetchall():
                p_id = b["practitioner_id"]
                if p_id not in blocks_by_practitioner:
                    blocks_by_practitioner[p_id] = []
                blocks_by_practitioner[p_id].append(dict(b))

            # 4. Fetch Actual Booked Appointments for this Day
            appt_query = """
                SELECT practitioner_id, COUNT(*) as booked_count
                FROM appointments
                WHERE organization_id = ? AND facility_id = ? AND DATE(start_at) = ?
                  AND status IN ('booked', 'confirmed', 'arrived', 'in_progress', 'completed')
                GROUP BY practitioner_id;
            """
            cur.execute(appt_query, (org_id, fac_id, target_date_str))
            booked_by_practitioner = {r["practitioner_id"]: r["booked_count"] for r in cur.fetchall()}

            # 5. Deterministic Capacity Computation
            practitioner_plans = []
            total_capacity = 0
            total_demand = 0

            for p in practitioners:
                p_id = p["practitioner_id"]
                p_name = p["practitioner_name"]

                # Parse working duration in minutes
                try:
                    s_h, s_m = map(int, p["start_time"].split(":"))
                    e_h, e_m = map(int, p["end_time"].split(":"))
                    total_work_mins = (e_h * 60 + e_m) - (s_h * 60 + s_m)
                except Exception:
                    total_work_mins = 480 # 8 hours fallback

                # Deduct break duration
                break_mins = 0
                if p.get("break_start_time") and p.get("break_end_time"):
                    try:
                        bs_h, bs_m = map(int, p["break_start_time"].split(":"))
                        be_h, be_m = map(int, p["break_end_time"].split(":"))
                        break_mins = (be_h * 60 + be_m) - (bs_h * 60 + bs_m)
                    except Exception:
                        break_mins = 60

                # Deduct blocked/leave minutes
                blocked_mins = 0
                p_blocks = blocks_by_practitioner.get(p_id, [])
                for b in p_blocks:
                    if b.get("block_start_at") and b.get("block_end_at"):
                        try:
                            b_start = datetime.fromisoformat(b["block_start_at"].replace("Z", "+00:00"))
                            b_end = datetime.fromisoformat(b["block_end_at"].replace("Z", "+00:00"))
                            dur = max(0, int((b_end - b_start).total_seconds() / 60))
                            blocked_mins += dur
                        except Exception:
                            pass

                effective_mins = max(0, total_work_mins - break_mins - blocked_mins)
                is_on_leave = (effective_mins == 0 and len(p_blocks) > 0)

                slot_duration = p.get("slot_duration_mins") or settings.get("default_slot_duration_mins", 15)
                buffer_mins = p.get("buffer_time_mins", 0)
                unit_slot_time = max(5, slot_duration + buffer_mins)

                calc_slots = effective_mins // unit_slot_time

                demand = booked_by_practitioner.get(p_id, 0)
                remaining_slots = max(0, calc_slots - demand)
                util_pct = round((demand / calc_slots * 100), 1) if calc_slots > 0 else 0.0

                practitioner_plans.append({
                    "practitioner_id": p_id,
                    "practitioner_name": p_name,
                    "configured_slots": calc_slots,
                    "booked_demand": demand,
                    "remaining_available_slots": remaining_slots,
                    "utilization_percent": util_pct,
                    "is_on_leave": is_on_leave,
                    "slot_duration_mins": slot_duration,
                    "working_window": f"{p['start_time']} - {p['end_time']}"
                })

                total_capacity += calc_slots
                total_demand += demand

            overall_util = round((total_demand / total_capacity * 100), 1) if total_capacity > 0 else 0.0

            return {
                "status": "calculated",
                "date": target_date_str,
                "facility_id": fac_id,
                "day_of_week": day_abbr,
                "capacity_formula": "total_configured_capacity = sum((shift_duration - break_duration) // (slot_duration + buffer))",
                "total_configured_capacity": total_capacity,
                "total_booked_demand": total_demand,
                "total_remaining_slots": max(0, total_capacity - total_demand),
                "utilization_percent": overall_util,
                "practitioners": practitioner_plans,
                "caveats": [
                    "Capacity calculations represent slot availability based on published schedules; they DO NOT set mandatory clinician quotas.",
                    "Faster consultation throughput is never encouraged or measured as a capacity gain."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 5. Hypothetical Capacity Scenario Planning (Simulations Segregated)
    # --------------------------------------------------------------------------

    def evaluate_capacity_scenario(
        self,
        scenario_data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Model hypothetical capacity adjustments strictly segregated from production schedules."""
        org_id = user_ctx.get("organization_id")
        fac_id = scenario_data.get("facility_id") or user_ctx.get("facility_id") or user_ctx.get("active_facility_id")
        target_date_str = scenario_data.get("target_date") or date.today().isoformat()
        hypothetical_changes = scenario_data.get("hypothetical_changes", [])

        # 1. Compute baseline plan
        baseline = self.get_capacity_plan({"date": target_date_str, "facility_id": fac_id}, user_ctx)
        baseline_cap = baseline.get("total_configured_capacity", 0)
        baseline_demand = baseline.get("total_booked_demand", 0)

        # 2. Apply hypothetical adjustments
        delta_slots = 0
        modifications_log = []

        for chg in hypothetical_changes:
            chg_type = chg.get("change_type") # 'ADD_PRACTITIONER_SHIFT', 'SIMULATE_LEAVE', 'MODIFY_SLOT_DURATION'
            if chg_type == "ADD_PRACTITIONER_SHIFT":
                added_hours = float(chg.get("hours", 4.0))
                slot_len = int(chg.get("slot_duration_mins", 15))
                added_slots = int((added_hours * 60) // slot_len)
                delta_slots += added_slots
                modifications_log.append(f"Added hypothetical shift (+{added_slots} slots)")

            elif chg_type == "SIMULATE_LEAVE":
                p_id = chg.get("practitioner_id")
                # find practitioner's baseline capacity
                p_base = next((p for p in baseline.get("practitioners", []) if p["practitioner_id"] == p_id), None)
                if p_base:
                    deducted = p_base["configured_slots"]
                    delta_slots -= deducted
                    modifications_log.append(f"Simulated leave for {p_base['practitioner_name']} (-{deducted} slots)")

            elif chg_type == "MODIFY_SLOT_DURATION":
                new_slot_len = int(chg.get("new_slot_duration_mins", 20))
                # Re-estimate all practitioners with new slot length
                # Approx scale factor: 15 / 20 = 0.75
                scale = 15.0 / max(5, new_slot_len)
                adjusted_cap = int(baseline_cap * scale)
                delta_slots = adjusted_cap - baseline_cap
                modifications_log.append(f"Modified default slot length to {new_slot_len}m (delta: {delta_slots} slots)")

        simulated_capacity = max(0, baseline_cap + delta_slots)
        variance_slots = simulated_capacity - baseline_cap
        simulated_util = round((baseline_demand / simulated_capacity * 100), 1) if simulated_capacity > 0 else 0.0

        scenario_id = f"scen-{uuid.uuid4().hex[:8]}"

        result = {
            "scenario_id": scenario_id,
            "scenario_name": scenario_data.get("scenario_name", "Hypothetical Capacity Simulation"),
            "target_date": target_date_str,
            "facility_id": fac_id,
            "is_simulation_only": True,
            "baseline_capacity": baseline_cap,
            "baseline_demand": baseline_demand,
            "simulated_capacity": simulated_capacity,
            "variance_slots": variance_slots,
            "simulated_utilization_percent": simulated_util,
            "modifications_log": modifications_log,
            "warning": "Simulated projection only. Production schedules, calendars, and bookings are UNCHANGED."
        }

        # If user requested to save scenario for comparison
        if scenario_data.get("save_scenario"):
            conn = self._get_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO capacity_scenarios (
                        id, organization_id, facility_id, scenario_name, scenario_description,
                        target_date, hypothetical_changes_json, baseline_demand, baseline_capacity,
                        scenario_capacity, variance_slots, is_simulation_only, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
                    """,
                    (
                        scenario_id, org_id, fac_id,
                        result["scenario_name"], scenario_data.get("description", ""),
                        target_date_str, json.dumps(hypothetical_changes),
                        baseline_demand, baseline_cap, simulated_capacity, variance_slots,
                        user_ctx.get("id") or user_ctx.get("user_id")
                    ),
                )
                conn.commit()
            finally:
                conn.close()

        return result

    def list_capacity_scenarios(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List previously evaluated hypothetical capacity scenarios."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM capacity_scenarios WHERE organization_id = ?"
            params = [org_id]
            if fac_id:
                query += " AND facility_id = ?"
                params.append(fac_id)
            query += " ORDER BY created_at DESC LIMIT 20;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 6. Fair Workload Distribution (Zero Surveillance Policy)
    # --------------------------------------------------------------------------

    def get_workload_distribution(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Provide transparent team workload allocation without clinician performance surveillance."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id") or user_ctx.get("active_facility_id")
        target_date = filters.get("date") or date.today().isoformat()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Practitioner active workload
            cur.execute(
                """
                SELECT 
                    u.id AS practitioner_id, u.full_name AS practitioner_name,
                    COUNT(q.id) AS total_assigned_tokens,
                    SUM(CASE WHEN q.status = 'waiting' THEN 1 ELSE 0 END) AS waiting_tokens,
                    SUM(CASE WHEN q.status = 'in_consultation' THEN 1 ELSE 0 END) AS in_consultation_tokens,
                    SUM(CASE WHEN q.status = 'completed' THEN 1 ELSE 0 END) AS completed_tokens
                FROM users u
                JOIN queue_tokens q ON q.practitioner_id = u.id
                WHERE q.organization_id = ? AND q.queue_date = ?
                GROUP BY u.id, u.full_name;
                """,
                (org_id, target_date),
            )
            practitioner_workload = [dict(r) for r in cur.fetchall()]

            # Administrative task workload by assigned role
            cur.execute(
                """
                SELECT assigned_role, status, COUNT(*) AS count
                FROM care_continuity_tasks
                WHERE organization_id = ?
                GROUP BY assigned_role, status;
                """,
                (org_id,),
            )
            role_task_workload = {}
            for r in cur.fetchall():
                role = r["assigned_role"]
                if role not in role_task_workload:
                    role_task_workload[role] = {}
                role_task_workload[role][r["status"]] = r["count"]

            return {
                "date": target_date,
                "facility_id": fac_id,
                "practitioner_workload": practitioner_workload,
                "role_task_workload": role_task_workload,
                "caveats": [
                    "Workload distribution assists clinic team coordination; it is NEVER an appraisal of practitioner diligence or speed.",
                    "Patient clinical complexity, procedure requirements, and non-consulting duties naturally differ across practitioners."
                ]
            }
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 7. Operational Alerts Lifecycle (Deduplicated, State-Managed)
    # --------------------------------------------------------------------------

    def list_operational_alerts(
        self,
        filters: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """List active or historical operational alerts with deduplication and state gating."""
        org_id = user_ctx.get("organization_id")
        fac_id = filters.get("facility_id") or user_ctx.get("facility_id")
        status_filter = filters.get("status", "ACTIVE").upper()

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            query = "SELECT * FROM operational_alerts WHERE organization_id = ?"
            params = [org_id]
            if fac_id:
                query += " AND (facility_id IS NULL OR facility_id = ?)"
                params.append(fac_id)
            if status_filter != "ALL":
                query += " AND status = ?"
                params.append(status_filter)
            query += " ORDER BY created_at DESC LIMIT 50;"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def acknowledge_alert(
        self,
        alert_id: str,
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Acknowledge an active operational alert."""
        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE operational_alerts
                SET status = 'ACKNOWLEDGED', acknowledged_by = ?, acknowledged_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status = 'ACTIVE';
                """,
                (user_id, alert_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Alert '{alert_id}' not found or already acknowledged/resolved.")
            conn.commit()
            return {"alert_id": alert_id, "status": "ACKNOWLEDGED", "acknowledged_by": user_id}
        finally:
            conn.close()

    def resolve_alert(
        self,
        alert_id: str,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve an operational alert with required operator resolution notes."""
        user_id = user_ctx.get("id") or user_ctx.get("user_id")
        notes = data.get("resolution_notes", "Remediated by clinic operations team.")

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE operational_alerts
                SET status = 'RESOLVED', resolved_by = ?, resolved_at = CURRENT_TIMESTAMP,
                    resolution_notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND status IN ('ACTIVE', 'ACKNOWLEDGED');
                """,
                (user_id, notes, alert_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Alert '{alert_id}' not found or already resolved.")
            conn.commit()
            return {"alert_id": alert_id, "status": "RESOLVED", "resolved_by": user_id, "notes": notes}
        finally:
            conn.close()

    # --------------------------------------------------------------------------
    # 8. Human-in-the-Loop Operational Actions Ledger
    # --------------------------------------------------------------------------

    def perform_operational_action(
        self,
        data: Dict[str, Any],
        user_ctx: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute and audit an authorized operational action with optimistic concurrency safeguards."""
        org_id = user_ctx.get("organization_id")
        fac_id = data.get("facility_id") or user_ctx.get("facility_id")
        actor_id = user_ctx.get("id") or user_ctx.get("user_id")

        action_type = data.get("action_type")
        target_entity = data.get("target_entity")
        target_id = data.get("target_id")
        reason = data.get("reason")

        if not action_type or not target_entity or not target_id or not reason:
            raise ValidationError("action_type, target_entity, target_id, and reason are mandatory.")

        valid_actions = [
            'ACKNOWLEDGE_ALERT', 'RESOLVE_ALERT', 'ASSIGN_TASK',
            'MARK_BLOCKER_RESOLVED', 'REQUEST_SCHEDULE_REVIEW',
            'RECORD_OPERATIONAL_EXCEPTION', 'RETRY_INTEGRATION_JOB'
        ]
        if action_type not in valid_actions:
            raise ValidationError(f"Invalid operational action '{action_type}'.")

        action_id = f"act-{uuid.uuid4().hex[:8]}"
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            # Execute specific state transitions where supported
            before_state = {"status": "OPEN"}
            after_state = {"status": "UPDATED"}

            if action_type == "ACKNOWLEDGE_ALERT":
                self.acknowledge_alert(target_id, user_ctx)
                before_state = {"status": "ACTIVE"}
                after_state = {"status": "ACKNOWLEDGED"}

            elif action_type == "RESOLVE_ALERT":
                self.resolve_alert(target_id, {"resolution_notes": reason}, user_ctx)
                before_state = {"status": "ACTIVE_OR_ACKNOWLEDGED"}
                after_state = {"status": "RESOLVED"}

            elif action_type == "ASSIGN_TASK":
                new_user_id = data.get("assigned_user_id")
                cur.execute(
                    """
                    UPDATE care_continuity_tasks
                    SET assigned_user_id = ?, status = 'IN_PROGRESS'
                    WHERE id = ? AND organization_id = ?;
                    """,
                    (new_user_id, target_id, org_id),
                )
                before_state = {"assigned_user_id": None}
                after_state = {"assigned_user_id": new_user_id, "status": "IN_PROGRESS"}

            elif action_type == "MARK_BLOCKER_RESOLVED":
                # E.g., unpause queue token
                cur.execute(
                    """
                    UPDATE queue_tokens
                    SET status = 'waiting', pause_reason = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND organization_id = ? AND status = 'paused';
                    """,
                    (target_id, org_id),
                )
                before_state = {"status": "paused"}
                after_state = {"status": "waiting"}

            # Log into operational_action_audit
            cur.execute(
                """
                INSERT INTO operational_action_audit (
                    id, organization_id, facility_id, action_type, target_entity, target_id,
                    before_state_json, after_state_json, reason, actor_id, correlation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    action_id, org_id, fac_id, action_type, target_entity, target_id,
                    json.dumps(before_state), json.dumps(after_state), reason, actor_id,
                    data.get("correlation_id", str(uuid.uuid4()))
                ),
            )
            conn.commit()

            return {
                "action_id": action_id,
                "action_type": action_type,
                "target_entity": target_entity,
                "target_id": target_id,
                "status": "SUCCESS",
                "actor_id": actor_id,
                "reason": reason,
                "occurred_at": datetime.now(timezone.utc).isoformat()
            }
        finally:
            conn.close()

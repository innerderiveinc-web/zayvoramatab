"""Phase 10 Domain Engine: Clinic Operations OS
Appointments, Token Queue, Practitioner Schedules, Facility Settings, Exact-Decimal Billing,
FEFO Pharmacy Inventory Ledger, Signed-Prescription Dispensing & Operational Reporting.
"""

import json
import uuid
import sqlite3
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
    ForbiddenError,
)
from apps.api.core.audit import log_audit_event


# ---------------------------------------------------------------------------
# Exact Monetary & Quantity Decimal Helpers (Zero Floating-Point Arithmetic)
# ---------------------------------------------------------------------------

TWO_PLACES = Decimal("0.01")
TEN_THOUSAND = Decimal("10000")

FORBIDDEN_PAYMENT_FIELDS = {
    "cvv",
    "cvc",
    "cvv2",
    "card_security_code",
    "security_code",
    "pin_block",
    "raw_card_number",
    "full_pan",
    "track_data",
}

APPOINTMENT_TRANSITIONS = {
    "requested": {"booked", "confirmed", "cancelled", "rescheduled"},
    "booked": {"confirmed", "arrived", "cancelled", "rescheduled", "no_show"},
    "confirmed": {"arrived", "cancelled", "rescheduled", "no_show"},
    "arrived": {"in_progress", "completed", "cancelled", "no_show"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
    "rescheduled": set(),
    "no_show": set(),
}

ACTIVE_APPOINTMENT_STATUSES = {"requested", "booked", "confirmed", "arrived", "in_progress"}

QUEUE_TOKEN_TRANSITIONS = {
    "checked_in": {"waiting", "called", "in_consultation", "paused", "cancelled", "no_show"},
    "waiting": {"called", "in_consultation", "paused", "cancelled", "no_show"},
    "called": {"in_consultation", "waiting", "paused", "cancelled", "no_show"},
    "in_consultation": {"paused", "completed", "cancelled"},
    "paused": {"waiting", "called", "in_consultation", "cancelled", "no_show"},
    "completed": set(),
    "cancelled": set(),
    "no_show": set(),
}

ACTIVE_QUEUE_STATUSES = {"checked_in", "waiting", "called", "in_consultation", "paused"}

PRIORITY_WEIGHTS = {
    "CLINICAL_URGENT": 1,
    "ELDERLY_ASSISTED": 2,
    "NORMAL": 3,
}


def to_money(val: Any, field_name: str = "amount") -> Decimal:
    """Parse a value into an exact 2-decimal-place Decimal without float imprecision."""
    if isinstance(val, float):
        raise ValidationError(
            f"Floating-point values are prohibited for monetary/quantity field '{field_name}'. Pass string or integer.",
            details={"field": field_name, "value": val},
        )
    if val is None or val == "":
        return Decimal("0.00")
    try:
        d = Decimal(str(val).strip())
    except (InvalidOperation, ValueError):
        raise ValidationError(f"Invalid decimal value for '{field_name}': {val}")
    return d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def fmt_money(d: Decimal) -> str:
    """Format Decimal to canonical '0.00' string."""
    return str(d.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def _has_clinical_read_access(user_ctx: Dict[str, Any]) -> bool:
    roles = set(user_ctx.get("roles", []))
    perms = set(user_ctx.get("permissions", []))
    if "PRACTITIONER" in roles or "CLINIC_ADMIN" in roles or "ORG_ADMIN" in roles:
        return True
    if "assessment:read" in perms or "modern_assessment:read" in perms:
        return True
    return False


class ClinicOperationsService:
    """Standalone domain engine for Prompt 10 Clinic Operations OS."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self, conn: Optional[sqlite3.Connection] = None) -> Tuple[sqlite3.Connection, bool]:
        if conn is not None:
            return conn, False
        c = DatabaseConnection(self.db_path).get_connection()
        return c, True

    # =========================================================================
    # 1. FACILITY SETTINGS & PRACTITIONER SCHEDULES
    # =========================================================================

    def get_facility_settings(
        self,
        organization_id: str,
        facility_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                "SELECT * FROM facility_settings WHERE facility_id = ? AND organization_id = ?;",
                (facility_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                # Initialize default facility settings
                c.execute(
                    """
                    INSERT OR IGNORE INTO facility_settings (
                        facility_id, organization_id, timezone, currency, tax_enabled,
                        default_tax_rate_bp, billing_enabled, billing_optional_for_consultation,
                        inventory_enabled, public_queue_display_enabled, allow_negative_stock_override,
                        near_expiry_warning_days, default_slot_duration_mins, buffer_time_mins
                    ) VALUES (?, ?, 'Asia/Kolkata', 'INR', 0, 0, 1, 1, 1, 1, 0, 90, 15, 0);
                    """,
                    (facility_id, organization_id),
                )
                if should_close:
                    c.commit()
                cur.execute(
                    "SELECT * FROM facility_settings WHERE facility_id = ? AND organization_id = ?;",
                    (facility_id, organization_id),
                )
                row = cur.fetchone()
            res = dict(row)
            res["working_days"] = json.loads(res.get("working_days_json") or '["MON","TUE","WED","THU","FRI","SAT"]')
            return res
        finally:
            if should_close:
                c.close()

    def update_facility_settings(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            current = self.get_facility_settings(organization_id, facility_id, conn=c)
            tz = payload.get("timezone", current["timezone"])
            currency = str(payload.get("currency", current["currency"])).upper()
            if len(currency) != 3:
                raise ValidationError("Currency must be a 3-letter ISO code (e.g. INR).")

            tax_enabled = 1 if payload.get("tax_enabled", bool(current["tax_enabled"])) else 0
            default_tax_rate_bp = int(payload.get("default_tax_rate_bp", current["default_tax_rate_bp"]))
            if default_tax_rate_bp < 0 or default_tax_rate_bp > 5000:
                raise ValidationError("default_tax_rate_bp must be between 0 and 5000 basis points.")

            billing_enabled = 1 if payload.get("billing_enabled", bool(current["billing_enabled"])) else 0
            inventory_enabled = 1 if payload.get("inventory_enabled", bool(current["inventory_enabled"])) else 0
            public_queue_display_enabled = (
                1 if payload.get("public_queue_display_enabled", bool(current["public_queue_display_enabled"])) else 0
            )
            allow_negative_stock_override = (
                1 if payload.get("allow_negative_stock_override", bool(current["allow_negative_stock_override"])) else 0
            )
            near_expiry_warning_days = int(payload.get("near_expiry_warning_days", current["near_expiry_warning_days"]))
            default_slot_duration_mins = int(
                payload.get("default_slot_duration_mins", current["default_slot_duration_mins"])
            )
            buffer_time_mins = int(payload.get("buffer_time_mins", current["buffer_time_mins"]))
            if default_slot_duration_mins < 5 or default_slot_duration_mins > 240:
                raise ValidationError("default_slot_duration_mins must be between 5 and 240 minutes.")

            working_days = payload.get("working_days", current["working_days"])
            working_hours_start = payload.get("working_hours_start", current["working_hours_start"])
            working_hours_end = payload.get("working_hours_end", current["working_hours_end"])
            receipt_header_title = payload.get("receipt_header_title", current["receipt_header_title"])
            receipt_footer_note = payload.get("receipt_footer_note", current["receipt_footer_note"])

            c.execute(
                """
                UPDATE facility_settings
                SET timezone = ?, currency = ?, tax_enabled = ?, default_tax_rate_bp = ?,
                    billing_enabled = ?, inventory_enabled = ?, public_queue_display_enabled = ?,
                    allow_negative_stock_override = ?, near_expiry_warning_days = ?,
                    default_slot_duration_mins = ?, buffer_time_mins = ?,
                    working_days_json = ?, working_hours_start = ?, working_hours_end = ?,
                    receipt_header_title = ?, receipt_footer_note = ?,
                    updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE facility_id = ? AND organization_id = ?;
                """,
                (
                    tz,
                    currency,
                    tax_enabled,
                    default_tax_rate_bp,
                    billing_enabled,
                    inventory_enabled,
                    public_queue_display_enabled,
                    allow_negative_stock_override,
                    near_expiry_warning_days,
                    default_slot_duration_mins,
                    buffer_time_mins,
                    json.dumps(working_days),
                    working_hours_start,
                    working_hours_end,
                    receipt_header_title,
                    receipt_footer_note,
                    actor_id,
                    facility_id,
                    organization_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="FACILITY_SETTINGS_UPDATED",
                target_entity_type="FACILITY_SETTINGS",
                target_entity_id=facility_id,
                details={"billing_enabled": billing_enabled, "inventory_enabled": inventory_enabled},
            )
            if should_close:
                c.commit()
            return self.get_facility_settings(organization_id, facility_id, conn=c)
        finally:
            if should_close:
                c.close()

    def upsert_practitioner_schedule(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Configure practitioner working hours while detecting conflicts with already-booked appointments."""
        c, should_close = self._get_conn(conn)
        try:
            practitioner_id = payload.get("practitioner_id")
            if not practitioner_id:
                raise ValidationError("practitioner_id is required.")
            day_of_week = str(payload.get("day_of_week", "ALL")).upper()
            start_time = payload.get("start_time", "09:00")
            end_time = payload.get("end_time", "17:00")
            break_start_time = payload.get("break_start_time", "13:00")
            break_end_time = payload.get("break_end_time", "14:00")
            slot_duration_mins = int(payload.get("slot_duration_mins", 15))
            buffer_time_mins = int(payload.get("buffer_time_mins", 0))
            slot_capacity = int(payload.get("slot_capacity", 1))
            room_resource = payload.get("room_resource", "Room-1")
            acknowledge_conflicts = bool(payload.get("acknowledge_conflicts", False))

            if start_time >= end_time:
                raise ValidationError("Schedule start_time must be earlier than end_time.")

            # Check existing booked appointments for this practitioner that would fall outside new working hours
            cur = c.cursor()
            cur.execute(
                """
                SELECT id, patient_id, start_at, end_at, status
                FROM appointments
                WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ?
                  AND status IN ('requested', 'booked', 'confirmed', 'arrived')
                ORDER BY start_at ASC;
                """,
                (organization_id, facility_id, practitioner_id),
            )
            conflicts = []
            for appt in cur.fetchall():
                appt_start_hhmm = appt["start_at"][11:16] if len(appt["start_at"]) >= 16 else "09:00"
                appt_end_hhmm = appt["end_at"][11:16] if len(appt["end_at"]) >= 16 else "09:15"
                outside_hours = appt_start_hhmm < start_time or appt_end_hhmm > end_time
                in_break = (
                    break_start_time
                    and break_end_time
                    and appt_start_hhmm < break_end_time
                    and appt_end_hhmm > break_start_time
                )
                if outside_hours or in_break:
                    conflicts.append(dict(appt))

            if conflicts and not acknowledge_conflicts:
                raise ConflictError(
                    "Schedule update conflicts with already-booked appointments. Resolve or pass acknowledge_conflicts=true (existing bookings will not be silently invalidated).",
                    details={
                        "code": "SCHEDULE_CONFLICT_WITH_BOOKED_APPOINTMENTS",
                        "conflict_count": len(conflicts),
                        "conflicting_appointments": conflicts,
                    },
                )

            sched_id = payload.get("id") or f"psched-{uuid.uuid4().hex[:10]}"
            c.execute(
                """
                INSERT INTO practitioner_schedules (
                    id, organization_id, facility_id, practitioner_id, day_of_week,
                    start_time, end_time, break_start_time, break_end_time,
                    slot_duration_mins, buffer_time_mins, slot_capacity, room_resource,
                    is_active, created_by, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(facility_id, practitioner_id, day_of_week) DO UPDATE SET
                    start_time = excluded.start_time,
                    end_time = excluded.end_time,
                    break_start_time = excluded.break_start_time,
                    break_end_time = excluded.break_end_time,
                    slot_duration_mins = excluded.slot_duration_mins,
                    buffer_time_mins = excluded.buffer_time_mins,
                    slot_capacity = excluded.slot_capacity,
                    room_resource = excluded.room_resource,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    sched_id,
                    organization_id,
                    facility_id,
                    practitioner_id,
                    day_of_week,
                    start_time,
                    end_time,
                    break_start_time,
                    break_end_time,
                    slot_duration_mins,
                    buffer_time_mins,
                    slot_capacity,
                    room_resource,
                    actor_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="PRACTITIONER_SCHEDULE_UPDATED",
                target_entity_type="PRACTITIONER_SCHEDULE",
                target_entity_id=practitioner_id,
                details={"day_of_week": day_of_week, "conflicts_detected": len(conflicts)},
            )
            if should_close:
                c.commit()
            cur.execute(
                "SELECT * FROM practitioner_schedules WHERE facility_id = ? AND practitioner_id = ? AND day_of_week = ?;",
                (facility_id, practitioner_id, day_of_week),
            )
            res = dict(cur.fetchone())
            res["conflicting_appointments"] = conflicts
            res["conflict_count"] = len(conflicts)
            return res
        finally:
            if should_close:
                c.close()

    def create_schedule_block(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Create a leave/holiday block and surface any conflicting already-booked appointments."""
        c, should_close = self._get_conn(conn)
        try:
            practitioner_id = payload.get("practitioner_id")
            block_start_at = payload.get("block_start_at")
            block_end_at = payload.get("block_end_at")
            block_type = payload.get("block_type", "LEAVE")
            reason = payload.get("reason", "Practitioner leave")
            acknowledge_conflicts = bool(payload.get("acknowledge_conflicts", False))

            if not practitioner_id or not block_start_at or not block_end_at:
                raise ValidationError("practitioner_id, block_start_at, and block_end_at are required.")
            if block_start_at >= block_end_at:
                raise ValidationError("block_start_at must be earlier than block_end_at.")

            cur = c.cursor()
            cur.execute(
                """
                SELECT id, patient_id, start_at, end_at, status
                FROM appointments
                WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ?
                  AND status IN ('requested', 'booked', 'confirmed', 'arrived')
                  AND start_at < ? AND end_at > ?;
                """,
                (organization_id, facility_id, practitioner_id, block_end_at, block_start_at),
            )
            conflicts = [dict(r) for r in cur.fetchall()]
            if conflicts and not acknowledge_conflicts:
                raise ConflictError(
                    "Leave/schedule block overlaps with already-booked appointments. Reschedule them or pass acknowledge_conflicts=true.",
                    details={
                        "code": "LEAVE_BLOCK_CONFLICTS_WITH_APPOINTMENTS",
                        "conflict_count": len(conflicts),
                        "conflicting_appointments": conflicts,
                    },
                )

            block_id = f"pblk-{uuid.uuid4().hex[:10]}"
            c.execute(
                """
                INSERT INTO practitioner_schedule_blocks (
                    id, organization_id, facility_id, practitioner_id,
                    block_start_at, block_end_at, block_type, reason,
                    conflict_count, is_active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?);
                """,
                (
                    block_id,
                    organization_id,
                    facility_id,
                    practitioner_id,
                    block_start_at,
                    block_end_at,
                    block_type,
                    reason,
                    len(conflicts),
                    actor_id,
                ),
            )
            if should_close:
                c.commit()
            return {
                "id": block_id,
                "practitioner_id": practitioner_id,
                "block_start_at": block_start_at,
                "block_end_at": block_end_at,
                "block_type": block_type,
                "reason": reason,
                "conflict_count": len(conflicts),
                "conflicting_appointments": conflicts,
            }
        finally:
            if should_close:
                c.close()

    def get_scheduling_availability(
        self,
        organization_id: str,
        facility_id: str,
        practitioner_id: str,
        target_date: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Compute backend-authoritative slot availability for a practitioner on target_date (YYYY-MM-DD)."""
        c, should_close = self._get_conn(conn)
        try:
            settings = self.get_facility_settings(organization_id, facility_id, conn=c)
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM practitioner_schedules
                WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ? AND is_active = 1
                ORDER BY CASE WHEN day_of_week != 'ALL' THEN 0 ELSE 1 END LIMIT 1;
                """,
                (organization_id, facility_id, practitioner_id),
            )
            sched = cur.fetchone()
            start_hhmm = sched["start_time"] if sched else settings["working_hours_start"]
            end_hhmm = sched["end_time"] if sched else settings["working_hours_end"]
            break_start = sched["break_start_time"] if sched else "13:00"
            break_end = sched["break_end_time"] if sched else "14:00"
            slot_mins = int(sched["slot_duration_mins"]) if sched else int(settings["default_slot_duration_mins"])
            buffer_mins = int(sched["buffer_time_mins"]) if sched else int(settings["buffer_time_mins"])
            room_resource = sched["room_resource"] if sched else "Room-1"

            day_start_iso = f"{target_date}T00:00:00"
            day_end_iso = f"{target_date}T23:59:59"

            # Existing active appointments on target_date
            cur.execute(
                """
                SELECT id, start_at, end_at, status
                FROM appointments
                WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ?
                  AND status IN ('requested', 'booked', 'confirmed', 'arrived', 'in_progress')
                  AND start_at >= ? AND start_at <= ?;
                """,
                (organization_id, facility_id, practitioner_id, day_start_iso, day_end_iso),
            )
            booked_appts = [dict(r) for r in cur.fetchall()]

            # Existing leave blocks overlapping target_date
            cur.execute(
                """
                SELECT id, block_start_at, block_end_at, block_type, reason
                FROM practitioner_schedule_blocks
                WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ?
                  AND is_active = 1 AND block_start_at <= ? AND block_end_at >= ?;
                """,
                (organization_id, facility_id, practitioner_id, day_end_iso, day_start_iso),
            )
            leave_blocks = [dict(r) for r in cur.fetchall()]

            # Generate slots
            slots = []
            curr_dt = datetime.strptime(f"{target_date}T{start_hhmm}:00", "%Y-%m-%dT%H:%M:%S")
            end_dt = datetime.strptime(f"{target_date}T{end_hhmm}:00", "%Y-%m-%dT%H:%M:%S")
            step = timedelta(minutes=slot_mins + buffer_mins)
            dur = timedelta(minutes=slot_mins)

            while curr_dt + dur <= end_dt:
                s_iso = curr_dt.strftime("%Y-%m-%dT%H:%M:%S")
                e_iso = (curr_dt + dur).strftime("%Y-%m-%dT%H:%M:%S")
                s_hhmm = curr_dt.strftime("%H:%M")
                e_hhmm = (curr_dt + dur).strftime("%H:%M")

                in_break = bool(break_start and break_end and s_hhmm < break_end and e_hhmm > break_start)
                in_leave = any(b["block_start_at"] < e_iso and b["block_end_at"] > s_iso for b in leave_blocks)
                booked = any(a["start_at"] < e_iso and a["end_at"] > s_iso for a in booked_appts)

                if not in_break:
                    slot_status = "AVAILABLE"
                    if booked:
                        slot_status = "BOOKED"
                    elif in_leave:
                        slot_status = "BLOCKED_LEAVE"
                    slots.append(
                        {
                            "start_at": s_iso,
                            "end_at": e_iso,
                            "status": slot_status,
                            "is_available": slot_status == "AVAILABLE",
                            "room_resource": room_resource,
                        }
                    )
                curr_dt += step

            return {
                "facility_id": facility_id,
                "practitioner_id": practitioner_id,
                "date": target_date,
                "timezone": settings["timezone"],
                "slot_duration_mins": slot_mins,
                "buffer_time_mins": buffer_mins,
                "available_count": sum(1 for s in slots if s["is_available"]),
                "booked_count": sum(1 for s in slots if s["status"] == "BOOKED"),
                "slots": slots,
            }
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 2. APPOINTMENT SCHEDULING & ENCOUNTER LINKING
    # =========================================================================

    def create_appointment(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            idempotency_key = payload.get("idempotency_key")
            cur = c.cursor()
            if idempotency_key:
                cur.execute(
                    "SELECT id FROM appointments WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                existing = cur.fetchone()
                if existing:
                    return self.get_appointment(organization_id, facility_id, existing["id"], conn=c)

            patient_id = payload.get("patient_id")
            practitioner_id = payload.get("practitioner_id")
            start_at = payload.get("start_at")
            end_at = payload.get("end_at")
            if not patient_id or not practitioner_id or not start_at:
                raise ValidationError("patient_id, practitioner_id, and start_at are required.")

            settings = self.get_facility_settings(organization_id, facility_id, conn=c)
            if not end_at:
                try:
                    dt_s = datetime.fromisoformat(start_at.replace("Z", ""))
                    dt_e = dt_s + timedelta(minutes=int(settings["default_slot_duration_mins"]))
                    end_at = dt_e.strftime("%Y-%m-%dT%H:%M:%S")
                except Exception:
                    raise ValidationError("Invalid ISO timestamp for start_at.")

            if start_at >= end_at:
                raise ValidationError("Appointment start_at must be earlier than end_at.")

            # Verify patient belongs to organization
            cur.execute(
                "SELECT id, display_name FROM patients WHERE id = ? AND organization_id = ?;",
                (patient_id, organization_id),
            )
            if not cur.fetchone():
                raise NotFoundError(f"Patient '{patient_id}' not found in organization.")

            # Check leave blocks
            cur.execute(
                """
                SELECT id, reason FROM practitioner_schedule_blocks
                WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ?
                  AND is_active = 1 AND block_start_at < ? AND block_end_at > ?;
                """,
                (organization_id, facility_id, practitioner_id, end_at, start_at),
            )
            blk = cur.fetchone()
            if blk:
                raise ConflictError(
                    f"Practitioner is unavailable during requested slot ({blk['reason']}).",
                    details={"block_id": blk["id"]},
                )

            # Check overlapping active appointments
            cur.execute(
                """
                SELECT id, start_at, end_at, status FROM appointments
                WHERE organization_id = ? AND facility_id = ? AND practitioner_id = ?
                  AND status IN ('requested', 'booked', 'confirmed', 'arrived', 'in_progress')
                  AND start_at < ? AND end_at > ?;
                """,
                (organization_id, facility_id, practitioner_id, end_at, start_at),
            )
            overlap = cur.fetchone()
            if overlap:
                raise ConflictError(
                    "Double-booking prevented: practitioner already has an active appointment overlapping this slot.",
                    details={"conflicting_appointment_id": overlap["id"]},
                )

            status = payload.get("status", "booked")
            if status not in ("requested", "booked", "confirmed"):
                raise ValidationError("Initial appointment status must be 'requested', 'booked', or 'confirmed'.")

            appt_id = f"appt-{uuid.uuid4().hex[:12]}"
            slot_lock_key = f"{facility_id}|{practitioner_id}|{start_at}"
            tz = payload.get("timezone", settings["timezone"])
            appt_type = payload.get("appointment_type", "INITIAL_CONSULTATION")
            reason_category = payload.get("reason_category", "GENERAL_CONSULTATION")
            clinical_reason_notes = payload.get("clinical_reason_notes")
            booking_source = payload.get("booking_source", "FRONT_DESK")
            followup_task_id = payload.get("followup_task_id")
            room_resource = payload.get("room_resource", "Room-1")

            try:
                c.execute(
                    """
                    INSERT INTO appointments (
                        id, organization_id, facility_id, patient_id, practitioner_id,
                        room_resource, start_at, end_at, timezone, appointment_type,
                        status, reason_category, clinical_reason_notes, booking_source,
                        followup_task_id, slot_lock_key, idempotency_key,
                        created_by, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        appt_id,
                        organization_id,
                        facility_id,
                        patient_id,
                        practitioner_id,
                        room_resource,
                        start_at,
                        end_at,
                        tz,
                        appt_type,
                        status,
                        reason_category,
                        clinical_reason_notes,
                        booking_source,
                        followup_task_id,
                        slot_lock_key,
                        idempotency_key,
                        actor_id,
                        actor_id,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    "Concurrent slot booking conflict detected for practitioner and start timestamp.",
                    details={"reason": str(exc)},
                )

            c.execute(
                """
                INSERT INTO appointment_events (id, appointment_id, event_type, from_status, to_status, reason, actor_id)
                VALUES (?, ?, 'CREATED', NULL, ?, ?, ?);
                """,
                (f"apev-{uuid.uuid4().hex[:10]}", appt_id, status, reason_category, actor_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="APPOINTMENT_CREATED",
                target_entity_type="APPOINTMENT",
                target_entity_id=appt_id,
                details={"patient_id": patient_id, "practitioner_id": practitioner_id, "start_at": start_at},
            )
            if should_close:
                c.commit()
            return self.get_appointment(organization_id, facility_id, appt_id, conn=c)
        finally:
            if should_close:
                c.close()

    def get_appointment(
        self,
        organization_id: str,
        facility_id: str,
        appointment_id: str,
        user_ctx: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT a.*, p.display_name AS patient_name, p.mrn AS patient_mrn,
                       u.full_name AS practitioner_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                LEFT JOIN users u ON a.practitioner_id = u.id
                WHERE a.id = ? AND a.organization_id = ?;
                """,
                (appointment_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Appointment '{appointment_id}' not found.")
            res = dict(row)
            if user_ctx and not _has_clinical_read_access(user_ctx):
                res["clinical_reason_notes"] = None
                res["clinical_reason_redacted"] = True
            else:
                res["clinical_reason_redacted"] = False

            cur.execute(
                "SELECT * FROM appointment_events WHERE appointment_id = ? ORDER BY occurred_at ASC;",
                (appointment_id,),
            )
            res["events"] = [dict(e) for e in cur.fetchall()]
            return res
        finally:
            if should_close:
                c.close()

    def list_appointments(
        self,
        organization_id: str,
        facility_id: str,
        filters: Optional[Dict[str, Any]] = None,
        user_ctx: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            filters = filters or {}
            clauses = ["a.organization_id = ?", "a.facility_id = ?"]
            params: List[Any] = [organization_id, facility_id]

            if filters.get("patient_id"):
                clauses.append("a.patient_id = ?")
                params.append(filters["patient_id"])
            if filters.get("practitioner_id"):
                clauses.append("a.practitioner_id = ?")
                params.append(filters["practitioner_id"])
            if filters.get("status"):
                clauses.append("a.status = ?")
                params.append(filters["status"])
            if filters.get("date"):
                d = filters["date"]
                clauses.append("a.start_at >= ? AND a.start_at <= ?")
                params.extend([f"{d}T00:00:00", f"{d}T23:59:59"])

            sql = f"""
                SELECT a.*, p.display_name AS patient_name, p.mrn AS patient_mrn,
                       u.full_name AS practitioner_name
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                LEFT JOIN users u ON a.practitioner_id = u.id
                WHERE {' AND '.join(clauses)}
                ORDER BY a.start_at ASC;
            """
            cur = c.cursor()
            cur.execute(sql, tuple(params))
            items = []
            can_read_clinical = _has_clinical_read_access(user_ctx) if user_ctx else True
            for r in cur.fetchall():
                item = dict(r)
                if not can_read_clinical:
                    item["clinical_reason_notes"] = None
                    item["clinical_reason_redacted"] = True
                else:
                    item["clinical_reason_redacted"] = False
                items.append(item)
            return items
        finally:
            if should_close:
                c.close()

    def transition_appointment_state(
        self,
        organization_id: str,
        facility_id: str,
        appointment_id: str,
        target_status: str,
        actor_id: str,
        reason: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            appt = self.get_appointment(organization_id, facility_id, appointment_id, conn=c)
            current_status = appt["status"]
            if target_status == current_status:
                return appt

            allowed = APPOINTMENT_TRANSITIONS.get(current_status, set())
            if target_status not in allowed:
                raise ValidationError(
                    f"Invalid appointment state transition from '{current_status}' to '{target_status}'.",
                    details={"current_status": current_status, "target_status": target_status, "allowed": list(allowed)},
                )

            if target_status in ("cancelled", "rescheduled") and not reason:
                raise ValidationError(f"A reason is required when marking an appointment '{target_status}'.")

            # Release slot lock if cancelled, rescheduled, or no_show
            new_slot_lock = appt["slot_lock_key"] if target_status in ACTIVE_APPOINTMENT_STATUSES else None

            c.execute(
                """
                UPDATE appointments
                SET status = ?, slot_lock_key = ?,
                    cancellation_reason = CASE WHEN ? = 'cancelled' THEN ? ELSE cancellation_reason END,
                    reschedule_reason = CASE WHEN ? = 'rescheduled' THEN ? ELSE reschedule_reason END,
                    version = version + 1, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    target_status,
                    new_slot_lock,
                    target_status,
                    reason,
                    target_status,
                    reason,
                    actor_id,
                    appointment_id,
                    organization_id,
                ),
            )
            c.execute(
                """
                INSERT INTO appointment_events (id, appointment_id, event_type, from_status, to_status, reason, actor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    f"apev-{uuid.uuid4().hex[:10]}",
                    appointment_id,
                    f"STATUS_{target_status.upper()}",
                    current_status,
                    target_status,
                    reason,
                    actor_id,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type=f"APPOINTMENT_{target_status.upper()}",
                target_entity_type="APPOINTMENT",
                target_entity_id=appointment_id,
                details={"from_status": current_status, "to_status": target_status, "reason": reason},
            )
            if should_close:
                c.commit()
            return self.get_appointment(organization_id, facility_id, appointment_id, conn=c)
        finally:
            if should_close:
                c.close()

    def check_in_appointment(
        self,
        organization_id: str,
        facility_id: str,
        appointment_id: str,
        actor_id: str,
        payload: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Check in an appointment -> mark 'arrived', issue OPD queue token, and link/create encounter."""
        c, should_close = self._get_conn(conn)
        try:
            payload = payload or {}
            appt = self.get_appointment(organization_id, facility_id, appointment_id, conn=c)
            if appt["status"] not in ("booked", "confirmed", "arrived"):
                raise ValidationError(
                    f"Cannot check in appointment in status '{appt['status']}'.",
                    details={"status": appt["status"]},
                )

            if appt["status"] != "arrived":
                self.transition_appointment_state(
                    organization_id, facility_id, appointment_id, "arrived", actor_id, reason="Patient checked in", conn=c
                )

            # Issue or retrieve queue token for this appointment
            queue_date = appt["start_at"][:10] if appt.get("start_at") else date.today().isoformat()
            token = self.issue_queue_token(
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                payload={
                    "patient_id": appt["patient_id"],
                    "practitioner_id": appt["practitioner_id"],
                    "appointment_id": appointment_id,
                    "visit_type": "SCHEDULED",
                    "queue_date": queue_date,
                    "priority": payload.get("priority", "NORMAL"),
                    "priority_reason": payload.get("priority_reason"),
                    "idempotency_key": f"checkin-appt-{appointment_id}",
                },
                conn=c,
            )

            # Link appointment to encounter created/linked by queue token
            if token.get("encounter_id"):
                c.execute(
                    "UPDATE appointments SET encounter_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                    (token["encounter_id"], appointment_id),
                )

            if should_close:
                c.commit()
            updated_appt = self.get_appointment(organization_id, facility_id, appointment_id, conn=c)
            updated_appt["queue_token"] = token
            return updated_appt
        finally:
            if should_close:
                c.close()

    def reschedule_appointment(
        self,
        organization_id: str,
        facility_id: str,
        appointment_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Mark original appointment as 'rescheduled' (releasing its slot lock) and book a linked replacement slot."""
        c, should_close = self._get_conn(conn)
        try:
            old_appt = self.get_appointment(organization_id, facility_id, appointment_id, conn=c)
            new_start_at = payload.get("new_start_at") or payload.get("start_at")
            new_end_at = payload.get("new_end_at") or payload.get("end_at")
            reason = payload.get("reason") or "Patient requested reschedule"
            if not new_start_at:
                raise ValidationError("new_start_at is required to reschedule an appointment.")

            # Transition old appointment to rescheduled (releases old slot_lock_key)
            self.transition_appointment_state(
                organization_id, facility_id, appointment_id, "rescheduled", actor_id, reason=reason, conn=c
            )

            # Create replacement appointment
            new_appt = self.create_appointment(
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                payload={
                    "patient_id": old_appt["patient_id"],
                    "practitioner_id": payload.get("practitioner_id", old_appt["practitioner_id"]),
                    "start_at": new_start_at,
                    "end_at": new_end_at,
                    "appointment_type": old_appt["appointment_type"],
                    "reason_category": old_appt["reason_category"],
                    "clinical_reason_notes": old_appt["clinical_reason_notes"],
                    "booking_source": old_appt["booking_source"],
                    "followup_task_id": old_appt["followup_task_id"],
                    "status": "booked",
                },
                conn=c,
            )
            c.execute(
                "UPDATE appointments SET rescheduled_from_id = ? WHERE id = ?;",
                (appointment_id, new_appt["id"]),
            )
            if should_close:
                c.commit()
            return self.get_appointment(organization_id, facility_id, new_appt["id"], conn=c)
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 3. TOKEN AND WAITING QUEUE
    # =========================================================================

    def issue_queue_token(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        user_ctx: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Issue an OPD token for a walk-in or scheduled arrival, preventing duplicate active tokens."""
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            idempotency_key = payload.get("idempotency_key")
            if idempotency_key:
                cur.execute(
                    "SELECT id FROM queue_tokens WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                idem_row = cur.fetchone()
                if idem_row:
                    return self.get_queue_token(organization_id, facility_id, idem_row["id"], conn=c)

            patient_id = payload.get("patient_id")
            practitioner_id = payload.get("practitioner_id")
            if not patient_id or not practitioner_id:
                raise ValidationError("patient_id and practitioner_id are required to issue a queue token.")

            # Verify patient exists in organization
            cur.execute(
                "SELECT id, display_name FROM patients WHERE id = ? AND organization_id = ?;",
                (patient_id, organization_id),
            )
            if not cur.fetchone():
                raise NotFoundError(f"Patient '{patient_id}' not found.")

            queue_date = payload.get("queue_date") or date.today().isoformat()
            department_queue = payload.get("department_queue", "GENERAL_OPD")
            visit_type = payload.get("visit_type", "WALK_IN")
            appointment_id = payload.get("appointment_id")
            priority = str(payload.get("priority", "NORMAL")).upper()
            priority_reason = payload.get("priority_reason")
            priority_authorized_by = None

            if priority not in PRIORITY_WEIGHTS:
                raise ValidationError(f"Invalid queue priority '{priority}'. Allowed: {list(PRIORITY_WEIGHTS.keys())}")

            if priority != "NORMAL":
                if not priority_reason or len(priority_reason.strip()) < 3:
                    raise ValidationError("Non-normal queue priority requires an explicit reviewed priority_reason.")
                # Enforce that priority is assigned by an authorized clinical/staff role
                if user_ctx:
                    roles = set(user_ctx.get("roles", []))
                    perms = set(user_ctx.get("permissions", []))
                    if priority == "CLINICAL_URGENT" and not (
                        "PRACTITIONER" in roles
                        or "NURSE" in roles
                        or "CLINIC_ADMIN" in roles
                        or "ORG_ADMIN" in roles
                        or "queue:priority_override" in perms
                    ):
                        raise ForbiddenError(
                            "CLINICAL_URGENT queue priority requires clinical practitioner, nurse, or supervisor authorization."
                        )
                priority_authorized_by = actor_id

            active_lock = f"{facility_id}|{queue_date}|{patient_id}|{practitioner_id}"
            cur.execute(
                "SELECT id, token_code, status FROM queue_tokens WHERE active_patient_queue_lock = ?;",
                (active_lock,),
            )
            dup = cur.fetchone()
            if dup:
                raise ConflictError(
                    f"Patient already has an active token ({dup['token_code']}, status={dup['status']}) for this practitioner today.",
                    details={"existing_token_id": dup["id"], "token_code": dup["token_code"]},
                )

            # Compute next sequential token number for facility + date + practitioner
            cur.execute(
                """
                SELECT COALESCE(MAX(token_number), 0) + 1 AS next_num
                FROM queue_tokens
                WHERE facility_id = ? AND queue_date = ? AND practitioner_id = ?;
                """,
                (facility_id, queue_date, practitioner_id),
            )
            token_number = int(cur.fetchone()["next_num"])
            token_code = f"T-{token_number:03d}"
            token_id = f"qtok-{uuid.uuid4().hex[:12]}"
            arrival_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

            # Create or link Encounter for seamless handoff to Consultation Workspace
            encounter_id = payload.get("encounter_id")
            if not encounter_id:
                from apps.api.domains.encounters import EncounterService

                enc = EncounterService.create_encounter(
                    conn=c,
                    organization_id=organization_id,
                    facility_id=facility_id,
                    patient_id=patient_id,
                    practitioner_id=practitioner_id,
                    encounter_type="FOLLOW_UP" if visit_type == "SCHEDULED" and payload.get("is_followup") else "OPD_VISIT",
                    reason_for_visit=payload.get("reason_for_visit") or "OPD Consultation",
                    actor_id=actor_id,
                )
                encounter_id = enc["id"]

            c.execute(
                """
                INSERT INTO queue_tokens (
                    id, organization_id, facility_id, queue_date, token_number, token_code,
                    patient_id, appointment_id, encounter_id, practitioner_id, department_queue,
                    visit_type, priority, priority_reason, priority_authorized_by,
                    status, arrival_at, active_patient_queue_lock, idempotency_key,
                    created_by, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting', ?, ?, ?, ?, ?);
                """,
                (
                    token_id,
                    organization_id,
                    facility_id,
                    queue_date,
                    token_number,
                    token_code,
                    patient_id,
                    appointment_id,
                    encounter_id,
                    practitioner_id,
                    department_queue,
                    visit_type,
                    priority,
                    priority_reason,
                    priority_authorized_by,
                    arrival_at,
                    active_lock,
                    idempotency_key,
                    actor_id,
                    actor_id,
                ),
            )
            c.execute(
                """
                INSERT INTO queue_token_events (id, token_id, event_type, from_status, to_status, reason, actor_id)
                VALUES (?, ?, 'ISSUED', NULL, 'waiting', ?, ?);
                """,
                (f"qtev-{uuid.uuid4().hex[:10]}", token_id, priority_reason or "Token issued", actor_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="QUEUE_TOKEN_ISSUED",
                target_entity_type="QUEUE_TOKEN",
                target_entity_id=token_id,
                details={"token_code": token_code, "patient_id": patient_id, "encounter_id": encounter_id},
            )
            if should_close:
                c.commit()
            return self.get_queue_token(organization_id, facility_id, token_id, conn=c)
        finally:
            if should_close:
                c.close()

    def get_queue_token(
        self,
        organization_id: str,
        facility_id: str,
        token_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT q.*, p.display_name AS patient_name, p.mrn AS patient_mrn,
                       u.full_name AS practitioner_name
                FROM queue_tokens q
                JOIN patients p ON q.patient_id = p.id
                LEFT JOIN users u ON q.practitioner_id = u.id
                WHERE q.id = ? AND q.organization_id = ?;
                """,
                (token_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Queue token '{token_id}' not found.")
            res = dict(row)
            cur.execute(
                "SELECT * FROM queue_token_events WHERE token_id = ? ORDER BY occurred_at ASC;",
                (token_id,),
            )
            res["events"] = [dict(e) for e in cur.fetchall()]
            return res
        finally:
            if should_close:
                c.close()

    def list_queue(
        self,
        organization_id: str,
        facility_id: str,
        filters: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            filters = filters or {}
            queue_date = filters.get("queue_date") or date.today().isoformat()
            clauses = ["q.organization_id = ?", "q.facility_id = ?", "q.queue_date = ?"]
            params: List[Any] = [organization_id, facility_id, queue_date]

            if filters.get("practitioner_id"):
                clauses.append("q.practitioner_id = ?")
                params.append(filters["practitioner_id"])
            if filters.get("status"):
                clauses.append("q.status = ?")
                params.append(filters["status"])

            sql = f"""
                SELECT q.*, p.display_name AS patient_name, p.mrn AS patient_mrn,
                       u.full_name AS practitioner_name
                FROM queue_tokens q
                JOIN patients p ON q.patient_id = p.id
                LEFT JOIN users u ON q.practitioner_id = u.id
                WHERE {' AND '.join(clauses)}
                ORDER BY
                    CASE q.priority
                        WHEN 'CLINICAL_URGENT' THEN 1
                        WHEN 'ELDERLY_ASSISTED' THEN 2
                        ELSE 3
                    END ASC,
                    q.token_number ASC;
            """
            cur = c.cursor()
            cur.execute(sql, tuple(params))
            tokens = [dict(r) for r in cur.fetchall()]
            return {
                "queue_date": queue_date,
                "facility_id": facility_id,
                "total_tokens": len(tokens),
                "waiting_count": sum(1 for t in tokens if t["status"] in ("checked_in", "waiting")),
                "called_count": sum(1 for t in tokens if t["status"] == "called"),
                "in_consultation_count": sum(1 for t in tokens if t["status"] == "in_consultation"),
                "completed_count": sum(1 for t in tokens if t["status"] == "completed"),
                "tokens": tokens,
            }
        finally:
            if should_close:
                c.close()

    def get_public_queue_display(
        self,
        organization_id: str,
        facility_id: str,
        queue_date: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Return a strictly privacy-preserving waiting room display without patient names, MRNs, or diagnoses."""
        c, should_close = self._get_conn(conn)
        try:
            q_date = queue_date or date.today().isoformat()
            cur = c.cursor()
            cur.execute(
                """
                SELECT q.token_code, q.token_number, q.department_queue, q.status,
                       u.full_name AS practitioner_name
                FROM queue_tokens q
                LEFT JOIN users u ON q.practitioner_id = u.id
                WHERE q.organization_id = ? AND q.facility_id = ? AND q.queue_date = ?
                  AND q.status IN ('waiting', 'called', 'in_consultation')
                ORDER BY
                    CASE q.priority
                        WHEN 'CLINICAL_URGENT' THEN 1
                        WHEN 'ELDERLY_ASSISTED' THEN 2
                        ELSE 3
                    END ASC,
                    q.token_number ASC;
                """,
                (organization_id, facility_id, q_date),
            )
            display_items = []
            for r in cur.fetchall():
                display_items.append(
                    {
                        "token_code": r["token_code"],
                        "token_number": r["token_number"],
                        "department_queue": r["department_queue"],
                        "practitioner_name": r["practitioner_name"],
                        "status": r["status"],
                        "privacy_redacted": True,
                    }
                )
            return {
                "queue_date": q_date,
                "facility_id": facility_id,
                "privacy_mode": "PUBLIC_SAFE_TOKEN_ONLY",
                "active_tokens": display_items,
            }
        finally:
            if should_close:
                c.close()

    def transition_queue_token(
        self,
        organization_id: str,
        facility_id: str,
        token_id: str,
        target_status: str,
        actor_id: str,
        reason: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            tok = self.get_queue_token(organization_id, facility_id, token_id, conn=c)
            current_status = tok["status"]
            if target_status == current_status:
                return tok

            allowed = QUEUE_TOKEN_TRANSITIONS.get(current_status, set())
            if target_status not in allowed:
                raise ValidationError(
                    f"Invalid queue token transition from '{current_status}' to '{target_status}'.",
                    details={"current_status": current_status, "target_status": target_status, "allowed": list(allowed)},
                )

            if target_status in ("paused", "cancelled") and not reason:
                raise ValidationError(f"A reason is required when transitioning a queue token to '{target_status}'.")

            now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            called_at = now_iso if target_status == "called" and not tok["called_at"] else tok["called_at"]
            started_at = (
                now_iso
                if target_status == "in_consultation" and not tok["consultation_started_at"]
                else tok["consultation_started_at"]
            )
            ended_at = now_iso if target_status == "completed" else tok["consultation_ended_at"]
            active_lock = tok["active_patient_queue_lock"] if target_status in ACTIVE_QUEUE_STATUSES else None

            c.execute(
                """
                UPDATE queue_tokens
                SET status = ?, called_at = ?, consultation_started_at = ?, consultation_ended_at = ?,
                    pause_reason = CASE WHEN ? = 'paused' THEN ? ELSE pause_reason END,
                    cancel_reason = CASE WHEN ? = 'cancelled' THEN ? ELSE cancel_reason END,
                    active_patient_queue_lock = ?, updated_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (
                    target_status,
                    called_at,
                    started_at,
                    ended_at,
                    target_status,
                    reason,
                    target_status,
                    reason,
                    active_lock,
                    actor_id,
                    token_id,
                    organization_id,
                ),
            )
            c.execute(
                """
                INSERT INTO queue_token_events (id, token_id, event_type, from_status, to_status, reason, actor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    f"qtev-{uuid.uuid4().hex[:10]}",
                    token_id,
                    f"TOKEN_{target_status.upper()}",
                    current_status,
                    target_status,
                    reason,
                    actor_id,
                ),
            )

            # Synchronize linked encounter and appointment when consultation starts or completes
            if target_status == "in_consultation":
                if tok.get("encounter_id"):
                    c.execute(
                        "UPDATE encounters SET status = 'IN_PROGRESS', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'DRAFT';",
                        (tok["encounter_id"],),
                    )
                if tok.get("appointment_id"):
                    c.execute(
                        "UPDATE appointments SET status = 'in_progress', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('booked','confirmed','arrived');",
                        (tok["appointment_id"],),
                    )
            elif target_status == "completed":
                if tok.get("appointment_id"):
                    c.execute(
                        "UPDATE appointments SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                        (tok["appointment_id"],),
                    )

            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type=f"QUEUE_TOKEN_{target_status.upper()}",
                target_entity_type="QUEUE_TOKEN",
                target_entity_id=token_id,
                details={"from_status": current_status, "to_status": target_status, "encounter_id": tok.get("encounter_id")},
            )
            if should_close:
                c.commit()
            return self.get_queue_token(organization_id, facility_id, token_id, conn=c)
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 4. BILLING, INVOICING, EXACT-DECIMAL PAYMENTS, REFUNDS & RECONCILIATION
    # =========================================================================

    def list_fee_catalog(
        self,
        organization_id: str,
        facility_id: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM fee_catalog_items
                WHERE organization_id = ? AND is_active = 1
                ORDER BY category ASC, code ASC;
                """,
                (organization_id,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                c.close()

    def upsert_fee_catalog_item(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            code = payload.get("code")
            name = payload.get("name")
            if not code or not name:
                raise ValidationError("Fee item code and name are required.")
            unit_price = to_money(payload.get("unit_price_decimal", payload.get("unit_price", "0.00")), "unit_price")
            if unit_price < Decimal("0.00"):
                raise ValidationError("Fee item unit_price cannot be negative.")
            tax_rate_bp = int(payload.get("tax_rate_bp", 0))
            currency = str(payload.get("currency", "INR")).upper()
            category = payload.get("category", "CONSULTATION")
            item_id = payload.get("id") or f"fee-{uuid.uuid4().hex[:10]}"

            c.execute(
                """
                INSERT INTO fee_catalog_items (
                    id, organization_id, facility_id, code, name, category,
                    currency, unit_price_decimal, tax_rate_bp, is_active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(organization_id, code) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    unit_price_decimal = excluded.unit_price_decimal,
                    tax_rate_bp = excluded.tax_rate_bp,
                    version = version + 1,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (item_id, organization_id, facility_id, code, name, category, currency, fmt_money(unit_price), tax_rate_bp, actor_id),
            )
            if should_close:
                c.commit()
            cur = c.cursor()
            cur.execute(
                "SELECT * FROM fee_catalog_items WHERE organization_id = ? AND code = ?;",
                (organization_id, code),
            )
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def create_invoice(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Create an invoice using exact Decimal arithmetic for all line items, discounts, and taxes."""
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            idempotency_key = payload.get("idempotency_key")
            if idempotency_key:
                cur.execute(
                    "SELECT id FROM invoices WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                idem = cur.fetchone()
                if idem:
                    return self.get_invoice(organization_id, facility_id, idem["id"], conn=c)

            patient_id = payload.get("patient_id")
            lines_input = payload.get("lines", [])
            if not patient_id:
                raise ValidationError("patient_id is required to create an invoice.")
            if not lines_input or not isinstance(lines_input, list):
                raise ValidationError("At least one invoice line item is required.")

            cur.execute(
                "SELECT id FROM patients WHERE id = ? AND organization_id = ?;",
                (patient_id, organization_id),
            )
            if not cur.fetchone():
                raise NotFoundError(f"Patient '{patient_id}' not found.")

            settings = self.get_facility_settings(organization_id, facility_id, conn=c)
            currency = str(payload.get("currency", settings["currency"])).upper()
            invoice_discount = to_money(payload.get("discount_decimal", "0.00"), "discount_decimal")
            discount_reason = payload.get("discount_reason")
            if invoice_discount > Decimal("0.00") and not discount_reason:
                raise ValidationError("discount_reason is required when applying an invoice-level discount.")

            subtotal = Decimal("0.00")
            total_line_discounts = Decimal("0.00")
            total_tax = Decimal("0.00")
            prepared_lines = []

            for idx, ln in enumerate(lines_input):
                qty = to_money(ln.get("quantity_decimal", ln.get("quantity", "1.00")), "quantity")
                unit_price = to_money(ln.get("unit_price_decimal", ln.get("unit_price", "0.00")), "unit_price")
                line_disc = to_money(ln.get("discount_decimal", ln.get("discount", "0.00")), "line_discount")
                tax_bp = int(ln.get("tax_rate_bp", settings["default_tax_rate_bp"] if settings["tax_enabled"] else 0))

                if qty <= Decimal("0.00"):
                    raise ValidationError("Line quantity must be positive.")
                if unit_price < Decimal("0.00") or line_disc < Decimal("0.00"):
                    raise ValidationError("Line unit_price and discount cannot be negative.")

                gross_line = (qty * unit_price).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                if line_disc > gross_line:
                    raise ValidationError("Line discount cannot exceed line gross amount.")
                taxable_base = gross_line - line_disc
                tax_amt = ((taxable_base * Decimal(tax_bp)) / TEN_THOUSAND).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
                line_total = taxable_base + tax_amt

                subtotal += gross_line
                total_line_discounts += line_disc
                total_tax += tax_amt

                prepared_lines.append(
                    {
                        "id": f"invl-{uuid.uuid4().hex[:12]}",
                        "fee_item_id": ln.get("fee_item_id"),
                        "inventory_item_id": ln.get("inventory_item_id"),
                        "description": ln.get("description") or "Clinical Service",
                        "quantity_decimal": fmt_money(qty),
                        "unit_price_decimal": fmt_money(unit_price),
                        "discount_decimal": fmt_money(line_disc),
                        "tax_rate_bp": tax_bp,
                        "tax_amount_decimal": fmt_money(tax_amt),
                        "line_total_decimal": fmt_money(line_total),
                        "sort_order": idx,
                    }
                )

            total_discount = total_line_discounts + invoice_discount
            if total_discount > subtotal:
                raise ValidationError("Total discount cannot exceed invoice subtotal.")
            grand_total = (subtotal - total_discount + total_tax).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

            cur.execute(
                "SELECT COUNT(*) AS cnt FROM invoices WHERE organization_id = ?;",
                (organization_id,),
            )
            seq = int(cur.fetchone()["cnt"]) + 1
            invoice_number = f"INV-2026-{seq:05d}"
            invoice_id = f"inv-{uuid.uuid4().hex[:12]}"

            c.execute(
                """
                INSERT INTO invoices (
                    id, organization_id, facility_id, invoice_number, patient_id,
                    encounter_id, appointment_id, currency, status,
                    subtotal_decimal, discount_decimal, discount_reason,
                    tax_decimal, total_decimal, paid_decimal, refunded_decimal,
                    balance_due_decimal, notes, idempotency_key, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'DRAFT', ?, ?, ?, ?, ?, '0.00', '0.00', ?, ?, ?, ?);
                """,
                (
                    invoice_id,
                    organization_id,
                    facility_id,
                    invoice_number,
                    patient_id,
                    payload.get("encounter_id"),
                    payload.get("appointment_id"),
                    currency,
                    fmt_money(subtotal),
                    fmt_money(total_discount),
                    discount_reason,
                    fmt_money(total_tax),
                    fmt_money(grand_total),
                    fmt_money(grand_total),
                    payload.get("notes"),
                    idempotency_key,
                    actor_id,
                ),
            )

            for pl in prepared_lines:
                c.execute(
                    """
                    INSERT INTO invoice_lines (
                        id, invoice_id, fee_item_id, inventory_item_id, description,
                        quantity_decimal, unit_price_decimal, discount_decimal,
                        tax_rate_bp, tax_amount_decimal, line_total_decimal, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        pl["id"],
                        invoice_id,
                        pl["fee_item_id"],
                        pl["inventory_item_id"],
                        pl["description"],
                        pl["quantity_decimal"],
                        pl["unit_price_decimal"],
                        pl["discount_decimal"],
                        pl["tax_rate_bp"],
                        pl["tax_amount_decimal"],
                        pl["line_total_decimal"],
                        pl["sort_order"],
                    ),
                )

            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="INVOICE_DRAFT_CREATED",
                target_entity_type="INVOICE",
                target_entity_id=invoice_id,
                details={"invoice_number": invoice_number, "total_decimal": fmt_money(grand_total), "currency": currency},
            )

            if payload.get("auto_finalize"):
                self.finalize_invoice(organization_id, facility_id, invoice_id, actor_id, conn=c)

            if should_close:
                c.commit()
            return self.get_invoice(organization_id, facility_id, invoice_id, conn=c)
        finally:
            if should_close:
                c.close()

    def get_invoice(
        self,
        organization_id: str,
        facility_id: str,
        invoice_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT i.*, p.display_name AS patient_name, p.mrn AS patient_mrn
                FROM invoices i
                JOIN patients p ON i.patient_id = p.id
                WHERE i.id = ? AND i.organization_id = ?;
                """,
                (invoice_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Invoice '{invoice_id}' not found.")
            inv = dict(row)
            cur.execute(
                "SELECT * FROM invoice_lines WHERE invoice_id = ? ORDER BY sort_order ASC;",
                (invoice_id,),
            )
            inv["lines"] = [dict(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT * FROM payments WHERE invoice_id = ? ORDER BY recorded_at ASC;",
                (invoice_id,),
            )
            inv["payments"] = [dict(r) for r in cur.fetchall()]
            cur.execute(
                "SELECT * FROM payment_refunds WHERE invoice_id = ? ORDER BY created_at ASC;",
                (invoice_id,),
            )
            inv["refunds"] = [dict(r) for r in cur.fetchall()]
            return inv
        finally:
            if should_close:
                c.close()

    def list_invoices(
        self,
        organization_id: str,
        facility_id: str,
        filters: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            filters = filters or {}
            clauses = ["i.organization_id = ?", "i.facility_id = ?"]
            params: List[Any] = [organization_id, facility_id]
            if filters.get("patient_id"):
                clauses.append("i.patient_id = ?")
                params.append(filters["patient_id"])
            if filters.get("status"):
                clauses.append("i.status = ?")
                params.append(filters["status"])

            cur = c.cursor()
            cur.execute(
                f"""
                SELECT i.*, p.display_name AS patient_name, p.mrn AS patient_mrn
                FROM invoices i
                JOIN patients p ON i.patient_id = p.id
                WHERE {' AND '.join(clauses)}
                ORDER BY i.created_at DESC;
                """,
                tuple(params),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                c.close()

    def finalize_invoice(
        self,
        organization_id: str,
        facility_id: str,
        invoice_id: str,
        actor_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Finalize a DRAFT invoice and lock an immutable snapshot."""
        c, should_close = self._get_conn(conn)
        try:
            inv = self.get_invoice(organization_id, facility_id, invoice_id, conn=c)
            if inv["status"] != "DRAFT":
                raise ConflictError(
                    f"Only DRAFT invoices can be finalized (current status: {inv['status']}).",
                    details={"status": inv["status"]},
                )
            now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            snapshot = {
                "invoice_id": inv["id"],
                "invoice_number": inv["invoice_number"],
                "patient_id": inv["patient_id"],
                "currency": inv["currency"],
                "subtotal_decimal": inv["subtotal_decimal"],
                "discount_decimal": inv["discount_decimal"],
                "tax_decimal": inv["tax_decimal"],
                "total_decimal": inv["total_decimal"],
                "lines": inv["lines"],
                "finalized_at": now_iso,
                "finalized_by": actor_id,
            }
            c.execute(
                """
                UPDATE invoices
                SET status = 'FINALIZED', finalized_at = ?, finalized_by = ?,
                    finalized_snapshot_json = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (now_iso, actor_id, json.dumps(snapshot, sort_keys=True), invoice_id, organization_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="INVOICE_FINALIZED",
                target_entity_type="INVOICE",
                target_entity_id=invoice_id,
                details={"invoice_number": inv["invoice_number"], "total_decimal": inv["total_decimal"]},
            )
            if should_close:
                c.commit()
            return self.get_invoice(organization_id, facility_id, invoice_id, conn=c)
        finally:
            if should_close:
                c.close()

    def record_payment(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Record an exact-decimal payment against a finalized invoice with idempotency and provider status honesty."""
        c, should_close = self._get_conn(conn)
        try:
            # Security check: never accept or store card CVV or raw payment credentials
            lower_keys = {str(k).lower() for k in payload.keys()}
            forbidden_found = lower_keys.intersection(FORBIDDEN_PAYMENT_FIELDS)
            if forbidden_found:
                raise ValidationError(
                    "Sensitive card security codes (CVV/CVC/raw PAN) are strictly prohibited.",
                    details={"prohibited_fields": list(forbidden_found)},
                )

            cur = c.cursor()
            idempotency_key = payload.get("idempotency_key")
            if idempotency_key:
                cur.execute(
                    "SELECT id FROM payments WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                idem = cur.fetchone()
                if idem:
                    cur.execute("SELECT * FROM payments WHERE id = ?;", (idem["id"],))
                    p_row = dict(cur.fetchone())
                    p_row["idempotent_replay"] = True
                    return p_row

            invoice_id = payload.get("invoice_id")
            if not invoice_id:
                raise ValidationError("invoice_id is required.")

            inv = self.get_invoice(organization_id, facility_id, invoice_id, conn=c)
            if inv["status"] == "DRAFT":
                # Auto-finalize draft invoice when payment is attempted
                inv = self.finalize_invoice(organization_id, facility_id, invoice_id, actor_id, conn=c)

            if inv["status"] in ("VOIDED", "PAID"):
                raise ConflictError(
                    f"Cannot record payment on invoice in status '{inv['status']}'.",
                    details={"invoice_status": inv["status"]},
                )

            amount = to_money(payload.get("amount_decimal", payload.get("amount")), "amount")
            if amount <= Decimal("0.00"):
                raise ValidationError("Payment amount must be greater than 0.00.")

            balance_due = to_money(inv["balance_due_decimal"], "balance_due")
            if amount > balance_due:
                raise ValidationError(
                    f"Payment amount ({fmt_money(amount)}) exceeds invoice balance due ({fmt_money(balance_due)}).",
                    details={"amount_decimal": fmt_money(amount), "balance_due_decimal": fmt_money(balance_due)},
                )

            payment_method = str(payload.get("payment_method", "CASH")).upper()
            if payment_method not in ("CASH", "UPI", "CARD", "BANK_TRANSFER", "MANUAL_OTHER"):
                raise ValidationError(f"Unsupported payment_method '{payment_method}'.")

            provider_mode = payload.get("provider_mode", "MANUAL_RECORDED")
            provider_status = str(payload.get("provider_status", "POSTED")).upper()
            if provider_status not in ("POSTED", "FAILED", "UNKNOWN", "PENDING_PROVIDER"):
                raise ValidationError(f"Invalid provider_status '{provider_status}'.")

            cur.execute("SELECT COUNT(*) AS cnt FROM payments WHERE organization_id = ?;", (organization_id,))
            p_seq = int(cur.fetchone()["cnt"]) + 1
            payment_number = f"PAY-2026-{p_seq:05d}"
            payment_id = f"pay-{uuid.uuid4().hex[:12]}"

            receipt_number = None
            receipt_snapshot = None
            if provider_status == "POSTED":
                receipt_number = f"RCP-2026-{p_seq:05d}"
                settings = self.get_facility_settings(organization_id, facility_id, conn=c)
                receipt_snapshot = {
                    "receipt_number": receipt_number,
                    "payment_number": payment_number,
                    "invoice_number": inv["invoice_number"],
                    "patient_name": inv["patient_name"],
                    "patient_mrn": inv["patient_mrn"],
                    "currency": inv["currency"],
                    "amount_paid_decimal": fmt_money(amount),
                    "payment_method": payment_method,
                    "provider_mode": provider_mode,
                    "header_title": settings["receipt_header_title"],
                    "footer_note": settings["receipt_footer_note"],
                    "issued_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                }

            c.execute(
                """
                INSERT INTO payments (
                    id, organization_id, facility_id, payment_number, invoice_id, patient_id,
                    currency, amount_decimal, refunded_amount_decimal, payment_method,
                    provider_mode, provider_reference, status, failure_reason,
                    receipt_number, receipt_snapshot_json, recorded_by, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '0.00', ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    payment_id,
                    organization_id,
                    facility_id,
                    payment_number,
                    invoice_id,
                    inv["patient_id"],
                    inv["currency"],
                    fmt_money(amount),
                    payment_method,
                    provider_mode,
                    payload.get("provider_reference"),
                    provider_status,
                    payload.get("failure_reason"),
                    receipt_number,
                    json.dumps(receipt_snapshot, sort_keys=True) if receipt_snapshot else None,
                    actor_id,
                    idempotency_key,
                ),
            )

            # Only allocate funds and update invoice paid balance if payment status is POSTED
            if provider_status == "POSTED":
                c.execute(
                    """
                    INSERT INTO payment_allocations (id, payment_id, invoice_id, allocated_amount_decimal)
                    VALUES (?, ?, ?, ?);
                    """,
                    (f"palloc-{uuid.uuid4().hex[:10]}", payment_id, invoice_id, fmt_money(amount)),
                )
                new_paid = to_money(inv["paid_decimal"]) + amount
                new_balance = balance_due - amount
                new_inv_status = "PAID" if new_balance == Decimal("0.00") else "PARTIALLY_PAID"
                c.execute(
                    """
                    UPDATE invoices
                    SET paid_decimal = ?, balance_due_decimal = ?, status = ?,
                        version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND organization_id = ?;
                    """,
                    (fmt_money(new_paid), fmt_money(new_balance), new_inv_status, invoice_id, organization_id),
                )

            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type=f"PAYMENT_{provider_status}",
                target_entity_type="PAYMENT",
                target_entity_id=payment_id,
                details={
                    "invoice_id": invoice_id,
                    "amount_decimal": fmt_money(amount),
                    "payment_method": payment_method,
                    "status": provider_status,
                },
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM payments WHERE id = ?;", (payment_id,))
            res = dict(cur.fetchone())
            res["idempotent_replay"] = False
            res["receipt"] = receipt_snapshot
            return res
        finally:
            if should_close:
                c.close()

    def refund_payment(
        self,
        organization_id: str,
        facility_id: str,
        payment_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Execute a permission-controlled, auditable refund without overwriting original payment amount."""
        c, should_close = self._get_conn(conn)
        try:
            reason = payload.get("reason")
            if not reason or len(reason.strip()) < 3:
                raise ValidationError("A documented reason is required to refund a payment.")

            cur = c.cursor()
            idempotency_key = payload.get("idempotency_key")
            if idempotency_key:
                cur.execute(
                    "SELECT * FROM payment_refunds WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                idem = cur.fetchone()
                if idem:
                    return dict(idem)

            cur.execute(
                "SELECT * FROM payments WHERE id = ? AND organization_id = ?;",
                (payment_id, organization_id),
            )
            pay = cur.fetchone()
            if not pay:
                raise NotFoundError(f"Payment '{payment_id}' not found.")
            if pay["status"] not in ("POSTED", "PARTIALLY_REFUNDED"):
                raise ConflictError(f"Cannot refund payment in status '{pay['status']}'.")

            orig_amt = to_money(pay["amount_decimal"])
            already_refunded = to_money(pay["refunded_amount_decimal"])
            refundable = orig_amt - already_refunded
            refund_amt = to_money(payload.get("amount_decimal", fmt_money(refundable)), "amount_decimal")

            if refund_amt <= Decimal("0.00") or refund_amt > refundable:
                raise ValidationError(
                    f"Refund amount ({fmt_money(refund_amt)}) must be between 0.01 and {fmt_money(refundable)}."
                )

            cur.execute("SELECT COUNT(*) AS cnt FROM payment_refunds WHERE organization_id = ?;", (organization_id,))
            r_seq = int(cur.fetchone()["cnt"]) + 1
            refund_number = f"REF-2026-{r_seq:05d}"
            refund_id = f"ref-{uuid.uuid4().hex[:12]}"

            c.execute(
                """
                INSERT INTO payment_refunds (
                    id, organization_id, facility_id, refund_number, payment_id, invoice_id,
                    currency, amount_decimal, refund_method, reason, status, authorized_by, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?, ?);
                """,
                (
                    refund_id,
                    organization_id,
                    facility_id,
                    refund_number,
                    payment_id,
                    pay["invoice_id"],
                    pay["currency"],
                    fmt_money(refund_amt),
                    payload.get("refund_method", pay["payment_method"]),
                    reason.strip(),
                    actor_id,
                    idempotency_key,
                ),
            )

            new_pay_refunded = already_refunded + refund_amt
            new_pay_status = "REFUNDED" if new_pay_refunded == orig_amt else "PARTIALLY_REFUNDED"
            c.execute(
                "UPDATE payments SET refunded_amount_decimal = ?, status = ? WHERE id = ?;",
                (fmt_money(new_pay_refunded), new_pay_status, payment_id),
            )

            # Update invoice refunded_decimal and balance_due_decimal
            inv = self.get_invoice(organization_id, facility_id, pay["invoice_id"], conn=c)
            inv_refunded = to_money(inv["refunded_decimal"]) + refund_amt
            inv_net_paid = to_money(inv["paid_decimal"]) - inv_refunded
            inv_total = to_money(inv["total_decimal"])
            inv_balance = inv_total - inv_net_paid
            inv_status = "REFUNDED" if inv_net_paid == Decimal("0.00") else "PARTIALLY_PAID"

            c.execute(
                """
                UPDATE invoices
                SET refunded_decimal = ?, balance_due_decimal = ?, status = ?,
                    version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
                """,
                (fmt_money(inv_refunded), fmt_money(inv_balance), inv_status, pay["invoice_id"]),
            )

            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="PAYMENT_REFUNDED",
                target_entity_type="PAYMENT_REFUND",
                target_entity_id=refund_id,
                details={
                    "payment_id": payment_id,
                    "invoice_id": pay["invoice_id"],
                    "amount_decimal": fmt_money(refund_amt),
                    "reason": reason.strip(),
                },
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM payment_refunds WHERE id = ?;", (refund_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def void_invoice(
        self,
        organization_id: str,
        facility_id: str,
        invoice_id: str,
        actor_id: str,
        reason: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Void an unpaid or fully-refunded invoice with mandatory reason and audit trail."""
        c, should_close = self._get_conn(conn)
        try:
            if not reason or len(reason.strip()) < 3:
                raise ValidationError("A documented reason is required to void an invoice.")
            inv = self.get_invoice(organization_id, facility_id, invoice_id, conn=c)
            if inv["status"] == "VOIDED":
                return inv

            net_paid = to_money(inv["paid_decimal"]) - to_money(inv["refunded_decimal"])
            if net_paid > Decimal("0.00"):
                raise ConflictError(
                    "Cannot void an invoice with unrefunded posted payments. Refund the posted payments first.",
                    details={"net_paid_decimal": fmt_money(net_paid)},
                )

            now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            c.execute(
                """
                UPDATE invoices
                SET status = 'VOIDED', voided_at = ?, voided_by = ?, void_reason = ?,
                    balance_due_decimal = '0.00', version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND organization_id = ?;
                """,
                (now_iso, actor_id, reason.strip(), invoice_id, organization_id),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="INVOICE_VOIDED",
                target_entity_type="INVOICE",
                target_entity_id=invoice_id,
                details={"invoice_number": inv["invoice_number"], "void_reason": reason.strip()},
            )
            if should_close:
                c.commit()
            return self.get_invoice(organization_id, facility_id, invoice_id, conn=c)
        finally:
            if should_close:
                c.close()

    def get_collections_report(
        self,
        organization_id: str,
        facility_id: str,
        filters: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Compute daily/period collections reconciling exact posted payments, refunds, voids, and balances."""
        c, should_close = self._get_conn(conn)
        try:
            filters = filters or {}
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM payments
                WHERE organization_id = ? AND facility_id = ?
                ORDER BY recorded_at ASC;
                """,
                (organization_id, facility_id),
            )
            payments = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT * FROM payment_refunds
                WHERE organization_id = ? AND facility_id = ? AND status = 'COMPLETED';
                """,
                (organization_id, facility_id),
            )
            refunds = [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT * FROM invoices
                WHERE organization_id = ? AND facility_id = ?;
                """,
                (organization_id, facility_id),
            )
            invoices = [dict(r) for r in cur.fetchall()]

            by_method: Dict[str, Decimal] = {
                "CASH": Decimal("0.00"),
                "UPI": Decimal("0.00"),
                "CARD": Decimal("0.00"),
                "BANK_TRANSFER": Decimal("0.00"),
                "MANUAL_OTHER": Decimal("0.00"),
            }
            gross_collected = Decimal("0.00")
            failed_or_unknown_count = 0

            for p in payments:
                if p["status"] in ("POSTED", "PARTIALLY_REFUNDED", "REFUNDED"):
                    amt = to_money(p["amount_decimal"])
                    gross_collected += amt
                    m = p["payment_method"]
                    by_method[m] = by_method.get(m, Decimal("0.00")) + amt
                elif p["status"] in ("FAILED", "UNKNOWN"):
                    failed_or_unknown_count += 1

            total_refunded = sum((to_money(r["amount_decimal"]) for r in refunds), Decimal("0.00"))
            net_collections = gross_collected - total_refunded
            outstanding_balance = sum(
                (to_money(i["balance_due_decimal"]) for i in invoices if i["status"] not in ("VOIDED", "DRAFT")),
                Decimal("0.00"),
            )
            voided_count = sum(1 for i in invoices if i["status"] == "VOIDED")

            return {
                "data_as_of": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "facility_id": facility_id,
                "currency": "INR",
                "gross_collections_decimal": fmt_money(gross_collected),
                "total_refunds_decimal": fmt_money(total_refunded),
                "net_collections_decimal": fmt_money(net_collections),
                "outstanding_balance_decimal": fmt_money(outstanding_balance),
                "collections_by_method": {k: fmt_money(v) for k, v in by_method.items()},
                "posted_payment_count": sum(
                    1 for p in payments if p["status"] in ("POSTED", "PARTIALLY_REFUNDED", "REFUNDED")
                ),
                "failed_or_unknown_payment_count": failed_or_unknown_count,
                "voided_invoice_count": voided_count,
            }
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 5. PHARMACY / DISPENSARY INVENTORY, BATCHES, EXPIRY & LEDGER MOVEMENTS
    # =========================================================================

    def _assert_inventory_enabled(
        self, organization_id: str, facility_id: str, conn: sqlite3.Connection
    ) -> Dict[str, Any]:
        settings = self.get_facility_settings(organization_id, facility_id, conn=conn)
        if not settings.get("inventory_enabled"):
            raise ConflictError(
                "Pharmacy/dispensary inventory module is disabled for this facility.",
                details={"code": "INVENTORY_MODULE_DISABLED", "facility_id": facility_id},
            )
        return settings

    def _ensure_default_locations(
        self, organization_id: str, facility_id: str, conn: sqlite3.Connection
    ) -> Tuple[str, str]:
        cur = conn.cursor()
        main_id = f"loc-main-{facility_id}"
        quar_id = f"loc-quar-{facility_id}"
        conn.execute(
            """
            INSERT OR IGNORE INTO inventory_locations (id, organization_id, facility_id, code, name, location_type, is_dispensable, is_active)
            VALUES
            (?, ?, ?, 'MAIN-DISP', 'Main Dispensary Shelf', 'MAIN_DISPENSARY', 1, 1),
            (?, ?, ?, 'QUAR-HOLD', 'Quarantine & Recall Hold', 'QUARANTINE_HOLD', 0, 1);
            """,
            (main_id, organization_id, facility_id, quar_id, organization_id, facility_id),
        )
        return main_id, quar_id

    def create_inventory_item(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            self._assert_inventory_enabled(organization_id, facility_id, c)
            sku = payload.get("sku")
            name = payload.get("name")
            if not sku or not name:
                raise ValidationError("Inventory item 'sku' and 'name' are required.")

            reorder_threshold = to_money(payload.get("reorder_threshold_decimal", "100.00"), "reorder_threshold")
            std_cost = to_money(payload.get("standard_cost_decimal", "0.00"), "standard_cost")
            sell_price = to_money(payload.get("selling_price_decimal", "0.00"), "selling_price")

            item_id = payload.get("id") or f"iitem-{uuid.uuid4().hex[:10]}"
            c.execute(
                """
                INSERT INTO inventory_items (
                    id, organization_id, facility_id, sku, name, formulation_id, ingredient_id,
                    dosage_form, strength, unit, reorder_threshold_decimal,
                    standard_cost_decimal, selling_price_decimal, manufacturer_name,
                    is_controlled_mudabbar, is_active, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(organization_id, sku) DO UPDATE SET
                    name = excluded.name,
                    reorder_threshold_decimal = excluded.reorder_threshold_decimal,
                    standard_cost_decimal = excluded.standard_cost_decimal,
                    selling_price_decimal = excluded.selling_price_decimal,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    item_id,
                    organization_id,
                    facility_id,
                    sku,
                    name,
                    payload.get("formulation_id"),
                    payload.get("ingredient_id"),
                    payload.get("dosage_form", "MAJOON"),
                    payload.get("strength"),
                    payload.get("unit", "g"),
                    fmt_money(reorder_threshold),
                    fmt_money(std_cost),
                    fmt_money(sell_price),
                    payload.get("manufacturer_name"),
                    1 if payload.get("is_controlled_mudabbar") else 0,
                    actor_id,
                ),
            )
            if should_close:
                c.commit()
            cur = c.cursor()
            cur.execute("SELECT * FROM inventory_items WHERE organization_id = ? AND sku = ?;", (organization_id, sku))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def list_inventory_items(
        self,
        organization_id: str,
        facility_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        c, should_close = self._get_conn(conn)
        try:
            self._assert_inventory_enabled(organization_id, facility_id, c)
            cur = c.cursor()
            cur.execute(
                """
                SELECT * FROM inventory_items
                WHERE organization_id = ? AND facility_id = ? AND is_active = 1
                ORDER BY name ASC;
                """,
                (organization_id, facility_id),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            if should_close:
                c.close()

    def receive_stock(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Receive a batch into inventory and record an immutable STOCK_RECEIPT ledger movement."""
        c, should_close = self._get_conn(conn)
        try:
            self._assert_inventory_enabled(organization_id, facility_id, c)
            main_loc_id, _ = self._ensure_default_locations(organization_id, facility_id, c)

            cur = c.cursor()
            idempotency_key = payload.get("idempotency_key")
            if idempotency_key:
                cur.execute(
                    "SELECT * FROM inventory_movements WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                idem = cur.fetchone()
                if idem:
                    return {"movement": dict(idem), "idempotent_replay": True}

            inventory_item_id = payload.get("inventory_item_id")
            batch_number = payload.get("batch_number")
            expiry_date = payload.get("expiry_date")
            qty = to_money(payload.get("quantity_decimal", payload.get("quantity")), "quantity")
            if not inventory_item_id or not batch_number or not expiry_date:
                raise ValidationError("inventory_item_id, batch_number, and expiry_date (YYYY-MM-DD) are required.")
            if qty <= Decimal("0.00"):
                raise ValidationError("Stock receipt quantity must be greater than 0.00.")

            cur.execute(
                "SELECT * FROM inventory_items WHERE id = ? AND organization_id = ?;",
                (inventory_item_id, organization_id),
            )
            item = cur.fetchone()
            if not item:
                raise NotFoundError(f"Inventory item '{inventory_item_id}' not found.")

            location_id = payload.get("location_id") or main_loc_id
            unit_cost = to_money(payload.get("unit_cost_decimal", item["standard_cost_decimal"]), "unit_cost")
            sell_price = to_money(payload.get("selling_price_decimal", item["selling_price_decimal"]), "selling_price")

            cur.execute(
                """
                SELECT * FROM inventory_batches
                WHERE facility_id = ? AND inventory_item_id = ? AND batch_number = ? AND location_id = ?;
                """,
                (facility_id, inventory_item_id, batch_number, location_id),
            )
            batch_row = cur.fetchone()
            if batch_row:
                batch_id = batch_row["id"]
                new_balance = to_money(batch_row["quantity_on_hand_decimal"]) + qty
                c.execute(
                    """
                    UPDATE inventory_batches
                    SET quantity_on_hand_decimal = ?, unit_cost_decimal = ?, selling_price_decimal = ?,
                        version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?;
                    """,
                    (fmt_money(new_balance), fmt_money(unit_cost), fmt_money(sell_price), batch_id),
                )
            else:
                batch_id = f"batch-{uuid.uuid4().hex[:12]}"
                new_balance = qty
                c.execute(
                    """
                    INSERT INTO inventory_batches (
                        id, organization_id, facility_id, inventory_item_id, location_id,
                        supplier_id, batch_number, manufactured_date, expiry_date,
                        status, quantity_on_hand_decimal, unit_cost_decimal, selling_price_decimal,
                        vendor_compliance_note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'AVAILABLE', ?, ?, ?, ?);
                    """,
                    (
                        batch_id,
                        organization_id,
                        facility_id,
                        inventory_item_id,
                        location_id,
                        payload.get("supplier_id"),
                        batch_number,
                        payload.get("manufactured_date"),
                        expiry_date,
                        fmt_money(new_balance),
                        fmt_money(unit_cost),
                        fmt_money(sell_price),
                        payload.get("vendor_compliance_note"),
                    ),
                )

            cur.execute("SELECT COUNT(*) AS cnt FROM inventory_movements WHERE organization_id = ?;", (organization_id,))
            m_seq = int(cur.fetchone()["cnt"]) + 1
            movement_number = f"MOV-2026-{m_seq:05d}"
            movement_id = f"imov-{uuid.uuid4().hex[:12]}"

            c.execute(
                """
                INSERT INTO inventory_movements (
                    id, organization_id, facility_id, movement_number, movement_type,
                    inventory_item_id, batch_id, from_location_id, to_location_id,
                    quantity_delta_decimal, balance_after_decimal, unit, unit_cost_decimal,
                    source_reference_type, source_reference_id, reason, actor_id, idempotency_key
                ) VALUES (?, ?, ?, ?, 'STOCK_RECEIPT', ?, ?, NULL, ?, ?, ?, ?, ?, 'PURCHASE_RECEIPT', ?, ?, ?, ?);
                """,
                (
                    movement_id,
                    organization_id,
                    facility_id,
                    movement_number,
                    inventory_item_id,
                    batch_id,
                    location_id,
                    fmt_money(qty),
                    fmt_money(new_balance),
                    item["unit"],
                    fmt_money(unit_cost),
                    payload.get("purchase_order_id") or payload.get("invoice_reference"),
                    payload.get("reason") or f"Stock receipt for batch {batch_number}",
                    actor_id,
                    idempotency_key,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="INVENTORY_STOCK_RECEIVED",
                target_entity_type="INVENTORY_BATCH",
                target_entity_id=batch_id,
                details={
                    "batch_number": batch_number,
                    "quantity_received": fmt_money(qty),
                    "balance_after": fmt_money(new_balance),
                },
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM inventory_batches WHERE id = ?;", (batch_id,))
            batch_out = dict(cur.fetchone())
            cur.execute("SELECT * FROM inventory_movements WHERE id = ?;", (movement_id,))
            mov_out = dict(cur.fetchone())
            return {"batch": batch_out, "movement": mov_out, "idempotent_replay": False}
        finally:
            if should_close:
                c.close()

    def record_inventory_movement(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Record an auditable stock movement (adjustment, quarantine, expiry write-off, or reversal)."""
        c, should_close = self._get_conn(conn)
        try:
            settings = self._assert_inventory_enabled(organization_id, facility_id, c)
            cur = c.cursor()
            idempotency_key = payload.get("idempotency_key")
            if idempotency_key:
                cur.execute(
                    "SELECT * FROM inventory_movements WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                idem = cur.fetchone()
                if idem:
                    return dict(idem)

            batch_id = payload.get("batch_id")
            movement_type = str(payload.get("movement_type", "")).upper()
            reason = payload.get("reason")
            if not batch_id or not movement_type:
                raise ValidationError("batch_id and movement_type are required.")
            if not reason or len(reason.strip()) < 3:
                raise ValidationError("A documented reason is required for all inventory movements and adjustments.")

            allowed_types = {
                "ADJUSTMENT_GAIN",
                "ADJUSTMENT_LOSS",
                "QUARANTINE_HOLD",
                "EXPIRY_WRITEOFF",
                "RETURN_FROM_PATIENT",
                "REVERSAL",
            }
            if movement_type not in allowed_types:
                raise ValidationError(f"Unsupported movement_type '{movement_type}'. Allowed: {list(allowed_types)}")

            cur.execute(
                """
                SELECT b.*, i.unit AS item_unit
                FROM inventory_batches b
                JOIN inventory_items i ON b.inventory_item_id = i.id
                WHERE b.id = ? AND b.organization_id = ? AND b.facility_id = ?;
                """,
                (batch_id, organization_id, facility_id),
            )
            batch = cur.fetchone()
            if not batch:
                raise NotFoundError(f"Batch '{batch_id}' not found.")

            current_qty = to_money(batch["quantity_on_hand_decimal"])
            reversal_of_id = payload.get("reversal_of_movement_id")

            if movement_type == "REVERSAL":
                if not reversal_of_id:
                    raise ValidationError("reversal_of_movement_id is required when movement_type is REVERSAL.")
                cur.execute(
                    "SELECT * FROM inventory_movements WHERE id = ? AND organization_id = ?;",
                    (reversal_of_id, organization_id),
                )
                orig_mov = cur.fetchone()
                if not orig_mov:
                    raise NotFoundError(f"Original movement '{reversal_of_id}' not found.")
                delta = -to_money(orig_mov["quantity_delta_decimal"])
            elif movement_type == "QUARANTINE_HOLD":
                # Quarantine locks the batch status without destroying quantity history
                delta = Decimal("0.00")
            else:
                raw_qty = to_money(payload.get("quantity_decimal", payload.get("quantity")), "quantity")
                if raw_qty <= Decimal("0.00"):
                    raise ValidationError("Movement quantity must be greater than 0.00.")
                if movement_type in ("ADJUSTMENT_LOSS", "EXPIRY_WRITEOFF"):
                    delta = -raw_qty
                else:
                    delta = raw_qty

            new_balance = current_qty + delta
            if new_balance < Decimal("0.00"):
                allow_neg = bool(settings.get("allow_negative_stock_override")) and bool(
                    payload.get("override_negative_stock")
                )
                if not allow_neg:
                    raise ConflictError(
                        f"Insufficient batch stock ({fmt_money(current_qty)}) for deduction ({fmt_money(abs(delta))}). Negative stock is blocked.",
                        details={"current_qty": fmt_money(current_qty), "requested_deduction": fmt_money(abs(delta))},
                    )

            new_batch_status = batch["status"]
            quarantine_reason = batch["quarantine_reason"]
            if movement_type == "QUARANTINE_HOLD":
                new_batch_status = "QUARANTINED"
                quarantine_reason = reason.strip()
            elif movement_type == "EXPIRY_WRITEOFF" and new_balance == Decimal("0.00"):
                new_batch_status = "EXPIRED_HOLD"

            # Optimistic concurrency update on batch
            upd = c.execute(
                """
                UPDATE inventory_batches
                SET quantity_on_hand_decimal = ?, status = ?, quarantine_reason = ?,
                    version = version + 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND version = ?;
                """,
                (fmt_money(new_balance), new_batch_status, quarantine_reason, batch_id, batch["version"]),
            )
            if upd.rowcount == 0:
                raise ConflictError("Concurrent batch modification detected. Please retry the inventory movement.")

            cur.execute("SELECT COUNT(*) AS cnt FROM inventory_movements WHERE organization_id = ?;", (organization_id,))
            m_seq = int(cur.fetchone()["cnt"]) + 1
            movement_number = f"MOV-2026-{m_seq:05d}"
            movement_id = f"imov-{uuid.uuid4().hex[:12]}"

            c.execute(
                """
                INSERT INTO inventory_movements (
                    id, organization_id, facility_id, movement_number, movement_type,
                    inventory_item_id, batch_id, from_location_id, to_location_id,
                    quantity_delta_decimal, balance_after_decimal, unit, unit_cost_decimal,
                    source_reference_type, source_reference_id, reversal_of_movement_id,
                    reason, authorized_by, actor_id, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    movement_id,
                    organization_id,
                    facility_id,
                    movement_number,
                    movement_type,
                    batch["inventory_item_id"],
                    batch_id,
                    batch["location_id"],
                    batch["location_id"],
                    fmt_money(delta),
                    fmt_money(new_balance),
                    batch["item_unit"],
                    batch["unit_cost_decimal"],
                    "MOVEMENT_REVERSAL" if movement_type == "REVERSAL" else "MANUAL_ADJUSTMENT",
                    reversal_of_id or payload.get("source_reference_id"),
                    reversal_of_id,
                    reason.strip(),
                    actor_id,
                    actor_id,
                    idempotency_key,
                ),
            )
            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type=f"INVENTORY_{movement_type}",
                target_entity_type="INVENTORY_MOVEMENT",
                target_entity_id=movement_id,
                details={
                    "batch_id": batch_id,
                    "delta": fmt_money(delta),
                    "balance_after": fmt_money(new_balance),
                    "reason": reason.strip(),
                },
            )
            if should_close:
                c.commit()
            cur.execute("SELECT * FROM inventory_movements WHERE id = ?;", (movement_id,))
            return dict(cur.fetchone())
        finally:
            if should_close:
                c.close()

    def list_batches(
        self,
        organization_id: str,
        facility_id: str,
        inventory_item_id: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> List[Dict[str, Any]]:
        """List batches ordered by First-Expiry-First-Out (FEFO) with expiry and quarantine flags."""
        c, should_close = self._get_conn(conn)
        try:
            settings = self._assert_inventory_enabled(organization_id, facility_id, c)
            warn_days = int(settings.get("near_expiry_warning_days", 90))
            today_str = date.today().isoformat()
            warn_cutoff = (date.today() + timedelta(days=warn_days)).isoformat()

            clauses = ["b.organization_id = ?", "b.facility_id = ?"]
            params: List[Any] = [organization_id, facility_id]
            if inventory_item_id:
                clauses.append("b.inventory_item_id = ?")
                params.append(inventory_item_id)

            cur = c.cursor()
            cur.execute(
                f"""
                SELECT b.*, i.name AS item_name, i.sku AS item_sku, i.unit AS item_unit,
                       l.name AS location_name, l.is_dispensable AS location_dispensable
                FROM inventory_batches b
                JOIN inventory_items i ON b.inventory_item_id = i.id
                JOIN inventory_locations l ON b.location_id = l.id
                WHERE {' AND '.join(clauses)}
                ORDER BY b.expiry_date ASC, b.created_at ASC;
                """,
                tuple(params),
            )
            batches = []
            for r in cur.fetchall():
                b = dict(r)
                qty = to_money(b["quantity_on_hand_decimal"])
                is_expired = b["expiry_date"] < today_str
                is_near_expiry = (not is_expired) and (b["expiry_date"] <= warn_cutoff)
                is_quarantined = b["status"] in ("QUARANTINED", "RECALLED", "EXPIRED_HOLD") or not b["location_dispensable"]
                b["is_expired"] = is_expired
                b["is_near_expiry"] = is_near_expiry
                b["is_quarantined"] = is_quarantined
                b["is_dispensable"] = (not is_expired) and (not is_quarantined) and (qty > Decimal("0.00"))
                batches.append(b)
            return batches
        finally:
            if should_close:
                c.close()

    def get_stock_summary(
        self,
        organization_id: str,
        facility_id: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Compute stock-on-hand, FEFO dispensable balance, low-stock alerts, and expiry risk."""
        c, should_close = self._get_conn(conn)
        try:
            items = self.list_inventory_items(organization_id, facility_id, conn=c)
            batches = self.list_batches(organization_id, facility_id, conn=c)

            by_item: Dict[str, List[Dict[str, Any]]] = {}
            for b in batches:
                by_item.setdefault(b["inventory_item_id"], []).append(b)

            summary_items = []
            low_stock_count = 0
            expired_batch_count = sum(1 for b in batches if b["is_expired"] and to_money(b["quantity_on_hand_decimal"]) > Decimal("0.00"))
            near_expiry_batch_count = sum(1 for b in batches if b["is_near_expiry"] and to_money(b["quantity_on_hand_decimal"]) > Decimal("0.00"))

            for it in items:
                item_batches = by_item.get(it["id"], [])
                total_on_hand = sum((to_money(b["quantity_on_hand_decimal"]) for b in item_batches), Decimal("0.00"))
                dispensable_qty = sum(
                    (to_money(b["quantity_on_hand_decimal"]) for b in item_batches if b["is_dispensable"]),
                    Decimal("0.00"),
                )
                reorder_thresh = to_money(it["reorder_threshold_decimal"])
                is_low_stock = dispensable_qty <= reorder_thresh
                if is_low_stock:
                    low_stock_count += 1
                fefo_candidate = next((b for b in item_batches if b["is_dispensable"]), None)

                summary_items.append(
                    {
                        "inventory_item_id": it["id"],
                        "sku": it["sku"],
                        "name": it["name"],
                        "formulation_id": it["formulation_id"],
                        "dosage_form": it["dosage_form"],
                        "unit": it["unit"],
                        "total_on_hand_decimal": fmt_money(total_on_hand),
                        "dispensable_quantity_decimal": fmt_money(dispensable_qty),
                        "reorder_threshold_decimal": fmt_money(reorder_thresh),
                        "is_low_stock": is_low_stock,
                        "fefo_suggested_batch_id": fefo_candidate["id"] if fefo_candidate else None,
                        "fefo_suggested_batch_number": fefo_candidate["batch_number"] if fefo_candidate else None,
                        "fefo_suggested_expiry": fefo_candidate["expiry_date"] if fefo_candidate else None,
                    }
                )

            return {
                "data_as_of": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "facility_id": facility_id,
                "compliance_disclaimer": "Inventory availability does not imply clinical appropriateness or replace a signed prescription.",
                "low_stock_item_count": low_stock_count,
                "expired_batch_count": expired_batch_count,
                "near_expiry_batch_count": near_expiry_batch_count,
                "items": summary_items,
            }
        finally:
            if should_close:
                c.close()

    def create_stocktake(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Record a stocktake session and automatically post ledger adjustments for any counted variances."""
        c, should_close = self._get_conn(conn)
        try:
            self._assert_inventory_enabled(organization_id, facility_id, c)
            main_loc_id, _ = self._ensure_default_locations(organization_id, facility_id, c)
            location_id = payload.get("location_id") or main_loc_id
            lines = payload.get("lines", [])
            if not lines:
                raise ValidationError("Stocktake session requires at least one counted batch line.")

            cur = c.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM stocktake_sessions WHERE organization_id = ?;", (organization_id,))
            s_seq = int(cur.fetchone()["cnt"]) + 1
            session_number = f"STK-2026-{s_seq:05d}"
            stocktake_id = f"stk-{uuid.uuid4().hex[:12]}"

            c.execute(
                """
                INSERT INTO stocktake_sessions (
                    id, organization_id, facility_id, session_number, location_id,
                    status, notes, created_by, approved_by, completed_at
                ) VALUES (?, ?, ?, ?, ?, 'COMPLETED', ?, ?, ?, CURRENT_TIMESTAMP);
                """,
                (stocktake_id, organization_id, facility_id, session_number, location_id, payload.get("notes"), actor_id, actor_id),
            )

            recorded_lines = []
            for ln in lines:
                batch_id = ln.get("batch_id")
                counted_qty = to_money(ln.get("counted_qty_decimal", ln.get("counted_qty")), "counted_qty")
                cur.execute(
                    "SELECT * FROM inventory_batches WHERE id = ? AND organization_id = ?;",
                    (batch_id, organization_id),
                )
                b = cur.fetchone()
                if not b:
                    raise NotFoundError(f"Batch '{batch_id}' not found.")

                expected_qty = to_money(b["quantity_on_hand_decimal"])
                variance = counted_qty - expected_qty
                adj_mov_id = None

                if variance != Decimal("0.00"):
                    mov_type = "ADJUSTMENT_GAIN" if variance > Decimal("0.00") else "ADJUSTMENT_LOSS"
                    mov = self.record_inventory_movement(
                        organization_id=organization_id,
                        facility_id=facility_id,
                        actor_id=actor_id,
                        payload={
                            "batch_id": batch_id,
                            "movement_type": mov_type,
                            "quantity_decimal": fmt_money(abs(variance)),
                            "reason": ln.get("reason") or f"Stocktake {session_number} reconciliation",
                            "source_reference_id": stocktake_id,
                        },
                        conn=c,
                    )
                    adj_mov_id = mov["id"]

                line_id = f"stkl-{uuid.uuid4().hex[:10]}"
                c.execute(
                    """
                    INSERT INTO stocktake_lines (
                        id, stocktake_id, batch_id, inventory_item_id,
                        expected_qty_decimal, counted_qty_decimal, variance_qty_decimal,
                        adjustment_movement_id, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        line_id,
                        stocktake_id,
                        batch_id,
                        b["inventory_item_id"],
                        fmt_money(expected_qty),
                        fmt_money(counted_qty),
                        fmt_money(variance),
                        adj_mov_id,
                        ln.get("reason"),
                    ),
                )
                recorded_lines.append(
                    {
                        "line_id": line_id,
                        "batch_id": batch_id,
                        "expected_qty_decimal": fmt_money(expected_qty),
                        "counted_qty_decimal": fmt_money(counted_qty),
                        "variance_qty_decimal": fmt_money(variance),
                        "adjustment_movement_id": adj_mov_id,
                    }
                )

            if should_close:
                c.commit()
            return {
                "id": stocktake_id,
                "session_number": session_number,
                "status": "COMPLETED",
                "lines": recorded_lines,
            }
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 6. PRESCRIPTION DISPENSING WORKFLOW (STRICTLY LINKED TO SIGNED RX)
    # =========================================================================

    def dispense_prescription(
        self,
        organization_id: str,
        facility_id: str,
        actor_id: str,
        payload: Dict[str, Any],
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Dispense medication against an authorized, finalized SIGNED prescription without mutating the prescription."""
        c, should_close = self._get_conn(conn)
        try:
            self._assert_inventory_enabled(organization_id, facility_id, c)
            cur = c.cursor()

            idempotency_key = payload.get("idempotency_key")
            if idempotency_key:
                cur.execute(
                    "SELECT id FROM dispense_records WHERE idempotency_key = ? AND organization_id = ?;",
                    (idempotency_key, organization_id),
                )
                idem = cur.fetchone()
                if idem:
                    res = self.get_dispense_record(organization_id, facility_id, idem["id"], conn=c)
                    res["idempotent_replay"] = True
                    return res

            prescription_id = payload.get("prescription_id")
            patient_id = payload.get("patient_id")
            items_to_dispense = payload.get("items", [])

            if not prescription_id or not patient_id:
                raise ValidationError("prescription_id and patient_id are required for dispensing.")
            if not items_to_dispense or not isinstance(items_to_dispense, list):
                raise ValidationError("At least one dispense line item is required.")

            # 1. Verify prescription exists, matches patient_id, and is SIGNED
            cur.execute(
                "SELECT * FROM prescriptions WHERE id = ? AND organization_id = ?;",
                (prescription_id, organization_id),
            )
            rx = cur.fetchone()
            if not rx:
                raise NotFoundError(f"Prescription '{prescription_id}' not found.")

            if rx["patient_id"] != patient_id:
                raise ValidationError(
                    "Patient ID does not match the patient on the specified prescription.",
                    details={"code": "PATIENT_PRESCRIPTION_MISMATCH"},
                )

            if rx["status"] != "SIGNED" or not rx["signed_by"] or not rx["signature_hash"]:
                raise ConflictError(
                    f"Cannot dispense prescription in status '{rx['status']}'. Only clinician-SIGNED prescriptions may be dispensed.",
                    details={"code": "UNSIGNED_PRESCRIPTION_CANNOT_DISPENSE", "prescription_status": rx["status"]},
                )

            cur.execute("SELECT COUNT(*) AS cnt FROM dispense_records WHERE organization_id = ?;", (organization_id,))
            d_seq = int(cur.fetchone()["cnt"]) + 1
            dispense_number = f"DSP-2026-{d_seq:05d}"
            dispense_id = f"disp-{uuid.uuid4().hex[:12]}"
            today_str = date.today().isoformat()

            prepared_dispense_lines = []
            labels = []
            any_partial = False

            for idx, dl in enumerate(items_to_dispense):
                batch_id = dl.get("batch_id")
                disp_qty = to_money(dl.get("dispensed_qty_decimal", dl.get("quantity")), "dispensed_qty")
                is_substituted = bool(dl.get("is_substituted", False))
                substitution_reason = dl.get("substitution_reason")
                substitution_approved_by = dl.get("substitution_approved_by")
                line_status = dl.get("line_status", "DISPENSED")

                if is_substituted:
                    if not substitution_reason or not substitution_approved_by:
                        raise ValidationError(
                            "Automatic substitution is prohibited. Substitution requires substitution_reason and clinician/pharmacist substitution_approved_by.",
                            details={"code": "UNAUTHORIZED_SUBSTITUTION_PROHIBITED"},
                        )
                    # Verify approver is an active practitioner or clinic/org admin
                    cur.execute(
                        """
                        SELECT r.code AS role_code
                        FROM user_organization_memberships uom
                        JOIN roles r ON uom.role_id = r.id
                        WHERE uom.user_id = ? AND uom.organization_id = ? AND uom.is_active = 1;
                        """,
                        (substitution_approved_by, organization_id),
                    )
                    approver_roles = {r["role_code"] for r in cur.fetchall()}
                    if not approver_roles.intersection({"PRACTITIONER", "CLINIC_ADMIN", "ORG_ADMIN"}):
                        raise AuthorizationError(
                            "Substitution must be approved by an authorized clinician/practitioner."
                        )
                    line_status = "SUBSTITUTED_APPROVED"

                if line_status in ("UNAVAILABLE", "REFUSED"):
                    any_partial = True
                    prepared_dispense_lines.append(
                        {
                            "id": f"dspl-{uuid.uuid4().hex[:10]}",
                            "prescription_item_id": dl.get("prescription_item_id"),
                            "inventory_item_id": dl.get("inventory_item_id"),
                            "batch_id": None,
                            "movement_id": None,
                            "line_status": line_status,
                            "prescribed_item_name": dl.get("prescribed_item_name", "Prescribed Item"),
                            "prescribed_dose_instructions": dl.get("prescribed_dose_instructions", ""),
                            "dispensed_qty_decimal": "0.00",
                            "unit": dl.get("unit", "g"),
                            "is_substituted": 0,
                            "substitution_reason": dl.get("reason"),
                            "substitution_approved_by": None,
                            "label_text": f"NOT DISPENSED ({line_status})",
                        }
                    )
                    continue

                if not batch_id:
                    raise ValidationError("batch_id is required for each dispensed medication line.")
                if disp_qty <= Decimal("0.00"):
                    raise ValidationError("dispensed_qty_decimal must be greater than 0.00.")

                cur.execute(
                    """
                    SELECT b.*, i.name AS item_name, i.unit AS item_unit, l.is_dispensable AS loc_dispensable
                    FROM inventory_batches b
                    JOIN inventory_items i ON b.inventory_item_id = i.id
                    JOIN inventory_locations l ON b.location_id = l.id
                    WHERE b.id = ? AND b.organization_id = ? AND b.facility_id = ?;
                    """,
                    (batch_id, organization_id, facility_id),
                )
                batch = cur.fetchone()
                if not batch:
                    raise NotFoundError(f"Inventory batch '{batch_id}' not found.")

                if (
                    batch["status"] != "AVAILABLE"
                    or not batch["loc_dispensable"]
                    or batch["expiry_date"] < today_str
                ):
                    raise ConflictError(
                        f"Batch '{batch['batch_number']}' is expired, quarantined, or in a non-dispensable location and cannot be dispensed.",
                        details={
                            "code": "BATCH_EXPIRED_OR_QUARANTINED",
                            "batch_id": batch_id,
                            "batch_status": batch["status"],
                            "expiry_date": batch["expiry_date"],
                        },
                    )

                on_hand = to_money(batch["quantity_on_hand_decimal"])
                if disp_qty > on_hand:
                    raise ConflictError(
                        f"Insufficient stock in batch '{batch['batch_number']}' (available: {fmt_money(on_hand)}, requested: {fmt_money(disp_qty)}).",
                        details={"code": "INSUFFICIENT_BATCH_STOCK"},
                    )

                new_balance = on_hand - disp_qty
                upd = c.execute(
                    """
                    UPDATE inventory_batches
                    SET quantity_on_hand_decimal = ?, version = version + 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND version = ?;
                    """,
                    (fmt_money(new_balance), batch_id, batch["version"]),
                )
                if upd.rowcount == 0:
                    raise ConflictError("Concurrent stock lock conflict on batch during dispensing. Please retry.")

                cur.execute(
                    "SELECT COUNT(*) AS cnt FROM inventory_movements WHERE organization_id = ?;",
                    (organization_id,),
                )
                m_seq = int(cur.fetchone()["cnt"]) + 1
                mov_id = f"imov-{uuid.uuid4().hex[:12]}"
                mov_num = f"MOV-2026-{m_seq:05d}"

                c.execute(
                    """
                    INSERT INTO inventory_movements (
                        id, organization_id, facility_id, movement_number, movement_type,
                        inventory_item_id, batch_id, from_location_id, to_location_id,
                        quantity_delta_decimal, balance_after_decimal, unit, unit_cost_decimal,
                        source_reference_type, source_reference_id, reason, actor_id
                    ) VALUES (?, ?, ?, ?, 'DISPENSE_ISSUE', ?, ?, ?, NULL, ?, ?, ?, ?, 'DISPENSE_RECORD', ?, ?, ?);
                    """,
                    (
                        mov_id,
                        organization_id,
                        facility_id,
                        mov_num,
                        batch["inventory_item_id"],
                        batch_id,
                        batch["location_id"],
                        fmt_money(-disp_qty),
                        fmt_money(new_balance),
                        batch["item_unit"],
                        batch["unit_cost_decimal"],
                        dispense_id,
                        f"Dispensed against signed prescription {rx['prescription_number']}",
                        actor_id,
                    ),
                )

                if line_status == "PARTIAL_FILL":
                    any_partial = True

                label_text = (
                    f"{batch['item_name']} | Batch: {batch['batch_number']} | Exp: {batch['expiry_date']} | "
                    f"Qty: {fmt_money(disp_qty)} {batch['item_unit']} | {dl.get('prescribed_dose_instructions', 'As directed by Hakeem')}"
                )
                labels.append(label_text)
                prepared_dispense_lines.append(
                    {
                        "id": f"dspl-{uuid.uuid4().hex[:10]}",
                        "prescription_item_id": dl.get("prescription_item_id"),
                        "inventory_item_id": batch["inventory_item_id"],
                        "batch_id": batch_id,
                        "movement_id": mov_id,
                        "line_status": line_status,
                        "prescribed_item_name": dl.get("prescribed_item_name") or batch["item_name"],
                        "prescribed_dose_instructions": dl.get("prescribed_dose_instructions") or "As directed",
                        "dispensed_qty_decimal": fmt_money(disp_qty),
                        "unit": batch["item_unit"],
                        "is_substituted": 1 if is_substituted else 0,
                        "substitution_reason": substitution_reason,
                        "substitution_approved_by": substitution_approved_by,
                        "label_text": label_text,
                    }
                )

            overall_status = "PARTIALLY_DISPENSED" if any_partial else "DISPENSED"
            c.execute(
                """
                INSERT INTO dispense_records (
                    id, organization_id, facility_id, dispense_number,
                    prescription_id, prescription_version, patient_id, encounter_id,
                    prescriber_id, dispenser_id, status, verification_notes,
                    label_payload_json, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    dispense_id,
                    organization_id,
                    facility_id,
                    dispense_number,
                    prescription_id,
                    rx["version_number"],
                    patient_id,
                    rx["encounter_id"],
                    rx["signed_by"],
                    actor_id,
                    overall_status,
                    payload.get("verification_notes"),
                    json.dumps({"prescription_number": rx["prescription_number"], "labels": labels}),
                    idempotency_key,
                ),
            )

            for pl in prepared_dispense_lines:
                c.execute(
                    """
                    INSERT INTO dispense_lines (
                        id, dispense_id, prescription_item_id, inventory_item_id,
                        batch_id, movement_id, line_status, prescribed_item_name,
                        prescribed_dose_instructions, dispensed_qty_decimal, unit,
                        is_substituted, substitution_reason, substitution_approved_by, label_text
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        pl["id"],
                        dispense_id,
                        pl["prescription_item_id"],
                        pl["inventory_item_id"],
                        pl["batch_id"],
                        pl["movement_id"],
                        pl["line_status"],
                        pl["prescribed_item_name"],
                        pl["prescribed_dose_instructions"],
                        pl["dispensed_qty_decimal"],
                        pl["unit"],
                        pl["is_substituted"],
                        pl["substitution_reason"],
                        pl["substitution_approved_by"],
                        pl["label_text"],
                    ),
                )

            log_audit_event(
                c,
                organization_id=organization_id,
                facility_id=facility_id,
                actor_id=actor_id,
                action_type="PRESCRIPTION_DISPENSED",
                target_entity_type="DISPENSE_RECORD",
                target_entity_id=dispense_id,
                details={
                    "dispense_number": dispense_number,
                    "prescription_id": prescription_id,
                    "status": overall_status,
                },
            )
            if should_close:
                c.commit()
            res = self.get_dispense_record(organization_id, facility_id, dispense_id, conn=c)
            res["idempotent_replay"] = False
            return res
        finally:
            if should_close:
                c.close()

    def get_dispense_record(
        self,
        organization_id: str,
        facility_id: str,
        dispense_id: str,
        user_ctx: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                """
                SELECT d.*, p.display_name AS patient_name, p.mrn AS patient_mrn,
                       rx.prescription_number, rx.signature_hash AS prescription_signature_hash
                FROM dispense_records d
                JOIN patients p ON d.patient_id = p.id
                JOIN prescriptions rx ON d.prescription_id = rx.id
                WHERE d.id = ? AND d.organization_id = ?;
                """,
                (dispense_id, organization_id),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(f"Dispense record '{dispense_id}' not found.")
            rec = dict(row)
            rec["label_payload"] = json.loads(rec.get("label_payload_json") or "{}")
            cur.execute("SELECT * FROM dispense_lines WHERE dispense_id = ?;", (dispense_id,))
            rec["lines"] = [dict(r) for r in cur.fetchall()]
            return rec
        finally:
            if should_close:
                c.close()

    # =========================================================================
    # 7. TODAY DASHBOARD & OPERATIONAL REPORTS
    # =========================================================================

    def get_today_dashboard(
        self,
        organization_id: str,
        facility_id: str,
        user_ctx: Dict[str, Any],
        target_date: Optional[str] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Return live, actionable Today Dashboard metrics backed by authorized database records."""
        c, should_close = self._get_conn(conn)
        try:
            t_date = target_date or date.today().isoformat()
            settings = self.get_facility_settings(organization_id, facility_id, conn=c)
            cur = c.cursor()

            # 1. Today's appointments
            appts = self.list_appointments(
                organization_id, facility_id, filters={"date": t_date}, user_ctx=user_ctx, conn=c
            )
            # 2. Today's queue
            queue_data = self.list_queue(organization_id, facility_id, filters={"queue_date": t_date}, conn=c)
            tokens = queue_data["tokens"]

            # 3. Payment tasks awaiting action (DRAFT or FINALIZED/PARTIALLY_PAID with balance > 0)
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM invoices
                WHERE organization_id = ? AND facility_id = ?
                  AND status IN ('DRAFT', 'FINALIZED', 'PARTIALLY_PAID');
                """,
                (organization_id, facility_id),
            )
            payment_tasks_count = int(cur.fetchone()["cnt"])

            # 4. Follow-ups due
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM follow_up_tasks
                WHERE organization_id = ? AND facility_id = ?
                  AND status IN ('planned', 'due', 'in_progress', 'escalated');
                """,
                (organization_id, facility_id),
            )
            followups_due_count = int(cur.fetchone()["cnt"])

            # 5. Inventory warnings (if enabled)
            inventory_alerts = {"enabled": bool(settings["inventory_enabled"]), "low_stock_count": 0, "near_expiry_count": 0, "expired_count": 0}
            if settings["inventory_enabled"]:
                stk = self.get_stock_summary(organization_id, facility_id, conn=c)
                inventory_alerts["low_stock_count"] = stk["low_stock_item_count"]
                inventory_alerts["near_expiry_count"] = stk["near_expiry_batch_count"]
                inventory_alerts["expired_count"] = stk["expired_batch_count"]

            # 6. Operational errors needing attention
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM payments
                WHERE organization_id = ? AND facility_id = ? AND status IN ('FAILED', 'UNKNOWN');
                """,
                (organization_id, facility_id),
            )
            failed_payments = int(cur.fetchone()["cnt"])
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM outbound_messages
                WHERE organization_id = ? AND facility_id = ? AND status = 'DEAD_LETTER';
                """,
                (organization_id, facility_id),
            )
            dead_letter_msgs = int(cur.fetchone()["cnt"])

            # 7. Unsigned items for practitioner
            unsigned_rx_count = 0
            if _has_clinical_read_access(user_ctx):
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt FROM prescriptions
                    WHERE organization_id = ? AND facility_id = ? AND status IN ('DRAFT', 'VALIDATION_REQUIRED');
                    """,
                    (organization_id, facility_id),
                )
                unsigned_rx_count = int(cur.fetchone()["cnt"])

            return {
                "data_as_of": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "date": t_date,
                "facility_id": facility_id,
                "role_view": user_ctx.get("roles", ["USER"])[0],
                "metrics": {
                    "todays_appointments_count": len(appts),
                    "walk_ins_waiting_count": sum(
                        1 for t in tokens if t["visit_type"] == "WALK_IN" and t["status"] in ("checked_in", "waiting")
                    ),
                    "total_waiting_count": queue_data["waiting_count"],
                    "currently_in_consultation_count": queue_data["in_consultation_count"],
                    "completed_visits_count": queue_data["completed_count"],
                    "payment_tasks_awaiting_action_count": payment_tasks_count,
                    "follow_ups_due_count": followups_due_count,
                    "unsigned_prescriptions_count": unsigned_rx_count,
                    "operational_errors_count": failed_payments + dead_letter_msgs,
                },
                "inventory_warnings": inventory_alerts,
                "active_queue_tokens": tokens[:15],
                "upcoming_appointments": appts[:15],
            }
        finally:
            if should_close:
                c.close()

    def get_operational_reports(
        self,
        organization_id: str,
        facility_id: str,
        filters: Optional[Dict[str, Any]] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive clinic operational report with exact metric definitions and zero clinical efficacy claims."""
        c, should_close = self._get_conn(conn)
        try:
            cur = c.cursor()
            cur.execute(
                "SELECT status, COUNT(*) AS cnt FROM appointments WHERE organization_id = ? AND facility_id = ? GROUP BY status;",
                (organization_id, facility_id),
            )
            appt_by_status = {r["status"]: int(r["cnt"]) for r in cur.fetchall()}
            total_appts = sum(appt_by_status.values())
            no_show_count = appt_by_status.get("no_show", 0)
            cancelled_count = appt_by_status.get("cancelled", 0)

            # Wait time calculation: minutes from arrival_at to consultation_started_at (or called_at)
            cur.execute(
                """
                SELECT arrival_at, called_at, consultation_started_at
                FROM queue_tokens
                WHERE organization_id = ? AND facility_id = ?
                  AND (called_at IS NOT NULL OR consultation_started_at IS NOT NULL);
                """,
                (organization_id, facility_id),
            )
            wait_mins_list = []
            for r in cur.fetchall():
                try:
                    t_arr = datetime.fromisoformat(r["arrival_at"].replace("Z", ""))
                    target_ts = r["consultation_started_at"] or r["called_at"]
                    t_start = datetime.fromisoformat(target_ts.replace("Z", ""))
                    diff_mins = max(0.0, (t_start - t_arr).total_seconds() / 60.0)
                    wait_mins_list.append(diff_mins)
                except Exception:
                    pass

            avg_wait_mins = round(sum(wait_mins_list) / len(wait_mins_list), 2) if wait_mins_list else 0.0

            collections = self.get_collections_report(organization_id, facility_id, conn=c)
            settings = self.get_facility_settings(organization_id, facility_id, conn=c)
            stock_summary = (
                self.get_stock_summary(organization_id, facility_id, conn=c)
                if settings.get("inventory_enabled")
                else {"enabled": False}
            )

            return {
                "data_as_of": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "facility_id": facility_id,
                "metric_definitions": {
                    "waiting_time_minutes": "Elapsed minutes from queue_tokens.arrival_at to consultation_started_at (or called_at).",
                    "net_collections_decimal": "Exact sum of POSTED payment amounts minus COMPLETED payment refunds.",
                    "no_show_rate_pct": "Percentage of total appointments marked 'no_show'.",
                },
                "claims_clinical_efficacy": False,
                "appointments_summary": {
                    "total_appointments": total_appts,
                    "by_status": appt_by_status,
                    "no_show_count": no_show_count,
                    "cancelled_count": cancelled_count,
                    "no_show_rate_pct": round((no_show_count / total_appts) * 100.0, 2) if total_appts else 0.0,
                },
                "queue_and_wait_times": {
                    "measured_tokens_count": len(wait_mins_list),
                    "average_wait_minutes": avg_wait_mins,
                },
                "billing_and_collections": collections,
                "inventory_and_dispensing": stock_summary,
            }
        finally:
            if should_close:
                c.close()

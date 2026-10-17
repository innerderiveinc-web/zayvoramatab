# Prompt 34 Repository & Workflow Discovery Audit
## Clinical Operations Command Center, Capacity Planning & Workflow Bottleneck Intelligence

**Document Type:** Architectural Discovery & Inventory Audit  
**Product:** ZAYVORA MATAB OS — Standalone Clinic & Matab Operating System  
**Phase:** 34 (Prompt 34)  
**Date:** 2026-10-14  

---

## 1. Inventory of Existing Operational Modules

| Area | Implementation Status | Canonical Tables & Services | Canonical States & Timestamps |
| :--- | :--- | :--- | :--- |
| **Organizations & Facilities** | **Production-backed** | `organizations`, `facilities`, `facility_settings` (Migration 001, 010, 011) | Timezone (`Asia/Kolkata`), `working_hours_start`, `working_hours_end`, `working_days_json`, `default_slot_duration_mins`, `buffer_time_mins`. |
| **Practitioner Schedules** | **Production-backed** | `practitioner_schedules`, `practitioner_schedule_blocks` (Migration 010) | Days (`MON`-`SUN`, `ALL`), `start_time`, `end_time`, `break_start_time`, `break_end_time`, `slot_duration_mins`, `slot_capacity`, `room_resource`. Blocks: `LEAVE`, `HOLIDAY`, `ADMINISTRATIVE_BLOCK`. |
| **Appointment Lifecycle** | **Production-backed** | `appointments`, `appointment_events` (Migration 010) | States: `requested`, `booked`, `confirmed`, `arrived`, `in_progress`, `completed`, `cancelled`, `rescheduled`, `no_show`. Timestamps: `start_at`, `end_at`, `created_at`, `updated_at`. Lock: `slot_lock_key`. |
| **Check-in & OPD Queue** | **Production-backed** | `queue_tokens`, `queue_token_events` (Migration 010) | States: `checked_in`, `waiting`, `called`, `in_consultation`, `paused`, `completed`, `cancelled`, `no_show`. Timestamps: `arrival_at`, `called_at`, `consultation_started_at`, `consultation_ended_at`. Lock: `active_patient_queue_lock`. |
| **Consultation & Encounters** | **Production-backed** | `encounters` (Migration 002) | States: `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`. Timestamps: `started_at`, `ended_at`, `created_at`, `updated_at`. |
| **Rooms & Resources** | **Partial** | Column `room_resource` in `appointments` & `practitioner_schedules` | Identified as text resources (e.g., `'Room-1'`, `'Tadbeer-Room'`). Master resource allocation table added in Migration 033 for deterministic room conflict and utilization calculations. |
| **Staff & Roles** | **Production-backed** | `users`, `user_roles`, `security_principals` (Migration 001, 029) | Role assignments (`PRACTITIONER`, `RECEPTIONIST`, `PHARMACIST`, `CARE_COORDINATOR`, `FACILITY_MANAGER`, `ORG_ADMIN`). Gated views without surveillance features. |
| **Billing & Payments** | **Production-backed** | `invoices`, `payments`, `payment_refunds` (Migration 010) | States: Invoices (`DRAFT`, `FINALIZED`, `PARTIALLY_PAID`, `PAID`, `VOIDED`, `REFUNDED`), Payments (`POSTED`, `FAILED`, `UNKNOWN`). Timestamps: `created_at`, `recorded_at`, `finalized_at`. |
| **Pharmacy & Dispensing** | **Production-backed** | `inventory_batches`, `dispense_records` (Migration 010) | States: `DISPENSED`, `VOIDED`. Timestamps: `dispensed_at`. Near-expiry warning window (`90` days). |
| **Follow-up & Continuity** | **Production-backed** | `follow_up_tasks` (Migration 009), `care_continuity_tasks` (Migration 024) | States: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `ESCALATED`, `CANCELLED`. Timestamps: `due_date`, `completed_at`. |
| **Audit & Ledger** | **Production-backed** | `clinical_ledger_events`, `audit_integrity_checkpoints` (Migration 028) | Continuous SHA-256 hash chaining ($H_i = \text{SHA-256}(C_i \parallel H_{i-1})$), immutable event history. |
| **Analytics Metrics** | **Production-backed** | `governed_metric_definitions`, `metric_calculation_runs` (Migration 032) | 12 pre-seeded metrics across all operational domains with versioned formulas and non-causal policies. |
| **Operational Thresholds & Alerts** | **Absent / Partial** | N/A prior to Prompt 34 | Authored in Migration 033 (`command_center_threshold_rules`, `operational_alerts`, `capacity_scenarios`, `operational_action_audit`). |

---

## 2. Canonical State Transitions & Workflow Sequences

### 2.1 The Outpatient Visit Workflow Sequence
1. **Booking:** `appointments(status='booked')` with `slot_lock_key`.
2. **Confirmation:** `appointments(status='confirmed')`.
3. **Arrival & Check-in:** Front-desk triggers `check_in_appointment`.
   - `appointments(status='arrived')`.
   - `queue_tokens` entry created with `status='waiting'`, `arrival_at=CURRENT_TIMESTAMP`, linking `appointment_id`.
4. **Call into Consultation:** Clinician calls patient.
   - `queue_tokens(status='called')`, `called_at=CURRENT_TIMESTAMP`.
5. **Consultation Commenced:**
   - `queue_tokens(status='in_consultation')`, `consultation_started_at=CURRENT_TIMESTAMP`.
   - `encounters(status='IN_PROGRESS')`, `started_at=CURRENT_TIMESTAMP`.
   - `appointments(status='in_progress')`.
6. **Consultation Completed & Locked:**
   - `encounters(status='COMPLETED')`, `ended_at=CURRENT_TIMESTAMP`.
   - `queue_tokens(status='completed')`, `consultation_ended_at=CURRENT_TIMESTAMP`.
   - `appointments(status='completed')`.
7. **Post-Consultation Administrative Handoffs:**
   - Billing: `invoices(status='FINALIZED')` $\to$ `payments(status='POSTED')`.
   - Pharmacy: `dispense_records(status='DISPENSED')`.
   - Follow-up: `care_continuity_tasks(status='PENDING')`.

---

## 3. Strict Non-Causal & Clinical Safety Boundaries

1. **Operations Only:** The Command Center coordinates workflows and resource allocations. It does not evaluate diagnostic accuracy, therapeutic efficacy, or recommend treatments.
2. **No Acuity Generation:** Queue elapsed times and wait durations are strictly operational measurements. They must never be labeled or translated into clinical triage acuity scores.
3. **No Clinician Speed Gamification:** Faster consultations do not mean better clinical care. Clinician performance surveillance and public comparison are strictly prohibited.
4. **Human-in-the-Loop Actions:** Operational bottlenecks do not trigger autonomous appointment cancellations, schedule changes, or automated clinical overrides. Every consequential action requires authenticated human review and confirmation.
5. **Privacy-Preserving Display:** Shared wallboards and public waiting displays expose only opaque tokens (`T-001`, `T-002`) and queue counts, never patient names, contact numbers, or medical reasons.

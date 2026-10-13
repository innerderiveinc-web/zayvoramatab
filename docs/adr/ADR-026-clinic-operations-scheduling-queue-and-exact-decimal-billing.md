# ADR-026: Clinic Operations Scheduling, OPD Queue Governance, and Exact-Decimal Billing

- **Status:** Accepted
- **Date:** 2026-10-13
- **Phase:** Prompt 10 — Clinic Operations OS: Appointments, Queue, Billing, Pharmacy Inventory & Staff Workspace

## Context
A practicing Unani Matab requires a cohesive operational management layer connecting front-desk scheduling, walk-in and appointment token queues, and patient billing without compromising clinical privacy or financial accuracy:
1. Front-desk appointment scheduling must prevent double-booking on practitioner time slots, release slots when appointments are cancelled or marked no-show, and surface conflicts if a practitioner's schedule or leave block overlaps already-booked patients.
2. OPD queue management must prevent accidental duplicate active tokens for the same patient/practitioner on the same day, enforce clinical authorization before assigning urgent clinical priority, and ensure public waiting-room displays expose only token numbers without leaking patient names, MRNs, or clinical diagnoses.
3. Billing and collections must never suffer from binary floating-point rounding drift, must never store raw payment card CVV/PIN data, must never mark failed/unknown payments as paid or issue receipts for them, and must provide idempotent payment capture and auditable refunds/voids.

## Decision
1. **Conflict-Safe Scheduling & Slot Locking (`practitioner_schedules`, `practitioner_schedule_blocks`, `appointments`):**
   - Active appointments hold a unique `slot_lock_key` (`{facility_id}:{practitioner_id}:{start_at}`), enforced via a unique database index.
   - Transitioning an appointment to `cancelled` or `no_show` clears `slot_lock_key`, immediately releasing the slot for re-booking while preserving the appointment and `appointment_events` audit history.
   - Updating practitioner working hours (`upsert_practitioner_schedule`) or creating leave blocks (`create_schedule_block`) deterministically checks for overlapping active appointments and raises `ConflictError` (`SCHEDULE_CONFLICT_WITH_BOOKED_APPOINTMENTS` / `LEAVE_BLOCK_CONFLICTS_WITH_APPOINTMENTS`) unless explicitly acknowledged.
2. **OPD Token Queue & Waiting-Room Privacy (`queue_tokens`, `queue_token_events`):**
   - Active tokens hold a unique `active_patient_queue_lock` (`{facility_id}:{queue_date}:{patient_id}:{practitioner_id}`), blocking accidental duplicate active tokens while allowing re-issuance after completion or cancellation.
   - Assigning `CLINICAL_URGENT` priority requires clinical role authorization (`CLINICAL_PRIORITY_PERMISSION_REQUIRED`) and a documented clinical reason.
   - Checking in an appointment or issuing a walk-in token links or creates an authorized `OPD_VISIT` encounter so the Hakeem can launch the Unified Consultation Workspace directly from the queue.
   - `get_public_queue_display` enforces `privacy_mode: PUBLIC_SAFE_TOKEN_ONLY`, returning only token codes, queue statuses, and room labels with zero patient PII or clinical notes.
3. **Exact-Decimal Billing, Honest Payment States, and Reconciliation (`invoices`, `payments`, `payment_refunds`):**
   - All monetary calculations use Python `Decimal` quantized to `0.01` (`ROUND_HALF_UP`). Raw `float` monetary inputs are rejected with `FLOAT_CURRENCY_NOT_ALLOWED`.
   - Finalizing an invoice freezes an immutable `finalized_snapshot_json`.
   - Payment payloads containing sensitive card security fields (`cvv`, `cvc`, `card_pin`, `full_pan`, `track_data`) are rejected immediately.
   - Payments with `provider_status` in `('FAILED', 'UNKNOWN', 'PENDING')` are persisted for operational visibility without incrementing `paid_decimal`, marking the invoice `PAID`, or issuing a receipt number.
   - Posted payments enforce `idempotency_key` deduplication and update net daily collections alongside permission-gated refunds (`billing:refund_void`).

## Consequences
- Zero double-bookings or silent schedule overwrites.
- Waiting-room displays are safe for public clinic monitors.
- Financial ledgers and daily collection reports are exact to the paisa/cent and resilient against network retries or failed UPI/card attempts.

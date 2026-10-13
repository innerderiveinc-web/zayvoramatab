# ADR-027: FEFO Pharmacy Inventory Ledger and Signed-Prescription Dispensing

- **Status:** Accepted
- **Date:** 2026-10-13
- **Phase:** Prompt 10 — Clinic Operations OS: Appointments, Queue, Billing, Pharmacy Inventory & Staff Workspace

## Context
Unani dispensaries (Dawakhana) manage classical polyherbal formulations (Murakkabat), single drugs (Mufradat), and clinic-prepared batches where potency, shelf life, and batch traceability are critical to patient safety:
1. Stock balances must never be modified via unlogged in-place edits; every stock change must be derived from an immutable movement ledger with batch/lot and expiry tracking.
2. Expired, quarantined, or depleted batches must be blocked from patient dispensing.
3. Dispensary staff must never dispense from an unsigned or draft prescription, must never silently substitute a prescribed formulation without clinician authorization, and dispensing must never mutate the cryptographic signature snapshot of a signed prescription.

## Decision
1. **Append-Only Inventory Movement Ledger & FEFO Batch Selection (`inventory_items`, `inventory_batches`, `inventory_movements`, `stocktake_sessions`):**
   - Every stock receipt, patient dispense, adjustment, quarantine hold, expiry write-off, stocktake variance, and reversal writes an immutable `inventory_movements` record recording `quantity_delta_decimal`, `balance_after_decimal`, `actor_id`, and `reason`.
   - Batch listings default to First-Expiry, First-Out (`ORDER BY expiry_date ASC`) and automatically flag expired and near-expiry batches (`expiry_warning_days`).
   - Negative stock is prevented unless explicitly enabled in `facility_settings.allow_negative_stock`.
2. **Signed-Prescription Dispensing Boundary (`dispense_records`, `dispense_lines`):**
   - `dispense_prescription` verifies that the target prescription exists for the same patient and organization and has `status == 'SIGNED'`. Attempting to dispense a `DRAFT` or `VALIDATION_REQUIRED` prescription fails closed with HTTP 409 (`UNSIGNED_PRESCRIPTION_CANNOT_DISPENSE`).
   - Batches that are `QUARANTINED`, `RECALLED`, `EXPIRED`, or past their `expiry_date` are blocked from dispensing (`BATCH_EXPIRED_OR_QUARANTINED`).
   - Setting `is_substituted: true` without an explicit clinician prescription amendment is rejected (`UNAUTHORIZED_SUBSTITUTION_PROHIBITED`).
   - Dispensing records the prescription's `signature_hash` on `dispense_records.prescription_signature_hash` and leaves the `prescriptions` row and its signed snapshot completely untouched.

## Consequences
- Complete lot-to-patient traceability for recalls, quality audits, and stock reconciliation.
- Strict separation between clinician prescribing authority and dispensary fulfillment.
- Zero tampering with signed prescription records during pharmacy fulfillment.

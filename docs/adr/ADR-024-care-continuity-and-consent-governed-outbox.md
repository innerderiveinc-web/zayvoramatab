# ADR-024: Versioned Follow-up Plans, Operational Task Invariants, and Consent-Governed Transactional Outbox

- **Status:** Accepted
- **Date:** 2026-10-13
- **Phase:** Prompt 09 — Follow-up, Care Continuity, Patient Communication & Outcome Tracking

## Context

In longitudinal Unani and integrative clinical practice, completing an encounter is the beginning of a care continuity loop. Without structured follow-up governance, clinics suffer from:
1. Silent loss of follow-up history when plans are edited in place.
2. Premature closure of missed-follow-up tasks merely because an automated SMS reminder was dispatched or without documented outreach attempts.
3. Double-booked repeat appointments or historical encounter corruption when a repeat visit is checked in.
4. Privacy leaks and regulatory violations when outbound reminders include sensitive diagnoses, medication names, or unconsented messaging during quiet hours.

## Decision

1. **Versioned Follow-up Plans & Auto-Spawned Tasks:**
   - Every `follow_up_plans` record maintains immutable version snapshots in `follow_up_plan_versions` (`v1`, `v2`, etc.) with mandatory amendment reasons.
   - Creating an active follow-up plan automatically spawns an operational `follow_up_tasks` entry with idempotency protection (`idempotency_key`).

2. **Operational Task Invariants & Role-Filtered Work Queue:**
   - Sending an outbound reminder transitions a task to `reminder_sent` (or records a `REMINDER_DISPATCHED` event) and **never** marks a follow-up task `completed`.
   - Transitioning a task to `unable_to_reach` requires at least one logged `contact_attempts` record (`NO_ANSWER`, `BUSY`, `WRONG_NUMBER`, etc.).
   - The Missed Follow-up Work Queue (`GET /api/v1/care-continuity/queue/follow-ups`) enforces role-based minimum-necessary redaction: reception/front-desk roles (`RECEPTIONIST`) receive operational scheduling fields while `clinical_summary_redacted` strips clinical conditions and monitoring instructions that are visible only to `PRACTITIONER` and `CLINIC_ADMIN`.

3. **Repeat-Visit Slot Locking & Non-Mutating Linked Encounters:**
   - `follow_up_appointments` prevents overlapping bookings for the same practitioner and facility (`ConflictError`).
   - Checking in or starting a repeat visit spawns a new linked encounter (`encounter_type = 'FOLLOW_UP'`, linked via `created_encounter_id` and `source_encounter_id`) without mutating the historical baseline encounter.

4. **Consent-Governed Transactional Outbox & Webhook Verification:**
   - Outbound patient communications require an `APPROVED` template version, enforce minimum-necessary privacy (rejecting sensitive keys like `diagnosis`, `medication_name`, `hiv_status` unless explicit `share_clinical_details_in_messages` opt-in is active), defer messages queued during quiet hours (`DEFERRED_QUIET_HOURS`), and re-verify channel consent and opt-out status **at send time** before provider dispatch.
   - Provider webhooks require HMAC-SHA256 signature verification (`X-Matab-Signature`), process `external_event_id` idempotently, transition exhausted retries to `DEAD_LETTER`, and immediately honor inbound `STOP`/`UNSUBSCRIBE` events by revoking channel consent.

## Consequences

- Complete auditability of follow-up schedule changes, outreach attempts, and appointment conversions.
- Zero unauthorized clinical disclosure over SMS/WhatsApp reminders and strict compliance with patient opt-out and quiet-hour preferences.

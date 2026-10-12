# ADR-008: Encounter Lifecycle State Machine and Concurrency Control

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 02)

---

## 1. Context and Problem Statement

Clinical encounters transition between multiple clinic stations (Front Desk -> Nursing / Vitals -> Practitioner Consultation Room -> Dispensary / Pharmacy). If multiple users view or edit the same patient record or encounter concurrently without concurrency control:
- A receptionist updating patient contact details could overwrite a practitioner's simultaneously entered notes (dirty write).
- An encounter could be marked completed or cancelled while a practitioner is actively typing observations.
- Encounter status transitions could bypass sequential clinical workflows.

## 2. Decision

1. **Finite State Machine:**
   - Allowed statuses: `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`.
   - Transitions:
     - `DRAFT` -> `IN_PROGRESS` (practitioner begins consultation)
     - `DRAFT` -> `CANCELLED` (patient leaves before being seen; requires mandatory cancellation reason)
     - `IN_PROGRESS` -> `COMPLETED` (consultation completed; records `ended_at`; locks record)
     - `IN_PROGRESS` -> `CANCELLED` (consultation aborted; requires mandatory cancellation reason)
     - Terminal states (`COMPLETED`, `CANCELLED`) cannot be modified or transitioned.
2. **Optimistic Concurrency Control:**
   - Both `patients` and `encounters` tables maintain an integer `version` column starting at `1`.
   - Any modification (`PATCH /api/v1/patients/{id}`, `PATCH /api/v1/encounters/{id}`) requires the client to supply `version`.
   - The database updates only where `id = ? AND version = ?`, incrementing `version = version + 1`. If the row count affected is 0, the server aborts with HTTP 409 Conflict.
3. **Daily Token Allocation:**
   - Each facility issues sequential daily token numbers starting at 1 each morning (`date(created_at) = date('now')`), ensuring easy patient queuing.

## 3. Consequences

### Positive:
- Elimination of dirty writes across multi-user clinic environments.
- Strict clinical workflow adherence (completed encounters cannot be silently altered).
- Natural queuing supported through facility daily tokens.

### Negative / Trade-offs:
- Frontend clients must track entity versions and gracefully handle 409 conflicts by prompting users to reload and re-apply changes.

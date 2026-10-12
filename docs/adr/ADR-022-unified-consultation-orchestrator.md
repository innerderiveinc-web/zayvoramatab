# ADR-022: Unified Consultation Workspace & Server-Authoritative Workflow Orchestrator

## Status
Accepted (Prompt 08 — Core Clinical Workflow Orchestration)

## Context
Practicing Hakeems and clinical staff in high-throughput outpatient Matabs previously had to hop between fragmented interface screens (demographics, Unani assessment, modern observation entry, formulation searches, prescription builder, and safety checks). This created cognitive fatigue, risk of skipping vital safety checks, and synchronization issues.

Furthermore, client-side workflow transitions cannot be trusted for clinical safety: relying on UI status flags to gate prescription sign-offs risks unsafe prescribing.

## Decision
1. **Single-Canvas Guided Journey:** Provide a unified consultation workspace composed of 7 guided sections:
   - 1. Visit Intake & Triage (`visit`)
   - 2. History & Physical Observations (`history_observations`)
   - 3. Unani Clinical Assessment (`unani_assessment`)
   - 4. Modern Assessment & Differential Lane (`modern_assessment`)
   - 5. Usul-e-Ilaj Care Plan & Nuskha Builder (`plan_nuskha`)
   - 6. Clinical Safety Firewall Review (`safety_review`)
   - 7. Finalize & Follow-up Scheduler (`finalize`)

2. **Server-Authoritative State Machine:** Encounter progression is strictly enforced by the server with explicit state transitions (`scheduled` -> `checked_in` -> `in_consultation` -> `ready_for_signoff` -> `signed` -> `completed`).

3. **Section Completion Tracking:** Each section maintains an explicit lifecycle state (`not_started`, `in_progress`, `complete`, `not_applicable`, `needs_review`). Marking a section `not_applicable` strictly requires a recorded clinical justification.

4. **Server-Side Gate Validation:** Electronic sign-off eligibility is calculated deterministically on the server. The gate verifies clinician identity and PIN configuration, completion of mandatory clinical sections, execution of the safety preflight firewall, absence of unhandled non-overridable blocks, and documented clinical rationales for all acknowledged warnings.

5. **Optimistic Concurrency & Debounced Autosave:** The workspace supports real-time autosave with version checking (`version_number`) to prevent overwrite collisions across multiple browser tabs or concurrent sessions.

## Consequences
- Clinicians experience a coherent clinical journey on a single canvas without screen-hopping.
- Clinical safety cannot be bypassed via UI manipulation or direct API tampering.
- Auditability is maintained at every step of the consultation lifecycle.

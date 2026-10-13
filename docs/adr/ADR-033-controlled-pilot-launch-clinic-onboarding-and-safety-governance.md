# ADR-033: Controlled Pilot Launch, 13-Stage Clinic Onboarding & Clinical Safety Governance

## Status
Accepted

## Context
Following the completion of the 12 core functional phases and the Prompt 13 Production Readiness Audit (which authorized a `CONDITIONAL_GO_FOR_LIMITED_PILOT`), ZAYVORA MATAB OS required a disciplined, repeatable operational framework for onboarding real-world pilot clinics without exposing patients to untested capabilities or unverified external dependencies.

Premature or uncontrolled deployment in clinical environments carries substantial risks:
1. Operational drift where disabled or mock features (e.g., live ABDM cloud sync, unverified carrier SMS) are inadvertently triggered in production.
2. Unprepared clinic staff attempting clinical consultations without completing role-specific synthetic scenario training.
3. High-risk legacy data imports corrupting existing relational records or creating ambiguous duplicate patients.
4. Support queues conflating mundane IT issues (password resets) with urgent clinical safety concerns (potential false-negative contraindications or adverse drug reactions).
5. Absence of pre-defined pause/stop criteria allowing a pilot to run despite emerging safety or data-loss signals.

## Decision
We implemented a comprehensive, server-enforced **Controlled Pilot Launch and Operational Readiness Engine** adhering to the following architectural pillars:
1. **Versioned Pilot Scope Enforcement:**
   - Every pilot runs under an explicit `pilot_programs` and `pilot_scope_versions` contract.
   - Enforced server-side via `enforce_pilot_scope`: any API invocation targeting a disabled module, un-enrolled facility, or unauthorized role fails closed with `ScopeRestrictionError` (HTTP 403 / 412).
2. **Server-Side Eligibility Gate:**
   - Recomputes eligibility on the backend (`evaluate_pilot_eligibility`) by verifying the Prompt 13 audit verdict (`CONDITIONAL_GO_FOR_LIMITED_PILOT`), running SQLite `PRAGMA integrity_check`, checking 0 active P0 stop events, and validating lead approvals. Client-supplied readiness flags are rejected.
3. **13-Stage Facility Onboarding Checklist:**
   - Formal sequential progression: Eligibility Confirmed -> Details Validated -> Staff Configured -> Schedules & Fees -> Templates -> Clinical Content -> Devices & Network -> Migration Decision -> Role Training -> Acceptance Tests -> Site Owner Approval -> Activation -> First-Week Review.
   - Every stage requires persisted evidence notes, blocker details, and accountable sign-off.
4. **Governed Data Migration with DRY-RUN Guarantee:**
   - Two-phase migration engine (`pilot_data_migrations`): `DRY_RUN` performs normalization and duplicate reconciliation with zero database writes; `EXECUTE` commits non-duplicate records and routes ambiguous identity matches to `patient_duplicate_candidates` for human clinician review.
5. **Role-Based Training Curricula & Scenario Acceptance:**
   - Curricula for Practitioners (Hakeem), Receptionists, Dispensers, and Administrators (`training_modules`).
   - Requires synthetic scenario evaluation with minimum 80–90% passing thresholds recorded in `staff_training_enrollments`.
6. **Dedicated Clinical Safety Governance Queue:**
   - Bypasses routine IT support queues: tickets flagged `CLINICAL_SAFETY_INCIDENT` or `SEV_1_CRITICAL` automatically clone to `clinical_safety_incident_queue`.
   - Requires formal clinical governance review and recorded disposition (`RULE_UPDATE_REQUIRED`, `MONOGRAPH_AMENDMENT`, `RETRAINING_ORDERED`, `FORMULATION_QUARANTINE`).
7. **P0 Stop Conditions & Non-Destructive Containment:**
   - Defined pause/stop triggers (`TENANT_EXPOSURE`, `UNAUTHORIZED_SIGNING`, `DATA_CORRUPTION`, `SAFETY_GATE_BYPASS`, `SAVE_FAILURE_LOOP`).
   - Containment deactivates live consultation intakes without altering, corrupting, or deleting historical signed clinical records.
8. **Real Operational Metrics & Periodic Review Packs:**
   - Automated metrics aggregation (training completion %, onboarding progress, open tickets by severity, active stops).
   - Generates formal `pilot_review_packs` with continue/pause/stop recommendations.

## Consequences
- **Positive:**
  - Guarantees that only authorized, trained clinics with verified prerequisites can accept live clinical traffic.
  - Eliminates the risk of untested external gateways running in pilot production.
  - Transparent clinical safety escalation protects patients and preserves pharmacovigilance provenance.
  - Zero loss of signed historical clinical records in the event of an operational pause or rollback.
- **Negative / Operational Considerations:**
  - Onboarding requires dedicated operational overhead and site owner sign-offs before a facility can be activated.

# ADR-025: Non-Causal Longitudinal Outcome Tracking, Unit/Method Compatibility Guards, and Adverse Effect Escalation

- **Status:** Accepted
- **Date:** 2026-10-13
- **Phase:** Prompt 09 — Follow-up, Care Continuity, Patient Communication & Outcome Tracking

## Context

Tracking patient-reported outcomes (e.g., Symptom Severity NRS 0–10, Digestive Comfort Score), clinician-assessed global impression (`CLINICIAN_GLOBAL_IMPRESSION`), medication adherence, and objective biomarkers across encounters is critical for chronic Unani and integrative care. However:
1. Uncontrolled trend charts often imply that observed symptom improvement proves causal treatment efficacy, creating scientific and regulatory misrepresentation.
2. Plotting values recorded with incompatible units (e.g., `mmHg` vs `kPa`) or incompatible measurement methods produces misleading clinical trajectories.
3. AI-extracted or unverified draft observations risk polluting verified clinical charts.
4. Patient-reported or staff-logged severe adverse effects require immediate clinical visibility and structured triage rather than passive storage.

## Decision

1. **Strict Non-Causal Longitudinal Trend Semantics:**
   - Every outcome trend computation (`get_patient_outcomes_and_trends`) explicitly sets `claims_causal_efficacy: false` and attaches a mandatory non-causal clinical disclaimer stating that observed longitudinal changes reflect chronological observations and do not establish causal treatment efficacy.
   - Trends are computed as descriptive delta directions (`LOWER_THAN_BASELINE`, `HIGHER_THAN_BASELINE`, `UNCHANGED`, `INSUFFICIENT_DATA`) without fabricating efficacy percentages.

2. **Unit & Measurement-Method Compatibility Guards:**
   - Before computing numeric deltas across data points for an `outcome_definition_id`, the engine checks unit consistency (`unit`) and measurement method consistency (`measurement_method`).
   - If units or measurement methods diverge across points in a series, the engine halts delta calculation and returns `trend_status: "cannot_compare_reliably"` with explicit `unit_consistent` / `method_consistent` diagnostic flags.

3. **Provenance Separation (`ai_draft_unverified` Exclusion):**
   - Outcome records carry explicit `source_type` (`PATIENT_REPORTED`, `CLINICIAN_ASSESSED`, `LAB_MEASURED`, `STAFF_LOGGED`, `AI_DRAFT_UNVERIFIED`) and `verification_status` (`VERIFIED`, `UNVERIFIED_PATIENT_REPORT`, `AI_DRAFT_UNVERIFIED`).
   - Any record flagged `AI_DRAFT_UNVERIFIED` is excluded from verified clinical trend series until reviewed and verified by an authorized clinician.

4. **Adverse Effect Escalation & Urgent Clinical Review Tasking:**
   - Logging an adverse effect (`adverse_effect_reports`) with `severity` in (`SEVERE`, `LIFE_THREATENING`) or `emergency_warning_given = true` automatically sets `escalation_required = 1` and atomically creates an urgent `ADVERSE_EFFECT_REVIEW` task (`priority = 'URGENT'`) in `follow_up_tasks` for immediate practitioner review.

## Consequences

- Prevents misleading efficacy claims and unit-mismatch charting errors.
- Preserves provenance boundaries between patient-reported, clinician-assessed, and unverified AI draft observations.
- Guarantees that severe post-visit adverse events immediately surface in the clinical follow-up queue.

# PROMPT 26 REPOSITORY AUDIT: Clinical Outcome Tracking, Treatment Response Measurement & Longitudinal Evaluation Engine

**Audit Date:** 2026-10-13  
**Auditor:** Antigravity AI Assistant & Clinical Architecture Team  
**Scope:** Repository readiness audit for Phase 26 outcome measurement, instrument registry, compatibility checking, treatment-course context, and longitudinal evaluation in `zayvora-matab-os`.

---

## 1. Audit Summary & Readiness Matrix

| Area | Status | Inspected Paths / Tables | Notes / Limitations |
|------|--------|--------------------------|---------------------|
| **Patient & Encounter Identity, RBAC, Multi-Tenancy** | `implemented_and_tested` | `patients`, `encounters`, `apps/api/core/permissions.py`, `apps/api/core/security.py` | Full multi-tenant isolation, facility memberships, and RBAC aliases functional and tested. |
| **Observations, Vitals, Labs & Units** | `implemented_and_tested` | `vitals`, `observations`, `modern_assessments`, `unani_assessments`, `apps/api/domains/modern_assessment.py` | Standard observation schema exists. Units preserved. Need extension for instrument-specific item responses and explicit calculation manifests. |
| **Follow-up Tasks, Communication & Contact Logs** | `implemented_and_tested` | `follow_up_tasks`, `contact_attempts`, `care_continuity_tasks`, `apps/api/domains/care_continuity.py`, `apps/api/domains/timeline.py` | Phase 9 & Phase 25 follow-up orchestration functional with contact attempt counting. |
| **Prescription Lifecycle & Treatment Exposure** | `implemented_and_tested` | `prescriptions`, `prescription_items`, `medication_status_ledger`, `apps/api/domains/prescriptions.py`, `apps/api/domains/timeline.py` | Cryptographically signed immutable prescriptions. Phase 25 medication status ledger tracks active/discontinued states; dispensing is separate from prescribing. |
| **Adverse Effects & Safety Workflow** | `implemented_and_tested` | `adverse_effect_reports`, `safety_evaluations`, `apps/api/domains/care_continuity.py`, `apps/api/domains/safety_firewall.py` | Structured adverse effect capture exists with escalation flag. Need dedicated linking between outcome measurements and safety workflow. |
| **Longitudinal Timeline & Provenance** | `implemented_and_tested` | `patient_timeline_events`, `apps/api/domains/timeline.py` | 7 stream lanes (`UNANI`, `MODERN`, `MEDICATION`, etc.), temporal precision (`YEAR`, `MONTH`, `DAY`, `EXACT_TIMESTAMP`), and encounter projection functional. |
| **Data Quality & Missingness Semantics** | `implemented_and_tested` | `dq_findings`, `dq_evaluations`, `apps/api/domains/data_quality.py` | Canonical 7 missingness states (`MISSING`, `UNKNOWN`, `NOT_RECORDED`, `NOT_ASSESSED`, `DECLINED_BY_PATIENT`, `NOT_APPLICABLE`, `UNAVAILABLE`) fully functional. |
| **Claim / Evidence Provenance & Clinician Review** | `implemented_and_tested` | `knowledge_assertions`, `claim_source_links`, `clinical_signoffs`, `apps/api/domains/evidence_verification.py`, `apps/api/domains/cds_orchestrator.py` | Dual-human review gates and citation verification engine fully functional. |
| **Patient Privacy, Communication Preferences & Retention** | `implemented_and_tested` | `communication_preferences`, `patient_consents`, `apps/api/core/permissions.py` | Zero leakage into global RAG or public telemetry. |
| **Existing Outcome Definitions & Records** | `partially_implemented` | `outcome_definitions`, `outcome_records` (Migration 009) | Simple baseline definitions and numeric records exist from Phase 9. Lacks instrument licensing metadata, item-level responses, protocol runs, explicit comparison compatibility checks, and clinical interpretation reviews. |
| **Measurement Instruments & Scoring Logic** | `not_implemented` | Needs `measurement_instruments`, `instrument_scoring_runs` | No instrument licensing or versioned scoring service exists yet. Needs implementation in Phase 26. |
| **Compatibility & Comparison Engine** | `not_implemented` | Needs `outcome_comparisons` | Comparison logic currently assumes direct numeric difference. Must enforce strict concept, instrument, unit, recall period, and version compatibility. |
| **Governed Care Episodes & Protocol Runs** | `not_implemented` | Needs `care_episodes`, `outcome_protocol_runs` | Episodes are currently loosely tied to encounters. Phase 26 will formalize `care_episodes` and `outcome_protocol_runs`. |
| **Treatment Exposure Context Integration** | `not_implemented` | Needs `treatment_exposure_contexts` | Does not currently formalize the distinction between prescribed, dispensed, and patient-reported exposure. |
| **Clinician Outcome Interpretations & Review Gate** | `not_implemented` | Needs `outcome_interpretations` | No separate interpretation entity exists separating observation from clinical interpretation. |
| **Analytics & Aggregate Reporting** | `partially_implemented` | `apps/api/domains/care_continuity.py` (`get_follow_up_analytics`) | Basic operational counters exist. Privacy-controlled aggregate outcome reporting with minimum cell sizes and disclosed denominators needs to be built. |

---

## 2. Identified Schema & Domain Requirements for Phase 26

To achieve full compliance with Prompt 26, Migration 025 and domain services must introduce:

1. **`outcome_concepts` & `measurement_instruments`:**
   - Versioned registry of outcome concepts and instruments.
   - License and permission state (`OPEN_ACCESS`, `LICENSED`, `CLINIC_CUSTOM`, `RESTRICTED`).
   - Sourced item schemas, allowed administration modes, and recall periods.
   - Prohibit claiming unvalidated instruments are validated.

2. **`outcome_protocols` & `outcome_protocol_runs`:**
   - Governed observation collection protocols defining baseline and follow-up time windows.
   - Run lifecycle (`OPEN`, `IN_PROGRESS`, `AWAITING_FOLLOW_UP`, `COMPLETED`, `INCOMPLETE`, `CANCELLED`).
   - Explicit baseline designation (recording who designated, when, and by what rule).

3. **`outcome_observations`:**
   - Raw vs normalized vs calculated values.
   - Distinct observation kinds: `PATIENT_REPORTED`, `CLINICIAN_OBSERVED`, `LABORATORY`, `DEVICE`, `CALCULATED`.
   - Distinct missingness states: `PRESENT`, `UNKNOWN`, `NOT_MEASURED`, `NOT_ASKED`, `DECLINED`, `UNAVAILABLE`, `PENDING`, `INVALID`, `ENTERED_IN_ERROR`.
   - Immutable raw responses with correction audit events.

4. **`instrument_scoring_runs`:**
   - Deterministic scoring engine for authorized instruments.
   - Preserves item-level inputs, formula version, and validation checks.
   - Rejects scoring when required items are missing according to instrument rules.

5. **`outcome_comparisons` & Compatibility Engine:**
   - Pre-comparison compatibility verification: concepts, instruments, units, population, administration mode, time semantics.
   - Explicit non-comparable states (`COMPARABLE`, `COMPARABLE_AFTER_APPROVED_CONVERSION`, `NOT_COMPARABLE_DIFFERENT_CONCEPT`, `NOT_COMPARABLE_DIFFERENT_INSTRUMENT`, `UNIT_UNRESOLVED`, `SOURCE_UNVERIFIED`, `TIME_UNCERTAIN`, `MISSING_REQUIRED_DATA`).
   - Calculation of change with preserved raw values, signed direction, and rule version.
   - Non-negotiable: Prohibit assigning "improved" or "treatment success" without a verified, authorized threshold.

6. **`treatment_exposure_contexts`:**
   - Descriptive association linking documented prescription, dispensing (if recorded), patient-reported consumption, and clinician medication reconciliation.
   - Strict ban on causal inference: temporal sequence $\neq$ treatment efficacy.

7. **`outcome_interpretations`:**
   - Complete separation between raw observation and clinician interpretation.
   - Review states: `DRAFT`, `REQUIRES_VALIDATION`, `READY_FOR_CLINICIAN_REVIEW`, `CLINICIAN_REVIEWED`, `REJECTED`.

8. **`outcome_aggregate_reports`:**
   - Bounded aggregate reporting with disclosure controls (minimum cell size $\ge 5$), explicit disclosure of missing data and denominators.
   - Prohibition of treatment ranking or cross-clinician efficacy comparisons on observational data.

---

## 3. Blockers & Mitigation Strategy

- **Blocker 1: Route collision on `/api/v1/patients/{id}/outcomes`:**
  - *Resolution:* Keep existing Phase 9 endpoint intact. Mount Phase 26 longitudinal outcome queries under `/api/v1/patients/(?P<patient_id>[^/]+)/outcome-evaluations` and `/api/v1/patients/(?P<patient_id>[^/]+)/outcomes/trends`.
- **Blocker 2: Conflating Missingness with Zero:**
  - *Resolution:* Enforce strict typing. `0` is a valid mathematical measurement; missing responses must be explicitly typed using the 7 canonical missingness states.
- **Blocker 3: Causal Claim Inflation:**
  - *Resolution:* Hardcode engine assertions rejecting `treatment_success` flags. Outputs are strictly labeled `DESCRIPTIVE_CHANGE` with explicit disclaimer: "Temporal association does not establish causal efficacy."

The repository is fully ready for Migration 025 and Phase 26 domain implementation.

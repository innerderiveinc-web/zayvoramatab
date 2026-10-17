# Architecture Decision Record (ADR) — ZAYVORA MATAB OS

## ADR-045: Clinical Outcome Tracking, Treatment Response Measurement & Longitudinal Evaluation Engine (Prompt 26)

- **Status:** Accepted
- **Date:** 2026-10-13
- **Author:** Clinical Architecture Team & Antigravity Assistant
- **Predecessors:** Prompts 01–25 (ADR-001 through ADR-044)
- **Primary Objective:** Build a governed outcome-measurement capability that lets clinicians define an appropriate baseline, record follow-up observations and patient-reported outcomes, compare only compatible measurements, document treatment exposure context, and review change over time—without inventing missing data, conflating temporal correlation with causal efficacy, or declaring success/failure from arbitrary thresholds.

---

### 1. Context & Clinical Problem Statement

Documenting patient response over time is essential for clinical care in Unani medicine (*Tanqiya*, *Tadeel*, formulation adjustments) and hospital continuity. However, conventional EHR outcome tracking and AI analytics suffer from severe failure modes:
1. **Conflating Change with Causation:** When a symptom score improves after a prescription is issued, systems frequently generate misleading charts or summaries implying the medicine caused the cure, ignoring regression to the mean, placebo response, lifestyle co-interventions, and natural disease resolution.
2. **Missing-Value Imputation in Clinical Records:** Filling missing questionnaire items with averages or assuming unasked questions represent zero symptoms falsifies medical records.
3. **Invented Success Thresholds:** Declaring a patient a "responder" or "treatment success" based on unvalidated percentage drops or LLM intuition rather than verified instrument manuals.
4. **Instrument Licensing and Integrity Violations:** Using proprietary scales without rights or modifying validated questionnaire wording while dishonestly retaining validation claims.
5. **Conflation of Prescribing with Exposure:** Assuming that because a formulation was prescribed, the patient received it, took it with full adherence, and took no other remedies.
6. **Epistemological Flattening:** Conflating traditional Unani clinical assessments (Nabz, Mizaj balance, Su-e-Hazm grades) with modern validated biomedical endpoints.
7. **Patient Privacy & Data Leakage:** Leaking confidential patient outcomes into global vector stores, public analytics, or cross-clinic marketing reports.

Prompt 26 establishes a source-grounded, permission-aware, and deterministic outcome tracking architecture to prevent these risks.

---

### 2. Architectural Decision & Core Mechanics

#### 2.1 Database Schema & Migration 025
Implement Migration 025 (`025_clinical_outcome_tracking_and_evaluation_schema.sql`) introducing 11 relational tables:
1. `care_episodes`: Explicit clinical follow-up contexts initiated by authorized clinicians.
2. `outcome_concepts`: Canonical registry of outcome concepts across clinical domains (`SYMPTOM_EXPERIENCE`, `FUNCTIONAL_STATUS`, `QUALITY_OF_LIFE`, `LABORATORY_MEASURE`, `UNANI_CLINICAL_MARKER`).
3. `measurement_instruments`: Registry of questionnaires and scales with licensing states (`OPEN_ACCESS`, `LICENSED`, `CLINIC_CUSTOM`, `RESTRICTED`), recall periods, administration modes, items schemas, and verified validity references.
4. `outcome_protocols`: Governed collection schedules defining baseline and follow-up time windows.
5. `outcome_protocol_runs`: Patient-specific protocol runs tracking baseline designation (`PRE_TREATMENT_OBSERVATION`, `CLINICIAN_MANUAL_SELECTION`) and completion states.
6. `outcome_observations`: Append-only raw observations preserving raw values, raw units, normalized values, item-level responses (`item_responses_json`), observation kinds (`PATIENT_REPORTED`, `CLINICIAN_OBSERVED`, `LABORATORY`, `DEVICE`, `CALCULATED`), and explicit missingness states (`PRESENT`, `DECLINED`, `NOT_MEASURED`, `NOT_ASKED`, `UNAVAILABLE`). Versioned corrections create new records with `supersedes_id`.
7. `instrument_scoring_runs`: Deterministic calculations capturing input manifests, formula versions, and scoring states (`COMPLETED`, `INCOMPLETE`, `UNLICENSED_METHOD_BLOCKED`).
8. `outcome_comparisons`: Bounded comparisons between eligible observations recording mathematical deltas, direction of change (`INCREASED`, `DECREASED`, `UNCHANGED`), and descriptive labels (`NUMERIC_DELTA_...`). Autonomous "treatment_success" labels are strictly prohibited.
9. `treatment_exposure_contexts`: Descriptive tracking linking canonical prescriptions, documented exposure periods, exposure status (`PRESCRIBED_NOT_CONFIRMED_TAKEN`, `DISPENSED_CONFIRMED`, `PATIENT_REPORTED_TAKEN`), patient-reported adherence %, reconciliation state, and mandatory causality disclaimer.
10. `outcome_interpretations`: Complete separation between raw observation and clinician interpretation. AI drafts are stored as `DRAFT` and require human clinician review (`CLINICIAN_REVIEWED`).
11. `outcome_aggregate_reports`: Governed aggregate reports with minimum cell size disclosure controls ($\ge 5$), explicit denominator and missing data rate disclosure, and non-causal disclaimers.

#### 2.2 Compatibility Preflight Engine
Before computing deltas, the engine verifies 8 compatibility dimensions:
- Concept equality (`concept_id`)
- Instrument and version equality (`instrument_id`, `instrument_version`)
- Unit compatibility (`raw_unit`, `normalized_unit`)
- Administration mode and recall period
- Temporal precision and verification state
- Missingness status (`status == 'PRESENT'`)

If compatibility fails, the engine outputs an explicit non-comparable status:
- `NOT_COMPARABLE_DIFFERENT_CONCEPT`
- `NOT_COMPARABLE_DIFFERENT_INSTRUMENT`
- `UNIT_UNRESOLVED`
- `MISSING_REQUIRED_DATA`
- `NOT_COMPARABLE_METHOD_OR_CONTEXT`

#### 2.3 Strict Separation of Layers
- **Raw Observation:** Exact patient response or clinical reading.
- **Normalized Measure:** Unit-standardized value retaining transformation method.
- **Calculated Score:** Verified formula output with item input manifest.
- **Longitudinal Delta:** Mathematical difference between compatible points.
- **Clinical Interpretation:** Clinician-authored or attested explanation.

#### 2.4 Non-Causal Exposure Context & Harms Preservation
- Documenting that a patient took a formulation before a symptom improved does not prove therapeutic efficacy. The engine mandates the disclaimer: *"Temporal association does not establish causal efficacy."*
- Adverse experiences and side effects cannot be hidden or suppressed by positive outcome summaries.

---

### 3. API Surface & Permission Model

Mounted REST endpoints in `apps/api/routes/outcomes.py`:
- `GET /api/v1/outcomes/instruments` (`outcomes:read`)
- `GET /api/v1/outcomes/instruments/(?P<id>[^/]+)` (`outcomes:read`)
- `GET /api/v1/outcomes/concepts` (`outcomes:read`)
- `GET /api/v1/outcomes/protocols` (`outcomes:read`)
- `POST /api/v1/care-episodes` (`outcomes:record`)
- `POST /api/v1/outcome-protocol-runs` (`outcomes:record`)
- `POST /api/v1/outcome-protocol-runs/(?P<id>[^/]+)/baseline` (`outcomes:record`)
- `POST /api/v1/outcome-observations` (`outcomes:record`)
- `POST /api/v1/outcome-observations/(?P<id>[^/]+)/correction` (`outcomes:record`)
- `GET /api/v1/outcome-observations/(?P<id>[^/]+)` (`outcomes:read`)
- `POST /api/v1/outcomes/instrument-scores` (`outcomes:record`)
- `POST /api/v1/outcomes/compare` (`outcomes:compare`)
- `POST /api/v1/patients/(?P<patient_id>[^/]+)/treatment-exposures` (`outcomes:record`)
- `GET /api/v1/patients/(?P<patient_id>[^/]+)/treatment-exposures` (`outcomes:read`)
- `POST /api/v1/outcome-interpretations` (`outcomes:interpret`)
- `POST /api/v1/outcome-interpretations/(?P<id>[^/]+)/review` (`outcomes:interpret`)
- `GET /api/v1/patients/(?P<patient_id>[^/]+)/outcomes/trends` (`outcomes:read`)
- `POST /api/v1/outcomes/aggregate-reports` (`outcomes:aggregate`)
- `GET /api/v1/outcomes/aggregate-reports/(?P<id>[^/]+)` (`outcomes:read` / `outcomes:aggregate`)

Permissions registered in `apps/api/core/permissions.py`:
- `outcomes:read`: View outcome concepts, instruments, observations, and patient trends.
- `outcomes:record`: Record observations, start protocol runs, designate baselines, update exposures.
- `outcomes:compare`: Execute compatibility checks and compute longitudinal deltas.
- `outcomes:interpret`: Create and review clinician outcome interpretations.
- `outcomes:manage`: Manage concept and instrument registries.
- `outcomes:aggregate`: Generate privacy-controlled aggregate QA reports.

---

### 4. Consequences & Verification

- **Strengths:**
  - Complete elimination of hallucinated or imputed clinical outcome data.
  - Zero unverified "treatment success" badges or causal overclaims.
  - Unani clinical markers and biomedical laboratory endpoints remain typed and historically distinct.
  - Instrument licensing boundaries strictly enforced (commercial/unlicensed instruments cannot run scoring).
  - Versioned, non-destructive audit trail for observation corrections.
- **Trade-offs:**
  - Clinicians must explicitly designate baseline observations and complete required questionnaire items.
  - Longitudinal deltas are strictly descriptive and require clinician interpretation for treatment adjustments.

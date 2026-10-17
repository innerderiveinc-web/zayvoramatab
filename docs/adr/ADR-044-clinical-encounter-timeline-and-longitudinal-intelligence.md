# Architecture Decision Record (ADR) — ZAYVORA MATAB OS

## ADR-044: Clinical Encounter Timeline, Longitudinal Patient Intelligence & Continuity-of-Care Engine (Prompt 25)

- **Status:** Accepted
- **Date:** 2026-10-13
- **Author:** Clinical Architecture Team & Antigravity Assistant
- **Predecessors:** Prompts 01–24 (ADR-001 through ADR-043)
- **Primary Objective:** Build a source-grounded longitudinal patient timeline, clinical intelligence layer, and continuity-of-care engine that presents authorized historical consultations, clinician observations, prescriptions, investigations, referrals, follow-ups, and recorded outcomes in their true temporal and provenance context—without inventing missing history, silently merging conflicting records, or treating historical events as current facts.

---

### 1. Context & Clinical Problem Statement

Clinical decision-making in Unani medicine and integrated care relies heavily on historical disease progression, seasonal temperament shifts, treatment response over time (*Tanqiya*, *Tadeel*, formulation adjustments), and follow-up continuity. Prior healthcare systems and unstructured timelines suffer from several severe failure modes:
1. **Timestamp Conflation:** Systems conflate the moment an event occurred (`occurred_at`) with the moment it was charted into the database (`recorded_at`), distorting clinical retrospectives.
2. **False Precision & Hallucinated History:** Approximating a patient's historical report ("diagnosed with jaundice 5 years ago") with a synthetic date-time like `2021-01-01T00:00:00.000Z` deceives decision support algorithms into assuming spurious chronologies.
3. **Epistemological Conflation:** Unani clinical assessments (Nabz, Baul, Baraz, Mizaj state, Akhlat imbalance) are improperly flattened into modern lab or diagnosis codes, obscuring traditional diagnostic trajectories.
4. **Active Medication Drift:** Historical prescriptions are left un-reconciled or erroneously assumed to be ongoing treatments without recorded discontinuation, dose modifications, or patient compliance status.
5. **Abandoned Follow-Up Tasks:** Referrals, red flag monitoring, and dietary follow-ups fall into administrative voids without structured task assignment, contact attempts tracking, or outcome documentation.
6. **AI Hallucination in Patient Summaries:** Large language models generating clinical summaries invent non-existent timeline events or collapse conflicting clinical records into false consensus.
7. **Patient Data Leakage:** Encounter events and confidential clinical timelines leak into global RAG indexes or multi-tenant telemetry.

Prompt 25 mandates an auditable, deterministic, and clinician-governed longitudinal intelligence engine to solve these challenges.

---

### 2. Architectural Decision & Core Mechanics

#### 2.1 Database Schema & Schema Migration 024
Implement Migration 024 (`024_longitudinal_patient_timeline_schema.sql`) creating four dedicated tables:
1. `patient_timeline_events`: Append-only projection of clinical events across 7 stream lanes (`UNANI`, `MODERN`, `MEDICATION`, `INVESTIGATION`, `CARE_CONTINUITY`, `OUTCOME`, `ADMINISTRATIVE`) with explicit `occurred_at`, `recorded_at`, `temporal_precision` (`EXACT_TIMESTAMP`, `DAY`, `MONTH`, `YEAR`), `clinical_significance` (`CRITICAL`, `IMPORTANT`, `ROUTINE`, `INFORMATIONAL`), `source_system`, and structured JSON payload.
2. `care_continuity_tasks`: Structured follow-up tasks (`FOLLOW_UP_CALL`, `ADHERENCE_CHECK`, `RED_FLAG_MONITORING`, `APPOINTMENT_REMINDER`, `LAB_REVIEW`, `DIET_LIFESTYLE_REVIEW`) with priority, due date, assigned role, contact attempt counters, attempt logs, and completion outcome notes.
3. `medication_status_ledger`: Longitudinal medication tracking capturing formulation name, formulation type (`MUFRADAT`, `MURAKKABAT`, `MODERN`), lifecycle state (`ACTIVE`, `DISCONTINUED`, `COMPLETED`, `PAUSED`), dosage summary, start date, end date, reason for discontinuation/change, and prescriber credentials.
4. `timeline_summary_runs`: Auditable narrative summaries of longitudinal patient history with draft text, clinical input provenance, generator mode, and mandatory human review status (`DRAFT`, `CLINICIAN_REVIEWED`, `REJECTED`).

#### 2.2 Temporal Precision & Provenance Integrity
- Every event records `occurred_at` (when it happened) separately from `recorded_at` (when entered).
- Supported temporal precisions:
  - `EXACT_TIMESTAMP`: Verified date and time (e.g., consultation signoff, lab draw).
  - `DAY`: Accurate to a specific calendar date (e.g., patient-reported symptom onset).
  - `MONTH`: Accurate to month and year (e.g., "began noticing fatigue in May 2024").
  - `YEAR`: Approximate historical year (e.g., "diagnosed with asthma in 2018").
- Coarse timestamps are never synthetically backfilled to 00:00:00 or current clock time.

#### 2.3 Epistemological Multi-Stream Separation
Events are segregated into distinct stream lanes:
- `UNANI`: Mizaj assessments, Nabz examinations, Baul/Baraz analysis, Usul-e-Ilaj phases (*Nudj*, *Tanqiya*, *Tadeel*), Ilaj-bit-Tadbeer regimens.
- `MODERN`: Vital signs, physical exams, ICD-10/biomedical diagnostic impressions, red flag alerts, emergency referrals.
- `MEDICATION`: Prescription issuances, dose adjustments, discontinuations, adverse drug reactions.
- `INVESTIGATION`: Diagnostic lab orders, imaging reports, point-of-care test results.
- `CARE_CONTINUITY`: Follow-up phone calls, triage checks, patient-reported recovery logs.
- `OUTCOME`: Longitudinal treatment response evaluations, symptom resolution milestones.
- `ADMINISTRATIVE`: Encounter check-ins, registration updates.

#### 2.4 Encounter Projection Engine
- When an encounter is finalized or explicitly synced (`POST /api/v1/encounters/{encounter_id}/timeline-sync`), `PatientTimelineEngine` projects all encounter data into atomic timeline events:
  - Encounter visit event (`ADMINISTRATIVE`).
  - Unani assessment & dominant Mizaj (`UNANI`).
  - Modern assessment & primary diagnosis (`MODERN`).
  - Signed prescription items (`MEDICATION`).
- Idempotent sync ensures events are updated or created without duplicate event inflation.

#### 2.5 Longitudinal Medication Ledger
- Tracks medication lifecycles independently of individual prescriptions.
- Distinguishes active therapy from discontinued or completed regimens.
- Changes in medication state require documented clinical rationale (`reason_for_change`).

#### 2.6 Care Continuity Task Orchestration
- Generates actionable, role-routed tasks (`CARE_COORDINATOR`, `TRIAGE_NURSE`, `CLINICIAN`, `PHARMACIST`).
- Records incremental contact attempts (`POST /api/v1/care-continuity/tasks/{task_id}/attempts`) with outcome notes and timestamped attempt log.
- Enforces explicit task completion with mandatory clinical outcome notes.

#### 2.7 Governed Timeline Summaries
- Summaries draft chronological longitudinal overviews without inventing missing periods.
- Stored as `DRAFT` and strictly prohibited from acting as legal medical records until authenticated via `POST /api/v1/timeline-summaries/{summary_id}/review` (`CLINICIAN_REVIEWED`).

#### 2.8 Patient Data Isolation
- Patient timelines and encounter projections are strictly isolated to patient-specific schemas and isolated tenant boundaries.
- Zero patient data is ever indexed into global RAG knowledge stores or shared telemetry logs.

---

### 3. API Surface & Permission Model

Mounted REST endpoints in `apps/api/routes/timeline.py`:
- `GET /api/v1/patients/(?P<patient_id>[^/]+)/longitudinal-timeline` (`timeline:read`)
- `POST /api/v1/patients/(?P<patient_id>[^/]+)/timeline-events` (`timeline:manage`)
- `POST /api/v1/encounters/(?P<encounter_id>[^/]+)/timeline-sync` (`timeline:manage`)
- `GET /api/v1/patients/(?P<patient_id>[^/]+)/medications` (`timeline:read`)
- `POST /api/v1/patients/(?P<patient_id>[^/]+)/medications/status` (`timeline:manage`)
- `GET /api/v1/care-continuity/tasks` (`timeline:read`)
- `POST /api/v1/care-continuity/tasks` (`timeline:manage`)
- `POST /api/v1/care-continuity/tasks/(?P<task_id>[^/]+)/attempts` (`timeline:manage`)
- `POST /api/v1/care-continuity/tasks/(?P<task_id>[^/]+)/complete` (`timeline:manage`)
- `POST /api/v1/patients/(?P<patient_id>[^/]+)/timeline-summaries` (`timeline:summarize`)
- `POST /api/v1/timeline-summaries/(?P<summary_id>[^/]+)/review` (`timeline:summarize`)

Permissions added to `apps/api/core/permissions.py`:
- `timeline:read`: View timeline events, medication ledger, continuity tasks, summaries.
- `timeline:manage`: Create events, sync encounters, record med states, schedule/complete tasks.
- `timeline:summarize`: Generate and review longitudinal narrative summaries.

---

### 4. Consequences & Verification

- **Strengths:**
  - True chronological clarity and provenance non-repudiation.
  - Zero date fabrication or artificial temporal precision.
  - Unani and modern diagnostic streams remain cleanly separated and historically traceable.
  - Medication drift prevented via explicit status ledger.
  - Closed-loop care continuity tracking.
  - Comprehensive unit and integration test coverage across all domain algorithms and HTTP endpoints.
- **Trade-offs:**
  - Encounter sync creates multiple projected timeline records, requiring efficient indexing on `(patient_id, occurred_at DESC)`.
  - Clinicians must explicitly record discontinuation when stopping a formulation outside a formal consultation.

# PROMPT 25 PREREQUISITE AUDIT: Clinical Encounter Timeline, Longitudinal Patient Intelligence & Continuity-of-Care Engine

**Document Type:** Architecture & Prerequisite Audit  
**Phase:** 25 — Longitudinal patient record, clinical timeline, follow-up continuity, and historical-context review  
**Product:** ZAYVORA MATAB OS (standalone clinic/Matab operating system)  
**Date:** October 2026  

---

## 1. Objective & Boundaries

Prompt 25 implements a reliable longitudinal patient timeline and continuity-of-care engine that organizes authorized historical consultations, patient-reported changes, clinician observations, assessments, prescriptions, laboratory results, referrals, follow-ups, and outcomes in their true temporal and epistemological context.

### Critical Non-Negotiables:
1. **Never Fabricate History:** The engine never manufactures historical encounters, test results, or time-of-day for coarse date-only records.
2. **True Temporal Distinction:** Explicitly distinguishes:
   - `occurred_at`: When the event clinically happened.
   - `temporal_precision`: `YEAR`, `MONTH`, `DAY`, `EXACT_TIMESTAMP`.
   - `recorded_at`: When the event was keyed into the system.
3. **Historical != Current:** Clear separation between historical diagnoses/medications and active clinical problems.
4. **Epistemological Lane Separation:** Preserves distinct streams: `UNANI`, `MODERN`, `MEDICATION`, `LABORATORY`, `ADMINISTRATIVE`, `PATIENT_REPORTED`, `CARE_CONTINUITY`.
5. **Care Continuity Task Tracking:** Deterministic follow-up tasks (`FOLLOW_UP_CALL`, `LAB_REVIEW`, `OUTCOME_ASSESSMENT`) with contact attempt logs and escalation reasons.
6. **Traceable AI Draft Summaries:** Any synthesized summary requires per-claim bindings to exact timeline event IDs, is guarded behind a feature flag, and remains in `DRAFT` status until qualified clinician review.
7. **Patient Data Isolation:** Zero leakage into global knowledge indexes or external telemetry.

---

## 2. Upstream Architecture Audit

| Prerequisite | Originating Phase | Status | Integration Touchpoint |
|---|---|---|---|
| **Patient Registry & Demographics** | Prompt 02 | Implemented & Seeded | Master patient envelope and MRN binding. |
| **Encounters Lifecycle** | Prompt 02, Prompt 08, Prompt 23 | Implemented & Seeded | Encounter events, status changes, signed snapshots. |
| **Unani Assessment & Usul-e-Ilaj** | Prompt 04 | Implemented & Seeded | Mizaj shifts, Nabz observations, care plan progressions. |
| **Modern Assessment & Vitals** | Prompt 05 | Implemented & Seeded | Clinical observations, differential revisions, lab reviews. |
| **Formularies & Prescriptions** | Prompt 03, Prompt 10 | Implemented & Seeded | Prescription issuance, dispensing logs, medication status ledger. |
| **Care Continuity Outbox** | Prompt 09 | Implemented & Seeded | Communication records, adverse effect escalations. |
| **Data Quality & Findings** | Prompt 24 | Implemented & Seeded | Remediation history, reconciliation decisions. |

---

## 3. Database Schema Design (Migration 024)

1. `patient_timeline_events`: Canonical event envelope with stream lane, occurred_at, temporal precision, source entity pointers, and clinical significance.
2. `care_continuity_tasks`: Operational tasks for follow-ups, adherence checks, and contact attempt audits.
3. `timeline_summary_runs`: Bound AI/draft summaries with mandatory claim-to-event bindings and clinician review state.
4. `medication_status_ledger`: Longitudinal tracking of active vs completed vs discontinued therapies.

SQLite 3 WAL mode compatibility and multi-tenant schema isolation are strictly preserved.

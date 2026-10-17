# PROMPT 24 PREREQUISITE AUDIT: Clinical Workflow Intelligence, Missing-Information Detection & Data-Quality Engine

**Document Type:** Architecture & Prerequisite Audit  
**Phase:** 24 — Clinical data completeness, contradiction detection, freshness, validation, and transparent workflow guidance  
**Product:** ZAYVORA MATAB OS (standalone clinic/Matab operating system)  
**Date:** October 2026  

---

## 1. Objective & Boundaries

Prompt 24 implements a deterministic, configurable data-quality and workflow-completeness engine that detects:
- Missing required clinical and administrative information
- Inconsistent values across related entities
- Stale or expired observations based on clinical freshness policies
- Unresolved identity conflicts or candidate duplicates
- Invalid units, out-of-range clinical observations, and bad date sequencing
- Workflow prerequisites required for encounter progression and finalization

### Critical Non-Negotiables:
1. **Never Fabricate Data:** The engine never populates missing fields with synthetic defaults, never assumes normal values for unrecorded tests, and never manufactures vitals or symptoms.
2. **Distinct Missingness States:** Absence of documentation is strictly distinguished:
   - `MISSING`: Required for workflow but absent.
   - `UNKNOWN`: Actively reported by patient/clinician as unknown.
   - `NOT_RECORDED`: Optional field omitted from note.
   - `NOT_ASSESSED`: Clinician purposefully did not perform exam.
   - `DECLINED_BY_PATIENT`: Patient explicitly refused examination or disclosure.
   - `NOT_APPLICABLE`: Field inapplicable to patient's clinical context.
   - `UNAVAILABLE`: Historical source record unretrievable.
3. **Completeness != Correctness:** No single pseudo-metric score concealing critical clinical contradictions.
4. **Transparent Remediation Routing:** Findings are routed to specific operational roles (`FRONT_DESK`, `TRIAGE_NURSE`, `CLINICIAN`, `PHARMACIST`, `ADMIN`) with clear clinical explanations.
5. **No Automatic Conflict Overwrite:** Conflicting sources are never overwritten by newest timestamp or AI guesses. All reconciliations require clinician review and documented rationale.

---

## 2. Upstream Architecture Audit

| Prerequisite | Originating Phase | Current Status | Integration Touchpoint |
|---|---|---|---|
| **Patient Registry & Demographics** | Prompt 02 | Implemented & Seeded | Demographics completeness, duplicate candidates, active status verification. |
| **Unani Assessment & Usul-e-Ilaj** | Prompt 04 | Implemented & Seeded | Mizaj assessment presence, Ajnas-e-Ashara, Nabz/Baul/Baraz completeness. |
| **Modern Assessment & Vitals** | Prompt 05 | Implemented & Seeded | Vitals units, systolic > diastolic validation, chief complaint presence, red flags. |
| **Consultation Orchestrator** | Prompt 08 | Implemented & Seeded | Multi-lane clinical coordination, draft tracking. |
| **Care Continuity & Outcomes** | Prompt 09 | Implemented & Seeded | Follow-up scheduling completeness, contact permissions. |
| **KAVS & Governed Knowledge** | Prompts 17–22 | Implemented & Seeded | Controlled catalog vocabularies, unit validation crosswalks. |
| **CDS Orchestrator & Approval** | Prompt 23 | Implemented & Seeded | 6-dimension readiness gate integration with data quality findings. |

---

## 3. Database Schema Design (Migration 023)

The following tables are designed to support Prompt 24:
1. `dq_rule_registry`: Configurable, versioned validation rules categorizing presence, validity, consistency, freshness, and workflow prerequisites.
2. `dq_evaluations`: Immutable audit records of data quality runs tied to exact entity snapshots.
3. `dq_findings`: Atomic findings detailing missingness state, severity, explanation, conflicting values, and remediation role.
4. `dq_field_provenance`: Granular record of field capture timestamps, authors, source streams, and units.
5. `dq_reconciliation_decisions`: Clinician-attributed conflict resolution ledger with required clinical rationale.
6. `dq_freshness_policies`: Field-specific validity windows (e.g. blood pressure freshness = 24h, pregnancy test = 72h).

All migrations maintain zero-dependency SQLite compliance and full backward compatibility.

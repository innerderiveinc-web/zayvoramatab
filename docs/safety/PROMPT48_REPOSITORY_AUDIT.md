# ZAYVORA MATAB OS — PROMPT 48 REPOSITORY AUDIT
## Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine

**Date:** 2026-10-14  
**Auditor:** Clinical Safety Engineer, Software Safety Architect, Verification Lead & Healthcare Workflow Analyst  
**Subsystems Inspected:** Prescription & Nuskha Signing, Deterministic Safety Firewall, CDS Orchestrator, Unani Assessment, Clinical RAG, Pharmacovigilance, Patient Identity, Audit Ledgers.

---

## 1. Intended Use Baseline & Scope Boundaries

### 1.1 Intended Users
- **Primary Clinical Users:** Licensed Hakeems, AYUSH clinicians, and Unani medical practitioners.
- **Secondary Clinical Users:** Triage nurses, clinical research coordinators, and clinical safety officers.
- **Administrative Users:** Front-desk receptionists, pharmacy dispensers, and billing cashiers (restricted from all clinical diagnostic and prescribing operations).

### 1.2 Intended Clinical Purposes
- Structured documentation of Unani temperamental evaluations (Mizaj, Afaal, Asbab-e-Sittah).
- Classical formulation (Mufradat and Murakkabat) reference and nuskha drafting.
- Deterministic drug safety preflight checking against documented patient allergies, drug-drug interactions, and toxic botanical substances (e.g. unpurified Schedule E(1) poisons such as *Strychnos nux-vomica* / Kuchla).
- Clinician attestation and legally binding electronic prescription signing via cryptographic PIN.
- Longitudinal care continuity tracking and ABDM/FHIR R4 health information exchange.

### 1.3 Excluded / Unauthorized Uses (Hard Safety Invariants)
- **Autonomous Diagnosis:** The system is explicitly prohibited from autonomously assigning clinical diagnoses or temperamental classifications.
- **Autonomous Prescribing:** The system must never independently sign or dispatch medical prescriptions without explicit clinician PIN entry.
- **Algorithmic Safety Bypass:** AI RAG assistant models cannot override, suppress, or modify deterministic safety firewall blocks.
- **Silent Patient Merging:** Automatic deduplication algorithms cannot merge distinct clinical histories without dual-human clinician confirmation.
- **Pediatric & Pregnancy Safety Override:** Automated systems cannot waive statutory toxic dosage ceilings for vulnerable populations.

---

## 2. Inventory of Existing Safety Controls & Architecture

| Workflow / Subsystem | Current Code Path | Relational Tables | Existing Safety Safeguards | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Prescription Signing** | `apps/api/domains/prescriptions.py`, `cds_orchestrator.py` | `prescriptions`, `prescription_items`, `clinical_signoffs` | Server-side PIN hash check, immutable SHA-256 snapshot, draft-to-signed state lock. | `IMPLEMENTED` |
| **Drug Safety Firewall** | `apps/api/domains/safety_firewall.py` | `safety_firewall_rules`, `normalized_substances` | Deterministic Schedule E(1) toxin blocks, allergy cross-matching, lethal dose ceiling enforcement. | `IMPLEMENTED` |
| **Dual-Lane Clinical Assessment** | `unani_assessment.py`, `modern_assessment.py` | `unani_clinical_assessments`, `modern_clinical_assessments` | Strict epistemological boundary; Unani Mizaj and modern ICD-10 diagnoses reside in separate stores. | `IMPLEMENTED` |
| **Knowledge RAG & Citations** | `clinical_rag.py`, `kavs.py` | `kavs_sources`, `rag_evidence_packs`, `rag_answer_runs` | Epistemological template separation, source rights preflight, page locator validation, retraction cascades. | `IMPLEMENTED` |
| **Pharmacovigilance** | `pharmacovigilance.py` | `safety_events`, `safety_event_triages`, `pharmacovigilance_signals` | WHO-UMC causality appraisal, cluster signal detection (PRR), statutory safety reporting formats. | `IMPLEMENTED` |
| **Patient Identity & Tenancy** | `data_governance.py`, `patients.py` | `patients`, `mdm_duplicate_candidate_reviews` | Optimistic concurrency (`version`), server-enforced facility tenancy, manual duplicate reconciliation. | `IMPLEMENTED` |

---

## 3. Gaps Identified (To be Resolved in Prompt 48)

1. **Absence of Unified Clinical Hazard Register:**
   - While individual safety mechanisms exist across modules, there is no centralized, versioned `clinical_hazard_register` documenting initiating causes, hazardous states, potential clinical consequences, and assigned clinical leads.
2. **Missing Traceable Safety Requirements Catalog:**
   - Safety constraints are embedded directly in Python code without formal traceability linking Intended Use $\to$ Hazard $\to$ Safety Requirement $\to$ Code Path $\to$ Verification Test $\to$ Release Gate.
3. **Lack of Structured Clinical Safety Cases (Claim-Context-Argument-Evidence):**
   - The repository lacks reviewable safety cases with explicit claims, operational scopes, limitations, exclusions, and Clinical Safety Officer approval records.
4. **No Pre-Deployment Safety Release Gate Evaluator:**
   - Deployments are evaluated for security and technical liveness, but not for safety case validity, control verification freshness, or open clinical hazards.
5. **No Closed-Loop Near-Miss & Clinical Safety Incident Tracker:**
   - Near misses, alert fatigue reports, and observed workflow deviations lack a dedicated non-punitive tracking loop connected to hazard re-evaluations and retest evidence.

---

## 4. Implementation Blueprint (Prompt 48)

1. **Migration 047:**
   - `clinical_intended_use_registry`
   - `clinical_hazard_register`
   - `safety_requirements_catalog`
   - `safety_control_verifications`
   - `clinical_safety_cases`
   - `clinical_safety_incidents`
   - `safety_release_gate_evaluations`
   - `clinical_safety_audit_ledger`
2. **Domain Engine (`EnterpriseClinicalSafetyCaseEngine`):**
   - Intended use catalog management and scope verification.
   - Clinical hazard registration with severity tiers (`CATASTROPHIC`, `CRITICAL`, `SERIOUS`, `MINOR`, `NEGLIGIBLE`).
   - Safety requirements catalog with bidirectional traceability to code paths and test suites.
   - Verification test evidence capture with freshness evaluation.
   - Structured Clinical Safety Case authoring and Clinical Safety Officer sign-off.
   - Closed-loop Near-Miss and Safety Incident reporting with corrective action tracking.
   - Deterministic Safety Release Gate evaluation (`PASS`, `BLOCKED`, `CONDITIONAL_PASS`, `STALE_EVIDENCE`).
   - Tamper-evident SHA-256 hash-chained clinical safety audit trail.
3. **REST API Interface (22 Endpoints):**
   - Mount `/api/v1/safety-case/` in `apps/api/router.py`.
4. **Web UI Governance Console:**
   - `Clinical Safety Cases & Hazards (P48)` tab in `apps/web/static/js/views/knowledge_admin.js`.
5. **Automated Verification:**
   - 10 unit tests in `tests/unit/test_clinical_safety.py` and 10 integration tests in `tests/integration/test_clinical_safety_api.py`.

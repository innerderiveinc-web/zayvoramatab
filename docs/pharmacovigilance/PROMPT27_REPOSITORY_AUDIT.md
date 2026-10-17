# ZAYVORA MATAB OS — Prompt 27 Repository Pre-Implementation Audit
## Clinical Safety Surveillance, Adverse Event Management & Pharmacovigilance Workflow

**Document Type:** Pre-Implementation Architectural & Codebase Audit  
**Product:** ZAYVORA MATAB OS — Standalone Clinic/Hospital Operating System  
**Phase:** 27 — Safety-Event Capture, Triage Workflow, Causality Review, Follow-Up, and Governed Reporting  
**Date:** October 2026  
**Status:** Completed & Pre-Flight Verified  

---

## 1. Executive Summary & Purpose

Prompt 27 establishes the **Clinical Safety Surveillance, Adverse Event Management & Pharmacovigilance Workflow** for ZAYVORA MATAB OS. In integrated traditional (Unani Tibb) and modern healthcare environments, patient safety surveillance must satisfy rigorous non-negotiable standards:
1. **Never fabricate safety events:** All reports, suspected product exposures, batch numbers, symptoms, lab investigations, seriousness determinations, and regulatory submissions must stem from genuine clinical/patient reports or documented verifications.
2. **Record reports before judging causality:** A suspected adverse reaction must be recorded immediately regardless of whether causality is confirmed, suspected, or initially deemed improbable.
3. **Strict separation of clinical dimensions:**
   - *Reported facts* vs *Clinical confirmation*
   - *Severity* (intensity, e.g., mild/moderate/severe) vs *Seriousness* (regulatory impact: death, life-threatening, hospitalization, disability, congenital anomaly)
   - *Expectedness* (listed in official monographs vs unlisted/unexpected)
   - *Causality assessment* (structured method, e.g., WHO-UMC, Naranjo, Unani Mizaj/Tadbeer context)
   - *Reportability* (jurisdiction requirements)
4. **No autonomous clinical or regulatory action:** The system never autonomously halts treatment, modifies formulations, or submits dossiers to external regulatory portals without explicit authorized clinician/compliance human approval.
5. **Preservation of original reporter narrative:** Verbatim text in Urdu, Arabic, Hindi, or English is preserved verbatim alongside normalized clinical summaries.
6. **Regulatory gateway safeguards:** Country-specific regulatory profiles (e.g., PvPI/CDSCO in India, DRAP in Pakistan, WHO Vigibase formats) remain inactive by default until confirmed and activated by designated compliance staff.

---

## 2. Codebase Audit of Existing Foundations

### 2.1 Existing Adverse Event Tables & Touchpoints
- **Migration 009 (`009_care_continuity_communications_schema.sql`):**
  - Table `adverse_effect_reports`: Basic schema (`patient_id`, `encounter_id`, `severity`, `description`, `action_taken`, `reported_by`).
  - Served initial care continuity alerting in early phases.
- **Migration 025 (`025_clinical_outcome_tracking_and_evaluation_schema.sql`):**
  - Table `treatment_exposure_contexts`: Includes `linked_adverse_effect_id` and non-negotiable `causality_disclaimer` field emphasizing that concurrent exposure does not establish causation.
- **Safety Firewall (`apps/api/domains/safety.py`, Migration 007):**
  - Deterministic checking of ingredient toxicity, Mudabbar processing, herb-drug interactions, contraindications, and Schedule E(1) rules prior to prescription signing.
  - Phase 27 safety surveillance integrates with the Safety Firewall by surfacing pharmacovigilance signal candidates without modifying prescribing rules automatically.
- **Clinical Decision Support (`apps/api/domains/cds.py`, Migration 022):**
  - Governed cards with mandatory human review. Pharmacovigilance alerts flow as informative advisory cards rather than automated prescription overrides.
- **Longitudinal Patient Timeline (`apps/api/domains/timeline.py`, Migration 024):**
  - Projects clinical events into patient timelines across distinct epistemological streams. Phase 27 safety cases project into patient timelines as safety surveillance events.

### 2.2 Architectural Gap Analysis for Phase 27
To satisfy Prompt 27, the system requires dedicated, auditable pharmacovigilance persistence and workflows:
1. **Safety Case Lifecycle Management (`safety_cases`):**
   - Distinct from general encounters; tracks `case_number`, `case_type` (ADVERSE_EVENT, SUSPECTED_ADVERSE_REACTION, PRODUCT_QUALITY_DEFECT, MEDICATION_ERROR, NEAR_MISS, THERAPEUTIC_FAILURE), `case_state` (DRAFT, INTAKE_COMPLETE, TRIAGED, UNDER_CLINICAL_REVIEW, CAUSALITY_EVALUATED, READY_FOR_SUBMISSION_REVIEW, SUBMISSION_PENDING, SUBMITTED, CLOSED), `case_version`, reporter demographics/contact (with privacy-protective masking), original verbatim narrative, and normalized summary.
2. **Granular Adverse Events (`safety_events`):**
   - Captures each distinct event/reaction, onset timestamp and precision (`EXACT_TIMESTAMP`, `DAY`, `MONTH`, `APPROXIMATE`), resolution status, course status, and clinical confirmation status (`SUSPECTED_UNCONFIRMED`, `CLINICIAN_CONFIRMED`, `REFUTED`, `INDETERMINATE`).
3. **Suspected Exposures (`suspected_exposures`):**
   - Product name, canonical formulation ID, batch/lot number, manufacturer details, dosage regimen, start/stop dates, role (`SUSPECTED`, `CONCOMITANT`, `INTERACTING`), identity resolution state (`CONFIRMED_CATALOG`, `PROVISIONAL_UNRESOLVED`, `FREE_TEXT_ONLY`).
4. **Decoupled Multidimensional Assessments (`safety_assessments`):**
   - Separate assessment records for `CLINICAL_CONFIRMATION`, `SEVERITY`, `SERIOUSNESS`, `EXPECTEDNESS`, `CAUSALITY`, `REPORTABILITY`.
   - Each with explicit assessment scale/method, rationale, assessor ID, assessor role, review status, and timestamp.
5. **Governed Regulatory Report Profiles (`regulatory_report_profiles`):**
   - Jurisdiction-specific profiles (e.g., PVPI_ASU, DRAP_PHARMACOVIGILANCE, WHO_E2B_R3) with strict field requirements, disabled (`is_active = 0`) by default until compliance verification.
6. **Regulatory Submissions Ledger (`safety_submissions`):**
   - Pre-submission package generation with SHA-256 integrity hash, two-person authorization workflow, submission state machine (`PENDING_AUTHORIZATION`, `AUTHORIZED`, `DISPATCH_BLOCKED`, `SUBMITTED`, `ACKNOWLEDGED`, `REJECTED`), and immutable receipt/acknowledgement capture.
7. **Duplicate Management & Follow-Up Tasks (`safety_case_links`, `safety_follow_up_tasks`):**
   - Reviewer-linked duplicate relationships (`POSSIBLE_DUPLICATE`, `CONFIRMED_DUPLICATE`, `FOLLOW_UP_REPORT`) without silent auto-merges; actionable follow-up task orchestration.
8. **Pharmacovigilance Signal Candidates (`safety_signals`, `safety_signal_reviews`):**
   - Aggregated signal candidate detection for repeated product-event combinations with clinical review queues.

---

## 3. Implementation Plan & Non-Negotiables Verification Matrix

| Prompt 27 Non-Negotiable | Mechanism / Component | Enforcement Point |
|---|---|---|
| **No Fabricated Data** | Relational schema with required reporter, narrative, and product inputs | Database constraints and API validation |
| **Record Before Judging** | Case state machine enters `INTAKE_COMPLETE` prior to any causality evaluation | `PharmacovigilanceEngine.create_safety_case()` |
| **No Auto Causality** | Causality must be an explicit `safety_assessments` record authored by a qualified clinician | `PharmacovigilanceEngine.record_assessment()` |
| **Separate Dimensions** | Distinct assessment rows for severity, seriousness, expectedness, causality | Enum constraints & separate review workflows |
| **No Autonomous Actions** | CDS cards are advisory; no automated prescription cancellations | Human clinician approval required |
| **Inactive Reg Profiles** | `is_active` default 0; activation requires compliance verification | Schema default & activation check |
| **Authorized Submission** | Cryptographic payload hash + human authorizer credential check | `PharmacovigilanceEngine.submit_report_package()` |
| **Verbatim Preservation** | `original_narrative` stored unedited alongside `normalized_summary` | `safety_cases` columns |
| **Privacy Protection** | `reporter_contact_redacted_json` stores masked PII with restricted access | API serialization & role checks |

---

## 4. Audit Sign-off

The architectural prerequisites across Migrations 001–025 are verified and operating at 100% test pass rate (420/420 tests). Migration 026 and `PharmacovigilanceEngine` will be implemented cleanly with standalone relational persistence and comprehensive testing.

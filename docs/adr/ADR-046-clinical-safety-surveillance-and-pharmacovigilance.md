# ADR-046: Clinical Safety Surveillance, Adverse Event Management & Pharmacovigilance Workflow (Prompt 27)

## Status
Accepted

## Context
In integrated traditional (Unani Tibb) and modern clinical practice, adverse event tracking and pharmacovigilance have historically suffered from informal reporting, unstandardized causality assumptions, conflation of reported symptoms with confirmed clinical findings, and manual regulatory filing burdens. Furthermore, AI or automated systems risk fabricating clinical causality, prematurely blaming herbal formulations without systematic dechallenge/rechallenge assessment, or auto-transmitting unverified reports to national pharmacovigilance centers.

Prompt 27 mandates an auditable, privacy-protective, and multidimensional pharmacovigilance workflow for ZAYVORA MATAB OS that strictly prevents fabrication, records reports before judging causality, enforces separation of clinical dimensions, requires human review for regulatory submissions, and keeps jurisdiction-specific reporting profiles disabled until verified by compliance staff.

## Decision
1. **Migration 026 Relational Persistence:**
   - `safety_cases`: Master safety case ledger recording intake channel, case type, case state, original verbatim narrative, normalized clinical summary, urgency level, emergency escalation state, and privacy-masked reporter contact details.
   - `safety_events`: Discrete adverse reactions with onset date precision (`EXACT_TIMESTAMP`, `DAY`, `MONTH`, `YEAR`, `APPROXIMATE`), course status, and clinical confirmation state (`SUSPECTED_UNCONFIRMED`, `CLINICIAN_CONFIRMED`, `REFUTED`, `INDETERMINATE`).
   - `suspected_exposures`: Medications, formulations, or substances linked to cases with batch/lot numbers, exposure roles (`SUSPECTED`, `CONCOMITANT`, `INTERACTING`, `HISTORICAL`), and catalog identity resolution tracking.
   - `safety_assessments`: Strictly decoupled assessments across six dimensions: `CLINICAL_CONFIRMATION`, `SEVERITY`, `SERIOUSNESS`, `EXPECTEDNESS`, `CAUSALITY`, and `REPORTABILITY`, each with required evaluation methods (WHO-UMC, Naranjo, Hartwig, ICH E2A) and clinical rationale.
   - `regulatory_report_profiles`: Standardized regulatory schemas (PvPI ASU India, DRAP Pharmacovigilance Pakistan, WHO Vigibase E2B) that are disabled by default (`is_active = 0`) until compliance verification.
   - `safety_submissions`: Governed regulatory submission packages with SHA-256 payload manifest hashes, two-person authorization gates, and verifiable receipt tracking.
   - `safety_case_links` and `safety_follow_up_tasks`: Explicit deduplication linking without silent auto-merges, and actionable follow-up query tracking.
   - `safety_signals`: Product-reaction pair candidate detection and review queues.
2. **Domain Engine (`PharmacovigilanceEngine`):**
   - Enforces fail-closed validation, verbatim narrative preservation in native scripts (Urdu, Arabic, English), privacy masking of PII, emergency red flag detection with automated clinical escalation, and human authorization checks.
3. **REST API Endpoints:**
   - 20 endpoints mounted under `/api/v1/safety/*` with permission checks (`safety:read`, `safety:record`, `safety:triage`, `safety:assess`, `safety:report`, `safety:manage`).

## Consequences
- **Positive:**
  - Complete compliance with national and international pharmacovigilance standards (PvPI, DRAP, WHO-UMC).
  - Absolute elimination of automated causality attribution or simulated regulatory dispatches.
  - Full auditability, patient privacy protection, and seamless integration with existing clinic workflows.
- **Negative / Trade-offs:**
  - Requires explicit clinical documentation across multiple dimensions rather than single-click reporting.
  - Submissions to external authorities require verified profiles and manual authorized dispatch.

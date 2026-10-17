# ADR-043: Clinical Workflow Intelligence, Missing-Information Detection & Data-Quality Engine (Prompt 24)

- **Status:** Accepted
- **Date:** October 2026
- **Context:**
  Prompt 24 mandates a deterministic, configurable data-quality and workflow-completeness engine for ZAYVORA MATAB OS. A critical failure mode in clinical information systems is silent data decay, treating omitted fields as negative/normal findings, and hiding severe clinical contradictions behind aggregate percentage completeness scores.
  The engine must detect missing required clinical information, unit mismatches, out-of-range physiological observations, stale laboratory/vital values, and unresolved duplicate records. It must explain each finding, distinguish administrative completeness from clinical adequacy, and route remediation to the appropriate operational role without inventing, silently changing, or autonomously interpreting patient data.

- **Decision:**
  1. **Canonical Missingness Classification:** Rejects treating unrecorded items as normal or negative. Categorizes all absent clinical data into seven explicit missingness states: `MISSING`, `UNKNOWN`, `NOT_RECORDED`, `NOT_ASSESSED`, `DECLINED_BY_PATIENT`, `NOT_APPLICABLE`, `UNAVAILABLE`.
  2. **Governed Data Quality Rule Registry (`dq_rule_registry`):** Versioned, reviewed rules classifying issues by category (`PRESENCE`, `VALIDITY`, `CONSISTENCY`, `FRESHNESS`, `IDENTITY`, `WORKFLOW_PREREQUISITE`), scope (`PATIENT`, `ENCOUNTER`, `ASSESSMENT`, `PRESCRIPTION`), severity (`INFO`, `WARNING`, `CRITICAL`, `BLOCKER`), and remediation role (`FRONT_DESK`, `TRIAGE_NURSE`, `CLINICIAN`, `PHARMACIST`, `ADMIN`).
  3. **Field-Specific Freshness Policies (`dq_freshness_policies`):** Establishes maximum age thresholds for dynamic clinical variables (e.g., blood pressure: 24h, temperature: 12h, pulse: 12h, pregnancy test: 72h, allergy review: 30 days). Expired records are marked as stale with explicit clinical severity and rationale.
  4. **Granular Field Provenance (`dq_field_provenance`):** Audits field capture timestamps, authors, units, and source streams (`PATIENT_REPORTED`, `CLINICIAN_OBSERVED`, `DEVICE_VITAL`, `EXTERNAL_RECORD`) to preserve evidence origins.
  5. **Deterministic Clinical Consistency & Validity Validation:** Validates physiological ranges (e.g. pulse rate between 30-220 bpm), measurement units (e.g. temperature must specify °C or °F), and logical relationships (e.g. systolic BP must be greater than diastolic BP).
  6. **Transparent Role-Routed Remediation:** Findings are routed to specific operational roles with clear clinical explanations and implications rather than unassigned alerts.
  7. **Human-Attributed Remediation & Safety Gating:** Remediations require recorded human actions (`RESOLVED`, `ACKNOWLEDGED_WITH_REASON`, `DEFERRED`). `BLOCKER` findings cannot be deferred; deferrals or acknowledgements require mandatory clinical justifications.
  8. **Clinician Conflict Reconciliation Ledger (`dq_reconciliation_decisions`):** Prohibits automatic conflict resolution (e.g., picking the newest timestamp or machine heuristics). Conflicting data across encounters or devices requires clinician review, option evaluation, and documented rationale.
  9. **Data Quality Workflow Readiness Gate:** Provides an automated preflight check ensuring zero unresolved `BLOCKER` data-quality findings prior to encounter finalization or prescription sign-off.
  10. **Zero Patient Context Leakage:** All evaluation findings remain strictly isolated within tenant boundaries; zero patient observations are leaked to external or shared telemetry.

- **Consequences:**
  - Complete elimination of silent assumption of normal values for undocumented observations.
  - Transparent remediation routing targeting front desk, nursing, and clinical staff appropriately.
  - Absolute preservation of evidence provenance and clinician accountability during conflict resolution.
  - Fail-closed clinical safety ensuring ungrounded or contradictory clinical encounters cannot be finalized.

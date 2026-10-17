# ADR-067: Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine

- **Status:** Accepted  
- **Date:** 2026-10-14  
- **Context:** Prompt 48 mandates an Enterprise Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine for ZAYVORA MATAB OS to identify clinical hazards, define safety requirements and controls, connect controls to executable test verifications, and govern release decisions for safety-relevant functionality. Core non-negotiables demand: (1) Intended Use Baseline: Clinical safety claims are strictly bounded by explicit intended-use statements with enumerated excluded uses; (2) Clinical Safety $\ne$ Cybersecurity: Secure access does not prove clinical correctness; (3) No Autonomous Prescribing/Diagnosing: Software cannot independently diagnose, prescribe, select nuskha, calculate doses, or replace clinical judgment; (4) Attributable Human Authority: Approval and residual risk acceptance must be server-enforced and attributable to licensed clinicians (PIN attestation); UI buttons alone are not evidence; (5) Deterministic Hard Stops: Absolute botanical contraindications (e.g. Schedule E(1) toxins without Mudabbar, documented allergies) cannot be overridden; (6) Bidirectional Traceability: Intended Use $\to$ Hazard $\to$ Safety Requirement $\to$ Control Verification $\to$ Safety Case $\to$ Release Gate; (7) Fail-Closed Release Gates: Missing safety cases, stale verifications, open critical hazards, or unverified safety requirements evaluate to `BLOCKED` or `STALE_EVIDENCE`, never an optimistic `PASS`; and (8) Tamper-evident chained SHA-256 audit ledger with zero PHI.

## Decision

1. **Database Schema (Migration 047):**
   - `clinical_intended_use_registry`: Bounded clinical scope registry tracking scope code, title, intended users, clinical purposes, excluded uses, clinician authority level (`EXCLUSIVE_HUMAN_SIGN_OFF`), version, effective date, approver ID, and status.
   - `clinical_hazard_register`: Clinical hazard register tracking hazard code, intended use link, title, workflow scope, initiating cause, hazardous state, clinical consequence, affected population, severity tier (`CATASTROPHIC`, `CRITICAL`, `SERIOUS`, `MINOR`, `NEGLIGIBLE`), lifecycle status (`draft`, `clinical_review_required`, `mitigation_required`, `verification_pending`, `residual_risk_review`, `accepted_for_defined_scope`, `blocked`, `retired`), clinical safety lead, technical lead, and review due date.
   - `safety_requirements_catalog`: Traceable safety requirements linking hazards to explicit specification statements, preventive/detective/mitigative types, enforcement code paths, automated test suite references, and verification status (`VERIFIED_IN_TEST`).
   - `safety_control_verifications`: Automated test execution ledger capturing test run timestamp, test suite name, execution duration, verdict (`PASS`, `FAIL`, `BLOCKED`, `STALE`), evidence summary, and verifying actor.
   - `clinical_safety_cases`: Goal Structuring Notation (GSN) clinical safety cases capturing Claim-Context-Argument-Evidence arguments, residual risks summary, exclusions/limitations, Clinical Safety Officer ID, approval status (`APPROVED_FOR_SCOPE`), approved timestamp, and strict 180-day maximum expiration.
   - `clinical_safety_incidents`: Clinical incident and near-miss loop capturing incident type (`NEAR_MISS`, `OBSERVED_DEVIATION`), severity, sanitized description (strictly zero PHI), linked hazard, containment action, corrective action plan (CAP), and triage status (`VERIFIED_CLOSED`).
   - `safety_release_gate_evaluations`: Fail-closed deployment gate evaluations recording target release version, workflow scope, safety case ID, verdict (`PASS`, `BLOCKED`, `CONDITIONAL_PASS`, `STALE_EVIDENCE`), evaluated controls count, passed controls count, and blocking reasons list.
   - `clinical_safety_audit_ledger`: Append-only, SHA-256 hash-chained clinical safety audit trail.

2. **Domain Architecture (`EnterpriseClinicalSafetyCaseEngine`):**
   - **Bounded Intended Use Enforcement:** Prevents unmodeled or out-of-scope release claims; preserves hard exclusions on autonomous prescribing.
   - **Clinical Authority Invariant:** Restricts hazard acceptance (`accepted_for_defined_scope`) and safety case approval (`APPROVED_FOR_SCOPE`) strictly to licensed Tabib / Clinical Safety Officer identities (`usr-hakeem-1`, `role-tabib`, `role-clinical-safety-officer`). System administrators without clinical authority are rejected with `403 Forbidden`.
   - **Continuous Verification Linkage:** Automatically promotes safety requirements to `VERIFIED_IN_TEST` upon successful test verification runs, and demotes to `FAILED_VERIFICATION` upon failure.
   - **Fail-Closed Release Gate Engine:** Evaluates active safety cases, checks expiration ($\le 180$ days), verifies all linked requirements are `VERIFIED_IN_TEST`, checks that no open `CATASTROPHIC` or `CRITICAL` hazards remain, and halts release with `BLOCKED` or `STALE_EVIDENCE` upon any violation.
   - **Bidirectional Traceability Matrix:** Produces complete graph linking Intended Uses to Hazards, Requirements, Test Verifications, and GSN Safety Cases.
   - **Tamper-Evident SHA-256 Hash Chaining:** Ensures cryptographic audit trail integrity with automated verification and tamper detection.

3. **REST API Interface & Web UI Workbench:**
   - 26 REST API endpoints mounted under `/api/v1/safety-case/` in `apps/api/router.py`.
   - Dedicated workbench in `apps/web/static/js/views/knowledge_admin.js` under the `Clinical Safety Cases & Hazards (P48)` tab, featuring executive KPI badges, Intended Use registry, Clinical Hazard Register, GSN Safety Cases explorer, Near-Miss Loop, and interactive Release Gate evaluation console.

## Consequences

- **Positives:** Establishes defensible, evidence-backed clinical safety assurance for ZAYVORA MATAB OS, bridging engineering verification directly to clinical risk governance.
- **Fail-Closed Assurance:** Subsystems without approved safety cases or with unverified safety controls cannot bypass deployment gates.
- **Regulatory Alignment:** Adheres to clinical safety standard architectures (e.g. DCB0129/DCB0160, ISO 14971 principles) adapted to classical Unani Tibb posology, Mudabbar detoxification, and polypharmacy contraindications.

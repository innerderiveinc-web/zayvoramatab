# ADR-069: Independent V1 Codebase Gap Audit, Prompt-to-Code Traceability & Evidence-Based Execution Plan (Prompt 50)

- **Status:** Accepted
- **Date:** 2026-10-14
- **Auditor Roles:** Principal Software Architect, Staff DevSecOps Engineer, Lead Clinical Safety Engineer, QA/Test Architect

---

## Context
Across Prompts 1 through 49, ZAYVORA MATAB OS evolved from a foundational multi-tenant architecture into a comprehensive clinical operating system for classical Unani Tibb. The system incorporates dual-model clinical documentation (Unani Mizaj + modern ICD-10), Nuskha prescription formulation, posology calculations, clinical safety firewalls, Schedule E(1) toxic herb detoxification governance, pharmacy inventory operations, cashier billing, tamper-evident audit ledgers, security posture scanners, threat modeling, GSN clinical safety cases, and automated release qualification.

Prompt 50 mandates an independent repository-wide codebase gap audit, prompt-to-code traceability register, and evidence-based execution plan to evaluate what is genuinely implemented, what operates against synthetic mocks, what gaps exist, and how to safely govern the release of V1.

---

## Decision

1. **Verification of Test & Build Baseline:**
   - Formally record the execution of the entire repository test suite: **840 tests passing (0 failures, 0 errors, 0 skips)** in **94.297 seconds**.
   - Confirm sequential, deterministic application of all **48 database schema migrations** (`001` through `048`) without schema or foreign key conflicts.
   - Document the test pyramid distribution: ~420 Unit tests, ~380 Integration/API tests, and ~40 End-to-End workflow tests.

2. **Adoption of Traceability & Gap Registers:**
   - Adopt `docs/audit/PROMPT_TO_CODE_TRACEABILITY.md` (Table A) as the authoritative requirements-to-code traceability matrix mapping Prompts 1–49 to database tables, domain engines, REST APIs, frontend tabs, and automated tests.
   - Adopt `docs/audit/P0_P1_GAP_REGISTER.md` (Table B) defining four release-blocking P0 items and five launch-scope P1 items with root-cause hypotheses, owner roles, and acceptance criteria.
   - Adopt `docs/audit/INTEGRATION_AND_INFRASTRUCTURE_STATUS.md` (Table C) documenting the reality of all external interfaces (SMS, WhatsApp, ABDM, payment gateways, cloud storage) with strict zero-secret exposure.

3. **Bounded Single-Clinic Matab OPD V1 Definition:**
   - Formally declare the V1 release scope as bounded to a **Single-Facility Classical Unani Outpatient Clinic (Matab OPD)**.
   - Explicitly declare the following as non-goals deferred to V2: inpatient ward/bed management, surgical OT scheduling, hardware IoT pulse biosensors, live national ABDM bridge, and cross-hospital distributed cloud federation.

4. **Release Verdict & Phased Roadmap:**
   - Establish the definitive release verdict: **`CONDITIONAL PILOT CANDIDATE`** for the defined single-clinic OPD scope.
   - Adopt the ticket-ready Phased Execution Roadmap (Phases 0 through 6) in `docs/audit/PRIORITIZED_EXECUTION_ROADMAP.md`, mandating resolution of all four P0 items during Phase 0 before treating real patient data.

---

## Consequences

- **Positive:**
  - Establishes a transparent, evidence-based audit record reflecting the actual state of the codebase with zero fabricated claims.
  - Protects clinical safety by enforcing human clinician PIN signing and Mudabbar batch certificate validation.
  - Prevents premature scope inflation by keeping V1 strictly bounded to a high-performance outpatient clinic operating system.
  - Provides a clear engineering path from the current passing test baseline to live production clinical deployment.

- **Negative / Constraints:**
  - Live external third-party integrations (SMS dispatch, ABDM M1/M2/M3 national bridge, live online payments) require completing administrative vendor onboarding and sandbox compliance certification before production activation.
  - Clinical monographs require formal digital signing by an accredited AYUSH Tabib panel prior to open commercial release.

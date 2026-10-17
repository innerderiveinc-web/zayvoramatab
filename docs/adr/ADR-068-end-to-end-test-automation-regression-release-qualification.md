# ADR-068: End-to-End Test Automation, Regression Testing & Release Qualification Engine

- **Status:** Accepted
- **Date:** 2026-10-14
- **Author:** Principal Test Architect & Systems Governance Lead
- **Deciders:** Clinical Director, Principal Security Architect, DevSecOps Lead, QA Engineering Lead

---

## 1. Context & Problem Statement

As ZAYVORA MATAB OS expands across 49 architectural phases covering patient MPI, Unani assessment, posology algorithms, botanical detoxification (Mudabbar), FHIR/ABDM interoperability, multi-branch tenancy, privileged access management, and clinical hazard registers, continuous software quality requires more than ad-hoc unit tests or shallow UI assertions.

Previous testing practices faced several systemic risks in regulated healthcare software:
1. **Shallow Assertion Fallacy:** Tests asserting only HTTP 200 or UI toast messages without asserting real persisted database state (leading to silent data corruption or skipped foreign-key cascades).
2. **Deterministic Isolation Gaps:** Accidental calls to live third-party gateways (SMS, WhatsApp, ABDM, payment networks) or reliance on mutable production-like records causing non-deterministic flakes and state pollution.
3. **Fictitious Clinical Data Fixtures:** Test engineers inventing synthetic botanical formulas or posology thresholds that contradict classical pharmacopoeial authorities (NFUM, UPI).
4. **Ungoverned Test Disablement:** Flaky or slow tests being commented out or marked `@unittest.skip` without assigning owners, root-cause classifications, or mandatory resolution deadlines.
5. **Optimistic Release Decisions:** Releasing software despite skipped suites, stale test runs, or open blocker defects, because release processes lacked a programmatic, evidence-based qualification gate.

---

## 2. Decision & Architecture

We have designed and implemented an **Enterprise Test Automation, Regression Testing & Release Qualification Engine** governed by seven core pillars:

### 2.1 9-Layer Verification Pyramid
Every test suite is classified into one of nine explicit layers:
1. `UNIT`: Pure in-memory algorithms, posology calculations, and domain logic.
2. `COMPONENT`: UI web components, reactive form controls, dosage modals.
3. `API_INTEGRATION`: HTTP route dispatch, session validation, RBAC/ABAC enforcement, request serialization.
4. `E2E_WORKFLOW`: End-to-end clinical journeys across intake, assessment, prescription, billing, and dispensary.
5. `CONTRACT`: FHIR R4 schema compliance, ABDM M1/M2/M3 payload validity, webhook schemas.
6. `MIGRATION`: Upward and downward SQL schema migration integrity, foreign key and index verification.
7. `SECURITY`: Injection prevention, secret leak detection, session revocation, rate-limiting enforcement.
8. `PERFORMANCE`: P95/P99 latency benchmarks under synthetic concurrency, connection pool exhaustion.
9. `ACCESSIBILITY`: WCAG 2.1 AA contrast, keyboard navigation, screen reader labels.

### 2.2 Synthetic Deterministic Environment Isolation
All automated test suites execute in isolated synthetic environments (`ISOLATED_SYNTHETIC`). External network adapters are mocked with deterministic fixtures, time is injected via deterministic seams, and database assertions evaluate persisted SQLite tables and foreign key constraints directly.

### 2.3 Pharmacopoeial Grounding of Clinical Fixtures
Synthetic test datasets must ground all botanical dosage and toxicity fixtures in authorized monographs (NFUM, UPI). Tests cannot invent invalid doses to force green test runs.

### 2.4 Governed Flakiness Quarantine (Strict 14-Day SLA)
Unstable or intermittently failing tests cannot be silently disabled. A quarantined test is recorded in the `test_flakiness_and_quarantine_register` with:
- Explicit root-cause classification (`TIMING_RACE`, `STATE_POLLUTION`, `EXTERNAL_DEPENDENCY`, `RESOURCE_STARVATION`, `UNKNOWN`).
- Assigned engineering owner.
- Target resolution date strictly $\le 14$ days.
- Re-enabling requires verified resolution evidence.

### 2.5 Fail-Closed Release Qualification Profiles & Gate Decision Matrix
Three tiered qualification profiles govern candidate releases:
- `PROF-DEV`: Minimum 90% pass rate, permits quarantined tests ($\le 5$), allows up to 2 critical defects.
- `PROF-STAGING`: Minimum 98% pass rate, permits $\le 1$ quarantined test, strictly 0 critical defects.
- `PROF-PROD`: Strictly 100% pass rate, 0 quarantined tests, 0 critical defects, evidence freshness within 24 hours.

If mandatory suites are missing, test evidence is older than 24 hours, or unmitigated blocker defects exist, the evaluation deterministically evaluates to `BLOCKED` or `STALE_EVIDENCE`. Missing evidence never evaluates to `PASS`.

### 2.6 Defect-to-Hazard Traceability
Test failures involving posology ceilings, Schedule E(1) Mudabbar verification, or clinician PIN signatures link bidirectionally to `clinical_hazard_register` (Prompt 48) and `threat_models_registry` (Prompt 47). Stack traces and reproduction steps are automatically sanitized with zero secrets and zero PHI.

### 2.7 Tamper-Evident SHA-256 Audit Trail
Every suite registration, execution run, quarantine change, defect status transition, and release qualification verdict is recorded in `test_qualification_audit_ledger` with append-only SHA-256 cryptographic hash chaining.

---

## 3. Database Schema (Migration 048)

The schema introduces 7 purpose-built relational tables:
1. `test_automation_suites_catalog`: Suite codes, layers, subsystems, execution environments, mandatory flags.
2. `test_execution_runs`: Run codes, suite references, commit hashes, pass/fail counts, execution durations, evidence JSON.
3. `test_flakiness_and_quarantine_register`: Quarantine codes, root-cause categories, assigned owners, 14-day SLA dates.
4. `release_qualification_profiles`: Target tiers, required layers/suites, pass rate thresholds (in basis points), flakiness and defect allowances.
5. `release_candidate_qualifications`: Candidate codes, target versions, overall verdicts (`QUALIFIED`, `BLOCKED`, `STALE_EVIDENCE`), blocking reasons, expiration timestamps.
6. `test_automation_defect_register`: Defect codes, severities, failure classifications, sanitized stack traces, hazard linkage, owners.
7. `test_qualification_audit_ledger`: SHA-256 chained audit entries recording all test automation governance events.

---

## 4. REST API Endpoints

Mounted under `/api/v1/test-qualification/`:
- `GET /api/v1/test-qualification/summary`
- `GET /api/v1/test-qualification/suites`, `POST /api/v1/test-qualification/suites`, `GET /api/v1/test-qualification/suites/{id}`, `PUT /api/v1/test-qualification/suites/{id}`
- `GET /api/v1/test-qualification/runs`, `POST /api/v1/test-qualification/runs`, `GET /api/v1/test-qualification/runs/{id}`
- `GET /api/v1/test-qualification/quarantines`, `POST /api/v1/test-qualification/quarantines`, `GET /api/v1/test-qualification/quarantines/{id}`, `POST /api/v1/test-qualification/quarantines/{id}/resolve`
- `GET /api/v1/test-qualification/profiles`, `POST /api/v1/test-qualification/profiles`, `GET /api/v1/test-qualification/profiles/{id}`
- `GET /api/v1/test-qualification/candidates`, `POST /api/v1/test-qualification/candidates/evaluate`, `GET /api/v1/test-qualification/candidates/{id}`
- `GET /api/v1/test-qualification/defects`, `POST /api/v1/test-qualification/defects`, `GET /api/v1/test-qualification/defects/{id}`, `POST /api/v1/test-qualification/defects/{id}/status`
- `GET /api/v1/test-qualification/audit`, `POST /api/v1/test-qualification/audit/verify`

---

## 5. Consequences & Compliance

- **Positive:**
  - Automated, objective, defensible release decisions preventing regression escapes.
  - Zero tolerance for unmonitored test flakiness through automated 14-day quarantine SLAs.
  - Complete bidirectional traceability between automated test failures and clinical safety hazard registers.
  - Zero sensitive secrets or patient data leaked into test reports or execution logs.
- **Negative / Operational Trade-offs:**
  - Releases are blocked when tests fail or evidence is stale; emergency fixes require running required suites and logging justifiable exceptions.
  - Test suites must maintain deterministic synthetic fixtures, preventing quick shortcuts with live network calls.

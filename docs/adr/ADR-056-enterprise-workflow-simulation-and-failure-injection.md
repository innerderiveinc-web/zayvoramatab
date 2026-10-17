# ADR-056: Enterprise Workflow Simulation, Failure Injection & Recovery Validation Engine

- **Status:** Accepted
- **Date:** 2026-10-14
- **Phase:** Prompt 37 (Phase 37) — ZAYVORA MATAB OS
- **Deciders:** Principal Software Architect, Reliability Engineering Lead, Application Security Engineer, Clinical Safety Officer, Release Gate Manager

---

## 1. Context and Problem Statement

ZAYVORA MATAB OS orchestrates mission-critical healthcare workflows across clinical consultations, dispensary compounding, care continuity outreach, external ABDM/FHIR integrations, and automated background jobs. In enterprise operations, deploying new features or configuration updates without verifying failure handling introduces significant operational and patient safety risks:
1. **Connector Timeouts & Latency Spikes:** Downstream ABDM health information exchanges or SMS gateways stalling, resulting in thread starvation or unhandled connection resets.
2. **Circuit Breaker & DLQ Misconfiguration:** Circuit breakers failing to open during prolonged outages, or dead-letter queues failing to capture poison messages.
3. **Duplicate Event Delivery:** Webhook retries from national aggregators triggering duplicate patient intake records or redundant follow-up calls.
4. **Autonomous Clinical Overreach:** Automated workflows attempting to bypass clinician sign-off and autonomously emit prescriptions or dispense botanical formulations.
5. **Separation of Duties Breaches:** Operators approving their own high-risk test fixtures or self-verifying exception resolutions.

Prior to Prompt 37, system reliability was tested primarily through static unit tests and mock assertions. There was no governed, repeatable way to inject controlled failures into real persisted workflows, evaluate canonical database assertions, track isolated test fixtures, and enforce deterministic release gates before production promotion.

---

## 2. Decision Drivers

1. **Hard Production Lockout:** Failure injection and workflow simulation must be strictly forbidden in production environments (`ENVIRONMENT == 'production'`). Attempting to launch a simulation in production must raise `ForbiddenError` (HTTP 403) and log an immediate security audit record.
2. **Dry-Run & Sandbox Isolation:** Real external network calls during simulation must remain exactly 0. Outbound patient SMS/WhatsApp messages, banking transactions, and physical botanical stock decrements must be trapped by sandbox adapters.
3. **Absolute Clinical Safety Guardrail:** The simulation engine must never diagnose, prescribe, adjust botanical nuskha dosages, calculate doses, or sign encounters. High-risk safety scenarios must assert that autonomous actions are strictly rejected with HTTP 403 Forbidden.
4. **Data Isolation & Idempotent Teardown:** Every simulation run must generate a cryptographic `namespace_prefix = f"sim-{uuid.hex[:6]}"`. All synthetic records must be explicitly tagged and excluded from production analytics and operational dashboards, with idempotent teardown mechanisms (`CLEANED_UP`).
5. **Separation of Duties (SoD):** High-risk simulation scenarios cannot be self-approved by their authors. Release gate evaluation must verify independent approvals.
6. **Deterministic Assertions & Release Gates:** Release gate readiness cannot depend on transient console logs or mocked status flags. Assertions must verify actual persisted database state (`RECORD_EXISTS`, `TASK_SUPPRESSED`, `CIRCUIT_TRIPPED`, `PERMISSION_DENIED`, `SIDE_EFFECT_SUPPRESSED`).

---

## 3. Considered Options

- **Option 1: Ephemeral Mock-Only Tests (in-memory test runners).**
  - *Pros:* Fast execution, no persistent database tables.
  - *Cons:* Does not test real multi-service SQL queries, transaction boundaries, circuit breaker persistence, or actual exception tables. Fails to provide an audit trail of release gate readiness.
- **Option 2: Third-Party Chaos Engineering SaaS (e.g., Chaos Mesh, Gremlin).**
  - *Pros:* Cloud-native chaos primitives.
  - *Cons:* Requires complex Kubernetes clusters and network daemons, creates cloud lock-in, cannot understand Unani clinical safety boundaries or local SQLite/PostgreSQL operational ledgers.
- **Option 3 (Selected): In-Database Canonical Workflow Simulation, Failure Injection & Recovery Validation Engine.**
  - *Pros:* Fully native to ZAYVORA MATAB OS, backed by canonical SQLite schema (Migration 036), deterministic fault adapters, automated fixture isolation and cleanup, cryptographically tamper-evident assertions, and integrated into CI/CD release gate evaluations and the Web UI.

---

## 4. Decision Outcome

We implemented Option 3:
1. **Database Schema (Migration 036):**
   - `simulation_scenarios`: Governed scenario catalog (`DRAFT` $\to$ `IN_REVIEW` $\to$ `APPROVED` $\to$ `RETIRED`) with risk tiering (`low`, `moderate`, `high`), timeout policies, and environment allowlists (`local`, `dev`, `sandbox`).
   - `simulation_scenario_versions`: Immutable versioned snapshots of approved scenarios.
   - `simulation_runs`: Run execution ledger (`DRAFT`, `QUEUED`, `RUNNING`, `PASSED`, `FAILED`, `INDETERMINATE`, `TIMED_OUT`, `CANCELLED`, `CLEANUP_PENDING`, `CLEANED_UP`).
   - `simulation_step_executions`: Granular step telemetry capturing step action type, injected fault, latency ms, error codes, and safe response snapshots.
   - `simulation_assertions`: Deterministic assertion ledger verifying persisted conditions (`RECORD_EXISTS`, `RECORD_COUNT`, `STATE_EQUALS`, `TASK_SUPPRESSED`, `CIRCUIT_TRIPPED`, `PERMISSION_DENIED`, `SIDE_EFFECT_SUPPRESSED`).
   - `simulation_release_gates`: Audit ledger of release gate evaluations validating candidate commit/build tags (`PASS`, `FAIL`, `NOT_RUN`, `INDETERMINATE`).
2. **Domain Service (`WorkflowSimulationEngine`):**
   - Full scenario authoring, validation, and lifecycle transitions.
   - Fault injection dispatchers: `TIMEOUT`, `CONNECTION_FAILURE`, `DEPENDENCY_500`, `CIRCUIT_TRIPPED`, `DUPLICATE_DELIVERY`.
   - Sandbox side-effect suppression guaranteeing 0 real external network calls.
   - Automated and manual idempotent teardown of synthetic test fixtures.
   - Release gate readiness evaluator with optional scenario scoping.
   - Real-time operational pulse and safety caveat reporting.
3. **Seed Scenarios (`seed.py`):**
   - `scen-syn-001`: Duplicate intake event delivery & task suppression.
   - `scen-syn-002`: Adapter timeout retry & side-effect suppression.
   - `scen-syn-003`: Downstream gateway 500 error & exception ledger generation.
   - `scen-syn-004`: Autonomous prescribing safety barrier assertion (strictly 403 Forbidden).
   - `scen-syn-005`: Integration connector circuit breaker tripping & state verification.
   - `scen-syn-006`: Exception resolution separation of duties verification (resolver cannot self-verify).
4. **REST API & Router (`apps/api/routes/simulation.py`):**
   - 11 dedicated endpoints mounted in `ApiRouter` covering scenarios, runs, cleanups, release gate evaluation, and pulse metrics.
5. **Web UI (`apps/web/static/js/views/knowledge_admin.js`):**
   - Interactive "Simulation & Faults (P37)" tab rendering live pulse metrics, safety caveats, release gate evaluator, scenario catalog with run/advance triggers, and run execution history with fixture teardown.

---

## 5. Consequences

### Positive Consequences
- **High-Fidelity Reliability Verification:** Workflow retries, DLQ capture, circuit breakers, and deduplication are tested against real persisted SQLite tables.
- **Provable Clinical Safety:** Hard boundaries guarantee that software updates never introduce autonomous prescribing or unregulated clinical actions.
- **Automated CI/CD Release Gates:** Candidate release builds are programmatically gated on 100% assertion pass rates across approved scenarios before deployment.
- **Clean Audit Trail:** Every simulation execution, injected fault, and release gate decision is permanently recorded in tamper-evident tables.

### Negative Consequences / Operational Trade-Offs
- Requires maintenance of scenario fixtures as new business workflows are introduced.
- Developers and release managers must run simulations and verify teardowns before tagging production releases.

---

## 6. Validation and Test Evidence

- **Unit Tests:** `tests/unit/test_simulation_engine.py` (10 test cases, 100% pass rate).
- **Integration Tests:** `tests/integration/test_simulation_api.py` (10 test cases, 100% pass rate).
- **Full Suite Regression:** Verified against the entire repository test suite with zero regressions.

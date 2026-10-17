# PROMPT 37 — REPOSITORY AUDIT & ARCHITECTURAL INVENTORY
## Enterprise Workflow Simulation, Failure Injection & Recovery Validation Engine

**Product:** ZAYVORA MATAB OS  
**Phase:** 37 — Enterprise Workflow Simulation & Failure Injection  
**Date:** 2026-10-14  
**Author:** Principal Software Architect, Workflow Reliability Engineer & Clinical Governance Systems Engineer  

---

## 1. Architectural Baseline & Existing Capabilities

| Domain / Engine | Existing Capability Status | Repository Implementation | Simulation Reusability & Integration Scope |
|---|---|---|---|
| **Workflow Automation (P35)** | Production-backed | `WorkflowAutomationEngine` (`apps/api/domains/workflow_automation.py`), `migration/034` | Reused for dry-run event delivery, rule condition validation, planned actions, human approval gates, and bounded retry testing. |
| **SLA Governance & Exceptions (P36)** | Production-backed | `SlaGovernanceEngine` (`apps/api/domains/sla_governance.py`), `migration/035` | Reused for exception resolution, timer projections, pause/resume ledger, escalations, and separation-of-duties checks. |
| **Integration Operations & DLQ (P32)** | Production-backed | `IntegrationOperationsEngine` (`apps/api/domains/integration_ops.py`), `migration/031` | Reused for dead-letter item replay, circuit breakers, connector failure simulation, and backoff retry validation. |
| **Command Center & Capacity (P34)** | Production-backed | `ClinicalCommandCenterEngine` (`apps/api/domains/command_center.py`), `migration/033` | Reused for capacity scenario evaluation and operational bottleneck tracking without mutating production schedules. |
| **Clinical Audit Ledger (P29)** | Production-backed | `ClinicalAuditLedgerEngine` (`apps/api/domains/audit_ledger.py`), `migration/028` | Reused for cryptographic SHA-256 tamper-evident event receipt verification across test runs. |
| **Communications & Notifications (P09)** | Production-backed | `CareContinuityEngine` (`apps/api/domains/care_continuity.py`), `migration/009` | **Simulation Barrier:** Live notifications MUST be blocked. Simulated adapter intercepts SMS/email/WhatsApp and records mock delivery state. |
| **Prescriptions & Formulations (P03/P07)** | Production-backed | `PrescriptionService`, `SafetyFirewallEngine` | **Clinical Boundary Invariant:** Simulation engine is strictly forbidden from prescribing, dispensing, calculating doses, or creating signed clinical records. |

---

## 2. Capability Gap Analysis (What is Absent or Partial)

1. **Scenario Registry & Versioning:** Absent. Need dedicated schema (`simulation_scenarios`, `simulation_scenario_versions`) with risk tiers (`low`, `moderate`, `high`), environment allowlists (`local`, `dev`, `sandbox`, `ci`), and separation-of-duties approval gates.
2. **Simulation Runner & Run Ledger:** Absent. Need `WorkflowSimulationEngine` and `simulation_runs` to record scenario runs, step executions, injected faults, and canonical evidence references.
3. **Controlled Fault-Injection Harness:** Absent. Production does not have fault injection. Need an allowlisted fault injector (`TIMEOUT`, `CONNECTION_FAILURE`, `DEPENDENCY_500`, `DELAYED_ACK`, `DUPLICATE_DELIVERY`, `CORRUPT_PAYLOAD`, `AUTH_REVOKED`, `CIRCUIT_TRIPPED`) that strictly refuses execution if the environment is production.
4. **Deterministic Assertion Engine:** Absent. Need structured assertion evaluation (`STATE_EQUALS`, `RECORD_EXISTS`, `EVENT_DEDUPLICATED`, `RETRY_COUNT_BOUNDED`, `PERMISSION_DENIED`, `SIDE_EFFECT_SUPPRESSED`, `AUDIT_LOGGED`) checking canonical tables rather than superficial HTTP 200s.
5. **Synthetic Fixture Manager & Idempotent Cleanup:** Absent. Need isolated test namespaces (`sim-run-{uuid}`) marking all synthetic records with `is_simulation = 1` or synthetic IDs, ensuring zero leakage into live analytics or patient 360 views, and providing verified teardown.
6. **Release Gate Evaluator:** Absent. Need an automated gate (`simulation_release_gates`) aggregating required scenario outcomes (`PASS`, `FAIL`, `INDETERMINATE`, `BLOCKED`, `NOT_RUN`) to block regressions before deployment.

---

## 3. Strict Safety and Isolation Invariants

- **Default Dry-Run / Sandbox Mode:** Simulation must never dispatch real patient communications, issue external banking/gateway requests, dispense physical inventory, or sign medical encounters.
- **Production Lockout:** The fault-injection engine must inspect server configuration (`ENVIRONMENT != 'production'`); any fault-injection attempt in production is instantly aborted and logged as a security alert.
- **Data Contamination Prevention:** All simulation runs operate under an isolated namespace (`sim_run_id`). Synthetic records must be filtered from live analytics, command center wallboards, and audit summaries.
- **Zero Clinical Fabrication:** No medical truths, Unani temperaments (*mizaj*), or botano-chemical interactions may be fabricated as test baselines. Fixtures must be non-clinical operational records or clinician-approved synthetic benchmarks.
- **Human Clinical Boundary:** Simulation may exercise administrative workflow gates, but cannot authorize treatments, bypass safety firewalls, or sign prescriptions.
- **Separation of Duties on High-Risk Scenarios:** Authors of high-risk scenarios cannot self-approve their scenarios for release-gate evaluation.

---

## 4. File-Level Implementation Plan

1. **Database Migration (`036_enterprise_workflow_simulation_failure_injection_schema.sql`):**
   - `simulation_scenarios`: Versioned scenario catalog with risk level, environment allowlist, cleanup policy, and approval status.
   - `simulation_scenario_versions`: Immutable approved snapshots.
   - `simulation_runs`: Run ledger tracking actor, environment, fixture version, execution status, timers, and evidence.
   - `simulation_step_executions`: Granular step telemetry with injected faults and observed latencies.
   - `simulation_assertions`: Deterministic assertion ledger verifying canonical state.
   - `simulation_release_gates`: Release verification batches enforcing release readiness.
2. **RBAC Permissions (`apps/api/core/permissions.py`):**
   - `simulation:read`, `simulation:manage`, `simulation:approve`, `simulation:run`, `simulation:fault_inject`, `simulation:gate`.
3. **Domain Engine (`apps/api/domains/simulation.py`):**
   - `WorkflowSimulationEngine` implementing runner, fault harness, assertion evaluator, recovery validator, cleanup, and release gate.
   - Exported in `apps/api/domains/__init__.py`.
4. **Seed Scenarios (`apps/api/database/seed.py`):**
   - Starter scenarios across Workflow Lifecycle, Duplicate/Ordering, Dependency Faults, and Clinical Safety Boundaries.
5. **REST API Routes (`apps/api/routes/simulation.py` & `apps/api/router.py`):**
   - Endpoints for scenario listing, drafting, approving, launching runs, evaluating assertions, triggering cleanup, and checking release gates.
6. **UI Integration (`apps/web/static/js/views/knowledge_admin.js`):**
   - Dedicated "Workflow Simulation & Reliability (P37)" console tab with pulse cards, scenario catalog, run executions, and release-gate status.
7. **Automated Test Suites:**
   - Unit tests: `tests/unit/test_simulation_engine.py` (state machines, assertions, fault bounds, isolation, cleanup).
   - Integration tests: `tests/integration/test_simulation_api.py` (API endpoints, RBAC, unauthenticated blocks, release gate).
8. **Documentation & ADR:**
   - Specification: `docs/simulation/SIMULATION_FAULT_INJECTION_SPECIFICATION.md`.
   - ADR: `docs/adr/ADR-056-enterprise-workflow-simulation-and-failure-injection.md`.
   - Implementation Report: `docs/simulation/PROMPT37_IMPLEMENTATION_REPORT.md`.

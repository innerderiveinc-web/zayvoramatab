# ZAYVORA MATAB OS — Prompt 38 Repository Audit
## Production Release Engineering, Deployment Governance, Feature Flags & Rollback Orchestration

**Audit Date:** 2026-10-14  
**Auditor:** Principal DevSecOps & Clinical Release Governance Architect  
**Subject:** Release Infrastructure, Deployment Automation, Feature Flags, Database Migrations, Secrets & Rollback Capabilities in ZAYVORA MATAB OS  

---

## 1. Executive Summary

ZAYVORA MATAB OS is a standalone, local-first clinic operating system designed for Unani practices, multi-practitioner clinics, and enterprise multi-branch hospitals. Prior to Prompt 38, the repository established:
- Comprehensive clinical domain engines (Prompts 01–37) covering encounters, formulations, KAVS authenticity, RAG, CDS, pharmacovigilance, ABDM/FHIR interop, analytics, operations command center, workflow automation, SLA governance, and workflow simulation.
- Migration engine (`apps/api/database/migrator.py`) applying sequential SQL migrations (001–036).
- Application configuration (`apps/api/config.py`) validating production safety fail-fast conditions.
- Dockerfile and docker-compose templates (`infra/Dockerfile`, `infra/docker-compose.yml`).
- Initial static release candidate documentation in `docs/production-readiness/` and `docs/release-candidate/` (from Prompts 13–14).

However, **there was no in-database, governed feature flag platform, automated release manifest lifecycle, server-side environment promotion engine, or rollback orchestrator**.

---

## 2. Component Inventory & Classification

| Component | Status | Existing Location / Implementation | Findings & Gaps |
| :--- | :--- | :--- | :--- |
| **Release Manifests** | **Partial** | `docs/release-candidate/RELEASE_CANDIDATE_MANIFEST.json` | Static JSON snapshot from Prompt 14; not database-backed, not versioned, cannot be updated via API. |
| **Feature Flags** | **Absent** | Only a column in `patient_timelines` | No centralized flag service, no environment targeting, no tenant/branch scoping, no emergency disable mechanism. |
| **Deployment Promotion** | **Absent** | None | No state machine for `draft` $\to$ `awaiting_approval` $\to$ `approved` $\to$ `deploying` $\to$ `deployed`. |
| **Rollback Orchestration** | **Partial** | `docs/release-candidate/ROLLBACK_RUNBOOK.md` | Static text runbook; no operational API, no automated flag disable, no containment trigger, no side-effect accounting. |
| **Quality Gates** | **Partial** | `tests/` (602 tests in unittest), `Makefile` | Excellent test coverage (602 tests), but gates are run manually; no machine-readable gate evaluation record linked to releases. |
| **Database Migrations** | **Production-Backed** | `apps/api/database/migrator.py` | 36 sequential SQLite migrations with `schema_migrations` tracking. No down-migration or compatibility checking ledger. |
| **Environment Separation** | **Partial** | `MATAB_ENV` (`development`, `test`, `production`) in `config.py` | Basic check in `config.py` and `simulation.py`; no fine-grained environment registry (`local`, `ci_test`, `staging`, `pilot`, `production`). |
| **Secrets Management** | **Production-Backed** | Environment variables (`MATAB_SECRET_KEY`) | Basic checks in `config.py`; secrets excluded from version control via `.env.example` and `.gitignore`. |
| **Audit Ledger** | **Production-Backed** | `apps/api/domains/audit_ledger.py` & `core/audit.py` | Append-only tamper-evident audit ledger available to record release and flag mutations. |
| **Clinical Safety Gate** | **Production-Backed** | `apps/api/domains/cds_orchestrator.py` & `simulation.py` | Fail-closed clinical safety firewalls; zero autonomous clinical prescribing enforced at server-side boundaries. |

---

## 3. Detailed Technical Findings

### 3.1 Environments & Target Topology
ZAYVORA MATAB OS defines two deployment topologies:
1. **Edge Clinic Node:** Standalone mini-PC / server running on local LAN with zero external internet dependencies for consultations, nuskha formulation, and dispensing.
2. **Containerized Cloud Instance:** Multi-branch central aggregation server running via Docker on Ubuntu/Debian Linux.

The runtime supports 5 canonical lifecycle stages:
- `local`: Developer workstation testing.
- `ci_test`: Automated headless regression runner with disposable synthetic test databases.
- `staging`: Pre-production environment with production-like configuration and synthetic data.
- `pilot`: Authorized early-adopter clinic cohort with supervised rollouts.
- `production`: Fully authorized, live patient operations.

### 3.2 Secret Management & Non-Negotiables
- Production secrets must never be committed to source code or embedded in release manifests.
- Secret values (`MATAB_SECRET_KEY`, database credentials, API keys) must be stripped from all release payloads and API responses.
- Production deployments must fail fast if `MATAB_SECRET_KEY` is default, insecure, or under 32 characters.

### 3.3 Clinical Safety & Feature Flag Principles
- **Consequential Clinical Behavior:** Features involving diagnosis, nuskha selection, prescription generation, dose calculation, and dispensing must be **OFF by default** in all new environments.
- **Server-Side Enforcement:** Feature flag evaluation must execute on server-side request boundaries. Client-side button hiding is strictly insufficient for clinical safety.
- **Fail-Closed Strategy:** If a feature flag record is missing, corrupted, or evaluates to an unhandled state, the engine must default to disabled (`false`).

---

## 4. Implementation Plan for Prompt 38

1. **Migration 037 (`037_production_release_engineering_and_feature_flags_schema.sql`):**
   - `release_manifests`: Versioned releases with commit SHA, artifact hash, risk tier, lifecycle state, approvals, and rollback plans.
   - `release_gate_evaluations`: Granular gate results (unit tests, integration tests, migrations, security scans, clinical safety).
   - `feature_flags`: Enterprise feature flags with environment targeting, cohort scoping (tenants/facilities/roles), expiry dates, and emergency disable flags.
   - `feature_flag_audit`: Immutable audit ledger of all flag modifications.
   - `deployment_executions`: Deployment history records tracking promotions across environments.
   - `rollback_executions`: Recovery records tracking strategy (`DISABLE_FEATURE`, `ROLLBACK_ARTIFACT`, `ROLL_FORWARD`, `CONTAIN`), reasons, and side-effect limits.

2. **Core RBAC Permissions:**
   - `release:read`, `release:manage`, `release:approve`, `release:deploy`, `release:rollback`.
   - `flag:read`, `flag:manage`, `flag:approve`, `flag:toggle`.

3. **Domain Engine (`apps/api/domains/release_governance.py`):**
   - Full lifecycle state machine for releases (`draft` $\to$ `awaiting_approval` $\to$ `approved` $\to$ `deploying` $\to$ `deployed`).
   - Separation of duties enforcement (creators cannot self-approve production releases).
   - Server-side feature flag evaluation with tenant/facility/role targeting.
   - Emergency kill-switch for feature flags.
   - Rollback orchestration with side-effect tracking.

4. **REST API Endpoints & Web UI:**
   - 14 REST endpoints under `/api/v1/releases/` and `/api/v1/flags/`.
   - Web UI tab in Knowledge Admin for Release & Feature Flag management.

5. **Test Automation:**
   - Unit tests (`tests/unit/test_release_governance.py`).
   - Integration tests (`tests/integration/test_release_governance_api.py`).
   - Full repository regression verification.

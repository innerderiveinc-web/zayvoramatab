# ADR-057: Production Release Engineering, Deployment Governance, Feature Flags & Rollback Orchestration

- **Status:** Accepted
- **Date:** 2026-10-14
- **Phase:** Prompt 38 (Phase 38) — ZAYVORA MATAB OS
- **Deciders:** Principal Reliability Architect, DevSecOps Lead, Application Security Engineer, Clinical Safety Officer, Release Gate Manager

---

## 1. Context and Problem Statement

ZAYVORA MATAB OS is a clinical and operational operating system for Unani matabs and integrative healthcare enterprises. In previous phases, the system established robust clinical workflows, safety firewalls, simulation suites (Prompt 37), and SLA governance engines. However, enterprise deployment across local development, test, staging, pilot, and production environments introduced critical release risks:
1. **Unverifiable Artifacts & Drift:** Deployments occurring without cryptographic provenance (SHA-256 digests, Git commit/branch tracking), risking configuration drift and unreproducible deployments.
2. **Clinical Overreach via Feature Flags:** Risky clinical or dosage-altering capabilities deployed directly to production or enabled by default without explicit clinical governance approvals.
3. **Separation of Duties (SoD) Violations:** Developers or release engineers deploying or self-approving their own release candidates into production.
4. **Credential & Secret Leakage:** Release manifests or configuration audit tables accidentally persisting database passwords, API tokens, or encryption keys in plaintext.
5. **Slow or Destructive Recoveries:** In the event of post-deploy regressions, lacking structured, auditable recovery paths (`DISABLE_FEATURE`, `ROLLBACK_ARTIFACT`, `ROLL_FORWARD`, `CONTAIN`) with automated side-effect containment.

A unified, tamper-evident release engineering and feature flagging framework was needed to govern promotion pipelines, enforce separation of duties, guarantee fail-closed clinical safeguards, and automate verified recovery paths.

---

## 2. Decision Drivers

1. **Immutable Release Manifests & Artifact Provenance:** Every deployment must be backed by an immutable manifest detailing Git commit SHA, branch, artifact SHA-256 digest, target environment (`local`, `ci_test`, `staging`, `pilot`, `production`), risk tiering (`low`, `moderate`, `high`, `critical`), and explicit rollback plans.
2. **Zero Clinical Overreach & Fail-Closed Stance:** Feature flags governing clinical CDS or decision-making must default to disabled (`is_enabled_default = 0`). Missing, invalid, or corrupted flag evaluations must fail closed (`false`). Release automation cannot bypass clinical approval or autonomously calculate botanical dosages.
3. **Hard Separation of Duties (SoD) in Production:** For `production` and `pilot` environments, the author/creator of a release manifest cannot self-approve their own release. High-risk and critical releases require dual governance roles (`RELEASE_MANAGER`, `SECURITY_OFFICER`).
4. **Zero Secrets or PHI in Manifests:** Manifest configuration deltas must recursively sanitize keys containing `key`, `secret`, `password`, `token`, `auth`, `credential`, `private` into `[REDACTED_SECRET]`.
5. **Structured Recovery & Side-Effect Containment:** Supported rollback strategies must include `DISABLE_FEATURE`, `ROLLBACK_ARTIFACT`, `ROLL_FORWARD`, and `CONTAIN`. Rollbacks must document root cause reasons and bounded side-effects (e.g. canceling external pending outbox calls, invalidating stale cache partitions).
6. **Automated Smoke & Preflight Verification:** Deployment promotions must automatically execute verified smoke tests (readiness, database connectivity, tenant isolation barrier, clinical safety firewall) before marking releases as `deployed`.

---

## 3. Considered Options

- **Option 1: Third-Party Feature Flag & CI/CD SaaS (e.g., LaunchDarkly, Split.io, GitHub Actions-only).**
  - *Pros:* Off-the-shelf cloud dashboards.
  - *Cons:* External SaaS dependencies violate standalone on-premise Unani matab requirements, risk leaking confidential patient/practice metadata, introduce vendor lock-in, and fail to enforce local database transaction safety.
- **Option 2: Plain Environment Variables & Git Tags.**
  - *Pros:* Minimal setup.
  - *Cons:* No runtime toggling, requires full service restarts for flag changes, lacks cohort targeting (tenants, facilities, roles), has zero audit trail of who flipped a toggle, and provides no recovery governance.
- **Option 3 (Selected): In-Database Canonical Release Engineering, Scoped Feature Flags & Rollback Orchestration Engine.**
  - *Pros:* Fully native to ZAYVORA MATAB OS, backed by relational SQLite schema (Migration 037), strict server-side cohort evaluation, immutable audit ledgers, automated pre-deploy gates and post-deploy smoke tests, separation-of-duties enforcement, and instantaneous emergency kill-switches integrated directly into the Web UI.

---

## 4. Decision Outcome

We implemented Option 3:

### 1. Database Schema (Migration 037)
- `release_manifests`: Core immutable deployment manifests tracking version tags, target environments, risk levels, lifecycle states (`draft` $\to$ `awaiting_approval` $\to$ `approved` $\to$ `deploying` $\to$ `deployed` / `verification_failed` / `rollback_requested` $\to$ `recovered`), Git commit/digest provenance, quality gates, and rollback plans.
- `release_gate_evaluations`: Granular gate evaluation logs (`UNIT_TESTS`, `INTEGRATION_TESTS`, `SECURITY_SCAN`, `MIGRATION_COMPATIBILITY`, `CLINICAL_SAFETY_GATE`, `SMOKE_TESTS`).
- `feature_flags`: Scoped feature flags with environment targeting (`local`, `ci_test`, `staging`, `pilot`, `production`), cohort targeting (tenants, facilities, roles, user IDs), expiry dates, and emergency kill-switches.
- `feature_flag_audit`: Append-only audit ledger tracking every flag change (previous state, new state, user ID, reason).
- `deployment_executions`: Promotion execution history with automated smoke test evidence snapshots.
- `rollback_executions`: Recovery records tracking strategy (`DISABLE_FEATURE`, `ROLLBACK_ARTIFACT`, `ROLL_FORWARD`, `CONTAIN`), execution author, reason, and side-effect limits.

### 2. Core Governance Engine (`ReleaseGovernanceEngine`)
- **Manifest Lifecycle Management:** Draft creation, updates, advancement (`approve`, `reject`, `pause`), quality gate evaluations, and automated state transitions.
- **Strict Separation of Duties:** Blocks self-approval in production/pilot environments with `ForbiddenError`.
- **Server-Side Scoped Flag Evaluation:** Evaluates environment active state, tenant/facility/role/user cohorts, and defaults to `false` (fail-closed) upon error or expiration.
- **Instantaneous Emergency Kill-Switches:** Immediate flag disabling with mandatory root-cause reason tracking.
- **Deployment Promotions & Recovery:** Automated smoke testing during deployment; multi-strategy rollback orchestration with side-effect tracking.

### 3. REST API & UI Workbench
- 15 REST endpoints mounted under `/api/v1/releases` and `/api/v1/flags` protected by RBAC permissions (`release:read`, `release:manage`, `release:approve`, `release:deploy`, `release:rollback`, `flag:read`, `flag:manage`, `flag:approve`, `flag:toggle`).
- Integrated into `apps/web/static/js/views/knowledge_admin.js` as the "Releases & Flags (P38)" workspace tab, featuring operational pulse metrics, release catalogs, gate pills, deployment/rollback triggers, and feature flag emergency kill-switches.

---

## 5. Consequences

### Positive
- **Auditable Provenance:** Every deployed artifact in test, staging, or production is cryptographically linked to a Git commit and artifact digest.
- **Controlled Clinical Rollouts:** Clinical CDS and prescription rules can be safely tested in pilot facilities without exposing all clinics or risking unintended automated dispensing.
- **Rapid Incident Recovery:** Operators can engage feature flag kill-switches or initiate structured rollbacks within seconds without restarting application servers.
- **Regulatory & Compliance Assurance:** Full compliance with AYUSH/ABDM digital governance requirements regarding software change management, separation of duties, and tamper-evident audit trails.

### Neutral / Trade-offs
- **Governance Overhead:** Production releases require dual approval from distinct user accounts, preventing rapid single-developer production pushes.
- **Flag Hygiene Maintenance:** Feature flags include mandatory expiry dates (`expiry_date`), requiring periodic deprecation audits to prevent stale conditional branches in code.

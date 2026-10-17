# ADR-058: Production Observability, Incident Response, SLO Governance & Reliability Operations Engine

- **Status:** Accepted
- **Date:** 2026-10-14
- **Phase:** Prompt 39 (Phase 39) — ZAYVORA MATAB OS
- **Deciders:** Principal Reliability Architect, DevSecOps Lead, Application Security Engineer, Clinical Safety Officer, Incident Commander

---

## 1. Context and Problem Statement

ZAYVORA MATAB OS coordinates mission-critical clinical consultations, botanical compounding, billing, and external health exchanges (ABDM/FHIR). Operating in production requires deep visibility into system reliability, dependency readiness, and real-time failures. Traditional monitoring solutions introduce severe risks when deployed in healthcare environments:
1. **Accidental PHI & Credential Leakage:** Logging entire HTTP request bodies or stack traces frequently leaks patient names, mobile numbers, national health IDs (ABHA), prescription formulations, or bearer tokens into log aggregators and metric labels.
2. **Alert Fatigue & Noise:** Raw log alerts firing without actionable runbooks, deduplication fingerprints, or explicit ownership cause operators to ignore critical warnings.
3. **Fictitious or Unverified SLOs:** Teams often publish generic "99.9% uptime" targets disconnected from true clinical user capabilities, or mistake shallow HTTP 200 liveness checks for end-to-end workflow health.
4. **Ad-Hoc, Chaotic Incident Handling:** Lacking a canonical incident state machine with required resolution proof leads to premature closure of incidents while regressions persist.
5. **Dangerous Automated Remediations:** Naive self-healing scripts that execute arbitrary shell commands or attempt to modify patient clinical records or prescription states without human approval.

A privacy-preserving, mathematically grounded, and governance-controlled observability, incident management, and SLO platform was required.

---

## 2. Decision Drivers

1. **Zero Clinical Overreach:** Observability tooling and automated remediations must never formulate, calculate doses, prescribe, dispense, or alter patient medical records.
2. **Absolute Privacy & Data Minimization:** Zero patient names, ABHA IDs, diagnoses, clinical notes, prescription contents, or secrets in logs, metric labels, alerts, or incident records.
3. **Strict Low-Cardinality Metric Labeling:** Metrics must be partitioned strictly by route templates (e.g. `/api/v1/encounters/{id}`) and bounded outcome classes (`SUCCESS`, `CLIENT_ERROR`, `SERVER_ERROR`, `TIMEOUT`, `BLOCKED`). High-cardinality entity IDs or UUIDs in metric dimensions are strictly prohibited.
4. **Four-Tier Health Model:**
   - **Liveness:** Lightweight check verifying the API process event loop is active (`/api/v1/health/live`).
   - **Readiness:** Shallow dependency verification safe for public load balancers without leaking internal database topology or credentials (`/api/v1/health/ready`).
   - **Deep Diagnostics:** Authenticated operator diagnostics inspecting database latency, queue lag, safety firewall readiness, and feature flag state (`/api/v1/observability/diagnostics/deep`).
   - **Workflow Correctness:** Verifying real domain transitions without creating fake records.
5. **Actionable Alerts with Mandatory Runbooks:** Every alert rule must define an explicit condition, evaluation window, owner role, and actionable runbook detailing diagnostic steps, mitigation options, and prohibited actions. Alerts must deduplicate on stable fingerprints and require verification evidence before clearance.
6. **Owner-Approved SLO Registry & Error Budgets:** SLIs must track good vs. total events. SLO targets must be explicit and approved. Missing telemetry intervals must be labeled `MEASUREMENT_GAP`, never assumed healthy.
7. **Canonical Incident Lifecycle State Machine:** Strict transitions:
   $$\text{detected} \longrightarrow \text{triaged} \longrightarrow \text{acknowledged} \longrightarrow \text{investigating} \longrightarrow \text{mitigating} \longrightarrow \text{monitoring\_recovery} \longrightarrow \text{resolved} \longrightarrow \text{postmortem\_due} \longrightarrow \text{reviewed} \longrightarrow \text{closed}$$
   Transition to `resolved` requires documented verification evidence.
8. **Bounded, Reversible Automated Remediation:** Strict allowlist (`RESTART_BACKGROUND_CONSUMER`, `PAUSE_FAILING_CONNECTOR`, `TRIP_EMERGENCY_FEATURE_FLAG`, `CLEAR_TRANSIENT_CACHE`, `RECONCILE_STALE_TRANSACTION`), enforced 300s cooldown windows, and zero clinical access.

---

## 3. Considered Options

- **Option 1: Third-Party Observability SaaS (Datadog, New Relic, Dynatrace).**
  - *Pros:* Rich managed cloud dashboards.
  - *Cons:* Violates standalone Unani matab on-premise operational mandates, risks leaking confidential health data to third-party clouds, creates external vendor lock-in, and lacks domain understanding of clinical safety boundaries.
- **Option 2: Standalone Prometheus / Alertmanager Daemon Cluster.**
  - *Pros:* Standard open-source cloud-native tooling.
  - *Cons:* Requires orchestrating separate background binaries and scrapes, introduces separate authentication realms outside matab RBAC, and does not provide an integrated incident state machine or runbook linking inside the clinic web workbench.
- **Option 3 (Selected): In-Database Canonical Observability, Alerting, SLO Governance & Incident Operations Engine.**
  - *Pros:* Fully native to ZAYVORA MATAB OS, backed by relational SQLite schema (Migration 038), zero external daemon dependencies, strict low-cardinality enforcement, deterministic fingerprint deduplication, integrated runbooks, canonical incident lifecycle state machine, and allowlisted remediation guardrails directly within the web workspace.

---

## 4. Decision Outcome

We implemented Option 3:

### 1. Database Schema (Migration 038)
- `observability_service_catalog`: Governed service catalog tracking upstream/downstream maps, criticality tiers, and health status.
- `observability_telemetry_metrics`: Bounded low-cardinality time-series metric snapshots with zero PHI.
- `observability_alert_definitions`: Versioned alert definitions with evaluation rules and mandatory runbooks.
- `observability_alert_instances`: Firing alert instances with deduplication fingerprints and resolution proofs.
- `observability_slo_registry`: Owner-approved SLO targets, event populations, error budgets, and burn rates.
- `observability_incidents`: Incident lifecycle records tracking commanders, severity, impact, and root causes.
- `observability_incident_timeline`: Chronological audit ledger of incident events and communications.
- `observability_remediation_actions`: Allowlisted, bounded automated remediations with cooldown tracking.

### 2. Core Governance Engine (`ObservabilityReliabilityEngine`)
- **Service Health Probes & Deep Diagnostics:** Aggregates database query latency, migration state, safety gate readiness, queue lag, and active kill-switches with zero secret disclosure.
- **Telemetry Ingestion & Cardinality Guardrails:** Enforces low-cardinality route templates and rejects any metric labels matching UUIDs, entity prefixes (`pat-`, `enc-`, `usr-`), emails, or phone numbers.
- **Alert Evaluation & Deduplication:** Evaluates alert rules against metric windows, deduplicates firing instances by SHA-256 fingerprint, and enforces resolution evidence before clearing.
- **Governed SLO Registry:** Computes error budgets ($E_{\text{total}} = N \cdot (1 - \text{target})$), remaining budgets, and burn rates.
- **Incident State Machine:** Enforces valid state transitions and mandates resolution evidence.
- **Safe Remediation Runner:** Executes allowlisted operational actions with 300s cooldown windows and strict lockouts preventing clinical record alterations.

### 3. REST API & UI Workbench
- 21 REST endpoints mounted under `/api/v1/observability/` protected by RBAC permissions (`observability:read`, `observability:metrics`, `observability:diagnostics`, `alert:read`, `alert:manage`, `alert:ack`, `incident:read`, `incident:create`, `incident:manage`, `incident:close`, `slo:read`, `slo:manage`, `remediation:execute`).
- Integrated into `apps/web/static/js/views/knowledge_admin.js` as the "Observability & Incidents (P39)" workspace tab, featuring operational pulse metrics, active firing alerts with runbooks, an incident response command console, an SLO error budget tracker, and safe remediation triggers.

---

## 5. Consequences

### Positive
- **Guaranteed Privacy & Data Minimization:** No patient identifiers or secrets can be exposed via observability dashboards or metric exports.
- **Actionable Operations:** Eliminates alert fatigue by attaching explicit runbooks and deduplication fingerprints to all alerts.
- **Verifiable Reliability:** SLOs provide transparent error budgets and burn rates, with explicit flags for telemetry gaps.
- **Safe Incident Coordination:** Structured incident transitions prevent prematurely declaring incidents resolved without verified evidence.
- **Protected Clinical Authority:** Automated remediations are strictly locked out of clinical records, ensuring clinical judgement remains exclusively with qualified clinicians.

### Neutral / Trade-offs
- **Telemetry Cardinality Restrictions:** Operators cannot query metrics by concrete patient ID or user ID; detailed entity-level investigations must use access-controlled audit logs.
- **Governance Requirement on SLOs:** New SLOs cannot immediately affect automated policies until approved by an accountable owner in the registry.

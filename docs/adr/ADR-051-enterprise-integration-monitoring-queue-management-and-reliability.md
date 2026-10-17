# ADR-051: Enterprise Integration Monitoring, API Reliability, Queue Management & Interoperability Operations Engine

- **Status:** Accepted
- **Date:** 2026-10-14
- **Product:** ZAYVORA MATAB OS — Standalone Clinic & Matab Operating System
- **Phase:** 32 — Operational Reliability, Connectors, Asynchronous Queues, Dead-Letter Governance, Unknown-Outcome Reconciliation & Interoperability Ops

---

## 1. Context & Problem Statement

ZAYVORA MATAB OS operates in mission-critical clinical environments where external interactions—such as ABDM Gateway exchanges, ABDM HIU/HIP consent workflows, FHIR DocumentBundle distributions, external laboratory information system (LIS) dispatch, and government health registries—depend on fallible third-party networks, intermittent cloud outages, partner rate limits, and latency spikes.

In healthcare systems, naive API integration models produce dangerous clinical and operational failures:
1. **Fabricated Operational Status:** Reporting a task as "delivered" or "successful" when an upstream HTTP request was merely accepted (202 Accepted) or dropped silently.
2. **Ambiguous Outcome Retries:** Blindly resending clinical orders, prescriptions, or consent revocations following network timeouts (`ERR_READ_TIMEOUT_AFTER_DISPATCH`), leading to duplicated treatments, duplicate billings, or conflicting state.
3. **Unchecked Infinite Loops & Cascading Outages:** Naive retry loops hammer downstream partners during outages, burning cloud egress budgets and tripping rate limits.
4. **Dead-Letter Queue as a Trash Bin:** Dropping failed transactions into an unmonitored DLQ without structured classifications, root-cause diagnostics, assigned ownership, or safe replay capabilities.
5. **Data Leakage in Operational Logs:** Dumping full JSON payloads containing Protected Health Information (PHI) and clinical diagnostic records into infrastructure log streams and telemetry dashboards.
6. **Clinical Safety & Consent Bypasses:** Blindly retrying outbound transactions days later without verifying whether the patient has since revoked consent or the prescription was cancelled.

---

## 2. Decision & Architectural Principles

We implement a deterministic, audited, and resilient **Enterprise Integration Monitoring, API Reliability & Queue Management Engine** governed by the following core architectural decisions:

### 2.1 Schema Architecture (Migration 031)
Seven purpose-built, referentially sound tables are introduced:
1. `integration_jobs`: The central durable integration job queue enforcing a strict 20-state lifecycle, retry budgets, payload manifest hashes, idempotency keys, and trace lineage.
2. `integration_attempts`: Every dispatch execution attempt is recorded with millisecond duration, sanitized result codes, retry classification, actual provider transaction IDs, and scrubbed error messages.
3. `integration_inbox_events`: Inbound webhooks, asynchronous callbacks, and external notifications with signature verification, replay protection, and deduplication keys.
4. `integration_reconciliations`: Governed investigations for ambiguous `outcome_unknown` states, enforcing factual evidence capture and formal determinations before state changes.
5. `dead_letter_items`: Structured DLQ items with classified reason codes, sanitized diagnostics, safe replay eligibility flags, assigned owner teams, and resolution audit records.
6. `connector_health_snapshots`: Multi-dimensional empirical health probe records (connectivity, liveness, auth verify, latency, queue lag).
7. `integration_circuit_breakers`: State-machine tracking consecutive failures per external connector, tripping to `OPEN` when failure thresholds are reached to shield downstream partners.

### 2.2 The 20-State Job Lifecycle Machine
Jobs progress through discrete, auditable states:
`created` $\to$ `queued` $\to$ `eligible_for_processing` $\to$ `running` $\to$ `waiting_for_external_response` $\to$ `waiting_for_callback` $\to$ `retry_scheduled` $\to$ `blocked_by_authorization` $\to$ `blocked_by_consent` $\to$ `blocked_by_validation` $\to$ `paused_for_reconciliation` $\to$ `outcome_unknown` $\to$ `partial` $\to$ `completed` $\to$ `failed_non_retryable` $\to$ `dead_lettered` $\to$ `cancel_requested` $\to$ `cancelled` $\to$ `expired` $\to$ `manual_review_required`.

Transitions from `outcome_unknown` directly to `completed` are strictly prohibited by code without formal reconciliation (`VALID_RECON_DETERMINATIONS`).

### 2.3 Strict Idempotency for Side Effects
Every outbound integration job requires a mandatory `idempotency_key`. If an identical idempotency key is submitted within the organization, the existing job is returned without creating duplicate side effects (`is_idempotent_duplicate = True`).

### 2.4 Bounded Exponential Backoff with Jitter
Retries are calculated with exponential backoff and randomized decorrelated jitter:
$$t_{\text{backoff}} = \min(t_{\text{max}}, t_{\text{base}} \times 2^{\text{attempt}}) \pm \text{jitter}$$
Retries are bounded by both `max_attempts` and an organizational `retry_budget`. Once exhausted, jobs transition to `dead_lettered`.

### 2.5 Zero PHI in Telemetry and Operational Logs
Payloads are stored only as SHA-256 manifest hashes (`payload_manifest_hash`). Operational metrics, traces, and dead-letter workbench listings expose only structured error categories and sanitized diagnostics, preventing patient PHI from leaking into monitoring streams.

### 2.6 Consent & Authorization Re-Verification on Retry
Before every retry attempt, patient consent records (`consent_ref`) and organizational policies are re-evaluated. If consent has expired or was revoked while a job was queued, the attempt aborts and marks the job `blocked_by_consent`.

---

## 3. Consequences

### Positive
- **Zero Ambiguous Retries:** Eliminates dangerous duplicate clinical orders and financial double-charges.
- **Fail-Safe Partner Protection:** Circuit breakers automatically isolate degraded downstream APIs before local thread exhaustion occurs.
- **Auditable Dead-Letter Remediation:** Operators have a safe workbench to inspect, fix schemas, and trigger safe replays without direct database manipulation.
- **Regulatory Privacy Compliance:** Zero raw PHI in monitoring tools ensures full compliance with DISHA, HIPAA, and ABDM data privacy standards.

### Negative / Trade-Offs
- Requires operators to resolve reconciliations when partner connections drop mid-flight.
- Introduces additional state storage in SQLite/PostgreSQL, managed by statutory retention policies.

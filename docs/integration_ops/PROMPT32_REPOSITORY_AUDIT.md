# ZAYVORA MATAB OS — Prompt 32 Repository Pre-Implementation Audit
## Enterprise Integration Monitoring, API Reliability, Queue Management & Interoperability Operations Engine

**Document Type:** Pre-Implementation Architectural & Codebase Audit  
**Product:** ZAYVORA MATAB OS — Standalone Clinic/Hospital Operating System  
**Phase:** 32 — Operational Reliability for Internal Services, External Connectors, Asynchronous Workflows, Callbacks, and Data-Exchange Reconciliation  
**Date:** October 2026  
**Status:** Pre-Flight Verified  

---

## 1. Executive Summary & Purpose

Prompt 32 establishes the **Enterprise Integration Monitoring, API Reliability, Queue Management & Interoperability Operations Engine** for ZAYVORA MATAB OS. In healthcare systems handling clinical prescribing, laboratory integrations, diagnostic transfers, and national health exchanges (e.g. ABDM / FHIR R4), technical operational failures must never compromise patient safety or corrupt clinical records.

### Non-Negotiable Tenets Strictly Enforced:
1. **Never Fabricate Operational Status:** Operational metrics (uptime, latency, queue lag, completion ratios, delivery receipts) must represent real measurements. No synthetic 99.99% claims without empirical baseline.
2. **Request Accepted $\neq$ Work Completed:** An HTTP 202, queued task, or local bundle export does not prove end-to-end clinical completion.
3. **Idempotency for All Side Effects:** Retrying an external call or replaying a queue item must never create duplicate prescriptions, duplicate billing lines, duplicate lab orders, or duplicate clinical notes.
4. **`outcome_unknown` is a First-Class State:** If a network timeout or crash occurs after dispatch, the system sets `outcome_unknown` and enforces status reconciliation before any non-idempotent retry.
5. **Governed Retry Budgets & Backoff:** Retries are bounded, jittered, and classified by failure type (transient vs permanent). Blind infinite loops are strictly prohibited.
6. **Dead-Letter Queue is Not a Trash Bin:** Every dead-lettered job must record a structured reason, assigned team owner, and safe remediation path.
7. **No Clinical Safety Bypass:** A technical connector failure must never be translated into "no issue found", "cleared", or "safe".
8. **Request/Response Lineage & Zero PHI in Telemetry:** Full correlation IDs, trace IDs, and idempotency keys are tracked; metrics and logs must never leak patient identifiable health information (PHI).
9. **Consent & Authorization Recheck on Retry:** Work waiting in queues or scheduled for retry must verify that patient consent and user permissions remain valid at the moment of execution.
10. **Callbacks Untrusted Until Verified:** Webhook callbacks must be authenticated via cryptographic signature, checked against a freshness window, and deduplicated before state mutation.
11. **Technical Status $\neq$ Clinical Status:** A transmitted message does not prove clinical review or patient adherence.

---

## 2. Codebase Audit of Existing Foundations

| Phase / Migration | Existing Relational & Domain Foundations | Status in Repo | Reusability for Phase 32 |
|---|---|---|---|
| **Prompt 01 & 02 (Platform Foundation & Patient Registry)** | Organizations, Facilities, Patients, Encounters | `implemented_and_tested` | Tenant and facility scoping for all operational jobs and connectors. |
| **Prompt 09 (Care Continuity & Outbound Messaging)** | `outbound_messages`, `message_delivery_events`, `contact_attempts` | `implemented_and_tested` | Provides channel delivery events; needs operational reliability oversight. |
| **Prompt 11 (Enterprise Multi-Branch Administration)** | `integration_connectors` (Migration 011) | `implemented_and_tested` | Core connector registry table with endpoint URLs, secret URIs, and environments (`SANDBOX`, `PRODUCTION`). |
| **Prompt 12 (Hospital Workflows & External Interoperability)** | `hospital_referrals`, `hospital_referral_events` | `implemented_and_tested` | Referral dispatch workflows requiring queue monitoring and retry governance. |
| **Prompt 28 (Knowledge Governance & Controlled Release)** | `governance_releases`, `governance_runtime_resolutions` | `implemented_and_tested` | Pins active specification versions for integration exchanges. |
| **Prompt 29 (Clinical Audit Ledger & Tamper-Evident Ledger)** | `audit_ledger_events`, `audit_integrity_checkpoints` | `implemented_and_tested` | Provides tamper-evident audit logging for operator actions (retries, replays, cancels, reconciliations). |
| **Prompt 30 (Security Governance, Privacy & Consent)** | `patient_consents`, `delegated_access_grants`, `security_principals` | `implemented_and_tested` | Gating checks for consent validity during queued job execution and retry dispatch. |
| **Prompt 31 (Enterprise Interoperability & FHIR/ABDM Exchange)** | `interop_transfer_outbox`, `interop_webhook_verifications`, `inbound_record_reconciliations` | `implemented_and_tested` | Provides the transactional outbox and webhook verification primitives that Phase 32 monitors and manages. |

---

## 3. Architecture & Schema Gap Analysis for Phase 32

To achieve production-grade operational reliability, ZAYVORA requires a dedicated **Integration Operations Engine** (`Migration 031`):

1. **`integration_jobs` (Durable 20-State Machine):**
   - Universal job orchestrator tracking internal asynchronous tasks and external connector dispatches.
   - States: `created`, `queued`, `eligible_for_processing`, `running`, `waiting_for_external_response`, `waiting_for_callback`, `retry_scheduled`, `blocked_by_authorization`, `blocked_by_consent`, `blocked_by_validation`, `paused_for_reconciliation`, `outcome_unknown`, `partial`, `completed`, `failed_non_retryable`, `dead_lettered`, `cancel_requested`, `cancelled`, `expired`, `manual_review_required`.
2. **`integration_attempts` (Granular Attempt History):**
   - Immutable log capturing attempt sequence, duration ms, idempotency key, error categorization (`RETRYABLE_NETWORK`, `NON_RETRYABLE_AUTH`, `UNKNOWN_TIMEOUT`), and provider transaction IDs.
3. **`integration_inbox_events` (Inbound Callback Deduplication):**
   - Validates cryptographic signatures, enforces replay windows, and deduplicates provider message IDs before triggering state machine transitions.
4. **`integration_reconciliations` (Unknown-Outcome Resolution):**
   - Governed resolution workflow for `outcome_unknown` jobs, executing provider queries, receipt comparisons, or authorized manual determinations.
5. **`dead_letter_items` (DLQ Workbench):**
   - Structured failure reasons (`RETRY_BUDGET_EXHAUSTED`, `CONSENT_REVOKED`, `UNRESOLVED_OUTCOME`), assigned team ownership, and safe replay eligibility.
6. **`connector_health_snapshots` (Multi-Dimensional Health Probes):**
   - Distinct dimensions: `LIVENESS`, `CONNECTIVITY`, `AUTH_VERIFY`, `CREDENTIAL_EXPIRY`, `QUEUE_LAG`, `BUSINESS_PING`.
   - Distinguishes "reachable" from "authorized for clinical transactions".
7. **`integration_circuit_breakers` (Fault Isolation):**
   - Prevents cascading failures by opening circuit on repeated partner errors (`CLOSED`, `OPEN`, `HALF_OPEN`).

---

## 4. Implementation Strategy & Next Steps

1. **Migration 031:** Create `031_integration_operations_reliability_schema.sql` supporting the 7 core operations tables.
2. **Domain Engine:** Implement `IntegrationOperationsEngine` in `apps/api/domains/integration_ops.py`.
3. **Permissions:** Register `ops:read`, `ops:retry`, `ops:cancel`, `ops:reconcile`, `ops:manage` in `apps/api/core/permissions.py`.
4. **REST APIs:** Implement endpoints in `apps/api/routes/integration_ops.py` and register in `apps/api/router.py`.
5. **UI Console:** Add "Integration Operations & Reliability (P32)" tab to `knowledge_admin.js`.
6. **Documentation:** Create ADR-051, Connector Contracts & Retry Policies spec, Operational Runbook & Incident Guide.
7. **Testing:** Create comprehensive unit tests (`test_integration_ops.py`) and integration tests (`test_integration_ops_api.py`), ensuring 100% pass across all 32 phases.

# ZAYVORA MATAB OS — Prompt 33 Repository Audit
## Canonical Entities, Source of Truth, Analytics Readiness & Lineage Assessment

**Document type:** System & Repository Audit  
**Phase:** 33 — Enterprise Analytics, Operational Intelligence & Clinical Governance Dashboards  
**Date:** October 2026  
**Status:** Audit Complete  

---

## 1. Executive Summary

This audit assesses the state of canonical persistence, domain models, and operational entities across ZAYVORA MATAB OS (Prompts 01–32) to establish the authoritative source of truth for all enterprise analytics, operational intelligence, and clinical governance dashboards.

### Core Architecture Guarantee
ZAYVORA MATAB OS maintains an absolute separation between canonical transactional persistence (SQLite in WAL mode / PostgreSQL) and derived analytical views. In accordance with the non-negotiables:
- No metric is fabricated or simulated.
- Missing or unconfigured domains are represented as `not_configured` or `insufficient_data`, never an invented zero or positive score.
- Uncontrolled observational data is never used to infer clinical efficacy or treatment causality.
- No public clinical success leaderboard or practitioner ranking is permitted.

---

## 2. Inventory of Canonical Domains & Operational Records

Each entity has been inspected across migrations 001–031 and verified:

| Canonical Entity | Migration / Table(s) | Operational State Lifecycle | Implementation Status | Analytics Readiness & Lineage |
| :--- | :--- | :--- | :--- | :--- |
| **Tenancy & Branches** | `001_foundation_schema.sql`<br>`organizations`, `facilities` | `active`, `suspended`, `archived` | **Production-Backed** | Authoritative hierarchy for tenant and facility isolation. Cross-tenant aggregation restricted to platform admins. |
| **Identity & RBAC** | `001_foundation_schema.sql`<br>`029_security_schema.sql`<br>`users`, `roles`, `security_principals` | `active`, `revoked`, `locked` | **Production-Backed** | Strict server-side permission checks (`analytics:read`, `analytics:export`, `analytics:govern`). Trusted principal scoping. |
| **Patient Registry** | `002_patient_encounter_schema.sql`<br>`patients`, `patient_aliases` | `active`, `inactive`, `merged` | **Production-Backed** | Authoritative demographic and registration counts. PII/PHI masked; only aggregate counts exposed. |
| **Appointments & Queue** | `010_clinic_operations_os_schema.sql`<br>`appointments`, `queue_tokens` | `booked`, `confirmed`, `arrived`, `in_progress`, `completed`, `cancelled`, `no_show` | **Production-Backed** | True operational queue and scheduling metrics. Differentiates cancellations and no-shows from completed visits. |
| **Encounters** | `002_patient_encounter_schema.sql`<br>`encounters` | `draft`, `signed`, `cancelled` | **Production-Backed** | Authoritative consultation volume. Distinguishes draft documentation from finalized signed care. |
| **Prescriptions & Nuskha** | `003_formulation_prescription_schema.sql`<br>`prescriptions`, `prescription_items` | `draft`, `validated`, `signed`, `dispensed`, `cancelled` | **Production-Backed** | Formulation volume and dispensing tracking. Strictly avoids clinical efficacy inference. |
| **Billing & Payments** | `010_clinic_operations_os_schema.sql`<br>`invoices`, `payments`, `payment_refunds` | Invoices: `DRAFT`, `FINALIZED`, `PARTIALLY_PAID`, `PAID`, `VOIDED`, `REFUNDED`<br>Payments: `POSTED`, `PARTIALLY_REFUNDED`, `REFUNDED` | **Production-Backed** | Decimal-safe financial accounting. Distinguishes invoiced totals from actual cash collections, refunds, and adjustments. |
| **Pharmacy & Inventory** | `010_clinic_operations_os_schema.sql`<br>`inventory_items`, `inventory_batches`, `inventory_movements` | Batches: `AVAILABLE`, `QUARANTINED`, `RECALLED`, `EXPIRED_HOLD`, `DEPLETED` | **Production-Backed** | Real-time FEFO batch stock, expiry horizon analysis (30/60/90 days), and immutable stock movement audits. |
| **Continuity & Follow-up** | `009_care_continuity_schema.sql`<br>`024_timeline_schema.sql`<br>`care_continuity_tasks`, `medication_status_ledger` | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` | **Production-Backed** | Follow-up compliance, overdue tasks, and contact attempt indicators. Process metrics, not efficacy. |
| **Safety Surveillance** | `026_pharmacovigilance_schema.sql`<br>`safety_cases`, `safety_events` | `INTAKE`, `TRIAGED`, `UNDER_INVESTIGATION`, `ACTION_TAKEN`, `REPORT_GENERATED`, `SUBMITTED`, `CLOSED` | **Production-Backed** | Independent adverse event counts, severity breakdown, and regulatory profile status. No autonomous diagnosis. |
| **Knowledge Governance** | `027_governance_schema.sql`<br>`governed_clinical_rules`, `governance_releases` | `DRAFT`, `SUBMITTED`, `VALIDATED`, `APPROVED`, `RELEASED`, `REJECTED`, `RETIRED` | **Production-Backed** | Rule versioning, safety firewall updates, approval queues, and test suite passage rates. |
| **Cryptographic Audit** | `028_audit_schema.sql`<br>`clinical_ledger_events`, `audit_integrity_checkpoints` | Immutable append-only ($H_i = \text{SHA-256}(C_i \parallel H_{i-1})$) | **Production-Backed** | Full audit event coverage across clinical and administrative domains. Verification checkpoint integrity. |
| **Interoperability & Reliability** | `031_integration_ops_schema.sql`<br>`integration_jobs`, `dead_letter_items`, `integration_circuit_breakers` | Jobs: 20-state lifecycle (`queued`, `outcome_unknown`, `dead_lettered`, etc.) | **Production-Backed** | Outbound queue reliability, active circuit breakers, dead-letter remediation counts, and unknown outcome tasks. |

---

## 3. Inventory of Existing Reporting & Analytics Implementations

Existing endpoints and methods across the codebase:
1. `apps/api/domains/care_continuity.py`:
   - `get_follow_up_analytics(org_id, fac_id)` -> Tasks by status, messages by status, adverse effects by status.
2. `apps/api/domains/clinic_operations.py`:
   - `handle_get_today_dashboard` -> Current day's tokens, arrivals, appointments, collections.
   - `handle_get_collections_report` -> Collections grouped by payment method over date range.
3. `apps/api/domains/integration_ops.py`:
   - `get_dashboard_summary(user_ctx)` -> Total jobs, active jobs, circuit breakers, and dead-letter items.
4. `apps/api/domains/outcomes.py`:
   - `generate_aggregate_report(criteria, user_ctx)` -> De-identified cohort aggregate reports with small-cell suppression ($\ge 5$).

### Strategic Reuse Plan:
We do not build competing analytical engines. The **Enterprise Analytics Engine** (`EnterpriseAnalyticsEngine`) acts as the central, unified semantic query and metrics abstraction layer, consolidating metrics across operational, clinical governance, and reliability domains while enforcing:
- Central metric registry with versioning and approval lifecycle.
- Server-side tenant/facility isolation.
- Standardized temporal windows (Today, Last 7 Days, Month-to-date, Custom Range) with IANA timezone boundaries.
- Consistent metadata: `status`, `freshness`, `limitations`, `source_entities`.

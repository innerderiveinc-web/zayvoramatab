# ADR-052: Enterprise Analytics, Operational Intelligence & Clinical Governance Dashboards (Prompt 33)

- **Status:** Accepted
- **Date:** 2026-10-14
- **Authors:** Core Architecture & Clinical Governance Team
- **Phase:** 33 (Prompt 33)

---

## 1. Context and Problem Statement

ZAYVORA MATAB OS operates in high-accountability clinical environments managing both modern ambulatory medicine and classical Unani healing traditions. In health-tech systems, naive analytics platforms frequently introduce severe systemic risks:
1. **Fabricated Metrics & Synthetic Hallucinations:** Estimating numbers or displaying placeholder mock counts under the guise of "predictive" dashboards.
2. **False Causal Inferences:** Equating operational activity or process compliance (e.g., signed encounters, completed documentation, prompt check-ins) with clinical cure, treatment effectiveness, or practitioner superiority.
3. **Public League Tables & Clinician Comparison:** Creating divisive, punitive, or legally indefensible clinician leaderboards based on observational EHR data without risk adjustment, severity stratification, or patient consent.
4. **Data Reduplication & Divergence:** Creating separate analytics data stores that desynchronize from canonical operational and clinical ledgers, producing contradictory financial and clinical figures.
5. **PHI Leakage in Aggregates & Telemetry:** Exposing identifiable patient demographics, clinical notes, or rare diagnoses in aggregate reports, CSV exports, or browser telemetry streams.
6. **Ambiguity Between Zero and Missing Data:** Conflating a legitimate count of zero with unrecorded data, unconfigured pipelines, failed batch runs, or stale caches.

To maintain clinical integrity, regulatory accountability, and multi-tenant trust, ZAYVORA MATAB OS required a principled, repository-native enterprise analytics and operational intelligence architecture.

---

## 2. Decision and Architecture Principles

We implemented a unified, role-aware, privacy-preserving **Enterprise Analytics, Operational Intelligence & Clinical Governance Architecture** governed by the following strict non-negotiables:

### 2.1 Never Fabricate Metrics or Patient Data
All metrics are derived deterministically and directly from canonical operational tables (`appointments`, `queue_tokens`, `encounters`, `invoices`, `payments`, `payment_refunds`, `inventory_batches`, `care_continuity_tasks`, `safety_cases`, `governed_artifacts`, `clinical_ledger_events`, `integration_jobs`). No mocked projections or simulated trends are ever displayed as factual measurements.

### 2.2 Strict Non-Causal Policy
Process metrics (e.g., encounters signed, follow-up calls logged, checklist completion) measure administrative workflow throughput and compliance. They do **not** imply clinical efficacy, therapeutic superiority, or patient cure. Every analytics endpoint and exported artifact explicitly binds mandatory governance caveats explaining these boundary conditions.

### 2.3 Role-Gated Access with Zero Public Leaderboards
Analytics views are strictly gated by authenticated role permissions (`analytics:read`, `analytics:export`, `analytics:govern`, `analytics:manage`). Productivity metrics are strictly personal to the individual clinician or aggregate to the facility level; public ranking, cross-clinician gamification, and competitive leaderboards are architecturally prohibited.

### 2.4 Decimal Monetary Precision & Reconciliation Integrity
Financial metrics use high-precision decimal representation. Net cash collection is calculated as:
$$\text{Net Cash Collections} = \sum(\text{payments.amount\_decimal}) - \sum(\text{payment\_refunds.amount\_decimal})$$
Accrued billings (`gross_invoiced`) are strictly segregated from realized cash collections. Identified variances between canonical records and analytics calculations trigger audited entries in `metric_reconciliation_exceptions`.

### 2.5 Central Governed Metric Registry (Catalogue)
Every metric is a first-class governed entity in `governed_metric_definitions` with an explicit lifecycle (`draft` $\to$ `review` $\to$ `approved` $\to$ `retired`), formal numerator/denominator definitions, inclusion/exclusion rules, accountable clinical or administrative owner, and calculation version pinning.

### 2.6 Zero PHI in Exports & SHA-256 Tamper-Evident Hashing
All dashboard exports (CSV/JSON) contain aggregated summary metrics only. Patient names, MRNs, phone numbers, and clinical narratives are stripped. Each export job writes an audit receipt to `analytics_export_audit` containing the SHA-256 fingerprint calculated over the exact byte payload delivered to the client.

### 2.7 Explicit Status Transparency
Analytics responses clearly delineate data freshness (`current`, `stale`, `insufficient_data`) and source watermarks (`CANONICAL_LIVE_REPLICA`), preventing confusion between true zeroes and uncomputed periods.

---

## 3. Database Schema (Migration 032)

Migration `032_enterprise_analytics_governance_schema.sql` establishes 4 core tables:

1. `governed_metric_definitions`: Master registry of metrics across Operations, Continuity, Finance, Inventory, Governance, and Data Quality domains.
2. `metric_calculation_runs`: Execution ledger recording aggregation grain, record count, execution duration, and calculation status.
3. `metric_reconciliation_exceptions`: Audit ledger for tracking discrepancies between source entities and analytics values.
4. `analytics_export_audit`: Tamper-evident ledger recording export format, filters, record count, user ID, and SHA-256 hash.

---

## 4. REST API Surface

Sixteen governed endpoints are mounted under `/api/v1/analytics/*`:
- `GET /api/v1/analytics/overview` (Executive Pulse)
- `GET /api/v1/analytics/clinic-operations`
- `GET /api/v1/analytics/patient-continuity`
- `GET /api/v1/analytics/finance` & `/finance-billing`
- `GET /api/v1/analytics/inventory` & `/inventory-dispensing`
- `GET /api/v1/analytics/clinical-governance` & `/governance-safety`
- `GET /api/v1/analytics/data-quality` & `/data-quality-readiness`
- `GET /api/v1/analytics/metrics` (Catalogue list)
- `POST /api/v1/analytics/metrics` (Create draft)
- `GET /api/v1/analytics/metrics/{key}` (Detail & lineage)
- `POST /api/v1/analytics/metrics/{id}/review` (Advance to review)
- `POST /api/v1/analytics/metrics/{id}/approve` (Approve definition)
- `POST /api/v1/analytics/metrics/{id}/retire` (Retire definition)
- `POST /api/v1/analytics/export` (Audited privacy-preserving export)
- `GET /api/v1/analytics/reconciliation-exceptions` (List exceptions)
- `POST /api/v1/analytics/reconciliation-exceptions` (Record exception)
- `POST /api/v1/analytics/reconciliation-exceptions/{id}/resolve` (Resolve exception)

---

## 5. Consequences

### Positive
- Unified, authoritative, trustworthy operational visibility for administrators and clinical directors.
- Defensible non-causal boundaries prevent misleading clinical claims from observational records.
- Elimination of data drift through direct derivation from canonical relational tables.
- Cryptographically verifiable export audit trail fulfilling statutory compliance standards.
- Zero PHI exposure in exported analytics and dashboard views.

### Trade-offs & Mitigations
- Direct query derivation against primary relational tables creates compute overhead during high-concurrency periods.
  - *Mitigation:* Queries utilize targeted composite indexes (`idx_payments_facility_date`, `idx_invoices_status_date`, `idx_appointments_facility_date`), strict period bounds, and support for asynchronous pre-aggregation.

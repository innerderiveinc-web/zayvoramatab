# ZAYVORA MATAB OS — PROMPT 41 REPOSITORY AUDIT
## Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Governance Engine

- **Date:** 2026-10-14
- **Phase:** Prompt 41 (Phase 41)
- **Scope:** Complete ZAYVORA MATAB OS Data Estate, Copies, Storage Tiers & Lifecycle Invariants
- **Reviewer:** Principal Software Architect, Privacy & Data Governance Engineer, Clinical Lifecycle Lead

---

## 1. Storage Tiers, Canonical Stores & Data Copies Discovery

ZAYVORA MATAB OS persists data across multiple distinct storage paradigms and physical locations:

### 1.1 Primary Relational Database (SQLite in WAL Mode)
- **Primary Database File:** `apps/api/database/zayvora_matab.db` (and isolated scratch databases during tests/drills).
- **Relational Tables:** 190+ canonical tables spanning 39 forward-only SQL migrations (`001` through `039`).
- **Core Entities:** Patients, encounters, Unani temperamental evaluations, modern clinical assessments, botanical formulations, prescriptions, appointments, queue tokens, billing invoices, payments, stock ledgers, knowledge monographs, safety rules, audit ledgers, and telemetry.

### 1.2 Filesystem Object & Document Storage
- **Clinical Artifacts Directory:** Generated consultation summaries, prescription bundles, patient instruction sheets, and ABDM health records stored as PDFs and JSON bundles with SHA-256 hashes.
- **KAVS Monograph Scans:** Digitized source pages, extraction JSONs, and citation locators.
- **Analytics & Audit Export Bundles:** Cryptographically hashed export packages (`audit_evidence_exports`, `analytics_export_audit`).
- **Database Backup Snapshots:** Online SQLite snapshot archives (`apps/api/database/backups/`).

### 1.3 Asynchronous Queues & Transactional Outboxes
- **Transactional Outboxes:** `integration_jobs`, `outbox_events`, `care_continuity_tasks` containing queued patient notifications, external ABDM exchange payloads, and webhook events.

### 1.4 In-Memory Caches & Materialized Read Models
- **Derived Read Models:** Command center queue metrics, analytics calculation runs (`metric_calculation_runs`), and capacity scenario simulations.
- **Search Indices:** In-memory transliteration dictionaries and canonical symptom indexes.

---

## 2. Real Data Estate Classification & Lifecycle Inventory

| Category ID | Category Name | Canonical Source | Sensitivity | Approved Retention (Baseline) | Disposal Action | Current Lifecycle State |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- |
| `patient_identity` | Master Patient Demographics | `patients`, `patient_identifiers` | `restricted_phi` | Statutory Minimum (7 Yrs post-last care) | `restrict` / `deidentify` | Production-backed; lacks automated retention evaluator |
| `clinical_encounters` | Encounters & SOAP Assessments | `encounters`, `modern_clinical_assessments` | `restricted_phi` | Statutory Minimum (7 Yrs) | `archive` then `restrict` | Production-backed; draft/signed states enforced |
| `prescriptions_nuskha` | Prescriptions & Botanical Formulations | `prescriptions`, `nuskha_items` | `restricted_phi` | Statutory Minimum (7 Yrs) | `archive` then `restrict` | Production-backed; immutable signed PIN receipts |
| `appointments_queue` | Clinic Queue & Appointment Slots | `appointments`, `queue_tokens` | `operational_confidential` | 3 Years | `delete` | Production-backed; historical records persist indefinitely |
| `billing_financials` | Invoices, Payments, Refunds | `invoices`, `payments`, `payment_refunds` | `financial_pci` | 8 Years (Tax & Financial Audit) | `restrict` / `archive` | Production-backed; financial immutability enforced |
| `inventory_batches` | Pharmacy Formulary & Batch Movements | `inventory_items`, `stock_movements` | `operational_confidential` | 5 Years post-batch expiry | `archive` | Production-backed; lot/batch ledger |
| `uploaded_documents` | Clinical Document Bundles & PDFs | `governed_artifacts`, local files | `restricted_phi` | Synchronized with clinical encounter | `archive` / `delete` | Production-backed; metadata in DB, bytes on disk |
| `knowledge_provenance`| KAVS Sources, Claims & Monographs | `clinical_sources`, `kavs_claims` | `public_knowledge` | Permanent / Archival | `retire` | Production-backed; review states enforced |
| `rules_governance` | Clinical Safety Rules & Flags | `safety_rules`, `feature_flags` | `operational_confidential` | Permanent version ledger | `retire` (No hard delete) | Production-backed; versioned rules |
| `audit_ledger` | Tamper-Evident Audit Ledger | `clinical_ledger_events`, `audit_events` | `operational_confidential` | Statutory Minimum (7 Yrs) | `immutable_worm` | Production-backed; SHA-256 state chaining |
| `integration_outbox` | Webhook Payloads & Job Queue | `integration_jobs`, `outbox_events` | `operational_confidential` | 90 Days post-delivery | `delete` / `purge` | Partial; no automatic TTL purge job |
| `telemetry_metrics` | Low-Cardinality Metric Samples | `observability_telemetry_metrics` | `operational_confidential` | 180 Days | `delete` / `aggregate` | Production-backed; low-cardinality |
| `analytics_read_models`| Materialized Analytics Runs | `metric_calculation_runs` | `operational_confidential` | 365 Days | `rebuild` / `delete` | Production-backed; derived read model |
| `temporary_exports` | Evidence & Report Downloads | `audit_evidence_exports`, temp files | `restricted_phi` | 30 Days | `secure_delete` | Partial; exports tracked but not auto-purged |

---

## 3. Identified Lifecycle & Deletion Gaps

1. **Absence of Unified Enterprise Retention Engine:**
   - Previous migrations introduced isolated retention fields (e.g. `audit_retention_policies` in Migration 028 for audit events, and `full_text_retention_permitted` in Migration 015 for KAVS), but no comprehensive engine spans patient, clinical, billing, document, and queue records.
2. **Missing Cross-Store Deletion Propagation:**
   - Deleting a patient or temporary export from the database does not automatically scrub corresponding files from the disk, outbox queues, or materialized caches.
3. **Absence of Governed Legal Hold Overrides:**
   - A universal legal hold mechanism across all data domains is required to freeze disposal/archival when clinical safety inquiries, litigation, or regulatory audits arise.
4. **No Deterministic Dry-Run Evaluator:**
   - Operators cannot preview which records are eligible for archival or disposal under an approved policy without risking unreviewed direct SQL mutations.
5. **No Data Subject Privacy Request Lifecycle:**
   - No structured workflow exists to intake, verify identity, plan, approve, execute, and verify patient privacy requests (e.g. data access, rectification, or restriction).

---

## 4. Implementation Strategy

1. **Schema Migration (`040_enterprise_data_lifecycle_retention_archival_deletion_schema.sql`):**
   - `data_lifecycle_inventory_catalog`: Authoritative inventory of data categories, canonical tables, sensitivity, and storage types.
   - `data_lifecycle_policies` & `data_lifecycle_policy_versions`: Governed, versioned retention and disposal policies with approval workflows.
   - `data_lifecycle_legal_holds`: Multi-domain legal hold registry that freezes archival/disposal.
   - `data_lifecycle_evaluation_runs`: Deterministic policy evaluation ledger supporting side-effect free dry runs.
   - `data_lifecycle_operations`: Governed lifecycle execution ledger tracking per-destination store outcomes (database, filesystem, caches, queues).
   - `data_lifecycle_requests`: Patient & regulatory privacy rights request workflow.
2. **RBAC Permissions (`apps/api/core/permissions.py`):**
   - Add `lifecycle:read`, `lifecycle:evaluate`, `lifecycle:hold`, `lifecycle:approve`, `lifecycle:execute`, and `lifecycle:request`.
3. **Domain Engine (`apps/api/domains/data_lifecycle.py`):**
   - `EnterpriseDataLifecycleEngine` managing inventory, versioned policies, legal holds, dry-run evaluation, multi-store disposal orchestration, and privacy request tracking.
4. **REST API Routes (`apps/api/routes/data_lifecycle.py`):**
   - Mount endpoints under `/api/v1/lifecycle/`.
5. **Web UI Workbench Integration:**
   - Add "Data Lifecycle & Retention (P41)" workspace tab to `apps/web/static/js/views/knowledge_admin.js`.
6. **Automated Unit & Integration Testing:**
   - `tests/unit/test_data_lifecycle.py` & `tests/integration/test_data_lifecycle_api.py`.

# ZAYVORA MATAB OS — PROMPT 40 REPOSITORY AUDIT
## Disaster Recovery, Business Continuity, Backup/Restore Verification & Resilience Engineering

- **Date:** 2026-10-14
- **Phase:** Prompt 40 (Phase 40)
- **Scope:** Complete ZAYVORA MATAB OS Data Estate & Operational Continuity Architecture
- **Reviewer:** Principal SRE, Software Architect, Database & Clinical Continuity Governance Engineer

---

## 1. Repository & Infrastructure Architecture Inventory

### 1.1 Storage Engines & Data Persistence
- **Primary Database Engine:** SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode = WAL`), high-concurrency connection pooling (`PRAGMA busy_timeout = 10000`), foreign key enforcement (`PRAGMA foreign_keys = ON`), and memory cache sizing (`PRAGMA cache_size = -64000`).
- **Database File:** `apps/api/database/zayvora_matab.db` (and isolated temporary files during testing/drills).
- **Relational Schema:** 38 forward-only SQL migrations (`001_foundation_schema.sql` through `038_production_observability_incident_and_slo_governance_schema.sql`) defining 186+ canonical tables.
- **Artifact & File Storage:** Local filesystem storage for clinical document bundles (`consultation_summary`, `prescription_bundle`, `patient_instruction_sheet`), source KAVS scans/PDFs, and export bundles with SHA-256 cryptographic fingerprints.
- **Transactional Outbox & Queues:** `integration_jobs`, `outbox_events`, `care_continuity_tasks` persisting asynchronous messages, webhooks, and retry ledgers with exponential backoff and dead-letter queues.
- **Audit & Governance Ledgers:** Tamper-evident ledgers (`clinical_ledger_events`, `audit_events`, `feature_flag_audit`, `security_audit_events`, `observability_incident_timeline`) utilizing immutable append-only structures with SHA-256 state chaining.

### 1.2 Existing Backup & Disaster Recovery Assets
1. **[`DATA_MIGRATION_BACKUP_RESTORE.md`](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/production-readiness/DATA_MIGRATION_BACKUP_RESTORE.md):**
   - Outlines online backup strategy using SQLite `VACUUM INTO` for zero-downtime crash-consistent snapshots.
   - Recommends AES-256 symmetrical GPG encryption for cold storage.
   - States target RTO (< 15 min) and RPO (< 5 min).
   - Status: *Documented operational runbook; manual shell execution; not dynamically governed via API or UI.*
2. **[`DATA_RECOVERY_VERIFICATION.md`](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/release-candidate/DATA_RECOVERY_VERIFICATION.md):**
   - Records an empirical isolated backup/restore drill performed on 2026-10-13 using Python's `sqlite3.Connection.backup(..., pages=100)`.
   - Validated `PRAGMA integrity_check` = `ok` and 100% table count parity.
   - Status: *One-time point-in-time test; lacks continuous drill execution orchestration and data reconciliation queues.*

---

## 2. Real Data Estate Criticality & Business Impact Analysis (BIA)

| Domain ID | Data Domain | System of Record Tables | Availability Criticality | RTO Target | RPO Target | Degraded Mode Policy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `auth_identity` | Authentication & User Access | `users`, `sessions`, `roles`, `permissions` | Tier 0 (Critical) | < 15 min | < 5 min | Allow cached active JWT verification; disable new credential creation |
| `patients_encounters` | Patient & Encounter Registry | `patients`, `patient_identifiers`, `encounters` | Tier 0 (Critical) | < 15 min | < 5 min | Read-only patient lookup; physical downtime capture forms |
| `appointments_queue` | Scheduling & Clinic Queue | `appointments`, `queue_tokens` | Tier 1 (Core) | < 30 min | < 15 min | Paper queue tokens with manual timestamping; re-entry post-recovery |
| `consultation_prescriptions` | Clinical Prescriptions & Nuskha | `prescriptions`, `nuskha_items`, `unani_assessments` | Tier 0 (Critical) | < 15 min | < 5 min | Hard stop on unsigned prescriptions; offline paper pad for emergency clinician orders |
| `billing_payments` | Invoicing & Settlements | `invoices`, `payments`, `payment_refunds` | Tier 1 (Core) | < 60 min | < 15 min | Manual paper receipts issued; reconcile after payment gateway/DB returns |
| `inventory_stock` | Pharmacy Stock & Batch Ledger | `inventory_items`, `inventory_batches`, `stock_movements` | Tier 2 (Supporting) | < 2 hrs | < 30 min | Emergency manual dispensing log; verify physical counts before reconciliation |
| `documents_artifacts` | Uploaded Files & Clinical Artifacts | `governed_artifacts`, filesystem PDFs | Tier 2 (Supporting) | < 4 hrs | < 1 hr | Metadata lookup in DB; re-fetch from physical paper archives if needed |
| `knowledge_provenance` | Monograph Provenance & KAVS | `clinical_sources`, `kavs_claims`, `kavs_extractions` | Tier 2 (Supporting) | < 4 hrs | < 4 hrs | Fall back to published reference books; suspend automated citations |
| `rules_governance` | Clinical Safety Rules & Flags | `clinical_rules`, `safety_cases`, `feature_flags` | Tier 0 (Critical) | < 15 min | 0 (Zero Loss) | Fail-closed: all overridable warnings escalate to mandatory clinician review |
| `integration_queues` | Transactional Outbox & Webhooks | `integration_jobs`, `outbox_events` | Tier 2 (Supporting) | < 2 hrs | < 15 min | Pause dispatching outbound webhooks/SMS; retry queue after service verification |
| `audit_ledger` | Immutable Audit Ledger | `clinical_ledger_events`, `audit_events` | Tier 0 (Critical) | < 30 min | 0 (Zero Loss) | Maintain local append-only journal; reject any recovery rewriting historic events |
| `analytics_read_models` | Analytics & Operational Command | `command_center_threshold_rules`, `analytics_runs`| Tier 3 (Internal) | < 8 hrs | < 24 hrs | Derived data; rebuild from canonical records once operational database is online |

---

## 3. Current Protection Gaps & Deficiencies

1. **Absence of Governed Disaster Recovery & BIA Catalog:**
   - No relational table stores the authoritative list of critical domains, recovery priorities, approved RTO/RPO targets, and accountability owners.
2. **Missing Dynamic Backup Catalog & Automated Checksums:**
   - Backups created ad-hoc without relational tracking of SHA-256 digests, encryption status, source sizes, or verification outcomes.
3. **No Governed Restore Drill Orchestrator:**
   - Previous drills were manual scratch scripts. No API exists to trigger an isolated test restore, execute step-by-step technical integrity checks, verify application workflow invariants, and safely clean up resources.
4. **No Downtime Runbooks & Offline Reconciliation Engine:**
   - When the clinic operates during an outage (e.g. power/network failure), staff record notes on paper. There is no governed digital reconciliation queue with duplicate detection, identity verification, and clinician sign-off.
5. **No Visual Disaster Recovery Workbench in Web UI:**
   - Clinic administrators and SREs have no interface to inspect backup freshness, trigger isolated restore drills, view downtime procedures, or reconcile downtime cards.

---

## 4. Implementation Plan for Prompt 40

### 4.1 Schema Migration (`039_disaster_recovery_and_business_continuity_schema.sql`)
- `dr_domain_criticality_catalog`: Governed BIA registry with RTO/RPO, owners, and degraded mode rules.
- `dr_backup_catalog`: Tracks physical online backups, SHA-256 checksums, encryption state, and verification logs.
- `dr_restore_drill_executions`: 7-step orchestrated restore verification pipeline tracking duration, RTO/RPO performance, technical checks, and cleanup status.
- `dr_business_continuity_runbooks`: Formal downtime playbooks with operational and clinical owners, allowed/prohibited actions, and resumption criteria.
- `dr_downtime_reconciliation_records`: Governed reconciliation queue for offline-captured patient encounters, vitals, prescriptions, and billing.

### 4.2 RBAC Permissions (`apps/api/core/permissions.py`)
- `dr:read`: View DR catalog, backups, drills, runbooks, and reconciliation records.
- `dr:backup`: Execute online database snapshot and calculate checksums.
- `dr:drill`: Initiate and execute isolated restore drill.
- `dr:reconcile`: Review and import offline downtime records into canonical tables.
- `dr:manage`: Update BIA targets, runbooks, and sign off on business resumption.

### 4.3 Domain Engine (`apps/api/domains/disaster_recovery.py`)
- `DisasterRecoveryContinuityEngine`:
  - Catalog management: Query domain criticality, update RTO/RPO policies.
  - Backup creation: Live online snapshot using `sqlite3.Connection.backup` with SHA-256 checksum, file size, and `PRAGMA integrity_check`.
  - Restore drill runner: Isolated temp directory restore, schema check, table count parity, workflow smoke testing (draft vs signed preservation, outbox side-effect suppression, foreign key checks), RTO/RPO delta math, and bounded cleanup.
  - Hard Production Safeguard: Refuse to execute restore drills against live production database paths (`ValidationError` / `ForbiddenError`).
  - Downtime reconciliation: Ingest offline paper records, detect duplicate references, enforce identity validation, and support clinician approval.

### 4.4 REST API Routes (`apps/api/routes/disaster_recovery.py`)
- `GET /api/v1/dr/domains`: List criticality catalog and RTO/RPO targets.
- `POST /api/v1/dr/backups`: Create online verified backup.
- `GET /api/v1/dr/backups`: List backup catalog.
- `POST /api/v1/dr/drills`: Execute isolated restore drill.
- `GET /api/v1/dr/drills`: List restore drill history and evidence.
- `GET /api/v1/dr/runbooks`: List downtime runbooks.
- `POST /api/v1/dr/reconciliation`: Ingest offline downtime record.
- `GET /api/v1/dr/reconciliation`: List reconciliation queue.
- `POST /api/v1/dr/reconciliation/:id/resolve`: Clinician/Admin resolves and reconciles offline record into canonical database.
- `GET /api/v1/dr/pulse`: Real-time DR posture metrics.

### 4.5 Web UI Workbench Integration
- Add "Disaster Recovery & Continuity (P40)" tab to admin workspace with pulse summary, BIA catalog, online backup generator, restore drill runner, downtime runbooks viewer, and reconciliation queue manager.

### 4.6 Automated Testing & Verification
- Unit tests (`tests/unit/test_disaster_recovery.py`): Test domain engine invariants, backup generation, isolated drill execution, production safety lockout, checksum verification, and downtime reconciliation.
- Integration tests (`tests/integration/test_disaster_recovery_api.py`): Test API endpoints with RBAC authentication and end-to-end restore drills.

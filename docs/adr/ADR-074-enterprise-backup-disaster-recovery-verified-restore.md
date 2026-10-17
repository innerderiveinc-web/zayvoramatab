# ADR-074: Enterprise Backup, Disaster Recovery, Business Continuity & Verified Restore Engine (Prompt 56)

- **Status:** Accepted
- **Date:** 2026-10-15
- **Author:** Principal Reliability Engineer, DevSecOps Lead & Clinical Governance Architect

---

## 1. Context & Problem Statement

ZAYVORA MATAB OS manages safety-critical clinical consultations, longitudinal electronic health records, active prescriptions, Unani herbal monograph citations, and multi-tenant clinic operational data. 

In healthcare IT systems, backups that have not been empirically restored and verified in an isolated environment represent unverified risk. Prior to Prompt 56:
1. Backups were treated as static file copies without cryptographic manifests, tamper-evident signatures, or component coverage metadata.
2. Restore operations carried high risk of side-effect leakage (e.g., executing outbound notification queues, triggering external webhook endpoints, or submitting real payment calls from restored environments).
3. RPO (Recovery Point Objective) and RTO (Recovery Time Objective) targets were qualitative estimates rather than empirically measured seconds recorded in automated drill logs.
4. Multi-tenant clinic data lacked explicit restore boundary validation, creating risks of cross-tenant leakage during restore operations.
5. Deletion lifecycle policies lacked cryptographic immutable lock guarantees against premature destruction or ransomware tampering.
6. DR audit actions lacked tamper-evident chaining.

A comprehensive, mathematically sound, zero-trust backup, disaster recovery, business continuity, and verified restore engine is required to ensure clinical provenance and operational survivability.

---

## 2. Decision & Architecture

We implemented the **Enterprise Backup, Disaster Recovery, Business Continuity & Verified Restore Engine** via Migration 053 and `BackupRestoreEngine`, incorporating the following core architectural pillars:

### Pillar 1: Governed Backup Manifests & Cryptographic Chain of Custody
- **Online Zero-Downtime SQLite Snapshots:** Utilizes SQLite's online backup API (`conn.backup(pages=100)`) in WAL mode to generate consistent, uncorrupted database copies without locking concurrent writers or clinic operations.
- **Cryptographic Companion Manifests:** Generates companion `.manifest.json` artifacts alongside database snapshots containing:
  - Database SHA-256 digest (`database_checksum_sha256`).
  - Attachments/artifacts SHA-256 digest (`attachments_checksum_sha256`).
  - Baseline table record counts (`table_record_counts_json`).
  - Schema and application versions (`schema_version='053'`, `application_version='1.0.0-enterprise'`).
  - Deterministic HMAC-like SHA-256 signature (`manifest_signature_sha256`) binding the manifest ID, backup ID, organization ID, database hash, attachments hash, table record counts, and schema version.
- **Independent Validation:** Real-time tamper detection recomputing physical file SHA-256 and manifest signatures, marking modified or corrupted artifacts as `tamper_detected` or `corrupted`.

### Pillar 2: Point-in-Time Recovery (PITR) Markers & Empirical RPO Measurement
- **Canary Checkpoint Markers:** Allows clinics to record timestamped checkpoints (`dr_pitr_recovery_points`) with passive WAL flushes (`PRAGMA wal_checkpoint(PASSIVE);`) and embedded canary payloads.
- **Empirical RPO Measurement:** Calculates exact data-loss windows in seconds during restore drills based on the delta between the target checkpoint timestamp and the snapshot timestamp ($RPO \le 300\text{s}$ target).

### Pillar 3: 7-Phase Isolated Restore Drill Execution with Hard Side-Effect Suppression
Executes isolated recovery exercises within disposable sandbox environments (`tempfile.mkdtemp()`) across 7 strictly ordered phases:
1. **Preflight Authorization & Safety Gate:** Requires explicit authorization. Emergency production restores require Chief Medical Officer (`CHIEF_MEDICAL_OFFICER`) or VP Security (`VP_SECURITY`) credentials.
2. **Backup Artifact & Manifest Verification:** Validates physical file presence, recomputes SHA-256, and verifies manifest signatures before restore.
3. **Isolated Sandbox Restore & Side-Effect Suppression:** Restores into a temporary sandbox with hard suppression of outbound side-effects (`outbound_messaging_suppressed=True`, `payments_suppressed=True`, `webhooks_suppressed=True`, `production_queues_paused=True`).
4. **Technical Schema & Constraint Integrity:** Executes `PRAGMA integrity_check;` and `PRAGMA foreign_key_check;` asserting zero violations.
5. **Clinical Invariant Verification:** Verifies patient records, encounters, prescriptions, and approved clinical monographs are present and uncorrupted.
6. **Multi-Tenant Boundary Validation:** Asserts all restored clinical entities belong to their designated `organization_id` and verifies cross-tenant IDOR defense on the restored instance.
7. **Sandbox Cleanup & Metrics Finalization:** Measures precise empirical RTO and RPO in seconds, verifies target compliance ($RTO \le 900\text{s}$, $RPO \le 300\text{s}$), and cleans up disposable sandboxes.

### Pillar 4: Production Promotion Gatekeeper
- Enforces a fail-closed promotion gate (`dr_isolated_restore_verifications`).
- Only restores that have passed all technical, clinical, and tenant isolation checks can be promoted (`PROMOTION_APPROVED`).
- Promoted restores require documented signoff notes and officer attribution.

### Pillar 5: Retention Lifecycle & Immutable Locks
- Supports 4 standardized retention tiers: `7_days_operational` (7d), `30_days_standard` (30d), `365_days_compliance` (365d), and `7_years_clinical_legal` (2555d).
- Implements immutable lock protection (`immutable_lock_until`). Backups under active lock cannot be purged by automated retention jobs, providing resilience against ransomware and unauthorized deletion.

### Pillar 6: Cryptographic SHA-256 Chained DR Governance Audit Ledger
- Records all backup creations, manifest verifications, restore drills, promotion decisions, and retention cleanups in an immutable ledger (`dr_governance_audit_ledger`).
- Rooted at genesis block `DGL-GENESIS-0001` with hash `81451b0bd926dd981dd08c993c0252c8380a0d9a236847ef1e696d58c5637941`.
- Provides an automated integrity checker detecting any modification, deletion, or reordering of blocks.

---

## 3. Consequences

### Positive Consequences
- **Zero-Downtime Live Backups:** WAL-mode SQLite backups run concurrently with active patient consultations without degradation or locks.
- **Provable Chain of Custody:** Signed manifests guarantee backup authenticity and detect byte-level tampering.
- **Zero Risk of Accidental Outbound Messaging:** Restored instances run in strict sandbox isolation with suppressed webhooks and messaging queues.
- **Empirical Compliance:** Timed drill logs provide auditable proof of RTO and RPO for regulatory audits.
- **Multi-Tenant Safety:** Strict tenant isolation validation prevents cross-clinic data leaks.

### Operational Constraints
- **Storage Management:** Retaining full snapshots requires disk space monitoring. The automated retention engine must run on schedule.
- **Executive Authorization:** Emergency production restores cannot be initiated without CMO or VP Security signoff.

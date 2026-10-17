# ADR-059: Disaster Recovery, Business Continuity, Backup/Restore Verification & Resilience Engineering

- **Status:** Accepted
- **Date:** 2026-10-14
- **Phase:** Prompt 40 (Phase 40) — ZAYVORA MATAB OS
- **Deciders:** Principal SRE, Software Architect, Database Engineer, Application Security Lead, Clinical Operations Continuity Lead

---

## 1. Context and Problem Statement

ZAYVORA MATAB OS operates as a standalone clinic and hospital operating system managing master patient records, unani assessments, botanical formulations, signed prescriptions, billing ledgers, and regulatory health information exchanges. Operating in production exposes the clinic to risks of hardware disruption, catastrophic power failure, database corruption, accidental deletions, network partitions, and third-party gateway outages.

Traditional approaches to disaster recovery in medical software suffer from critical flaws:
1. **Unverified Backups:** Relying on backup jobs reporting "success" without ever executing isolated restoration drills to verify data integrity, foreign key references, and schema completeness.
2. **Destructive Production Testing:** Testing restore scripts against live production systems, risking catastrophic data loss, race conditions, or accidental overwrites.
3. **Absence of Governed Business Impact Analysis (BIA):** Treating all tables identically, without clear RTO/RPO targets, domain owners, or degraded-mode operating playbooks.
4. **Data Loss During Downtime:** When systems go offline, clinic staff record notes on paper; without a governed digital reconciliation queue, paper records are lost, duplicated, or entered without clinical attribution.
5. **Accidental Side-Effect Dispatches:** Restoring a database snapshot into a test or recovery environment that immediately replays outbound payment charges, SMS messages, or ABDM sync calls.
6. **Clinical Safety Bypasses:** Allowing recovery procedures to guess missing clinical facts or silently normalize corrupted medical records without clinician approval.

A comprehensive, privacy-preserving, and mathematically verified disaster recovery and business continuity platform was required.

---

## 2. Decision Drivers

1. **Non-Negotiable Safety & Isolation Invariants:**
   - Restore drills must default strictly to isolated non-production sandboxes (`tempfile.mkdtemp()`) with isolated credentials and suppressed external network egress.
   - Any restore request targeting production paths without multi-party emergency authorization must be rejected immediately (`ForbiddenError` / HTTP 403).
2. **Governed Business Impact Analysis (BIA) & Criticality Catalog:**
   - 12 core clinical and operational domains mapped into 4 criticality tiers (`tier_0_critical`, `tier_1_core`, `tier_2_supporting`, `tier_3_internal`) with approved RTO and RPO targets, accountable owners, and degraded-mode policies.
3. **Live Online Zero-Downtime Database Backups:**
   - SQLite native non-blocking backup API (`sqlite3.Connection.backup` with chunked page streaming) operating in Write-Ahead Logging (`WAL`) mode with automatic cryptographic SHA-256 digest computation and `PRAGMA integrity_check`.
4. **7-Step Restore Verification Pipeline:**
   - Strict progressive pipeline:
     $$\text{Authorize \& Scope} \longrightarrow \text{Validate Backup} \longrightarrow \text{Restore in Isolation} \longrightarrow \text{Verify Technical Integrity} \longrightarrow \text{Verify Application Workflows} \longrightarrow \text{Document Results} \longrightarrow \text{Clean Up}$$
   - Technical checks: `PRAGMA integrity_check = ok`, `PRAGMA foreign_key_check = 0 violations`, schema table parity.
   - Workflow checks: RBAC viability, encounter lifecycle preservation (draft vs signed), prescription signature retention, clinical safety rules intact, and transactional outbox suppression.
5. **Business Continuity & Downtime Runbooks:**
   - Role-owned playbooks (`cb-app-offline`, `cb-db-outage`, `cb-network-partition`, `cb-payment-gateway-down`) defining permitted vs. prohibited clinical capabilities and resumption criteria.
6. **Governed Downtime Reconciliation Queue:**
   - Secure digital queue for ingesting paper downtime cards, enforcing duplicate reference detection, redacting sensitive credentials (`[REDACTED_SECRET]`), and requiring clinician sign-off before committing to canonical records.
7. **Business Resumption Authorization:**
   - Formal sign-off state machine requiring an authorized clinician or SRE before operational service is certified as resumed.

---

## 3. Considered Options

- **Option 1: Rely on Cloud-Provider Automatic VM / Volume Snapshots.**
  - *Pros:* Fully managed by cloud infrastructure.
  - *Cons:* Violates standalone Unani matab on-premise operational mandates, fails to verify database application-level consistency or foreign keys, does not provide a downtime paper reconciliation queue, and offers zero visibility to clinic operators.
- **Option 2: Ad-Hoc Shell Scripts & Manual Restore Drills.**
  - *Pros:* Simple to write.
  - *Cons:* Prone to human error, lacks auditability, no relational ledger of drill executions, no automated step verification, and risks accidental production overwrites.
- **Option 3 (Selected): In-Database Governed Disaster Recovery, Backup Verification & Business Continuity Engine.**
  - *Pros:* Fully integrated into ZAYVORA MATAB OS via Migration 039; provides dynamic BIA criticality catalog, live online non-blocking backups with SHA-256 digests, automated 7-step isolated sandbox restore drills with hard production lockouts, downtime runbooks, offline record reconciliation queue, and real-time posture indicators in the web workbench.

---

## 4. Decision Outcome

We implemented Option 3:

### 1. Database Schema (Migration 039)
- `dr_domain_criticality_catalog`: BIA registry storing 12 domains, tiers, owners, RTO/RPO targets, and policies.
- `dr_backup_catalog`: Physical backup snapshots, SHA-256 checksums, encryption status, and integrity logs.
- `dr_restore_drill_executions`: 7-step drill executions ledger with durations, data loss windows, and verification reports.
- `dr_business_continuity_runbooks`: Downtime playbooks with operational/clinical leads, safe/prohibited actions, and resumption criteria.
- `dr_downtime_reconciliation_records`: Paper-to-digital reconciliation queue with duplicate detection and clinician sign-off.

### 2. Domain Engine (`apps/api/domains/disaster_recovery.py`)
- `DisasterRecoveryContinuityEngine`: Provides BIA policy updates, online backup snapshots, 7-step isolated restore drills, hard production lockout, and downtime record reconciliation.

### 3. REST API Routes (`apps/api/routes/disaster_recovery.py`)
- Mounted 13 endpoints under `/api/v1/dr/` for domains, backups, drills, runbooks, reconciliation, and posture pulse.

### 4. RBAC Permissions (`apps/api/core/permissions.py`)
- Added `dr:read`, `dr:backup`, `dr:drill`, `dr:reconcile`, and `dr:manage`.

### 5. Web UI Workbench
- Added "Disaster Recovery & Continuity (P40)" tab with operational pulse cards, BIA catalog, online backup generator, isolated drill runner, downtime runbooks viewer, and reconciliation queue manager.

---

## 5. Consequences

### Positive
- Validated proof of recoverability: Backups are empirically verified in disposable sandboxes without risking live data.
- Controlled clinic downtime: Standardized downtime forms, safe/prohibited capability boundaries, and a digital reconciliation queue prevent double-entry and missing patient notes.
- High operational transparency: Real-time pulse cards display verified RTO/RPO posture and drill durations.

### Negative / Trade-offs
- Offline paper transcription requires manual clinician review to prevent transcription errors.
- Isolated restore drills consume temporary disk space during execution (safely cleaned up post-verification).

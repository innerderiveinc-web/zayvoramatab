# ADR-060: Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Governance Engine

## Status
Accepted

## Context
As a standalone clinic and Unani practice operating system operating under AYUSH, Indian EHR Standards, Digital Personal Data Protection Act (DPDPA 2023), and National Medical Commission guidelines, ZAYVORA MATAB OS must govern the full lifecycle of records—from creation through active clinical use, statutory retention, archival, legal hold, and disposal. 

Without an enterprise lifecycle governance engine, systems are prone to:
1. Accidental or unauthorized physical destruction of signed encounters and prescriptions, violating medical record keeping mandates (minimum 7-year retention).
2. Data spillage across unmapped secondary copies (filesystem exports, read-model caches, event queues).
3. Inability to freeze records under legal hold during court cases, consumer dispute notices, or clinical safety inquiries.
4. Premature deletion of tax/financial or security audit records.
5. Inability to fulfill patient data subject privacy rights (access, export, correction, erasure) in a governed, verifiable manner.

## Decision
We implement a unified, multi-store, policy-governed data lifecycle and retention framework comprising:

1. **Database Schema (Migration 040):**
   - `data_lifecycle_inventory_catalog`: Authoritative inventory of 14 clinical and operational data categories, tracking canonical source tables, storage types (`relational_table`, `file_system_artifact`, `event_queue`, `cache_read_model`), sensitivity classifications (`restricted_phi`, `financial_pci`, `operational_confidential`, `public_knowledge`), and linked physical copies.
   - `data_lifecycle_policies`: Versioned, approver-governed retention policies specifying retention triggers, periods (in days), archival rules (`RESTRICTED_READ_ONLY`, `COLD_STORAGE_PARTITION`, `FILESYSTEM_COMPRESSED`), disposal actions (`restrict`, `deidentify`, `delete`, `manual_review`), and hold behaviors.
   - `data_lifecycle_legal_holds`: Universal preservation registry overriding all retention policies. Active holds immediately and strictly freeze disposal or archival operations on affected records across categories and patients.
   - `data_lifecycle_evaluation_runs`: Deterministic, side-effect free dry-run evaluations computing counts of evaluated, eligible, held, and ineligible records without mutating underlying tables.
   - `data_lifecycle_operations`: Governed multi-store disposal and archival ledger recording per-store verification statuses and SHA-256 audit receipts.
   - `data_lifecycle_requests`: Patient data subject privacy rights request pipeline with mandatory identity verification gate, plan approval, and verified execution.

2. **Core Clinical Immutability & Safety Invariant:**
   - Physical row deletion of signed clinical encounters and signed prescriptions is strictly prohibited. Governed disposal on signed clinical records transitions rows to `archived` / `restricted` status while preserving legal provenance and consultation history.

3. **Multi-Store Reach & Truthful Statuses:**
   - Deletion operations account for all registered storage tiers and distinguish `restricted`, `deletion_partial`, and `verified_complete`.

4. **REST API Interface:**
   - 15 endpoints mounted under `/api/v1/lifecycle/` covering inventory, versioned policies, approval, dry-run evaluation, governed disposal, legal holds, privacy requests, and real-time pulse metrics.

5. **Web UI Workbench:**
   - Interactive console under the Clinical Knowledge Base and Governance view featuring real-time pulse telemetry cards, dry-run simulator, legal hold register, policy catalog, data inventory table, and privacy request tracking.

## Consequences
- **Positive:** Full statutory compliance with AYUSH, NMC, and DPDPA mandates; zero risk of silent destruction of signed patient records; comprehensive visibility into data estate; legally defensible legal hold freezes.
- **Negative:** Additional operational overhead requiring clinical director and DPO authorization for policy updates and erasure fulfillments.

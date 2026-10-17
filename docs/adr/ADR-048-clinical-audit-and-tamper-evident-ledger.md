# ADR-048: Clinical Audit, Accountability, Compliance Evidence & Tamper-Evident Event Ledger (Prompt 29)

## Status
Accepted

## Context
Clinical computing environments require absolute accountability, regulatory non-repudiation, and tamper-evident logging for high-consequence clinical and administrative actions. Prior to Prompt 29, application actions were tracked in standard relational audit tables that lacked continuous cryptographic chaining, fail-closed guarantees for gated operations, formal data-minimization boundaries, or append-only dispute mechanisms. In traditional architectures, administrative database access allows silent tampering, deletion, or retrofitting of historical records without detection.

Prompt 29 establishes an auditable, immutable, cryptographically verifiable event ledger for ZAYVORA MATAB OS that proves whether an event occurred, when it occurred, who authorized it, what inputs were present, and whether any byte has been modified since it was recorded.

## Decision
1. **Migration 028 Persistence:**
   - `clinical_ledger_events`: Central event ledger with strictly continuous integer sequence numbering (`ledger_sequence`), server NTP UTC timestamps, tenant/clinic isolation, exact entity versioning, result state tracking, and continuous SHA-256 hash chaining:
     $$H_i = \text{SHA-256}(C_i \parallel H_{i-1})$$
     anchored from `GENESIS_HASH = 0000000000000000000000000000000000000000000000000000000000000000`.
   - `audit_annotations`: Append-only dispute and correction ledger. Original ledger events and hashes are never edited or deleted; corrections are appended as child annotations with documented rationale and supporting ticket references.
   - `audit_integrity_checkpoints`: Verification checkpoints recording the outcome of cryptographic integrity sweeps (`passed_for_checked_scope` or `failed_integrity_mismatch`), total events verified, root hash, and any mismatch diagnostics.
   - `audit_retention_policies`: Governed statutory retention rules (e.g., standard clinical 7-year / 2555 days minimum, break-glass 10-year, safety/adverse event 25-year) with deletion prohibition flags.
   - `audit_legal_holds`: Formal litigation and regulatory inspection holds locking matching scopes from archiving or purging.
   - `audit_evidence_exports`: Purpose-bound compliance evidence export packages bound to an integrity checkpoint root hash and signed by an authorized compliance officer.
2. **Domain Engine (`ClinicalAuditLedgerEngine`):**
   - **Strict Data Minimization:** Passwords, tokens, bearer secrets, API keys, and full narrative clinical charts are sanitized/redacted before canonical serialization, preventing sensitive data leakage into the audit subsystem.
   - **Deterministic Canonical Serialization:** Fields are serialized using RFC 8785 canonical JSON formatting (sorted keys, compact delimiters) to guarantee deterministic cryptographic hash reproducibility.
   - **Fail-Closed Protection:** Consequential actions (e.g. `PRESCRIPTION_SIGN`, `BREAK_GLASS_ACCESS`, `SAFETY_OVERRIDE`) fail closed: if the audit event cannot be committed to the ledger, the clinical action itself is aborted.
   - **No Silent Auto-Repair:** If an integrity sweep detects a sequence jump, missing record, or payload hash mismatch, it records a `failed_integrity_mismatch` checkpoint with explicit error diagnostics. It never silently overwrites historical hashes.
3. **REST APIs & UI:**
   - 9 endpoints mounted under `/api/v1/audit/ledger/*` with granular role-based permissions (`audit:read`, `audit:record`, `audit:verify`, `audit:annotate`, `audit:export`, `audit:manage`).
   - Integrated "Audit Ledger & Integrity (P29)" console into the Knowledge Admin UI featuring live chain metrics, event filters, inspection modal, annotation modal, one-click integrity sweeps, legal hold placement, and compliance package exports.

## Consequences
- **Positive:**
  - Guaranteed non-repudiation and cryptographic tamper evidence meeting statutory healthcare standards (HIPAA, ISO 27799, 21 CFR Part 11, and National Digital Health Guidelines).
  - Absolute preservation of historical truth: silent deletes and edits are architecturally impossible.
  - Granular accountability across clinical signing, safety overrides, break-glass emergencies, and knowledge releases.
- **Negative / Trade-offs:**
  - Modest write latency overhead incurred for serial SHA-256 hash chaining and canonical JSON formatting during consequential transactions.

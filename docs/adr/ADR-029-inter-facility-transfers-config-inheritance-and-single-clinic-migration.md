# ADR-029: Inter-Facility Transfers, Layered Configuration Inheritance, and Single-Clinic Migration

- **Status:** Accepted
- **Date:** 2026-10-13
- **Phase:** Prompt 11 — Multi-Doctor, Multi-Branch & Hospital Administration Foundation

## Context

Operating multiple branches requires controlled patient movement between branches, consistent yet customizable operational policies across facilities, prerequisite-checked module activation, governed external integration credentials, and a safe upgrade path for existing single-clinic deployments.

## Decision

1. **Controlled Inter-Facility Transfers (`facility_transfers`, `facility_transfer_events`):**
   - Initiating a transfer sets `status = 'requested'` (never automatically `accepted`) and preserves the originating facility's source encounter untouched.
   - Only staff authorized at the receiving facility can `accept`, `decline`, or `complete` the transfer (`TRANSFER_RECIPIENT_UNAUTHORIZED`).
   - Completing an accepted transfer creates a new linked `TRANSFER_RECEIVING_VISIT` encounter at the receiving facility while preserving the source encounter at the originating facility.
2. **Cross-Facility Patient Continuity & Governed Merge (`patient_facility_links`, `patient_merge_requests`):**
   - Cross-facility encounter visibility is governed by the organization's `cross_facility_continuity_policy` (`SAME_ORG_TREATMENT_TEAM`, `EXPLICIT_CONSENT_REQUIRED`, `FACILITY_ISOLATED`) and per-branch `privacy_restriction_level` (`STANDARD`, `RESTRICTED_BRANCH_ONLY`). When restricted records are omitted, the API discloses `restricted_records_omitted_count` and `has_inaccessible_branch_records: true`.
   - Duplicate patient merges across branches require a formal `patient_merge_requests` submission and human approval (`review_patient_merge_request`), recording every relinked record in `patient_merge_events`.
3. **4-Tier Layered Configuration Inheritance & Module Prerequisite DAG:**
   - Configuration resolves in order: `PLATFORM_SECURITY_BASELINE` (immutable floor) > `FACILITY_OVERRIDE` > `ORGANIZATION` > `DEFAULT`.
   - Any attempt to weaken platform security controls (`PLATFORM_SECURITY_CONSTRAINT_VIOLATION`) or store plaintext secrets (`PLAINTEXT_SECRET_PROHIBITED`) is rejected.
   - Facility configuration changes are versioned in `configuration_versions` and support deterministic rollback (`rollback_facility_configuration`).
   - Facility modules (`facility_module_entitlements`) enforce prerequisite DAG validation (`MODULE_PREREQUISITES_NOT_MET`) and block disabling modules with active dependents (`MODULE_HAS_ACTIVE_DEPENDENTS`).
4. **Repeatable Single-Clinic Migration (`run_single_clinic_migration`):**
   - Supports `DRY_RUN` and `EXECUTE` modes, reconciles pre/post record counts across all clinical and operational tables, detects orphan records, and idempotently links legacy single-clinic records to the default facility.

## Consequences

- Ensures safe clinical handoffs between branches without overwriting originating clinical encounters.
- Provides auditable configuration governance and zero-data-loss migration from single-clinic to multi-branch operation.

# Repository Audit & Canonical Workflow Entity Mapping (Prompt 35)

**Product:** ZAYVORA MATAB OS — Standalone Unani Clinic & Practice Operating System  
**Phase:** 35 — Clinical Workflow Automation, Rules Engine & Human-Approved Task Orchestration  
**Audit Date:** October 2026  
**Auditor:** Principal Software & Clinical Safety Architect  

---

## 1. Executive Summary & Purpose

The purpose of Phase 35 is to implement a robust, deterministic, version-controlled **Workflow Automation, Rules Engine & Human-Approved Task Orchestration Layer**. It automates routine administrative coordination, reminder dispatch, stock checks, and queue escalation across the clinic, while preserving human accountability and enforcing strict non-negotiable boundaries on clinical decisions.

Before introducing new tables or engines, this audit catalogs all existing domain entities, state machines, background task queues, and communication facilities in ZAYVORA MATAB OS.

---

## 2. Inventory of Existing Canonical Entities & State Machines

| Domain Entity | Primary Schema / Migration | Implementation Status | Canonical State Machine | Automation Relevance for Phase 35 |
| :--- | :--- | :--- | :--- | :--- |
| **Appointments** | `001_foundation_schema.sql`, `010_clinic_operations_os_schema.sql` | Production-backed | `booked` $\to$ `confirmed` $\to$ `arrived` $\to$ `in_progress` $\to$ `completed` / `cancelled` / `no_show` | Event source for appointment prep tasks and reminders (Workflow A). |
| **Queue Tokens** | `010_clinic_operations_os_schema.sql`, `033_clinical_command_center_capacity_planning_schema.sql` | Production-backed | `checked_in` $\to$ `waiting` $\to$ `called` $\to$ `in_consultation` $\to$ `completed` / `cancelled` | Event source for stall alerts and bottleneck escalations (Workflow C). |
| **Encounters** | `002_patient_encounter_schema.sql` | Production-backed | `draft` $\to$ `signed` $\to$ `locked` / `amended` | Source of truth for completed clinical visits. Automation **cannot** sign encounters. |
| **Follow-up Plans** | `009_care_continuity_communications_schema.sql` | Production-backed | `active` $\to$ `amended` $\to$ `completed` $\to$ `cancelled` | Authorized clinician plans containing explicit due dates (Workflow B). |
| **Care Continuity Tasks** | `009_care_continuity_communications_schema.sql`, `024_longitudinal_patient_timeline_schema.sql` | Production-backed | `planned` $\to$ `due` $\to$ `in_progress` $\to$ `completed` / `rescheduled` / `escalated` / `needs_review` | Action target for automated task generation and assignment. |
| **Communication Preferences** | `009_care_continuity_communications_schema.sql` | Production-backed | Explicit consent, `opt_out_status` (0/1), `do_not_contact_scope`, `quiet_hours`, `preferred_channel` | Mandatory consent check before enqueuing any patient-facing message. |
| **Communication Templates** | `009_care_continuity_communications_schema.sql` | Production-backed | `draft` $\to$ `pending_review` $\to$ `approved` $\to$ `retired` with version pinning and placeholder allowlists | Mandatory template approval check. Prohibits sensitive clinical fields in general templates. |
| **Communication Outbox** | `009_care_continuity_communications_schema.sql` | Production-backed | `pending` $\to$ `dispatched` $\to$ `delivered` / `failed` / `suppressed` | Target queue for approved communications. |
| **Invoices & Billing** | `010_clinic_operations_os_schema.sql` | Production-backed | `DRAFT` $\to$ `FINALIZED` $\to$ `PARTIALLY_PAID` $\to$ `PAID` / `VOID` | Sensitive administrative domain. Modifications require human approval. |
| **Inventory Batches** | `010_clinic_operations_os_schema.sql` | Production-backed | `AVAILABLE` $\to$ `QUARANTINED` $\to$ `DEPLETED` / `EXPIRED` | Monitored by Workflow E for low-stock and near-expiry review tasks. |
| **Integration Jobs & DLQ** | `031_integration_operations_reliability_schema.sql` | Production-backed | 20-state machine; `dead_letter_items` | Monitored by Workflow F for automated retries or operator review tasks. |
| **Command Center Alerts** | `033_clinical_command_center_capacity_planning_schema.sql` | Production-backed | `ACTIVE` $\to$ `ACKNOWLEDGED` $\to$ `RESOLVED` | Operational alert desk integration. |
| **Audit Ledger** | `028_clinical_audit_compliance_tamper_evident_ledger_schema.sql` | Production-backed | Immutable append-only cryptographic event hash chain | Records all automated action executions, approvals, and overrides. |

---

## 3. Gaps & Integration Opportunities

1. **Workflow Rules Engine:** Currently, threshold rules exist for the Command Center (`command_center_threshold_rules`), and clinical rules exist for knowledge governance (`governed_clinical_rules`), but there is no general, schema-validated, event-triggered workflow automation engine.
2. **Action Classification & Approval Gates:** Prior phases handled approvals in specific silos (e.g. CDS approval, Rule release approval). Phase 35 introduces a unified action classification registry (`routine_administrative`, `communication`, `sensitive_administrative`, `clinical_review_only`) with deterministic approval gates.
3. **Execution Outbox & Traceability:** Workflow events require a transactional envelope, deterministic idempotency keys, safe pause on ambiguity, and a dedicated execution attempt ledger.

---

## 4. Architectural Boundaries & Non-Negotiables

- **No Arbitrary Code Execution:** The rule evaluator must use a bounded, strictly allowlisted operator set (`equals`, `not_equals`, `in`, `not_in`, `exists`, `not_exists`, `before`, `after`, `greater_than`, `less_than`). No `eval`, `exec`, or dynamic SQL.
- **Human Clinical Primacy:** Autonomous prescription, dosage, nuskha formulation, and clinical note signing are strictly prohibited. Automation may only create a `clinical_review_only` task for an authorized human clinician.
- **Consent Pre-flight:** Patient communications must pass active consent, quiet hours, and template validation before dispatch.

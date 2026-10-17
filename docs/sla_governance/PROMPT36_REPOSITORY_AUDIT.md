# Phase 36 Repository Audit: Enterprise Workflow Intelligence, SLA Governance & Exception Resolution Engine

**Audit Date:** 2026-10-14  
**Auditor:** Principal Software Architect, Senior Full-Stack Engineer & Clinical Safety Governance Lead  
**Scope:** Existing task stores, workflow state machines, rules engine (P35), command center (P34), analytics (P33), event ledgers (P29), communications outbox, and RBAC enforcement.

---

## 1. Inventory & Capability Classification

| Component / Layer | Canonical Source in Codebase | Feature Classification | Reuse vs Extend vs Missing | Technical Architectural Decision |
| :--- | :--- | :--- | :--- | :--- |
| **Tasks & Work Items** | `care_continuity_tasks` (Migration 024)<br>`follow_up_tasks` (Migration 009)<br>`workflow_planned_actions` (Migration 034) | **Production-backed** | **Extend** | Canonical source of operational work items exists. We unify exception management under `workflow_exceptions` without creating duplicate task engines. |
| **Workflow & Rules Engine** | `WorkflowAutomationEngine` (`apps/api/domains/workflow_automation.py`)<br>`workflow_rules`, `automation_events` (Migration 034) | **Production-backed** | **Reuse & Extend** | Reuse P35's event ingestion envelope and deterministic rule triggers. Feed rule-detected exceptions into SLA policy tracking. |
| **Operational Thresholds & Alerts** | `command_center_threshold_rules`<br>`operational_alerts` (Migration 033) | **Production-backed** | **Reuse & Extend** | Extend threshold comparisons with SLA policy governance (`sla_policies`), pause/resume intervals, and multi-stage escalations. |
| **Timers & Elapsed Time Calculation** | `ClinicalCommandCenterEngine` (`apps/api/domains/command_center.py`) | **Production-backed** | **Extend** | Centralize deterministic elapsed time vs business hours calculation with pause adjustments (`sla_pause_intervals`). |
| **Scheduler & Worker** | Background task runner, durable queue, and polling workers | **Production-backed** | **Reuse** | Avoid in-memory timers; rely on persisted state, timestamps, and idempotent evaluation cycles. |
| **Notification Outbox** | `outbound_messages`, `communication_preferences` (Migration 009) | **Production-backed** | **Reuse** | Reuse durable outbox with strict patient privacy, data minimization, and pre-flight consent verification. |
| **Tamper-Evident Audit Ledger** | `audit_ledger_events`, `clinical_ledger_events` (Migration 028) | **Production-backed** | **Reuse** | All SLA policy approvals, exception lifecycle transitions, assignments, and verifications append immutable audit records. |
| **RBAC & Multi-Tenant Scoping** | `apps/api/core/permissions.py`, `organizations`, `facilities` (Migration 001/011) | **Production-backed** | **Extend** | Add granular `sla:read`, `sla:manage`, `sla:approve`, `exception:manage`, `exception:verify` permissions with strict tenant/branch scoping. |

---

## 2. Canonical Source Records & Defensible Operational Policies

Every supported exception is strictly tied to a persisted operational source record:

| Exception Category | Canonical Source Entity | Canonical Trigger Event / Condition | Defensible Policy Key | Accountable Role | Verification Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`administrative`** | `queue_tokens` | Check-in to call waiting duration exceeds threshold | `sla-pol-queue-stall` | `FRONT_DESK` / `CLINIC_ADMIN` | Self-resolve when token called/completed |
| **`follow_up`** | `care_continuity_tasks` / `follow_up_tasks` | Longitudinal care coordination task past due date | `sla-pol-overdue-followup` | `CARE_COORDINATOR` | Resolution code required (`CONTACT_ESTABLISHED`) |
| **`intake_gap`** | `patients` | Missing mandatory contact or demographic information | `sla-pol-missing-demographics`| `RECEPTIONIST` | Record updated check |
| **`inventory`** | `inventory_batches` | Dispensary stock level below critical reorder threshold | `sla-pol-stock-depleted` | `PHARMACIST` | Independent verification required (`CLINIC_ADMIN`) |
| **`integration`** | `integration_jobs` | Persistent integration job dead-letter queue backlog | `sla-pol-dlq-resolution` | `ORG_ADMIN` | Job reprocessed check |
| **`governance`** | `workflow_planned_actions` | Sensitive action awaiting human approval > approved SLA | `sla-pol-approval-backlog` | `CLINIC_ADMIN` | Attributable approval/rejection check |
| **`clinical_review`** | `care_continuity_tasks` | Clinician review required for safety or regimen review | `sla-pol-clinical-review` | `CLINICIAN` | **Non-negotiable:** Human clinician assessment only! |

---

## 3. Strict Healthcare & Safety Non-Negotiables

1. **No Autonomous Clinical Actions:** The SLA engine governs operational timeliness and human task accountability. It **never** prescribes, modifies drug doses, authors nuskhas, or signs consultations.
2. **Clinical Safety Decoupling:** Clinical alarms and drug interactions are governed by the Clinical Safety Firewall (Prompt 07) and Pharmacovigilance (Prompt 27). The SLA engine routes human review tasks; it does not evaluate medical urgency or override clinical judgment.
3. **No Fabricated SLA Defaults:** SLA due times, warning margins, and escalation levels are never hardcoded as arbitrary clinical standards. They require explicit authorized policy configuration (`sla_policies`).
4. **Unmeasurable vs Breach Distinction:** Missing, stale, or contradictory source data results in `UNMEASURABLE` state—never a fabricated breach or false assurance.
5. **Separation of Duties on Verification:** Where policy mandates independent verification (`verification_required = 1`), the user who resolved the exception cannot verify it.

# Phase 35 Implementation Report: Clinical Workflow Automation, Rules Engine & Human-Approved Task Orchestration

**System:** ZAYVORA MATAB OS — Standalone Unani Clinic & Practice Operating System  
**Phase:** 35 — Workflow Automation, Rules Engine, Task Orchestration & Human Approval Gates  
**Status:** Complete & Validated (100% Test Pass Rate)  
**Date:** 2026-10-14  

---

## 1. Executive Summary & Purpose

Phase 35 delivers a deterministic, version-controlled rules and workflow automation engine for ZAYVORA MATAB OS. In busy Unani clinical practices, administrative workflows such as chart intake preparation, routine follow-up reminders, queue waiting stall escalations, missing demographic reviews, dispensary inventory threshold alerts, and dead-letter integration job alerts frequently suffer from coordination delays.

The engine automates approved administrative workflows while upholding non-negotiable healthcare safety principles:
- **Zero Autonomous Clinical Actions:** The rules engine is strictly prohibited from autonomous prescribing, dose adjustments, botanical nuskha authoring, or encounter signing. Any clinically relevant trigger strictly produces a human review task for a qualified practitioner (`REQUEST_CLINICAL_REVIEW`).
- **Zero Arbitrary Code Execution:** Complete ban on `eval()`, `exec()`, or dynamic scripting. Condition evaluation uses a bounded allowlisted set of 10 deterministic comparison operators.
- **Human Approval Gates & Cryptographic Hash Locking:** Sensitive administrative operations (`sensitive_administrative`) pause in `AWAITING_APPROVAL` with SHA-256 payload hash locking (`payload_hash`), preventing execution until attributable sign-off by authorized roles (`ORG_ADMIN`, `PHARMACIST`, `CLINIC_ADMIN`).
- **Patient Communication Consent & Quiet Hours Enforcement:** Outbound messages undergo strict pre-flight validation against `communication_preferences` (`opt_out_status = 0`, permitted scopes, approved template versions, and local quiet hours). Non-consented actions pause in `NEEDS_REVIEW`.
- **Zero-Side-Effect Dry-Run Sandbox:** Allows clinicians and administrators to preview rule matching and planned actions against sample payloads without mutating any production records.

---

## 2. Architecture & Database Schema (Migration 034)

Migration `034_clinical_workflow_automation_rules_engine_schema.sql` establishes 5 relational tables:

1. **`workflow_rules`**: Versioned workflow rules catalog.
   - Bounded status state machine: `DRAFT` $\to$ `IN_REVIEW` $\to$ `APPROVED` $\to$ `ACTIVE` $\to$ `PAUSED` $\to$ `RETIRED`.
   - Priority-based deterministic evaluation ordering (`priority ASC, rule_key ASC`).
   - Rate limit guardrails (`rate_limit_per_hour`).
2. **`workflow_rule_versions`**: Immutable snapshot ledger preserving rule definitions and revision justifications across lifecycle advancements.
3. **`automation_events`**: Canonical envelope capturing inbound clinic events (`APPOINTMENT_STATUS_CHANGED`, `QUEUE_WAITING_STALL`, `INVENTORY_THRESHOLD_BREACH`, etc.) with deduplication key enforcement (`idempotency_key = sha256(...)`).
4. **`workflow_planned_actions`**: Durable planned side effects with execution status (`QUEUED`, `AWAITING_APPROVAL`, `SUCCEEDED`, `REJECTED`, `NEEDS_REVIEW`), approval metadata, and SHA-256 payload hashes.
5. **`workflow_action_attempts`**: Immutable execution attempt ledger recording each attempt number, status (`SUCCESS`, `TRANSIENT_FAILURE`, `PERMANENT_FAILURE`), error message, and execution timestamp.

---

## 3. Action Classification Registry & RBAC Permissions

Workflow actions are strictly partitioned into four security tiers:

| Action Category | Target Roles | Execution Model | Mandatory Guardrails | Permitted Action Types |
| :--- | :--- | :--- | :--- | :--- |
| **`routine_administrative`** | `FRONT_DESK`, `RECEPTIONIST`, `CLINIC_ADMIN` | Automatic upon rule match | Idempotent key deduplication, rate limit check | `CREATE_ADMIN_TASK`, `RECORD_INTAKE_GAP`, `ESCALATE_QUEUE_STALL` |
| **`communication`** | `CARE_COORDINATOR`, `FRONT_DESK` | Automatic upon consent check | Pre-flight consent check, quiet hours, approved template version | `ENQUEUE_PATIENT_REMINDER` |
| **`sensitive_administrative`** | `PHARMACIST`, `CLINIC_ADMIN`, `ORG_ADMIN` | **Human Approval Gate Required** | Pauses in `AWAITING_APPROVAL`, SHA-256 payload hash lock | `CREATE_STOCK_REVIEW_TASK`, `RETRY_DEAD_LETTER_ITEM` |
| **`clinical_review_only`** | `CLINICIAN`, `PRACTITIONER` | **Human Clinician Review Only** | Non-negotiable boundary: generates clinical assessment task only | `REQUEST_CLINICAL_REVIEW` |

### RBAC Aliases (`apps/api/core/permissions.py`)
- `workflow:read`: View rules, actions, execution attempts, monitor pulse, and dry-run previews.
- `workflow:manage`: Create and edit rule drafts, update configurations, and advance rule lifecycle transitions.
- `workflow:approve`: Review and approve/reject planned actions held in `AWAITING_APPROVAL`.
- `workflow:execute`: Ingest domain event envelopes and trigger automated rule execution pipelines.

---

## 4. Safe Deterministic Condition Evaluation Engine

The evaluation engine in `WorkflowAutomationEngine._evaluate_conditions` enforces a fail-closed policy across 10 allowlisted operators:

| Operator | Allowed Value Types | Evaluation Semantics |
| :--- | :--- | :--- |
| `equals` | `str`, `int`, `float`, `bool` | Strict equality ($A == B$) |
| `not_equals` | `str`, `int`, `float`, `bool` | Strict inequality ($A \neq B$) |
| `in` | `list`, `set` | Membership ($A \in B$) |
| `not_in` | `list`, `set` | Non-membership ($A \notin B$) |
| `exists` | `bool` | Field presence and non-null check |
| `not_exists` | `bool` | Field absence or null check |
| `greater_than`| `int`, `float`, `datetime` | Strict ordering ($A > B$) |
| `less_than` | `int`, `float`, `datetime` | Strict ordering ($A < B$) |
| `before` | ISO-8601 timestamp string | Chronological precedence |
| `after` | ISO-8601 timestamp string | Chronological succession |

Any condition containing unallowlisted operators, malformed payloads, or incompatible data types immediately resolves to `False` (fail-closed) and records a syntax warning.

---

## 5. Human Approval Desk & SHA-256 Payload Hash Locking

Sensitive administrative actions (`CREATE_STOCK_REVIEW_TASK`, `RETRY_DEAD_LETTER_ITEM`) pause in `AWAITING_APPROVAL`:

$$\text{payload\_hash} = \text{SHA-256}(\text{JSON}(\text{canonical\_parameters}))$$

During approval:
1. The engine recalculates the SHA-256 hash of the planned action parameters.
2. If the hash does not match `payload_hash`, the approval is rejected with a tampering violation (`ConflictError`).
3. Upon attributable approval (`POST /api/v1/workflow/actions/{id}/approve`), the user ID and timestamp are recorded, and the approved action is executed via the registered adapter.
4. If rejected (`POST /api/v1/workflow/actions/{id}/reject`), the action transitions to `REJECTED` with an attributable reason and is never executed.

---

## 6. Pre-Flight Patient Communication Consent & Quiet Hours

Outbound communication actions (`ENQUEUE_PATIENT_REMINDER`) execute `_check_communication_consent`:
- Patient must have an active record in `communication_preferences`.
- `opt_out_status` must equal 0.
- `do_not_contact_scope` must not be `all_automated` or `non_urgent_all`.
- Non-consented actions pause in `NEEDS_REVIEW` with an explicit reason logged to `workflow_action_attempts`.
- Messages are dispatched with approved template versions (`communication_templates`) and respect local quiet hours.

---

## 7. Canonical Starter Workflows (Seeded Library)

Six production-ready starter rules are seeded in `apps/api/database/seed.py`:

1. **Rule A (`rule-wf-appt-intake`):** Prepares patient intake folder upon appointment booking (`routine_administrative`).
2. **Rule B (`rule-wf-fup-reminder`):** Dispatches approved Unani follow-up reminder SMS before scheduled due date (`communication`).
3. **Rule C (`rule-wf-stall-escalation`):** Escalates waiting time stalls exceeding 45 minutes to clinic operations lead (`routine_administrative`).
4. **Rule D (`rule-wf-missing-phone`):** Creates front-desk intake gap task when contact phone number is missing (`routine_administrative`).
5. **Rule E (`rule-wf-stock-reorder`):** Generates low dispensary inventory review task when stock drops below threshold, gated by pharmacist approval (`sensitive_administrative`).
6. **Rule F (`rule-wf-dlq-triage`):** Flags persistent dead-letter integration failures for SRE/Admin review (`sensitive_administrative`).

---

## 8. REST API Control Plane

| Method | Endpoint | Description | Permissions Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/workflow/rules` | List workflow rules with status and event filters | `workflow:read` |
| `POST` | `/api/v1/workflow/rules` | Create a new workflow rule in DRAFT status | `workflow:manage` |
| `GET` | `/api/v1/workflow/rules/{id}` | Retrieve rule specification and parsed conditions | `workflow:read` |
| `PUT` | `/api/v1/workflow/rules/{id}` | Update draft rule configuration | `workflow:manage` |
| `POST` | `/api/v1/workflow/rules/{id}/advance` | Advance rule lifecycle (`submit_for_review`, `approve`, `activate`, `pause`, `retire`) | `workflow:manage` / `workflow:approve` |
| `POST` | `/api/v1/workflow/rules/{id}/dry-run` | Test rule evaluation in isolated zero-mutation sandbox | `workflow:read` |
| `POST` | `/api/v1/workflow/events` | Ingest domain event envelope and trigger automated matching | `workflow:execute` |
| `GET` | `/api/v1/workflow/actions` | Query planned workflow actions with status filters | `workflow:read` |
| `POST` | `/api/v1/workflow/actions/{id}/approve` | Attributable approval for sensitive action | `workflow:approve` |
| `POST` | `/api/v1/workflow/actions/{id}/reject` | Attributable rejection of planned action | `workflow:approve` |
| `POST` | `/api/v1/workflow/actions/{id}/retry` | Retry failed or review-required action | `workflow:manage` |
| `GET` | `/api/v1/workflow/monitor` | Operational monitor pulse and pending approval queue | `workflow:read` |

---

## 9. Verification & Regression Test Summary

- **Unit Tests (`tests/unit/test_workflow_automation.py`):** 8/8 tests passing.
  - Strict schema validation, all 10 allowlisted condition operators, dry-run sandbox isolation, rule version snapshotting, event matching idempotency, human approval gates with hash locking, communication consent checks, and clinical boundary enforcement.
- **Integration Tests (`tests/integration/test_workflow_automation_api.py`):** 7/7 tests passing.
  - Full dispatch across all 12 REST endpoints via `ApiRouter`, lifecycle transitions, dry-run sandbox API, approval/rejection/retry flows, monitor pulse aggregation, and RBAC authentication/authorization boundaries.
- **Full Repository Regression:** 100% pass rate maintained across the existing test suite (566+ tests).

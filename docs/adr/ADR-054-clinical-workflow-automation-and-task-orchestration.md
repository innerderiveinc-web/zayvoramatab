# ADR-054: Clinical Workflow Automation, Rules Engine & Human-Approved Task Orchestration

- **Status:** Accepted
- **Date:** 2026-10-14
- **Phase:** Prompt 35 (Phase 35) — Clinical Workflow Automation, Rules Engine & Task Orchestration
- **Deciders:** Principal Software Architect, Senior Full-Stack Engineer, Workflow Platform Engineer, Application Security Engineer, Clinical Safety Governance Lead

---

## 1. Context & Problem Statement

Operational bottlenecks in busy Unani Matabs and clinic environments frequently stem from manual administrative coordination: intake chart preparation delays, missed patient follow-up reminders, unmonitored queue waiting stalls, missing contact information discovery gaps, and unaddressed pharmacy batch depletion thresholds.

However, naive workflow automation engines in healthcare introduce grave risks:
1. **Autonomous Clinical Overreach:** Automated systems attempting to modify medication regimens, calculate botanical dosages, or finalize consultations without clinical oversight.
2. **Arbitrary Code Execution Hazards:** Dynamic evaluation systems utilizing Python `eval()`, JavaScript `vm2`, or dynamic scripting languages that expose the application to Remote Code Execution (RCE) and code injection vulnerabilities.
3. **Unchecked Communication & Consent Violations:** Enqueuing patient SMS or messaging without verifying active consent, honoring opt-outs, or checking local quiet hours.
4. **Idempotency Failures & Action Duplication:** Duplicate event retries leading to multiple identical tasks, repeated patient notifications, or redundant dispensary purchase orders.
5. **Untracked Mutations & Invisible Execution:** Background automations changing operational states without cryptographic provenance, audit trails, or attributable human approval gates for sensitive actions.

---

## 2. Decision

We implement a deterministic, version-controlled rules and workflow automation engine strictly bounded to administrative and operational domains:

1. **Strict Clinical Boundary Non-Negotiable:**
   - The engine is fundamentally prohibited from performing autonomous clinical actions: **zero autonomous prescribing, dosing, nuskha formulation, or encounter signing**.
   - Regulated clinical conditions can **only** yield a `REQUEST_CLINICAL_REVIEW` task assigned to a licensed clinician for human judgment.

2. **Action Classification & Approval Matrix:**
   - **`routine_administrative`:** Automatic execution for pre-approved low-risk operational tasks (`CREATE_ADMIN_TASK`, `RECORD_INTAKE_GAP`, `ESCALATE_QUEUE_STALL`).
   - **`communication`:** Automatic enqueuing into durable messaging outbox with mandatory pre-flight consent verification, active opt-out checks, and quiet-hours compliance.
   - **`sensitive_administrative`:** Pauses in `AWAITING_APPROVAL` with SHA-256 payload hash locking (`payload_hash`). Execution is blocked until explicit, attributable approval by an authorized role (`ORG_ADMIN`, `PHARMACIST`, `CLINIC_ADMIN`).
   - **`clinical_review_only`:** Strictly restricted to generating clinician assessment tasks.

3. **Deterministic Condition Evaluation with Zero `eval` / `exec`:**
   - Rule condition logic is strictly restricted to an allowlisted set of 10 bounded operators:
     `equals`, `not_equals`, `in`, `not_in`, `exists`, `not_exists`, `greater_than`, `less_than`, `before`, `after`.
   - Any unknown operator, type mismatch, or syntax violation fails closed with zero production side effects.

4. **Zero-Side-Effect Dry-Run Sandbox:**
   - Evaluates rule conditions against provided sample event payloads, reporting matched criteria, proposed actions, and approval requirements without mutating database tables.

5. **Durable Ledger & Schema (Migration 034):**
   - `workflow_rules`: Versioned rules with status state machine (`DRAFT` $\to$ `IN_REVIEW` $\to$ `APPROVED` $\to$ `ACTIVE` $\to$ `PAUSED` $\to$ `RETIRED`).
   - `workflow_rule_versions`: Immutable audit snapshots of historical rule revisions.
   - `automation_events`: Envelope tracking incoming domain events with SHA-256 idempotency key deduplication.
   - `workflow_planned_actions`: Planned side effects with execution status, payload hashes, and retry counters.
   - `workflow_action_attempts`: Execution attempt ledger tracking each execution attempt and failure reason.

6. **REST API Control Plane & Knowledge Admin Console:**
   - 12 versioned endpoints mounted under `/api/v1/workflow/` with granular RBAC (`workflow:read`, `workflow:manage`, `workflow:approve`, `workflow:execute`).
   - Interactive UI tab in `apps/web/static/js/views/knowledge_admin.js` providing operations pulse, rule catalog, human approval desk, and dry-run tester.

---

## 3. Starter Workflow Library

Phase 35 seeds six canonical starter rules covering clinic operations:
- **Rule A (`rule-wf-appt-intake`):** Prepares patient chart tasks upon appointment booking (`routine_administrative`).
- **Rule B (`rule-wf-fup-reminder`):** Dispatches approved SMS follow-up reminders subject to patient consent (`communication`).
- **Rule C (`rule-wf-stall-escalation`):** Escalates waiting delays exceeding 45 minutes to clinic lead (`routine_administrative`).
- **Rule D (`rule-wf-missing-phone`):** Flags missing contact phone numbers at intake (`routine_administrative`).
- **Rule E (`rule-wf-stock-reorder`):** Generates dispensary low stock review tasks gated behind pharmacist approval (`sensitive_administrative`).
- **Rule F (`rule-wf-dlq-triage`):** Flags persistent dead-letter items for SRE / Admin review (`sensitive_administrative`).

---

## 4. Consequences & Benefits

- **Positive:**
  - Administrative overhead is reduced without compromising clinical safety.
  - Zero possibility of code injection or sandbox escaping through deterministic JSON condition evaluation.
  - Full traceability and attributable sign-off on sensitive dispensary and operational actions.
  - Zero communication spam or un-consented patient outreach.
- **Negative / Trade-offs:**
  - Sensitive administrative tasks require human approval before side-effect dispatch, adding a deliberate friction point to prioritize safety.
  - Rule expressions cannot use arbitrary nested algorithmic logic; complex non-standard conditions require extending domain models rather than writing inline expressions.

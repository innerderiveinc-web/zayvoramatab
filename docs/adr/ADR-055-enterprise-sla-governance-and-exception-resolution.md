# ADR-055: Enterprise Workflow Intelligence, SLA Governance & Exception Resolution Engine

- **Status:** Accepted
- **Date:** 2026-10-14
- **Phase:** Prompt 36 (Phase 36) — ZAYVORA MATAB OS
- **Deciders:** Principal Software Architect, Workflow Operations Architect, Application Security Engineer, Clinical Safety Officer

---

## 1. Context and Problem Statement

ZAYVORA MATAB OS coordinates high-touch Unani clinical practices, dispensary compounding, patient queueing, longitudinal care continuity, and multi-branch hospital interoperability. As operations scale across facilities, clinics face operational workflow exceptions:
1. Patient wait times exceeding reasonable administrative expectations.
2. Clinical review and safety requests awaiting clinician attention.
3. Care continuity outreach tasks falling behind target timeframes.
4. Intake demographic and contact information gaps delaying appointment verification.
5. Critical dispensary inventory and botanical stock falling below safe reserve levels.
6. Integration connector failures and dead-letter queues delaying data exchange.
7. Backlogs in governance human approval gates.

Prior to Prompt 36, operational delays were either unmonitored or treated with ad-hoc notifications without formal ownership, pause capabilities, escalations, or resolution verification. Furthermore, naive SLA implementations in healthcare risk severe hazards:
- **Clinical Boundary Violations:** Confusing administrative response targets with medical triage acuity, or automating medical diagnoses/prescriptions under the guise of "resolving" an SLA.
- **Data Fabrication:** Guessing missing baseline timestamps or fabricating resolution durations instead of declaring an unmeasurable state.
- **Uncontrolled Self-Resolution:** Allowing operators to self-resolve and self-verify items without separation of duties.
- **PHI Leakage in Alerting:** Broadcasting patient names, diagnoses, or prescriptions across operations channels or paging systems during escalations.

---

## 2. Decision Drivers

1. **Strict Non-Negotiable Clinical Boundary:** Zero autonomous clinical actions. The engine must never diagnose, prescribe, adjust botanical nuskha dosages, or sign encounters. Clinical review requests must route strictly as human review tasks (`REQUEST_CLINICAL_REVIEW`) for certified human clinicians (`CLINICIAN`).
2. **Canonical Data Model (No Parallel Task Engine):** Unify SLA governance into a canonical `workflow_exceptions` ledger linked to existing entities (`queue_tokens`, `care_continuity_tasks`, `patients`, `inventory_batches`, `integration_jobs`, `workflow_planned_actions`) via `source_entity` and `source_entity_id`.
3. **Deterministic Timers & Pause Accounting:** Accurately subtract verified pause intervals from elapsed durations. Freeze timers upon resolution. Output `UNMEASURABLE` whenever timestamps are missing or corrupt.
4. **Idempotent Ingestion & Deduplication:** Enforce deterministic deduplication via `deduplication_key = sha256(org + category + source_entity + source_id + policy_key)` to prevent duplicate ticket floods.
5. **Separation of Duties:** Enforce independent verification where required by policy—a user who resolves an exception is strictly forbidden from verifying their own resolution.
6. **Zero-PHI Escalations:** Broadcast escalation alerts must strictly contain safe operational identifiers and deep-links, completely omitting protected health information (PHI).

---

## 3. Considered Options

- **Option 1: Ad-hoc alerts in Command Center without persistent SLA records.**
  - *Pros:* Quick to add, no new database schema.
  - *Cons:* No accountability, no pause accounting, no audit trail, prone to repeated alerts and ignored bottlenecks.
- **Option 2: Standalone external ticket system (e.g., Jira/Zendesk integration).**
  - *Pros:* Offloads SLA logic to third-party tools.
  - *Cons:* Breaches data residency, leaks PHI to external SaaS, creates fragmented workflow state outside the clinic OS.
- **Option 3 (Selected): In-database canonical SLA Governance & Exception Resolution Engine.**
  - *Pros:* Zero external dependencies, deterministic timer accounting, cryptographic deduplication, strict separation of duties, zero-PHI alerting, full RBAC alignment, and seamless integration into the Command Center and Knowledge Admin consoles.

---

## 4. Decision Outcome

We implemented Option 3:
1. **Database Schema (Migration 035):**
   - `sla_policies`: Versioned SLA policies (`DRAFT` $\to$ `IN_REVIEW` $\to$ `APPROVED` $\to$ `ACTIVE` $\to$ `PAUSED` $\to$ `RETIRED`) with warning/breach thresholds, owner roles, allowed resolution codes, and pause eligibility.
   - `sla_policy_versions`: Immutable snapshots created upon policy approval.
   - `workflow_exceptions`: Canonical operational work items (`OPEN` $\to$ `ACKNOWLEDGED` $\to$ `IN_PROGRESS` $\to$ `WAITING` $\to$ `RESOLVED` $\to$ `VERIFIED` / `DISMISSED` / `REOPENED`).
   - `sla_pause_intervals`: Pause ledger recording pause reasons (`WAITING_PATIENT_RESPONSE`, `SUPPLIER_DELIVERY_PENDING`, `SYSTEM_OUTAGE`, `EXTERNAL_REFERRAL_PENDING`, `ADMINISTRATIVE_HOLD`), pause duration, and timestamps.
   - `sla_escalation_events`: Multi-stage escalation history recording dispatched zero-PHI alerts.
2. **Domain Service (`SlaGovernanceEngine`):**
   - Encapsulates policy registry, draft lifecycle, deterministic timer calculations, pause/resume duration tracking, escalation matrix evaluation, resolution code validation, separation of duties checks, and real-time operational monitor summaries.
3. **REST API (`apps/api/routes/sla_governance.py` & `apps/api/router.py`):**
   - Exposes 19 REST endpoints under `/api/v1/sla/` protected by granular permissions (`sla:read`, `sla:manage`, `sla:approve`, `exception:manage`, `exception:verify`).
4. **Starter Policies Seeded (Migration & Seed):**
   - 7 canonical policies covering patient wait time, follow-up outreach, demographic intake, inventory depleted restock, integration DLQ resolution, governance approval backlog, and clinical review routing.
5. **Web Console Integration:**
   - Interactive SLA Governance & Exception Resolution workspace embedded into Knowledge Admin (`apps/web/static/js/views/knowledge_admin.js`), featuring real-time pulse cards, exception queue actions, timer badges, and policy lifecycle controls.

---

## 5. Consequences & Compliance

- **Positive:**
  - Clear, governed service targets across all operational departments.
  - Legitimate operational pauses (e.g., patient stepped out, supplier delivery pending) prevent false SLA breaches.
  - Complete accountability with audit-tracked escalations and independent resolution verification.
  - Clean separation between operational administrative SLAs and medical triage.
- **Negative / Operational Burden:**
  - Clinic supervisors must periodically review policies and approve version changes.
  - Strict separation of duties requires at least two staff members to resolve and verify critical items.

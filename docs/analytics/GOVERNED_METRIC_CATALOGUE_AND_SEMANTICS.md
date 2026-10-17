# Governed Metric Catalogue & Semantic Specification

**Document Type:** Technical and Governance Reference  
**Product:** ZAYVORA MATAB OS — Standalone Clinic & Matab Operating System  
**Phase:** 33 — Enterprise Analytics, Operational Intelligence & Clinical Governance Dashboards  
**Standard:** Strict Non-Causal Observational Governance Standard  

---

## 1. Executive Summary & Governance Contract

This document provides the canonical definition, mathematical formula, inclusion/exclusion criteria, source entities, and non-causal interpretation guidelines for all governed metrics tracked in ZAYVORA MATAB OS.

### 1.1 The Non-Causal Policy Contract
Observational EHR records measure **administrative process completion**, **workflow compliance**, and **operational volume**. Under no circumstances may any metric in this catalogue be interpreted or reported as:
- Proof of clinical effectiveness or cure.
- Statistical superiority of one clinician or branch over another.
- Direct therapeutic attribution of Unani formulations without prospective controlled trials.

### 1.2 State Disambiguation Rule
All metric responses in ZAYVORA MATAB OS must unambiguously differentiate between:
- **`0`**: A legitimate, verified count of zero events occurring during a period where data collection was fully active and healthy.
- **`insufficient_data`**: Fewer data points exist than the minimum statistical threshold required for reliable reporting.
- **`not_configured`**: The underlying integration, feature module, or tracker is not enabled for the organization or facility.
- **`stale`**: The background pre-aggregation calculation is older than the configured refresh policy SLA.
- **`failed`**: The aggregation job encountered an execution error and was safely aborted.

---

## 2. Canonical Governed Metrics Catalogue

### 2.1 Operations Domain

#### `operations.appointments_completed`
- **Metric Key:** `operations.appointments_completed`
- **Domain:** OPERATIONS
- **Metric Type:** Count
- **Unit:** visits
- **Formula:** $\text{COUNT}(\text{id}) \text{ WHERE status} = \text{'completed'}$
- **Numerator Definition:** Total appointments marked `completed` by treating clinician or reception staff within the period.
- **Denominator Definition:** N/A (Absolute count)
- **Inclusion Rules:**
  - `status = 'completed'`
  - `start_at` falls between `period_start` and `period_end`
  - Valid `organization_id` (and matching `facility_id` when filtered)
- **Exclusion Rules:**
  - Cancelled appointments (`status = 'cancelled'`)
  - No-show appointments (`status = 'no_show'`)
  - Test or synthetic records
- **Source Entities:** `appointments`
- **Accountable Owner:** CLINICAL_DIRECTOR
- **Permitted Roles:** `ORG_ADMIN`, `PRACTITIONER`, `FACILITY_MANAGER`, `RECEPTIONIST`
- **Caveats:** Completed visit counts measure operational volume and documentation completion; they do not indicate consultation thoroughness or therapeutic efficacy.

#### `operations.appointments_no_show_rate`
- **Metric Key:** `operations.appointments_no_show_rate`
- **Domain:** OPERATIONS
- **Metric Type:** Rate
- **Unit:** %
- **Formula:** $\frac{\text{COUNT}(\text{id} \mid \text{status} = \text{'no\_show'})}{\text{COUNT}(\text{id} \mid \text{status} \in \{\text{'completed'}, \text{'no\_show'}, \text{'arrived'}\})} \times 100$
- **Numerator Definition:** Total booked appointments where the patient failed to present and was marked `no_show`.
- **Denominator Definition:** Total scheduled visits with definitive patient outcome (completed, arrived, or no-show).
- **Inclusion Rules:** Confirmed booked appointments with conclusive arrival/no-show recording.
- **Exclusion Rules:** Appointments cancelled prior to the scheduled slot time; walk-in tokens not booked in advance.
- **Source Entities:** `appointments`
- **Accountable Owner:** FRONT_DESK_LEAD
- **Permitted Roles:** `ORG_ADMIN`, `PRACTITIONER`, `FACILITY_MANAGER`, `RECEPTIONIST`
- **Caveats:** High no-show rates reflect booking friction or communication barriers, not patient dissatisfaction with clinical care.

#### `operations.queue_tokens_waiting`
- **Metric Key:** `operations.queue_tokens_waiting`
- **Domain:** OPERATIONS
- **Metric Type:** Gauge / Count
- **Unit:** patients
- **Formula:** $\text{COUNT}(\text{id}) \text{ WHERE status} = \text{'waiting'} \land \text{queue\_date} = \text{CURRENT\_DATE}$
- **Numerator Definition:** Instantaneous count of active OPD queue tokens waiting for triage or clinician consultation.
- **Denominator Definition:** N/A
- **Inclusion Rules:** Tokens issued today in `waiting` state.
- **Exclusion Rules:** Completed, called, in-consultation, or cancelled tokens.
- **Source Entities:** `queue_tokens`
- **Accountable Owner:** FRONT_DESK_LEAD
- **Permitted Roles:** `ORG_ADMIN`, `PRACTITIONER`, `FACILITY_MANAGER`, `RECEPTIONIST`
- **Caveats:** Real-time gauge reflecting physical clinic congestion; does not stratify emergency or fast-tracked patients.

#### `operations.encounters_signed`
- **Metric Key:** `operations.encounters_signed`
- **Domain:** OPERATIONS
- **Metric Type:** Count
- **Unit:** encounters
- **Formula:** $\text{COUNT}(\text{id}) \text{ WHERE status} \in \{\text{'COMPLETED'}, \text{'signed'}\}$
- **Numerator Definition:** Clinical consultation encounters finalized, electronically signed, and locked.
- **Denominator Definition:** N/A
- **Inclusion Rules:** Encounters with valid practitioner signature finalized within period.
- **Exclusion Rules:** Draft encounters, encounters currently in progress, cancelled encounters.
- **Source Entities:** `encounters`
- **Accountable Owner:** CHIEF_MEDICAL_OFFICER
- **Permitted Roles:** `ORG_ADMIN`, `PRACTITIONER`, `FACILITY_MANAGER`
- **Caveats:** Electronic signature is a legal and regulatory documentation milestone, not an assessment of diagnosis correctness.

---

### 2.2 Continuity & Care Domain

#### `continuity.tasks_overdue`
- **Metric Key:** `continuity.tasks_overdue`
- **Domain:** CONTINUITY
- **Metric Type:** Count
- **Unit:** tasks
- **Formula:** $\text{COUNT}(\text{id}) \text{ WHERE status} \in \{\text{'PENDING'}, \text{'IN\_PROGRESS'}\} \land \text{due\_date} < \text{CURRENT\_TIMESTAMP}$
- **Numerator Definition:** Uncompleted follow-up outreach calls, lab review reminders, or adherence checks past scheduled due date.
- **Denominator Definition:** N/A
- **Inclusion Rules:** Open tasks with `due_date` strictly prior to current time.
- **Exclusion Rules:** Completed, escalated, or cancelled tasks.
- **Source Entities:** `care_continuity_tasks`
- **Accountable Owner:** CARE_COORDINATOR
- **Permitted Roles:** `ORG_ADMIN`, `PRACTITIONER`, `FACILITY_MANAGER`
- **Caveats:** Overdue tasks indicate administrative backlog in care outreach, not clinical failure or patient drop-out.

---

### 2.3 Finance Domain

#### `finance.gross_invoiced`
- **Metric Key:** `finance.gross_invoiced`
- **Domain:** FINANCE
- **Metric Type:** Amount
- **Unit:** INR
- **Formula:** $\sum(\text{CAST}(\text{total\_decimal AS REAL})) \text{ WHERE status} \in \{\text{'FINALIZED'}, \text{'PARTIALLY\_PAID'}, \text{'PAID'}\}$
- **Numerator Definition:** Total monetary value of invoices finalized during the accounting window.
- **Denominator Definition:** N/A
- **Inclusion Rules:** Invoices legally finalized and locked for billing.
- **Exclusion Rules:** Draft proforma invoices, voided bills, cancelled estimates.
- **Source Entities:** `invoices`
- **Accountable Owner:** FINANCE_MANAGER
- **Permitted Roles:** `ORG_ADMIN`, `FINANCE_OFFICER`, `FACILITY_MANAGER`
- **Caveats:** Gross invoiced amount measures accrued accounts receivable, NOT realized cash collection or clinic net income.

#### `finance.net_collections`
- **Metric Key:** `finance.net_collections`
- **Domain:** FINANCE
- **Metric Type:** Amount
- **Unit:** INR
- **Formula:** $\sum(\text{payments.amount\_decimal}) - \sum(\text{payment\_refunds.amount\_decimal})$
- **Numerator Definition:** Realized cash, UPI, card, and bank collections received minus authorized customer refunds issued.
- **Denominator Definition:** N/A
- **Inclusion Rules:**
  - Payments with `status IN ('POSTED', 'COMPLETED')`
  - Refunds with `status = 'COMPLETED'`
- **Exclusion Rules:** Pending provider transactions, failed payment attempts, unauthorized drafts.
- **Source Entities:** `payments`, `payment_refunds`
- **Accountable Owner:** CHIEF_FINANCIAL_OFFICER
- **Permitted Roles:** `ORG_ADMIN`, `FINANCE_OFFICER`
- **Caveats:** Net cash collections represent actual bank/cash settlement; does not account for unpaid outstanding receivables.

---

### 2.4 Inventory & Dispensing Domain

#### `inventory.batches_near_expiry`
- **Metric Key:** `inventory.batches_near_expiry`
- **Domain:** INVENTORY
- **Metric Type:** Count
- **Unit:** batches
- **Formula:** $\text{COUNT}(\text{id}) \text{ WHERE is\_active} = 1 \land \text{quantity\_on\_hand} > 0 \land \text{expiry\_date} \le \text{DATE('now', '+90 days')}$
- **Numerator Definition:** Active pharmacy stock batches approaching expiration within 90 calendar days.
- **Denominator Definition:** N/A
- **Inclusion Rules:** Non-depleted batches currently on dispensary or warehouse shelves.
- **Exclusion Rules:** Depleted batches (`quantity_on_hand = 0`), quarantined or recalled batches, expired batches already written off.
- **Source Entities:** `inventory_batches`
- **Accountable Owner:** HEAD_PHARMACIST
- **Permitted Roles:** `ORG_ADMIN`, `PHARMACIST`, `FACILITY_MANAGER`
- **Caveats:** Near-expiry counts reflect stock rotation urgency and FEFO inventory efficiency.

---

### 2.5 Clinical Governance Domain

#### `governance.safety_cases_open`
- **Metric Key:** `governance.safety_cases_open`
- **Domain:** GOVERNANCE
- **Metric Type:** Count
- **Unit:** cases
- **Formula:** $\text{COUNT}(\text{id}) \text{ WHERE case\_state} \in \{\text{'DRAFT'}, \text{'INTAKE\_COMPLETE'}, \text{'TRIAGED'}, \text{'UNDER\_CLINICAL\_REVIEW'}\}$
- **Numerator Definition:** Open pharmacovigilance and adverse event intake files undergoing clinical triage or investigation.
- **Denominator Definition:** N/A
- **Inclusion Rules:** Valid intake files within the organization's pharmacovigilance perimeter.
- **Exclusion Rules:** Closed cases, evaluated cases with completed causality determinations and regulatory filings.
- **Source Entities:** `safety_cases`
- **Accountable Owner:** PATIENT_SAFETY_OFFICER
- **Permitted Roles:** `ORG_ADMIN`, `CLINICAL_DIRECTOR`
- **Caveats:** A higher count of open safety cases frequently indicates a vigilant, proactive reporting culture rather than high product toxicity. Zero adverse events does NOT prove absolute product safety when reporting completeness is unverified.

#### `governance.rules_pending_review`
- **Metric Key:** `governance.rules_pending_review`
- **Domain:** GOVERNANCE
- **Metric Type:** Count
- **Unit:** rules
- **Formula:** $\text{COUNT}(\text{id}) \text{ WHERE current\_lifecycle\_state} \in \{\text{'DRAFT'}, \text{'SUBMITTED\_FOR\_REVIEW'}, \text{'TECHNICAL\_VALIDATION\_PENDING'}\}$
- **Numerator Definition:** Clinical rules, ontology concepts, or formulation safety boundaries awaiting expert governance approval.
- **Denominator Definition:** N/A
- **Inclusion Rules:** Unreleased rule artifacts currently in the governance gate pipeline.
- **Exclusion Rules:** Active released rules, archived rules, rejected drafts.
- **Source Entities:** `governed_artifacts`
- **Accountable Owner:** GOVERNANCE_BOARD_SECRETARY
- **Permitted Roles:** `ORG_ADMIN`, `KNOWLEDGE_ADMIN`
- **Caveats:** Measures editorial and clinical review workload backlog before production deployment.

---

### 2.6 Data Quality & Integration Operations Domain

#### `operations.dead_letter_items`
- **Metric Key:** `operations.dead_letter_items`
- **Domain:** DATA_QUALITY
- **Metric Type:** Count
- **Unit:** items
- **Formula:** $\text{COUNT}(\text{dlq.id}) \text{ WHERE dlq.resolution\_status} = \text{'PENDING'}$
- **Numerator Definition:** Failed ABDM or external integration jobs exhausted of automatic retry attempts requiring operator intervention.
- **Denominator Definition:** N/A
- **Inclusion Rules:** DLQ records awaiting manual reconciliation or poison-pill discard.
- **Exclusion Rules:** Resolved, replayed, or dismissed DLQ items.
- **Source Entities:** `dead_letter_items`, `integration_jobs`
- **Accountable Owner:** INTEGRATION_SRE_LEAD
- **Permitted Roles:** `ORG_ADMIN`, `INTEGRATION_OPERATOR`
- **Caveats:** Identifies external API reliability friction, payload formatting errors, or network outages. Zero PHI is contained in error classifications.

---

## 3. Metric Lifecycle State Machine

Each metric definition in `governed_metric_definitions` advances through four strictly controlled lifecycle states:

```
+------------+       Submit       +------------+       Approve       +--------------+
|   DRAFT    |  ===============>  |   REVIEW   |  =================> |   APPROVED   |
+------------+                    +------------+                     +--------------+
                                                                             |
                                                                             | Retire
                                                                             v
                                                                     +--------------+
                                                                     |   RETIRED    |
                                                                     +--------------+
```

1. **`draft`**: Authored by domain specialists. Cannot be queried in production executive reports.
2. **`review`**: Submitted to the Clinical Governance & Analytics Board. Under technical and semantic validation.
3. **`approved`**: Formally validated by authorized Clinical Director or Chief Financial Officer. Available for enterprise reporting and audited export.
4. **`retired`**: Deprecated or superseded. Preserved for retrospective historical audit compliance; blocked from new dashboards.

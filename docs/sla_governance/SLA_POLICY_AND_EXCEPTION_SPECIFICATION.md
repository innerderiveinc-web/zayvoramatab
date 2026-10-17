# Specification: Operational SLA Policy Registry, Exception Lifecycle & Escalation Engine

**System:** ZAYVORA MATAB OS — Standalone Unani Clinic & Practice Operating System  
**Phase:** 36 — SLA Governance & Exception Resolution Engine  

---

## 1. Operational SLA Policy Registry Specification

Policies are version-controlled entities authored, approved, and tracked in `sla_policies` and `sla_policy_versions`.

### Schema & Fields
- `id`: Unique policy identifier (`sla-pol-...`).
- `organization_id`: Multi-tenant boundary.
- `facility_id`: Optional branch scoping (NULL = organization default).
- `policy_key`: Stable canonical slug (e.g. `sla-pol-queue-stall`).
- `name`: Descriptive human title.
- `category`: Bounded exception category:
  `administrative`, `follow_up`, `intake_gap`, `inventory`, `integration`, `governance`, `clinical_review`.
- `target_entity_type`: Canonical database entity (`queue_tokens`, `care_continuity_tasks`, `patients`, `inventory_batches`, `integration_jobs`, `workflow_planned_actions`).
- `owner_role`: Primary accountable operational role (`FRONT_DESK`, `RECEPTIONIST`, `CARE_COORDINATOR`, `PHARMACIST`, `CLINIC_ADMIN`, `ORG_ADMIN`, `CLINICIAN`).
- `version`: Monotonically increasing version integer.
- `status`: Lifecycle state machine (`DRAFT`, `IN_REVIEW`, `APPROVED`, `ACTIVE`, `RETIRED`).
- `time_basis`: `elapsed` (continuous 24x7) or `business_hours` (09:00 - 18:00 local time).
- `timezone`: Pinned timezone (`Asia/Kolkata`).
- `warning_threshold_mins`: Duration in minutes before item is flagged `AT_RISK`.
- `breach_threshold_mins`: Duration in minutes before item is flagged `BREACHED`.
- `pause_eligibility`: JSON array of allowlisted pause reason codes:
  - `WAITING_PATIENT_RESPONSE`
  - `SUPPLIER_DELIVERY_PENDING`
  - `SYSTEM_OUTAGE`
  - `EXTERNAL_REFERRAL_PENDING`
  - `ADMINISTRATIVE_HOLD`
- `escalation_matrix_json`: Array of escalation stage definitions:
  - `stage`: Integer (1, 2, 3)
  - `trigger_delay_mins`: Minutes after breach before stage activates
  - `escalate_to_role`: Target role receiving alert
  - `channel`: Notification channel (`in_app`, `email`, `sms`)
  - `cooldown_mins`: Minimum interval before repeated notification
- `verification_required`: 0 or 1. If 1, requires distinct verifier.
- `allowed_resolution_codes_json`: Array of permitted resolution codes.
- `approved_by` / `approved_at`: Attributable governance sign-off.

---

## 2. Canonical Exception Lifecycle State Machine

Exceptions navigate an auditable, deterministic state machine:

```
        ┌────────────────────────────────────────────────────────┐
        │                                                        │
        ▼                                                        │
     [ OPEN ] ──► [ ACKNOWLEDGED ] ──► [ IN_PROGRESS ]           │
        │                                    │                   │
        │ (dismiss)                          │ (pause)           │
        ▼                                    ▼                   │
   [ DISMISSED ]                         [ WAITING ]             │
                                             │ (resume)          │
                                             ▼                   │
                                       [ IN_PROGRESS ]           │
                                             │                   │
                                             ▼                   │
                                       [ RESOLVED ]              │
                                             │                   │
                     ┌───────────────────────┴───────────────────┘
                     │ (if verification_required)  │ (if verification fails or reopen)
                     ▼                             ▼
                [ VERIFIED ]                  [ REOPENED ]
```

### Transition Invariants
1. **`OPEN` $\to$ `ACKNOWLEDGED`**: Explicit acceptance of operational responsibility by assigned user or role.
2. **`ACKNOWLEDGED` $\to$ `IN_PROGRESS`**: Active work begun.
3. **`IN_PROGRESS` $\to$ `WAITING`**: Permitted only with an approved `pause_reason_code`. Automatically records a pause interval in `sla_pause_intervals`.
4. **`WAITING` $\to$ `IN_PROGRESS`**: Work resumed; closes the active pause interval and computes duration.
5. **`IN_PROGRESS` $\to$ `RESOLVED`**: Requires a valid `resolution_code` and resolution summary notes. If `verification_required == 0`, finalizes resolution.
6. **`RESOLVED` $\to$ `VERIFIED`**: Requires independent authorized verifier (`exception:verify`). The user who recorded `RESOLVED` cannot self-verify when verification is required (Separation of Duties).
7. **`*` $\to$ `DISMISSED`**: Allowed only with attributable dismissal justification (e.g. duplicate, invalid, or system test).
8. **`RESOLVED` / `VERIFIED` $\to$ `REOPENED`**: Permitted when new contradictory evidence arrives or independent verification fails.

---

## 3. SLA Timer & Effective Elapsed Time Calculation

The SLA timer computes effective operational duration:

$$\text{Effective Duration} = \text{Current Time} - \text{Start Time} - \sum \text{Approved Pause Durations}$$

### Timer States
- **`ON_TRACK`**: $\text{Effective Duration} < \text{Warning Threshold}$.
- **`AT_RISK`**: $\text{Warning Threshold} \le \text{Effective Duration} < \text{Breach Threshold}$.
- **`BREACHED`**: $\text{Effective Duration} \ge \text{Breach Threshold}$.
- **`PAUSED`**: Exception is currently in `WAITING` state under an authorized pause reason.
- **`RESOLVED`**: Exception is resolved; timer is permanently frozen at resolution timestamp.
- **`UNMEASURABLE`**: Start timestamp missing, contradictory, or future-dated; explicitly labeled without guessing.

---

## 4. Multi-Stage Escalation Engine & Privacy Boundaries

When an exception enters `BREACHED` status:
1. The engine checks `escalation_matrix_json` against effective breach duration.
2. For each eligible stage, checks `sla_escalation_events` for existing execution.
3. If not executed and past cooldown, dispatches the notification via the configured channel.
4. **Data Minimization:** Notifications contain ONLY generic operational metadata:
   - Exception ID, Category, Policy Title, Elapsed Hours, and Secure System Deep-Link.
   - **Zero Patient Health Information (PHI):** No patient names, MRNs, diagnoses, symptoms, or prescriptions are broadcast over external alerts.

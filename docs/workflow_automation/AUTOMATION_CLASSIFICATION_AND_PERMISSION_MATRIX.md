# Automation Classification and Permission Matrix

**Product:** ZAYVORA MATAB OS — Standalone Unani Clinic & Practice Operating System  
**Phase:** 35 — Clinical Workflow Automation, Rules Engine & Human-Approved Task Orchestration  
**Governance Authority:** Clinical Safety Committee & Head of Clinic Operations  

---

## 1. Classification Categories

Every automated rule and proposed action in ZAYVORA MATAB OS must be explicitly declared and validated against one of four strict action categories before it can be saved, approved, or executed.

```
                              ┌──────────────────────────────────┐
                              │     Triggered Workflow Event     │
                              └─────────────────┬────────────────┘
                                                │
                                    [Rule Evaluator Match]
                                                │
                                                ▼
                         ┌──────────────────────────────────────────────┐
                         │      Action Classification Determination     │
                         └──────┬──────────────┬──────────────┬─────────┘
                                │              │              │         │
                   ┌────────────┘              │              │         └────────────┐
                   ▼                           ▼              ▼                      ▼
        ┌──────────────────────┐   ┌─────────────────┐ ┌───────────────┐ ┌────────────────────────┐
        │ROUTINE ADMINISTRATIVE│   │  COMMUNICATION  │ │   SENSITIVE   │ │ CLINICAL / CONSEQUENTIAL│
        │                      │   │                 │ │ ADMINISTRATIVE│ │                         │
        │ • Policy permitted   │   │ • Consent Check │ │ • Human Gate  │ │ • PROHIBITED AUTONOMOUS│
        │ • Automated dispatch │   │ • Template Ver  │ │ • Explicit    │ │ • Creates Review Task   │
        │ • Idempotent         │   │ • Quiet Hours   │ │   Approval    │ │   for Clinician ONLY    │
        └──────────────────────┘   └─────────────────┘ └───────────────┘ └────────────────────────┘
```

---

## 2. Action Category Matrix

| Category Key | Category Description | Autonomy Level | Required Approval Gate | Allowed Adapters / Actions | Prohibited Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `routine_administrative` | Low-impact operational routing, queue sorting, and status bookkeeping. | Fully Automated (when rule is `active` and policy permits). | None at runtime; rule version must be approved at activation. | `create_administrative_task`<br>`assign_task_to_role`<br>`reconcile_duplicate_event`<br>`record_intake_gap` | Modifying clinical notes, altering invoices, or overriding clinician assignments. |
| `communication` | Patient-facing or internal staff notifications and reminders. | Automated **only** after strict 5-point consent & preference pre-flight check. | Pre-approved template version required; human review if consent is ambiguous. | `enqueue_patient_reminder`<br>`enqueue_internal_alert` | Sending messages when consent is absent/revoked, sending novel unapproved advice, or including sensitive clinical diagnoses. |
| `sensitive_administrative` | High-impact administrative actions: billing adjustments, schedule alterations, external writes. | Held in `awaiting_approval`. | Explicit attributable human approval required from authorized role (`ORG_ADMIN` or `CLINIC_ADMIN`). | `hold_appointment_for_review`<br>`flag_billing_reconciliation`<br>`retry_dead_letter_item`<br>`quarantine_inventory_batch` | Executing bulk modifications or irreversible external side effects without attributable human sign-off. |
| `clinical_review_only` | Consequential clinical workflows: diagnosis, prescription, dosage, nuskha selection, or adverse event handling. | **STRICTLY PROHIBITED AUTONOMOUSLY.** | Must be executed directly by qualified licensed human clinician. | `create_clinical_review_task`<br>`escalate_to_practitioner` | Autonomous prescribing, dosing, signing encounters, diagnostic coding, or dismissing adverse reactions. |

---

## 3. Communication Pre-flight Checklist (Category `communication`)

Before any patient-facing communication action can transition from `planned` to `queued`:
1. **Verified Canonical Record:** Associated appointment or follow-up plan must exist in a valid state.
2. **Patient Consent & Channel:** `communication_preferences` must show `opt_out_status = 0`, permitted category matching, and channel matching.
3. **Template Approval:** The exact template ID and version must be `approved` by an authorized supervisor.
4. **Placeholder Sanitization:** Prohibited placeholders (`diagnosis`, `medication_name`, etc.) must be strictly rejected.
5. **Quiet Hours Policy:** Sending timestamps falling within quiet hours (e.g. 21:00 - 08:00) must be scheduled for the next allowed window.

If any check fails, the action transitions to `needs_review` with an explanatory reason code; it is **never** forced through.

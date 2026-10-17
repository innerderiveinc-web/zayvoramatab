# Operational Thresholds & Bottleneck Stage Catalogue

**Product:** ZAYVORA MATAB OS — Standalone Matab/Clinic Operating System  
**Phase:** 34 — Clinical Operations Command Center & Bottleneck Intelligence  
**Document Status:** Approved Canonical Standard  
**Governance Authority:** Clinic Operations Leadership & Clinical Governance Committee  

---

## 1. Executive Overview & Ethical Safeguards

The Operational Bottleneck Detection Engine monitors operational throughput stages to alert clinic managers, reception teams, and nursing coordinators to excessive administrative delays. 

### Core Non-Negotiable Operational Constraints:
1. **Zero Clinical Acuity Inference**: Queue elapsed wait times and bottleneck alerts represent logistical queuing durations only. They are **never** presented as clinical triage acuity scores. High elapsed times do not imply a deteriorating patient, and fast throughput does not imply clinical stability.
2. **Zero Clinician Speed Ranking**: Clinicians are never ranked or evaluated based on consultation speed or hourly throughput. Complex Unani clinical examinations (*Nabz*, *Baul-o-Baraz*, *Mizaj* assessments, or regimental therapy counseling) naturally require varying durations.
3. **Transparent Factual Reasons Only**: The engine outputs factual descriptions of current database states (e.g. *"Patient waiting in reception; practitioner has not called token"*). When a reason code is absent, the engine reports `"Reason not recorded"`; it never invents unverified justifications.
4. **Segregation of Hypothetical Simulations**: Capacity simulations are strictly isolated in `capacity_scenarios` and never mutate live production schedules or patient appointments.

---

## 2. Canonical Stage Threshold Catalogue

The table below specifies the default approved thresholds for all operational throughput stages across OPD clinics and Matabs.

| Stage Key | Operational Stage Description | Warning Threshold (Mins) | Critical Threshold (Mins) | Primary Operational Owner | Default Factual Reason Format |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `CHECK_IN_TO_CALL` | Patient checked-in at reception awaiting practitioner token call | 30 | 60 | Front Desk Lead / Reception | *"Patient waiting in reception; practitioner has not called token."* |
| `CALL_TO_START` | Token called by practitioner awaiting patient transit to consultation room | 15 | 30 | Clinic Nurse / Attendant | *"Token called; consultation not marked in-progress."* |
| `CONSULTATION_DURATION` | Active encounter underway inside consultation room | 45 | 90 | Clinic Operations Lead | *"Encounter active for extended duration; complex assessment in progress."* |
| `DISCHARGE_TO_BILLING` | Encounter signed/finalized awaiting billing invoice generation | 20 | 45 | Billing Supervisor / Cashier | *"Consultation concluded; invoice not finalized."* |
| `BILLING_TO_PAYMENT` | Finalized invoice awaiting patient payment posting | 30 | 60 | Cashier / Billing Desk | *"Invoice generated; payment receipt pending."* |
| `FOLLOW_UP_COMPLETION` | Active care continuity task past designated scheduled window | 1440 (24h) | 2880 (48h) | Care Coordinator | *"Care continuity task past scheduled window without contact attempt."* |
| `DLQ_RESOLUTION` | Interoperability dead-letter queue item pending operator triage | 60 | 240 | Integration SRE / Admin | *"Dead-letter queue item awaiting operator inspection."* |

---

## 3. Threshold Governance & Rule Lifecycle

Threshold rules are stored in `command_center_threshold_rules`. 

### Threshold Scoping Hierarchy:
1. **Facility-Specific Override**: Rules where `facility_id = :facility_id` and `is_active = 1` take precedence.
2. **Organization-Wide Baseline**: Rules where `facility_id IS NULL` and `organization_id = :organization_id`.
3. **Engine Default**: Built-in fallbacks when configuration is not yet persisted.

### Rule Mutation Controls:
- All changes to warning and critical thresholds must be approved by authorized personnel (`ROLE_ORG_ADMIN` or `CLINIC_ADMIN`).
- Rule updates increment the `version` integer column.
- Superseded rules are archived with `is_active = 0`.

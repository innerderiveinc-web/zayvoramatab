# ADR-053: Clinical Operations Command Center, Capacity Planning & Workflow Bottleneck Intelligence (Prompt 34)

- **Status:** Accepted
- **Date:** 2026-10-14
- **Authors:** Core Architecture, Workflow Operations & Clinical Governance Team
- **Phase:** 34 (Prompt 34)

---

## 1. Context and Problem Statement

Ambulatory clinics and Unani Matab operations frequently experience queue congestion, unpredictable patient arrivals, room allocation bottlenecks, and uneven clinician workloads. Traditional operational dashboards often exacerbate clinical and administrative issues through unsafe design anti-patterns:
1. **Conflating Operational Elapsed Times with Triage Acuity:** Naive command centers label waiting times as triage urgency, misguiding staff into assuming patients waiting longer are clinically sicker, or conversely assuming newly arrived patients do not require immediate medical attention.
2. **Punitive Clinician Speed Rankings:** Comparing doctors on throughput per hour creates perverse incentives that compromise meticulous Unani clinical examination (*Nabz*, *Baul-o-Baraz*, holistic dietetic evaluation, regimental therapies) and modern clinical thoroughness.
3. **Fabricated or Speculative Operational Metrics:** Guessing waiting durations or inventing hypothetical numbers when schedules or timestamps are missing.
4. **Leakage of PHI on Public Wallboards:** Displaying patient names, MRNs, or diagnosis categories on waiting room monitors and OPD hallway wallboards.
5. **Pollution of Production Records with Simulations:** Running "what-if" capacity planning experiments that mutate live production schedules or disrupt actual patient bookings.

To solve these challenges safely, ZAYVORA MATAB OS required a principled, transparent, and deterministic Clinical Operations Command Center and Capacity Planning Engine.

---

## 2. Decision and Architecture Principles

We implemented a unified, role-aware, privacy-preserving **Clinical Operations Command Center, Capacity Planning & Workflow Bottleneck Intelligence Engine** governed by the following core non-negotiables:

### 2.1 Pure Operations Scoping — Never Assess Clinical Efficacy
The engine operates strictly on logistics, queue states, and administrative throughput. It never evaluates clinical efficacy, therapeutic outcomes, diagnoses, or prescribing decisions.

### 2.2 Queue Elapsed Time is Never a Clinical Triage Acuity Score
Waiting timers measure logistical duration in reception and consultation rooms. They are **never** presented, styled, or categorized as clinical triage acuity scores.

### 2.3 Strict Prohibition on Clinician Speed Rankings
Workload distribution views present assigned tokens and appointment counts for logistical load balancing across rooms and roles. Clinicians are **never** ranked by consultation speed, and faster consultations are never represented as higher quality care.

### 2.4 Deterministic Capacity Computation
Capacity is computed using a deterministic mathematical formula based solely on configured calendars:
$$\text{Capacity Slots} = \sum_{p \in \text{Scheduled Practitioners}} \left\lfloor \frac{\text{Shift Minutes} - \text{Break Minutes} - \text{Blocked Leave Minutes}}{\text{Slot Duration Minutes} + \text{Buffer Minutes}} \right\rfloor$$
When schedules or facility operating settings are absent, the engine explicitly reports `status: "configuration_incomplete"`, `status: "facility_closed"`, or `status: "no_practitioners_scheduled"` rather than guessing numbers.

### 2.5 Strict Segregation of Hypothetical Simulations
What-if simulations are tagged with `is_simulation_only: true`, stored strictly in `capacity_scenarios`, carry permanent audit provenance, and are completely isolated from live production schedules and patient appointments.

### 2.6 Privacy-Preserving Wallboard Mode (Zero PHI)
When wallboard mode is enabled (`wallboard_mode=true`), the engine strips `patient_id`, `mrn`, and `patient_name`, replacing them with opaque token references (e.g. `Token T-101`) to allow public waiting room displays without exposing protected health information.

### 2.7 Transparent Factual Reasons
Bottleneck intelligence compares stage elapsed durations against approved thresholds and outputs factual database states (e.g. *"Patient waiting in reception; practitioner has not called token"*). When a reason is absent, the engine states `"Reason not recorded"`.

---

## 3. Database Schema (Migration 033)

Migration `033_clinical_command_center_capacity_planning_schema.sql` establishes 4 core tables:
1. `command_center_threshold_rules`: Governed warning and critical thresholds per operational stage.
2. `operational_alerts`: Deduplicated, severity-managed operational alerts with lifecycle management (`ACTIVE`, `ACKNOWLEDGED`, `RESOLVED`).
3. `capacity_scenarios`: Hypothetical scenario simulation records segregated from production calendars.
4. `operational_action_audit`: Tamper-evident ledger of human operational decisions.

---

## 4. Consequences and Verification

- **Positive:** Authorized clinic staff gain reliable, real-time situational awareness of today's workload, bottlenecks, and capacity constraints without risking patient privacy, clinical triage confusion, or clinician morale.
- **Verification:** Validated by comprehensive unit tests (`tests/unit/test_command_center.py`), full REST API integration tests (`tests/integration/test_command_center_api.py`), and full repository regression test suite (544+ tests passing).

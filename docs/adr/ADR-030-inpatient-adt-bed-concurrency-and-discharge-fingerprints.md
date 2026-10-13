# ADR-030: Inpatient ADT State Machine, Bed Concurrency Locking & Discharge Fingerprints

## Status
Accepted

## Context
As ZAYVORA MATAB OS expands from outpatient dispensaries to multi-specialty Unani hospitals and inpatient facilities offering specialized *Ilaj-bil-Tadbeer* (Regimenal Therapies such as Hijama, Dalk, Hammam, Fasd, and Taleeq), inpatient Admission, Discharge, and Transfer (ADT) workflows become essential.

Hospital operations present critical patient safety and operational risks:
1. **Bed Double-Allocation Hazard:** Concurrent staff admitting or transferring patients into the same bed simultaneously without database-level concurrency locking causes severe operational confusion and clinical safety incidents.
2. **Loss of Location & Shift History:** When patients are moved between wards (e.g., Observation to Regimenal Therapy to General Ward), standard CRUD overwrites lose clinical handover context, shift accountability, and timestamped movement history.
3. **Discharge Summaries Lacking Completeness Verification:** Clinicians discharging patients with incomplete medical courses, vague follow-up plans, or missing emergency return precautions risk patient readmission and adverse outcomes.
4. **Discharge Summary Post-Discharge Alteration:** Inpatient discharge summaries are legal medical documents that must be locked with cryptographic tamper-evidence once signed by the attending practitioner.

## Decision
We implement a dedicated, enterprise Inpatient ADT and Bed Management architecture:

### 1. Database-Level Unique Concurrency Lock (`active_stay_lock`)
- In `ipd_beds`, we maintain an `active_stay_lock TEXT UNIQUE` column.
- When a bed is reserved or occupied, `active_stay_lock` is set to `stay:<bed_id>:<admission_id>`.
- The database unique constraint guarantees that at most one active admission can ever hold a given bed at any instant. Concurrent attempts to allocate the bed immediately raise a `ConflictError` (HTTP 409).
- When a bed is released upon transfer or discharge, `active_stay_lock` is cleared (`NULL`) and the bed transitions to `cleaning` before becoming `available`.

### 2. Strict 8-State Inpatient ADT State Machine
- Admission requests follow discrete transitions: `requested` -> `accepted` -> `awaiting_bed` -> `admitted` -> `transferred` -> `discharged` (or `cancelled` / `entered_in_error`).
- An admission request never automatically defaults to `admitted` without explicit bed assignment.
- Patient admission generates a dedicated `INPATIENT_STAY` encounter while leaving previous outpatient encounters completely intact and referenced via `originating_encounter_id`.

### 3. Clinical Handover & Chain-of-Custody Events
- Inter-ward and bed transfers create immutable rows in `ipd_handover_records` and `ipd_admission_events`, documenting previous location, destination, shift teams, clinical summary, and attending practitioner.

### 4. Mandatory Section Checklist & Cryptographic PIN Signing
- A discharge summary enforces mandatory clinical sections (`course_in_hospital`, `follow_up_plan_summary`, `return_precautions`).
- Signing requires the attending clinician to enter their secret digital PIN, verified against `practitioner_profiles.digital_signature_pin_hash`.
- Upon valid verification, an immutable snapshot is frozen in `ipd_discharge_summary_versions` with a SHA-256 cryptographic digest. Subsequent amendments create new version records without modifying the signed original.

## Consequences
- **Positive:** Eliminates double-booking of hospital beds; guarantees referential integrity across inpatient stays; provides legally defensible discharge summaries with cryptographic non-repudiation.
- **Negative:** Requires staff to follow formal bed release and cleaning transitions before reallocating beds; enforces strict PIN verification on clinician sign-off.

# Capacity Planning & Demand Forecasting Runbook

**Product:** ZAYVORA MATAB OS — Standalone Matab/Clinic Operating System  
**Phase:** 34 — Clinical Operations Command Center & Capacity Planning  
**Document Status:** Operational Runbook  

---

## 1. Deterministic Capacity Planning Methodology

Capacity in ZAYVORA MATAB OS is strictly calculated from persisted calendar schedules, facility working hours, and practitioner breaks. It is never estimated through probabilistic guessing or unverified heuristics.

### Canonical Capacity Slot Formula:

$$\text{Capacity Slots} = \sum_{p \in \text{Scheduled Practitioners}} \left\lfloor \frac{\text{Shift Minutes} - \text{Break Minutes} - \text{Blocked Leave Minutes}}{\text{Slot Duration Minutes} + \text{Buffer Minutes}} \right\rfloor$$

### Handling Missing Configurations:
- If facility settings or operating hours are absent, the engine returns:
  ```json
  {
    "status": "configuration_incomplete",
    "missing_inputs": ["facility_settings"],
    "message": "Capacity unavailable — facility settings not configured."
  }
  ```
- If the facility is closed on the target day of the week, the engine returns `status: "facility_closed"`.
- If no practitioner schedules are defined for that day, the engine returns `status: "no_practitioners_scheduled"`.
- The engine **never** invents fallback clinician shifts or assumes 24/7 availability.

---

## 2. Demand Calculation & Utilization Metric

### Demand Definition:
$$\text{Total Booked Demand} = \text{Count of Appointments with Status } \in (\text{booked}, \text{confirmed}, \text{arrived}, \text{in\_progress}, \text{completed})$$

### Utilization Percentage:
$$\text{Utilization \%} = \min\left(100.0, \text{round}\left(\frac{\text{Booked Demand}}{\text{Total Configured Capacity}} \times 100, 1\right)\right)$$

---

## 3. What-If Scenario Simulations

Clinic administrators can evaluate operational adjustments without modifying production calendars:

### Supported Adjustments:
1. `ADD_PRACTITIONER_SHIFT`: Simulates adding a temporary shift or locum practitioner (+hours).
2. `REMOVE_PRACTITIONER_SHIFT`: Simulates sudden doctor illness or emergency leave (-hours).
3. `MODIFY_SLOT_DURATION`: Evaluates shifting from 15-minute consultations to 20 or 30 minutes.

### Strict Segregation Safeguard:
All simulations are tagged with `is_simulation_only: true` and saved strictly to `capacity_scenarios`. They carry permanent audit provenance and display the banner:
> *"Simulated projection only. Production schedules, calendars, and bookings are UNCHANGED."*

---

## 4. Privacy Wallboard Operational Guidelines

For shared waiting room monitors and OPD hallway wallboards:
1. Enable `wallboard_mode=true` via UI or `?wallboard_mode=true` API parameter.
2. System automatically sanitizes response:
   - Strips `patient_id`, `mrn`, and `patient_name`.
   - Injects opaque token label: `Token T-101`.
   - Omits clinical notes, reasons, and diagnosis fields.
3. Wallboards provide real-time queue progression without compromising patient privacy or violating ABDM / HIPAA privacy mandates.

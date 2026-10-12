# ZAYVORA MATAB OS

> **Unani-first clinical practice, supported by modern clinical workflows.**  
> *Easy for an individual Hakeem. Complete for a clinic. Configurable for a hospital.*

**Version:** 1.1.0  
**Status:** Independent Standalone Build  
**Zero-Dependency Runtime:** Python 3.9+ / SQLite WAL / Modern Standards Web Client  

---

## 1. Executive Overview

ZAYVORA MATAB OS is a completely standalone clinical operating system engineered specifically for Unani medicine practitioners (Tabibs/Hakeems), multi-practitioner clinics, and institutional hospitals.

### Hard Independence Boundary
This product is **not** an integration, UI theme, or sub-module of the legacy ZAYVORA Health OS. It maintains its own independent repository, relational database, domain services, REST APIs, authentication lifecycle, deterministic safety engines, and test suite. It runs, migrates, prescribes, and prints without external cloud services or legacy systems being online.

---

## 2. Architecture & Design Principles

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ZAYVORA MATAB OS RUNTIME                        │
├────────────────────────────────┬───────────────────────────────────────┤
│ Profile A: MATAB (Solo Hakeem) │ - Single-room queue & walk-in OPD     │
│                                │ - Fast 5-minute Consultation Canvas   │
│                                │ - Unani assessment & Nuskha compiler  │
│                                │ - Thermal / A4 prescription printing  │
├────────────────────────────────┼───────────────────────────────────────┤
│ Profile B: CLINIC (Multi-Doc)  │ + Multi-doctor scheduling queues      │
│                                │ + Dispensary & FEFO batch inventory   │
│                                │ + Patient billing, receipts & ledger  │
├────────────────────────────────┼───────────────────────────────────────┤
│ Profile C: HOSPITAL (Inst.)    │ + Multi-facility scoping & RBAC       │
│                                │ + Break-glass access logging          │
│                                │ + Standard FHIR / ABDM adapters       │
└────────────────────────────────┴───────────────────────────────────────┘
```

1. **Relational-First Single Source of Truth:** All transactions, clinical encounters, and immutable prescriptions are recorded in an ACID-compliant relational store with foreign key enforcement and Write-Ahead Logging (WAL).
2. **Simple Front of House / Powerful Back of House:** A clean, 5-destination role-aware shell backed by deep deterministic safety rules, clinical ontologies, and tamper-evident audit chaining.
3. **Deterministic Safety Preflight:** Prescriptions must pass server-side preflight evaluation yielding `PASS`, `WARN`, `BLOCK`, or `UNKNOWN`. `BLOCK` strictly prohibits signing; `UNKNOWN` invokes a fail-closed clinical review hold.
4. **No Autonomous AI Signing:** Clinical AI assistants are purely advisory drafts; prescriptions can only be signed by licensed human practitioners with PIN verification.
5. **Immutable Records & Tamper-Evident Chaining:** Signed prescriptions are append-only and stamped with a cryptographic SHA-256 fingerprint. All audit events are linked using forward-chained cryptographic hashes.

---

## 3. Five Primary Destinations & Consultation Canvas

- **1. Today:** The Command Center answering *"Who needs my attention next?"* (Next patient hero card, OPD token queue, attention alerts).
- **2. Patients:** Master Patient Index (MPI), duplicate warning heuristic, and longitudinal **Patient 360** (vitals curve, previous Nuskha history, documented allergies).
- **3. Consultation:** The unified **3-Zone Consultation Canvas**:
  - *Zone 1 (Patient Context):* Collapsible demographics, allergies indicator, active medications, vital history.
  - *Zone 2 (Main Clinical Work Area):* Progressive stepper: Chief Complaint -> Vitals & Exam -> Parallel Assessment (Unani Mizaj & Modern Red Flags) -> Usul-e-Ilaj Care Plan -> Nuskha Builder -> Review & Electronic Sign.
  - *Zone 3 (Contextual Guidance Rail):* Real-time safety preflight report and statutory classical citations (NFUM, UPI).
- **4. Prescriptions:** Register of signed and draft prescriptions with thermal receipt & A4 print generator.
- **5. Follow-ups:** Continuum care review tasks and cohort surveillance.
- **More Hub:** Dispensary batch FEFO inventory, Capability Registry monitor, and Chained Audit log inspector.

---

## 4. Governed Classical Sources & Safety Rules

All botanical monographs and formulation recipes cite verified statutory sources:
- **NFUM (National Formulary of Unani Medicine):** Parts I-VI.
- **UPI (Unani Pharmacopoeia of India):** Parts I-II.
- **Al-Qanun fi al-Tibb (Avicenna):** Theoretical Mizaj and Afaal principles.
- **Bayaz-e-Kabir (Hakeem Kabiruddin):** Practical formulation recipes and corrective adjuvants (*Badal / Musleh*).
- **Schedule E(1) & Mudabbar Rules:** Mandatory verification of detoxification for poisonous botanicals (e.g. *Kuchla / Strychnos nux-vomica*).

---

## 5. Quickstart & Testing

### Prerequisites
- Python 3.9+ (Standard Library)
- Modern Web Browser (Edge, Chrome, Safari, Firefox)

### 1. Run Automated Test Suite
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
*(Runs 26 comprehensive unit, integration, and security tests in < 0.5s).*

### 2. Start the Server
```bash
python3 -m matab.server
```
Navigate your browser to `http://127.0.0.1:8000`.

### 3. Demo Credentials
- **Hakeem (Practitioner):** Username: `hakeem` | Password: `matab123` | Signing PIN: `1234`
- **Receptionist (Front Desk):** Username: `reception` | Password: `matab123`
- **Pharmacist (Dispensary):** Username: `pharmacy` | Password: `matab123`
*(All demo patient records are synthetic and marked with `[SYNTHETIC TEST RECORD]` tags).*

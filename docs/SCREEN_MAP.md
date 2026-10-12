# Screen Map & UX Architecture — ZAYVORA MATAB OS

**Design Doctrine:** Keep the front of house calm, minimal, and task-focused. Maximum of 5 high-frequency primary navigation destinations, plus an expandable "More" hub for operations, formulary, and administration.

---

## 1. High-Level Navigation Topology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TOP BAR: FACILITY / PROFILE / USER              │
├─────────┬──────────────┬──────────────┬───────────────┬────────────────┤
│ 1. TODAY│ 2. PATIENTS  │3.CONSULTATION│4.PRESCRIPTIONS│ 5. FOLLOW-UPS  │ [MORE...]
└─────────┴──────────────┴──────────────┴───────────────┴────────────────┴──────────┘
```

### Destination Breakdown

### Destination 1: `Today` (The Command Center)
- **Primary Question Answered:** *"Who needs my attention next?"*
- **Components:**
  - **Next Patient Card:** Prominent OPD Token number, patient name, arrival time, chief complaint badge, and a single "Start Consultation" CTA.
  - **Waiting List Queue:** Real-time list of waiting patients with status (`WAITING`, `WITH_NURSE`, `IN_CONSULTATION`).
  - **Action Items Rail:** Unsigned drafts (badge counter), urgent lab reviews, pending follow-ups due today.

### Destination 2: `Patients` (Patient 360 & Registry)
- **Components:**
  - Fast search by Name, Phone Number, or MRN.
  - Instant Duplicate Warning modal showing prospective match percentage and reasons.
  - **Patient 360 Drawer:** Longitudinal timeline showing past visits, previous Nuskha formulas, known drug/herb allergies, and historical Mizaj tendency curve.

### Destination 3: `Consultation` (The Single Canvas)
- **Structured 3-Zone Encounter Workspace:**
  - **Zone 1: Patient Context (Left Rail, Collapsible):**
    - Patient Photo/Avatar, Name, Age/Gender, MRN, OPD Token.
    - Prominent Allergies indicator (Red badge).
    - Current Active Medications & Previous Visit Summary.
  - **Zone 2: Main Clinical Work Area (Center, Step-by-Step Stepper):**
    - Step 1: Chief Complaint & Structured History of Present Illness (HPI).
    - Step 2: Vitals (BP, Pulse, Temp, RR, SpO2, Weight) & Physical Examination.
    - Step 3: Parallel Clinical Assessment:
      - *Unani Track:* Mizaj evaluation (Dam, Balgham, Safra, Sauda), Nabz (Pulse), Baul & Baraz qualitative findings.
      - *Modern Track:* Problem list, ICD-10 suggestions, Red Flag checklists.
    - Step 4: Care Plan (*Usul-e-Ilaj*): Dietary modifications (*Ilaj-bil-Ghiza*), Regimen therapies (*Ilaj-bit-Tadbeer* like Hijama, Daluk, Riyazat).
    - Step 5: Nuskha Formulation Builder: Search approved formulary (e.g. *Majoon Arad Khurma*, *Sharbat Bazoori*), dosage form, unit, frequency, duration, and vehicle (*Anupan*).
    - Step 6: Clinician Review & Electronic Signature with PIN.
  - **Zone 3: Contextual Guidance Rail (Right Rail, Collapsible):**
    - Real-time Safety Preflight Alerts (`PASS`, `WARN`, `BLOCK`, `UNKNOWN`).
    - Classical text citations and NFUM monograph extracts.
    - AI Socratic draft assistance (optional, read-only draft suggestion).

### Destination 4: `Prescriptions` (Formulary & Order History)
- Filter by: `Drafts`, `Signed`, `Dispensed`, `Cancelled`.
- One-click Thermal Receipt / A4 PDF Print preview.
- Immutable amendment history tracking with visual diff of changes.

### Destination 5: `Follow-ups` (Care Continuum)
- Scheduled patient reviews, 7-day/14-day/30-day monitoring cohorts.
- Follow-up call task list for clinic receptionists.
- Adverse event logging and resolution status.

### Destination 6: `More` (Role & Profile Gated)
- **Dispensary & Inventory:** FEFO batch tracking, expiry alerts, Mudabbar certification check.
- **Clinic Billing:** Quick receipt generation, payment method, OPD consultation fee register.
- **Formulary Knowledge Browser:** Search classical monographs (NFUM, UPI, Bayaz-e-Kabir).
- **System Governance & Audit:** Capability Registry status monitor, tamper-evident audit logs.
- **Settings:** Organization profile (Matab vs Clinic vs Hospital), users, and print templates.

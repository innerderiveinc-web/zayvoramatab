# ZAYVORA MATAB OS — V1 Bounded Scope & Release Acceptance Criteria

**Audit Version:** 1.0.0 (Prompt 50 Repository-Wide Baseline)  
**Target Operational Profile:** Single-Facility Classical Unani Matab (Outpatient Department / OPD Clinic)  
**Primary Deployment Mode:** On-Premises or Private Cloud Linux Instance running Python 3.11+ and SQLite WAL Mode  

---

## 1. Executive Definition of V1

The initial release (V1.0.0) of **ZAYVORA MATAB OS** is explicitly bounded to provide a complete, safe, robust, and ergonomically superior operating system for a single-facility classical Unani outpatient clinic (Matab). It harmonizes traditional Unani diagnostic frameworks (Mizaj, Nabz, Akhlat) with modern clinical safety firewalls, strict posology controls, pharmacy dispensing, cashier billing, and tamper-evident auditability.

---

## 2. In-Scope Modules for V1

| Subsystem / Functional Area | In-Scope Operational Capabilities for V1 Release | Primary User Persona |
| :--- | :--- | :--- |
| **Patient Registration & Triage** | Patient demographic capture, longitudinal MRN generation, vital signs recording (BP, Pulse, RR, Temp, Weight), and emergency triage. | Clinic Receptionist / Triage Nurse |
| **Dual-Model Clinical Consultation** | Stepper-driven consultation workflow: Classical Unani assessment (10-point Nabz analysis, Mizaj radial scoring, Baul/Baraz) integrated with modern ICD-10 diagnostic coding. | Clinician (Doctor / Tabib / Hakeem) |
| **Prescribing & Formulation Builder** | High-density keyboard-driven Nuskha prescription builder, classical compound formulations (Majun, Jawarish, Itrifal, Habb), and automated posology calculations. | Clinician (Doctor / Tabib) |
| **Clinical Safety Firewall** | Deterministic drug-herb, herb-herb contraindication checks, Schedule E(1) toxic botanical safeguards, mandatory Mudabbar purification check, and Tabib PIN attestation gate. | Safety Firewall Engine / Clinician |
| **Pharmacy & Dispensing Operations** | Dispensary stock tracking, batch inventory management, Mudabbar batch certificate verification, and real-time stock deduction upon dispensing. | Pharmacist / Dispensary Officer |
| **Cashier Billing & Receipts** | Tariff calculation for consultations, procedures (Ilaj-bit-Tadbeer), and dispensed medicines; multi-mode payment capture (Cash, UPI, Card); printable receipts. | Cashier / Billing Staff |
| **Care Continuity & Parhez Instructions** | Standardized dietary recommendations (Parhez / Ghiza), bilingual prescription PDF generation (Urdu/English), and follow-up appointment booking. | Clinician / Receptionist |
| **Cryptographic Audit & Security** | Immutable SHA-256 chained audit ledgers, role-based access control (RBAC/ABAC), emergency break-glass logging, and zero plaintext secret disclosure. | Compliance & Security Officer |
| **Release & Quality Governance** | Non-intrusive security posture scanners, STRIDE threat models, GSN clinical safety cases, automated test execution, and fail-closed release gates. | Engineering & Quality Lead |

---

## 3. Explicit Non-Goals (Deferred to V2 Enterprise Release)

To prevent scope creep, ensure clinical safety, and preserve system reliability, the following enterprise capabilities are explicitly declared as **OUT OF SCOPE** for the V1 release:

1. **Inpatient Hospitalization & Bed Management:** Inpatient wards, bed allocation matrices, and intensive care workflows are deferred to V2. V1 focuses strictly on Outpatient Clinics (OPD).
2. **Surgical Operation Theater (OT) Management:** Regimenal therapies (Ilaj-bit-Tadbeer like Hijama, Fasd, Dalk) are supported as outpatient procedures; major surgical scheduling is out of scope.
3. **Live ABDM Production Network Bridge:** Full national live data exchange via National Health Authority bridges requires government compliance certification. V1 provides complete synthetic sandbox conformance; live production activation is scheduled for V1.1.
4. **Hardware IoT Bio-Sensors:** Real-time hardware USB/Bluetooth pulse sensors (*Nabz-o-Meter*) are not required; V1 relies on clinician sensory evaluation input.
5. **Multi-Hospital Cross-Enterprise Cloud Synchronization:** Real-time multi-region distributed consensus across independent hospital networks is deferred. V1 supports branch-level data scoping within a single clinic entity.
6. **AI Autonomous Prescribing:** The system explicitly forbids autonomous AI prescription writing. AI and RAG components act purely in an advisory capacity (*CDS Level 1*), strictly requiring human Tabib confirmation and PIN signing.

---

## 4. Release Acceptance Criteria for V1.0.0

A candidate build must satisfy all eight objective criteria to achieve the **`QUALIFIED`** release verdict:

- [x] **Criterion 1 (Test Suite Integrity):** 100% of the 840 automated tests must pass cleanly (0 failures, 0 errors, 0 skips) across Unit, Integration, and E2E suites.
- [x] **Criterion 2 (Database Schema Cleanliness):** All 48 database migrations must apply sequentially without errors or circular foreign key dependencies.
- [ ] **Criterion 3 (Clinical Monograph Attestation - P0):** Formal digital sign-off by an accredited AYUSH Tabib on core single and compound drug posologies recorded in the governance ledger (`GAP-P0-01`).
- [ ] **Criterion 4 (Production Secret Key Enforcement - P0):** Fail-closed application startup validation preventing default or insecure fallback secrets in production environments (`GAP-P0-02`).
- [ ] **Criterion 5 (Mudabbar Batch Verification at Dispensary - P0):** Pharmacist dispensary workflow enforces physical batch certificate verification for Schedule E(1) toxic herbs prior to dispensation (`GAP-P0-03`).
- [ ] **Criterion 6 (Automated SQLite WAL Checkpointing - P0):** Periodic background task performing SQLite WAL checkpointing and integrity verification (`GAP-P0-04`).
- [x] **Criterion 7 (Security Posture Gate):** Built-in security scanners (SCA, Secrets, Headers, SQL Injection) must report zero unmitigated High or Critical findings.
- [x] **Criterion 8 (Audit Ledger Cryptographic Integrity):** Tamper-evident SHA-256 hash chains across all five audit ledgers must verify cleanly with zero hash mismatches.

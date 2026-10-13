# ZAYVORA MATAB OS — Release Notes (v1.0.0-rc1)
## Release Candidate for Standalone Clinic Pilot Launch

---

## 1. Overview
ZAYVORA MATAB OS **v1.0.0-rc1** is the first stabilized release candidate of the completely standalone AYUSH/Unani Clinical Operations System. Built with zero runtime, API, or database reliance on the legacy Health OS, this build provides edge-ready clinic operations, digital prescribing, deterministic clinical safety preflight, multi-tenancy, and tamper-evident audit logging.

---

## 2. Key Capabilities in this Release

### Clinical & Consultation Engine
- **Master Patient Index (MPI) & Patient 360:** Longitudinal record tracking across past visits, diagnoses, prescriptions, and allergies.
- **Unani Clinical Assessment:** Structured eight-fold examination (`Nabz`, `Baul`, `Baraz`, `Mizaj`), temperament grading, and `Usul-e-Ilaj` treatment planning.
- **Modern Clinical Assessment:** Vital sign analysis, emergency red flag triage, and objective problem list documentation.
- **Nuskha-Wisi Prescription Engine:** Classical Unani formulation builder with dosage forms (`SAFOOF`, `MAJOON`, `HAB`, `SHARBAT`), unit conversion, and frequency calculation.
- **Deterministic Safety Firewall:** Zero AI hallucination; evaluates toxic botanicals (Schedule E(1) Mudabbar requirements), pediatric contraindications, and 48 documented herb-drug interaction pairs with strict fail-closed enforcement.
- **Cryptographic PIN Signatures:** Clinicians electronically sign prescriptions using PBKDF2-verified PINs, generating immutable SHA-256 digital fingerprints and locking historical snapshots.
- **Document Rendering:** Generates printable A4 consultation sheets matching the exact signed snapshot with digital fingerprint verification and draft watermarking.

### Clinic Operations & Administration
- **Daily Queue Management:** Token distribution with daily counter resets per facility.
- **Exact Accounting & Invoicing:** Integer paise arithmetic preventing floating-point rounding errors across line items and payments.
- **Dispensary & Inventory OS:** FEFO batch dispensing; blocks expired stock, quarantined batches, and unsigned prescriptions.
- **Multi-Branch Hierarchy:** Multi-facility tenancy isolation with independent role-based permissions (`RBAC`).
- **Controlled Pilot Operations & Evaluation:** Governed pilot onboarding checklists, data migration dry-run reconciliations, P0 stop conditions, and 14-metric adoption scorecards with explicit telemetry availability flags.

---

## 3. Scope Boundaries & Known Limitations
1. **Live ABDM Gateway:** Operating in verified `CONTRACT_TESTED_HARNESS` mode. Live connectivity to the NHA National Health Gateway requires facility registration on the Health Facility Registry (HFR).
2. **Cellular SMS & Online Payments:** External cellular SMS gateways and online payment webhooks are disabled by default (`BLOCKED_BY_EXTERNAL_DEPENDENCY`); local thermal printing, cash, and manual POS card accounting operate fully offline.
3. **Formulary Extensibility:** Initial verified catalog includes 25 classical standard monographs and 48 interaction pairs. Compounded formulas not in the catalog must be verified manually by attending clinicians.

---

## 4. Upgrade & Installation Instructions
Refer to [`DEPLOYMENT_RUNBOOK.md`](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/production-readiness/DEPLOYMENT_RUNBOOK.md) for server provisioning and SQLite database initialization.

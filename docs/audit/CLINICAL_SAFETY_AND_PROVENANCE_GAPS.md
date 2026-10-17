# ZAYVORA MATAB OS — Clinical Safety, Mudabbar Governance & Provenance Audit

**Audit Version:** 1.0.0 (Prompt 50 Repository-Wide Baseline)  
**Clinical Scope:** Unani Tibb & AYUSH Prescribing Safety, Classical Monograph Provenance, Toxic Botanical Safeguards (Schedule E(1)), Posology Ceilings, and Clinician Attestation Gates  

---

## 1. Classical Unani Pharmacopoeial Grounding & Provenance

### 1.1. Authoritative Source Documents
The system's knowledge base and prescribing rules are derived from recognized classical and statutory compendia:
- **NFUM:** National Formulary of Unani Medicine (Parts I–VI, Ministry of AYUSH, Government of India).
- **UPI:** Unani Pharmacopoeia of India (Parts I & II).
- **Al-Qanun fi al-Tibb (The Canon of Medicine):** Ibn Sina (Avicenna) — classical mizaj principles and single drug actions.
- **Kitab al-Kulliyat:** Ibn Rushd (Averroes) — foundational physiology and organ-axis dynamics.

### 1.2. Provenance Integrity Audit
- **Locator Pinning:** Every monograph in `unani_monographs` and clinical claim in `kavs_claims` is linked to a source document ID, edition, volume, and page locator.
- **Current Evidence Limitation:** While synthetic seeds reflect canonical formulations (e.g., Majun Dabidul Ward, Habb-e-Suranjan, Roghan-e-Badam Shirin), production deployment requires formal clinical signing and validation by an accredited Tabib / AYUSH panel before live patient prescribing.

---

## 2. Mudabbar (Detoxification) & Schedule E(1) Safeguards

### 2.1. Regulated Botanicals & Minerals
Under the Drugs and Cosmetics Act (Schedule E(1) of ASU Drugs), toxic botanical and mineral substances require mandatory detoxification (*Mudabbar*) prior to compound formulation:
- **Azaraqi (Kuchla / *Strychnos nux-vomica*):** Contains strychnine and brucine; requires boiling in cow's milk or frying in Roghan-e-Zard.
- **Afyoon (*Papaver somniferum*):** Opium alkaloid; strictly controlled posology and detoxification.
- **Bhilawan (*Semecarpus anacardium*):** Irritant vesicant juice; requires rubbing with brick powder and washing.
- **Samm-ul-Far (*Arsenic trioxide*):** Requires intensive classical calcination (*Kushta*).

### 2.2. Safety Firewall Enforcement Mechanisms
1. **Prescribing Interlock:**
   - Attempting to prescribe an unpurified (`raw`) Schedule E(1) botanical immediately triggers a high-severity `HARD_STOP` alert in `safety_firewall_engine.py`.
   - The prescription status is blocked in `BLOCKED_SAFETY_VIOLATION` unless the clinician explicitly specifies the `mudabbar` formulation variant.
2. **Clinician PIN Attestation Gate:**
   - Overriding a severe posology or Schedule E(1) alert cannot be done via a casual click. The system mandatorily requires the Tabib's 4-digit secret authorization PIN and a recorded clinical justification.
3. **Dispensary Batch Verification:**
   - At the pharmacy dispensary counter, dispensing a Schedule E(1) drug requires the pharmacist to verify and record the physical Mudabbar batch certificate number in `dispensation_records`.

---

## 3. Posology Ceilings & Pediatric/Geriatric Scaling

### 3.1. Posology Calculation Rules (`posology_service.py`)
- **Single Dose Maximum:** Rejection if a single dose exceeds the pharmacopoeial ceiling (e.g., Azaraqi > 60 mg single dose).
- **Daily Cumulative Maximum:** Strict checking of total 24-hour intake across multiple doses.
- **Pediatric & Geriatric Scaling:**
  - Automatically adjusts dosage using Young's Rule and Clark's Rule based on patient age and weight captured during triage.
  - Generates warning for patients < 12 years or > 65 years when prescribing potent compound nuskhas.

---

## 4. Goal Structuring Notation (GSN) Clinical Safety Cases

### 4.1. Safety Case Architecture (`clinical_safety_case_service.py`)
- Clinical safety claims are structured using Goal Structuring Notation (GSN):
  - **Top Goal (G01):** "The ZAYVORA MATAB OS prescribing and consultation engine does not cause preventable harm to patients."
  - **Strategy (S01):** "Argument based on multi-tiered deterministic safety firewalls, clinician PIN attestation, and pharmacopoeial grounding."
  - **Evidence Nodes (E01–E05):** Automated tests, audit records, and verified monograph locators.
- **Fail-Closed Clinical Release Gate:**
  - Evaluates all active clinical hazards. If any hazard classified as `CATASTROPHIC` or `CRITICAL` remains unmitigated, the release qualification gate strictly outputs `BLOCKED`.

---

## 5. Clinical Safety Action Plan for V1 Pilot

1. **Tabib Certification Panel:** Convene a 3-member panel of AYUSH-certified BUMS/MD (Unani) practitioners to review and cryptographically sign the top 100 core outpatient formulations in the database.
2. **Physical Mudabbar Protocol Sign-Off:** Establish written standard operating procedures (SOPs) for the clinic pharmacy compounding room verifying detoxification certificates for all incoming raw herbs.

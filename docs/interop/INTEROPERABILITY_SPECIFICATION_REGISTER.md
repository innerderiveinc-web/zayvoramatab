# Enterprise Interoperability Specification Register & Governance Contract

**Document ID:** SPEC-REG-P31-2026-01  
**Project:** ZAYVORA MATAB OS  
**Phase:** 31 — Enterprise Interoperability, FHIR APIs, ABDM Integration & External-System Data Exchange  
**Release Target:** Enterprise Production & ABDM Sandbox/Production Milestone Certification (M1–M4)

---

## 1. Pinned Specifications & Standards Registry

To prevent runtime drift, inconsistent FHIR profiling, and invalid ABDM API payloads, all interoperability components in ZAYVORA MATAB OS are strictly pinned to the following authoritative standards:

| Standard / Guide | Official Package / System URI | Pinned Version | Status | Integrity Checksum (SHA-256) |
|---|---|---|---|---|
| **HL7 FHIR Core** | `http://hl7.org/fhir/R4` | `4.0.1` | ACTIVE | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| **NRCeS ABDM IG** | `https://nrces.in/ndhm/fhir/r4` / `ndhm.in` | `6.5.0` | ACTIVE | `4a8f9c0e7b2134d9a6e1189c4d29f1092a8b301c29e123fa98e091b4129a0081` |
| **LOINC** | `http://loinc.org` | `2.76` | ACTIVE | `b491a18204d2091c6e189d20c38210924b11129c910123efca49591b7852b112` |
| **SNOMED CT** | `http://snomed.info/sct` | `2024-03` | ACTIVE | `5c89110294e10928b610192e48201948ba10291e019283fa4891b02938102931` |
| **UCUM** | `http://unitsofmeasure.org` | `2.1` | ACTIVE | `1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b` |
| **ABDM HIE-CM** | `https://dev.abdm.gov.in/gateway/v0.5` | `v3.0.0` | ACTIVE | `9f8e7d6c5b4a3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b` |

---

## 2. Supported FHIR Profiles & Resource Structure

ZAYVORA MATAB OS implements deterministic serialization and validation for the following NRCeS-compliant FHIR R4 resources:

1. **Patient Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient`
   - Maps internal canonical patient demographics, ABHA number (`14-digit`), and ABHA address (`<name>@abdm`).
2. **Practitioner Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Practitioner`
   - Maps treating Hakeem / Doctor credentials, state council registration, HPR token.
3. **Encounter Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Encounter`
   - Clinical encounter classification (`AMB`, `EMER`, `IMP`), consultation start/end timestamps, facility reference.
4. **Condition Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Condition`
   - Clinical diagnosis, dual-track Unani Tashkhees and modern ICD-10/SNOMED findings, verification status.
5. **Observation Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Observation`
   - Vital signs, lab measurements, Mizaj assessment, Nabz characteristics, and clinical findings.
6. **MedicationRequest Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/MedicationRequest`
   - Classical Unani formulations (Nuskha items) and modern medications, dosage form, frequency, duration, route.
7. **DiagnosticReport Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/DiagnosticReport`
   - Structured laboratory and radiological investigation summaries.
8. **DocumentReference & Composition:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/Composition`
   - Clinical summary document, discharge summary, or OPD consultation note with clinician cryptographic signature.
9. **Bundle Profile:** `https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentBundle`
   - Bundle `type = 'document'`, with `Composition` as the mandatory first entry (`Bundle.entry[0].resource`).

---

## 3. Unani Terminology Preservation & Mapping Rules

### 3.1 Ethical & Epistemological Principle
Unani medicine operates on distinct systemic concepts (Mizaj, Akhlat, Quwa, Arwah, Tabiat, Asbab-e-Sittah Zarooriyyah). Forcing classical Unani constructs into generic modern ICD/SNOMED codes damages clinical fidelity and produces misleading automated clinical decision support.

### 3.2 Controlled Mapping Taxonomy
Every terminology mapping entry in `interop_terminology_mappings` must be assigned one of four discrete mapping states:

1. **`exact_reviewed`**: Proven semantic and diagnostic equivalence approved by an AYUSH/Unani-modern expert review panel.
   - Example: *Humma-e-Aafan* $\rightarrow$ SNOMED CT `409702008` (Infectious fever).
2. **`broader_than`**: Target modern concept covers a wider category than the Unani diagnosis.
   - Example: *Zeeq-un-Nafs Balghami* $\rightarrow$ SNOMED CT `195967001` (Asthma) [Modern term does not distinguish phlegmatic humor pathogenesis].
3. **`narrower_than`**: Target modern concept represents a narrower manifestation.
   - Example: *Su-e-Mizaj Har* $\rightarrow$ SNOMED CT `386661006` (Fever).
4. **`no_safe_mapping`**: Default for core Unani constitutional concepts where no modern biomedical equivalent exists.
   - Example: *Mizaj Damawi*, *Safra-e-Ghayr Tabiyya*, *Munzij Balgham*, *Tadbeer Hijamah*.
   - **Enforcement:** In FHIR JSON exports, these concepts MUST be emitted with the internal canonical code, Arabic/Urdu name, transliterated display, and an unmapped annotation, preserving clinical intent without lossy translation.

---

## 4. ABDM Integration Architecture (Milestones M1–M4)

### 4.1 Milestone 1 (M1) — ABHA Identity Management
- Search, link, and verify ABHA addresses and 14-digit ABHA numbers.
- Aadhaar / Mobile OTP verification simulation and sandbox token management.
- Link verified ABHA identity to local `patients` record without duplicate creation.

### 4.2 Milestone 2 (M2) — Health Information Provider (HIP)
- **Care-Context Registration:** Link clinic encounters as distinct care contexts under the patient's ABHA identity.
- **Discovery Privacy:** Care context display names MUST NOT contain clinical diagnosis, sensitive medications, or private health details (e.g. use generic `OPD Consultation - 14 Oct 2026`).
- **Data Transfer:** Upon validated data flow request, bundle health data according to requested `hiType` (`OPConsultation`, `Prescription`, `DischargeSummary`, `DiagnosticReport`), encrypt using ECDH (Curve25519) + AES-GCM, and push to ABDM gateway.

### 4.3 Milestone 3 (M3) — Health Information User (HIU)
- **Consent Request Lifecycle:** Create structured consent request defining requester clinician, purpose code (`CAREMGT`, `BTG`, `PUBHLTH`), date range (`from` $\rightarrow$ `to`), and allowed `hiTypes`.
- **Artefact Gatekeeper:** When consent is granted, store the ABDM consent artefact. Prior to fetching external records, verify:
  1. Artefact status is `GRANTED`.
  2. Current time is between `dateRange.from` and `dateRange.to`.
  3. Requested `hiType` matches the granted permission.
  4. If status transitions to `REVOKED` or `EXPIRED`, immediately terminate access.

### 4.4 Milestone 4 (M4) — Registries
- Health Facility Registry (HFR) identifier binding for clinics and branches.
- Healthcare Professional Registry (HPR) verification for practicing Hakeems.

---

## 5. Inbound Clinical Reconciliation Queue

To protect patient safety and maintain legal non-repudiation:
1. External FHIR bundles received from outside hospitals, labs, or ABDM are **STAGED** in `inbound_record_reconciliations`.
2. Staged records **NEVER** modify `encounters`, `prescriptions`, or `patient_allergies` automatically.
3. A clinician must review staged items in the consultation workspace and select:
   - `ACCEPT_INTO_RECORD`: Incorporates the data with provenance tracking (`external_source`).
   - `REJECT_INCOMPATIBLE`: Rejects data that is erroneous or clinically inapplicable.
   - `FLAG_CONTRADICTION`: Alerts the treating team to conflicts between external history and local findings.
   - `FILE_AS_EXTERNAL_ATTACHMENT`: Stores record as reference-only document without active clinical status.

---

## 6. Durable Outbox & Replay-Safe Webhook Dispatch

1. **Transactional Outbox:** All external exports and ABDM callback payloads are inserted into `interop_transfer_outbox` in the same database transaction as the business event.
2. **Idempotency:** Every transfer specifies an `idempotency_key` and payload SHA-256 hash. Re-transmissions with identical keys return the existing record without duplicate dispatch.
3. **Replay Protection:** Inbound callbacks must verify:
   - Request timestamp within 300 seconds of current system time ($|T_{\text{now}} - T_{\text{req}}| \le 300$s).
   - Unique request ID / nonce verification preventing duplicate processing.

---

## 7. Cryptographic Audit Ledger Integration (Prompt 29)

Every interoperability transaction emits an immutable event to `ClinicalAuditLedgerEngine`:
- **Event Categories:** `INTEROP_SPEC_REGISTER`, `INTEROP_FHIR_EXPORT`, `INTEROP_FHIR_IMPORT`, `INTEROP_ABDM_M1`, `INTEROP_ABDM_M2`, `INTEROP_ABDM_M3`, `INTEROP_ABDM_M4`, `INTEROP_RECONCILE`.
- **Result States:** Constrained strictly to Prompt 29's permitted vocabulary: `blocked`, `denied`, `failed`, `partial`, `succeeded`, `unknown`.
- **Hash Chaining:** Each record is chained via $H_i = \text{SHA-256}(C_i \parallel H_{i-1})$.

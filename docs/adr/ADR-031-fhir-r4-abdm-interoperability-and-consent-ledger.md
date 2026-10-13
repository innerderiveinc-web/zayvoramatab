# ADR-031: HL7 FHIR R4 Bundles, ABDM Interoperability & Purpose-Aware Consent Ledger

## Status
Accepted

## Context
Ayushman Bharat Digital Mission (ABDM) and international healthcare interoperability require Indian AYUSH and modern hospitals to participate as both Health Information Providers (HIP) and Health Information Users (HIU). This involves exchanging clinical documents structured in HL7 FHIR R4 according to NRCeS India National Digital Health Blueprint profiles.

Key risks and architectural considerations:
1. **Unani Semantic Lossiness:** Classical Unani concepts (qualitative *Mizaj* grades, *Akhlat* humor imbalances, *Afaal* organ faculties, polyherbal compound nuskhas) lack exact 1:1 pre-coordinated equivalents in modern ontologies like SNOMED-CT, LOINC, or ICD-10. Blindly force-mapping Unani diagnoses into modern codes strips clinical fidelity; conversely, omitting standard codes prevents national health data exchange.
2. **Consent-Free Data Leakage:** Exchanging health records without active, purpose-specific patient consent violates data privacy regulations and ABDM specifications.
3. **Premature Certification Claims:** Software that connects only to mock stubs must never claim live production compliance or active certification before receiving official NHA gateway credentials and sandbox validation.

## Decision
We implement a standards-compliant, honest, and provider-independent interoperability architecture:

### 1. Provider-Independent FHIR R4 Exporter & Schema Validator
- Supports 14 FHIR R4 resources: `Bundle`, `Composition`, `Patient`, `Practitioner`, `Organization`, `Encounter`, `Condition`, `Observation`, `MedicationRequest`, `Medication`, `CarePlan`, `DiagnosticReport`, `Specimen`, `ServiceRequest`.
- Generates compliant FHIR R4 Document Bundles for three standard clinical document types:
  - `OPConsultation` (Outpatient consultation note, prescriptions, and vital observations)
  - `DischargeSummary` (Inpatient admission, hospital course, procedures, and discharge medications)
  - `DiagnosticReport` (Laboratory orders, specimen metadata, test results, and critical flags)
- Validates structural completeness and mandatory fields before serialization.

### 2. Lossless Unani Extensions with Explicit Provenance
- In `terminology_mappings`, mappings record equivalence levels: `EQUIVALENT`, `WIDER`, `NARROWER`, `INEXACT_LOSSY`, and `UNMAPPED`.
- Where an inexact match occurs, FHIR resources preserve the original Unani concept in custom extensions (`https://matab.zayvora.org/fhir/StructureDefinition/unani-mizaj-assessment`) alongside the mapped target code, including an explicit human-readable `lossiness_note`.

### 3. Purpose- and Scope-Aware Consent Ledger
- Patient data exports verify active records in `data_sharing_consents`.
- Consents verify `status = 'GRANTED'`, validate temporal validity (`valid_from` <= now <= `valid_until`), and check permissible purpose codes (e.g., `CAREMGT`, `EMERGENCY`). Revoked consents instantly block outbound FHIR generation.

### 4. Transparent Readiness Demarcation & Contract-Accurate ABDM Test Harness
- The system explicitly demarcates three distinct integration states:
  - `CONTRACT_TESTED_HARNESS`: Fully validated against ABDM API specifications via internal test harness.
  - `EXTERNAL_SANDBOX_VALIDATED`: Connected to NHA sandbox gateway with active client ID/secret.
  - `PRODUCTION_APPROVED`: Live certified production deployment.
- In the absence of live production credentials, the system records `BLOCKED_BY_EXTERNAL_DEPENDENCY` and operates strictly in `CONTRACT_TESTED_HARNESS`, logging all exchanges in `abdm_exchange_traces` with idempotent replay protection.

## Consequences
- **Positive:** Enables seamless interoperability with national health networks; safeguards patient consent; preserves classical Unani medical semantics without data degradation; maintains total honesty regarding sandbox/production certification status.
- **Negative:** Requires ongoing maintenance of terminology crosswalk tables as NRCeS and WHO release updated AYUSH terminologies.

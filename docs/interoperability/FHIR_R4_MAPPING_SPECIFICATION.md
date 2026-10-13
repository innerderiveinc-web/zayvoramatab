# FHIR R4 Resource Mapping Specification — ZAYVORA MATAB OS (Phase 12)

- **FHIR Version:** `4.0.1` (HL7 FHIR R4)
- **Target Profile Set:** `HL7-FHIR-R4-CORE` and `NRCES-ABDM-FHIR-R4-V6.5`
- **Mapping Version:** `MAP-FHIR-R4-2026.1`

---

## 1. Core Mapping Principles & Lossy Transformation Policy

1. **Zero Silent Data Loss:** Every mapped resource preserves the original MATAB OS source identifier, version, and clinician-authored text (`text.div` and `code.text`).
2. **Epistemological Integrity for Unani Medicine:** Classical Unani concepts (`Mizaj`, `Ajnas-e-Ashara`, `Usul-e-Ilaj`, `Murakkabat` polyherbal formulations, and `Tadbeer/Mudabbar` detoxification states) are **never** forced into false equivalence with biomedical ICD-10 or SNOMED-CT codes. When exported to FHIR R4:
   - They use the explicit ZAYVORA Unani terminology URI (`https://terminology.zayvora.org/CodeSystem/unani-clinical-v1`) alongside human-readable `code.text`.
   - Any mapping from local codes to standard external codes (`LOINC`, `SNOMED-CT`, `ICD-10`, `UCUM`) is resolved through the versioned `terminology_mappings` table, which records `equivalence_level` (`EQUIVALENT`, `WIDER`, `NARROWER`, `INEXACT_LOSSY`, `UNMAPPED`) and emits an explicit `lossy_mapping_warnings` array whenever `equivalence_level != 'EQUIVALENT'`.

---

## 2. Field-Level Resource Mapping Table

| FHIR R4 Resource | MATAB OS Source Table & Column | Target FHIR Element | Datatype / Coding System | Cardinality | Req? | Validation & Lossiness Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Patient** | `patients.id`, `patients.mrn` | `Patient.id`, `Patient.identifier[0]` | `Identifier` (`urn:zayvora:mrn`) | `1..*` | Yes | Must include `system` and `value`; ABHA added if verified in `patient_identifiers`. |
| **Patient** | `patients.display_name`, `given_name`, `family_name` | `Patient.name[0]` | `HumanName` | `1..*` | Yes | Required in both Core R4 and ABDM Patient profile. |
| **Patient** | `patients.sex` (`MALE`,`FEMALE`,`OTHER`,`UNKNOWN`) | `Patient.gender` | `code` (`male`,`female`,`other`,`unknown`) | `1..1` | Yes | Lowercase normalization; invalid values rejected. |
| **Patient** | `patients.date_of_birth` | `Patient.birthDate` | `date` (`YYYY-MM-DD`) | `0..1` | Opt | Validated ISO-8601 date format. |
| **Practitioner** | `users.id`, `users.full_name` | `Practitioner.id`, `Practitioner.name[0]` | `HumanName` | `1..*` | Yes | Links HPR identifier from `external_id_mappings` if configured. |
| **Organization** | `organizations.id`, `name`, `code` | `Organization.id`, `name`, `identifier[0]` | `Identifier` | `1..1` | Yes | Links HFR identifier if configured. |
| **Location** | `facilities.id`, `ipd_wards`, `ipd_beds` | `Location.id`, `name`, `mode`, `physicalType` | `CodeableConcept` | `1..1` | Yes | Maps Facility (`si`), Ward (`wa`), Room (`ro`), Bed (`bd`). |
| **Encounter** | `encounters.id`, `encounter_type`, `status` | `Encounter.id`, `status`, `class`, `subject` | `Coding` (`v3-ActCode`: `AMB` / `IMP`) | `1..1` | Yes | `INPATIENT_STAY` maps to `class.code = 'IMP'`; `OPD_VISIT` maps to `'AMB'`. |
| **Observation** | `lab_results` / `modern_clinical_observations` | `Observation.id`, `status`, `code`, `subject`, `valueQuantity` / `valueString` | `CodeableConcept` (`LOINC` + local code) | `1..1` | Yes | Preserves original unit and reference range; flags unmapped local codes. |
| **ServiceRequest** | `lab_orders` / `hospital_referrals` | `ServiceRequest.id`, `status`, `intent`, `code`, `subject`, `Priority` | `CodeableConcept` | `1..1` | Yes | `intent = 'order'`; preserves clinical indication in `reasonCode[0].text`. |
| **Specimen** | `lab_specimens.id`, `specimen_type`, `collected_at` | `Specimen.id`, `status`, `type`, `subject`, `collection.collectedDateTime` | `CodeableConcept` | `1..1` | Yes | Links to `ServiceRequest` and `Patient`. |
| **DiagnosticReport** | `lab_diagnostic_reports` / `lab_orders` | `DiagnosticReport.id`, `status`, `code`, `subject`, `result[]`, `performer[]` | `CodeableConcept` | `1..1` | Yes | Aggregates verified `Observation` references with performing lab provenance. |
| **MedicationRequest** | `prescriptions`, `prescription_items` | `MedicationRequest.id`, `status`, `intent`, `medicationCodeableConcept`, `dosageInstruction` | `CodeableConcept` (`urn:zayvora:formulary`) | `1..*` | Yes | Unani polyherbal formulations retain classical name, dose, Anupan/Badal instructions; emits lossy warning if external biomedical code is absent. |
| **Condition** | `modern_clinical_problems` / `ipd_admissions.diagnosis` | `Condition.id`, `clinicalStatus`, `verificationStatus`, `code`, `subject` | `CodeableConcept` | `1..1` | Yes | Preserves clinician verification status (`confirmed`, `provisional`, `differential`). |
| **Composition** | `ipd_discharge_summaries` / `consultation_documents` | `Composition.id`, `status`, `type`, `subject`, `date`, `author[]`, `title`, `section[]` | `CodeableConcept` (`LOINC` document type) | `1..1` | Yes | Used as root entry of FHIR Document Bundles (`DischargeSummary`, `OPConsultation`, `Prescription`, `DiagnosticReport`). |
| **Provenance** | `audit_events` / signature metadata | `Provenance.id`, `target[]`, `recorded`, `agent[]`, `signature[]` | `Signature` (SHA-256 digest) | `1..1` | Yes | Attaches source system identity, mapping version (`MAP-FHIR-R4-2026.1`), and cryptographic SHA-256 signature digest. |

---

## 3. Unsupported Resources Behavior

Any request to validate, export, or import a FHIR resource type outside the declared supported set returns a deterministic `400 VALIDATION_ERROR` with error code `UNSUPPORTED_FHIR_RESOURCE_TYPE` and lists the supported resource types. No resource or clinical field is silently ignored.

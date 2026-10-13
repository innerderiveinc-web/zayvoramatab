# ABDM & FHIR R4 Standards Discovery Report — ZAYVORA MATAB OS (Phase 12)

- **Document Status:** Verified Technical Discovery & Architecture Baseline
- **Date:** 2026-10-13
- **Scope:** Prompt 12 — Hospital Workflows & Interoperability (IPD/ADT, Laboratory, Referrals, FHIR R4 & ABDM)
- **Official Normative References Consulted:**
  - Ayushman Bharat Digital Mission (ABDM) Official Portal (`https://abdm.gov.in/`) & Sandbox (`https://sandbox.abdm.gov.in/`)
  - National Health Authority (NHA) Health Data Management Policy (HDMP)
  - NRCeS (National Resource Centre for EHR Standards) FHIR R4 Implementation Guide for ABDM (v6.5.0 / FHIR R4.0.1)

---

## 1. ABDM Participant Roles Relevant to ZAYVORA MATAB OS

Under the ABDM architecture, ZAYVORA MATAB OS supports two primary functional roles when deployed at a registered clinic or hospital:
1. **Health Information Provider (HIP):** Generates and stores clinical records (OPD Consultation Records, Prescriptions, Diagnostic Lab Reports, Discharge Summaries) and makes them discoverable/shareable upon verified patient consent via the Health Information Exchange – Consent Manager (HIE-CM).
2. **Health Information User (HIU):** Requests access to a patient's historical clinical records from external HIPs only after obtaining explicit, time-bounded, purpose-specific patient consent through the HIE-CM.

---

## 2. Current Deployment Role & Honest Readiness Status

- **Target Role:** Dual HIP / HIU adapter architecture with HIP care-context linking and consent-verified FHIR R4 bundle packaging implemented first.
- **Current Readiness State in This Standalone Repository:**
  - **Internal Interoperability Gateway & FHIR R4 Validator/Mapper:** `FUNCTIONALLY_TESTED` (local deterministic persistence and validation).
  - **ABDM Contract-Accurate Adapter & Cryptographic/Consent State Machine:** `CONTRACT_TESTED_HARNESS` (tested against contract-accurate test harness with simulated HIE-CM callbacks, signature verification, consent artifact validation, expiry/revocation checks, and idempotency).
  - **External NHA ABDM Sandbox Connection:** `BLOCKED_BY_EXTERNAL_DEPENDENCY` (requires organization-specific NHA Sandbox client ID/secret, registered webhook callback domain, HFR facility ID, and HPR practitioner IDs).
  - **ABDM Certification / Production Connection:** `NOT_APPROVED` (no claim of NHA certification or live ABDM network connection is made).

---

## 3. Required FHIR Version, Implementation Guide & Profiles

- **Base Standard:** HL7 FHIR Release 4 (`4.0.1`).
- **India / ABDM Target Profiles:** NRCeS ABDM FHIR Implementation Guide (`v6.5.0`), which constrains FHIR R4 resources for Indian health data exchange:
  - `Bundle` (Document Bundle with `identifier`, `type = 'document'`, `timestamp`, `entry` starting with `Composition`)
  - `Composition` (Clinical Consultation Record, Prescription Record, DiagnosticReport Record, DischargeSummary Record)
  - `Patient` (with `identifier` coding for MRN / ABHA, `name`, `gender`, `birthDate`, `telecom`)
  - `Practitioner` (with `identifier` for HPR / State Council license)
  - `Organization` & `Location` (with `identifier` for HFR / local facility code)
  - `Encounter` (`class` coding `AMB` for OPD, `IMP` for IPD inpatient stay, `period`, `status`)
  - `Condition`, `Observation`, `DiagnosticReport`, `ServiceRequest`, `Specimen`
  - `MedicationRequest`, `MedicationDispense`, `AllergyIntolerance`, `CarePlan`, `DocumentReference`, `Provenance`

---

## 4. Supported Health Record Types (Health Information Types - HITypes)

In alignment with ABDM Health Information Types (`hiType`):
1. `OPConsultation` — Outpatient Consultation Summary (chief complaints, physical/Unani exam, assessment, care plan).
2. `Prescription` — Signed Nuskha / Medication Order bundle (`MedicationRequest` + `Organization` + `Practitioner` + `Patient`).
3. `DiagnosticReport` — Laboratory test results (`DiagnosticReport` + `Observation` + `Specimen` + `ServiceRequest`).
4. `DischargeSummary` — Signed Inpatient (IPD) Discharge Summary (`Composition` + `Encounter` + `Condition` + `MedicationRequest` + `CarePlan`).
5. `WellnessRecord` — Vital signs and longitudinal observations.

---

## 5. Sandbox Onboarding, Certification & Production Approval Steps

Before any live external transmission is enabled, the deploying healthcare organization must complete:
1. **NHA Sandbox Registration:** Obtain sandbox `clientId` and `clientSecret` and register callback URLs.
2. **Registry Onboarding:** Register facility in **Health Facility Registry (HFR)** and practitioners in **Healthcare Professionals Registry (HPR)**.
3. **Functional Milestone Verification (M1, M2, M3):**
   - **M1:** ABHA verification / creation workflow.
   - **M2:** HIP care-context linking and consent-based encrypted health record push.
   - **M3:** HIU consent request initiation and encrypted health record reception.
4. **Security Audit:** Pass CERT-In empanelled vendor vulnerability assessment and penetration testing (VAPT) and NHA functional audit before production gateway credentials are issued.

---

## 6. Consent Manager (HIE-CM) APIs & Callback Flows

All ABDM exchanges are asynchronous and callback-driven:
- **Care Context Linking:** `/v0.5/links/link/add-contexts` -> callback `/v0.5/links/link/on-add-contexts`
- **Consent Notification (HIP/HIU):** `/v0.5/consents/hip/notify` & `/v0.5/consents/hiu/notify` -> callback `/v0.5/consents/hip/on-notify`
- **Health Information Request (HIP):** `/v0.5/health-information/hip/request` -> callback `/v0.5/health-information/hip/on-request`
- **Every callback and outbound request** carries:
  - `requestId` (UUID v4)
  - `timestamp` (UTC ISO-8601)
  - `X-CM-ID` header identifying the target HIE-CM environment (e.g., `sbx` for sandbox)

---

## 7. Identity & Facility Registry Processes (ABHA, HPR, HFR)

- **ABHA (Ayushman Bharat Health Account):** Stored as a verified or unverified patient identifier in `patient_identifiers` (`identifier_type = 'ABHA'`). Presence of an ABHA ID **never** constitutes consent to fetch or transmit clinical data.
- **HFR (Health Facility Registry):** Mapped in `external_id_mappings` (`entity_type = 'FACILITY'`, `system_uri = 'https://facility.abdm.gov.in'`).
- **HPR (Healthcare Professionals Registry):** Mapped in `external_id_mappings` (`entity_type = 'PRACTITIONER'`, `system_uri = 'https://doctor.abdm.gov.in'`).

---

## 8. Cryptographic, Key Management & Callback Security Requirements

- **Credentials:** Gateway secrets must be referenced via `secret_ref_uri` (`vault://`, `kms://`, `env://`, `secret-mgr://`) and never stored in plaintext database rows or returned to UI clients.
- **Webhook / Callback Verification:** Inbound callbacks must verify HMAC-SHA256 / gateway signature headers and validate `requestId` idempotency to reject replay attacks.
- **Payload Encryption (Fidelius / ECDH Curve25519):** ABDM data transfer payloads require ephemeral Diffie-Hellman (Curve25519) key exchange and AES-GCM encryption when transmitting over the live HIE-CM data push URL.

---

## 9. Privacy, Consent, Revocation & Audit Requirements

- **Explicit Consent Artifact Required:** Every outbound or inbound external data exchange must reference an active `data_sharing_consents` record with:
  - `status = 'GRANTED'`
  - `valid_from <= now <= valid_until`
  - Requested resource category included in `allowed_hi_types_json` and `allowed_resource_types_json`
- **Immediate Revocation & Expiry:** When a consent artifact is marked `REVOKED` or `EXPIRED`, any subsequent export/share request using that consent artifact is immediately blocked (`CONSENT_REVOKED_OR_EXPIRED`).
- **Auditability:** Every validation, export, import, consent notification, and callback event is recorded in `audit_events` and `interop_jobs` with actor, correlation ID, consent ID, and outcome.

---

## 10. Out-of-Scope Capabilities (Explicitly Disabled)

- Live transmission of patient health information to external NHA servers (disabled until sandbox/production credentials and HFR/HPR onboarding are configured).
- Autonomous AI mapping of unverified clinical terms into SNOMED-CT/LOINC/ICD-10 codes.
- Full PACS DICOM image streaming or ICU ventilator telemetry streaming.
- Automated claim adjudication (NHCX Insurance Claims Exchange).

# Enterprise Interoperability Repository Audit — Phase 31

**Document ID:** AUDIT-P31-INTEROP-2026-01  
**Project:** ZAYVORA MATAB OS  
**Phase:** 31 — Enterprise Interoperability, FHIR APIs, ABDM Integration & External-System Data Exchange  
**Audit Date:** October 2026  
**Auditor:** Antigravity AI Pair Programmer & Clinical Systems Architect  
**Baseline Test Status:** 491 tests passing (100% clean baseline)

---

## 1. Executive Summary

This repository audit assesses the current interoperability, FHIR data exchange, terminology mapping, and Ayushman Bharat Digital Mission (ABDM) capabilities in ZAYVORA MATAB OS prior to the implementation of Prompt 31.

The platform previously established baseline hospital workflows, initial FHIR R4 serializers, and simulated ABDM test harnesses in **Prompt 12** (`HospitalInteropService` and Migration 012). However, enterprise-grade, legally compliant, and clinically safe healthcare data exchange demands strict adherence to official NRCeS Implementation Guides (`ndhm.in#6.5.0`), non-lossy Unani terminology governance, inbound record reconciliation to avoid silent overwrites, purpose- and scope-bound ABDM consent artefact gating, durable outbox delivery, and integration with the Prompt 29 cryptographic audit ledger.

---

## 2. Pre-Existing Interoperability Assets (Phase 12 Analysis)

### 2.1 Database Tables (Migration 012)
- `terminology_mappings`: Initial mapping between local codes and external systems (LOINC, SNOMED-CT). *Gap:* Lacks explicit mapping state taxonomy required by Prompt 31 (`exact_reviewed`, `broader_than`, `narrower_than`, `no_safe_mapping`), authoring attribution, and unmapped Unani concept protection.
- `external_id_mappings`: Basic storage for ABHA numbers, HFR IDs, and HPR tokens.
- `data_sharing_consents`: Coarse consent record. *Gap:* Lacks distinction between ABDM HIU consent requests and cryptographically signed consent artefacts; lacks hiType filtering down to granular resource instances.
- `interop_jobs`: Basic job queue. *Gap:* Lacks durable outbox semantics, chunked multi-page transfer tracking, and external acknowledgment verification.
- `abdm_exchange_traces`: Trace table for ABDM callbacks.

### 2.2 Service Implementation (`apps/api/domains/hospital_interop.py`)
- Provides `HospitalInteropService` covering inpatient ADT, bed management, lab orders, and baseline FHIR bundle generation.
- Supports core profiles: `Patient`, `Practitioner`, `Encounter`, `Condition`, `Observation`, `MedicationRequest`, `DiagnosticReport`, `Composition`, `Bundle`.
- *Architecture Decision:* Maintain `HospitalInteropService` for inpatient operations and clinical charting, while establishing a dedicated enterprise domain engine `EnterpriseInteroperabilityEngine` in `apps/api/domains/interoperability.py` backed by Migration 030 (`030_enterprise_interoperability_fhir_abdm_data_exchange_schema.sql`) to govern external connectors, specification registry, terminology mappings, ABDM M1-M4 workflows, inbound clinician reconciliation queues, and tamper-evident ledger logging.

---

## 3. Detailed Gap Analysis & Prompt 31 Mandates

### 3.1 Pinned Specification Registry (`ndhm.in#6.5.0`)
- **Requirement:** Maintain a deterministic specification registry that pins:
  - HL7 FHIR Release 4.0.1 (Specification URI: `http://hl7.org/fhir/R4`)
  - NRCeS ABDM FHIR Implementation Guide `ndhm.in#6.5.0` (Package URL: `https://nrces.in/ndhm/fhir/r4`)
  - LOINC version `2.76`
  - SNOMED CT version `2024-03`
  - UCUM version `2.1`
- **Mitigation:** Table `interop_specification_registry` tracking specification canonical URI, package ID, semantic version, publication date, SHA-256 package hash, and validation status (`active`, `superseded`, `deprecated`).

### 3.2 Unani Concept Terminology Preservation & Meaning Defense
- **Requirement:** Classical Unani concepts (Mizaj, Akhlat, Nabz, Baul, Baraz, Nuskha formulations, Tadbeer regimens) must **NEVER** be coerced into lossy modern SNOMED/ICD codes without verified clinical review.
- **Mapping States:**
  - `exact_reviewed`: True clinical equivalence certified by a senior Unani-modern expert panel.
  - `broader_than`: Modern code represents a broader category (lossy specialization).
  - `narrower_than`: Modern code represents a narrower condition (partial fit).
  - `no_safe_mapping`: Default for classical concepts (e.g. *Damawi Mizaj*, *Su-e-Mizaj Maddi*, *Munzij-Mushil therapy*). The FHIR representation MUST preserve the canonical Unani concept, local script, and transliterated display without misleading standard code binding.
- **Mitigation:** Table `interop_terminology_mappings` and validator rejecting unreviewed lossy coercion.

### 3.3 ABDM Integration Architecture (M1, M2, M3, M4)
- **M1 (Identity):** ABHA address (`<user>@abdm`), ABHA number (`14-digit`), mobile OTP verification, KYC status, and linked local patient record.
- **M2 (HIP - Health Information Provider):** Care-context discovery without PHI leakage in display strings; secure Diffie-Hellman encryption / transfer; notification callbacks.
- **M3 (HIU - Health Information User):** Structured consent request generation; consent artefact status polling/notification; granular data fetch bound strictly to granted date ranges and HI types. Immediate blocking upon revocation.
- **M4 (Registries):** Health Facility Registry (HFR) and Healthcare Professional Registry (HPR) verification.

### 3.4 Inbound Record Ingestion & Clinician Reconciliation Queue
- **Requirement:** External records received via FHIR or ABDM must **NEVER** silently overwrite local clinical charts, active problem lists, or current prescriptions.
- **Mitigation:** Table `inbound_record_reconciliations` staging incoming bundles in an isolated queue with source provenance (`source_system`, `source_actor`, `retrieval_consent_id`). A clinician must review each incoming item and choose `ACCEPT_INTO_RECORD`, `REJECT_INCOMPATIBLE`, `FLAG_CONTRADICTION`, or `FILE_AS_EXTERNAL_ATTACHMENT`.

### 3.5 Durable Outbox & Replay-Safe Webhook Dispatch
- **Requirement:** Reliable delivery to external health networks with exponential backoff, SHA-256 payload checksums, idempotency keys, and replay attack prevention (timestamp freshness $\le 300$s and nonce tracking).
- **Mitigation:** Table `interop_transfer_outbox` and `interop_webhook_verifications`.

### 3.6 Cryptographic Audit Ledger Integration (Prompt 29)
- **Requirement:** Every interoperability export, ABDM consent exchange, inbound record reception, and clinician reconciliation decision must emit structured audit events to `ClinicalAuditLedgerEngine` ($H_i = \text{SHA-256}(C_i \parallel H_{i-1})$) using Prompt 29's valid result states: `blocked`, `denied`, `failed`, `partial`, `succeeded`, `unknown`.

---

## 4. Implementation Strategy

1. **Specification Register Document:** Author `docs/interop/INTEROPERABILITY_SPECIFICATION_REGISTER.md` defining all pinned profiles and mapping policies.
2. **Schema Migration 030:** Create `030_enterprise_interoperability_fhir_abdm_data_exchange_schema.sql` with 7 dedicated tables.
3. **Domain Engine:** Create `EnterpriseInteroperabilityEngine` in `apps/api/domains/interoperability.py`.
4. **Permissions:** Add `interop:read`, `interop:write`, `interop:admin`, `interop:reconcile` in `apps/api/core/permissions.py`.
5. **REST API Endpoints:** Create `apps/api/routes/interoperability.py` with 16 endpoints.
6. **Frontend UI:** Integrate Interoperability Console in `apps/web/static/js/views/knowledge_admin.js`.
7. **Architectural Decision Record:** Author `docs/adr/ADR-050-enterprise-interoperability-fhir-and-abdm-data-exchange.md`.
8. **Testing & Verification:** Comprehensive unit and integration test suites validating zero regressions.

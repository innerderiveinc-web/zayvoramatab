# Feature & Engine Capability Registry — ZAYVORA MATAB OS

**Version:** 1.1  
**Lifecycle States:**
1. `NOT_IMPLEMENTED`
2. `IMPLEMENTED_NOT_CONNECTED`
3. `CONNECTED_NOT_VALIDATED`
4. `FUNCTIONALLY_TESTED`
5. `CLINICALLY_REVIEWED`
6. `PILOT_APPROVED`
7. `PRODUCTION_APPROVED`
8. `DISABLED_OR_DEGRADED`

---

## Current Subsystem Status Matrix

| Engine / Capability | Capability ID | Current State | Evidence & Verification Notes |
|---|---|---|---|
| **Identity & Authentication** | `core.identity` | `FUNCTIONALLY_TESTED` | Session management, password hashing, and role verification tested. |
| **Tenant & Facility Isolation** | `core.tenancy` | `FUNCTIONALLY_TESTED` | Strict organization & facility query filtering verified in multi-tenant tests. |
| **Tamper-Evident Audit Logging** | `core.audit` | `FUNCTIONALLY_TESTED` | Chained SHA-256 tamper-evident log tested for break detection. |
| **Patient Index & Duplicate Detection** | `clinical.patients` | `FUNCTIONALLY_TESTED` | Patient registration, duplicate heuristics, and Patient 360 tested. |
| **Encounter State Machine & Vitals** | `clinical.encounters`| `FUNCTIONALLY_TESTED` | OPD queue, encounter transitions, vitals, and clinical notes tested. |
| **Unani Mizaj & Ajnas Scoring** | `unani.assessment` | `FUNCTIONALLY_TESTED` | Classical 4-temperament scoring & qualitative checks validated in engine tests. |
| **Modern Clinical Support & Red Flags** | `clinical.support` | `FUNCTIONALLY_TESTED` | Deterministic red flag triage rules and ICD candidate suggestions tested. |
| **Usul-e-Ilaj Care Planning** | `clinical.care_plan` | `FUNCTIONALLY_TESTED` | Ghiza (diet) and Tadbeer (regimen) care plan builder verified. |
| **Nuskha Formulation Compiler** | `prescriptions.nuskha`| `FUNCTIONALLY_TESTED` | Multi-item compounding, unit conversion, and posology checks tested. |
| **Deterministic Safety Preflight** | `prescriptions.safety`| `FUNCTIONALLY_TESTED` | Allergy, dose limit, duplicate ingredient, and fail-closed checks verified. |
| **Immutable Electronic Signing** | `prescriptions.sign` | `FUNCTIONALLY_TESTED` | Practitioner PIN challenge, SHA-256 fingerprinting, and versioning tested. |
| **Printable Prescription View** | `prescriptions.print`| `FUNCTIONALLY_TESTED` | Verified prescription layout and patient instructions tested. |
| **Clinic Appointments & Follow-ups** | `operations.followup`| `FUNCTIONALLY_TESTED` | Follow-up scheduling and due queue tested. |
| **Dispensary Batch FEFO Inventory** | `operations.inventory`| `FUNCTIONALLY_TESTED` | First-Expired-First-Out batch tracking and Mudabbar check tested. |
| **FHIR / ABDM Adapter Connectors** | `integration.abdm` | `CONNECTED_NOT_VALIDATED`| Optional stub adapter present, disabled by default per ADR-001. |
| **Autonomous AI Scribe / LLM** | `ai.scribe` | `NOT_IMPLEMENTED` | Excluded from primary safety path; Socratic guidance remains advisory. |
| **Hospital IPD / Inpatient Nursing**| `hospital.ipd` | `NOT_IMPLEMENTED` | Explicitly marked not enabled for initial Matab/Clinic release. |

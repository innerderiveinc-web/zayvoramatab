# Test Strategy & Quality Assurance Architecture — ZAYVORA MATAB OS

**Version:** 1.1  
**Principle:** 100% Deterministic, Reproducible, Zero-Mock Verification on Live Database Engine.

---

## 1. Test Pyramid & Execution Tiers

```
               ┌──────────────────────┐
               │  End-to-End Clinical │  (Full Consultation -> Preflight -> Sign)
               │      Scenarios       │
               ├──────────────────────┤
               │   API Integration    │  (REST endpoints, RBAC, Tenancy, Errors)
               ├──────────────────────┤
               │ Domain Engine Units  │  (Mizaj Math, Safety Preflight, Chained Audit)
               └──────────────────────┘
```

### Tier 1: Domain Engine Unit Tests
- **Unani Mizaj Scoring:** Test qualitative and questionnaire scoring for pure and compound temperaments (*Damwi*, *Balghami*, *Safrawi*, *Saudawi*, *Motadil*).
- **Safety Preflight Rules:**
  - Duplicate ingredient detection across distinct compound formulations (e.g. *Filfil Siyah* present in multiple *Jawarish* / *Majoon* formulas).
  - Maximum daily dose threshold violations (triggers `BLOCK`).
  - Known allergen matches (e.g., *Roghan Badam* for nut allergy triggers `BLOCK`).
  - Schedule E(1) hazardous botanicals without Mudabbar certification (triggers `BLOCK`).
  - Pregnancy / Lactation contraindications (e.g., *Abhal / Juniperus* triggers `BLOCK` in pregnancy).
  - Missing interaction data (triggers fail-closed `UNKNOWN`).
- **Audit Log Chaining:** Test cryptographic SHA-256 chain verification and tamper detection.

### Tier 2: Multi-Tenant & RBAC Security Tests
- Enforce that queries with `facility_A` cannot read or mutate patients or encounters belonging to `facility_B`.
- Enforce that a `RECEPTIONIST` session calling `/api/v1/prescriptions/{id}/sign` receives HTTP 403 Forbidden.
- Enforce session invalidation upon logout.

### Tier 3: End-to-End Clinical Workflows
- Register new patient with duplicate checks -> Issue OPD token -> Enter vitals & notes -> Assess Mizaj -> Build Nuskha -> Run preflight -> Clinician electronic signature -> Verify immutable record and generated print layout.

---

## 2. Test Execution Command

Run the complete test suite directly with standard Python unittest:
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
All test datasets must be strictly synthetic and marked as `[SYNTHETIC TEST RECORD]`.

# Release Blocker Register — ZAYVORA MATAB OS

**Version:** 1.1  
**Purpose:** Formal register of non-negotiable release gates. If any gate fails, build promotion to `PILOT_APPROVED` or `PRODUCTION_APPROVED` is strictly blocked.

---

## 1. Safety & Clinical Integrity Blockers

| Gate ID | Description | Verification Criterion | Status |
|---|---|---|---|
| **RB-01** | **Deterministic Preflight Block** | Formulations containing lethal overdose or absolute pregnancy contraindication must produce `BLOCK` and prevent electronic signature. | **VERIFIED IN TESTS** |
| **RB-02** | **Fail-Closed Unknown Policy** | Where critical safety rule data is missing or corrupted, the system must not report `PASS`; it must report `UNKNOWN` and block default signing. | **VERIFIED IN TESTS** |
| **RB-03** | **No AI Autonomous Prescribing** | Scribe or AI suggestions must remain advisory; only human credentials with valid practitioner IDs can sign. | **VERIFIED IN CODE & RBAC** |
| **RB-04** | **Immutable Prescription History** | Signed prescriptions must never be overwritten in-place. Amendments must create linked versions (`v2`, `v3`). | **VERIFIED IN TESTS** |
| **RB-05** | **No Silent Mock Fallbacks** | Production builds must never silently fallback to simulated data if database or safety rules fail. | **ENFORCED ARCHITECTURALLY** |

---

## 2. Security & Operational Blockers

| Gate ID | Description | Verification Criterion | Status |
|---|---|---|---|
| **RB-06** | **Cross-Tenant Data Isolation** | Requests from Facility A must be strictly barred from accessing records of Facility B. | **VERIFIED IN TESTS** |
| **RB-07** | **Tamper-Evident Audit Chaining** | Any manual tampering or alteration of historical audit log records must break SHA-256 chain verification. | **VERIFIED IN TESTS** |
| **RB-08** | **Zero Runtime Dependency on Legacy OS** | MATAB OS must start, migrate, seed, and complete clinical encounters without any legacy service online. | **VERIFIED IN STANDALONE ENGINE** |
| **RB-09** | **Deterministic Database Migrations** | Schema migrations must execute idempotently and support clean rollback/recovery. | **VERIFIED IN ENGINE** |
| **RB-10** | **Synthetic Data Clear Labeling** | All demo or seed patients must carry explicit `[SYNTHETIC TEST RECORD]` banners to prevent confusion with real patient records. | **ENFORCED IN SEED FIXTURES** |

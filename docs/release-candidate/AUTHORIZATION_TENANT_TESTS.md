# ZAYVORA MATAB OS — Authorization and Tenant Isolation Audit (Prompt 16)
## Multi-Tenancy Boundary Enforcement, Negative Security Testing & RBAC Verification

This document details the multi-tenant isolation and role-based access control (RBAC) negative test results across organizations, facilities, and clinical roles.

---

## 1. Multi-Tenant Isolation Architecture
ZAYVORA MATAB OS enforces database-level and query-level tenant scoping:
- Every query touching clinical, financial, or administrative entities includes `WHERE organization_id = ?` derived strictly from the authenticated JWT session (`req["user"]["organization_id"]`).
- Client-supplied `organization_id` parameters in request bodies or query strings are ignored in favor of the cryptographically signed JWT payload.
- Cross-tenant object ID substitution (IDOR) fails closed: if Tenant A attempts to fetch an entity belonging to Tenant B, the server responds with `HTTP 404 Not Found` (to prevent identifier probing) or `HTTP 403 Forbidden`.

---

## 2. Negative Authorization Test Matrix

| Test Case ID | Attack Vector / Negative Scenario | Targeted API Endpoint | Role Under Test | Expected Response | Observed Response | Status |
| :---: | :--- | :--- | :--- | :---: | :---: | :---: |
| **SEC-001** | Cross-tenant patient record access | `GET /api/v1/patients/{tenant_b_patient_id}` | Tenant A Doctor | `HTTP 404 Not Found` | `HTTP 404 Not Found` | **PASS** |
| **SEC-002** | Cross-tenant prescription signing attempt | `POST /api/v1/prescriptions/{tenant_b_rx_id}/sign` | Tenant A Doctor | `HTTP 404 Not Found` | `HTTP 404 Not Found` | **PASS** |
| **SEC-003** | Cross-tenant encounter access | `GET /api/v1/encounters/{tenant_b_enc_id}` | Tenant A Nurse | `HTTP 404 Not Found` | `HTTP 404 Not Found` | **PASS** |
| **SEC-004** | Cross-tenant inventory batch deduction | `POST /api/v1/clinic/inventory/batches/{tenant_b_batch_id}/adjust` | Tenant A Pharmacist | `HTTP 404 Not Found` | `HTTP 404 Not Found` | **PASS** |
| **SEC-005** | Unauthorized role: Nurse signing prescription | `POST /api/v1/prescriptions/{id}/sign` | Clinical Nurse | `HTTP 403 Forbidden` (`Missing permission: prescription:sign`) | `HTTP 403 Forbidden` | **PASS** |
| **SEC-006** | Unauthorized role: Receptionist modifying clinical assessment | `PUT /api/v1/unani/assessments/{id}` | Receptionist | `HTTP 403 Forbidden` (`Missing permission: clinical:write`) | `HTTP 403 Forbidden` | **PASS** |
| **SEC-007** | Invalid digital signature PIN during sign-off | `POST /api/v1/prescriptions/{id}/sign` | Prescribing Doctor | `HTTP 401 Unauthorized` (`Invalid PIN`) | `HTTP 401 Unauthorized` | **PASS** |
| **SEC-008** | Client spoofing `status: SIGNED` on prescription update | `PUT /api/v1/prescriptions/{id}` | Malicious Client | Server ignores status, stays `DRAFT` | Status remains `DRAFT` | **PASS** |
| **SEC-009** | Attempting to sign empty prescription (0 items) | `POST /api/v1/prescriptions/{id}/sign` | Prescribing Doctor | `HTTP 400 Bad Request` (`Zero items`) | `HTTP 400 Bad Request` | **PASS** |
| **SEC-010** | Attempting to dispense unsigned prescription draft | `POST /api/v1/clinic/dispensary/dispense` | Pharmacist | `HTTP 409 Conflict` (`Only SIGNED rx can be dispensed`) | `HTTP 409 Conflict` | **PASS** |
| **SEC-011** | Cross-tenant audit event log exfiltration | `GET /api/v1/audit/events` | Tenant A Admin | Returns only Tenant A audit rows | Only Tenant A logs returned | **PASS** |
| **SEC-012** | Deactivated user attempting API login | `POST /api/v1/auth/login` | Deactivated Staff | `HTTP 401 Unauthorized` (`Account inactive`) | `HTTP 401 Unauthorized` | **PASS** |

---

## 3. Automated Test Execution Evidence
- **Suites:** `tests/integration/test_tenancy_isolation.py`, `tests/integration/test_patient_tenancy_security.py`, `tests/integration/test_unani_tenancy_security.py`, `tests/unit/test_security_rbac.py`
- **Command:** `python3 -m unittest tests/integration/test_tenancy_isolation.py tests/integration/test_patient_tenancy_security.py tests/integration/test_unani_tenancy_security.py tests/unit/test_security_rbac.py`
- **Output:**
  ```
  Ran 19 tests in 0.984s
  OK
  ```
- **Conclusion:** Tenancy isolation and RBAC security boundaries are enforced strictly in SQL queries and domain logic. Fail-closed security invariants remain intact across all tested scenarios.

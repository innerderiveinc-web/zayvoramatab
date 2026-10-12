# Threat Model & Security Posture — Phase 1 Foundation

**Evaluation Framework:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)  
**System Scope:** Authentication, Multi-Tenant Boundaries, Role Scoping, Audit Logging, and Rate Limiting.  

---

## 1. STRIDE Analysis & Enforced Mitigations

| Threat ID | Threat Vector | Primary Impact | Phase 1 Enforced Mitigation |
|---|---|---|---|
| **STRIDE-01** | **Spoofing (Credential Brute-Force)** | Unauthorized account takeover. | Rate limiting on `/api/v1/auth/login` (max 5 failed attempts per IP window); PBKDF2/SHA-256 password hashing with individual salt; generic authentication error messages that do not reveal user existence. |
| **STRIDE-02** | **Tampering (Tenant ID Injection)** | Malicious user injects foreign `organization_id` or `facility_id` in request payloads or query params. | **Deny-by-default server-side tenancy:** The API ignores user-submitted organization IDs and verifies facility membership against the authenticated session server-side. |
| **STRIDE-03** | **Repudiation (Unlogged Actions)** | Privileged administrator denies modifying user roles or disabling a practitioner. | **Append-only Audit Trail:** Every authentication, permission change, and membership mutation is permanently recorded in `audit_events` with actor ID, UTC timestamp, request ID, and outcome. |
| **STRIDE-04** | **Info Disclosure (Secrets in Errors/Logs)** | Stack traces or database credentials leaked in API responses. | Standardized RFC 7807 error format with sanitized messages; sensitive fields (`password`, `token`, `secret`) are scrubbed before audit logging; production startup fails if default secrets are detected. |
| **STRIDE-05** | **Denial of Service (Unauthenticated Flooding)** | Resource exhaustion via public endpoints. | Liveness `/api/v1/health/live` performs minimal memory checks; unauthenticated routes are rate-limited; request payload size limits (<64KB) are enforced. |
| **STRIDE-06** | **Elevation of Privilege (Role Bypass)** | Receptionist calls `/api/v1/users` or alters facility memberships. | Role-Based Access Control (RBAC) enforced on the server for all routes; missing permissions result in HTTP 403 Forbidden. |
| **STRIDE-07** | **Info Disclosure (Patient Enumeration via Search)** | Attacker enumerates existing patients by querying phone/name substrings. | Patient search strictly scopes by `organization_id`; requires `patient:read` permission; returns paginated results; direct foreign IDOR lookups return 404 NOT_FOUND instead of 403 to prevent existence discovery. |
| **STRIDE-08** | **Tampering (Concurrent Demographic Overwrite)** | Two staff members simultaneously edit patient records, causing dirty writes / lost updates. | Optimistic concurrency control via `version` column. Every demographic and encounter draft update requires matching version; mismatched version fails with HTTP 409 Conflict. |
| **STRIDE-09** | **Elevation of Privilege (Unauthorized Duplicate Merging)** | Operator merges patient records without supervisory verification, polluting clinical history. | Automatic data merging is strictly disabled in code. Resolving duplicates is restricted to human operator review (`CONFIRMED_DIFFERENT` or `DEFERRED`) with required reasoning and audit event. |
| **STRIDE-10** | **Info Disclosure (Clinical Narrative Leakage)** | Administrative/front-desk staff accessing timeline view see clinical notes and sensitive diagnoses. | Longitudinal timeline queries dynamically redact `reason_for_visit` and clinical notes based on requesting user role; only `PRACTITIONER`, `ORG_ADMIN`, and `CLINIC_ADMIN` receive clinical narrative fields. |

---

## 2. Multi-Tenant Negative Testing Invariants

- A user belonging to `org-alpha` MUST receive HTTP 403 or 404 when querying entities belonging to `org-beta`.
- Supplying `organization_id=org-beta` in a request header or query parameter MUST NOT override the session's authenticated organization boundary.
- All database queries must include explicit parameterized filters on `organization_id` and `facility_id`.
- Foreign tenant lookups for patient records or encounters MUST return HTTP 404 NOT_FOUND to prevent cross-tenant enumeration.
- Concurrent updates to patients or encounters with stale versions MUST return HTTP 409 Conflict.

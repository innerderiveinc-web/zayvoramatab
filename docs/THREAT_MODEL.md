# Threat Model & Security Posture — ZAYVORA MATAB OS

**Methodology:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)  
**Scope:** MATAB OS Standalone Runtime, Clinic Server, Web Client, Local SQLite/PostgreSQL Database, Audit Logging, and Prescription Engine.  

---

## 1. Asset Inventory & Trust Boundaries

### 1.1 Critical Assets
1. **Protected Health Information (PHI):** Patient identity, mobile numbers, Aadhaar/ABHA identifiers, clinical notes, Unani temperament assessments, vitals, and diagnosis records.
2. **Medical Orders (Prescriptions):** Formulation items, ingredient dosages, routes, frequencies, clinician electronic signatures, and dispensation records.
3. **Clinical Safety Rules & Formulary:** Ingredient dosage limits, contraindication registries, toxic botanical Mudabbar rules, and herb-drug interaction tables.
4. **Audit Trail:** Append-only log of clinician actions, authentication events, prescription signings, and data accesses.

### 1.2 Trust Boundaries
- **TB-1: Client Browser / PWA <---> MATAB OS Gateway (HTTP/REST):** Untrusted network boundary. Must enforce TLS 1.3, strict CORS, HTTP-only SameSite cookies or bearer tokens.
- **TB-2: Gateway / Auth Service <---> Domain Services:** Internal application process boundary. Enforces role-based access control (RBAC) and facility/tenant isolation.
- **TB-3: Domain Services <---> Persistence Layer (SQLite/Postgres):** Data boundary. Enforces parameterized queries, foreign key integrity, and encryption-at-rest.
- **TB-4: Clinical Engines <---> External Adapters (FHIR/ABDM/SMS):** External perimeter. Disabled by default; egress requires explicit credentialing, rate limiting, and timeout circuit-breakers.

---

## 2. STRIDE Threat Analysis & Mitigations

| Threat ID | Category | Threat Scenario | Impact | Mitigation in MATAB OS |
|---|---|---|---|---|
| **TH-01** | **Spoofing** | Unauthorized user assumes identity of an authorized Hakeem to sign prescriptions. | Critical: Fraudulent prescriptions, patient harm. | Strong credential hashing (PBKDF2/Argon2id), session invalidation on logout, optional re-authentication / PIN challenge before signing. |
| **TH-02** | **Tampering** | Clinic staff alters signed prescription dosage to conceal a dispensing error. | Critical: Patient toxicity, loss of legal validity. | Prescriptions are immutable upon signature. Any amendment creates a new version (`v2`). Cryptographic SHA-256 fingerprint generated at signature time and verified on retrieval. |
| **TH-03** | **Repudiation** | Clinician denies signing a contraindicated formulation following an adverse event. | High: Legal dispute, regulatory non-compliance. | Append-only audit log records actor ID, practitioner license, timestamp, client IP, payload SHA-256 hash, and preflight outcome. Audit log uses tamper-evident chained hashing. |
| **TH-04** | **Info Disclosure** | Receptionist views confidential clinical notes or HIV/psychiatric history across facilities. | High: PHI breach, privacy violation. | Granular role-based scoping (`receptionist` role can only see appointment queue and basic demographics; clinical notes restricted to `hakeem` and authorized care team). |
| **TH-05** | **Info Disclosure** | Cross-tenant data leakage in multi-facility clinic setups. | Critical: Cross-clinic privacy violation. | Every database query scopes strictly by `organization_id` and `facility_id`. Automated multi-tenant isolation unit tests run in CI. |
| **TH-06** | **Denial of Service** | Malformed Nuskha payload with circular ingredient references exhausts server CPU. | Medium: OPD queue disruption. | Strict input validation, recursion depth limits on formulation trees, payload size caps (<64KB for JSON requests), request timeouts (5000ms). |
| **TH-07** | **Elevation of Priv.** | Authenticated receptionist invokes `/api/v1/prescriptions/{id}/sign` via API injection. | Critical: Unauthorized medical practice. | Strict server-side RBAC on all mutation endpoints. Role is verified from the cryptographically verified session token, ignoring client-submitted role fields. |
| **TH-08** | **Safety Bypass** | Safety engine failure causes prescription to be signed despite fatal toxic dose. | Catastrophic: Lethal overdose. | **Fail-Closed Policy:** If the safety preflight service is unreachable or encounters an uncaught exception, the signature endpoint aborts with HTTP 503 and prohibits signing. `BLOCK` status strictly halts finalization. |

---

## 3. Data Protection & Privacy Controls

1. **No Silent Mock Fallbacks:** In live operational mode, failure of any clinical backend must display clear `UNAVAILABLE` or `REVIEW REQUIRED` indicators. The system will never silently substitute simulated patient data or synthetic approvals.
2. **Data Minimization in Logs:** Audit and server application logs explicitly scrub patient names, phone numbers, and full clinical note bodies. Log entries record opaque IDs (`patient_id`, `encounter_id`, `actor_id`).
3. **Tamper-Evident Audit Chaining:** Every audit record incorporates a SHA-256 hash of `(previous_hash + timestamp + actor_id + action + resource_id + payload_digest)`. Any retroactive modification breaks the hash chain and triggers an alert.

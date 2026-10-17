# API & Integration Certification, Contract Testing & Developer Governance Specification
## ZAYVORA MATAB OS — Enterprise Developer Platform & Integration Architecture (Phase 52)

### 1. Architectural Mandate & Non-Negotiables
1. **Zero Unverified Production Claims:** An integration is certified for production only when its contract, authorization, idempotency, webhook signatures, and live/sandbox evidence have been rigorously verified.
2. **Explicit 6-Tier Evidence Levels:**
   - `CONTRACT_DEFINED`: OpenAPI / JSON schema formally specified.
   - `MOCK_TESTED`: Tested against local unit/integration test double.
   - `CONTRACT_TESTED`: Automated validation of payloads against JSON schema.
   - `SANDBOX_VERIFIED`: Confirmed against external staging or sandbox environment.
   - `PRODUCTION_SMOKE_VERIFIED`: Verified in live environment via low-risk non-intrusive probe.
   - `UNVERIFIED`: Integration registered or configured without empirical proof.
3. **Fail-Closed Boundary Hardening:** Every endpoint enforces server-side authentication, tenant boundary checks, and role/scope authorization.
4. **Strict Server-Side Idempotency:** State-mutating operations require an `Idempotency-Key`. Identical requests return cached responses; payload mutations using the same key trigger `HTTP 409 Conflict`.
5. **Inbound Webhook Verification:** Constant-time cryptographic HMAC verification, replay deduplication, and timestamp freshness validation ($\le 300\text{s}$).
6. **Outbound SSRF Shield:** Strict validation of destination hosts against private, loopback, and link-local IP blocks prior to dispatch.
7. **Tamper-Evident SHA-256 Chained Governance Ledger:** Immutable audit trail linking key lifecycles, webhook deliveries, and certification audits.

---

### 2. Enterprise Integrations Catalog

| Integration ID | System / Provider Name | Direction | Category | Auth Method | Data Classification | Rate Limit | Current Certification Level |
|---|---|---|---|---|---|---|---|
| `INT-CORE-CLINICAL` | Core Matab Clinical OS API | BIDIRECTIONAL | `INTERNAL_SERVICE` | `BEARER_JWT` | `RESTRICTED_PHI` | 1200 RPM | **CONTRACT_TESTED** |
| `INT-INTERNAL-CDS` | Clinical Decision Support Orchestrator | INBOUND | `CLINICAL_CDS` | `BEARER_JWT` | `RESTRICTED_PHI` | 300 RPM | **CONTRACT_TESTED** |
| `INT-FHIR-R4` | HL7 FHIR R4 Bundle Exchange | BIDIRECTIONAL | `STANDARDS_FHIR` | `MUTUAL_TLS` | `RESTRICTED_PHI` | 300 RPM | **CONTRACT_TESTED** |
| `INT-ABDM-GW` | National Health Authority ABDM M1/M2/M3 | BIDIRECTIONAL | `NATIONAL_INTEROP_ABDM` | `BEARER_JWT` | `RESTRICTED_PHI` | 120 RPM | **MOCK_TESTED** |
| `INT-TWILIO-SMS` | Twilio SMS & Patient Notification | OUTBOUND | `COMMUNICATIONS_SMS` | `API_KEY` | `INTERNAL_OPERATIONAL` | 240 RPM | **MOCK_TESTED** |
| `INT-RAZORPAY-PAY` | Razorpay Payments & Billing | BIDIRECTIONAL | `PAYMENTS_GATEWAY` | `HMAC_SIGNATURE` | `CONFIDENTIAL_FINANCIAL` | 180 RPM | **MOCK_TESTED** |
| `INT-OUTBOUND-WH` | Tenant Outbound Clinical Events | OUTBOUND | `CLINICAL_EVENT_OUTBOUND` | `HMAC_SIGNATURE` | `RESTRICTED_PHI` | 120 RPM | **CONTRACT_TESTED** |

---

### 3. Developer API Keys & Credential Management
- **Token Generation Format:**
  - Sandbox: `ak_test_<48-hex-chars>`
  - Production: `ak_live_<48-hex-chars>`
- **Storage Policy:**
  - Raw tokens are returned to the developer strictly once upon creation.
  - Server persists only `SHA-256(raw_key)`.
  - Keys can be scoped to specific permissions (`api:read`, `encounters:read`, etc.), bounded by rate limits, and restricted to client IP CIDRs.

---

### 4. Idempotency & Distributed Failure Recovery
- **Request Header:** `Idempotency-Key: <unique-uuid-or-client-token>`
- **Storage Table:** `api_idempotency_store` (keyed by `tenant_id`, `idempotency_key`, `endpoint_path`).
- **Conflict Handling:**
  - If a key is presented with an identical SHA-256 payload hash: returns cached `status_code` and JSON body.
  - If a key is presented with a mismatched payload hash: returns `HTTP 409 Conflict` (`IDEMPOTENCY_PAYLOAD_MISMATCH`).

---

### 5. Webhook Security Architecture

#### Inbound Webhooks
1. **Twilio SMS / Voice:**
   - Header: `X-Twilio-Signature`
   - Verification: HMAC-SHA1 over sorted POST parameters and request URL.
2. **Razorpay Payments:**
   - Header: `X-Razorpay-Signature`
   - Verification: HMAC-SHA256 over raw request body.
3. **Generic Inbound Webhooks:**
   - Header: `X-Webhook-Signature` (`t=timestamp,v1=signature`)
   - Tolerance: Skew between `t` and current epoch must be $\le 300\text{ seconds}$.
   - Deduplication: `api_inbound_webhook_receipts` enforces unique `(provider, event_id)` constraint.

#### Outbound Webhooks & SSRF Shield
Before dispatching any HTTP POST to a tenant-configured webhook URL:
1. Destination scheme must be `https://` (or `http://` only if `allow_test_local=True`).
2. Destination hostname must resolve to valid public IPv4/IPv6 addresses.
3. Destination addresses are verified against the private address blacklist:
   - `127.0.0.0/8` (Loopback)
   - `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (RFC 1918 Private)
   - `169.254.0.0/16` (Cloud Metadata / Link Local)
   - `0.0.0.0/8`, `::1/128`, `fc00::/7`, `fe80::/10`
4. Requests resolving to blacklisted IPs are immediately aborted with `SSRF_BLOCKED` and logged as dead-lettered.

---

### 6. Cryptographic Audit Ledger
All developer actions and integration certifications are recorded into `api_developer_governance_ledger`:
$$\text{record\_hash} = \text{SHA256}(\text{prev\_hash} \parallel \text{ledger\_id} \parallel \text{event\_type} \parallel \text{payload\_json} \parallel \text{created\_at})$$
Chain verification iterates from the genesis block (`0000...0000`), validating that no historical records, key generations, or certifications have been manipulated.

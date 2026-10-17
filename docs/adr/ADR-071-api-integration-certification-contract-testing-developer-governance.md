# ADR-071: API & Integration Certification, Contract Testing & Developer Governance Engine

## Status
**ACCEPTED** (Prompt 52 / Phase 52)

## Date
2026-10-15

## Context & Problem Statement
ZAYVORA MATAB OS integrates clinical workflows, internal microservices (CDS Orchestrator, KAVS Knowledge Engine), and external partners (National ABDM Gateway M1/M2/M3, HL7 FHIR R4 Bundle Exchange, Twilio SMS/WhatsApp, Razorpay payment webhooks, and tenant clinical event webhooks). Prior to Phase 52, while integration queues and retry policies existed in Phase 32 (`integration_ops`), there was no unified contract-first governance engine, developer API key lifecycle, standardized idempotency cache, strict SSRF shield for outbound webhooks, or multi-level evidence-based integration certification framework.

A structured developer governance engine is required to ensure:
1. Zero unvetted or mocked integrations are falsely labeled production-ready.
2. Explicit differentiation of evidence levels (`CONTRACT_DEFINED`, `MOCK_TESTED`, `CONTRACT_TESTED`, `SANDBOX_VERIFIED`, `PRODUCTION_SMOKE_VERIFIED`, `UNVERIFIED`).
3. Strict boundary hardening: server-side authorization on every endpoint, tenant isolation, and fail-closed handling.
4. Server-side idempotency protection preventing double-billing, duplicate consultations, or re-dispensing of medications.
5. Inbound webhook verification using provider-specific HMAC signatures (Razorpay SHA-256, Twilio SHA-1) with timestamp freshness checks ($\le 300\text{s}$) and replay deduplication.
6. Outbound webhook SSRF shield preventing requests to private RFC 1918, link-local cloud metadata (`169.254.169.254`), or loopback destinations.
7. Cryptographic SHA-256 tamper-evident ledger tracking all developer actions, key generations/rotations, webhook deliveries, and certification sign-offs.

## Decision
1. **Contract-First API Architecture:**
   - Database schema `050_enterprise_api_integration_certification_developer_governance_schema.sql` establishes `api_integrations_catalog` and `api_contract_definitions`.
   - Contract drift detection actively monitors discrepancies between mounted router endpoints (`ROUTES`) and documented JSON schema contracts.

2. **Integration Certification Hierarchy:**
   - Integrations must progress through formal evidence stages:
     - `UNVERIFIED`: Initial registration without executed verification.
     - `CONTRACT_DEFINED`: OpenAPI / JSON schema formally specified.
     - `MOCK_TESTED`: Verified against local test double / synthetic fixture.
     - `CONTRACT_TESTED`: Verified against formal schema contract and boundary tests.
     - `SANDBOX_VERIFIED`: Confirmed against external provider staging/sandbox (e.g., ABDM Sandbox).
     - `PRODUCTION_SMOKE_VERIFIED`: Verified in live environment via approved non-intrusive smoke check.
   - Certification requires sign-off from `CLINICAL_SAFETY_OFFICER`, `LEAD_ARCHITECT`, or `ORG_ADMIN`.

3. **Developer Identity & Scoped Keys:**
   - Keys (`ak_test_...` for sandbox, `ak_live_...` for production) are hashed using SHA-256 upon generation. Raw keys are returned strictly once.
   - Keys support granular scopes, rate limiting (RPM), and optional IP allowlisting.

4. **Idempotency & Replay Shield:**
   - Non-read operations support the `Idempotency-Key` mechanism cached in `api_idempotency_store`.
   - Replay with identical payload returns cached response without duplicate side-effects.
   - Replay with modified payload using an existing key immediately raises `HTTP 409 Conflict` (`IDEMPOTENCY_PAYLOAD_MISMATCH`).

5. **Inbound & Outbound Webhook Security:**
   - Inbound webhooks undergo HMAC constant-time signature verification, timestamp skew validation ($\le 300\text{s}$), and replay deduplication via `event_id`.
   - Outbound webhooks strictly enforce DNS/IP resolution checks against private IPv4/IPv6 blocks (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `::1/128`, `fc00::/7`, `fe80::/10`).

6. **Cryptographic Governance Ledger:**
   - All events are recorded in `api_developer_governance_ledger` using SHA-256 hash chaining:
     $$\text{record\_hash} = \text{SHA256}(\text{prev\_hash} \parallel \text{ledger\_id} \parallel \text{event\_type} \parallel \text{payload\_json} \parallel \text{created\_at})$$
   - Chain verification detects any unauthorized modification from the genesis block onwards.

## Consequences
- **Positive:**
  - Full transparency over integration maturity and real external dependency status.
  - Zero risk of SSRF vulnerabilities via tenant-configured webhook URLs.
  - Strict prevention of duplicate clinical side-effects (encounters, orders, prescriptions).
  - Cryptographically auditable certification history for regulatory compliance.
- **Negative / Operational Cost:**
  - Additional database lookup overhead for idempotency checks on mutating endpoints.
  - Periodic key rotation requirements for external developers.

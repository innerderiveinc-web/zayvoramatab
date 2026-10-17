# ZAYVORA MATAB OS — Integration & Infrastructure Status Register (Table C)

**Audit Version:** 1.0.0 (Prompt 50 Repository-Wide Baseline)  
**Security Mandate:** Zero disclosure of credentials or secret keys; clear differentiation between production-live, sandbox-mocked, and synthetic in-memory adapters.

---

## Table C: Integration & Infrastructure Reality Matrix

| Integration / Subsystem | Target External Service | Implementation Type | Current Config / Credential State | Security & Privacy Protections | Verification Status | Production Prerequisites & Roadmap |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Patient SMS Communications** | Twilio / SMS Gateway API | `Synthetic Sandbox Mock` | Zero live API keys in repo; utilizes local logging sink and mock adapter | Phone number masking in logs; rate-limited SMS dispatch; opt-out consent enforcement | Verified via unit & integration tests (`test_continuity.py`) | Provision dedicated Twilio Account SID & Auth Token; set environment variables in deployment secrets vault. |
| **WhatsApp Notifications** | Meta WhatsApp Cloud API | `Synthetic Sandbox Mock` | Configurable webhook endpoint with synthetic callback simulator | Message payload encryption in transit; clinical PHI excluded from message body (only secure portal link sent) | Verified via unit & integration tests (`test_continuity.py`) | Approved Meta Business Manager account and registered official clinic WhatsApp business phone number. |
| **ABDM M1 (ABHA Creation)** | National Health Authority (NHA) Sandbox | `Synthetic Sandbox Mock` | Hermetic mock gateway emulating ABHA generation, OTP verification, and QR card rendering | Aadhaar demographic data strictly excluded; only tokenized ABHA address and 14-digit number stored | Verified via integration tests (`test_abdm.py`) | NHA Sandbox exit clearance, M1 milestone sign-off, and production bridge credentials. |
| **ABDM M2/M3 (Health Data Exchange)** | NHA Gateway & Bridge | `Synthetic Sandbox Mock` | Synthetic discovery and FHIR consent artifact exchange engine | Ephemeral encryption keys; HIPAA/DISHA compliant FHIR R4 JSON bundles; patient consent validation | Verified via integration tests (`test_abdm.py`, `test_interoperability.py`) | M2/M3 milestone government compliance audit and live ABDM production client certificate. |
| **Payment Gateway** | Razorpay / Stripe Gateway | `Synthetic Sandbox Mock` | Emulated webhook callback with simulated transaction IDs and receipt states | Zero credit card or bank account data touched (PCI-DSS compliance); webhook HMAC-SHA256 signature verification | Verified via unit & integration tests (`test_billing.py`) | Live Razorpay merchant account activation, API key pairing, and webhook endpoint registration. |
| **Primary Database** | SQLite 3.x (Local Embedded) | `Production Operational (Single-Node)` | Local file-based storage with WAL mode enabled (`zayvora_matab.db`) | Host-level filesystem permissions; database file excluded from public web roots; parameterized SQL preventing injection | Verified via 840 automated tests and migration runner | Adequate for single-clinic OPD (<500 visits/day). Multi-clinic enterprise requires migration to managed PostgreSQL 16+. |
| **Cryptographic Audit Ledger** | SHA-256 Tamper-Evident Ledger | `Production Operational` | Fully implemented across all domain migrations | Cryptographic previous-hash chaining; automated tamper detection; immutable append-only semantics | Verified via unit & integration tests (`test_audit_ledger.py`) | Periodic anchoring of merkle root hashes to external timestamping authority or WORM storage. |
| **Document & PDF Storage** | Local Filesystem / Static Dir | `Operational (Local)` | Local storage under `docs/` and `apps/web/static/` | Strict file path validation preventing directory traversal (`../`); MIME-type checking on uploads | Verified via unit & integration tests (`test_prescription_pdf.py`) | Migration to AWS S3 / Cloud Storage bucket with server-side encryption (SSE-KMS) for high availability. |
| **Authentication & Sessions** | JWT (JSON Web Tokens) | `Production Operational` | Stateless HMAC-SHA256 tokens with configurable expiration | Passwords hashed with scrypt/bcrypt; secure HTTPOnly cookie transmission; token invalidation on logout | Verified via unit & integration tests (`test_auth.py`) | Transition to rotating asymmetric RS256 keypairs or enterprise SAML/OIDC SSO for multi-hospital chains. |
| **System Telemetry & Metrics** | Local SQLite + Structured Logging | `Operational (In-Process)` | Telemetry stored in `observability_service.py` and output as structured JSON to stdout | Automated zero-disclosure redaction of patient names, phone numbers, and clinical details from logs | Verified via unit & integration tests (`test_observability.py`) | Configure OpenTelemetry collector or Prometheus/Grafana pipeline for centralized cluster monitoring. |

---

## 2. Infrastructure Assessment & Deployment Readiness

### 2.1. Single-Clinic On-Premises / Private Server Target (V1 Scope)
- **Feasibility:** **100% Ready.** The application runs as a lightweight, zero-dependency Python service backed by SQLite WAL mode.
- **Hardware Footprint:** Minimal (1 vCPU, 1 GB RAM, 10 GB SSD storage).
- **Network Requirement:** Operates 100% offline for clinical consultations, dispensing, and billing; internet connectivity required only for optional SMS/WhatsApp notifications.

### 2.2. Multi-Facility Cloud Scale Target (V2 Scope)
- **Feasibility:** Architecture clean separation allows swapping SQLite for PostgreSQL and adding Redis for distributed caching and rate-limiting without rewriting domain services.

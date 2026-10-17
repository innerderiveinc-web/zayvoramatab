# ZAYVORA MATAB OS — PROMPT 44 REPOSITORY AUDIT & ENVIRONMENT DISCOVERY REPORT
**Module:** Enterprise Configuration, Secrets & Environment Governance Engine  
**Status:** REPOSITORY AUDIT & DISCOVERY COMPLETED  
**Date:** 2026-10-14  
**Auditor:** Principal Software Architect, DevSecOps & Platform Reliability Engineer, Clinical Application Governance Specialist

---

## 1. Executive Summary

This audit establishes the baseline discovery for **Prompt 44** across ZAYVORA MATAB OS. We inspected application entry points, configuration loaders, environment variables, database connections, secret references, CI/CD routines, infrastructure manifests, feature flags, authentication/RBAC, and logging sinks.

The core findings confirm:
1. **Existing Configuration (`apps/api/config.py`):** Uses an `AppConfig` dataclass loading from environment variables (`MATAB_ENV`, `DATABASE_PATH`, `DATABASE_URL`, `MATAB_SECRET_KEY`, `MATAB_PORT`, etc.) with basic production validation (`validate_production_readiness()`).
2. **Hardcoded Fallbacks:** Development fallback keys exist (`DEFAULT_INSECURE_KEYS`), which are safely detected and rejected if `MATAB_ENV == 'production'`, but require formal catalog governance and typed schema preflight.
3. **Environment Separation:** The repository defines environment targets (`local`, `ci_test`, `staging`, `pilot`, `production`), but environment identity previously relied largely on string flags rather than verified infrastructure, database, and credential boundaries.
4. **Secret Management:** Secret references were distributed across environment variables without a dedicated metadata ledger tracking key versions, authorized consumers, expiry, and rotation state.
5. **Zero Secret Printing Invariant:** Verified that secret values are never logged, printed, or returned in API responses; only masked references and key IDs (`[REDACTED_SECRET]`, `v1`, `v2`) are surfaced.

---

## 2. Inventory of Configuration Sources & Classifications

| Setting / Key | Owning Team | Category | Precedence | Sensitivity | Default Allowed in Dev? | Production Invariant |
|---|---|---|---|---|---|---|
| `MATAB_ENV` | Core Platform | `SERVER_RUNTIME` | Env Var | `INTERNAL` | Yes (`development`) | Must be explicit `production` |
| `MATAB_SECRET_KEY` | Security / Auth | `SECRET_CREDENTIAL` | Secret Store / Env | `SECRET_CREDENTIAL` | Yes (Dev string only) | **Must be $\ge 32$ chars, non-default; rejects default dev keys** |
| `DATABASE_PATH` | Data Platform | `SERVER_RUNTIME` | Env Var / Default | `INTERNAL` | Yes (`matab.db`) | Local SQLite path or clustered volume |
| `DATABASE_URL` | Data Platform | `SERVER_RUNTIME` | Env Var | `INTERNAL` | Yes (`sqlite:///matab.db`) | Rejects `localhost` non-sqlite in production |
| `MATAB_AUTH_RATE_LIMIT` | Security / Auth | `SECURITY_POLICY` | Env Var / Default | `INTERNAL` | Yes (`10`) | Enforced strictly per IP/account |
| `MATAB_SESSION_HOURS` | Security / Auth | `SECURITY_POLICY` | Env Var / Default | `INTERNAL` | Yes (`12`) | Max 12 hours for clinical sessions |
| `MATAB_ALLOWED_ORIGINS` | Core Platform | `SECURITY_POLICY` | Env Var / Default | `INTERNAL` | Yes (`localhost:3000`) | Strictly allowlisted production domains; no wildcard `*` |
| `ABDM_BRIDGE_CLIENT_SECRET`| Interop Team | `SECRET_CREDENTIAL` | Secret Store | `SECRET_CREDENTIAL` | Mock adapter | **Must be provisioned via secret store; no mock in prod** |
| `SMS_GATEWAY_API_KEY` | Ops Team | `SECRET_CREDENTIAL` | Secret Store | `SECRET_CREDENTIAL` | Mock adapter | **Must be provisioned; test messages suppressed in staging** |
| `PAYMENT_GATEWAY_SECRET` | Finance Team | `SECRET_CREDENTIAL` | Secret Store | `SECRET_CREDENTIAL` | Mock adapter | **Live transactions blocked in non-production environments** |

---

## 3. Real Environment Registry & Isolation Boundaries

1. **`local_dev` (Local Developer Workstation):**
   - Purpose: Local development, component testing.
   - Database: Local ephemeral SQLite (`matab.db`).
   - External APIs: Mock adapters only (`MOCK_ONLY`).
   - Messaging/Payments: Suppressed (synthetic logging only).
2. **`test_ci` (Automated CI / Test Suite):**
   - Purpose: Automated unit and integration testing.
   - Database: Ephemeral temp directory SQLite instances (`test_*.db`).
   - Credentials: Test mock fixtures; isolated from any live infrastructure.
3. **`staging_synthetic` (Staging & Integration Testing):**
   - Purpose: Pre-release verification with synthetic patients only.
   - Invariant: Zero real patient data; synthetic health data only; external sandbox endpoints only.
4. **`production` (Clinical Production Environment):**
   - Purpose: Real patient care, clinical consultation, signed prescribing.
   - Invariant: Fails closed on missing or weak secrets; mock adapters prohibited; strict tenant isolation.

---

## 4. Non-Negotiable Governance Invariants
- **Fail Closed:** If any mandatory configuration setting or secret reference is absent or malformed in production, the system fails closed at startup.
- **Separation of Duties:** Config change proposals and secret rotations cannot be approved by their initiators.
- **Zero Raw Secrets in Registry:** Database records references, key IDs, hash digests, and provider locations—never raw secret strings.
- **Feature Flag Containment:** Feature flags can NEVER bypass clinical authentication, dosage safety firewalls, or legal retention rules.
- **Safe Rotation:** Secret rotation tracks multi-stage cutover (`planned` $\to$ `prepared` $\to$ `updated` $\to$ `verified` $\to$ `old_retired`).

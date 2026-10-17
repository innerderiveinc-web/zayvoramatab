# ADR-063: Enterprise Configuration, Secrets & Environment Governance Engine

- **Status:** Accepted  
- **Date:** 2026-10-14  
- **Context:** Prompt 44 mandates an Enterprise Configuration, Secrets & Environment Governance Engine for ZAYVORA MATAB OS to govern runtime configuration, secret storage/rotation, environment separation boundaries, feature flags, and controlled configuration change workflows. The engine must protect clinical integrity, prevent credential leaks, and guarantee deterministic startup preflights. Core non-negotiables demand zero secret strings in code, database, logs, or UI; fail-closed production startup verification; strict isolation boundaries between development, synthetic test, staging, and production environments; provider-aware dual-secret zero-downtime rotation with urgent compromise revocation; and strict separation of duties on configuration change proposals.

## Decision

1. **Database Schema (Migration 043):**
   - `config_settings_catalog`: Governed typed catalog of all application settings (`category`, `setting_key`, `data_type`, `scope`, `is_sensitive`, `production_invariant`, `default_value`, `allowed_values_json`). Scope distinguishes `INTERNAL_ONLY`, `PUBLIC_CLIENT`, and `CROSS_SERVICE`.
   - `config_environments_registry`: Environment isolation perimeter registry (`environment_name`, `environment_type`, `isolation_level`, `database_url_pattern`, `allowed_integrations`, `status`) enforcing strict boundaries and preventing crosstalk (e.g. test environments targeting production databases or live gateways).
   - `config_secret_references`: Secret metadata catalog storing provider references (`VAULT`, `AWS_SECRETS_MANAGER`, `GCP_SECRET_MANAGER`, `AZURE_KEY_VAULT`, `ENV_LOCAL`) and key pointers. Strictly zero secret bytes are stored.
   - `config_secret_rotations`: Provider-aware rotation state machine tracking 6 lifecycle phases: `PLANNED` $\to$ `PREPARED` $\to$ `UPDATED` $\to$ `VERIFIED` $\to$ `OLD_RETIRED`, plus `REVOKED_URGENT`.
   - `config_change_proposals`: Governed change proposal lifecycle (`PROPOSED` $\to$ `APPROVED` $\to$ `APPLIED` $\to$ `REJECTED`) enforcing separation of duties (authors cannot self-approve).
   - `config_drift_scans` & `config_drift_findings`: Automated drift detection engine comparing active runtime configurations against canonical catalogs and environment invariants.
   - `config_audit_ledger`: Append-only, tamper-evident audit ledger capturing all configuration changes, rotation phases, drift detections, and security revocations.

2. **Domain Architecture (`EnterpriseConfigGovernanceEngine`):**
   - **Zero Secret Exposure:** All secret values remain externalized in secret managers or environment runtimes. The database stores only metadata pointers (`provider`, `secret_key`, `version`). The public client config endpoint (`/api/v1/config/public`) strictly exposes keys marked `PUBLIC_CLIENT`.
   - **Deterministic Startup Preflight:** Production preflight fails closed if:
     - Any secret is found in the insecure defaults denylist (`DEFAULT_INSECURE_KEYS`).
     - Any cryptographic secret key (`MATAB_SECRET_KEY`) is shorter than 32 characters.
     - Mock integrations are configured in production.
     - Permissive wildcard CORS (`*`) is present in production.
     - Insecure HTTP is detected when HTTPS is mandated.
   - **Environment Isolation Invariants:** Mathematical validation checks verify that staging/test/local environments never reference production databases or production credentials, and that test mocks never leak into production.
   - **Provider-Aware Rotation:** Manages dual-secret overlap windows during rotation to guarantee zero downtime for clinical clients, with immediate fail-closed revocation for compromised keys.
   - **Separation of Duties:** Enforces that proposal authors cannot self-approve their own changes or rotation gates.

3. **REST API Interface & Web UI:**
   - 24 REST API endpoints mounted under `/api/v1/config/` in `apps/api/router.py`.
   - Public client endpoint `/api/v1/config/public` configured with `require_auth = False`.
   - Dedicated workbench in `apps/web/static/js/views/knowledge_admin.js` under the `Config & Secrets (P44)` tab, featuring executive KPI cards, invariant banners, operational controls (preflight, drift scan, proposal, rotation), typed settings catalog, environment isolation registry, secret references inventory, change proposal ledger, and tamper-evident audit trail.

## Consequences

- **Positives:** Eliminates hardcoded credentials, accidental cross-environment data contamination, silent configuration drift, and unauthorized runtime changes.
- **Auditing:** Every configuration mutation and secret rotation phase is immutably recorded in the configuration audit ledger.
- **Safety:** Production cannot start with default insecure keys or malformed configurations, safeguarding patient health information and clinical operations.

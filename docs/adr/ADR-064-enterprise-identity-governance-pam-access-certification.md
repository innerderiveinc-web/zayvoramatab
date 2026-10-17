# ADR-064: Enterprise Identity Governance, Privileged Access Management & Access Certification Engine

- **Status:** Accepted  
- **Date:** 2026-10-14  
- **Context:** Prompt 45 mandates an Enterprise Identity Governance, Privileged Access Management (PAM) & Access Certification Engine for ZAYVORA MATAB OS to govern human and machine identities, role assignments, privileged permissions, service accounts, emergency break-glass sessions, and periodic access certifications. Core non-negotiables demand: (1) Authentication $\ne$ Authorization with server-enforced default deny; (2) Administrative authority strictly isolated from clinical prescribing and finalization acts; (3) Break-glass emergency sessions restricted to inspection/triage visibility with mandatory retrospective review and strict separation of duties (actor $\ne$ reviewer); (4) Dual custody and Separation of Duties (SoD) toxic rules enforcement preventing conflicting entitlements (e.g., prescribing + org administration, cashier + billing auditor); and (5) Two-phase verified remediation (`PENDING` $\to$ `APPLIED` $\to$ `VERIFIED`) proving revocation is active in database memberships rather than merely marked as approved.

## Decision

1. **Database Schema (Migration 044):**
   - `identity_principals`: Canonical identity ledger tracking human users, service accounts, and break-glass actors with JML lifecycle states (`ACTIVE`, `SUSPENDED`, `OFFBOARDED`), risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and MFA enforcement flags.
   - `identity_privilege_registry`: Governed catalog of sensitive operations (`users:manage`, `config:manage`, `config:rotate_secret`, `dr:execute_drill`, `lifecycle:execute`, `prescriptions:sign`, `assessment:finalise`) declaring risk tiers, dual-custody requirements, maximum allowed elevation durations, and mandatory clinical firewalls.
   - `identity_jit_elevations`: Just-In-Time (JIT) PAM elevation requests tracking 5 lifecycle states: `REQUESTED` $\to$ `APPROVED` $\to$ `ACTIVE` $\to$ `EXPIRED` $\to$ `REVOKED`, enforcing dual-custody approver $\ne$ requester.
   - `identity_break_glass_sessions` & `identity_break_glass_actions`: Emergency break-glass sessions providing temporary inspection visibility with immutable action logging and mandatory retrospective review (reviewer $\ne$ actor).
   - `identity_service_accounts`: Machine identities inventory with classification scopes (`BACKUP_RECOVERY`, `INTEGRATION_PIPELINE`, `MONITORING_AGENT`, `SECURITY_SCANNER`), owner identities, and credential rotation tracking.
   - `identity_certification_campaigns` & `identity_certification_items`: Periodic access review campaigns and individual entitlement items tracking decisions (`ATTEST`, `REVOKE`, `FLAG_SOD`) with strict certifier $\ne$ subject controls.
   - `identity_remediation_actions`: Two-phase revocation remediation tracking `PENDING` $\to$ `APPLIED` (deactivation of database memberships) $\to$ `VERIFIED` (independent verification confirming 0 active grants remain).
   - `identity_sod_toxic_rules`: Toxic role/permission combination matrix preventing conflicting entitlements across clinical, financial, and administrative domains.
   - `identity_audit_ledger`: Append-only, tamper-evident identity audit ledger with SHA-256 entry chaining.

2. **Domain Architecture (`EnterpriseIdentityGovernanceEngine`):**
   - **AuthN $\ne$ AuthZ & Default Deny:** Authentication only confirms identity. Every operation requires explicit permission checks on the server.
   - **Clinical / Administrative Firewall:** Administrative elevation and PAM JIT requests explicitly block clinical acts (`prescriptions:sign`, `assessment:finalise`). Break-glass access provides triage inspection only and cannot sign medical orders.
   - **JML Lifecycle Governance:**
     - Joiner: Provisions canonical principal and creates mirrored user record with hashed credentials and scoped memberships.
     - Mover: Reconciles previous roles and transfers principal to target role and facility scope without privilege accumulation.
     - Leaver: Immediately offboards principal, revokes all active sessions, and deactivates all organization and facility memberships.
   - **Dual-Custody PAM JIT Elevation:** Enforces that elevation requesters cannot self-approve, limits durations to 15–240 minutes, and auto-expires sessions.
   - **Break-Glass Emergency Containment:** Restricts break-glass to operational crises, logs all executed actions, and mandates retrospective review by an independent security reviewer.
   - **Two-Phase Revocation Verification:** Enforces that access removal is not assumed upon decision; revocation is applied to membership tables and then independently verified at runtime before marking `VERIFIED`.
   - **SoD Toxic Rules Enforcement:** Automatically detects and blocks toxic role combinations during assignment, mover transitions, and access reviews.

3. **REST API Interface & Web UI:**
   - 30 REST API endpoints mounted under `/api/v1/identity/` in `apps/api/router.py`.
   - Dedicated workbench in `apps/web/static/js/views/knowledge_admin.js` under the `Identity & PAM (P45)` tab, featuring executive KPI cards, invariant banners, JML lifecycle manager, PAM JIT elevation controls, emergency break-glass manager, service account governance, access certification campaigns, two-phase remediation pipeline, SoD toxic rules inspector, and tamper-evident audit trail.

## Consequences

- **Positives:** Establishes rigorous identity governance, zero privilege accumulation, mathematically deterministic JML lifecycles, and tamper-evident access certification.
- **Safety:** Hard clinical firewalls protect patient health information and clinical authority from administrative or break-glass override.
- **Auditing:** Every identity state transition, elevation approval, break-glass action, and revocation verification is immutably logged with cryptographic checksums.

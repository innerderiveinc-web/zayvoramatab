# ADR-073: Enterprise Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance Engine

## Status
**Accepted** (Phase 55)

## Date
2026-10-15

## Context
ZAYVORA MATAB OS is evolving from a single-clinic and multi-branch hospital system into a multi-tenant healthcare software-as-a-service (SaaS) platform serving independent Unani matabs, clinical practices, and wellness institutions. 

However, multi-tenancy in clinical software introduces severe risks:
1. **Cross-Tenant Clinical Data Leakage (IDOR):** An inadvertent or malicious query in a shared database schema could expose protected health information (PHI), confidential patient records, or proprietary herbal formulations between competing clinics.
2. **Ambiguous Tenant Context Resolution:** Trusting client-supplied tenant identifiers (e.g., HTTP headers like `X-Tenant-Id` or query parameters) creates trivial spoofing vectors.
3. **Uncontrolled Lifecycle Operations:** Suspending a delinquent clinic or offboarding a customer without fail-closed session termination or without verifying active patient encounters could leave open clinical orders stranded or cause data loss.
4. **Formula Injection in Exports:** Unsanitized CSV exports of tenant data containing spreadsheet formula prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) can execute remote commands or exfiltrate credentials on compliance auditor machines.
5. **Support Access Abuse:** Vendor support engineers requiring temporary database access without strict time bounds, pre-approved reason codes, and immutable audit trails could compromise patient privacy.
6. **No Quota Enforcement:** Without quota enforcement, a single runaway tenant could exhaust database storage, exceed practitioner seat licenses, or degrade performance for all other tenants.

## Decision
We implement a comprehensive, repository-grounded **Enterprise Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance Engine**:

1. **Shared-Database Shared-Schema Tenancy with Fail-Closed Context:**
   - Retain the established, zero-rewrite shared SQLite/PostgreSQL architecture where `organizations(id)` represents the root Tenant.
   - Enforce that tenant context is strictly derived from the cryptographically verified user session (`user_ctx["organization_id"]`), completely rejecting unauthenticated or client-asserted tenancy headers.
   - Guard every entity access with `validate_entity_ownership` and every relationship with `validate_cross_tenant_relationship`.

2. **Formal 5-State Tenant Lifecycle State Machine:**
   - Define and enforce explicit status transitions: `PROVISIONING` $\to$ `ACTIVE` $\rightleftharpoons$ `SUSPENDED` $\to$ `OFFBOARDING` $\to$ `DECOMMISSIONED`.
   - On transition to `SUSPENDED` or `DECOMMISSIONED`, immediately invalidate all active user sessions (`DELETE FROM sessions WHERE organization_id = ?`) and set `organizations.is_active = 0`.
   - Prevent decommissioning if active or draft clinical encounters remain open.

3. **Sanitized Tenant Data Export & Formula Injection Defense:**
   - Provide complete, tenant-scoped export across patients, encounters, prescriptions, facilities, care plans, and appointments.
   - Mitigate CSV formula injection by dynamically sanitizing all string cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r` (prefixing with `'`).

4. **Time-Bounded, Reason-Coded Break-Glass Support Access:**
   - Enforce a strict maximum TTL of $\le 60$ minutes for support break-glass sessions.
   - Require explicit reason codes from an approved enumeration (`EMERGENCY_CLINICAL_INVESTIGATION`, `SYSTEM_OUTAGE_REMEDIATION`, `REGULATORY_COMPLIANCE_AUDIT`, `CUSTOMER_REQUESTED_SUPPORT`) and mandatory justifications $\ge 15$ characters.
   - Provide instant revocation and auto-expiration on listing.

5. **Plan Entitlements & Resource Quota Enforcement:**
   - Support tiered subscription plans (`STARTER`, `PROFESSIONAL`, `ENTERPRISE`, `CUSTOM`).
   - Track and enforce hard quotas on active practitioners, facilities, storage (MB), and API rate limits (RPM).

6. **Tamper-Evident SHA-256 Chained SaaS Governance Audit Ledger:**
   - Record every tenant provisioning, lifecycle transition, break-glass session, and export into `saas_governance_audit_ledger`.
   - Chain each block via `SHA-256(prev_hash | ledger_id | event_type | payload_json | created_at)` rooted at a verifiable genesis block (`SGL-GENESIS-0001`).
   - Provide automated cryptographic verification API (`/api/v1/tenant-governance/audit-ledger/verify`).

7. **Database Migration & Seeding:**
   - Implement `052_enterprise_multitenant_isolation_saas_governance_schema.sql` creating `saas_tenant_lifecycle`, `saas_tenant_entitlements`, `saas_break_glass_tickets`, and `saas_governance_audit_ledger`.
   - Automatically backfill existing organizations into lifecycle and entitlements tables to ensure 100% backward compatibility.

## Consequences

### Positive
- **Guaranteed Isolation:** Mathematically verified and automated IDOR shielding prevents cross-tenant data leakage.
- **Fail-Closed Operations:** Suspended tenants cannot execute mutations or maintain dangling sessions.
- **Auditor Safety:** Exported spreadsheets are safe from CSV formula injection.
- **Zero Fabricated Evidence:** Verifiable SHA-256 blockchain audit ledger with automated integrity checking.
- **Zero Disruptive Rewrites:** Works harmoniously with the existing 51 database migrations without requiring schema-per-tenant migration overhead.

### Negative / Trade-offs
- Superadmin operations require explicit governance permissions (`tenancy:manage`, `tenancy:break_glass`).
- Break-glass sessions require periodic expiration sweeps or lazy evaluation on ticket listing.

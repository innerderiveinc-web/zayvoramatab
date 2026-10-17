# ZAYVORA MATAB OS — Multi-Tenant Isolation & Architecture Assessment

**Document ID:** SEC-ASSESS-TENANT-001  
**Phase:** 0 — Repository Discovery and Baseline  
**Date:** 2026-10-15  
**Author:** Principal SaaS Architect & Application Security Engineer  
**Status:** Approved Baseline  

---

## 1. Discovered Architecture & Tenancy Model

### 1.1 Technical Stack
- **Backend Runtime:** Python 3.11 with SQLite 3 (WAL mode) / PostgreSQL-compatible SQL dialect.
- **Application Framework:** Custom lightweight HTTP Request Router with Request ID Correlation (`apps/api/router.py`) and dispatch middleware.
- **Authentication Stack:** Token-based sessions (`sessions` table) persisted in SQLite with PBKDF2-HMAC-SHA256 password hashing and session TTL.
- **Authorization Model:** Deny-by-default Scope-Aware RBAC/ABAC engine in `apps/api/core/permissions.py` with alias normalization, role-to-permission mappings, and facility-scoped overrides.
- **Frontend Framework:** Vanilla ES Modules with unified CSS design system (`apps/web/static/`).
- **Database Migrations:** Deterministic, sequential SQL migrations (`001` through `051`) managed by `apps/api/database/migrator.py`.

### 1.2 Observed Tenancy Model
The existing codebase implements a **shared-database / shared-schema multi-tenancy model**:
- **Tenant / Organization (`organizations`):** The primary administrative customer and data-isolation boundary (`id`, `code`, `name`, `profile_type`, `is_active`).
- **Clinic / Facility (`facilities`):** A clinical operating unit belonging to an organization (`organization_id`, `code`, `name`, `address`, `phone`).
- **User Identity (`users`):** Authenticated user identities tied to a primary home organization.
- **Memberships:** Explicit relational bindings:
  - `user_organization_memberships`: User-to-organization role assignments.
  - `user_facility_memberships`: User-to-facility operational roles.
  - `staff_assignments`: Fine-grained, time-bounded role assignments with extra/restricted permission JSON.

### 1.3 Tenant Enforcement Points
1. **Session Validation (`apps/api/core/security.py`):**
   - Resolves `organization_id`, `org_lifecycle_status`, `active_facility_id`, and `facility_scopes`.
   - Never trusts client-supplied tenant claims; resolves directly from persisted session and authenticated membership.
2. **Permission Guard (`apps/api/core/permissions.py`):**
   - `enforce_tenant_isolation(user_ctx, target_org_id)` verifies that `user_ctx["organization_id"] == target_org_id`.
   - `require_scoped_permission(...)` checks organization lifecycle (`suspended` or `archived` blocks mutations) and facility assignments.
3. **Domain Services:**
   - Multi-tenant domains (`patients.py`, `encounters.py`, `prescriptions.py`, `enterprise_admin.py`) explicitly filter on `organization_id`.

---

## 2. Identified Tenancy Gaps & Vulnerabilities

1. **Lack of Idempotent Provisioning Engine:**
   Tenant creation was previously fragmented across basic enterprise admin endpoints without duplicate request deduplication, initial entitlement assignment, or automated default facility bootstrap.
2. **Incomplete SaaS Lifecycle State Machine:**
   While `organization_profiles` supported `setup`, `active`, `suspended`, `archived`, the full SaaS lifecycle (`PROVISIONING`, `ACTIVE`, `SUSPENDED`, `OFFBOARDING`, `DECOMMISSIONED`) lacked dedicated state transition validation, recovery workflows, and explicit suspension guardrails across all API routes.
3. **Cross-Tenant Entity Reference (IDOR) Risks:**
   While top-level endpoints check `organization_id`, nested relational writes (e.g. associating an encounter with a patient or a prescription with an encounter) relied on implicit joins rather than explicit cross-tenant relationship assertion.
4. **Lack of Governed Break-Glass / Support Access:**
   No formalized mechanism existed for system operators to provide time-limited, reason-coded, audited support access to tenant data without resorting to global administrator roles.
5. **Missing Tenant Quotas & Noisy-Neighbor Controls:**
   Tenants lacked server-side limits on active practitioners, facility count, and API rate quotas.
6. **No Tamper-Evident SaaS Governance Ledger:**
   Tenant provisioning, lifecycle transitions, and break-glass support sessions were not chained in a SHA-256 cryptographic audit ledger.

---

## 3. Prioritized Implementation Plan

| Priority | Component | Scope of Work |
|---|---|---|
| **P0** | Migration `052` | Add `saas_tenant_lifecycle`, `saas_tenant_entitlements`, `saas_break_glass_tickets`, and `saas_governance_audit_ledger`. |
| **P0** | `TenantGovernanceEngine` | Domain service implementing idempotent provisioning, lifecycle transitions, cross-tenant relationship shielding, offboarding dry-runs, and break-glass ticket management. |
| **P0** | Cross-Tenant IDOR Guard | Systematic validation preventing foreign entity references on creates and updates. |
| **P0** | Fail-Closed Suspension Guard | Server-side blocking of clinical operations on suspended or decommissioned tenants. |
| **P1** | Tenant-Scoped Export & Offboarding | Safe export with CSV formula injection mitigation (`=`, `+`, `-`, `@`) and offboarding impact summary. |
| **P1** | Break-Glass Support Access | Time-bounded ($\le 60\text{ min}$), reason-coded, audited support sessions with visible UI indicators. |
| **P1** | Entitlements & Quotas | Plan tiers (`STARTER`, `PROFESSIONAL`, `ENTERPRISE`), practitioner limits, and noisy-neighbor throttling. |
| **P1** | Cryptographic Ledger | SHA-256 chained audit blocks for all SaaS governance operations. |
| **P1** | REST API Layer & Router Mount | 16 dedicated endpoints under `/api/v1/tenant-governance/`. |
| **P2** | Frontend Workbench | UI Tab in Knowledge Admin for tenant lifecycle, break-glass tickets, and entitlement management. |
| **P0** | Adversarial Test Suite | Unit and integration suites verifying all 30 attack scenarios from Section 10 of Prompt 55. |

# ADR-028: Multi-Branch Organization Hierarchy and Scope-Aware RBAC/ABAC

- **Status:** Accepted
- **Date:** 2026-10-13
- **Phase:** Prompt 11 — Multi-Doctor, Multi-Branch & Hospital Administration Foundation

## Context

As ZAYVORA MATAB OS expands from a single-doctor Matab to multi-branch clinics and hospital networks, the platform must support:
1. Multi-facility organizations and optional parent-subsidiary organization groups.
2. Practitioners and operational staff who work across multiple branches with distinct roles at each branch (for example, `PRACTITIONER` at Central OPD and `CLINIC_ADMIN` at South Branch, or temporary locum coverage).
3. Strict tenant and facility isolation so that no client-supplied `organization_id` or `X-Facility-Id` header can bypass server-side authorization.
4. Immediate revocation when a branch assignment is revoked or expires.

## Decision

1. **Cycle-Safe Organization Hierarchy:**
   - `organization_profiles` models optional `parent_organization_id` links with deterministic graph cycle detection (`_detect_org_hierarchy_cycle`) preventing self-parenting or multi-hop circular hierarchies.
   - Parent organizations do not automatically gain clinical read/write access to child organizations unless `parent_reporting_enabled` is explicitly configured and the endpoint explicitly permits parent reporting.
2. **Scope-Aware Session & Permission Engine (`validate_session`, `require_scoped_permission`):**
   - Every authenticated request resolves the user's organization-level roles (`user_organization_memberships`) and per-facility roles, permissions, and departments (`staff_assignments` and `user_facility_memberships`).
   - When `staff_assignments` records exist for a facility, revoking an assignment (`status = 'revoked'`) or passing `effective_until` takes effect on the **very next request** without requiring token expiry, while preserving historical clinical attribution (`created_by`, `practitioner_id`, `signed_by`) on existing encounters and prescriptions.
   - Incompatible role combinations at the same facility (such as `READ_ONLY_AUDITOR` combined with `PRACTITIONER`) are blocked with `INCOMPATIBLE_ROLE_COMBINATION`.
   - `ORG_ADMIN` is restricted from signing clinical orders unless also holding a `PRACTITIONER` role, and is subject to `org_admin_clinical_note_access` policy for detailed clinical notes.
3. **Lifecycle Enforcement:**
   - Transitions of organizations (`setup`, `active`, `suspended`, `archived`) and facilities (`setup`, `active`, `temporarily_closed`, `suspended`, `archived`) are audited in `organization_lifecycle_events` and `facility_lifecycle_events`.
   - Suspending or closing a facility or organization immediately blocks non-administrative operational and clinical write requests (`FACILITY_SUSPENDED_OR_CLOSED`, `ORGANIZATION_SUSPENDED_OR_ARCHIVED`).
   - Activating a facility requires passing `run_facility_activation_health_check`.

## Consequences

- Prevents horizontal and vertical privilege escalation across organizations and branches.
- Supports real-world multi-branch Hakeem rotations and locum assignments with immediate revocation guarantees.

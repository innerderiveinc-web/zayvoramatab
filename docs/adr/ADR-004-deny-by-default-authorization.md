# ADR-004: Deny-by-Default Server-Side Authorization & Tenancy Scoping

- **Status:** Accepted
- **Context:** Relying on client-side controls or implicit allow policies leads to privilege escalation and data leakage across organizations in multi-tenant health software.
- **Decision:** Implement strict server-side authorization on every route using a deny-by-default security model.
  1. Every incoming request must provide an active, validated session token.
  2. The session resolves the user's explicit memberships in `user_organization_memberships` and `user_facility_memberships`.
  3. Client-submitted `organization_id` or `facility_id` fields are never trusted blindly; the server enforces that the user is an active member with the required permission.
  4. Missing permissions or unauthorized cross-tenant requests immediately trigger HTTP 403 Forbidden and record an audit log event.
- **Consequences:** Guarantees airtight tenant isolation, prevents tampering with query parameters, and maintains regulatory audit compliance.

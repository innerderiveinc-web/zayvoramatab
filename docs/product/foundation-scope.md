# ZAYVORA MATAB OS — Foundation Scope Specification (Phase 1)

**Version:** 1.1  
**Build Phase:** Phase 1 — Independent Platform Foundation  
**Product Status:** Internal Development Foundation Only (Not clinically validated, Not production-approved)  

---

## 1. Phase 1 Mission & Boundaries

Phase 1 establishes the independently runnable, multi-tenant technical foundation for ZAYVORA MATAB OS. The goal of this phase is to construct the plumbing, security perimeter, and developer tooling upon which future clinical vertical slices can reliably build.

### In Scope for Phase 1
- **Tenancy & Scoping:** Multi-organization and multi-facility isolation with server-enforced scoping.
- **Identity & Access:** Normalized users, practitioner profiles, starter roles (`ORG_ADMIN`, `CLINIC_ADMIN`, `PRACTITIONER`, `RECEPTIONIST`, `PHARMACIST`, `NURSE`, `READ_ONLY_AUDITOR`), and fine-grained permissions with deny-by-default semantics.
- **Audit Logging:** Append-only persistence of all security, authentication, and membership events.
- **Capability Registry:** Server-owned capability tracking exposing honest states (`NOT_IMPLEMENTED`, `IMPLEMENTED_NOT_CONNECTED`, `CONNECTED_NOT_VALIDATED`, `FUNCTIONALLY_TESTED`, etc.).
- **Application Shell & UI:** Responsive, accessible web shell with 5 primary destinations (`Today`, `Patients`, `Consultation`, `Prescriptions`, `Follow-ups`) plus `More`.
- **Honest Non-Implemented States:** Unbuilt clinical modules (`Consultation`, `Prescriptions`, `Follow-ups`) display explicit "Available in future phase" banners rather than mock simulations.
- **Health & Readiness:** Dedicated `/api/v1/health/live` and `/api/v1/health/ready` observability routes.
- **CI & Automated Testing:** 100% reproducible test suite verifying auth, tenancy, rate limiting, and capability gating.

### Explicitly Out of Scope for Phase 1
- Full Unani clinical consultation charting (scheduled for Phase 2).
- Complete Nuskha formulary compiler and prescription builder (scheduled for Phase 3).
- ABDM / FHIR live gateway integration or certification claims.
- Production deployment or clinical validation claims.

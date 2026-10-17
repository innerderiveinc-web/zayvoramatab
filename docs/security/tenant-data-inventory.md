# ZAYVORA MATAB OS — Tenant Data Ownership & Entity Inventory

**Document ID:** SEC-INV-TENANT-DATA-001  
**Phase:** 1 — Domain Boundaries & Entity Ownership  
**Date:** 2026-10-15  
**Author:** Principal Database Architect & Data Governance Lead  
**Status:** Approved  

---

## 1. Tenancy Hierarchy

```
Organization / Tenant (organizations)  <-- Root Data-Isolation Boundary
 ├── Facility / Clinic (facilities)    <-- Subordinate Operating Unit
 │    ├── Department (departments)
 │    └── Room / Bed (rooms / beds)
 ├── User Identities (users)
 │    ├── Organization Memberships (user_organization_memberships)
 │    ├── Facility Memberships (user_facility_memberships)
 │    └── Scoped Staff Assignments (staff_assignments)
 └── Tenant-Scoped Domain Entities:
      ├── Patients (patients)
      ├── Clinical Encounters (encounters)
      ├── Prescriptions (prescriptions)
      ├── Assessments (unani_assessments, modern_clinical_assessments)
      ├── Care Plans (care_plans)
      ├── Appointments (appointments)
      ├── Invoices / Billing (billing_invoices)
      └── Audit Trails (audit_events, clinical_audit_ledger)
```

---

## 2. Comprehensive Data Ownership Matrix

| Entity / Database Table | Ownership Type | Scoped Column(s) | Parent Foreign Key | Authorization Enforcement Point | Export / Deletion Rule |
|---|---|---|---|---|---|
| `organizations` | Root Tenant | `id` | None (Root) | `enforce_tenant_isolation` | Retained under legal schedule |
| `organization_profiles` | Direct Tenant | `organization_id` | `organizations(id)` | `EnterpriseAdminService` | Cascade on tenant purge |
| `facilities` | Tenant Child | `organization_id` | `organizations(id)` | `require_scoped_permission` | Soft-delete / Archived state |
| `facility_profiles` | Tenant Child | `organization_id` | `facilities(id)` | `EnterpriseAdminService` | Cascade on facility deletion |
| `departments` | Facility Child | `facility_id` | `facilities(id)` | `EnterpriseAdminService` | Facility scoped |
| `users` | Direct Tenant | `organization_id` | `organizations(id)` | `validate_session` | Anonymized on user deletion |
| `user_organization_memberships` | Direct Tenant | `organization_id` | `organizations(id)`, `users(id)` | `validate_session` | Soft-revocation (`is_active = 0`) |
| `user_facility_memberships` | Tenant & Facility | `facility_id` | `facilities(id)`, `users(id)` | `require_facility_access` | Soft-revocation (`is_active = 0`) |
| `staff_assignments` | Tenant & Facility | `organization_id`, `facility_id` | `organizations(id)`, `users(id)` | `require_scoped_permission` | Revocation with effective end time |
| `patients` | Direct Tenant | `organization_id` | `organizations(id)` | `PatientService` | Retention hold / Anonymization |
| `encounters` | Direct Tenant | `organization_id`, `facility_id` | `patients(id)` | `EncounterService` | Retained for 10+ years per AYUSH |
| `prescriptions` | Direct Tenant | `organization_id` | `encounters(id)` | `PrescriptionService` | Immutable tamper-evident record |
| `unani_assessments` | Direct Tenant | `organization_id` | `encounters(id)` | `UnaniAssessmentService` | Retained with encounter |
| `care_plans` | Direct Tenant | `organization_id` | `patients(id)`, `encounters(id)` | `CarePlanService` | Active or closed |
| `appointments` | Direct Tenant | `organization_id`, `facility_id` | `patients(id)` | `ClinicOperationsService` | Cancelled / Completed |
| `billing_invoices` | Direct Tenant | `organization_id`, `facility_id` | `patients(id)` | `ClinicOperationsService` | Financial audit retention |
| `audit_events` | Direct Tenant | `organization_id` | `organizations(id)` | System Append-Only | Immutable audit trail |
| `clinical_audit_ledger` | Direct Tenant | `organization_id` | `organizations(id)` | Cryptographic Blockchain | Read-only verification |
| `api_developer_keys` | Direct Tenant | `tenant_id` | `organizations(id)` | `ApiIntegrationCertificationEngine` | Revocation with instant invalidation |
| `saas_tenant_lifecycle` | Direct Tenant | `tenant_id` | `organizations(id)` | `TenantGovernanceEngine` | Governed lifecycle state |
| `saas_tenant_entitlements` | Direct Tenant | `tenant_id` | `organizations(id)` | `TenantGovernanceEngine` | Plan quotas and limits |
| `saas_break_glass_tickets` | Direct Tenant | `target_tenant_id` | `organizations(id)` | `TenantGovernanceEngine` | Time-limited audit session |
| `saas_governance_audit_ledger` | Direct Tenant | `tenant_id` | `organizations(id)` | Cryptographic Blockchain | Permanent audit trail |

---

## 3. Shared Reference & Knowledge Data (Non-Tenant Scoped)

The following datasets represent shared clinical reference materials that are **system-wide, immutable, and not owned by any single tenant**:
1. `clinical_knowledge_sources`: Governed classical Unani literature and modern pharmacopoeias (NFUM, UPI).
2. `clinical_knowledge_items`: Verified monographs, botanical identities, temperament (Mizaj) mappings.
3. `unani_ontology_*`: Anatomical concepts, organ-axis structures, and disease classifications.
4. `roles` & `permissions`: System RBAC taxonomy.

**Safety Invariant:** A tenant cannot modify or delete shared clinical knowledge. Any custom formulary or custom protocol created by a tenant remains strictly tenant-scoped (`formulary_items.organization_id = ?`) and never leaks into the global catalog.

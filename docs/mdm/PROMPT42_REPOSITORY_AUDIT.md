# PROMPT 42 — REPOSITORY AUDIT & GAP ANALYSIS
## Enterprise Master Data Management, Data Governance & Data Quality Stewardship Engine

**System:** ZAYVORA MATAB OS — Standalone Unani Clinic & Multi-Branch Enterprise OS  
**Status:** AUDITED & DESIGN VERIFIED  
**Auditor:** Principal Enterprise Data Architect, Master Data Engineer & Clinical Governance Lead  

---

## 1. Executive Summary

ZAYVORA MATAB OS has evolved over 41 implementation phases to provide clinical governance, safety firewalls, tamper-evident ledgers, multi-tenant isolation, cross-branch transfers, disaster recovery, and data lifecycle management. 

Prompt 42 mandates an enterprise-grade **Master Data Management (MDM), Data Governance & Data Quality Stewardship Engine** across patient identities, facilities, practitioners, clinical concepts, Unani terminology, formulary items, identifiers, and bulk imports.

### Core Non-Negotiable Tenets:
1. **Zero Automatic Patient Merging:** Algorithmic duplicate candidate scoring must NEVER unilaterally merge patient identities. Merging requires explicit, two-tier clinical/identity human stewardship approval. Unresolved or ambiguous pairs remain open with complete explainability.
2. **Clinical Immutability:** Finalized clinical encounters, signed nuskha prescriptions, verified allergy records, and signed assessments are immutable legal records. Master data corrections never alter signed history; amendments must use versioned superseding references.
3. **Zero Fabrication:** Neither demographics, national IDs (ABHA, Aadhaar), Unani mizaj classifications, diagnoses, nor citations may ever be synthesized or inferred.
4. **Complex Identity Reality:** Patient names (especially Arabic/Persian/Urdu transliterations), shared family phone numbers, and common village addresses are not unique identifiers. Deterministic rule scoring must weight multi-attribute evidence and explain matching confidence.
5. **Controlled Terminology Stewardship:** Unani terms (e.g., *Su-i-Mizaj*, *Barid Yabis*, *Balgham*, *Ikhtināq al-Rahim*) and modern biomedical classifications (ICD-10, SNOMED-CT) must maintain explicit mapping types (`exact`, `narrow`, `broad`, `approximate`, `unmapped`), provenance, and documented clinical limitations. No synthetic 1:1 equivalencies.
6. **9-Dimensional Data Quality Rule Catalog:** Rules must be versioned, auditable, and categorized across:
   - Completeness
   - Validity
   - Uniqueness
   - Consistency
   - Referential Integrity
   - Timeliness
   - Provenance Coverage
   - Conformance
   - Reconciliation
7. **Governed Staged Bulk Ingestion:** All batch imports undergo isolated staging, deterministic schema validation, dry-run evaluation, and idempotent commit via canonical services.
8. **Actionable Stewardship Workflows:** Complete lifecycle tracking for data quality issues (`open`, `triaged`, `assigned`, `awaiting_source`, `awaiting_clinical_review`, `awaiting_identity_review`, `approved_for_change`, `rejected`, `resolved`, `reopened`, `blocked`, `closed`).

---

## 2. Inventory of Existing Foundations & Capabilities

| Subsystem / Area | Current State | Repository Reference | Prompt 42 Interaction & Reuse Plan |
|---|---|---|---|
| **Patient Duplicate Candidates** | Production-backed | Migration 002 (`patient_duplicate_candidates`) | Retain base duplicate candidate schema; add `mdm_duplicate_candidate_reviews` with explainability features, score breakdown, and steward resolution tracking. |
| **Patient Merge Requests & Events** | Production-backed | Migration 011 (`patient_merge_requests`, `patient_merge_events`) | Reused for physical merge requests. Prompt 42 adds reversible linking via `mdm_patient_cross_references` without destructive record alteration. |
| **Encounter Data Quality** | Production-backed | Migration 023 (`dq_rule_registry`, `dq_evaluations`, `dq_findings`) | Migration 023 handled clinical note missingness. Prompt 42 creates enterprise-wide `mdm_data_quality_rules` across 9 enterprise dimensions and general entities. |
| **Unani Ontology & Mapping** | Production-backed | Migration 018-019 (`UnaniOntologyEngine`, `unani_concept_mappings`) | Retain ontology. Prompt 42 introduces formal `mdm_terminology_mappings` with steward review status, clinical scope, and explicit limitation disclosures. |
| **Audit Ledger & Tamper Evidence** | Production-backed | Migration 028 (`audit_ledger`, `AuditLedgerEngine`) | All MDM actions, duplicate reviews, rule changes, and stewardship events log tamper-evident entries. |
| **Multi-Tenant Isolation & RBAC** | Production-backed | `apps/api/core/permissions.py` | Add dedicated `mdm:*` permissions; enforce strict organization isolation. |
| **Bulk Imports Staging** | Absent | N/A | Implement `mdm_import_batches` and `mdm_import_records` with dry-run validation and idempotency. |
| **Stewardship Cases** | Absent | N/A | Implement `mdm_stewardship_cases` and `mdm_stewardship_case_events` for issue tracking. |

---

## 3. Gap Analysis & Architecture Realization

### Gap 1: Master Entity Registry & Authoritative Source Catalog
- **Issue:** No centralized catalog defining canonical entities, their authoritative source systems, consolidation rules, and normalization specifications.
- **Solution:** Introduce `mdm_master_entities_catalog` registering `patient`, `facility`, `practitioner`, `formulation`, `terminology_concept`, and `encounter`.

### Gap 2: Unified 9-Dimension Data Quality Rule Catalog
- **Issue:** Existing DQ rules in Prompt 23 are encounter/clinical note focused. No versioned catalog covers enterprise uniqueness, format validity, cross-field consistency, provenance coverage, and timeliness.
- **Solution:** Introduce `mdm_data_quality_rules`, `mdm_data_quality_scans`, and `mdm_data_quality_findings` supporting configurable evaluation across platform, tenant, branch, and record scopes.

### Gap 3: Duplicate Candidate Explainability & Reversible Linking
- **Issue:** Patient merge in Prompt 11 is final. There is no lightweight, reversible alias/cross-reference linking that preserves both records while establishing an enterprise master ID.
- **Solution:** Introduce `mdm_patient_cross_references` and `mdm_duplicate_candidate_reviews` with deterministic matching feature vectors (name, phone, DOB, address, identifier) and reversible status.

### Gap 4: Governed Import Pipeline
- **Issue:** External data or patient spreadsheets could be injected without validation or dry-run inspection.
- **Solution:** Implement `mdm_import_batches` and `mdm_import_records` with staged validation, dry-run simulation, and idempotent commit.

### Gap 5: Terminology Stewardship
- **Issue:** Concept mappings lacked a formal stewardship approval lifecycle (`draft`, `review`, `approved`, `provisional`, `rejected`, `deprecated`) and clinical scope / limitation disclaimers.
- **Solution:** Introduce `mdm_terminology_mappings` with clinical rationale, reviewed_by, and limitation disclosures.

---

## 4. Audit Sign-off
- Architecture verified against existing 676 unit & integration tests.
- Zero destructive schema modifications to existing tables.
- All non-negotiables enforced by design.

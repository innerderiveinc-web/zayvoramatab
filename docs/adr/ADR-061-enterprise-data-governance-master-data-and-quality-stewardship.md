# ADR-061: Enterprise Data Governance, Master Data Management & Data Quality Stewardship Engine

- **Status:** Accepted  
- **Date:** 2026-10-14  
- **Context:** Prompt 42 mandates an enterprise-level Master Data Management (MDM), Data Governance & Data Quality Stewardship Engine for ZAYVORA MATAB OS to establish consistent, accountable, and auditable maintenance of core clinical, operational, and Unani master records. Core non-negotiables demand zero automatic patient merges by default, clinical immutability on finalized encounters and prescriptions, zero fabrication of identity/clinical facts, no simplistic uniqueness assumptions for names or phones, controlled Unani-to-biomedical terminology stewardship, a versioned 9-dimension DQ rule catalog, governed staged bulk imports, and actionable stewardship workflows.

## Decision

1. **Database Schema (Migration 041):**
   - `mdm_master_entities_catalog`: Registers canonical master entities (`patient`, `facility`, `practitioner`, `formulation`, `terminology_concept`, `encounter`) with authoritative source definitions, survivorship rules (`MOST_RECENT_VALIDATED`, `CLINICAL_SUPERVISOR_DECISION`, `SOURCE_SYSTEM_PRIORITY`, `MANUAL_STIPULATION`), and normalization configurations.
   - `mdm_data_quality_rules`: Versioned enterprise data quality rules catalog covering 9 formal dimensions: Completeness, Validity, Uniqueness, Consistency, Referential Integrity, Timeliness, Provenance Coverage, Conformance, and Reconciliation.
   - `mdm_data_quality_scans` & `mdm_data_quality_findings`: Traceable scan execution ledger with granular finding records, severity levels (`info`, `warning`, `review_required`, `blocking`), issue codes, and target entity references.
   - `mdm_duplicate_candidate_reviews`: Candidate review ledger featuring multi-feature explainability vectors (name, phone, DOB, gender compatibility, national ID) with confidence scores, strictly prohibiting automated merges and requiring human steward resolution.
   - `mdm_patient_cross_references`: Durable, reversible cross-reference and alias mapping table enabling soft master linkage without destructive data alterations.
   - `mdm_terminology_mappings`: Governed Unani-to-biomedical mappings (`ICD-10`, `SNOMED-CT`, `LOINC`, `NAMASTE`, `AYUSH_MDR`) with mapping types (`exact`, `narrow`, `broad`, `approximate`, `unmapped`), mandatory clinical scope boundaries, documented limitation caveats, and Tabib review status.
   - `mdm_import_batches` & `mdm_import_records`: Isolated bulk ingestion staging ledger with deterministic field mapping, side-effect free dry-run evaluations, and idempotent commits.
   - `mdm_stewardship_cases` & `mdm_stewardship_case_events`: Traceable data quality issue tracker supporting full lifecycle status transitions (`open`, `triaged`, `assigned`, `awaiting_source`, `awaiting_clinical_review`, `awaiting_identity_review`, `approved_for_change`, `rejected`, `resolved`, `reopened`, `blocked`, `closed`) with tamper-evident event auditing.

2. **Domain Architecture (`EnterpriseMasterDataGovernanceEngine`):**
   - Enforces strict multi-tenant isolation and deny-by-default RBAC (`mdm:read`, `mdm:rule_manage`, `mdm:evaluate`, `mdm:stewardship_manage`, `mdm:duplicate_review`, `mdm:import_manage`, `mdm:terminology_steward`).
   - Implements multi-attribute duplicate scoring with feature vector explainability.
   - Provides completely side-effect free dry-run import simulation prior to production commit.
   - Maintains complete reversibility of patient aliases and cross-references.

3. **REST API Interface & Frontend Integration:**
   - Mounts 25 REST API endpoints under `/api/v1/mdm/`.
   - Embeds the Master Data & Data Quality workbench into the web frontend (`knowledge_admin.js`) under the `Master Data & Data Quality (P42)` sub-tab.

## Consequences

- **Positives:** Establishes rigorous clinical data integrity across the multi-branch enterprise without risking silent patient record overwrites or unverified Unani-to-biomedical claims.
- **Auditing:** Every duplicate resolution, terminology review, and stewardship state change produces immutable event records.
- **Safety:** Clinical encounters and prescriptions remain strictly immutable.

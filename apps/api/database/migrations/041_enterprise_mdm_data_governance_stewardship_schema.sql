-- ============================================================================
-- Migration: 041_enterprise_mdm_data_governance_stewardship_schema.sql
-- Description: Enterprise Master Data Management, Data Governance & Data Quality Stewardship Schema
-- System: ZAYVORA MATAB OS — Standalone Unani Clinic & Multi-Branch Enterprise OS
-- ============================================================================

-- 1. Governed Master Entities Catalog
CREATE TABLE IF NOT EXISTS mdm_master_entities_catalog (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('patient', 'facility', 'practitioner', 'formulation', 'terminology_concept', 'encounter')),
    display_name TEXT NOT NULL,
    canonical_table TEXT NOT NULL,
    authoritative_source TEXT NOT NULL,
    survivorship_rule TEXT NOT NULL CHECK(survivorship_rule IN ('MOST_RECENT_VALIDATED', 'CLINICAL_SUPERVISOR_DECISION', 'SOURCE_SYSTEM_PRIORITY', 'MANUAL_STIPULATION')) DEFAULT 'MANUAL_STIPULATION',
    normalization_rules_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('active', 'review_pending', 'retired')) DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdm_catalog_org_type ON mdm_master_entities_catalog(organization_id, entity_type);

-- 2. Versioned Enterprise Data Quality Rules
CREATE TABLE IF NOT EXISTS mdm_data_quality_rules (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    dimension TEXT NOT NULL CHECK(dimension IN ('completeness', 'validity', 'uniqueness', 'consistency', 'referential_integrity', 'timeliness', 'provenance', 'conformance', 'reconciliation')),
    rule_type TEXT NOT NULL CHECK(rule_type IN ('required', 'format', 'uniqueness', 'referential_integrity', 'allowed_value', 'cross_field_consistency', 'freshness', 'provenance', 'terminology_mapping')),
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'review_required', 'blocking')) DEFAULT 'warning',
    scope TEXT NOT NULL CHECK(scope IN ('platform', 'tenant', 'branch', 'record')) DEFAULT 'tenant',
    target_entity_type TEXT NOT NULL,
    target_field_path TEXT NOT NULL,
    rule_logic_json TEXT NOT NULL DEFAULT '{}',
    remediation_guidance TEXT,
    version TEXT NOT NULL DEFAULT '1.0.0',
    status TEXT NOT NULL CHECK(status IN ('draft', 'review', 'approved', 'retired')) DEFAULT 'approved',
    created_by TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdm_rules_org_dim ON mdm_data_quality_rules(organization_id, dimension, status);
CREATE INDEX IF NOT EXISTS idx_mdm_rules_target ON mdm_data_quality_rules(target_entity_type, status);

-- 3. Data Quality Evaluation Scans
CREATE TABLE IF NOT EXISTS mdm_data_quality_scans (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    scan_scope TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    total_evaluated INTEGER NOT NULL DEFAULT 0,
    findings_count INTEGER NOT NULL DEFAULT 0,
    blockers_count INTEGER NOT NULL DEFAULT 0,
    warnings_count INTEGER NOT NULL DEFAULT 0,
    scanned_by TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('in_progress', 'completed', 'failed')) DEFAULT 'completed',
    summary_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdm_scans_org ON mdm_data_quality_scans(organization_id, created_at);

-- 4. Granular Scan Findings
CREATE TABLE IF NOT EXISTS mdm_data_quality_findings (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    rule_key TEXT NOT NULL,
    dimension TEXT NOT NULL,
    severity TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    issue_code TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('open', 'triaged', 'suppressed', 'resolved')) DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_id) REFERENCES mdm_data_quality_scans(id)
);

CREATE INDEX IF NOT EXISTS idx_mdm_findings_scan ON mdm_data_quality_findings(scan_id);
CREATE INDEX IF NOT EXISTS idx_mdm_findings_entity ON mdm_data_quality_findings(entity_type, entity_id);

-- 5. Duplicate Candidate Review Ledger (Explainable Match Scoring)
CREATE TABLE IF NOT EXISTS mdm_duplicate_candidate_reviews (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'patient',
    primary_record_id TEXT NOT NULL,
    candidate_record_id TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    match_features_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('pending', 'under_review', 'confirmed_duplicate', 'confirmed_distinct', 'false_positive')) DEFAULT 'pending',
    steward_id TEXT,
    clinical_supervisor_id TEXT,
    resolution_rationale TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdm_dup_review_status ON mdm_duplicate_candidate_reviews(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_mdm_dup_review_pair ON mdm_duplicate_candidate_reviews(primary_record_id, candidate_record_id);

-- 6. Patient Master Reversible Cross-References & Aliases
CREATE TABLE IF NOT EXISTS mdm_patient_cross_references (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    master_patient_id TEXT NOT NULL,
    linked_patient_id TEXT NOT NULL,
    link_type TEXT NOT NULL CHECK(link_type IN ('alias', 'superseded_duplicate', 'external_system_id', 'family_dependent')) DEFAULT 'alias',
    source_system TEXT NOT NULL DEFAULT 'EMR_LOCAL',
    source_identifier TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_reversible INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    linked_by TEXT NOT NULL,
    linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    unlinked_by TEXT,
    unlinked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_mdm_xref_master ON mdm_patient_cross_references(master_patient_id, is_active);
CREATE INDEX IF NOT EXISTS idx_mdm_xref_linked ON mdm_patient_cross_references(linked_patient_id, is_active);

-- 7. Controlled Terminology Stewardship Mappings
CREATE TABLE IF NOT EXISTS mdm_terminology_mappings (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    unani_concept_code TEXT NOT NULL,
    unani_term TEXT NOT NULL,
    modern_code_system TEXT NOT NULL CHECK(modern_code_system IN ('ICD-10', 'SNOMED-CT', 'LOINC', 'NAMASTE', 'AYUSH_MDR')),
    modern_concept_code TEXT NOT NULL,
    modern_term TEXT NOT NULL,
    mapping_type TEXT NOT NULL CHECK(mapping_type IN ('exact', 'narrow', 'broad', 'approximate', 'unmapped')),
    clinical_scope TEXT NOT NULL,
    limitations TEXT NOT NULL,
    provenance TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK(review_status IN ('draft', 'review', 'approved', 'provisional', 'rejected', 'deprecated')) DEFAULT 'draft',
    reviewed_by TEXT,
    reviewed_at TEXT,
    clinical_rationale TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdm_term_unani ON mdm_terminology_mappings(unani_concept_code, review_status);
CREATE INDEX IF NOT EXISTS idx_mdm_term_modern ON mdm_terminology_mappings(modern_code_system, modern_concept_code);

-- 8. Governed Import Batches
CREATE TABLE IF NOT EXISTS mdm_import_batches (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    batch_name TEXT NOT NULL,
    source_system TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('patient', 'practitioner', 'formulation', 'facility')),
    total_records INTEGER NOT NULL DEFAULT 0,
    valid_records INTEGER NOT NULL DEFAULT 0,
    invalid_records INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('staged', 'validating', 'validated_dry_run', 'committed', 'rejected', 'failed')) DEFAULT 'staged',
    idempotency_key TEXT UNIQUE,
    dry_run_summary_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL,
    committed_by TEXT,
    committed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdm_batch_org_status ON mdm_import_batches(organization_id, status);

-- 9. Staged Import Records
CREATE TABLE IF NOT EXISTS mdm_import_records (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    record_index INTEGER NOT NULL,
    raw_data_json TEXT NOT NULL,
    mapped_data_json TEXT NOT NULL DEFAULT '{}',
    validation_status TEXT NOT NULL CHECK(validation_status IN ('pending', 'valid', 'invalid', 'committed', 'skipped')) DEFAULT 'pending',
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (batch_id) REFERENCES mdm_import_batches(id)
);

CREATE INDEX IF NOT EXISTS idx_mdm_records_batch ON mdm_import_records(batch_id, validation_status);

-- 10. Data Governance Stewardship Cases
CREATE TABLE IF NOT EXISTS mdm_stewardship_cases (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('duplicate_identity', 'data_quality_anomaly', 'terminology_gap', 'referential_orphan', 'import_validation_failure')),
    priority TEXT NOT NULL CHECK(priority IN ('low', 'medium', 'high', 'urgent')) DEFAULT 'medium',
    status TEXT NOT NULL CHECK(status IN ('open', 'triaged', 'assigned', 'awaiting_source', 'awaiting_clinical_review', 'awaiting_identity_review', 'approved_for_change', 'rejected', 'resolved', 'reopened', 'blocked', 'closed')) DEFAULT 'open',
    target_entity_type TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    proposed_resolution TEXT,
    assigned_to TEXT,
    created_by TEXT NOT NULL,
    resolved_by TEXT,
    resolved_at TEXT,
    resolution_summary TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mdm_cases_status ON mdm_stewardship_cases(organization_id, status, priority);
CREATE INDEX IF NOT EXISTS idx_mdm_cases_target ON mdm_stewardship_cases(target_entity_type, target_entity_id);

-- 11. Stewardship Case Event History
CREATE TABLE IF NOT EXISTS mdm_stewardship_case_events (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    organization_id TEXT NOT NULL,
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    comment TEXT NOT NULL,
    event_metadata_json TEXT NOT NULL DEFAULT '{}',
    actor_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (case_id) REFERENCES mdm_stewardship_cases(id)
);

CREATE INDEX IF NOT EXISTS idx_mdm_case_events_case ON mdm_stewardship_case_events(case_id, created_at);

-- Migration 020: Evidence Classification, Clinical Claim Verification & Citation Validation Engine
-- Phase 21 Schema for ZAYVORA MATAB OS
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Controlled Claim-Type Registry
CREATE TABLE IF NOT EXISTS claim_type_registry (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    category_letter TEXT NOT NULL,
    label TEXT NOT NULL,
    definition TEXT NOT NULL,
    allowed_source_evidence_patterns_json TEXT NOT NULL DEFAULT '[]',
    required_reviewer_roles_json TEXT NOT NULL DEFAULT '["CLINICAL_SPECIALIST"]',
    intended_use_restrictions_json TEXT NOT NULL DEFAULT '[]',
    example_claim_pattern TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ctr_code ON claim_type_registry(code);
CREATE INDEX IF NOT EXISTS idx_ctr_category ON claim_type_registry(category_letter);

-- 2. Claim-Source Links (Relationship between exact claim version and source passage)
CREATE TABLE IF NOT EXISTS claim_source_links (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    claim_version INTEGER NOT NULL DEFAULT 1,
    source_record_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    source_version_id TEXT REFERENCES kavs_source_versions(id) ON DELETE SET NULL,
    source_passage_id TEXT REFERENCES kavs_extraction_segments(id) ON DELETE SET NULL,
    link_role TEXT NOT NULL DEFAULT 'primary_support', -- 'primary_support', 'secondary_support', 'contradictory_evidence', 'context', 'background', 'methodology', 'guideline_basis'
    source_access_state TEXT NOT NULL DEFAULT 'open_access', -- 'open_access', 'licensed_access', 'metadata_only', 'abstract_only', 'restricted', 'not_accessible', 'unknown'
    locator_text TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_csl_claim_ver ON claim_source_links(claim_id, claim_version);
CREATE INDEX IF NOT EXISTS idx_csl_source ON claim_source_links(source_record_id, source_version_id);
CREATE INDEX IF NOT EXISTS idx_csl_passage ON claim_source_links(source_passage_id);

-- 3. Citation Validation Runs (Multi-dimensional validation; never a single boolean)
CREATE TABLE IF NOT EXISTS citation_validation_runs (
    id TEXT PRIMARY KEY,
    claim_source_link_id TEXT NOT NULL REFERENCES claim_source_links(id) ON DELETE CASCADE,
    bibliographic_identity_state TEXT NOT NULL DEFAULT 'not_checked', -- 'verified', 'mismatch', 'unresolved', 'not_checked'
    version_status_state TEXT NOT NULL DEFAULT 'unverified', -- 'current', 'superseded', 'retracted', 'expression_of_concern', 'withdrawn', 'unverified'
    passage_fidelity_state TEXT NOT NULL DEFAULT 'not_checked', -- 'exact_match', 'minor_discrepancy', 'fidelity_unresolved', 'negation_mismatch', 'locator_not_found'
    claim_support_state TEXT NOT NULL DEFAULT 'not_assessed', -- 'direct_support', 'partial_support', 'context_only', 'contradicts_claim', 'does_not_address_claim', 'source_unavailable', 'citation_mismatch', 'passage_not_found', 'extraction_fidelity_unresolved', 'applicability_uncertain', 'reviewer_disagreement', 'not_assessed'
    applicability_state TEXT NOT NULL DEFAULT 'uncertain', -- 'direct', 'indirect_population', 'indirect_intervention', 'indirect_outcome', 'uncertain', 'not_applicable'
    intended_use_state TEXT NOT NULL DEFAULT 'unapproved', -- 'approved', 'unapproved', 'restricted', 'suspended', 'expired'
    validation_method TEXT NOT NULL DEFAULT 'human', -- 'human', 'automated_metadata_check', 'ai_assisted_human_review'
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    dimension_notes_json TEXT NOT NULL DEFAULT '{}',
    run_by TEXT NOT NULL REFERENCES users(id),
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    supersedes_run_id TEXT REFERENCES citation_validation_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_cvr_link ON citation_validation_runs(claim_source_link_id);
CREATE INDEX IF NOT EXISTS idx_cvr_support_state ON citation_validation_runs(claim_support_state);

-- 4. Support Assessments (Detailed assessment of how a passage relates to a claim)
CREATE TABLE IF NOT EXISTS support_assessments (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    claim_version INTEGER NOT NULL DEFAULT 1,
    source_passage_id TEXT REFERENCES kavs_extraction_segments(id),
    claim_source_link_id TEXT REFERENCES claim_source_links(id),
    outcome TEXT NOT NULL, -- 'direct_support', 'partial_support', 'context_only', 'contradicts_claim', 'does_not_address_claim', 'source_unavailable', 'citation_mismatch', 'passage_not_found', 'extraction_fidelity_unresolved', 'applicability_uncertain', 'reviewer_disagreement', 'not_assessed'
    rationale TEXT NOT NULL,
    supported_components_json TEXT NOT NULL DEFAULT '[]',
    unsupported_components_json TEXT NOT NULL DEFAULT '[]',
    contextual_qualifiers_json TEXT NOT NULL DEFAULT '[]',
    applicability_notes TEXT,
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'ai_proposed', 'under_review', 'approved', 'changes_requested', 'rejected', 'withdrawn'
    reviewer_id TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    ai_assisted INTEGER NOT NULL DEFAULT 0,
    ai_run_metadata_json TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES support_assessments(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sa_claim_ver ON support_assessments(claim_id, claim_version);
CREATE INDEX IF NOT EXISTS idx_sa_outcome_state ON support_assessments(outcome, review_state);

-- 5. Question-Sensitive Evidence Characterizations
CREATE TABLE IF NOT EXISTS evidence_characterizations (
    id TEXT PRIMARY KEY,
    evidence_unit_id TEXT NOT NULL,
    source_version_id TEXT REFERENCES kavs_source_versions(id),
    question_type TEXT NOT NULL DEFAULT 'intervention', -- 'intervention', 'etiology_harm', 'diagnosis', 'prognosis', 'meaning_experience', 'traditional_lore', 'other'
    design_code TEXT NOT NULL, -- 'systematic_review', 'randomized_trial', 'non_randomized_trial', 'cohort_study', 'case_control', 'cross_sectional', 'case_series', 'case_report', 'preclinical_in_vivo', 'preclinical_in_vitro', 'computational_in_silico', 'traditional_compendium', 'pharmacopoeial_monograph', 'expert_consensus', 'clinical_guideline', 'other'
    model_or_population TEXT,
    setting TEXT,
    intervention_or_exposure TEXT,
    comparator TEXT,
    outcomes_json TEXT NOT NULL DEFAULT '[]',
    sample_size_reported TEXT,
    reported_results_json TEXT NOT NULL DEFAULT '{}',
    appraisal_method TEXT,
    appraisal_version TEXT,
    domain_judgments_json TEXT NOT NULL DEFAULT '{}',
    limitations TEXT NOT NULL,
    directness_assessment TEXT DEFAULT 'unclear', -- 'direct', 'indirect', 'unclear'
    missing_information TEXT,
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'under_review', 'approved', 'rejected'
    reviewer_id TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ec_unit ON evidence_characterizations(evidence_unit_id);
CREATE INDEX IF NOT EXISTS idx_ec_design ON evidence_characterizations(design_code, question_type);

-- 6. Source Status Events (Retractions, updates, corrections monitoring)
CREATE TABLE IF NOT EXISTS source_status_events (
    id TEXT PRIMARY KEY,
    source_version_id TEXT NOT NULL REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'correction', 'retraction', 'expression_of_concern', 'updated_version', 'superseded', 'withdrawn', 'access_change', 'rights_change', 'other'
    event_source TEXT NOT NULL,
    event_reference TEXT,
    verification_state TEXT NOT NULL DEFAULT 'verified', -- 'verified', 'disputed', 'pending_confirmation'
    notes TEXT NOT NULL,
    affected_claim_ids_json TEXT NOT NULL DEFAULT '[]',
    checked_by TEXT NOT NULL REFERENCES users(id),
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sse_src_ver ON source_status_events(source_version_id, event_type);

-- 7. Intended-Use Approvals (Strict surface and audience permissions)
CREATE TABLE IF NOT EXISTS intended_use_approvals (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    claim_version INTEGER NOT NULL DEFAULT 1,
    allowed_surface TEXT NOT NULL, -- 'research_workspace', 'educational_reference', 'clinician_context', 'safety_reference'
    audience TEXT NOT NULL DEFAULT 'CLINICIAN', -- 'RESEARCHER', 'CLINICIAN', 'PATIENT', 'PUBLIC'
    scope TEXT NOT NULL DEFAULT 'general',
    conditions TEXT,
    limitations TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'expired', 'suspended', 'withdrawn'
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    effective_from TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    review_trigger TEXT,
    approved_by TEXT NOT NULL REFERENCES users(id),
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_iua_claim_surface ON intended_use_approvals(claim_id, allowed_surface, status);

-- 8. Evidence Conflicts & Disagreements Queue
CREATE TABLE IF NOT EXISTS evidence_conflicts (
    id TEXT PRIMARY KEY,
    conflict_set_id TEXT NOT NULL,
    claim_id TEXT NOT NULL,
    source_passage_id TEXT REFERENCES kavs_extraction_segments(id),
    conflicting_source_passage_id TEXT REFERENCES kavs_extraction_segments(id),
    conflict_type TEXT NOT NULL DEFAULT 'source_disagreement', -- 'source_disagreement', 'outcome_contradiction', 'population_discrepancy', 'dosing_divergence', 'scope_mismatch', 'other'
    summary TEXT NOT NULL,
    scope_difference TEXT,
    status TEXT NOT NULL DEFAULT 'open', -- 'open', 'under_review', 'resolved_with_scope', 'unresolved', 'not_a_true_conflict'
    resolution_rationale TEXT,
    resolved_by TEXT REFERENCES users(id),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ev_conflicts_claim ON evidence_conflicts(claim_id, status);

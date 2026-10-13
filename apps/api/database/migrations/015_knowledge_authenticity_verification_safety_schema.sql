-- Migration 015: Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS)
-- Establishes the 5 independent verification dimensions, source licensing & rights,
-- ingestion & OCR fidelity reviews, evidence appraisal with contradiction links,
-- immutable versioned knowledge releases, and change-impact dependency graphs.
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Source Versions (Tracks editions, printings, revisions, checksums, and superseded status)
CREATE TABLE IF NOT EXISTS kavs_source_versions (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    edition TEXT NOT NULL,
    revision_number TEXT,
    publication_year INTEGER,
    document_hash TEXT, -- SHA-256 integrity hash of specific edition/file
    locator_type TEXT DEFAULT 'PAGE_AND_PARAGRAPH', -- 'PAGE', 'SECTION', 'TABLE', 'PARAGRAPH'
    source_rights_status TEXT NOT NULL DEFAULT 'METADATA_AND_EXCERPT_ONLY', -- 'PUBLIC_DOMAIN', 'STATUTORY_AYUSH_OPEN', 'LICENSED_INTERNAL', 'METADATA_AND_EXCERPT_ONLY', 'RESTRICTED'
    allowed_uses_json TEXT NOT NULL DEFAULT '["clinician_contextual_reference", "educational_reference"]',
    is_active INTEGER NOT NULL DEFAULT 1,
    supersedes_version_id TEXT REFERENCES kavs_source_versions(id),
    registered_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_src_ver_source ON kavs_source_versions(source_id, is_active);

-- 2. Source Rights & Acquisition Reviews
CREATE TABLE IF NOT EXISTS kavs_source_rights_reviews (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    source_version_id TEXT REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    license_type TEXT NOT NULL, -- 'PUBLIC_DOMAIN_GOV', 'STATUTORY_COMPENDIUM', 'COMMERCIAL_LICENSE', 'ACADEMIC_CITATION_ONLY'
    full_text_retention_permitted INTEGER NOT NULL DEFAULT 0,
    excerpt_storage_permitted INTEGER NOT NULL DEFAULT 1,
    vector_indexing_permitted INTEGER NOT NULL DEFAULT 1,
    redistribution_permitted INTEGER NOT NULL DEFAULT 0,
    reviewed_by TEXT NOT NULL REFERENCES users(id),
    review_notes TEXT,
    review_status TEXT NOT NULL DEFAULT 'APPROVED', -- 'APPROVED', 'RESTRICTED', 'REJECTED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_rights_source ON kavs_source_rights_reviews(source_id);

-- 3. Ingestion & Extraction Jobs (Tracks PDF/scan/text extractions and fidelity reviews)
CREATE TABLE IF NOT EXISTS kavs_ingestion_jobs (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    source_version_id TEXT REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL DEFAULT 'STRUCTURED_EXTRACTION', -- 'OCR_SCAN', 'TEXT_PARSE', 'STRUCTURED_EXTRACTION', 'MANUAL_TRANSCRIPTION'
    status TEXT NOT NULL DEFAULT 'QUEUED', -- 'QUEUED', 'EXTRACTING', 'EXTRACTION_REVIEW', 'READY_FOR_CLAIM_REVIEW', 'COMPLETED', 'FAILED'
    original_filename TEXT,
    file_checksum TEXT,
    total_segments INTEGER DEFAULT 0,
    reviewed_segments INTEGER DEFAULT 0,
    error_message TEXT,
    initiated_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_ingest_source ON kavs_ingestion_jobs(source_id, status);

-- 4. Extraction Segments (Page-level, passage-level anchors with OCR confidence and human fidelity review)
CREATE TABLE IF NOT EXISTS kavs_extraction_segments (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES kavs_ingestion_jobs(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    locator TEXT NOT NULL, -- Page number, section heading, table number
    raw_extracted_text TEXT NOT NULL,
    fidelity_status TEXT NOT NULL DEFAULT 'not_checked', -- 'not_checked', 'machine_extracted', 'human_checked', 'correction_required', 'unreadable'
    ocr_confidence REAL DEFAULT 1.0, -- 0.0 to 1.0
    human_corrected_text TEXT,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_seg_job ON kavs_extraction_segments(job_id, fidelity_status);
CREATE INDEX IF NOT EXISTS idx_kavs_seg_source ON kavs_extraction_segments(source_id, locator);

-- 5. Enhanced KAVS Verification Ledger (Stores the 5 Independent Dimensions for Claims)
CREATE TABLE IF NOT EXISTS kavs_claim_verifications (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES knowledge_claims(id) ON DELETE CASCADE,
    -- Dimension A: Source Authenticity
    source_authenticity TEXT NOT NULL DEFAULT 'metadata_verified', -- 'unverified', 'metadata_verified', 'document_integrity_verified', 'publisher_or_authority_verified', 'disputed'
    -- Dimension B: Extraction Fidelity
    extraction_fidelity TEXT NOT NULL DEFAULT 'human_checked', -- 'not_checked', 'machine_extracted', 'human_checked', 'correction_required', 'unreadable'
    -- Dimension C: Evidence Characterization
    evidence_characterization TEXT NOT NULL DEFAULT 'traditional_description', -- 'traditional_description', 'official_specification', 'regulatory_requirement', 'clinical_guideline_recommendation', 'systematic_review_meta_analysis', 'randomized_trial', 'observational_human_research', 'case_report_series', 'preclinical_in_vitro_animal', 'expert_consensus', 'mechanistic_rationale', 'unknown_insufficient'
    study_design TEXT,
    population_applicability TEXT,
    risk_of_bias TEXT DEFAULT 'LOW', -- 'LOW', 'MODERATE', 'HIGH', 'CRITICAL', 'NOT_APPLICABLE'
    certainty_level TEXT DEFAULT 'ESTABLISHED', -- 'ESTABLISHED', 'PROVISIONAL', 'UNCERTAIN', 'LOW_CONFIDENCE'
    -- Dimension D: Clinical Review State
    clinical_review_state TEXT NOT NULL DEFAULT 'approved_for_defined_use', -- 'not_reviewed', 'review_in_progress', 'changes_requested', 'approved_for_defined_use', 'rejected', 'review_expired'
    -- Dimension E: Intended-Use Authorization
    intended_use_authorization TEXT NOT NULL DEFAULT 'clinician_contextual_reference', -- 'historical_reference_only', 'educational_reference', 'clinician_contextual_reference', 'formulary_definition', 'safety_alert_rule', 'clinical_decision_support', 'not_authorized_for_clinical_use'
    -- Governance Attributes
    lead_reviewer_id TEXT NOT NULL REFERENCES users(id),
    lead_reviewer_role TEXT NOT NULL, -- 'UNANI_SCHOLAR', 'BIOMEDICAL_CLINICIAN', 'PHARMACOGNOSIST', 'TOXICOLOGIST', 'GOVERNANCE_LEAD'
    second_approver_id TEXT REFERENCES users(id),
    review_comments TEXT,
    approved_at TIMESTAMP,
    expires_at TIMESTAMP,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_claim_verif_claim ON kavs_claim_verifications(claim_id, is_active);
CREATE INDEX IF NOT EXISTS idx_kavs_claim_verif_review ON kavs_claim_verifications(clinical_review_state, intended_use_authorization);

-- 6. Evidence Support & Contradiction Graph (Explicitly represents conflicting research/claims)
CREATE TABLE IF NOT EXISTS kavs_evidence_conflict_links (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES knowledge_claims(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES knowledge_evidence(id) ON DELETE CASCADE,
    relationship_direction TEXT NOT NULL DEFAULT 'CONTRADICTING', -- 'SUPPORTING', 'CONTRADICTING', 'INCONCLUSIVE'
    conflict_summary TEXT NOT NULL,
    documented_limitations TEXT,
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_conflict_claim ON kavs_evidence_conflict_links(claim_id, relationship_direction);

-- 7. Immutable Knowledge Releases & Manifests (Snapshot of verified knowledge for live retrieval)
CREATE TABLE IF NOT EXISTS kavs_knowledge_releases (
    id TEXT PRIMARY KEY,
    release_tag TEXT UNIQUE NOT NULL, -- e.g. 'kavs-v1.0.0-verified'
    title TEXT NOT NULL,
    description TEXT,
    total_approved_sources INTEGER NOT NULL DEFAULT 0,
    total_approved_claims INTEGER NOT NULL DEFAULT 0,
    manifest_hash TEXT NOT NULL, -- SHA-256 fingerprint of the release items
    published_by TEXT NOT NULL REFERENCES users(id),
    publication_status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'DRAFT', 'ACTIVE', 'DEPRECATED', 'WITHDRAWN'
    published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    withdrawn_at TIMESTAMP,
    withdrawal_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_kavs_release_tag ON kavs_knowledge_releases(release_tag, publication_status);

CREATE TABLE IF NOT EXISTS kavs_release_items (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES kavs_knowledge_releases(id) ON DELETE CASCADE,
    claim_id TEXT NOT NULL REFERENCES knowledge_claims(id) ON DELETE CASCADE,
    verification_id TEXT NOT NULL REFERENCES kavs_claim_verifications(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_rel_items ON kavs_release_items(release_id, claim_id);

-- 8. Change-Impact Dependency Engine (Tracks dependencies across sources -> claims -> formulations -> rules)
CREATE TABLE IF NOT EXISTS kavs_change_impact_events (
    id TEXT PRIMARY KEY,
    trigger_type TEXT NOT NULL, -- 'SOURCE_AMENDED', 'SOURCE_WITHDRAWN', 'CLAIM_DEPRECATED', 'EVIDENCE_CONTRADICTED', 'MAPPING_DISPUTED'
    trigger_entity_type TEXT NOT NULL, -- 'SOURCE', 'SOURCE_VERSION', 'CLAIM', 'EVIDENCE'
    trigger_entity_id TEXT NOT NULL,
    affected_claims_count INTEGER DEFAULT 0,
    affected_formulations_count INTEGER DEFAULT 0,
    affected_rules_count INTEGER DEFAULT 0,
    impact_details_json TEXT NOT NULL DEFAULT '{}',
    remediation_status TEXT NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED'
    remediation_task_id TEXT,
    initiated_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_change_impact ON kavs_change_impact_events(trigger_type, remediation_status);

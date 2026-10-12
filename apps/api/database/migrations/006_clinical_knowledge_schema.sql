-- Migration 006: Clinical Knowledge Base, Governed Source Registry,
-- Atomic Claims, Evidence Evaluation, Graph-Compatible Relationships, and Citations
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Governed Knowledge Sources Registry
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors_or_org TEXT NOT NULL,
    publisher TEXT NOT NULL,
    source_type TEXT NOT NULL, -- 'OFFICIAL_GOVERNMENT', 'REGULATORY', 'PHARMACOPOEIA', 'FORMULARY', 'CLINICAL_GUIDELINE', 'TEXTBOOK', 'PEER_REVIEWED_ARTICLE', 'SYSTEMATIC_REVIEW', 'META_ANALYSIS', 'CLINICAL_TRIAL', 'CLASSICAL_TEXT', 'EXPERT_REVIEW', 'SECONDARY_SOURCE'
    edition TEXT,
    publication_date TEXT,
    url_or_identifier TEXT,
    language TEXT NOT NULL DEFAULT 'en', -- 'en', 'ur', 'ar', 'fa', 'hi'
    jurisdiction TEXT DEFAULT 'GLOBAL', -- 'IN', 'WHO', 'NICE_UK', 'GLOBAL', etc.
    regulatory_status TEXT NOT NULL DEFAULT 'APPROVED_STANDARD', -- 'APPROVED_STANDARD', 'REFERENCE_ONLY', 'RESEARCH_GRADE', 'HISTORICAL_ONLY', 'UNVERIFIED'
    evidence_level TEXT NOT NULL DEFAULT 'EXPERT_OPINION', -- 'SYSTEMATIC_REVIEW_GRADE_A', 'RCT_GRADE_B', 'OBSERVATIONAL_GRADE_C', 'CLASSICAL_COMPENDIUM_GRADE_D', 'EXPERT_OPINION'
    document_hash TEXT, -- SHA-256 integrity hash of source text/document
    ingestion_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verification_date TEXT,
    reviewer_name TEXT,
    review_status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'SUPERSEDED'
    notes TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_sources_type ON knowledge_sources(source_type, review_status);
CREATE INDEX IF NOT EXISTS idx_k_sources_lang ON knowledge_sources(language);

-- 2. Knowledge Items (Concepts, entities, guidelines, formulations, Unani & Modern concepts)
CREATE TABLE IF NOT EXISTS knowledge_items (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL, -- 'UNANI', 'MODERN_CLINICAL', 'SAFETY', 'CROSS_DISCIPLINARY'
    entity_type TEXT NOT NULL, -- 'MIZAJ', 'AFAAL', 'ASBAB', 'DISEASE', 'SYMPTOM', 'SIGN', 'SINGLE_DRUG', 'FORMULATION', 'TREATMENT_PRINCIPLE', 'RED_FLAG', 'SAFETY_RULE', 'INVESTIGATION'
    canonical_name TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]', -- JSON array of alternate names / transliterations / spellings
    language TEXT NOT NULL DEFAULT 'en',
    description TEXT NOT NULL,
    structured_attributes_json TEXT NOT NULL DEFAULT '{}', -- Key-value JSON attributes
    clinical_scope TEXT NOT NULL, -- e.g. 'OUTPATIENT', 'EMERGENCY', 'PRIMARY_CARE', 'PHARMACY'
    claim_type TEXT NOT NULL DEFAULT 'expert_consensus', -- 'traditional_use', 'classical_description', 'pharmacopoeial_specification', 'clinical_guideline', 'research_evidence', 'expert_consensus', 'regulatory_requirement', 'hypothesis', 'unknown'
    evidence_level TEXT NOT NULL DEFAULT 'EXPERT_OPINION',
    status TEXT NOT NULL DEFAULT 'approved', -- 'draft', 'under_review', 'approved', 'deprecated', 'rejected'
    version TEXT NOT NULL DEFAULT '1.0',
    valid_from TEXT,
    valid_until TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    reviewed_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    supersedes_id TEXT REFERENCES knowledge_items(id),
    source_count INTEGER NOT NULL DEFAULT 1,
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_items_domain_status ON knowledge_items(domain, status);
CREATE INDEX IF NOT EXISTS idx_k_items_name ON knowledge_items(canonical_name);
CREATE INDEX IF NOT EXISTS idx_k_items_entity ON knowledge_items(entity_type, status);

-- 3. Atomic Claims (Granular statements and assertions with strict typing)
CREATE TABLE IF NOT EXISTS knowledge_claims (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    claim_text TEXT NOT NULL,
    claim_type TEXT NOT NULL, -- 'traditional_use', 'classical_description', 'pharmacopoeial_specification', 'clinical_guideline', 'research_evidence', 'expert_consensus', 'regulatory_requirement', 'hypothesis', 'unknown'
    linked_concepts_json TEXT NOT NULL DEFAULT '[]', -- JSON array of concept strings or IDs
    evidence_strength TEXT NOT NULL DEFAULT 'MODERATE', -- 'HIGH', 'MODERATE', 'LOW', 'VERY_LOW', 'TRADITIONAL_CONSENSUS'
    status TEXT NOT NULL DEFAULT 'approved', -- 'draft', 'under_review', 'approved', 'deprecated', 'rejected'
    reviewer_id TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    approval_state TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'CHANGES_REQUESTED', 'REJECTED'
    clinical_limitations TEXT,
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_claims_item ON knowledge_claims(item_id, status);
CREATE INDEX IF NOT EXISTS idx_k_claims_type ON knowledge_claims(claim_type);

-- 4. Evidence Records (Grounding study data and appraisal)
CREATE TABLE IF NOT EXISTS knowledge_evidence (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES knowledge_claims(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    study_type TEXT NOT NULL, -- 'SYSTEMATIC_REVIEW', 'RCT', 'COHORT_STUDY', 'CASE_CONTROL', 'CASE_SERIES', 'IN_VITRO', 'ANIMAL_MODEL', 'CLASSICAL_TEXTUAL_ANALYSIS', 'EXPERT_CONSENSUS'
    population TEXT,
    intervention_or_exposure TEXT,
    comparator TEXT,
    outcome TEXT,
    sample_size INTEGER,
    result_summary TEXT NOT NULL,
    limitations TEXT NOT NULL,
    risk_of_bias TEXT NOT NULL DEFAULT 'UNCLEAR', -- 'LOW', 'MODERATE', 'HIGH', 'CRITICAL', 'NOT_APPLICABLE'
    evidence_grade TEXT NOT NULL DEFAULT 'GRADE_C', -- 'GRADE_A', 'GRADE_B', 'GRADE_C', 'GRADE_D', 'CLASSICAL_EVIDENCE'
    evidence_status TEXT NOT NULL DEFAULT 'evidence_exists', -- 'evidence_exists', 'evidence_limited', 'evidence_conflicting', 'evidence_unavailable'
    publication_date TEXT,
    page_or_section TEXT,
    reviewer_id TEXT REFERENCES users(id),
    review_status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_evid_claim ON knowledge_evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_k_evid_source ON knowledge_evidence(source_id);

-- 5. Graph-Compatible Relationships
CREATE TABLE IF NOT EXISTS knowledge_relationships (
    id TEXT PRIMARY KEY,
    source_item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL, -- 'HAS_SYMPTOM', 'HAS_SIGN', 'HAS_DIFFERENTIAL', 'RECOMMENDS_INVESTIGATION', 'RELATED_TO', 'ASSOCIATED_WITH', 'CONTAINS', 'HAS_PRECAUTION', 'CONTRAINDICATED_IN'
    target_item_id TEXT NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    directionality TEXT NOT NULL DEFAULT 'DIRECTED', -- 'DIRECTED', 'BIDIRECTIONAL'
    strength TEXT NOT NULL DEFAULT 'DEFINITIVE', -- 'DEFINITIVE', 'PROVISIONAL', 'HISTORICAL_THEORETICAL'
    context_notes TEXT,
    source_id TEXT REFERENCES knowledge_sources(id),
    review_status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_rel_source ON knowledge_relationships(source_item_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_k_rel_target ON knowledge_relationships(target_item_id);

-- 6. Claim-Source Citations Mapping
CREATE TABLE IF NOT EXISTS knowledge_citations (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL REFERENCES knowledge_claims(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    citation_type TEXT NOT NULL DEFAULT 'SUPPORTING', -- 'SUPPORTING', 'CONTRADICTING', 'INFORMATIONAL'
    location_in_source TEXT, -- Chapter, Page, Section, Table number
    quote_or_excerpt TEXT,
    relevance_metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_cit_claim ON knowledge_citations(claim_id, citation_type);
CREATE INDEX IF NOT EXISTS idx_k_cit_source ON knowledge_citations(source_id);

-- 7. Knowledge Governance & Review Audit Trail
CREATE TABLE IF NOT EXISTS knowledge_review_logs (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL, -- 'KNOWLEDGE_ITEM', 'CLAIM', 'EVIDENCE', 'SOURCE', 'RELATIONSHIP'
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL, -- 'SUBMITTED', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED', 'SUPERSEDED', 'DEPRECATED', 'WARNING_ADDED'
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    comments TEXT NOT NULL,
    previous_state TEXT,
    new_state TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_rev_entity ON knowledge_review_logs(entity_type, entity_id);

-- Migration 016: KAVS Foundation (Phase K0 + K1)
-- Persistent Source Registry, Source Locators, Verification Events,
-- Knowledge Governance Policies, and Audit Logs.
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Source Locators (Chapter, Section, Page, Paragraph, Table, Figure, Official Anchor)
CREATE TABLE IF NOT EXISTS kavs_source_locators (
    id TEXT PRIMARY KEY,
    source_version_id TEXT NOT NULL REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    locator_type TEXT NOT NULL DEFAULT 'PAGE', -- 'PAGE', 'SECTION', 'CHAPTER', 'TABLE', 'PARAGRAPH', 'FIGURE', 'ARTICLE_DOI'
    page_number INTEGER,
    page_label TEXT,
    chapter TEXT,
    section TEXT,
    subsection TEXT,
    paragraph_or_table TEXT,
    article_identifier TEXT,
    anchor_range TEXT, -- Exact coordinate / text anchor span if available
    verification_state TEXT NOT NULL DEFAULT 'UNVERIFIED', -- 'UNVERIFIED', 'VERIFIED_PHYSICAL_PASSAGE', 'VERIFIED_DIGITAL_ANCHOR', 'DISPUTED'
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_loc_ver ON kavs_source_locators(source_version_id, locator_type);

-- 2. Source Verification Events (Discrete audit of authenticity, document integrity, publisher, and edition)
CREATE TABLE IF NOT EXISTS kavs_source_verification_events (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    source_version_id TEXT REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    verification_type TEXT NOT NULL, -- 'METADATA_VERIFICATION', 'PUBLISHER_AUTHORITY', 'DOCUMENT_INTEGRITY_HASH', 'EDITION_REVISION', 'RIGHTS_USAGE', 'PASSAGE_FIDELITY'
    result TEXT NOT NULL, -- 'VERIFIED_PASS', 'VERIFIED_WITH_RESTRICTIONS', 'DISPUTED', 'REJECTED'
    evidence_reference TEXT, -- URL, catalog entry, certificate, physical archive ID
    policy_version TEXT NOT NULL DEFAULT 'v1.0-gov',
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    reviewer_role TEXT NOT NULL DEFAULT 'GOVERNANCE_LEAD',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_verif_src ON kavs_source_verification_events(source_id, verification_type);

-- 3. Knowledge Governance Policy Registry (Versioned governance rules)
CREATE TABLE IF NOT EXISTS kavs_governance_policies (
    id TEXT PRIMARY KEY,
    policy_code TEXT NOT NULL UNIQUE, -- e.g. 'KAVS-POL-001'
    version TEXT NOT NULL, -- e.g. '1.0.0'
    title TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'SUPERSEDED', 'WITHDRAWN'
    policy_document_hash TEXT,
    approved_by TEXT NOT NULL REFERENCES users(id),
    approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    summary TEXT NOT NULL
);

-- 4. KAVS Audit Events (Tamper-evident append-only ledger for all KAVS state changes)
CREATE TABLE IF NOT EXISTS kavs_audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL, -- 'SOURCE_REGISTERED', 'SOURCE_VERSIONED', 'RIGHTS_REVIEWED', 'VERIFICATION_RECORDED', 'LOCATOR_CREATED', 'CLAIM_VERIFIED', 'CLAIM_AMENDED', 'RELEASE_PUBLISHED', 'RELEASE_WITHDRAWN'
    entity_type TEXT NOT NULL, -- 'SOURCE', 'SOURCE_VERSION', 'LOCATOR', 'CLAIM', 'RELEASE'
    entity_id TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    actor_role TEXT,
    prior_state TEXT,
    new_state TEXT,
    reason TEXT,
    correlation_id TEXT,
    outcome TEXT NOT NULL DEFAULT 'SUCCESS', -- 'SUCCESS', 'FAILED', 'BLOCKED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_audit_entity ON kavs_audit_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_kavs_audit_actor ON kavs_audit_events(actor_id, event_type);

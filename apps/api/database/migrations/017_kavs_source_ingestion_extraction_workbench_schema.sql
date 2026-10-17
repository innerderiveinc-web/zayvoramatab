-- Migration 017: KAVS Phase K2-K3 Source Ingestion, OCR Fidelity & Claim Extraction Workbench
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Rights Preflight Decisions & Audit Receipts
CREATE TABLE IF NOT EXISTS kavs_rights_preflight_events (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    source_version_id TEXT REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    requested_operation TEXT NOT NULL, -- 'RETAIN_FILE', 'EXTRACT_TEXT', 'RUN_OCR', 'INDEX_VECTORS', 'SHOW_EXCERPTS', 'SHOW_FULL_TEXT', 'EXPORT_REDISTRIBUTE'
    rights_policy_version TEXT NOT NULL DEFAULT 'v1.0-rights',
    decision TEXT NOT NULL, -- 'ALLOWED', 'BLOCKED', 'RESTRICTED'
    reason TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_preflight_src ON kavs_rights_preflight_events(source_id, decision);

-- 2. Secure Source File Storage & Checksums
CREATE TABLE IF NOT EXISTS kavs_source_files (
    id TEXT PRIMARY KEY,
    source_version_id TEXT NOT NULL REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    storage_key TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    magic_byte_verified INTEGER NOT NULL DEFAULT 1,
    sha256_checksum TEXT NOT NULL,
    malware_scan_status TEXT NOT NULL DEFAULT 'CLEAN', -- 'PENDING', 'CLEAN', 'QUARANTINED', 'NOT_SCANNED'
    upload_status TEXT NOT NULL DEFAULT 'COMPLETED', -- 'UPLOADING', 'COMPLETED', 'CANCELLED', 'CORRUPTED'
    uploaded_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_file_ver ON kavs_source_files(source_version_id, sha256_checksum);

-- 3. Ingestion Job Transition Events
CREATE TABLE IF NOT EXISTS kavs_ingestion_job_events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES kavs_ingestion_jobs(id) ON DELETE CASCADE,
    prior_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    actor_id TEXT REFERENCES users(id),
    reason TEXT,
    error_category TEXT,
    correlation_id TEXT,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_job_ev ON kavs_ingestion_job_events(job_id, new_state);

-- 4. Ingestion Extraction Pages (PDF Index vs Printed Page Label separation)
CREATE TABLE IF NOT EXISTS kavs_extraction_pages (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES kavs_ingestion_jobs(id) ON DELETE CASCADE,
    source_version_id TEXT REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    pdf_page_index INTEGER NOT NULL,
    printed_page_label TEXT,
    chapter TEXT,
    section TEXT,
    ocr_engine TEXT DEFAULT 'TESSERACT_OCR_v5',
    ocr_confidence REAL,
    detected_language TEXT DEFAULT 'en',
    raw_page_text TEXT NOT NULL,
    normalized_search_text TEXT,
    quality_flags_json TEXT DEFAULT '[]',
    page_status TEXT NOT NULL DEFAULT 'EXTRACTED', -- 'EXTRACTED', 'REQUIRES_MANUAL_TRANSCRIPTION', 'VERIFIED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_page_job ON kavs_extraction_pages(job_id, pdf_page_index);

-- 5. Structured Table Extractions
CREATE TABLE IF NOT EXISTS kavs_extraction_tables (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES kavs_ingestion_jobs(id) ON DELETE CASCADE,
    page_id TEXT REFERENCES kavs_extraction_pages(id) ON DELETE CASCADE,
    locator_id TEXT REFERENCES kavs_source_locators(id),
    table_title TEXT NOT NULL,
    headers_json TEXT NOT NULL DEFAULT '[]',
    rows_json TEXT NOT NULL DEFAULT '[]',
    footnotes TEXT,
    extraction_confidence REAL DEFAULT 1.0,
    structure_status TEXT NOT NULL DEFAULT 'STRUCTURED', -- 'STRUCTURED', 'PARTIAL_IMAGE_FALLBACK', 'MANUAL_CORRECTION_REQUIRED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Extraction Correction History (Before/After Audit)
CREATE TABLE IF NOT EXISTS kavs_extraction_corrections (
    id TEXT PRIMARY KEY,
    segment_id TEXT NOT NULL REFERENCES kavs_extraction_segments(id) ON DELETE CASCADE,
    original_machine_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    correction_reason TEXT NOT NULL,
    corrected_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_corr_seg ON kavs_extraction_corrections(segment_id);

-- 7. Candidate Claim Drafts (AI / Deterministic Extraction Workbench)
CREATE TABLE IF NOT EXISTS kavs_claim_drafts (
    id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES kavs_ingestion_jobs(id) ON DELETE CASCADE,
    segment_id TEXT NOT NULL REFERENCES kavs_extraction_segments(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
    source_version_id TEXT NOT NULL REFERENCES kavs_source_versions(id) ON DELETE CASCADE,
    locator_id TEXT REFERENCES kavs_source_locators(id),
    proposed_claim_text TEXT NOT NULL,
    proposed_claim_type TEXT NOT NULL DEFAULT 'traditional_use',
    extracted_concepts_json TEXT DEFAULT '[]',
    has_high_risk_elements INTEGER NOT NULL DEFAULT 0, -- Numbers, doses, potent compounds, negative statements
    uncertainty_flags_json TEXT DEFAULT '[]',
    extraction_model_info TEXT NOT NULL DEFAULT 'DETERMINISTIC_PARSER_v1.0',
    draft_status TEXT NOT NULL DEFAULT 'DRAFT_UNVERIFIED', -- 'DRAFT_UNVERIFIED', 'SUBMITTED_FOR_REVIEW', 'REJECTED', 'PROMOTED_TO_CLAIM'
    reviewer_id TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    promoted_claim_id TEXT REFERENCES knowledge_claims(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kavs_cdraft_status ON kavs_claim_drafts(draft_status, has_high_risk_elements);

-- 8. Ingestion Adapter Registry
CREATE TABLE IF NOT EXISTS kavs_adapter_registry (
    id TEXT PRIMARY KEY,
    adapter_name TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL,
    supported_formats_json TEXT NOT NULL DEFAULT '[]',
    extraction_method TEXT NOT NULL,
    limitations TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

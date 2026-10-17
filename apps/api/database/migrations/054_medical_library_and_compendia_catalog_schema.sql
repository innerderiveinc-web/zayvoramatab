-- Migration 054: Medical Library & Compendia Catalog Schema
-- Standalone Classical & Biomedical Clinical Library Infrastructure for ZAYVORA MATAB OS

CREATE TABLE IF NOT EXISTS medical_library_books (
    id TEXT PRIMARY KEY,
    organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    title_original TEXT,
    primary_author TEXT NOT NULL,
    authority_category TEXT NOT NULL, -- CLASSICAL_CANON, PHARMACOPOEIA_FORMULARY, MATERIA_MEDICA, DIAGNOSTICS_SURGERY, MODERN_INTERNAL_MEDICINE, PRINCIPLES_PHYSIOLOGY, REGIMENTAL_THERAPY, TERMINOLOGY_GOVERNANCE
    language TEXT NOT NULL,          -- ARABIC, URDU, ENGLISH, MULTILINGUAL
    publication_era TEXT,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    file_format TEXT NOT NULL,       -- PDF, RAR, ZIP
    sha256_hash TEXT NOT NULL,
    curation_status TEXT NOT NULL DEFAULT 'VERIFIED_BENCHMARK',
    description TEXT,
    topics_json TEXT DEFAULT '[]',
    clinical_significance TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_med_lib_books_cat ON medical_library_books(authority_category);
CREATE INDEX IF NOT EXISTS idx_med_lib_books_lang ON medical_library_books(language);
CREATE INDEX IF NOT EXISTS idx_med_lib_books_author ON medical_library_books(primary_author);
CREATE INDEX IF NOT EXISTS idx_med_lib_books_code ON medical_library_books(code);

CREATE TABLE IF NOT EXISTS medical_library_citations (
    id TEXT PRIMARY KEY,
    book_id TEXT NOT NULL REFERENCES medical_library_books(id) ON DELETE CASCADE,
    condition_or_formulation TEXT NOT NULL,
    chapter_or_volume TEXT,
    page_reference TEXT,
    quote_or_excerpt TEXT,
    clinical_action TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_med_lib_citations_book ON medical_library_citations(book_id);
CREATE INDEX IF NOT EXISTS idx_med_lib_citations_cond ON medical_library_citations(condition_or_formulation);

-- Phase 3 Schema: Formulation Library, Nuskha-Wisi, Prescriptions, Safety Preflight, and Electronic Sign-off
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Statutory and Classical Knowledge Sources
CREATE TABLE IF NOT EXISTS clinical_sources (
    id TEXT PRIMARY KEY,
    organization_id TEXT REFERENCES organizations(id) ON DELETE CASCADE, -- NULL for global statutory sources
    code TEXT NOT NULL UNIQUE, -- 'NFUM', 'UPI', 'BAYAZ_KABIR', 'AL_QANUN'
    title TEXT NOT NULL,
    author_authority TEXT NOT NULL,
    edition TEXT,
    publication_year INTEGER,
    legal_status TEXT NOT NULL DEFAULT 'STATUTORY', -- 'STATUTORY', 'HISTORICAL_BENCHMARK', 'RESEARCH'
    url_or_reference TEXT,
    verification_status TEXT NOT NULL DEFAULT 'VERIFIED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Master Ingredient Catalog
CREATE TABLE IF NOT EXISTS ingredient_catalog (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL, -- 'Almond / Badam'
    unani_name TEXT NOT NULL, -- 'Badam Shireen'
    botanical_name TEXT, -- 'Prunus dulcis'
    category TEXT NOT NULL DEFAULT 'BOTANICAL', -- 'BOTANICAL', 'MINERAL', 'ANIMAL'
    temperament_mizaj TEXT, -- 'HOT_DRY', 'HOT_MOIST', 'COLD_DRY', 'COLD_MOIST', 'MOTADIL'
    degree INTEGER DEFAULT 1,
    single_dose_min_mg INTEGER,
    single_dose_max_mg INTEGER,
    daily_dose_max_mg INTEGER,
    is_mudabbar_required INTEGER NOT NULL DEFAULT 0,
    is_schedule_e1 INTEGER NOT NULL DEFAULT 0,
    source_id TEXT REFERENCES clinical_sources(id),
    review_status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'RETIRED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ingredient_names ON ingredient_catalog(canonical_name, unani_name);

-- 3. Master Formulations (Stable Identity)
CREATE TABLE IF NOT EXISTS formulations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    code TEXT NOT NULL, -- e.g. 'FORM-001'
    name TEXT NOT NULL, -- e.g. 'Sharbat Bazoori Motadil'
    transliteration TEXT,
    dosage_form TEXT NOT NULL, -- 'SAFOOF', 'MAJOON', 'SHARBAT', 'HAB', 'QURS', 'KHAMIRA', 'JOSHANDA', 'ROGHAN', 'ARQ', 'ITRIFAL'
    current_version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'RETIRED'
    created_by TEXT REFERENCES users(id),
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_formulations_org_status ON formulations(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_formulations_name ON formulations(organization_id, name);

-- 4. Immutable Formulation Versions
CREATE TABLE IF NOT EXISTS formulation_versions (
    id TEXT PRIMARY KEY,
    formulation_id TEXT NOT NULL REFERENCES formulations(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    preparation_method TEXT,
    standard_indication TEXT,
    standard_adult_dose TEXT,
    classical_source_id TEXT REFERENCES clinical_sources(id),
    source_locator TEXT, -- e.g. 'NFUM Part I, Page 142'
    status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'RETIRED'
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(formulation_id, version_number)
);

-- 5. Formulation Ingredients (Composition Mapping)
CREATE TABLE IF NOT EXISTS formulation_ingredients (
    id TEXT PRIMARY KEY,
    formulation_version_id TEXT NOT NULL REFERENCES formulation_versions(id) ON DELETE CASCADE,
    ingredient_id TEXT NOT NULL REFERENCES ingredient_catalog(id) ON DELETE CASCADE,
    quantity_mg INTEGER NOT NULL,
    unit TEXT NOT NULL DEFAULT 'mg',
    is_chief_ingredient INTEGER NOT NULL DEFAULT 0,
    processing_notes TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(formulation_version_id, ingredient_id)
);

-- 6. Formulation Synonyms (Multi-script Search)
CREATE TABLE IF NOT EXISTS formulation_synonyms (
    id TEXT PRIMARY KEY,
    formulation_id TEXT NOT NULL REFERENCES formulations(id) ON DELETE CASCADE,
    synonym TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'ur', -- 'ur', 'hi', 'en', 'ar'
    script TEXT -- 'nastaliq', 'devanagari', 'latin'
);

-- 7. Formulation Reviews Log
CREATE TABLE IF NOT EXISTS formulation_reviews (
    id TEXT PRIMARY KEY,
    formulation_version_id TEXT NOT NULL REFERENCES formulation_versions(id) ON DELETE CASCADE,
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL, -- 'APPROVED', 'REJECTED', 'RETIRED'
    notes TEXT,
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Clinical Contraindications
CREATE TABLE IF NOT EXISTS safety_contraindications (
    id TEXT PRIMARY KEY,
    ingredient_id TEXT REFERENCES ingredient_catalog(id) ON DELETE CASCADE,
    contraindication_type TEXT NOT NULL, -- 'PREGNANCY', 'LACTATION', 'PEDIATRIC', 'ALLERGY_NUT', 'HYPERTENSION'
    severity TEXT NOT NULL DEFAULT 'BLOCK', -- 'BLOCK', 'WARN'
    rationale TEXT NOT NULL
);

-- 9. Patient Allergies Register
CREATE TABLE IF NOT EXISTS patient_allergies (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    allergen_name TEXT NOT NULL, -- e.g. 'Badam', 'Roghan Badam Shireen'
    severity TEXT NOT NULL DEFAULT 'SEVERE', -- 'MILD', 'MODERATE', 'SEVERE'
    reaction TEXT,
    recorded_by TEXT REFERENCES users(id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_allergies_pat ON patient_allergies(patient_id);

-- 10. Prescriptions Header
CREATE TABLE IF NOT EXISTS prescriptions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    prescription_number TEXT NOT NULL, -- 'RX-2026-00001'
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    practitioner_id TEXT NOT NULL REFERENCES users(id),
    version_number INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'VALIDATION_REQUIRED', 'SIGNED', 'CANCELLED', 'SUPERSEDED'
    overall_safety_state TEXT NOT NULL DEFAULT 'UNKNOWN', -- 'UNKNOWN', 'PASS', 'WARN', 'BLOCK'
    parent_prescription_id TEXT REFERENCES prescriptions(id),
    amendment_reason TEXT,
    cancellation_reason TEXT,
    patient_instructions_language TEXT DEFAULT 'ur',
    signed_at TIMESTAMP,
    signed_by TEXT REFERENCES users(id),
    signature_hash TEXT, -- SHA-256 fingerprint
    signed_snapshot TEXT, -- Full immutable JSON snapshot
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, prescription_number)
);

CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_prescriptions_encounter ON prescriptions(encounter_id, status);
CREATE INDEX IF NOT EXISTS idx_prescriptions_org ON prescriptions(organization_id, status);

-- 11. Prescription Line Items
CREATE TABLE IF NOT EXISTS prescription_items (
    id TEXT PRIMARY KEY,
    prescription_id TEXT NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL DEFAULT 'CATALOG_FORMULATION', -- 'CATALOG_FORMULATION', 'CUSTOM_FORMULA'
    formulation_id TEXT REFERENCES formulations(id),
    formulation_version_id TEXT REFERENCES formulation_versions(id),
    item_name TEXT NOT NULL,
    dosage_form TEXT NOT NULL, -- 'SAFOOF', 'MAJOON', 'SHARBAT', 'HAB', 'QURS', etc.
    dose_amount TEXT NOT NULL,
    dose_unit TEXT NOT NULL, -- 'g', 'mg', 'ml', 'hab', 'qurs', 'spoonful', 'drops', 'masha', 'ratti'
    route TEXT NOT NULL DEFAULT 'ORAL',
    frequency TEXT NOT NULL, -- 'OD', 'BD', 'TDS', 'QID', 'BEDTIME', 'SOS'
    duration_days INTEGER NOT NULL,
    quantity_to_dispense TEXT,
    instructions TEXT,
    anupan_vehicle TEXT DEFAULT 'WATER',
    composition_snapshot TEXT, -- JSON for custom formulas
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_prescription_items_rx ON prescription_items(prescription_id, sort_order);

-- 12. Safety Preflight Validation Findings
CREATE TABLE IF NOT EXISTS prescription_validation_findings (
    id TEXT PRIMARY KEY,
    prescription_id TEXT NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    prescription_version INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    rule_set_version TEXT NOT NULL DEFAULT 'v1.0-preflight',
    severity TEXT NOT NULL, -- 'INFO', 'WARNING', 'BLOCK'
    finding_code TEXT NOT NULL,
    message TEXT NOT NULL,
    item_reference TEXT,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_by TEXT REFERENCES users(id),
    acknowledged_at TIMESTAMP,
    acknowledged_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_findings_rx_ver ON prescription_validation_findings(prescription_id, prescription_version);

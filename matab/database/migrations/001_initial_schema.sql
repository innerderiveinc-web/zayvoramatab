-- Migration 001: Initial Relational Schema for ZAYVORA MATAB OS
-- SQLite / ANSI SQL Compatible

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tenancy & Organization
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    license_number TEXT,
    profile_type TEXT NOT NULL DEFAULT 'MATAB', -- 'MATAB', 'CLINIC', 'HOSPITAL'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS facilities (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    username TEXT NOT NULL UNIQUE,
    email TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL, -- 'ADMIN', 'HAKEEM', 'DOCTOR', 'NURSE', 'RECEPTIONIST', 'PHARMACIST'
    full_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS practitioners (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    license_type TEXT NOT NULL DEFAULT 'BUMS', -- 'BUMS', 'MD_UNANI', 'MBBS'
    registration_number TEXT NOT NULL,
    registration_council TEXT NOT NULL,
    digital_signature_pin_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_facility_memberships (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    role_in_facility TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, facility_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Patients Domain
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    mrn TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT,
    dob TEXT,
    gender TEXT NOT NULL, -- 'MALE', 'FEMALE', 'OTHER'
    phone TEXT NOT NULL,
    email TEXT,
    blood_group TEXT,
    emergency_contact_name TEXT,
    emergency_contact_phone TEXT,
    primary_language TEXT NOT NULL DEFAULT 'UR', -- 'UR', 'HI', 'EN'
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, mrn)
);

CREATE INDEX IF NOT EXISTS idx_patients_search ON patients(organization_id, phone, first_name);

CREATE TABLE IF NOT EXISTS patient_allergies (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    allergen_type TEXT NOT NULL, -- 'HERBAL', 'PHARMACEUTICAL', 'FOOD'
    allergen_name TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MODERATE', -- 'MILD', 'MODERATE', 'SEVERE'
    reaction_description TEXT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS possible_duplicate_matches (
    id TEXT PRIMARY KEY,
    patient_a_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    patient_b_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    match_confidence REAL NOT NULL,
    match_reasons TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    resolved_by TEXT,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clinical Encounters & Observations
CREATE TABLE IF NOT EXISTS encounters (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    practitioner_id TEXT REFERENCES practitioners(id),
    token_number INTEGER NOT NULL,
    encounter_type TEXT NOT NULL DEFAULT 'WALK_IN', -- 'WALK_IN', 'APPOINTMENT', 'FOLLOW_UP'
    status TEXT NOT NULL DEFAULT 'ARRIVED', -- 'ARRIVED', 'IN_CONSULTATION', 'SIGNED', 'COMPLETED', 'CANCELLED'
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_encounters_queue ON encounters(facility_id, status, created_at);

CREATE TABLE IF NOT EXISTS vitals (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    systolic_bp INTEGER,
    diastolic_bp INTEGER,
    pulse_bpm INTEGER,
    temperature_f REAL,
    respiratory_rate INTEGER,
    weight_kg REAL,
    height_cm REAL,
    spo2_percent INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clinical_notes (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    chief_complaint TEXT NOT NULL,
    history_of_present_illness TEXT,
    past_medical_history TEXT,
    general_physical_exam TEXT,
    systemic_exam TEXT,
    author_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unani Clinical Assessment Track
CREATE TABLE IF NOT EXISTS unani_assessments (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    hakeem_id TEXT NOT NULL REFERENCES practitioners(id),
    dominant_mizaj TEXT NOT NULL DEFAULT 'UNKNOWN', -- 'DAMWI', 'BALGHAMI', 'SAFRAWI', 'SAUDAWI', 'MOTADIL', 'UNKNOWN'
    mizaj_secondary TEXT,
    su_e_mizaj_type TEXT DEFAULT 'NONE', -- 'SAADA', 'MADDI', 'NONE'
    nabz_quality TEXT, -- 'AZEEM', 'SAREE', 'MUTAWASSIT', 'SAGHEER', 'BATEE'
    baul_observations TEXT,
    baraz_observations TEXT,
    afaal_summary TEXT,
    asbab_sittah_assessment TEXT,
    clinical_interpretation TEXT,
    assessment_status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'FINAL'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mizaj_questionnaire_responses (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES unani_assessments(id) ON DELETE CASCADE,
    question_key TEXT NOT NULL,
    selected_option TEXT NOT NULL,
    score_dam INTEGER NOT NULL DEFAULT 0,
    score_balgham INTEGER NOT NULL DEFAULT 0,
    score_safra INTEGER NOT NULL DEFAULT 0,
    score_sauda INTEGER NOT NULL DEFAULT 0
);

-- Modern Clinical Support Track
CREATE TABLE IF NOT EXISTS clinical_problems (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    problem_name TEXT NOT NULL,
    icd10_code TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    is_red_flag INTEGER NOT NULL DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Care Plan (Usul-e-Ilaj)
CREATE TABLE IF NOT EXISTS care_plans (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    usul_e_ilaj_summary TEXT NOT NULL,
    modality_flags TEXT NOT NULL, -- Comma-separated: 'ILAJ_BIL_DAWA,ILAJ_BIL_GHIZA,ILAJ_BIT_TADBEER'
    dietary_guidelines_ghiza TEXT,
    regimen_tadbeer_instructions TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS follow_up_tasks (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    due_date TEXT NOT NULL,
    target_objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SCHEDULED', -- 'SCHEDULED', 'ATTENDED', 'MISSED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Clinical Knowledge Catalog & Formulary
CREATE TABLE IF NOT EXISTS knowledge_sources (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author_authority TEXT NOT NULL,
    edition TEXT,
    publication_year INTEGER,
    legal_status TEXT NOT NULL DEFAULT 'STATUTORY' -- 'STATUTORY', 'HISTORICAL_BENCHMARK', 'RESEARCH'
);

CREATE TABLE IF NOT EXISTS ingredients (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    unani_name TEXT NOT NULL,
    botanical_name TEXT,
    temperament_mizaj TEXT, -- 'HOT_DRY', 'HOT_MOIST', 'COLD_DRY', 'COLD_MOIST'
    degree INTEGER DEFAULT 1,
    single_dose_min_mg INTEGER,
    single_dose_max_mg INTEGER,
    daily_dose_max_mg INTEGER,
    is_mudabbar_required INTEGER NOT NULL DEFAULT 0,
    is_schedule_e1 INTEGER NOT NULL DEFAULT 0,
    source_id TEXT REFERENCES knowledge_sources(id)
);

CREATE TABLE IF NOT EXISTS formulations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    dosage_form TEXT NOT NULL, -- 'SAFOOF', 'MAJOON', 'KHAMIRA', 'JOSHANDA', 'ITRIFAL', 'HAB', 'ARQ', 'ROGHAN'
    classical_source_id TEXT REFERENCES knowledge_sources(id),
    standard_indication TEXT,
    standard_adult_dose TEXT,
    is_verified INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS formulation_ingredients (
    id TEXT PRIMARY KEY,
    formulation_id TEXT NOT NULL REFERENCES formulations(id) ON DELETE CASCADE,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    quantity_mg INTEGER NOT NULL,
    is_chief_ingredient INTEGER NOT NULL DEFAULT 0,
    UNIQUE(formulation_id, ingredient_id)
);

CREATE TABLE IF NOT EXISTS safety_contraindications (
    id TEXT PRIMARY KEY,
    ingredient_id TEXT NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    contraindication_type TEXT NOT NULL, -- 'PREGNANCY', 'LACTATION', 'PEDIATRIC', 'ALLERGY_NUT', 'HYPERTENSION'
    severity TEXT NOT NULL DEFAULT 'BLOCK', -- 'BLOCK', 'WARN'
    rationale TEXT NOT NULL
);

-- Prescriptions & Preflight Checks
CREATE TABLE IF NOT EXISTS prescriptions (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    hakeem_id TEXT NOT NULL REFERENCES practitioners(id),
    version_number INTEGER NOT NULL DEFAULT 1,
    parent_prescription_id TEXT REFERENCES prescriptions(id),
    amendment_reason TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'PREFLIGHT_PASSED', 'PREFLIGHT_BLOCKED', 'SIGNED', 'DISPENSED', 'CANCELLED'
    overall_safety_state TEXT NOT NULL DEFAULT 'UNKNOWN', -- 'UNKNOWN', 'PASS', 'WARN', 'BLOCK'
    signature_timestamp TIMESTAMP,
    signature_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prescription_items (
    id TEXT PRIMARY KEY,
    prescription_id TEXT NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    item_type TEXT NOT NULL DEFAULT 'CATALOG_FORMULATION', -- 'CATALOG_FORMULATION', 'CUSTOM_COMPOUND', 'SINGLE_HERB'
    formulation_id TEXT REFERENCES formulations(id),
    custom_name TEXT,
    dosage_form TEXT NOT NULL,
    dose_amount TEXT NOT NULL,
    dose_unit TEXT NOT NULL, -- 'g', 'mg', 'ml', 'masha', 'ratti'
    frequency TEXT NOT NULL, -- 'OD', 'BD', 'TDS', 'QID', 'SOS'
    duration_days INTEGER NOT NULL,
    instructions TEXT,
    anupan_vehicle TEXT DEFAULT 'WATER'
);

CREATE TABLE IF NOT EXISTS safety_check_runs (
    id TEXT PRIMARY KEY,
    prescription_id TEXT NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    overall_result TEXT NOT NULL, -- 'PASS', 'WARN', 'BLOCK', 'UNKNOWN'
    check_details TEXT NOT NULL, -- JSON string
    override_rationale TEXT,
    overridden_by TEXT REFERENCES practitioners(id)
);

-- Operations & Governance
CREATE TABLE IF NOT EXISTS inventory_batches (
    id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    formulation_id TEXT REFERENCES formulations(id),
    ingredient_id TEXT REFERENCES ingredients(id),
    batch_number TEXT NOT NULL,
    mfg_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    quantity_remaining INTEGER NOT NULL,
    unit TEXT NOT NULL,
    is_mudabbar_certified INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id),
    actor_id TEXT REFERENCES users(id),
    action_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    details TEXT,
    client_ip TEXT,
    prev_hash TEXT NOT NULL,
    chain_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_chain ON audit_events(organization_id, created_at);

CREATE TABLE IF NOT EXISTS feature_registry (
    engine_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    state TEXT NOT NULL, -- 'NOT_IMPLEMENTED', 'IMPLEMENTED_NOT_CONNECTED', 'CONNECTED_NOT_VALIDATED', 'FUNCTIONALLY_TESTED', 'CLINICALLY_REVIEWED', 'PILOT_APPROVED', 'PRODUCTION_APPROVED', 'DISABLED_OR_DEGRADED'
    last_tested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    owner TEXT NOT NULL
);

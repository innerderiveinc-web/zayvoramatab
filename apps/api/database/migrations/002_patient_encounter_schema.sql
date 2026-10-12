-- Phase 2 Schema: Patient Registry, Identifiers, Contacts, Consents, Duplicates, and Encounters
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Patients Master Entity
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    mrn TEXT NOT NULL,
    given_name TEXT NOT NULL,
    family_name TEXT,
    display_name TEXT NOT NULL,
    date_of_birth TEXT, -- ISO YYYY-MM-DD
    estimated_age INTEGER,
    age_recorded_at TEXT, -- ISO timestamp
    sex TEXT NOT NULL DEFAULT 'UNKNOWN', -- 'MALE', 'FEMALE', 'OTHER', 'UNKNOWN'
    preferred_language TEXT DEFAULT 'ur', -- 'ur', 'hi', 'en', etc.
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'INACTIVE'
    version INTEGER NOT NULL DEFAULT 1, -- Optimistic concurrency control
    created_by TEXT REFERENCES users(id),
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, mrn)
);

CREATE INDEX IF NOT EXISTS idx_patients_org_status ON patients(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_patients_org_mrn ON patients(organization_id, mrn);
CREATE INDEX IF NOT EXISTS idx_patients_org_display_name ON patients(organization_id, display_name);

-- 2. Patient Identifiers
CREATE TABLE IF NOT EXISTS patient_identifiers (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    identifier_type TEXT NOT NULL, -- 'MRN', 'NATIONAL_ID', 'ABHA', 'PASSPORT', 'DRIVING_LICENSE', 'OTHER'
    identifier_value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    issuer TEXT,
    is_verified INTEGER NOT NULL DEFAULT 0,
    verification_metadata TEXT,
    is_retired INTEGER NOT NULL DEFAULT 0,
    retired_reason TEXT,
    retired_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_identifiers_lookup ON patient_identifiers(organization_id, identifier_type, normalized_value);
CREATE INDEX IF NOT EXISTS idx_patient_identifiers_patient ON patient_identifiers(patient_id, is_retired);

-- 3. Patient Contacts
CREATE TABLE IF NOT EXISTS patient_contacts (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    contact_type TEXT NOT NULL, -- 'PHONE', 'WHATSAPP', 'EMAIL', 'EMERGENCY'
    contact_value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    is_preferred INTEGER NOT NULL DEFAULT 0,
    is_verified INTEGER NOT NULL DEFAULT 0,
    use TEXT DEFAULT 'MOBILE', -- 'MOBILE', 'HOME', 'WORK'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_contacts_lookup ON patient_contacts(organization_id, contact_type, normalized_value);
CREATE INDEX IF NOT EXISTS idx_patient_contacts_patient ON patient_contacts(patient_id);

-- 4. Patient Addresses
CREATE TABLE IF NOT EXISTS patient_addresses (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    address_line1 TEXT,
    address_line2 TEXT,
    city TEXT,
    state TEXT,
    postal_code TEXT,
    country TEXT DEFAULT 'IN',
    is_primary INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patient_addresses_patient ON patient_addresses(patient_id);

-- 5. Patient Consents & Communication Preferences
CREATE TABLE IF NOT EXISTS patient_consents (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL, -- 'GENERAL_CARE', 'COMMUNICATION_SMS', 'COMMUNICATION_WHATSAPP', 'DATA_SHARING_RESEARCH', 'EXTERNAL_REFERRAL'
    status TEXT NOT NULL, -- 'GRANTED', 'REFUSED', 'WITHDRAWN'
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    source_method TEXT NOT NULL, -- 'VERBAL_PATIENT', 'WRITTEN_FORM', 'DIGITAL_APP'
    recorded_by TEXT NOT NULL REFERENCES users(id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    withdrawn_at TIMESTAMP,
    withdrawal_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_patient_consents_lookup ON patient_consents(patient_id, purpose, status);

-- 6. Duplicate Resolution Queue (Human-Controlled, No Automatic Merge)
CREATE TABLE IF NOT EXISTS patient_duplicate_candidates (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id_a TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    patient_id_b TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    match_score REAL NOT NULL,
    match_rules TEXT NOT NULL, -- JSON array of triggered rules
    status TEXT NOT NULL DEFAULT 'PENDING_REVIEW', -- 'PENDING_REVIEW', 'CONFIRMED_DIFFERENT', 'DEFERRED', 'MERGED_FUTURE'
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, patient_id_a, patient_id_b)
);

CREATE INDEX IF NOT EXISTS idx_duplicate_candidates_org ON patient_duplicate_candidates(organization_id, status);

-- 7. Encounters Lifecycle
CREATE TABLE IF NOT EXISTS encounters (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    practitioner_id TEXT REFERENCES users(id),
    token_number INTEGER,
    encounter_type TEXT NOT NULL DEFAULT 'OPD_VISIT', -- 'OPD_VISIT', 'FOLLOW_UP', 'TELECONSULT', 'EMERGENCY'
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED'
    reason_for_visit TEXT,
    cancellation_reason TEXT,
    version INTEGER NOT NULL DEFAULT 1, -- Optimistic concurrency control
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id, created_at);
CREATE INDEX IF NOT EXISTS idx_encounters_facility_status ON encounters(facility_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_encounters_practitioner ON encounters(practitioner_id, status);

-- Migration 026: Clinical Safety Surveillance, Adverse Event Management & Pharmacovigilance Schema
-- Phase 27 for ZAYVORA MATAB OS
-- Strict non-negotiables enforced:
-- 1. Never fabricate safety events, exposures, causality, or outcomes
-- 2. Record reports before judging causality (intake independent of attribution)
-- 3. Temporal association is not causation; causality is a separate evaluated dimension
-- 4. Strict dimensional separation: reported facts, clinical confirmation, severity, seriousness, expectedness, causality, reportability
-- 5. Never fabricate regulatory requirements (profiles disabled by default until verified)
-- 6. No automatic regulatory submission (two-person or authorized human gate with receipts)
-- 7. No autonomous treatment advice (safety engine does not alter care plans directly)
-- 8. Preserve original reporter narrative verbatim in native language/script

-- 1. Safety Cases Master Table
CREATE TABLE IF NOT EXISTS safety_cases (
    id TEXT PRIMARY KEY,
    case_number TEXT NOT NULL UNIQUE,
    tenant_id TEXT NOT NULL,
    facility_id TEXT NOT NULL,
    patient_id TEXT REFERENCES patients(id) ON DELETE SET NULL,
    case_type TEXT NOT NULL CHECK (case_type IN (
        'ADVERSE_EVENT',
        'SUSPECTED_ADVERSE_REACTION',
        'PRODUCT_QUALITY_DEFECT',
        'MEDICATION_ERROR',
        'NEAR_MISS',
        'THERAPEUTIC_FAILURE'
    )),
    intake_channel TEXT NOT NULL CHECK (intake_channel IN (
        'DIRECT_CLINICIAN_ENTRY',
        'PATIENT_PORTAL',
        'FOLLOW_UP_OUTREACH',
        'PHARMACY_DISPENSING',
        'EXTERNAL_COMMUNICATION',
        'TELEMEDICINE'
    )),
    received_at TEXT NOT NULL,
    case_state TEXT NOT NULL DEFAULT 'DRAFT' CHECK (case_state IN (
        'DRAFT',
        'INTAKE_COMPLETE',
        'TRIAGED',
        'UNDER_CLINICAL_REVIEW',
        'CAUSALITY_EVALUATED',
        'READY_FOR_SUBMISSION_REVIEW',
        'SUBMISSION_PENDING',
        'SUBMITTED',
        'CLOSED'
    )),
    case_version INTEGER NOT NULL DEFAULT 1,
    reporter_type TEXT NOT NULL CHECK (reporter_type IN (
        'PHYSICIAN_HAKEEM',
        'PHARMACIST',
        'NURSE',
        'PATIENT',
        'FAMILY_CAREGIVER',
        'MANUFACTURER',
        'REGULATORY_AUTHORITY',
        'OTHER'
    )),
    reporter_name TEXT,
    reporter_contact_redacted_json TEXT NOT NULL DEFAULT '{}',
    original_narrative TEXT NOT NULL,
    original_language TEXT NOT NULL DEFAULT 'en',
    normalized_summary TEXT,
    urgency_level TEXT NOT NULL DEFAULT 'ROUTINE' CHECK (urgency_level IN (
        'EMERGENCY',
        'EXPEDITED',
        'ROUTINE',
        'INFORMATIONAL'
    )),
    emergency_escalated INTEGER NOT NULL DEFAULT 0,
    emergency_escalated_at TEXT,
    emergency_escalated_to TEXT,
    duplicate_review_state TEXT NOT NULL DEFAULT 'NOT_EVALUATED' CHECK (duplicate_review_state IN (
        'NOT_EVALUATED',
        'POTENTIAL_DUPLICATES_IDENTIFIED',
        'REVIEWED_UNIQUE',
        'MERGED_INTO_MASTER',
        'LINKED_AS_CHILD'
    )),
    closure_rationale TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_cases_patient ON safety_cases(patient_id, case_state);
CREATE INDEX IF NOT EXISTS idx_safety_cases_urgency ON safety_cases(urgency_level, case_state);
CREATE INDEX IF NOT EXISTS idx_safety_cases_number ON safety_cases(case_number);

-- 2. Safety Events Table (Distinct reported reaction/symptom events)
CREATE TABLE IF NOT EXISTS safety_events (
    id TEXT PRIMARY KEY,
    safety_case_id TEXT NOT NULL REFERENCES safety_cases(id) ON DELETE CASCADE,
    event_version INTEGER NOT NULL DEFAULT 1,
    event_description_reported TEXT NOT NULL,
    coded_term_ref TEXT,
    onset_date TEXT NOT NULL,
    onset_date_precision TEXT NOT NULL DEFAULT 'EXACT_TIMESTAMP' CHECK (onset_date_precision IN (
        'EXACT_TIMESTAMP',
        'DAY',
        'MONTH',
        'YEAR',
        'APPROXIMATE'
    )),
    resolution_date TEXT,
    course_status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (course_status IN (
        'ACTIVE',
        'IMPROVED',
        'RESOLVED',
        'RESOLVED_WITH_SEQUELAE',
        'FATAL',
        'UNKNOWN'
    )),
    clinical_confirmation_state TEXT NOT NULL DEFAULT 'SUSPECTED_UNCONFIRMED' CHECK (clinical_confirmation_state IN (
        'SUSPECTED_UNCONFIRMED',
        'CLINICIAN_CONFIRMED',
        'REFUTED',
        'INDETERMINATE'
    )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_events_case ON safety_events(safety_case_id);
CREATE INDEX IF NOT EXISTS idx_safety_events_course ON safety_events(course_status);

-- 3. Suspected Exposures Table (Medications, formulations, or substances)
CREATE TABLE IF NOT EXISTS suspected_exposures (
    id TEXT PRIMARY KEY,
    safety_case_id TEXT NOT NULL REFERENCES safety_cases(id) ON DELETE CASCADE,
    reported_product_name TEXT NOT NULL,
    canonical_formulation_id TEXT REFERENCES formulations(id),
    batch_lot_number TEXT,
    dose_route_frequency TEXT,
    documented_start_date TEXT,
    documented_stop_date TEXT,
    prescription_id TEXT REFERENCES prescriptions(id),
    dispense_event_id TEXT,
    exposure_role TEXT NOT NULL DEFAULT 'SUSPECTED' CHECK (exposure_role IN (
        'SUSPECTED',
        'CONCOMITANT',
        'INTERACTING',
        'HISTORICAL'
    )),
    patient_reported_use_state TEXT NOT NULL DEFAULT 'CONFIRMED_TAKEN' CHECK (patient_reported_use_state IN (
        'CONFIRMED_TAKEN',
        'POSSIBLY_TAKEN',
        'DENIED_TAKEN',
        'UNKNOWN'
    )),
    identity_resolution_state TEXT NOT NULL DEFAULT 'FREE_TEXT_ONLY' CHECK (identity_resolution_state IN (
        'CONFIRMED_CATALOG',
        'PROVISIONAL_UNRESOLVED',
        'FREE_TEXT_ONLY'
    )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_suspected_exposures_case ON suspected_exposures(safety_case_id);
CREATE INDEX IF NOT EXISTS idx_suspected_exposures_formulation ON suspected_exposures(canonical_formulation_id);

-- 4. Multidimensional Safety Assessments Table
CREATE TABLE IF NOT EXISTS safety_assessments (
    id TEXT PRIMARY KEY,
    safety_case_id TEXT NOT NULL REFERENCES safety_cases(id) ON DELETE CASCADE,
    event_id TEXT REFERENCES safety_events(id) ON DELETE SET NULL,
    exposure_id TEXT REFERENCES suspected_exposures(id) ON DELETE SET NULL,
    assessment_dimension TEXT NOT NULL CHECK (assessment_dimension IN (
        'CLINICAL_CONFIRMATION',
        'SEVERITY',
        'SERIOUSNESS',
        'EXPECTEDNESS',
        'CAUSALITY',
        'REPORTABILITY'
    )),
    assessment_value TEXT NOT NULL,
    method_or_scale_ref TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    assessor_id TEXT NOT NULL REFERENCES users(id),
    assessor_role TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'SUBMITTED' CHECK (review_status IN (
        'DRAFT',
        'SUBMITTED',
        'VERIFIED',
        'SUPERSEDED'
    )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_assessments_case ON safety_assessments(safety_case_id, assessment_dimension);

-- 5. Regulatory Report Profiles Table
CREATE TABLE IF NOT EXISTS regulatory_report_profiles (
    id TEXT PRIMARY KEY,
    profile_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    jurisdiction_code TEXT NOT NULL,
    product_category TEXT NOT NULL,
    governing_authority TEXT NOT NULL,
    form_standard_version TEXT NOT NULL,
    minimum_required_fields_json TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 0, -- Non-negotiable: MUST BE DISABLED until compliance staff verification
    verification_date TEXT,
    compliance_reviewer_id TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reg_profiles_code ON regulatory_report_profiles(profile_code);
CREATE INDEX IF NOT EXISTS idx_reg_profiles_jurisdiction ON regulatory_report_profiles(jurisdiction_code, is_active);

-- 6. Governed Safety Submissions Table
CREATE TABLE IF NOT EXISTS safety_submissions (
    id TEXT PRIMARY KEY,
    safety_case_id TEXT NOT NULL REFERENCES safety_cases(id) ON DELETE RESTRICT,
    profile_id TEXT NOT NULL REFERENCES regulatory_report_profiles(id) ON DELETE RESTRICT,
    case_version INTEGER NOT NULL DEFAULT 1,
    payload_manifest_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('VALID', 'INVALID', 'WARNINGS')),
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    authorized_by TEXT REFERENCES users(id),
    authorized_at TEXT,
    submission_status TEXT NOT NULL DEFAULT 'PENDING_AUTHORIZATION' CHECK (submission_status IN (
        'PENDING_AUTHORIZATION',
        'AUTHORIZED',
        'DISPATCH_BLOCKED',
        'SUBMITTED',
        'ACKNOWLEDGED',
        'REJECTED'
    )),
    dispatch_blocked_reason TEXT,
    transaction_ref TEXT,
    acknowledgement_artifact TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_submissions_case ON safety_submissions(safety_case_id, submission_status);

-- 7. Case Deduplication & Relationship Links Table
CREATE TABLE IF NOT EXISTS safety_case_links (
    id TEXT PRIMARY KEY,
    source_case_id TEXT NOT NULL REFERENCES safety_cases(id) ON DELETE CASCADE,
    target_case_id TEXT NOT NULL REFERENCES safety_cases(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
        'POSSIBLE_DUPLICATE',
        'CONFIRMED_DUPLICATE',
        'FOLLOW_UP_REPORT',
        'RELATED_CASE',
        'NOT_SAME_CASE'
    )),
    rationale TEXT NOT NULL,
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_links_source ON safety_case_links(source_case_id, target_case_id);

-- 8. Follow-up Tasks Table
CREATE TABLE IF NOT EXISTS safety_follow_up_tasks (
    id TEXT PRIMARY KEY,
    safety_case_id TEXT NOT NULL REFERENCES safety_cases(id) ON DELETE CASCADE,
    required_field_or_query TEXT NOT NULL,
    assigned_role TEXT NOT NULL CHECK (assigned_role IN (
        'HAKEEM_CLINICIAN',
        'PHARMACIST',
        'SAFETY_OFFICER',
        'COMMUNITY_OUTREACH',
        'ADMIN'
    )),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN (
        'PENDING',
        'IN_PROGRESS',
        'COMPLETED',
        'UNABLE_TO_CONTACT',
        'CANCELLED'
    )),
    attempts_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    due_date TEXT,
    completion_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_tasks_case ON safety_follow_up_tasks(safety_case_id, status);

-- 9. Safety Signals Table
CREATE TABLE IF NOT EXISTS safety_signals (
    id TEXT PRIMARY KEY,
    signal_name TEXT NOT NULL,
    product_identifier TEXT NOT NULL,
    reaction_term TEXT NOT NULL,
    case_count INTEGER NOT NULL DEFAULT 1,
    evaluation_status TEXT NOT NULL DEFAULT 'DETECTED' CHECK (evaluation_status IN (
        'DETECTED',
        'UNDER_INVESTIGATION',
        'CONFIRMED_RISK',
        'REFUTED',
        'MONITORING'
    )),
    clinical_justification TEXT,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_signals_product ON safety_signals(product_identifier, reaction_term);

-- 10. Seed standard disabled regulatory profiles (Must remain is_active = 0 until verified)
INSERT OR IGNORE INTO regulatory_report_profiles (
    id, profile_code, title, jurisdiction_code, product_category,
    governing_authority, form_standard_version, minimum_required_fields_json,
    is_active, verification_date, compliance_reviewer_id, created_at
) VALUES 
(
    'reg-prof-pvpi-1',
    'PVPI_AYUSH_ASU',
    'Pharmacovigilance Programme for ASU Drugs (PvPI)',
    'IN',
    'UNANI_ASU',
    'All India Institute of Ayurveda / Ministry of Ayush',
    'v2.1',
    '["patient_identifier", "suspected_formulation", "adverse_reaction_description", "onset_date", "reporter_type", "causality_assessment"]',
    0,
    NULL,
    NULL,
    CURRENT_TIMESTAMP
),
(
    'reg-prof-drap-1',
    'DRAP_PV_CENTRE',
    'DRAP National Pharmacovigilance Centre (NPC)',
    'PK',
    'UNANI_ASU',
    'Drug Regulatory Authority of Pakistan (DRAP)',
    'v1.0',
    '["patient_identifier", "suspected_formulation", "adverse_reaction_description", "onset_date", "reporter_type", "seriousness_determination"]',
    0,
    NULL,
    NULL,
    CURRENT_TIMESTAMP
),
(
    'reg-prof-who-1',
    'WHO_VIGIBASE_E2B',
    'WHO Uppsala Monitoring Centre E2B(R3) Traditional Medicine Track',
    'GLOBAL',
    'COMPLEMENTARY',
    'WHO-UMC',
    'E2B(R3)',
    '["patient_identifier", "suspected_substance", "reaction_coded_term", "onset_date", "reporter_qualification", "causality_method"]',
    0,
    NULL,
    NULL,
    CURRENT_TIMESTAMP
);

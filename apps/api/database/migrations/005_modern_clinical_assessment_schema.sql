-- Migration 005: Modern Clinical Assessment, Differential Diagnosis Support,
-- Investigation Considerations, and Referral Safety
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Clinical Content Sources (Knowledge Governance)
CREATE TABLE IF NOT EXISTS clinical_content_sources (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authority TEXT NOT NULL,
    version TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'approved_active', -- 'not_configured', 'draft', 'under_review', 'approved_active', 'expired_or_due_for_review', 'retired', 'temporarily_unavailable'
    source_uri TEXT,
    effective_date TEXT,
    expiry_date TEXT,
    licence_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clin_src_status ON clinical_content_sources(review_status);

-- 2. Clinical Rule Definitions (Deterministic Red-Flags, Differential Heuristics, Investigation Guidelines)
CREATE TABLE IF NOT EXISTS clinical_rule_definitions (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL UNIQUE,
    rule_version TEXT NOT NULL,
    rule_type TEXT NOT NULL, -- 'RED_FLAG', 'DIFFERENTIAL_HEURISTIC', 'INVESTIGATION_GUIDELINE'
    title TEXT NOT NULL,
    scope TEXT NOT NULL,
    source_id TEXT REFERENCES clinical_content_sources(id),
    severity TEXT NOT NULL DEFAULT 'WARNING', -- 'EMERGENT', 'URGENT', 'WARNING', 'INFO'
    required_inputs_json TEXT NOT NULL, -- JSON array of required concept/field keys
    logic_definition_json TEXT NOT NULL, -- JSON structure of rules and criteria
    plain_language_rationale TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    governance_status TEXT NOT NULL DEFAULT 'approved_active', -- 'not_configured', 'draft', 'under_review', 'approved_active', 'expired_or_due_for_review', 'retired', 'temporarily_unavailable'
    clinical_owner TEXT NOT NULL,
    reviewer_name TEXT NOT NULL,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clin_rules_type_status ON clinical_rule_definitions(rule_type, governance_status);

-- 3. Modern Clinical Assessments (Encounter Header)
CREATE TABLE IF NOT EXISTS modern_clinical_assessments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'SIGNED', 'AMENDED', 'CANCELLED'
    assessment_date TEXT NOT NULL,
    chief_complaint TEXT,
    history_of_present_illness TEXT,
    past_medical_history TEXT,
    surgical_history TEXT,
    family_history TEXT,
    personal_social_history TEXT,
    medication_history TEXT,
    allergies_review_status TEXT NOT NULL DEFAULT 'NOT_REVIEWED', -- 'NOT_RECORDED', 'NOT_REVIEWED', 'REVIEWED_NONE_REPORTED', 'REVIEWED_ALLERGIES_RECORDED'
    review_of_systems_json TEXT, -- JSON structure of systems and observations
    physical_examination_json TEXT, -- JSON structure of examination findings
    working_assessment TEXT,
    clinical_rationale TEXT,
    uncertainty_level TEXT NOT NULL DEFAULT 'NOT_ASSESSED', -- 'HIGH_CONFIDENCE', 'MODERATE_CONFIDENCE', 'PROVISIONAL', 'UNCERTAIN', 'NOT_ASSESSED'
    ai_drafted_notes TEXT,
    ai_draft_status TEXT NOT NULL DEFAULT 'NONE', -- 'NONE', 'DRAFT_AWAITING_REVIEW', 'CLINICIAN_REVIEWED_AND_ACCEPTED', 'CLINICIAN_REJECTED'
    version_number INTEGER NOT NULL DEFAULT 1,
    parent_assessment_id TEXT REFERENCES modern_clinical_assessments(id),
    signed_at TIMESTAMP,
    signed_by TEXT REFERENCES users(id),
    signature_hash TEXT, -- SHA-256 integrity fingerprint
    signed_snapshot TEXT, -- Complete immutable JSON snapshot
    cancellation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mod_assess_patient ON modern_clinical_assessments(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_mod_assess_encounter ON modern_clinical_assessments(encounter_id, status);
CREATE INDEX IF NOT EXISTS idx_mod_assess_org ON modern_clinical_assessments(organization_id, status);

-- 4. Clinical Observations & Vitals (Typed, validated measurements with provenance & reference ranges)
CREATE TABLE IF NOT EXISTS clinical_observations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    assessment_id TEXT REFERENCES modern_clinical_assessments(id) ON DELETE CASCADE,
    observation_type TEXT NOT NULL, -- 'VITAL_SIGN', 'LABORATORY', 'PHYSICAL_FINDING', 'SYSTEM_REVIEW'
    concept_code TEXT,
    concept_name TEXT NOT NULL, -- e.g. 'Systolic Blood Pressure', 'Heart Rate', 'Fasting Blood Sugar'
    value_numeric REAL,
    value_text TEXT,
    unit TEXT, -- e.g. 'mmHg', 'bpm', 'degC', 'mg/dL', '%'
    reference_range_low REAL,
    reference_range_high REAL,
    reference_range_provenance TEXT,
    interpretation TEXT DEFAULT 'UNKNOWN', -- 'NORMAL', 'ABNORMAL_HIGH', 'ABNORMAL_LOW', 'CRITICAL', 'UNKNOWN'
    source_type TEXT NOT NULL DEFAULT 'CLINICIAN_ENTERED', -- 'CLINICIAN_ENTERED', 'PATIENT_REPORTED', 'DEVICE_IMPORTED', 'EXTERNAL_DOCUMENT'
    source_provenance TEXT,
    measured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recorded_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clin_obs_patient ON clinical_observations(patient_id, observation_type);
CREATE INDEX IF NOT EXISTS idx_clin_obs_encounter ON clinical_observations(encounter_id);
CREATE INDEX IF NOT EXISTS idx_clin_obs_assessment ON clinical_observations(assessment_id);

-- 5. Clinician-Controlled Clinical Problem List & Confirmed Diagnoses
CREATE TABLE IF NOT EXISTS clinical_problems (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    assessment_id TEXT NOT NULL REFERENCES modern_clinical_assessments(id) ON DELETE CASCADE,
    problem_title TEXT NOT NULL,
    code_system TEXT, -- 'ICD-10-MOCK', 'SNOMED-CT-MOCK', 'UNCODED'
    code_value TEXT,
    coding_status TEXT NOT NULL DEFAULT 'UNCODED', -- 'CONFIRMED_CODED', 'UNCODED', 'MAPPING_PENDING'
    status TEXT NOT NULL DEFAULT 'PROVISIONAL', -- 'PROVISIONAL', 'CONFIRMED', 'RESOLVED', 'RULED_OUT'
    onset_date TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    clinical_notes TEXT,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clin_prob_patient ON clinical_problems(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_clin_prob_assessment ON clinical_problems(assessment_id);

-- 6. Differential Diagnosis Support Candidates (Candidate-level rationale & explainability)
CREATE TABLE IF NOT EXISTS differential_candidates (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES modern_clinical_assessments(id) ON DELETE CASCADE,
    candidate_label TEXT NOT NULL,
    candidate_code TEXT,
    code_system TEXT,
    surfaced_by_type TEXT NOT NULL DEFAULT 'RULE_DERIVED', -- 'RULE_DERIVED', 'CLINICIAN_ENTERED', 'KNOWLEDGE_RETRIEVED'
    rule_id TEXT REFERENCES clinical_rule_definitions(id),
    rule_version TEXT,
    evidence_status TEXT NOT NULL DEFAULT 'FOR_CLINICIAN_REVIEW',
    rationale TEXT NOT NULL,
    supporting_findings_json TEXT NOT NULL DEFAULT '[]',
    contradicting_findings_json TEXT NOT NULL DEFAULT '[]',
    missing_information_json TEXT NOT NULL DEFAULT '[]',
    source_references_json TEXT NOT NULL DEFAULT '[]',
    limitations TEXT,
    review_required INTEGER NOT NULL DEFAULT 1,
    clinician_decision TEXT NOT NULL DEFAULT 'PENDING_REVIEW', -- 'PENDING_REVIEW', 'ACCEPTED', 'REJECTED', 'DEFERRED', 'CONFIRMED_AS_PROBLEM'
    clinician_rationale TEXT,
    decided_by TEXT REFERENCES users(id),
    decided_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diff_cand_assess ON differential_candidates(assessment_id);

-- 7. Red-Flag Events & Safety Escalation Records
CREATE TABLE IF NOT EXISTS red_flag_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    assessment_id TEXT NOT NULL REFERENCES modern_clinical_assessments(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL REFERENCES clinical_rule_definitions(id),
    rule_version TEXT NOT NULL,
    severity TEXT NOT NULL, -- 'EMERGENT', 'URGENT', 'WARNING'
    trigger_facts_json TEXT NOT NULL,
    plain_language_reason TEXT NOT NULL,
    recommended_action TEXT NOT NULL,
    is_acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_by TEXT REFERENCES users(id),
    acknowledged_at TIMESTAMP,
    clinician_action_taken TEXT, -- 'EMERGENCY_TRANSFER_INITIATED', 'URGENT_REFERRAL_DOCUMENTED', 'OVERRIDDEN_WITH_RATIONALE', 'FURTHER_INVESTIGATION_PLANNED', 'MONITORING_CONTINUED'
    override_rationale TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_red_flags_assess ON red_flag_events(assessment_id, is_acknowledged);
CREATE INDEX IF NOT EXISTS idx_red_flags_patient ON red_flag_events(patient_id);

-- 8. Investigation Considerations (Non-Ordering Clinical Guidance)
CREATE TABLE IF NOT EXISTS investigation_considerations (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES modern_clinical_assessments(id) ON DELETE CASCADE,
    clinical_question TEXT NOT NULL,
    suggested_investigation TEXT NOT NULL,
    modality TEXT NOT NULL DEFAULT 'LABORATORY', -- 'LABORATORY', 'IMAGING', 'CARDIOLOGY_ECG', 'PULMONARY_FUNCTION', 'ENDOSCOPY'
    rationale TEXT NOT NULL,
    guideline_source TEXT,
    rule_id TEXT REFERENCES clinical_rule_definitions(id),
    rule_version TEXT,
    limitations TEXT,
    clinician_decision TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'ORDER_PLANNED', 'DEFERRED', 'NOT_INDICATED'
    clinician_notes TEXT,
    decided_by TEXT REFERENCES users(id),
    decided_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inv_cons_assess ON investigation_considerations(assessment_id);

-- 9. Referral & Escalation Records
CREATE TABLE IF NOT EXISTS referral_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    assessment_id TEXT NOT NULL REFERENCES modern_clinical_assessments(id) ON DELETE CASCADE,
    reason_for_referral TEXT NOT NULL,
    target_specialty TEXT NOT NULL, -- 'CARDIOLOGY', 'GASTROENTEROLOGY', 'PULMONOLOGY', 'EMERGENCY_MEDICINE', 'INTERNAL_MEDICINE', 'GENERAL_SURGERY'
    destination_facility TEXT,
    urgency TEXT NOT NULL DEFAULT 'ROUTINE', -- 'ROUTINE', 'URGENT', 'EMERGENT'
    handover_summary TEXT NOT NULL,
    patient_informed_status TEXT NOT NULL DEFAULT 'INFORMED_AGREED', -- 'INFORMED_AGREED', 'INFORMED_REFUSED', 'UNABLE_TO_INFORM', 'NOT_DISCUSSED'
    patient_informed_notes TEXT,
    actual_status TEXT NOT NULL DEFAULT 'DOCUMENTED', -- 'DOCUMENTED', 'SENT_TO_EXTERNAL', 'PATIENT_DISPATCHED', 'COMPLETED', 'CANCELLED'
    author_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_referral_patient ON referral_records(patient_id, actual_status);
CREATE INDEX IF NOT EXISTS idx_referral_assessment ON referral_records(assessment_id);

-- 10. Governed Assessment Amendments
CREATE TABLE IF NOT EXISTS clinical_assessment_amendments (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES modern_clinical_assessments(id) ON DELETE CASCADE,
    prior_version_number INTEGER NOT NULL,
    amendment_reason TEXT NOT NULL,
    amendment_notes TEXT,
    prior_snapshot TEXT NOT NULL,
    prior_snapshot_hash TEXT NOT NULL,
    amended_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_assess_amend_assess ON clinical_assessment_amendments(assessment_id);

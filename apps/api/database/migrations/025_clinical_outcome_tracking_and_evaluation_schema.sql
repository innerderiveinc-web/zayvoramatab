-- Migration 025: Clinical Outcome Tracking, Treatment Response Measurement & Longitudinal Evaluation Schema
-- Phase 26 for ZAYVORA MATAB OS
-- Strict non-negotiables enforced:
-- 1. Never fabricate outcomes or impute missing observations
-- 2. Separate raw observations from calculated scores and clinical interpretations
-- 3. Temporal sequence / change is not causation
-- 4. Meaningful change thresholds must be verified, not invented
-- 5. Instrument licensing and validity tracking
-- 6. Strict compatibility checking before comparisons
-- 7. Distinguish Unani and modern streams
-- 8. Fail-safe missingness states and zero patient data leakage

-- 1. Care Episodes (Explicit clinical follow-up contexts)
CREATE TABLE IF NOT EXISTS care_episodes (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    reason TEXT NOT NULL,
    opened_by TEXT NOT NULL REFERENCES users(id),
    opened_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'PAUSED', 'COMPLETED', 'CANCELLED', 'UNKNOWN'
    closed_by TEXT REFERENCES users(id),
    closed_at TEXT,
    closure_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_care_episodes_patient ON care_episodes(patient_id, status);

-- 2. Outcome Concepts Registry
CREATE TABLE IF NOT EXISTS outcome_concepts (
    id TEXT PRIMARY KEY,
    canonical_code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    domain TEXT NOT NULL, -- 'SYMPTOM_EXPERIENCE', 'FUNCTIONAL_STATUS', 'QUALITY_OF_LIFE', 'LABORATORY_MEASURE', 'PATIENT_EXPERIENCE', 'SAFETY_EVENT', 'UNANI_CLINICAL_MARKER', 'OTHER'
    source_or_definition_ref TEXT,
    allowed_data_types TEXT NOT NULL DEFAULT 'NUMERIC', -- 'NUMERIC', 'ORDINAL', 'BOOLEAN', 'CATEGORICAL', 'TEXT'
    permitted_units_json TEXT NOT NULL DEFAULT '[]',
    is_patient_reported INTEGER NOT NULL DEFAULT 1,
    is_clinician_observed INTEGER NOT NULL DEFAULT 1,
    is_objective_measure INTEGER NOT NULL DEFAULT 0,
    review_state TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'APPROVED', 'RETIRED'
    version TEXT NOT NULL DEFAULT '1.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_concepts_code ON outcome_concepts(canonical_code);
CREATE INDEX IF NOT EXISTS idx_outcome_concepts_domain ON outcome_concepts(domain);

-- 3. Measurement Instruments Registry
CREATE TABLE IF NOT EXISTS measurement_instruments (
    id TEXT PRIMARY KEY,
    instrument_name TEXT NOT NULL,
    instrument_code TEXT NOT NULL UNIQUE,
    developer_or_authority TEXT,
    instrument_version TEXT NOT NULL DEFAULT '1.0',
    intended_construct TEXT NOT NULL,
    target_population TEXT,
    recall_period TEXT NOT NULL DEFAULT 'PAST_7_DAYS', -- 'PAST_24_HOURS', 'PAST_7_DAYS', 'PAST_14_DAYS', 'PAST_30_DAYS', 'CURRENT_MOMENT', 'UNSPECIFIED'
    language_version TEXT NOT NULL DEFAULT 'en',
    administration_mode TEXT NOT NULL DEFAULT 'PATIENT_SELF_REPORT', -- 'PATIENT_SELF_REPORT', 'INTERVIEWER_ADMINISTERED', 'CLINICIAN_RATED', 'DEVICE'
    items_schema_json TEXT NOT NULL DEFAULT '[]', -- JSON array of item definitions: [{id, text, min, max, required, reverse_coded}]
    scoring_method_code TEXT,
    scoring_version TEXT,
    interpretation_thresholds_json TEXT, -- Sourced thresholds only; otherwise NULL
    validity_evidence_refs_json TEXT DEFAULT '[]',
    license_state TEXT NOT NULL DEFAULT 'OPEN_ACCESS', -- 'OPEN_ACCESS', 'LICENSED', 'CLINIC_CUSTOM', 'RESTRICTED'
    terms_restrictions TEXT,
    is_validated INTEGER NOT NULL DEFAULT 0, -- Strictly guarded: 1 only if authorized validity evidence is linked
    review_state TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'APPROVED', 'SUSPENDED', 'RETIRED'
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_measurement_instruments_code ON measurement_instruments(instrument_code);

-- 4. Outcome Protocols (Schedules and windows for outcome collection)
CREATE TABLE IF NOT EXISTS outcome_protocols (
    id TEXT PRIMARY KEY,
    protocol_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0',
    target_conditions_json TEXT DEFAULT '[]',
    baseline_window_days_prior INTEGER NOT NULL DEFAULT 14,
    baseline_window_days_post INTEGER NOT NULL DEFAULT 0,
    follow_up_windows_json TEXT NOT NULL DEFAULT '[]', -- [{time_point: 'WEEK_2', target_days: 14, window_minus: 3, window_plus: 3}, ...]
    instrument_ids_json TEXT NOT NULL DEFAULT '[]',
    concept_ids_json TEXT NOT NULL DEFAULT '[]',
    missing_data_policy TEXT NOT NULL DEFAULT 'EXPLICIT_MISSINGNESS_PRESERVED',
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'DRAFT', 'IN_REVIEW', 'ACTIVE', 'SUSPENDED', 'RETIRED'
    approved_by TEXT REFERENCES users(id),
    approved_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_protocols_code ON outcome_protocols(protocol_code);

-- 5. Outcome Protocol Runs (Patient-specific protocol execution)
CREATE TABLE IF NOT EXISTS outcome_protocol_runs (
    id TEXT PRIMARY KEY,
    protocol_id TEXT NOT NULL REFERENCES outcome_protocols(id),
    protocol_version TEXT NOT NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    episode_id TEXT REFERENCES care_episodes(id),
    baseline_observation_id TEXT,
    baseline_designated_by TEXT REFERENCES users(id),
    baseline_designated_at TEXT,
    baseline_selection_method TEXT, -- 'PRE_TREATMENT_OBSERVATION', 'CLINICIAN_MANUAL_SELECTION', 'PROTOCOL_DEFAULT'
    baseline_state TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'DESIGNATED', 'MISSING_OR_UNAVAILABLE'
    planned_windows_json TEXT NOT NULL DEFAULT '[]',
    run_state TEXT NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'IN_PROGRESS', 'AWAITING_FOLLOW_UP', 'COMPLETED', 'INCOMPLETE', 'CANCELLED'
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_protocol_runs_patient ON outcome_protocol_runs(patient_id, run_state);

-- 6. Outcome Observations (Raw observations, items, and values)
CREATE TABLE IF NOT EXISTS outcome_observations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT REFERENCES encounters(id),
    episode_id TEXT REFERENCES care_episodes(id),
    protocol_run_id TEXT REFERENCES outcome_protocol_runs(id),
    concept_id TEXT REFERENCES outcome_concepts(id),
    instrument_id TEXT REFERENCES measurement_instruments(id),
    instrument_version TEXT,
    observation_kind TEXT NOT NULL, -- 'PATIENT_REPORTED', 'CLINICIAN_OBSERVED', 'LABORATORY', 'DEVICE', 'CALCULATED', 'IMPORTED_RECORD', 'OTHER'
    raw_value_numeric REAL,
    raw_value_text TEXT,
    raw_unit TEXT,
    normalized_value_numeric REAL,
    normalized_value_text TEXT,
    normalized_unit TEXT,
    value_type TEXT NOT NULL DEFAULT 'NUMERIC', -- 'NUMERIC', 'ORDINAL', 'BOOLEAN', 'CATEGORICAL', 'TEXT', 'COMPLEX_JSON'
    item_responses_json TEXT, -- Preserves individual raw answers for multi-item questionnaires
    status TEXT NOT NULL DEFAULT 'PRESENT', -- 'PRESENT', 'UNKNOWN', 'NOT_MEASURED', 'NOT_ASKED', 'DECLINED', 'UNAVAILABLE', 'PENDING', 'INVALID', 'ENTERED_IN_ERROR'
    missingness_reason TEXT,
    effective_at TEXT NOT NULL,
    effective_time_precision TEXT NOT NULL DEFAULT 'EXACT_TIMESTAMP', -- 'EXACT_TIMESTAMP', 'DAY', 'MONTH', 'YEAR'
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observer_id TEXT NOT NULL REFERENCES users(id),
    observer_role TEXT NOT NULL DEFAULT 'CLINICIAN',
    verification_state TEXT NOT NULL DEFAULT 'UNVERIFIED', -- 'VERIFIED', 'UNVERIFIED', 'AI_DRAFT_UNVERIFIED', 'ENTERED_IN_ERROR'
    input_manifest_json TEXT, -- Calculation manifest with input IDs for derived measures
    limitations_notes TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_obs_patient ON outcome_observations(patient_id, effective_at);
CREATE INDEX IF NOT EXISTS idx_outcome_obs_concept ON outcome_observations(concept_id);
CREATE INDEX IF NOT EXISTS idx_outcome_obs_instrument ON outcome_observations(instrument_id);

-- 7. Instrument Scoring Runs (Deterministic questionnaire calculations)
CREATE TABLE IF NOT EXISTS instrument_scoring_runs (
    id TEXT PRIMARY KEY,
    instrument_id TEXT NOT NULL REFERENCES measurement_instruments(id),
    instrument_version TEXT NOT NULL,
    observation_id TEXT NOT NULL REFERENCES outcome_observations(id),
    scoring_rule_code TEXT NOT NULL,
    scoring_version TEXT NOT NULL,
    total_items_count INTEGER NOT NULL,
    completed_items_count INTEGER NOT NULL,
    missing_items_count INTEGER NOT NULL,
    validity_check_passed INTEGER NOT NULL,
    calculated_score REAL,
    scoring_status TEXT NOT NULL, -- 'COMPLETED', 'INCOMPLETE', 'INVALID', 'UNLICENSED_METHOD_BLOCKED'
    calculation_manifest_json TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_scoring_runs_obs ON instrument_scoring_runs(observation_id);

-- 8. Outcome Comparisons (Governed compatibility and delta computation)
CREATE TABLE IF NOT EXISTS outcome_comparisons (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    comparison_type TEXT NOT NULL DEFAULT 'BASELINE_VS_FOLLOWUP', -- 'BASELINE_VS_FOLLOWUP', 'SEQUENTIAL_FOLLOWUP', 'MULTI_TIMEPOINT'
    left_observation_id TEXT NOT NULL REFERENCES outcome_observations(id),
    right_observation_id TEXT NOT NULL REFERENCES outcome_observations(id),
    compatibility_result TEXT NOT NULL, -- 'COMPARABLE', 'COMPARABLE_AFTER_APPROVED_CONVERSION', 'NOT_COMPARABLE_DIFFERENT_CONCEPT', 'NOT_COMPARABLE_DIFFERENT_INSTRUMENT', 'NOT_COMPARABLE_METHOD_OR_CONTEXT', 'UNIT_UNRESOLVED', 'SOURCE_UNVERIFIED', 'TIME_UNCERTAIN', 'MISSING_REQUIRED_DATA'
    compatibility_reason TEXT NOT NULL,
    delta_numeric REAL,
    delta_percentage REAL,
    direction_of_change TEXT, -- 'INCREASED', 'DECREASED', 'UNCHANGED', 'NOT_APPLICABLE'
    clinical_interpretation_label TEXT, -- e.g. 'NUMERIC_CHANGE_RECORDED' (NEVER autonomous 'treatment_success')
    calculation_method TEXT NOT NULL,
    limitations TEXT,
    status TEXT NOT NULL DEFAULT 'CALCULATED', -- 'CALCULATED', 'NOT_COMPARABLE', 'INSUFFICIENT_DATA', 'INVALID', 'REVIEW_REQUIRED'
    computed_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_comparisons_patient ON outcome_comparisons(patient_id, created_at);

-- 9. Treatment Exposure Contexts (Descriptive association without causal overclaim)
CREATE TABLE IF NOT EXISTS treatment_exposure_contexts (
    id TEXT PRIMARY KEY,
    episode_id TEXT REFERENCES care_episodes(id),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    prescription_id TEXT REFERENCES prescriptions(id),
    formulation_name TEXT NOT NULL,
    documented_start_date TEXT,
    documented_end_date TEXT,
    exposure_status TEXT NOT NULL DEFAULT 'PRESCRIBED_NOT_CONFIRMED_TAKEN', -- 'PRESCRIBED_NOT_CONFIRMED_TAKEN', 'DISPENSED_CONFIRMED', 'PATIENT_REPORTED_TAKEN', 'PATIENT_REPORTED_MISSED', 'DISCONTINUED_EARLY'
    patient_reported_adherence_percent REAL,
    clinician_reconciliation_state TEXT NOT NULL DEFAULT 'UNRECONCILED', -- 'RECONCILED', 'UNRECONCILED', 'DISCREPANCY_NOTED'
    co_interventions_json TEXT DEFAULT '[]',
    linked_adverse_effect_id TEXT,
    causality_disclaimer TEXT NOT NULL DEFAULT 'Temporal association does not establish causal efficacy.',
    recorded_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_treatment_exposure_patient ON treatment_exposure_contexts(patient_id);

-- 10. Outcome Interpretations (Separation of measurement from clinical interpretation)
CREATE TABLE IF NOT EXISTS outcome_interpretations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    episode_id TEXT REFERENCES care_episodes(id),
    encounter_id TEXT REFERENCES encounters(id),
    observation_ids_json TEXT NOT NULL DEFAULT '[]',
    comparison_ids_json TEXT NOT NULL DEFAULT '[]',
    interpretation_type TEXT NOT NULL, -- 'CLINICIAN_AUTHORED', 'APPROVED_RULE_OUTPUT', 'AI_DRAFT'
    interpretation_text TEXT NOT NULL,
    author_id TEXT NOT NULL REFERENCES users(id),
    author_role TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'REQUIRES_VALIDATION', 'READY_FOR_CLINICIAN_REVIEW', 'CLINICIAN_REVIEWED', 'CHANGES_REQUESTED', 'REJECTED'
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TEXT,
    review_notes TEXT,
    evidence_manifest_json TEXT NOT NULL DEFAULT '{}',
    limitations TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_interpretations_patient ON outcome_interpretations(patient_id, review_status);

-- 11. Outcome Aggregate Reports (Governed reporting with disclosure controls)
CREATE TABLE IF NOT EXISTS outcome_aggregate_reports (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    report_title TEXT NOT NULL,
    purpose TEXT NOT NULL,
    cohort_criteria_json TEXT NOT NULL,
    time_window_start TEXT NOT NULL,
    time_window_end TEXT NOT NULL,
    total_eligible_cohort INTEGER NOT NULL,
    measured_cohort INTEGER NOT NULL,
    missing_data_count INTEGER NOT NULL,
    missing_data_rate_percent REAL NOT NULL,
    minimum_cell_size_applied INTEGER NOT NULL DEFAULT 5,
    aggregated_metrics_json TEXT NOT NULL,
    limitations_disclaimer TEXT NOT NULL,
    generated_by TEXT NOT NULL REFERENCES users(id),
    approval_state TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'GOVERNANCE_APPROVED', 'REJECTED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_aggregate_reports_org ON outcome_aggregate_reports(organization_id, created_at);

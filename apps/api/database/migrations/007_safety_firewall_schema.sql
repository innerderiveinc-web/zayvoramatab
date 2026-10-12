-- Migration 007: Clinical Safety Firewall + Interaction & Contraindication Engine
-- Governed safety rules, normalized substances & aliases, interaction records,
-- auditable preflight runs, safety findings, and clinician overrides.
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Governed Normalized Substances Catalog (Ingredient & Drug Identity)
CREATE TABLE IF NOT EXISTS normalized_substances (
    id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    substance_type TEXT NOT NULL, -- 'BOTANICAL', 'MINERAL', 'ANIMAL', 'SYNTHETIC_ALLOPATHIC', 'POLYHERBAL_COMPOUND'
    botanical_binomial TEXT, -- Latin binomial e.g. 'Cassia angustifolia', 'Piper nigrum'
    plant_part TEXT, -- e.g. 'Leaves', 'Fruit', 'Bark', 'Root'
    preparation_details TEXT, -- e.g. 'Coarse Powder', 'Purified Extract', 'Calcined (Kushta)'
    atc_or_rxnorm_code TEXT,
    unani_temperament TEXT,
    toxicity_classification TEXT DEFAULT 'NON_TOXIC', -- 'NON_TOXIC', 'SCHEDULE_E1_POISON', 'CAUTION_RESTRICTED'
    is_mudabbar_required INTEGER NOT NULL DEFAULT 0,
    resolution_status TEXT NOT NULL DEFAULT 'RESOLVED', -- 'RESOLVED', 'AMBIGUOUS', 'UNRESOLVED', 'CONFLICTING'
    review_status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'DEPRECATED'
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_norm_subst_name ON normalized_substances(canonical_name);
CREATE INDEX IF NOT EXISTS idx_norm_subst_type ON normalized_substances(substance_type);

-- 2. Substance Aliases & Transliterations
CREATE TABLE IF NOT EXISTS substance_aliases (
    id TEXT PRIMARY KEY,
    substance_id TEXT NOT NULL REFERENCES normalized_substances(id) ON DELETE CASCADE,
    alias_name TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en', -- 'en', 'ur', 'ar', 'fa', 'hi'
    is_preferred INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_subst_alias_name ON substance_aliases(alias_name);
CREATE INDEX IF NOT EXISTS idx_subst_alias_subst ON substance_aliases(substance_id);

-- 3. Governed Safety Rules Registry
CREATE TABLE IF NOT EXISTS safety_rules (
    id TEXT PRIMARY KEY,
    rule_code TEXT NOT NULL UNIQUE, -- e.g. 'SAF-ALLERGY-001', 'SAF-DD-001', 'SAF-HD-001', 'SAF-CONTRA-001'
    rule_type TEXT NOT NULL, -- 'ALLERGY_MATCH', 'DRUG_DRUG_INTERACTION', 'HERB_DRUG_INTERACTION', 'HERB_HERB_INTERACTION', 'CONTRAINDICATION', 'PRECAUTION', 'DOSE_BOUNDS', 'DUPLICATE_THERAPY', 'RED_FLAG'
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    trigger_expression_json TEXT NOT NULL, -- Structured JSON criteria
    required_patient_factors_json TEXT NOT NULL DEFAULT '[]', -- JSON array: e.g. ['allergies', 'is_pregnant', 'renal_impairment']
    severity TEXT NOT NULL DEFAULT 'high', -- 'critical', 'high', 'moderate', 'low', 'informational'
    certainty TEXT NOT NULL DEFAULT 'established', -- 'established', 'probable', 'possible', 'insufficient_data'
    action_guidance TEXT NOT NULL,
    limitations TEXT,
    source_citation_id TEXT REFERENCES knowledge_sources(id),
    evidence_level TEXT NOT NULL DEFAULT 'EXPERT_OPINION',
    status TEXT NOT NULL DEFAULT 'approved', -- 'draft', 'under_review', 'approved', 'deprecated', 'rejected'
    version TEXT NOT NULL DEFAULT '1.0.0',
    effective_from TEXT,
    effective_until TEXT,
    reviewer_id TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    supersedes_rule_id TEXT REFERENCES safety_rules(id),
    jurisdiction TEXT DEFAULT 'GLOBAL',
    is_overridable INTEGER NOT NULL DEFAULT 1, -- 0 for strictly non-overridable critical blocks
    is_synthetic INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_rules_type_stat ON safety_rules(rule_type, status);
CREATE INDEX IF NOT EXISTS idx_safety_rules_code ON safety_rules(rule_code);

-- 4. Drug-Drug, Herb-Drug & Ingredient-Ingredient Interactions Catalog
CREATE TABLE IF NOT EXISTS interaction_records (
    id TEXT PRIMARY KEY,
    primary_substance_id TEXT NOT NULL REFERENCES normalized_substances(id) ON DELETE CASCADE,
    secondary_substance_id TEXT NOT NULL REFERENCES normalized_substances(id) ON DELETE CASCADE,
    interaction_type TEXT NOT NULL, -- 'DRUG_DRUG', 'HERB_DRUG', 'HERB_HERB', 'INGREDIENT_DUPLICATION'
    severity TEXT NOT NULL, -- 'critical', 'high', 'moderate', 'low', 'informational'
    certainty TEXT NOT NULL, -- 'established', 'probable', 'possible', 'insufficient_data'
    clinical_description TEXT NOT NULL,
    reported_outcome TEXT NOT NULL,
    management_guidance TEXT NOT NULL,
    evidence_type TEXT NOT NULL DEFAULT 'HUMAN_CLINICAL', -- 'HUMAN_CLINICAL', 'OBSERVATIONAL', 'ANIMAL_IN_VITRO', 'THEORETICAL_MECHANISTIC'
    source_citation_id TEXT REFERENCES knowledge_sources(id),
    limitations TEXT,
    review_status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'DEPRECATED'
    version TEXT NOT NULL DEFAULT '1.0.0',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_interactions_pair ON interaction_records(primary_substance_id, secondary_substance_id);
CREATE INDEX IF NOT EXISTS idx_interactions_type ON interaction_records(interaction_type, severity);

-- 5. Auditable Preflight Runs & Traceability
CREATE TABLE IF NOT EXISTS safety_preflight_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    prescription_id TEXT REFERENCES prescriptions(id) ON DELETE SET NULL,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    clinician_id TEXT NOT NULL REFERENCES users(id),
    overall_status TEXT NOT NULL, -- 'blocked', 'action_required', 'reviewed_with_cautions', 'no_applicable_alert_found', 'unable_to_assess', 'engine_unavailable'
    ruleset_version TEXT NOT NULL DEFAULT 'v2.0-governed',
    input_snapshot_json TEXT NOT NULL, -- Exact immutable JSON snapshot of patient and prescription inputs
    coverage_report_json TEXT NOT NULL, -- JSON coverage and limits report
    is_latest INTEGER NOT NULL DEFAULT 1,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_preflight_runs_rx ON safety_preflight_runs(prescription_id, is_latest);
CREATE INDEX IF NOT EXISTS idx_preflight_runs_pat ON safety_preflight_runs(patient_id);

-- 6. Safety Preflight Findings
CREATE TABLE IF NOT EXISTS safety_findings (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES safety_preflight_runs(id) ON DELETE CASCADE,
    rule_id TEXT REFERENCES safety_rules(id),
    rule_code TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    finding_type TEXT NOT NULL, -- 'ALLERGY', 'INTERACTION', 'CONTRAINDICATION', 'PRECAUTION', 'DOSE_OVERDOSE', 'DUPLICATE', 'STRUCTURAL_ERROR', 'RED_FLAG', 'MISSING_DATA'
    severity TEXT NOT NULL, -- 'critical', 'high', 'moderate', 'low', 'informational'
    certainty TEXT NOT NULL, -- 'established', 'probable', 'possible', 'insufficient_data'
    title TEXT NOT NULL,
    concise_rationale TEXT NOT NULL,
    matched_facts_json TEXT NOT NULL DEFAULT '{}',
    limitations TEXT,
    required_next_action TEXT NOT NULL,
    is_overridable INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'acknowledged', 'resolved_by_amendment', 'overridden_with_rationale', 'referred_for_review', 'not_applicable'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_findings_run ON safety_findings(run_id, status);
CREATE INDEX IF NOT EXISTS idx_safety_findings_sev ON safety_findings(severity);

-- 7. Clinician Finding Dispositions & Auditable Overrides
CREATE TABLE IF NOT EXISTS safety_finding_dispositions (
    id TEXT PRIMARY KEY,
    finding_id TEXT NOT NULL REFERENCES safety_findings(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES safety_preflight_runs(id) ON DELETE CASCADE,
    clinician_id TEXT NOT NULL REFERENCES users(id),
    disposition_type TEXT NOT NULL, -- 'ACKNOWLEDGED', 'OVERRIDDEN_WITH_RATIONALE', 'RESOLVED_BY_AMENDMENT', 'REFERRED_FOR_REVIEW'
    clinical_rationale TEXT NOT NULL,
    policy_reference TEXT,
    override_approved_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_finding_dispositions_find ON safety_finding_dispositions(finding_id);

-- 8. Rule Simulator Test Cases & Regression Results
CREATE TABLE IF NOT EXISTS safety_rule_test_cases (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL REFERENCES safety_rules(id) ON DELETE CASCADE,
    case_name TEXT NOT NULL,
    description TEXT,
    synthetic_input_json TEXT NOT NULL,
    expected_severity TEXT NOT NULL,
    expected_status TEXT NOT NULL, -- 'EXPECTED_TRIGGER', 'EXPECTED_PASS', 'EXPECTED_UNABLE_TO_ASSESS'
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS safety_rule_test_results (
    id TEXT PRIMARY KEY,
    test_case_id TEXT NOT NULL REFERENCES safety_rule_test_cases(id) ON DELETE CASCADE,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    outcome TEXT NOT NULL, -- 'PASSED', 'FAILED', 'ERROR'
    actual_severity TEXT,
    error_message TEXT
);

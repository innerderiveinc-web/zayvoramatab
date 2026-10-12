-- Migration 004: Unani Clinical Assessment, Organ-Axis Mapping, and Usul-e-Ilaj Care Planning
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Unani Assessment Templates
CREATE TABLE IF NOT EXISTS unani_assessment_templates (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- e.g. 'TMPL-UNANI-CORE', 'TMPL-MIZAJ-EXTENDED'
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'ur', -- 'ur', 'en', 'hi'
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'DRAFT', 'RETIRED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Immutable Assessment Template Versions
CREATE TABLE IF NOT EXISTS unani_assessment_template_versions (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES unani_assessment_templates(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    definition_json TEXT NOT NULL, -- Serialized prompt structure & instructions
    validation_metadata TEXT,
    author_id TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'RETIRED'
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    effective_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_tmpl_ver_status ON unani_assessment_template_versions(template_id, status);

-- 3. Version-Scoped Assessment Domains
CREATE TABLE IF NOT EXISTS unani_assessment_domains (
    id TEXT PRIMARY KEY,
    template_version_id TEXT NOT NULL REFERENCES unani_assessment_template_versions(id) ON DELETE CASCADE,
    domain_key TEXT NOT NULL, -- 'MIZAJ', 'AFAAL', 'ASBAB_SITTAH', 'ALAMAT', 'NABZ', 'BAUL', 'BARAZ'
    label TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_mandatory INTEGER NOT NULL DEFAULT 0,
    UNIQUE(template_version_id, domain_key)
);

-- 4. Assessment Options Taxonomy
CREATE TABLE IF NOT EXISTS unani_assessment_options (
    id TEXT PRIMARY KEY,
    domain_id TEXT NOT NULL REFERENCES unani_assessment_domains(id) ON DELETE CASCADE,
    option_key TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    score_weights_json TEXT, -- Optional weights (inactive without approved scoring instrument)
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(domain_id, option_key)
);

-- 5. Clinical Governance Review Records
CREATE TABLE IF NOT EXISTS clinical_review_records (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL, -- 'TEMPLATE_VERSION', 'ORGAN_AXIS_MAPPING', 'USUL_E_ILAJ_PRINCIPLE'
    entity_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL, -- 'APPROVED', 'REJECTED', 'RETIRED'
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clin_rev_entity ON clinical_review_records(entity_type, entity_id);

-- 6. Encounter Unani Assessments (Header)
CREATE TABLE IF NOT EXISTS unani_assessments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    template_version_id TEXT NOT NULL REFERENCES unani_assessment_template_versions(id),
    author_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'FINALISED', 'SUPERSEDED'
    assessment_date DATE NOT NULL,
    dominant_mizaj TEXT NOT NULL DEFAULT 'NOT_ASSESSED', -- 'DAMAWWI', 'BALGHAMI', 'SAFRAWI', 'SAUDAWI', 'MOTADIL', 'NOT_ASSESSED', 'UNCERTAIN', 'MIXED'
    secondary_mizaj TEXT,
    mizaj_rationale TEXT,
    mizaj_uncertainty TEXT NOT NULL DEFAULT 'NOT_ASSESSED', -- 'HIGH_CONFIDENCE', 'MODERATE_CONFIDENCE', 'UNCERTAIN', 'PROVISIONAL', 'NOT_ASSESSED'
    clinical_reasoning TEXT,
    alternative_considerations TEXT,
    unresolved_questions TEXT,
    version_number INTEGER NOT NULL DEFAULT 1,
    parent_assessment_id TEXT REFERENCES unani_assessments(id),
    signed_at TIMESTAMP,
    signed_by TEXT REFERENCES users(id),
    signature_hash TEXT,
    signed_snapshot TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_unani_assess_patient ON unani_assessments(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_unani_assess_encounter ON unani_assessments(encounter_id, status);
CREATE INDEX IF NOT EXISTS idx_unani_assess_org ON unani_assessments(organization_id, status);

-- 7. Assessment Field Responses (Observations & Findings with Provenance)
CREATE TABLE IF NOT EXISTS unani_assessment_responses (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES unani_assessments(id) ON DELETE CASCADE,
    domain_key TEXT NOT NULL, -- 'MIZAJ', 'AFAAL', 'ASBAB_SITTAH', etc.
    field_key TEXT NOT NULL, -- 'lawn_complexion', 'makool_mashroob', 'quwwat_hazima', etc.
    field_label TEXT NOT NULL,
    field_value TEXT,
    data_type TEXT NOT NULL DEFAULT 'TEXT', -- 'TEXT', 'OPTION', 'NUMBER', 'BOOLEAN'
    unit TEXT,
    semantic_state TEXT NOT NULL DEFAULT 'OBSERVED', -- 'OBSERVED', 'NORMAL', 'IMPAIRED', 'UNKNOWN', 'NOT_ASKED', 'NOT_ASSESSED', 'NOT_APPLICABLE'
    provenance TEXT NOT NULL DEFAULT 'CLINICIAN_OBSERVED', -- 'PATIENT_REPORTED', 'CLINICIAN_OBSERVED', 'MEASURED', 'IMPORTED', 'AI_DRAFTED'
    observed_at TIMESTAMP,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_unani_resp_assess ON unani_assessment_responses(assessment_id, domain_key);

-- 8. Structured Diagnostic Conclusions
CREATE TABLE IF NOT EXISTS unani_assessment_conclusions (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES unani_assessments(id) ON DELETE CASCADE,
    conclusion_type TEXT NOT NULL, -- 'MIZAJ', 'SU_E_MIZAJ', 'MARAZ', 'FUNCTIONAL_IMPAIRMENT'
    code TEXT,
    title TEXT NOT NULL,
    description TEXT,
    evidence_notes TEXT,
    certainty TEXT NOT NULL DEFAULT 'PROVISIONAL', -- 'DEFINITIVE', 'PROVISIONAL', 'DIFFERENTIAL', 'UNCERTAIN'
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_unani_conc_assess ON unani_assessment_conclusions(assessment_id);

-- 9. Assessment Amendments
CREATE TABLE IF NOT EXISTS unani_assessment_amendments (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES unani_assessments(id) ON DELETE CASCADE,
    amended_assessment_id TEXT NOT NULL REFERENCES unani_assessments(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    author_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Organ-Axis Concepts Catalog
CREATE TABLE IF NOT EXISTS organ_axis_concepts (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- 'MEDA', 'KABID', 'QALB', 'DIMAGH', 'KULYAH', 'REEH', 'ASAAB'
    canonical_name TEXT NOT NULL,
    unani_name TEXT NOT NULL,
    anatomical_correlate TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' -- 'ACTIVE', 'RETIRED'
);

-- 11. Organ-Axis Mappings (Contextual Associations)
CREATE TABLE IF NOT EXISTS organ_axis_mappings (
    id TEXT PRIMARY KEY,
    source_concept_id TEXT NOT NULL REFERENCES organ_axis_concepts(id) ON DELETE CASCADE,
    target_concept_id TEXT NOT NULL REFERENCES organ_axis_concepts(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL DEFAULT 'ASSOCIATED_WITH', -- 'ASSOCIATED_WITH', 'TRADITIONALLY_RELATED_TO', 'MAY_PROMPT_REVIEW_OF', 'NOT_EQUIVALENT_TO'
    plain_explanation TEXT NOT NULL,
    clinical_utility_notes TEXT,
    evidence_level TEXT NOT NULL DEFAULT 'HISTORICAL_BENCHMARK', -- 'REVIEWED', 'UNREVIEWED', 'HISTORICAL_BENCHMARK'
    status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'RETIRED'
    source_id TEXT REFERENCES clinical_sources(id),
    source_locator TEXT, -- e.g. 'Al-Qanun fi al-Tibb, Vol 1, Discourse on Digestion'
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_oa_mappings_pair ON organ_axis_mappings(source_concept_id, target_concept_id, status);

-- 12. Assessment Mapping Results (Encounter Exposure Audit)
CREATE TABLE IF NOT EXISTS assessment_mapping_results (
    id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES unani_assessments(id) ON DELETE CASCADE,
    mapping_id TEXT NOT NULL REFERENCES organ_axis_mappings(id) ON DELETE CASCADE,
    clinician_acknowledged INTEGER NOT NULL DEFAULT 0,
    clinician_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. Usul-e-Ilaj Treatment Principles Vocabulary
CREATE TABLE IF NOT EXISTS usul_e_ilaj_principles (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- 'TANQIYA', 'TADEEL_E_MIZAJ', 'TAHLEEL', 'TAQWIYAT', 'HIFZ_E_SEHAT', 'TASKEEN'
    name_unani TEXT NOT NULL,
    name_english TEXT NOT NULL,
    name_urdu TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' -- 'ACTIVE', 'RETIRED'
);

-- 14. Immutable Principle Versions
CREATE TABLE IF NOT EXISTS usul_e_ilaj_principle_versions (
    id TEXT PRIMARY KEY,
    principle_id TEXT NOT NULL REFERENCES usul_e_ilaj_principles(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    definition TEXT NOT NULL,
    indications TEXT,
    contraindications TEXT,
    monitoring_guidance TEXT,
    status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'RETIRED'
    source_id TEXT REFERENCES clinical_sources(id),
    source_locator TEXT,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(principle_id, version_number)
);

-- 15. Care Plans (Header)
CREATE TABLE IF NOT EXISTS care_plans (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    author_id TEXT NOT NULL REFERENCES users(id),
    responsible_practitioner_id TEXT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    overall_goal TEXT,
    clinical_rationale TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'PROPOSED', 'ACTIVE', 'COMPLETED', 'DISCONTINUED', 'SUPERSEDED'
    review_date DATE,
    finalised_at TIMESTAMP,
    finalised_by TEXT REFERENCES users(id),
    version_number INTEGER NOT NULL DEFAULT 1,
    parent_care_plan_id TEXT REFERENCES care_plans(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_care_plans_patient ON care_plans(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_care_plans_encounter ON care_plans(encounter_id, status);
CREATE INDEX IF NOT EXISTS idx_care_plans_org ON care_plans(organization_id, status);

-- 16. Care Plan Line Items (Principles & Interventions)
CREATE TABLE IF NOT EXISTS care_plan_items (
    id TEXT PRIMARY KEY,
    care_plan_id TEXT NOT NULL REFERENCES care_plans(id) ON DELETE CASCADE,
    principle_id TEXT REFERENCES usul_e_ilaj_principles(id),
    principle_version_id TEXT REFERENCES usul_e_ilaj_principle_versions(id),
    objective TEXT NOT NULL,
    clinician_rationale TEXT,
    intended_intervention TEXT NOT NULL,
    cautions TEXT,
    monitoring_plan TEXT,
    expected_outcome TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'COMPLETED', 'DISCONTINUED', 'SUPERSEDED'
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_care_plan_items_cp ON care_plan_items(care_plan_id, sort_order);

-- 17. Care Plan Links to Prescriptions
CREATE TABLE IF NOT EXISTS care_plan_links (
    id TEXT PRIMARY KEY,
    care_plan_id TEXT NOT NULL REFERENCES care_plans(id) ON DELETE CASCADE,
    care_plan_item_id TEXT REFERENCES care_plan_items(id) ON DELETE CASCADE,
    link_type TEXT NOT NULL DEFAULT 'PRESCRIPTION_DRAFT', -- 'PRESCRIPTION_DRAFT', 'PRESCRIPTION_SIGNED'
    prescription_id TEXT NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_care_plan_links_rx ON care_plan_links(prescription_id);

-- 18. Care Plan Follow-up Outcomes
CREATE TABLE IF NOT EXISTS care_plan_outcomes (
    id TEXT PRIMARY KEY,
    care_plan_item_id TEXT NOT NULL REFERENCES care_plan_items(id) ON DELETE CASCADE,
    outcome_status TEXT NOT NULL, -- 'ACHIEVED', 'PARTIALLY_ACHIEVED', 'NOT_ACHIEVED', 'UNRESOLVED', 'ADVERSE_REACTION'
    observation_notes TEXT NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    uncertainty_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cp_outcomes_item ON care_plan_outcomes(care_plan_item_id);

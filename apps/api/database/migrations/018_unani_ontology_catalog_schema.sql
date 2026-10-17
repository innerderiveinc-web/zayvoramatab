-- Migration 018: Unani Ontology, Canonical Terminology, Mufradat Material Identity,
-- Murakkabat Formulation Catalog, Source-Grounded Knowledge Assertions, and Review Tasks
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Knowledge Concepts (Stable Identity Object)
CREATE TABLE IF NOT EXISTS knowledge_concepts (
    id TEXT PRIMARY KEY,
    concept_type TEXT NOT NULL, -- 'unani_term', 'clinical_process', 'organ_or_structure', 'material', 'ingredient', 'formulation', 'dosage_form', 'preparation_method', 'assessment_concept', 'external_concept'
    canonical_label TEXT NOT NULL, -- Editorial display label (never treated as verbatim source quote)
    definition_assertion_id TEXT, -- Pointer to approved sourced definition assertion
    status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'in_review', 'approved_identity', 'restricted', 'deprecated', 'withdrawn'
    identity_resolution_state TEXT NOT NULL DEFAULT 'unresolved', -- 'unresolved', 'candidate', 'resolved', 'disputed'
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES knowledge_concepts(id),
    review_notes TEXT,
    created_by TEXT NOT NULL,
    updated_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_concepts_type_status ON knowledge_concepts(concept_type, status);
CREATE INDEX IF NOT EXISTS idx_k_concepts_label ON knowledge_concepts(canonical_label);
CREATE INDEX IF NOT EXISTS idx_k_concepts_resolution ON knowledge_concepts(identity_resolution_state);

-- 2. Concept Names (Multi-script, original wording, transliterations, synonyms)
CREATE TABLE IF NOT EXISTS concept_names (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    name_text_original TEXT NOT NULL,
    script TEXT NOT NULL DEFAULT 'latin', -- 'arabic', 'urdu', 'persian', 'devanagari', 'latin'
    language_tag TEXT NOT NULL DEFAULT 'en', -- 'ur', 'ar', 'fa', 'hi', 'en', 'la', 'sa'
    transliteration TEXT,
    transliteration_scheme TEXT,
    normalized_search_text TEXT NOT NULL,
    name_type TEXT NOT NULL DEFAULT 'preferred_label', -- 'source_name', 'preferred_label', 'synonym', 'variant_spelling', 'regional_name', 'historical_name', 'trade_name', 'common_name', 'scientific_name', 'candidate_alias'
    source_passage_id TEXT REFERENCES kavs_extraction_segments(id),
    assertion_id TEXT, -- Substantive alias assertion ID
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'pending', 'approved', 'rejected', 'disputed'
    valid_from TEXT,
    valid_to TEXT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_concept_names_cid_state ON concept_names(concept_id, review_state);
CREATE INDEX IF NOT EXISTS idx_concept_names_norm ON concept_names(normalized_search_text);
CREATE INDEX IF NOT EXISTS idx_concept_names_script_lang ON concept_names(script, language_tag);

-- 3. Material Identity (Mufradat / Single-drug with explicit ambiguity representation)
CREATE TABLE IF NOT EXISTS material_identity (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL UNIQUE REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    material_class TEXT NOT NULL DEFAULT 'botanical', -- 'botanical', 'animal_derived', 'mineral', 'metal', 'salt', 'processed_material', 'other', 'unknown'
    identity_status TEXT NOT NULL DEFAULT 'unresolved', -- 'unresolved', 'candidate', 'reviewed', 'disputed', 'rejected'
    scientific_name TEXT, -- Sourced Latin binomial
    taxonomic_authority TEXT, -- e.g. 'IPNI', 'POWO', 'Species Plantarum L.'
    external_identifier TEXT, -- e.g. 'IPNI:12345'
    plant_part_or_material_form TEXT, -- e.g. 'Dried ripe fruit', 'Bark', 'Resin'
    geographic_or_source_context TEXT,
    processing_state TEXT, -- 'Raw', 'Purified (Mudabbar)', 'Calcined (Kushta)'
    identity_evidence_assertion_id TEXT,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mat_id_class_status ON material_identity(material_class, identity_status);
CREATE INDEX IF NOT EXISTS idx_mat_id_sci_name ON material_identity(scientific_name);

-- 4. Catalog Formulations (Murakkabat compound formulations from literature/editions)
CREATE TABLE IF NOT EXISTS catalog_formulations (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL UNIQUE REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    formulation_class TEXT NOT NULL DEFAULT 'unknown', -- 'majoon', 'safoof', 'sharbat', 'hab', 'qurs', 'khamira', 'joshanda', 'roghan', 'arq', 'itrifal', 'kushta', 'marham', 'tila', 'unknown'
    source_specific_name TEXT NOT NULL,
    source_edition_id TEXT REFERENCES kavs_source_versions(id),
    identity_status TEXT NOT NULL DEFAULT 'unresolved', -- 'unresolved', 'candidate', 'reviewed', 'disputed', 'rejected'
    dosage_form TEXT, -- Sourced dosage form string
    preparation_description_assertion_id TEXT,
    formula_version TEXT,
    status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'in_review', 'approved_identity', 'deprecated', 'withdrawn'
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cat_forms_class_status ON catalog_formulations(formulation_class, status);
CREATE INDEX IF NOT EXISTS idx_cat_forms_src_edition ON catalog_formulations(source_edition_id);

-- 5. Catalog Formulation Ingredients (Source-backed component statements)
CREATE TABLE IF NOT EXISTS catalog_formulation_ingredients (
    id TEXT PRIMARY KEY,
    formulation_id TEXT NOT NULL REFERENCES catalog_formulations(id) ON DELETE CASCADE,
    material_concept_id TEXT REFERENCES knowledge_concepts(id),
    source_component_name_original TEXT NOT NULL,
    source_passage_id TEXT REFERENCES kavs_extraction_segments(id),
    assertion_id TEXT,
    quantity_value REAL,
    quantity_min REAL,
    quantity_max REAL,
    quantity_unit_original TEXT, -- e.g. 'masha', 'tola', 'dirham', 'dam', 'ser'
    quantity_unit_normalized TEXT, -- e.g. 'g', 'mg', 'ml' (only when verified conversion rule exists)
    quantity_expression_original TEXT, -- Verbatim notation e.g. '2 1/2 masha'
    quantity_basis TEXT NOT NULL DEFAULT 'unknown', -- 'mass', 'volume', 'count', 'ratio', 'parts', 'other', 'unknown'
    processing_instruction_assertion_id TEXT,
    component_identity_state TEXT NOT NULL DEFAULT 'unresolved', -- 'unresolved', 'candidate', 'reviewed', 'disputed'
    quantity_review_state TEXT NOT NULL DEFAULT 'unreviewed', -- 'unreviewed', 'reviewed', 'ambiguous', 'not_stated'
    sequence_index INTEGER,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cat_form_ingr_form ON catalog_formulation_ingredients(formulation_id);
CREATE INDEX IF NOT EXISTS idx_cat_form_ingr_mat ON catalog_formulation_ingredients(material_concept_id);
CREATE INDEX IF NOT EXISTS idx_cat_form_ingr_states ON catalog_formulation_ingredients(component_identity_state, quantity_review_state);

-- 6. Knowledge Assertions (Provenance-bound claims and assertions)
CREATE TABLE IF NOT EXISTS knowledge_assertions (
    id TEXT PRIMARY KEY,
    subject_concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL, -- e.g. 'has_mizaj', 'has_action', 'indicated_for', 'contraindicated_in', 'has_adverse_effect', 'has_corrective', 'has_substitute', 'has_dose', 'has_part', 'prepared_by', 'has_definition', 'has_synonym'
    object_concept_id TEXT REFERENCES knowledge_concepts(id),
    object_literal TEXT,
    source_passage_id TEXT REFERENCES kavs_extraction_segments(id),
    source_quote_exact TEXT, -- Verbatim extracted quote
    source_language TEXT DEFAULT 'en',
    source_script TEXT DEFAULT 'latin',
    page_locator TEXT,
    section_locator TEXT,
    table_locator TEXT,
    figure_locator TEXT,
    assertion_scope TEXT NOT NULL DEFAULT 'identity', -- 'identity', 'terminology', 'composition', 'preparation', 'historical', 'traditional_use', 'clinical', 'safety', 'regulatory', 'other'
    interpretation_note TEXT,
    evidence_characterization TEXT NOT NULL DEFAULT 'traditional_description', -- 'classical_description', 'pharmacopoeial_specification', 'empirical_observation', 'clinical_study', 'expert_consensus', 'unverified_claim'
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'source_check_required', 'extraction_review_required', 'expert_review_required', 'changes_requested', 'approved_for_defined_use', 'rejected', 'deprecated', 'withdrawn'
    approved_intended_use TEXT, -- 'clinician_contextual_reference', 'formulation_catalog_reference', 'safety_firewall_rule', 'educational_reference', 'unapproved'
    reviewer_id TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    decision_rationale TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES knowledge_assertions(id),
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_k_assertions_sub_pred ON knowledge_assertions(subject_concept_id, predicate);
CREATE INDEX IF NOT EXISTS idx_k_assertions_scope_state ON knowledge_assertions(assertion_scope, review_state);
CREATE INDEX IF NOT EXISTS idx_k_assertions_intended_use ON knowledge_assertions(approved_intended_use);

-- 7. Concept Relations (Typed relationship registry for taxonomy & navigation)
CREATE TABLE IF NOT EXISTS concept_relations (
    id TEXT PRIMARY KEY,
    subject_concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    predicate TEXT NOT NULL,
    object_concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    assertion_id TEXT REFERENCES knowledge_assertions(id), -- Substantive relation must point to approved assertion
    relation_class TEXT NOT NULL DEFAULT 'terminology', -- 'taxonomy', 'terminology', 'identity_candidate', 'formulation_component', 'historical', 'clinical', 'safety', 'external_crosswalk', 'other'
    status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'pending_review', 'approved', 'disputed', 'rejected', 'deprecated'
    directionality TEXT NOT NULL DEFAULT 'directed', -- 'directed', 'bidirectional'
    valid_time TEXT,
    created_by TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_c_relations_sub_obj ON concept_relations(subject_concept_id, object_concept_id);
CREATE INDEX IF NOT EXISTS idx_c_relations_class_status ON concept_relations(relation_class, status);

-- 8. External Identifier Crosswalks (Explicit, non-inferred mappings)
CREATE TABLE IF NOT EXISTS external_identifier_crosswalks (
    id TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    system_uri TEXT NOT NULL, -- e.g. 'http://id.nlm.nih.gov/mesh', 'http://snomed.info/sct', 'urn:ipni.org:names', 'urn:kew.org:wcvp'
    system_label TEXT NOT NULL, -- e.g. 'MeSH', 'SNOMED-CT', 'IPNI', 'POWO', 'NCBI'
    external_code TEXT NOT NULL,
    external_preferred_label TEXT,
    mapping_type TEXT NOT NULL DEFAULT 'related_to', -- 'exact', 'broader_than', 'narrower_than', 'related_to', 'candidate_equivalence', 'no_safe_mapping'
    status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'approved', 'disputed', 'rejected'
    evidence_assertion_id TEXT REFERENCES knowledge_assertions(id),
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crosswalks_cid_sys ON external_identifier_crosswalks(concept_id, system_label);
CREATE INDEX IF NOT EXISTS idx_crosswalks_ext_code ON external_identifier_crosswalks(system_label, external_code);

-- 9. Catalog Change Events (Append-only audit trail)
CREATE TABLE IF NOT EXISTS catalog_change_events (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL, -- 'concept', 'name', 'material', 'formulation', 'ingredient', 'assertion', 'relation', 'crosswalk'
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL, -- 'CREATE', 'UPDATE', 'SUBMIT_REVIEW', 'APPROVE', 'REJECT', 'DISPUTE', 'WITHDRAW', 'DEPRECATE'
    prior_state_json TEXT,
    new_state_json TEXT,
    actor_id TEXT NOT NULL,
    rationale TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cat_change_entity ON catalog_change_events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_cat_change_actor ON catalog_change_events(actor_id);

-- 10. Catalog Review Tasks (Role-gated review queues)
CREATE TABLE IF NOT EXISTS catalog_review_tasks (
    id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    task_type TEXT NOT NULL, -- 'PASSAGE_FIDELITY', 'TERMINOLOGY_TRANSLITERATION', 'MATERIAL_TAXONOMY', 'FORMULATION_COMPOSITION', 'MODERN_CROSSWALK', 'CLINICAL_ASSERTION', 'CONFLICT_ADJUDICATION'
    priority TEXT NOT NULL DEFAULT 'MEDIUM', -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'IN_REVIEW', 'APPROVED', 'CHANGES_REQUESTED', 'REJECTED'
    assigned_role TEXT NOT NULL DEFAULT 'UNANI_SCHOLAR', -- 'UNANI_SCHOLAR', 'BOTANIST', 'PHARMACOGNOSIST', 'CLINICAL_GOVERNANCE_LEAD'
    assigned_to TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cat_rev_tasks_status ON catalog_review_tasks(status, task_type);
CREATE INDEX IF NOT EXISTS idx_cat_rev_tasks_entity ON catalog_review_tasks(entity_type, entity_id);

-- Migration 019: Unani Clinical Knowledge Mapping, Relation Type Registry,
-- Versioned Organ-Axis Frameworks, Cross-Disciplinary Concept Mappings,
-- Relationship Conflicts Adjudication, and Encounter-Scoped Hypotheses
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Controlled Relation-Type Registry
CREATE TABLE IF NOT EXISTS relation_type_registry (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL,
    definition TEXT NOT NULL,
    relation_class TEXT NOT NULL, -- 'source_documentation', 'terminology', 'identity_crosswalk', 'unani_knowledge', 'modern_clinical', 'product_navigation', 'patient_specific'
    subject_type_constraints_json TEXT NOT NULL DEFAULT '[]', -- JSON array of allowed subject concept types
    object_type_constraints_json TEXT NOT NULL DEFAULT '[]', -- JSON array of allowed object concept types
    directionality TEXT NOT NULL DEFAULT 'directed', -- 'directed', 'bidirectional'
    is_clinically_actionable INTEGER NOT NULL DEFAULT 0,
    requires_source_assertion INTEGER NOT NULL DEFAULT 1,
    required_reviewer_roles_json TEXT NOT NULL DEFAULT '["UNANI_SCHOLAR"]',
    allowed_intended_uses_json TEXT NOT NULL DEFAULT '["clinician_contextual_reference"]',
    ui_display_label TEXT NOT NULL,
    ui_warning_text TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'UNDER_REVIEW', 'APPROVED', 'DEPRECATED'
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rel_type_code ON relation_type_registry(code);
CREATE INDEX IF NOT EXISTS idx_rel_type_class ON relation_type_registry(relation_class, status);

-- 2. Provenance-Bound Relationship Assertions
CREATE TABLE IF NOT EXISTS relationship_assertions (
    id TEXT PRIMARY KEY,
    subject_concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    predicate_type_id TEXT NOT NULL REFERENCES relation_type_registry(id) ON DELETE CASCADE,
    object_concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    assertion_id TEXT REFERENCES knowledge_assertions(id), -- Provenance claim link; required for substantive relationships
    relationship_level TEXT NOT NULL DEFAULT 'classical_text', -- 'ui_navigation_grouping', 'classical_text', 'clinician_authored_case_hypothesis', 'reviewed_evidence_based', 'research_hypothesis'
    scope TEXT NOT NULL DEFAULT 'global',
    context TEXT,
    qualifiers_json TEXT DEFAULT '{}',
    polarity TEXT NOT NULL DEFAULT 'supports', -- 'supports', 'refutes', 'uncertain', 'not_applicable'
    valid_from TEXT,
    valid_to TEXT,
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'source_check_required', 'expert_review_required', 'approved_for_defined_use', 'changes_requested', 'disputed', 'rejected', 'deprecated', 'withdrawn'
    intended_use_approval TEXT DEFAULT 'unapproved',
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES relationship_assertions(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    decision_rationale TEXT
);

CREATE INDEX IF NOT EXISTS idx_rel_assert_sub_obj ON relationship_assertions(subject_concept_id, object_concept_id);
CREATE INDEX IF NOT EXISTS idx_rel_assert_level_state ON relationship_assertions(relationship_level, review_state);

-- 3. Versioned Organ-Axis Frameworks (Product Conceptual Model)
CREATE TABLE IF NOT EXISTS organ_axis_frameworks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL, -- e.g. '1.0.0'
    framework_type TEXT NOT NULL DEFAULT 'product_navigation_model', -- 'product_navigation_model', 'traditional_model', 'research_model', 'clinical_model'
    description TEXT NOT NULL,
    purpose TEXT NOT NULL,
    limitations TEXT NOT NULL,
    source_basis_json TEXT NOT NULL DEFAULT '[]', -- JSON array of source IDs
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'under_review', 'approved', 'deprecated', 'withdrawn'
    approved_use_scope TEXT DEFAULT 'navigation_only', -- 'navigation_only', 'clinician_contextual_reference', 'clinical_decision_support'
    effective_from TEXT,
    effective_to TEXT,
    supersedes_id TEXT REFERENCES organ_axis_frameworks(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version)
);

CREATE INDEX IF NOT EXISTS idx_oa_framework_name_ver ON organ_axis_frameworks(name, version);
CREATE INDEX IF NOT EXISTS idx_oa_framework_state ON organ_axis_frameworks(framework_type, review_state);

-- 4. Organ-Axis Memberships
CREATE TABLE IF NOT EXISTS organ_axis_memberships (
    id TEXT PRIMARY KEY,
    framework_id TEXT NOT NULL REFERENCES organ_axis_frameworks(id) ON DELETE CASCADE,
    concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    axis_name TEXT NOT NULL, -- e.g. 'GASTRO_HEPATIC_AXIS', 'BRAIN_GUT_AXIS', 'CARDIO_PULMONARY_AXIS'
    membership_type TEXT NOT NULL DEFAULT 'navigation_group', -- 'navigation_group', 'source_documented_membership', 'reviewed_clinical_membership', 'research_hypothesis'
    assertion_id TEXT REFERENCES knowledge_assertions(id), -- Required for source/clinical claims
    display_order INTEGER NOT NULL DEFAULT 0,
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'approved', 'disputed', 'rejected'
    limitations TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES organ_axis_memberships(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_oa_member_frm_axis ON organ_axis_memberships(framework_id, axis_name);
CREATE INDEX IF NOT EXISTS idx_oa_member_concept ON organ_axis_memberships(concept_id);

-- 5. Cross-Disciplinary Concept Mappings
CREATE TABLE IF NOT EXISTS concept_mappings (
    id TEXT PRIMARY KEY,
    source_concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    target_system TEXT NOT NULL, -- 'ICD-11', 'SNOMED-CT', 'LOINC', 'MeSH', 'POWO'
    target_system_version TEXT,
    target_identifier TEXT NOT NULL,
    target_label TEXT NOT NULL,
    mapping_type TEXT NOT NULL DEFAULT 'related_to', -- 'exact', 'broader_than', 'narrower_than', 'related_to', 'candidate_equivalence', 'no_safe_mapping'
    mapping_scope TEXT DEFAULT 'general',
    limitations TEXT,
    evidence_assertion_id TEXT REFERENCES knowledge_assertions(id),
    review_state TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'under_review', 'approved', 'disputed', 'rejected'
    approved_intended_use TEXT DEFAULT 'unapproved',
    reviewer_id TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_id TEXT REFERENCES concept_mappings(id),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_c_mappings_src_sys ON concept_mappings(source_concept_id, target_system);
CREATE INDEX IF NOT EXISTS idx_c_mappings_target ON concept_mappings(target_system, target_identifier);
CREATE INDEX IF NOT EXISTS idx_c_mappings_type_state ON concept_mappings(mapping_type, review_state);

-- 6. Relationship Conflicts Adjudication
CREATE TABLE IF NOT EXISTS relationship_conflicts (
    id TEXT PRIMARY KEY,
    assertion_id TEXT NOT NULL REFERENCES knowledge_assertions(id) ON DELETE CASCADE,
    conflicting_assertion_id TEXT NOT NULL REFERENCES knowledge_assertions(id) ON DELETE CASCADE,
    conflict_type TEXT NOT NULL DEFAULT 'source_disagreement', -- 'source_disagreement', 'identity_ambiguity', 'interpretation_disagreement', 'temporal_difference', 'scope_mismatch', 'other'
    description TEXT NOT NULL,
    resolution_state TEXT NOT NULL DEFAULT 'open', -- 'open', 'under_review', 'resolved_with_scope', 'unresolved', 'not_a_true_conflict'
    resolution_rationale TEXT,
    resolved_by TEXT REFERENCES users(id),
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rel_conflicts_state ON relationship_conflicts(resolution_state, conflict_type);
CREATE INDEX IF NOT EXISTS idx_rel_conflicts_asserts ON relationship_conflicts(assertion_id, conflicting_assertion_id);

-- 7. Encounter-Scoped Case Hypotheses (Protected Patient Clinical Record Only)
CREATE TABLE IF NOT EXISTS case_hypothesis_links (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    concept_id TEXT NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
    relation_type_code TEXT NOT NULL,
    clinical_note_reference TEXT,
    hypothesis_text TEXT NOT NULL,
    author_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'considered', 'rejected', 'resolved', 'historical'
    supporting_observation_ids_json TEXT NOT NULL DEFAULT '[]',
    referenced_assertion_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_case_hypo_enc ON case_hypothesis_links(encounter_id, status);
CREATE INDEX IF NOT EXISTS idx_case_hypo_concept ON case_hypothesis_links(concept_id);

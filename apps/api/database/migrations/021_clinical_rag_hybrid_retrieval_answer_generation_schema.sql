-- Migration 021: Evidence-Aware Clinical Knowledge Retrieval (Hybrid RAG) & Answer Generation Schema
-- Phase 22 of ZAYVORA MATAB OS
-- Strict non-negotiables: Zero hallucination, per-claim citation binding, server-side intended-use gating,
-- fail-closed clinical publication perimeter, and honest abstention.

-- 1. Reviewed Query-Intent Registry
CREATE TABLE IF NOT EXISTS rag_query_intent_registry (
    intent_code TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    allowed_surfaces_json TEXT NOT NULL DEFAULT '[]',
    prohibited_actions_json TEXT NOT NULL DEFAULT '[]',
    requires_strict_abstention INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed controlled query intents
INSERT OR IGNORE INTO rag_query_intent_registry (
    intent_code, category, description, allowed_surfaces_json, prohibited_actions_json, requires_strict_abstention
) VALUES
('source_lookup', 'LOOKUP', 'Locate a specified source, author, edition, or passage locator.', '["research_workspace", "educational_reference", "clinician_context"]', '["prescribe", "diagnose", "dose"]', 0),
('terminology_lookup', 'LOOKUP', 'Explain an approved Unani or botanical term with canonical context.', '["educational_reference", "research_workspace", "clinician_context"]', '["prescribe", "diagnose"]', 0),
('traditional_source_summary', 'SYNTHESIS', 'Summarize classical Unani source documentation without inferring modern efficacy.', '["educational_reference", "clinician_context", "research_workspace"]', '["prescribe", "diagnose", "assert_modern_cure"]', 0),
('evidence_summary', 'SYNTHESIS', 'Summarize approved clinical evidence claims and study limitations within a defined scope.', '["clinician_context", "research_workspace", "safety_reference"]', '["prescribe", "diagnose", "universal_cure_claim"]', 0),
('citation_check', 'VERIFICATION', 'Inspect the support assessment, passage fidelity, and retraction status of a citation.', '["research_workspace", "educational_reference", "clinician_context"]', '["prescribe"]', 0),
('safety_information_lookup', 'SAFETY', 'Retrieve approved pharmacovigilance, contraindication, toxicity, and interaction records.', '["safety_reference", "clinician_context"]', '["calculate_dose", "assure_unverified_safety"]', 0),
('regulatory_reference_lookup', 'REGULATORY', 'Retrieve statutory pharmacopoeial standards, GMP compliance, or licensing notices.', '["educational_reference", "research_workspace"]', '["prescribe", "diagnose"]', 0),
('catalog_lookup', 'CATALOG', 'Find approved concepts, Mufradat identities, and formulation records.', '["clinician_context", "research_workspace", "educational_reference"]', '["prescribe", "sign_prescription"]', 0),
('clinical_context_search', 'CLINICAL', 'Retrieve approved contextual information for an authorized clinician with patient privacy preserved.', '["clinician_context"]', '["autonomous_diagnosis", "autonomous_prescription", "calculate_dose"]', 0),
('restricted_clinical_action', 'RESTRICTED', 'Prohibited clinical requests attempting autonomous diagnosis, formulation selection, or dosing.', '[]', '["diagnose", "prescribe", "dose", "dispense"]', 1);

-- 2. Immutable Evidence Packs (Reproducible run context)
CREATE TABLE IF NOT EXISTS rag_evidence_packs (
    id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    normalized_query TEXT NOT NULL,
    query_intent TEXT NOT NULL,
    requested_surface TEXT NOT NULL,
    user_role TEXT NOT NULL,
    caller_user_id TEXT NOT NULL,
    encounter_id TEXT,
    included_passage_ids_json TEXT NOT NULL DEFAULT '[]',
    included_claim_ids_json TEXT NOT NULL DEFAULT '[]',
    excluded_candidates_json TEXT NOT NULL DEFAULT '[]',
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    reproducibility_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (query_intent) REFERENCES rag_query_intent_registry(intent_code)
);

CREATE INDEX IF NOT EXISTS idx_rag_ep_query ON rag_evidence_packs(normalized_query);
CREATE INDEX IF NOT EXISTS idx_rag_ep_caller ON rag_evidence_packs(caller_user_id);

-- 3. Structured Answer Runs
CREATE TABLE IF NOT EXISTS rag_answer_runs (
    id TEXT PRIMARY KEY,
    evidence_pack_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    answer_status TEXT NOT NULL CHECK (answer_status IN (
        'answered', 'partially_answered', 'insufficient_evidence',
        'source_unavailable', 'needs_clarification', 'restricted_request',
        'review_required', 'system_error'
    )),
    query_scope TEXT,
    answer_text TEXT NOT NULL,
    clinical_boundary_notice TEXT,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('passed', 'failed_closed', 'partially_passed')),
    validation_failure_reasons_json TEXT DEFAULT '[]',
    generation_model TEXT NOT NULL DEFAULT 'deterministic_clinical_rag_engine',
    executed_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evidence_pack_id) REFERENCES rag_evidence_packs(id)
);

CREATE INDEX IF NOT EXISTS idx_rag_ar_status ON rag_answer_runs(answer_status);
CREATE INDEX IF NOT EXISTS idx_rag_ar_pack ON rag_answer_runs(evidence_pack_id);

-- 4. Atomic Answer Claims (Statement-level granular units)
CREATE TABLE IF NOT EXISTS rag_answer_claims (
    id TEXT PRIMARY KEY,
    answer_run_id TEXT NOT NULL,
    claim_sequence INTEGER NOT NULL,
    statement_text TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    bound_claim_id TEXT,
    support_state TEXT NOT NULL CHECK (support_state IN (
        'direct_support', 'partial_support', 'unsupported', 'contradicted', 'unassessed'
    )),
    is_validated INTEGER NOT NULL DEFAULT 0,
    cautions_json TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (answer_run_id) REFERENCES rag_answer_runs(id) ON DELETE CASCADE,
    FOREIGN KEY (bound_claim_id) REFERENCES knowledge_claims(id)
);

CREATE INDEX IF NOT EXISTS idx_rag_ac_run ON rag_answer_claims(answer_run_id);
CREATE INDEX IF NOT EXISTS idx_rag_ac_bound ON rag_answer_claims(bound_claim_id);

-- 5. Granular Answer Citations (Per-claim passage binding)
CREATE TABLE IF NOT EXISTS rag_answer_citations (
    id TEXT PRIMARY KEY,
    answer_claim_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_version_id TEXT,
    passage_id TEXT,
    locator TEXT,
    display_reference TEXT NOT NULL,
    access_state TEXT NOT NULL DEFAULT 'open_access',
    passage_text_excerpt TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (answer_claim_id) REFERENCES rag_answer_claims(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES knowledge_sources(id)
);

CREATE INDEX IF NOT EXISTS idx_rag_cit_claim ON rag_answer_citations(answer_claim_id);
CREATE INDEX IF NOT EXISTS idx_rag_cit_source ON rag_answer_citations(source_id);

-- 6. Retrieval & Answer Feedback Queue
CREATE TABLE IF NOT EXISTS rag_retrieval_feedback (
    id TEXT PRIMARY KEY,
    answer_run_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL CHECK (feedback_type IN (
        'wrong_concept', 'irrelevant_passage', 'missing_source',
        'citation_mismatch', 'overstated_claim', 'missing_qualifier',
        'inaccessible_source', 'conflicting_evidence', 'unsafe_labeling',
        'retraction_reported'
    )),
    notes TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_review' CHECK (status IN (
        'pending_review', 'under_review', 'resolved', 'dismissed'
    )),
    reported_by TEXT NOT NULL,
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (answer_run_id) REFERENCES rag_answer_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_rag_fb_run ON rag_retrieval_feedback(answer_run_id);
CREATE INDEX IF NOT EXISTS idx_rag_fb_status ON rag_retrieval_feedback(status);

-- 7. Versioned Benchmark Evaluation Dataset
CREATE TABLE IF NOT EXISTS rag_eval_dataset (
    id TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_intent TEXT NOT NULL,
    expected_status TEXT NOT NULL,
    expected_claim_types_json TEXT NOT NULL DEFAULT '[]',
    expected_source_ids_json TEXT NOT NULL DEFAULT '[]',
    expected_abstention_reason TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

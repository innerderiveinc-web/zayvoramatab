-- Phase 23 Schema: Clinical Decision Support (CDS) Orchestrator & Clinician Approval Workflow
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Governed Decision-Support Policy Registry
CREATE TABLE IF NOT EXISTS cds_policy_registry (
    id TEXT PRIMARY KEY,
    policy_code TEXT NOT NULL UNIQUE,
    policy_name TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    description TEXT NOT NULL,
    trigger_event TEXT NOT NULL, -- 'ENCOUNTER_INTAKE', 'ASSESSMENT_COMPLETED', 'PRE_PRESCRIPTION', 'SIGN_OFF_ATTEMPT'
    required_action TEXT NOT NULL, -- 'REVIEW_REQUIRED', 'SAFETY_EVALUATION', 'MISSING_DATA_DISCLOSURE', 'AMBIGUITY_RESOLVE'
    severity_default TEXT NOT NULL DEFAULT 'WARNING', -- 'INFO', 'WARNING', 'BLOCKER'
    is_active INTEGER NOT NULL DEFAULT 1,
    governance_approval_ref TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cds_policy_code ON cds_policy_registry(policy_code, is_active);
CREATE INDEX IF NOT EXISTS idx_cds_policy_trigger ON cds_policy_registry(trigger_event, is_active);

-- Seed initial reviewed clinical governance policies
INSERT OR IGNORE INTO cds_policy_registry (id, policy_code, policy_name, policy_version, description, trigger_event, required_action, severity_default, is_active, governance_approval_ref) VALUES
('POL-001', 'POL-ALLERGY-CHECK', 'Patient Allergy & Hypersensitivity Review', 'v1.0', 'Mandates review of documented patient allergies and cross-reactivity matching prior to formulation drafting.', 'PRE_PRESCRIPTION', 'SAFETY_EVALUATION', 'BLOCKER', 1, 'GOV-SAFE-2026-001'),
('POL-002', 'POL-POSOLOGY-RANGE', 'Monograph Posology & Unit Ceilings', 'v1.0', 'Enforces strict adherence to traditional monograph dose ranges, maximum daily posology, and valid unit conversion.', 'PRE_PRESCRIPTION', 'REVIEW_REQUIRED', 'WARNING', 1, 'GOV-SAFE-2026-002'),
('POL-003', 'POL-E1-MUDABBAR', 'Schedule E(1) Detoxification & Tadbeer Verification', 'v1.0', 'Requires explicit clinician verification of detoxification processing (Mudabbar) for Schedule E(1) hazardous substances.', 'PRE_PRESCRIPTION', 'SAFETY_EVALUATION', 'BLOCKER', 1, 'GOV-SAFE-2026-003'),
('POL-004', 'POL-CONTRAINDICATION', 'Physiological & Demographic Contraindications', 'v1.0', 'Enforces pregnancy, lactation, pediatric, and geriatric contraindication checks against documented patient demographics.', 'ASSESSMENT_COMPLETED', 'SAFETY_EVALUATION', 'BLOCKER', 1, 'GOV-SAFE-2026-004'),
('POL-005', 'POL-EVIDENCE-BINDING', 'Decision Support Traceable Evidence Binding', 'v1.0', 'Mandates that every factual decision-support card is bound to verified KAVS source passages with locators and active intended-use approval.', 'ASSESSMENT_COMPLETED', 'REVIEW_REQUIRED', 'WARNING', 1, 'GOV-KAVS-2026-005'),
('POL-006', 'POL-IDENTITY-AMBIGUITY', 'Material Identity Disambiguation Gate', 'v1.0', 'Blocks progression when an ingredient term maps to multiple botanical or mineral species without explicit clinician disambiguation.', 'PRE_PRESCRIPTION', 'AMBIGUITY_RESOLVE', 'BLOCKER', 1, 'GOV-TAX-2026-006'),
('POL-007', 'POL-UNANI-MODERN-BOUNDARY', 'Epistemological Independence of Parallel Assessments', 'v1.0', 'Preserves distinct identities of Unani and modern diagnostic streams, preventing unauthorized automated cross-domain diagnosis.', 'ASSESSMENT_COMPLETED', 'MISSING_DATA_DISCLOSURE', 'INFO', 1, 'GOV-CLIN-2026-007'),
('POL-008', 'POL-RESTRICTED-ACTION', 'Autonomous Prescribing & Diagnostic Interception Gate', 'v1.0', 'Blocks any generative or algorithmic attempt to autonomously prescribe, select formulas, or calculate dosages.', 'ENCOUNTER_INTAKE', 'SAFETY_EVALUATION', 'BLOCKER', 1, 'GOV-ETHIC-2026-008'),
('POL-009', 'POL-ENCOUNTER-STALENESS', 'Concurrency & Version Currency Protection', 'v1.0', 'Invalidates active decision-support runs and safety evaluations if the encounter version increments during drafting.', 'SIGN_OFF_ATTEMPT', 'REVIEW_REQUIRED', 'BLOCKER', 1, 'GOV-ENG-2026-009'),
('POL-010', 'POL-SIGNATURE-ATTESTATION', 'Clinician Attestation & Non-Repudiation Gate', 'v1.0', 'Requires authenticated authorized clinician credential, cryptographic hash signing, and explicit inspection of rendered documents.', 'SIGN_OFF_ATTEMPT', 'REVIEW_REQUIRED', 'BLOCKER', 1, 'GOV-LEGAL-2026-010');

-- 2. Immutable CDS Execution Runs
CREATE TABLE IF NOT EXISTS cds_runs (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    encounter_version INTEGER NOT NULL,
    requested_by TEXT NOT NULL REFERENCES users(id),
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    query_scope TEXT NOT NULL DEFAULT 'FULL_ENCOUNTER', -- 'FULL_ENCOUNTER', 'ASSESSMENT_ONLY', 'PRESCRIPTION_PREFLIGHT', 'SAFETY_ONLY'
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    run_state TEXT NOT NULL DEFAULT 'running', -- 'queued', 'running', 'completed', 'partial', 'blocked', 'failed', 'cancelled'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    input_manifest_json TEXT, -- Serialized encounter facts, demographics, vitals, assessments, rx items
    evidence_pack_ref TEXT REFERENCES rag_evidence_packs(id),
    orchestrator_version TEXT NOT NULL DEFAULT 'v1.0',
    failure_codes_json TEXT,
    safe_error_summary TEXT,
    supersedes_run_id TEXT REFERENCES cds_runs(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cds_runs_encounter ON cds_runs(encounter_id, encounter_version);
CREATE INDEX IF NOT EXISTS idx_cds_runs_state ON cds_runs(run_state);

-- 3. Typed Decision-Support Cards
CREATE TABLE IF NOT EXISTS cds_cards (
    id TEXT PRIMARY KEY,
    cds_run_id TEXT NOT NULL REFERENCES cds_runs(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    encounter_version INTEGER NOT NULL,
    card_type TEXT NOT NULL, -- 'missing_information_prompt', 'safety_finding', 'source_backed_reference', 'conflicting_record_alert', 'followup_reminder', 'terminology_ambiguity'
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    triggering_inputs_json TEXT NOT NULL DEFAULT '[]', -- Provenance of inputs triggering this card
    evidence_refs_json TEXT NOT NULL DEFAULT '[]', -- Bound KAVS claim/source/passage locators
    rule_refs_json TEXT NOT NULL DEFAULT '[]', -- Policy registry references
    limitations_json TEXT NOT NULL DEFAULT '[]', -- Epistemic caveats, missing data notes, coverage bounds
    severity TEXT NOT NULL DEFAULT 'INFO', -- 'INFO', 'WARNING', 'BLOCKER'
    blocking_state INTEGER NOT NULL DEFAULT 0, -- 1 if card blocks workflow progression
    blocking_reason TEXT,
    review_status TEXT NOT NULL DEFAULT 'not_reviewed', -- 'not_reviewed', 'accepted', 'rejected', 'edited', 'deferred', 'not_applicable'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    invalidated_at TIMESTAMP,
    invalidation_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_cds_cards_run ON cds_cards(cds_run_id);
CREATE INDEX IF NOT EXISTS idx_cds_cards_encounter ON cds_cards(encounter_id, encounter_version);
CREATE INDEX IF NOT EXISTS idx_cds_cards_review ON cds_cards(review_status, blocking_state);

-- 4. Clinician Review Decisions & Attributions
CREATE TABLE IF NOT EXISTS cds_reviews (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cds_cards(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    encounter_version INTEGER NOT NULL,
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    reviewer_role TEXT NOT NULL,
    action TEXT NOT NULL, -- 'accept_as_documentation', 'accept_with_edit', 'reject', 'defer', 'mark_not_applicable', 'request_more_information'
    original_payload_hash TEXT NOT NULL,
    edited_content TEXT,
    rationale TEXT,
    acknowledgements_json TEXT,
    idempotency_key TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    supersedes_id TEXT REFERENCES cds_reviews(id)
);

CREATE INDEX IF NOT EXISTS idx_cds_reviews_card ON cds_reviews(card_id);
CREATE INDEX IF NOT EXISTS idx_cds_reviews_encounter ON cds_reviews(encounter_id, encounter_version);

-- 5. Safety Evaluation References (Preserving Safety Firewall Authority)
CREATE TABLE IF NOT EXISTS safety_evaluation_refs (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    encounter_version INTEGER NOT NULL,
    external_or_internal_result_id TEXT NOT NULL, -- References safety_preflight_runs(id)
    evaluation_status TEXT NOT NULL, -- 'completed_no_flag_within_scope', 'warning_found', 'blocking_issue_found', 'incomplete_due_to_missing_data', 'not_applicable', 'service_unavailable', 'identity_unresolved', 'not_evaluated', 'stale_result'
    ruleset_version TEXT NOT NULL,
    input_manifest_hash TEXT NOT NULL,
    evaluated_at TIMESTAMP NOT NULL,
    validity_policy TEXT NOT NULL DEFAULT 'STRICT_ENCOUNTER_VERSION',
    is_stale INTEGER NOT NULL DEFAULT 0,
    stale_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_safety_eval_refs_encounter ON safety_evaluation_refs(encounter_id, encounter_version);

-- 6. Unified Clinical Sign-offs & Cryptographic Attestations
CREATE TABLE IF NOT EXISTS clinical_signoffs (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    encounter_version INTEGER NOT NULL,
    entity_type TEXT NOT NULL, -- 'ENCOUNTER', 'PRESCRIPTION', 'CARE_PLAN'
    entity_id TEXT NOT NULL,
    entity_version INTEGER NOT NULL,
    signer_id TEXT NOT NULL REFERENCES users(id),
    signer_role TEXT NOT NULL,
    credential_number TEXT,
    signing_method TEXT NOT NULL DEFAULT 'PIN_VERIFIED', -- 'PIN_VERIFIED', 'PKI_DIGITAL_CERT', 'HMAC_ATTESTATION'
    signature_hash TEXT NOT NULL, -- Cryptographic hash over canonical payload snapshot
    canonical_payload_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    is_superseded INTEGER NOT NULL DEFAULT 0,
    superseded_by_signoff_id TEXT REFERENCES clinical_signoffs(id),
    signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clinical_signoffs_entity ON clinical_signoffs(entity_type, entity_id, entity_version);
CREATE INDEX IF NOT EXISTS idx_clinical_signoffs_encounter ON clinical_signoffs(encounter_id, encounter_version);

-- 7. Encounter Formal Amendments (Post-Signature Corrections)
CREATE TABLE IF NOT EXISTS encounter_amendments (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    original_encounter_version INTEGER NOT NULL,
    amended_encounter_version INTEGER NOT NULL,
    requested_by TEXT NOT NULL REFERENCES users(id),
    clinical_justification TEXT NOT NULL,
    changes_summary_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL', -- 'PENDING_APPROVAL', 'APPROVED', 'REJECTED'
    approved_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_encounter_amendments_enc ON encounter_amendments(encounter_id);

-- 8. Governed Workflow Events Ledger (Append-Only Event Sourcing)
CREATE TABLE IF NOT EXISTS workflow_events (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    encounter_version INTEGER NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    event_code TEXT NOT NULL, -- 'INTAKE', 'ASSESSMENT_SAVE', 'CDS_TRIGGER', 'CDS_REVIEW', 'SAFETY_EVAL', 'SIGN_OFF', 'AMEND', 'CANCEL'
    actor_id TEXT NOT NULL REFERENCES users(id),
    reason TEXT,
    prerequisites_validated_json TEXT,
    side_effects_json TEXT,
    idempotency_key TEXT,
    transitioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_events_encounter ON workflow_events(encounter_id, transitioned_at);

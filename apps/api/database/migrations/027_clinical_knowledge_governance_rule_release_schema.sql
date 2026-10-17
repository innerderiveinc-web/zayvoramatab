-- Migration 027: Clinical Knowledge Governance, Rule Versioning & Controlled Safety-Rule Release Schema
-- Phase 28 for ZAYVORA MATAB OS
-- Strict non-negotiables enforced:
-- 1. Never fabricate clinical knowledge or governance evidence
-- 2. No direct-to-production clinical changes (must pass formal lifecycle states)
-- 3. No automatic approval by AI (AI can propose, but cannot approve/activate)
-- 4. Separate artifact approval from deployment; separate technical validity from clinical validity
-- 5. Preserve provenance, explicit scope, and immutable content hashes
-- 6. Keep old records interpretable; no retroactive rewrites of clinical records
-- 7. Production disable/rollback must be tested and verified

-- 1. Governed Artifacts Master Envelope
CREATE TABLE IF NOT EXISTS governed_artifacts (
    id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    stable_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    current_version_id TEXT,
    owner_role TEXT NOT NULL,
    owning_domain TEXT NOT NULL,
    intended_use TEXT NOT NULL,
    scope_json TEXT NOT NULL DEFAULT '{}',
    criticality_class TEXT NOT NULL CHECK (criticality_class IN (
        'EDITORIAL',
        'TERMINOLOGY_IDENTITY',
        'EVIDENCE_CLAIM',
        'CLINICAL_BEHAVIOR',
        'REGULATORY_SAFETY',
        'EMERGENCY_PATCH'
    )),
    current_lifecycle_state TEXT NOT NULL DEFAULT 'DRAFT' CHECK (current_lifecycle_state IN (
        'DRAFT',
        'SUBMITTED_FOR_REVIEW',
        'CHANGES_REQUESTED',
        'REVIEW_APPROVED',
        'TECHNICAL_VALIDATION_PENDING',
        'TECHNICAL_VALIDATION_PASSED',
        'VALIDATION_FAILED',
        'RELEASE_CANDIDATE',
        'RELEASE_APPROVED',
        'DEPLOYMENT_IN_PROGRESS',
        'DEPLOYED_VERIFICATION_PENDING',
        'ACTIVE',
        'SUPERSEDED',
        'SUSPENDED',
        'WITHDRAWN',
        'REJECTED',
        'ROLLED_BACK'
    )),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_art_type ON governed_artifacts(artifact_type, current_lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_gov_art_key ON governed_artifacts(stable_key);

-- 2. Governed Artifact Versions (Immutable Content & Hashes)
CREATE TABLE IF NOT EXISTS governed_artifact_versions (
    id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES governed_artifacts(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    version_label TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_manifest_hash TEXT NOT NULL,
    diff_summary TEXT,
    change_type TEXT NOT NULL CHECK (change_type IN (
        'NEW',
        'CORRECTION',
        'SCOPE_CHANGE',
        'EVIDENCE_UPDATE',
        'RULE_CHANGE',
        'WITHDRAWAL',
        'EDITORIAL_CHANGE',
        'SECURITY_FIX'
    )),
    author_id TEXT NOT NULL REFERENCES users(id),
    supporting_evidence_refs_json TEXT NOT NULL DEFAULT '[]',
    applicable_scope_json TEXT NOT NULL DEFAULT '{}',
    limitations_and_exclusions TEXT,
    effective_date TEXT,
    deprecation_date TEXT,
    schema_version TEXT NOT NULL DEFAULT '1.0',
    supersedes_version_id TEXT,
    lifecycle_state TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_art_ver ON governed_artifact_versions(artifact_id, version_number);
CREATE INDEX IF NOT EXISTS idx_gov_art_ver_hash ON governed_artifact_versions(payload_manifest_hash);

-- 3. Governed Artifact Transitions (Auditable State Machine Ledger)
CREATE TABLE IF NOT EXISTS governed_artifact_transitions (
    id TEXT PRIMARY KEY,
    artifact_version_id TEXT NOT NULL REFERENCES governed_artifact_versions(id) ON DELETE CASCADE,
    prior_state TEXT NOT NULL,
    next_state TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    actor_role TEXT NOT NULL,
    rationale TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    transition_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_trans_ver ON governed_artifact_transitions(artifact_version_id);

-- 4. Governed Clinical Rules (Typed, Sandboxed Rule Logic)
CREATE TABLE IF NOT EXISTS governed_clinical_rules (
    id TEXT PRIMARY KEY,
    artifact_version_id TEXT NOT NULL REFERENCES governed_artifact_versions(id) ON DELETE CASCADE,
    stable_key TEXT NOT NULL,
    version_number INTEGER NOT NULL DEFAULT 1,
    rule_purpose TEXT NOT NULL,
    clinical_domain TEXT NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN (
        'MISSING_DATA_BLOCKER',
        'SAFETY_WARNING',
        'IDENTITY_CONSTRAINT',
        'SOURCE_DISPLAY_POLICY',
        'WORKFLOW_PREREQUISITE',
        'DATA_QUALITY_VALIDATION',
        'CONTRAINDICATION_CHECK'
    )),
    scope_json TEXT NOT NULL DEFAULT '{}',
    required_inputs_json TEXT NOT NULL DEFAULT '[]',
    condition_expression_json TEXT NOT NULL,
    output_state_and_message_json TEXT NOT NULL,
    criticality_priority TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (criticality_priority IN (
        'LOW',
        'MEDIUM',
        'HIGH',
        'CRITICAL'
    )),
    is_blocking INTEGER NOT NULL DEFAULT 0,
    permitted_override_roles_json TEXT NOT NULL DEFAULT '[]',
    test_fixtures_json TEXT NOT NULL DEFAULT '[]',
    fallback_state TEXT NOT NULL DEFAULT 'RULE_UNAVAILABLE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_clin_rule_key ON governed_clinical_rules(stable_key, version_number);

-- 5. Rule Test Executions (Deterministic Verification)
CREATE TABLE IF NOT EXISTS rule_test_executions (
    id TEXT PRIMARY KEY,
    rule_definition_id TEXT NOT NULL REFERENCES governed_clinical_rules(id) ON DELETE CASCADE,
    test_case_name TEXT NOT NULL,
    input_payload_json TEXT NOT NULL,
    expected_output_state TEXT NOT NULL,
    actual_output_state TEXT NOT NULL,
    test_result TEXT NOT NULL CHECK (test_result IN ('PASSED', 'FAILED', 'ERROR')),
    execution_latency_ms REAL NOT NULL DEFAULT 0.0,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rule_test_exec ON rule_test_executions(rule_definition_id);

-- 6. Governance Releases (Immutable Release Manifests & Staging)
CREATE TABLE IF NOT EXISTS governance_releases (
    id TEXT PRIMARY KEY,
    release_sequence INTEGER NOT NULL UNIQUE,
    release_tag TEXT NOT NULL UNIQUE,
    environment TEXT NOT NULL CHECK (environment IN (
        'STAGING',
        'PRODUCTION',
        'SHADOW_EVALUATION',
        'CANARY'
    )),
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    validation_run_ids_json TEXT NOT NULL DEFAULT '[]',
    approvals_json TEXT NOT NULL DEFAULT '[]',
    rollout_mode TEXT NOT NULL DEFAULT 'SHADOW_EVALUATION' CHECK (rollout_mode IN (
        'SHADOW_EVALUATION',
        'CANARY',
        'FULL_PRODUCTION',
        'DISABLED'
    )),
    runtime_verification_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (runtime_verification_status IN (
        'PENDING',
        'VERIFIED_MATCH',
        'HASH_MISMATCH',
        'BLOCKED'
    )),
    is_active INTEGER NOT NULL DEFAULT 0,
    deployed_at TEXT,
    deployed_by TEXT REFERENCES users(id),
    suspended_at TEXT,
    suspended_by TEXT REFERENCES users(id),
    suspension_reason TEXT,
    rollback_target_release_id TEXT REFERENCES governance_releases(id),
    rolled_back_at TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_rel_tag ON governance_releases(release_tag);
CREATE INDEX IF NOT EXISTS idx_gov_rel_active ON governance_releases(environment, is_active);

-- 7. Governance Impact Analysis (Dependency Mapping)
CREATE TABLE IF NOT EXISTS governance_impact_analyses (
    id TEXT PRIMARY KEY,
    source_artifact_version_id TEXT NOT NULL REFERENCES governed_artifact_versions(id) ON DELETE CASCADE,
    dependent_artifacts_json TEXT NOT NULL DEFAULT '[]',
    dependent_rules_json TEXT NOT NULL DEFAULT '[]',
    dependent_apis_json TEXT NOT NULL DEFAULT '[]',
    active_encounters_count INTEGER NOT NULL DEFAULT 0,
    risk_assessment TEXT NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_impact_ver ON governance_impact_analyses(source_artifact_version_id);

-- 8. Runtime Version Resolution Ledger (Pinning Active Versions for Encounters)
CREATE TABLE IF NOT EXISTS governance_runtime_resolutions (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL,
    action_name TEXT NOT NULL,
    release_id TEXT NOT NULL REFERENCES governance_releases(id),
    resolved_rule_versions_json TEXT NOT NULL DEFAULT '[]',
    resolved_knowledge_versions_json TEXT NOT NULL DEFAULT '[]',
    resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gov_runtime_res ON governance_runtime_resolutions(encounter_id, action_name);

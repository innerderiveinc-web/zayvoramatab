-- ============================================================================
-- Migration 037: Production Release Engineering, Deployment Governance,
-- Feature Flags & Rollback Orchestration Schema
--
-- Phase 38: Production Release Engineering, Environments, Immutable Manifests,
-- Server-Side Scoped Feature Flags, Recovery Runbooks & Rollback Execution Ledger
-- ============================================================================

-- 1. Release Manifests Ledger
CREATE TABLE IF NOT EXISTS release_manifests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    version_tag TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    git_commit TEXT NOT NULL,
    git_branch TEXT NOT NULL DEFAULT 'main',
    artifact_digest TEXT NOT NULL,
    target_environment TEXT NOT NULL DEFAULT 'staging' CHECK (target_environment IN ('local', 'ci_test', 'staging', 'pilot', 'production')),
    risk_level TEXT NOT NULL DEFAULT 'moderate' CHECK (risk_level IN ('low', 'moderate', 'high', 'critical')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'validation_failed', 'blocked', 'awaiting_approval', 'approved',
        'deploying', 'deployed', 'verification_failed', 'paused',
        'rollback_requested', 'rolling_back', 'rolled_forward', 'recovered', 'cancelled'
    )),
    quality_gates_json TEXT NOT NULL DEFAULT '{}',
    migrations_json TEXT NOT NULL DEFAULT '[]',
    feature_flags_json TEXT NOT NULL DEFAULT '[]',
    config_changes_json TEXT NOT NULL DEFAULT '{}',
    affected_modules_json TEXT NOT NULL DEFAULT '[]',
    required_approvals_json TEXT NOT NULL DEFAULT '[]',
    actual_approvals_json TEXT NOT NULL DEFAULT '[]',
    rollback_plan_json TEXT NOT NULL DEFAULT '{}',
    post_deploy_evidence_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT NOT NULL,
    approved_by TEXT,
    deployed_by TEXT,
    deployed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, version_tag)
);

CREATE INDEX IF NOT EXISTS idx_rel_manifests_org_env ON release_manifests (organization_id, target_environment);
CREATE INDEX IF NOT EXISTS idx_rel_manifests_status ON release_manifests (status);

-- 2. Release Gate Evaluations Ledger
CREATE TABLE IF NOT EXISTS release_gate_evaluations (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES release_manifests(id) ON DELETE CASCADE,
    gate_type TEXT NOT NULL CHECK (gate_type IN (
        'UNIT_TESTS', 'INTEGRATION_TESTS', 'SECURITY_SCAN',
        'MIGRATION_COMPATIBILITY', 'CLINICAL_SAFETY_GATE', 'SMOKE_TESTS'
    )),
    status TEXT NOT NULL CHECK (status IN ('PASSED', 'FAILED', 'BLOCKED', 'SKIPPED', 'INDETERMINATE')),
    evidence_summary TEXT,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    evaluated_by TEXT NOT NULL,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rel_gates_release ON release_gate_evaluations (release_id);

-- 3. Enterprise Feature Flags Catalog
CREATE TABLE IF NOT EXISTS feature_flags (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    flag_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL DEFAULT 'operational' CHECK (category IN (
        'clinical_cds', 'integration', 'security', 'ui_ux', 'operational', 'patient_engagement'
    )),
    risk_level TEXT NOT NULL DEFAULT 'moderate' CHECK (risk_level IN ('low', 'moderate', 'high', 'critical')),
    owner_role TEXT NOT NULL DEFAULT 'ORG_ADMIN',
    is_enabled_default INTEGER NOT NULL DEFAULT 0,
    state_by_environment_json TEXT NOT NULL DEFAULT '{"local":false,"ci_test":false,"staging":false,"pilot":false,"production":false}',
    targeting_rules_json TEXT NOT NULL DEFAULT '{"organizations":[],"facilities":[],"roles":[],"user_ids":[]}',
    expiry_date TEXT,
    is_emergency_disabled INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, flag_key)
);

CREATE INDEX IF NOT EXISTS idx_feature_flags_org ON feature_flags (organization_id);
CREATE INDEX IF NOT EXISTS idx_feature_flags_key ON feature_flags (flag_key);

-- 4. Feature Flag Audit History
CREATE TABLE IF NOT EXISTS feature_flag_audit (
    id TEXT PRIMARY KEY,
    flag_id TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN (
        'CREATE', 'UPDATE_METADATA', 'UPDATE_ENV_STATE', 'UPDATE_TARGETING',
        'EMERGENCY_DISABLE', 'EMERGENCY_RESTORE', 'RETIRE'
    )),
    previous_state_json TEXT,
    new_state_json TEXT,
    reason TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ff_audit_flag ON feature_flag_audit (flag_id);

-- 5. Deployment Executions History
CREATE TABLE IF NOT EXISTS deployment_executions (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES release_manifests(id),
    environment TEXT NOT NULL CHECK (environment IN ('local', 'ci_test', 'staging', 'pilot', 'production')),
    status TEXT NOT NULL CHECK (status IN ('IN_PROGRESS', 'SUCCESS', 'FAILED', 'ABORTED')),
    smoke_tests_passed INTEGER NOT NULL DEFAULT 0,
    evidence_snapshot_json TEXT NOT NULL DEFAULT '{}',
    executed_by TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_deploy_exec_release ON deployment_executions (release_id);

-- 6. Rollback & Recovery Executions Ledger
CREATE TABLE IF NOT EXISTS rollback_executions (
    id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL REFERENCES release_manifests(id),
    strategy TEXT NOT NULL CHECK (strategy IN ('DISABLE_FEATURE', 'ROLLBACK_ARTIFACT', 'ROLL_FORWARD', 'CONTAIN')),
    target_environment TEXT NOT NULL CHECK (target_environment IN ('local', 'ci_test', 'staging', 'pilot', 'production')),
    trigger_reason TEXT NOT NULL,
    authorized_by TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('INITIATED', 'IN_PROGRESS', 'COMPLETED', 'FAILED')),
    side_effects_acknowledged_json TEXT NOT NULL DEFAULT '[]',
    recovery_verification_json TEXT NOT NULL DEFAULT '{}',
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rollback_exec_release ON rollback_executions (release_id);

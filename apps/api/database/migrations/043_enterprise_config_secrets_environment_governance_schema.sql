-- ============================================================================
-- Migration: 043_enterprise_config_secrets_environment_governance_schema.sql
-- Description: Enterprise Configuration, Secrets & Environment Governance Schema
-- System: ZAYVORA MATAB OS — Standalone Unani Clinic & Multi-Branch Enterprise OS
-- ============================================================================

-- 1. Governed Configuration Settings Catalog
CREATE TABLE IF NOT EXISTS config_settings_catalog (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    config_key TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('PUBLIC_CLIENT', 'SERVER_RUNTIME', 'SECRET_CREDENTIAL', 'SECURITY_POLICY', 'CLINICAL_WORKFLOW_POLICY', 'FEATURE_FLAG_POLICY', 'DERIVED')),
    data_type TEXT NOT NULL CHECK(data_type IN ('string', 'integer', 'boolean', 'json', 'url', 'enum', 'secret_ref')),
    owner_team TEXT NOT NULL DEFAULT 'Core Platform',
    environment_scope TEXT NOT NULL DEFAULT 'all' CHECK(environment_scope IN ('all', 'development', 'staging', 'production', 'test')),
    tenant_scope TEXT NOT NULL DEFAULT 'global' CHECK(tenant_scope IN ('global', 'tenant', 'facility')),
    precedence_order TEXT NOT NULL DEFAULT 'ENV_OVER_DB' CHECK(precedence_order IN ('ENV_OVER_DB', 'DB_OVER_ENV', 'SECRET_STORE_ONLY', 'IMMUTABLE_FILE')),
    is_required INTEGER NOT NULL DEFAULT 1 CHECK(is_required IN (0, 1)),
    default_value_json TEXT NOT NULL DEFAULT 'null',
    validation_rules_json TEXT NOT NULL DEFAULT '{}',
    is_runtime_refreshable INTEGER NOT NULL DEFAULT 0 CHECK(is_runtime_refreshable IN (0, 1)),
    change_risk_level TEXT NOT NULL DEFAULT 'low' CHECK(change_risk_level IN ('low', 'medium', 'high', 'critical')),
    required_approver_role TEXT NOT NULL DEFAULT 'PLATFORM_ADMIN',
    consumers_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, config_key)
);

CREATE INDEX IF NOT EXISTS idx_config_catalog_org_cat ON config_settings_catalog(organization_id, category);
CREATE INDEX IF NOT EXISTS idx_config_catalog_key ON config_settings_catalog(config_key);

-- 2. Governed Environments Registry & Isolation Perimeters
CREATE TABLE IF NOT EXISTS config_environments_registry (
    id TEXT PRIMARY KEY,
    environment_code TEXT NOT NULL UNIQUE CHECK(environment_code IN ('local_dev', 'shared_dev', 'test_ci', 'staging_synthetic', 'production')),
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    owner TEXT NOT NULL,
    database_resource_type TEXT NOT NULL,
    database_resource_ref TEXT NOT NULL,
    secret_store_namespace TEXT NOT NULL,
    service_identity TEXT NOT NULL,
    ingress_policy TEXT NOT NULL,
    egress_policy TEXT NOT NULL,
    external_api_classification TEXT NOT NULL CHECK(external_api_classification IN ('SANDBOX', 'PRODUCTION', 'MOCK_ONLY')),
    synthetic_data_only INTEGER NOT NULL DEFAULT 1 CHECK(synthetic_data_only IN (0, 1)),
    destructive_actions_allowed INTEGER NOT NULL DEFAULT 0 CHECK(destructive_actions_allowed IN (0, 1)),
    live_messaging_allowed INTEGER NOT NULL DEFAULT 0 CHECK(live_messaging_allowed IN (0, 1)),
    live_payments_allowed INTEGER NOT NULL DEFAULT 0 CHECK(live_payments_allowed IN (0, 1)),
    active_config_version TEXT NOT NULL DEFAULT '1.0.0',
    verification_status TEXT NOT NULL DEFAULT 'verified' CHECK(verification_status IN ('verified', 'unverified', 'mismatch', 'degraded')),
    last_verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_env_code ON config_environments_registry(environment_code);

-- 3. Governed Secret References (Strictly Metadata, Zero Raw Secret Text)
CREATE TABLE IF NOT EXISTS config_secret_references (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    secret_name TEXT NOT NULL,
    secret_type TEXT NOT NULL CHECK(secret_type IN ('DATABASE_CREDENTIAL', 'API_KEY', 'WEBHOOK_SIGNING_SECRET', 'ENCRYPTION_KEY', 'SESSION_KEY', 'NOTIFICATION_GATEWAY_CREDENTIAL', 'ABDM_BRIDGE_CREDENTIAL', 'PAYMENT_GATEWAY_KEY', 'BACKUP_ENCRYPTION_KEY')),
    provider_type TEXT NOT NULL CHECK(provider_type IN ('VAULT', 'AWS_SECRETS_MANAGER', 'GCP_SECRET_MANAGER', 'AZURE_KEY_VAULT', 'KUBERNETES_SECRET', 'ENV_VARIABLE')),
    provider_secret_ref TEXT NOT NULL,
    environment_code TEXT NOT NULL REFERENCES config_environments_registry(environment_code),
    owner_team TEXT NOT NULL,
    authorized_consumers_json TEXT NOT NULL DEFAULT '[]',
    key_version TEXT NOT NULL DEFAULT 'v1',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'rotation_in_progress', 'retired', 'revoked', 'compromised')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    rotated_at TEXT,
    expires_at TEXT,
    last_verified_at TEXT,
    incident_id TEXT,
    UNIQUE(organization_id, secret_name, environment_code)
);

CREATE INDEX IF NOT EXISTS idx_config_secrets_org_env ON config_secret_references(organization_id, environment_code);
CREATE INDEX IF NOT EXISTS idx_config_secrets_status ON config_secret_references(status);

-- 4. Secret Rotation Workflow Executions
CREATE TABLE IF NOT EXISTS config_secret_rotations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    secret_ref_id TEXT NOT NULL REFERENCES config_secret_references(id) ON DELETE CASCADE,
    rotation_reason TEXT NOT NULL CHECK(rotation_reason IN ('SCHEDULED_EXPIRY', 'ROUTINE_SECURITY_POLICY', 'STAFF_TURNOVER', 'SUSPECTED_COMPROMISE', 'SYSTEM_UPGRADE')),
    initiated_by TEXT NOT NULL,
    old_key_version TEXT NOT NULL,
    new_key_version TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('planned', 'prepared', 'updated', 'verified', 'old_retired', 'partial', 'failed', 'indeterminate', 'revoked_urgent')) DEFAULT 'planned',
    consumer_validation_json TEXT NOT NULL DEFAULT '{}',
    sanitized_evidence_json TEXT NOT NULL DEFAULT '{}',
    failure_reason TEXT,
    initiated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_config_rotations_ref ON config_secret_rotations(secret_ref_id);
CREATE INDEX IF NOT EXISTS idx_config_rotations_state ON config_secret_rotations(state);

-- 5. Governed Configuration Change Proposals
CREATE TABLE IF NOT EXISTS config_change_proposals (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    title TEXT NOT NULL,
    environment_code TEXT NOT NULL REFERENCES config_environments_registry(environment_code),
    requester_id TEXT NOT NULL,
    change_category TEXT NOT NULL CHECK(change_category IN ('RUNTIME_SETTING', 'SECURITY_POLICY', 'CLINICAL_WORKFLOW', 'ENDPOINT_UPDATE')),
    diff_metadata_json TEXT NOT NULL DEFAULT '{}',
    impact_assessment_json TEXT NOT NULL DEFAULT '{}',
    rollback_plan TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'review_pending', 'approved', 'rejected', 'applied', 'rolled_back')),
    approved_by TEXT,
    approved_at TEXT,
    applied_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_proposals_org_status ON config_change_proposals(organization_id, status);

-- 6. Configuration Drift Scans & Findings
CREATE TABLE IF NOT EXISTS config_drift_scans (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    environment_code TEXT NOT NULL REFERENCES config_environments_registry(environment_code),
    scan_type TEXT NOT NULL CHECK(scan_type IN ('SCHEDULED', 'PREFLIGHT', 'POST_DEPLOY', 'MANUAL_AUDIT')),
    total_evaluated INTEGER NOT NULL DEFAULT 0,
    drift_count INTEGER NOT NULL DEFAULT 0,
    critical_drift_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('passed', 'drift_detected', 'failed')) DEFAULT 'passed',
    scanned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_drift_env ON config_drift_scans(environment_code, scanned_at);

CREATE TABLE IF NOT EXISTS config_drift_findings (
    id TEXT PRIMARY KEY,
    scan_id TEXT NOT NULL REFERENCES config_drift_scans(id) ON DELETE CASCADE,
    config_key TEXT NOT NULL,
    finding_type TEXT NOT NULL CHECK(finding_type IN (
        'UNMANAGED_SETTING', 'VALUE_MISMATCH', 'WRONG_ENVIRONMENT_SECRET', 
        'DISABLED_SECURITY_CONTROL', 'EXPIRED_CREDENTIAL', 'STALE_FLAG', 
        'UNEXPECTED_ENDPOINT', 'MOCK_IN_PRODUCTION'
    )),
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
    details_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('open', 'resolved', 'exception_granted')) DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_drift_find_scan ON config_drift_findings(scan_id, severity);

-- 7. Tamper-Evident Configuration Audit Ledger (Zero Secrets Stored)
CREATE TABLE IF NOT EXISTS config_audit_ledger (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK(action_type IN (
        'CONFIG_CREATED', 'CONFIG_UPDATED', 'SECRET_REGISTERED', 
        'ROTATION_INITIATED', 'ROTATION_COMPLETED', 'ROTATION_FAILED', 
        'DRIFT_SCAN_RUN', 'EMERGENCY_KILLSWITCH', 'CHANGE_PROPOSAL_APPROVED', 
        'CHANGE_APPLIED', 'SECRET_COMPROMISE_FLAGGED'
    )),
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    target_key_or_ref TEXT NOT NULL,
    environment_code TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_audit_org_act ON config_audit_ledger(organization_id, action_type);

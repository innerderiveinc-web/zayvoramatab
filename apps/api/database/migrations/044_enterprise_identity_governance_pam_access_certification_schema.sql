-- ============================================================================
-- Migration 044: Enterprise Identity Governance, Privileged Access Management (PAM)
--               & Access Certification Engine
-- Phase 45: ZAYVORA MATAB OS
-- ============================================================================

-- 1. Unified Identity Principals Registry (Human & Non-Human)
CREATE TABLE IF NOT EXISTS identity_principals (
    id TEXT PRIMARY KEY,
    principal_type TEXT NOT NULL, -- 'HUMAN', 'SERVICE_ACCOUNT', 'BATCH_JOB', 'CI_CD', 'OBSERVABILITY_AGENT'
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    account_state TEXT NOT NULL DEFAULT 'ACTIVE', -- 'INVITED', 'ACTIVE', 'SUSPENDED', 'DISABLED', 'DEPROVISIONING', 'OFFBOARDED', 'DELETED'
    owner_user_id TEXT REFERENCES users(id), -- Accountable human owner (mandatory for non-human identities)
    environment TEXT NOT NULL DEFAULT 'production', -- 'production', 'staging_synthetic', 'local_dev'
    is_interactive_allowed INTEGER NOT NULL DEFAULT 1, -- 0 for machine accounts
    last_active_at TIMESTAMP,
    metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_identity_principals_lookup ON identity_principals(organization_id, account_state);
CREATE INDEX IF NOT EXISTS idx_identity_principals_type ON identity_principals(principal_type, environment);

-- 2. Governed Privileged Operations Registry
CREATE TABLE IF NOT EXISTS identity_privilege_registry (
    id TEXT PRIMARY KEY,
    privilege_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- 'USER_ADMIN', 'SECURITY_CONFIG', 'INFRASTRUCTURE', 'DATA_GOVERNANCE', 'CLINICAL_AUTHORITY'
    risk_tier TEXT NOT NULL DEFAULT 'HIGH', -- 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    is_clinical_authority INTEGER NOT NULL DEFAULT 0, -- Invariant: 1 = clinical (cannot be granted via admin PAM elevation)
    max_elevation_seconds INTEGER NOT NULL DEFAULT 14400, -- Maximum allowed duration (default 4 hours)
    requires_dual_approval INTEGER NOT NULL DEFAULT 1,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_privilege_registry_key ON identity_privilege_registry(privilege_key);

-- 3. Just-In-Time (JIT) Privileged Elevation State Machine
CREATE TABLE IF NOT EXISTS identity_jit_elevations (
    id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES identity_principals(id) ON DELETE CASCADE,
    privilege_key TEXT NOT NULL,
    resource_scope TEXT NOT NULL DEFAULT 'GLOBAL',
    requested_by TEXT NOT NULL REFERENCES users(id),
    approved_by TEXT REFERENCES users(id),
    justification TEXT NOT NULL,
    ticket_reference TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL DEFAULT 3600,
    status TEXT NOT NULL DEFAULT 'JIT_REQUESTED', -- 'JIT_REQUESTED', 'APPROVED', 'ACTIVATED', 'EXPIRED', 'REVOKED', 'REJECTED'
    activated_at TIMESTAMP,
    expires_at TIMESTAMP,
    revoked_at TIMESTAMP,
    revoked_by TEXT REFERENCES users(id),
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jit_elevations_lookup ON identity_jit_elevations(principal_id, status);

-- 4. Emergency Break-Glass Sessions with Clinical Guardrails
CREATE TABLE IF NOT EXISTS identity_break_glass_sessions (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT NOT NULL REFERENCES users(id),
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    patient_id TEXT REFERENCES patients(id),
    reason_code TEXT NOT NULL,
    justification TEXT NOT NULL,
    ticket_reference TEXT NOT NULL,
    started_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'EXPIRED', 'REVOKED', 'REVIEWED_JUSTIFIED', 'REVIEWED_ABUSE'
    clinical_act_attempted INTEGER NOT NULL DEFAULT 0, -- Hard invariant check (must remain 0)
    post_reviewer_id TEXT REFERENCES users(id),
    post_reviewed_at TIMESTAMP,
    post_review_decision TEXT, -- 'REVIEWED_JUSTIFIED', 'REVIEWED_ABUSE'
    post_review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_break_glass_actor ON identity_break_glass_sessions(actor_user_id, status);

-- 5. Service Accounts & Machine Identities Catalog
CREATE TABLE IF NOT EXISTS identity_service_accounts (
    id TEXT PRIMARY KEY,
    service_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    owner_user_id TEXT NOT NULL REFERENCES users(id),
    environment TEXT NOT NULL DEFAULT 'production',
    credential_type TEXT NOT NULL DEFAULT 'API_KEY', -- 'API_KEY', 'WORKLOAD_IDENTITY', 'TOKEN_ROTATING'
    credential_ref TEXT NOT NULL, -- Pointer to secret manager reference (zero secret bytes stored)
    permitted_workloads_json TEXT NOT NULL DEFAULT '[]',
    is_interactive_allowed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'SUSPENDED', 'DEPROVISIONED'
    dependency_checklist_json TEXT NOT NULL DEFAULT '[]',
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_service_accounts_owner ON identity_service_accounts(owner_user_id, status);

-- 6. Access Certification Campaigns & Governance
CREATE TABLE IF NOT EXISTS identity_certification_campaigns (
    id TEXT PRIMARY KEY,
    campaign_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    target_scope TEXT NOT NULL, -- 'CLINICAL_ROLES', 'PRIVILEGED_ADMINS', 'SERVICE_ACCOUNTS', 'FACILITY_MEMBERSHIPS'
    due_date TEXT NOT NULL,
    snapshot_timestamp TIMESTAMP NOT NULL,
    owner_user_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'DRAFT', 'ACTIVE', 'IN_REVIEW', 'COMPLETED', 'EXPIRED'
    total_items_count INTEGER NOT NULL DEFAULT 0,
    reviewed_items_count INTEGER NOT NULL DEFAULT 0,
    retained_count INTEGER NOT NULL DEFAULT 0,
    revoked_count INTEGER NOT NULL DEFAULT 0,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. Access Certification Line-Items (Decisions)
CREATE TABLE IF NOT EXISTS identity_certification_items (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES identity_certification_campaigns(id) ON DELETE CASCADE,
    principal_id TEXT NOT NULL,
    principal_name TEXT NOT NULL,
    role_or_permission TEXT NOT NULL,
    resource_scope TEXT NOT NULL DEFAULT 'GLOBAL',
    decision TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'RETAIN', 'REDUCE', 'REVOKE', 'INVESTIGATE', 'DEFER'
    reviewer_id TEXT REFERENCES users(id),
    decided_at TIMESTAMP,
    rationale TEXT,
    remediation_action_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_certification_items_lookup ON identity_certification_items(campaign_id, decision);

-- 8. Two-Phase Remediation Actions (Applied & Verified Revocation)
CREATE TABLE IF NOT EXISTS identity_remediation_actions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT REFERENCES identity_certification_campaigns(id) ON DELETE SET NULL,
    certification_item_id TEXT REFERENCES identity_certification_items(id) ON DELETE SET NULL,
    principal_id TEXT NOT NULL,
    target_grant TEXT NOT NULL,
    action_type TEXT NOT NULL, -- 'REVOKE_ROLE', 'REDUCE_SCOPE', 'DEACTIVATE_USER'
    status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'APPLIED', 'VERIFIED', 'FAILED'
    applied_at TIMESTAMP,
    applied_by TEXT REFERENCES users(id),
    verified_at TIMESTAMP,
    verified_by TEXT REFERENCES users(id),
    verification_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_remediation_actions_status ON identity_remediation_actions(status);

-- 9. Separation of Duties (SoD) & Toxic Combinations Matrix
CREATE TABLE IF NOT EXISTS identity_sod_toxic_rules (
    id TEXT PRIMARY KEY,
    rule_code TEXT NOT NULL UNIQUE,
    role_or_perm_a TEXT NOT NULL,
    role_or_perm_b TEXT NOT NULL,
    risk_tier TEXT NOT NULL DEFAULT 'CRITICAL', -- 'CRITICAL', 'HIGH'
    rationale TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sod_rules_lookup ON identity_sod_toxic_rules(rule_code, is_active);

-- 10. Tamper-Evident Identity Governance Audit Ledger
CREATE TABLE IF NOT EXISTS identity_audit_ledger (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL, -- 'JOINER_CREATED', 'MOVER_TRANSITION', 'LEAVER_OFFBOARDED', 'JIT_REQUESTED', 'JIT_APPROVED', 'JIT_ACTIVATED', 'JIT_EXPIRED', 'BREAK_GLASS_ACTIVATED', 'BREAK_GLASS_REVIEWED', 'SERVICE_ACCOUNT_REGISTERED', 'CERTIFICATION_DECIDED', 'REMEDIATION_APPLIED', 'REMEDIATION_VERIFIED'
    principal_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_name TEXT,
    action_details TEXT,
    target_resource TEXT,
    result_status TEXT NOT NULL DEFAULT 'SUCCESS', -- 'SUCCESS', 'DENIED', 'VIOLATION_BLOCKED'
    metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_identity_audit_event ON identity_audit_ledger(event_type, created_at);

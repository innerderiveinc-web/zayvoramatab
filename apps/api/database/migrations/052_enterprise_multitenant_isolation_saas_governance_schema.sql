-- Migration 052: Enterprise Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance Schema
-- Phase 55 of ZAYVORA MATAB OS

CREATE TABLE IF NOT EXISTS saas_tenant_lifecycle (
    tenant_id TEXT PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('PROVISIONING', 'ACTIVE', 'SUSPENDED', 'OFFBOARDING', 'DECOMMISSIONED')),
    previous_status TEXT,
    status_reason TEXT,
    provisioning_idempotency_key TEXT UNIQUE,
    provisioned_by TEXT,
    activated_at TEXT,
    suspended_at TEXT,
    offboarded_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saas_tenant_entitlements (
    tenant_id TEXT PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    plan_tier TEXT NOT NULL DEFAULT 'PROFESSIONAL' CHECK(plan_tier IN ('STARTER', 'PROFESSIONAL', 'ENTERPRISE', 'CUSTOM')),
    max_active_practitioners INTEGER NOT NULL DEFAULT 10,
    max_facilities INTEGER NOT NULL DEFAULT 5,
    max_storage_mb INTEGER NOT NULL DEFAULT 5000,
    api_rate_limit_rpm INTEGER NOT NULL DEFAULT 120,
    features_enabled_json TEXT NOT NULL DEFAULT '["CLINICAL_CORE", "INVENTORY", "TELEHEALTH", "ABDM_INTEGRATION"]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saas_break_glass_tickets (
    ticket_id TEXT PRIMARY KEY,
    target_tenant_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    support_user_id TEXT NOT NULL REFERENCES users(id),
    reason_code TEXT NOT NULL CHECK(reason_code IN ('EMERGENCY_CLINICAL_INVESTIGATION', 'SYSTEM_OUTAGE_REMEDIATION', 'REGULATORY_COMPLIANCE_AUDIT', 'CUSTOMER_REQUESTED_SUPPORT')),
    justification TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 30,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'EXPIRED', 'REVOKED')),
    approved_by TEXT NOT NULL,
    session_token TEXT UNIQUE,
    started_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    revoked_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS saas_governance_audit_ledger (
    ledger_id TEXT PRIMARY KEY,
    sequence_number INTEGER NOT NULL,
    tenant_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_saas_lifecycle_status ON saas_tenant_lifecycle(status);
CREATE INDEX IF NOT EXISTS idx_saas_tickets_target ON saas_break_glass_tickets(target_tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_saas_ledger_seq ON saas_governance_audit_ledger(sequence_number);

-- Backfill pre-existing organizations into lifecycle and entitlements
INSERT OR IGNORE INTO saas_tenant_lifecycle (tenant_id, status, status_reason, activated_at, created_at, updated_at)
SELECT id, 'ACTIVE', 'Pre-existing organization backfill', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
FROM organizations;

INSERT OR IGNORE INTO saas_tenant_entitlements (tenant_id, plan_tier, max_active_practitioners, max_facilities, max_storage_mb, api_rate_limit_rpm)
SELECT id, 'PROFESSIONAL', 10, 5, 5000, 120
FROM organizations;

-- Genesis Block for SaaS Governance Audit Ledger
INSERT OR IGNORE INTO saas_governance_audit_ledger (
    ledger_id, sequence_number, tenant_id, event_type, actor_id, target_id,
    payload_json, prev_hash, record_hash, created_at
) VALUES (
    'SGL-GENESIS-0001',
    1,
    'T-SYSTEM',
    'GENESIS_BLOCK',
    'SYSTEM',
    'GLOBAL',
    '{"message": "Genesis Block of Multi-Tenant SaaS Governance Ledger"}',
    '0000000000000000000000000000000000000000000000000000000000000000',
    '7b66ee0b38b91ce9a1aed2a2dacd6d8ef348f7cf15a98b176140fa17b0a866ba',
    '2026-10-15T00:00:00.000000Z'
);

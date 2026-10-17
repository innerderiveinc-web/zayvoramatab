-- Migration 053: Enterprise Backup, Disaster Recovery, Business Continuity & Verified Restore Schema
-- Phase 56 of ZAYVORA MATAB OS

-- 1. Governed Backup Manifests (Tamper-Evident Chain of Custody)
CREATE TABLE IF NOT EXISTS dr_backup_manifests (
    manifest_id TEXT PRIMARY KEY,
    backup_id TEXT NOT NULL REFERENCES dr_backup_catalog(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL,
    source_environment TEXT NOT NULL DEFAULT 'production',
    application_version TEXT NOT NULL DEFAULT '1.0.0-enterprise',
    schema_version TEXT NOT NULL DEFAULT '053',
    database_checksum_sha256 TEXT NOT NULL,
    attachments_checksum_sha256 TEXT,
    manifest_signature_sha256 TEXT NOT NULL,
    component_coverage_json TEXT NOT NULL DEFAULT '["database", "attachments", "manifest"]',
    table_record_counts_json TEXT NOT NULL DEFAULT '{}',
    retention_policy_tier TEXT NOT NULL DEFAULT '30_days_standard' CHECK(retention_policy_tier IN ('7_days_operational', '30_days_standard', '365_days_compliance', '7_years_clinical_legal')),
    retention_expires_at TEXT NOT NULL,
    immutable_lock_until TEXT,
    validation_status TEXT NOT NULL DEFAULT 'unverified' CHECK(validation_status IN ('unverified', 'verified_clean', 'tamper_detected', 'corrupted')),
    validated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dr_manifests_backup ON dr_backup_manifests(backup_id);
CREATE INDEX IF NOT EXISTS idx_dr_manifests_org ON dr_backup_manifests(organization_id);
CREATE INDEX IF NOT EXISTS idx_dr_manifests_status ON dr_backup_manifests(validation_status);

-- 2. Point-In-Time Recovery Markers & Canary Transactions (RPO Measurement)
CREATE TABLE IF NOT EXISTS dr_pitr_recovery_points (
    marker_id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    marker_timestamp TEXT NOT NULL,
    transaction_seq INTEGER NOT NULL DEFAULT 1,
    marker_label TEXT NOT NULL,
    wal_checkpoint_status TEXT NOT NULL DEFAULT 'checkpointed' CHECK(wal_checkpoint_status IN ('pending', 'checkpointed', 'flushed')),
    canary_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dr_pitr_timestamp ON dr_pitr_recovery_points(marker_timestamp);
CREATE INDEX IF NOT EXISTS idx_dr_pitr_org ON dr_pitr_recovery_points(organization_id);

-- 3. Isolated Restore Drill Verifications & Promotion Gatekeeper
CREATE TABLE IF NOT EXISTS dr_isolated_restore_verifications (
    verification_id TEXT PRIMARY KEY,
    drill_id TEXT NOT NULL REFERENCES dr_restore_drill_executions(id) ON DELETE CASCADE,
    backup_id TEXT NOT NULL REFERENCES dr_backup_catalog(id),
    organization_id TEXT NOT NULL,
    target_environment TEXT NOT NULL DEFAULT 'isolated_test_sandbox' CHECK(target_environment IN ('isolated_test_sandbox', 'staging_isolated', 'production_emergency')),
    technical_integrity_ok INTEGER NOT NULL DEFAULT 0,
    foreign_key_violations_count INTEGER NOT NULL DEFAULT 0,
    clinical_invariants_ok INTEGER NOT NULL DEFAULT 0,
    tenant_isolation_ok INTEGER NOT NULL DEFAULT 0,
    outbound_side_effects_suppressed INTEGER NOT NULL DEFAULT 1,
    rto_measured_seconds REAL NOT NULL DEFAULT 0.0,
    rpo_measured_seconds REAL NOT NULL DEFAULT 0.0,
    promotion_status TEXT NOT NULL DEFAULT 'DISPOSABLE_SANDBOX_CLEANED' CHECK(promotion_status IN (
        'PENDING_VALIDATION', 'QUALIFIED_FOR_PROMOTION', 'PROMOTION_APPROVED', 'PROMOTION_REJECTED', 'DISPOSABLE_SANDBOX_CLEANED'
    )),
    promoted_by TEXT,
    promoted_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dr_verif_drill ON dr_isolated_restore_verifications(drill_id);
CREATE INDEX IF NOT EXISTS idx_dr_verif_status ON dr_isolated_restore_verifications(promotion_status);

-- 4. Cryptographic SHA-256 Chained DR Governance Audit Ledger
CREATE TABLE IF NOT EXISTS dr_governance_audit_ledger (
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

CREATE INDEX IF NOT EXISTS idx_dr_ledger_seq ON dr_governance_audit_ledger(sequence_number);
CREATE INDEX IF NOT EXISTS idx_dr_ledger_tenant ON dr_governance_audit_ledger(tenant_id);

-- 5. Seed Genesis Block for DR Governance Audit Ledger
INSERT OR IGNORE INTO dr_governance_audit_ledger (
    ledger_id, sequence_number, tenant_id, event_type, actor_id, target_id,
    payload_json, prev_hash, record_hash, created_at
) VALUES (
    'DGL-GENESIS-0001',
    1,
    'T-SYSTEM',
    'GENESIS_BLOCK',
    'SYSTEM',
    'GLOBAL',
    '{"message": "Genesis Block of Disaster Recovery & Verified Restore Ledger"}',
    '0000000000000000000000000000000000000000000000000000000000000000',
    '81451b0bd926dd981dd08c993c0252c8380a0d9a236847ef1e696d58c5637941',
    '2026-10-15T00:00:00.000000Z'
);

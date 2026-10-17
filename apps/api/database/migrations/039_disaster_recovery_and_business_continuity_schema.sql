-- ============================================================================
-- Migration: 039_disaster_recovery_and_business_continuity_schema.sql
-- Description: Disaster Recovery, Business Continuity, Backup/Restore Verification & Downtime Reconciliation Schema
-- System: ZAYVORA MATAB OS — Standalone Unani Clinic & Practice Operating System
-- ============================================================================

-- 1. Governed BIA & Criticality Domain Catalog
CREATE TABLE IF NOT EXISTS dr_domain_criticality_catalog (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    domain_name TEXT NOT NULL,
    tier TEXT NOT NULL CHECK(tier IN ('tier_0_critical', 'tier_1_core', 'tier_2_supporting', 'tier_3_internal')),
    system_of_record_tables_json TEXT NOT NULL DEFAULT '[]',
    business_owner TEXT NOT NULL,
    technical_owner TEXT NOT NULL,
    approved_rto_minutes INTEGER NOT NULL DEFAULT 15,
    approved_rpo_minutes INTEGER NOT NULL DEFAULT 5,
    degraded_mode_policy TEXT NOT NULL,
    reconciliation_protocol TEXT NOT NULL,
    last_drill_timestamp TEXT,
    status TEXT NOT NULL CHECK(status IN ('fully_protected', 'partially_protected', 'untested', 'at_risk')) DEFAULT 'untested',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dr_domains_tier ON dr_domain_criticality_catalog(tier);
CREATE INDEX IF NOT EXISTS idx_dr_domains_status ON dr_domain_criticality_catalog(status);

-- 2. Physical Backup Catalog
CREATE TABLE IF NOT EXISTS dr_backup_catalog (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    backup_type TEXT NOT NULL CHECK(backup_type IN ('full', 'incremental_wal', 'table_export')) DEFAULT 'full',
    scope TEXT NOT NULL CHECK(scope IN ('database_all', 'database_tables', 'artifacts')) DEFAULT 'database_all',
    source_database_path TEXT NOT NULL,
    backup_artifact_path TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    encryption_status TEXT NOT NULL CHECK(encryption_status IN ('encrypted_aes256', 'unencrypted_isolated_dev')) DEFAULT 'unencrypted_isolated_dev',
    encryption_key_id TEXT,
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'corrupted', 'purged')) DEFAULT 'pending',
    integrity_check_status TEXT NOT NULL CHECK(integrity_check_status IN ('unverified', 'passed', 'failed')) DEFAULT 'unverified',
    integrity_check_output TEXT,
    total_tables INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_dr_backups_status ON dr_backup_catalog(status);
CREATE INDEX IF NOT EXISTS idx_dr_backups_created ON dr_backup_catalog(created_at);

-- 3. Restore Drill Execution Ledger
CREATE TABLE IF NOT EXISTS dr_restore_drill_executions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    backup_id TEXT NOT NULL REFERENCES dr_backup_catalog(id),
    target_environment TEXT NOT NULL CHECK(target_environment IN ('isolated_test_sandbox', 'staging_isolated', 'production_emergency')) DEFAULT 'isolated_test_sandbox',
    requested_by TEXT NOT NULL,
    authorized_by TEXT NOT NULL,
    incident_ref TEXT,
    purpose TEXT NOT NULL,
    step_progress_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN (
        'requested', 'running', 'technical_verification_passed',
        'workflow_verification_passed', 'indeterminate_partial',
        'failed', 'cleaned_up', 'business_resumption_approved'
    )) DEFAULT 'requested',
    duration_seconds REAL DEFAULT 0.0,
    data_loss_window_seconds REAL DEFAULT 0.0,
    verification_report_json TEXT NOT NULL DEFAULT '{}',
    reviewer_sign_off_id TEXT,
    resumption_authorized_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dr_drills_backup ON dr_restore_drill_executions(backup_id);
CREATE INDEX IF NOT EXISTS idx_dr_drills_status ON dr_restore_drill_executions(status);

-- 4. Business Continuity & Downtime Runbooks
CREATE TABLE IF NOT EXISTS dr_business_continuity_runbooks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    title TEXT NOT NULL,
    trigger_conditions TEXT NOT NULL,
    operational_owner TEXT NOT NULL,
    clinical_lead TEXT NOT NULL,
    safe_capabilities_json TEXT NOT NULL DEFAULT '[]',
    prohibited_actions_json TEXT NOT NULL DEFAULT '[]',
    offline_recording_procedure_markdown TEXT NOT NULL,
    reconciliation_protocol_markdown TEXT NOT NULL,
    resumption_criteria_json TEXT NOT NULL DEFAULT '[]',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dr_runbooks_active ON dr_business_continuity_runbooks(is_active);

-- 5. Downtime Offline Record Reconciliation Queue
CREATE TABLE IF NOT EXISTS dr_downtime_reconciliation_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    runbook_id TEXT NOT NULL REFERENCES dr_business_continuity_runbooks(id),
    downtime_reference_code TEXT NOT NULL,
    domain TEXT NOT NULL CHECK(domain IN ('patient_encounter', 'vital_signs', 'prescription_order', 'billing_invoice', 'stock_dispensation')),
    patient_identifier TEXT NOT NULL,
    captured_by_name TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    recorded_payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('pending_review', 'validated', 'reconciled', 'conflicted_duplicate', 'rejected')) DEFAULT 'pending_review',
    reconciled_by TEXT,
    reconciled_at TEXT,
    target_canonical_id TEXT,
    reconciliation_notes TEXT,
    conflict_resolution_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dr_reconciliation_status ON dr_downtime_reconciliation_records(status);
CREATE INDEX IF NOT EXISTS idx_dr_reconciliation_ref ON dr_downtime_reconciliation_records(downtime_reference_code);
CREATE INDEX IF NOT EXISTS idx_dr_reconciliation_patient ON dr_downtime_reconciliation_records(patient_identifier);

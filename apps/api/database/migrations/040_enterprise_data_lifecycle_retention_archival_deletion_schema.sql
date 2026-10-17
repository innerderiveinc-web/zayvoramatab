-- ============================================================================
-- Migration: 040_enterprise_data_lifecycle_retention_archival_deletion_schema.sql
-- Description: Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Governance Schema
-- System: ZAYVORA MATAB OS — Standalone Unani Clinic & Practice Operating System
-- ============================================================================

-- 1. Governed Data Category Inventory Catalog
CREATE TABLE IF NOT EXISTS data_lifecycle_inventory_catalog (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    category_name TEXT NOT NULL,
    description TEXT NOT NULL,
    canonical_source_table TEXT NOT NULL,
    storage_type TEXT NOT NULL CHECK(storage_type IN ('relational_table', 'file_system_artifact', 'event_queue', 'cache_read_model')),
    data_owner_role TEXT NOT NULL,
    technical_owner_role TEXT NOT NULL,
    sensitivity_classification TEXT NOT NULL CHECK(sensitivity_classification IN ('restricted_phi', 'financial_pci', 'operational_confidential', 'public_knowledge')),
    linked_copies_json TEXT NOT NULL DEFAULT '[]',
    default_policy_key TEXT,
    disposal_supported TEXT NOT NULL CHECK(disposal_supported IN ('delete', 'deidentify', 'restrict', 'manual_review')) DEFAULT 'manual_review',
    backup_behavior TEXT NOT NULL DEFAULT 'EXPIRE_WITH_BACKUP_ROTATION',
    status TEXT NOT NULL CHECK(status IN ('governed', 'review_due', 'unmapped')) DEFAULT 'governed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dl_inventory_sens ON data_lifecycle_inventory_catalog(sensitivity_classification);
CREATE INDEX IF NOT EXISTS idx_dl_inventory_status ON data_lifecycle_inventory_catalog(status);

-- 2. Versioned Retention Policy Registry
CREATE TABLE IF NOT EXISTS data_lifecycle_policies (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    policy_key TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0.0',
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    data_category_ids_json TEXT NOT NULL DEFAULT '[]',
    scope TEXT NOT NULL CHECK(scope IN ('platform', 'tenant', 'branch', 'record')) DEFAULT 'tenant',
    retention_trigger TEXT NOT NULL CHECK(retention_trigger IN ('creation_date', 'discharge_date', 'last_encounter_date', 'finalization_date', 'closure_date')) DEFAULT 'creation_date',
    retention_period_days INTEGER NOT NULL DEFAULT 2555,
    archive_rule TEXT NOT NULL CHECK(archive_rule IN ('COLD_STORAGE_PARTITION', 'RESTRICTED_READ_ONLY', 'FILESYSTEM_COMPRESSED', 'NONE')) DEFAULT 'RESTRICTED_READ_ONLY',
    disposal_action TEXT NOT NULL CHECK(disposal_action IN ('delete', 'deidentify', 'restrict', 'manual_review')) DEFAULT 'manual_review',
    hold_behavior TEXT NOT NULL CHECK(hold_behavior IN ('STRICT_BLOCK', 'NOTIFY_AND_HOLD')) DEFAULT 'STRICT_BLOCK',
    downstream_propagation_rule TEXT NOT NULL CHECK(downstream_propagation_rule IN ('ALL_LINKED_STORES', 'PRIMARY_ONLY', 'CASCADE_PURGE')) DEFAULT 'ALL_LINKED_STORES',
    backup_behavior TEXT NOT NULL DEFAULT 'EXPIRE_WITH_BACKUP_ROTATION',
    accountable_owner TEXT NOT NULL,
    approver_roles_json TEXT NOT NULL DEFAULT '[]',
    jurisdiction_tags_json TEXT NOT NULL DEFAULT '[]',
    legal_source_references_json TEXT NOT NULL DEFAULT '[]',
    caveats_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL CHECK(status IN ('draft', 'review', 'approved', 'retired')) DEFAULT 'draft',
    effective_from TEXT,
    effective_to TEXT,
    created_by TEXT NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dl_policies_key ON data_lifecycle_policies(policy_key);
CREATE INDEX IF NOT EXISTS idx_dl_policies_status ON data_lifecycle_policies(status);

-- 3. Universal Legal Holds & Preservation Register
CREATE TABLE IF NOT EXISTS data_lifecycle_legal_holds (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    hold_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    reason_category TEXT NOT NULL CHECK(reason_category IN ('litigation', 'regulatory_investigation', 'clinical_safety_inquiry', 'audit_preservation')),
    scope_filter_json TEXT NOT NULL DEFAULT '{}',
    placed_by TEXT NOT NULL,
    placed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_date TEXT,
    released_at TEXT,
    released_by TEXT,
    release_reason TEXT,
    status TEXT NOT NULL CHECK(status IN ('active', 'released', 'expired')) DEFAULT 'active',
    affected_records_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dl_holds_status ON data_lifecycle_legal_holds(status);
CREATE INDEX IF NOT EXISTS idx_dl_holds_code ON data_lifecycle_legal_holds(hold_code);

-- 4. Retention Evaluation & Dry-Run Runs Ledger
CREATE TABLE IF NOT EXISTS data_lifecycle_evaluation_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    policy_id TEXT NOT NULL REFERENCES data_lifecycle_policies(id),
    policy_version TEXT NOT NULL,
    category_id TEXT NOT NULL REFERENCES data_lifecycle_inventory_catalog(id),
    run_mode TEXT NOT NULL CHECK(run_mode IN ('dry_run', 'enforcement_execution')) DEFAULT 'dry_run',
    records_evaluated INTEGER NOT NULL DEFAULT 0,
    records_eligible INTEGER NOT NULL DEFAULT 0,
    records_held INTEGER NOT NULL DEFAULT 0,
    records_ineligible INTEGER NOT NULL DEFAULT 0,
    evaluation_summary_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN ('completed', 'failed')) DEFAULT 'completed',
    executed_by TEXT NOT NULL,
    executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dl_eval_policy ON data_lifecycle_evaluation_runs(policy_id);
CREATE INDEX IF NOT EXISTS idx_dl_eval_category ON data_lifecycle_evaluation_runs(category_id);

-- 5. Governed Lifecycle Operations & Secure Disposal Ledger
CREATE TABLE IF NOT EXISTS data_lifecycle_operations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK(operation_type IN ('archive', 'restrict', 'deidentify', 'secure_delete', 'reconcile_restore')),
    category_id TEXT NOT NULL REFERENCES data_lifecycle_inventory_catalog(id),
    target_record_id TEXT NOT NULL,
    policy_id TEXT NOT NULL REFERENCES data_lifecycle_policies(id),
    policy_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'pending', 'running', 'archived', 'restricted', 'deidentified',
        'deletion_partial', 'verified_complete', 'blocked_by_hold', 'failed'
    )) DEFAULT 'pending',
    per_store_status_json TEXT NOT NULL DEFAULT '{}',
    verification_evidence_json TEXT NOT NULL DEFAULT '{}',
    executed_by TEXT NOT NULL,
    authorized_by TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_dl_ops_target ON data_lifecycle_operations(category_id, target_record_id);
CREATE INDEX IF NOT EXISTS idx_dl_ops_status ON data_lifecycle_operations(status);

-- 6. Data Subject Privacy Rights & Correction Requests
CREATE TABLE IF NOT EXISTS data_lifecycle_requests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    request_type TEXT NOT NULL CHECK(request_type IN ('data_access', 'data_export', 'rectification', 'erasure_restriction', 'objection')),
    requester_identity_type TEXT NOT NULL CHECK(requester_identity_type IN ('patient', 'guardian', 'regulatory_authority', 'legal_counsel')),
    patient_identifier TEXT NOT NULL,
    identity_verified INTEGER NOT NULL DEFAULT 0,
    proposed_plan_json TEXT NOT NULL DEFAULT '{}',
    authorized_by TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'received', 'identity_verified', 'in_review', 'approved', 'executing',
        'completed', 'rejected', 'blocked_by_hold'
    )) DEFAULT 'received',
    rejection_reason TEXT,
    closure_evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dl_req_status ON data_lifecycle_requests(status);
CREATE INDEX IF NOT EXISTS idx_dl_req_patient ON data_lifecycle_requests(patient_identifier);

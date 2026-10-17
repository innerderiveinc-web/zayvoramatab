-- Migration 048: Enterprise Test Automation, Regression Testing & Release Qualification Schema
-- Phase 49: ZAYVORA MATAB OS

-- 1. Test Automation Suites Catalog
CREATE TABLE IF NOT EXISTS test_automation_suites_catalog (
    id TEXT PRIMARY KEY,
    suite_code TEXT NOT NULL UNIQUE, -- e.g. SUITE-UNIT-PRESCRIPTIONS, SUITE-E2E-PATIENT-JOURNEY
    name TEXT NOT NULL,
    test_layer TEXT NOT NULL, -- UNIT, COMPONENT, API_INTEGRATION, E2E_WORKFLOW, CONTRACT, MIGRATION, SECURITY, PERFORMANCE, ACCESSIBILITY
    target_subsystem TEXT NOT NULL, -- CLINICAL_PRESCRIPTIONS, PATIENT_REGISTRY, IDENTITY_RBAC, INTEROPERABILITY_FHIR, DATA_LIFECYCLE, etc.
    test_file_path TEXT NOT NULL, -- e.g. tests/unit/test_prescriptions.py
    command_template TEXT NOT NULL, -- e.g. python -m unittest tests/unit/test_prescriptions.py
    execution_environment TEXT NOT NULL DEFAULT 'ISOLATED_SYNTHETIC', -- ISOLATED_SYNTHETIC, LOCAL_DEV, CI_RUNNER, STAGING_SANDBOX
    is_mandatory_for_release INTEGER NOT NULL DEFAULT 1, -- 1=True, 0=False
    timeout_seconds INTEGER NOT NULL DEFAULT 60,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, QUARANTINED, DEPRECATED
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasc_code ON test_automation_suites_catalog(suite_code);
CREATE INDEX IF NOT EXISTS idx_tasc_layer ON test_automation_suites_catalog(test_layer);
CREATE INDEX IF NOT EXISTS idx_tasc_subsystem ON test_automation_suites_catalog(target_subsystem);
CREATE INDEX IF NOT EXISTS idx_tasc_status ON test_automation_suites_catalog(status);

-- 2. Test Execution Runs Evidence Ledger
CREATE TABLE IF NOT EXISTS test_execution_runs (
    id TEXT PRIMARY KEY,
    run_code TEXT NOT NULL UNIQUE, -- e.g. RUN-20261014-001
    suite_id TEXT NOT NULL REFERENCES test_automation_suites_catalog(id) ON DELETE CASCADE,
    target_release_version TEXT NOT NULL DEFAULT 'v1.0.0',
    environment TEXT NOT NULL DEFAULT 'ISOLATED_SYNTHETIC',
    commit_hash TEXT NOT NULL DEFAULT 'HEAD',
    trigger_source TEXT NOT NULL DEFAULT 'CI_PIPELINE', -- CI_PIPELINE, MANUAL_QUALIFICATION, PRE_RELEASE_GATE
    status TEXT NOT NULL DEFAULT 'PASSED', -- PASSED, FAILED, BLOCKED, SKIPPED, FLAKY, QUARANTINED
    total_tests INTEGER NOT NULL DEFAULT 0,
    passed_tests INTEGER NOT NULL DEFAULT 0,
    failed_tests INTEGER NOT NULL DEFAULT 0,
    skipped_tests INTEGER NOT NULL DEFAULT 0,
    execution_duration_ms INTEGER NOT NULL DEFAULT 0,
    evidence_summary_json TEXT NOT NULL DEFAULT '{}',
    executed_by_actor_id TEXT NOT NULL DEFAULT 'usr-admin-1',
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ter_code ON test_execution_runs(run_code);
CREATE INDEX IF NOT EXISTS idx_ter_suite ON test_execution_runs(suite_id);
CREATE INDEX IF NOT EXISTS idx_ter_status ON test_execution_runs(status);
CREATE INDEX IF NOT EXISTS idx_ter_version ON test_execution_runs(target_release_version);

-- 3. Test Flakiness & Quarantine Register
CREATE TABLE IF NOT EXISTS test_flakiness_and_quarantine_register (
    id TEXT PRIMARY KEY,
    quarantine_code TEXT NOT NULL UNIQUE, -- e.g. QRN-202610-001
    suite_id TEXT NOT NULL REFERENCES test_automation_suites_catalog(id) ON DELETE CASCADE,
    test_name TEXT NOT NULL,
    reason TEXT NOT NULL,
    root_cause_category TEXT NOT NULL DEFAULT 'UNKNOWN', -- TIMING_RACE, STATE_POLLUTION, EXTERNAL_DEPENDENCY, RESOURCE_STARVATION, UNKNOWN
    quarantined_by_actor_id TEXT NOT NULL,
    assigned_owner TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE_QUARANTINE', -- ACTIVE_QUARANTINE, INVESTIGATING, FIX_IN_PROGRESS, RESOLVED, RE_ENABLED
    quarantined_at TEXT NOT NULL DEFAULT (datetime('now')),
    target_resolution_date TEXT NOT NULL, -- strictly <= 14 days
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tfqr_code ON test_flakiness_and_quarantine_register(quarantine_code);
CREATE INDEX IF NOT EXISTS idx_tfqr_suite ON test_flakiness_and_quarantine_register(suite_id);
CREATE INDEX IF NOT EXISTS idx_tfqr_status ON test_flakiness_and_quarantine_register(status);

-- 4. Release Qualification Profiles
CREATE TABLE IF NOT EXISTS release_qualification_profiles (
    id TEXT PRIMARY KEY,
    profile_code TEXT NOT NULL UNIQUE, -- PROF-DEV, PROF-STAGING, PROF-PROD
    name TEXT NOT NULL,
    target_tier TEXT NOT NULL, -- DEVELOPMENT, STAGING_PILOT, PRODUCTION_REGULATED
    required_test_layers_json TEXT NOT NULL, -- JSON array of strings
    required_suites_json TEXT NOT NULL, -- JSON array of suite_codes
    min_pass_rate_bp INTEGER NOT NULL DEFAULT 10000, -- Basis points: 10000 = 100%, 9800 = 98%
    allow_quarantined_tests INTEGER NOT NULL DEFAULT 0, -- 1=True, 0=False
    max_critical_defects INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rqp_code ON release_qualification_profiles(profile_code);
CREATE INDEX IF NOT EXISTS idx_rqp_tier ON release_qualification_profiles(target_tier);

-- 5. Release Candidate Qualifications (Gate Decisions)
CREATE TABLE IF NOT EXISTS release_candidate_qualifications (
    id TEXT PRIMARY KEY,
    candidate_code TEXT NOT NULL UNIQUE, -- e.g. RC-QUAL-202610-001
    target_release_version TEXT NOT NULL,
    profile_id TEXT NOT NULL REFERENCES release_qualification_profiles(id),
    commit_hash TEXT NOT NULL,
    repository_revision TEXT NOT NULL DEFAULT 'HEAD',
    overall_verdict TEXT NOT NULL DEFAULT 'BLOCKED', -- QUALIFIED, BLOCKED, CONDITIONAL_PASS, STALE_EVIDENCE
    evaluated_suites_count INTEGER NOT NULL DEFAULT 0,
    passed_suites_count INTEGER NOT NULL DEFAULT 0,
    total_tests_executed INTEGER NOT NULL DEFAULT 0,
    total_tests_passed INTEGER NOT NULL DEFAULT 0,
    open_defects_count INTEGER NOT NULL DEFAULT 0,
    blocking_reasons_json TEXT NOT NULL DEFAULT '[]', -- JSON array of strings
    qualification_summary_json TEXT NOT NULL DEFAULT '{}',
    qualified_by_actor_id TEXT NOT NULL,
    evaluated_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL, -- Qualification expires after 72 hours if not deployed
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_rcq_code ON release_candidate_qualifications(candidate_code);
CREATE INDEX IF NOT EXISTS idx_rcq_verdict ON release_candidate_qualifications(overall_verdict);
CREATE INDEX IF NOT EXISTS idx_rcq_version ON release_candidate_qualifications(target_release_version);

-- 6. Test Automation Defect Register
CREATE TABLE IF NOT EXISTS test_automation_defect_register (
    id TEXT PRIMARY KEY,
    defect_code TEXT NOT NULL UNIQUE, -- e.g. DEF-202610-001
    title TEXT NOT NULL,
    test_run_id TEXT REFERENCES test_execution_runs(id) ON DELETE SET NULL,
    test_name TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MAJOR', -- BLOCKER, CRITICAL, MAJOR, MINOR
    failure_classification TEXT NOT NULL DEFAULT 'PRODUCT_DEFECT', -- PRODUCT_DEFECT, TEST_DEFECT, ENVIRONMENT_FLAKE, DATA_CORRUPTION, UNKNOWN
    sanitized_stack_trace TEXT NOT NULL, -- Zero PHI, zero raw credentials
    reproduction_steps TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN', -- OPEN, INVESTIGATING, FIX_IN_PROGRESS, VERIFIED_CLOSED
    linked_hazard_id TEXT, -- Traceability link to clinical_hazard_register(id)
    assigned_owner TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tadr_code ON test_automation_defect_register(defect_code);
CREATE INDEX IF NOT EXISTS idx_tadr_status ON test_automation_defect_register(status);
CREATE INDEX IF NOT EXISTS idx_tadr_severity ON test_automation_defect_register(severity);
CREATE INDEX IF NOT EXISTS idx_tadr_hazard ON test_automation_defect_register(linked_hazard_id);

-- 7. Tamper-Evident Test Qualification Audit Ledger
CREATE TABLE IF NOT EXISTS test_qualification_audit_ledger (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL, -- SUITE_REGISTERED, TEST_RUN_LOGGED, TEST_QUARANTINED, QUARANTINE_RESOLVED, DEFECT_LOGGED, DEFECT_CLOSED, RELEASE_QUALIFIED
    severity TEXT NOT NULL DEFAULT 'INFO', -- INFO, WARNING, ERROR, CRITICAL
    actor_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action_details_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tqal_type ON test_qualification_audit_ledger(event_type);
CREATE INDEX IF NOT EXISTS idx_tqal_actor ON test_qualification_audit_ledger(actor_id);
CREATE INDEX IF NOT EXISTS idx_tqal_time ON test_qualification_audit_ledger(occurred_at);

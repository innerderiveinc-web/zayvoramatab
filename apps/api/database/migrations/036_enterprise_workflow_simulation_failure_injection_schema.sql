-- Migration 036: Enterprise Workflow Simulation, Failure Injection & Recovery Validation Schema
-- Phase 37 for ZAYVORA MATAB OS

PRAGMA foreign_keys = OFF;

-- 1. Governed Simulation Scenarios
CREATE TABLE IF NOT EXISTS simulation_scenarios (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    scenario_key TEXT NOT NULL,
    name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('workflow_lifecycle', 'duplicate_and_ordering', 'dependency_faults', 'clinical_safety_boundary')),
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'moderate', 'high')),
    environment_allowlist_json TEXT NOT NULL DEFAULT '["local","dev","sandbox","ci"]',
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'RETIRED')),
    owner_role TEXT NOT NULL DEFAULT 'SYSTEM_ADMIN',
    required_permissions_json TEXT NOT NULL DEFAULT '["simulation:run"]',
    steps_json TEXT NOT NULL DEFAULT '[]',
    assertions_json TEXT NOT NULL DEFAULT '[]',
    cleanup_policy TEXT NOT NULL DEFAULT 'automatic' CHECK (cleanup_policy IN ('automatic', 'manual_review')),
    timeout_seconds INTEGER NOT NULL DEFAULT 60,
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, scenario_key)
);

CREATE INDEX IF NOT EXISTS idx_sim_scen_org_status ON simulation_scenarios(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_sim_scen_cat ON simulation_scenarios(category);

-- 2. Scenario Version History Snapshots
CREATE TABLE IF NOT EXISTS simulation_scenario_versions (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES simulation_scenarios(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    change_reason TEXT,
    authored_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scenario_id, version)
);

-- 3. Simulation Runs Ledger
CREATE TABLE IF NOT EXISTS simulation_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    scenario_id TEXT NOT NULL REFERENCES simulation_scenarios(id) ON DELETE RESTRICT,
    scenario_version INTEGER NOT NULL,
    scenario_key TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'local',
    status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('DRAFT', 'QUEUED', 'RUNNING', 'PASSED', 'FAILED', 'INDETERMINATE', 'TIMED_OUT', 'CANCELLED', 'CLEANUP_PENDING', 'CLEANED_UP')),
    namespace_prefix TEXT NOT NULL,
    is_dry_run INTEGER NOT NULL DEFAULT 1,
    fault_manifest_json TEXT NOT NULL DEFAULT '[]',
    steps_count INTEGER NOT NULL DEFAULT 0,
    passed_assertions_count INTEGER NOT NULL DEFAULT 0,
    total_assertions_count INTEGER NOT NULL DEFAULT 0,
    failure_reason TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    executed_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sim_runs_org_status ON simulation_runs(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_sim_runs_scen ON simulation_runs(scenario_id);

-- 4. Step Telemetry & Injected Faults
CREATE TABLE IF NOT EXISTS simulation_step_executions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    target_service TEXT NOT NULL,
    fault_injected TEXT,
    payload_snapshot_safe TEXT,
    response_snapshot_safe TEXT,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'SUCCESS' CHECK (status IN ('SUCCESS', 'FAULT_INJECTED', 'FAILED', 'SKIPPED')),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sim_step_run ON simulation_step_executions(run_id);

-- 5. Canonical Assertions Ledger
CREATE TABLE IF NOT EXISTS simulation_assertions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    assertion_key TEXT NOT NULL,
    assertion_type TEXT NOT NULL,
    expected_condition TEXT NOT NULL,
    observed_result TEXT,
    status TEXT NOT NULL CHECK (status IN ('passed', 'failed', 'indeterminate', 'not_applicable')),
    evidence_reference TEXT,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sim_assert_run ON simulation_assertions(run_id);

-- 6. Release Gate Verification
CREATE TABLE IF NOT EXISTS simulation_release_gates (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    target_release_tag TEXT NOT NULL,
    evaluation_status TEXT NOT NULL CHECK (evaluation_status IN ('PASS', 'FAIL', 'INDETERMINATE', 'BLOCKED', 'NOT_RUN')),
    total_scenarios_evaluated INTEGER NOT NULL DEFAULT 0,
    passed_scenarios_count INTEGER NOT NULL DEFAULT 0,
    failed_scenarios_count INTEGER NOT NULL DEFAULT 0,
    evidence_summary_json TEXT NOT NULL DEFAULT '{}',
    evaluated_by TEXT REFERENCES users(id),
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, target_release_tag)
);

PRAGMA foreign_keys = ON;

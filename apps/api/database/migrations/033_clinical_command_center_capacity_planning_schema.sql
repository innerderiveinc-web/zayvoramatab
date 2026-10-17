-- Migration 033: Clinical Operations Command Center, Capacity Planning & Workflow Bottleneck Schema
-- Phase 34 for ZAYVORA MATAB OS
-- Strict non-negotiables enforced:
-- 1. Never fabricate live activity, wait times, appointment volumes, or alert thresholds.
-- 2. Strictly operational: Never diagnose, prescribe, triage acuity, or assess clinician competence.
-- 3. Queue elapsed times must NEVER be presented as clinical acuity or triage scores.
-- 4. Transparent reasons only: "reason not recorded" when cause is absent. Never invent causality.
-- 5. Scenario simulations must remain segregated from production records.
-- 6. Human-in-the-loop: Every action requires authenticated authorization and audit logging.

-- 1. Approved Operational Threshold Rules
CREATE TABLE IF NOT EXISTS command_center_threshold_rules (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    stage_key TEXT NOT NULL CHECK (stage_key IN (
        'CHECK_IN_TO_CALL',         -- Time waiting in reception before being called
        'CALL_TO_START',            -- Time between call and consultation commencement
        'CONSULTATION_DURATION',    -- Operational consultation elapsed time (non-clinical)
        'DISCHARGE_TO_BILLING',     -- Post-consultation billing clearance duration
        'BILLING_TO_PAYMENT',       -- Finalized invoice awaiting payment receipt
        'FOLLOW_UP_COMPLETION',     -- Scheduled care outreach task completion duration
        'DLQ_RESOLUTION'            -- Integration dead-letter item triage duration
    )),
    warning_threshold_mins INTEGER NOT NULL,
    critical_threshold_mins INTEGER NOT NULL,
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, facility_id, stage_key)
);

CREATE INDEX IF NOT EXISTS idx_cmd_thresholds ON command_center_threshold_rules(
    organization_id, facility_id, stage_key, is_active
);

-- 2. Operational Alerts (Deduplicated, State-Managed)
CREATE TABLE IF NOT EXISTS operational_alerts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    alert_type TEXT NOT NULL CHECK (alert_type IN (
        'STAGE_THRESHOLD_EXCEEDED',
        'SCHEDULE_CONFLICT',
        'OVERDUE_FOLLOWUP_BACKLOG',
        'DLQ_JOB_BLOCKED',
        'STALE_OPERATIONAL_FEED'
    )),
    severity TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'CRITICAL')),
    deduplication_key TEXT NOT NULL UNIQUE,
    source_entity TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    stage_key TEXT,
    measured_value_mins REAL,
    threshold_value_mins REAL,
    factual_reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN (
        'ACTIVE', 'ACKNOWLEDGED', 'RESOLVED', 'SUPPRESSED'
    )),
    acknowledged_by TEXT REFERENCES users(id),
    acknowledged_at TIMESTAMP,
    resolved_by TEXT REFERENCES users(id),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    cooldown_until TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cmd_alerts_lookup ON operational_alerts(
    organization_id, facility_id, status, severity
);
CREATE INDEX IF NOT EXISTS idx_cmd_alerts_dedup ON operational_alerts(deduplication_key);

-- 3. Capacity Scenarios (Simulations Segregated from Production)
CREATE TABLE IF NOT EXISTS capacity_scenarios (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    scenario_name TEXT NOT NULL,
    scenario_description TEXT,
    target_date TEXT NOT NULL, -- YYYY-MM-DD
    hypothetical_changes_json TEXT NOT NULL DEFAULT '[]',
    baseline_demand INTEGER NOT NULL DEFAULT 0,
    baseline_capacity INTEGER NOT NULL DEFAULT 0,
    scenario_capacity INTEGER NOT NULL DEFAULT 0,
    variance_slots INTEGER NOT NULL DEFAULT 0,
    is_simulation_only INTEGER NOT NULL DEFAULT 1 CHECK (is_simulation_only = 1),
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cmd_scenarios ON capacity_scenarios(
    organization_id, facility_id, target_date
);

-- 4. Human-in-the-Loop Operational Action Audit Ledger
CREATE TABLE IF NOT EXISTS operational_action_audit (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'ACKNOWLEDGE_ALERT',
        'RESOLVE_ALERT',
        'ASSIGN_TASK',
        'MARK_BLOCKER_RESOLVED',
        'REQUEST_SCHEDULE_REVIEW',
        'RECORD_OPERATIONAL_EXCEPTION',
        'RETRY_INTEGRATION_JOB'
    )),
    target_entity TEXT NOT NULL,
    target_id TEXT NOT NULL,
    before_state_json TEXT,
    after_state_json TEXT,
    reason TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    correlation_id TEXT,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cmd_action_audit ON operational_action_audit(
    organization_id, facility_id, actor_id, occurred_at
);

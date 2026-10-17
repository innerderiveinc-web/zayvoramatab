-- Migration 035: Enterprise Workflow Intelligence, SLA Governance & Exception Resolution Schema
-- Phase 36 for ZAYVORA MATAB OS
-- Enforces versioned SLA policies, canonical exception lifecycles, timer pause intervals,
-- multi-stage escalations, independent verification gates, and tamper-evident audit trails.

-- 1. Master Operational SLA Policy Registry
CREATE TABLE IF NOT EXISTS sla_policies (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    policy_key TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL CHECK (
        category IN ('administrative', 'follow_up', 'intake_gap', 'inventory', 'integration', 'governance', 'clinical_review')
    ),
    target_entity_type TEXT NOT NULL,
    owner_role TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (
        status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'ACTIVE', 'RETIRED')
    ) DEFAULT 'DRAFT',
    time_basis TEXT NOT NULL CHECK (
        time_basis IN ('elapsed', 'business_hours')
    ) DEFAULT 'elapsed',
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    warning_threshold_mins INTEGER NOT NULL,
    breach_threshold_mins INTEGER NOT NULL,
    pause_eligibility_json TEXT NOT NULL DEFAULT '[]', -- Array of permitted pause reason codes
    escalation_matrix_json TEXT NOT NULL DEFAULT '[]', -- Array of {stage, trigger_delay_mins, escalate_to_role, channel, cooldown_mins}
    verification_required INTEGER NOT NULL DEFAULT 0,  -- 1 if independent verification is mandated
    allowed_resolution_codes_json TEXT NOT NULL DEFAULT '[]', -- Permitted resolution codes
    effective_from TIMESTAMP,
    effective_to TIMESTAMP,
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, policy_key, version)
);

CREATE INDEX IF NOT EXISTS idx_sla_policies_lookup ON sla_policies(
    organization_id, category, status, policy_key
);

-- 2. Operational SLA Policy Versions (Immutable Historical Auditing)
CREATE TABLE IF NOT EXISTS sla_policy_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES sla_policies(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    change_reason TEXT,
    authored_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(policy_id, version)
);

CREATE INDEX IF NOT EXISTS idx_sla_policy_vers ON sla_policy_versions(policy_id, version);

-- 3. Canonical Workflow Exceptions & Work Items
CREATE TABLE IF NOT EXISTS workflow_exceptions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    policy_id TEXT NOT NULL REFERENCES sla_policies(id),
    policy_version INTEGER NOT NULL DEFAULT 1,
    category TEXT NOT NULL CHECK (
        category IN ('administrative', 'follow_up', 'intake_gap', 'inventory', 'integration', 'governance', 'clinical_review')
    ),
    source_entity TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    source_event_id TEXT,
    deduplication_key TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    factual_reason TEXT NOT NULL,
    safe_summary TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (
        priority IN ('LOW', 'NORMAL', 'HIGH', 'URGENT')
    ) DEFAULT 'NORMAL',
    status TEXT NOT NULL CHECK (
        status IN ('OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'WAITING', 'RESOLVED', 'VERIFIED', 'DISMISSED', 'REOPENED')
    ) DEFAULT 'OPEN',
    assigned_role TEXT NOT NULL,
    assigned_user_id TEXT REFERENCES users(id),
    started_at TIMESTAMP NOT NULL,
    due_at TIMESTAMP NOT NULL,
    breached_at TIMESTAMP,
    acknowledged_by TEXT REFERENCES users(id),
    acknowledged_at TIMESTAMP,
    resolved_by TEXT REFERENCES users(id),
    resolved_at TIMESTAMP,
    resolution_code TEXT,
    resolution_notes TEXT,
    verified_by TEXT REFERENCES users(id),
    verified_at TIMESTAMP,
    verification_notes TEXT,
    dismissed_by TEXT REFERENCES users(id),
    dismissed_at TIMESTAMP,
    dismissal_reason TEXT,
    reopened_by TEXT REFERENCES users(id),
    reopened_at TIMESTAMP,
    reopen_reason TEXT,
    total_paused_duration_mins INTEGER NOT NULL DEFAULT 0,
    current_escalation_stage INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wf_exc_queue ON workflow_exceptions(
    organization_id, facility_id, status, category, due_at
);
CREATE INDEX IF NOT EXISTS idx_wf_exc_owner ON workflow_exceptions(
    organization_id, assigned_user_id, status
);
CREATE INDEX IF NOT EXISTS idx_wf_exc_source ON workflow_exceptions(
    source_entity, source_entity_id
);

-- 4. Exception Pause / Resume Intervals Ledger
CREATE TABLE IF NOT EXISTS sla_pause_intervals (
    id TEXT PRIMARY KEY,
    exception_id TEXT NOT NULL REFERENCES workflow_exceptions(id) ON DELETE CASCADE,
    pause_reason_code TEXT NOT NULL,
    pause_notes TEXT,
    paused_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    paused_by TEXT NOT NULL REFERENCES users(id),
    resumed_at TIMESTAMP,
    resumed_by TEXT REFERENCES users(id),
    duration_mins INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sla_pause_exc ON sla_pause_intervals(exception_id, paused_at);

-- 5. Multi-Stage Escalation Execution Ledger
CREATE TABLE IF NOT EXISTS sla_escalation_events (
    id TEXT PRIMARY KEY,
    exception_id TEXT NOT NULL REFERENCES workflow_exceptions(id) ON DELETE CASCADE,
    policy_id TEXT NOT NULL REFERENCES sla_policies(id),
    stage INTEGER NOT NULL,
    target_role TEXT NOT NULL,
    channel TEXT NOT NULL,
    recipient_ref TEXT,
    notification_message_safe TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('QUEUED', 'DISPATCHED', 'FAILED', 'SUPPRESSED')
    ) DEFAULT 'QUEUED',
    dispatched_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exception_id, stage)
);

CREATE INDEX IF NOT EXISTS idx_sla_esc_exc ON sla_escalation_events(exception_id, stage);

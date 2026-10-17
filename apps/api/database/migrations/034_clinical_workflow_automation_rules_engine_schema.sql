-- Migration 034: Clinical Workflow Automation, Rules Engine & Task Orchestration Schema
-- Phase 35 for ZAYVORA MATAB OS
-- Enforces deterministic schema validation, versioned rule lifecycles, action classification,
-- human approval gates, execution outbox, and idempotent action attempts.

-- 1. Master Governed Workflow Rules Registry
CREATE TABLE IF NOT EXISTS workflow_rules (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    rule_key TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    description TEXT,
    event_type TEXT NOT NULL, -- e.g. 'APPOINTMENT_STATUS_CHANGED', 'FOLLOW_UP_TASK_DUE', 'QUEUE_WAITING_STALL', 'MISSING_ADMIN_INFO', 'INVENTORY_THRESHOLD_BREACH', 'INTEGRATION_JOB_FAILED'
    event_schema_version TEXT NOT NULL DEFAULT '1.0.0',
    conditions_json TEXT NOT NULL DEFAULT '[]', -- Array of {field, operator, value}
    actions_json TEXT NOT NULL DEFAULT '[]',     -- Array of {type, category, parameters, approval_policy}
    action_category TEXT NOT NULL CHECK (
        action_category IN ('routine_administrative', 'communication', 'sensitive_administrative', 'clinical_review_only')
    ),
    priority INTEGER NOT NULL DEFAULT 100,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (
        status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'ACTIVE', 'PAUSED', 'RETIRED')
    ) DEFAULT 'DRAFT',
    owner_role TEXT NOT NULL DEFAULT 'CLINIC_ADMIN',
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    rate_limit_per_hour INTEGER NOT NULL DEFAULT 100,
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, rule_key, version)
);

CREATE INDEX IF NOT EXISTS idx_wf_rules_lookup ON workflow_rules(
    organization_id, event_type, status, priority ASC
);

-- 2. Workflow Rule Versions (Immutable Historical Snapshots & Test Validation Evidence)
CREATE TABLE IF NOT EXISTS workflow_rule_versions (
    id TEXT PRIMARY KEY,
    rule_id TEXT NOT NULL REFERENCES workflow_rules(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    change_summary TEXT,
    validation_evidence_json TEXT, -- Record of dry-run test results and validation proof
    authored_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rule_id, version)
);

CREATE INDEX IF NOT EXISTS idx_wf_rule_vers ON workflow_rule_versions(rule_id, version);

-- 3. Ingested Workflow Events (Durable Processable Intake Envelope)
CREATE TABLE IF NOT EXISTS automation_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    event_source TEXT NOT NULL, -- 'appointments', 'queue_tokens', 'follow_up_tasks', 'inventory_batches', 'integration_jobs'
    source_entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    correlation_id TEXT,
    causation_id TEXT, -- Prevent circular workflow loops
    status TEXT NOT NULL CHECK (
        status IN ('RECEIVED', 'EVALUATED', 'NO_MATCH', 'PROCESSED', 'FAILED', 'QUARANTINED')
    ) DEFAULT 'RECEIVED',
    quarantine_reason TEXT,
    occurred_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auto_events_queue ON automation_events(
    organization_id, status, event_type, occurred_at
);
CREATE INDEX IF NOT EXISTS idx_auto_events_source ON automation_events(
    event_source, source_entity_id
);

-- 4. Planned Workflow Actions & Human Approval Gates
CREATE TABLE IF NOT EXISTS workflow_planned_actions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    event_id TEXT NOT NULL REFERENCES automation_events(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL REFERENCES workflow_rules(id),
    rule_version INTEGER NOT NULL,
    action_type TEXT NOT NULL, -- e.g. 'CREATE_ADMIN_TASK', 'ENQUEUE_PATIENT_REMINDER', 'ESCALATE_QUEUE_STALL', 'CREATE_STOCK_REVIEW_TASK', 'REQUEST_CLINICAL_REVIEW'
    action_category TEXT NOT NULL CHECK (
        action_category IN ('routine_administrative', 'communication', 'sensitive_administrative', 'clinical_review_only')
    ),
    target_entity TEXT NOT NULL,
    target_id TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    payload_hash TEXT NOT NULL, -- SHA-256 fingerprint of exact proposed action payload for approval locking
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (
        status IN ('PLANNED', 'AWAITING_APPROVAL', 'APPROVED', 'REJECTED', 'QUEUED', 'RUNNING', 'SUCCEEDED', 'RETRY_SCHEDULED', 'NEEDS_REVIEW', 'CANCELLED')
    ) DEFAULT 'PLANNED',
    approval_required INTEGER NOT NULL DEFAULT 0,
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    rejection_reason TEXT,
    review_notes TEXT,
    attempts_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    next_retry_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wf_actions_status ON workflow_planned_actions(
    organization_id, status, next_retry_at
);
CREATE INDEX IF NOT EXISTS idx_wf_actions_approval ON workflow_planned_actions(
    organization_id, status, approval_required
);

-- 5. Action Execution Attempts Ledger (Auditable Attempt Trace)
CREATE TABLE IF NOT EXISTS workflow_action_attempts (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES workflow_planned_actions(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('SUCCESS', 'TRANSIENT_FAILURE', 'PERMANENT_FAILURE', 'UNCERTAIN_OUTCOME', 'CONSENT_DENIED', 'RECONCILED')
    ),
    result_json TEXT,
    error_message TEXT,
    duration_ms INTEGER,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wf_attempts_action ON workflow_action_attempts(
    action_id, attempt_number
);

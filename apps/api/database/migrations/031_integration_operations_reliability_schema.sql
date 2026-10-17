-- Migration 031: Enterprise Integration Monitoring, API Reliability, Queue Management & Interoperability Operations Schema
-- Phase 32 for ZAYVORA MATAB OS
-- Strict non-negotiables enforced:
-- 1. Never fabricate operational status (uptime, progress, external delivery receipts).
-- 2. Request accepted != work completed (HTTP 202 is not clinical/business completion).
-- 3. Idempotency for all side effects (retries must not duplicate clinical entities).
-- 4. outcome_unknown is a first-class state requiring reconciliation before non-idempotent retry.
-- 5. Retry only within bounded policy; no blind infinite loops.
-- 6. Dead-letter items require structured reason, ownership, and safe remediation paths.
-- 7. Zero PHI in telemetry, metrics, queue lag, and routine operational logs.
-- 8. Recheck consent and authorization prior to queued execution or retry.

-- 1. Integration Jobs Master Ledger (Universal 20-State Machine)
CREATE TABLE IF NOT EXISTS integration_jobs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id),
    operation_id TEXT NOT NULL,
    operation_type TEXT NOT NULL CHECK (operation_type IN (
        'FHIR_BUNDLE_EXPORT',
        'ABDM_CARE_CONTEXT_LINK',
        'ABDM_HEALTH_DATA_TRANSFER',
        'LIS_ORDER_DISPATCH',
        'LIS_RESULT_PULL',
        'EXTERNAL_WEBHOOK_NOTIFY',
        'DOCUMENT_GENERATION',
        'PRESCRIPTION_TRANSMIT'
    )),
    connector_id TEXT REFERENCES integration_connectors(id),
    environment TEXT NOT NULL DEFAULT 'SANDBOX' CHECK (environment IN (
        'DEVELOPMENT', 'SANDBOX', 'PRODUCTION'
    )),
    source_entity_id TEXT NOT NULL,
    source_entity_version INTEGER NOT NULL DEFAULT 1,
    payload_manifest_hash TEXT NOT NULL,
    payload_ref TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    trace_id TEXT,
    consent_ref TEXT,
    job_state TEXT NOT NULL DEFAULT 'created' CHECK (job_state IN (
        'created',
        'queued',
        'eligible_for_processing',
        'running',
        'waiting_for_external_response',
        'waiting_for_callback',
        'retry_scheduled',
        'blocked_by_authorization',
        'blocked_by_consent',
        'blocked_by_validation',
        'paused_for_reconciliation',
        'outcome_unknown',
        'partial',
        'completed',
        'failed_non_retryable',
        'dead_lettered',
        'cancel_requested',
        'cancelled',
        'expired',
        'manual_review_required'
    )),
    priority_class TEXT NOT NULL DEFAULT 'ROUTINE' CHECK (priority_class IN (
        'STAT_CRITICAL', 'URGENT', 'ROUTINE', 'BULK_BATCH'
    )),
    attempts_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    timeout_seconds INTEGER NOT NULL DEFAULT 30,
    retry_budget INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMP,
    completed_at TIMESTAMP,
    expired_at TIMESTAMP,
    owner_team TEXT NOT NULL DEFAULT 'INTEGRATIONS_ENG',
    incident_ref TEXT,
    result_summary_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_integration_jobs_org_state ON integration_jobs(organization_id, job_state);
CREATE INDEX IF NOT EXISTS idx_integration_jobs_op_conn ON integration_jobs(operation_type, connector_id);
CREATE INDEX IF NOT EXISTS idx_integration_jobs_idemp ON integration_jobs(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_integration_jobs_correl ON integration_jobs(correlation_id);

-- 2. Granular Attempt Execution Ledger
CREATE TABLE IF NOT EXISTS integration_attempts (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES integration_jobs(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    idempotency_key TEXT NOT NULL,
    sanitized_result_code TEXT,
    retry_classification TEXT CHECK (retry_classification IN (
        'RETRYABLE_NETWORK',
        'RETRYABLE_RATE_LIMIT',
        'RETRYABLE_5XX',
        'NON_RETRYABLE_AUTH',
        'NON_RETRYABLE_VALIDATION',
        'NON_RETRYABLE_4XX',
        'UNKNOWN_TIMEOUT'
    )),
    actual_provider_tx_id TEXT,
    status TEXT NOT NULL DEFAULT 'started' CHECK (status IN (
        'started', 'response_received', 'timeout', 'failed', 'unknown', 'completed'
    )),
    error_sanitized TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_integration_attempts_job ON integration_attempts(job_id, attempt_number);
CREATE INDEX IF NOT EXISTS idx_integration_attempts_status ON integration_attempts(status);

-- 3. Inbound Callback & Webhook Deduplication Inbox
CREATE TABLE IF NOT EXISTS integration_inbox_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    connector_id TEXT REFERENCES integration_connectors(id),
    external_msg_id TEXT NOT NULL,
    authenticated_source TEXT NOT NULL,
    signature_verified INTEGER NOT NULL DEFAULT 1,
    replay_prevented INTEGER NOT NULL DEFAULT 1,
    deduplication_key TEXT NOT NULL UNIQUE,
    processing_status TEXT NOT NULL DEFAULT 'RECEIVED' CHECK (processing_status IN (
        'RECEIVED', 'VERIFIED', 'PROCESSED', 'DUPLICATE_IGNORED', 'STALE_REJECTED', 'SIGNATURE_FAILED'
    )),
    linked_job_id TEXT REFERENCES integration_jobs(id),
    payload_sha256 TEXT NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_integration_inbox_dedup ON integration_inbox_events(deduplication_key);
CREATE INDEX IF NOT EXISTS idx_integration_inbox_status ON integration_inbox_events(organization_id, processing_status);

-- 4. Unknown-Outcome Reconciliation Ledger
CREATE TABLE IF NOT EXISTS integration_reconciliations (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES integration_jobs(id) ON DELETE CASCADE,
    trigger_reason TEXT NOT NULL,
    reconciliation_method TEXT NOT NULL CHECK (reconciliation_method IN (
        'STATUS_QUERY', 'PROVIDER_TX_LOOKUP', 'CALLBACK_REPLAY', 'PARTNER_RECEIPT_MATCH', 'AUTHORIZED_MANUAL_REVIEW'
    )),
    evidence_references_json TEXT NOT NULL DEFAULT '[]',
    determination TEXT NOT NULL DEFAULT 'still_unknown' CHECK (determination IN (
        'confirmed_completed', 'confirmed_not_completed', 'partially_completed', 'duplicate_confirmed', 'still_unknown', 'requires_partner_action', 'cannot_reconcile'
    )),
    is_manual INTEGER NOT NULL DEFAULT 0,
    reconciled_by TEXT REFERENCES users(id),
    decision_notes TEXT NOT NULL,
    reconciled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_integration_recon_job ON integration_reconciliations(job_id, determination);

-- 5. Dead-Letter Workbench & Remediation Table
CREATE TABLE IF NOT EXISTS dead_letter_items (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES integration_jobs(id) ON DELETE CASCADE,
    last_attempt_id TEXT REFERENCES integration_attempts(id),
    reason_code TEXT NOT NULL CHECK (reason_code IN (
        'RETRY_BUDGET_EXHAUSTED',
        'PERMANENT_BUSINESS_REJECTION',
        'MALFORMED_PAYLOAD',
        'UNSUPPORTED_PROFILE',
        'MISSING_CREDENTIALS',
        'CONSENT_REVOKED',
        'CALLBACK_AUTH_FAILED',
        'UNRESOLVED_OUTCOME',
        'SCHEMA_MAPPING_ERROR',
        'OPERATOR_INTERVENTION_REQUIRED'
    )),
    sanitized_diagnostics TEXT NOT NULL,
    safe_replay_eligible INTEGER NOT NULL DEFAULT 0,
    owner_team TEXT NOT NULL DEFAULT 'INTEGRATIONS_ENG',
    incident_id TEXT,
    resolution_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (resolution_status IN (
        'PENDING', 'REPLAYED', 'CANCELLED', 'ACKNOWLEDGED_TERMINATED', 'MANUAL_REMEDIATED'
    )),
    resolved_by TEXT REFERENCES users(id),
    resolution_rationale TEXT,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dead_letter_job ON dead_letter_items(job_id, resolution_status);
CREATE INDEX IF NOT EXISTS idx_dead_letter_reason ON dead_letter_items(reason_code);

-- 6. Multi-Dimensional Connector Health Snapshots
CREATE TABLE IF NOT EXISTS connector_health_snapshots (
    id TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL REFERENCES integration_connectors(id) ON DELETE CASCADE,
    probe_type TEXT NOT NULL CHECK (probe_type IN (
        'LIVENESS', 'CONNECTIVITY', 'AUTH_VERIFY', 'CREDENTIAL_EXPIRY', 'QUEUE_LAG', 'BUSINESS_PING'
    )),
    probe_result TEXT NOT NULL CHECK (probe_result IN (
        'HEALTHY', 'DEGRADED', 'UNAVAILABLE', 'NOT_SUPPORTED', 'NOT_CHECKED', 'CREDENTIALS_INVALID'
    )),
    latency_ms INTEGER,
    queue_lag_count INTEGER NOT NULL DEFAULT 0,
    oldest_msg_age_seconds INTEGER NOT NULL DEFAULT 0,
    active_spec_version TEXT,
    limitation_notes TEXT,
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conn_health_snap ON connector_health_snapshots(connector_id, probe_type, snapshot_at);

-- 7. Fault Isolation Circuit Breakers
CREATE TABLE IF NOT EXISTS integration_circuit_breakers (
    id TEXT PRIMARY KEY,
    connector_id TEXT NOT NULL UNIQUE REFERENCES integration_connectors(id) ON DELETE CASCADE,
    state TEXT NOT NULL DEFAULT 'CLOSED' CHECK (state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    failure_threshold INTEGER NOT NULL DEFAULT 5,
    recovery_time_seconds INTEGER NOT NULL DEFAULT 60,
    last_state_change_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_failure_at TIMESTAMP,
    last_probe_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_circuit_breakers_state ON integration_circuit_breakers(connector_id, state);

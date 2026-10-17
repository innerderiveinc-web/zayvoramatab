-- Migration 051: Enterprise Performance, Scalability & Capacity Governance
-- Phase 54 of ZAYVORA MATAB OS
-- Implements benchmark scenarios, run metrics, slow-query registry, capacity profiles,
-- dependency circuit-breaker states, and SHA-256 tamper-evident performance governance ledger.

CREATE TABLE IF NOT EXISTS perf_benchmark_scenarios (
    scenario_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- READ_HEAVY, WRITE_INTENSIVE, MIXED_CLINICAL, SEARCH_INDEX, BACKGROUND_QUEUE
    target_endpoint TEXT NOT NULL,
    http_method TEXT NOT NULL DEFAULT 'GET',
    target_p95_ms REAL NOT NULL DEFAULT 200.0,
    target_p99_ms REAL NOT NULL DEFAULT 500.0,
    max_error_rate_pct REAL NOT NULL DEFAULT 1.0,
    concurrency_level INTEGER NOT NULL DEFAULT 10,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, DEPRECATED, INACTIVE
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS perf_benchmark_runs (
    run_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES perf_benchmark_scenarios(scenario_id) ON DELETE CASCADE,
    environment TEXT NOT NULL DEFAULT 'ISOLATED_STAGING', -- LOCAL_DEV, ISOLATED_STAGING, PRE_PROD
    sample_size INTEGER NOT NULL,
    duration_seconds REAL NOT NULL,
    concurrency INTEGER NOT NULL,
    throughput_rps REAL NOT NULL,
    p50_latency_ms REAL NOT NULL,
    p95_latency_ms REAL NOT NULL,
    p99_latency_ms REAL NOT NULL,
    min_latency_ms REAL NOT NULL,
    max_latency_ms REAL NOT NULL,
    error_count INTEGER NOT NULL DEFAULT 0,
    error_rate_pct REAL NOT NULL DEFAULT 0.0,
    cpu_utilization_pct REAL,
    memory_mb REAL,
    sla_status TEXT NOT NULL, -- PASS, BREACH, WARNING
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS perf_slow_query_registry (
    query_fingerprint TEXT PRIMARY KEY,
    query_template TEXT NOT NULL,
    execution_count INTEGER NOT NULL DEFAULT 1,
    avg_duration_ms REAL NOT NULL,
    max_duration_ms REAL NOT NULL,
    last_seen_at TEXT NOT NULL,
    recommended_index TEXT,
    status TEXT NOT NULL DEFAULT 'TRIAGED', -- TRIAGED, INDEX_APPLIED, RESOLVED, IGNORED
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS perf_capacity_profiles (
    profile_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    assumed_concurrent_practitioners INTEGER NOT NULL,
    assumed_daily_consultations INTEGER NOT NULL,
    measured_headroom_pct REAL NOT NULL,
    bottleneck_resource TEXT NOT NULL, -- DATABASE_WRITE_LOCK, CPU_PASSWORD_HASH, MEMORY_CACHE, EXTERNAL_ABDM_LATENCY
    recommended_max_concurrency INTEGER NOT NULL,
    graceful_degradation_policy_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS perf_circuit_breaker_states (
    dependency_id TEXT PRIMARY KEY, -- DEP-ABDM, DEP-TWILIO, DEP-RAZORPAY, DEP-EXTERNAL-LIS
    state TEXT NOT NULL DEFAULT 'CLOSED', -- CLOSED, HALF_OPEN, OPEN
    failure_threshold INTEGER NOT NULL DEFAULT 5,
    failure_count INTEGER NOT NULL DEFAULT 0,
    recovery_timeout_sec INTEGER NOT NULL DEFAULT 30,
    last_failure_at TEXT,
    last_state_change_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fallback_action TEXT NOT NULL DEFAULT 'QUEUE_ASYNCHRONOUS' -- QUEUE_ASYNCHRONOUS, FAIL_SAFE_DEGRADE, REJECT_IMMEDIATE
);

CREATE TABLE IF NOT EXISTS perf_governance_audit_ledger (
    ledger_id TEXT PRIMARY KEY,
    sequence_number INTEGER NOT NULL,
    event_type TEXT NOT NULL, -- SCENARIO_CREATED, BENCHMARK_EXECUTED, SLOW_QUERY_LOGGED, CAPACITY_PROFILE_UPDATED, CIRCUIT_BREAKER_TRIPPED
    actor_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_perf_runs_scenario ON perf_benchmark_runs(scenario_id, created_at);
CREATE INDEX IF NOT EXISTS idx_perf_slow_query_dur ON perf_slow_query_registry(avg_duration_ms DESC);
CREATE INDEX IF NOT EXISTS idx_perf_cb_state ON perf_circuit_breaker_states(state);
CREATE INDEX IF NOT EXISTS idx_perf_ledger_seq ON perf_governance_audit_ledger(sequence_number);

-- Seed Baseline Scenarios
INSERT OR IGNORE INTO perf_benchmark_scenarios (
    scenario_id, name, category, target_endpoint, http_method,
    target_p95_ms, target_p99_ms, max_error_rate_pct, concurrency_level, status
) VALUES 
(
    'SCN-PATIENT-SEARCH', 'Patient Lookup by MRN or Soundex Phone', 'SEARCH_INDEX',
    '/api/v1/patients', 'GET', 120.0, 300.0, 0.5, 15, 'ACTIVE'
),
(
    'SCN-ENCOUNTER-CREATE', 'Clinical Outpatient Consultation Intake', 'WRITE_INTENSIVE',
    '/api/v1/encounters', 'POST', 180.0, 450.0, 0.5, 10, 'ACTIVE'
),
(
    'SCN-RX-SAFETY-PREFLIGHT', 'Classical Posology Ceilings & Mudabbar Toxicity Preflight', 'MIXED_CLINICAL',
    '/api/v1/safety/preflight', 'POST', 150.0, 400.0, 0.1, 12, 'ACTIVE'
),
(
    'SCN-KNOWLEDGE-QUERY', 'Classical Unani Mizaj / Botanical Monograph Retrieval', 'READ_HEAVY',
    '/api/v1/knowledge/search', 'GET', 90.0, 250.0, 0.5, 20, 'ACTIVE'
),
(
    'SCN-QUEUE-DISPATCH', 'Background Async Event & Interop Task Ingestion', 'BACKGROUND_QUEUE',
    '/api/v1/integration-ops/queues/enqueue', 'POST', 100.0, 300.0, 1.0, 25, 'ACTIVE'
);

-- Seed Baseline Capacity Profile
INSERT OR IGNORE INTO perf_capacity_profiles (
    profile_id, name, assumed_concurrent_practitioners, assumed_daily_consultations,
    measured_headroom_pct, bottleneck_resource, recommended_max_concurrency, graceful_degradation_policy_json
) VALUES (
    'CAP-OPD-SINGLE-CLINIC', 'Single-Facility Community Matab OPD Baseline', 5, 250, 42.5,
    'DATABASE_WRITE_LOCK', 30,
    '{"queue_degradation_threshold_ms": 500, "drop_analytics_rollups_on_load": true, "enable_read_stale_glossary": true}'
);

-- Seed Baseline Circuit Breakers
INSERT OR IGNORE INTO perf_circuit_breaker_states (
    dependency_id, state, failure_threshold, failure_count, recovery_timeout_sec, fallback_action
) VALUES 
('DEP-ABDM', 'CLOSED', 5, 0, 45, 'QUEUE_ASYNCHRONOUS'),
('DEP-TWILIO', 'CLOSED', 5, 0, 30, 'QUEUE_ASYNCHRONOUS'),
('DEP-RAZORPAY', 'CLOSED', 3, 0, 60, 'FAIL_SAFE_DEGRADE');

-- Seed Genesis Audit Block for Performance Governance Ledger
INSERT OR IGNORE INTO perf_governance_audit_ledger (
    ledger_id, sequence_number, event_type, actor_id, tenant_id, target_id,
    payload_json, prev_hash, record_hash, created_at
) VALUES (
    'PGL-GENESIS-0001', 1, 'GENESIS_BLOCK', 'SYSTEM', 'T-SYSTEM', 'SYSTEM_ROOT',
    '{"message": "Genesis Block of Enterprise Performance, Scalability & Capacity Ledger"}',
    '0000000000000000000000000000000000000000000000000000000000000000',
    '19be4b719fe1ffa007788aed8dfd8c69740f6eb2e22e2f52af4b6798a88f3f8e',
    '2026-10-15T00:00:00.000000Z'
);

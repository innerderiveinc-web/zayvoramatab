-- ============================================================================
-- Migration 038: Production Observability, Incident Response, SLO Governance
-- & Reliability Operations Engine
-- Phase 39 for ZAYVORA MATAB OS
-- ============================================================================

-- 1. Service Catalog & Dependency Registry
CREATE TABLE IF NOT EXISTS observability_service_catalog (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    service_key VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    description TEXT,
    owner_role VARCHAR(64) NOT NULL,
    tier VARCHAR(32) NOT NULL DEFAULT 'tier_2_business_critical',
    upstream_dependencies_json TEXT NOT NULL DEFAULT '[]',
    downstream_dependencies_json TEXT NOT NULL DEFAULT '[]',
    health_status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY',
    last_probed_at DATETIME,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, service_key)
);

CREATE INDEX IF NOT EXISTS idx_obs_svc_org ON observability_service_catalog(organization_id, service_key);
CREATE INDEX IF NOT EXISTS idx_obs_svc_status ON observability_service_catalog(health_status);

-- 2. Low-Cardinality Telemetry Metrics Time-Series
CREATE TABLE IF NOT EXISTS observability_telemetry_metrics (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    metric_name VARCHAR(128) NOT NULL,
    route_or_subsystem VARCHAR(128) NOT NULL,
    outcome_class VARCHAR(32) NOT NULL,
    metric_value REAL NOT NULL,
    unit VARCHAR(32) NOT NULL DEFAULT 'count',
    measurement_type VARCHAR(32) NOT NULL DEFAULT 'MEASURED',
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_obs_metrics_lookup ON observability_telemetry_metrics(organization_id, metric_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_obs_metrics_route ON observability_telemetry_metrics(route_or_subsystem, outcome_class);

-- 3. Actionable Alert Definitions & Runbooks
CREATE TABLE IF NOT EXISTS observability_alert_definitions (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    alert_key VARCHAR(64) NOT NULL,
    title VARCHAR(128) NOT NULL,
    description TEXT NOT NULL,
    service_key VARCHAR(64) NOT NULL,
    severity VARCHAR(32) NOT NULL DEFAULT 'P3_MEDIUM',
    metric_name VARCHAR(128) NOT NULL,
    condition_operator VARCHAR(16) NOT NULL DEFAULT 'GT',
    threshold_value REAL NOT NULL,
    evaluation_window_seconds INTEGER NOT NULL DEFAULT 300,
    owner_role VARCHAR(64) NOT NULL,
    runbook_markdown TEXT NOT NULL,
    notification_channels_json TEXT NOT NULL DEFAULT '["ops_dashboard"]',
    dedup_fingerprint_rule VARCHAR(128) NOT NULL DEFAULT 'alert_key+service_key',
    is_enabled INTEGER NOT NULL DEFAULT 1,
    version VARCHAR(16) NOT NULL DEFAULT '1.0.0',
    created_by VARCHAR(64) NOT NULL,
    updated_by VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, alert_key)
);

CREATE INDEX IF NOT EXISTS idx_obs_alert_def_org ON observability_alert_definitions(organization_id, alert_key);
CREATE INDEX IF NOT EXISTS idx_obs_alert_def_svc ON observability_alert_definitions(service_key);

-- 4. Firing & Resolved Alert Instances
CREATE TABLE IF NOT EXISTS observability_alert_instances (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    alert_definition_id VARCHAR(64) NOT NULL,
    alert_key VARCHAR(64) NOT NULL,
    fingerprint VARCHAR(128) NOT NULL,
    severity VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'FIRING',
    current_value REAL NOT NULL,
    threshold_value REAL NOT NULL,
    firing_evidence_json TEXT NOT NULL DEFAULT '{}',
    resolution_evidence_json TEXT NOT NULL DEFAULT '{}',
    incident_id VARCHAR(64),
    fired_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at DATETIME,
    acknowledged_by VARCHAR(64),
    resolved_at DATETIME,
    resolved_by VARCHAR(64),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alert_definition_id) REFERENCES observability_alert_definitions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_obs_alert_inst_status ON observability_alert_instances(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_obs_alert_inst_fp ON observability_alert_instances(fingerprint);

-- 5. Governed Service-Level Objectives (SLO) Registry
CREATE TABLE IF NOT EXISTS observability_slo_registry (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    slo_key VARCHAR(64) NOT NULL,
    name VARCHAR(128) NOT NULL,
    service_key VARCHAR(64) NOT NULL,
    sli_description TEXT NOT NULL,
    target_ratio REAL NOT NULL DEFAULT 0.99,
    window_days INTEGER NOT NULL DEFAULT 30,
    owner_role VARCHAR(64) NOT NULL,
    approval_status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    approved_by VARCHAR(64),
    approved_at DATETIME,
    total_events INTEGER NOT NULL DEFAULT 0,
    good_events INTEGER NOT NULL DEFAULT 0,
    error_budget_total REAL NOT NULL DEFAULT 0.0,
    error_budget_remaining REAL NOT NULL DEFAULT 0.0,
    burn_rate REAL NOT NULL DEFAULT 0.0,
    compliance_status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY',
    known_gaps_notes TEXT,
    version VARCHAR(16) NOT NULL DEFAULT '1.0.0',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, slo_key)
);

CREATE INDEX IF NOT EXISTS idx_obs_slo_org ON observability_slo_registry(organization_id, slo_key);
CREATE INDEX IF NOT EXISTS idx_obs_slo_svc ON observability_slo_registry(service_key);

-- 6. Incident Management Lifecycle
CREATE TABLE IF NOT EXISTS observability_incidents (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    incident_code VARCHAR(64) NOT NULL,
    title VARCHAR(256) NOT NULL,
    summary TEXT NOT NULL,
    service_key VARCHAR(64) NOT NULL,
    environment VARCHAR(32) NOT NULL DEFAULT 'staging',
    severity VARCHAR(32) NOT NULL DEFAULT 'P3_MEDIUM',
    status VARCHAR(32) NOT NULL DEFAULT 'detected',
    commander_user_id VARCHAR(64) NOT NULL,
    commander_role VARCHAR(64) NOT NULL,
    responders_json TEXT NOT NULL DEFAULT '[]',
    impact_scope TEXT NOT NULL,
    source_alert_id VARCHAR(64),
    runbook_url_or_key VARCHAR(128),
    mitigation_summary TEXT,
    root_cause_summary TEXT,
    resolution_evidence_json TEXT NOT NULL DEFAULT '{}',
    detected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at DATETIME,
    mitigated_at DATETIME,
    resolved_at DATETIME,
    closed_at DATETIME,
    created_by VARCHAR(64) NOT NULL,
    updated_by VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_id, incident_code)
);

CREATE INDEX IF NOT EXISTS idx_obs_inc_org_status ON observability_incidents(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_obs_inc_sev ON observability_incidents(severity);

-- 7. Immutable Incident Timeline Events
CREATE TABLE IF NOT EXISTS observability_incident_timeline (
    id VARCHAR(64) PRIMARY KEY,
    incident_id VARCHAR(64) NOT NULL,
    actor_id VARCHAR(64) NOT NULL,
    actor_role VARCHAR(64) NOT NULL,
    entry_type VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES observability_incidents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_obs_inc_tl_inc ON observability_incident_timeline(incident_id, created_at);

-- 8. Allowlisted Remediation Actions & Guardrails
CREATE TABLE IF NOT EXISTS observability_remediation_actions (
    id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    incident_id VARCHAR(64),
    action_type VARCHAR(64) NOT NULL,
    target_resource VARCHAR(128) NOT NULL,
    environment VARCHAR(32) NOT NULL DEFAULT 'staging',
    status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED',
    precondition_check_passed INTEGER NOT NULL DEFAULT 1,
    post_verification_passed INTEGER NOT NULL DEFAULT 1,
    side_effect_summary TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 2,
    cooldown_seconds INTEGER NOT NULL DEFAULT 300,
    executed_by VARCHAR(64) NOT NULL,
    error_message TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_obs_rem_act ON observability_remediation_actions(organization_id, action_type, status);

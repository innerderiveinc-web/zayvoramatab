-- Migration 050: Enterprise API Integration Certification, Contract Testing & Developer Governance
-- Phase 52 of ZAYVORA MATAB OS
-- Implements contract-first API catalog, Developer API keys, idempotency cache,
-- webhook subscription/delivery with SSRF shield, inbound webhook receipt verification,
-- integration certification lifecycle, and SHA-256 tamper-evident governance ledger.

CREATE TABLE IF NOT EXISTS api_integrations_catalog (
    integration_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL, -- PATIENT_PORTAL_APP, INTERNAL_SERVICE, CLINICAL_CDS, COMMUNICATIONS_SMS, PAYMENTS_GATEWAY, NATIONAL_INTEROP_ABDM, STANDARDS_FHIR, CLINICAL_EVENT_OUTBOUND
    direction TEXT NOT NULL, -- INBOUND, OUTBOUND, BIDIRECTIONAL
    provider_name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    base_url_env_key TEXT NOT NULL,
    auth_type TEXT NOT NULL, -- API_KEY, BEARER_JWT, MUTUAL_TLS, HMAC_SIGNATURE
    data_classification TEXT NOT NULL, -- RESTRICTED_PHI, CONFIDENTIAL_FINANCIAL, INTERNAL_OPERATIONAL
    rate_limit_rpm INTEGER NOT NULL DEFAULT 60,
    timeout_ms INTEGER NOT NULL DEFAULT 5000,
    retry_policy_json TEXT NOT NULL DEFAULT '{"max_retries": 3, "backoff_factor": 2.0, "jitter": true}',
    idempotency_required INTEGER NOT NULL DEFAULT 1,
    certification_level TEXT NOT NULL DEFAULT 'UNVERIFIED', -- CONTRACT_DEFINED, MOCK_TESTED, CONTRACT_TESTED, SANDBOX_VERIFIED, PRODUCTION_SMOKE_VERIFIED, UNVERIFIED
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, DEPRECATED, INACTIVE
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_contract_definitions (
    contract_id TEXT PRIMARY KEY,
    integration_id TEXT NOT NULL REFERENCES api_integrations_catalog(integration_id) ON DELETE CASCADE,
    endpoint_path TEXT NOT NULL,
    http_method TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    summary TEXT NOT NULL,
    required_scopes TEXT NOT NULL DEFAULT '[]', -- JSON array of strings
    request_schema_json TEXT NOT NULL DEFAULT '{}',
    response_schema_json TEXT NOT NULL DEFAULT '{}',
    error_schema_json TEXT NOT NULL DEFAULT '{}',
    is_idempotent INTEGER NOT NULL DEFAULT 0,
    is_deprecated INTEGER NOT NULL DEFAULT 0,
    deprecation_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(integration_id, http_method, endpoint_path, version)
);

CREATE TABLE IF NOT EXISTS api_developer_keys (
    key_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    facility_id TEXT,
    client_name TEXT NOT NULL,
    key_prefix TEXT NOT NULL, -- e.g. ak_live_ or ak_test_
    key_hash TEXT NOT NULL, -- SHA-256 of API key token
    environment TEXT NOT NULL DEFAULT 'SANDBOX', -- SANDBOX, PRODUCTION
    allowed_scopes TEXT NOT NULL DEFAULT '[]', -- JSON array of permissions/scopes
    rate_limit_rpm INTEGER NOT NULL DEFAULT 120,
    allowed_ips_json TEXT, -- Optional JSON array of permitted CIDRs/IPs
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, ROTATING, REVOKED, EXPIRED
    expires_at TEXT,
    last_used_at TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_idempotency_store (
    idempotency_key TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    endpoint_path TEXT NOT NULL,
    request_hash TEXT NOT NULL, -- SHA-256 of request payload
    status_code INTEGER NOT NULL,
    response_body_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, idempotency_key, endpoint_path)
);

CREATE TABLE IF NOT EXISTS api_webhook_subscriptions (
    subscription_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    target_url TEXT NOT NULL,
    event_types TEXT NOT NULL, -- JSON array of events, e.g. ["encounter.finalized", "prescription.signed"]
    secret_hash TEXT NOT NULL, -- SHA-256 of webhook signing secret
    is_active INTEGER NOT NULL DEFAULT 1,
    ssrf_validated INTEGER NOT NULL DEFAULT 1,
    failure_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_webhook_deliveries (
    delivery_id TEXT PRIMARY KEY,
    subscription_id TEXT NOT NULL REFERENCES api_webhook_subscriptions(subscription_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    request_payload_json TEXT NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    delivery_status TEXT NOT NULL, -- DELIVERED, RETRYING, DEAD_LETTERED, BLOCKED_SSRF
    error_message TEXT,
    next_retry_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_inbound_webhook_receipts (
    receipt_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider TEXT NOT NULL, -- TWILIO, RAZORPAY, ABDM, GENERIC_HMAC
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    signature_header TEXT NOT NULL,
    timestamp_header TEXT,
    verification_status TEXT NOT NULL, -- VERIFIED, INVALID_SIGNATURE, EXPIRED_TIMESTAMP, REPLAY_DUPLICATE
    payload_hash TEXT NOT NULL,
    received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider, event_id)
);

CREATE TABLE IF NOT EXISTS api_integration_certifications (
    certification_id TEXT PRIMARY KEY,
    integration_id TEXT NOT NULL REFERENCES api_integrations_catalog(integration_id) ON DELETE CASCADE,
    certification_level TEXT NOT NULL, -- CONTRACT_DEFINED, MOCK_TESTED, CONTRACT_TESTED, SANDBOX_VERIFIED, PRODUCTION_SMOKE_VERIFIED, UNVERIFIED
    evidence_summary TEXT NOT NULL,
    test_suite_run_id TEXT,
    certified_by TEXT NOT NULL,
    certified_by_role TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, REVOKED, EXPIRED
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_developer_governance_ledger (
    ledger_id TEXT PRIMARY KEY,
    sequence_number INTEGER NOT NULL,
    event_type TEXT NOT NULL, -- INTEGRATION_REGISTERED, CONTRACT_UPDATED, KEY_GENERATED, KEY_REVOKED, WEBHOOK_DELIVERED, INBOUND_WEBHOOK_VERIFIED, INTEGRATION_CERTIFIED
    actor_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    record_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for high-throughput query performance
CREATE INDEX IF NOT EXISTS idx_api_integrations_tenant ON api_integrations_catalog(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_contract_lookup ON api_contract_definitions(http_method, endpoint_path);
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_developer_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_developer_keys(tenant_id);
CREATE INDEX IF NOT EXISTS idx_api_idempotency_lookup ON api_idempotency_store(tenant_id, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_api_webhook_deliv_sub ON api_webhook_deliveries(subscription_id, delivery_status);
CREATE INDEX IF NOT EXISTS idx_api_inbound_lookup ON api_inbound_webhook_receipts(provider, event_id);
CREATE INDEX IF NOT EXISTS idx_api_cert_integration ON api_integration_certifications(integration_id, status);
CREATE INDEX IF NOT EXISTS idx_api_ledger_seq ON api_developer_governance_ledger(sequence_number);

-- Seed Baseline Integrations
INSERT OR IGNORE INTO api_integrations_catalog (
    integration_id, tenant_id, title, category, direction, provider_name, version,
    base_url_env_key, auth_type, data_classification, rate_limit_rpm, timeout_ms,
    retry_policy_json, idempotency_required, certification_level, status
) VALUES 
(
    'INT-CORE-CLINICAL', 'T-SYSTEM', 'Core Matab Clinical OS API', 'INTERNAL_SERVICE', 'BIDIRECTIONAL',
    'ZAYVORA Internal', 'v1', 'MATAB_API_BASE_URL', 'BEARER_JWT', 'RESTRICTED_PHI',
    1200, 3000, '{"max_retries": 1, "backoff_factor": 1.0, "jitter": false}', 1, 'CONTRACT_TESTED', 'ACTIVE'
),
(
    'INT-INTERNAL-CDS', 'T-SYSTEM', 'Clinical Decision Support Orchestrator', 'CLINICAL_CDS', 'INBOUND',
    'ZAYVORA CDS Engine', 'v1', 'MATAB_CDS_BASE_URL', 'BEARER_JWT', 'RESTRICTED_PHI',
    300, 4000, '{"max_retries": 2, "backoff_factor": 1.5, "jitter": true}', 1, 'CONTRACT_TESTED', 'ACTIVE'
),
(
    'INT-FHIR-R4', 'T-SYSTEM', 'FHIR R4 Diagnostic & Encounters Exchange', 'STANDARDS_FHIR', 'BIDIRECTIONAL',
    'HL7 FHIR R4 Specification', '4.0.1', 'MATAB_FHIR_BASE_URL', 'MUTUAL_TLS', 'RESTRICTED_PHI',
    300, 5000, '{"max_retries": 3, "backoff_factor": 2.0, "jitter": true}', 1, 'CONTRACT_TESTED', 'ACTIVE'
),
(
    'INT-ABDM-GW', 'T-SYSTEM', 'ABDM Ayushman Bharat Digital Mission Gateway', 'NATIONAL_INTEROP_ABDM', 'BIDIRECTIONAL',
    'National Health Authority (NHA)', 'v0.5', 'ABDM_GATEWAY_URL', 'BEARER_JWT', 'RESTRICTED_PHI',
    120, 8000, '{"max_retries": 3, "backoff_factor": 2.0, "jitter": true}', 1, 'MOCK_TESTED', 'ACTIVE'
),
(
    'INT-TWILIO-SMS', 'T-SYSTEM', 'Twilio SMS & Patient Notification Gateway', 'COMMUNICATIONS_SMS', 'OUTBOUND',
    'Twilio Inc.', '2010-04-01', 'TWILIO_API_BASE_URL', 'API_KEY', 'INTERNAL_OPERATIONAL',
    240, 5000, '{"max_retries": 3, "backoff_factor": 2.0, "jitter": true}', 1, 'MOCK_TESTED', 'ACTIVE'
),
(
    'INT-RAZORPAY-PAY', 'T-SYSTEM', 'Razorpay Payment & Invoicing Webhooks', 'PAYMENTS_GATEWAY', 'BIDIRECTIONAL',
    'Razorpay Software Pvt Ltd', 'v1', 'RAZORPAY_API_BASE_URL', 'HMAC_SIGNATURE', 'CONFIDENTIAL_FINANCIAL',
    180, 5000, '{"max_retries": 3, "backoff_factor": 2.0, "jitter": true}', 1, 'MOCK_TESTED', 'ACTIVE'
),
(
    'INT-OUTBOUND-WH', 'T-SYSTEM', 'Tenant Outbound Clinical Event Webhooks', 'CLINICAL_EVENT_OUTBOUND', 'OUTBOUND',
    'Tenant Secure Consumer', 'v1', 'TENANT_WEBHOOK_URL', 'HMAC_SIGNATURE', 'RESTRICTED_PHI',
    120, 5000, '{"max_retries": 5, "backoff_factor": 2.0, "jitter": true}', 1, 'CONTRACT_TESTED', 'ACTIVE'
);

-- Seed Baseline Contract Definitions for Core Clinical API
INSERT OR IGNORE INTO api_contract_definitions (
    contract_id, integration_id, endpoint_path, http_method, version, summary,
    required_scopes, request_schema_json, response_schema_json, error_schema_json,
    is_idempotent, is_deprecated
) VALUES 
(
    'CTR-ENC-CREATE', 'INT-CORE-CLINICAL', '/api/v1/encounters', 'POST', 'v1',
    'Create or initialize an outpatient clinical consultation encounter',
    '["encounters:write"]',
    '{"type": "object", "required": ["patient_id", "facility_id", "encounter_type"], "properties": {"patient_id": {"type": "string"}, "facility_id": {"type": "string"}, "encounter_type": {"type": "string", "enum": ["OPD", "TELEMEDICINE", "FOLLOWUP"]}}}',
    '{"type": "object", "required": ["encounter_id", "status"], "properties": {"encounter_id": {"type": "string"}, "status": {"type": "string"}}}',
    '{"type": "object", "required": ["error", "code", "message"], "properties": {"error": {"type": "boolean"}, "code": {"type": "string"}, "message": {"type": "string"}}}',
    1, 0
),
(
    'CTR-RX-SIGN', 'INT-CORE-CLINICAL', '/api/v1/prescriptions/{id}/sign', 'POST', 'v1',
    'Electronically sign a Tabib prescription with clinician PIN',
    '["prescriptions:sign"]',
    '{"type": "object", "required": ["clinician_pin"], "properties": {"clinician_pin": {"type": "string", "pattern": "^[0-9]{4,8}$"}}}',
    '{"type": "object", "required": ["prescription_id", "status", "signed_at"], "properties": {"prescription_id": {"type": "string"}, "status": {"type": "string"}, "signed_at": {"type": "string"}}}',
    '{"type": "object", "required": ["error", "code", "message"], "properties": {"error": {"type": "boolean"}, "code": {"type": "string"}, "message": {"type": "string"}}}',
    1, 0
);

-- Seed Genesis Audit Block for Developer Governance Ledger
INSERT OR IGNORE INTO api_developer_governance_ledger (
    ledger_id, sequence_number, event_type, actor_id, tenant_id, target_id,
    payload_json, prev_hash, record_hash, created_at
) VALUES (
    'DGL-GENESIS-0001', 1, 'GENESIS_BLOCK', 'SYSTEM', 'T-SYSTEM', 'SYSTEM_ROOT',
    '{"message": "Genesis Block of Enterprise API Developer Governance Ledger"}',
    '0000000000000000000000000000000000000000000000000000000000000000',
    'bb83f3e2fe7e2dc6cd545be113afae895114a7d87e8e30e322242c68bef38c1c',
    '2026-10-15T00:00:00.000000Z'
);


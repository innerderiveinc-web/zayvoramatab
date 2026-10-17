-- Migration 030: Enterprise Interoperability, FHIR APIs, ABDM Integration & External-System Data Exchange
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Interoperability Specification & Profile Registry
CREATE TABLE IF NOT EXISTS interop_specification_registry (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    spec_code TEXT NOT NULL,
    spec_name TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    package_id TEXT NOT NULL,
    pinned_version TEXT NOT NULL,
    release_date TEXT,
    sha256_checksum TEXT NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'active' CHECK (validation_status IN ('active', 'superseded', 'deprecated', 'draft')),
    spec_metadata_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, spec_code, pinned_version)
);

CREATE INDEX IF NOT EXISTS idx_interop_spec_org_status ON interop_specification_registry(organization_id, validation_status);

-- 2. Terminology Mappings with Semantic Preservation
CREATE TABLE IF NOT EXISTS interop_terminology_mappings (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    concept_domain TEXT NOT NULL CHECK (concept_domain IN (
        'UNANI_MIZAJ', 'UNANI_AKHLAT', 'UNANI_TASHKHEES', 'UNANI_NUSKHA',
        'LAB_OBSERVATION', 'MODERN_DIAGNOSIS', 'VITAL_SIGN'
    )),
    internal_code TEXT NOT NULL,
    internal_display TEXT NOT NULL,
    internal_system_uri TEXT NOT NULL DEFAULT 'https://zayvora.internal/unani/canonical',
    target_system_uri TEXT NOT NULL,
    target_code TEXT,
    target_display TEXT,
    mapping_state TEXT NOT NULL DEFAULT 'no_safe_mapping' CHECK (mapping_state IN (
        'exact_reviewed', 'broader_than', 'narrower_than', 'no_safe_mapping'
    )),
    clinical_rationale TEXT,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, internal_code, target_system_uri)
);

CREATE INDEX IF NOT EXISTS idx_interop_term_org_domain ON interop_terminology_mappings(organization_id, concept_domain, mapping_state);

-- 3. ABDM Consent Requests (M3 HIU Flow)
CREATE TABLE IF NOT EXISTS abdm_consent_requests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    requester_id TEXT NOT NULL REFERENCES users(id),
    abha_number TEXT,
    abha_address TEXT NOT NULL,
    purpose_code TEXT NOT NULL DEFAULT 'CAREMGT' CHECK (purpose_code IN (
        'CAREMGT', 'BTG', 'PUBHLTH', 'HPCONSMT', 'DSRCH'
    )),
    hi_types_json TEXT NOT NULL DEFAULT '["OPConsultation","Prescription","DiagnosticReport","DischargeSummary"]',
    date_range_from TIMESTAMP NOT NULL,
    date_range_to TIMESTAMP NOT NULL,
    expiry_timestamp TIMESTAMP NOT NULL,
    gateway_request_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'REQUESTED' CHECK (status IN (
        'REQUESTED', 'GRANTED', 'DENIED', 'EXPIRED', 'REVOKED'
    )),
    response_details_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_abdm_req_org_patient ON abdm_consent_requests(organization_id, patient_id, status);

-- 4. ABDM Granted Consent Artefacts (M2 HIP / M3 HIU Scope Gatekeeper)
CREATE TABLE IF NOT EXISTS abdm_consent_artefacts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    consent_request_id TEXT REFERENCES abdm_consent_requests(id) ON DELETE SET NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    artefact_id TEXT NOT NULL UNIQUE,
    cm_id TEXT NOT NULL DEFAULT 'sbx',
    consent_details_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'GRANTED' CHECK (status IN ('GRANTED', 'REVOKED', 'EXPIRED')),
    signature_verified INTEGER NOT NULL DEFAULT 1,
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    revocation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_abdm_artefact_org_patient ON abdm_consent_artefacts(organization_id, patient_id, status);

-- 5. Inbound Clinical Record Reconciliation Queue (Zero Silent Overwrite)
CREATE TABLE IF NOT EXISTS inbound_record_reconciliations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id),
    patient_id TEXT NOT NULL REFERENCES patients(id),
    encounter_id TEXT REFERENCES encounters(id),
    source_system TEXT NOT NULL,
    source_connector_id TEXT,
    source_identifier TEXT,
    source_consent_id TEXT,
    resource_type TEXT NOT NULL CHECK (resource_type IN (
        'Condition', 'Observation', 'MedicationRequest', 'DiagnosticReport', 'DocumentReference', 'Bundle'
    )),
    raw_payload_json TEXT NOT NULL,
    extracted_summary_json TEXT NOT NULL,
    reconciliation_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (reconciliation_status IN (
        'PENDING_REVIEW', 'ACCEPTED', 'REJECTED', 'CONTRADICTION_FLAGGED', 'ATTACHED_AS_DOCUMENT'
    )),
    reconciliation_decision_notes TEXT,
    reconciled_by TEXT REFERENCES users(id),
    reconciled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_inbound_rec_org_status ON inbound_record_reconciliations(organization_id, patient_id, reconciliation_status);

-- 6. Durable Integration Outbox (Idempotent & Replay-Safe Delivery)
CREATE TABLE IF NOT EXISTS interop_transfer_outbox (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id),
    job_type TEXT NOT NULL CHECK (job_type IN (
        'FHIR_DOCUMENT_EXPORT', 'ABDM_NOTIFY_CARE_CONTEXT', 'ABDM_DATA_PUSH', 'LIS_ORDER_DISPATCH', 'EXTERNAL_WEBHOOK'
    )),
    destination_endpoint TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    header_metadata_json TEXT NOT NULL DEFAULT '{}',
    delivery_status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (delivery_status IN (
        'QUEUED', 'SENDING', 'DELIVERED', 'FAILED_RETRYABLE', 'DEAD_LETTER'
    )),
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    next_attempt_at TIMESTAMP,
    delivered_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_interop_outbox_org_status ON interop_transfer_outbox(organization_id, delivery_status);

-- 7. Inbound Webhook & Replay Protection Ledger
CREATE TABLE IF NOT EXISTS interop_webhook_verifications (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    source_system TEXT NOT NULL,
    request_id TEXT NOT NULL UNIQUE,
    timestamp_header TEXT NOT NULL,
    signature_header TEXT,
    signature_valid INTEGER NOT NULL DEFAULT 1,
    is_replay_prevented INTEGER NOT NULL DEFAULT 1,
    event_type TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    processing_status TEXT NOT NULL DEFAULT 'VERIFIED' CHECK (processing_status IN (
        'VERIFIED', 'PROCESSED', 'REJECTED_STALE', 'REJECTED_SIGNATURE', 'REJECTED_DUPLICATE'
    )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_interop_webhook_org_source ON interop_webhook_verifications(organization_id, source_system, processing_status);

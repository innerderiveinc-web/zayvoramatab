-- Migration 028: Clinical Audit, Accountability, Compliance Evidence & Tamper-Evident Event Ledger Schema
-- Phase 29 for ZAYVORA MATAB OS
-- Strict non-negotiables enforced:
-- 1. Never fabricate audit events or verification results
-- 2. Audit actual outcomes, not attempted UI clicks (attempt vs committed result distinct)
-- 3. No silent editing or deletion of audit history (corrections appended as annotations)
-- 4. Cryptographic tamper evidence: SHA-256 hash chaining over canonical event representations
-- 5. Separate clinical records from audit ledger; preserve exact entity versions and actors
-- 6. No secrets or full patient chart narratives in audit metadata (data minimization)
-- 7. Fail closed for consequential actions when audit commit cannot be secured

-- 1. Audit Event Policy Registry
CREATE TABLE IF NOT EXISTS audit_event_policy_registry (
    id TEXT PRIMARY KEY,
    event_code TEXT NOT NULL UNIQUE,
    event_family TEXT NOT NULL,
    description TEXT NOT NULL,
    required_metadata_fields_json TEXT NOT NULL DEFAULT '[]',
    requires_diff_hash INTEGER NOT NULL DEFAULT 0,
    gates_consequential_action INTEGER NOT NULL DEFAULT 0,
    access_classification TEXT NOT NULL DEFAULT 'RESTRICTED_AUDIT',
    authorized_reviewer_roles_json TEXT NOT NULL DEFAULT '["READ_ONLY_AUDITOR", "ORG_ADMIN"]',
    retention_policy_ref TEXT NOT NULL DEFAULT 'CLINICAL_STANDARD_7YR',
    failure_handling TEXT NOT NULL DEFAULT 'BLOCK_ACTION' CHECK (failure_handling IN (
        'BLOCK_ACTION',
        'DURABLE_OUTBOX',
        'APPROVED_DEFERRED_CAPTURE',
        'NON_BLOCKING_WITH_ALERT'
    )),
    schema_version TEXT NOT NULL DEFAULT '1.0',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_pol_family ON audit_event_policy_registry(event_family, is_active);
CREATE INDEX IF NOT EXISTS idx_audit_pol_code ON audit_event_policy_registry(event_code);

-- 2. Clinical Ledger Events (Cryptographically Chained, Append-Only)
CREATE TABLE IF NOT EXISTS clinical_ledger_events (
    event_id TEXT PRIMARY KEY,
    event_schema_version TEXT NOT NULL DEFAULT '1.0',
    event_code TEXT NOT NULL,
    event_family TEXT NOT NULL,
    event_time TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    time_source TEXT NOT NULL DEFAULT 'SERVER_NTP_UTC',
    actor_principal_id TEXT,
    actor_type TEXT NOT NULL CHECK (actor_type IN (
        'human',
        'service',
        'scheduled_job',
        'integration',
        'anonymous',
        'unknown'
    )),
    acting_role TEXT,
    on_behalf_of_principal_id TEXT,
    tenant_id TEXT NOT NULL,
    clinic_id TEXT NOT NULL,
    branch_id TEXT,
    session_ref TEXT,
    request_id TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    target_entity_version TEXT,
    target_record_hash TEXT,
    action TEXT NOT NULL,
    action_intent TEXT NOT NULL,
    result_state TEXT NOT NULL CHECK (result_state IN (
        'succeeded',
        'failed',
        'denied',
        'partial',
        'unknown',
        'blocked'
    )),
    reason_code TEXT,
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    previous_event_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    ledger_sequence INTEGER NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clin_ledger_seq ON clinical_ledger_events(ledger_sequence);
CREATE INDEX IF NOT EXISTS idx_clin_ledger_target ON clinical_ledger_events(target_entity_type, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_clin_ledger_actor ON clinical_ledger_events(actor_principal_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_clin_ledger_req ON clinical_ledger_events(request_id);

-- 3. Audit Annotations & Dispute Ledger (No Silent Edits)
CREATE TABLE IF NOT EXISTS audit_annotations (
    id TEXT PRIMARY KEY,
    target_event_id TEXT NOT NULL REFERENCES clinical_ledger_events(event_id) ON DELETE CASCADE,
    annotation_type TEXT NOT NULL CHECK (annotation_type IN (
        'CORRECTION_REQUESTED',
        'CORRECTION_REVIEWED',
        'ANNOTATION_ADDED',
        'EVENT_DISPUTED',
        'CORRECTION_ACCEPTED',
        'CORRECTION_REJECTED',
        'INTEGRITY_EXCEPTION_OPENED',
        'INTEGRITY_EXCEPTION_RESOLVED'
    )),
    actor_id TEXT NOT NULL REFERENCES users(id),
    rationale TEXT NOT NULL,
    supporting_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_annot_event ON audit_annotations(target_event_id);

-- 4. Audit Integrity Checkpoints (Verification Runs & Root Hashes)
CREATE TABLE IF NOT EXISTS audit_integrity_checkpoints (
    id TEXT PRIMARY KEY,
    checkpoint_type TEXT NOT NULL CHECK (checkpoint_type IN (
        'SCHEDULED_SWEEP',
        'TRANSACTIONAL_CHECK',
        'MANUAL_VERIFICATION',
        'COMPLIANCE_EXPORT_AUDIT'
    )),
    checked_scope TEXT NOT NULL,
    start_sequence INTEGER NOT NULL,
    end_sequence INTEGER NOT NULL,
    total_events_checked INTEGER NOT NULL,
    root_hash TEXT NOT NULL,
    verification_result TEXT NOT NULL CHECK (verification_result IN (
        'passed_for_checked_scope',
        'failed_integrity_mismatch',
        'missing_event_suspected',
        'sequence_gap_detected',
        'checkpoint_unavailable',
        'partial_verification',
        'verification_error'
    )),
    mismatch_details_json TEXT NOT NULL DEFAULT '[]',
    verified_by TEXT NOT NULL REFERENCES users(id),
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_chk_scope ON audit_integrity_checkpoints(checked_scope, verification_result);

-- 5. Governed Retention Policies
CREATE TABLE IF NOT EXISTS audit_retention_policies (
    id TEXT PRIMARY KEY,
    policy_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    event_family TEXT NOT NULL,
    retention_period_days INTEGER NOT NULL,
    governing_legal_source TEXT NOT NULL,
    archival_method TEXT NOT NULL DEFAULT 'IMMUTABLE_WORM_SNAPSHOT',
    is_active INTEGER NOT NULL DEFAULT 1,
    approved_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ret_pol_family ON audit_retention_policies(event_family);

-- 6. Legal Holds (Suspending Deletion / Archival)
CREATE TABLE IF NOT EXISTS audit_legal_holds (
    id TEXT PRIMARY KEY,
    hold_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    scope_filter_json TEXT NOT NULL,
    reason TEXT NOT NULL,
    placed_by TEXT NOT NULL REFERENCES users(id),
    placed_at TEXT NOT NULL,
    released_at TEXT,
    released_by TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RELEASED')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_legal_holds_status ON audit_legal_holds(status);

-- 7. Audit Evidence Exports (Authorized Compliance Dossiers)
CREATE TABLE IF NOT EXISTS audit_evidence_exports (
    id TEXT PRIMARY KEY,
    export_number TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    total_events_exported INTEGER NOT NULL,
    export_manifest_hash TEXT NOT NULL,
    verification_checkpoint_id TEXT REFERENCES audit_integrity_checkpoints(id),
    requested_by TEXT NOT NULL REFERENCES users(id),
    authorized_by TEXT REFERENCES users(id),
    export_artifact_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_exp_num ON audit_evidence_exports(export_number);

-- 8. Seed Standard Audit Event Policies
INSERT OR IGNORE INTO audit_event_policy_registry (
    id, event_code, event_family, description, required_metadata_fields_json,
    requires_diff_hash, gates_consequential_action, access_classification,
    failure_handling, schema_version, is_active
) VALUES 
(
    'pol-presc-sign',
    'PRESCRIPTION_SIGN',
    'prescription_lifecycle',
    'Cryptographically signed electronic prescription order by licensed clinician',
    '["prescription_id", "patient_id", "items_count", "preflight_result", "signer_pin_verified"]',
    1,
    1,
    'RESTRICTED_AUDIT',
    'BLOCK_ACTION',
    '1.0',
    1
),
(
    'pol-safety-override',
    'SAFETY_OVERRIDE',
    'safety_override',
    'Documented clinical override of a safety firewall warning or rule alert',
    '["rule_id", "rule_stable_key", "override_rationale", "clinician_credential"]',
    0,
    1,
    'RESTRICTED_AUDIT',
    'BLOCK_ACTION',
    '1.0',
    1
),
(
    'pol-break-glass',
    'BREAK_GLASS_ACCESS',
    'break_glass_access',
    'Emergency break-glass access to sensitive patient clinical record',
    '["patient_id", "emergency_reason", "duration_minutes"]',
    0,
    1,
    'SECURITY_CRITICAL',
    'BLOCK_ACTION',
    '1.0',
    1
),
(
    'pol-release-deploy',
    'RELEASE_DEPLOYMENT',
    'release_deployment',
    'Deployment and runtime activation of a governed clinical knowledge or rule release',
    '["release_id", "release_tag", "manifest_hash", "environment"]',
    1,
    1,
    'GOVERNANCE_AUDIT',
    'BLOCK_ACTION',
    '1.0',
    1
),
(
    'pol-data-export',
    'DATA_EXPORT',
    'data_export',
    'Bulk or granular patient or clinical data export execution',
    '["export_purpose", "records_count", "destination_type"]',
    0,
    1,
    'RESTRICTED_AUDIT',
    'BLOCK_ACTION',
    '1.0',
    1
);

-- 9. Seed Standard Retention Policies
INSERT OR IGNORE INTO audit_retention_policies (
    id, policy_code, title, event_family, retention_period_days, governing_legal_source
) VALUES
(
    'ret-pol-clin-7yr',
    'CLINICAL_STANDARD_7YR',
    'Clinical Encounter & Prescription Audit 7-Year Retention',
    'clinical_record_change',
    2555,
    'National Clinical Records Retention Guidelines'
),
(
    'ret-pol-sec-3yr',
    'SECURITY_AUDIT_3YR',
    'Authentication & Access Security 3-Year Retention',
    'authentication',
    1095,
    'Cybersecurity & Identity Governance Standards'
),
(
    'ret-pol-safety-10yr',
    'SAFETY_SURVEILLANCE_10YR',
    'Pharmacovigilance & Safety Surveillance 10-Year Retention',
    'pharmacovigilance',
    3650,
    'National Pharmacovigilance Programme Statutory Rule'
);

-- Migration 046: Enterprise Threat Modeling, Abuse-Case Analysis & Secure SDLC Governance Schema
-- Phase 47: ZAYVORA MATAB OS

-- 1. Threat Models Subsystem Registry
CREATE TABLE IF NOT EXISTS threat_models_registry (
    id TEXT PRIMARY KEY,
    model_code TEXT NOT NULL UNIQUE, -- e.g. TM-CLINICAL-CDS-001, TM-PATIENT-ID-001
    title TEXT NOT NULL,
    subsystem_scope TEXT NOT NULL, -- CLINICAL_CDS_AND_PRESCRIPTIONS, PATIENT_IDENTITY_AND_REGISTRY, UNANI_KAVS_AND_RAG, INTEROPERABILITY_ABDM_FHIR, CONFIG_AND_SECRETS, DATA_LIFECYCLE_AND_RETENTION, IDENTITY_AND_PAM, CLINIC_OPERATIONS_AND_BILLING, SECURITY_POSTURE_AND_VULNS
    repository_revision TEXT NOT NULL DEFAULT 'HEAD',
    deployment_version TEXT NOT NULL DEFAULT 'v1.0.0',
    owner_role TEXT NOT NULL DEFAULT 'Principal Security Architect',
    security_reviewer_id TEXT,
    clinical_reviewer_id TEXT,
    privacy_reviewer_id TEXT,
    lifecycle_state TEXT NOT NULL DEFAULT 'draft', -- draft, discovery, review_required, mitigation_in_progress, residual_risk_review, approved_for_scope, stale, retired
    assumptions_json TEXT, -- JSON array of strings
    exclusions_json TEXT,  -- JSON array of strings
    dependencies_json TEXT, -- JSON array of strings
    is_stale INTEGER NOT NULL DEFAULT 0, -- 1 = Stale, requires re-review
    stale_reason TEXT,
    last_reviewed_at TEXT,
    next_review_due_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tm_scope ON threat_models_registry(subsystem_scope);
CREATE INDEX IF NOT EXISTS idx_tm_state ON threat_models_registry(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_tm_stale ON threat_models_registry(is_stale);

-- 2. Trust Boundaries & Data Flow Inventory
CREATE TABLE IF NOT EXISTS threat_trust_boundaries (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL REFERENCES threat_models_registry(id) ON DELETE CASCADE,
    boundary_name TEXT NOT NULL,
    source_actor_or_component TEXT NOT NULL,
    destination_component TEXT NOT NULL,
    data_classification TEXT NOT NULL DEFAULT 'TIER_2_PHI', -- TIER_1_CREDENTIALS, TIER_2_PHI, TIER_3_KNOWLEDGE, TIER_4_AUDIT, TIER_5_OPERATIONAL
    protocol_or_interface TEXT NOT NULL DEFAULT 'HTTPS/JSON_REST',
    auth_mechanism TEXT NOT NULL DEFAULT 'BEARER_TOKEN_RBAC',
    encryption_status TEXT NOT NULL DEFAULT 'TLS_1_3_IN_TRANSIT',
    evidence_status TEXT NOT NULL DEFAULT 'verified_in_code', -- verified_in_code, verified_in_config, verified_in_test, runtime_verified, inferred, unknown
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tb_model ON threat_trust_boundaries(model_id);

-- 3. Abuse Cases & Threat Scenario Catalogue (STRIDE + Clinical Safety Hazard)
CREATE TABLE IF NOT EXISTS threat_abuse_cases (
    id TEXT PRIMARY KEY,
    model_id TEXT NOT NULL REFERENCES threat_models_registry(id) ON DELETE CASCADE,
    threat_code TEXT NOT NULL UNIQUE, -- e.g. TAC-CDS-001, TAC-ID-001
    title TEXT NOT NULL,
    methodology TEXT NOT NULL DEFAULT 'STRIDE_PLUS_CLINICAL_HAZARD',
    threat_class TEXT NOT NULL, -- SPOOFING, TAMPERING, REPUDIATION, INFO_DISCLOSURE, DENIAL_OF_SERVICE, ELEVATION_OF_PRIVILEGE, CLINICAL_HAZARD, SUPPLY_CHAIN
    actor_type TEXT NOT NULL DEFAULT 'AUTHENTICATED_USER', -- EXTERNAL_ATTACKER, AUTHENTICATED_USER, MALICIOUS_INSIDER, COMPROMISED_SERVICE, DISCREDITED_CLINICIAN, UNPRIVILEGED_STAFF
    target_asset TEXT NOT NULL,
    trust_boundary_id TEXT REFERENCES threat_trust_boundaries(id),
    attack_path_summary TEXT NOT NULL, -- Safe non-operational exploit summary
    clinical_safety_hazard TEXT NOT NULL DEFAULT 'NONE', -- DIRECT_HARM_PRESCRIBING_ERROR, DIAGNOSTIC_TAMPERING_MISROUTING, CONSENT_OR_PRIVACY_VIOLATION, OPERATIONAL_DISRUPTION, NONE
    severity TEXT NOT NULL DEFAULT 'HIGH', -- CRITICAL, HIGH, MEDIUM, LOW, NEGLIGIBLE
    lifecycle_status TEXT NOT NULL DEFAULT 'identified', -- identified, needs_validation, mitigation_planned, mitigation_implemented, verification_pending, verified_mitigated, residual_risk_review, accepted_by_authorized_owner, blocked, closed_with_evidence
    accountable_owner_role TEXT NOT NULL DEFAULT 'Security Lead',
    mitigation_due_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tac_model ON threat_abuse_cases(model_id);
CREATE INDEX IF NOT EXISTS idx_tac_status ON threat_abuse_cases(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_tac_severity ON threat_abuse_cases(severity);

-- 4. Testable Controls & Verification Requirements
CREATE TABLE IF NOT EXISTS threat_testable_controls (
    id TEXT PRIMARY KEY,
    threat_id TEXT NOT NULL REFERENCES threat_abuse_cases(id) ON DELETE CASCADE,
    control_code TEXT NOT NULL UNIQUE, -- e.g. CTL-CDS-001, CTL-ID-001
    title TEXT NOT NULL,
    control_type TEXT NOT NULL DEFAULT 'PREVENTIVE', -- PREVENTIVE, DETECTIVE, RECOVERY
    enforcement_code_path TEXT NOT NULL, -- e.g. apps.api.domains.cds_orchestrator.CDSOrchestratorEngine.sign_encounter
    test_suite_reference TEXT NOT NULL, -- e.g. tests.unit.test_cds_orchestrator.TestCDSOrchestrator.test_admin_cannot_sign_prescription
    verification_status TEXT NOT NULL DEFAULT 'VERIFIED_IN_TEST', -- PLANNED, IMPLEMENTED, VERIFIED_IN_TEST, FAILED_VERIFICATION, STALE
    last_verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ttc_threat ON threat_testable_controls(threat_id);
CREATE INDEX IF NOT EXISTS idx_ttc_status ON threat_testable_controls(verification_status);

-- 5. Governed Residual Risk Decisions Ledger
CREATE TABLE IF NOT EXISTS threat_residual_risk_decisions (
    id TEXT PRIMARY KEY,
    threat_id TEXT NOT NULL REFERENCES threat_abuse_cases(id) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    business_rationale TEXT NOT NULL,
    compensating_controls TEXT NOT NULL,
    authorized_owner_role TEXT NOT NULL, -- Chief Information Security Officer, Clinical Safety Officer, Privacy Officer
    authorized_by_principal_id TEXT NOT NULL,
    authorized_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL, -- strictly <= 90 days from authorization
    residual_risk_tier TEXT NOT NULL DEFAULT 'LOW', -- CRITICAL, HIGH, MEDIUM, LOW, NEGLIGIBLE
    status TEXT NOT NULL DEFAULT 'APPROVED', -- DRAFT, APPROVED, EXPIRED, REVOKED
    clinical_hazard_reviewed INTEGER NOT NULL DEFAULT 1, -- 1 = explicitly evaluated and acknowledged
    review_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trr_threat ON threat_residual_risk_decisions(threat_id);
CREATE INDEX IF NOT EXISTS idx_trr_status ON threat_residual_risk_decisions(status);

-- 6. SDLC Change Reviews & Release Gate Evaluations
CREATE TABLE IF NOT EXISTS sdlc_change_reviews (
    id TEXT PRIMARY KEY,
    change_id TEXT NOT NULL UNIQUE, -- e.g. PR-1048, CHG-2026-001
    title TEXT NOT NULL,
    repository_revision TEXT NOT NULL DEFAULT 'HEAD',
    target_subsystem TEXT NOT NULL,
    threat_model_id TEXT REFERENCES threat_models_registry(id),
    change_classification TEXT NOT NULL DEFAULT 'STANDARD_CHANGE', -- STANDARD_CHANGE, HIGH_IMPACT_SECURITY, HIGH_IMPACT_CLINICAL, HIGH_IMPACT_PRIVACY, INFRASTRUCTURE_SECRETS
    security_review_status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED, WAIVED
    clinical_review_status TEXT NOT NULL DEFAULT 'NOT_REQUIRED', -- NOT_REQUIRED, PENDING, APPROVED, REJECTED
    privacy_review_status TEXT NOT NULL DEFAULT 'NOT_REQUIRED', -- NOT_REQUIRED, PENDING, APPROVED, REJECTED
    gate_verdict TEXT NOT NULL DEFAULT 'BLOCKED', -- PASS, BLOCKED, CONDITIONAL_PASS, STALE_MODEL, NOT_RUN
    blocking_reasons_json TEXT, -- JSON array of strings
    evaluated_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sdlc_subsystem ON sdlc_change_reviews(target_subsystem);
CREATE INDEX IF NOT EXISTS idx_sdlc_verdict ON sdlc_change_reviews(gate_verdict);

-- 7. Chained Tamper-Evident Threat & SDLC Audit Ledger
CREATE TABLE IF NOT EXISTS threat_sdlc_audit_ledger (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL, -- THREAT_MODEL_CREATED, THREAT_MODEL_STATUS_CHANGED, ABUSE_CASE_LOGGED, RISK_ACCEPTED, SDLC_GATE_EVALUATED
    severity TEXT NOT NULL DEFAULT 'INFO', -- INFO, WARNING, ERROR, CRITICAL
    actor_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action_details_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_threat_audit_actor ON threat_sdlc_audit_ledger(actor_id);
CREATE INDEX IF NOT EXISTS idx_threat_audit_type ON threat_sdlc_audit_ledger(event_type);

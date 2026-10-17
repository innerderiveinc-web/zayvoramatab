-- Migration 047: Enterprise Clinical Safety Case, Hazard Analysis & Safety Control Verification Schema
-- Phase 48: ZAYVORA MATAB OS

-- 1. Intended Use & Clinical Scope Registry
CREATE TABLE IF NOT EXISTS clinical_intended_use_registry (
    id TEXT PRIMARY KEY,
    scope_code TEXT NOT NULL UNIQUE, -- e.g. IU-PRESCRIPTION-SIGNING, IU-UNANI-MIZAJ, IU-CDS-FIREWALL, IU-PATIENT-IDENTITY
    title TEXT NOT NULL,
    intended_users_json TEXT NOT NULL, -- JSON array of strings
    clinical_purposes_json TEXT NOT NULL, -- JSON array of strings
    excluded_uses_json TEXT NOT NULL, -- JSON array of strings
    clinician_authority_level TEXT NOT NULL DEFAULT 'EXCLUSIVE_HUMAN_SIGN_OFF', -- EXCLUSIVE_HUMAN_SIGN_OFF, SUPERVISED_DOCUMENTATION
    version TEXT NOT NULL DEFAULT '1.0.0',
    effective_date TEXT NOT NULL,
    clinical_approver_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'APPROVED', -- DRAFT, APPROVED, SUPERSEDED, RETIRED
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_ciu_scope ON clinical_intended_use_registry(scope_code);
CREATE INDEX IF NOT EXISTS idx_ciu_status ON clinical_intended_use_registry(status);

-- 2. Clinical Hazard Register
CREATE TABLE IF NOT EXISTS clinical_hazard_register (
    id TEXT PRIMARY KEY,
    hazard_code TEXT NOT NULL UNIQUE, -- e.g. HAZ-RX-001, HAZ-TOX-001, HAZ-ID-001
    intended_use_id TEXT REFERENCES clinical_intended_use_registry(id),
    title TEXT NOT NULL,
    workflow_scope TEXT NOT NULL, -- PRESCRIPTION_SIGNING, UNANI_ASSESSMENT, CDS_RULE_EVALUATION, PATIENT_REGISTRY, KAVS_CITATION_RETRIEVAL, INTEGRATIONS_AND_DISPENSING
    initiating_cause TEXT NOT NULL,
    hazardous_state TEXT NOT NULL,
    clinical_consequence TEXT NOT NULL,
    affected_population TEXT NOT NULL DEFAULT 'GENERAL_OPD', -- GENERAL_OPD, PEDIATRIC, GERIATRIC, PREGNANT_LACTATING, ALLERGIC_PATIENTS
    severity_tier TEXT NOT NULL DEFAULT 'CRITICAL', -- CATASTROPHIC, CRITICAL, SERIOUS, MINOR, NEGLIGIBLE
    lifecycle_status TEXT NOT NULL DEFAULT 'draft', -- draft, clinical_review_required, mitigation_required, verification_pending, residual_risk_review, accepted_for_defined_scope, blocked, retired
    clinical_safety_lead_id TEXT NOT NULL DEFAULT 'usr-hakeem-1',
    technical_lead_id TEXT NOT NULL DEFAULT 'usr-admin-1',
    review_due_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_haz_code ON clinical_hazard_register(hazard_code);
CREATE INDEX IF NOT EXISTS idx_haz_scope ON clinical_hazard_register(workflow_scope);
CREATE INDEX IF NOT EXISTS idx_haz_status ON clinical_hazard_register(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_haz_severity ON clinical_hazard_register(severity_tier);

-- 3. Safety Requirements & Traceable Controls Catalog
CREATE TABLE IF NOT EXISTS safety_requirements_catalog (
    id TEXT PRIMARY KEY,
    hazard_id TEXT NOT NULL REFERENCES clinical_hazard_register(id) ON DELETE CASCADE,
    req_code TEXT NOT NULL UNIQUE, -- e.g. SR-RX-001, SR-TOX-001
    title TEXT NOT NULL,
    requirement_type TEXT NOT NULL DEFAULT 'PREVENTIVE', -- PREVENTIVE, DETECTIVE, MITIGATIVE
    specification_statement TEXT NOT NULL,
    enforcement_code_path TEXT NOT NULL, -- e.g. apps.api.domains.cds_orchestrator.CDSOrchestratorEngine.sign_encounter
    test_suite_reference TEXT NOT NULL, -- e.g. tests.unit.test_cds_orchestrator.TestCDSOrchestrator.test_admin_cannot_sign_prescription
    verification_status TEXT NOT NULL DEFAULT 'VERIFIED_IN_TEST', -- PLANNED, IMPLEMENTED, VERIFIED_IN_TEST, FAILED_VERIFICATION, STALE
    last_verified_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sr_hazard ON safety_requirements_catalog(hazard_id);
CREATE INDEX IF NOT EXISTS idx_sr_status ON safety_requirements_catalog(verification_status);

-- 4. Safety Control Verifications Evidence Ledger
CREATE TABLE IF NOT EXISTS safety_control_verifications (
    id TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL REFERENCES safety_requirements_catalog(id) ON DELETE CASCADE,
    test_run_timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    test_suite_name TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'ISOLATED_SYNTHETIC', -- ISOLATED_SYNTHETIC, CI_RUNNER
    execution_duration_ms INTEGER NOT NULL DEFAULT 50,
    status TEXT NOT NULL DEFAULT 'PASS', -- PASS, FAIL, BLOCKED, STALE
    evidence_summary TEXT NOT NULL,
    verified_by_actor_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_scv_req ON safety_control_verifications(requirement_id);
CREATE INDEX IF NOT EXISTS idx_scv_status ON safety_control_verifications(status);

-- 5. Clinical Safety Cases (Claim-Context-Argument-Evidence)
CREATE TABLE IF NOT EXISTS clinical_safety_cases (
    id TEXT PRIMARY KEY,
    case_code TEXT NOT NULL UNIQUE, -- e.g. CSC-PRESCRIPTION-V1
    title TEXT NOT NULL,
    workflow_scope TEXT NOT NULL, -- PRESCRIPTION_SIGNING, UNANI_ASSESSMENT, CDS_RULE_EVALUATION, PATIENT_REGISTRY, KAVS_CITATION_RETRIEVAL
    target_release_version TEXT NOT NULL DEFAULT 'v1.0.0',
    claim_statement TEXT NOT NULL,
    context_and_assumptions TEXT NOT NULL,
    argument_narrative TEXT NOT NULL,
    residual_risks_summary TEXT NOT NULL,
    exclusions_and_limitations TEXT NOT NULL,
    clinical_safety_officer_id TEXT NOT NULL,
    approval_status TEXT NOT NULL DEFAULT 'APPROVED_FOR_SCOPE', -- DRAFT, PENDING_CLINICAL_REVIEW, APPROVED_FOR_SCOPE, CONDITIONALLY_APPROVED, REJECTED, STALE
    approved_at TEXT,
    expires_at TEXT NOT NULL, -- strictly <= 180 days
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_csc_code ON clinical_safety_cases(case_code);
CREATE INDEX IF NOT EXISTS idx_csc_status ON clinical_safety_cases(approval_status);
CREATE INDEX IF NOT EXISTS idx_csc_scope ON clinical_safety_cases(workflow_scope);

-- 6. Clinical Safety Incidents & Near-Miss Loop
CREATE TABLE IF NOT EXISTS clinical_safety_incidents (
    id TEXT PRIMARY KEY,
    incident_code TEXT NOT NULL UNIQUE, -- e.g. INC-2026-001, NM-2026-001
    incident_type TEXT NOT NULL DEFAULT 'NEAR_MISS', -- NEAR_MISS, OBSERVED_DEVIATION, ALERT_FATIGUE_REPORT, UNEXPECTED_SYSTEM_HOLD
    workflow_scope TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'MEDIUM', -- CRITICAL, HIGH, MEDIUM, LOW
    sanitized_description TEXT NOT NULL, -- Strictly zero PHI
    linked_hazard_id TEXT REFERENCES clinical_hazard_register(id),
    containment_action TEXT,
    corrective_action_plan TEXT,
    corrective_action_status TEXT NOT NULL DEFAULT 'REPORTED', -- REPORTED, TRIAGED, INVESTIGATING, CORRECTIVE_ACTION_PENDING, VERIFIED_CLOSED
    reported_by_actor_id TEXT NOT NULL,
    closed_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_csi_code ON clinical_safety_incidents(incident_code);
CREATE INDEX IF NOT EXISTS idx_csi_status ON clinical_safety_incidents(corrective_action_status);
CREATE INDEX IF NOT EXISTS idx_csi_hazard ON clinical_safety_incidents(linked_hazard_id);

-- 7. Safety Release Gate Evaluations
CREATE TABLE IF NOT EXISTS safety_release_gate_evaluations (
    id TEXT PRIMARY KEY,
    evaluation_code TEXT NOT NULL UNIQUE, -- e.g. SRG-2026-001
    target_release_version TEXT NOT NULL,
    workflow_scope TEXT NOT NULL,
    safety_case_id TEXT REFERENCES clinical_safety_cases(id),
    gate_verdict TEXT NOT NULL DEFAULT 'BLOCKED', -- PASS, BLOCKED, CONDITIONAL_PASS, STALE_EVIDENCE
    evaluated_controls_count INTEGER NOT NULL DEFAULT 0,
    passed_controls_count INTEGER NOT NULL DEFAULT 0,
    blocking_reasons_json TEXT, -- JSON array of strings
    evaluated_by_actor_id TEXT NOT NULL,
    evaluated_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_srg_scope ON safety_release_gate_evaluations(workflow_scope);
CREATE INDEX IF NOT EXISTS idx_srg_verdict ON safety_release_gate_evaluations(gate_verdict);

-- 8. Chained Tamper-Evident Clinical Safety Audit Ledger
CREATE TABLE IF NOT EXISTS clinical_safety_audit_ledger (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL, -- HAZARD_CREATED, HAZARD_STATUS_CHANGED, SAFETY_REQUIREMENT_ADDED, CONTROL_VERIFIED, SAFETY_CASE_APPROVED, INCIDENT_LOGGED, RELEASE_GATE_EVALUATED
    severity TEXT NOT NULL DEFAULT 'INFO', -- INFO, WARNING, ERROR, CRITICAL
    actor_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action_details_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL,
    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_csa_actor ON clinical_safety_audit_ledger(actor_id);
CREATE INDEX IF NOT EXISTS idx_csa_type ON clinical_safety_audit_ledger(event_type);

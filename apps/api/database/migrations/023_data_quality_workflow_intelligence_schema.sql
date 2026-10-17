-- Migration 023: Clinical Workflow Intelligence, Missing-Information Detection & Data-Quality Schema
-- Phase 24: Configurable data quality rules, deterministic evaluations, granular findings, field provenance, and reconciliation decisions.

-- 1. Governed Data Quality Rule Registry
CREATE TABLE IF NOT EXISTS dq_rule_registry (
    rule_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('PRESENCE', 'VALIDITY', 'CONSISTENCY', 'FRESHNESS', 'IDENTITY', 'WORKFLOW_PREREQUISITE')),
    severity TEXT NOT NULL CHECK(severity IN ('INFO', 'WARNING', 'CRITICAL', 'BLOCKER')),
    scope_type TEXT NOT NULL CHECK(scope_type IN ('PATIENT', 'ENCOUNTER', 'ASSESSMENT', 'PRESCRIPTION')),
    field_paths_json TEXT NOT NULL DEFAULT '[]',
    rule_logic_json TEXT NOT NULL DEFAULT '{}',
    remediation_role TEXT NOT NULL CHECK(remediation_role IN ('FRONT_DESK', 'TRIAGE_NURSE', 'CLINICIAN', 'PHARMACIST', 'ADMIN')),
    is_active INTEGER NOT NULL DEFAULT 1,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dq_rules_scope ON dq_rule_registry(scope_type, is_active);
CREATE INDEX IF NOT EXISTS idx_dq_rules_severity ON dq_rule_registry(severity, is_active);

-- 2. Field Freshness Policies
CREATE TABLE IF NOT EXISTS dq_freshness_policies (
    policy_code TEXT PRIMARY KEY,
    field_name TEXT NOT NULL,
    max_age_hours INTEGER NOT NULL,
    clinical_rationale TEXT NOT NULL,
    stale_severity TEXT NOT NULL DEFAULT 'WARNING' CHECK(stale_severity IN ('INFO', 'WARNING', 'CRITICAL', 'BLOCKER')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dq_freshness_field ON dq_freshness_policies(field_name, is_active);

-- 3. Data Quality Evaluation Runs
CREATE TABLE IF NOT EXISTS dq_evaluations (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    facility_id TEXT,
    encounter_id TEXT,
    patient_id TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    target_version INTEGER NOT NULL DEFAULT 1,
    evaluation_trigger TEXT NOT NULL DEFAULT 'MANUAL',
    findings_count INTEGER NOT NULL DEFAULT 0,
    blockers_count INTEGER NOT NULL DEFAULT 0,
    evaluated_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (encounter_id) REFERENCES encounters(id)
);

CREATE INDEX IF NOT EXISTS idx_dq_evals_encounter ON dq_evaluations(encounter_id, created_at);
CREATE INDEX IF NOT EXISTS idx_dq_evals_patient ON dq_evaluations(patient_id, created_at);

-- 4. Granular Data Quality Findings
CREATE TABLE IF NOT EXISTS dq_findings (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL,
    encounter_id TEXT,
    patient_id TEXT NOT NULL,
    rule_code TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    field_path TEXT NOT NULL,
    missingness_state TEXT CHECK(missingness_state IN ('MISSING', 'UNKNOWN', 'NOT_RECORDED', 'NOT_ASSESSED', 'DECLINED_BY_PATIENT', 'NOT_APPLICABLE', 'UNAVAILABLE', NULL)),
    finding_summary TEXT NOT NULL,
    explanation TEXT NOT NULL,
    clinical_implication TEXT,
    conflicting_values_json TEXT DEFAULT '[]',
    remediation_role TEXT NOT NULL,
    remediation_status TEXT NOT NULL DEFAULT 'OPEN' CHECK(remediation_status IN ('OPEN', 'RESOLVED', 'ACKNOWLEDGED_WITH_REASON', 'DEFERRED')),
    resolution_details_json TEXT DEFAULT '{}',
    resolved_by TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (evaluation_id) REFERENCES dq_evaluations(id),
    FOREIGN KEY (rule_code) REFERENCES dq_rule_registry(rule_code)
);

CREATE INDEX IF NOT EXISTS idx_dq_findings_eval ON dq_findings(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_dq_findings_enc_status ON dq_findings(encounter_id, remediation_status, severity);
CREATE INDEX IF NOT EXISTS idx_dq_findings_pat_status ON dq_findings(patient_id, remediation_status);

-- 5. Field Provenance Tracking
CREATE TABLE IF NOT EXISTS dq_field_provenance (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_value TEXT,
    unit TEXT,
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL,
    source_stream TEXT NOT NULL CHECK(source_stream IN ('PATIENT_REPORTED', 'CLINICIAN_OBSERVED', 'DEVICE_VITAL', 'EXTERNAL_RECORD')),
    source_encounter_id TEXT,
    freshness_policy_code TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (freshness_policy_code) REFERENCES dq_freshness_policies(policy_code)
);

CREATE INDEX IF NOT EXISTS idx_dq_provenance_entity ON dq_field_provenance(entity_type, entity_id, field_name);

-- 6. Clinician Conflict Reconciliation Decisions
CREATE TABLE IF NOT EXISTS dq_reconciliation_decisions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    encounter_id TEXT,
    field_name TEXT NOT NULL,
    conflict_summary TEXT NOT NULL,
    options_evaluated_json TEXT NOT NULL DEFAULT '[]',
    selected_value TEXT,
    clinician_rationale TEXT NOT NULL,
    reconciled_by TEXT NOT NULL,
    reconciled_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (reconciled_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_dq_reconcile_pat ON dq_reconciliation_decisions(patient_id, field_name);

-- 7. Seed Governed Freshness Policies
INSERT OR IGNORE INTO dq_freshness_policies (policy_code, field_name, max_age_hours, clinical_rationale, stale_severity)
VALUES
    ('FP-VITALS-BP', 'vitals.blood_pressure', 24, 'Blood pressure changes dynamically and should be reassessed at each consultation visit.', 'WARNING'),
    ('FP-VITALS-TEMP', 'vitals.temperature', 12, 'Body temperature reflects acute inflammatory or infectious changes requiring recent observation.', 'WARNING'),
    ('FP-VITALS-PULSE', 'vitals.pulse', 12, 'Pulse rate and Nabz must represent the patient current acute circulatory status.', 'WARNING'),
    ('FP-PREGNANCY-STATUS', 'patient.pregnancy_status', 72, 'Pregnancy status critical for contraindication screening (Mudirr-e-Baul, Mushil medications).', 'CRITICAL'),
    ('FP-ALLERGY-REVIEW', 'patient.allergies', 720, 'Known allergy list should be reviewed and re-confirmed every 30 days.', 'WARNING');

-- 8. Seed Governed Data Quality Rules
INSERT OR IGNORE INTO dq_rule_registry (rule_code, name, category, severity, scope_type, field_paths_json, rule_logic_json, remediation_role)
VALUES
    ('DQ-PAT-PHONE', 'Patient Primary Phone Verification', 'PRESENCE', 'WARNING', 'PATIENT',
     '["phone"]', '{"check": "not_empty"}', 'FRONT_DESK'),

    ('DQ-PAT-DOB', 'Patient Date of Birth Presence', 'PRESENCE', 'WARNING', 'PATIENT',
     '["dob"]', '{"check": "not_empty"}', 'FRONT_DESK'),

    ('DQ-ENC-CHIEF-COMPLAINT', 'Consultation Chief Complaint Presence', 'PRESENCE', 'BLOCKER', 'ENCOUNTER',
     '["chief_complaint"]', '{"check": "not_empty"}', 'CLINICIAN'),

    ('DQ-VITALS-BP-ORDER', 'Blood Pressure Systolic/Diastolic Consistency', 'CONSISTENCY', 'CRITICAL', 'ASSESSMENT',
     '["vitals.blood_pressure_systolic", "vitals.blood_pressure_diastolic"]', '{"check": "greater_than", "lhs": "systolic", "rhs": "diastolic"}', 'TRIAGE_NURSE'),

    ('DQ-VITALS-PULSE-RANGE', 'Physiological Pulse Range Validation', 'VALIDITY', 'WARNING', 'ASSESSMENT',
     '["vitals.pulse_rate"]', '{"check": "range", "min": 30, "max": 220}', 'TRIAGE_NURSE'),

    ('DQ-VITALS-TEMP-UNIT', 'Temperature Measurement Unit Validation', 'VALIDITY', 'WARNING', 'ASSESSMENT',
     '["vitals.temperature_unit"]', '{"check": "in_list", "allowed": ["C", "F", "celsius", "fahrenheit"]}', 'TRIAGE_NURSE'),

    ('DQ-UNANI-MIZAJ-PRESENCE', 'Unani Primary Mizaj Classification Presence', 'PRESENCE', 'WARNING', 'ENCOUNTER',
     '["unani_assessment.mizaj"]', '{"check": "not_empty_if_lane_active"}', 'CLINICIAN'),

    ('DQ-RX-SIG-PRESENCE', 'Prescription Dosage & Sig Instructions Complete', 'PRESENCE', 'BLOCKER', 'PRESCRIPTION',
     '["items.instructions", "items.dosage"]', '{"check": "not_empty_for_all_items"}', 'CLINICIAN'),

    ('DQ-DUPLICATE-PATIENT-FLAG', 'Unresolved Duplicate Patient Candidates', 'IDENTITY', 'WARNING', 'PATIENT',
     '["patient_duplicate_candidates"]', '{"check": "zero_pending_candidates"}', 'FRONT_DESK'),

    ('DQ-WORKFLOW-ARRIVED-TRIAGE', 'Arrived Patient Triage Incomplete', 'WORKFLOW_PREREQUISITE', 'INFO', 'ENCOUNTER',
     '["vitals"]', '{"check": "vitals_recorded_for_arrived"}', 'TRIAGE_NURSE');

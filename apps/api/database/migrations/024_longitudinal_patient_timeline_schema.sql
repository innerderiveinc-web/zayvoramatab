-- Migration 024: Longitudinal Patient Timeline & Continuity-of-Care Schema
-- Phase 25: Canonical temporal events, stream lanes, care continuity tasks, medication status ledger, and traceable summaries.

-- 1. Canonical Patient Timeline Events Envelope
CREATE TABLE IF NOT EXISTS patient_timeline_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    facility_id TEXT,
    patient_id TEXT NOT NULL,
    encounter_id TEXT,
    stream_lane TEXT NOT NULL CHECK(stream_lane IN ('UNANI', 'MODERN', 'MEDICATION', 'LABORATORY', 'ADMINISTRATIVE', 'PATIENT_REPORTED', 'CARE_CONTINUITY')),
    event_type TEXT NOT NULL,
    event_title TEXT NOT NULL,
    event_summary TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    temporal_precision TEXT NOT NULL DEFAULT 'EXACT_TIMESTAMP' CHECK(temporal_precision IN ('YEAR', 'MONTH', 'DAY', 'EXACT_TIMESTAMP')),
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    recorded_by TEXT NOT NULL,
    source_entity_type TEXT NOT NULL,
    source_entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    clinical_significance TEXT NOT NULL DEFAULT 'ROUTINE' CHECK(clinical_significance IN ('ROUTINE', 'IMPORTANT', 'CRITICAL_EVENT')),
    is_current_status INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (encounter_id) REFERENCES encounters(id)
);

CREATE INDEX IF NOT EXISTS idx_timeline_patient_occurred ON patient_timeline_events(patient_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_stream_lane ON patient_timeline_events(patient_id, stream_lane, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_source ON patient_timeline_events(source_entity_type, source_entity_id);

-- 2. Care Continuity Tasks & Contact Attempts
CREATE TABLE IF NOT EXISTS care_continuity_tasks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    facility_id TEXT,
    patient_id TEXT NOT NULL,
    originating_encounter_id TEXT,
    task_type TEXT NOT NULL CHECK(task_type IN ('FOLLOW_UP_CALL', 'LAB_REVIEW', 'ADHERENCE_CHECK', 'OUTCOME_ASSESSMENT', 'REFERRAL_HANDOFF')),
    due_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'ESCALATED', 'CANCELLED')),
    assigned_role TEXT NOT NULL CHECK(assigned_role IN ('FRONT_DESK', 'TRIAGE_NURSE', 'CLINICIAN', 'PHARMACIST', 'CARE_COORDINATOR')),
    assigned_user_id TEXT,
    contact_attempts_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_at TEXT,
    outcome_notes TEXT,
    escalation_reason TEXT,
    completed_by TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (originating_encounter_id) REFERENCES encounters(id)
);

CREATE INDEX IF NOT EXISTS idx_continuity_patient_status ON care_continuity_tasks(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_continuity_due_role ON care_continuity_tasks(due_date, assigned_role, status);

-- 3. Medication Longitudinal Status Ledger
CREATE TABLE IF NOT EXISTS medication_status_ledger (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    formulation_name TEXT NOT NULL,
    formulation_type TEXT NOT NULL CHECK(formulation_type IN ('MUFRADAT', 'MURAKKABAT', 'ALLOPATHIC', 'UNKNOWN')),
    originating_prescription_id TEXT,
    current_state TEXT NOT NULL CHECK(current_state IN ('ACTIVE', 'DISCONTINUED', 'COMPLETED', 'ON_HOLD', 'PATIENT_REPORTED_STOPPED')),
    dosage_summary TEXT,
    start_date TEXT NOT NULL,
    end_date TEXT,
    discontinuation_reason TEXT,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (originating_prescription_id) REFERENCES prescriptions(id)
);

CREATE INDEX IF NOT EXISTS idx_med_ledger_patient_state ON medication_status_ledger(patient_id, current_state);

-- 4. Longitudinal Clinical Timeline Summary Runs
CREATE TABLE IF NOT EXISTS timeline_summary_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    summary_type TEXT NOT NULL DEFAULT 'LONGITUDINAL_OVERVIEW' CHECK(summary_type IN ('LONGITUDINAL_OVERVIEW', 'MEDICATION_HISTORY', 'ORGAN_AXIS_PROGRESSION', 'DISEASE_CHRONOLOGY')),
    date_range_start TEXT,
    date_range_end TEXT,
    draft_text TEXT NOT NULL,
    event_claim_bindings_json TEXT NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(review_status IN ('DRAFT', 'CLINICIAN_REVIEWED', 'REJECTED')),
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_notes TEXT,
    feature_flag_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (requested_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_timeline_summaries_patient ON timeline_summary_runs(patient_id, created_at DESC);

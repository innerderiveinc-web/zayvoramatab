-- ============================================================================
-- MIGRATION 013: Controlled Pilot Launch, Clinic Onboarding, Training & Operations
-- ZAYVORA MATAB OS — Independent Standalone Product
-- ============================================================================

-- 1. Pilot Programs
CREATE TABLE IF NOT EXISTS pilot_programs (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT', -- DRAFT, ELIGIBILITY_VERIFIED, ACTIVATED, PAUSED, STOPPED, CONCLUDED
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    target_start_date DATE,
    target_end_date DATE,
    actual_start_date TIMESTAMP,
    actual_end_date TIMESTAMP,
    audit_report_ref TEXT NOT NULL DEFAULT 'AUDIT-PROMPT13-REPORT-2026-10-13',
    audit_verdict TEXT NOT NULL DEFAULT 'CONDITIONAL_GO_FOR_LIMITED_PILOT',
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pilot_prog_org ON pilot_programs(organization_id);
CREATE INDEX IF NOT EXISTS idx_pilot_prog_status ON pilot_programs(status);

-- 2. Versioned Pilot Scope Records
CREATE TABLE IF NOT EXISTS pilot_scope_versions (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE, SUPERSEDED, REVOKED
    enabled_modules_json TEXT NOT NULL,
    disabled_modules_json TEXT NOT NULL,
    permitted_roles_json TEXT NOT NULL,
    permitted_facilities_json TEXT NOT NULL,
    supported_languages_json TEXT DEFAULT '["en", "ur", "hi"]',
    supported_devices_json TEXT DEFAULT '["DESKTOP_WEB", "TABLET_WEB"]',
    known_limitations TEXT,
    support_hours TEXT DEFAULT '09:00 - 18:00 IST',
    escalation_matrix_json TEXT,
    effective_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_by_clinical_lead TEXT REFERENCES users(id),
    approved_by_security_lead TEXT REFERENCES users(id),
    approved_by_product_lead TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pilot_program_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_pilot_scope_prog ON pilot_scope_versions(pilot_program_id);

-- 3. Facility Onboarding 13-Stage Checklists
CREATE TABLE IF NOT EXISTS facility_onboarding_checklists (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    stage_code TEXT NOT NULL,
    stage_title TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, IN_PROGRESS, COMPLETED, BLOCKED, WAIVED
    owner_user_id TEXT REFERENCES users(id),
    due_date DATE,
    completed_at TIMESTAMP,
    evidence_notes TEXT,
    blocker_details TEXT,
    signoff_user_id TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pilot_program_id, facility_id, stage_code)
);
CREATE INDEX IF NOT EXISTS idx_fac_onboard_fac ON facility_onboarding_checklists(facility_id);
CREATE INDEX IF NOT EXISTS idx_fac_onboard_prog ON facility_onboarding_checklists(pilot_program_id);

-- 4. Training Modules & Curricula
CREATE TABLE IF NOT EXISTS training_modules (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    target_role TEXT NOT NULL, -- TABIB, RECEPTIONIST, DISPENSER, ADMIN, NURSE
    title TEXT NOT NULL,
    description TEXT,
    curriculum_version TEXT NOT NULL DEFAULT '1.0',
    synthetic_scenario_data TEXT,
    min_pass_score INTEGER NOT NULL DEFAULT 80,
    is_mandatory BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Staff Training Enrollments & Scenario Acceptance
CREATE TABLE IF NOT EXISTS staff_training_enrollments (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    training_module_id TEXT NOT NULL REFERENCES training_modules(id),
    status TEXT NOT NULL DEFAULT 'ASSIGNED', -- ASSIGNED, IN_PROGRESS, PASSED, FAILED, RETRAINING_REQUIRED
    score INTEGER,
    scenario_acceptance_notes TEXT,
    completed_at TIMESTAMP,
    certified_by_user_id TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pilot_program_id, facility_id, user_id, training_module_id)
);
CREATE INDEX IF NOT EXISTS idx_trn_enroll_user ON staff_training_enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_trn_enroll_fac ON staff_training_enrollments(facility_id);

-- 6. Support & Emergency Incident Tickets
CREATE TABLE IF NOT EXISTS pilot_support_tickets (
    id TEXT PRIMARY KEY,
    ticket_number TEXT UNIQUE NOT NULL,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    reporter_user_id TEXT NOT NULL REFERENCES users(id),
    category TEXT NOT NULL, -- ACCESS_LOGIN, PATIENT_ENCOUNTER, PRESCRIPTION_DOC, SAFETY_ALERT, APPOINTMENT_BILLING, INTEGRATIONS, PERFORMANCE, PRIVACY_SECURITY, CLINICAL_SAFETY_INCIDENT
    severity TEXT NOT NULL, -- SEV_1_CRITICAL, SEV_2_HIGH, SEV_3_MODERATE, SEV_4_LOW
    subject TEXT NOT NULL,
    safe_description TEXT NOT NULL,
    trace_id TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN', -- OPEN, TRIAGED, IN_PROGRESS, RESOLVED, CLOSED, ESCALATED
    assigned_owner_role TEXT,
    assigned_user_id TEXT REFERENCES users(id),
    resolution_notes TEXT,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sup_tkt_prog ON pilot_support_tickets(pilot_program_id);
CREATE INDEX IF NOT EXISTS idx_sup_tkt_fac ON pilot_support_tickets(facility_id);
CREATE INDEX IF NOT EXISTS idx_sup_tkt_sev ON pilot_support_tickets(severity);

-- 7. Clinical Safety Governance Queue (Dedicated Path for Patient Safety Concerns)
CREATE TABLE IF NOT EXISTS clinical_safety_incident_queue (
    id TEXT PRIMARY KEY,
    incident_number TEXT UNIQUE NOT NULL,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    reporter_user_id TEXT NOT NULL REFERENCES users(id),
    ticket_id TEXT REFERENCES pilot_support_tickets(id),
    issue_type TEXT NOT NULL, -- FALSE_ALERT, MISSED_ALERT, INCORRECT_MAPPING, DOSAGE_ERROR, SIGNATURE_MISMATCH, ADVERSE_EFFECT_CONCERN
    clinical_description TEXT NOT NULL,
    evidence_snapshot_json TEXT,
    severity TEXT NOT NULL DEFAULT 'CRITICAL', -- CRITICAL, MAJOR, MODERATE
    clinical_governance_reviewer_id TEXT REFERENCES users(id),
    governance_action TEXT, -- NO_ACTION, RULE_UPDATE_REQUIRED, MONOGRAPH_AMENDMENT, RETRAINING_ORDERED, FORMULATION_QUARANTINE
    status TEXT NOT NULL DEFAULT 'PENDING_REVIEW', -- PENDING_REVIEW, UNDER_INVESTIGATION, RESOLVED, DISMISSED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_safe_inc_prog ON clinical_safety_incident_queue(pilot_program_id);
CREATE INDEX IF NOT EXISTS idx_safe_inc_status ON clinical_safety_incident_queue(status);

-- 8. Structured Feedback & Triage Items
CREATE TABLE IF NOT EXISTS pilot_feedback_items (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    category TEXT NOT NULL, -- USABILITY_FRICTION, MISSING_WORKFLOW, RELIABILITY, CLINICAL_CONTENT, SAFETY_CONCERN, INTEGRATION, TRAINING_GAP, FEATURE_REQUEST
    impact_level TEXT NOT NULL, -- BLOCKING, HIGH, MEDIUM, LOW
    affected_workflow TEXT NOT NULL,
    software_version TEXT NOT NULL,
    description TEXT NOT NULL,
    reproduction_steps TEXT,
    status TEXT NOT NULL DEFAULT 'NEW', -- NEW, TRIAGED, ACCEPTED_BACKLOG, RESOLVED, REJECTED
    triage_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fdbk_prog ON pilot_feedback_items(pilot_program_id);
CREATE INDEX IF NOT EXISTS idx_fdbk_cat ON pilot_feedback_items(category);

-- 9. Stop Conditions & Containment Events
CREATE TABLE IF NOT EXISTS pilot_stop_events (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    facility_id TEXT REFERENCES facilities(id),
    triggered_by_user_id TEXT NOT NULL REFERENCES users(id),
    condition_code TEXT NOT NULL, -- TENANT_EXPOSURE, UNAUTHORIZED_SIGNING, DATA_CORRUPTION, SAFETY_GATE_BYPASS, FALSE_SAFETY_RESULT, CREDENTIALS_EXPOSED, SAVE_FAILURE_LOOP, RESTORE_FAILURE
    action_taken TEXT NOT NULL, -- PAUSE_FACILITY, PAUSE_PILOT_ALL, DISABLE_MODULE, TERMINATE_PILOT
    affected_module TEXT,
    containment_actions_json TEXT NOT NULL,
    restart_criteria TEXT,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_stop_evt_prog ON pilot_stop_events(pilot_program_id);
CREATE INDEX IF NOT EXISTS idx_stop_evt_active ON pilot_stop_events(is_active);

-- 10. Daily & Weekly Review Packs
CREATE TABLE IF NOT EXISTS pilot_review_packs (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    review_type TEXT NOT NULL, -- DAILY, WEEKLY, FINAL_PILOT_VERDICT
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    metrics_snapshot_json TEXT NOT NULL,
    incidents_summary_json TEXT NOT NULL,
    feedback_summary_json TEXT NOT NULL,
    recommendation TEXT NOT NULL, -- CONTINUE_AS_PLANNED, EXTEND_PILOT_DURATION, PAUSE_FOR_REMEDIATION, EXPAND_TO_NEXT_FACILITY, TERMINATE_PILOT
    prepared_by_user_id TEXT NOT NULL REFERENCES users(id),
    approved_by_clinical_lead TEXT REFERENCES users(id),
    approved_by_operations_lead TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rev_pack_prog ON pilot_review_packs(pilot_program_id);

-- 11. Governed Data Migration & Reconciliation Runs
CREATE TABLE IF NOT EXISTS pilot_data_migrations (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    source_system_name TEXT NOT NULL,
    source_authority_reference TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'DRY_RUN', -- DRY_RUN, EXECUTE
    status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, RUNNING, COMPLETED, FAILED, ROLLED_BACK
    total_records_read INTEGER DEFAULT 0,
    records_migrated INTEGER DEFAULT 0,
    records_rejected INTEGER DEFAULT 0,
    ambiguous_duplicates_flagged INTEGER DEFAULT 0,
    reconciliation_report_json TEXT,
    error_log_json TEXT,
    executed_by_user_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_mig_prog ON pilot_data_migrations(pilot_program_id);
CREATE INDEX IF NOT EXISTS idx_mig_fac ON pilot_data_migrations(facility_id);

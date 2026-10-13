-- ============================================================================
-- MIGRATION 014: Post-Pilot Evaluation, Adoption Scorecard & Scale Decision
-- ZAYVORA MATAB OS — Independent Standalone Product
-- ============================================================================

-- 1. Pilot Evaluations (Master Evaluation Lifecycle Record)
CREATE TABLE IF NOT EXISTS pilot_evaluations (
    id TEXT PRIMARY KEY,
    pilot_program_id TEXT NOT NULL REFERENCES pilot_programs(id),
    scope_version_id TEXT REFERENCES pilot_scope_versions(id),
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT REFERENCES facilities(id),
    evaluation_title TEXT NOT NULL,
    build_commit TEXT NOT NULL,
    review_period_start DATE NOT NULL,
    review_period_end DATE NOT NULL,
    status TEXT NOT NULL DEFAULT 'NOT_STARTED', -- NOT_STARTED, EVIDENCE_COLLECTION, NOT_YET_ASSESSABLE, ASSESSABLE_WITH_LIMITATIONS, READY_FOR_DECISION, DECISION_APPROVED, REMEDIATION_REQUIRED
    enabled_features_json TEXT NOT NULL DEFAULT '[]',
    disabled_features_json TEXT NOT NULL DEFAULT '[]',
    roles_covered_json TEXT NOT NULL DEFAULT '[]',
    integrations_covered_json TEXT NOT NULL DEFAULT '[]',
    success_criteria_json TEXT DEFAULT '{}',
    targets_json TEXT DEFAULT '{}',
    findings_summary TEXT,
    limitations_summary TEXT,
    primary_recommendation TEXT, -- CONTINUE_CURRENT_PILOT, EXPAND_WITHIN_APPROVED_SCOPE, EXPAND_TO_ADDITIONAL_FACILITY, ENABLE_SPECIFIC_MODULE, PAUSE_FOR_REMEDIATION, STOP_OR_ROLLBACK, NOT_YET_ASSESSABLE
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pilot_eval_prog ON pilot_evaluations(pilot_program_id);
CREATE INDEX IF NOT EXISTS idx_pilot_eval_org ON pilot_evaluations(organization_id);
CREATE INDEX IF NOT EXISTS idx_pilot_eval_status ON pilot_evaluations(status);

-- 2. Evidence Inventory Items
CREATE TABLE IF NOT EXISTS evidence_inventory_items (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    source_reference TEXT NOT NULL,
    category TEXT NOT NULL, -- PILOT_SCOPE, RELEASE_COMMIT, AUDIT_STATUS, ONBOARDING_ASSIGNMENT, TRAINING_ACCEPTANCE, MONITORING_COVERAGE, WORKFLOW_TELEMETRY, PREFLIGHT_FAILURES, INCIDENTS_LOG, SUPPORT_TICKETS, USER_FEEDBACK, INTEGRATION_HEALTH, BACKUP_RESTORE_EXERCISE, CLINICAL_GOVERNANCE
    owner TEXT NOT NULL,
    build_commit TEXT NOT NULL,
    date_range_start DATE,
    date_range_end DATE,
    completeness TEXT NOT NULL DEFAULT 'COMPLETE', -- COMPLETE, PARTIAL, MISSING, UNAVAILABLE
    access_restrictions TEXT DEFAULT 'INTERNAL_RESTRICTED',
    extraction_method TEXT NOT NULL, -- SQL_AUDIT_QUERY, TELEMETRY_EXPORT, MANUAL_AUDIT, TEST_HARNESS_LOG
    limitations TEXT,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED', -- VERIFIED, UNVERIFIED, CONTESTED
    verified_by TEXT REFERENCES users(id),
    verified_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_evi_inv_eval ON evidence_inventory_items(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_evi_inv_cat ON evidence_inventory_items(category);

-- 3. Metric Definitions (Pre-agreed versioned metric specifications)
CREATE TABLE IF NOT EXISTS metric_definitions (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    domain_category TEXT NOT NULL, -- WORKFLOW_USABILITY, RELIABILITY, CLINICAL_INTEGRITY, SAFETY_GOVERNANCE, TRAINING_ADOPTION, SUPPORT_OPERATIONS, COMMUNICATIONS_INTEGRATIONS, CLINICAL_OUTCOMES
    definition TEXT NOT NULL,
    numerator_definition TEXT,
    denominator_definition TEXT,
    data_source TEXT NOT NULL,
    calculation_method TEXT NOT NULL,
    exclusions TEXT,
    baseline_target TEXT,
    threshold_target TEXT,
    version TEXT NOT NULL DEFAULT '1.0',
    owner_role TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_met_def_code ON metric_definitions(code);
CREATE INDEX IF NOT EXISTS idx_met_def_domain ON metric_definitions(domain_category);

-- 4. Metric Observations (Calculated or explicitly unavailable metric results)
CREATE TABLE IF NOT EXISTS metric_observations (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    metric_definition_id TEXT NOT NULL REFERENCES metric_definitions(id),
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    numerator_value REAL,
    denominator_value REAL,
    observed_value REAL,
    observed_formatted TEXT,
    is_unavailable BOOLEAN NOT NULL DEFAULT 0,
    unavailable_reason TEXT,
    target_met BOOLEAN,
    limitations TEXT,
    review_state TEXT NOT NULL DEFAULT 'UNREVIEWED', -- UNREVIEWED, REVIEWED, ACCEPTED, DISPUTED
    reviewer_notes TEXT,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_met_obs_eval ON metric_observations(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_met_obs_def ON metric_observations(metric_definition_id);

-- 5. Feedback Theme Reviews (Deduplicated themes with redacted evidence & hypotheses)
CREATE TABLE IF NOT EXISTS feedback_theme_reviews (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    theme_title TEXT NOT NULL,
    classification TEXT NOT NULL, -- USABILITY_FRICTION, MISSING_WORKFLOW, RELIABILITY_PERFORMANCE, CLINICAL_CONTENT_QUESTION, SAFETY_CONCERN, INTEGRATION_ISSUE, TRAINING_GAP, ACCESSIBILITY_LANGUAGE, FEATURE_REQUEST
    affected_role TEXT NOT NULL,
    affected_workflow TEXT NOT NULL,
    verified_count INTEGER NOT NULL DEFAULT 1,
    redacted_evidence_quote TEXT NOT NULL,
    severity_impact TEXT NOT NULL, -- CRITICAL, HIGH, MEDIUM, LOW
    root_cause_hypothesis TEXT NOT NULL, -- Must be clearly labelled as hypothesis
    disposition TEXT NOT NULL DEFAULT 'OPEN', -- ACCEPTED_ACTION, GOVERNANCE_REVIEW_REQUIRED, WONT_FIX, CANNOT_REPRODUCE, RETEST_REQUIRED
    owner_role TEXT NOT NULL,
    proposed_fix_rationale TEXT,
    retest_requirement TEXT,
    is_governance_reviewed BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_fdb_thm_eval ON feedback_theme_reviews(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_fdb_thm_class ON feedback_theme_reviews(classification);

-- 6. Incident and Risk Reviews (Pre-expansion risk re-review ledger)
CREATE TABLE IF NOT EXISTS incident_risk_reviews (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    issue_ref TEXT NOT NULL,
    issue_type TEXT NOT NULL, -- P0_FINDING, P1_FINDING, SAFETY_INCIDENT, NEAR_MISS, PRIVACY_SECURITY, WRONG_PATIENT_ASSOC, SIGNATURE_DOC_MISMATCH, DATA_CORRUPTION, BACKUP_RESTORE_FAIL, INTEGRATION_SCOPE_VIOLATION, PERMISSION_BYPASS, STALE_CLINICAL_CONTENT
    severity TEXT NOT NULL, -- P0_CRITICAL, P1_HIGH, P2_MEDIUM, P3_LOW
    verified_facts TEXT NOT NULL,
    uncertainties TEXT,
    containment_status TEXT NOT NULL, -- CONTAINED, MONITORING, UNCONTAINED
    confirmed_root_cause TEXT,
    suspected_root_cause TEXT,
    corrective_action TEXT NOT NULL,
    retest_evidence_ref TEXT,
    is_safety_downgraded BOOLEAN NOT NULL DEFAULT 0, -- Must stay 0; safety concerns cannot be downgraded purely because no harm was reported
    approving_owner_id TEXT REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'OPEN', -- OPEN, MITIGATED, RESOLVED, WAIVED_RESIDUAL_RISK
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_inc_risk_eval ON incident_risk_reviews(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_inc_risk_sev ON incident_risk_reviews(severity);

-- 7. Expansion Proposals (Distinct proposals for independent gate evaluation)
CREATE TABLE IF NOT EXISTS expansion_proposals (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    proposal_type TEXT NOT NULL, -- MORE_USERS_SAME_FACILITY, ANOTHER_BRANCH_FACILITY, PHARMACY_INVENTORY_ENABLEMENT, EXTERNAL_COMMUNICATIONS, HOSPITAL_IPD_LAB_REFERRAL, FHIR_ABDM_EXCHANGE, LARGER_DATA_VOLUME, BROADER_PRODUCTION_AVAILABILITY
    target_scope_details_json TEXT NOT NULL,
    justification TEXT NOT NULL,
    prerequisite_dependencies_json TEXT NOT NULL,
    overall_gate_status TEXT NOT NULL DEFAULT 'PENDING', -- PENDING, PASSED, BLOCKED, REJECTED
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_exp_prop_eval ON expansion_proposals(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_exp_prop_type ON expansion_proposals(proposal_type);

-- 8. Expansion Gate Results (Independent gate evaluation checklist items)
CREATE TABLE IF NOT EXISTS expansion_gate_results (
    id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES expansion_proposals(id),
    gate_name TEXT NOT NULL, -- DEPENDENCY_CHECK, SCOPE_ACCESS_TESTS, TRAINING_ONBOARDING_CAPACITY, END_TO_END_TESTS, CLINICAL_CONTENT_APPROVAL, BACKUP_RESTORE_DRILL, INCIDENT_RESPONSE_READY, INTEGRATION_READINESS, MONITORING_SUPPORT_CAPACITY, ABSENCE_OF_STOP_CONDITIONS, MANDATORY_SAFETY_GATE
    gate_status TEXT NOT NULL, -- PASS, FAIL, BLOCKED, WAIVED
    evidence_notes TEXT,
    blocker_details TEXT,
    checked_by TEXT REFERENCES users(id),
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(proposal_id, gate_name)
);
CREATE INDEX IF NOT EXISTS idx_exp_gate_prop ON expansion_gate_results(proposal_id);

-- 9. Evaluation Decision Records (Formal scale/containment verdict)
CREATE TABLE IF NOT EXISTS evaluation_decision_records (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    decision TEXT NOT NULL, -- CONTINUE_CURRENT_PILOT, EXPAND_WITHIN_APPROVED_SCOPE, EXPAND_TO_ADDITIONAL_FACILITY, ENABLE_SPECIFIC_MODULE, PAUSE_FOR_REMEDIATION, STOP_OR_ROLLBACK, NOT_YET_ASSESSABLE
    rationale TEXT NOT NULL,
    allowed_scope_summary TEXT NOT NULL,
    disabled_features_summary TEXT NOT NULL,
    accepted_residual_risks TEXT,
    next_review_date DATE,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dec_rec_eval ON evaluation_decision_records(evaluation_id);

-- 10. Multi-Role Decision Approvals (Requires Clinical, Ops, and Security signatures)
CREATE TABLE IF NOT EXISTS decision_approvals (
    id TEXT PRIMARY KEY,
    decision_record_id TEXT NOT NULL REFERENCES evaluation_decision_records(id),
    required_role TEXT NOT NULL, -- CLINICAL_GOVERNANCE, PRODUCT_OPERATIONS, SECURITY_PRIVACY
    approver_user_id TEXT NOT NULL REFERENCES users(id),
    approval_status TEXT NOT NULL, -- APPROVED, REJECTED, CONDITIONAL
    conditions_or_notes TEXT,
    signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(decision_record_id, required_role)
);
CREATE INDEX IF NOT EXISTS idx_dec_app_dec ON decision_approvals(decision_record_id);

-- 11. Remediation Actions (Auditable post-evaluation corrective tasks)
CREATE TABLE IF NOT EXISTS remediation_actions (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    category TEXT NOT NULL, -- SAFETY, SECURITY, USABILITY, RELIABILITY, TRAINING, INTEGRATION, MONITORING
    priority TEXT NOT NULL, -- P0, P1, P2, P3
    owner_role TEXT NOT NULL,
    owner_user_id TEXT REFERENCES users(id),
    due_date DATE,
    retest_requirement TEXT NOT NULL,
    retest_evidence_ref TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN', -- OPEN, IN_PROGRESS, RETEST_PENDING, VERIFIED_CLOSED, WONT_FIX
    closed_by TEXT REFERENCES users(id),
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rem_act_eval ON remediation_actions(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_rem_act_stat ON remediation_actions(status);

-- 12. Evaluation Report Versions (Version-controlled markdown & manifest snapshots)
CREATE TABLE IF NOT EXISTS evaluation_report_versions (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES pilot_evaluations(id),
    version_number INTEGER NOT NULL,
    report_title TEXT NOT NULL,
    report_markdown TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    generated_by TEXT NOT NULL REFERENCES users(id),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(evaluation_id, version_number)
);
CREATE INDEX IF NOT EXISTS idx_rep_ver_eval ON evaluation_report_versions(evaluation_id);

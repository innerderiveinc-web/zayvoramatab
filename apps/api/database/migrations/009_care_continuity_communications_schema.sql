-- Phase 9 Schema: Follow-up, Care Continuity, Patient Communication & Outcome Tracking
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Follow-up Plans (Clinician-Authored Longitudinal Directives)
CREATE TABLE IF NOT EXISTS follow_up_plans (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    care_plan_id TEXT,
    review_due_at TEXT NOT NULL, -- ISO-8601 timestamp or YYYY-MM-DD
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    purpose TEXT NOT NULL,
    review_format TEXT NOT NULL DEFAULT 'in_person', -- 'in_person', 'teleconsultation', 'phone_check', 'lab_review'
    monitoring_items_json TEXT NOT NULL DEFAULT '[]',
    safety_instructions TEXT,
    escalation_guidance TEXT,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'amended', 'completed', 'cancelled'
    version_number INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fup_plans_patient ON follow_up_plans(organization_id, facility_id, patient_id, status);
CREATE INDEX IF NOT EXISTS idx_fup_plans_encounter ON follow_up_plans(encounter_id);

-- 2. Follow-up Plan Versions (Immutable Audit History)
CREATE TABLE IF NOT EXISTS follow_up_plan_versions (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES follow_up_plans(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    change_reason TEXT,
    authored_by TEXT NOT NULL REFERENCES users(id),
    authored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(plan_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_fup_plan_versions_plan ON follow_up_plan_versions(plan_id, version_number);

-- 3. Follow-up Tasks (Actionable Operational & Clinical Work Items)
CREATE TABLE IF NOT EXISTS follow_up_tasks (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    plan_id TEXT REFERENCES follow_up_plans(id) ON DELETE SET NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    assigned_to TEXT REFERENCES users(id),
    assigned_role TEXT DEFAULT 'PRACTITIONER',
    due_at TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    purpose TEXT NOT NULL,
    clinical_context_summary TEXT, -- Role-gated in queue views (hidden from front-desk receptionists)
    planned_channel TEXT NOT NULL DEFAULT 'in_person', -- 'in_person', 'sms', 'whatsapp', 'phone_call', 'teleconsultation'
    priority TEXT NOT NULL DEFAULT 'routine', -- 'routine', 'high', 'urgent'
    status TEXT NOT NULL DEFAULT 'planned', -- 'planned', 'due', 'in_progress', 'completed', 'rescheduled', 'patient_declined', 'unable_to_reach', 'cancelled', 'escalated', 'entered_in_error'
    completion_outcome TEXT,
    completion_notes TEXT,
    rescheduled_from_due_at TEXT,
    reschedule_reason TEXT,
    idempotency_key TEXT UNIQUE,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fup_tasks_queue ON follow_up_tasks(organization_id, facility_id, status, due_at, priority);
CREATE INDEX IF NOT EXISTS idx_fup_tasks_patient ON follow_up_tasks(patient_id, status);
CREATE INDEX IF NOT EXISTS idx_fup_tasks_plan ON follow_up_tasks(plan_id);

-- 4. Follow-up Task Lifecycle Events
CREATE TABLE IF NOT EXISTS follow_up_task_events (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES follow_up_tasks(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'CREATED', 'STATUS_CHANGED', 'ASSIGNED', 'RESCHEDULED', 'CONTACT_ATTEMPTED', 'REMINDER_DISPATCHED'
    from_status TEXT,
    to_status TEXT,
    actor_id TEXT NOT NULL REFERENCES users(id),
    reason TEXT,
    metadata_json TEXT,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fup_task_events_task ON follow_up_task_events(task_id, occurred_at);

-- 5. Documented Contact Attempts (Required before marking unable_to_reach)
CREATE TABLE IF NOT EXISTS contact_attempts (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    task_id TEXT NOT NULL REFERENCES follow_up_tasks(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    channel TEXT NOT NULL, -- 'sms', 'whatsapp', 'email', 'phone_call', 'in_person'
    attempt_outcome TEXT NOT NULL, -- 'reached', 'no_answer', 'busy', 'wrong_number', 'declined', 'message_sent'
    notes TEXT,
    outbound_message_id TEXT,
    attempted_by TEXT NOT NULL REFERENCES users(id),
    attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contact_attempts_task ON contact_attempts(task_id, attempted_at);

-- 6. Follow-up Appointments & Repeat-Visit Bookings
CREATE TABLE IF NOT EXISTS follow_up_appointments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    followup_task_id TEXT REFERENCES follow_up_tasks(id) ON DELETE SET NULL,
    source_encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    repeat_encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    practitioner_id TEXT NOT NULL REFERENCES users(id),
    scheduled_start_at TEXT NOT NULL,
    scheduled_end_at TEXT NOT NULL,
    slot_lock_key TEXT UNIQUE, -- Active slot lock (facility_id + practitioner_id + scheduled_start_at) when status is booked/confirmed/arrived; NULL when cancelled/no_show
    visit_mode TEXT NOT NULL DEFAULT 'in_person', -- 'in_person', 'teleconsultation'
    status TEXT NOT NULL DEFAULT 'requested', -- 'requested', 'booked', 'confirmed', 'arrived', 'completed', 'cancelled', 'no_show'
    reason_for_visit TEXT,
    cancellation_reason TEXT,
    booked_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fup_appointments_patient ON follow_up_appointments(patient_id, scheduled_start_at);
CREATE INDEX IF NOT EXISTS idx_fup_appointments_slot ON follow_up_appointments(facility_id, practitioner_id, scheduled_start_at, status);

-- 7. Patient Communication Preferences & Granular Consent State
CREATE TABLE IF NOT EXISTS communication_preferences (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    patient_id TEXT NOT NULL UNIQUE REFERENCES patients(id) ON DELETE CASCADE,
    preferred_language TEXT NOT NULL DEFAULT 'en', -- 'en', 'ur', 'hi', 'ar'
    preferred_channel TEXT NOT NULL DEFAULT 'sms', -- 'sms', 'whatsapp', 'email', 'phone_call', 'none'
    permitted_categories_json TEXT NOT NULL DEFAULT '["clinical_reminder", "appointment_confirmation", "safety_followup"]',
    allow_marketing INTEGER NOT NULL DEFAULT 0, -- Strictly separated from clinical reminders
    verified_contact_ref TEXT,
    quiet_hours_start TEXT NOT NULL DEFAULT '21:00',
    quiet_hours_end TEXT NOT NULL DEFAULT '08:00',
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    opt_out_status INTEGER NOT NULL DEFAULT 0, -- 1 if patient opted out of automated messages
    do_not_contact_scope TEXT NOT NULL DEFAULT 'none', -- 'none', 'marketing_only', 'non_urgent_all', 'all_automated'
    consent_source TEXT NOT NULL DEFAULT 'front_desk_registration',
    recorded_by TEXT NOT NULL REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_comm_prefs_patient ON communication_preferences(organization_id, patient_id);

-- 8. Governed Communication Templates & Versions
CREATE TABLE IF NOT EXISTS communication_templates (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    template_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    channel TEXT NOT NULL, -- 'sms', 'whatsapp', 'email', 'phone_call'
    language TEXT NOT NULL DEFAULT 'en',
    category TEXT NOT NULL, -- 'clinical_reminder', 'appointment_confirmation', 'safety_followup', 'missed_visit_outreach'
    current_version INTEGER NOT NULL DEFAULT 1,
    approval_status TEXT NOT NULL DEFAULT 'draft', -- 'draft', 'pending_review', 'approved', 'retired'
    contains_sensitive_fields INTEGER NOT NULL DEFAULT 0,
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS communication_template_versions (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL REFERENCES communication_templates(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    body_template TEXT NOT NULL,
    allowed_placeholders_json TEXT NOT NULL DEFAULT '["patient_name", "facility_name", "appointment_date", "clinic_phone"]',
    prohibited_placeholders_json TEXT NOT NULL DEFAULT '["diagnosis", "medication_name", "hiv_status", "psychiatric_notes", "detailed_symptoms"]',
    approval_status TEXT NOT NULL DEFAULT 'draft',
    authored_by TEXT NOT NULL REFERENCES users(id),
    approved_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(template_id, version_number)
);

-- 9. Reminder Policies
CREATE TABLE IF NOT EXISTS reminder_policies (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    policy_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    timing_offset_minutes INTEGER NOT NULL DEFAULT -1440, -- e.g. 24h before due
    channel TEXT NOT NULL DEFAULT 'sms',
    template_id TEXT NOT NULL REFERENCES communication_templates(id),
    quiet_hours_start TEXT NOT NULL DEFAULT '21:00',
    quiet_hours_end TEXT NOT NULL DEFAULT '08:00',
    max_attempts INTEGER NOT NULL DEFAULT 3,
    retry_interval_minutes INTEGER NOT NULL DEFAULT 60,
    allow_sensitive_placeholders INTEGER NOT NULL DEFAULT 0,
    approval_status TEXT NOT NULL DEFAULT 'approved',
    version_number INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 10. Communication Provider Configurations
CREATE TABLE IF NOT EXISTS communication_provider_configs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    provider_code TEXT NOT NULL, -- 'sandbox_sms', 'sandbox_whatsapp', 'sandbox_email', 'manual_call_log'
    channel TEXT NOT NULL,
    credentials_redacted_json TEXT NOT NULL DEFAULT '{"api_key": "***REDACTED***"}',
    webhook_secret_hash TEXT NOT NULL DEFAULT 'matab_webhook_secret_dev_key',
    rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
    status TEXT NOT NULL DEFAULT 'active',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, facility_id, provider_code)
);

-- 11. Durable Outbound Messages, Delivery Events & Job Outbox
CREATE TABLE IF NOT EXISTS outbound_messages (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    task_id TEXT REFERENCES follow_up_tasks(id) ON DELETE SET NULL,
    appointment_id TEXT REFERENCES follow_up_appointments(id) ON DELETE SET NULL,
    template_id TEXT NOT NULL REFERENCES communication_templates(id),
    template_version_id TEXT NOT NULL REFERENCES communication_template_versions(id),
    channel TEXT NOT NULL,
    provider_code TEXT NOT NULL,
    recipient_ref TEXT NOT NULL,
    rendered_body TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'clinical_reminder',
    status TEXT NOT NULL DEFAULT 'queued', -- 'queued', 'deferred_quiet_hours', 'sent', 'accepted', 'delivered', 'read', 'failed', 'suppressed', 'dead_letter'
    suppression_reason TEXT,
    failure_reason TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    scheduled_for TEXT,
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    provider_message_id TEXT,
    idempotency_key TEXT UNIQUE,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outbound_messages_patient ON outbound_messages(patient_id, created_at);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_task ON outbound_messages(task_id, status);
CREATE INDEX IF NOT EXISTS idx_outbound_messages_provider_msg ON outbound_messages(provider_message_id);

CREATE TABLE IF NOT EXISTS message_delivery_events (
    id TEXT PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES outbound_messages(id) ON DELETE CASCADE,
    provider_code TEXT NOT NULL,
    provider_event_id TEXT NOT NULL UNIQUE, -- Enforces webhook idempotency
    event_type TEXT NOT NULL, -- 'queued', 'sent', 'accepted', 'delivered', 'read', 'failed', 'opt_out_received', 'suppressed', 'dead_letter'
    raw_payload_json TEXT,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_msg_delivery_events_msg ON message_delivery_events(message_id, occurred_at);

CREATE TABLE IF NOT EXISTS job_outbox (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    job_type TEXT NOT NULL, -- 'DISPATCH_OUTBOUND_MESSAGE', 'EVALUATE_OVERDUE_TASKS'
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed', 'dead_letter'
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    next_run_at TEXT,
    last_error TEXT,
    idempotency_key TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_job_outbox_status ON job_outbox(status, next_run_at);

-- 12. Structured Outcome Definitions & Longitudinal Outcome Records
CREATE TABLE IF NOT EXISTS outcome_definitions (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    domain TEXT NOT NULL, -- 'symptom_severity', 'functional_status', 'vital_sign', 'adherence', 'unani_clinical_marker'
    response_type TEXT NOT NULL, -- 'numeric', 'scale', 'ordinal', 'text', 'boolean'
    unit TEXT,
    scale_min REAL,
    scale_max REAL,
    directionality TEXT NOT NULL DEFAULT 'lower_is_better', -- 'lower_is_better', 'higher_is_better', 'target_range', 'neutral'
    collection_method TEXT NOT NULL DEFAULT 'clinical_interview',
    instrument_version TEXT NOT NULL DEFAULT '1.0',
    review_status TEXT NOT NULL DEFAULT 'approved', -- 'draft', 'approved', 'retired'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS outcome_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    follow_up_task_id TEXT REFERENCES follow_up_tasks(id) ON DELETE SET NULL,
    care_plan_id TEXT,
    definition_id TEXT NOT NULL REFERENCES outcome_definitions(id),
    reporter_type TEXT NOT NULL, -- 'patient_reported', 'caregiver_reported', 'clinician_observed', 'device_imported', 'ai_draft_unverified'
    value_numeric REAL,
    value_text TEXT,
    unit TEXT,
    collection_method TEXT NOT NULL,
    source_context TEXT DEFAULT 'followup_review', -- 'baseline_encounter', 'followup_review', 'patient_outreach', 'home_monitoring'
    verification_status TEXT NOT NULL DEFAULT 'verified', -- 'verified', 'unverified', 'ai_draft_unverified', 'entered_in_error'
    notes TEXT,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    recorded_at TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outcome_records_patient ON outcome_records(patient_id, definition_id, recorded_at);
CREATE INDEX IF NOT EXISTS idx_outcome_records_task ON outcome_records(follow_up_task_id);

-- 13. Adverse Effect Reports & Safety Escalation
CREATE TABLE IF NOT EXISTS adverse_effect_reports (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id),
    facility_id TEXT NOT NULL REFERENCES facilities(id),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    prescription_id TEXT REFERENCES prescriptions(id) ON DELETE SET NULL,
    follow_up_task_id TEXT REFERENCES follow_up_tasks(id) ON DELETE SET NULL,
    suspected_medication TEXT NOT NULL,
    patient_description TEXT NOT NULL,
    onset_date TEXT,
    patient_reported_severity TEXT NOT NULL DEFAULT 'moderate', -- 'mild', 'moderate', 'severe', 'life_threatening'
    clinician_assessed_severity TEXT NOT NULL DEFAULT 'unassessed', -- 'unassessed', 'mild', 'moderate', 'severe', 'life_threatening'
    causality_assessment TEXT NOT NULL DEFAULT 'patient_suspected', -- 'patient_suspected', 'clinician_assessed', 'undetermined'
    action_taken TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending_clinician_review', -- 'pending_clinician_review', 'reviewed', 'escalated', 'closed'
    escalated_to_safety_firewall INTEGER NOT NULL DEFAULT 0,
    urgent_flag INTEGER NOT NULL DEFAULT 0,
    reviewed_by TEXT REFERENCES users(id),
    reviewed_at TIMESTAMP,
    reported_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_adverse_effects_patient ON adverse_effect_reports(organization_id, facility_id, patient_id, review_status);
CREATE INDEX IF NOT EXISTS idx_adverse_effects_urgent ON adverse_effect_reports(organization_id, facility_id, urgent_flag, review_status);

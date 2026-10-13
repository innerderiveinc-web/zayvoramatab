-- Phase 12 Schema: Hospital Workflows (IPD/ADT, Bed Management, Laboratory/LIS, Referrals) & Interoperability (FHIR R4, Terminology, Consent & ABDM)
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. IPD Wards
CREATE TABLE IF NOT EXISTS ipd_wards (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    department_id TEXT REFERENCES facility_departments(id) ON DELETE SET NULL,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    ward_type TEXT NOT NULL DEFAULT 'GENERAL_UNANI_WARD' CHECK (ward_type IN (
        'GENERAL_UNANI_WARD', 'REGIMENAL_THERAPY_WARD', 'PRIVATE_SUITE',
        'HIGH_DEPENDENCY_UNIT', 'ISOLATION_WARD', 'OBSERVATION_UNIT'
    )),
    gender_policy TEXT NOT NULL DEFAULT 'MIXED' CHECK (gender_policy IN ('MIXED', 'FEMALE_ONLY', 'MALE_ONLY')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance')),
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, code)
);

CREATE INDEX IF NOT EXISTS idx_ipd_wards_facility ON ipd_wards(organization_id, facility_id, status);

-- 2. IPD Beds (Concurrency-Safe Operational & Occupancy State)
CREATE TABLE IF NOT EXISTS ipd_beds (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    ward_id TEXT NOT NULL REFERENCES ipd_wards(id) ON DELETE CASCADE,
    room_number TEXT NOT NULL DEFAULT 'RM-1',
    bed_code TEXT NOT NULL,
    bed_category TEXT NOT NULL DEFAULT 'STANDARD' CHECK (bed_category IN (
        'STANDARD', 'SEMI_PRIVATE', 'PRIVATE', 'HDU', 'ISOLATION', 'REGIMENAL_TABLE_BED'
    )),
    operational_status TEXT NOT NULL DEFAULT 'available' CHECK (operational_status IN (
        'available', 'reserved', 'occupied', 'cleaning', 'maintenance', 'out_of_service'
    )),
    active_admission_id TEXT,
    active_patient_id TEXT REFERENCES patients(id) ON DELETE SET NULL,
    active_stay_lock TEXT UNIQUE, -- Non-null when reserved or occupied to guarantee at most one active stay per bed
    maintenance_reason TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, bed_code)
);

CREATE INDEX IF NOT EXISTS idx_ipd_beds_ward_status ON ipd_beds(organization_id, facility_id, ward_id, operational_status);

-- 3. IPD Admissions (ADT State Machine)
CREATE TABLE IF NOT EXISTS ipd_admissions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    department_id TEXT REFERENCES facility_departments(id) ON DELETE SET NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    originating_encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    inpatient_encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    admitting_practitioner_id TEXT NOT NULL REFERENCES users(id),
    care_team_json TEXT NOT NULL DEFAULT '[]',
    admission_type TEXT NOT NULL DEFAULT 'ELECTIVE' CHECK (admission_type IN (
        'ELECTIVE', 'EMERGENCY', 'OBSERVATION', 'REGIMENAL_INPATIENT', 'TRANSFER_IN'
    )),
    urgency TEXT NOT NULL DEFAULT 'ROUTINE' CHECK (urgency IN ('ROUTINE', 'URGENT', 'EMERGENCY')),
    reason_for_admission TEXT NOT NULL,
    provisional_diagnosis TEXT,
    status TEXT NOT NULL DEFAULT 'requested' CHECK (status IN (
        'requested', 'accepted', 'awaiting_bed', 'admitted', 'transferred',
        'discharged', 'cancelled', 'entered_in_error'
    )),
    assigned_ward_id TEXT REFERENCES ipd_wards(id) ON DELETE SET NULL,
    assigned_bed_id TEXT REFERENCES ipd_beds(id) ON DELETE SET NULL,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP,
    admitted_at TIMESTAMP,
    discharged_at TIMESTAMP,
    discharge_type TEXT,
    discharge_destination TEXT,
    cancellation_reason TEXT,
    idempotency_key TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_ipd_admissions_fac_status ON ipd_admissions(organization_id, facility_id, status);
CREATE INDEX IF NOT EXISTS idx_ipd_admissions_patient ON ipd_admissions(organization_id, patient_id);

-- 4. IPD Bed Occupancy Events (Append-Only Audit Trail)
CREATE TABLE IF NOT EXISTS ipd_bed_occupancy_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    bed_id TEXT NOT NULL REFERENCES ipd_beds(id) ON DELETE CASCADE,
    admission_id TEXT REFERENCES ipd_admissions(id) ON DELETE SET NULL,
    patient_id TEXT REFERENCES patients(id) ON DELETE SET NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    event_type TEXT NOT NULL,
    reason TEXT,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ipd_bed_events_bed ON ipd_bed_occupancy_events(bed_id, created_at);

-- 5. IPD Admission Events (ADT History Preserving Source Location & Care Team)
CREATE TABLE IF NOT EXISTS ipd_admission_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    admission_id TEXT NOT NULL REFERENCES ipd_admissions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    from_ward_id TEXT,
    to_ward_id TEXT,
    from_bed_id TEXT,
    to_bed_id TEXT,
    from_department_id TEXT,
    to_department_id TEXT,
    handover_summary TEXT,
    reason TEXT,
    idempotency_key TEXT,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ipd_admission_events_adm ON ipd_admission_events(admission_id, created_at);

-- 6. IPD Clinical Handover Records
CREATE TABLE IF NOT EXISTS ipd_handover_records (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    admission_id TEXT NOT NULL REFERENCES ipd_admissions(id) ON DELETE CASCADE,
    inpatient_encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    from_team_or_shift TEXT NOT NULL,
    to_team_or_shift TEXT NOT NULL,
    clinical_summary TEXT NOT NULL,
    active_medications_summary TEXT,
    pending_tasks_summary TEXT,
    authored_by TEXT NOT NULL REFERENCES users(id),
    accepted_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. IPD Discharge Summaries & Immutable Versions
CREATE TABLE IF NOT EXISTS ipd_discharge_summaries (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    admission_id TEXT NOT NULL UNIQUE REFERENCES ipd_admissions(id) ON DELETE CASCADE,
    inpatient_encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'signed', 'amended')),
    course_in_hospital TEXT NOT NULL,
    confirmed_diagnoses_json TEXT NOT NULL DEFAULT '[]',
    significant_investigations_json TEXT NOT NULL DEFAULT '[]',
    procedures_performed_json TEXT NOT NULL DEFAULT '[]',
    discharge_medications_json TEXT NOT NULL DEFAULT '[]',
    pending_results_json TEXT NOT NULL DEFAULT '[]',
    follow_up_plan_summary TEXT NOT NULL,
    return_precautions TEXT NOT NULL,
    checklist_completed INTEGER NOT NULL DEFAULT 0,
    missing_sections_json TEXT NOT NULL DEFAULT '[]',
    current_version INTEGER NOT NULL DEFAULT 1,
    signed_by TEXT REFERENCES users(id),
    signed_at TIMESTAMP,
    signature_hash TEXT,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ipd_discharge_summary_versions (
    id TEXT PRIMARY KEY,
    summary_id TEXT NOT NULL REFERENCES ipd_discharge_summaries(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    signature_hash TEXT,
    amendment_reason TEXT,
    authored_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(summary_id, version_number)
);

-- 8. Laboratory Test Catalog
CREATE TABLE IF NOT EXISTS lab_catalog_items (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    loinc_code TEXT,
    category TEXT NOT NULL DEFAULT 'BIOCHEMISTRY',
    specimen_type TEXT NOT NULL DEFAULT 'VENOUS_BLOOD',
    default_unit TEXT NOT NULL,
    reference_range_text TEXT NOT NULL,
    critical_low REAL,
    critical_high REAL,
    collection_instructions TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);

-- 9. Laboratory Orders
CREATE TABLE IF NOT EXISTS lab_orders (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    ordering_practitioner_id TEXT NOT NULL REFERENCES users(id),
    order_number TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'ROUTINE' CHECK (priority IN ('ROUTINE', 'URGENT', 'STAT')),
    clinical_indication TEXT NOT NULL,
    tests_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'ordered' CHECK (status IN (
        'draft', 'ordered', 'accepted', 'specimen_pending', 'collected',
        'received_by_lab', 'in_progress', 'preliminary', 'final',
        'cancelled', 'rejected', 'unable_to_perform', 'corrected'
    )),
    external_lis_connector_id TEXT REFERENCES integration_connectors(id) ON DELETE SET NULL,
    external_lis_order_id TEXT,
    external_lis_status TEXT,
    cancellation_reason TEXT,
    idempotency_key TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, order_number),
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_lab_orders_fac_status ON lab_orders(organization_id, facility_id, status);
CREATE INDEX IF NOT EXISTS idx_lab_orders_patient ON lab_orders(organization_id, patient_id);

-- 10. Laboratory Specimens & Chain-of-Custody Events
CREATE TABLE IF NOT EXISTS lab_specimens (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    order_id TEXT NOT NULL REFERENCES lab_orders(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    specimen_code TEXT NOT NULL,
    specimen_type TEXT NOT NULL,
    collection_site TEXT,
    container_type TEXT,
    collected_by TEXT NOT NULL REFERENCES users(id),
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    received_by TEXT REFERENCES users(id),
    received_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'collected' CHECK (status IN ('collected', 'received', 'rejected')),
    rejection_reason TEXT,
    external_specimen_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lab_specimen_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    specimen_id TEXT NOT NULL REFERENCES lab_specimens(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. Laboratory Results & Versioned Amendments
CREATE TABLE IF NOT EXISTS lab_results (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    order_id TEXT NOT NULL REFERENCES lab_orders(id) ON DELETE CASCADE,
    specimen_id TEXT REFERENCES lab_specimens(id) ON DELETE SET NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    test_code TEXT NOT NULL,
    test_name TEXT NOT NULL,
    loinc_code TEXT,
    result_value TEXT NOT NULL,
    unit TEXT NOT NULL,
    original_external_value TEXT NOT NULL,
    original_external_unit TEXT NOT NULL,
    conversion_method TEXT,
    reference_range TEXT,
    abnormal_flag TEXT NOT NULL DEFAULT 'NORMAL' CHECK (abnormal_flag IN (
        'NORMAL', 'LOW', 'HIGH', 'CRITICAL_LOW', 'CRITICAL_HIGH', 'ABNORMAL'
    )),
    is_critical INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'final' CHECK (status IN ('preliminary', 'final', 'corrected', 'amended')),
    source_type TEXT NOT NULL DEFAULT 'NATIVE_MANUAL_ENTRY' CHECK (source_type IN (
        'NATIVE_MANUAL_ENTRY', 'EXTERNAL_LIS_IMPORT'
    )),
    source_system_id TEXT NOT NULL DEFAULT 'MATAB-NATIVE-LAB',
    external_result_id TEXT,
    performing_lab_name TEXT NOT NULL,
    releasing_practitioner_name TEXT,
    validation_state TEXT NOT NULL DEFAULT 'VALIDATED' CHECK (validation_state IN (
        'VALIDATED', 'FLAGGED_UNIT_OR_CODE_MISMATCH', 'UNVERIFIED_EXTERNAL'
    )),
    validation_warnings_json TEXT NOT NULL DEFAULT '[]',
    acknowledged_by TEXT REFERENCES users(id),
    acknowledged_at TIMESTAMP,
    acknowledgment_notes TEXT,
    idempotency_key TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_lab_results_order ON lab_results(order_id);
CREATE INDEX IF NOT EXISTS idx_lab_results_patient ON lab_results(organization_id, patient_id);

CREATE TABLE IF NOT EXISTS lab_result_versions (
    id TEXT PRIMARY KEY,
    result_id TEXT NOT NULL REFERENCES lab_results(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    result_value TEXT NOT NULL,
    unit TEXT NOT NULL,
    status TEXT NOT NULL,
    amendment_reason TEXT,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(result_id, version_number)
);

-- 12. Structured Hospital Referrals & Consultation Requests
CREATE TABLE IF NOT EXISTS hospital_referrals (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    originating_facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    receiving_facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    receiving_department_id TEXT REFERENCES facility_departments(id) ON DELETE SET NULL,
    external_recipient_organization TEXT,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    source_encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    referring_practitioner_id TEXT NOT NULL REFERENCES users(id),
    receiving_practitioner_id TEXT REFERENCES users(id),
    referral_type TEXT NOT NULL DEFAULT 'INTERNAL_HOSPITAL_CONSULT' CHECK (referral_type IN (
        'INTERNAL_HOSPITAL_CONSULT', 'INTER_BRANCH_REFERRAL', 'EXTERNAL_FACILITY_REFERRAL'
    )),
    priority TEXT NOT NULL DEFAULT 'ROUTINE' CHECK (priority IN ('ROUTINE', 'URGENT', 'EMERGENCY')),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft', 'pending_authorization', 'ready_to_send', 'sent', 'received',
        'accepted', 'declined', 'appointment_pending', 'in_progress',
        'response_received', 'completed', 'cancelled', 'failed_delivery'
    )),
    reason_for_referral TEXT NOT NULL,
    clinical_question TEXT NOT NULL,
    clinical_summary TEXT NOT NULL,
    allergies_and_medications_summary TEXT,
    authorized_attachments_json TEXT NOT NULL DEFAULT '[]',
    consent_reference_id TEXT,
    recipient_info_request_notes TEXT,
    decline_reason TEXT,
    consultation_response_report TEXT,
    closure_outcome TEXT,
    followup_task_id TEXT,
    sent_at TIMESTAMP,
    accepted_at TIMESTAMP,
    completed_at TIMESTAMP,
    idempotency_key TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_hospital_referrals_org_status ON hospital_referrals(organization_id, status);

CREATE TABLE IF NOT EXISTS hospital_referral_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    referral_id TEXT NOT NULL REFERENCES hospital_referrals(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. Versioned Terminology & Code Mappings
CREATE TABLE IF NOT EXISTS terminology_mappings (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    concept_domain TEXT NOT NULL CHECK (concept_domain IN (
        'LAB_TEST', 'UNIT_OF_MEASURE', 'DIAGNOSIS_PROBLEM', 'CLINICAL_FINDING',
        'UNANI_CONCEPT', 'MEDICATION_FORMULATION'
    )),
    local_code TEXT NOT NULL,
    local_display TEXT NOT NULL,
    target_system_uri TEXT NOT NULL,
    target_version TEXT NOT NULL DEFAULT '2026.1',
    target_code TEXT,
    target_display TEXT,
    equivalence_level TEXT NOT NULL DEFAULT 'EQUIVALENT' CHECK (equivalence_level IN (
        'EQUIVALENT', 'WIDER', 'NARROWER', 'INEXACT_LOSSY', 'UNMAPPED'
    )),
    lossiness_note TEXT,
    mapping_version TEXT NOT NULL DEFAULT 'MAP-FHIR-R4-2026.1',
    is_reviewed INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, concept_domain, local_code, target_system_uri)
);

-- 14. External Identifier Mappings (ABHA, HFR, HPR, External LIS IDs)
CREATE TABLE IF NOT EXISTS external_id_mappings (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('PATIENT', 'PRACTITIONER', 'FACILITY', 'ORGANIZATION')),
    local_entity_id TEXT NOT NULL,
    external_system_uri TEXT NOT NULL,
    external_identifier TEXT NOT NULL,
    is_verified INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, external_system_uri, external_identifier)
);

-- 15. Data-Sharing & Exchange Consents (Purpose- & Scope-Aware)
CREATE TABLE IF NOT EXISTS data_sharing_consents (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    purpose_code TEXT NOT NULL DEFAULT 'CAREMGT' CHECK (purpose_code IN (
        'CAREMGT', 'BTG', 'PUBHLTH', 'PATRQT', 'REFERRAL_EXCHANGE'
    )),
    requester_name TEXT NOT NULL,
    recipient_name TEXT NOT NULL,
    allowed_hi_types_json TEXT NOT NULL DEFAULT '["OPConsultation","Prescription","DiagnosticReport","DischargeSummary"]',
    allowed_resource_types_json TEXT NOT NULL DEFAULT '["Patient","Encounter","Observation","DiagnosticReport","MedicationRequest","Composition"]',
    valid_from TIMESTAMP NOT NULL,
    valid_until TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'GRANTED' CHECK (status IN ('GRANTED', 'DENIED', 'REVOKED', 'EXPIRED')),
    external_consent_artifact_id TEXT,
    source_system TEXT NOT NULL DEFAULT 'MATAB-CONSENT-LEDGER',
    revocation_reason TEXT,
    revoked_at TIMESTAMP,
    recorded_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_data_sharing_consents_patient ON data_sharing_consents(organization_id, patient_id, status);

-- 16. Interoperability Jobs & Dead-Letter Queue
CREATE TABLE IF NOT EXISTS interop_jobs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    connector_id TEXT REFERENCES integration_connectors(id) ON DELETE SET NULL,
    job_type TEXT NOT NULL CHECK (job_type IN (
        'FHIR_VALIDATE', 'FHIR_EXPORT', 'FHIR_IMPORT',
        'LIS_ORDER_DISPATCH', 'LIS_RESULT_IMPORT',
        'ABDM_CARE_CONTEXT_LINK', 'ABDM_CONSENT_NOTIFY', 'ABDM_HI_TRANSFER'
    )),
    direction TEXT NOT NULL CHECK (direction IN ('INBOUND', 'OUTBOUND', 'INTERNAL_VALIDATION')),
    target_profile TEXT NOT NULL DEFAULT 'HL7-FHIR-R4-CORE',
    fhir_version TEXT NOT NULL DEFAULT '4.0.1',
    mapping_version TEXT NOT NULL DEFAULT 'MAP-FHIR-R4-2026.1',
    patient_id TEXT REFERENCES patients(id) ON DELETE SET NULL,
    consent_id TEXT REFERENCES data_sharing_consents(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'processing', 'succeeded', 'failed_retryable', 'dead_letter', 'rejected_validation'
    )),
    attempt_count INTEGER NOT NULL DEFAULT 1,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    idempotency_key TEXT,
    correlation_id TEXT NOT NULL,
    payload_hash_sha256 TEXT NOT NULL,
    summary_metadata_json TEXT NOT NULL DEFAULT '{}',
    validation_issues_json TEXT NOT NULL DEFAULT '[]',
    lossy_warnings_json TEXT NOT NULL DEFAULT '[]',
    error_code TEXT,
    error_message TEXT,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_interop_jobs_org_status ON interop_jobs(organization_id, status);

-- 17. ABDM Exchange & Callback Verification Traces
CREATE TABLE IF NOT EXISTS abdm_exchange_traces (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    request_id TEXT NOT NULL,
    abdm_flow_type TEXT NOT NULL CHECK (abdm_flow_type IN (
        'CARE_CONTEXT_LINK', 'CONSENT_NOTIFY', 'HEALTH_INFO_REQUEST', 'CALLBACK_VERIFICATION'
    )),
    participant_role TEXT NOT NULL DEFAULT 'HIP' CHECK (participant_role IN ('HIP', 'HIU')),
    patient_id TEXT REFERENCES patients(id) ON DELETE SET NULL,
    consent_artifact_id TEXT,
    cm_id TEXT NOT NULL DEFAULT 'sbx',
    signature_verified INTEGER NOT NULL DEFAULT 0,
    readiness_mode TEXT NOT NULL DEFAULT 'CONTRACT_TEST_HARNESS' CHECK (readiness_mode IN (
        'CONTRACT_TEST_HARNESS', 'EXTERNAL_SANDBOX', 'PRODUCTION'
    )),
    status TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, request_id)
);

-- Phase 11 Schema: Multi-Doctor, Multi-Branch & Hospital Administration Foundation
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Organization Extended Profiles & Hierarchy Governance
CREATE TABLE IF NOT EXISTS organization_profiles (
    organization_id TEXT PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
    parent_organization_id TEXT REFERENCES organizations(id) ON DELETE RESTRICT,
    lifecycle_status TEXT NOT NULL DEFAULT 'active' CHECK (
        lifecycle_status IN ('setup', 'active', 'suspended', 'archived')
    ),
    legal_name TEXT,
    tax_registration_number TEXT,
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    default_language TEXT NOT NULL DEFAULT 'en',
    deployment_mode TEXT NOT NULL DEFAULT 'SHARED_MULTITENANT' CHECK (
        deployment_mode IN ('SHARED_MULTITENANT', 'DEDICATED_TENANT', 'ON_PREMISE')
    ),
    cross_facility_continuity_policy TEXT NOT NULL DEFAULT 'SAME_ORG_TREATMENT_TEAM' CHECK (
        cross_facility_continuity_policy IN ('SAME_ORG_TREATMENT_TEAM', 'EXPLICIT_CONSENT_REQUIRED', 'FACILITY_ISOLATED')
    ),
    org_admin_clinical_note_access INTEGER NOT NULL DEFAULT 0,
    parent_reporting_enabled INTEGER NOT NULL DEFAULT 0,
    suspension_reason TEXT,
    suspended_at TIMESTAMP,
    archived_at TIMESTAMP,
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (organization_id != parent_organization_id)
);

CREATE INDEX IF NOT EXISTS idx_org_profiles_parent ON organization_profiles(parent_organization_id, lifecycle_status);

CREATE TABLE IF NOT EXISTS organization_lifecycle_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    downstream_impact_summary_json TEXT,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_org_lifecycle_org ON organization_lifecycle_events(organization_id, created_at);

-- 2. Facility Extended Profiles & Lifecycle History
CREATE TABLE IF NOT EXISTS facility_profiles (
    facility_id TEXT PRIMARY KEY REFERENCES facilities(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_type TEXT NOT NULL DEFAULT 'MATAB' CHECK (
        facility_type IN ('MATAB', 'MULTI_DOCTOR_CLINIC', 'BRANCH_CLINIC', 'HOSPITAL_OPD', 'HOSPITAL')
    ),
    lifecycle_status TEXT NOT NULL DEFAULT 'active' CHECK (
        lifecycle_status IN ('setup', 'active', 'temporarily_closed', 'suspended', 'archived')
    ),
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    city TEXT,
    state_province TEXT,
    postal_code TEXT,
    country TEXT NOT NULL DEFAULT 'IN',
    emergency_contact_phone TEXT,
    operating_hours_json TEXT NOT NULL DEFAULT '{}',
    suspension_reason TEXT,
    suspended_at TIMESTAMP,
    archived_at TIMESTAMP,
    activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fac_profiles_org_status ON facility_profiles(organization_id, lifecycle_status);

CREATE TABLE IF NOT EXISTS facility_lifecycle_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    affected_appointments_count INTEGER NOT NULL DEFAULT 0,
    affected_tasks_count INTEGER NOT NULL DEFAULT 0,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fac_lifecycle_fac ON facility_lifecycle_events(facility_id, created_at);

-- 3. Departments / Services, Units / Teams, and Rooms / Resources
CREATE TABLE IF NOT EXISTS facility_departments (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    department_type TEXT NOT NULL DEFAULT 'UNANI_OPD' CHECK (
        department_type IN (
            'UNANI_OPD', 'GENERAL_OPD', 'SPECIALTY_CLINIC', 'PHARMACY_DISPENSARY',
            'LABORATORY', 'IMAGING', 'EMERGENCY', 'ADMINISTRATION', 'REGIMENAL_THERAPY'
        )
    ),
    head_practitioner_id TEXT REFERENCES users(id),
    required_module_key TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('setup', 'active', 'inactive', 'archived')
    ),
    is_operational INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, code)
);

CREATE INDEX IF NOT EXISTS idx_fac_depts_fac ON facility_departments(organization_id, facility_id, status);

CREATE TABLE IF NOT EXISTS department_units (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    department_id TEXT NOT NULL REFERENCES facility_departments(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(department_id, code)
);

CREATE TABLE IF NOT EXISTS facility_rooms (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    department_id TEXT REFERENCES facility_departments(id) ON DELETE SET NULL,
    room_code TEXT NOT NULL,
    name TEXT NOT NULL,
    room_type TEXT NOT NULL DEFAULT 'CONSULTATION_CHAMBER' CHECK (
        room_type IN ('CONSULTATION_CHAMBER', 'PROCEDURE_ROOM', 'DISPENSARY_COUNTER', 'WAITING_AREA', 'WARD_ROOM', 'LAB_COLLECTION')
    ),
    capacity INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'maintenance', 'archived')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, room_code)
);

-- 4. Scoped Staff & Practitioner Assignments (Facility / Department / Role / Effective Window)
CREATE TABLE IF NOT EXISTS staff_assignments (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE, -- NULL only when scope_level = 'ORGANIZATION'
    department_id TEXT REFERENCES facility_departments(id) ON DELETE SET NULL,
    unit_id TEXT REFERENCES department_units(id) ON DELETE SET NULL,
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    role_code TEXT NOT NULL,
    scope_level TEXT NOT NULL DEFAULT 'FACILITY' CHECK (
        scope_level IN ('ORGANIZATION', 'FACILITY', 'DEPARTMENT')
    ),
    assignment_type TEXT NOT NULL DEFAULT 'PRIMARY' CHECK (
        assignment_type IN ('PRIMARY', 'SECONDARY_BRANCH', 'LOCUM_TEMPORARY', 'VISITING_CONSULTANT')
    ),
    employment_status TEXT NOT NULL DEFAULT 'FULL_TIME' CHECK (
        employment_status IN ('FULL_TIME', 'PART_TIME', 'CONTRACT_LOCUM', 'VISITING', 'SEPARATED')
    ),
    extra_permissions_json TEXT NOT NULL DEFAULT '[]',
    restricted_permissions_json TEXT NOT NULL DEFAULT '[]',
    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    effective_until TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('pending_approval', 'active', 'suspended', 'revoked', 'expired', 'transferred')
    ),
    approved_by TEXT REFERENCES users(id),
    approved_at TIMESTAMP,
    revoked_by TEXT REFERENCES users(id),
    revoked_at TIMESTAMP,
    revocation_reason TEXT,
    transferred_to_assignment_id TEXT,
    notes TEXT,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_staff_assign_user_org ON staff_assignments(user_id, organization_id, status);
CREATE INDEX IF NOT EXISTS idx_staff_assign_fac ON staff_assignments(organization_id, facility_id, status);

-- 5. Layered Configuration Inheritance & Version History
CREATE TABLE IF NOT EXISTS configuration_policies (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    department_id TEXT REFERENCES facility_departments(id) ON DELETE CASCADE,
    scope_level TEXT NOT NULL CHECK (scope_level IN ('ORGANIZATION', 'FACILITY', 'DEPARTMENT')),
    config_json TEXT NOT NULL DEFAULT '{}',
    current_version INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_config_policies_scope ON configuration_policies(organization_id, facility_id, scope_level);

CREATE TABLE IF NOT EXISTS configuration_versions (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES configuration_policies(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    scope_level TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    change_reason TEXT NOT NULL,
    changed_by TEXT NOT NULL REFERENCES users(id),
    rolled_back_from_version INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(policy_id, version_number)
);

-- 6. Module Entitlements & Feature Flags (Per Facility)
CREATE TABLE IF NOT EXISTS facility_module_entitlements (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    module_key TEXT NOT NULL CHECK (
        module_key IN (
            'clinical_core',
            'unani_assessment',
            'modern_assessment',
            'knowledge_retrieval',
            'safety_firewall',
            'appointments_queue',
            'billing',
            'pharmacy_inventory',
            'followup_continuity',
            'hospital_modules',
            'integrations_reporting'
        )
    ),
    is_enabled INTEGER NOT NULL DEFAULT 1,
    readiness_status TEXT NOT NULL DEFAULT 'FUNCTIONALLY_TESTED',
    prerequisites_json TEXT NOT NULL DEFAULT '[]',
    last_health_check_status TEXT NOT NULL DEFAULT 'PASS',
    last_health_check_detail TEXT,
    updated_by TEXT REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(facility_id, module_key)
);

CREATE INDEX IF NOT EXISTS idx_fac_modules_lookup ON facility_module_entitlements(organization_id, facility_id, module_key);

-- 7. Patient Cross-Facility Continuity Links & Governed Merge Workflow
CREATE TABLE IF NOT EXISTS patient_facility_links (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    local_facility_mrn TEXT NOT NULL,
    registration_source TEXT NOT NULL DEFAULT 'OPD_REGISTRATION',
    care_team_department_id TEXT REFERENCES facility_departments(id) ON DELETE SET NULL,
    primary_practitioner_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    privacy_restriction_level TEXT NOT NULL DEFAULT 'STANDARD' CHECK (
        privacy_restriction_level IN ('STANDARD', 'RESTRICTED_BRANCH_ONLY', 'CONFIDENTIAL')
    ),
    cross_facility_consent_granted INTEGER NOT NULL DEFAULT 1,
    consent_reference_id TEXT,
    is_merged_redirect INTEGER NOT NULL DEFAULT 0,
    merged_into_patient_id TEXT REFERENCES patients(id),
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT REFERENCES users(id),
    UNIQUE(patient_id, facility_id),
    UNIQUE(facility_id, local_facility_mrn)
);

CREATE INDEX IF NOT EXISTS idx_pat_fac_links_pat ON patient_facility_links(organization_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_pat_fac_links_fac ON patient_facility_links(organization_id, facility_id);

CREATE TABLE IF NOT EXISTS patient_merge_requests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    source_patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    target_patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'pending_review' CHECK (
        status IN ('pending_review', 'approved_merged', 'rejected')
    ),
    match_evidence_json TEXT NOT NULL DEFAULT '{}',
    request_reason TEXT NOT NULL,
    requested_by TEXT NOT NULL REFERENCES users(id),
    reviewed_by TEXT REFERENCES users(id),
    review_notes TEXT,
    merged_records_summary_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    CHECK (source_patient_id != target_patient_id)
);

CREATE TABLE IF NOT EXISTS patient_merge_events (
    id TEXT PRIMARY KEY,
    merge_request_id TEXT NOT NULL REFERENCES patient_merge_requests(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    source_patient_id TEXT NOT NULL,
    target_patient_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    affected_table TEXT NOT NULL,
    affected_record_id TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. Inter-Facility Transfers & Referrals
CREATE TABLE IF NOT EXISTS facility_transfers (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    target_organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    originating_facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    receiving_facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    receiving_department_id TEXT REFERENCES facility_departments(id) ON DELETE SET NULL,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE RESTRICT,
    source_encounter_id TEXT REFERENCES encounters(id) ON DELETE RESTRICT,
    destination_encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    referring_practitioner_id TEXT NOT NULL REFERENCES users(id),
    receiving_practitioner_id TEXT REFERENCES users(id),
    transfer_type TEXT NOT NULL DEFAULT 'INTERNAL_BRANCH_REFERRAL' CHECK (
        transfer_type IN ('INTERNAL_BRANCH_REFERRAL', 'SPECIALTY_ESCALATION', 'EMERGENCY_TRANSFER', 'CROSS_ORG_EXTERNAL')
    ),
    urgency TEXT NOT NULL DEFAULT 'ROUTINE' CHECK (
        urgency IN ('ROUTINE', 'PRIORITY', 'URGENT', 'EMERGENCY')
    ),
    status TEXT NOT NULL DEFAULT 'requested' CHECK (
        status IN ('draft', 'requested', 'accepted', 'declined', 'in_transit', 'arrived', 'completed', 'cancelled')
    ),
    reason_for_transfer TEXT NOT NULL,
    minimum_clinical_summary TEXT NOT NULL,
    authorized_attachments_json TEXT NOT NULL DEFAULT '[]',
    consent_basis TEXT NOT NULL DEFAULT 'TREATMENT_CONTINUITY',
    acceptance_notes TEXT,
    decline_reason TEXT,
    completion_outcome_summary TEXT,
    missing_information_notes TEXT,
    idempotency_key TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accepted_at TIMESTAMP,
    declined_at TIMESTAMP,
    arrived_at TIMESTAMP,
    completed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (originating_facility_id != receiving_facility_id)
);

CREATE INDEX IF NOT EXISTS idx_transfers_org_orig ON facility_transfers(organization_id, originating_facility_id, status);
CREATE INDEX IF NOT EXISTS idx_transfers_org_recv ON facility_transfers(organization_id, receiving_facility_id, status);
CREATE INDEX IF NOT EXISTS idx_transfers_patient ON facility_transfers(organization_id, patient_id);

CREATE TABLE IF NOT EXISTS facility_transfer_events (
    id TEXT PRIMARY KEY,
    transfer_id TEXT NOT NULL REFERENCES facility_transfers(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    actor_facility_id TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. Hospital Integration Registry & Secret Reference Boundaries
CREATE TABLE IF NOT EXISTS integration_connectors (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    connector_type TEXT NOT NULL CHECK (
        connector_type IN (
            'ABDM_ABHA', 'FHIR_R4_ENDPOINT', 'LIS_LAB', 'PACS_IMAGING',
            'INSURANCE_BILLING', 'PHARMACY_ERP', 'SMS_WHATSAPP_GATEWAY',
            'OIDC_SSO', 'ACCOUNTING_EXPORT'
        )
    ),
    name TEXT NOT NULL,
    environment TEXT NOT NULL DEFAULT 'SANDBOX' CHECK (
        environment IN ('DEVELOPMENT', 'SANDBOX', 'PRODUCTION')
    ),
    lifecycle_state TEXT NOT NULL DEFAULT 'CONFIGURED_NOT_CONNECTED' CHECK (
        lifecycle_state IN (
            'CONFIGURED_NOT_CONNECTED',
            'CONNECTED_UNVERIFIED',
            'SANDBOX_TESTED',
            'PRODUCTION_ACTIVE',
            'DISABLED',
            'ERROR'
        )
    ),
    endpoint_url TEXT,
    api_version TEXT DEFAULT 'v1',
    secret_ref_uri TEXT, -- Reference URI in Secrets Manager (NEVER plaintext secret)
    allowed_scopes_json TEXT NOT NULL DEFAULT '[]',
    retry_policy_json TEXT NOT NULL DEFAULT '{"max_retries":3,"backoff_seconds":5}',
    data_sharing_policy_ref TEXT,
    last_verified_at TIMESTAMP,
    last_health_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    last_error_message TEXT,
    updated_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_integrations_org_fac ON integration_connectors(organization_id, facility_id, connector_type);

-- 10. Time-Bound Platform Support Access & Single-Clinic Migration Runs
CREATE TABLE IF NOT EXISTS support_access_grants (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT REFERENCES facilities(id) ON DELETE CASCADE,
    support_user_id TEXT NOT NULL REFERENCES users(id),
    approved_by_user_id TEXT NOT NULL REFERENCES users(id),
    reason_ticket_ref TEXT NOT NULL,
    allow_clinical_phi_read INTEGER NOT NULL DEFAULT 0, -- Must default to 0; support is NOT a clinical superuser
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'revoked')),
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS single_clinic_migration_runs (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    default_facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('DRY_RUN', 'EXECUTE', 'VERIFY_ROLLBACK')),
    status TEXT NOT NULL CHECK (status IN ('COMPLETED', 'REMEDIATION_REQUIRED', 'ROLLED_BACK')),
    pre_counts_json TEXT NOT NULL,
    post_counts_json TEXT NOT NULL,
    orphans_detected_json TEXT NOT NULL DEFAULT '[]',
    backup_reference TEXT,
    executed_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

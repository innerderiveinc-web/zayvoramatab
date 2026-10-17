-- ============================================================================
-- Migration 029: Enterprise Security, Privacy, Consent & Identity Access Governance
-- Phase 30: ZAYVORA MATAB OS
-- ============================================================================

-- 1. Unified Security Principals
CREATE TABLE IF NOT EXISTS security_principals (
    id TEXT PRIMARY KEY,
    principal_type TEXT NOT NULL, -- 'human', 'service_account', 'integration_client'
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    tenant_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    account_state TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'SUSPENDED', 'OFFBOARDED', 'LOCKED'
    is_mfa_enforced INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_principals_lookup ON security_principals(tenant_id, account_state);

-- 2. Enhanced User Sessions (with step-up auth, device context, remote logout)
CREATE TABLE IF NOT EXISTS user_sessions (
    id TEXT PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    active_facility_id TEXT,
    ip_address TEXT,
    user_agent TEXT,
    device_fingerprint TEXT,
    step_up_verified_at TIMESTAMP,
    step_up_scope TEXT,
    expires_at TIMESTAMP NOT NULL,
    idle_timeout_at TIMESTAMP NOT NULL,
    is_revoked INTEGER NOT NULL DEFAULT 0,
    revoked_at TIMESTAMP,
    revocation_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_lookup ON user_sessions(user_id, is_revoked);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token);

-- 3. Clinician Professional Credential Registry
CREATE TABLE IF NOT EXISTS clinician_credential_registry (
    id TEXT PRIMARY KEY,
    practitioner_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_type TEXT NOT NULL, -- 'BUMS', 'MD_UNANI', 'MBBS', 'AYUSH_REGISTRATION', 'PHARMACY_LICENSE'
    registration_number TEXT NOT NULL,
    issuing_council TEXT NOT NULL,
    jurisdiction TEXT NOT NULL DEFAULT 'INDIA',
    verification_source TEXT NOT NULL, -- 'STATE_COUNCIL_PORTAL', 'NATIONAL_COMMISSION_INDIAN_SYSTEM_MEDICINE', 'MANUAL_DOCUMENT_AUDIT'
    verification_status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'verified', 'expired', 'suspended', 'restricted', 'revoked', 'unknown'
    verified_at TIMESTAMP,
    verified_by TEXT REFERENCES users(id),
    effective_date TEXT NOT NULL,
    expiry_date TEXT,
    approved_scope TEXT DEFAULT 'FULL_CLINICAL_UNANI',
    restriction_notes TEXT,
    evidence_reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clinician_credentials_lookup ON clinician_credential_registry(practitioner_user_id, verification_status);

-- 4. Governed Consent & Authority Records
CREATE TABLE IF NOT EXISTS consent_authority_records (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    consent_type TEXT NOT NULL, -- 'TREATMENT_GENERAL', 'DATA_SHARING_REFERRAL', 'TELECONSULTATION', 'RESEARCH_OBSERVATIONAL', 'COMMUNICATION_CHANNELS', 'REPRESENTATIVE_AUTHORITY'
    purpose_code TEXT NOT NULL,
    data_categories_json TEXT NOT NULL DEFAULT '["demographics","clinical_records"]',
    recipient_scope TEXT NOT NULL DEFAULT 'INTERNAL_FACILITY',
    channel TEXT NOT NULL DEFAULT 'IN_PERSON_CLINIC',
    language_code TEXT NOT NULL DEFAULT 'en',
    notice_version TEXT NOT NULL DEFAULT 'v2026.1',
    status TEXT NOT NULL DEFAULT 'granted', -- 'draft', 'presented', 'granted', 'refused', 'withdrawn', 'expired', 'superseded', 'under_review'
    granting_party_type TEXT NOT NULL DEFAULT 'PATIENT_DIRECT', -- 'PATIENT_DIRECT', 'LEGAL_GUARDIAN', 'DESIGNATED_REPRESENTATIVE'
    granting_party_name TEXT,
    authority_evidence_ref TEXT,
    effective_from TIMESTAMP NOT NULL,
    valid_until TIMESTAMP,
    withdrawn_at TIMESTAMP,
    withdrawn_by TEXT REFERENCES users(id),
    withdrawal_reason TEXT,
    collected_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_consent_authority_lookup ON consent_authority_records(patient_id, consent_type, status);

-- 5. Delegated Temporary Access Grants
CREATE TABLE IF NOT EXISTS delegated_access_grants (
    id TEXT PRIMARY KEY,
    grantor_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    delegatee_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT,
    target_resource_type TEXT NOT NULL, -- 'PATIENT', 'ENCOUNTER', 'ALL_PATIENTS_FACILITY'
    target_resource_id TEXT,
    allowed_actions_json TEXT NOT NULL DEFAULT '["read","create_draft"]',
    purpose TEXT NOT NULL,
    starts_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'EXPIRED', 'REVOKED'
    revoked_at TIMESTAMP,
    revoked_by TEXT REFERENCES users(id),
    revocation_reason TEXT,
    approval_ref TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_delegated_grants_lookup ON delegated_access_grants(delegatee_user_id, status);

-- 6. Emergency Break-Glass Events
CREATE TABLE IF NOT EXISTS break_glass_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    facility_id TEXT,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    reason_code TEXT NOT NULL, -- 'ACUTE_LIFE_THREATENING_EMERGENCY', 'UNRESPONSIVE_PATIENT_NO_CONSENT', 'CRITICAL_ALLERGY_CHECK', 'DISASTER_RESPONSE'
    rationale TEXT NOT NULL,
    granted_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'EXPIRED', 'REVOKED', 'REVIEWED_JUSTIFIED', 'REVIEWED_ABUSE'
    access_count INTEGER NOT NULL DEFAULT 0,
    accessed_resources_json TEXT DEFAULT '[]',
    post_review_by TEXT REFERENCES users(id),
    post_reviewed_at TIMESTAMP,
    post_review_decision TEXT,
    post_review_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_break_glass_lookup ON break_glass_events(user_id, patient_id, status);

-- 7. Access Review Campaigns & Decisions (Periodic Recertification)
CREATE TABLE IF NOT EXISTS access_review_campaigns (
    id TEXT PRIMARY KEY,
    campaign_code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    scope_type TEXT NOT NULL, -- 'CLINICAL_ROLES', 'PRIVILEGED_ADMINS', 'SERVICE_ACCOUNTS', 'FACILITY_MEMBERSHIPS'
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'COMPLETED', 'CANCELLED'
    due_date TEXT NOT NULL,
    created_by TEXT NOT NULL REFERENCES users(id),
    completed_at TIMESTAMP,
    summary_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS access_review_decisions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES access_review_campaigns(id) ON DELETE CASCADE,
    subject_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_or_permission TEXT NOT NULL,
    reviewer_id TEXT NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL, -- 'RETAIN', 'MODIFY', 'REVOKE', 'INVESTIGATE', 'EXCEPTION_APPROVED'
    rationale TEXT NOT NULL,
    remediation_action TEXT,
    remediation_status TEXT NOT NULL DEFAULT 'PENDING', -- 'PENDING', 'EXECUTED', 'WAIVED'
    decided_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_access_review_decisions ON access_review_decisions(campaign_id, subject_user_id);

-- 8. Versioned Security Policy Registry
CREATE TABLE IF NOT EXISTS security_policy_registry (
    id TEXT PRIMARY KEY,
    policy_code TEXT NOT NULL UNIQUE,
    policy_version TEXT NOT NULL DEFAULT 'v1.0',
    title TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    action TEXT NOT NULL,
    effect TEXT NOT NULL DEFAULT 'ALLOW', -- 'ALLOW', 'DENY'
    priority INTEGER NOT NULL DEFAULT 100, -- lower number = higher precedence
    conditions_json TEXT NOT NULL DEFAULT '{}',
    reason_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE', -- 'DRAFT', 'REVIEW', 'ACTIVE', 'SUSPENDED', 'RETIRED'
    owner_role TEXT NOT NULL DEFAULT 'SECURITY_OFFICER',
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_security_policy_lookup ON security_policy_registry(resource_type, action, status);

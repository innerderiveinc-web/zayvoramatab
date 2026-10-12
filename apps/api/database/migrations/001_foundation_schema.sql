-- Phase 1 Foundation Schema: Tenancy, Identity, RBAC, Audit, and Capability Registry
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 1. Organizations & Facilities (Tenancy)
CREATE TABLE IF NOT EXISTS organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    license_number TEXT,
    profile_type TEXT NOT NULL DEFAULT 'MATAB', -- 'MATAB', 'CLINIC', 'HOSPITAL'
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS facilities (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    address TEXT,
    phone TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, code)
);

CREATE INDEX IF NOT EXISTS idx_facilities_org ON facilities(organization_id, is_active);

-- 2. Users & Practitioner Profiles
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    username TEXT NOT NULL UNIQUE,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_org ON users(organization_id, is_active);

CREATE TABLE IF NOT EXISTS practitioner_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    license_type TEXT NOT NULL DEFAULT 'BUMS', -- 'BUMS', 'MD_UNANI', 'MBBS', 'OTHER'
    registration_number TEXT,
    registration_council TEXT,
    is_credential_verified INTEGER NOT NULL DEFAULT 0, -- Do not claim verified in foundation
    digital_signature_pin_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Roles and Permissions (RBAC)
CREATE TABLE IF NOT EXISTS roles (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- 'ORG_ADMIN', 'CLINIC_ADMIN', 'PRACTITIONER', 'RECEPTIONIST', 'PHARMACIST', 'NURSE', 'READ_ONLY_AUDITOR'
    name TEXT NOT NULL,
    description TEXT,
    is_system_role INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE, -- e.g. 'users:read', 'users:write', 'audit:read', 'encounters:read'
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id TEXT NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY(role_id, permission_id)
);

-- 4. Memberships (User to Org and User to Facility)
CREATE TABLE IF NOT EXISTS user_organization_memberships (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, organization_id)
);

CREATE TABLE IF NOT EXISTS user_facility_memberships (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    facility_id TEXT NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, facility_id)
);

CREATE INDEX IF NOT EXISTS idx_user_fac_mem ON user_facility_memberships(user_id, facility_id, is_active);

-- 5. Sessions & Password Resets
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    active_facility_id TEXT REFERENCES facilities(id),
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS password_resets (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reset_token_hash TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_consumed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. Audit Events (Append-Only)
CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    organization_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
    facility_id TEXT REFERENCES facilities(id) ON DELETE SET NULL,
    actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    action_type TEXT NOT NULL,
    target_entity_type TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'SUCCESS', -- 'SUCCESS', 'DENIED', 'FAILURE'
    reason_code TEXT,
    request_id TEXT NOT NULL,
    client_ip TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_org_time ON audit_events(organization_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_req ON audit_events(request_id);

-- 7. Capability / Feature Registry
CREATE TABLE IF NOT EXISTS capability_registry (
    engine_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    status TEXT NOT NULL, -- 'NOT_IMPLEMENTED', 'IMPLEMENTED_NOT_CONNECTED', 'CONNECTED_NOT_VALIDATED', 'FUNCTIONALLY_TESTED', 'CLINICALLY_REVIEWED', 'PILOT_APPROVED', 'PRODUCTION_APPROVED', 'DISABLED_OR_DEGRADED'
    is_enabled INTEGER NOT NULL DEFAULT 1,
    health_reason TEXT,
    required_permission TEXT,
    last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

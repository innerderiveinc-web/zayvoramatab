"""Synthetic Development Seeder for ZAYVORA MATAB OS.
Enforces non-production execution safeguard. All generated accounts are strictly synthetic.
"""

import sys
from datetime import datetime
from apps.api.config import config
from apps.api.database.connection import DatabaseConnection

def hash_seed_password(pw: str) -> str:
    # Deterministic PBKDF2 calculation for 'matab123'
    # matches: pbkdf2:sha256:10000$saltmatab$cfcfe0609a07d21882e815afe9d739d83223c87c3766546d5a656da687629707
    return "pbkdf2:sha256:10000$saltmatab$cfcfe0609a07d21882e815afe9d739d83223c87c3766546d5a656da687629707"

def seed_development_data(db_path: str = None) -> None:
    """Seed synthetic development organizations, facilities, roles, users, and capability registry."""
    if config.is_production():
        raise RuntimeError("CRITICAL ERROR: Seed command is prohibited in PRODUCTION environment.")

    manager = DatabaseConnection(db_path or config.db_path)
    conn = manager.get_connection()
    try:
        print("[SEED] Starting synthetic development data seeding...")
        
        # 1. Demo Organization
        conn.execute("""
            INSERT OR REPLACE INTO organizations (id, name, code, license_number, profile_type, is_active)
            VALUES ('org-matab-default', 'ZAYVORA Matab Dawakhana (Synthetic Dev Org)', 'ZMD-001', 'AYUSH/DEV/2026/SYNTHETIC', 'MATAB', 1);
        """)

        # 2. Two Facilities for Multi-Facility testing
        conn.execute("""
            INSERT OR REPLACE INTO facilities (id, organization_id, name, code, address, phone, is_active)
            VALUES 
            ('fac-central-opd', 'org-matab-default', 'Central Matab OPD [Synthetic]', 'OPD-1', '101 Dawakhana Chowk, Delhi', '+91-9800000001', 1),
            ('fac-south-branch', 'org-matab-default', 'South Branch Clinic [Synthetic]', 'OPD-2', '45 Nizamuddin West, Delhi', '+91-9800000002', 1);
        """)

        # 3. Standard Roles
        roles_data = [
            ('role-org-admin', 'ORG_ADMIN', 'Organization Administrator', 'Full tenant management and configuration'),
            ('role-clinic-admin', 'CLINIC_ADMIN', 'Clinic Administrator', 'Facility operations and staff assignments'),
            ('role-practitioner', 'PRACTITIONER', 'Licensed Practitioner (Hakeem)', 'Clinical consultation and prescription signing'),
            ('role-receptionist', 'RECEPTIONIST', 'Front Desk Receptionist', 'Patient registration, appointment queuing and tokens'),
            ('role-pharmacist', 'PHARMACIST', 'Dispensary Pharmacist', 'Medication dispensing and stock verification'),
            ('role-nurse', 'NURSE', 'Clinic Nurse / Attendant', 'Vitals recording and patient prep'),
            ('role-auditor', 'READ_ONLY_AUDITOR', 'Read-Only Compliance Auditor', 'Audit log review and compliance inspections')
        ]
        for r_id, code, name, desc in roles_data:
            conn.execute("""
                INSERT OR REPLACE INTO roles (id, code, name, description, is_system_role)
                VALUES (?, ?, ?, ?, 1);
            """, (r_id, code, name, desc))

        # 4. Standard Permissions
        permissions_data = [
            ('perm-org-manage', 'org:manage', 'Manage Organization', 'ORGANIZATION'),
            ('perm-fac-manage', 'facility:manage', 'Manage Facilities', 'FACILITY'),
            ('perm-users-manage', 'users:manage', 'Manage Users & Roles', 'USERS'),
            ('perm-audit-read', 'audit:read', 'Read Security Audit Logs', 'AUDIT'),
            ('perm-caps-read', 'capabilities:read', 'Inspect System Capabilities', 'SYSTEM'),
            ('perm-patients-read', 'patients:read', 'View Patient Demographics', 'CLINICAL'),
            ('perm-patients-write', 'patients:write', 'Register & Edit Patients', 'CLINICAL'),
            ('perm-patient-read', 'patient:read', 'View Patient Record', 'CLINICAL'),
            ('perm-patient-create', 'patient:create', 'Register New Patient', 'CLINICAL'),
            ('perm-patient-update', 'patient:update_demographics', 'Update Patient Demographics', 'CLINICAL'),
            ('perm-patient-dup', 'patient:resolve_duplicate', 'Resolve Duplicate Candidates', 'CLINICAL'),
            ('perm-encounters-read', 'encounters:read', 'View Clinical Encounters', 'CLINICAL'),
            ('perm-encounters-write', 'encounters:write', 'Chart Clinical Encounters', 'CLINICAL'),
            ('perm-encounter-read', 'encounter:read', 'Read Encounter Details', 'CLINICAL'),
            ('perm-encounter-create', 'encounter:create', 'Create New Encounter', 'CLINICAL'),
            ('perm-encounter-update', 'encounter:update_draft', 'Update Draft Encounter', 'CLINICAL'),
            ('perm-encounter-cancel', 'encounter:cancel', 'Cancel Encounter', 'CLINICAL'),
            ('perm-consent-read', 'consent:read', 'View Patient Consents', 'CLINICAL'),
            ('perm-consent-record', 'consent:record', 'Record Patient Consent', 'CLINICAL'),
            ('perm-consent-withdraw', 'consent:withdraw', 'Withdraw Patient Consent', 'CLINICAL'),
            ('perm-prescriptions-sign', 'prescriptions:sign', 'Sign Medical Prescriptions', 'CLINICAL')
        ]
        for p_id, code, name, cat in permissions_data:
            conn.execute("""
                INSERT OR REPLACE INTO permissions (id, code, name, category)
                VALUES (?, ?, ?, ?);
            """, (p_id, code, name, cat))

        # Assign Role Permissions
        # ORG_ADMIN gets all permissions
        for p_id, _, _, _ in permissions_data:
            conn.execute("INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES ('role-org-admin', ?);", (p_id,))
        
        # PRACTITIONER gets clinical, patients, encounters, sign, consent, capabilities:read
        for p_code in [
            'patients:read', 'patients:write', 'patient:read', 'patient:create', 'patient:update_demographics',
            'encounters:read', 'encounters:write', 'encounter:read', 'encounter:create', 'encounter:update_draft', 'encounter:cancel',
            'consent:read', 'consent:record', 'prescriptions:sign', 'capabilities:read'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-practitioner', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # RECEPTIONIST gets patient read/create/update/duplicate, encounter read/create/cancel, consent read/record, capabilities:read
        for p_code in [
            'patients:read', 'patients:write', 'patient:read', 'patient:create', 'patient:update_demographics', 'patient:resolve_duplicate',
            'encounters:read', 'encounter:read', 'encounter:create', 'encounter:cancel',
            'consent:read', 'consent:record', 'capabilities:read'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-receptionist', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # READ_ONLY_AUDITOR gets audit:read, patient:read, encounter:read, consent:read, capabilities:read
        for p_code in ['audit:read', 'patients:read', 'patient:read', 'encounters:read', 'encounter:read', 'consent:read', 'capabilities:read']:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-auditor', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # 5. Synthetic Development Users
        pw_hash = hash_seed_password("matab123")
        users_data = [
            ('usr-admin-1', 'admin', 'admin.synthetic@zayvora.test', pw_hash, '[SYNTHETIC] Admin User', 'role-org-admin'),
            ('usr-hakeem-1', 'hakeem', 'hakeem.synthetic@zayvora.test', pw_hash, '[SYNTHETIC] Hakeem Tariq Ahmad', 'role-practitioner'),
            ('usr-recep-1', 'reception', 'reception.synthetic@zayvora.test', pw_hash, '[SYNTHETIC] Farhan Ali (Front Desk)', 'role-receptionist'),
            ('usr-pharm-1', 'pharmacy', 'pharmacy.synthetic@zayvora.test', pw_hash, '[SYNTHETIC] Bilal Siddiqui (Pharmacist)', 'role-pharmacist'),
            ('usr-auditor-1', 'auditor', 'auditor.synthetic@zayvora.test', pw_hash, '[SYNTHETIC] Compliance Auditor', 'role-auditor')
        ]

        for u_id, username, email, pwh, full_name, role_id in users_data:
            conn.execute("""
                INSERT OR REPLACE INTO users (id, organization_id, username, email, password_hash, full_name, is_active)
                VALUES (?, 'org-matab-default', ?, ?, ?, ?, 1);
            """, (u_id, username, email, pwh, full_name))

            # User Org Membership
            conn.execute("""
                INSERT OR REPLACE INTO user_organization_memberships (id, user_id, organization_id, role_id, is_active)
                VALUES (?, ?, 'org-matab-default', ?, 1);
            """, (f"uom-{u_id}", u_id, role_id))

            # Facility Memberships (Hakeem and Reception belong to fac-central-opd)
            conn.execute("""
                INSERT OR REPLACE INTO user_facility_memberships (id, user_id, facility_id, role_id, is_active)
                VALUES (?, ?, 'fac-central-opd', ?, 1);
            """, (f"ufm-{u_id}-1", u_id, role_id))

        # Practitioner Profile for Hakeem Tariq
        conn.execute("""
            INSERT OR REPLACE INTO practitioner_profiles (id, user_id, license_type, registration_number, registration_council, is_credential_verified, digital_signature_pin_hash)
            VALUES ('prac-hakeem-1', 'usr-hakeem-1', 'BUMS', 'BUMS/DEL/8921/2012', 'Delhi Bharatiya Chikitsa Parishad', 0, '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4');
        """)

        # 6. Synthetic Patients Dataset (Clearly tagged [Synthetic] to avoid production confusion)
        patients_seed = [
            (
                'pat-syn-001', 'org-matab-default', 'fac-central-opd', 'MRN-2026-00001',
                'Muhammad', 'Irfan', 'Muhammad Irfan [Synthetic]', '1985-06-15', None, None,
                'MALE', 'ur', 'ACTIVE', 1, 'usr-recep-1', '+919876543210', '9876543210',
                'DL-991823', 'Old Delhi, Gate 4'
            ),
            (
                'pat-syn-002', 'org-matab-default', 'fac-central-opd', 'MRN-2026-00002',
                'Mohammad', 'Irfan', 'Mohammad Irfan [Synthetic]', None, 41, datetime.utcnow().isoformat(),
                'MALE', 'ur', 'ACTIVE', 1, 'usr-recep-1', '+919876543210', '9876543210',
                None, 'Daryaganj'
            ),
            (
                'pat-syn-003', 'org-matab-default', 'fac-central-opd', 'MRN-2026-00003',
                'فاطمہ', 'زہرا', 'Fatima Zehra (فاطمہ زہرا) [Synthetic]', '1992-11-20', None, None,
                'FEMALE', 'ur', 'ACTIVE', 1, 'usr-recep-1', '+919811223344', '9811223344',
                'ABHA-9912-3841', 'Nizamuddin West'
            ),
            (
                'pat-syn-004', 'org-matab-default', 'fac-central-opd', 'MRN-2026-00004',
                'Abdul', 'Rashid', 'Haji Abdul Rashid [Synthetic]', None, 68, datetime.utcnow().isoformat(),
                'MALE', 'ur', 'ACTIVE', 1, 'usr-recep-1', '+919899001122', '9899001122',
                None, 'Ballimaran, Chandni Chowk'
            )
        ]

        for p_id, o_id, f_id, mrn, gname, fname, dname, dob, eage, arat, sex, lang, st, ver, cby, phone, nphone, nat_id, addr in patients_seed:
            conn.execute("""
                INSERT OR REPLACE INTO patients (
                    id, organization_id, facility_id, mrn, given_name, family_name, display_name,
                    date_of_birth, estimated_age, age_recorded_at, sex, preferred_language, status,
                    version, created_by, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (p_id, o_id, f_id, mrn, gname, fname, dname, dob, eage, arat, sex, lang, st, ver, cby, cby))

            # Phone Contact
            conn.execute("""
                INSERT OR REPLACE INTO patient_contacts (id, patient_id, organization_id, contact_type, contact_value, normalized_value, is_preferred, use)
                VALUES (?, ?, ?, 'PHONE', ?, ?, 1, 'MOBILE');
            """, (f"cnt-{p_id}-1", p_id, o_id, phone, nphone))

            # National Identifier if provided
            if nat_id:
                conn.execute("""
                    INSERT OR REPLACE INTO patient_identifiers (id, patient_id, organization_id, identifier_type, identifier_value, normalized_value, issuer)
                    VALUES (?, ?, ?, 'NATIONAL_ID', ?, ?, 'GOVT');
                """, (f"idn-{p_id}-1", p_id, o_id, nat_id, nat_id.lower().replace("-", "")))

            # Primary Address if provided
            if addr:
                conn.execute("""
                    INSERT OR REPLACE INTO patient_addresses (id, patient_id, organization_id, address_line1, city, is_primary)
                    VALUES (?, ?, ?, ?, 'Delhi', 1);
                """, (f"adr-{p_id}-1", p_id, o_id, addr))

            # Initial General Care Consent
            conn.execute("""
                INSERT OR REPLACE INTO patient_consents (id, patient_id, organization_id, purpose, status, policy_version, source_method, recorded_by)
                VALUES (?, ?, ?, 'GENERAL_CARE', 'GRANTED', 'v1.0', 'VERBAL_PATIENT', ?);
            """, (f"cns-{p_id}-1", p_id, o_id, cby))

        # 7. Seed Duplicate Candidate Pair (pat-syn-001 and pat-syn-002 share same phone + similar name)
        conn.execute("""
            INSERT OR REPLACE INTO patient_duplicate_candidates (
                id, organization_id, patient_id_a, patient_id_b, match_score, match_rules,
                status, review_notes
            )
            VALUES (
                'dup-pair-001', 'org-matab-default', 'pat-syn-001', 'pat-syn-002', 0.90, 'EXACT_PHONE_MATCH',
                'PENDING_REVIEW', 'Identified identical mobile number 9876543210 during registration'
            );
        """)

        # 8. Seed Synthetic Encounters
        encounters_seed = [
            (
                'enc-syn-001', 'org-matab-default', 'fac-central-opd', 'pat-syn-001', 'usr-hakeem-1',
                1, 'OPD_VISIT', 'IN_PROGRESS', 'Persistent headache and epigastric burning (Sudaa-wa-Hurqat-e-Middah)',
                'usr-hakeem-1'
            ),
            (
                'enc-syn-002', 'org-matab-default', 'fac-central-opd', 'pat-syn-003', 'usr-hakeem-1',
                2, 'OPD_VISIT', 'COMPLETED', 'Routine Unani wellness and Mizaj consultation',
                'usr-hakeem-1'
            ),
            (
                'enc-syn-003', 'org-matab-default', 'fac-central-opd', 'pat-syn-004', 'usr-hakeem-1',
                3, 'FOLLOW_UP', 'DRAFT', 'Follow-up for joint stiffness (Waja-ul-Mafasil)',
                'usr-recep-1'
            )
        ]

        for e_id, o_id, f_id, p_id, prac_id, tok, etype, st, reason, cby in encounters_seed:
            conn.execute("""
                INSERT OR REPLACE INTO encounters (
                    id, organization_id, facility_id, patient_id, practitioner_id, token_number,
                    encounter_type, status, reason_for_visit, version, started_at, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, ?);
            """, (e_id, o_id, f_id, p_id, prac_id, tok, etype, st, reason, cby))

        # 9. Capability Registry (Updated with Phase 2 Clinical Verticals)
        capabilities_seed = [
            ('core.identity', 'Identity and Tenancy Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'users:manage'),
            ('core.tenancy', 'Organization/Facility Scope Filter', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'facility:manage'),
            ('core.rbac', 'Role-Based Access Control Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'users:manage'),
            ('core.audit', 'Append-Only Audit Event Logger', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'audit:read'),
            ('core.capabilities', 'Capability & Engine State Registry', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'capabilities:read'),
            
            # Prompt 02: Core Clinical Workflow (Patient MPI and Encounter Lifecycle)
            ('clinical.patients_mpi', 'Master Patient Index & Demographics Registry', '1.2.0', 'FUNCTIONALLY_TESTED', 1, None, 'patient:read'),
            ('clinical.encounters', 'Encounter Lifecycle & OPD Queue Engine', '1.2.0', 'FUNCTIONALLY_TESTED', 1, None, 'encounter:read'),
            
            # Future clinical engines: STRICTLY NOT_IMPLEMENTED in Phase 1 / Phase 2
            ('clinical.consultation', 'Single 3-Zone Consultation Canvas', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Phase 2 Foundation completed; clinical charting scheduled for Phase 3', 'encounters:write'),
            ('clinical.unani_mizaj', 'Unani Mizaj & Ajnas Scoring Engine', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Scheduled for Phase 3 validation', 'encounters:write'),
            ('clinical.prescriptions_nuskha', 'Nuskha Builder & Posology Compiler', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Scheduled for Phase 3 clinical vertical slice', 'prescriptions:sign'),
            ('clinical.safety_preflight', 'Deterministic Safety Preflight Engine', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Scheduled for Phase 3 safety gate', 'prescriptions:sign'),
            ('operations.dispensary', 'FEFO Batch Dispensary Inventory', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Scheduled for Phase 4 clinic operations', 'facility:manage'),
            ('operations.followups', 'Care Continuum Follow-up Queues', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Scheduled for Phase 4 clinic operations', 'encounters:read'),
            ('integration.abdm', 'FHIR / ABDM Adapter Connector', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Disabled by default; pending hospital accreditation', 'org:manage'),
            ('ai.scribe', 'Contextual AI Note Scribe', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Excluded from core clinical safety path', 'encounters:write'),
            ('hospital.ipd', 'Inpatient Nursing Ward Engine', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Disabled for initial Matab profile', 'org:manage')
        ]

        for eng_id, name, ver, status, enabled, reason, perm in capabilities_seed:
            conn.execute("""
                INSERT OR REPLACE INTO capability_registry (engine_id, name, version, status, is_enabled, health_reason, required_permission)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (eng_id, name, ver, status, enabled, reason, perm))

        conn.commit()
        print("[SEED] Successfully seeded synthetic development dataset.")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_development_data()


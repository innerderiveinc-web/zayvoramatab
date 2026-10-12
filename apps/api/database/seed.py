"""Synthetic Development Seeder for ZAYVORA MATAB OS.
Enforces non-production execution safeguard. All generated accounts are strictly synthetic.
"""

import sys
import json
import hashlib
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
        conn.execute("PRAGMA foreign_keys = OFF;")
        
        # 1. Demo Organization
        conn.execute("""
            INSERT INTO organizations (id, name, code, license_number, profile_type, is_active)
            VALUES ('org-matab-default', 'ZAYVORA Matab Dawakhana (Synthetic Dev Org)', 'ZMD-001', 'AYUSH/DEV/2026/SYNTHETIC', 'MATAB', 1)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name, code=excluded.code, license_number=excluded.license_number, profile_type=excluded.profile_type, is_active=excluded.is_active;
        """)

        # 2. Two Facilities for Multi-Facility testing
        conn.execute("""
            INSERT INTO facilities (id, organization_id, name, code, address, phone, is_active)
            VALUES 
            ('fac-central-opd', 'org-matab-default', 'Central Matab OPD [Synthetic]', 'OPD-1', '101 Dawakhana Chowk, Delhi', '+91-9800000001', 1),
            ('fac-south-branch', 'org-matab-default', 'South Branch Clinic [Synthetic]', 'OPD-2', '45 Nizamuddin West, Delhi', '+91-9800000002', 1)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name, address=excluded.address, phone=excluded.phone, is_active=excluded.is_active;
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
            ('perm-prescriptions-sign', 'prescriptions:sign', 'Sign Medical Prescriptions', 'CLINICAL'),
            # Prompt 03 Formulary & Prescription Permissions
            ('perm-form-read', 'formulary:read', 'Browse Formulation Catalog', 'CLINICAL'),
            ('perm-form-create', 'formulary:draft_create', 'Author Draft Formulations', 'CLINICAL'),
            ('perm-form-update', 'formulary:draft_update', 'Edit Draft Formulations', 'CLINICAL'),
            ('perm-form-submit', 'formulary:submit_review', 'Submit Formulations for Review', 'CLINICAL'),
            ('perm-form-approve', 'formulary:approve', 'Approve/Reject Formulations', 'GOVERNANCE'),
            ('perm-rx-create', 'prescription:create_draft', 'Create Prescription Drafts', 'CLINICAL'),
            ('perm-rx-read', 'prescription:read', 'Read Prescription Records', 'CLINICAL'),
            ('perm-rx-update', 'prescription:update_draft', 'Update Draft Prescription Items', 'CLINICAL'),
            ('perm-rx-validate', 'prescription:validate', 'Run Safety Preflight Validation', 'CLINICAL'),
            ('perm-rx-sign', 'prescription:sign', 'Electronically Sign Prescriptions', 'CLINICAL'),
            ('perm-rx-amend', 'prescription:amend', 'Amend Signed Prescriptions', 'CLINICAL'),
            ('perm-rx-cancel', 'prescription:cancel', 'Cancel Prescriptions', 'CLINICAL'),
            ('perm-rx-export', 'prescription:export', 'Print / Export Prescription Documents', 'CLINICAL'),
            # Prompt 04 Unani Assessment, Organ-Axis & Care Planning Permissions
            ('perm-assess-read', 'assessment:read', 'View Unani Clinical Assessments', 'CLINICAL'),
            ('perm-assess-create', 'assessment:create_draft', 'Create Draft Unani Assessment', 'CLINICAL'),
            ('perm-assess-update', 'assessment:update_draft', 'Update Draft Unani Assessment', 'CLINICAL'),
            ('perm-assess-finalise', 'assessment:finalise', 'Clinically Finalise & Attest Unani Assessment', 'CLINICAL'),
            ('perm-assess-amend', 'assessment:amend', 'Amend Finalised Unani Assessment', 'CLINICAL'),
            ('perm-tpl-read', 'template:read', 'Read Assessment Templates', 'CLINICAL'),
            ('perm-tpl-manage', 'template:manage', 'Manage Assessment Templates & Versions', 'GOVERNANCE'),
            ('perm-oa-read', 'organ_axis:read', 'Browse Organ-Axis Contextual Mappings', 'CLINICAL'),
            ('perm-oa-manage', 'organ_axis:manage', 'Govern Organ-Axis Mappings', 'GOVERNANCE'),
            ('perm-usul-read', 'usul_e_ilaj:read', 'Browse Usul-e-Ilaj Principle Vocabulary', 'CLINICAL'),
            ('perm-usul-manage', 'usul_e_ilaj:manage', 'Govern Usul-e-Ilaj Principle Definitions', 'GOVERNANCE'),
            ('perm-cp-read', 'care_plan:read', 'View Longitudinal Care Plans', 'CLINICAL'),
            ('perm-cp-create', 'care_plan:create', 'Create Usul-e-Ilaj Care Plans', 'CLINICAL'),
            ('perm-cp-update', 'care_plan:update', 'Update Care Plans and Items', 'CLINICAL'),
            ('perm-cp-finalise', 'care_plan:finalise', 'Finalise and Activate Care Plans', 'CLINICAL'),
            # Prompt 05 Modern Clinical Assessment & Decision Support
            ('perm-mod-assess-read', 'modern_assessment:read', 'View Modern Clinical Assessments', 'CLINICAL'),
            ('perm-mod-assess-create', 'modern_assessment:create_draft', 'Create Draft Modern Assessment', 'CLINICAL'),
            ('perm-mod-assess-update', 'modern_assessment:update_draft', 'Update Draft Modern Assessment', 'CLINICAL'),
            ('perm-mod-assess-sign', 'modern_assessment:sign', 'Electronically Sign Modern Clinical Assessment', 'CLINICAL'),
            ('perm-mod-assess-amend', 'modern_assessment:amend', 'Amend Signed Modern Clinical Assessment', 'CLINICAL'),
            ('perm-mod-assess-cancel', 'modern_assessment:cancel', 'Cancel Modern Clinical Assessment', 'CLINICAL'),
            ('perm-clin-rules-read', 'clinical_rules:read', 'Read Governed Clinical Rules & Decision Support', 'CLINICAL'),
            ('perm-clin-rules-manage', 'clinical_rules:manage', 'Manage Clinical Decision Rules & Sources', 'GOVERNANCE')
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
        
        # CLINIC_ADMIN gets all formulary, prescription, assessment, care plan, and modern assessment permissions
        for p_code in [
            'patients:read', 'patients:write', 'patient:read', 'patient:create', 'patient:update_demographics',
            'encounters:read', 'encounters:write', 'encounter:read', 'encounter:create', 'encounter:update_draft', 'encounter:cancel',
            'consent:read', 'consent:record', 'prescriptions:sign', 'capabilities:read',
            'formulary:read', 'formulary:draft_create', 'formulary:draft_update', 'formulary:submit_review', 'formulary:approve',
            'prescription:create_draft', 'prescription:read', 'prescription:update_draft', 'prescription:validate',
            'prescription:sign', 'prescription:amend', 'prescription:cancel', 'prescription:export',
            'assessment:read', 'assessment:create_draft', 'assessment:update_draft', 'assessment:finalise', 'assessment:amend',
            'template:read', 'template:manage', 'organ_axis:read', 'organ_axis:manage', 'usul_e_ilaj:read', 'usul_e_ilaj:manage',
            'care_plan:read', 'care_plan:create', 'care_plan:update', 'care_plan:finalise',
            'modern_assessment:read', 'modern_assessment:create_draft', 'modern_assessment:update_draft',
            'modern_assessment:cancel', 'clinical_rules:read', 'clinical_rules:manage'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-clinic-admin', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # PRACTITIONER gets full clinical assessment, prescribing, care planning, and modern assessment
        for p_code in [
            'patients:read', 'patients:write', 'patient:read', 'patient:create', 'patient:update_demographics',
            'encounters:read', 'encounters:write', 'encounter:read', 'encounter:create', 'encounter:update_draft', 'encounter:cancel',
            'consent:read', 'consent:record', 'prescriptions:sign', 'capabilities:read',
            'formulary:read', 'formulary:draft_create', 'formulary:draft_update', 'formulary:submit_review',
            'prescription:create_draft', 'prescription:read', 'prescription:update_draft', 'prescription:validate',
            'prescription:sign', 'prescription:amend', 'prescription:cancel', 'prescription:export',
            'assessment:read', 'assessment:create_draft', 'assessment:update_draft', 'assessment:finalise', 'assessment:amend',
            'template:read', 'organ_axis:read', 'usul_e_ilaj:read',
            'care_plan:read', 'care_plan:create', 'care_plan:update', 'care_plan:finalise',
            'modern_assessment:read', 'modern_assessment:create_draft', 'modern_assessment:update_draft',
            'modern_assessment:sign', 'modern_assessment:amend', 'modern_assessment:cancel',
            'clinical_rules:read'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-practitioner', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # RECEPTIONIST gets patient read/create/update/duplicate, encounter read/create/cancel, consent read/record, prescription read/export
        for p_code in [
            'patients:read', 'patients:write', 'patient:read', 'patient:create', 'patient:update_demographics', 'patient:resolve_duplicate',
            'encounters:read', 'encounter:read', 'encounter:create', 'encounter:cancel',
            'consent:read', 'consent:record', 'capabilities:read', 'prescription:read', 'prescription:export',
            'care_plan:read'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-receptionist', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # PHARMACIST gets formulary read, prescription read, care_plan read, and export
        for p_code in ['formulary:read', 'prescription:read', 'prescription:export', 'capabilities:read', 'care_plan:read']:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-pharmacist', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # READ_ONLY_AUDITOR gets audit:read, patient:read, encounter:read, consent:read, formulary:read, prescription:read, assessment:read, care_plan:read, capabilities:read
        for p_code in ['audit:read', 'patients:read', 'patient:read', 'encounters:read', 'encounter:read', 'consent:read', 'formulary:read', 'prescription:read', 'assessment:read', 'care_plan:read', 'organ_axis:read', 'usul_e_ilaj:read', 'capabilities:read']:
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

        # 9. Seed Synthetic Clinical Sources
        sources_seed = [
            ('src-nfum', 'NFUM', 'National Formulary of Unani Medicine (NFUM) Parts I-VI', 'Ministry of AYUSH / CCRUM, Govt of India', 'Second Edition', 2006, 'STATUTORY', 'https://ayush.gov.in/nfum', 'VERIFIED'),
            ('src-upi', 'UPI', 'Unani Pharmacopoeia of India (UPI) Parts I-II', 'Pharmacopoeia Commission for Indian Medicine & Homoeopathy', 'First Edition', 2007, 'STATUTORY', 'https://pcim.gov.in/upi', 'VERIFIED'),
            ('src-bayaz', 'BAYAZ_KABIR', 'Bayaz-e-Kabir (Dawa-Sazi)', 'Hakeem Kabiruddin', 'Daftar-e-Maseeh Edition', 1935, 'HISTORICAL_BENCHMARK', 'Classical Formulary Benchmark', 'VERIFIED')
        ]
        for s_id, code, title, auth, ed, yr, leg, ref, ver_st in sources_seed:
            conn.execute("""
                INSERT OR REPLACE INTO clinical_sources (id, code, title, author_authority, edition, publication_year, legal_status, url_or_reference, verification_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (s_id, code, title, auth, ed, yr, leg, ref, ver_st))

        # 10. Seed Synthetic Ingredients Catalog
        ingredients_seed = [
            ('ing-badam', 'Almond / Badam', 'Badam Shireen', 'Prunus dulcis', 'BOTANICAL', 'HOT_MOIST', 1, 5000, 15000, 30000, 0, 0, 'src-upi', 'APPROVED'),
            ('ing-bekh-kasni', 'Chicory Root', 'Bekh-e-Kasni', 'Cichorium intybus', 'BOTANICAL', 'COLD_MOIST', 1, 3000, 7000, 15000, 0, 0, 'src-upi', 'APPROVED'),
            ('ing-tukhm-kheera', 'Cucumber Seed', 'Tukhm-e-Kheera', 'Cucumis sativus', 'BOTANICAL', 'COLD_MOIST', 1, 3000, 7000, 14000, 0, 0, 'src-upi', 'APPROVED'),
            ('ing-tukhm-kakdi', 'Melon Seed', 'Tukhm-e-Kakdi', 'Cucumis melo', 'BOTANICAL', 'COLD_MOIST', 1, 3000, 7000, 14000, 0, 0, 'src-upi', 'APPROVED'),
            ('ing-tukhm-kahu', 'Lettuce Seed', 'Tukhm-e-Kahu', 'Lactuca sativa', 'BOTANICAL', 'COLD_DRY', 2, 2000, 5000, 10000, 0, 0, 'src-upi', 'APPROVED'),
            ('ing-kuchla', 'Poison Nut / Nux Vomica', 'Kuchla (Azaaraqi)', 'Strychnos nux-vomica', 'BOTANICAL', 'HOT_DRY', 3, 30, 65, 130, 1, 1, 'src-upi', 'APPROVED'),
            ('ing-abhal', 'Juniper Berries', 'Abhal', 'Juniperus communis', 'BOTANICAL', 'HOT_DRY', 2, 2000, 5000, 10000, 0, 0, 'src-upi', 'APPROVED'),
            ('ing-zanjabil', 'Dried Ginger', 'Zanjabil (Sonth)', 'Zingiber officinale', 'BOTANICAL', 'HOT_DRY', 2, 1000, 3000, 6000, 0, 0, 'src-upi', 'APPROVED'),
            ('ing-filfil', 'Black Pepper', 'Filfil Siyah', 'Piper nigrum', 'BOTANICAL', 'HOT_DRY', 3, 500, 1500, 3000, 0, 0, 'src-upi', 'APPROVED')
        ]
        for ing_id, cname, uname, bname, cat, mizaj, deg, smin, smax, dmax, mud, s_e1, src_id, rst in ingredients_seed:
            conn.execute("""
                INSERT OR REPLACE INTO ingredient_catalog (
                    id, canonical_name, unani_name, botanical_name, category, temperament_mizaj,
                    degree, single_dose_min_mg, single_dose_max_mg, daily_dose_max_mg,
                    is_mudabbar_required, is_schedule_e1, source_id, review_status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (ing_id, cname, uname, bname, cat, mizaj, deg, smin, smax, dmax, mud, s_e1, src_id, rst))

        # 11. Seed Safety Contraindications
        conn.execute("""
            INSERT OR REPLACE INTO safety_contraindications (id, ingredient_id, contraindication_type, severity, rationale)
            VALUES 
            ('con-abhal-preg', 'ing-abhal', 'PREGNANCY', 'BLOCK', 'Emmenagogue / Abortifacient: Strictly contraindicated during pregnancy.'),
            ('con-kuchla-ped', 'ing-kuchla', 'PEDIATRIC', 'BLOCK', 'Potent Strychnine Alkaloid: Contraindicated in pediatric patients under 12 years.');
        """)

        # 12. Seed Patient Allergies (pat-syn-001 allergic to Badam / Almond)
        conn.execute("""
            INSERT OR REPLACE INTO patient_allergies (id, patient_id, organization_id, allergen_name, severity, reaction, recorded_by)
            VALUES 
            ('alg-syn-001', 'pat-syn-001', 'org-matab-default', 'Roghan Badam Shireen (Almond)', 'SEVERE', 'Acute angioedema and bronchospasm upon ingestion of almond oil preparations.', 'usr-hakeem-1');
        """)

        # 13. Seed Formulations and Reviewed Versions
        formulations_seed = [
            (
                'form-sharbat-bazoori', 'org-matab-default', 'FORM-001', 'Sharbat Bazoori Motadil',
                'شربت بزوری معتدل', 'SHARBAT', 1, 'APPROVED', 'usr-admin-1',
                'Diuretic, lithotriptic, and liver/kidney deobstruent (Mufattih Sudad)', '20 to 40 ml twice daily with fresh water',
                'src-nfum', 'NFUM Part I, Page 142'
            ),
            (
                'form-majoon-arad', 'org-matab-default', 'FORM-002', 'Majoon Arad Khurma',
                'معجون آرد خرما', 'MAJOON', 1, 'APPROVED', 'usr-admin-1',
                'Nourishing tonic (Muqawwi-e-Bah) and spermatogenic', '10 g twice daily with warm milk',
                'src-bayaz', 'Bayaz-e-Kabir Vol II, Page 85'
            ),
            (
                'form-hab-azaarqi', 'org-matab-default', 'FORM-003', 'Habb-e-Azaarqi',
                'حب ازارقی', 'HAB', 1, 'APPROVED', 'usr-admin-1',
                'Neuromuscular stimulant for chronic joint stiffness and facial palsy', '1 pill (500mg) once daily after meals',
                'src-nfum', 'NFUM Part II, Page 38'
            ),
            (
                'form-hab-abhal', 'org-matab-default', 'FORM-004', 'Habb-e-Mudir (Abhal Compound)',
                'حب مدر', 'HAB', 1, 'APPROVED', 'usr-admin-1',
                'Uterine stimulant and emmenagogue for amenorrhea', '1 to 2 pills BD',
                'src-bayaz', 'Bayaz-e-Kabir Vol I, Page 112'
            ),
            (
                'form-draft-unreviewed', 'org-matab-default', 'FORM-999', 'Jawarish Mastagi (Trial Compound)',
                'جوارش مصطگی', 'MAJOON', 1, 'DRAFT', 'usr-hakeem-1',
                'Gastric tonic formulation currently under trial review', '5 g BD',
                'src-bayaz', 'Unreviewed monograph entry'
            )
        ]

        for f_id, o_id, code, name, translit, dform, ver, st, author, indic, dose, src_id, loc in formulations_seed:
            conn.execute("""
                INSERT OR REPLACE INTO formulations (id, organization_id, code, name, transliteration, dosage_form, current_version, status, created_by, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (f_id, o_id, code, name, translit, dform, ver, st, author, author))

            v_id = f"ver-{f_id}-1"
            conn.execute("""
                INSERT OR REPLACE INTO formulation_versions (
                    id, formulation_id, version_number, standard_indication, standard_adult_dose,
                    classical_source_id, source_locator, status, reviewed_by, reviewed_at, review_notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'Synthetic verified formulation monograph');
            """, (v_id, f_id, ver, indic, dose, src_id, loc, st, author))

        # 14. Seed Formulation Ingredients
        form_ingredients = [
            # Sharbat Bazoori Motadil ingredients
            ('fi-baz-1', 'ver-form-sharbat-bazoori-1', 'ing-bekh-kasni', 5000, 1),
            ('fi-baz-2', 'ver-form-sharbat-bazoori-1', 'ing-tukhm-kheera', 3000, 0),
            ('fi-baz-3', 'ver-form-sharbat-bazoori-1', 'ing-tukhm-kakdi', 3000, 0),
            ('fi-baz-4', 'ver-form-sharbat-bazoori-1', 'ing-tukhm-kahu', 2000, 0),
            # Majoon Arad Khurma (Contains Almond -> allergen)
            ('fi-arad-1', 'ver-form-majoon-arad-1', 'ing-badam', 4000, 1),
            ('fi-arad-2', 'ver-form-majoon-arad-1', 'ing-zanjabil', 1000, 0),
            # Habb-e-Azaarqi (Contains Kuchla -> Schedule E1 toxin)
            ('fi-aza-1', 'ver-form-hab-azaarqi-1', 'ing-kuchla', 60, 1),
            ('fi-aza-2', 'ver-form-hab-azaarqi-1', 'ing-filfil', 120, 0),
            # Habb-e-Abhal (Contains Abhal -> Pregnancy contraindication)
            ('fi-abh-1', 'ver-form-hab-abhal-1', 'ing-abhal', 500, 1),
            ('fi-abh-2', 'ver-form-hab-abhal-1', 'ing-zanjabil', 250, 0)
        ]
        for fi_id, fv_id, ing_id, q_mg, is_chief in form_ingredients:
            conn.execute("""
                INSERT OR REPLACE INTO formulation_ingredients (id, formulation_version_id, ingredient_id, quantity_mg, is_chief_ingredient)
                VALUES (?, ?, ?, ?, ?);
            """, (fi_id, fv_id, ing_id, q_mg, is_chief))

        # 15. Seed Synthetic Prescriptions
        # rx-syn-001: Signed prescription for pat-syn-003 in enc-syn-002
        rx_snapshot = json.dumps({
            "prescription_number": "RX-2026-00001",
            "patient_mrn": "MRN-2026-00003",
            "patient_name": "Maryam Khatoon",
            "encounter_id": "enc-syn-002",
            "practitioner_name": "Hakeem Tariq Ahmad",
            "items": [
                {
                    "item_name": "Sharbat Bazoori Motadil",
                    "dosage_form": "SHARBAT",
                    "dose_amount": "20",
                    "dose_unit": "ml",
                    "route": "ORAL",
                    "frequency": "BD",
                    "duration_days": 14,
                    "anupan_vehicle": "Aab-e-Taza (Fresh Water)",
                    "instructions": "Take 20 ml with 1 glass of fresh water in the morning and evening."
                }
            ],
            "signed_at": "2026-10-12T10:30:00Z"
        })
        rx_hash = hashlib.sha256(rx_snapshot.encode("utf-8")).hexdigest()

        conn.execute("""
            INSERT OR REPLACE INTO prescriptions (
                id, organization_id, facility_id, prescription_number, patient_id, encounter_id,
                practitioner_id, version_number, status, overall_safety_state, signed_at, signed_by,
                signature_hash, signed_snapshot
            )
            VALUES (
                'rx-syn-001', 'org-matab-default', 'fac-central-opd', 'RX-2026-00001', 'pat-syn-003',
                'enc-syn-002', 'usr-hakeem-1', 1, 'SIGNED', 'PASS', CURRENT_TIMESTAMP, 'usr-hakeem-1',
                ?, ?
            );
        """, (rx_hash, rx_snapshot))

        conn.execute("""
            INSERT OR REPLACE INTO prescription_items (
                id, prescription_id, item_type, formulation_id, formulation_version_id, item_name,
                dosage_form, dose_amount, dose_unit, route, frequency, duration_days, instructions, anupan_vehicle, sort_order
            )
            VALUES (
                'rxi-syn-001', 'rx-syn-001', 'CATALOG_FORMULATION', 'form-sharbat-bazoori', 'ver-form-sharbat-bazoori-1',
                'Sharbat Bazoori Motadil', 'SHARBAT', '20', 'ml', 'ORAL', 'BD', 14,
                'Take 20 ml with 1 glass of fresh water in the morning and evening.', 'Aab-e-Taza (Fresh Water)', 1
            );
        """)

        # 16. Prompt 04: Statutory Source for Classical Physiology (Al-Qanun)
        conn.execute("""
            INSERT OR REPLACE INTO clinical_sources (id, organization_id, code, title, author_authority, edition, publication_year, legal_status, url_or_reference, verification_status)
            VALUES ('src-al-qanun', NULL, 'AL_QANUN', 'Al-Qanun fi al-Tibb (The Canon of Medicine)', 'Ibn Sina (Avicenna)', 'Standard Arabic/Urdu Critical Edition', 1025, 'HISTORICAL_BENCHMARK', 'Jamia Hamdard / CCRUM Archives', 'VERIFIED');
        """)

        # 17. Prompt 04: Unani Assessment Templates & Core Version
        conn.execute("""
            INSERT OR REPLACE INTO unani_assessment_templates (id, code, name, purpose, language, status)
            VALUES ('tmpl-unani-core', 'TMPL-UNANI-CORE', 'Standard Unani Clinical Examination & Mizaj Assessment', 'Routine OPD clinical examination covering Ajnas-e-Ashara, Afaal, and Asbab-e-Sittah', 'ur', 'ACTIVE');
        """)

        tmpl_def = json.dumps({
            "sections": ["mizaj_indicators", "afaal_functional", "asbab_sittah", "examination_nabz_baul_baraz"],
            "scoring_rule": "CLINICIAN_ENTERED_ONLY",
            "instruction": "Record observed and patient-reported signs. Clinician must explicitly enter final Mizaj determination and uncertainty."
        })
        conn.execute("""
            INSERT OR REPLACE INTO unani_assessment_template_versions (
                id, template_id, version_number, definition_json, validation_metadata,
                status, effective_date
            )
            VALUES ('ver-tmpl-unani-core-1', 'tmpl-unani-core', 1, ?, '{"mandatory_domains": ["MIZAJ", "AFAAL"]}', 'APPROVED', '2026-01-01');
        """, (tmpl_def,))

        domains_seed = [
            ('dom-mizaj', 'ver-tmpl-unani-core-1', 'MIZAJ', 'Mizaj (Temperament) Indicators', 'Ajnas-e-Ashara indicators including complexion, touch, build, and sleep', 1, 1),
            ('dom-afaal', 'ver-tmpl-unani-core-1', 'AFAAL', 'Afaal (Functional & Faculty Observations)', 'Assessment of Quwa (faculties) and Afaal (functions: digestive, respiratory, cognitive)', 2, 1),
            ('dom-asbab', 'ver-tmpl-unani-core-1', 'ASBAB_SITTAH', 'Asbab-e-Sittah Zarooriyyah (Lifestyle Context)', 'Air, food/drink, bodily movement/rest, psychic movement/rest, sleep/wakefulness, retention/evacuation', 3, 0),
            ('dom-nabz', 'ver-tmpl-unani-core-1', 'NABZ', 'Nabz (Pulse Examination)', 'Ten pulse characteristics: volume, strength, speed, frequency, compressibility, etc.', 4, 0),
            ('dom-baul', 'ver-tmpl-unani-core-1', 'BAUL', 'Baul (Urine Examination)', 'Color, consistency, transparency, sediment, and froth', 5, 0),
            ('dom-baraz', 'ver-tmpl-unani-core-1', 'BARAZ', 'Baraz (Stool Examination)', 'Color, quantity, odor, and evacuation transit', 6, 0)
        ]
        for d_id, tv_id, key, lbl, desc, s_ord, mand in domains_seed:
            conn.execute("""
                INSERT OR REPLACE INTO unani_assessment_domains (id, template_version_id, domain_key, label, description, sort_order, is_mandatory)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (d_id, tv_id, key, lbl, desc, s_ord, mand))

        options_seed = [
            ('opt-miz-dam', 'dom-mizaj', 'DAMAWWI', 'Damawwi (Hot & Moist / Sanguineous)', 'Predominance of blood humor (Dam)', 1),
            ('opt-miz-bal', 'dom-mizaj', 'BALGHAMI', 'Balghami (Cold & Moist / Phlegmatic)', 'Predominance of phlegm humor (Balgham)', 2),
            ('opt-miz-saf', 'dom-mizaj', 'SAFRAWI', 'Safrawi (Hot & Dry / Choleric)', 'Predominance of yellow bile (Safra)', 3),
            ('opt-miz-sau', 'dom-mizaj', 'SAUDAWI', 'Saudawi (Cold & Dry / Melancholic)', 'Predominance of black bile (Sauda)', 4),
            ('opt-miz-mot', 'dom-mizaj', 'MOTADIL', 'Motadil (Balanced / Eutemperament)', 'Harmonious humoral equilibrium', 5)
        ]
        for o_id, d_id, o_key, o_lbl, o_desc, s_ord in options_seed:
            conn.execute("""
                INSERT OR REPLACE INTO unani_assessment_options (id, domain_id, option_key, label, description, sort_order)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (o_id, d_id, o_key, o_lbl, o_desc, s_ord))

        # 18. Prompt 04: Organ-Axis Concepts Catalog & Contextual Mappings
        oa_concepts = [
            ('oac-meda', 'MEDA', 'Stomach (Meda)', 'معدہ', 'Gastric cavity / Digestive tract', 'ACTIVE'),
            ('oac-dimagh', 'DIMAGH', 'Brain (Dimagh)', 'دماغ', 'Central nervous system & Psychic faculty', 'ACTIVE'),
            ('oac-kabid', 'KABID', 'Liver (Kabid)', 'کبد', 'Hepato-biliary system & Nutritive faculty', 'ACTIVE'),
            ('oac-qalb', 'QALB', 'Heart (Qalb)', 'قلب', 'Cardiovascular system & Vital faculty', 'ACTIVE'),
            ('oac-kulyah', 'KULYAH', 'Kidneys (Kulyah)', 'گردہ', 'Renal urinary excretion system', 'ACTIVE')
        ]
        for cid, code, cname, uname, anat, st in oa_concepts:
            conn.execute("""
                INSERT OR REPLACE INTO organ_axis_concepts (id, code, canonical_name, unani_name, anatomical_correlate, status)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (cid, code, cname, uname, anat, st))

        oa_mappings = [
            (
                'oam-meda-dimagh', 'oac-meda', 'oac-dimagh', 'ASSOCIATED_WITH',
                'Su-e-Hazm (impaired gastric digestion) produces noxious gastric vapors (Bukharaat-e-Meda) that ascend to the brain, inducing secondary cephalalgia (Sudaa) and vertigo.',
                'Examine gastric history, food intake, and epigastric discomfort when evaluating chronic headaches.',
                'HISTORICAL_BENCHMARK', 'APPROVED', 'src-al-qanun', 'Vol 1, Book 3, Treatise on Cephalalgia & Gastric Axis',
                'usr-hakeem-1', '2026-01-10'
            ),
            (
                'oam-meda-kabid', 'oac-meda', 'oac-kabid', 'TRADITIONALLY_RELATED_TO',
                'First digestion in the stomach (Hazm-e-Midi) directly prepares chyme (Kylos) for the second digestion in the liver (Hazm-e-Kabidi). Raw gastric chyme leads to sluggish hepatic humor synthesis.',
                'Consider gentle liver tonic (Muqawwi-e-Kabid) when treating chronic chronic gastric hypomotility.',
                'HISTORICAL_BENCHMARK', 'APPROVED', 'src-al-qanun', 'Vol 1, Discourse on the Four Stages of Digestion',
                'usr-hakeem-1', '2026-01-10'
            )
        ]
        for mid, scid, tcid, rel, exp, util, ev, st, s_id, s_loc, r_by, r_at in oa_mappings:
            conn.execute("""
                INSERT OR REPLACE INTO organ_axis_mappings (
                    id, source_concept_id, target_concept_id, relationship_type,
                    plain_explanation, clinical_utility_notes, evidence_level, status,
                    source_id, source_locator, reviewed_by, reviewed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (mid, scid, tcid, rel, exp, util, ev, st, s_id, s_loc, r_by, r_at))

        # 19. Prompt 04: Usul-e-Ilaj Treatment Principles Vocabulary & Versions
        principles_seed = [
            ('uip-tanqiya', 'TANQIYA', 'Tanqiya', 'Evacuation / Humoral Cleansing', 'تنقیہ', 'ACTIVE'),
            ('uip-tadeel', 'TADEEL_E_MIZAJ', 'Tadeel-e-Mizaj', 'Temperamental Normalization', 'تعدیل مزاج', 'ACTIVE'),
            ('uip-tahleel', 'TAHLEEL', 'Tahleel', 'Resolution of Morbid Humors', 'تحلیل', 'ACTIVE'),
            ('uip-taqwiyat', 'TAQWIYAT', 'Taqwiyat', 'Target Faculty Strengthening', 'تقویت', 'ACTIVE'),
            ('uip-hifz', 'HIFZ_E_SEHAT', 'Hifz-e-Sehat', 'Preservation of Health / Regimen', 'حفظ صحت', 'ACTIVE'),
            ('uip-taskeen', 'TASKEEN', 'Taskeen', 'Palliative Symptom Relief', 'تسکین', 'ACTIVE')
        ]
        for pid, code, nunani, neng, nurdu, st in principles_seed:
            conn.execute("""
                INSERT OR REPLACE INTO usul_e_ilaj_principles (id, code, name_unani, name_english, name_urdu, status)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (pid, code, nunani, neng, nurdu, st))

        principle_versions_seed = [
            (
                'ver-uip-tanqiya-1', 'uip-tanqiya', 1,
                'Evacuation of accumulated morbid humors (Mawad-e-Fasida) via natural emunctory pathways (emesis, purgation, diuresis, diaphoresis).',
                'Indicated in plethora (Imtila) and Maddi diseases where morbid matter is confirmed.',
                'Contraindicated in severe physical debility, advanced cachexia, and acute dehydration.',
                'Monitor hydration, pulse stability, and abdominal cramping during evacuant regimen.',
                'APPROVED', 'src-al-qanun', 'Book 1, Canon of Therapeutics'
            ),
            (
                'ver-uip-tadeel-1', 'uip-tadeel', 1,
                'Restoring temperamental balance through counter-acting qualities (Ilaj-bid-Didd) using foods, herbs, and climatic adjustments.',
                'Indicated in all simple Su-e-Mizaj (Sada) and post-evacuation convalescence.',
                'Requires accurate ongoing determination of target organ temperament.',
                'Weekly monitoring of pulse (Nabz) and digestive fire (Hazm).',
                'APPROVED', 'src-al-qanun', 'Book 1, Discourse on Temperamental Rectification'
            ),
            (
                'ver-uip-taqwiyat-1', 'uip-taqwiyat', 1,
                'Consolidating and strengthening the innate faculty (Quwwat) of the affected organ using specific tonics (Muqawwiyat).',
                'Indicated following humor resolution to prevent disease recurrence.',
                'Contraindicated while acute active inflammation or morbid matter is unexpelled.',
                'Bi-weekly functional review of digestion, stamina, and sleep.',
                'APPROVED', 'src-al-qanun', 'Book 1, Strengthening Weakened Organs'
            )
        ]
        for pvid, pid, vnum, defn, ind, cind, mon, st, sid, sloc in principle_versions_seed:
            conn.execute("""
                INSERT OR REPLACE INTO usul_e_ilaj_principle_versions (
                    id, principle_id, version_number, definition, indications, contraindications,
                    monitoring_guidance, status, source_id, source_locator
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (pvid, pid, vnum, defn, ind, cind, mon, st, sid, sloc))

        # 20. Prompt 04: Synthetic Finalised Unani Assessment for pat-syn-001
        uas_snapshot = json.dumps({
            "assessment_id": "uas-syn-001",
            "dominant_mizaj": "BALGHAMI",
            "secondary_mizaj": "SAUDAWI",
            "mizaj_uncertainty": "HIGH_CONFIDENCE",
            "clinical_reasoning": "Su-e-Mizaj Balghami Maddi affecting the gastric faculty (Meda) with secondary Bukharaat-e-Meda causing Sudaa (headache).",
            "signed_at": "2026-10-12T10:15:00Z"
        })
        uas_hash = hashlib.sha256(uas_snapshot.encode("utf-8")).hexdigest()

        conn.execute("""
            INSERT OR REPLACE INTO unani_assessments (
                id, organization_id, facility_id, patient_id, encounter_id, template_version_id,
                author_id, status, assessment_date, dominant_mizaj, secondary_mizaj, mizaj_rationale,
                mizaj_uncertainty, clinical_reasoning, version_number, signed_at, signed_by,
                signature_hash, signed_snapshot
            )
            VALUES (
                'uas-syn-001', 'org-matab-default', 'fac-central-opd', 'pat-syn-001', 'enc-syn-001',
                'ver-tmpl-unani-core-1', 'usr-hakeem-1', 'FINALISED', '2026-10-12', 'BALGHAMI', 'SAUDAWI',
                'Pale complexion, cold/moist touch, sluggish digestion after dairy intake.',
                'HIGH_CONFIDENCE', 'Su-e-Mizaj Balghami Maddi affecting Meda with Bukharaat ascending to Dimagh.',
                1, CURRENT_TIMESTAMP, 'usr-hakeem-1', ?, ?
            );
        """, (uas_hash, uas_snapshot))

        # Assessment responses
        conn.execute("""
            INSERT OR REPLACE INTO unani_assessment_responses (
                id, assessment_id, domain_key, field_key, field_label, field_value, data_type,
                semantic_state, provenance, notes
            )
            VALUES 
            ('uar-syn-001', 'uas-syn-001', 'MIZAJ', 'lawn_complexion', 'Complexion', 'Pale whitish tinge', 'TEXT', 'OBSERVED', 'CLINICIAN_OBSERVED', 'Consistent with Balghami predominance'),
            ('uar-syn-002', 'uas-syn-001', 'AFAAL', 'hazm_digestion', 'Digestive Transit', 'Sluggish, delayed gastric emptying', 'TEXT', 'IMPAIRED', 'PATIENT_REPORTED', 'Complains of heaviness 2-3 hours after meals'),
            ('uar-syn-003', 'uas-syn-001', 'ASBAB_SITTAH', 'makool_mashroob', 'Dietary Intake', 'High consumption of cold yoghurt and chilled water', 'TEXT', 'OBSERVED', 'PATIENT_REPORTED', 'Aggravating cold/moist qualities');
        """)

        # Assessment conclusion
        conn.execute("""
            INSERT OR REPLACE INTO unani_assessment_conclusions (
                id, assessment_id, conclusion_type, code, title, description, certainty, sort_order
            )
            VALUES ('uac-syn-001', 'uas-syn-001', 'SU_E_MIZAJ', 'SU-BALGHAM-MADDI', 'Su-e-Mizaj Balghami Maddi (Gastric Axis)', 'Phlegmatic dyscrasia of gastric faculty with secondary cephalalgia', 'DEFINITIVE', 1);
        """)

        # 21. Prompt 04: Synthetic Active Care Plan for pat-syn-001
        conn.execute("""
            INSERT OR REPLACE INTO care_plans (
                id, organization_id, facility_id, patient_id, encounter_id, author_id,
                responsible_practitioner_id, title, overall_goal, clinical_rationale,
                status, review_date, finalised_at, finalised_by, version_number
            )
            VALUES (
                'cpl-syn-001', 'org-matab-default', 'fac-central-opd', 'pat-syn-001', 'enc-syn-001',
                'usr-hakeem-1', 'usr-hakeem-1', 'Care Plan: Su-e-Mizaj Balghami Resolution',
                'Restore gastric temperament, eliminate cold/moist stagnation, and resolve reflex headache.',
                'Two-stage protocol: initial gentle evacuation of phlegm followed by temperamental normalization and gastric faculty strengthening.',
                'ACTIVE', '2026-10-26', CURRENT_TIMESTAMP, 'usr-hakeem-1', 1
            );
        """)

        conn.execute("""
            INSERT OR REPLACE INTO care_plan_items (
                id, care_plan_id, principle_id, principle_version_id, objective,
                clinician_rationale, intended_intervention, cautions, monitoring_plan,
                expected_outcome, status, sort_order
            )
            VALUES 
            (
                'cpi-syn-001', 'cpl-syn-001', 'uip-tanqiya', 'ver-uip-tanqiya-1',
                'Gentle evacuation of excess cold moist chyme and mucosal stagnation',
                'Required prior to tonic therapy to avoid locking morbid matter in tissues',
                'Warm decoctions with Anise and Fennel seeds; dietary cessation of chilled dairy',
                'Avoid harsh purgatives; check hydration',
                'Daily stool consistency check; monitoring of epigastric fullness',
                'Reduced post-prandial heaviness within 7 days',
                'ACTIVE', 1
            ),
            (
                'cpi-syn-002', 'cpl-syn-001', 'uip-tadeel', 'ver-uip-tadeel-1',
                'Temperamental normalization of gastric faculty (Meda)',
                'Restore physiological warmth to enhance gastric transformation',
                'Sharbat Bazoori Motadil and warm regimen',
                'Confirm absence of acute hot inflammatory fever before administering',
                'Follow up in 14 days for pulse (Nabz) and symptom score review',
                'Resolution of headache and restoration of natural appetite',
                'ACTIVE', 2
            );
        """)

        # Link cpi-syn-002 to rx-syn-001
        conn.execute("""
            INSERT OR REPLACE INTO care_plan_links (
                id, care_plan_id, care_plan_item_id, link_type, prescription_id, notes
            )
            VALUES ('cpl-link-001', 'cpl-syn-001', 'cpi-syn-002', 'PRESCRIPTION_SIGNED', 'rx-syn-001', 'Linked to Sharbat Bazoori Motadil prescription');
        """)

        # 22. Prompt 05: Clinical Content Sources & Governed Decision Rules [Synthetic]
        conn.execute("""
            INSERT OR REPLACE INTO clinical_content_sources (
                id, title, authority, version, review_status, source_uri, effective_date, expiry_date, licence_metadata
            ) VALUES 
            ('src-nice-cks-synth', 'NICE Clinical Knowledge Summaries [Synthetic Knowledge Source]', 'NICE / Matab Clinical Governance Committee', '2026.1', 'approved_active', 'https://cks.nice.org.uk', '2026-01-01', '2027-01-01', 'Synthetic educational reference dataset'),
            ('src-who-stg-synth', 'WHO Standard Treatment Guidelines [Synthetic Knowledge Source]', 'WHO / Matab Evidence Review Board', '2025.2', 'approved_active', 'https://who.int/publications', '2025-06-01', '2026-12-31', 'Open access guideline synthesis'),
            ('src-icd10-subset-synth', 'ICD-10 Clinical Core Subset [Synthetic Reference Catalog]', 'WHO / Internal Governance', '2026', 'approved_active', 'https://icd.who.int', '2026-01-01', '2028-01-01', 'Open WHO terminology subset');
        """)

        # Governed Red-Flag Rules
        rf_rules_data = [
            (
                'rule-rf-001', 'RULE-RF-001', '1.0.0', 'RED_FLAG', 'Chest Pain with Ischemic Features',
                'Cardiovascular / Emergency', 'src-nice-cks-synth', 'EMERGENT',
                json.dumps(['chest_pain', 'radiation_or_diaphoresis']),
                json.dumps({'trigger_terms': ['chest pain', 'angina', 'chest pressure'], 'radiation_terms': ['radiation', 'left arm', 'jaw', 'diaphoresis', 'sweating', 'syncope']}),
                'Acute chest pain radiating to left arm or jaw with diaphoresis carries high likelihood of Acute Coronary Syndrome (ACS).',
                'Immediate Emergency Department transfer with 12-lead ECG, oxygen, and IV access. Do not delay emergency care.',
                'approved_active', 'Dr. Farooq Khan, MD', 'Governance Committee'
            ),
            (
                'rule-rf-002', 'RULE-RF-002', '1.0.0', 'RED_FLAG', 'Severe Hypertension / Hypertensive Emergency',
                'Cardiovascular / Nephrology', 'src-nice-cks-synth', 'EMERGENT',
                json.dumps(['systolic_blood_pressure', 'diastolic_blood_pressure']),
                json.dumps({'sbp_threshold': 180, 'dbp_threshold': 110}),
                'Blood pressure >= 180/110 mmHg carries acute risk of target organ damage (encephalopathy, acute pulmonary edema, aortic dissection).',
                'Assess immediately for target organ damage. Initiate urgent antihypertensive protocol or emergency transfer.',
                'approved_active', 'Dr. Farooq Khan, MD', 'Governance Committee'
            ),
            (
                'rule-rf-003', 'RULE-RF-003', '1.0.0', 'RED_FLAG', 'Suspected Sepsis / Severe Systemic Inflammatory Response',
                'Critical Care / Infectious Disease', 'src-who-stg-synth', 'EMERGENT',
                json.dumps(['heart_rate', 'respiratory_rate', 'body_temperature']),
                json.dumps({'temp_high': 38.3, 'temp_low': 36.0, 'hr_high': 90, 'rr_high': 20}),
                'SIRS criteria (temperature abnormalities, tachycardia, tachypnea) with suspected infection indicates potential life-threatening organ dysfunction.',
                'Initiate Sepsis Six pathway: blood cultures, lactate, fluid resuscitation, and IV antimicrobials within 1 hour.',
                'approved_active', 'Dr. Aisha Siddiqui, MD', 'Governance Committee'
            ),
            (
                'rule-rf-004', 'RULE-RF-004', '1.0.0', 'RED_FLAG', 'Acute Focal Neurological Deficit (FAST)',
                'Neurology / Emergency', 'src-nice-cks-synth', 'EMERGENT',
                json.dumps(['facial_droop', 'arm_weakness', 'slurred_speech']),
                json.dumps({'fast_terms': ['facial droop', 'arm weakness', 'slurred speech', 'sudden numbness', 'hemiparesis']}),
                'Sudden onset focal neurological deficit suggests acute ischemic stroke or intracranial hemorrhage within thrombolysis window.',
                'Immediate acute stroke team activation. Urgent non-contrast head CT.',
                'approved_active', 'Dr. Farooq Khan, MD', 'Governance Committee'
            )
        ]
        for r_id, code, ver, rtype, title, scope, src_id, sev, req_in, logic, rat, act, gov, owner, rev in rf_rules_data:
            conn.execute("""
                INSERT OR REPLACE INTO clinical_rule_definitions (
                    id, rule_id, rule_version, rule_type, title, scope, source_id, severity,
                    required_inputs_json, logic_definition_json, plain_language_rationale,
                    recommended_action, governance_status, clinical_owner, reviewer_name, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (r_id, code, ver, rtype, title, scope, src_id, sev, req_in, logic, rat, act, gov, owner, rev))

        # Governed Differential Heuristics
        ddx_rules_data = [
            (
                'rule-ddx-001', 'RULE-DDX-001', '1.0.0', 'DIFFERENTIAL_HEURISTIC', 'Acute Cough & Dyspnea Heuristic',
                'Pulmonology', 'src-nice-cks-synth', 'WARNING',
                json.dumps(['chief_complaint']),
                json.dumps({
                    'trigger_terms': ['cough', 'dyspnea', 'breathlessness', 'wheeze', 'chest tightness'],
                    'candidates': [
                        {
                            'label': 'Acute Bronchitis',
                            'code': 'J20.9',
                            'code_system': 'ICD-10-MOCK',
                            'rationale': 'Self-limiting inflammation of large airways, typically following viral upper respiratory infection without focal consolidation.',
                            'supporting_findings_pool': ['cough', 'clear sputum', 'normal breath sounds'],
                            'contradicting_findings_pool': ['high fever', 'focal consolidation', 'dullness on percussion'],
                            'standard_missing_information': ['Chest radiograph to exclude consolidation', 'Duration of symptoms (> 3 weeks)'],
                            'sources': ['NICE CKS: Cough - acute (2025)']
                        },
                        {
                            'label': 'Bronchial Asthma Exacerbation',
                            'code': 'J45.9',
                            'code_system': 'ICD-10-MOCK',
                            'rationale': 'Reversible airway obstruction characterized by wheezing, breathlessness, and cough, often worse at night or early morning.',
                            'supporting_findings_pool': ['wheezing', 'dyspnea', 'breathlessness', 'chest tightness'],
                            'contradicting_findings_pool': ['hemoptysis', 'asymmetric breath sounds'],
                            'standard_missing_information': ['Peak Expiratory Flow (PEF) measurement', 'History of atopy or nocturnal awakening'],
                            'sources': ['GINA Guidelines: Global Strategy for Asthma Management (2024)']
                        },
                        {
                            'label': 'Community-Acquired Pneumonia',
                            'code': 'J18.9',
                            'code_system': 'ICD-10-MOCK',
                            'rationale': 'Lower respiratory tract infection with parenchymal consolidation, presenting with fever, productive cough, and systemic symptoms.',
                            'supporting_findings_pool': ['crackles', 'fever', 'productive cough', 'tachypnea'],
                            'contradicting_findings_pool': ['normal breath sounds', 'absence of systemic fever'],
                            'standard_missing_information': ['Chest radiograph (PA view)', 'Sputum culture and inflammatory markers (CRP/ESR)'],
                            'sources': ['BTS Guidelines for the Management of Community-Acquired Pneumonia']
                        }
                    ]
                }),
                'Heuristic differential framework for adult acute respiratory presentation.',
                'Correlate clinical auscultation and vitals. Order diagnostic chest x-ray if focal crackles or hypoxia observed.',
                'approved_active', 'Dr. Aisha Siddiqui, MD', 'Governance Committee'
            ),
            (
                'rule-ddx-002', 'RULE-DDX-002', '1.0.0', 'DIFFERENTIAL_HEURISTIC', 'Epigastric Pain / Dyspepsia Heuristic',
                'Gastroenterology', 'src-nice-cks-synth', 'WARNING',
                json.dumps(['chief_complaint']),
                json.dumps({
                    'trigger_terms': ['epigastric pain', 'dyspepsia', 'indigestion', 'heartburn', 'stomach burning'],
                    'candidates': [
                        {
                            'label': 'Peptic Ulcer Disease (Gastric / Duodenal)',
                            'code': 'K27.9',
                            'code_system': 'ICD-10-MOCK',
                            'rationale': 'Mucosal break in stomach or proximal duodenum characterized by burning epigastric discomfort, often related to meals.',
                            'supporting_findings_pool': ['epigastric pain', 'burning pain', 'nighttime pain', 'relief with antacids'],
                            'contradicting_findings_pool': ['radiating to shoulder', 'jaundice'],
                            'standard_missing_information': ['Helicobacter pylori status', 'NSAID exposure history', 'Alarm features (weight loss, vomiting)'],
                            'sources': ['NICE CG184: Gastro-oesophageal reflux disease and dyspepsia in adults']
                        },
                        {
                            'label': 'Gastroesophageal Reflux Disease (GERD)',
                            'code': 'K21.9',
                            'code_system': 'ICD-10-MOCK',
                            'rationale': 'Retrograde flow of gastric contents causing troublesome pyrosis (heartburn) and acid regurgitation.',
                            'supporting_findings_pool': ['heartburn', 'acid regurgitation', 'worse lying flat', 'sour taste'],
                            'contradicting_findings_pool': ['severe localized tenderness', 'persistent fever'],
                            'standard_missing_information': ['Response to empirical PPI trial', 'Postural association'],
                            'sources': ['ACG Clinical Guideline for the Diagnosis and Management of GERD (2022)']
                        },
                        {
                            'label': 'Cholelithiasis / Biliary Colic',
                            'code': 'K80.2',
                            'code_system': 'ICD-10-MOCK',
                            'rationale': 'Episodic right upper quadrant or epigastric pain precipitated by fatty meals, lasting 1 to 5 hours.',
                            'supporting_findings_pool': ['right upper quadrant pain', 'postprandial pain', 'radiation to right shoulder or back'],
                            'contradicting_findings_pool': ['relief with food', 'continuous pain > 24 hours without fever'],
                            'standard_missing_information': ['Abdominal ultrasound', 'Liver function tests (bilirubin, ALT, ALP)'],
                            'sources': ['WSES Guidelines for the Management of Acute Cholecystitis and Biliary Colic']
                        }
                    ]
                }),
                'Heuristic differential for upper abdominal and dyspeptic presentations.',
                'Assess for alarm symptoms (dysphagia, hematemesis, melena, unintentional weight loss). Prompt endoscopy if alarm features present.',
                'approved_active', 'Dr. Farooq Khan, MD', 'Governance Committee'
            )
        ]
        for r_id, code, ver, rtype, title, scope, src_id, sev, req_in, logic, rat, act, gov, owner, rev in ddx_rules_data:
            conn.execute("""
                INSERT OR REPLACE INTO clinical_rule_definitions (
                    id, rule_id, rule_version, rule_type, title, scope, source_id, severity,
                    required_inputs_json, logic_definition_json, plain_language_rationale,
                    recommended_action, governance_status, clinical_owner, reviewer_name, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (r_id, code, ver, rtype, title, scope, src_id, sev, req_in, logic, rat, act, gov, owner, rev))

        # Governed Investigation Guidelines
        inv_rules_data = [
            (
                'rule-inv-001', 'RULE-INV-001', '1.0.0', 'INVESTIGATION_GUIDELINE', 'Upper GI Endoscopy for Dyspepsia with Alarm Features',
                'Gastroenterology', 'src-nice-cks-synth', 'URGENT',
                json.dumps(['chief_complaint']),
                json.dumps({
                    'trigger_terms': ['epigastric pain', 'dyspepsia', 'indigestion', 'heartburn'],
                    'investigations': [
                        {
                            'clinical_question': 'Is mucosal ulceration, Barrett esophagus, or malignancy present?',
                            'suggested_investigation': 'Diagnostic Esophagogastroduodenoscopy (Upper GI Endoscopy)',
                            'modality': 'ENDOSCOPY',
                            'rationale': 'NICE guidance recommends urgent direct visualization for patients with persistent dyspepsia and alarm symptoms (weight loss, dysphagia, vomiting) or age > 55.'
                        },
                        {
                            'clinical_question': 'Is active Helicobacter pylori colonization present in gastric mucosa?',
                            'suggested_investigation': 'Helicobacter pylori Stool Antigen Test (HpSA)',
                            'modality': 'LABORATORY',
                            'rationale': 'First-line non-invasive assessment prior to empirical acid-suppressive therapy.'
                        }
                    ]
                }),
                'Targeted investigations to rule out organic pathology in chronic dyspepsia.',
                'Document clinical decision to order or defer with patient informed consent.',
                'approved_active', 'Dr. Farooq Khan, MD', 'Governance Committee'
            ),
            (
                'rule-inv-002', 'RULE-INV-002', '1.0.0', 'INVESTIGATION_GUIDELINE', '12-Lead ECG & Biomarkers for Acute Chest Discomfort',
                'Cardiology', 'src-nice-cks-synth', 'EMERGENT',
                json.dumps(['chief_complaint']),
                json.dumps({
                    'trigger_terms': ['chest pain', 'angina', 'chest pressure', 'substernal pain'],
                    'associated_red_flags': ['RULE-RF-001'],
                    'investigations': [
                        {
                            'clinical_question': 'Are ischemic ST-T changes, bundle branch block, or arrhythmia present?',
                            'suggested_investigation': 'Standard 12-Lead Resting Electrocardiogram (ECG)',
                            'modality': 'CARDIOLOGY_ECG',
                            'rationale': 'Mandatory diagnostic test within 10 minutes of clinical encounter for all patients with acute non-traumatic chest discomfort.'
                        },
                        {
                            'clinical_question': 'Is there measurable myocardial injury or necrosis?',
                            'suggested_investigation': 'High-Sensitivity Cardiac Troponin I / T',
                            'modality': 'LABORATORY',
                            'rationale': 'Definitive biochemical marker for acute myocardial infarction.'
                        }
                    ]
                }),
                'Essential diagnostic protocol for acute chest symptoms.',
                'Obtain immediate ECG without delaying emergency supportive interventions.',
                'approved_active', 'Dr. Farooq Khan, MD', 'Governance Committee'
            )
        ]
        for r_id, code, ver, rtype, title, scope, src_id, sev, req_in, logic, rat, act, gov, owner, rev in inv_rules_data:
            conn.execute("""
                INSERT OR REPLACE INTO clinical_rule_definitions (
                    id, rule_id, rule_version, rule_type, title, scope, source_id, severity,
                    required_inputs_json, logic_definition_json, plain_language_rationale,
                    recommended_action, governance_status, clinical_owner, reviewer_name, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (r_id, code, ver, rtype, title, scope, src_id, sev, req_in, logic, rat, act, gov, owner, rev))

        # 23. Capability Registry (Updated with Prompt 03, 04, and 05 Engines)
        capabilities_seed = [
            ('core.identity', 'Identity and Tenancy Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'users:manage'),
            ('core.tenancy', 'Organization/Facility Scope Filter', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'facility:manage'),
            ('core.rbac', 'Role-Based Access Control Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'users:manage'),
            ('core.audit', 'Append-Only Audit Event Logger', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'audit:read'),
            ('core.capabilities', 'Capability & Engine State Registry', '1.1.0', 'FUNCTIONALLY_TESTED', 1, None, 'capabilities:read'),
            
            # Prompt 02: Core Clinical Workflow
            ('clinical.patients_mpi', 'Master Patient Index & Demographics Registry', '1.2.0', 'FUNCTIONALLY_TESTED', 1, None, 'patient:read'),
            ('clinical.encounters', 'Encounter Lifecycle & OPD Queue Engine', '1.2.0', 'FUNCTIONALLY_TESTED', 1, None, 'encounter:read'),
            
            # Prompt 03: Formulation Library, Prescription Engine, and Safety Preflight
            ('clinical.formulary', 'Formulation Library & Monograph Provenance Engine', '1.3.0', 'FUNCTIONALLY_TESTED', 1, None, 'formulary:read'),
            ('clinical.prescriptions_nuskha', 'Nuskha Builder, Posology & Digital Signing Engine', '1.3.0', 'FUNCTIONALLY_TESTED', 1, None, 'prescription:sign'),
            ('clinical.safety_preflight', 'Deterministic Safety Preflight Engine (Allergies, Mudabbar, Contraindications)', '1.3.0', 'FUNCTIONALLY_TESTED', 1, None, 'prescription:validate'),
            
            # Prompt 04: Unani Clinical Assessment, Organ-Axis Mapping, and Usul-e-Ilaj Care Planning
            ('clinical.unani_assessment', 'Unani Clinical Assessment & Provenance Engine', '1.4.0', 'FUNCTIONALLY_TESTED', 1, None, 'assessment:read'),
            ('clinical.organ_axis', 'Organ-Axis Contextual Mapping Layer', '1.4.0', 'FUNCTIONALLY_TESTED', 1, None, 'organ_axis:read'),
            ('clinical.usul_e_ilaj_planner', 'Usul-e-Ilaj Treatment Principles & Care Plan Engine', '1.4.0', 'FUNCTIONALLY_TESTED', 1, None, 'care_plan:read'),

            # Prompt 05: Modern Clinical Assessment & Decision Support
            ('clinical.modern_assessment', 'Modern Clinical Assessment & Problem List Engine', '1.5.0', 'FUNCTIONALLY_TESTED', 1, None, 'modern_assessment:read'),
            ('clinical.decision_support_rules', 'Governed Red-Flag and Differential Decision Rules Catalog', '1.5.0', 'FUNCTIONALLY_TESTED', 1, None, 'clinical_rules:read'),

            # Future clinical engines: STRICTLY NOT_IMPLEMENTED in Phase 1
            ('clinical.consultation', 'Single 3-Zone Consultation Canvas', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Prescribing vertical complete; full 3-zone canvas scheduled for Phase 3', 'encounters:write'),
            ('clinical.unani_mizaj', 'Unani Mizaj & Ajnas Scoring Engine', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Automated score classifier disabled; clinician-entered assessment active in clinical.unani_assessment', 'encounters:write'),
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

        conn.execute("PRAGMA foreign_keys = ON;")
        conn.commit()
        print("[SEED] Successfully seeded synthetic development dataset.")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_development_data()


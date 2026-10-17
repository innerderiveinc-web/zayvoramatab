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
            ('role-cashier', 'CASHIER', 'Billing & Cashier Officer', 'Invoices, payments, receipts and daily collections'),
            ('role-inventory-manager', 'INVENTORY_MANAGER', 'Inventory & Stock Manager', 'Stock receipts, batches, stocktakes and adjustments'),
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
            ('perm-clin-rules-manage', 'clinical_rules:manage', 'Manage Clinical Decision Rules & Sources', 'GOVERNANCE'),
            ('perm-knowledge-read', 'knowledge:read', 'Search and Read Clinical Knowledge & Citations', 'CLINICAL'),
            ('perm-knowledge-manage', 'knowledge:manage', 'Author, Review, and Approve Clinical Knowledge & Sources', 'GOVERNANCE'),
            # Prompt 08 Unified Consultation Workspace & Orchestrator Permissions
            ('perm-enc-finalize', 'encounter:finalize', 'Electronically Sign and Finalize Consultations', 'CLINICAL'),
            ('perm-enc-sign', 'encounter:sign', 'Electronic Signature on Encounter Documents', 'CLINICAL'),
            ('perm-enc-sections', 'encounter:manage_sections', 'Manage Consultation Guided Section States', 'CLINICAL'),
            # Prompt 09 Care Continuity, Follow-up, Patient Communications & Outcome Tracking Permissions
            ('perm-fup-read', 'followup:read', 'View Follow-up Plans, Tasks & Queues', 'CLINICAL'),
            ('perm-fup-write', 'followup:write', 'Create and Update Follow-up Plans, Tasks & Appointments', 'CLINICAL'),
            ('perm-fup-assign', 'followup:assign', 'Assign Follow-up Tasks', 'CLINICAL'),
            ('perm-comm-prefs', 'communications:manage_preferences', 'Manage Patient Communication Preferences & Opt-Out', 'OPERATIONS'),
            ('perm-comm-send', 'communications:send', 'Queue and Dispatch Governed Patient Communications', 'OPERATIONS'),
            ('perm-comm-tpl', 'communications:approve_templates', 'Author and Approve Communication Templates', 'GOVERNANCE'),
            ('perm-out-read', 'outcomes:read', 'View Longitudinal Clinical Outcomes & Trends', 'CLINICAL'),
            ('perm-out-rec', 'outcomes:record', 'Record Clinical and Patient-Reported Outcomes', 'CLINICAL'),
            ('perm-adr-report', 'adverse_effects:report', 'Report Suspected Adverse Medication Effects', 'CLINICAL'),
            ('perm-adr-review', 'adverse_effects:review', 'Clinically Review and Escalate Adverse Effect Reports', 'CLINICAL'),
            # Prompt 10 Clinic Operations OS (Appointments, Queue, Billing, Inventory & Dispensing)
            ('perm-ops-read', 'operations:read', 'View Clinic Today Dashboard & Operational Status', 'OPERATIONS'),
            ('perm-sched-manage', 'scheduling:manage', 'Configure Practitioner Schedules & Leave Blocks', 'OPERATIONS'),
            ('perm-appt-read', 'appointments:read', 'View Clinic Appointments & Availability', 'OPERATIONS'),
            ('perm-appt-write', 'appointments:write', 'Book, Check-in, Reschedule & Cancel Appointments', 'OPERATIONS'),
            ('perm-queue-read', 'queue:read', 'View OPD Waiting Queue', 'OPERATIONS'),
            ('perm-queue-write', 'queue:write', 'Issue Queue Tokens & Transition Queue States', 'OPERATIONS'),
            ('perm-queue-prio', 'queue:priority_override', 'Authorize Urgent Clinical Queue Priority', 'OPERATIONS'),
            ('perm-bill-read', 'billing:read', 'View Invoices, Receipts & Collections', 'BILLING'),
            ('perm-bill-write', 'billing:write', 'Create Invoices & Record Payments', 'BILLING'),
            ('perm-bill-cat', 'billing:manage_catalog', 'Configure Clinic Service & Fee Catalog', 'BILLING'),
            ('perm-bill-refund', 'billing:refund_void', 'Authorize Payment Refunds & Invoice Voids', 'BILLING'),
            ('perm-inv-read', 'inventory:read', 'View Dispensary Inventory, Stock & Batches', 'INVENTORY'),
            ('perm-inv-write', 'inventory:write', 'Manage Inventory Items & Receive Stock', 'INVENTORY'),
            ('perm-inv-adj', 'inventory:adjust', 'Record Inventory Adjustments, Quarantine & Stocktakes', 'INVENTORY'),
            ('perm-disp-read', 'dispensing:read', 'View Prescription Dispensing Records', 'INVENTORY'),
            ('perm-disp-write', 'dispensing:write', 'Dispense Signed Prescriptions', 'INVENTORY'),
            ('perm-rep-read', 'reports:read', 'View Clinic Operational Reports', 'OPERATIONS'),
            # Prompt 11 Multi-Doctor, Multi-Branch & Hospital Administration Foundation
            ('perm-ent-org', 'enterprise:org_manage', 'Manage Enterprise Organization Hierarchy & Lifecycle', 'ENTERPRISE'),
            ('perm-ent-fac', 'enterprise:facility_manage', 'Manage Branch Facilities & Activation Lifecycle', 'ENTERPRISE'),
            ('perm-ent-dept', 'enterprise:department_manage', 'Manage Facility Departments, Units & Rooms', 'ENTERPRISE'),
            ('perm-ent-assign', 'enterprise:assignment_manage', 'Manage Scoped Staff & Practitioner Assignments', 'ENTERPRISE'),
            ('perm-ent-cfg', 'enterprise:config_manage', 'Manage Layered Configuration & Overrides', 'ENTERPRISE'),
            ('perm-ent-mod', 'enterprise:module_manage', 'Manage Facility Module Entitlements', 'ENTERPRISE'),
            ('perm-ent-trf-r', 'enterprise:transfer_read', 'View Inter-Facility Transfers & Referrals', 'ENTERPRISE'),
            ('perm-ent-trf-w', 'enterprise:transfer_write', 'Initiate, Accept & Complete Inter-Facility Transfers', 'ENTERPRISE'),
            ('perm-ent-merge', 'enterprise:patient_merge', 'Review & Approve Governed Patient Merges', 'ENTERPRISE'),
            ('perm-ent-intg', 'enterprise:integration_manage', 'Manage Hospital Integration Connectors', 'ENTERPRISE'),
            ('perm-ent-aud', 'enterprise:audit_read', 'Search Enterprise Administrative Audit Events', 'ENTERPRISE'),
            # Prompt 41 Enterprise Data Lifecycle, Retention & Disposal Permissions
            ('perm-lifecycle-read', 'lifecycle:read', 'View Data Lifecycle Inventory, Policies & Runs', 'LIFECYCLE'),
            ('perm-lifecycle-eval', 'lifecycle:evaluate', 'Execute Retention Evaluations & Dry-Runs', 'LIFECYCLE'),
            ('perm-lifecycle-hold', 'lifecycle:hold', 'Place & Release Legal Holds', 'LIFECYCLE'),
            ('perm-lifecycle-appr', 'lifecycle:approve', 'Approve Retention Policies & Deletion Actions', 'LIFECYCLE'),
            ('perm-lifecycle-exec', 'lifecycle:execute', 'Execute Governed Disposal & Archival Operations', 'LIFECYCLE'),
            ('perm-lifecycle-req', 'lifecycle:request', 'Manage Data Subject Privacy Requests', 'LIFECYCLE'),
            # Prompt 45 Enterprise Identity Governance, PAM & Certification Permissions
            ('perm-id-read', 'identity:read', 'View Identity Governance, Accounts, Elevations & Campaigns', 'IDENTITY'),
            ('perm-id-manage', 'identity:manage', 'Manage Identities, JML Lifecycles & Service Accounts', 'IDENTITY'),
            ('perm-id-elevate', 'identity:elevate', 'Request Just-In-Time PAM Privilege Elevation', 'IDENTITY'),
            ('perm-id-approve', 'identity:approve_elevation', 'Approve Just-In-Time Elevation Requests', 'IDENTITY'),
            ('perm-id-breakglass', 'identity:break_glass', 'Activate & Manage Emergency Break-Glass Sessions', 'IDENTITY'),
            ('perm-id-certify', 'identity:certify', 'Execute Access Certification Campaigns & Attestations', 'IDENTITY'),
            ('perm-id-remediate', 'identity:remediate', 'Execute & Verify Identity Access Remediation Actions', 'IDENTITY'),
            # Prompt 46 Enterprise Security Posture, Vulnerability Governance & Control Verification Permissions
            ('perm-sec-posture-read', 'security:posture_read', 'View Security Posture, Assets, Controls & Findings', 'SECURITY'),
            ('perm-sec-posture-manage', 'security:posture_manage', 'Manage Security Assets, Controls & Release Gates', 'SECURITY'),
            ('perm-sec-scan-exec', 'security:scan_execute', 'Execute Verification Scanners & Evidence Collectors', 'SECURITY'),
            ('perm-sec-vuln-triage', 'security:vulnerability_triage', 'Triage, Prioritize & Verify Vulnerability Findings', 'SECURITY'),
            ('perm-sec-exc-approve', 'security:exception_approve', 'Authorize Governed Security Exceptions & Risk Acceptances', 'SECURITY'),
            ('perm-sec-gate-eval', 'security:gate_evaluate', 'Evaluate Security Release Gates & Deployment Verification', 'SECURITY'),
            # Prompt 47 Threat Modeling, Abuse-Case Analysis & Secure SDLC Governance Permissions
            ('perm-tm-read', 'threat_model:read', 'View Threat Models, Trust Boundaries & SDLC Reviews', 'SECURITY'),
            ('perm-tm-manage', 'threat_model:manage', 'Manage Threat Models, Trust Boundaries & Controls', 'SECURITY'),
            ('perm-tm-review', 'threat_model:review', 'Review Threat Models & Authorize Scopes', 'SECURITY'),
            ('perm-tm-risk-accept', 'threat_model:risk_accept', 'Authorize Governed Residual Risk Decisions', 'SECURITY'),
            ('perm-sdlc-intake', 'sdlc:change_intake', 'Register SDLC Change Reviews & Scope Checks', 'SECURITY'),
            ('perm-sdlc-eval', 'sdlc:gate_evaluate', 'Evaluate SDLC Release Deployment Gates', 'SECURITY'),
            # Prompt 48 Clinical Safety Case, Hazard Analysis & Safety Control Governance Permissions
            ('perm-csc-read', 'safety_case:read', 'View Clinical Safety Cases, Hazards & Incident Reviews', 'SAFETY'),
            ('perm-csc-manage', 'safety_case:manage', 'Manage Clinical Hazards, Requirements & Incidents', 'SAFETY'),
            ('perm-csc-clin-review', 'safety_case:clinical_review', 'Authorize Clinical Hazards & Severity Sign-offs', 'SAFETY'),
            ('perm-csc-verify', 'safety_case:verify', 'Record Safety Control Verification Proofs', 'SAFETY'),
            ('perm-csc-approve', 'safety_case:approve_case', 'Formally Authorize Clinical Safety Cases', 'SAFETY'),
            ('perm-csc-gate-eval', 'safety_case:gate_evaluate', 'Evaluate Clinical Safety Release Deployment Gates', 'SAFETY'),
            # Prompt 49 End-to-End Test Automation, Regression & Release Qualification Permissions
            ('perm-test-qual-read', 'test_qualification:read', 'View Test Automation Suites, Runs & Qualifications', 'TESTING'),
            ('perm-test-qual-manage', 'test_qualification:manage', 'Manage Test Automation Suites, Profiles & Defects', 'TESTING'),
            ('perm-test-qual-exec', 'test_qualification:execute', 'Trigger Test Automation Runs & Evaluations', 'TESTING'),
            ('perm-test-qual-quar', 'test_qualification:quarantine', 'Quarantine and Re-enable Flaky Tests', 'TESTING'),
            ('perm-test-qual-rel', 'test_qualification:qualify_release', 'Formally Authorize Release Candidate Qualifications', 'TESTING')
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
        
        # CLINIC_ADMIN gets all clinical, governance, and clinic operations permissions
        for p_code in [
            'facility:manage', 'patients:read', 'patients:write', 'patient:read', 'patient:create', 'patient:update_demographics',
            'encounters:read', 'encounters:write', 'encounter:read', 'encounter:create', 'encounter:update_draft', 'encounter:cancel',
            'consent:read', 'consent:record', 'prescriptions:sign', 'capabilities:read',
            'formulary:read', 'formulary:draft_create', 'formulary:draft_update', 'formulary:submit_review', 'formulary:approve',
            'prescription:create_draft', 'prescription:read', 'prescription:update_draft', 'prescription:validate',
            'prescription:sign', 'prescription:amend', 'prescription:cancel', 'prescription:export',
            'assessment:read', 'assessment:create_draft', 'assessment:update_draft', 'assessment:finalise', 'assessment:amend',
            'template:read', 'template:manage', 'organ_axis:read', 'organ_axis:manage', 'usul_e_ilaj:read', 'usul_e_ilaj:manage',
            'care_plan:read', 'care_plan:create', 'care_plan:update', 'care_plan:finalise',
            'modern_assessment:read', 'modern_assessment:create_draft', 'modern_assessment:update_draft',
            'modern_assessment:cancel', 'clinical_rules:read', 'clinical_rules:manage',
            'knowledge:read', 'knowledge:manage',
            'encounter:finalize', 'encounter:sign', 'encounter:manage_sections',
            'followup:read', 'followup:write', 'followup:assign',
            'communications:manage_preferences', 'communications:send', 'communications:approve_templates',
            'outcomes:read', 'outcomes:record', 'adverse_effects:report', 'adverse_effects:review',
            'operations:read', 'scheduling:manage', 'appointments:read', 'appointments:write',
            'queue:read', 'queue:write', 'queue:priority_override',
            'billing:read', 'billing:write', 'billing:manage_catalog', 'billing:refund_void',
            'inventory:read', 'inventory:write', 'inventory:adjust', 'dispensing:read', 'dispensing:write', 'reports:read',
            'enterprise:facility_manage', 'enterprise:department_manage', 'enterprise:assignment_manage',
            'enterprise:config_manage', 'enterprise:module_manage', 'enterprise:transfer_read', 'enterprise:transfer_write',
            'lifecycle:read', 'lifecycle:evaluate', 'lifecycle:hold', 'lifecycle:request',
            'identity:read', 'identity:manage', 'identity:elevate',
            'security:posture_read', 'security:scan_execute',
            'threat_model:read', 'sdlc:change_intake',
            'safety_case:read', 'safety_case:manage', 'safety_case:clinical_review',
            'safety_case:verify', 'safety_case:approve_case', 'safety_case:gate_evaluate',
            'test_qualification:read', 'test_qualification:manage', 'test_qualification:execute',
            'test_qualification:quarantine', 'test_qualification:qualify_release'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-clinic-admin', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # PRACTITIONER gets full clinical assessment, prescribing, care planning, modern assessment, and clinical queue/appointment operations
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
            'clinical_rules:read', 'knowledge:read',
            'encounter:finalize', 'encounter:sign', 'encounter:manage_sections',
            'followup:read', 'followup:write', 'followup:assign',
            'communications:manage_preferences', 'communications:send', 'communications:approve_templates',
            'outcomes:read', 'outcomes:record', 'adverse_effects:report', 'adverse_effects:review',
            'operations:read', 'scheduling:manage', 'appointments:read', 'appointments:write',
            'queue:read', 'queue:write', 'queue:priority_override',
            'billing:read', 'inventory:read', 'dispensing:read', 'reports:read',
            'enterprise:transfer_read', 'enterprise:transfer_write',
            'safety_case:read', 'safety_case:manage', 'safety_case:clinical_review',
            'safety_case:verify', 'safety_case:approve_case', 'safety_case:gate_evaluate',
            'test_qualification:read', 'test_qualification:manage', 'test_qualification:execute',
            'test_qualification:quarantine', 'test_qualification:qualify_release'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-practitioner', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # RECEPTIONIST gets front-desk registration, appointments, queue tokens, basic invoice/payment recording, and follow-up scheduling (NO clinical notes or refund/void authority)
        for p_code in [
            'patients:read', 'patients:write', 'patient:read', 'patient:create', 'patient:update_demographics', 'patient:resolve_duplicate',
            'encounters:read', 'encounter:read', 'encounter:create', 'encounter:cancel',
            'consent:read', 'consent:record', 'capabilities:read', 'prescription:read', 'prescription:export',
            'care_plan:read', 'followup:read', 'followup:write', 'communications:manage_preferences', 'communications:send',
            'operations:read', 'appointments:read', 'appointments:write', 'queue:read', 'queue:write',
            'billing:read', 'billing:write'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-receptionist', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # PHARMACIST gets formulary read, prescription read, inventory read/adjust, and dispensing read/write (NO clinical assessment notes or prescribing)
        for p_code in [
            'patients:read', 'patient:read', 'formulary:read', 'prescription:read', 'prescription:export',
            'capabilities:read', 'care_plan:read', 'operations:read',
            'inventory:read', 'inventory:write', 'inventory:adjust', 'dispensing:read', 'dispensing:write'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-pharmacist', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # CASHIER gets billing, invoicing, payment recording, refunds/voids, and collections report (NO clinical notes or prescription signing)
        for p_code in [
            'patients:read', 'patient:read', 'capabilities:read', 'operations:read',
            'billing:read', 'billing:write', 'billing:refund_void', 'reports:read'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-cashier', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # INVENTORY_MANAGER gets stock receipt, batch management, adjustments, and stocktakes (NO prescription signing or clinical amendments)
        for p_code in [
            'formulary:read', 'capabilities:read', 'operations:read',
            'inventory:read', 'inventory:write', 'inventory:adjust', 'dispensing:read', 'reports:read'
        ]:
            conn.execute("""
                INSERT OR IGNORE INTO role_permissions (role_id, permission_id) 
                SELECT 'role-inventory-manager', id FROM permissions WHERE code = ?;
            """, (p_code,))

        # READ_ONLY_AUDITOR gets read-only access across clinical, operational, billing, and inventory domains
        for p_code in [
            'audit:read', 'patients:read', 'patient:read', 'encounters:read', 'encounter:read', 'consent:read',
            'formulary:read', 'prescription:read', 'assessment:read', 'care_plan:read', 'organ_axis:read',
            'usul_e_ilaj:read', 'capabilities:read', 'operations:read', 'appointments:read', 'queue:read',
            'billing:read', 'inventory:read', 'dispensing:read', 'reports:read'
        ]:
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
            ('usr-cashier-1', 'cashier', 'cashier.synthetic@zayvora.test', pw_hash, '[SYNTHETIC] Nadeem Khan (Cashier)', 'role-cashier'),
            ('usr-inv-1', 'inventory', 'inventory.synthetic@zayvora.test', pw_hash, '[SYNTHETIC] Salman Mirza (Inventory Manager)', 'role-inventory-manager'),
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

            # Facility Memberships (belong to fac-central-opd)
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

        # 23. Governed Knowledge Sources Registry (Prompt 06)
        knowledge_sources_seed = [
            (
                'src-qanun-synth',
                'Al-Qanun fi al-Tibb (The Canon of Medicine) [Synthetic Classical Monograph]',
                'Ibn Sina (Avicenna)', 'CCRUM & Classical Archives', 'CLASSICAL_TEXT', 'Book I & II',
                '1025', 'URN:NBS:UNANI:CANON:001', 'ar', 'GLOBAL', 'APPROVED_STANDARD',
                'CLASSICAL_COMPENDIUM_GRADE_D', 'a1b2c3d4e5canonhash', 'Dr. Hakim Tariq Jamil', 'APPROVED',
                'Authoritative classical reference on Mizaj, Humors, and Simple Drugs.', 1
            ),
            (
                'src-upi-synth',
                'Unani Pharmacopoeia of India (UPI) [Synthetic Pharmacopoeial Standard]',
                'Pharmacopoeia Commission for Indian Medicine & Homoeopathy (PCIM&H)',
                'Ministry of AYUSH, Govt of India', 'PHARMACOPOEIA', 'Vol I & II',
                '2016', 'ISBN:978-81-901151-2-1', 'en', 'IN', 'APPROVED_STANDARD',
                'SYSTEMATIC_REVIEW_GRADE_A', 'f6e5d4c3b2upihash', 'Pharmacopoeia Committee', 'APPROVED',
                'Official statutory monograph standard for identity, purity, posology, and Tadbeer.', 1
            ),
            (
                'src-nice-dyspepsia-synth',
                'Gastro-oesophageal reflux disease and dyspepsia in adults (NG1) [Synthetic Clinical Guideline]',
                'National Institute for Health and Care Excellence (NICE)',
                'NICE Guidelines', 'CLINICAL_GUIDELINE', 'Guideline NG1',
                '2019', 'https://www.nice.org.uk/guidance/ng1', 'en', 'NICE_UK', 'APPROVED_STANDARD',
                'SYSTEMATIC_REVIEW_GRADE_A', 'c3d4e5f6g7nicehash', 'NICE Guideline Development Group', 'APPROVED',
                'Evidence-based clinical guideline for investigation, red flags, and management of adult dyspepsia.', 1
            ),
            (
                'src-who-cough-synth',
                'WHO Clinical Practice Handbook for Respiratory Symptoms [Synthetic Guideline]',
                'World Health Organization (WHO)', 'WHO Press', 'CLINICAL_GUIDELINE', '2nd Edition',
                '2021', 'https://who.int/publications/cough-stg', 'en', 'WHO', 'APPROVED_STANDARD',
                'SYSTEMATIC_REVIEW_GRADE_A', 'e7f8g9h0i1whohash', 'WHO Clinical Review Panel', 'APPROVED',
                'Standard clinical algorithms for evaluating acute and subacute cough in primary care.', 1
            )
        ]
        for s_id, title, auth, pub, stype, ed, pdate, uid, lang, jur, reg, ev_lvl, dhash, rev, rstat, notes, is_syn in knowledge_sources_seed:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_sources (
                    id, title, authors_or_org, publisher, source_type, edition,
                    publication_date, url_or_identifier, language, jurisdiction,
                    regulatory_status, evidence_level, document_hash, ingestion_date,
                    verification_date, reviewer_name, review_status, notes, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?);
            """, (s_id, title, auth, pub, stype, ed, pdate, uid, lang, jur, reg, ev_lvl, dhash, rev, rstat, notes, is_syn))

        # 24. Governed Knowledge Items (Concepts, Herbs, Formulations, Principles)
        knowledge_items_seed = [
            (
                'ki-senna-synth', 'UNANI', 'SINGLE_DRUG', 'Senna (Cassia angustifolia / Sana Makki)',
                json.dumps(['Sana Makki', 'Cassia senna', 'Senna alexandrina', 'Sana']), 'en',
                'Classical Unani purgative botanical used for Tanqia-e-Mawad (evacuation of morbid humors).',
                json.dumps({'temperament': 'Hot 1, Dry 2', 'primary_action': 'Mushil-e-Safra wa Balgham', 'dose_range': '3-7 g'}),
                'PRIMARY_CARE', 'pharmacopoeial_specification', 'CLASSICAL_COMPENDIUM_GRADE_D',
                'approved', '1.0', 'usr-hakeem-1', 'usr-admin-1', 2, 1
            ),
            (
                'ki-filfil-siah-synth', 'UNANI', 'SINGLE_DRUG', 'Filfil Siah (Piper nigrum / Black Pepper)',
                json.dumps(['Black Pepper', 'Kali Mirch', 'Piper nigrum']), 'en',
                'Kasir-e-Riyah (carminative) and Muqawwi-e-Meda (stomachic) drug used in digestive and cold dystemperaments.',
                json.dumps({'temperament': 'Hot 3, Dry 3', 'primary_action': 'Hazim, Kasir-e-Riyah', 'dose_range': '0.5-1 g'}),
                'PRIMARY_CARE', 'traditional_use', 'CLASSICAL_COMPENDIUM_GRADE_D',
                'approved', '1.0', 'usr-hakeem-1', 'usr-admin-1', 1, 1
            ),
            (
                'ki-balghami-mizaj-synth', 'UNANI', 'MIZAJ', 'Mizaj Balghami (Phlegmatic Temperament)',
                json.dumps(['Phlegmatic Temperament', 'Cold and Moist Temperament', 'Mizaj Barid Ratab', 'balgham']), 'en',
                'Primary temperamental state characterized by coldness and moisture, slow digestion, and pale complexion.',
                json.dumps({'quality': 'Barid Ratab (Cold & Moist)', 'predominant_humor': 'Balgham', 'pulse_quality': 'Bati, Layyin'}),
                'OUTPATIENT', 'classical_description', 'CLASSICAL_COMPENDIUM_GRADE_D',
                'approved', '1.0', 'usr-hakeem-1', 'usr-admin-1', 1, 1
            ),
            (
                'ki-dyspepsia-synth', 'MODERN_CLINICAL', 'DISEASE', 'Dyspepsia (Functional & Organic)',
                json.dumps(['Indigestion', 'Su-e-Hazm', 'Gastric discomfort', 'IBS']), 'en',
                'Symptom complex of epigastric pain, early satiety, and postprandial fullness.',
                json.dumps({'icd10': 'K30', 'guideline': 'NICE NG1', 'red_flags': ['Dysphagia', 'Weight loss', 'GI bleeding']}),
                'PRIMARY_CARE', 'clinical_guideline', 'SYSTEMATIC_REVIEW_GRADE_A',
                'approved', '1.0', 'usr-admin-1', 'usr-admin-1', 2, 1
            ),
            (
                'ki-cough-synth', 'MODERN_CLINICAL', 'SYMPTOM', 'Acute Cough (Su\'al)',
                json.dumps(['Khansi', 'Respiratory cough', 'Sual', 'Bronchitis']), 'en',
                'Sudden onset reflex clearing of respiratory airway lasting under 3 weeks.',
                json.dumps({'icd10': 'R05', 'guideline': 'WHO STG', 'red_flags': ['Hemoptysis', 'Stridor', 'High fever']}),
                'OUTPATIENT', 'clinical_guideline', 'SYSTEMATIC_REVIEW_GRADE_A',
                'approved', '1.0', 'usr-admin-1', 'usr-admin-1', 2, 1
            )
        ]
        for ki_id, dom, etype, cname, aliases, lang, desc, attr, scope, ctype, ev_lvl, stat, ver, cr_by, rev_by, scount, is_syn in knowledge_items_seed:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_items (
                    id, domain, entity_type, canonical_name, aliases_json, language,
                    description, structured_attributes_json, clinical_scope, claim_type,
                    evidence_level, status, version, created_by, reviewed_by, approved_at,
                    source_count, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?);
            """, (ki_id, dom, etype, cname, aliases, lang, desc, attr, scope, ctype, ev_lvl, stat, ver, cr_by, rev_by, scount, is_syn))

        # 25. Atomic Claims Seed (Granular assertions)
        claims_seed = [
            (
                'clm-senna-01', 'ki-senna-synth',
                'Senna leaves contain sennosides A and B which stimulate colon motility for evacuation of humors.',
                'pharmacopoeial_specification', json.dumps(['Constipation', 'Tanqia-e-Mawad']),
                'HIGH', 'approved', 'usr-admin-1', 'APPROVED',
                'Contraindicated in mechanical bowel obstruction, inflammatory bowel disease, and severe dehydration.', 1
            ),
            (
                'clm-senna-02', 'ki-senna-synth',
                'Traditional Unani formulation practice specifies corrective processing (Tadbeer/Musleh) with Gulqand or Roghan Badam to prevent griping.',
                'traditional_use', json.dumps(['Tadbeer', 'Musleh', 'Griping']),
                'MODERATE', 'approved', 'usr-admin-1', 'APPROVED',
                'Classical practice consensus; supported by centuries of empirical clinical records.', 1
            ),
            (
                'clm-dyspepsia-01', 'ki-dyspepsia-synth',
                'Routine endoscopy is not recommended in uninvestigated dyspepsia under age 55 without alarm signs (NICE NG1).',
                'clinical_guideline', json.dumps(['Dyspepsia', 'Endoscopy', 'Red Flags']),
                'HIGH', 'approved', 'usr-admin-1', 'APPROVED',
                'Patients over 55 with persistent symptoms or alarm symptoms require urgent referral.', 1
            ),
            (
                'clm-balgham-01', 'ki-balghami-mizaj-synth',
                'Individuals of Balghami temperament are prone to slow gastrointestinal transit, mucoid stool, and sluggish metabolic functions.',
                'classical_description', json.dumps(['Balgham', 'Dyspepsia', 'Bowel motility']),
                'MODERATE', 'approved', 'usr-admin-1', 'APPROVED',
                'Qualitative constitutional assessment; clinical correlation required with physical signs.', 1
            )
        ]
        for c_id, it_id, ctext, ctype, lconcepts, estrength, stat, rev_id, app_state, limits, is_syn in claims_seed:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_claims (
                    id, item_id, claim_text, claim_type, linked_concepts_json,
                    evidence_strength, status, reviewer_id, reviewed_at, approval_state,
                    clinical_limitations, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?);
            """, (c_id, it_id, ctext, ctype, lconcepts, estrength, stat, rev_id, app_state, limits, is_syn))

        # 26. Evidence Appraisals & Citations Seed
        evidence_seed = [
            (
                'evd-senna-01', 'clm-senna-01', 'src-upi-synth', 'SYSTEMATIC_REVIEW',
                'Adult ambulatory patients with acute constipation', 'Oral standardized sennoside extract',
                'Placebo', 'Demonstrated laxative response within 6 to 12 hours', 120,
                'Significant reduction in colonic transit time and softened stool consistency.',
                'Chronic unsupervised use exceeding 7 days may result in electrolyte depletion.',
                'LOW', 'GRADE_A', 'evidence_exists', '2016', 'UPI Vol II, Monograph Senna'
            ),
            (
                'evd-dyspepsia-01', 'clm-dyspepsia-01', 'src-nice-dyspepsia-synth', 'SYSTEMATIC_REVIEW',
                'Adult primary care dyspepsia cohort', 'H. pylori test-and-treat vs empiric PPI',
                'Direct endoscopy', 'Equivalent symptom resolution with 78% reduction in invasive procedures', 1450,
                'Empiric non-invasive strategy is safe and cost-effective in the absence of alarm signs.',
                'Applicable only when red flag indicators (dysphagia, bleeding, persistent vomiting) are absent.',
                'LOW', 'GRADE_A', 'evidence_exists', '2019', 'NICE NG1 Section 1.3'
            )
        ]
        for e_id, c_id, s_id, stype, pop, intv, comp, outc, ss, rsum, lim, rbias, egrd, estat, pdate, page in evidence_seed:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_evidence (
                    id, claim_id, source_id, study_type, population, intervention_or_exposure,
                    comparator, outcome, sample_size, result_summary, limitations,
                    risk_of_bias, evidence_grade, evidence_status, publication_date,
                    page_or_section, reviewer_id, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'usr-admin-1', 'APPROVED');
            """, (e_id, c_id, s_id, stype, pop, intv, comp, outc, ss, rsum, lim, rbias, egrd, estat, pdate, page))

            # Matching citation
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_citations (
                    id, claim_id, source_id, citation_type, location_in_source, quote_or_excerpt
                ) VALUES (?, ?, ?, 'SUPPORTING', ?, ?);
            """, (f"cit-{e_id}", c_id, s_id, page, rsum))

        # 27. Graph-Compatible Relationships Seed
        relationships_seed = [
            ('rel-001', 'ki-dyspepsia-synth', 'HAS_SYMPTOM', 'ki-cough-synth', 'DIRECTED', 'PROVISIONAL', 'GERD-induced chronic cough axis', 'src-nice-dyspepsia-synth'),
            ('rel-002', 'ki-balghami-mizaj-synth', 'ASSOCIATED_WITH', 'ki-dyspepsia-synth', 'DIRECTED', 'DEFINITIVE', 'Classical Su-e-Mizaj Barid predisposition to slow gastric emptying', 'src-qanun-synth'),
            ('rel-003', 'ki-senna-synth', 'HAS_PRECAUTION', 'ki-dyspepsia-synth', 'DIRECTED', 'DEFINITIVE', 'Avoid high dose Senna in inflammatory abdominal distress without Musleh', 'src-upi-synth')
        ]
        for r_id, s_item, r_type, t_item, direct, strn, cnotes, s_id in relationships_seed:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge_relationships (
                    id, source_item_id, relationship_type, target_item_id,
                    directionality, strength, context_notes, source_id, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'APPROVED');
            """, (r_id, s_item, r_type, t_item, direct, strn, cnotes, s_id))

        # 28. Normalized Substances Catalog (Prompt 07)
        substances_seed = [
            (
                'sub-senna', 'Senna', 'BOTANICAL', 'Cassia angustifolia', 'Leaves', 'Purified Dried Foliage',
                'A06AB06', 'Hot 1, Dry 2', 'NON_TOXIC', 0, 'RESOLVED', 'APPROVED', 1
            ),
            (
                'sub-filfil-siah', 'Filfil Siah', 'BOTANICAL', 'Piper nigrum', 'Fruit', 'Coarse Powder',
                'A16AX', 'Hot 3, Dry 3', 'NON_TOXIC', 0, 'RESOLVED', 'APPROVED', 1
            ),
            (
                'sub-azaraqi', 'Azaraqi (Kuchla)', 'BOTANICAL', 'Strychnos nux-vomica', 'Seeds', 'Mudabbar Detoxified Seeds',
                'N07XX', 'Hot 4, Dry 4', 'SCHEDULE_E1_POISON', 1, 'RESOLVED', 'APPROVED', 1
            ),
            (
                'sub-digoxin', 'Digoxin', 'SYNTHETIC_ALLOPATHIC', None, None, 'Pharmaceutical Grade',
                'C01AA05', None, 'CAUTION_RESTRICTED', 0, 'RESOLVED', 'APPROVED', 1
            ),
            (
                'sub-warfarin', 'Warfarin', 'SYNTHETIC_ALLOPATHIC', None, None, 'Pharmaceutical Grade',
                'B01AA03', None, 'CAUTION_RESTRICTED', 0, 'RESOLVED', 'APPROVED', 1
            )
        ]
        for s_id, cname, stype, bname, part, prep, code, temp, tox, mud, rstat, rev_stat, is_syn in substances_seed:
            conn.execute("""
                INSERT OR REPLACE INTO normalized_substances (
                    id, canonical_name, substance_type, botanical_binomial, plant_part,
                    preparation_details, atc_or_rxnorm_code, unani_temperament, toxicity_classification,
                    is_mudabbar_required, resolution_status, review_status, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (s_id, cname, stype, bname, part, prep, code, temp, tox, mud, rstat, rev_stat, is_syn))

        # 29. Substance Aliases & Transliterations
        aliases_seed = [
            ('al-senna-1', 'sub-senna', 'Sana Makki', 'ur', 1),
            ('al-senna-2', 'sub-senna', 'Cassia senna', 'en', 0),
            ('al-senna-3', 'sub-senna', 'Senna alexandrina', 'en', 0),
            ('al-filfil-1', 'sub-filfil-siah', 'Black Pepper', 'en', 1),
            ('al-filfil-2', 'sub-filfil-siah', 'Kali Mirch', 'hi', 1),
            ('al-azaraqi-1', 'sub-azaraqi', 'Kuchla', 'ur', 1),
            ('al-azaraqi-2', 'sub-azaraqi', 'Nux Vomica', 'en', 1),
            ('al-azaraqi-3', 'sub-azaraqi', 'Strychnos nux-vomica', 'en', 0)
        ]
        for a_id, s_id, aname, lang, pref in aliases_seed:
            conn.execute("""
                INSERT OR REPLACE INTO substance_aliases (
                    id, substance_id, alias_name, language, is_preferred
                ) VALUES (?, ?, ?, ?, ?);
            """, (a_id, s_id, aname, lang, pref))

        # 30. Governed Safety Rules
        safety_rules_seed = [
            (
                'rule-saf-allg-01', 'SAF-ALLERGY-001', 'ALLERGY_MATCH',
                'Documented Patient Allergy Match',
                'Prescribed product or constituent ingredient matches patient documented allergy record.',
                json.dumps({'match_target': 'allergen_name'}), json.dumps(['allergies']),
                'critical', 'established', 'Discontinue prescribed item immediately.',
                'Cross-reactivity between botanical families requires verified clinical monograph.',
                'src-upi-synth', 'SYSTEMATIC_REVIEW_GRADE_A', 'approved', '1.0.0', 0, 1
            ),
            (
                'rule-saf-tox-01', 'SAF-TOX-001', 'CONTRAINDICATION',
                'Schedule E(1) Toxin / Mudabbar Verification',
                'Substance is a Schedule E(1) restricted toxic botanical requiring verified Mudabbar processing.',
                json.dumps({'toxicity_class': 'SCHEDULE_E1_POISON', 'mudabbar_required': 1}), json.dumps([]),
                'critical', 'established', 'Verify and document certified Mudabbar detoxification prior to sign-off.',
                'Unprocessed botanical administration strictly prohibited by AYUSH drug rules.',
                'src-upi-synth', 'SYSTEMATIC_REVIEW_GRADE_A', 'approved', '1.0.0', 0, 1
            ),
            (
                'rule-saf-preg-senna', 'SAF-PREG-SENNA', 'CONTRAINDICATION',
                'Pregnancy Contraindication: Stimulant Anthraquinone Laxatives',
                'High-dose stimulant anthraquinone laxatives (Senna) carry risk of reflex pelvic congestion.',
                json.dumps({'substance': 'Senna', 'condition': 'PREGNANCY'}), json.dumps(['is_pregnant']),
                'critical', 'established', 'Avoid Senna during first trimester; substitute bulk-forming Ispaghol.',
                'Short-term low dose under direct supervision in late pregnancy requires documented justification.',
                'src-nice-dyspepsia-synth', 'SYSTEMATIC_REVIEW_GRADE_A', 'approved', '1.0.0', 0, 1
            )
        ]
        for r_id, rcode, rtype, title, desc, trig, req_f, sev, cert, act, lim, src_id, ev_lvl, stat, ver, ovr, is_syn in safety_rules_seed:
            conn.execute("""
                INSERT OR REPLACE INTO safety_rules (
                    id, rule_code, rule_type, title, description, trigger_expression_json,
                    required_patient_factors_json, severity, certainty, action_guidance,
                    limitations, source_citation_id, evidence_level, status, version,
                    is_overridable, is_synthetic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (r_id, rcode, rtype, title, desc, trig, req_f, sev, cert, act, lim, src_id, ev_lvl, stat, ver, ovr, is_syn))

        # 31. Herb-Drug & Drug-Drug Interactions Catalog
        interactions_seed = [
            (
                'int-senna-digoxin', 'sub-senna', 'sub-digoxin', 'HERB_DRUG', 'critical', 'established',
                'Chronic or high-dose Senna laxative use may induce hypokalemia, significantly potentiating Digoxin cardiac toxicity.',
                'Increased risk of fatal cardiac arrhythmias and digitalis intoxication.',
                'Avoid concurrent administration. Monitor serum potassium and cardiac rhythm if co-prescribed.',
                'HUMAN_CLINICAL', 'src-nice-dyspepsia-synth', 'Risk correlates with duration of laxative overuse.', 'APPROVED', '1.0.0'
            ),
            (
                'int-filfil-warfarin', 'sub-filfil-siah', 'sub-warfarin', 'HERB_DRUG', 'moderate', 'probable',
                'Piperine in Filfil Siah inhibits CYP3A4 and P-glycoprotein, potentially elevating free plasma Warfarin concentration.',
                'Elevated INR and potential bleeding risk.',
                'Monitor International Normalized Ratio (INR) when introducing high doses of Filfil Siah.',
                'HUMAN_CLINICAL', 'src-who-cough-synth', 'Observed with standardized piperine extract doses > 20 mg/day.', 'APPROVED', '1.0.0'
            )
        ]
        for i_id, p_id, s_id, itype, sev, cert, cdesc, outc, mguid, etype, scit, lim, rstat, ver in interactions_seed:
            conn.execute("""
                INSERT OR REPLACE INTO interaction_records (
                    id, primary_substance_id, secondary_substance_id, interaction_type,
                    severity, certainty, clinical_description, reported_outcome, management_guidance,
                    evidence_type, source_citation_id, limitations, review_status, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (i_id, p_id, s_id, itype, sev, cert, cdesc, outc, mguid, etype, scit, lim, rstat, ver))

        # 32. Capability Registry (Updated with Prompt 07 Engine)
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

            # Prompt 06: Clinical Knowledge Base & Evidence Retrieval Engine
            ('clinical.knowledge_base', 'Governed Clinical Knowledge & Sources Registry', '1.6.0', 'FUNCTIONALLY_TESTED', 1, None, 'knowledge:read'),
            ('clinical.evidence_retrieval', 'Hybrid Evidence Retrieval & Contextual Citation Engine', '1.6.0', 'FUNCTIONALLY_TESTED', 1, None, 'knowledge:read'),

            # Prompt 07: Clinical Safety Firewall & Interaction Engine
            ('clinical.safety_firewall', 'Clinical Safety Firewall & Herb-Drug Interaction Engine', '1.7.0', 'FUNCTIONALLY_TESTED', 1, None, 'prescription:validate'),

            # Prompt 08: Unified Consultation Workspace & Clinical Workflow Orchestrator
            ('clinical.consultation_orchestrator', 'Unified Consultation Workspace & Workflow Orchestrator', '1.8.0', 'FUNCTIONALLY_TESTED', 1, None, 'encounters:write'),

            # Prompt 09: Follow-up, Care Continuity, Patient Communication & Outcome Tracking
            ('clinical.care_continuity', 'Follow-up Plans, Tasks & Repeat-Visit Continuity Engine', '1.9.0', 'FUNCTIONALLY_TESTED', 1, None, 'followup:read'),
            ('operations.patient_communications', 'Consent-Governed Patient Reminder Outbox & Sandbox Adapters', '1.9.0', 'FUNCTIONALLY_TESTED', 1, None, 'communications:send'),
            ('clinical.outcome_tracking', 'Longitudinal Outcome Tracking & Non-Causal Trend Engine', '1.9.0', 'FUNCTIONALLY_TESTED', 1, None, 'outcomes:read'),

            # Prompt 10: Clinic Operations OS (Appointments, Queue, Billing, Pharmacy Inventory & Dispensing)
            ('operations.appointments_queue', 'Appointment Scheduling, Slot Availability & OPD Token Queue Engine', '1.10.0', 'FUNCTIONALLY_TESTED', 1, None, 'appointments:read'),
            ('operations.billing_invoicing', 'Exact-Decimal Billing, Invoicing, Receipts & Reconciliation Engine', '1.10.0', 'FUNCTIONALLY_TESTED', 1, None, 'billing:read'),
            ('operations.pharmacy_inventory_ledger', 'FEFO Batch Dispensary Inventory Ledger & Stocktake Engine', '1.10.0', 'FUNCTIONALLY_TESTED', 1, None, 'inventory:read'),
            ('operations.prescription_dispensing', 'Signed-Prescription Verification & Dispensing Workflow Engine', '1.10.0', 'FUNCTIONALLY_TESTED', 1, None, 'dispensing:read'),
            ('operations.clinic_reports', 'Clinic Operational Dashboards & Reconciliation Reports Engine', '1.10.0', 'FUNCTIONALLY_TESTED', 1, None, 'reports:read'),

            # Prompt 11: Multi-Doctor, Multi-Branch & Hospital Administration Foundation
            ('enterprise.multi_branch_hierarchy', 'Multi-Branch Organization, Facility & Department Hierarchy Engine', '1.11.0', 'FUNCTIONALLY_TESTED', 1, None, 'enterprise:org_manage'),
            ('enterprise.scoped_assignments_rbac', 'Scoped Staff Assignments & Facility/Department RBAC/ABAC Engine', '1.11.0', 'FUNCTIONALLY_TESTED', 1, None, 'enterprise:assignment_manage'),
            ('enterprise.inter_facility_transfers', 'Controlled Inter-Facility Transfers, Referrals & Continuity Engine', '1.11.0', 'FUNCTIONALLY_TESTED', 1, None, 'enterprise:transfer_read'),
            ('enterprise.config_inheritance_modules', 'Layered Configuration Inheritance & Module Entitlement Engine', '1.11.0', 'FUNCTIONALLY_TESTED', 1, None, 'enterprise:config_manage'),
            ('enterprise.integration_governance', 'Hospital Integration Connector & Secret Reference Registry', '1.11.0', 'FUNCTIONALLY_TESTED', 1, None, 'enterprise:integration_manage'),
            ('safety.clinical_safety_case', 'Clinical Safety Case, Hazard Analysis & Verification Engine', '1.48.0', 'FUNCTIONALLY_TESTED', 1, None, 'safety_case:read'),
            ('testing.test_automation_release_qualification', 'End-to-End Test Automation, Regression & Release Qualification Engine', '1.49.0', 'FUNCTIONALLY_TESTED', 1, None, 'test_qualification:read'),

            # Future clinical engines: STRICTLY NOT_IMPLEMENTED in Phase 1
            ('clinical.consultation', 'Single 3-Zone Consultation Canvas', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Unified workspace active under clinical.consultation_orchestrator', 'encounters:write'),
            ('operations.followups', 'Care Continuum Follow-up Queues', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Care continuity active under clinical.care_continuity', 'encounters:read'),

            # Future clinical engines: STRICTLY NOT_IMPLEMENTED in Phase 1
            ('clinical.unani_mizaj', 'Unani Mizaj & Ajnas Scoring Engine', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Clinician-entered assessment active in clinical.unani_assessment', 'encounters:write'),
            ('operations.dispensary', 'FEFO Batch Dispensary Inventory', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Active under operations.pharmacy_inventory_ledger & prescription_dispensing', 'facility:manage'),
            ('integration.abdm', 'FHIR / ABDM Adapter Connector', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Hospital workflows active under hospital_workflows', 'org:manage'),
            ('ai.scribe', 'Contextual AI Note Scribe', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Excluded from core clinical safety path', 'encounters:write'),
            ('hospital.ipd', 'Inpatient Nursing Ward Engine', '1.1.0', 'NOT_IMPLEMENTED', 0, 'Inter-facility transfers active under enterprise.inter_facility_transfers', 'org:manage')
        ]


        for eng_id, name, ver, status, enabled, reason, perm in capabilities_seed:
            conn.execute("""
                INSERT OR REPLACE INTO capability_registry (engine_id, name, version, status, is_enabled, health_reason, required_permission)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (eng_id, name, ver, status, enabled, reason, perm))

        # 33. Prompt 09: Governed Communication Templates, Provider Configs & Outcome Definitions (if migration 009 applied)
        cur_check = conn.cursor()
        cur_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='communication_templates';")
        if cur_check.fetchone():
            templates_seed = [
                (
                    'ctpl-appt-reminder-en', 'org-matab-default', 'TPL-APPT-REMINDER-EN',
                    'Standard Appointment & Follow-up Reminder (Neutral)', 'sms', 'en', 'clinical_reminder',
                    1, 'approved', 0, 'usr-admin-1',
                    'ctplv-appt-reminder-en-v1',
                    'Assalamu Alaikum {{patient_name}}, you have a scheduled clinical review at {{facility_name}} on {{appointment_date}}. For assistance call {{clinic_phone}}.'
                ),
                (
                    'ctpl-whatsapp-followup-en', 'org-matab-default', 'TPL-WHATSAPP-FOLLOWUP-EN',
                    'WhatsApp Follow-up Check-in (Neutral)', 'whatsapp', 'en', 'clinical_reminder',
                    1, 'approved', 0, 'usr-admin-1',
                    'ctplv-whatsapp-followup-en-v1',
                    'Hello {{patient_name}}, this is a care continuity reminder from {{facility_name}} for your review due on {{appointment_date}}.'
                ),
                (
                    'ctpl-draft-unapproved', 'org-matab-default', 'TPL-DRAFT-UNAPPROVED',
                    'Unapproved Draft Reminder Template', 'sms', 'en', 'clinical_reminder',
                    1, 'draft', 0, None,
                    'ctplv-draft-unapproved-v1',
                    'Draft message for {{patient_name}} at {{facility_name}}.'
                )
            ]
            for tid, oid, tcode, tname, chan, lang, cat, ver, astat, sens, aby, vid, body_tpl in templates_seed:
                conn.execute("""
                    INSERT OR REPLACE INTO communication_templates (
                        id, organization_id, template_code, name, channel, language, category,
                        current_version, approval_status, contains_sensitive_fields, approved_by,
                        approved_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'usr-admin-1');
                """, (tid, oid, tcode, tname, chan, lang, cat, ver, astat, sens, aby))
                conn.execute("""
                    INSERT OR REPLACE INTO communication_template_versions (
                        id, template_id, version_number, body_template, approval_status, authored_by, approved_by
                    ) VALUES (?, ?, 1, ?, ?, 'usr-admin-1', ?);
                """, (vid, tid, body_tpl, astat, aby))

            providers_seed = [
                ('pconf-sms-1', 'org-matab-default', 'fac-central-opd', 'sandbox_sms', 'sms'),
                ('pconf-wa-1', 'org-matab-default', 'fac-central-opd', 'sandbox_whatsapp', 'whatsapp'),
                ('pconf-em-1', 'org-matab-default', 'fac-central-opd', 'sandbox_email', 'email'),
                ('pconf-mc-1', 'org-matab-default', 'fac-central-opd', 'manual_call_log', 'phone_call')
            ]
            for pid, oid, fid, pcode, chan in providers_seed:
                conn.execute("""
                    INSERT OR REPLACE INTO communication_provider_configs (
                        id, organization_id, facility_id, provider_code, channel, status
                    ) VALUES (?, ?, ?, ?, ?, 'active');
                """, (pid, oid, fid, pcode, chan))

            outcome_defs_seed = [
                ('odef-nrs-pain', 'OUT-NRS-PAIN', 'Numerical Pain Rating Scale (0-10)', 'symptom_severity', 'scale', 'score_0_10', 0.0, 10.0, 'lower_is_better', 'clinical_interview', '1.0', 'approved'),
                ('odef-dyspepsia', 'OUT-DYSPEPSIA-SCORE', 'Epigastric Discomfort & Dyspepsia Severity (0-10)', 'symptom_severity', 'scale', 'score_0_10', 0.0, 10.0, 'lower_is_better', 'clinical_interview', '1.0', 'approved'),
                ('odef-sbp', 'OUT-SBP-MMHG', 'Systolic Blood Pressure', 'vital_sign', 'numeric', 'mmHg', 50.0, 260.0, 'lower_is_better', 'automated_cuff', '1.0', 'approved'),
                ('odef-adherence', 'OUT-REGIMEN-ADHERENCE', 'Self-Reported Regimen Adherence Percentage', 'adherence', 'numeric', 'percent', 0.0, 100.0, 'higher_is_better', 'patient_self_report', '1.0', 'approved')
            ]
            for od_id, code, name, dom, rtype, unit, smin, smax, direc, cmeth, iver, rstat in outcome_defs_seed:
                conn.execute("""
                    INSERT OR REPLACE INTO outcome_definitions (
                        id, code, name, domain, response_type, unit, scale_min, scale_max,
                        directionality, collection_method, instrument_version, review_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (od_id, code, name, dom, rtype, unit, smin, smax, direc, cmeth, iver, rstat))

        # 34. Prompt 10: Facility Settings, Practitioner Schedule, Fee Catalog & Dispensary Inventory (if migration 010 applied)
        cur_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='facility_settings';")
        if cur_check.fetchone():
            conn.execute("""
                INSERT OR REPLACE INTO facility_settings (
                    facility_id, organization_id, timezone, currency, tax_enabled,
                    default_tax_rate_bp, billing_enabled, billing_optional_for_consultation,
                    inventory_enabled, public_queue_display_enabled, allow_negative_stock_override,
                    near_expiry_warning_days, default_slot_duration_mins, buffer_time_mins,
                    updated_by
                ) VALUES ('fac-central-opd', 'org-matab-default', 'Asia/Kolkata', 'INR', 0, 0, 1, 1, 1, 1, 0, 90, 15, 0, 'usr-admin-1');
            """)

            conn.execute("""
                INSERT OR REPLACE INTO practitioner_schedules (
                    id, organization_id, facility_id, practitioner_id, day_of_week,
                    start_time, end_time, break_start_time, break_end_time,
                    slot_duration_mins, buffer_time_mins, slot_capacity, room_resource,
                    is_active, created_by
                ) VALUES ('psched-hakeem-default', 'org-matab-default', 'fac-central-opd', 'usr-hakeem-1', 'ALL',
                          '09:00', '17:00', '13:00', '14:00', 15, 0, 1, 'Room-1', 1, 'usr-admin-1');
            """)

            fee_seed = [
                ('fee-consult-opd', 'org-matab-default', 'fac-central-opd', 'CONSULT-OPD', 'Initial Unani Consultation (Matab OPD)', 'CONSULTATION', 'INR', '300.00', 0),
                ('fee-consult-fup', 'org-matab-default', 'fac-central-opd', 'CONSULT-FUP', 'Follow-up Clinical Review', 'FOLLOW_UP_CONSULTATION', 'INR', '150.00', 0),
                ('fee-tadbir-hijama', 'org-matab-default', 'fac-central-opd', 'TADBIR-HIJAMA', 'Ilaj-bil-Tadbir: Hijama (Cupping Session)', 'PROCEDURE_TADBIR', 'INR', '600.00', 0)
            ]
            for fid_item, oid, fac_id, fcode, fname, fcat, curr, uprice, tbp in fee_seed:
                conn.execute("""
                    INSERT OR REPLACE INTO fee_catalog_items (
                        id, organization_id, facility_id, code, name, category, currency, unit_price_decimal, tax_rate_bp, is_active, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'usr-admin-1');
                """, (fid_item, oid, fac_id, fcode, fname, fcat, curr, uprice, tbp))

            conn.execute("""
                INSERT OR REPLACE INTO suppliers (id, organization_id, code, name, license_number, phone, is_active)
                VALUES ('sup-dawakhana-1', 'org-matab-default', 'SUP-DAWA-01', 'National Unani Dawakhana Suppliers [Synthetic]', 'AYUSH-MFG-1092', '+91-11-23009900', 1);
            """)

            conn.execute("""
                INSERT OR REPLACE INTO inventory_locations (id, organization_id, facility_id, code, name, location_type, is_dispensable, is_active)
                VALUES
                ('loc-main-fac-central-opd', 'org-matab-default', 'fac-central-opd', 'MAIN-DISP', 'Main Dispensary Shelf', 'MAIN_DISPENSARY', 1, 1),
                ('loc-quar-fac-central-opd', 'org-matab-default', 'fac-central-opd', 'QUAR-HOLD', 'Quarantine & Recall Hold', 'QUARANTINE_HOLD', 0, 1);
            """)

            inv_items_seed = [
                ('iitem-bazoori', 'org-matab-default', 'fac-central-opd', 'SKU-SHARBAT-BAZOORI', 'Sharbat Bazoori Motadil (200ml)', 'form-sharbat-bazoori', 'SHARBAT', 'ml', '200.00', '85.00', '120.00'),
                ('iitem-jawarish-jallinoos', 'org-matab-default', 'fac-central-opd', 'SKU-JAWARISH-JALLINOOS', 'Majoon Arad Khurma (125g)', 'form-majoon-arad', 'MAJOON', 'g', '250.00', '140.00', '210.00')
            ]
            for iid, oid, fac_id, sku, iname, form_id, dform, unit, rthresh, scost, sprice in inv_items_seed:
                conn.execute("""
                    INSERT OR REPLACE INTO inventory_items (
                        id, organization_id, facility_id, sku, name, formulation_id, dosage_form, unit,
                        reorder_threshold_decimal, standard_cost_decimal, selling_price_decimal, is_active, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'usr-admin-1');
                """, (iid, oid, fac_id, sku, iname, form_id, dform, unit, rthresh, scost, sprice))

            batches_seed = [
                ('batch-bazoori-2027', 'org-matab-default', 'fac-central-opd', 'iitem-bazoori', 'loc-main-fac-central-opd', 'sup-dawakhana-1', 'BZM-2026-A', '2026-01-15', '2027-12-31', 'AVAILABLE', '1000.00', '85.00', '120.00'),
                ('batch-jawarish-2027', 'org-matab-default', 'fac-central-opd', 'iitem-jawarish-jallinoos', 'loc-main-fac-central-opd', 'sup-dawakhana-1', 'JJL-2026-B', '2026-02-01', '2027-11-30', 'AVAILABLE', '1500.00', '140.00', '210.00')
            ]
            for bid, oid, fac_id, iid, lid, sid, bnum, mdate, edate, bstat, qty, ucost, sprice in batches_seed:
                conn.execute("""
                    INSERT OR REPLACE INTO inventory_batches (
                        id, organization_id, facility_id, inventory_item_id, location_id, supplier_id,
                        batch_number, manufactured_date, expiry_date, status,
                        quantity_on_hand_decimal, unit_cost_decimal, selling_price_decimal
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (bid, oid, fac_id, iid, lid, sid, bnum, mdate, edate, bstat, qty, ucost, sprice))

        # 35. Prompt 11: Organization Profiles, Facility Profiles, Departments & Integration Registry (if migration 011 applied)
        cur_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='organization_profiles';")
        if cur_check.fetchone():
            conn.execute("""
                INSERT OR REPLACE INTO organization_profiles (
                    organization_id, parent_organization_id, lifecycle_status, legal_name,
                    timezone, default_language, deployment_mode, cross_facility_continuity_policy,
                    org_admin_clinical_note_access, updated_by
                ) VALUES (
                    'org-matab-default', NULL, 'active', 'ZAYVORA Matab Dawakhana Foundation [Synthetic]',
                    'Asia/Kolkata', 'en', 'SHARED_MULTITENANT', 'SAME_ORG_TREATMENT_TEAM', 0, 'usr-admin-1'
                );
            """)

            conn.execute("""
                INSERT OR REPLACE INTO facility_profiles (
                    facility_id, organization_id, facility_type, lifecycle_status, timezone, city, state_province, country, updated_by
                ) VALUES
                ('fac-central-opd', 'org-matab-default', 'MULTI_DOCTOR_CLINIC', 'active', 'Asia/Kolkata', 'Delhi', 'DL', 'IN', 'usr-admin-1'),
                ('fac-south-branch', 'org-matab-default', 'BRANCH_CLINIC', 'active', 'Asia/Kolkata', 'Delhi', 'DL', 'IN', 'usr-admin-1');
            """)

            conn.execute("""
                INSERT OR REPLACE INTO facility_departments (
                    id, organization_id, facility_id, code, name, department_type, head_practitioner_id,
                    required_module_key, status, is_operational, created_by
                ) VALUES
                ('dept-central-unani-opd', 'org-matab-default', 'fac-central-opd', 'UNANI-OPD', 'Unani General & Moalejat OPD', 'UNANI_OPD', 'usr-hakeem-1', 'unani_assessment', 'active', 1, 'usr-admin-1'),
                ('dept-central-dispensary', 'org-matab-default', 'fac-central-opd', 'DAWAKHANA', 'Central Unani Dispensary', 'PHARMACY_DISPENSARY', NULL, 'pharmacy_inventory', 'active', 1, 'usr-admin-1'),
                ('dept-south-unani-opd', 'org-matab-default', 'fac-south-branch', 'SOUTH-OPD', 'South Branch Unani OPD', 'UNANI_OPD', 'usr-hakeem-1', 'unani_assessment', 'active', 1, 'usr-admin-1');
            """)

            conn.execute("""
                INSERT OR REPLACE INTO integration_connectors (
                    id, organization_id, facility_id, connector_type, name, environment,
                    lifecycle_state, endpoint_url, api_version, secret_ref_uri,
                    data_sharing_policy_ref, last_health_status, updated_by
                ) VALUES (
                    'intg-abdm-sandbox', 'org-matab-default', 'fac-central-opd', 'ABDM_ABHA',
                    'ABDM Health ID Sandbox Bridge [Synthetic]', 'SANDBOX',
                    'CONFIGURED_NOT_CONNECTED', 'https://dev.abdm.gov.in/gateway', 'v0.5',
                    'vault://matab-secrets/org-matab-default/abdm-sandbox',
                    'POL-ABDM-CONSENT-2026', 'UNVERIFIED', 'usr-admin-1'
                );
            """)

        # 36. Prompt 12: Hospital Wards, Beds, Laboratory Catalog & Terminology Mappings (if migration 012 applied)
        cur_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ipd_wards';")
        if cur_check.fetchone():
            conn.execute("""
                INSERT OR REPLACE INTO ipd_wards (
                    id, organization_id, facility_id, department_id, code, name, ward_type, gender_policy, status, created_by
                ) VALUES
                ('wrd-unani-moalejat-1', 'org-matab-default', 'fac-central-opd', 'dept-central-unani-opd', 'MOA-W1', 'Moalejat & Ilaj-bil-Tadbeer Inpatient Ward [Synthetic]', 'REGIMENAL_THERAPY_WARD', 'MIXED', 'active', 'usr-admin-1'),
                ('wrd-acute-obs-1', 'org-matab-default', 'fac-central-opd', 'dept-central-unani-opd', 'OBS-W1', 'Short-Stay Observation & HDU Ward [Synthetic]', 'HIGH_DEPENDENCY_UNIT', 'MIXED', 'active', 'usr-admin-1');
            """)

            conn.execute("""
                INSERT OR REPLACE INTO ipd_beds (
                    id, organization_id, facility_id, ward_id, room_number, bed_code, bed_category,
                    operational_status, active_admission_id, active_patient_id, active_stay_lock
                ) VALUES
                ('bed-moa-101a', 'org-matab-default', 'fac-central-opd', 'wrd-unani-moalejat-1', '101', 'MOA-101A', 'STANDARD', 'available', NULL, NULL, NULL),
                ('bed-moa-101b', 'org-matab-default', 'fac-central-opd', 'wrd-unani-moalejat-1', '101', 'MOA-101B', 'STANDARD', 'available', NULL, NULL, NULL),
                ('bed-obs-201a', 'org-matab-default', 'fac-central-opd', 'wrd-acute-obs-1', '201', 'OBS-201A', 'HDU', 'available', NULL, NULL, NULL);
            """)

            conn.execute("""
                INSERT OR REPLACE INTO lab_catalog_items (
                    id, organization_id, code, name, loinc_code, category, specimen_type,
                    default_unit, reference_range_text, critical_low, critical_high, collection_instructions, is_active
                ) VALUES
                ('lcat-serum-k', 'org-matab-default', 'LAB-K', 'Serum Potassium (K+)', '2823-3', 'BIOCHEMISTRY', 'VENOUS_BLOOD', 'mmol/L', '3.5 - 5.1 mmol/L', 2.8, 6.2, 'Avoid hemolysis; serum separator tube.', 1),
                ('lcat-hba1c', 'org-matab-default', 'LAB-HBA1C', 'Glycated Hemoglobin (HbA1c)', '4548-4', 'BIOCHEMISTRY', 'WHOLE_BLOOD_EDTA', '%', '4.0 - 5.6 %', NULL, 12.0, 'EDTA lavender top; no fasting required.', 1),
                ('lcat-sgpt', 'org-matab-default', 'LAB-ALT', 'Alanine Aminotransferase (ALT/SGPT)', '1742-6', 'HEPATIC_PANEL', 'VENOUS_BLOOD', 'U/L', '7.0 - 56.0 U/L', NULL, 500.0, 'Serum separator tube.', 1);
            """)

            conn.execute("""
                INSERT OR REPLACE INTO terminology_mappings (
                    id, organization_id, concept_domain, local_code, local_display,
                    target_system_uri, target_version, target_code, target_display, equivalence_level, lossiness_note
                ) VALUES
                ('tmap-mizaj-hd', 'org-matab-default', 'UNANI_CONCEPT', 'HAR_YABIS', 'Har Yabis (Hot & Dry Temperament)',
                 'http://snomed.info/sct', '2026.1', 'UNANI-EXT-MIZAJ-HY', 'Unani Constitutional Assessment: Har Yabis', 'INEXACT_LOSSY',
                 'Classical Unani qualitative Mizaj grading has no exact 1:1 SNOMED CT pre-coordinated equivalent; exported with Unani provenance extension.');
            """)

            # 23. Controlled Pilot Launch & Clinic Onboarding Seeds (Prompt 14)
            conn.execute("""
                INSERT OR REPLACE INTO pilot_programs (
                    id, code, name, description, status, organization_id, target_start_date, target_end_date,
                    audit_report_ref, audit_verdict, created_by
                ) VALUES (
                    'plt-prog-2026-q4', 'PILOT-MATAB-2026-Q4', 'ZAYVORA Matab Phase 1 Limited Clinic Pilot',
                    'Governed outpatient clinic pilot covering patient registration, consultation, Unani assessment, nuskha prescribing, safety firewall, and dispensary.',
                    'ELIGIBILITY_VERIFIED', 'org-matab-default', '2026-10-15', '2026-12-15',
                    'AUDIT-PROMPT13-REPORT-2026-10-13', 'CONDITIONAL_GO_FOR_LIMITED_PILOT', 'usr-admin-1'
                );
            """)

            conn.execute("""
                INSERT OR REPLACE INTO pilot_scope_versions (
                    id, pilot_program_id, version_number, status,
                    enabled_modules_json, disabled_modules_json, permitted_roles_json, permitted_facilities_json,
                    supported_languages_json, supported_devices_json, known_limitations,
                    approved_by_clinical_lead, approved_by_security_lead, approved_by_product_lead
                ) VALUES (
                    'psc-ver-2026-1', 'plt-prog-2026-q4', 1, 'ACTIVE',
                    '["PATIENT_REGISTRY", "UNIFIED_CONSULTATION", "UNANI_ASSESSMENT", "PRESCRIPTION_ENGINE", "CLINICAL_SAFETY_FIREWALL", "DISPENSARY_QUEUE", "BILLING"]',
                    '["ABDM_LIVE_SYNC", "CARRIER_SMS_LIVE", "PAYMENT_GATEWAY_WEBHOOK"]',
                    '["CHIEF_TABIB", "TABIB", "DISPENSER", "CASHIER", "STAFF", "HOSPITAL_ADMIN", "ORG_ADMIN", "CLINIC_ADMIN", "PRACTITIONER", "RECEPTIONIST", "PHARMACIST"]',
                    '["fac-central-opd"]',
                    '["en", "ur", "hi"]', '["DESKTOP_WEB", "TABLET_WEB"]',
                    'External live ABDM gateway push is disabled; operates via contract-tested outbox harness.',
                    'usr-hakeem-1', 'usr-admin-1', 'usr-admin-1'
                );
            """)

            training_modules_seed = [
                ('trn-mod-tabib-1', 'TRN-TABIB-01', 'TABIB', 'Unani Consultation & Safety Preflight Workflow',
                 'Guided training on patient 360, Mizaj assessment, nuskha builder, fail-closed safety preflight, and PIN digital signing.', '1.0', 85),
                ('trn-mod-recept-1', 'TRN-RECEPT-01', 'RECEPTIONIST', 'Front-Desk Patient Registration, Duplicate Check & Queue',
                 'Patient registration, duplicate resolution, appointment token generation, and privacy-safe queue management.', '1.0', 80),
                ('trn-mod-disp-1', 'TRN-DISP-01', 'DISPENSER', 'Dispensary Queue, FEFO Batch Dispensing & Stock Movements',
                 'Opening finalized prescriptions, batch expiry verification, stock subtraction, and prohibited substitution rules.', '1.0', 85),
                ('trn-mod-admin-1', 'TRN-ADMIN-01', 'ADMIN', 'Facility Onboarding, Role Setup & Incident Escalation',
                 '13-stage facility onboarding checklist, staff credentialing, and SEV-1 emergency escalation.', '1.0', 90)
            ]
            for m_id, code, role, title, desc, ver, score in training_modules_seed:
                conn.execute("""
                    INSERT OR REPLACE INTO training_modules (
                        id, code, target_role, title, description, curriculum_version, min_pass_score, is_mandatory
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1);
                """, (m_id, code, role, title, desc, ver, score))

            # Initial 13-stage onboarding checklist for fac-central-opd
            stages = [
                ('1_ELIGIBILITY_CONFIRMED', 'Prompt 13 Audit Eligibility & Pilot Scope Confirmed', 1, 'COMPLETED'),
                ('2_FACILITY_DETAILS_VALIDATED', 'Organization & Facility Regulatory Details Validated', 2, 'COMPLETED'),
                ('3_STAFF_ROLES_CONFIGURED', 'Practitioner & Staff Scope-Aware Roles Configured', 3, 'COMPLETED'),
                ('4_SCHEDULES_FEES_CONFIGURED', 'Consultation Schedules, Rooms & Fee Catalog Configured', 4, 'COMPLETED'),
                ('5_TEMPLATES_CHECKED', 'Print Templates & Approved Communication Templates Checked', 5, 'COMPLETED'),
                ('6_CLINICAL_CONTENT_REVIEWED', 'Unani Monographs & Clinical Safety Datasets Reviewed', 6, 'COMPLETED'),
                ('7_DEVICES_NETWORK_CHECKED', 'Clinic Devices, Barcode Scanners & Local Network Checked', 7, 'COMPLETED'),
                ('8_DATA_MIGRATION_DECISION', 'Data Migration Decision Approved (Controlled Registration Mode)', 8, 'COMPLETED'),
                ('9_ROLE_TRAINING_COMPLETED', 'Role-Based Staff Training & Scenario Practice Completed', 9, 'IN_PROGRESS'),
                ('10_ACCEPTANCE_TESTS_PASSED', 'User Acceptance Testing & Synthetic Scenario Verification Passed', 10, 'PENDING'),
                ('11_SITE_OWNER_APPROVAL', 'Site Medical Director & Facility Owner Approval Recorded', 11, 'PENDING'),
                ('12_FACILITY_ACTIVATED', 'Facility Activated for Controlled Pilot Live Traffic', 12, 'PENDING'),
                ('13_FIRST_WEEK_REVIEW', 'First-Week Operational Review & Quality Check Completed', 13, 'PENDING')
            ]
            for s_code, s_title, s_order, s_status in stages:
                s_id = f"fob-chk-{s_order}"
                conn.execute("""
                    INSERT OR REPLACE INTO facility_onboarding_checklists (
                        id, pilot_program_id, facility_id, stage_code, stage_title, stage_order, status, owner_user_id
                    ) VALUES (?, 'plt-prog-2026-q4', 'fac-central-opd', ?, ?, ?, ?, 'usr-admin-1');
                """, (s_id, s_code, s_title, s_order, s_status))
            # Phase 34: Command Center Canonical Threshold Rules
            threshold_rules = [
                ('rule-th-001', 'org-matab-default', None, 'CHECK_IN_TO_CALL', 30, 60, 'usr-admin-1', 1),
                ('rule-th-002', 'org-matab-default', None, 'CALL_TO_START', 15, 30, 'usr-admin-1', 1),
                ('rule-th-003', 'org-matab-default', None, 'CONSULTATION_DURATION', 45, 90, 'usr-admin-1', 1),
                ('rule-th-004', 'org-matab-default', None, 'DISCHARGE_TO_BILLING', 20, 45, 'usr-admin-1', 1),
                ('rule-th-005', 'org-matab-default', None, 'BILLING_TO_PAYMENT', 30, 60, 'usr-admin-1', 1),
                ('rule-th-006', 'org-matab-default', None, 'FOLLOW_UP_COMPLETION', 1440, 2880, 'usr-admin-1', 1),
                ('rule-th-007', 'org-matab-default', None, 'DLQ_RESOLUTION', 60, 240, 'usr-admin-1', 1)
            ]
            for tr_id, o_id, f_id, stage, warn, crit, app_by, ver in threshold_rules:
                conn.execute("""
                    INSERT OR REPLACE INTO command_center_threshold_rules (
                        id, organization_id, facility_id, stage_key, warning_threshold_mins,
                        critical_threshold_mins, approved_by, approved_at, version, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 1);
                """, (tr_id, o_id, f_id, stage, warn, crit, app_by, ver))
            # Phase 35: Workflow Automation Starter Rules
            starter_rules = [
                (
                    'wf-rule-001', 'org-matab-default', 'fac-central-opd', 'rule-wf-appt-intake',
                    'Appointment Intake Prep Automation',
                    'Generates an administrative chart-preparation task when a new appointment is confirmed.',
                    'APPOINTMENT_STATUS_CHANGED', '1.0.0',
                    json.dumps([{"field": "event.status", "operator": "equals", "value": "booked"}]),
                    json.dumps([{"type": "CREATE_ADMIN_TASK", "category": "routine_administrative", "parameters": {"task_name": "Prepare Patient File"}}]),
                    'routine_administrative', 10, 1, 'ACTIVE', 'RECEPTIONIST', 'usr-admin-1'
                ),
                (
                    'wf-rule-002', 'org-matab-default', 'fac-central-opd', 'rule-wf-fup-reminder',
                    'Clinician Follow-up Reminder Dispatch',
                    'Dispatches an approved reminder when a clinician-authored follow-up task approaches due date.',
                    'FOLLOW_UP_TASK_DUE', '1.0.0',
                    json.dumps([{"field": "event.priority", "operator": "in", "value": ["routine", "high"]}]),
                    json.dumps([{"type": "ENQUEUE_PATIENT_REMINDER", "category": "communication", "parameters": {"template_code": "CLINICAL_REMINDER_SMS"}}]),
                    'communication', 20, 1, 'ACTIVE', 'CARE_COORDINATOR', 'usr-admin-1'
                ),
                (
                    'wf-rule-003', 'org-matab-default', 'fac-central-opd', 'rule-wf-stall-escalation',
                    'OPD Queue Delay Escalation',
                    'Alerts front desk lead when waiting time exceeds approved threshold.',
                    'QUEUE_WAITING_STALL', '1.0.0',
                    json.dumps([{"field": "event.elapsed_mins", "operator": "greater_than", "value": 45}]),
                    json.dumps([{"type": "ESCALATE_QUEUE_STALL", "category": "routine_administrative", "parameters": {"escalate_to_role": "CLINIC_ADMIN"}}]),
                    'routine_administrative', 30, 1, 'ACTIVE', 'CLINIC_ADMIN', 'usr-admin-1'
                ),
                (
                    'wf-rule-004', 'org-matab-default', 'fac-central-opd', 'rule-wf-missing-phone',
                    'Missing Contact Number Intake Task',
                    'Creates a front desk intake gap task when patient phone number is missing.',
                    'MISSING_ADMIN_INFO', '1.0.0',
                    json.dumps([{"field": "event.missing_field", "operator": "equals", "value": "phone"}]),
                    json.dumps([{"type": "RECORD_INTAKE_GAP", "category": "routine_administrative", "parameters": {"action_needed": "Collect Phone at Check-in"}}]),
                    'routine_administrative', 40, 1, 'ACTIVE', 'RECEPTIONIST', 'usr-admin-1'
                ),
                (
                    'wf-rule-005', 'org-matab-default', 'fac-central-opd', 'rule-wf-stock-reorder',
                    'Pharmacy Low Stock Review Task',
                    'Creates an inventory review task when available stock drops below threshold (human approval gate).',
                    'INVENTORY_THRESHOLD_BREACH', '1.0.0',
                    json.dumps([{"field": "event.remaining_quantity", "operator": "less_than", "value": 10}]),
                    json.dumps([{"type": "CREATE_STOCK_REVIEW_TASK", "category": "sensitive_administrative", "parameters": {"threshold": 10}}]),
                    'sensitive_administrative', 50, 1, 'ACTIVE', 'PHARMACIST', 'usr-admin-1'
                ),
                (
                    'wf-rule-006', 'org-matab-default', 'fac-central-opd', 'rule-wf-dlq-triage',
                    'Integration Dead-Letter Escalation',
                    'Flags persistent integration failures for SRE / Admin review.',
                    'INTEGRATION_JOB_FAILED', '1.0.0',
                    json.dumps([{"field": "event.retry_count", "operator": "greater_than", "value": 3}]),
                    json.dumps([{"type": "RETRY_DEAD_LETTER_ITEM", "category": "sensitive_administrative", "parameters": {"max_retries": 3}}]),
                    'sensitive_administrative', 60, 1, 'ACTIVE', 'ORG_ADMIN', 'usr-admin-1'
                )
            ]
            for r_id, o_id, f_id, r_key, r_name, desc, ev_type, s_ver, conds, acts, cat, prio, ver, st, owner, app_by in starter_rules:
                conn.execute("""
                    INSERT OR REPLACE INTO workflow_rules (
                        id, organization_id, facility_id, rule_key, rule_name, description,
                        event_type, event_schema_version, conditions_json, actions_json,
                        action_category, priority, version, status, owner_role,
                        approved_by, approved_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                """, (r_id, o_id, f_id, r_key, r_name, desc, ev_type, s_ver, conds, acts, cat, prio, ver, st, owner, app_by, app_by))

            # Phase 36: Enterprise SLA Governance Policies (if migration 035 applied)
            cur_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sla_policies';")
            if cur_check.fetchone():
                starter_policies = [
                    (
                        'sla-pol-001', 'org-matab-default', 'fac-central-opd', 'sla-pol-queue-stall',
                        'OPD Patient Queue Stall Resolution SLA',
                        'Resolution SLA for patients waiting between check-in and consultation call.',
                        'administrative', 'queue_tokens', 'FRONT_DESK', 1, 'ACTIVE', 'elapsed',
                        30, 45,
                        json.dumps(['WAITING_PATIENT_RESPONSE', 'ADMINISTRATIVE_HOLD']),
                        json.dumps([
                            {'stage': 1, 'trigger_delay_mins': 0, 'escalate_to_role': 'FRONT_DESK', 'channel': 'in_app', 'cooldown_mins': 15},
                            {'stage': 2, 'trigger_delay_mins': 15, 'escalate_to_role': 'CLINIC_ADMIN', 'channel': 'in_app', 'cooldown_mins': 30}
                        ]),
                        0,
                        json.dumps(['CALLED_TO_CONSULT', 'APPOINTMENT_RESCHEDULED', 'PATIENT_LEFT']),
                        'usr-admin-1'
                    ),
                    (
                        'sla-pol-002', 'org-matab-default', 'fac-central-opd', 'sla-pol-overdue-followup',
                        'Care Continuity Outreach Follow-up SLA',
                        'Resolution SLA for clinician-directed longitudinal outreach tasks.',
                        'follow_up', 'care_continuity_tasks', 'CARE_COORDINATOR', 1, 'ACTIVE', 'business_hours',
                        1440, 2880,
                        json.dumps(['WAITING_PATIENT_RESPONSE', 'EXTERNAL_REFERRAL_PENDING']),
                        json.dumps([
                            {'stage': 1, 'trigger_delay_mins': 0, 'escalate_to_role': 'CARE_COORDINATOR', 'channel': 'in_app', 'cooldown_mins': 120},
                            {'stage': 2, 'trigger_delay_mins': 240, 'escalate_to_role': 'CLINIC_ADMIN', 'channel': 'in_app', 'cooldown_mins': 240}
                        ]),
                        0,
                        json.dumps(['CONTACT_ESTABLISHED', 'PATIENT_DECLINED', 'UNREACHABLE_AFTER_ATTEMPTS']),
                        'usr-admin-1'
                    ),
                    (
                        'sla-pol-003', 'org-matab-default', 'fac-central-opd', 'sla-pol-missing-demographics',
                        'Intake Demographic & Contact Correction SLA',
                        'Resolution SLA for patients registered with missing phone or emergency contact.',
                        'intake_gap', 'patients', 'RECEPTIONIST', 1, 'ACTIVE', 'elapsed',
                        60, 120,
                        json.dumps(['ADMINISTRATIVE_HOLD']),
                        json.dumps([
                            {'stage': 1, 'trigger_delay_mins': 0, 'escalate_to_role': 'RECEPTIONIST', 'channel': 'in_app', 'cooldown_mins': 30}
                        ]),
                        0,
                        json.dumps(['PHONE_CAPTURED', 'PATIENT_REFUSED_DISCLOSURE']),
                        'usr-admin-1'
                    ),
                    (
                        'sla-pol-004', 'org-matab-default', 'fac-central-opd', 'sla-pol-stock-depleted',
                        'Dispensary Critical Low Stock Restock SLA',
                        'Resolution SLA for dispensary stock depleted below safety reserve.',
                        'inventory', 'inventory_batches', 'PHARMACIST', 1, 'ACTIVE', 'elapsed',
                        240, 480,
                        json.dumps(['SUPPLIER_DELIVERY_PENDING']),
                        json.dumps([
                            {'stage': 1, 'trigger_delay_mins': 0, 'escalate_to_role': 'PHARMACIST', 'channel': 'in_app', 'cooldown_mins': 60},
                            {'stage': 2, 'trigger_delay_mins': 120, 'escalate_to_role': 'CLINIC_ADMIN', 'channel': 'in_app', 'cooldown_mins': 120}
                        ]),
                        1,
                        json.dumps(['STOCK_RESTOCKED', 'SUBSTITUTE_BATCH_ALLOCATED', 'FORMULATION_DISCONTINUED']),
                        'usr-admin-1'
                    ),
                    (
                        'sla-pol-005', 'org-matab-default', 'fac-central-opd', 'sla-pol-dlq-resolution',
                        'Dead-Letter Integration Queue Recovery SLA',
                        'Resolution SLA for persistent connector and webhook delivery failures.',
                        'integration', 'integration_jobs', 'ORG_ADMIN', 1, 'ACTIVE', 'elapsed',
                        120, 240,
                        json.dumps(['SYSTEM_OUTAGE']),
                        json.dumps([
                            {'stage': 1, 'trigger_delay_mins': 0, 'escalate_to_role': 'ORG_ADMIN', 'channel': 'in_app', 'cooldown_mins': 60}
                        ]),
                        0,
                        json.dumps(['JOB_REPROCESSED', 'PAYLOAD_AMENDED_AND_REPLAYED', 'CORRUPT_PAYLOAD_ARCHIVED']),
                        'usr-admin-1'
                    ),
                    (
                        'sla-pol-006', 'org-matab-default', 'fac-central-opd', 'sla-pol-approval-backlog',
                        'Governance Human Approval Gate Turnaround SLA',
                        'Resolution SLA for sensitive dispensary and operational tasks awaiting human approval.',
                        'governance', 'workflow_planned_actions', 'CLINIC_ADMIN', 1, 'ACTIVE', 'elapsed',
                        180, 360,
                        json.dumps(['ADMINISTRATIVE_HOLD']),
                        json.dumps([
                            {'stage': 1, 'trigger_delay_mins': 0, 'escalate_to_role': 'CLINIC_ADMIN', 'channel': 'in_app', 'cooldown_mins': 60}
                        ]),
                        0,
                        json.dumps(['ACTION_APPROVED', 'ACTION_REJECTED']),
                        'usr-admin-1'
                    ),
                    (
                        'sla-pol-007', 'org-matab-default', 'fac-central-opd', 'sla-pol-clinical-review',
                        'Clinician Regimen & Safety Review Routing SLA',
                        'Routing SLA for clinical assessment requests (Strictly qualified human clinician decision).',
                        'clinical_review', 'care_continuity_tasks', 'CLINICIAN', 1, 'ACTIVE', 'elapsed',
                        120, 240,
                        json.dumps(['WAITING_PATIENT_RESPONSE']),
                        json.dumps([
                            {'stage': 1, 'trigger_delay_mins': 0, 'escalate_to_role': 'CLINICIAN', 'channel': 'in_app', 'cooldown_mins': 60}
                        ]),
                        0,
                        json.dumps(['CLINICIAN_ASSESSMENT_COMPLETED', 'CARE_PLAN_AMENDED']),
                        'usr-admin-1'
                    )
                ]
                for p_id, o_id, f_id, p_key, p_name, p_desc, p_cat, p_tgt, p_own, p_ver, p_st, p_tb, p_warn, p_br, p_pause, p_esc, p_vr, p_res, app_by in starter_policies:
                    conn.execute("""
                        INSERT OR REPLACE INTO sla_policies (
                            id, organization_id, facility_id, policy_key, name, description,
                            category, target_entity_type, owner_role, version, status, time_basis,
                            timezone, warning_threshold_mins, breach_threshold_mins,
                            pause_eligibility_json, escalation_matrix_json, verification_required,
                            allowed_resolution_codes_json, effective_from, approved_by, approved_at, created_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Asia/Kolkata', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP, ?);
                    """, (p_id, o_id, f_id, p_key, p_name, p_desc, p_cat, p_tgt, p_own, p_ver, p_st, p_tb, p_warn, p_br, p_pause, p_esc, p_vr, p_res, app_by, app_by))

                # 40. Prompt 37: Enterprise Workflow Simulation & Failure Injection Starter Scenarios
                cur_sim = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='simulation_scenarios';")
                if cur_sim.fetchone():
                    starter_scenarios = [
                        (
                            'scen-syn-001', 'org-matab-default', 'fac-central-opd', 'sim-scen-duplicate-intake',
                            'Duplicate Patient Intake Event Idempotency & Task Suppression',
                            'Verify duplicate patient intake events do not generate duplicate queue tokens or administrative work items.',
                            'duplicate_and_ordering', 'low',
                            json.dumps(['local', 'dev', 'sandbox', 'ci']), 1, 'APPROVED', 'SYSTEM_ADMIN',
                            json.dumps(['simulation:run']),
                            json.dumps([
                                {
                                    'step_order': 1,
                                    'action_type': 'INGEST_EVENT',
                                    'target_service': 'workflow_automation',
                                    'payload': {'event_type': 'PATIENT_CHECKED_IN', 'patient_id': 'pat-syn-001', 'correlation_id': 'idemp-sim-intake-001'}
                                },
                                {
                                    'step_order': 2,
                                    'action_type': 'INGEST_EVENT',
                                    'target_service': 'workflow_automation',
                                    'fault': {'fault_type': 'DUPLICATE_DELIVERY', 'delay_ms': 50},
                                    'payload': {'event_type': 'PATIENT_CHECKED_IN', 'patient_id': 'pat-syn-001', 'correlation_id': 'idemp-sim-intake-001'}
                                }
                            ]),
                            json.dumps([
                                {
                                    'assertion_key': 'assert-single-event',
                                    'assertion_type': 'EVENT_DEDUPLICATED',
                                    'expected_condition': 'count == 1',
                                    'target_table': 'automation_events',
                                    'filter_field': 'correlation_id',
                                    'filter_value': 'idemp-sim-intake-001'
                                }
                            ]),
                            'automatic', 30, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'scen-syn-002', 'org-matab-default', 'fac-central-opd', 'sim-scen-adapter-timeout-retry',
                            'Notification Gateway Timeout & Bounded Backoff Retry',
                            'Simulate downstream SMS/WhatsApp provider socket timeout and verify bounded retry backoff without message leakage.',
                            'dependency_faults', 'moderate',
                            json.dumps(['local', 'dev', 'sandbox', 'ci']), 1, 'APPROVED', 'CLINIC_ADMIN',
                            json.dumps(['simulation:run', 'simulation:fault_inject']),
                            json.dumps([
                                {
                                    'step_order': 1,
                                    'action_type': 'DISPATCH_COMMUNICATION',
                                    'target_service': 'care_continuity',
                                    'fault': {'fault_type': 'TIMEOUT', 'timeout_ms': 2000},
                                    'payload': {'recipient': '+919999999999', 'template_code': 'APPOINTMENT_REMINDER', 'channel': 'SMS'}
                                }
                            ]),
                            json.dumps([
                                {
                                    'assertion_key': 'assert-side-effect-suppressed',
                                    'assertion_type': 'SIDE_EFFECT_SUPPRESSED',
                                    'expected_condition': 'real_network_calls == 0',
                                    'target_table': 'simulation_step_executions',
                                    'filter_field': 'fault_injected',
                                    'filter_value': 'TIMEOUT'
                                }
                            ]),
                            'automatic', 60, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'scen-syn-003', 'org-matab-default', 'fac-central-opd', 'sim-scen-sla-escalation',
                            'Administrative Workflow Exception Lifecycle & Multi-Stage Escalation',
                            'Validate SLA exception timer breaching, pause accounting, and zero-PHI multi-stage alert dispatching.',
                            'workflow_lifecycle', 'low',
                            json.dumps(['local', 'dev', 'sandbox', 'ci']), 1, 'APPROVED', 'SYSTEM_ADMIN',
                            json.dumps(['simulation:run']),
                            json.dumps([
                                {
                                    'step_order': 1,
                                    'action_type': 'CREATE_EXCEPTION',
                                    'target_service': 'sla_governance',
                                    'payload': {'category': 'administrative', 'source_entity': 'queue_tokens', 'source_entity_id': 'tok-sim-001', 'started_at': '2026-10-14 00:00:00'}
                                },
                                {
                                    'step_order': 2,
                                    'action_type': 'EVALUATE_ESCALATION',
                                    'target_service': 'sla_governance',
                                    'payload': {'source_entity_id': 'tok-sim-001'}
                                }
                            ]),
                            json.dumps([
                                {
                                    'assertion_key': 'assert-escalation-stage-recorded',
                                    'assertion_type': 'RECORD_EXISTS',
                                    'expected_condition': 'count >= 1',
                                    'target_table': 'sla_escalation_events',
                                    'filter_field': 'status',
                                    'filter_value': 'DISPATCHED'
                                }
                            ]),
                            'automatic', 45, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'scen-syn-004', 'org-matab-default', 'fac-central-opd', 'sim-scen-clinical-safety-block',
                            'Clinical Safety Hard Block on Autonomous Prescribing',
                            'Attempt automated prescription creation without human clinician signing and verify strict rejection.',
                            'clinical_safety_boundary', 'high',
                            json.dumps(['local', 'dev', 'sandbox', 'ci']), 1, 'APPROVED', 'CLINICIAN',
                            json.dumps(['simulation:run']),
                            json.dumps([
                                {
                                    'step_order': 1,
                                    'action_type': 'ATTEMPT_AUTONOMOUS_PRESCRIPTION',
                                    'target_service': 'prescriptions',
                                    'payload': {'patient_id': 'pat-syn-001', 'formulation_name': 'Sharbat Bazoori', 'auto_sign': True}
                                }
                            ]),
                            json.dumps([
                                {
                                    'assertion_key': 'assert-permission-denied',
                                    'assertion_type': 'PERMISSION_DENIED',
                                    'expected_condition': 'status_code == 403',
                                    'target_table': 'simulation_step_executions',
                                    'filter_field': 'status',
                                    'filter_value': 'FAILED'
                                }
                            ]),
                            'automatic', 30, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'scen-syn-005', 'org-matab-default', 'fac-central-opd', 'sim-scen-dlq-circuit-breaker',
                            'Integration Dead-Letter Recovery & Circuit Breaker Trip',
                            'Simulate 5 consecutive remote 500 errors tripping circuit breaker and safe fallback.',
                            'dependency_faults', 'moderate',
                            json.dumps(['local', 'dev', 'sandbox', 'ci']), 1, 'APPROVED', 'ORG_ADMIN',
                            json.dumps(['simulation:run', 'simulation:fault_inject']),
                            json.dumps([
                                {
                                    'step_order': 1,
                                    'action_type': 'INVOKE_CONNECTOR',
                                    'target_service': 'integration_ops',
                                    'fault': {'fault_type': 'CIRCUIT_TRIPPED', 'failure_threshold': 5},
                                    'payload': {'connector_id': 'intg-abdm-sandbox', 'action': 'POST_LAB_ORDER'}
                                }
                            ]),
                            json.dumps([
                                {
                                    'assertion_key': 'assert-circuit-open',
                                    'assertion_type': 'STATE_EQUALS',
                                    'expected_condition': 'circuit_state == OPEN',
                                    'target_table': 'integration_circuit_breakers',
                                    'filter_field': 'connector_id',
                                    'filter_value': 'intg-abdm-sandbox'
                                }
                            ]),
                            'automatic', 60, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'scen-syn-006', 'org-matab-default', 'fac-central-opd', 'sim-scen-sod-verification-block',
                            'Separation of Duties Verification Self-Approval Block',
                            'Attempt exception self-verification by the resolving user and assert strict 403 Forbidden.',
                            'clinical_safety_boundary', 'moderate',
                            json.dumps(['local', 'dev', 'sandbox', 'ci']), 1, 'APPROVED', 'CLINIC_ADMIN',
                            json.dumps(['simulation:run']),
                            json.dumps([
                                {
                                    'step_order': 1,
                                    'action_type': 'ATTEMPT_SELF_VERIFICATION',
                                    'target_service': 'sla_governance',
                                    'payload': {'exception_id': 'exc-sim-001', 'user_id': 'usr-admin-1'}
                                }
                            ]),
                            json.dumps([
                                {
                                    'assertion_key': 'assert-sod-forbidden',
                                    'assertion_type': 'PERMISSION_DENIED',
                                    'expected_condition': 'status_code == 403',
                                    'target_table': 'simulation_step_executions',
                                    'filter_field': 'status',
                                    'filter_value': 'FAILED'
                                }
                            ]),
                            'automatic', 30, 'usr-admin-1', 'usr-admin-1'
                        )
                    ]
                    for s_id, o_id, f_id, s_key, s_name, s_purp, s_cat, s_risk, s_env, s_ver, s_st, s_own, s_perms, s_steps, s_asserts, s_clean, s_tout, app_by, cr_by in starter_scenarios:
                        conn.execute("""
                            INSERT OR REPLACE INTO simulation_scenarios (
                                id, organization_id, facility_id, scenario_key, name, purpose,
                                category, risk_level, environment_allowlist_json, version, status,
                                owner_role, required_permissions_json, steps_json, assertions_json,
                                cleanup_policy, timeout_seconds, approved_by, approved_at, created_by,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (
                            s_id, o_id, f_id, s_key, s_name, s_purp, s_cat, s_risk, s_env, s_ver, s_st,
                            s_own, s_perms, s_steps, s_asserts, s_clean, s_tout, app_by, cr_by
                        ))

                        # Snapshot version
                        ver_id = f"scenv-{s_id}-v{s_ver}"
                        snap_obj = {
                            "id": s_id, "scenario_key": s_key, "name": s_name, "purpose": s_purp,
                            "category": s_cat, "risk_level": s_risk, "version": s_ver, "status": s_st,
                            "steps": json.loads(s_steps), "assertions": json.loads(s_asserts)
                        }
                        conn.execute("""
                            INSERT OR REPLACE INTO simulation_scenario_versions (
                                id, scenario_id, version, snapshot_json, change_reason, authored_by, created_at
                            ) VALUES (?, ?, ?, ?, 'Initial approved seed scenario', ?, CURRENT_TIMESTAMP);
                        """, (ver_id, s_id, s_ver, json.dumps(snap_obj), app_by))

            # Prompt 38: Seed Initial Release Manifest & Feature Flags
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feature_flags';")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) as count FROM feature_flags WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_flags = [
                        (
                            'flag-cds-deep-reasoning', 'org-matab-default', 'flag-cds-deep-reasoning',
                            'Extended CDS Reasoning & Interaction Engine',
                            'Hybrid retrieval and deep drug-herb interaction checks',
                            'clinical_cds', 'high', 'CLINICAL_SAFETY_OFFICER', 0,
                            json.dumps({"local": True, "ci_test": True, "staging": True, "pilot": False, "production": False}),
                            json.dumps({"organizations": ["org-matab-default"], "facilities": [], "roles": ["PRACTITIONER", "CLINICIAN"], "user_ids": []}),
                            '2026-12-31', 0, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'flag-abdm-live-sync', 'org-matab-default', 'flag-abdm-live-sync',
                            'ABDM National Gateway Live Synchronization',
                            'Real-time ABDM health repository record pushing',
                            'integration', 'high', 'SECURITY_OFFICER', 0,
                            json.dumps({"local": False, "ci_test": False, "staging": True, "pilot": False, "production": False}),
                            json.dumps({"organizations": ["org-matab-default"], "facilities": ["fac-central-opd"], "roles": [], "user_ids": []}),
                            '2026-12-31', 0, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'flag-patient-portal-v2', 'org-matab-default', 'flag-patient-portal-v2',
                            'Patient Longitudinal Timeline Portal V2',
                            'Self-service patient access to longitudinal care encounters',
                            'patient_engagement', 'moderate', 'ORG_ADMIN', 0,
                            json.dumps({"local": True, "ci_test": True, "staging": True, "pilot": True, "production": False}),
                            json.dumps({"organizations": ["org-matab-default"], "facilities": [], "roles": [], "user_ids": []}),
                            '2026-12-31', 0, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'flag-auto-sms-reminders', 'org-matab-default', 'flag-auto-sms-reminders',
                            'Consent-Governed Auto SMS Appointment Reminders',
                            'Automated SMS notifications dispatched prior to scheduled visits',
                            'operational', 'moderate', 'ORG_ADMIN', 0,
                            json.dumps({"local": True, "ci_test": True, "staging": True, "pilot": True, "production": False}),
                            json.dumps({"organizations": ["org-matab-default"], "facilities": [], "roles": [], "user_ids": []}),
                            '2026-12-31', 0, 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'flag-advanced-nuskha-analytics', 'org-matab-default', 'flag-advanced-nuskha-analytics',
                            'Advanced Dispensary Nuskha Analytics',
                            'Compound frequency, botanical turnover, and inventory projections',
                            'operational', 'low', 'ORG_ADMIN', 1,
                            json.dumps({"local": True, "ci_test": True, "staging": True, "pilot": True, "production": True}),
                            json.dumps({"organizations": ["org-matab-default"], "facilities": [], "roles": [], "user_ids": []}),
                            '2027-06-30', 0, 'usr-admin-1', 'usr-admin-1'
                        )
                    ]
                    for f_id, o_id, f_key, f_name, f_desc, f_cat, f_risk, f_own, f_def, f_env, f_targ, f_exp, f_emg, c_by, u_by in seed_flags:
                        conn.execute("""
                            INSERT OR REPLACE INTO feature_flags (
                                id, organization_id, flag_key, name, description, category, risk_level,
                                owner_role, is_enabled_default, state_by_environment_json, targeting_rules_json,
                                expiry_date, is_emergency_disabled, created_by, updated_by, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (f_id, o_id, f_key, f_name, f_desc, f_cat, f_risk, f_own, f_def, f_env, f_targ, f_exp, f_emg, c_by, u_by))

                # Seed initial release manifest
                cursor.execute("SELECT COUNT(*) as count FROM release_manifests WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    rel_id = 'rel-v2026.10.14-01'
                    qg = {"UNIT_TESTS": "PASSED", "INTEGRATION_TESTS": "PASSED", "SECURITY_SCAN": "PASSED", "MIGRATION_COMPATIBILITY": "PASSED", "CLINICAL_SAFETY_GATE": "PASSED"}
                    migs = ["036_enterprise_workflow_simulation_failure_injection_schema.sql", "037_production_release_engineering_and_feature_flags_schema.sql"]
                    ffs = ["flag-cds-deep-reasoning", "flag-abdm-live-sync", "flag-patient-portal-v2", "flag-auto-sms-reminders", "flag-advanced-nuskha-analytics"]
                    apprv = [{"approved_by": "usr-admin-1", "approved_at": "2026-10-14T03:00:00Z", "role": "RELEASE_MANAGER", "notes": "Prompt 37/38 full release candidate"}]
                    rb_plan = {"strategy": "ROLLBACK_ARTIFACT", "target_environment": "staging", "prerequisites": ["Previous artifact available"]}
                    smoke = {"health_live": "OK", "database_connection": "OK", "tenant_isolation_barrier": "VERIFIED", "clinical_safety_firewall": "VERIFIED_FAIL_CLOSED"}

                    conn.execute("""
                        INSERT OR REPLACE INTO release_manifests (
                            id, organization_id, version_tag, title, description,
                            git_commit, git_branch, artifact_digest, target_environment, risk_level,
                            status, quality_gates_json, migrations_json, feature_flags_json,
                            config_changes_json, affected_modules_json, required_approvals_json,
                            actual_approvals_json, rollback_plan_json, post_deploy_evidence_json,
                            created_by, approved_by, deployed_by, deployed_at, created_at, updated_at
                        ) VALUES (?, 'org-matab-default', 'v2026.10.14-01', 'ZAYVORA MATAB OS v1.1.0-RC Production Release Candidate',
                            'Full clinical governance, simulation validation, and operational engine suite.',
                            '8f9b21a', 'main', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                            'staging', 'high', 'deployed', ?, ?, ?, '{}', '["clinical","operations","governance"]',
                            '["RELEASE_MANAGER","SECURITY_OFFICER"]', ?, ?, ?, 'usr-admin-1', 'usr-admin-1', 'usr-admin-1',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                    """, (rel_id, json.dumps(qg), json.dumps(migs), json.dumps(ffs), json.dumps(apprv), json.dumps(rb_plan), json.dumps(smoke)))

                    # Insert gate evaluation records
                    for gtype, gst in qg.items():
                        conn.execute("""
                            INSERT OR REPLACE INTO release_gate_evaluations (
                                id, release_id, gate_type, status, evidence_summary, metrics_json, evaluated_by, evaluated_at
                            ) VALUES (?, ?, ?, ?, 'Initial seed gate evaluation verified', '{}', 'usr-admin-1', CURRENT_TIMESTAMP);
                        """, (f"gate-{rel_id}-{gtype}", rel_id, gtype, gst))

                    # Insert initial deployment execution record
                    conn.execute("""
                        INSERT OR REPLACE INTO deployment_executions (
                            id, release_id, environment, status, smoke_tests_passed,
                            evidence_snapshot_json, executed_by, started_at, completed_at
                        ) VALUES (?, ?, 'staging', 'SUCCESS', 1, ?, 'usr-admin-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                    """, (f"dep-{rel_id}-staging", rel_id, json.dumps(smoke)))

            # Prompt 39: Seed Initial Service Catalog, Alerts, SLOs & Telemetry
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='observability_service_catalog';")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) as count FROM observability_service_catalog WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_services = [
                        ('svc-auth', 'org-matab-default', 'svc-auth', 'Authentication & Session Service', 'Session issuance, token validation, scoped RBAC', 'PLATFORM_ENGINEER', 'tier_1_mission_critical', '[]', '["svc-encounters","svc-prescriptions"]', 'HEALTHY'),
                        ('svc-patients', 'org-matab-default', 'svc-patients', 'Master Patient Index (MPI)', 'Patient demographics, deduplication, consent', 'PLATFORM_ENGINEER', 'tier_1_mission_critical', '["svc-auth"]', '["svc-encounters"]', 'HEALTHY'),
                        ('svc-encounters', 'org-matab-default', 'svc-encounters', 'Clinical Encounter & OPD Queue', 'Encounter lifecycle, clinical charting, triage', 'CLINICAL_SAFETY_OFFICER', 'tier_1_mission_critical', '["svc-auth","svc-patients"]', '["svc-prescriptions"]', 'HEALTHY'),
                        ('svc-safety-firewall', 'org-matab-default', 'svc-safety-firewall', 'Clinical Safety Firewall', 'Herb-drug interactions, contraindication checks', 'CLINICAL_SAFETY_OFFICER', 'tier_1_mission_critical', '["svc-auth"]', '["svc-prescriptions"]', 'HEALTHY'),
                        ('svc-prescriptions', 'org-matab-default', 'svc-prescriptions', 'Formulary & Nuskha Builder', 'Prescription posology, digital signing, validation', 'CLINICAL_SAFETY_OFFICER', 'tier_1_mission_critical', '["svc-safety-firewall"]', '["svc-billing-inventory"]', 'HEALTHY'),
                        ('svc-billing-inventory', 'org-matab-default', 'svc-billing-inventory', 'Billing & Pharmacy Inventory', 'Exact-decimal billing, FEFO batch stock, dispensing', 'PLATFORM_ENGINEER', 'tier_2_business_critical', '["svc-prescriptions"]', '[]', 'HEALTHY'),
                        ('svc-knowledge-rag', 'org-matab-default', 'svc-knowledge-rag', 'KAVS Evidence & RAG Assistant', 'Knowledge hybrid retrieval, unani ontology, citations', 'PLATFORM_ENGINEER', 'tier_2_business_critical', '["svc-auth"]', '[]', 'HEALTHY'),
                        ('svc-integration-jobs', 'org-matab-default', 'svc-integration-jobs', 'Integration Queue & Background Workers', 'ABDM sync, FHIR bundles, asynchronous jobs', 'INTEGRATION_LEAD', 'tier_2_business_critical', '["svc-auth"]', '[]', 'HEALTHY'),
                        ('svc-audit-ledger', 'org-matab-default', 'svc-audit-ledger', 'Append-Only Audit Ledger', 'Tamper-evident security audit trail', 'SECURITY_OFFICER', 'tier_1_mission_critical', '[]', '[]', 'HEALTHY'),
                        ('svc-release-flags', 'org-matab-default', 'svc-release-flags', 'Release Governance & Feature Flags', 'Release promotions, cohort targeting, kill-switches', 'RELEASE_MANAGER', 'tier_2_business_critical', '[]', '[]', 'HEALTHY')
                    ]
                    for s_id, o_id, s_key, s_name, s_desc, s_own, s_tier, s_up, s_dn, s_st in seed_services:
                        conn.execute("""
                            INSERT OR REPLACE INTO observability_service_catalog (
                                id, organization_id, service_key, name, description, owner_role, tier,
                                upstream_dependencies_json, downstream_dependencies_json, health_status,
                                last_probed_at, is_active, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (s_id, o_id, s_key, s_name, s_desc, s_own, s_tier, s_up, s_dn, s_st))

                # Seed Alert Definitions
                cursor.execute("SELECT COUNT(*) as count FROM observability_alert_definitions WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_alerts = [
                        (
                            'alert-def-api-5xx', 'org-matab-default', 'ALERT-API-HIGH-5XX-RATE',
                            'High HTTP 5XX Internal Server Error Rate',
                            'Spike in HTTP 500 errors exceeding 5 instances in 5 minutes across API routes',
                            'svc-auth', 'P1_CRITICAL', 'api.requests.error_count', 'GT', 5.0, 300,
                            'PLATFORM_ENGINEER',
                            '### RUNBOOK: High 5XX Rate\n1. Inspect /api/v1/observability/diagnostics/deep for database pool or lock errors.\n2. Verify if recent release was promoted via /api/v1/releases/manifests.\n3. If isolated to a feature flag, engage emergency kill-switch.\n4. Prohibited: Never restart DB during active consultation hours without failover.',
                            json.dumps(["ops_dashboard", "pager_duty_sandbox"]), 'alert_key+service_key', 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'alert-def-queue-backlog', 'org-matab-default', 'ALERT-QUEUE-BACKLOG-ACCUMULATION',
                            'Integration Worker Queue Backlog Accumulation',
                            'Asynchronous integration jobs queue backlog exceeding 50 pending records',
                            'svc-integration-jobs', 'P2_HIGH', 'queue.jobs.backlog_depth', 'GT', 50.0, 600,
                            'INTEGRATION_LEAD',
                            '### RUNBOOK: Queue Backlog\n1. Inspect dead_letter_items table for poison messages.\n2. Verify external gateway connectivity status for ABDM/LIS.\n3. Execute allowlisted remediation RESTART_BACKGROUND_CONSUMER if worker thread stalled.',
                            json.dumps(["ops_dashboard"]), 'alert_key+service_key', 'usr-admin-1', 'usr-admin-1'
                        ),
                        (
                            'alert-def-safety-firewall', 'org-matab-default', 'ALERT-SAFETY-GATE-FAIL-CLOSED',
                            'Clinical Safety Firewall Evaluator Degradation',
                            'Safety preflight evaluation errors or unapproved rule bypass attempts detected',
                            'svc-safety-firewall', 'P1_CRITICAL', 'safety_firewall.violations.total', 'GT', 0.0, 60,
                            'CLINICAL_SAFETY_OFFICER',
                            '### RUNBOOK: Clinical Safety Firewall Alert\n1. Confirm fail-closed behavior: All draft prescriptions must be blocked from signing.\n2. Check rule release ledger in clinical_knowledge_rule_releases.\n3. Escalate immediately to Clinical Safety Officer.',
                            json.dumps(["ops_dashboard", "clinical_governance_channel"]), 'alert_key+service_key', 'usr-admin-1', 'usr-admin-1'
                        )
                    ]
                    for a_id, o_id, a_key, a_title, a_desc, a_svc, a_sev, a_met, a_op, a_thr, a_win, a_own, a_rb, a_ch, a_fp, c_by, u_by in seed_alerts:
                        conn.execute("""
                            INSERT OR REPLACE INTO observability_alert_definitions (
                                id, organization_id, alert_key, title, description, service_key,
                                severity, metric_name, condition_operator, threshold_value,
                                evaluation_window_seconds, owner_role, runbook_markdown,
                                notification_channels_json, dedup_fingerprint_rule, is_enabled, version,
                                created_by, updated_by, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '1.0.0', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (a_id, o_id, a_key, a_title, a_desc, a_svc, a_sev, a_met, a_op, a_thr, a_win, a_own, a_rb, a_ch, a_fp, c_by, u_by))

                # Seed Governed SLO Registry
                cursor.execute("SELECT COUNT(*) as count FROM observability_slo_registry WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_slos = [
                        (
                            'slo-api-availability', 'org-matab-default', 'SLO-API-AVAILABILITY',
                            'Core API Request Success Availability', 'svc-auth',
                            'Proportion of valid authenticated API requests returning non-5XX status codes',
                            0.995, 30, 'PLATFORM_ENGINEER', 'APPROVED', 'usr-admin-1',
                            1000, 998, 5.0, 3.0, 0.4, 'HEALTHY', 'Measured via telemetry metrics buffer'
                        ),
                        (
                            'slo-safety-firewall-availability', 'org-matab-default', 'SLO-SAFETY-FIREWALL-AVAILABILITY',
                            'Clinical Safety Preflight Verification Availability', 'svc-safety-firewall',
                            'Proportion of prescription preflight safety checks completing without evaluator error',
                            0.999, 30, 'CLINICAL_SAFETY_OFFICER', 'APPROVED', 'usr-admin-1',
                            500, 500, 0.5, 0.5, 0.0, 'HEALTHY', 'Zero tolerance for silent unhandled evaluator crashes'
                        )
                    ]
                    for s_id, o_id, s_key, s_name, s_svc, s_desc, s_tgt, s_win, s_own, s_st, app_by, tot, good, eb_tot, eb_rem, burn, comp, gaps in seed_slos:
                        conn.execute("""
                            INSERT OR REPLACE INTO observability_slo_registry (
                                id, organization_id, slo_key, name, service_key, sli_description,
                                target_ratio, window_days, owner_role, approval_status, approved_by, approved_at,
                                total_events, good_events, error_budget_total, error_budget_remaining,
                                burn_rate, compliance_status, known_gaps_notes, version, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, '1.0.0', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (s_id, o_id, s_key, s_name, s_svc, s_desc, s_tgt, s_win, s_own, s_st, app_by, tot, good, eb_tot, eb_rem, burn, comp, gaps))

                # Seed Sample Telemetry Metrics
                cursor.execute("SELECT COUNT(*) as count FROM observability_telemetry_metrics WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_metrics = [
                        ('met-seed-01', 'org-matab-default', 'api.requests.total', '/api/v1/encounters', 'SUCCESS', 1.0, 'count', 'MEASURED'),
                        ('met-seed-02', 'org-matab-default', 'api.requests.total', '/api/v1/prescriptions', 'SUCCESS', 1.0, 'count', 'MEASURED'),
                        ('met-seed-03', 'org-matab-default', 'api.requests.total', '/api/v1/auth/login', 'SUCCESS', 1.0, 'count', 'MEASURED'),
                        ('met-seed-04', 'org-matab-default', 'queue.jobs.backlog_depth', 'worker.integration_jobs', 'SUCCESS', 2.0, 'gauge', 'MEASURED')
                    ]
                    for m_id, o_id, m_name, m_route, m_out, m_val, m_unit, m_type in seed_metrics:
                        conn.execute("""
                            INSERT OR REPLACE INTO observability_telemetry_metrics (
                                id, organization_id, metric_name, route_or_subsystem, outcome_class,
                                metric_value, unit, measurement_type, timestamp, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (m_id, o_id, m_name, m_route, m_out, m_val, m_unit, m_type))

                # Prompt 40: Seed BIA Criticality Domain Catalog
                cursor.execute("SELECT COUNT(*) as count FROM dr_domain_criticality_catalog WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_domains = [
                        (
                            'auth_identity', 'org-matab-default', 'Authentication & User Access', 'tier_0_critical',
                            json.dumps(['users', 'sessions', 'roles', 'permissions']),
                            'SECURITY_OFFICER', 'PLATFORM_ENGINEER', 15, 5,
                            'Allow verified active JWT tokens; suspend new credential creation',
                            'Reconcile credential revocation list against security audit log',
                            'fully_protected'
                        ),
                        (
                            'patients_encounters', 'org-matab-default', 'Patient Registry & Clinical Encounters', 'tier_0_critical',
                            json.dumps(['patients', 'patient_identifiers', 'encounters']),
                            'CLINICAL_DIRECTOR', 'DATABASE_ENGINEER', 15, 5,
                            'Read-only lookup from offline cache; physical downtime intake forms',
                            'Batch import and identity deduplication against Master Patient Index',
                            'fully_protected'
                        ),
                        (
                            'consultation_prescriptions', 'org-matab-default', 'Clinical Prescriptions & Formulations', 'tier_0_critical',
                            json.dumps(['prescriptions', 'nuskha_items', 'unani_assessments']),
                            'CHIEF_HAKEEM', 'CLINICAL_SAFETY_OFFICER', 15, 5,
                            'Physical paper prescription pads with mandatory clinician signature; zero autonomous signing',
                            'Dual-clinician reconciliation of paper orders into canonical prescription ledger',
                            'fully_protected'
                        ),
                        (
                            'rules_governance', 'org-matab-default', 'Clinical Safety Firewall & Rules', 'tier_0_critical',
                            json.dumps(['clinical_rules', 'safety_cases', 'feature_flags']),
                            'CLINICAL_SAFETY_OFFICER', 'SOFTWARE_ARCHITECT', 15, 0,
                            'Fail-closed: all overridable warnings escalate to mandatory manual clinician approval',
                            'Re-verify safety rule release hashes against governed registry before unlocking',
                            'fully_protected'
                        ),
                        (
                            'audit_ledger', 'org-matab-default', 'Immutable Audit & Compliance Ledger', 'tier_0_critical',
                            json.dumps(['clinical_ledger_events', 'audit_events']),
                            'COMPLIANCE_OFFICER', 'SRE_LEAD', 30, 0,
                            'Append-only local queue; reject any restore attempting to rewrite historical hash chains',
                            'Cryptographic verification of SHA-256 state chain continuity',
                            'fully_protected'
                        ),
                        (
                            'appointments_queue', 'org-matab-default', 'Scheduling & Clinic Queue Tokens', 'tier_1_core',
                            json.dumps(['appointments', 'queue_tokens']),
                            'CLINIC_ADMIN', 'PLATFORM_ENGINEER', 30, 15,
                            'Manual paper queue tokens with arrival timestamps',
                            'Chronological token ingestion and duplicate check upon system return',
                            'partially_protected'
                        ),
                        (
                            'billing_payments', 'org-matab-default', 'Invoicing, Payments & Settlement', 'tier_1_core',
                            json.dumps(['invoices', 'payments', 'payment_refunds']),
                            'FINANCE_DIRECTOR', 'DATABASE_ENGINEER', 60, 15,
                            'Pre-numbered offline receipt books; defer online card/gateway settlement',
                            'Cross-match payment gateway settlement reports against physical receipt log',
                            'partially_protected'
                        ),
                        (
                            'inventory_stock', 'org-matab-default', 'Pharmacy Formulary & Batch Inventory', 'tier_2_supporting',
                            json.dumps(['inventory_items', 'inventory_batches', 'stock_movements']),
                            'PHARMACY_LEAD', 'DATABASE_ENGINEER', 120, 30,
                            'Manual stock dispensation sheet; suspend automated reorder calculations',
                            'Post-recovery physical inventory count audit and variance adjustment log',
                            'partially_protected'
                        ),
                        (
                            'documents_artifacts', 'org-matab-default', 'Clinical Document Bundles & PDFs', 'tier_2_supporting',
                            json.dumps(['governed_artifacts']),
                            'CLINIC_ADMIN', 'STORAGE_ADMIN', 240, 60,
                            'Reference paper consultation summaries and physical copies',
                            'Validate SHA-256 digests between DB metadata and filesystem storage',
                            'partially_protected'
                        ),
                        (
                            'knowledge_provenance', 'org-matab-default', 'KAVS Monograph & Citation Provenance', 'tier_2_supporting',
                            json.dumps(['clinical_sources', 'kavs_claims', 'kavs_extractions']),
                            'KAVS_CURATOR', 'SOFTWARE_ARCHITECT', 240, 240,
                            'Fall back to published physical Unani pharmacopoeia references',
                            'Verify source integrity against canonical citation locator registry',
                            'partially_protected'
                        ),
                        (
                            'integration_queues', 'org-matab-default', 'Transactional Outbox & Webhooks', 'tier_2_supporting',
                            json.dumps(['integration_jobs', 'outbox_events']),
                            'INTEGRATIONS_LEAD', 'SRE_LEAD', 120, 15,
                            'Pause outbound SMS/webhook dispatchers to prevent duplicate side effects',
                            'Idempotency check on external delivery receipts before unpausing queues',
                            'partially_protected'
                        ),
                        (
                            'analytics_read_models', 'org-matab-default', 'Operational Analytics & Command Center', 'tier_3_internal',
                            json.dumps(['command_center_threshold_rules', 'analytics_runs']),
                            'OPERATIONS_DIRECTOR', 'DATA_ENGINEER', 480, 1440,
                            'Suspend live dashboard refresh; rely on primary operational counters',
                            'Trigger background recalculation from restored canonical transactional records',
                            'fully_protected'
                        )
                    ]
                    for d_id, o_id, d_name, d_tier, d_tbls, b_own, t_own, rto, rpo, deg, rec, st in seed_domains:
                        conn.execute("""
                            INSERT OR REPLACE INTO dr_domain_criticality_catalog (
                                id, organization_id, domain_name, tier, system_of_record_tables_json,
                                business_owner, technical_owner, approved_rto_minutes, approved_rpo_minutes,
                                degraded_mode_policy, reconciliation_protocol, status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (d_id, o_id, d_name, d_tier, d_tbls, b_own, t_own, rto, rpo, deg, rec, st))

                # Prompt 40: Seed Business Continuity & Downtime Runbooks
                cursor.execute("SELECT COUNT(*) as count FROM dr_business_continuity_runbooks WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_runbooks = [
                        (
                            'cb-app-offline', 'org-matab-default', 'Application Service Downtime (Database Operational)',
                            'Web server / API service unresponsive or undergoing emergency patching',
                            'PLATFORM_ENGINEER', 'CHIEF_HAKEEM',
                            json.dumps(['Direct read-only database query via CLI', 'Paper intake for emergency walk-ins']),
                            json.dumps(['Direct SQL write to production without migration', 'Unverified prescribing']),
                            'Use Standard Downtime Form DT-01. Record Patient MRN, symptoms, vitals, and prescribed herbs.',
                            'Verify paper record authenticity; import into canonical encounters via reconciliation queue.',
                            json.dumps(['API service responds to /health/ready', 'Auth sessions verified', 'Zero unhandled errors'])
                        ),
                        (
                            'cb-db-outage', 'org-matab-default', 'Primary Database Storage Failure / Active Recovery Drill',
                            'SQLite file corruption, WAL checkpoint failure, or disk volume unavailable',
                            'DATABASE_ENGINEER', 'CLINICAL_DIRECTOR',
                            json.dumps(['Switch to isolated standby instance', 'Physical clinic paper workflow']),
                            json.dumps(['Modifying damaged database in-place', 'Replaying unverified transactions']),
                            'Activate physical clinic paper operations. Dispense from emergency floor stock.',
                            'Execute 7-step restore drill into isolated target; verify PRAGMA integrity_check = ok before cutover.',
                            json.dumps(['Database integrity check passes', 'Zero foreign key violations', 'Table count matches catalog'])
                        ),
                        (
                            'cb-network-partition', 'org-matab-default', 'Clinic Edge Network Partition / Internet Outage',
                            'Loss of ISP connectivity at clinic branch; cloud/external APIs unreachable',
                            'NETWORK_ADMIN', 'CLINIC_ADMIN',
                            json.dumps(['Local offline OPD consultations', 'Local dispensary medication delivery']),
                            json.dumps(['Attempting external ABDM sync', 'External payment processing']),
                            'Operate in local-first standalone clinic mode. Log all transactions locally.',
                            'Hold outbound integration outbox in paused status; unpause with deduplication check once network restored.',
                            json.dumps(['Internet ping restored for >10 mins', 'ABDM connector healthy', 'Outbox queues processed cleanly'])
                        ),
                        (
                            'cb-payment-gateway-down', 'org-matab-default', 'Third-Party Payment Gateway Outage',
                            'Payment processor API down, webhook failures, or settlement timeout spikes',
                            'FINANCE_DIRECTOR', 'INTEGRATIONS_LEAD',
                            json.dumps(['Cash collection', 'Manual UPI QR receipts', 'Credit billing for registered patients']),
                            json.dumps(['Double-charging credit cards', 'Blocking clinical care due to gateway error']),
                            'Issue physical paper receipt with serial number and note payment method (Cash / Offline QR).',
                            'Reconcile bank settlement batch against physical receipt serial numbers.',
                            json.dumps(['Gateway API status green', 'Webhook queue processed', 'Zero pending reconciliation disputes'])
                        )
                    ]
                    for r_id, o_id, r_title, r_trig, op_own, cl_lead, s_caps, p_acts, off_proc, rec_proc, res_crit in seed_runbooks:
                        conn.execute("""
                            INSERT OR REPLACE INTO dr_business_continuity_runbooks (
                                id, organization_id, title, trigger_conditions, operational_owner,
                                clinical_lead, safe_capabilities_json, prohibited_actions_json,
                                offline_recording_procedure_markdown, reconciliation_protocol_markdown,
                                resumption_criteria_json, is_active, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (r_id, o_id, r_title, r_trig, op_own, cl_lead, s_caps, p_acts, off_proc, rec_proc, res_crit))

                # Prompt 40: Seed Sample Downtime Reconciliation Record
                cursor.execute("SELECT COUNT(*) as count FROM dr_downtime_reconciliation_records WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    conn.execute("""
                        INSERT OR REPLACE INTO dr_downtime_reconciliation_records (
                            id, organization_id, runbook_id, downtime_reference_code, domain,
                            patient_identifier, captured_by_name, captured_at, recorded_payload_json,
                            status, created_at, updated_at
                        ) VALUES (
                            'dtr-seed-001', 'org-matab-default', 'cb-app-offline', 'DT-PAPER-20261014-001',
                            'patient_encounter', 'P-10001', 'Dr. Tariq Khan', CURRENT_TIMESTAMP,
                            ?, 'pending_review', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """, (json.dumps({
                        "chief_complaint": "Severe Su-e-Mizaj Har with headache",
                        "nabz_rate": 84,
                        "nabz_type": "Saree (Rapid)",
                        "prescribed_formulation": "Sharbat Bazoori Motadil",
                        "dosage": "20ml twice daily with water",
                        "notes": "Recorded on paper downtime slip DT-01 during network maintenance"
                    }),))

                # Prompt 41: Seed Data Lifecycle Inventory Catalog
                cursor.execute("SELECT COUNT(*) as count FROM data_lifecycle_inventory_catalog WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_categories = [
                        ('cat-pt-demographics', 'org-matab-default', 'patient_demographics', 'Patient Master Demographic & Identity Profiles', 'patients', 'relational_table', 'CLINICAL_DIRECTOR', 'DATABASE_ENGINEER', 'restricted_phi', json.dumps(['patients_fts', 'timeline_events']), 'pol-clinical-statutory-7yr', 'restrict', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-clinical-encounters', 'org-matab-default', 'clinical_encounters', 'Clinical Encounter Notes, Consultations & Diagnoses', 'encounters', 'relational_table', 'CHIEF_HAKEEM', 'BACKEND_LEAD', 'restricted_phi', json.dumps(['encounter_sections', 'timeline_events']), 'pol-clinical-statutory-7yr', 'restrict', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-prescriptions-nuskha', 'org-matab-default', 'prescriptions_nuskha', 'Signed Prescriptions & Customized Nuskha Formulations', 'prescriptions', 'relational_table', 'CHIEF_HAKEEM', 'BACKEND_LEAD', 'restricted_phi', json.dumps(['prescription_items', 'dispensing_records']), 'pol-clinical-statutory-7yr', 'restrict', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-formulary-master', 'org-matab-default', 'formulary_master', 'Approved Unani Formulations, Single Herbs & Substitutions', 'formulations', 'relational_table', 'FORMULARY_COMMITTEE', 'DATABASE_ENGINEER', 'public_knowledge', json.dumps(['formulation_ingredients', 'formulations_fts']), None, 'manual_review', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-appointment-sched', 'org-matab-default', 'appointment_scheduling', 'Appointment Bookings, Queues & OPD Tokens', 'appointments', 'relational_table', 'CLINIC_ADMIN', 'BACKEND_LEAD', 'restricted_phi', json.dumps(['queue_entries', 'operational_metrics']), 'pol-clinical-statutory-7yr', 'deidentify', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-inventory-ledger', 'org-matab-default', 'inventory_ledger', 'Pharmacy Stock Movements, Batches & Expiry Tracking', 'inventory_transactions', 'relational_table', 'INVENTORY_MANAGER', 'DATABASE_ENGINEER', 'operational_confidential', json.dumps(['inventory_items', 'stock_batches']), 'pol-financial-7yr', 'restrict', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-billing-trans', 'org-matab-default', 'billing_transactions', 'Invoices, Payments, Receipts, Voids & Adjustments', 'invoices', 'relational_table', 'FINANCE_DIRECTOR', 'DATABASE_ENGINEER', 'financial_pci', json.dumps(['payments', 'invoice_items', 'cashier_sessions']), 'pol-financial-7yr', 'restrict', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-comms-history', 'org-matab-default', 'comms_history', 'Patient Reminders, SMS & WhatsApp Delivery Transcripts', 'communication_logs', 'relational_table', 'COMMUNICATIONS_LEAD', 'BACKEND_LEAD', 'restricted_phi', json.dumps(['communication_threads']), 'pol-clinical-statutory-7yr', 'delete', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-knowledge-corpus', 'org-matab-default', 'knowledge_corpus', 'Unani Canon Textbooks, Classical Formularies & Research Citations', 'unani_knowledge_sources', 'relational_table', 'KNOWLEDGE_STEWARD', 'PLATFORM_ENGINEER', 'public_knowledge', json.dumps(['unani_literature_corpus', 'knowledge_embeddings']), None, 'manual_review', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-security-audit', 'org-matab-default', 'security_audit_ledger', 'Cryptographic Hash-Chained Security & Access Audit Records', 'security_audit_log', 'relational_table', 'COMPLIANCE_OFFICER', 'SECURITY_ENGINEER', 'operational_confidential', json.dumps(['audit_chains', 'auth_session_events']), 'pol-audit-7yr', 'manual_review', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-integration-outbox', 'org-matab-default', 'integration_outbox', 'Asynchronous Integration Connector Outbox Payloads & ABDM Sync', 'integration_outbox', 'event_queue', 'INTEGRATIONS_LEAD', 'PLATFORM_ENGINEER', 'operational_confidential', json.dumps(['integration_dead_letter', 'retry_queues']), 'pol-outbox-90d', 'delete', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-cache-ephemeral', 'org-matab-default', 'cache_ephemeral', 'In-Memory Query Projections, Transient Buffers & View Caches', 'analytics_read_models', 'cache_read_model', 'PLATFORM_ENGINEER', 'PLATFORM_ENGINEER', 'operational_confidential', json.dumps(['command_center_aggregates', 'rate_limit_buckets']), None, 'delete', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-system-backups', 'org-matab-default', 'system_backups', 'Encrypted Automated SQLite WAL Backups & Restore Archives', 'dr_backup_catalog', 'file_system_artifact', 'DATABASE_ENGINEER', 'INFRASTRUCTURE_LEAD', 'restricted_phi', json.dumps(['dr_manifests', 'backup_volumes']), None, 'manual_review', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed'),
                        ('cat-temp-exports', 'org-matab-default', 'temp_export_artifacts', 'Staging CSV/PDF Export Files & Ephemeral Reports', 'temporary_exports', 'file_system_artifact', 'OPERATIONS_MANAGER', 'BACKEND_LEAD', 'restricted_phi', json.dumps(['staging_filesystem_blobs']), 'pol-temp-exports-30d', 'delete', 'EXPIRE_WITH_BACKUP_ROTATION', 'governed')
                    ]
                    for c_id, o_id, c_name, c_desc, c_src, c_styp, d_own, t_own, sens, l_cop, def_pol, disp, bkp, st in seed_categories:
                        conn.execute("""
                            INSERT OR REPLACE INTO data_lifecycle_inventory_catalog (
                                id, organization_id, category_name, description, canonical_source_table,
                                storage_type, data_owner_role, technical_owner_role, sensitivity_classification,
                                linked_copies_json, default_policy_key, disposal_supported, backup_behavior,
                                status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (c_id, o_id, c_name, c_desc, c_src, c_styp, d_own, t_own, sens, l_cop, def_pol, disp, bkp, st))

                # Prompt 41: Seed Versioned Retention Policies
                cursor.execute("SELECT COUNT(*) as count FROM data_lifecycle_policies WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_policies = [
                        (
                            'pol-clinical-statutory-7yr', 'org-matab-default', 'CLINICAL_STATUTORY_7YR', '1.0.0',
                            'Clinical Records Statutory 7-Year Retention Policy',
                            'Governs preservation of patient encounters, signed prescriptions, assessments, and health logs for 7 years minimum from last consultation.',
                            json.dumps(['cat-clinical-encounters', 'cat-prescriptions-nuskha', 'cat-pt-demographics']),
                            'tenant', 'last_encounter_date', 2555, 'RESTRICTED_READ_ONLY', 'restrict', 'STRICT_BLOCK', 'ALL_LINKED_STORES',
                            'CLINICAL_GOVERNANCE_BOARD', json.dumps(['CHIEF_HAKEEM', 'CLINICAL_DIRECTOR', 'LEGAL_COUNSEL']),
                            json.dumps(['IN-AYUSH', 'IN-EHR-STANDARD-2016', 'NMC-ETHICS-2002']),
                            json.dumps(['Clinical Establishments Act', 'Ayurveda, Siddha and Unani Drugs Rules']),
                            json.dumps(['Signed encounters cannot be physically deleted; only transitioned to restricted archival']),
                            'approved', '2026-01-01', None, 'SYSTEM_BOOTSTRAP', 'CLINICAL_DIRECTOR', '2026-01-01 00:00:00'
                        ),
                        (
                            'pol-financial-7yr', 'org-matab-default', 'FINANCIAL_TRANSACTIONS_7YR', '1.0.0',
                            'Financial & Billing Transactions 7-Year Statutory Policy',
                            'Invoices, payment receipts, voids, cashier reconciliation batches, and inventory movements preserved for 7 fiscal years.',
                            json.dumps(['cat-billing-trans', 'cat-inventory-ledger']),
                            'tenant', 'creation_date', 2555, 'RESTRICTED_READ_ONLY', 'restrict', 'STRICT_BLOCK', 'ALL_LINKED_STORES',
                            'FINANCE_DIRECTOR', json.dumps(['FINANCE_DIRECTOR', 'CHIEF_EXECUTIVE']),
                            json.dumps(['IN-COMPANIES-ACT', 'IN-GST-ACT-2017']),
                            json.dumps(['Section 128 Companies Act 2013', 'GST Section 36']),
                            json.dumps(['Zero hard deletion allowed during open tax audit periods']),
                            'approved', '2026-01-01', None, 'SYSTEM_BOOTSTRAP', 'FINANCE_DIRECTOR', '2026-01-01 00:00:00'
                        ),
                        (
                            'pol-audit-7yr', 'org-matab-default', 'SECURITY_AUDIT_LOG_7YR', '1.0.0',
                            'Security & Access Audit Ledger 7-Year Immutability Policy',
                            'Cryptographic hash-chained security logs, authentication events, and administrative actions retained immutable for 7 years.',
                            json.dumps(['cat-security-audit']),
                            'platform', 'creation_date', 2555, 'RESTRICTED_READ_ONLY', 'manual_review', 'STRICT_BLOCK', 'ALL_LINKED_STORES',
                            'CHIEF_INFORMATION_SECURITY_OFFICER', json.dumps(['CISO', 'COMPLIANCE_OFFICER']),
                            json.dumps(['ISO-27001', 'CERT-IN-2022']),
                            json.dumps(['CERT-In Cybersecurity Directions 2022', 'DISHA Privacy Guidelines']),
                            json.dumps(['Requires two-party authorization before any disposal review']),
                            'approved', '2026-01-01', None, 'SYSTEM_BOOTSTRAP', 'CISO', '2026-01-01 00:00:00'
                        ),
                        (
                            'pol-outbox-90d', 'org-matab-default', 'INTEGRATION_OUTBOX_90D', '1.0.0',
                            'Integration Outbox Dispatch 90-Day Retention Policy',
                            'Successfully acknowledged outbound connector and ABDM events purged after 90 days of verified completion.',
                            json.dumps(['cat-integration-outbox']),
                            'tenant', 'closure_date', 90, 'NONE', 'delete', 'STRICT_BLOCK', 'PRIMARY_ONLY',
                            'INTEGRATIONS_LEAD', json.dumps(['PLATFORM_ENGINEER', 'INTEGRATIONS_LEAD']),
                            json.dumps(['OPERATIONAL']),
                            json.dumps(['Operational System Hygiene Guideline']),
                            json.dumps(['Unacknowledged or dead-letter messages are retained until manually reconciled']),
                            'approved', '2026-01-01', None, 'SYSTEM_BOOTSTRAP', 'PLATFORM_ENGINEER', '2026-01-01 00:00:00'
                        ),
                        (
                            'pol-temp-exports-30d', 'org-matab-default', 'TEMP_EXPORTS_30D', '1.0.0',
                            'Temporary Export Artifacts 30-Day Purge Policy',
                            'Temporary CSV/PDF report files, analytical staging caches, and temporary export artifacts wiped after 30 days.',
                            json.dumps(['cat-temp-exports']),
                            'tenant', 'creation_date', 30, 'FILESYSTEM_COMPRESSED', 'delete', 'STRICT_BLOCK', 'CASCADE_PURGE',
                            'OPERATIONS_MANAGER', json.dumps(['OPERATIONS_MANAGER', 'BACKEND_LEAD']),
                            json.dumps(['PRIVACY-MINIMIZATION']),
                            json.dumps(['Digital Personal Data Protection Act 2023 - Data Minimization Principle']),
                            json.dumps(['Filesystem unlinks must be verified with sha256 checksum nullification']),
                            'approved', '2026-01-01', None, 'SYSTEM_BOOTSTRAP', 'OPERATIONS_MANAGER', '2026-01-01 00:00:00'
                        )
                    ]
                    for p_id, o_id, p_key, ver, titl, p_desc, cats, scp, trig, p_days, arch, disp, hld, prp, own, appr, jur, leg, cav, st, ef_fr, ef_to, c_by, a_by, a_at in seed_policies:
                        conn.execute("""
                            INSERT OR REPLACE INTO data_lifecycle_policies (
                                id, organization_id, policy_key, version, title, description,
                                data_category_ids_json, scope, retention_trigger, retention_period_days,
                                archive_rule, disposal_action, hold_behavior, downstream_propagation_rule,
                                accountable_owner, approver_roles_json, jurisdiction_tags_json,
                                legal_source_references_json, caveats_json, status, effective_from, effective_to,
                                created_by, approved_by, approved_at, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (p_id, o_id, p_key, ver, titl, p_desc, cats, scp, trig, p_days, arch, disp, hld, prp, own, appr, jur, leg, cav, st, ef_fr, ef_to, c_by, a_by, a_at))

                # Prompt 41: Seed Sample Active Legal Hold
                cursor.execute("SELECT COUNT(*) as count FROM data_lifecycle_legal_holds WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    conn.execute("""
                        INSERT OR REPLACE INTO data_lifecycle_legal_holds (
                            id, organization_id, hold_code, title, reason_category,
                            scope_filter_json, placed_by, placed_at, review_date,
                            status, affected_records_count, created_at, updated_at
                        ) VALUES (
                            'hold-seed-001', 'org-matab-default', 'LH-2026-MED-001',
                            'Preservation Order: District Consumer Disputes Redressal Forum Notice',
                            'litigation', ?, 'LEGAL_COUNSEL', CURRENT_TIMESTAMP, '2027-10-14',
                            'active', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """, (json.dumps({"category_id": "cat-clinical-encounters", "patient_id": "pat-syn-001"}),))

                # Prompt 42: Seed Master Entities Catalog
                cursor.execute("SELECT COUNT(*) as count FROM mdm_master_entities_catalog WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_master_entities = [
                        ('mdm-ent-patient', 'org-matab-default', 'patient', 'Master Patient Identity', 'patients', 'EMR_PRIMARY', 'CLINICAL_SUPERVISOR_DECISION', json.dumps({"name_cleaning": "trim_and_titlecase", "phone_normalization": "E164"})),
                        ('mdm-ent-facility', 'org-matab-default', 'facility', 'Master Clinic Facility', 'facilities', 'SYSTEM_CORE', 'SOURCE_SYSTEM_PRIORITY', json.dumps({})),
                        ('mdm-ent-practitioner', 'org-matab-default', 'practitioner', 'Master Practitioner (Tabib / Hakeem)', 'users', 'REGULATORY_REGISTRY', 'MOST_RECENT_VALIDATED', json.dumps({})),
                        ('mdm-ent-formulation', 'org-matab-default', 'formulation', 'Master Unani Formulary & Nuskha Catalog', 'formulations', 'SYSTEM_CORE', 'SOURCE_SYSTEM_PRIORITY', json.dumps({})),
                        ('mdm-ent-terminology', 'org-matab-default', 'terminology_concept', 'Governed Unani & Biomedical Terminology Catalog', 'mdm_terminology_mappings', 'SYSTEM_CORE', 'MANUAL_STIPULATION', json.dumps({})),
                        ('mdm-ent-encounter', 'org-matab-default', 'encounter', 'Master Clinical Encounter Record', 'encounters', 'EMR_PRIMARY', 'MANUAL_STIPULATION', json.dumps({}))
                    ]
                    for me_id, o_id, et, dn, ct, auth, surv, nrm in seed_master_entities:
                        conn.execute("""
                            INSERT OR REPLACE INTO mdm_master_entities_catalog (
                                id, organization_id, entity_type, display_name, canonical_table,
                                authoritative_source, survivorship_rule, normalization_rules_json,
                                status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (me_id, o_id, et, dn, ct, auth, surv, nrm))

                # Prompt 42: Seed Enterprise Data Quality Rules across 9 Dimensions
                cursor.execute("SELECT COUNT(*) as count FROM mdm_data_quality_rules WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_dq_rules = [
                        ('dq-rule-001', 'org-matab-default', 'RULE_PATIENT_MANDATORY_CONTACT', 'Patient Mandatory Reachable Contact', 'clinical_patient', 'completeness', 'required', 'review_required', 'tenant', 'patient', 'phone', json.dumps({"fields": ["phone", "address"], "require_at_least_one": True}), 'Patient must have at least one valid phone or physical address recorded.'),
                        ('dq-rule-002', 'org-matab-default', 'RULE_VALID_PHONE_FORMAT', 'Standard E.164 Phone Digit Range', 'clinical_patient', 'validity', 'format', 'warning', 'tenant', 'patient', 'phone', json.dumps({"regex": r"^\+?[0-9]{10,15}$"}), 'Phone numbers must contain between 10 and 15 numeric digits.'),
                        ('dq-rule-003', 'org-matab-default', 'RULE_UNIQUE_NATIONAL_ID', 'Strict Tenant-Level National ID Uniqueness', 'clinical_patient', 'uniqueness', 'uniqueness', 'blocking', 'tenant', 'patient', 'national_id', json.dumps({"unique_scope": "organization"}), 'ABHA / National ID cannot be duplicated across active patients in same organization.'),
                        ('dq-rule-004', 'org-matab-default', 'RULE_ENCOUNTER_DATES_LOGICAL', 'Encounter Closed After Start Time', 'clinical_encounter', 'consistency', 'cross_field_consistency', 'blocking', 'tenant', 'encounter', 'closed_at', json.dumps({"operator": "closed_at_gte_started_at"}), 'Encounter closed_at must be strictly greater than or equal to started_at.'),
                        ('dq-rule-005', 'org-matab-default', 'RULE_ENCOUNTER_PATIENT_EXISTS', 'Referential Integrity: Encounter Patient Foreign Key', 'clinical_encounter', 'referential_integrity', 'referential_integrity', 'blocking', 'tenant', 'encounter', 'patient_id', json.dumps({"target_table": "patients"}), 'Encounter patient_id must point to an existing active patient in the same organization.'),
                        ('dq-rule-006', 'org-matab-default', 'RULE_CLINICAL_VITALS_FRESHNESS', 'Clinical Vitals Freshness Policy', 'clinical_encounter', 'timeliness', 'freshness', 'warning', 'tenant', 'patient', 'vitals', json.dumps({"max_age_hours": 48}), 'Vitals older than 48 hours must be re-evaluated during active consultation.'),
                        ('dq-rule-007', 'org-matab-default', 'RULE_PROVENANCE_REQUIRED', 'Mandatory Provenance for Clinical Claims', 'clinical_knowledge', 'provenance', 'provenance', 'review_required', 'tenant', 'encounter', 'author_id', json.dumps({"require_author": True, "require_timestamp": True}), 'Every clinical record must record author_id and timestamp.'),
                        ('dq-rule-008', 'org-matab-default', 'RULE_GENDER_CONFORMANCE', 'HL7/ISO Standard Gender Code Conformance', 'clinical_patient', 'conformance', 'allowed_value', 'warning', 'tenant', 'patient', 'gender', json.dumps({"allowed_values": ["M", "F", "O", "U", "MALE", "FEMALE", "OTHER"]}), 'Gender must conform to standardized categorical values.'),
                        ('dq-rule-009', 'org-matab-default', 'RULE_DISPENSE_INVENTORY_MATCH', 'Reconciliation: Dispensed Nuskha Batch Decrement', 'pharmacy_inventory', 'reconciliation', 'cross_field_consistency', 'blocking', 'tenant', 'encounter', 'dispense_items', json.dumps({"reconcile_with": "inventory_ledger"}), 'Dispensed medicines must match recorded decrement in inventory ledger.')
                    ]
                    for r_id, o_id, r_key, r_nm, dom, dim, r_typ, sev, scp, tgt_e, tgt_f, r_log, rem in seed_dq_rules:
                        conn.execute("""
                            INSERT OR REPLACE INTO mdm_data_quality_rules (
                                id, organization_id, rule_key, name, domain, dimension, rule_type,
                                severity, scope, target_entity_type, target_field_path,
                                rule_logic_json, remediation_guidance, version, status,
                                created_by, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '1.0.0', 'approved', 'SYSTEM_BOOTSTRAP', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (r_id, o_id, r_key, r_nm, dom, dim, r_typ, sev, scp, tgt_e, tgt_f, r_log, rem))

                # Prompt 42: Seed Governed Terminology Mappings
                cursor.execute("SELECT COUNT(*) as count FROM mdm_terminology_mappings WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_terms = [
                        (
                            'tmap-seed-001', 'org-matab-default', 'SU_I_MIZAJ_BARID', 'Su-i-Mizaj Barid (Abnormal Cold Temperament)',
                            'SNOMED-CT', '386661006', 'Fever / Hypothermia disposition', 'approximate',
                            'general_unani_triage',
                            'Unani Su-i-Mizaj Barid represents a constitutional metabolic deceleration, not acute hypothermia.',
                            'Al-Qanun fi al-Tibb, Ibn Sina, Book I; CCRUM Classical Terminology',
                            'approved', 'CLINICAL_DIRECTOR', '2026-01-01 00:00:00',
                            'Approved as approximate operational mapping for cross-referencing only.'
                        ),
                        (
                            'tmap-seed-002', 'org-matab-default', 'IKHTINAQ_AL_RAHIM', 'Ikhtināq al-Rahim (Uterine Suffocation / Hysterical Neurosis)',
                            'ICD-10', 'F44.9', 'Dissociative and conversion disorder, unspecified', 'approximate',
                            'neuropsychiatry_gynaecology',
                            'Classical term incorporates autonomic and pelvic congestion factors not represented in modern psychiatric classification.',
                            'Kamil al-Sinaah al-Tibbiyah, Ali ibn al-Abbas al-Majusi',
                            'approved', 'CLINICAL_DIRECTOR', '2026-01-01 00:00:00',
                            'Approved with caveat that Unani treatment regimen addresses humor balances.'
                        )
                    ]
                    for tm_id, o_id, uc, ut, ms, mc, mt, m_typ, scp, lim, prov, st, r_by, r_at, rat in seed_terms:
                        conn.execute("""
                            INSERT OR REPLACE INTO mdm_terminology_mappings (
                                id, organization_id, unani_concept_code, unani_term, modern_code_system,
                                modern_concept_code, modern_term, mapping_type, clinical_scope,
                                limitations, provenance, review_status, reviewed_by, reviewed_at,
                                clinical_rationale, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (tm_id, o_id, uc, ut, ms, mc, mt, m_typ, scp, lim, prov, st, r_by, r_at, rat))

                # Prompt 42: Seed Sample Stewardship Case
                cursor.execute("SELECT COUNT(*) as count FROM mdm_stewardship_cases WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    conn.execute("""
                        INSERT OR REPLACE INTO mdm_stewardship_cases (
                            id, organization_id, title, description, category, priority,
                            status, target_entity_type, target_entity_id, proposed_resolution,
                            assigned_to, created_by, created_at, updated_at
                        ) VALUES (
                            'case-seed-001', 'org-matab-default',
                            'Data Quality Review: Verify Primary Phone Number for Patient pat-syn-001',
                            'Automated scan flagged potentially truncated mobile number for review.',
                            'data_quality_anomaly', 'medium', 'open', 'patient', 'pat-syn-001',
                            'Contact patient at next consultation to re-verify phone country code.',
                            'usr-steward-001', 'SYSTEM_BOOTSTRAP', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                # Prompt 43: Seed Governed Lineage Contracts, Graph Nodes, Edges & Change Requests
                cursor.execute("SELECT COUNT(*) as count FROM lineage_contracts_registry WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_contracts = [
                        (
                            'cnt-seed-patients', 'org-matab-default', 'db:patients', 'database', '1.0.0',
                            'Patient Registry Team',
                            json.dumps({
                                "table": "patients",
                                "columns": {
                                    "id": {"type": "TEXT", "primary_key": True},
                                    "mrn": {"type": "TEXT", "unique": True},
                                    "given_name": {"type": "TEXT", "nullable": False},
                                    "family_name": {"type": "TEXT", "nullable": True},
                                    "gender": {"type": "TEXT", "enum": ["male", "female", "other"]}
                                }
                            }),
                            'BACKWARD', 'RESTRICTED_PHI', 'approved',
                            json.dumps(["Legacy historical imports may have unverified addresses"])
                        ),
                        (
                            'cnt-seed-encounters', 'org-matab-default', 'db:encounters', 'database', '1.0.0',
                            'Clinical Care Team',
                            json.dumps({
                                "table": "encounters",
                                "columns": {
                                    "id": {"type": "TEXT", "primary_key": True},
                                    "patient_id": {"type": "TEXT", "references": "patients.id"},
                                    "practitioner_id": {"type": "TEXT"},
                                    "status": {"type": "TEXT", "enum": ["in_progress", "completed", "cancelled"]}
                                }
                            }),
                            'BACKWARD', 'RESTRICTED_PHI', 'approved', '[]'
                        ),
                        (
                            'cnt-seed-prescriptions', 'org-matab-default', 'db:prescriptions', 'database', '1.0.0',
                            'Pharmacovigilance & Formulations',
                            json.dumps({
                                "table": "prescriptions",
                                "columns": {
                                    "id": {"type": "TEXT", "primary_key": True},
                                    "encounter_id": {"type": "TEXT", "references": "encounters.id"},
                                    "patient_id": {"type": "TEXT", "references": "patients.id"},
                                    "status": {"type": "TEXT", "enum": ["draft", "signed", "dispensed"]}
                                }
                            }),
                            'BACKWARD', 'RESTRICTED_PHI', 'approved', '[]'
                        ),
                        (
                            'cnt-seed-api-encounter', 'org-matab-default', 'api:v1:encounters', 'api', '1.0.0',
                            'Integration Ops Team',
                            json.dumps({
                                "endpoint": "/api/v1/encounters",
                                "method": "POST",
                                "request_body": {"patient_id": "string", "facility_id": "string", "encounter_type": "string"},
                                "response_body": {"id": "string", "status": "string"}
                            }),
                            'BACKWARD', 'INTERNAL', 'approved', '[]'
                        ),
                        (
                            'cnt-seed-fhir-export', 'org-matab-default', 'export:abdm:fhir_bundle', 'export', '1.0.0',
                            'Interoperability Team',
                            json.dumps({
                                "resourceType": "Bundle",
                                "type": "document",
                                "entry": ["Composition", "Patient", "Practitioner", "MedicationRequest"]
                            }),
                            'FULL', 'RESTRICTED_PHI', 'approved', '[]'
                        )
                    ]
                    for cid, oid, ckey, ctyp, ver, own, sdef, pol, sens, st, lim in seed_contracts:
                        conn.execute("""
                            INSERT OR REPLACE INTO lineage_contracts_registry (
                                id, organization_id, contract_key, contract_type, version,
                                owner, schema_definition_json, compatibility_policy,
                                sensitivity, status, limitations_json, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (cid, oid, ckey, ctyp, ver, own, sdef, pol, sens, st, lim))

                    # Seed Lineage Nodes
                    seed_nodes = [
                        ('nod-table-patients', 'org-matab-default', 'table:patients', 'db_table', 'Patients Table', 'Canonical patients table in SQLite storage', 'cnt-seed-patients', 'Patient Registry Team', 'RESTRICTED_PHI', '{}'),
                        ('nod-col-patients-id', 'org-matab-default', 'col:patients.id', 'db_column', 'Patient Identifier', 'Unique UUID primary key for patient', None, 'Core Platform', 'INTERNAL', '{}'),
                        ('nod-col-patients-mrn', 'org-matab-default', 'col:patients.mrn', 'db_column', 'Medical Record Number', 'Enterprise unique MRN identifier', None, 'Patient Registry Team', 'RESTRICTED_PHI', '{}'),
                        ('nod-table-encounters', 'org-matab-default', 'table:encounters', 'db_table', 'Encounters Table', 'Clinical encounters storage', 'cnt-seed-encounters', 'Clinical Care Team', 'RESTRICTED_PHI', '{}'),
                        ('nod-table-prescriptions', 'org-matab-default', 'table:prescriptions', 'db_table', 'Prescriptions Table', 'Prescription and nuskha formulation storage', 'cnt-seed-prescriptions', 'Pharmacovigilance Team', 'RESTRICTED_PHI', '{}'),
                        ('nod-rule-dosage-check', 'org-matab-default', 'rule:nuskha_dosage_safety', 'workflow_rule', 'Nuskha Dosage Safety Gate', 'Dosage and toxic herb validation rule engine', None, 'Clinical Safety Directorate', 'INTERNAL', '{}'),
                        ('nod-api-post-encounter', 'org-matab-default', 'api:post_encounter', 'api_endpoint', 'Create Encounter API', 'REST API endpoint for consultation encounters', 'cnt-seed-api-encounter', 'Integration Ops', 'INTERNAL', '{}'),
                        ('nod-metric-active-patients', 'org-matab-default', 'metric:active_patients_kpi', 'analytics_metric', 'Active Patients KPI Cube', 'Analytics cube for longitudinal patient continuity', None, 'Analytics Team', 'INTERNAL', '{}'),
                        ('nod-ext-abdm-gateway', 'org-matab-default', 'ext:abdm_gateway', 'external_integration', 'National ABDM Gateway', 'ABDM M1/M2/M3 Health Information Exchange', 'cnt-seed-fhir-export', 'Interoperability Team', 'RESTRICTED_PHI', '{}')
                    ]
                    for nid, oid, nkey, ntyp, nname, ndesc, cid, nown, nsens, nmeta in seed_nodes:
                        conn.execute("""
                            INSERT OR REPLACE INTO lineage_nodes (
                                id, organization_id, node_key, node_type, name, description,
                                contract_id, owner, sensitivity, metadata_json, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (nid, oid, nkey, ntyp, nname, ndesc, cid, nown, nsens, nmeta))

                    # Seed Lineage Edges
                    seed_edges = [
                        ('edg-seed-001', 'org-matab-default', 'nod-table-patients', 'nod-col-patients-id', 'produces', 'schema_fk', 'verified', '{"relation": "has_column"}'),
                        ('edg-seed-002', 'org-matab-default', 'nod-table-patients', 'nod-col-patients-mrn', 'produces', 'schema_fk', 'verified', '{"relation": "has_column"}'),
                        ('edg-seed-003', 'org-matab-default', 'nod-table-patients', 'nod-table-encounters', 'reads', 'schema_fk', 'verified', '{"fk": "encounters.patient_id -> patients.id"}'),
                        ('edg-seed-004', 'org-matab-default', 'nod-table-encounters', 'nod-table-prescriptions', 'writes', 'code_reference', 'verified', '{"module": "apps.api.domains.prescriptions"}'),
                        ('edg-seed-005', 'org-matab-default', 'nod-table-prescriptions', 'nod-rule-dosage-check', 'validates', 'code_reference', 'verified', '{"engine": "SafetyFirewallEngine"}'),
                        ('edg-seed-006', 'org-matab-default', 'nod-api-post-encounter', 'nod-table-encounters', 'writes', 'code_reference', 'verified', '{"route": "handle_encounter_create"}'),
                        ('edg-seed-007', 'org-matab-default', 'nod-table-encounters', 'nod-metric-active-patients', 'aggregates_into', 'code_reference', 'verified', '{"cube": "encounter_volume"}'),
                        ('edg-seed-008', 'org-matab-default', 'nod-table-encounters', 'nod-ext-abdm-gateway', 'exports_to', 'config', 'verified', '{"adapter": "AbdmFhirAdapter"}')
                    ]
                    for eid, oid, src, tgt, rel, ev_typ, v_st, ev_dt in seed_edges:
                        conn.execute("""
                            INSERT OR REPLACE INTO lineage_edges (
                                id, organization_id, source_node_id, target_node_id,
                                relationship_type, evidence_type, verification_status,
                                evidence_details_json, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (eid, oid, src, tgt, rel, ev_typ, v_st, ev_dt))

                    # Seed Sample Change Request
                    conn.execute("""
                        INSERT OR REPLACE INTO lineage_change_requests (
                            id, organization_id, title, requester_id, contract_id,
                            source_node_id, target_version, change_type, diff_payload_json,
                            migration_plan_json, status, created_at, updated_at
                        ) VALUES (
                            'lcr-seed-001', 'org-matab-default',
                            'Add Optional Emergency Contact Extension Field to Patients Schema',
                            'usr-hakeem-1', 'cnt-seed-patients', 'nod-table-patients',
                            '1.1.0', 'additive',
                            '{"add_column": {"emergency_contact_name": "TEXT", "nullable": true}}',
                            '{"strategy": "ONLINE_ADD_COLUMN", "rollback": "DROP_COLUMN_NOT_REQUIRED"}',
                            'approved_for_test', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                # Prompt 44: Seed Governed Environments, Settings Catalog & Secret References
                cursor.execute("SELECT COUNT(*) as count FROM config_environments_registry;")
                if cursor.fetchone()["count"] == 0:
                    seed_envs = [
                        ('env-local', 'local_dev', 'Local Developer Workstation', 'Local workstation development and fast iteration', 'Local Engineering', 'sqlite_file', 'matab.db', 'local-env', 'service-local-dev', '127.0.0.1/32', 'none', 'MOCK_ONLY', 1, 0, 0, 0, '1.0.0', 'verified'),
                        ('env-test', 'test_ci', 'Automated CI / Test Suite', 'Automated test suite and regression runner', 'QA Team', 'sqlite_memory', ':memory:', 'ci-secrets', 'service-ci-runner', 'isolated-ci', 'none', 'MOCK_ONLY', 1, 0, 0, 0, '1.0.0', 'verified'),
                        ('env-staging', 'staging_synthetic', 'Staging Synthetic Environment', 'Pre-production verification with synthetic clinical patients', 'Platform Team', 'sqlite_file', 'staging_matab.db', 'staging-vault', 'service-staging', 'vpc-internal', 'outbound-proxy', 'SANDBOX', 1, 0, 0, 0, '1.0.0', 'verified'),
                        ('env-prod', 'production', 'Production Clinical Cluster', 'Live hospital and clinic patient consultation & encounters', 'SRE & Clinical Directorate', 'sqlite_wal', '/var/data/matab.db', 'prod-vault', 'service-matab-prod', 'public-https-waf', 'restricted-egress', 'PRODUCTION', 0, 0, 1, 1, '1.0.0', 'verified')
                    ]
                    for eid, code, name, purp, own, db_t, db_r, s_ns, s_id, ing, eg, ext_c, synth, dest, msg, pay, ver, v_st in seed_envs:
                        conn.execute("""
                            INSERT OR REPLACE INTO config_environments_registry (
                                id, environment_code, name, purpose, owner, database_resource_type,
                                database_resource_ref, secret_store_namespace, service_identity,
                                ingress_policy, egress_policy, external_api_classification,
                                synthetic_data_only, destructive_actions_allowed, live_messaging_allowed,
                                live_payments_allowed, active_config_version, verification_status,
                                last_verified_at, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (eid, code, name, purp, own, db_t, db_r, s_ns, s_id, ing, eg, ext_c, synth, dest, msg, pay, ver, v_st))

                cursor.execute("SELECT COUNT(*) as count FROM config_settings_catalog WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_settings = [
                        ('cfg-001', 'org-matab-default', 'MATAB_ENV', 'Active runtime environment tier', 'SERVER_RUNTIME', 'string', 'Core Platform', 'all', 'global', 'ENV_OVER_DB', 1, json.dumps('development'), json.dumps({'allowed': ['development', 'staging', 'production', 'test']}), 0, 'critical', 'PLATFORM_ADMIN', json.dumps(['ApiServer', 'AuditLedger'])),
                        ('cfg-002', 'org-matab-default', 'MATAB_SECRET_KEY', 'Cryptographic signing key for sessions and tokens', 'SECRET_CREDENTIAL', 'secret_ref', 'Security / Auth', 'all', 'global', 'SECRET_STORE_ONLY', 1, json.dumps(None), json.dumps({'min_length': 32}), 0, 'critical', 'CISO', json.dumps(['SessionMiddleware', 'TokenVerifier'])),
                        ('cfg-003', 'org-matab-default', 'MATAB_PORT', 'HTTP API listen port', 'SERVER_RUNTIME', 'integer', 'Core Platform', 'all', 'global', 'ENV_OVER_DB', 1, json.dumps(8000), json.dumps({'min': 1024, 'max': 65535}), 0, 'low', 'PLATFORM_ADMIN', json.dumps(['HttpServer'])),
                        ('cfg-004', 'org-matab-default', 'MATAB_SESSION_HOURS', 'Maximum clinical session lifetime in hours', 'SECURITY_POLICY', 'integer', 'Security / Auth', 'all', 'global', 'DB_OVER_ENV', 1, json.dumps(12), json.dumps({'min': 1, 'max': 24}), 1, 'medium', 'PLATFORM_ADMIN', json.dumps(['AuthService'])),
                        ('cfg-005', 'org-matab-default', 'MATAB_ALLOWED_ORIGINS', 'CORS origin allowlist', 'SECURITY_POLICY', 'string', 'Security / Auth', 'all', 'global', 'ENV_OVER_DB', 1, json.dumps('http://localhost:3000,http://127.0.0.1:8000'), json.dumps({'disallow_wildcard_in_prod': True}), 0, 'high', 'PLATFORM_ADMIN', json.dumps(['CorsMiddleware'])),
                        ('cfg-006', 'org-matab-default', 'APP_CLIENT_NAME', 'Branding title for web UI workbench', 'PUBLIC_CLIENT', 'string', 'UI / Frontend', 'all', 'global', 'IMMUTABLE_FILE', 0, json.dumps('ZAYVORA MATAB OS'), json.dumps({}), 1, 'low', 'PLATFORM_ADMIN', json.dumps(['SpaFrontend'])),
                        ('cfg-007', 'org-matab-default', 'CLINICAL_SYSTEM_VERSION', 'Governed software build release version', 'PUBLIC_CLIENT', 'string', 'Release Engineering', 'all', 'global', 'IMMUTABLE_FILE', 1, json.dumps('2026.10-LTS'), json.dumps({}), 0, 'low', 'PLATFORM_ADMIN', json.dumps(['SpaFrontend', 'DiagnosticProbe']))
                    ]
                    for cid, oid, ckey, cdesc, ccat, dt, own, es, ts, prec, req, def_v, val_r, ref, rk, appr, cons in seed_settings:
                        conn.execute("""
                            INSERT OR REPLACE INTO config_settings_catalog (
                                id, organization_id, config_key, description, category,
                                data_type, owner_team, environment_scope, tenant_scope,
                                precedence_order, is_required, default_value_json,
                                validation_rules_json, is_runtime_refreshable, change_risk_level,
                                required_approver_role, consumers_json, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (cid, oid, ckey, cdesc, ccat, dt, own, es, ts, prec, req, def_v, val_r, ref, rk, appr, cons))

                cursor.execute("SELECT COUNT(*) as count FROM config_secret_references WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    seed_secrets = [
                        ('sec-001', 'org-matab-default', 'MATAB_SECRET_KEY_REF', 'SESSION_KEY', 'ENV_VARIABLE', 'env:MATAB_SECRET_KEY', 'production', 'Security / Auth', json.dumps(['SessionMiddleware']), 'v1', 'active'),
                        ('sec-002', 'org-matab-default', 'ABDM_BRIDGE_CLIENT_SECRET', 'ABDM_BRIDGE_CREDENTIAL', 'VAULT', 'vault://matab/prod/abdm-key', 'production', 'Interoperability Team', json.dumps(['AbdmGatewayClient']), 'v1', 'active'),
                        ('sec-003', 'org-matab-default', 'SMS_GATEWAY_API_KEY', 'NOTIFICATION_GATEWAY_CREDENTIAL', 'AWS_SECRETS_MANAGER', 'arn:aws:secretsmanager:ap-south-1:matab/sms', 'production', 'Operations Team', json.dumps(['NotificationService']), 'v1', 'active'),
                        ('sec-004', 'org-matab-default', 'PAYMENT_GATEWAY_SECRET', 'PAYMENT_GATEWAY_KEY', 'VAULT', 'vault://matab/prod/payment-key', 'production', 'Finance Team', json.dumps(['BillingGateway']), 'v1', 'active')
                    ]
                    for sid, oid, sname, styp, ptyp, pref, env, own, cons, ver, st in seed_secrets:
                        conn.execute("""
                            INSERT OR REPLACE INTO config_secret_references (
                                id, organization_id, secret_name, secret_type, provider_type,
                                provider_secret_ref, environment_code, owner_team,
                                authorized_consumers_json, key_version, status, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                        """, (sid, oid, sname, styp, ptyp, pref, env, own, cons, ver, st))

                # Sample change proposal
                cursor.execute("SELECT COUNT(*) as count FROM config_change_proposals WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    conn.execute("""
                        INSERT OR REPLACE INTO config_change_proposals (
                            id, organization_id, title, environment_code, requester_id,
                            change_category, diff_metadata_json, impact_assessment_json,
                            rollback_plan, status, created_at, updated_at
                        ) VALUES (
                            'ccp-seed-001', 'org-matab-default',
                            'Adjust Clinical Inactivity Timeout to 14 Hours for Extended Consultation Clinics',
                            'production', 'usr-hakeem-1', 'SECURITY_POLICY',
                            '{"key": "MATAB_SESSION_HOURS", "old_value": 12, "new_value": 14}',
                            '{"impact": "Low. Slightly extends JWT session lifetime for rural OPD camps."}',
                            'Revert MATAB_SESSION_HOURS to 12 via standard config update.',
                            'draft', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                # Seed baseline config audit entry
                cursor.execute("SELECT COUNT(*) as count FROM config_audit_ledger WHERE organization_id = 'org-matab-default';")
                if cursor.fetchone()["count"] == 0:
                    conn.execute("""
                        INSERT OR REPLACE INTO config_audit_ledger (
                            id, organization_id, action_type, actor_id, actor_role,
                            target_key_or_ref, environment_code, metadata_json, created_at
                        ) VALUES (
                            'aud-seed-001', 'org-matab-default', 'CONFIG_CREATED',
                            'SYSTEM_BOOTSTRAP', 'PLATFORM_ADMIN', 'MATAB_ENV', 'all',
                            '{"event": "system_bootstrap_baseline_seeding"}', CURRENT_TIMESTAMP
                        );
                    """)

                # -------------------------------------------------------------
                # Prompt 45: Enterprise Identity Governance, PAM & Certification
                # -------------------------------------------------------------
                cursor.execute("SELECT COUNT(*) as count FROM identity_privilege_registry;")
                if cursor.fetchone()["count"] == 0:
                    # 1. Privileged Operations Registry
                    privileges_data = [
                        ('priv-user-manage', 'users:manage', 'User & Identity Management', 'USER_ADMIN', 'CRITICAL', 0, 7200, 1, 'Create and manage user accounts and role assignments'),
                        ('priv-config-manage', 'config:manage', 'Runtime Configuration Management', 'SECURITY_CONFIG', 'CRITICAL', 0, 7200, 1, 'Modify server runtime and security settings'),
                        ('priv-secret-rotate', 'config:rotate_secret', 'Cryptographic Secret Rotation', 'SECURITY_CONFIG', 'CRITICAL', 0, 3600, 1, 'Initiate and advance secret rotation cycles'),
                        ('priv-dr-drill', 'dr:execute_drill', 'Disaster Recovery Restore Execution', 'INFRASTRUCTURE', 'HIGH', 0, 14400, 1, 'Run isolated database recovery exercises'),
                        ('priv-lifecycle-exec', 'lifecycle:execute', 'Data Lifecycle & Archival Execution', 'DATA_GOVERNANCE', 'HIGH', 0, 14400, 1, 'Execute legal hold, archival, or retention jobs'),
                        ('priv-rx-sign', 'prescriptions:sign', 'Clinical Prescription Digital Signing', 'CLINICAL_AUTHORITY', 'CRITICAL', 1, 0, 0, 'Clinically sign immutable prescription records (BUMS credential required)'),
                        ('priv-assess-final', 'assessment:finalise', 'Clinical Assessment Attestation', 'CLINICAL_AUTHORITY', 'CRITICAL', 1, 0, 0, 'Clinically attest Unani clinical encounters')
                    ]
                    for pid, pkey, pname, pcat, prisk, pclin, pmax, pdual, pdesc in privileges_data:
                        conn.execute("""
                            INSERT OR REPLACE INTO identity_privilege_registry (
                                id, privilege_key, name, category, risk_tier, is_clinical_authority,
                                max_elevation_seconds, requires_dual_approval, description
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (pid, pkey, pname, pcat, prisk, pclin, pmax, pdual, pdesc))

                    # 2. Separation of Duties Toxic Rules
                    sod_data = [
                        ('sod-001', 'SOD-001', 'billing:refund_void', 'audit:read', 'CRITICAL', 'Financial cashier operator cannot audit own invoice voids or cash ledger'),
                        ('sod-002', 'SOD-002', 'users:manage', 'access:certify', 'HIGH', 'Role administrator cannot certify their own role assignments'),
                        ('sod-003', 'SOD-003', 'prescriptions:sign', 'org:manage', 'CRITICAL', 'Administrative infrastructure manager cannot clinically sign medical prescriptions'),
                        ('sod-004', 'SOD-004', 'break_glass:actor', 'break_glass:reviewer', 'CRITICAL', 'Actor initiating emergency break-glass cannot conduct retrospective audit review'),
                        ('sod-005', 'SOD-005', 'jit:requester', 'jit:approver', 'CRITICAL', 'JIT elevation requester cannot self-approve their own elevation request')
                    ]
                    for sid, scode, s_a, s_b, srisk, srat in sod_data:
                        conn.execute("""
                            INSERT OR REPLACE INTO identity_sod_toxic_rules (
                                id, rule_code, role_or_perm_a, role_or_perm_b, risk_tier, rationale, is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, 1);
                        """, (sid, scode, s_a, s_b, srisk, srat))

                    # 3. Mirror Human Users into identity_principals
                    human_principals = [
                        ('idp-usr-admin-1', 'HUMAN', 'usr-admin-1', '[SYNTHETIC] Admin User', 'admin.synthetic@zayvora.test', 'org-matab-default', 'ACTIVE', 1),
                        ('idp-usr-hakeem-1', 'HUMAN', 'usr-hakeem-1', '[SYNTHETIC] Hakeem Tariq Ahmad', 'hakeem.synthetic@zayvora.test', 'org-matab-default', 'ACTIVE', 1),
                        ('idp-usr-recep-1', 'HUMAN', 'usr-recep-1', '[SYNTHETIC] Farhan Ali (Front Desk)', 'reception.synthetic@zayvora.test', 'org-matab-default', 'ACTIVE', 1),
                        ('idp-usr-pharm-1', 'HUMAN', 'usr-pharm-1', '[SYNTHETIC] Bilal Siddiqui (Pharmacist)', 'pharmacy.synthetic@zayvora.test', 'org-matab-default', 'ACTIVE', 1),
                        ('idp-usr-cashier-1', 'HUMAN', 'usr-cashier-1', '[SYNTHETIC] Nadeem Khan (Cashier)', 'cashier.synthetic@zayvora.test', 'org-matab-default', 'ACTIVE', 1),
                        ('idp-usr-inv-1', 'HUMAN', 'usr-inv-1', '[SYNTHETIC] Salman Mirza (Inventory Manager)', 'inventory.synthetic@zayvora.test', 'org-matab-default', 'ACTIVE', 1),
                        ('idp-usr-auditor-1', 'HUMAN', 'usr-auditor-1', '[SYNTHETIC] Compliance Auditor', 'auditor.synthetic@zayvora.test', 'org-matab-default', 'ACTIVE', 1)
                    ]
                    for ip_id, p_type, u_id, p_name, p_email, org_id, a_state, is_inter in human_principals:
                        conn.execute("""
                            INSERT OR REPLACE INTO identity_principals (
                                id, principal_type, user_id, name, email, organization_id,
                                account_state, environment, is_interactive_allowed, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'production', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (ip_id, p_type, u_id, p_name, p_email, org_id, a_state, is_inter))

                    # 4. Service Accounts & Machine Identities
                    service_accounts_data = [
                        ('sa-backup-worker', 'svc-backup-worker', 'Database Streaming Backup Daemon', 'usr-admin-1', 'production', 'WORKLOAD_IDENTITY', 'ref-vault-db-backup', '["db_snapshot", "wal_archive"]', '["database_backup"]'),
                        ('sa-audit-sync', 'svc-audit-sync', 'Tamper-Evident Ledger Immutability Sync', 'usr-admin-1', 'production', 'API_KEY', 'ref-vault-audit-sync', '["audit_digest_export"]', '["tamper_evident_sync"]')
                    ]
                    for sa_id, skey, sname, sowner, senv, sctype, scref, swl, sdeps in service_accounts_data:
                        conn.execute("""
                            INSERT OR REPLACE INTO identity_service_accounts (
                                id, service_key, name, owner_user_id, environment,
                                credential_type, credential_ref, permitted_workloads_json,
                                is_interactive_allowed, status, dependency_checklist_json,
                                created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'ACTIVE', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (sa_id, skey, sname, sowner, senv, sctype, scref, swl, sdeps))

                        conn.execute("""
                            INSERT OR REPLACE INTO identity_principals (
                                id, principal_type, name, organization_id, account_state,
                                owner_user_id, environment, is_interactive_allowed, created_at, updated_at
                            ) VALUES (?, 'SERVICE_ACCOUNT', ?, 'org-matab-default', 'ACTIVE', ?, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                        """, (f"idp-{skey}", sname, sowner, senv))

                    # 5. Access Certification Campaign
                    conn.execute("""
                        INSERT OR REPLACE INTO identity_certification_campaigns (
                            id, campaign_code, title, target_scope, due_date,
                            snapshot_timestamp, owner_user_id, status, total_items_count,
                            reviewed_items_count, retained_count, revoked_count, created_at
                        ) VALUES (
                            'camp-seed-001', 'CAMP-2026-Q4-CLINICAL', 'Q4 2026 Clinical & Administrative Recertification',
                            'CLINICAL_ROLES', '2026-12-31', CURRENT_TIMESTAMP, 'usr-admin-1', 'ACTIVE', 2, 0, 0, 0, CURRENT_TIMESTAMP
                        );
                    """)

                    # 6. Baseline Audit Ledger Record
                    conn.execute("""
                        INSERT OR REPLACE INTO identity_audit_ledger (
                            id, event_type, principal_id, actor_id, actor_name,
                            action_details, target_resource, result_status, metadata_json, created_at
                        ) VALUES (
                            'aud-id-seed-001', 'SYSTEM_INITIALIZED', 'GLOBAL', 'usr-admin-1', 'Admin User',
                            'Enterprise identity governance engine initialized with baseline catalog',
                            'GLOBAL', 'SUCCESS', '{"event": "system_bootstrap"}', CURRENT_TIMESTAMP
                        );
                    """)

                    # Prompt 46: Security Posture, Vulnerability Governance & Control Verification
                    # 1. Assets Inventory
                    sec_assets = [
                        ('asset-app-src', 'ZAYVORA Clinical Backend & Frontend Source', 'APPLICATION_SOURCE', 'PRODUCTION', 'AppSec Lead', 'INTERNAL', 'REST Endpoints, CLI scripts, Web console', 'Core Unani Clinical OS Engine & Web Console', 'COVERED', 'EVID-SRC-001'),
                        ('asset-deps-py', 'Python Dependency Manifest & Standard Libraries', 'DEPENDENCIES', 'PRODUCTION', 'DevSecOps Engineer', 'INTERNAL', 'pyproject.toml, virtualenv runtime', 'Runtime Libraries & Cryptographic Primitives', 'COVERED', 'EVID-DEP-001'),
                        ('asset-secrets', 'Credential References & Secret Manager Pointers', 'SECRETS', 'PRODUCTION', 'Security Platform Architect', 'CONFIDENTIAL_SECURITY', 'Vault & Secret Manager metadata pointers', 'Key Vault & Token Signing Keys', 'COVERED', 'EVID-SEC-001'),
                        ('asset-apis', 'Protected REST API Routing & Handlers', 'APIS', 'PRODUCTION', 'API Security Lead', 'RESTRICTED_PHI', 'HTTP /api/v1/ routes with require_permission', 'Clinical CRUD, Prescription Signing & Consultation Orchestrator', 'COVERED', 'EVID-API-001'),
                        ('asset-container', 'Container Image & Hardened Runtime', 'CONTAINERS', 'PRODUCTION', 'Platform SRE', 'INTERNAL', 'infra/Dockerfile with user matab', 'Hardened Container Execution with Non-root User', 'COVERED', 'EVID-CNT-001'),
                        ('asset-database', 'Relational SQLite/PostgreSQL Database Engine', 'DATABASE', 'PRODUCTION', 'Data Governance Lead', 'RESTRICTED_PHI', 'Parameterized SQL queries and migrations', 'Longitudinal Health Records & Audit Ledgers', 'COVERED', 'EVID-DB-001')
                    ]
                    for a_id, aname, acat, aenv, aowner, asens, aentry, acrit, acov, alast in sec_assets:
                        conn.execute("""
                            INSERT OR REPLACE INTO security_assets_inventory (
                                id, asset_name, asset_category, environment, owner_role,
                                data_sensitivity, entry_points_summary, critical_clinical_function,
                                scan_coverage_status, last_scanned_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                        """, (a_id, aname, acat, aenv, aowner, asens, aentry, acrit, acov))

                    # 2. Controls Registry
                    sec_controls = [
                        ('ctrl-sca-001', 'SEC-SCA-001', 'Dependency & SCA Vulnerability Verification', 'Known CVE vulnerabilities in direct and transitive packages', 'DEPENDENCIES', 'package-advisory-scanner', '1.0.0', 'CI_GATE', 'PASSED', 'AppSec Lead', 'BLOCKING_HARD', 'Requires approved advisory database', 'EVID-SCA-BOOTSTRAP'),
                        ('ctrl-sec-001', 'SEC-SECRET-001', 'Repository & Configuration Secret Leak Detection', 'Plaintext API keys, JWT signing keys, and passwords committed', 'SECRETS', 'credential-entropy-scanner', '1.0.0', 'CI_GATE', 'PASSED', 'SecOps Lead', 'BLOCKING_HARD', 'Scans active repository files and configs', 'EVID-SEC-BOOTSTRAP'),
                        ('ctrl-authz-001', 'SEC-AUTHZ-001', 'API Endpoint Authorization & Security Headers Verification', 'Bypassed authentication, missing permissions, or missing security headers', 'APIS', 'endpoint-authz-auditor', '1.0.0', 'CI_GATE', 'PASSED', 'API Security Lead', 'BLOCKING_HARD', 'Scans all mounted routes and response headers', 'EVID-AUTHZ-BOOTSTRAP'),
                        ('ctrl-cont-001', 'SEC-CONT-001', 'Container Image & Non-Root Execution Verification', 'Privileged container execution or unpinned base images', 'CONTAINERS', 'dockerfile-security-linter', '1.0.0', 'PRE_RELEASE', 'PASSED', 'Platform SRE', 'BLOCKING_HARD', 'Evaluates infra/Dockerfile against CIS benchmarks', 'EVID-CONT-BOOTSTRAP'),
                        ('ctrl-sqli-001', 'SEC-SQLI-001', 'SQL Parameterization & Injection Safety Verification', 'SQL injection via unparameterized string formatting', 'DATABASE', 'ast-sql-parameter-verifier', '1.0.0', 'CI_GATE', 'PASSED', 'Data Governance Lead', 'BLOCKING_HARD', 'Verifies parameterized ? queries in all domain handlers', 'EVID-SQLI-BOOTSTRAP')
                    ]
                    for c_id, c_code, c_title, c_risk, c_target, c_tool, c_ver, c_cad, c_stat, c_owner, c_gate, c_lim, c_evid in sec_controls:
                        conn.execute("""
                            INSERT OR REPLACE INTO security_controls_registry (
                                id, control_code, title, risk_addressed, target_asset_category,
                                tool_or_method, tool_version, execution_cadence, status,
                                accountable_owner_role, release_gate_level, limitations_and_exclusions,
                                last_executed_at, last_evidence_ref
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?);
                        """, (c_id, c_code, c_title, c_risk, c_target, c_tool, c_ver, c_cad, c_stat, c_owner, c_gate, c_lim, c_evid))

                    # 3. Sample Baseline Finding
                    conn.execute("""
                        INSERT OR REPLACE INTO security_vulnerability_findings (
                            id, finding_code, title, asset_id, affected_component,
                            vulnerability_category, source_severity, organizational_priority,
                            cve_reference, exposure_context, clinical_impact, evidence_summary,
                            status, owner_id, remediation_plan, created_at, updated_at
                        ) VALUES (
                            'vuln-seed-001', 'VULN-2026-001', 'Missing Content-Security-Policy Strict Nonce Directive',
                            'asset-apis', 'apps/web/index.html', 'MISSING_SECURITY_HEADER',
                            'LOW', 'P3_LOW', 'CWE-1021', 'INTERNET_FACING', 'NO_CLINICAL_IMPACT',
                            'HTTP headers response contains nosniff and DENY, but lacks script-src nonce directive.',
                            'TRIAGED', 'usr-admin-1', 'Implement nonce-based script injection policy in production gateway.',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                    # 4. Baseline Security Exception
                    conn.execute("""
                        INSERT OR REPLACE INTO security_exceptions_ledger (
                            id, finding_id, control_id, scope, rationale,
                            compensating_controls, accountable_risk_owner, approved_by,
                            approved_at, expires_at, status, review_notes, created_at
                        ) VALUES (
                            'exc-seed-001', 'vuln-seed-001', 'ctrl-authz-001', 'apps/web/index.html',
                            'Static HTML console operates without external script dependencies; CSP header added at reverse proxy.',
                            'Reverse proxy enforces strict Content-Security-Policy headers; client scripts run in isolated origin.',
                            'Chief Information Security Officer', 'usr-admin-1',
                            CURRENT_TIMESTAMP, '2026-12-31T23:59:59', 'APPROVED',
                            'Authorized for Q4 2026 operational release.', CURRENT_TIMESTAMP
                        );
                    """)

                    # 5. Baseline Security Audit Record
                    conn.execute("""
                        INSERT OR REPLACE INTO security_audit_ledger (
                            id, event_type, severity, actor_id, target_type, target_id,
                            action_details_json, previous_hash, entry_hash, occurred_at
                        ) VALUES (
                            'aud-sec-seed-001', 'SYSTEM_INITIALIZED', 'INFO', 'usr-admin-1',
                            'ENGINE', 'security_posture_engine',
                            '{"message": "Enterprise Security Posture & Vulnerability Governance Engine bootstrapped with baseline controls and assets."}',
                            'GENESIS_BLOCK', 'c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2',
                            CURRENT_TIMESTAMP
                        );
                    """)

                    # --- PROMPT 47: THREAT MODELING, ABUSE CASES & SECURE SDLC SEED ---
                    # 1. Baseline Threat Model: Clinical Decision Support & Prescriptions
                    conn.execute("""
                        INSERT OR REPLACE INTO threat_models_registry (
                            id, model_code, title, subsystem_scope, repository_revision,
                            deployment_version, owner_role, security_reviewer_id, clinical_reviewer_id,
                            privacy_reviewer_id, lifecycle_state, assumptions_json, exclusions_json,
                            dependencies_json, is_stale, last_reviewed_at, next_review_due_at,
                            created_at, updated_at
                        ) VALUES (
                            'tm-cds-001', 'TM-CLINICAL-CDS-001',
                            'Clinical Decision Support, Safety Firewalls & Prescription Signing Architecture',
                            'CLINICAL_CDS_AND_PRESCRIPTIONS', 'HEAD', 'v1.0.0',
                            'Principal Security Architect', 'usr-admin-1', 'usr-hakeem-1', 'usr-admin-1',
                            'approved_for_scope',
                            '["Server-side PIN verification active", "Deterministic safety rules loaded", "Multi-tenant facility boundaries active"]',
                            '["Third-party external LLM inference", "Public unauthenticated CDS access"]',
                            '["prescriptions", "cds_runs", "clinical_signoffs", "safety_firewalls"]',
                            0, CURRENT_TIMESTAMP, '2027-01-14T00:00:00',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                    # 2. Baseline Trust Boundary
                    conn.execute("""
                        INSERT OR REPLACE INTO threat_trust_boundaries (
                            id, model_id, boundary_name, source_actor_or_component,
                            destination_component, data_classification, protocol_or_interface,
                            auth_mechanism, encryption_status, evidence_status, notes, created_at
                        ) VALUES (
                            'tb-cds-001', 'tm-cds-001',
                            'AI/CDS Orchestrator <-> Clinician Review & Attestation',
                            'CDS Orchestrator Engine', 'Clinician Attestation Workflow',
                            'TIER_2_PHI', 'IN_PROCESS_API', 'SESSION_PIN_HASH',
                            'MEMORY_SAFE', 'verified_in_code',
                            'Enforces zero autonomous AI signing. PIN verification required for finalization.',
                            CURRENT_TIMESTAMP
                        );
                    """)

                    # 3. Baseline Abuse Case
                    conn.execute("""
                        INSERT OR REPLACE INTO threat_abuse_cases (
                            id, model_id, threat_code, title, methodology, threat_class,
                            actor_type, target_asset, trust_boundary_id, attack_path_summary,
                            clinical_safety_hazard, severity, lifecycle_status,
                            accountable_owner_role, mitigation_due_date, created_at, updated_at
                        ) VALUES (
                            'tac-cds-001', 'tm-cds-001', 'TAC-CDS-001',
                            'Administrative Bypass of Clinician PIN on Prescription Signing',
                            'STRIDE_PLUS_CLINICAL_HAZARD', 'CLINICAL_HAZARD',
                            'MALICIOUS_INSIDER', 'prescriptions', 'tb-cds-001',
                            'Attacker attempts to forge or bypass clinician PIN to sign medical orders using administrative Bearer token.',
                            'DIRECT_HARM_PRESCRIBING_ERROR', 'CRITICAL', 'verified_mitigated',
                            'Clinical Safety Officer', '2026-12-31T23:59:59',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                    # 4. Baseline Testable Control
                    conn.execute("""
                        INSERT OR REPLACE INTO threat_testable_controls (
                            id, threat_id, control_code, title, control_type,
                            enforcement_code_path, test_suite_reference,
                            verification_status, last_verified_at, created_at
                        ) VALUES (
                            'ttc-cds-001', 'tac-cds-001', 'CTL-CDS-001',
                            'Server-Enforced Clinician PIN & License Attestation', 'PREVENTIVE',
                            'apps.api.domains.cds_orchestrator.CDSOrchestratorEngine.sign_encounter',
                            'tests.unit.test_cds_orchestrator.TestCDSOrchestrator.test_admin_cannot_sign_prescription',
                            'VERIFIED_IN_TEST', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                    # 5. Baseline SDLC Change Review
                    conn.execute("""
                        INSERT OR REPLACE INTO sdlc_change_reviews (
                            id, change_id, title, repository_revision, target_subsystem,
                            threat_model_id, change_classification, security_review_status,
                            clinical_review_status, privacy_review_status, gate_verdict,
                            blocking_reasons_json, evaluated_at, created_at
                        ) VALUES (
                            'sdlc-cr-001', 'PR-1048',
                            'Enhance CDS Schedule E(1) Dosage Calculation Check',
                            'HEAD', 'CLINICAL_CDS_AND_PRESCRIPTIONS', 'tm-cds-001',
                            'HIGH_IMPACT_CLINICAL', 'APPROVED', 'APPROVED', 'NOT_REQUIRED',
                            'PASS', '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        );
                    """)

                    # 6. Baseline Threat SDLC Audit Record
                    conn.execute("""
                        INSERT OR REPLACE INTO threat_sdlc_audit_ledger (
                            id, event_type, severity, actor_id, target_type, target_id,
                            action_details_json, previous_hash, entry_hash, occurred_at
                        ) VALUES (
                            'aud-tm-seed-001', 'SYSTEM_INITIALIZED', 'INFO', 'usr-admin-1',
                            'ENGINE', 'threat_modeling_sdlc_service',
                            '{"message": "Enterprise Threat Modeling, Abuse-Case Analysis & Secure SDLC Engine bootstrapped with baseline models and controls."}',
                            'GENESIS_BLOCK_THREAT_SDLC_P47', 'd4f9b876a321e09876543210fedcba9876543210abcdef0123456789abcdef01',
                            CURRENT_TIMESTAMP
                        );
                    """)

            # Prompt 48: Clinical Safety Case, Hazard Analysis & Verification Engine Seeding
            cur_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clinical_intended_use_registry';")
            if cur_check.fetchone():
                # 1. Baseline Intended Use
                conn.execute("""
                    INSERT OR REPLACE INTO clinical_intended_use_registry (
                        id, scope_code, title, intended_users_json, clinical_purposes_json,
                        excluded_uses_json, clinician_authority_level, version, effective_date,
                        clinical_approver_id, status, created_at, updated_at
                    ) VALUES (
                        'iu-rx-001', 'IU-PRESCRIPTION-SIGNING',
                        'Unani Prescription Posology, Contraindication Preflight & Digital Signing Workflow',
                        '["Licensed Tabib", "Clinical Hakeem", "Supervising Practitioner"]',
                        '["Outpatient Unani prescription authoring", "Dosage ceiling preflight check", "Mudabbar purification validation", "Herb-drug interaction checking"]',
                        '["Autonomous diagnostic or prescribing algorithms", "Emergency life support triage", "Unsupervised patient self-medication"]',
                        'EXCLUSIVE_HUMAN_SIGN_OFF', '1.0.0', date('now'),
                        'usr-hakeem-1', 'APPROVED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 2. Baseline Hazard Register
                conn.execute("""
                    INSERT OR REPLACE INTO clinical_hazard_register (
                        id, hazard_code, intended_use_id, title, workflow_scope,
                        initiating_cause, hazardous_state, clinical_consequence,
                        affected_population, severity_tier, lifecycle_status,
                        clinical_safety_lead_id, technical_lead_id, review_due_date,
                        created_at, updated_at
                    ) VALUES (
                        'haz-rx-001', 'HAZ-RX-001', 'iu-rx-001',
                        'Exceeding Maximum Pharmacopoeial Dosage in Unani Prescription Formulation',
                        'PRESCRIPTION_SIGNING',
                        'Practitioner posology typo or unmonitored compound escalation beyond NFUM/UPI posology ceiling',
                        'Dispensing toxic botanical or classical compound with unsafe single or cumulative daily dose',
                        'Acute toxicity, neurotoxicity, renal/hepatic injury, or emergency hospitalization',
                        'GENERAL_OPD', 'CRITICAL', 'accepted_for_defined_scope',
                        'usr-hakeem-1', 'usr-admin-1', date('now', '+180 days'),
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 3. Baseline Safety Requirement
                conn.execute("""
                    INSERT OR REPLACE INTO safety_requirements_catalog (
                        id, hazard_id, req_code, title, requirement_type,
                        specification_statement, enforcement_code_path, test_suite_reference,
                        verification_status, last_verified_at, created_at
                    ) VALUES (
                        'sr-rx-001', 'haz-rx-001', 'SR-RX-001',
                        'Deterministic Maximum Daily Dosage Ceiling Enforcement',
                        'PREVENTIVE',
                        'The prescription preflight validator MUST deterministically reject any formulation item where the calculated single or 24-hour cumulative dose exceeds the NFUM pharmacopoeial maximum.',
                        'apps.api.domains.prescriptions.PrescriptionEngine._validate_posology',
                        'tests.unit.test_prescriptions.TestPrescriptionPreflight.test_exceeded_maximum_dosage_rejected',
                        'VERIFIED_IN_TEST', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 4. Baseline Safety Control Verification
                conn.execute("""
                    INSERT OR REPLACE INTO safety_control_verifications (
                        id, requirement_id, test_run_timestamp, test_suite_name,
                        environment, execution_duration_ms, status, evidence_summary,
                        verified_by_actor_id, created_at
                    ) VALUES (
                        'scv-rx-001', 'sr-rx-001', CURRENT_TIMESTAMP,
                        'tests.unit.test_prescriptions.TestPrescriptionPreflight.test_exceeded_maximum_dosage_rejected',
                        'ISOLATED_SYNTHETIC', 42, 'PASS',
                        'Verified deterministic rejection with ValidationError when single dose exceeds UPI ceiling.',
                        'usr-hakeem-1', CURRENT_TIMESTAMP
                    );
                """)

                # 5. Baseline Clinical Safety Case
                conn.execute("""
                    INSERT OR REPLACE INTO clinical_safety_cases (
                        id, case_code, title, workflow_scope, target_release_version,
                        claim_statement, context_and_assumptions, argument_narrative,
                        residual_risks_summary, exclusions_and_limitations,
                        clinical_safety_officer_id, approval_status, approved_at,
                        expires_at, created_at, updated_at
                    ) VALUES (
                        'csc-rx-001', 'CSC-PRESCRIPTION-V1',
                        'Clinical Safety Case for Unani Prescription Engine & Posology Governance',
                        'PRESCRIPTION_SIGNING', 'v1.0.0',
                        'The Unani Prescription Engine safely prevents toxic overdose, unpurified Schedule E(1) dispensing, and unauthenticated signing through deterministic fail-closed preflights.',
                        'Assumes licensed practitioner operates workstation and authenticates with secret PIN attestation.',
                        'Claim G1: All posology rules execute deterministically. Claim G2: Hard-stop contraindications cannot be bypassed. Claim G3: Attributable human authority required.',
                        'Residual risk of unlisted external polypharmacy mitigated by pre-consultation drug history reconciliation dialog.',
                        'Strictly excluded from autonomous dispensing, automated IV compounding, and unverified OTC sales.',
                        'usr-hakeem-1', 'APPROVED_FOR_SCOPE', CURRENT_TIMESTAMP,
                        date('now', '+180 days'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 6. Baseline Clinical Safety Incident / Near Miss
                conn.execute("""
                    INSERT OR REPLACE INTO clinical_safety_incidents (
                        id, incident_code, incident_type, workflow_scope, severity,
                        sanitized_description, linked_hazard_id, containment_action,
                        corrective_action_plan, corrective_action_status, reported_by_actor_id,
                        closed_at, created_at, updated_at
                    ) VALUES (
                        'csi-seed-001', 'INC-2026-001', 'NEAR_MISS', 'PRESCRIPTION_SIGNING', 'MEDIUM',
                        'Practitioner noticed a posology soft-warning did not trigger during draft autosave, though preflight hard stop prevented signing.',
                        'haz-rx-001', 'Preflight validation at signing blocked dispensing successfully.',
                        'Added draft validation preview endpoint and unit regression test.',
                        'VERIFIED_CLOSED', 'usr-hakeem-1', CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 7. Baseline Safety Release Gate Evaluation
                conn.execute("""
                    INSERT OR REPLACE INTO safety_release_gate_evaluations (
                        id, evaluation_code, target_release_version, workflow_scope,
                        safety_case_id, gate_verdict, evaluated_controls_count,
                        passed_controls_count, blocking_reasons_json, evaluated_by_actor_id,
                        evaluated_at, created_at
                    ) VALUES (
                        'srg-seed-001', 'SRG-2026-001', 'v1.0.0', 'PRESCRIPTION_SIGNING',
                        'csc-rx-001', 'PASS', 1, 1, '[]', 'usr-hakeem-1',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 8. Baseline Clinical Safety Audit Record
                conn.execute("""
                    INSERT OR REPLACE INTO clinical_safety_audit_ledger (
                        id, event_type, severity, actor_id, target_type, target_id,
                        action_details_json, previous_hash, entry_hash, occurred_at
                    ) VALUES (
                        'aud-cs-seed-001', 'SAFETY_SYSTEM_INITIALIZED', 'INFO', 'usr-hakeem-1',
                        'ENGINE', 'clinical_safety_case_service',
                        '{"message": "Enterprise Clinical Safety Case, Hazard Analysis & Verification Engine initialized with baseline GSN safety case and controls."}',
                        'GENESIS_BLOCK_CLINICAL_SAFETY_P48',
                        'e5a8c901f432b10987654321fedcba0987654321abcdef1234567890abcdef02',
                        CURRENT_TIMESTAMP
                    );
                """)


            # Prompt 49: Test Automation, Regression Testing & Release Qualification Engine Seeding
            cur_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_automation_suites_catalog';")
            if cur_check.fetchone():
                # 1. Baseline Test Suites Catalog
                conn.execute("""
                    INSERT OR REPLACE INTO test_automation_suites_catalog (
                        id, suite_code, name, test_layer, target_subsystem,
                        test_file_path, command_template, execution_environment,
                        is_mandatory_for_release, timeout_seconds, status,
                        created_at, updated_at
                    ) VALUES (
                        'tasc-unit-rx-001', 'SUITE-UNIT-PRESCRIPTIONS',
                        'Unit Test Suite - Unani Prescriptions & Posology Engine',
                        'UNIT', 'CLINICAL_PRESCRIPTIONS',
                        'tests/unit/test_prescriptions.py',
                        'python -m unittest tests/unit/test_prescriptions.py',
                        'ISOLATED_SYNTHETIC', 1, 60, 'ACTIVE',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)
                conn.execute("""
                    INSERT OR REPLACE INTO test_automation_suites_catalog (
                        id, suite_code, name, test_layer, target_subsystem,
                        test_file_path, command_template, execution_environment,
                        is_mandatory_for_release, timeout_seconds, status,
                        created_at, updated_at
                    ) VALUES (
                        'tasc-e2e-smoke-001', 'SUITE-E2E-SMOKE-RELEASE-QUALIFICATION',
                        'E2E Smoke Release Qualification Journey',
                        'E2E_WORKFLOW', 'RELEASE_QUALIFICATION',
                        'tests/e2e/test_smoke_release_qualification_e2e.py',
                        'python -m unittest tests/e2e/test_smoke_release_qualification_e2e.py',
                        'ISOLATED_SYNTHETIC', 1, 120, 'ACTIVE',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 2. Baseline Test Execution Run
                conn.execute("""
                    INSERT OR REPLACE INTO test_execution_runs (
                        id, run_code, suite_id, target_release_version, environment,
                        commit_hash, trigger_source, status, total_tests,
                        passed_tests, failed_tests, skipped_tests,
                        execution_duration_ms, evidence_summary_json,
                        executed_by_actor_id, started_at, completed_at, created_at
                    ) VALUES (
                        'ter-seed-001', 'RUN-20261014-001', 'tasc-unit-rx-001',
                        'v1.0.0', 'ISOLATED_SYNTHETIC', 'HEAD', 'CI_PIPELINE',
                        'PASSED', 18, 18, 0, 0, 1250,
                        '{"details": "All posology ceiling, mudabbar detoxification, and digital signing tests passed cleanly."}',
                        'usr-admin-1', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 3. Baseline Flakiness & Quarantine Register
                conn.execute("""
                    INSERT OR REPLACE INTO test_flakiness_and_quarantine_register (
                        id, quarantine_code, suite_id, test_name, reason,
                        root_cause_category, quarantined_by_actor_id, assigned_owner,
                        status, quarantined_at, target_resolution_date, resolved_at,
                        created_at, updated_at
                    ) VALUES (
                        'tfqr-seed-001', 'QRN-202610-001', 'tasc-unit-rx-001',
                        'test_external_sms_network_latency_retry',
                        'Flaky network latency simulation causes timeout intermittently in local dev.',
                        'TIMING_RACE', 'usr-admin-1', 'qa-lead@zayvora.internal',
                        'ACTIVE_QUARANTINE', CURRENT_TIMESTAMP, date('now', '+14 days'), NULL,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 4. Baseline Release Qualification Profiles
                profiles_seed = [
                    (
                        'rqp-prof-dev-001', 'PROF-DEV', 'Development Release Profile', 'DEVELOPMENT',
                        '["UNIT"]', '["SUITE-UNIT-PRESCRIPTIONS"]',
                        9000, 1, 2
                    ),
                    (
                        'rqp-prof-staging-001', 'PROF-STAGING', 'Staging Pilot Release Profile', 'STAGING_PILOT',
                        '["UNIT", "E2E_WORKFLOW"]',
                        '["SUITE-UNIT-PRESCRIPTIONS", "SUITE-E2E-SMOKE-RELEASE-QUALIFICATION"]',
                        9800, 1, 0
                    ),
                    (
                        'rqp-prof-prod-001', 'PROF-PROD', 'Production Regulated Release Profile', 'PRODUCTION_REGULATED',
                        '["UNIT", "E2E_WORKFLOW"]',
                        '["SUITE-UNIT-PRESCRIPTIONS", "SUITE-E2E-SMOKE-RELEASE-QUALIFICATION"]',
                        10000, 0, 0
                    )
                ]
                for p_id, p_code, p_name, p_tier, req_layers, req_suites, min_pr, allow_q, max_cd in profiles_seed:
                    conn.execute("""
                        INSERT OR REPLACE INTO release_qualification_profiles (
                            id, profile_code, name, target_tier, required_test_layers_json,
                            required_suites_json, min_pass_rate_bp, allow_quarantined_tests,
                            max_critical_defects, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
                    """, (p_id, p_code, p_name, p_tier, req_layers, req_suites, min_pr, allow_q, max_cd))

                # 5. Baseline Release Candidate Qualification
                conn.execute("""
                    INSERT OR REPLACE INTO release_candidate_qualifications (
                        id, candidate_code, target_release_version, profile_id,
                        commit_hash, repository_revision, overall_verdict,
                        evaluated_suites_count, passed_suites_count, total_tests_executed,
                        total_tests_passed, open_defects_count, blocking_reasons_json,
                        qualification_summary_json, qualified_by_actor_id, evaluated_at,
                        expires_at, created_at
                    ) VALUES (
                        'rcq-seed-001', 'RC-QUAL-202610-001', 'v1.0.0', 'rqp-prof-prod-001',
                        'HEAD', 'main-sha256-verified', 'QUALIFIED',
                        2, 2, 18, 18, 0, '[]',
                        '{"verdict": "QUALIFIED", "notes": "Production release profile requirements satisfied with 100% test pass rate and 0 open defects."}',
                        'usr-admin-1', CURRENT_TIMESTAMP, date('now', '+3 days'), CURRENT_TIMESTAMP
                    );
                """)

                # 6. Baseline Test Automation Defect Register
                conn.execute("""
                    INSERT OR REPLACE INTO test_automation_defect_register (
                        id, defect_code, title, test_run_id, test_name, severity,
                        failure_classification, sanitized_stack_trace, reproduction_steps,
                        status, linked_hazard_id, assigned_owner, created_at, updated_at
                    ) VALUES (
                        'tadr-seed-001', 'DEF-202610-001',
                        'Draft autosave posology soft-warning toast rendered in red instead of amber',
                        'ter-seed-001', 'test_prescription_draft_warning_toast_color', 'MINOR',
                        'TEST_DEFECT', 'AssertionError: ''text-red-500'' != ''text-amber-500''',
                        '1. Open prescription draft. 2. Enter soft warning dosage. 3. Verify CSS class.',
                        'VERIFIED_CLOSED', 'haz-rx-001', 'ui-team@zayvora.internal',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    );
                """)

                # 7. Baseline Test Qualification Audit Ledger
                conn.execute("""
                    INSERT OR REPLACE INTO test_qualification_audit_ledger (
                        id, event_type, severity, actor_id, target_type, target_id,
                        action_details_json, previous_hash, entry_hash, occurred_at
                    ) VALUES (
                        'aud-tq-seed-001', 'TEST_SYSTEM_INITIALIZED', 'INFO', 'usr-admin-1',
                        'ENGINE', 'test_automation_release_qualification_service',
                        '{"message": "Enterprise Test Automation, Regression & Release Qualification Engine initialized with baseline profiles, catalog, and evidence ledger."}',
                        'GENESIS_BLOCK_TEST_QUALIFICATION_P49',
                        'd8e3b21c45a67890f1234567890abcdef1234567890abcdef1234567890abcdef01',
                        CURRENT_TIMESTAMP
                    );
                """)


        conn.execute("PRAGMA foreign_keys = ON;")

        conn.commit()
        print("[SEED] Successfully seeded synthetic development dataset.")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_development_data()


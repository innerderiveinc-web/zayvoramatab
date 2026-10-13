"""HTTP Request Router with Request ID Correlation and Middleware Dispatch."""

import re
import json
import uuid
import sqlite3
from typing import Dict, Any, Tuple, Optional
from apps.api.core.errors import AppError, NotFoundError, AuthenticationError
from apps.api.core.security import validate_session
from apps.api.database.connection import get_db
from apps.api.routes import (
    health, auth, tenancy, admin, audit, capabilities, patients, encounters,
    formulations, prescriptions, unani_assessment, organ_axis, care_plans,
    modern_assessment, clinical_rules, knowledge, safety_firewall,
    consultation_orchestrator, care_continuity, clinic_operations
)


ROUTES = [
    # Observability & Liveness
    ("GET", r"^/api/v1/health/live$", health.handle_health_live, False),
    ("GET", r"^/api/v1/health/ready$", health.handle_health_ready, False),
    
    # Authentication & Session
    ("POST", r"^/api/v1/auth/login$", auth.handle_auth_login, False),
    ("POST", r"^/api/v1/auth/logout$", auth.handle_auth_logout, True),
    ("GET", r"^/api/v1/auth/me$", auth.handle_auth_me, True),
    ("POST", r"^/api/v1/auth/password-reset$", auth.handle_password_reset_request, False),
    
    # Tenancy & Facilities
    ("GET", r"^/api/v1/organizations$", tenancy.handle_organizations_list, True),
    ("GET", r"^/api/v1/facilities$", tenancy.handle_facilities_list, True),
    ("POST", r"^/api/v1/facilities$", tenancy.handle_facilities_create, True),
    ("GET", r"^/api/v1/facilities/(?P<id>[^/]+)$", tenancy.handle_facility_get, True),
    
    # Administration (Users, Roles, Permissions)
    ("GET", r"^/api/v1/users$", admin.handle_users_list, True),
    ("POST", r"^/api/v1/users$", admin.handle_users_create, True),
    ("GET", r"^/api/v1/roles$", admin.handle_roles_list, True),
    ("GET", r"^/api/v1/permissions$", admin.handle_permissions_list, True),
    
    # Audit & Governance
    ("GET", r"^/api/v1/audit$", audit.handle_audit_list, True),
    ("GET", r"^/api/v1/system/capabilities$", capabilities.handle_capabilities_list, True),

    # Patients Domain (Master Patient Index, Identifiers, Consents, Duplicates, Timeline)
    ("POST", r"^/api/v1/patients$", patients.handle_patients_create, True),
    ("GET", r"^/api/v1/patients$", patients.handle_patients_search, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)$", patients.handle_patient_get_360, True),
    ("PATCH", r"^/api/v1/patients/(?P<id>[^/]+)$", patients.handle_patient_update_demographics, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/identifiers$", patients.handle_patient_identifiers_list, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/identifiers$", patients.handle_patient_identifier_add, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/identifiers/(?P<identifier_id>[^/]+)/retire$", patients.handle_patient_identifier_retire, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/consents$", patients.handle_patient_consents_list, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/consents$", patients.handle_patient_consent_record, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/consents/(?P<consent_id>[^/]+)/withdraw$", patients.handle_patient_consent_withdraw, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/duplicate-candidates$", patients.handle_patient_duplicate_candidates_get, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/duplicate-resolutions/(?P<candidate_id>[^/]+)$", patients.handle_patient_duplicate_resolution, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/timeline$", patients.handle_patient_timeline, True),
    ("POST", r"^/api/v1/patients/(?P<id>[^/]+)/encounters$", encounters.handle_encounter_create_for_patient, True),

    # Encounters Domain (Lifecycle, Transitions)
    ("GET", r"^/api/v1/encounters/(?P<id>[^/]+)$", encounters.handle_encounter_get, True),
    ("PATCH", r"^/api/v1/encounters/(?P<id>[^/]+)$", encounters.handle_encounter_update_draft, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/transition$", encounters.handle_encounter_transition, True),

    # Prompt 03: Formulary & Knowledge Sources
    ("GET", r"^/api/v1/clinical-sources$", formulations.handle_clinical_sources_list, True),
    ("GET", r"^/api/v1/ingredients$", formulations.handle_ingredients_search, True),
    ("GET", r"^/api/v1/formulations$", formulations.handle_formulations_search, True),
    ("GET", r"^/api/v1/formulations/(?P<id>[^/]+)$", formulations.handle_formulation_get, True),
    ("POST", r"^/api/v1/formulations$", formulations.handle_formulation_create_draft, True),
    ("POST", r"^/api/v1/formulations/versions/(?P<version_id>[^/]+)/submit-review$", formulations.handle_formulation_submit_review, True),
    ("POST", r"^/api/v1/formulations/versions/(?P<version_id>[^/]+)/approve$", formulations.handle_formulation_approve, True),

    # Prompt 03: Prescriptions & Nuskha Engine
    ("POST", r"^/api/v1/prescriptions$", prescriptions.handle_prescription_create_draft, True),
    ("GET", r"^/api/v1/prescriptions/(?P<id>[^/]+)$", prescriptions.handle_prescription_get, True),
    ("PATCH", r"^/api/v1/prescriptions/(?P<id>[^/]+)$", prescriptions.handle_prescription_update_draft, True),
    ("POST", r"^/api/v1/prescriptions/(?P<id>[^/]+)/validate$", prescriptions.handle_prescription_validate, True),
    ("POST", r"^/api/v1/prescriptions/(?P<id>[^/]+)/findings/(?P<finding_id>[^/]+)/acknowledge$", prescriptions.handle_prescription_acknowledge_warning, True),
    ("POST", r"^/api/v1/prescriptions/(?P<id>[^/]+)/sign$", prescriptions.handle_prescription_sign, True),
    ("POST", r"^/api/v1/prescriptions/(?P<id>[^/]+)/amend$", prescriptions.handle_prescription_amend, True),
    ("POST", r"^/api/v1/prescriptions/(?P<id>[^/]+)/cancel$", prescriptions.handle_prescription_cancel, True),
    ("GET", r"^/api/v1/prescriptions/(?P<id>[^/]+)/document$", prescriptions.handle_prescription_render_document, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/prescriptions$", prescriptions.handle_patient_prescriptions_list, True),

    # Prompt 04: Unani Assessment Templates & Encounter Assessments
    ("GET", r"^/api/v1/unani/templates$", unani_assessment.handle_unani_templates_list, True),
    ("GET", r"^/api/v1/unani/templates/versions/(?P<version_id>[^/]+)$", unani_assessment.handle_unani_template_version_get, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/unani-assessments$", unani_assessment.handle_unani_assessment_create_for_encounter, True),
    ("GET", r"^/api/v1/unani-assessments/(?P<id>[^/]+)$", unani_assessment.handle_unani_assessment_get, True),
    ("PATCH", r"^/api/v1/unani-assessments/(?P<id>[^/]+)$", unani_assessment.handle_unani_assessment_update_draft, True),
    ("POST", r"^/api/v1/unani-assessments/(?P<id>[^/]+)/finalise$", unani_assessment.handle_unani_assessment_finalise, True),
    ("POST", r"^/api/v1/unani-assessments/(?P<id>[^/]+)/amend$", unani_assessment.handle_unani_assessment_amend, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/unani-assessments$", unani_assessment.handle_patient_unani_assessments_list, True),

    # Prompt 04: Organ-Axis Contextual Mappings
    ("GET", r"^/api/v1/organ-axis/concepts$", organ_axis.handle_organ_axis_concepts_list, True),
    ("GET", r"^/api/v1/organ-axis/mappings$", organ_axis.handle_organ_axis_mappings_list, True),
    ("GET", r"^/api/v1/organ-axis/mappings/(?P<id>[^/]+)$", organ_axis.handle_organ_axis_mapping_get, True),
    ("POST", r"^/api/v1/organ-axis/mappings/(?P<id>[^/]+)/acknowledge$", organ_axis.handle_organ_axis_mapping_acknowledge, True),

    # Prompt 04: Usul-e-Ilaj Treatment Principles & Care Plans
    ("GET", r"^/api/v1/usul-e-ilaj/principles$", care_plans.handle_principles_list, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/care-plans$", care_plans.handle_care_plan_create_for_encounter, True),
    ("GET", r"^/api/v1/care-plans/(?P<id>[^/]+)$", care_plans.handle_care_plan_get, True),
    ("PATCH", r"^/api/v1/care-plans/(?P<id>[^/]+)$", care_plans.handle_care_plan_update_draft, True),
    ("POST", r"^/api/v1/care-plans/(?P<id>[^/]+)/transition$", care_plans.handle_care_plan_transition, True),
    ("POST", r"^/api/v1/care-plans/(?P<id>[^/]+)/items/(?P<item_id>[^/]+)/link-prescription$", care_plans.handle_care_plan_link_prescription, True),
    ("POST", r"^/api/v1/care-plans/(?P<id>[^/]+)/items/(?P<item_id>[^/]+)/outcomes$", care_plans.handle_care_plan_record_outcome, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/care-plans$", care_plans.handle_patient_care_plans_list, True),

    # Prompt 05: Modern Clinical Assessment & Decision Support
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/modern-assessments$", modern_assessment.handle_modern_assessment_create_for_encounter, True),
    ("GET", r"^/api/v1/encounters/(?P<id>[^/]+)/modern-assessments$", modern_assessment.handle_modern_assessment_get_for_encounter, True),
    ("GET", r"^/api/v1/modern-assessments/(?P<id>[^/]+)$", modern_assessment.handle_modern_assessment_get, True),
    ("PATCH", r"^/api/v1/modern-assessments/(?P<id>[^/]+)$", modern_assessment.handle_modern_assessment_update_draft, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/observations$", modern_assessment.handle_modern_assessment_observations_add, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/run-safety-checks$", modern_assessment.handle_modern_assessment_run_safety_checks, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/red-flags/(?P<alert_id>[^/]+)/acknowledge$", modern_assessment.handle_modern_assessment_acknowledge_red_flag, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/differential-support$", modern_assessment.handle_modern_assessment_run_differential, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/differential-candidates/(?P<candidate_id>[^/]+)/decision$", modern_assessment.handle_modern_assessment_decide_differential, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/problems$", modern_assessment.handle_modern_assessment_problem_add, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/investigations/(?P<inv_id>[^/]+)/decision$", modern_assessment.handle_modern_assessment_decide_investigation, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/referrals$", modern_assessment.handle_modern_assessment_referral_create, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/sign$", modern_assessment.handle_modern_assessment_sign, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/amend$", modern_assessment.handle_modern_assessment_amend, True),
    ("POST", r"^/api/v1/modern-assessments/(?P<id>[^/]+)/cancel$", modern_assessment.handle_modern_assessment_cancel, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/modern-assessments$", modern_assessment.handle_patient_modern_assessments_list, True),

    # Prompt 05: Clinical Content & Governed Rules Catalog
    ("GET", r"^/api/v1/clinical-content/status$", clinical_rules.handle_clinical_content_status, True),
    ("GET", r"^/api/v1/clinical-rules$", clinical_rules.handle_clinical_rules_list, True),

    # Prompt 06: Clinical Knowledge Base, Governed Source Registry, Claims & Evidence
    ("POST", r"^/api/v1/knowledge/sources$", knowledge.handle_create_source, True),
    ("GET", r"^/api/v1/knowledge/sources/(?P<id>[^/]+)$", knowledge.handle_get_source, True),
    ("GET", r"^/api/v1/knowledge/sources$", knowledge.handle_list_sources, True),
    ("POST", r"^/api/v1/knowledge/items$", knowledge.handle_create_knowledge_item, True),
    ("GET", r"^/api/v1/knowledge/items/(?P<id>[^/]+)$", knowledge.handle_get_knowledge_item, True),
    ("GET", r"^/api/v1/knowledge/items/(?P<id>[^/]+)/synthesize$", knowledge.handle_synthesize_evidence, True),
    ("GET", r"^/api/v1/knowledge/items$", knowledge.handle_list_knowledge_items, True),
    ("POST", r"^/api/v1/knowledge/claims$", knowledge.handle_create_claim, True),
    ("GET", r"^/api/v1/knowledge/claims/(?P<id>[^/]+)$", knowledge.handle_get_claim, True),
    ("POST", r"^/api/v1/knowledge/evidence$", knowledge.handle_create_evidence, True),
    ("GET", r"^/api/v1/knowledge/evidence/(?P<id>[^/]+)$", knowledge.handle_get_evidence, True),
    ("GET", r"^/api/v1/knowledge/search$", knowledge.handle_search_knowledge, True),
    ("POST", r"^/api/v1/knowledge/retrieve$", knowledge.handle_retrieve_context, True),
    ("GET", r"^/api/v1/knowledge/citations/(?P<id>[^/]+)$", knowledge.handle_get_citation, True),
    ("POST", r"^/api/v1/knowledge/review/(?P<id>[^/]+)/approve$", knowledge.handle_approve_item, True),
    ("POST", r"^/api/v1/knowledge/review/(?P<id>[^/]+)/reject$", knowledge.handle_reject_item, True),
    ("POST", r"^/api/v1/knowledge/review/(?P<id>[^/]+)/request-changes$", knowledge.handle_request_changes_item, True),
    ("GET", r"^/api/v1/knowledge/review/queue$", knowledge.handle_get_review_queue, True),
    ("GET", r"^/api/v1/knowledge/audit-logs/(?P<id>[^/]+)$", knowledge.handle_get_review_logs, True),

    # Prompt 07: Clinical Safety Firewall & Interaction Engine
    ("POST", r"^/api/v1/safety/preflight$", safety_firewall.handle_run_preflight, True),
    ("GET", r"^/api/v1/safety/preflight/(?P<run_id>[^/]+)$", safety_firewall.handle_get_preflight_run, True),
    ("POST", r"^/api/v1/safety/findings/(?P<finding_id>[^/]+)/disposition$", safety_firewall.handle_record_disposition, True),
    ("GET", r"^/api/v1/safety/substances/resolve$", safety_firewall.handle_resolve_substance, True),

    # Prompt 08: Unified Consultation Workspace & Clinical Workflow Orchestrator
    ("GET", r"^/api/v1/encounters/(?P<id>[^/]+)/workspace$", consultation_orchestrator.handle_get_workspace, True),
    ("PATCH", r"^/api/v1/encounters/(?P<id>[^/]+)/workspace$", consultation_orchestrator.handle_update_workspace_draft, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/autosave$", consultation_orchestrator.handle_autosave, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/sections/(?P<section_key>[^/]+)/complete$", consultation_orchestrator.handle_complete_section, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/sections/(?P<section_key>[^/]+)/mark-not-applicable$", consultation_orchestrator.handle_mark_section_na, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/state-transition$", consultation_orchestrator.handle_orchestrator_transition, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/validate-signoff$", consultation_orchestrator.handle_validate_signoff, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/finalize$", consultation_orchestrator.handle_finalize_encounter, True),
    ("GET", r"^/api/v1/encounters/(?P<id>[^/]+)/documents$", consultation_orchestrator.handle_get_documents, True),
    ("POST", r"^/api/v1/encounters/(?P<id>[^/]+)/followup-tasks$", consultation_orchestrator.handle_create_followup, True),

    # Prompt 09: Follow-up, Care Continuity, Patient Communication & Outcome Tracking
    ("POST", r"^/api/v1/follow-up/plans$", care_continuity.handle_create_follow_up_plan, True),
    ("GET", r"^/api/v1/follow-up/plans$", care_continuity.handle_list_follow_up_plans, True),
    ("GET", r"^/api/v1/follow-up/plans/(?P<id>[^/]+)$", care_continuity.handle_get_follow_up_plan, True),
    ("PATCH", r"^/api/v1/follow-up/plans/(?P<id>[^/]+)$", care_continuity.handle_update_follow_up_plan, True),
    ("POST", r"^/api/v1/follow-up/tasks$", care_continuity.handle_create_follow_up_task, True),
    ("GET", r"^/api/v1/follow-up/tasks/(?P<id>[^/]+)$", care_continuity.handle_get_follow_up_task, True),
    ("POST", r"^/api/v1/follow-up/tasks/(?P<id>[^/]+)/contact-attempts$", care_continuity.handle_record_contact_attempt, True),
    ("POST", r"^/api/v1/follow-up/tasks/(?P<id>[^/]+)/transition$", care_continuity.handle_transition_follow_up_task, True),
    ("POST", r"^/api/v1/follow-up/appointments$", care_continuity.handle_create_appointment, True),
    ("GET", r"^/api/v1/follow-up/appointments/(?P<id>[^/]+)$", care_continuity.handle_get_appointment, True),
    ("POST", r"^/api/v1/follow-up/appointments/(?P<id>[^/]+)/transition$", care_continuity.handle_transition_appointment, True),
    ("GET", r"^/api/v1/follow-up/queue$", care_continuity.handle_get_follow_up_queue, True),
    ("GET", r"^/api/v1/follow-up/analytics$", care_continuity.handle_get_follow_up_analytics, True),
    ("GET", r"^/api/v1/patient-communications/preferences/(?P<patient_id>[^/]+)$", care_continuity.handle_get_comm_preferences, True),
    ("PUT", r"^/api/v1/patient-communications/preferences/(?P<patient_id>[^/]+)$", care_continuity.handle_upsert_comm_preferences, True),
    ("GET", r"^/api/v1/patient-communications/templates$", care_continuity.handle_list_comm_templates, True),
    ("POST", r"^/api/v1/patient-communications/templates$", care_continuity.handle_create_comm_template, True),
    ("POST", r"^/api/v1/patient-communications/templates/(?P<id>[^/]+)/approve$", care_continuity.handle_approve_comm_template, True),
    ("POST", r"^/api/v1/patient-communications/send$", care_continuity.handle_send_communication, True),
    ("POST", r"^/api/v1/patient-communications/messages/(?P<id>[^/]+)/dispatch$", care_continuity.handle_dispatch_queued_message, True),
    ("GET", r"^/api/v1/patient-communications/messages/(?P<id>[^/]+)$", care_continuity.handle_get_outbound_message, True),
    ("POST", r"^/api/v1/patient-communications/provider-webhooks/(?P<provider>[^/]+)$", care_continuity.handle_provider_webhook, False),
    ("GET", r"^/api/v1/outcomes/definitions$", care_continuity.handle_list_outcome_definitions, True),
    ("POST", r"^/api/v1/outcomes/definitions$", care_continuity.handle_create_outcome_definition, True),
    ("POST", r"^/api/v1/outcomes/records$", care_continuity.handle_record_outcome, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/outcomes$", care_continuity.handle_get_patient_outcomes, True),
    ("POST", r"^/api/v1/adverse-effects$", care_continuity.handle_report_adverse_effect, True),
    ("POST", r"^/api/v1/adverse-effects/(?P<id>[^/]+)/review$", care_continuity.handle_review_adverse_effect, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/follow-up-summary$", care_continuity.handle_get_patient_continuity_summary, True),

    # Prompt 10: Clinic Operations OS (Appointments, Queue, Billing, Inventory & Dispensing)
    ("GET", r"^/api/v1/operations/today$", clinic_operations.handle_get_today_dashboard, True),
    ("GET", r"^/api/v1/operations/reports$", clinic_operations.handle_get_operational_reports, True),
    ("GET", r"^/api/v1/operations/settings$", clinic_operations.handle_get_facility_settings, True),
    ("PUT", r"^/api/v1/operations/settings$", clinic_operations.handle_update_facility_settings, True),
    ("POST", r"^/api/v1/scheduling/practitioner-schedules$", clinic_operations.handle_upsert_practitioner_schedule, True),
    ("POST", r"^/api/v1/scheduling/blocks$", clinic_operations.handle_create_schedule_block, True),
    ("GET", r"^/api/v1/scheduling/availability$", clinic_operations.handle_get_scheduling_availability, True),

    ("POST", r"^/api/v1/appointments$", clinic_operations.handle_create_appointment, True),
    ("GET", r"^/api/v1/appointments$", clinic_operations.handle_list_appointments, True),
    ("GET", r"^/api/v1/appointments/(?P<id>[^/]+)$", clinic_operations.handle_get_appointment, True),
    ("PATCH", r"^/api/v1/appointments/(?P<id>[^/]+)$", clinic_operations.handle_update_appointment, True),
    ("POST", r"^/api/v1/appointments/(?P<id>[^/]+)/confirm$", clinic_operations.handle_confirm_appointment, True),
    ("POST", r"^/api/v1/appointments/(?P<id>[^/]+)/check-in$", clinic_operations.handle_check_in_appointment, True),
    ("POST", r"^/api/v1/appointments/(?P<id>[^/]+)/cancel$", clinic_operations.handle_cancel_appointment, True),
    ("POST", r"^/api/v1/appointments/(?P<id>[^/]+)/reschedule$", clinic_operations.handle_reschedule_appointment, True),

    ("POST", r"^/api/v1/queue/tokens$", clinic_operations.handle_issue_queue_token, True),
    ("GET", r"^/api/v1/queue$", clinic_operations.handle_list_queue, True),
    ("POST", r"^/api/v1/queue/tokens/(?P<id>[^/]+)/call$", clinic_operations.handle_call_queue_token, True),
    ("POST", r"^/api/v1/queue/tokens/(?P<id>[^/]+)/start$", clinic_operations.handle_start_queue_token, True),
    ("POST", r"^/api/v1/queue/tokens/(?P<id>[^/]+)/complete$", clinic_operations.handle_complete_queue_token, True),
    ("POST", r"^/api/v1/queue/tokens/(?P<id>[^/]+)/cancel$", clinic_operations.handle_cancel_queue_token, True),

    ("GET", r"^/api/v1/billing/fee-catalog$", clinic_operations.handle_list_fee_catalog, True),
    ("POST", r"^/api/v1/billing/fee-catalog$", clinic_operations.handle_upsert_fee_catalog, True),
    ("POST", r"^/api/v1/billing/invoices$", clinic_operations.handle_create_invoice, True),
    ("GET", r"^/api/v1/billing/invoices$", clinic_operations.handle_list_invoices, True),
    ("GET", r"^/api/v1/billing/invoices/(?P<id>[^/]+)$", clinic_operations.handle_get_invoice, True),
    ("POST", r"^/api/v1/billing/invoices/(?P<id>[^/]+)/finalize$", clinic_operations.handle_finalize_invoice, True),
    ("POST", r"^/api/v1/billing/payments$", clinic_operations.handle_record_payment, True),
    ("POST", r"^/api/v1/billing/payments/(?P<id>[^/]+)/refund$", clinic_operations.handle_refund_payment, True),
    ("POST", r"^/api/v1/billing/invoices/(?P<id>[^/]+)/void$", clinic_operations.handle_void_invoice, True),
    ("GET", r"^/api/v1/billing/reports/collections$", clinic_operations.handle_get_collections_report, True),

    ("POST", r"^/api/v1/inventory/items$", clinic_operations.handle_create_inventory_item, True),
    ("GET", r"^/api/v1/inventory/items$", clinic_operations.handle_list_inventory_items, True),
    ("POST", r"^/api/v1/inventory/receipts$", clinic_operations.handle_receive_stock, True),
    ("POST", r"^/api/v1/inventory/movements$", clinic_operations.handle_record_inventory_movement, True),
    ("GET", r"^/api/v1/inventory/stock$", clinic_operations.handle_get_inventory_stock, True),
    ("GET", r"^/api/v1/inventory/batches$", clinic_operations.handle_list_inventory_batches, True),
    ("POST", r"^/api/v1/inventory/stocktakes$", clinic_operations.handle_create_stocktake, True),
    ("POST", r"^/api/v1/dispensing$", clinic_operations.handle_dispense_prescription, True),
    ("GET", r"^/api/v1/dispensing/(?P<id>[^/]+)$", clinic_operations.handle_get_dispense_record, True),
]

class ApiRouter:
    @staticmethod
    def dispatch(method: str, path: str, headers: Dict[str, str], query_params: Dict[str, str],
                  body_bytes: bytes, client_ip: str, db_path: Optional[str] = None) -> Tuple[int, Dict[str, str], bytes]:
        """Dispatch incoming request through middleware, authentication, and route handlers."""
        # Correlation / Request ID tracking
        request_id = headers.get("x-request-id") or str(uuid.uuid4())

        if "?" in path:
            raw_path, raw_qs = path.split("?", 1)
            path = raw_path
            if not query_params:
                from urllib.parse import parse_qs
                parsed = parse_qs(raw_qs)
                query_params = {k: v[0] for k, v in parsed.items()}

        # Parse JSON payload
        body = {}
        if body_bytes:
            try:
                body = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                err_resp = {
                    "error": True,
                    "code": "MALFORMED_JSON",
                    "message": "Malformed JSON payload in request body",
                    "request_id": request_id,
                    "details": {}
                }
                return 400, {"Content-Type": "application/json", "X-Request-Id": request_id}, json.dumps(err_resp).encode("utf-8")

        # Resolve auth token (Bearer header or cookie)
        auth_header = headers.get("authorization") or headers.get("Authorization") or ""
        token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else headers.get("x-auth-token", "")

        req = {
            "method": method,
            "path": path,
            "headers": headers,
            "query_params": query_params,
            "body": body,
            "body_bytes": body_bytes,
            "auth_token": token,
            "client_ip": client_ip,
            "request_id": request_id,
            "path_params": {},
            "db_path": db_path
        }


        with get_db(db_path) as conn:
            for route_method, pattern, handler_fn, requires_auth in ROUTES:
                if route_method == method:
                    match = re.match(pattern, path)
                    if match:
                        req["path_params"] = match.groupdict()

                        # Enforce Session Authentication
                        if requires_auth:
                            try:
                                req["user"] = validate_session(conn, token)
                            except AuthenticationError as e:
                                e.request_id = request_id
                                return e.status_code, {"Content-Type": "application/json", "X-Request-Id": request_id}, json.dumps(e.to_dict()).encode("utf-8")

                        try:
                            status_code, response_data = handler_fn(conn, req)
                            resp_bytes = json.dumps(response_data, indent=2, default=str).encode("utf-8")
                            return status_code, {"Content-Type": "application/json", "X-Request-Id": request_id}, resp_bytes
                        except AppError as e:
                            e.request_id = request_id
                            resp_bytes = json.dumps(e.to_dict()).encode("utf-8")
                            return e.status_code, {"Content-Type": "application/json", "X-Request-Id": request_id}, resp_bytes
                        except Exception as e:
                            err_resp = {
                                "error": True,
                                "code": "INTERNAL_SERVER_ERROR",
                                "message": "An internal server error occurred.",
                                "request_id": request_id,
                                "details": {}
                            }
                            resp_bytes = json.dumps(err_resp).encode("utf-8")
                            return 500, {"Content-Type": "application/json", "X-Request-Id": request_id}, resp_bytes

            # Route not matched
            err_resp = {
                "error": True,
                "code": "NOT_FOUND",
                "message": f"Endpoint '{method} {path}' not found.",
                "request_id": request_id,
                "details": {}
            }
            return 404, {"Content-Type": "application/json", "X-Request-Id": request_id}, json.dumps(err_resp).encode("utf-8")

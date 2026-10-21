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
    consultation_orchestrator, care_continuity, clinic_operations, enterprise_admin,
    hospital_interop, pilot_launch, post_pilot_evaluation, kavs, ontology, knowledge_mapping,
    evidence_verification, clinical_rag, cds_orchestrator, data_quality, timeline,
    outcomes, pharmacovigilance, governance, audit_ledger, security_governance,
    interoperability, integration_ops, analytics, command_center,
    workflow_automation, sla_governance, simulation, release_governance,
    observability, disaster_recovery, data_lifecycle, data_governance,
    data_lineage, config_governance, identity_governance, security_posture,
    threat_modeling, clinical_safety, test_automation, accessibility_localization,
    api_integration_certification, performance_scalability, tenant_governance,
    backup_restore, library, master_clinical,
    ai_copilot, zfie_routes, inventory, library_corpus, outcomes_prom,
    settings_routes
)




ROUTES = [
    # 1. Clinical Advisor & Decision Support (Governed Clinical Reference & Classical Unani Engine)
    ("POST", r"^/api/v1/hakeem-ai/query$", ai_copilot.handle_ai_query, True),
    ("POST", r"^/api/v1/clinical/ai-assistant$", ai_copilot.handle_ai_query, True),
    ("GET", r"^/api/v1/hakeem-ai/status$", ai_copilot.handle_ai_status, True),

    # 2. ZFIE (Formulation Intelligence Engine - Molecular & Bio-Targets)
    ("GET", r"^/api/v1/zfie/formulations/(?P<sku>[^/]+)/molecular-profile$", zfie_routes.handle_zfie_formulation_profile, True),
    ("GET", r"^/api/v1/zfie/compounds$", zfie_routes.handle_zfie_compounds, True),
    ("GET", r"^/api/v1/zfie/targets$", zfie_routes.handle_zfie_targets, True),

    # 3. FEFO Inventory, Dispensing & Statutory Mudabbar Gate
    ("GET", r"^/api/v1/inventory$", inventory.handle_inventory_list, True),
    ("POST", r"^/api/v1/inventory/allocate-fefo$", inventory.handle_inventory_allocate_fefo, True),
    ("POST", r"^/api/v1/inventory/dispense$", inventory.handle_inventory_dispense, True),

    # 5. Grand Classical Library & Corpus (1,593 Standard Terms & 250 Mufradat)
    ("GET", r"^/api/v1/library/corpus/terms$", library_corpus.handle_corpus_terms, False),
    ("GET", r"^/api/v1/library/corpus/mufradat$", library_corpus.handle_corpus_mufradat, False),
    ("GET", r"^/api/v1/library/corpus/mufradat/(?P<herb_id>[^/]+)$", library_corpus.handle_corpus_mufrad_detail, False),
    ("GET", r"^/api/v1/library/corpus/sources$", library_corpus.handle_corpus_sources, False),

    # 6. Patient-Side Outcome Measures (PROMs) & Adherence
    ("POST", r"^/api/v1/outcomes/proms$", outcomes_prom.handle_prom_create, True),
    ("GET", r"^/api/v1/outcomes/proms$", outcomes_prom.handle_prom_list, True),
    ("POST", r"^/api/v1/outcomes/adherence$", outcomes_prom.handle_adherence_create, True),
    ("GET", r"^/api/v1/outcomes/adherence$", outcomes_prom.handle_adherence_list, True),

    # Observability & Liveness
    ("GET", r"^/api/v1/health/live$", health.handle_health_live, False),
    ("GET", r"^/api/v1/health/ready$", health.handle_health_ready, False),
    
    # Authentication & Session
    ("POST", r"^/api/v1/auth/login$", auth.handle_auth_login, False),
    ("POST", r"^/api/v1/auth/register-clinic$", auth.handle_auth_register_clinic, False),
    ("POST", r"^/api/v1/auth/logout$", auth.handle_auth_logout, True),
    ("GET", r"^/api/v1/auth/me$", auth.handle_auth_me, True),
    ("POST", r"^/api/v1/auth/password-reset$", auth.handle_password_reset_request, False),
    
    # 0. System Settings & Matab Preferences Studio
    ("GET", r"^/api/v1/settings$", settings_routes.handle_settings_get, True),
    ("POST", r"^/api/v1/settings$", settings_routes.handle_settings_save, True),
    ("PUT", r"^/api/v1/settings$", settings_routes.handle_settings_save, True),
    
    # Tenancy & Facilities
    ("GET", r"^/api/v1/organizations$", tenancy.handle_organizations_list, True),
    ("POST", r"^/api/v1/organizations$", enterprise_admin.handle_organization_create, True),
    ("GET", r"^/api/v1/organizations/(?P<organization_id>[^/]+)$", enterprise_admin.handle_organization_get, True),
    ("PATCH", r"^/api/v1/organizations/(?P<organization_id>[^/]+)$", enterprise_admin.handle_organization_update, True),
    ("POST", r"^/api/v1/organizations/(?P<organization_id>[^/]+)/suspend$", enterprise_admin.handle_organization_suspend, True),
    ("POST", r"^/api/v1/organizations/(?P<organization_id>[^/]+)/reactivate$", enterprise_admin.handle_organization_reactivate, True),
    ("POST", r"^/api/v1/organizations/(?P<organization_id>[^/]+)/memberships$", enterprise_admin.handle_organization_membership_create, True),
    ("GET", r"^/api/v1/organizations/(?P<organization_id>[^/]+)/configuration$", enterprise_admin.handle_organization_config_get, True),
    ("PATCH", r"^/api/v1/organizations/(?P<organization_id>[^/]+)/configuration$", enterprise_admin.handle_organization_config_update, True),

    ("GET", r"^/api/v1/facilities$", tenancy.handle_facilities_list, True),
    ("POST", r"^/api/v1/facilities$", tenancy.handle_facilities_create, True),
    ("GET", r"^/api/v1/facilities/(?P<id>[^/]+)$", tenancy.handle_facility_get, True),
    ("PATCH", r"^/api/v1/facilities/(?P<facility_id>[^/]+)$", enterprise_admin.handle_facility_update, True),
    ("GET", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/activation-check$", enterprise_admin.handle_facility_activation_check, True),
    ("POST", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/suspend$", enterprise_admin.handle_facility_suspend, True),
    ("POST", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/reactivate$", enterprise_admin.handle_facility_reactivate, True),
    ("POST", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/departments$", enterprise_admin.handle_department_create, True),
    ("GET", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/departments$", enterprise_admin.handle_departments_list, True),
    ("POST", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/assignments$", enterprise_admin.handle_staff_assignment_create, True),
    ("GET", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/assignments$", enterprise_admin.handle_staff_assignments_list, True),
    ("GET", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/configuration$", enterprise_admin.handle_facility_config_get, True),
    ("PATCH", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/configuration$", enterprise_admin.handle_facility_config_update, True),
    ("POST", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/configuration/rollback$", enterprise_admin.handle_facility_config_rollback, True),
    ("GET", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/modules$", enterprise_admin.handle_facility_modules_list, True),
    ("POST", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/modules/(?P<module_key>[^/]+)/enable$", enterprise_admin.handle_facility_module_enable, True),
    ("POST", r"^/api/v1/facilities/(?P<facility_id>[^/]+)/modules/(?P<module_key>[^/]+)/disable$", enterprise_admin.handle_facility_module_disable, True),

    ("GET", r"^/api/v1/assignments$", enterprise_admin.handle_staff_assignments_list, True),
    ("POST", r"^/api/v1/assignments/(?P<assignment_id>[^/]+)/revoke$", enterprise_admin.handle_staff_assignment_revoke, True),
    
    # Administration (Users, Roles, Permissions)
    ("GET", r"^/api/v1/users$", admin.handle_users_list, True),
    ("POST", r"^/api/v1/users$", admin.handle_users_create, True),
    ("GET", r"^/api/v1/roles$", admin.handle_roles_list, True),
    ("GET", r"^/api/v1/permissions$", admin.handle_permissions_list, True),
    
    # Audit & Governance
    ("GET", r"^/api/v1/audit$", audit.handle_audit_list, True),
    ("GET", r"^/api/v1/admin/audit-events$", enterprise_admin.handle_enterprise_audit_events, True),
    ("POST", r"^/api/v1/admin/single-clinic-migration$", enterprise_admin.handle_single_clinic_migration, True),
    ("GET", r"^/api/v1/system/capabilities$", capabilities.handle_capabilities_list, True),

    # Patients Domain (Master Patient Index, Identifiers, Consents, Duplicates, Timeline)
    ("POST", r"^/api/v1/patients$", patients.handle_patients_create, True),
    ("GET", r"^/api/v1/patients$", patients.handle_patients_search, True),
    ("POST", r"^/api/v1/patients/merge-requests$", enterprise_admin.handle_patient_merge_request_create, True),
    ("POST", r"^/api/v1/patients/merge-requests/(?P<merge_request_id>[^/]+)/review$", enterprise_admin.handle_patient_merge_request_review, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)$", patients.handle_patient_get_360, True),
    ("GET", r"^/api/v1/patients/(?P<id>[^/]+)/360$", patients.handle_patient_get_360, True),
    ("PATCH", r"^/api/v1/patients/(?P<id>[^/]+)$", patients.handle_patient_update_demographics, True),
    ("POST", r"^/api/v1/patients/(?P<patient_id>[^/]+)/facility-links$", enterprise_admin.handle_patient_facility_link_create, True),
    ("GET", r"^/api/v1/patients/(?P<patient_id>[^/]+)/cross-facility-continuity$", enterprise_admin.handle_patient_cross_facility_continuity_get, True),
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

    # Prompt 11: Inter-Facility Transfers & Hospital Integrations
    ("POST", r"^/api/v1/transfers$", enterprise_admin.handle_transfer_create, True),
    ("GET", r"^/api/v1/transfers$", enterprise_admin.handle_transfers_list, True),
    ("GET", r"^/api/v1/transfers/(?P<transfer_id>[^/]+)$", enterprise_admin.handle_transfer_get, True),
    ("POST", r"^/api/v1/transfers/(?P<transfer_id>[^/]+)/accept$", enterprise_admin.handle_transfer_accept, True),
    ("POST", r"^/api/v1/transfers/(?P<transfer_id>[^/]+)/decline$", enterprise_admin.handle_transfer_decline, True),
    ("POST", r"^/api/v1/transfers/(?P<transfer_id>[^/]+)/complete$", enterprise_admin.handle_transfer_complete, True),
    ("POST", r"^/api/v1/integrations/connectors$", enterprise_admin.handle_integration_connector_create, True),
    ("GET", r"^/api/v1/integrations/connectors$", enterprise_admin.handle_integration_connectors_list, True),
    ("POST", r"^/api/v1/integrations/connectors/(?P<connector_id>[^/]+)/verify$", enterprise_admin.handle_integration_connector_verify, True),

    # Encounters Domain (Lifecycle, Transitions)
    ("GET", r"^/api/v1/encounters/queue$", clinic_operations.handle_list_queue, True),
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

    # Prompt 12: Hospital Workflows (IPD/ADT, Wards/Beds, Laboratory, Referrals, FHIR R4 & ABDM)
    ("POST", r"^/api/v1/ipd/wards$", hospital_interop.handle_create_ward, True),
    ("GET", r"^/api/v1/ipd/wards$", hospital_interop.handle_list_wards, True),
    ("POST", r"^/api/v1/ipd/beds$", hospital_interop.handle_create_bed, True),
    ("GET", r"^/api/v1/ipd/beds$", hospital_interop.handle_list_beds, True),
    ("GET", r"^/api/v1/ipd/occupancy-dashboard$", hospital_interop.handle_get_occupancy_dashboard, True),

    ("POST", r"^/api/v1/ipd/admissions$", hospital_interop.handle_create_admission_request, True),
    ("GET", r"^/api/v1/ipd/admissions$", hospital_interop.handle_list_admissions, True),
    ("GET", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)$", hospital_interop.handle_get_admission, True),
    ("POST", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)/accept$", hospital_interop.handle_accept_admission, True),
    ("POST", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)/admit$", hospital_interop.handle_admit_patient, True),
    ("POST", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)/transfer$", hospital_interop.handle_transfer_inpatient, True),
    ("POST", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)/discharge$", hospital_interop.handle_discharge_patient, True),
    ("POST", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)/discharge-summary$", hospital_interop.handle_create_or_update_discharge_summary, True),
    ("GET", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)/discharge-summary$", hospital_interop.handle_get_discharge_summary, True),
    ("POST", r"^/api/v1/ipd/admissions/(?P<id>[^/]+)/discharge-summary/sign$", hospital_interop.handle_sign_discharge_summary, True),

    ("POST", r"^/api/v1/lab/catalog$", hospital_interop.handle_create_lab_catalog_item, True),
    ("GET", r"^/api/v1/lab/catalog$", hospital_interop.handle_list_lab_catalog, True),
    ("POST", r"^/api/v1/lab/orders$", hospital_interop.handle_create_lab_order, True),
    ("GET", r"^/api/v1/lab/orders$", hospital_interop.handle_list_lab_orders, True),
    ("GET", r"^/api/v1/lab/orders/(?P<id>[^/]+)$", hospital_interop.handle_get_lab_order, True),
    ("POST", r"^/api/v1/lab/orders/(?P<id>[^/]+)/collect$", hospital_interop.handle_collect_specimen, True),
    ("POST", r"^/api/v1/lab/results$", hospital_interop.handle_record_lab_result, True),
    ("GET", r"^/api/v1/lab/results/(?P<id>[^/]+)$", hospital_interop.handle_get_lab_result, True),

    ("POST", r"^/api/v1/hospital-referrals$", hospital_interop.handle_create_referral, True),
    ("GET", r"^/api/v1/hospital-referrals$", hospital_interop.handle_list_referrals, True),
    ("GET", r"^/api/v1/hospital-referrals/(?P<id>[^/]+)$", hospital_interop.handle_get_referral, True),
    ("POST", r"^/api/v1/hospital-referrals/(?P<id>[^/]+)/accept$", hospital_interop.handle_accept_referral, True),
    ("POST", r"^/api/v1/hospital-referrals/(?P<id>[^/]+)/decline$", hospital_interop.handle_decline_referral, True),
    ("POST", r"^/api/v1/hospital-referrals/(?P<id>[^/]+)/close$", hospital_interop.handle_close_referral, True),

    ("POST", r"^/api/v1/interop/consents$", hospital_interop.handle_record_consent, True),
    ("POST", r"^/api/v1/interop/fhir/validate$", hospital_interop.handle_validate_fhir_resource, True),
    ("POST", r"^/api/v1/interop/fhir/export$", hospital_interop.handle_export_fhir_bundle, True),
    ("POST", r"^/api/v1/interop/abdm/harness-request$", hospital_interop.handle_abdm_harness_request, True),

    # Phase 14: Controlled Pilot Launch & Clinic Onboarding
    ("GET", r"^/api/v1/pilot/programs$", pilot_launch.handle_list_pilot_programs, True),
    ("POST", r"^/api/v1/pilot/programs$", pilot_launch.handle_create_pilot_program, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)$", pilot_launch.handle_get_pilot_program, True),
    ("POST", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/scope$", pilot_launch.handle_declare_scope, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/eligibility$", pilot_launch.handle_evaluate_eligibility, True),
    ("POST", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/activate$", pilot_launch.handle_activate_pilot, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/facilities/(?P<facility_id>[^/]+)/checklist$", pilot_launch.handle_get_facility_checklist, True),
    ("POST", r"^/api/v1/pilot/checklists/(?P<id>[^/]+)/update$", pilot_launch.handle_update_checklist_stage, True),
    ("POST", r"^/api/v1/pilot/migrations/run$", pilot_launch.handle_run_data_migration, True),
    ("GET", r"^/api/v1/pilot/training/modules$", pilot_launch.handle_list_training_modules, True),
    ("POST", r"^/api/v1/pilot/training/enroll$", pilot_launch.handle_enroll_staff_training, True),
    ("POST", r"^/api/v1/pilot/training/enrollments/(?P<id>[^/]+)/complete$", pilot_launch.handle_complete_training, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/facilities/(?P<facility_id>[^/]+)/training-matrix$", pilot_launch.handle_get_training_matrix, True),
    ("POST", r"^/api/v1/pilot/tickets$", pilot_launch.handle_create_support_ticket, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/tickets$", pilot_launch.handle_list_support_tickets, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/safety-queue$", pilot_launch.handle_list_safety_queue, True),
    ("POST", r"^/api/v1/pilot/safety-queue/(?P<id>[^/]+)/resolve$", pilot_launch.handle_resolve_safety_incident, True),
    ("POST", r"^/api/v1/pilot/feedback$", pilot_launch.handle_submit_feedback, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/feedback$", pilot_launch.handle_list_feedback, True),
    ("POST", r"^/api/v1/pilot/stop-events/trigger$", pilot_launch.handle_trigger_stop_condition, True),
    ("POST", r"^/api/v1/pilot/stop-events/(?P<id>[^/]+)/resolve$", pilot_launch.handle_resolve_stop_condition, True),
    ("GET", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/metrics$", pilot_launch.handle_get_pilot_metrics, True),
    ("POST", r"^/api/v1/pilot/programs/(?P<id>[^/]+)/review-packs$", pilot_launch.handle_generate_review_pack, True),

    # Prompt 15: Post-Pilot Evaluation, Adoption Scorecard & Scale Decision
    ("GET", r"^/api/v1/pilot-evaluations$", post_pilot_evaluation.handle_list_evaluations, True),
    ("POST", r"^/api/v1/pilot-evaluations$", post_pilot_evaluation.handle_create_evaluation, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)$", post_pilot_evaluation.handle_get_evaluation, True),
    ("PATCH", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/status$", post_pilot_evaluation.handle_update_evaluation_status, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/collect-evidence$", post_pilot_evaluation.handle_collect_evidence, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/evidence$", post_pilot_evaluation.handle_list_evidence, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/calculate-scorecard$", post_pilot_evaluation.handle_calculate_scorecard, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/scorecard$", post_pilot_evaluation.handle_list_scorecard, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/review-feedback$", post_pilot_evaluation.handle_review_feedback, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/feedback-themes$", post_pilot_evaluation.handle_list_feedback_themes, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/review-risks$", post_pilot_evaluation.handle_review_risks, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/incident-risks$", post_pilot_evaluation.handle_list_incident_risks, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/expansion-proposals$", post_pilot_evaluation.handle_create_expansion_proposal, True),
    ("POST", r"^/api/v1/pilot-evaluations/expansion-proposals/(?P<proposal_id>[^/]+)/gates$", post_pilot_evaluation.handle_evaluate_expansion_gate, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/expansion-proposals$", post_pilot_evaluation.handle_list_expansion_proposals, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/record-decision$", post_pilot_evaluation.handle_record_decision, True),
    ("POST", r"^/api/v1/pilot-evaluations/decision-approvals$", post_pilot_evaluation.handle_approve_decision, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/decision$", post_pilot_evaluation.handle_get_decision, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/actions$", post_pilot_evaluation.handle_create_remediation_action, True),
    ("POST", r"^/api/v1/pilot-evaluations/actions/(?P<action_id>[^/]+)/close$", post_pilot_evaluation.handle_close_remediation_action, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/actions$", post_pilot_evaluation.handle_list_remediation_actions, True),
    ("POST", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/report$", post_pilot_evaluation.handle_generate_report, True),
    ("GET", r"^/api/v1/pilot-evaluations/(?P<id>[^/]+)/report$", post_pilot_evaluation.handle_generate_report, True),
    # Aliased routes for admin prefix
    ("GET", r"^/api/v1/admin/pilot-evaluations$", post_pilot_evaluation.handle_list_evaluations, True),
    ("POST", r"^/api/v1/admin/pilot-evaluations$", post_pilot_evaluation.handle_create_evaluation, True),
    ("GET", r"^/api/v1/admin/pilot-evaluations/(?P<id>[^/]+)$", post_pilot_evaluation.handle_get_evaluation, True),
    ("POST", r"^/api/v1/admin/pilot-evaluations/(?P<id>[^/]+)/collect-evidence$", post_pilot_evaluation.handle_collect_evidence, True),
    ("POST", r"^/api/v1/admin/pilot-evaluations/(?P<id>[^/]+)/calculate-scorecard$", post_pilot_evaluation.handle_calculate_scorecard, True),
    ("POST", r"^/api/v1/admin/pilot-evaluations/(?P<id>[^/]+)/review-risks$", post_pilot_evaluation.handle_review_risks, True),
    ("POST", r"^/api/v1/admin/pilot-evaluations/(?P<id>[^/]+)/evaluate-expansion$", post_pilot_evaluation.handle_create_expansion_proposal, True),
    ("GET", r"^/api/v1/admin/pilot-evaluations/(?P<id>[^/]+)/report$", post_pilot_evaluation.handle_generate_report, True),
    ("GET", r"^/api/v1/admin/pilot-evaluations/(?P<id>[^/]+)/actions$", post_pilot_evaluation.handle_list_remediation_actions, True),

    # Medical Library & Classical Compendia Infrastructure
    ("GET", r"^/api/v1/library/stats$", library.handle_library_stats, True),
    ("GET", r"^/api/v1/library/books$", library.handle_library_books_list, True),
    ("GET", r"^/api/v1/library/books/(?P<book_id>[^/]+)/view$", library.handle_library_book_view, True),
    ("GET", r"^/api/v1/library/books/(?P<book_id>[^/]+)$", library.handle_library_book_detail, True),
    ("POST", r"^/api/v1/library/reindex$", library.handle_library_reindex, True),

    # ZAYVORA Master Clinical System (12 Axes, 21 Protocols, 21 Kits, Parhez & Safety)
    ("GET", r"^/api/v1/clinical/axes$", master_clinical.handle_get_axes, True),
    ("POST", r"^/api/v1/clinical/axes/score$", master_clinical.handle_score_axes, True),
    ("GET", r"^/api/v1/clinical/protocols$", master_clinical.handle_get_protocols, True),
    ("GET", r"^/api/v1/clinical/protocols/(?P<id>[^/]+)$", master_clinical.handle_get_protocol_detail, True),
    ("GET", r"^/api/v1/clinical/kits$", master_clinical.handle_get_kits, True),
    ("GET", r"^/api/v1/clinical/parhez$", master_clinical.handle_get_parhez_list, True),
    ("GET", r"^/api/v1/clinical/parhez/(?P<code>[^/]+)$", master_clinical.handle_get_parhez_detail, True),
    ("POST", r"^/api/v1/clinical/safety/check$", master_clinical.handle_check_safety, True),

    # Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS)
    # 1. Sources & Provenance Registry
    ("POST", r"^/api/v1/kavs/sources$", kavs.handle_create_source, True),
    ("GET", r"^/api/v1/kavs/sources$", kavs.handle_list_sources, True),
    ("GET", r"^/api/v1/kavs/sources/(?P<id>[^/]+)$", kavs.handle_get_source, True),
    ("PATCH", r"^/api/v1/kavs/sources/(?P<id>[^/]+)$", kavs.handle_update_source, True),
    ("GET", r"^/api/v1/kavs/sources/(?P<id>[^/]+)/versions$", kavs.handle_list_source_versions, True),
    ("POST", r"^/api/v1/kavs/sources/(?P<id>[^/]+)/versions$", kavs.handle_register_source_version_for_source, True),
    ("POST", r"^/api/v1/kavs/sources/versions$", kavs.handle_register_source_version, True),
    ("GET", r"^/api/v1/kavs/sources/versions/(?P<id>[^/]+)$", kavs.handle_get_source_version, True),
    ("POST", r"^/api/v1/kavs/sources/rights-reviews$", kavs.handle_record_rights_review, True),
    ("POST", r"^/api/v1/kavs/sources/versions/(?P<id>[^/]+)/preflight-rights$", kavs.handle_preflight_rights, True),
    ("POST", r"^/api/v1/kavs/sources/versions/(?P<id>[^/]+)/upload-file$", kavs.handle_upload_source_file, True),
    ("GET", r"^/api/v1/kavs/source-files/(?P<id>[^/]+)$", kavs.handle_get_source_file, True),

    # 2. Source Locators
    ("POST", r"^/api/v1/kavs/sources/versions/(?P<id>[^/]+)/locators$", kavs.handle_create_source_locator, True),
    ("GET", r"^/api/v1/kavs/sources/versions/(?P<id>[^/]+)/locators$", kavs.handle_list_source_locators, True),
    ("GET", r"^/api/v1/kavs/locators$", kavs.handle_list_source_locators, True),
    ("POST", r"^/api/v1/kavs/locators/(?P<id>[^/]+)/verify$", kavs.handle_verify_source_locator, True),

    # 3. Source Verification Events
    ("POST", r"^/api/v1/kavs/sources/(?P<id>[^/]+)/verification-events$", kavs.handle_record_source_verification_event, True),
    ("GET", r"^/api/v1/kavs/sources/(?P<id>[^/]+)/verification-events$", kavs.handle_list_source_verification_events, True),
    ("GET", r"^/api/v1/kavs/verification-events$", kavs.handle_list_source_verification_events, True),

    # 4. Governance Policies
    ("POST", r"^/api/v1/kavs/policies$", kavs.handle_register_governance_policy, True),
    ("GET", r"^/api/v1/kavs/policies$", kavs.handle_list_governance_policies, True),
    ("GET", r"^/api/v1/kavs/policies/active$", kavs.handle_get_active_governance_policy, True),

    # 5. Atomic Claims Lifecycle & Review
    ("POST", r"^/api/v1/kavs/claims$", kavs.handle_create_atomic_claim, True),
    ("GET", r"^/api/v1/kavs/claims$", kavs.handle_list_atomic_claims, True),
    ("GET", r"^/api/v1/kavs/claims/(?P<id>[^/]+)$", kavs.handle_get_atomic_claim, True),
    ("POST", r"^/api/v1/kavs/claims/(?P<id>[^/]+)/submit-review$", kavs.handle_submit_claim_for_review, True),
    ("POST", r"^/api/v1/kavs/claims/(?P<id>[^/]+)/approve$", kavs.handle_approve_claim, True),
    ("POST", r"^/api/v1/kavs/claims/(?P<id>[^/]+)/reject$", kavs.handle_reject_claim, True),
    ("POST", r"^/api/v1/kavs/claims/(?P<id>[^/]+)/withdraw$", kavs.handle_withdraw_claim, True),

    # 6. Ingestion & Extraction Jobs & Workbench
    ("POST", r"^/api/v1/kavs/ingestion/jobs$", kavs.handle_create_ingestion_job, True),
    ("GET", r"^/api/v1/kavs/ingestion/jobs$", kavs.handle_list_ingestion_jobs, True),
    ("GET", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)$", kavs.handle_get_ingestion_job, True),
    ("POST", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/transition$", kavs.handle_transition_ingestion_job, True),
    ("POST", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/cancel$", kavs.handle_cancel_ingestion_job, True),
    ("POST", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/retry$", kavs.handle_retry_ingestion_job, True),
    ("POST", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/pages$", kavs.handle_add_extraction_page, True),
    ("GET", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/pages$", kavs.handle_list_extraction_pages, True),
    ("GET", r"^/api/v1/kavs/extraction-pages/(?P<id>[^/]+)$", kavs.handle_get_extraction_page, True),
    ("POST", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/segments$", kavs.handle_add_extraction_segment, True),
    ("GET", r"^/api/v1/kavs/extraction-segments/(?P<id>[^/]+)$", kavs.handle_get_extraction_segment, True),
    ("POST", r"^/api/v1/kavs/extraction-segments/(?P<id>[^/]+)/corrections$", kavs.handle_record_segment_correction, True),
    ("POST", r"^/api/v1/kavs/extraction-segments/(?P<id>[^/]+)/mark-unreadable$", kavs.handle_mark_segment_unreadable, True),
    ("POST", r"^/api/v1/kavs/ingestion/segments/(?P<id>[^/]+)/review$", kavs.handle_review_extraction_segment, True),
    ("POST", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/tables$", kavs.handle_add_extraction_table, True),
    ("GET", r"^/api/v1/kavs/ingestion/jobs/(?P<id>[^/]+)/tables$", kavs.handle_list_extraction_tables, True),

    # 6B. Candidate Claim Drafts
    ("POST", r"^/api/v1/kavs/claim-drafts$", kavs.handle_create_claim_draft, True),
    ("GET", r"^/api/v1/kavs/claim-drafts$", kavs.handle_list_claim_drafts, True),
    ("GET", r"^/api/v1/kavs/claim-drafts/(?P<id>[^/]+)$", kavs.handle_get_claim_draft, True),
    ("POST", r"^/api/v1/kavs/claim-drafts/(?P<id>[^/]+)/submit-review$", kavs.handle_submit_claim_draft_for_review, True),
    ("POST", r"^/api/v1/kavs/claim-drafts/(?P<id>[^/]+)/reject$", kavs.handle_reject_claim_draft, True),
    ("POST", r"^/api/v1/kavs/claim-drafts/(?P<id>[^/]+)/promote$", kavs.handle_promote_draft_to_atomic_claim, True),

    # 6C. Quality & Queue Dashboards
    ("GET", r"^/api/v1/kavs/ingestion-quality$", kavs.handle_get_ingestion_quality, True),
    ("GET", r"^/api/v1/kavs/ingestion-queue/health$", kavs.handle_get_ingestion_queue_health, True),

    # 7. Five-Dimension Claim Verification & Conflicts
    ("POST", r"^/api/v1/kavs/claims/(?P<id>[^/]+)/verifications$", kavs.handle_record_claim_verification, True),
    ("GET", r"^/api/v1/kavs/verifications/(?P<id>[^/]+)$", kavs.handle_get_claim_verification, True),
    ("POST", r"^/api/v1/kavs/claims/(?P<id>[^/]+)/conflicts$", kavs.handle_link_evidence_conflict, True),

    # 8. Knowledge Releases & Impact
    ("POST", r"^/api/v1/kavs/releases$", kavs.handle_publish_knowledge_release, True),
    ("POST", r"^/api/v1/kavs/releases/(?P<tag>[^/]+)/withdraw$", kavs.handle_withdraw_knowledge_release, True),
    ("POST", r"^/api/v1/kavs/impact-events$", kavs.handle_record_change_impact, True),
    ("POST", r"^/api/v1/kavs/retrieve$", kavs.handle_retrieve_verified_context, True),

    # 9. Audit Trail
    ("GET", r"^/api/v1/kavs/audit-events$", kavs.handle_list_kavs_audit_events, True),

    # Prompt 19: Unani Ontology & Canonical Materia-Medica Catalog
    ("GET", r"^/api/v1/ontology/concepts$", ontology.handle_list_concepts, True),
    ("POST", r"^/api/v1/ontology/concepts$", ontology.handle_create_concept, True),
    ("GET", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)$", ontology.handle_get_concept, True),
    ("PATCH", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)$", ontology.handle_update_concept, True),
    ("POST", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)/names$", ontology.handle_add_concept_name, True),
    ("POST", r"^/api/v1/ontology/names/(?P<id>[^/]+)/decision$", ontology.handle_review_concept_name, True),
    ("POST", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)/materials$", ontology.handle_set_material_identity, True),
    ("POST", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)/formulations$", ontology.handle_create_catalog_formulation, True),
    ("POST", r"^/api/v1/ontology/formulations/(?P<id>[^/]+)/components$", ontology.handle_add_formulation_ingredient, True),
    ("POST", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)/assertions$", ontology.handle_create_knowledge_assertion, True),
    ("POST", r"^/api/v1/ontology/assertions/(?P<id>[^/]+)/decision$", ontology.handle_review_knowledge_assertion, True),
    ("POST", r"^/api/v1/ontology/assertions/(?P<id>[^/]+)/withdraw$", ontology.handle_withdraw_knowledge_assertion, True),
    ("POST", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)/relations$", ontology.handle_create_concept_relation, True),
    ("POST", r"^/api/v1/ontology/concepts/(?P<id>[^/]+)/crosswalks$", ontology.handle_add_external_crosswalk, True),
    ("GET", r"^/api/v1/ontology/search$", ontology.handle_search_catalog, True),
    ("GET", r"^/api/v1/ontology/tasks$", ontology.handle_list_catalog_tasks, True),
    ("GET", r"^/api/v1/ontology/audit$", ontology.handle_list_catalog_change_events, True),

    # Prompt 20: Unani Clinical Knowledge Mapping & Organ-Axis Governance
    # 1. Controlled Relation Types
    ("GET", r"^/api/v1/knowledge/relations/types$", knowledge_mapping.handle_list_relation_types, True),
    ("POST", r"^/api/v1/knowledge/relations/types$", knowledge_mapping.handle_create_relation_type, True),
    ("GET", r"^/api/v1/knowledge/relations/types/(?P<id>[^/]+)$", knowledge_mapping.handle_get_relation_type, True),

    # 2. Relationship Assertions
    ("POST", r"^/api/v1/knowledge/relations$", knowledge_mapping.handle_create_relation, True),
    ("GET", r"^/api/v1/knowledge/relations$", knowledge_mapping.handle_list_relations, True),
    ("GET", r"^/api/v1/knowledge/relations/candidates$", knowledge_mapping.handle_list_relation_candidates, True),
    ("GET", r"^/api/v1/knowledge/relations/(?P<id>[^/]+)$", knowledge_mapping.handle_get_relation, True),
    ("POST", r"^/api/v1/knowledge/relations/(?P<id>[^/]+)/review$", knowledge_mapping.handle_review_relation, True),
    ("POST", r"^/api/v1/knowledge/relations/(?P<id>[^/]+)/withdraw$", knowledge_mapping.handle_withdraw_relation, True),

    # 3. Versioned Organ-Axis Frameworks & Memberships
    ("GET", r"^/api/v1/organ-axis/frameworks$", knowledge_mapping.handle_list_frameworks, True),
    ("POST", r"^/api/v1/organ-axis/frameworks$", knowledge_mapping.handle_create_framework, True),
    ("GET", r"^/api/v1/organ-axis/frameworks/(?P<id>[^/]+)$", knowledge_mapping.handle_get_framework, True),
    ("POST", r"^/api/v1/organ-axis/frameworks/(?P<id>[^/]+)/publish$", knowledge_mapping.handle_publish_framework, True),
    ("GET", r"^/api/v1/organ-axis/frameworks/(?P<id>[^/]+)/memberships$", knowledge_mapping.handle_list_framework_memberships, True),
    ("POST", r"^/api/v1/organ-axis/frameworks/(?P<id>[^/]+)/memberships$", knowledge_mapping.handle_add_framework_membership, True),

    # 4. Cross-Disciplinary Concept Mappings
    ("POST", r"^/api/v1/knowledge/mappings$", knowledge_mapping.handle_create_concept_mapping, True),
    ("GET", r"^/api/v1/knowledge/mappings$", knowledge_mapping.handle_list_concept_mappings, True),
    ("GET", r"^/api/v1/knowledge/mappings/candidates$", knowledge_mapping.handle_list_concept_mapping_candidates, True),
    ("GET", r"^/api/v1/knowledge/mappings/(?P<id>[^/]+)$", knowledge_mapping.handle_get_concept_mapping, True),
    ("POST", r"^/api/v1/knowledge/mappings/(?P<id>[^/]+)/review$", knowledge_mapping.handle_review_concept_mapping, True),

    # 5. Relationship Conflicts
    ("POST", r"^/api/v1/knowledge/conflicts$", knowledge_mapping.handle_report_conflict, True),
    ("GET", r"^/api/v1/knowledge/conflicts$", knowledge_mapping.handle_list_conflicts, True),
    ("GET", r"^/api/v1/knowledge/conflicts/(?P<id>[^/]+)$", knowledge_mapping.handle_get_conflict, True),
    ("POST", r"^/api/v1/knowledge/conflicts/(?P<id>[^/]+)/adjudicate$", knowledge_mapping.handle_adjudicate_conflict, True),

    # 6. Encounter-Scoped Case Hypotheses
    ("POST", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/hypothesis-links$", knowledge_mapping.handle_create_encounter_hypothesis, True),
    ("GET", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/hypothesis-links$", knowledge_mapping.handle_list_encounter_hypotheses, True),
    ("PATCH", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/hypothesis-links/(?P<id>[^/]+)/status$", knowledge_mapping.handle_update_encounter_hypothesis_status, True),

    # 7. Bounded Knowledge Graph Traversal
    ("GET", r"^/api/v1/knowledge/graph/traverse$", knowledge_mapping.handle_traverse_knowledge_graph, True),

    # Prompt 21: Evidence Classification, Clinical Claim Verification & Citation Validation Engine
    ("GET", r"^/api/v1/evidence/claim-types$", evidence_verification.handle_list_claim_types, True),
    ("POST", r"^/api/v1/evidence/claims$", evidence_verification.handle_create_claim, True),
    ("GET", r"^/api/v1/evidence/claims$", evidence_verification.handle_list_claims, True),
    ("GET", r"^/api/v1/evidence/claims/(?P<id>[^/]+)$", evidence_verification.handle_get_claim, True),
    ("POST", r"^/api/v1/evidence/claims/(?P<id>[^/]+)/source-links$", evidence_verification.handle_link_claim_to_source, True),
    ("GET", r"^/api/v1/evidence/claims/(?P<id>[^/]+)/source-links$", evidence_verification.handle_list_claim_source_links, True),
    ("POST", r"^/api/v1/evidence/citations/validate$", evidence_verification.handle_validate_citation, True),
    ("GET", r"^/api/v1/evidence/citations/validation-runs/(?P<id>[^/]+)$", evidence_verification.handle_get_validation_run, True),
    ("POST", r"^/api/v1/evidence/support-assessments$", evidence_verification.handle_create_support_assessment, True),
    ("POST", r"^/api/v1/evidence/support-assessments/(?P<id>[^/]+)/review$", evidence_verification.handle_review_support_assessment, True),
    ("POST", r"^/api/v1/evidence/characterizations$", evidence_verification.handle_create_characterization, True),
    ("POST", r"^/api/v1/evidence/characterizations/(?P<id>[^/]+)/review$", evidence_verification.handle_review_characterization, True),
    ("POST", r"^/api/v1/evidence/sources/(?P<id>[^/]+)/status-events$", evidence_verification.handle_record_source_status_event, True),
    ("GET", r"^/api/v1/evidence/sources/(?P<id>[^/]+)/status-events$", evidence_verification.handle_list_source_status_events, True),
    ("POST", r"^/api/v1/evidence/intended-use-approvals$", evidence_verification.handle_create_intended_use_approval, True),
    ("POST", r"^/api/v1/evidence/intended-use-approvals/(?P<id>[^/]+)/suspend$", evidence_verification.handle_suspend_intended_use_approval, True),
    ("POST", r"^/api/v1/evidence/conflicts$", evidence_verification.handle_create_evidence_conflict, True),
    ("GET", r"^/api/v1/evidence/conflicts$", evidence_verification.handle_list_evidence_conflicts, True),
    ("POST", r"^/api/v1/evidence/conflicts/(?P<id>[^/]+)/resolve$", evidence_verification.handle_resolve_evidence_conflict, True),
    ("GET", r"^/api/v1/evidence/clinician-context/(?P<id>[^/]+)$", evidence_verification.handle_get_clinician_context_claim, True),

    # Prompt 22: Evidence-Aware Clinical Knowledge Retrieval (Hybrid RAG) & Answer Generation Engine
    ("POST", r"^/api/v1/knowledge/retrieval/search$", clinical_rag.handle_search_knowledge, True),
    ("POST", r"^/api/v1/knowledge/retrieval/evidence-pack$", clinical_rag.handle_create_evidence_pack, True),
    ("GET", r"^/api/v1/knowledge/retrieval/packs/(?P<id>[^/]+)$", clinical_rag.handle_get_evidence_pack, True),
    ("POST", r"^/api/v1/knowledge/answers/draft$", clinical_rag.handle_generate_answer_draft, True),
    ("POST", r"^/api/v1/knowledge/answers/validate$", clinical_rag.handle_validate_answer, True),
    ("POST", r"^/api/v1/knowledge/answers$", clinical_rag.handle_orchestrated_answer, True),
    ("GET", r"^/api/v1/knowledge/answers/(?P<id>[^/]+)$", clinical_rag.handle_get_answer, True),
    ("GET", r"^/api/v1/knowledge/answers/(?P<id>[^/]+)/citations$", clinical_rag.handle_get_answer_citations, True),
    ("POST", r"^/api/v1/knowledge/retrieval/feedback$", clinical_rag.handle_create_retrieval_feedback, True),
    ("GET", r"^/api/v1/knowledge/retrieval/feedback$", clinical_rag.handle_list_retrieval_feedback, True),
    ("POST", r"^/api/v1/knowledge/retrieval/feedback/(?P<id>[^/]+)/resolve$", clinical_rag.handle_resolve_retrieval_feedback, True),

    # Prompt 23: Clinical Decision Support (CDS) Orchestrator & Clinician Approval Workflow
    ("GET", r"^/api/v1/cds/policies$", cds_orchestrator.handle_list_policies, True),
    ("GET", r"^/api/v1/cds/policies/(?P<code>[^/]+)$", cds_orchestrator.handle_get_policy, True),
    ("POST", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/cds-runs$", cds_orchestrator.handle_execute_cds_run, True),
    ("GET", r"^/api/v1/cds/runs/(?P<id>[^/]+)$", cds_orchestrator.handle_get_cds_run, True),
    ("GET", r"^/api/v1/cds/runs/(?P<id>[^/]+)/cards$", cds_orchestrator.handle_get_cds_run_cards, True),
    ("GET", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/cds-cards$", cds_orchestrator.handle_get_encounter_cards, True),
    ("POST", r"^/api/v1/cds/cards/(?P<id>[^/]+)/review$", cds_orchestrator.handle_review_card, True),
    ("GET", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/readiness$", cds_orchestrator.handle_check_readiness, True),
    ("POST", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/cds-transition$", cds_orchestrator.handle_transition_state, True),
    ("POST", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/sign$", cds_orchestrator.handle_sign_encounter, True),
    ("POST", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/amendments$", cds_orchestrator.handle_request_amendment, True),
    ("POST", r"^/api/v1/cds/kill-switch$", cds_orchestrator.handle_set_kill_switch, True),
    ("GET", r"^/api/v1/cds/kill-switch$", cds_orchestrator.handle_get_kill_switch, True),

    # Prompt 24: Clinical Workflow Intelligence & Data Quality Engine
    ("GET", r"^/api/v1/data-quality/rules$", data_quality.handle_list_rules, True),
    ("GET", r"^/api/v1/data-quality/rules/(?P<rule_code>[^/]+)$", data_quality.handle_get_rule, True),
    ("GET", r"^/api/v1/data-quality/freshness-policies$", data_quality.handle_list_freshness_policies, True),
    ("POST", r"^/api/v1/data-quality/evaluations$", data_quality.handle_evaluate_data_quality, True),
    ("GET", r"^/api/v1/data-quality/findings$", data_quality.handle_list_findings, True),
    ("GET", r"^/api/v1/data-quality/findings/(?P<id>[^/]+)$", data_quality.handle_get_finding, True),
    ("POST", r"^/api/v1/data-quality/findings/(?P<id>[^/]+)/resolve$", data_quality.handle_resolve_finding, True),
    ("POST", r"^/api/v1/data-quality/reconcile$", data_quality.handle_reconcile_conflict, True),
    ("POST", r"^/api/v1/data-quality/provenance$", data_quality.handle_record_provenance, True),
    ("GET", r"^/api/v1/data-quality/provenance$", data_quality.handle_get_provenance, True),
    ("GET", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/data-quality-readiness$", data_quality.handle_check_dq_readiness, True),

    # Prompt 25: Longitudinal Patient Timeline & Care Continuity Engine
    ("GET", r"^/api/v1/patients/(?P<patient_id>[^/]+)/longitudinal-timeline$", timeline.handle_get_timeline, True),
    ("POST", r"^/api/v1/patients/(?P<patient_id>[^/]+)/timeline-events$", timeline.handle_record_timeline_event, True),
    ("POST", r"^/api/v1/encounters/(?P<encounter_id>[^/]+)/timeline-sync$", timeline.handle_sync_encounter_events, True),
    ("GET", r"^/api/v1/patients/(?P<patient_id>[^/]+)/medications$", timeline.handle_list_medications, True),
    ("POST", r"^/api/v1/patients/(?P<patient_id>[^/]+)/medications/status$", timeline.handle_update_medication_status, True),
    ("POST", r"^/api/v1/care-continuity/tasks$", timeline.handle_create_continuity_task, True),
    ("GET", r"^/api/v1/care-continuity/tasks$", timeline.handle_list_continuity_tasks, True),
    ("POST", r"^/api/v1/care-continuity/tasks/(?P<id>[^/]+)/attempts$", timeline.handle_record_contact_attempt, True),
    ("POST", r"^/api/v1/care-continuity/tasks/(?P<id>[^/]+)/complete$", timeline.handle_complete_continuity_task, True),
    ("POST", r"^/api/v1/patients/(?P<patient_id>[^/]+)/timeline-summaries$", timeline.handle_generate_timeline_summary, True),
    ("POST", r"^/api/v1/timeline-summaries/(?P<id>[^/]+)/review$", timeline.handle_review_timeline_summary, True),

    # Prompt 26: Clinical Outcome Tracking, Treatment Response Measurement & Longitudinal Evaluation
    ("GET", r"^/api/v1/outcomes/instruments$", outcomes.handle_list_instruments, True),
    ("GET", r"^/api/v1/outcomes/instruments/(?P<id>[^/]+)$", outcomes.handle_get_instrument, True),
    ("GET", r"^/api/v1/outcomes/concepts$", outcomes.handle_list_concepts, True),
    ("GET", r"^/api/v1/outcomes/protocols$", outcomes.handle_list_protocols, True),
    ("POST", r"^/api/v1/care-episodes$", outcomes.handle_open_care_episode, True),
    ("POST", r"^/api/v1/outcome-protocol-runs$", outcomes.handle_start_protocol_run, True),
    ("POST", r"^/api/v1/outcome-protocol-runs/(?P<id>[^/]+)/baseline$", outcomes.handle_designate_baseline, True),
    ("POST", r"^/api/v1/outcome-observations$", outcomes.handle_record_observation, True),
    ("POST", r"^/api/v1/outcome-observations/(?P<id>[^/]+)/correction$", outcomes.handle_correct_observation, True),
    ("GET", r"^/api/v1/outcome-observations/(?P<id>[^/]+)$", outcomes.handle_get_observation, True),
    ("POST", r"^/api/v1/outcomes/instrument-scores$", outcomes.handle_score_instrument, True),
    ("POST", r"^/api/v1/outcomes/compare$", outcomes.handle_compare_observations, True),
    ("POST", r"^/api/v1/patients/(?P<patient_id>[^/]+)/treatment-exposures$", outcomes.handle_record_treatment_exposure, True),
    ("GET", r"^/api/v1/patients/(?P<patient_id>[^/]+)/treatment-exposures$", outcomes.handle_list_treatment_exposures, True),
    ("POST", r"^/api/v1/outcome-interpretations$", outcomes.handle_create_interpretation, True),
    ("POST", r"^/api/v1/outcome-interpretations/(?P<id>[^/]+)/review$", outcomes.handle_review_interpretation, True),
    ("GET", r"^/api/v1/patients/(?P<patient_id>[^/]+)/outcomes/trends$", outcomes.handle_get_patient_longitudinal_outcomes, True),
    ("POST", r"^/api/v1/outcomes/aggregate-reports$", outcomes.handle_generate_aggregate_report, True),
    ("GET", r"^/api/v1/outcomes/aggregate-reports/(?P<id>[^/]+)$", outcomes.handle_get_aggregate_report, True),

    # Prompt 27: Clinical Safety Surveillance, Adverse Event Management & Pharmacovigilance
    ("POST", r"^/api/v1/safety/cases$", pharmacovigilance.handle_create_safety_case, True),
    ("GET", r"^/api/v1/safety/cases$", pharmacovigilance.handle_list_safety_cases, True),
    ("GET", r"^/api/v1/safety/cases/(?P<id>[^/]+)$", pharmacovigilance.handle_get_safety_case, True),
    ("POST", r"^/api/v1/safety/cases/(?P<id>[^/]+)/events$", pharmacovigilance.handle_add_safety_event, True),
    ("POST", r"^/api/v1/safety/cases/(?P<id>[^/]+)/exposures$", pharmacovigilance.handle_add_suspected_exposure, True),
    ("POST", r"^/api/v1/safety/cases/(?P<id>[^/]+)/triage$", pharmacovigilance.handle_update_triage, True),
    ("POST", r"^/api/v1/safety/cases/(?P<id>[^/]+)/assessments$", pharmacovigilance.handle_record_assessment, True),
    ("POST", r"^/api/v1/safety/assessments/(?P<id>[^/]+)/review$", pharmacovigilance.handle_review_assessment, True),
    ("POST", r"^/api/v1/safety/cases/(?P<id>[^/]+)/follow-up-tasks$", pharmacovigilance.handle_create_follow_up_task, True),
    ("POST", r"^/api/v1/safety/follow-up-tasks/(?P<id>[^/]+)/attempt$", pharmacovigilance.handle_record_follow_up_attempt, True),
    ("POST", r"^/api/v1/safety/cases/(?P<id>[^/]+)/links$", pharmacovigilance.handle_link_cases, True),
    ("GET", r"^/api/v1/safety/regulatory-profiles$", pharmacovigilance.handle_list_regulatory_profiles, True),
    ("POST", r"^/api/v1/safety/regulatory-profiles/(?P<id>[^/]+)/verify$", pharmacovigilance.handle_verify_regulatory_profile, True),
    ("POST", r"^/api/v1/safety/cases/(?P<id>[^/]+)/report-package$", pharmacovigilance.handle_build_report_package, True),
    ("POST", r"^/api/v1/safety/submissions/(?P<id>[^/]+)/authorize$", pharmacovigilance.handle_authorize_submission, True),
    ("POST", r"^/api/v1/safety/submissions/(?P<id>[^/]+)/dispatch$", pharmacovigilance.handle_dispatch_submission, True),
    ("GET", r"^/api/v1/safety/submissions/(?P<id>[^/]+)$", pharmacovigilance.handle_get_submission, True),
    ("POST", r"^/api/v1/safety/signals$", pharmacovigilance.handle_create_or_update_signal, True),
    ("GET", r"^/api/v1/safety/signals$", pharmacovigilance.handle_list_signals, True),
    ("POST", r"^/api/v1/safety/signals/(?P<id>[^/]+)/review$", pharmacovigilance.handle_review_signal, True),

    # Prompt 28: Clinical Knowledge Governance, Rule Versioning & Controlled Release
    ("POST", r"^/api/v1/governance/artifacts$", governance.handle_create_artifact, True),
    ("GET", r"^/api/v1/governance/artifacts$", governance.handle_list_artifacts, True),
    ("GET", r"^/api/v1/governance/artifacts/(?P<id>[^/]+)$", governance.handle_get_artifact, True),
    ("POST", r"^/api/v1/governance/artifacts/(?P<id>[^/]+)/versions$", governance.handle_create_artifact_version, True),
    ("POST", r"^/api/v1/governance/versions/(?P<id>[^/]+)/transition$", governance.handle_transition_version_state, True),
    ("POST", r"^/api/v1/governance/rules$", governance.handle_create_clinical_rule, True),
    ("POST", r"^/api/v1/governance/rules/(?P<id>[^/]+)/tests$", governance.handle_execute_rule_tests, True),
    ("POST", r"^/api/v1/governance/versions/(?P<id>[^/]+)/impact$", governance.handle_analyze_impact, True),
    ("POST", r"^/api/v1/governance/releases$", governance.handle_create_release, True),
    ("GET", r"^/api/v1/governance/releases/(?P<id>[^/]+)$", governance.handle_get_release, True),
    ("POST", r"^/api/v1/governance/releases/(?P<id>[^/]+)/approve$", governance.handle_approve_release, True),
    ("POST", r"^/api/v1/governance/releases/(?P<id>[^/]+)/deploy$", governance.handle_deploy_release, True),
    ("POST", r"^/api/v1/governance/releases/(?P<id>[^/]+)/suspend$", governance.handle_suspend_release, True),
    ("POST", r"^/api/v1/governance/releases/(?P<id>[^/]+)/rollback$", governance.handle_rollback_release, True),
    ("POST", r"^/api/v1/governance/runtime/resolve$", governance.handle_resolve_runtime_versions, True),

    # Prompt 29: Clinical Audit, Accountability & Tamper-Evident Ledger
    ("POST", r"^/api/v1/audit/ledger/events$", audit_ledger.handle_record_event, True),
    ("GET", r"^/api/v1/audit/ledger/events$", audit_ledger.handle_query_ledger, True),
    ("GET", r"^/api/v1/audit/ledger/events/(?P<id>[^/]+)$", audit_ledger.handle_get_event, True),
    ("POST", r"^/api/v1/audit/ledger/events/(?P<id>[^/]+)/annotations$", audit_ledger.handle_add_annotation, True),
    ("POST", r"^/api/v1/audit/ledger/integrity-checks$", audit_ledger.handle_verify_integrity, True),
    ("GET", r"^/api/v1/audit/ledger/retention-policies$", audit_ledger.handle_list_retention_policies, True),
    ("POST", r"^/api/v1/audit/ledger/legal-holds$", audit_ledger.handle_place_legal_hold, True),
    ("POST", r"^/api/v1/audit/ledger/legal-holds/(?P<id>[^/]+)/release$", audit_ledger.handle_release_legal_hold, True),
    ("POST", r"^/api/v1/audit/ledger/exports$", audit_ledger.handle_export_evidence_package, True),

    # Prompt 30: Enterprise Security, Privacy, Consent & Identity Access Governance
    ("GET", r"^/api/v1/security/me$", security_governance.handle_security_me, True),
    ("GET", r"^/api/v1/security/sessions$", security_governance.handle_list_sessions, True),
    ("POST", r"^/api/v1/security/sessions/revoke$", security_governance.handle_revoke_session, True),
    ("POST", r"^/api/v1/security/step-up$", security_governance.handle_verify_step_up, True),
    ("POST", r"^/api/v1/security/credentials$", security_governance.handle_register_credential, True),
    ("POST", r"^/api/v1/security/credentials/(?P<id>[^/]+)/verify$", security_governance.handle_verify_credential, True),
    ("POST", r"^/api/v1/security/credentials/(?P<id>[^/]+)/suspend$", security_governance.handle_suspend_credential, True),
    ("GET", r"^/api/v1/security/consent-records$", security_governance.handle_list_consent_records, True),
    ("POST", r"^/api/v1/security/consent-records$", security_governance.handle_record_consent, True),
    ("POST", r"^/api/v1/security/consent-records/(?P<id>[^/]+)/withdraw$", security_governance.handle_withdraw_consent, True),
    ("POST", r"^/api/v1/security/delegations$", security_governance.handle_grant_delegation, True),
    ("POST", r"^/api/v1/security/delegations/(?P<id>[^/]+)/revoke$", security_governance.handle_revoke_delegation, True),
    ("POST", r"^/api/v1/security/break-glass$", security_governance.handle_request_break_glass, True),
    ("GET", r"^/api/v1/security/break-glass/(?P<id>[^/]+)$", security_governance.handle_get_break_glass, True),
    ("POST", r"^/api/v1/security/break-glass/(?P<id>[^/]+)/review$", security_governance.handle_review_break_glass, True),
    ("POST", r"^/api/v1/security/access-reviews$", security_governance.handle_create_access_review, True),
    ("POST", r"^/api/v1/security/access-reviews/(?P<id>[^/]+)/decisions$", security_governance.handle_record_access_decision, True),
    ("GET", r"^/api/v1/security/access-reviews$", security_governance.handle_list_access_reviews, True),
    ("POST", r"^/api/v1/security/policies$", security_governance.handle_create_security_policy, True),
    ("POST", r"^/api/v1/security/policies/evaluate$", security_governance.handle_evaluate_security_policy, True),
    ("GET", r"^/api/v1/security/audit/coverage$", security_governance.handle_get_audit_coverage, True),

    # Prompt 31: Enterprise Interoperability, FHIR APIs & ABDM Integration
    ("GET", r"^/api/v1/interop/specifications$", interoperability.handle_list_specifications, True),
    ("POST", r"^/api/v1/interop/specifications$", interoperability.handle_register_specification, True),
    ("POST", r"^/api/v1/interop/specifications/deprecate$", interoperability.handle_deprecate_specification, True),
    ("GET", r"^/api/v1/interop/terminology$", interoperability.handle_list_terminology_mappings, True),
    ("POST", r"^/api/v1/interop/terminology$", interoperability.handle_upsert_terminology_mapping, True),
    ("POST", r"^/api/v1/interop/fhir/export-encounter$", interoperability.handle_export_encounter_bundle, True),
    ("POST", r"^/api/v1/interop/abdm/verify-identity$", interoperability.handle_verify_abha_identity, True),
    ("POST", r"^/api/v1/interop/abdm/link-patient$", interoperability.handle_link_abha_to_patient, True),
    ("GET", r"^/api/v1/interop/abdm/care-contexts$", interoperability.handle_discover_care_contexts, True),
    ("POST", r"^/api/v1/interop/abdm/notify-context-link$", interoperability.handle_notify_context_linked, True),
    ("POST", r"^/api/v1/interop/abdm/consent-requests$", interoperability.handle_create_consent_request, True),
    ("POST", r"^/api/v1/interop/abdm/consent-status-callback$", interoperability.handle_consent_status_callback, True),
    ("POST", r"^/api/v1/interop/abdm/validate-consent-scope$", interoperability.handle_validate_consent_scope, True),
    ("POST", r"^/api/v1/interop/abdm/revoke-consent$", interoperability.handle_revoke_consent_artefact, True),
    ("POST", r"^/api/v1/interop/abdm/verify-hfr$", interoperability.handle_verify_hfr, True),
    ("POST", r"^/api/v1/interop/abdm/verify-hpr$", interoperability.handle_verify_hpr, True),
    ("POST", r"^/api/v1/interop/inbound/stage$", interoperability.handle_stage_inbound_record, True),
    ("GET", r"^/api/v1/interop/inbound/queue$", interoperability.handle_list_reconciliation_queue, True),
    ("POST", r"^/api/v1/interop/inbound/reconcile$", interoperability.handle_reconcile_record, True),
    ("POST", r"^/api/v1/interop/outbox/enqueue$", interoperability.handle_enqueue_outbox, True),
    ("GET", r"^/api/v1/interop/outbox/jobs$", interoperability.handle_list_outbox_jobs, True),
    ("POST", r"^/api/v1/interop/outbox/dispatch$", interoperability.handle_dispatch_outbox, True),
    ("POST", r"^/api/v1/interop/webhooks/verify$", interoperability.handle_verify_webhook, True),

    # Prompt 32: Enterprise Integration Operations, API Reliability & Queue Management
    ("GET", r"^/api/v1/ops/dashboard$", integration_ops.handle_get_dashboard_summary, True),
    ("GET", r"^/api/v1/ops/connectors$", integration_ops.handle_list_connectors, True),
    ("GET", r"^/api/v1/ops/connectors/(?P<id>[^/]+)$", integration_ops.handle_get_connector, True),
    ("POST", r"^/api/v1/ops/connectors/(?P<id>[^/]+)/health-snapshot$", integration_ops.handle_record_health_snapshot, True),
    ("POST", r"^/api/v1/ops/connectors/(?P<id>[^/]+)/circuit-breaker$", integration_ops.handle_update_circuit_breaker, True),
    ("POST", r"^/api/v1/ops/connectors/(?P<id>[^/]+)/disable$", integration_ops.handle_disable_connector, True),
    ("GET", r"^/api/v1/ops/jobs$", integration_ops.handle_list_jobs, True),
    ("POST", r"^/api/v1/ops/jobs$", integration_ops.handle_create_job, True),
    ("GET", r"^/api/v1/ops/jobs/(?P<id>[^/]+)$", integration_ops.handle_get_job, True),
    ("POST", r"^/api/v1/ops/jobs/(?P<id>[^/]+)/attempt$", integration_ops.handle_execute_job_attempt, True),
    ("POST", r"^/api/v1/ops/jobs/(?P<id>[^/]+)/transition$", integration_ops.handle_transition_job_state, True),
    ("POST", r"^/api/v1/ops/jobs/(?P<id>[^/]+)/reconcile$", integration_ops.handle_initiate_reconciliation, True),
    ("POST", r"^/api/v1/ops/callbacks$", integration_ops.handle_ingest_callback, True),
    ("POST", r"^/api/v1/ops/reconciliations/(?P<id>[^/]+)/resolve$", integration_ops.handle_resolve_reconciliation, True),
    ("GET", r"^/api/v1/ops/dead-letter$", integration_ops.handle_list_dead_letter_items, True),
    ("POST", r"^/api/v1/ops/dead-letter/(?P<id>[^/]+)/resolve$", integration_ops.handle_resolve_dead_letter_item, True),

    # Prompt 33: Enterprise Analytics, Operational Intelligence & Governance
    ("GET", r"^/api/v1/analytics/overview$", analytics.handle_get_executive_overview, True),
    ("GET", r"^/api/v1/analytics/clinic-operations$", analytics.handle_get_clinic_operations, True),
    ("GET", r"^/api/v1/analytics/patient-continuity$", analytics.handle_get_patient_continuity, True),
    ("GET", r"^/api/v1/analytics/finance$", analytics.handle_get_finance_metrics, True),
    ("GET", r"^/api/v1/analytics/finance-billing$", analytics.handle_get_finance_metrics, True),
    ("GET", r"^/api/v1/analytics/inventory$", analytics.handle_get_inventory_metrics, True),
    ("GET", r"^/api/v1/analytics/inventory-dispensing$", analytics.handle_get_inventory_metrics, True),
    ("GET", r"^/api/v1/analytics/clinical-governance$", analytics.handle_get_clinical_governance, True),
    ("GET", r"^/api/v1/analytics/governance-safety$", analytics.handle_get_clinical_governance, True),
    ("GET", r"^/api/v1/analytics/data-quality$", analytics.handle_get_data_quality, True),
    ("GET", r"^/api/v1/analytics/data-quality-readiness$", analytics.handle_get_data_quality, True),
    ("GET", r"^/api/v1/analytics/metrics$", analytics.handle_list_metrics, True),
    ("POST", r"^/api/v1/analytics/metrics$", analytics.handle_create_metric, True),
    ("GET", r"^/api/v1/analytics/metrics/(?P<key>[^/]+)$", analytics.handle_get_metric, True),
    ("POST", r"^/api/v1/analytics/metrics/(?P<id>[^/]+)/review$", analytics.handle_advance_metric_to_review, True),
    ("POST", r"^/api/v1/analytics/metrics/(?P<id>[^/]+)/approve$", analytics.handle_approve_metric, True),
    ("POST", r"^/api/v1/analytics/metrics/(?P<id>[^/]+)/retire$", analytics.handle_retire_metric, True),
    ("POST", r"^/api/v1/analytics/export$", analytics.handle_generate_export, True),
    ("GET", r"^/api/v1/analytics/reconciliation-exceptions$", analytics.handle_list_reconciliation_exceptions, True),
    ("POST", r"^/api/v1/analytics/reconciliation-exceptions$", analytics.handle_record_reconciliation_exception, True),
    ("POST", r"^/api/v1/analytics/reconciliation-exceptions/(?P<id>[^/]+)/resolve$", analytics.handle_resolve_reconciliation_exception, True),

    # Prompt 34: Clinical Operations Command Center & Capacity Planning
    ("GET", r"^/api/v1/command-center/live$", command_center.handle_get_live_operations, True),
    ("GET", r"^/api/v1/command-center/schedule$", command_center.handle_get_today_schedule, True),
    ("GET", r"^/api/v1/command-center/bottlenecks$", command_center.handle_get_workflow_bottlenecks, True),
    ("GET", r"^/api/v1/command-center/capacity$", command_center.handle_get_capacity_plan, True),
    ("POST", r"^/api/v1/command-center/capacity/simulate$", command_center.handle_simulate_capacity_scenario, True),
    ("GET", r"^/api/v1/command-center/capacity/scenarios$", command_center.handle_list_capacity_scenarios, True),
    ("GET", r"^/api/v1/command-center/workload$", command_center.handle_get_workload_distribution, True),
    ("GET", r"^/api/v1/command-center/alerts$", command_center.handle_list_operational_alerts, True),
    ("POST", r"^/api/v1/command-center/alerts/(?P<id>[^/]+)/acknowledge$", command_center.handle_acknowledge_alert, True),
    ("POST", r"^/api/v1/command-center/alerts/(?P<id>[^/]+)/resolve$", command_center.handle_resolve_alert, True),
    ("POST", r"^/api/v1/command-center/actions$", command_center.handle_perform_operational_action, True),

    # Prompt 35: Clinical Workflow Automation & Rules Engine
    ("GET", r"^/api/v1/workflow/rules$", workflow_automation.handle_list_rules, True),
    ("POST", r"^/api/v1/workflow/rules$", workflow_automation.handle_create_rule, True),
    ("GET", r"^/api/v1/workflow/rules/(?P<id>[^/]+)$", workflow_automation.handle_get_rule, True),
    ("PUT", r"^/api/v1/workflow/rules/(?P<id>[^/]+)$", workflow_automation.handle_update_rule, True),
    ("POST", r"^/api/v1/workflow/rules/(?P<id>[^/]+)/advance$", workflow_automation.handle_advance_rule_status, True),
    ("POST", r"^/api/v1/workflow/rules/(?P<id>[^/]+)/dry-run$", workflow_automation.handle_dry_run_rule, True),
    ("POST", r"^/api/v1/workflow/events$", workflow_automation.handle_ingest_event, True),
    ("GET", r"^/api/v1/workflow/actions$", workflow_automation.handle_list_actions, True),
    ("POST", r"^/api/v1/workflow/actions/(?P<id>[^/]+)/approve$", workflow_automation.handle_approve_action, True),
    ("POST", r"^/api/v1/workflow/actions/(?P<id>[^/]+)/reject$", workflow_automation.handle_reject_action, True),
    ("POST", r"^/api/v1/workflow/actions/(?P<id>[^/]+)/retry$", workflow_automation.handle_retry_action, True),
    ("GET", r"^/api/v1/workflow/monitor$", workflow_automation.handle_get_workflow_monitor, True),

    # Prompt 36: Enterprise Workflow Intelligence, SLA Governance & Exception Resolution
    ("GET", r"^/api/v1/sla/policies$", sla_governance.handle_list_policies, True),
    ("POST", r"^/api/v1/sla/policies$", sla_governance.handle_create_policy, True),
    ("GET", r"^/api/v1/sla/policies/(?P<id>[^/]+)$", sla_governance.handle_get_policy, True),
    ("PUT", r"^/api/v1/sla/policies/(?P<id>[^/]+)$", sla_governance.handle_update_policy, True),
    ("POST", r"^/api/v1/sla/policies/(?P<id>[^/]+)/advance$", sla_governance.handle_advance_policy_status, True),
    ("GET", r"^/api/v1/sla/exceptions$", sla_governance.handle_list_exceptions, True),
    ("POST", r"^/api/v1/sla/exceptions$", sla_governance.handle_create_exception, True),
    ("GET", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)$", sla_governance.handle_get_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/acknowledge$", sla_governance.handle_acknowledge_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/assign$", sla_governance.handle_assign_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/start$", sla_governance.handle_start_work_on_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/pause$", sla_governance.handle_pause_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/resume$", sla_governance.handle_resume_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/resolve$", sla_governance.handle_resolve_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/verify$", sla_governance.handle_verify_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/dismiss$", sla_governance.handle_dismiss_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/reopen$", sla_governance.handle_reopen_exception, True),
    ("POST", r"^/api/v1/sla/exceptions/(?P<id>[^/]+)/escalate$", sla_governance.handle_escalate_exception, True),
    ("GET", r"^/api/v1/sla/monitor$", sla_governance.handle_get_sla_monitor, True),

    # Prompt 37: Enterprise Workflow Simulation, Failure Injection & Recovery Validation
    ("GET", r"^/api/v1/simulation/scenarios$", simulation.handle_list_scenarios, True),
    ("POST", r"^/api/v1/simulation/scenarios$", simulation.handle_create_scenario, True),
    ("GET", r"^/api/v1/simulation/scenarios/(?P<id>[^/]+)$", simulation.handle_get_scenario, True),
    ("PUT", r"^/api/v1/simulation/scenarios/(?P<id>[^/]+)$", simulation.handle_update_scenario, True),
    ("POST", r"^/api/v1/simulation/scenarios/(?P<id>[^/]+)/advance$", simulation.handle_advance_scenario_status, True),
    ("POST", r"^/api/v1/simulation/scenarios/(?P<id>[^/]+)/run$", simulation.handle_launch_simulation_run, True),
    ("GET", r"^/api/v1/simulation/runs$", simulation.handle_list_simulation_runs, True),
    ("POST", r"^/api/v1/simulation/runs$", simulation.handle_launch_simulation_run, True),
    ("GET", r"^/api/v1/simulation/runs/(?P<id>[^/]+)$", simulation.handle_get_simulation_run, True),
    ("POST", r"^/api/v1/simulation/runs/(?P<id>[^/]+)/cleanup$", simulation.handle_cleanup_simulation_run, True),
    ("POST", r"^/api/v1/simulation/release-gate$", simulation.handle_evaluate_release_gate, True),
    ("GET", r"^/api/v1/simulation/pulse$", simulation.handle_get_simulation_pulse, True),

    # Prompt 38: Production Release Engineering, Feature Flags & Rollback Orchestration
    ("GET", r"^/api/v1/releases/manifests$", release_governance.handle_list_releases, True),
    ("POST", r"^/api/v1/releases/manifests$", release_governance.handle_create_release, True),
    ("GET", r"^/api/v1/releases/manifests/(?P<id>[^/]+)$", release_governance.handle_get_release, True),
    ("PUT", r"^/api/v1/releases/manifests/(?P<id>[^/]+)$", release_governance.handle_update_release, True),
    ("POST", r"^/api/v1/releases/manifests/(?P<id>[^/]+)/advance$", release_governance.handle_advance_release, True),
    ("POST", r"^/api/v1/releases/manifests/(?P<id>[^/]+)/gates$", release_governance.handle_record_gate_evaluation, True),
    ("POST", r"^/api/v1/releases/manifests/(?P<id>[^/]+)/deploy$", release_governance.handle_deploy_release, True),
    ("POST", r"^/api/v1/releases/manifests/(?P<id>[^/]+)/rollback$", release_governance.handle_rollback_release, True),
    ("GET", r"^/api/v1/flags$", release_governance.handle_list_flags, True),
    ("POST", r"^/api/v1/flags$", release_governance.handle_create_flag, True),
    ("GET", r"^/api/v1/flags/(?P<id>[^/]+)$", release_governance.handle_get_flag, True),
    ("PUT", r"^/api/v1/flags/(?P<id>[^/]+)$", release_governance.handle_update_flag, True),
    ("POST", r"^/api/v1/flags/(?P<id>[^/]+)/emergency-disable$", release_governance.handle_toggle_emergency_disable, True),
    ("GET", r"^/api/v1/flags/evaluate$", release_governance.handle_evaluate_flag, True),
    ("POST", r"^/api/v1/flags/evaluate$", release_governance.handle_evaluate_flag, True),
    ("GET", r"^/api/v1/releases/pulse$", release_governance.handle_get_release_pulse, True),

    # Prompt 39: Production Observability, Alerting, SLOs & Incident Response
    ("GET", r"^/api/v1/observability/services$", observability.handle_list_services, True),
    ("GET", r"^/api/v1/observability/diagnostics/deep$", observability.handle_deep_diagnostics, True),
    ("POST", r"^/api/v1/observability/metrics$", observability.handle_record_metric, True),
    ("GET", r"^/api/v1/observability/metrics/summary$", observability.handle_query_metrics_summary, True),
    ("GET", r"^/api/v1/observability/alerts/definitions$", observability.handle_list_alert_definitions, True),
    ("POST", r"^/api/v1/observability/alerts/definitions$", observability.handle_create_alert_definition, True),
    ("POST", r"^/api/v1/observability/alerts/evaluate$", observability.handle_evaluate_alerts, True),
    ("GET", r"^/api/v1/observability/alerts/instances$", observability.handle_list_alert_instances, True),
    ("POST", r"^/api/v1/observability/alerts/instances/(?P<id>[^/]+)/acknowledge$", observability.handle_acknowledge_alert_instance, True),
    ("POST", r"^/api/v1/observability/alerts/instances/(?P<id>[^/]+)/resolve$", observability.handle_resolve_alert_instance, True),
    ("GET", r"^/api/v1/observability/slos$", observability.handle_list_slos, True),
    ("POST", r"^/api/v1/observability/slos$", observability.handle_create_slo, True),
    ("POST", r"^/api/v1/observability/slos/(?P<id>[^/]+)/approve$", observability.handle_approve_slo, True),
    ("POST", r"^/api/v1/observability/slos/events$", observability.handle_record_slo_events, True),
    ("GET", r"^/api/v1/observability/incidents$", observability.handle_list_incidents, True),
    ("POST", r"^/api/v1/observability/incidents$", observability.handle_create_incident, True),
    ("GET", r"^/api/v1/observability/incidents/(?P<id>[^/]+)$", observability.handle_get_incident, True),
    ("POST", r"^/api/v1/observability/incidents/(?P<id>[^/]+)/transition$", observability.handle_transition_incident, True),
    ("POST", r"^/api/v1/observability/incidents/(?P<id>[^/]+)/timeline$", observability.handle_add_incident_timeline, True),
    ("POST", r"^/api/v1/observability/remediation$", observability.handle_execute_remediation, True),
    ("GET", r"^/api/v1/observability/pulse$", observability.handle_get_observability_pulse, True),

    # Prompt 40: Disaster Recovery, Business Continuity & Resilience Operations
    ("GET", r"^/api/v1/dr/domains$", disaster_recovery.handle_get_domain_catalog, True),
    ("PATCH", r"^/api/v1/dr/domains/(?P<id>[^/]+)$", disaster_recovery.handle_update_domain_policy, True),
    ("POST", r"^/api/v1/dr/backups$", disaster_recovery.handle_create_online_backup, True),
    ("GET", r"^/api/v1/dr/backups$", disaster_recovery.handle_list_backups, True),
    ("POST", r"^/api/v1/dr/drills$", disaster_recovery.handle_execute_restore_drill, True),
    ("GET", r"^/api/v1/dr/drills$", disaster_recovery.handle_list_drills, True),
    ("GET", r"^/api/v1/dr/drills/(?P<id>[^/]+)$", disaster_recovery.handle_get_drill_details, True),
    ("POST", r"^/api/v1/dr/drills/(?P<id>[^/]+)/sign-off$", disaster_recovery.handle_sign_off_drill, True),
    ("GET", r"^/api/v1/dr/runbooks$", disaster_recovery.handle_list_runbooks, True),
    ("POST", r"^/api/v1/dr/reconciliation$", disaster_recovery.handle_ingest_downtime_record, True),
    ("GET", r"^/api/v1/dr/reconciliation$", disaster_recovery.handle_list_reconciliation_queue, True),
    ("POST", r"^/api/v1/dr/reconciliation/(?P<id>[^/]+)/resolve$", disaster_recovery.handle_resolve_downtime_record, True),
    ("GET", r"^/api/v1/dr/pulse$", disaster_recovery.handle_get_dr_pulse, True),
 
     # Prompt 41: Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Governance
     ("GET", r"^/api/v1/lifecycle/inventory$", data_lifecycle.handle_get_inventory, True),
     ("GET", r"^/api/v1/lifecycle/policies$", data_lifecycle.handle_get_policies, True),
     ("POST", r"^/api/v1/lifecycle/policies$", data_lifecycle.handle_create_policy, True),
     ("POST", r"^/api/v1/lifecycle/policies/(?P<id>[^/]+)/approve$", data_lifecycle.handle_approve_policy, True),
     ("POST", r"^/api/v1/lifecycle/evaluations/dry-run$", data_lifecycle.handle_evaluate_dry_run, True),
     ("POST", r"^/api/v1/lifecycle/operations/execute$", data_lifecycle.handle_execute_disposal, True),
     ("GET", r"^/api/v1/lifecycle/holds$", data_lifecycle.handle_list_legal_holds, True),
     ("POST", r"^/api/v1/lifecycle/holds$", data_lifecycle.handle_place_legal_hold, True),
     ("POST", r"^/api/v1/lifecycle/holds/(?P<id>[^/]+)/release$", data_lifecycle.handle_release_legal_hold, True),
     ("GET", r"^/api/v1/lifecycle/requests$", data_lifecycle.handle_list_privacy_requests, True),
     ("POST", r"^/api/v1/lifecycle/requests$", data_lifecycle.handle_ingest_privacy_request, True),
     ("POST", r"^/api/v1/lifecycle/requests/(?P<id>[^/]+)/verify-identity$", data_lifecycle.handle_verify_request_identity, True),
     ("POST", r"^/api/v1/lifecycle/requests/(?P<id>[^/]+)/approve$", data_lifecycle.handle_approve_request_plan, True),
     ("POST", r"^/api/v1/lifecycle/requests/(?P<id>[^/]+)/execute$", data_lifecycle.handle_execute_request_plan, True),
     ("GET", r"^/api/v1/lifecycle/pulse$", data_lifecycle.handle_get_lifecycle_pulse, True),

     # Prompt 42: Enterprise Master Data Management, Data Governance & Data Quality Stewardship
     ("GET", r"^/api/v1/mdm/entities$", data_governance.handle_get_master_entities, True),
     ("POST", r"^/api/v1/mdm/entities$", data_governance.handle_register_master_entity, True),
     ("GET", r"^/api/v1/mdm/rules$", data_governance.handle_list_dq_rules, True),
     ("POST", r"^/api/v1/mdm/rules$", data_governance.handle_create_dq_rule, True),
     ("POST", r"^/api/v1/mdm/scans/run$", data_governance.handle_run_dq_scan, True),
     ("GET", r"^/api/v1/mdm/scans$", data_governance.handle_list_dq_scans, True),
     ("GET", r"^/api/v1/mdm/scans/(?P<id>[^/]+)/findings$", data_governance.handle_get_scan_findings, True),
     ("POST", r"^/api/v1/mdm/duplicates/detect$", data_governance.handle_detect_duplicate_candidates, True),
     ("GET", r"^/api/v1/mdm/duplicates/reviews$", data_governance.handle_list_duplicate_reviews, True),
     ("POST", r"^/api/v1/mdm/duplicates/reviews/(?P<id>[^/]+)/resolve$", data_governance.handle_resolve_duplicate_review, True),
     ("GET", r"^/api/v1/mdm/cross-references$", data_governance.handle_list_cross_references, True),
     ("POST", r"^/api/v1/mdm/cross-references$", data_governance.handle_create_cross_reference, True),
     ("POST", r"^/api/v1/mdm/cross-references/(?P<id>[^/]+)/unlink$", data_governance.handle_unlink_cross_reference, True),
     ("GET", r"^/api/v1/mdm/terminology/mappings$", data_governance.handle_list_terminology_mappings, True),
     ("POST", r"^/api/v1/mdm/terminology/mappings$", data_governance.handle_create_terminology_mapping, True),
     ("POST", r"^/api/v1/mdm/terminology/mappings/(?P<id>[^/]+)/review$", data_governance.handle_review_terminology_mapping, True),
     ("POST", r"^/api/v1/mdm/imports/stage$", data_governance.handle_stage_import_batch, True),
     ("POST", r"^/api/v1/mdm/imports/(?P<id>[^/]+)/dry-run$", data_governance.handle_evaluate_import_dry_run, True),
     ("POST", r"^/api/v1/mdm/imports/(?P<id>[^/]+)/commit$", data_governance.handle_commit_import_batch, True),
     ("GET", r"^/api/v1/mdm/imports$", data_governance.handle_list_import_batches, True),
     ("POST", r"^/api/v1/mdm/stewardship/cases$", data_governance.handle_create_stewardship_case, True),
     ("GET", r"^/api/v1/mdm/stewardship/cases$", data_governance.handle_list_stewardship_cases, True),
     ("POST", r"^/api/v1/mdm/stewardship/cases/(?P<id>[^/]+)/transition$", data_governance.handle_transition_stewardship_case, True),
     ("GET", r"^/api/v1/mdm/stewardship/cases/(?P<id>[^/]+)/events$", data_governance.handle_get_stewardship_case_events, True),
     ("GET", r"^/api/v1/mdm/pulse$", data_governance.handle_get_mdm_pulse, True),

     # Prompt 43: Enterprise Data Lineage, Schema Evolution & Change Impact Analysis
     ("GET", r"^/api/v1/lineage/contracts$", data_lineage.handle_get_contracts, True),
     ("POST", r"^/api/v1/lineage/contracts$", data_lineage.handle_create_contract, True),
     ("GET", r"^/api/v1/lineage/contracts/(?P<id>[^/]+)$", data_lineage.handle_get_contract, True),
     ("GET", r"^/api/v1/lineage/nodes$", data_lineage.handle_get_nodes, True),
     ("POST", r"^/api/v1/lineage/nodes$", data_lineage.handle_register_node, True),
     ("GET", r"^/api/v1/lineage/nodes/(?P<id>[^/]+)$", data_lineage.handle_get_node, True),
     ("GET", r"^/api/v1/lineage/edges$", data_lineage.handle_get_edges, True),
     ("POST", r"^/api/v1/lineage/edges$", data_lineage.handle_create_edge, True),
     ("DELETE", r"^/api/v1/lineage/edges/(?P<id>[^/]+)$", data_lineage.handle_delete_edge, True),
     ("GET", r"^/api/v1/lineage/trace/(?P<id>[^/]+)$", data_lineage.handle_trace_lineage, True),
     ("GET", r"^/api/v1/lineage/change-requests$", data_lineage.handle_list_change_requests, True),
     ("POST", r"^/api/v1/lineage/change-requests$", data_lineage.handle_create_change_request, True),
     ("GET", r"^/api/v1/lineage/change-requests/(?P<id>[^/]+)$", data_lineage.handle_get_change_request, True),
     ("POST", r"^/api/v1/lineage/change-requests/(?P<id>[^/]+)/analyze$", data_lineage.handle_analyze_impact, True),
     ("POST", r"^/api/v1/lineage/change-requests/(?P<id>[^/]+)/reviews$", data_lineage.handle_submit_review, True),
     ("POST", r"^/api/v1/lineage/change-requests/(?P<id>[^/]+)/transition$", data_lineage.handle_transition_change_request, True),
     ("GET", r"^/api/v1/lineage/summary$", data_lineage.handle_get_lineage_summary, True),

     # Prompt 44: Enterprise Configuration, Secrets & Environment Governance
     ("GET", r"^/api/v1/config/settings$", config_governance.handle_get_settings, True),
     ("POST", r"^/api/v1/config/settings$", config_governance.handle_register_setting, True),
     ("GET", r"^/api/v1/config/settings/(?P<id>[^/]+)$", config_governance.handle_get_setting, True),
     ("GET", r"^/api/v1/config/public$", config_governance.handle_get_public_config, False),
     ("GET", r"^/api/v1/config/environments$", config_governance.handle_get_environments, True),
     ("GET", r"^/api/v1/config/environments/(?P<code>[^/]+)$", config_governance.handle_get_environment, True),
     ("POST", r"^/api/v1/config/environments/isolation-check$", config_governance.handle_validate_isolation, True),
     ("POST", r"^/api/v1/config/preflight$", config_governance.handle_run_preflight, True),
     ("GET", r"^/api/v1/config/secrets$", config_governance.handle_get_secret_references, True),
     ("POST", r"^/api/v1/config/secrets$", config_governance.handle_register_secret_reference, True),
     ("GET", r"^/api/v1/config/secrets/(?P<id>[^/]+)$", config_governance.handle_get_secret_reference, True),
     ("POST", r"^/api/v1/config/secrets/rotate$", config_governance.handle_initiate_rotation, True),
     ("POST", r"^/api/v1/config/rotations/(?P<id>[^/]+)/advance$", config_governance.handle_advance_rotation, True),
     ("POST", r"^/api/v1/config/secrets/(?P<id>[^/]+)/revoke-compromised$", config_governance.handle_urgent_revocation, True),
     ("GET", r"^/api/v1/config/proposals$", config_governance.handle_list_proposals, True),
     ("POST", r"^/api/v1/config/proposals$", config_governance.handle_create_proposal, True),
     ("GET", r"^/api/v1/config/proposals/(?P<id>[^/]+)$", config_governance.handle_get_proposal, True),
     ("POST", r"^/api/v1/config/proposals/(?P<id>[^/]+)/approve$", config_governance.handle_approve_proposal, True),
     ("POST", r"^/api/v1/config/proposals/(?P<id>[^/]+)/apply$", config_governance.handle_apply_proposal, True),
     ("POST", r"^/api/v1/config/proposals/(?P<id>[^/]+)/rollback$", config_governance.handle_rollback_proposal, True),
     ("POST", r"^/api/v1/config/drift/scans/run$", config_governance.handle_run_drift_scan, True),
     ("GET", r"^/api/v1/config/drift/scans$", config_governance.handle_get_drift_scans, True),
     ("GET", r"^/api/v1/config/audit$", config_governance.handle_get_audit_ledger, True),
     ("GET", r"^/api/v1/config/summary$", config_governance.handle_get_governance_summary, True),

     # Prompt 45: Enterprise Identity Governance, Privileged Access Management (PAM) & Access Certification
     ("GET", r"^/api/v1/identity/summary$", identity_governance.handle_get_identity_summary, True),
     ("GET", r"^/api/v1/identity/principals$", identity_governance.handle_list_principals, True),
     ("POST", r"^/api/v1/identity/principals$", identity_governance.handle_create_principal, True),
     ("GET", r"^/api/v1/identity/principals/(?P<id>[^/]+)$", identity_governance.handle_get_principal, True),
     ("POST", r"^/api/v1/identity/principals/(?P<id>[^/]+)/mover$", identity_governance.handle_mover_transition, True),
     ("POST", r"^/api/v1/identity/principals/(?P<id>[^/]+)/leaver$", identity_governance.handle_leaver_offboarding, True),
     ("GET", r"^/api/v1/identity/users/(?P<id>[^/]+)/effective-access$", identity_governance.handle_verify_effective_access, True),
     ("GET", r"^/api/v1/identity/privileges$", identity_governance.handle_list_privileges, True),
     ("GET", r"^/api/v1/identity/elevations$", identity_governance.handle_list_elevations, True),
     ("POST", r"^/api/v1/identity/elevations$", identity_governance.handle_request_elevation, True),
     ("POST", r"^/api/v1/identity/elevations/(?P<id>[^/]+)/approve$", identity_governance.handle_approve_elevation, True),
     ("POST", r"^/api/v1/identity/elevations/(?P<id>[^/]+)/activate$", identity_governance.handle_activate_elevation, True),
     ("POST", r"^/api/v1/identity/elevations/(?P<id>[^/]+)/revoke$", identity_governance.handle_revoke_elevation, True),
     ("GET", r"^/api/v1/identity/break-glass$", identity_governance.handle_list_break_glass, True),
     ("POST", r"^/api/v1/identity/break-glass$", identity_governance.handle_activate_break_glass, True),
     ("POST", r"^/api/v1/identity/break-glass/(?P<id>[^/]+)/action$", identity_governance.handle_record_break_glass_action, True),
     ("POST", r"^/api/v1/identity/break-glass/(?P<id>[^/]+)/review$", identity_governance.handle_review_break_glass, True),
     ("GET", r"^/api/v1/identity/service-accounts$", identity_governance.handle_list_service_accounts, True),
     ("POST", r"^/api/v1/identity/service-accounts$", identity_governance.handle_register_service_account, True),
     ("POST", r"^/api/v1/identity/service-accounts/(?P<id>[^/]+)/deprovision$", identity_governance.handle_deprovision_service_account, True),
     ("GET", r"^/api/v1/identity/campaigns$", identity_governance.handle_list_campaigns, True),
     ("POST", r"^/api/v1/identity/campaigns$", identity_governance.handle_create_campaign, True),
     ("GET", r"^/api/v1/identity/campaigns/(?P<id>[^/]+)/items$", identity_governance.handle_list_campaign_items, True),
     ("POST", r"^/api/v1/identity/certification-items/(?P<id>[^/]+)/decision$", identity_governance.handle_record_certification_decision, True),
     ("GET", r"^/api/v1/identity/remediations$", identity_governance.handle_list_remediations, True),
     ("POST", r"^/api/v1/identity/remediations/(?P<id>[^/]+)/execute$", identity_governance.handle_execute_remediation, True),
     ("POST", r"^/api/v1/identity/remediations/(?P<id>[^/]+)/verify$", identity_governance.handle_verify_remediation, True),
     ("GET", r"^/api/v1/identity/sod-rules$", identity_governance.handle_list_sod_rules, True),
     ("POST", r"^/api/v1/identity/sod-rules/check$", identity_governance.handle_check_sod_rules, True),
     ("GET", r"^/api/v1/identity/audit-ledger$", identity_governance.handle_list_identity_audit_ledger, True),

     # Prompt 46: Enterprise Security Posture, Vulnerability Governance & Verification
     ("GET", r"^/api/v1/security-posture/summary$", security_posture.handle_get_security_summary, True),
     ("GET", r"^/api/v1/security-posture/assets$", security_posture.handle_list_security_assets, True),
     ("POST", r"^/api/v1/security-posture/assets$", security_posture.handle_register_security_asset, True),
     ("GET", r"^/api/v1/security-posture/controls$", security_posture.handle_list_security_controls, True),
     ("POST", r"^/api/v1/security-posture/scans/run-all$", security_posture.handle_run_all_security_scans, True),
     ("POST", r"^/api/v1/security-posture/scans/sca$", security_posture.handle_run_sca_scan, True),
     ("POST", r"^/api/v1/security-posture/scans/secrets$", security_posture.handle_run_secret_scan, True),
     ("POST", r"^/api/v1/security-posture/scans/api-authz$", security_posture.handle_run_api_authz_scan, True),
     ("POST", r"^/api/v1/security-posture/scans/container$", security_posture.handle_run_container_scan, True),
     ("POST", r"^/api/v1/security-posture/scans/sql-param$", security_posture.handle_run_sql_param_scan, True),
     ("GET", r"^/api/v1/security-posture/findings$", security_posture.handle_list_findings, True),
     ("POST", r"^/api/v1/security-posture/findings$", security_posture.handle_create_finding, True),
     ("GET", r"^/api/v1/security-posture/findings/(?P<id>[^/]+)$", security_posture.handle_get_finding, True),
     ("POST", r"^/api/v1/security-posture/findings/(?P<id>[^/]+)/transition$", security_posture.handle_transition_finding, True),
     ("GET", r"^/api/v1/security-posture/exceptions$", security_posture.handle_list_exceptions, True),
     ("POST", r"^/api/v1/security-posture/exceptions$", security_posture.handle_request_exception, True),
     ("GET", r"^/api/v1/security-posture/gates$", security_posture.handle_list_gate_evaluations, True),
     ("POST", r"^/api/v1/security-posture/gates/evaluate$", security_posture.handle_evaluate_release_gate, True),
     ("GET", r"^/api/v1/security-posture/audit-ledger$", security_posture.handle_list_security_audit_ledger, True),

     # Prompt 47: Threat Modeling, Abuse-Case Analysis & Secure SDLC Governance Engine
     ("GET", r"^/api/v1/threat-modeling/dashboard-summary$", threat_modeling.handle_get_threat_modeling_summary, True),
     ("GET", r"^/api/v1/threat-modeling/models$", threat_modeling.handle_list_threat_models, True),
     ("POST", r"^/api/v1/threat-modeling/models$", threat_modeling.handle_create_threat_model, True),
     ("GET", r"^/api/v1/threat-modeling/models/(?P<id>[^/]+)$", threat_modeling.handle_get_threat_model, True),
     ("POST", r"^/api/v1/threat-modeling/models/(?P<id>[^/]+)/transition$", threat_modeling.handle_transition_model_state, True),
     ("POST", r"^/api/v1/threat-modeling/models/check-stale$", threat_modeling.handle_check_stale_models, True),
     ("GET", r"^/api/v1/threat-modeling/trust-boundaries$", threat_modeling.handle_list_trust_boundaries, True),
     ("POST", r"^/api/v1/threat-modeling/trust-boundaries$", threat_modeling.handle_create_trust_boundary, True),
     ("GET", r"^/api/v1/threat-modeling/abuse-cases$", threat_modeling.handle_list_abuse_cases, True),
     ("POST", r"^/api/v1/threat-modeling/abuse-cases$", threat_modeling.handle_create_abuse_case, True),
     ("GET", r"^/api/v1/threat-modeling/abuse-cases/(?P<id>[^/]+)$", threat_modeling.handle_get_abuse_case, True),
     ("POST", r"^/api/v1/threat-modeling/abuse-cases/(?P<id>[^/]+)/transition$", threat_modeling.handle_transition_abuse_case, True),
     ("GET", r"^/api/v1/threat-modeling/controls$", threat_modeling.handle_list_testable_controls, True),
     ("POST", r"^/api/v1/threat-modeling/controls$", threat_modeling.handle_create_testable_control, True),
     ("POST", r"^/api/v1/threat-modeling/controls/(?P<id>[^/]+)/verify$", threat_modeling.handle_verify_control, True),
     ("GET", r"^/api/v1/threat-modeling/residual-risks$", threat_modeling.handle_list_residual_risks, True),
     ("POST", r"^/api/v1/threat-modeling/residual-risks$", threat_modeling.handle_create_residual_risk, True),
     ("POST", r"^/api/v1/threat-modeling/residual-risks/(?P<id>[^/]+)/revoke$", threat_modeling.handle_revoke_residual_risk, True),
     ("GET", r"^/api/v1/threat-modeling/change-reviews$", threat_modeling.handle_list_change_reviews, True),
     ("POST", r"^/api/v1/threat-modeling/change-reviews$", threat_modeling.handle_create_change_review, True),
     ("POST", r"^/api/v1/threat-modeling/change-reviews/(?P<id>[^/]+)/evaluate$", threat_modeling.handle_evaluate_sdlc_gate, True),
     ("GET", r"^/api/v1/threat-modeling/audit-ledger$", threat_modeling.handle_get_threat_audit_ledger, True),

     # Prompt 48: Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine
     ("GET", r"^/api/v1/safety-case/summary$", clinical_safety.handle_get_clinical_safety_summary, True),
     ("GET", r"^/api/v1/safety-case/intended-use$", clinical_safety.handle_list_intended_uses, True),
     ("POST", r"^/api/v1/safety-case/intended-use$", clinical_safety.handle_register_intended_use, True),
     ("GET", r"^/api/v1/safety-case/intended-use/(?P<id>[^/]+)$", clinical_safety.handle_get_intended_use, True),
     ("GET", r"^/api/v1/safety-case/hazards$", clinical_safety.handle_list_hazards, True),
     ("POST", r"^/api/v1/safety-case/hazards$", clinical_safety.handle_create_hazard, True),
     ("GET", r"^/api/v1/safety-case/hazards/(?P<id>[^/]+)$", clinical_safety.handle_get_hazard, True),
     ("POST", r"^/api/v1/safety-case/hazards/(?P<id>[^/]+)/status$", clinical_safety.handle_update_hazard_status, True),
     ("GET", r"^/api/v1/safety-case/requirements$", clinical_safety.handle_list_requirements, True),
     ("POST", r"^/api/v1/safety-case/requirements$", clinical_safety.handle_create_requirement, True),
     ("GET", r"^/api/v1/safety-case/requirements/(?P<id>[^/]+)$", clinical_safety.handle_get_requirement, True),
     ("POST", r"^/api/v1/safety-case/verifications$", clinical_safety.handle_record_control_verification, True),
     ("GET", r"^/api/v1/safety-case/verifications$", clinical_safety.handle_list_verifications, True),
     ("GET", r"^/api/v1/safety-case/cases$", clinical_safety.handle_list_safety_cases, True),
     ("POST", r"^/api/v1/safety-case/cases$", clinical_safety.handle_create_safety_case, True),
     ("GET", r"^/api/v1/safety-case/cases/(?P<id>[^/]+)$", clinical_safety.handle_get_safety_case, True),
     ("POST", r"^/api/v1/safety-case/cases/(?P<id>[^/]+)/review$", clinical_safety.handle_review_safety_case, True),
     ("GET", r"^/api/v1/safety-case/incidents$", clinical_safety.handle_list_incidents, True),
     ("POST", r"^/api/v1/safety-case/incidents$", clinical_safety.handle_report_incident, True),
     ("GET", r"^/api/v1/safety-case/incidents/(?P<id>[^/]+)$", clinical_safety.handle_get_incident, True),
     ("POST", r"^/api/v1/safety-case/incidents/(?P<id>[^/]+)/triage$", clinical_safety.handle_triage_incident, True),
     ("POST", r"^/api/v1/safety-case/release-gates/evaluate$", clinical_safety.handle_evaluate_release_gate, True),
     ("GET", r"^/api/v1/safety-case/release-gates$", clinical_safety.handle_list_release_gates, True),
     ("GET", r"^/api/v1/safety-case/traceability$", clinical_safety.handle_get_traceability_matrix, True),
     ("GET", r"^/api/v1/safety-case/audit$", clinical_safety.handle_get_audit_trail, True),
     ("POST", r"^/api/v1/safety-case/audit/verify$", clinical_safety.handle_verify_audit_integrity, True),

     # Prompt 49: End-to-End Test Automation, Regression & Release Qualification
     ("GET", r"^/api/v1/test-qualification/summary$", test_automation.handle_get_test_qualification_summary, True),
     ("GET", r"^/api/v1/test-qualification/suites$", test_automation.handle_list_test_suites, True),
     ("POST", r"^/api/v1/test-qualification/suites$", test_automation.handle_register_test_suite, True),
     ("GET", r"^/api/v1/test-qualification/suites/(?P<id>[^/]+)$", test_automation.handle_get_test_suite, True),
     ("PUT", r"^/api/v1/test-qualification/suites/(?P<id>[^/]+)$", test_automation.handle_update_test_suite, True),
     ("GET", r"^/api/v1/test-qualification/runs$", test_automation.handle_list_execution_runs, True),
     ("POST", r"^/api/v1/test-qualification/runs$", test_automation.handle_record_execution_run, True),
     ("GET", r"^/api/v1/test-qualification/runs/(?P<id>[^/]+)$", test_automation.handle_get_execution_run, True),
     ("GET", r"^/api/v1/test-qualification/quarantines$", test_automation.handle_list_quarantined_tests, True),
     ("POST", r"^/api/v1/test-qualification/quarantines$", test_automation.handle_quarantine_test, True),
     ("GET", r"^/api/v1/test-qualification/quarantines/(?P<id>[^/]+)$", test_automation.handle_get_quarantined_test, True),
     ("POST", r"^/api/v1/test-qualification/quarantines/(?P<id>[^/]+)/resolve$", test_automation.handle_resolve_quarantine, True),
     ("GET", r"^/api/v1/test-qualification/profiles$", test_automation.handle_list_qualification_profiles, True),
     ("POST", r"^/api/v1/test-qualification/profiles$", test_automation.handle_create_qualification_profile, True),
     ("GET", r"^/api/v1/test-qualification/profiles/(?P<id>[^/]+)$", test_automation.handle_get_qualification_profile, True),
     ("GET", r"^/api/v1/test-qualification/candidates$", test_automation.handle_list_candidate_qualifications, True),
     ("POST", r"^/api/v1/test-qualification/candidates/evaluate$", test_automation.handle_evaluate_release_candidate, True),
     ("GET", r"^/api/v1/test-qualification/candidates/(?P<id>[^/]+)$", test_automation.handle_get_candidate_qualification, True),
     ("GET", r"^/api/v1/test-qualification/defects$", test_automation.handle_list_defects, True),
     ("POST", r"^/api/v1/test-qualification/defects$", test_automation.handle_log_defect, True),
     ("GET", r"^/api/v1/test-qualification/defects/(?P<id>[^/]+)$", test_automation.handle_get_defect, True),
     ("POST", r"^/api/v1/test-qualification/defects/(?P<id>[^/]+)/status$", test_automation.handle_update_defect_status, True),
     ("GET", r"^/api/v1/test-qualification/audit$", test_automation.handle_get_audit_ledger, True),
     ("POST", r"^/api/v1/test-qualification/audit/verify$", test_automation.handle_verify_audit_integrity, True),

     # Prompt 51: Accessibility, Localization, RTL & Clinical Human-Factors Engine
     ("GET", r"^/api/v1/a11y-i18n/locales$", accessibility_localization.handle_list_locales, True),
     ("POST", r"^/api/v1/a11y-i18n/locales$", accessibility_localization.handle_register_locale, True),
     ("GET", r"^/api/v1/a11y-i18n/catalogs$", accessibility_localization.handle_list_catalogs, True),
     ("POST", r"^/api/v1/a11y-i18n/catalogs$", accessibility_localization.handle_upsert_catalog_entry, True),
     ("POST", r"^/api/v1/a11y-i18n/catalogs/(?P<id>[^/]+)/review$", accessibility_localization.handle_review_catalog_entry, True),
     ("GET", r"^/api/v1/a11y-i18n/glossary$", accessibility_localization.handle_list_glossary, True),
     ("POST", r"^/api/v1/a11y-i18n/glossary$", accessibility_localization.handle_upsert_glossary_term, True),
     ("GET", r"^/api/v1/a11y-i18n/preferences/(?P<user_id>[^/]+)$", accessibility_localization.handle_get_user_preferences, True),
     ("PUT", r"^/api/v1/a11y-i18n/preferences/(?P<user_id>[^/]+)$", accessibility_localization.handle_update_user_preferences, True),
     ("GET", r"^/api/v1/a11y-i18n/a11y-audits$", accessibility_localization.handle_list_a11y_audits, True),
     ("POST", r"^/api/v1/a11y-i18n/a11y-audits$", accessibility_localization.handle_record_a11y_audit, True),
     ("GET", r"^/api/v1/a11y-i18n/human-factors/scenarios$", accessibility_localization.handle_list_human_factors_scenarios, True),
     ("POST", r"^/api/v1/a11y-i18n/human-factors/scenarios$", accessibility_localization.handle_record_human_factors_scenario, True),
     ("GET", r"^/api/v1/a11y-i18n/audit$", accessibility_localization.handle_get_audit_ledger, True),
     ("POST", r"^/api/v1/a11y-i18n/audit/verify$", accessibility_localization.handle_verify_audit_integrity, True),

     # Prompt 52: API & Integration Certification, Contract Testing & Developer Governance
     ("GET", r"^/api/v1/api-governance/integrations$", api_integration_certification.handle_list_integrations, True),
     ("POST", r"^/api/v1/api-governance/integrations$", api_integration_certification.handle_register_integration, True),
     ("GET", r"^/api/v1/api-governance/integrations/(?P<id>[^/]+)$", api_integration_certification.handle_get_integration, True),
     ("GET", r"^/api/v1/api-governance/contracts$", api_integration_certification.handle_list_contracts, True),
     ("POST", r"^/api/v1/api-governance/contracts$", api_integration_certification.handle_register_contract, True),
     ("POST", r"^/api/v1/api-governance/drift-check$", api_integration_certification.handle_contract_drift_check, True),
     ("GET", r"^/api/v1/api-governance/keys$", api_integration_certification.handle_list_api_keys, True),
     ("POST", r"^/api/v1/api-governance/keys$", api_integration_certification.handle_generate_api_key, True),
     ("POST", r"^/api/v1/api-governance/keys/(?P<id>[^/]+)/revoke$", api_integration_certification.handle_revoke_api_key, True),
     ("POST", r"^/api/v1/api-governance/idempotency/check$", api_integration_certification.handle_idempotency_check, True),
     ("POST", r"^/api/v1/api-governance/webhooks/verify-inbound$", api_integration_certification.handle_verify_inbound_webhook, True),
     ("POST", r"^/api/v1/api-governance/webhooks/subscriptions$", api_integration_certification.handle_create_webhook_subscription, True),
     ("POST", r"^/api/v1/api-governance/webhooks/subscriptions/(?P<id>[^/]+)/dispatch$", api_integration_certification.handle_dispatch_webhook, True),
     ("POST", r"^/api/v1/api-governance/certify$", api_integration_certification.handle_certify_integration, True),
     ("GET", r"^/api/v1/api-governance/certifications$", api_integration_certification.handle_list_certifications, True),
     ("GET", r"^/api/v1/api-governance/audit-ledger/verify$", api_integration_certification.handle_verify_ledger_integrity, True),

     # Performance, Scalability & Capacity Engineering (Prompt 54)
     ("GET", r"^/api/v1/performance/scenarios$", performance_scalability.handle_list_scenarios, True),
     ("POST", r"^/api/v1/performance/scenarios$", performance_scalability.handle_register_scenario, True),
     ("GET", r"^/api/v1/performance/scenarios/(?P<id>[^/]+)$", performance_scalability.handle_get_scenario, True),
     ("POST", r"^/api/v1/performance/scenarios/(?P<id>[^/]+)/run$", performance_scalability.handle_run_microbenchmark, True),
     ("POST", r"^/api/v1/performance/runs$", performance_scalability.handle_record_benchmark_run, True),
     ("GET", r"^/api/v1/performance/runs$", performance_scalability.handle_list_benchmark_runs, True),
     ("GET", r"^/api/v1/performance/slow-queries$", performance_scalability.handle_list_slow_queries, True),
     ("POST", r"^/api/v1/performance/slow-queries$", performance_scalability.handle_log_slow_query, True),
     ("GET", r"^/api/v1/performance/capacity-profiles$", performance_scalability.handle_list_capacity_profiles, True),
     ("POST", r"^/api/v1/performance/capacity-profiles/(?P<id>[^/]+)/evaluate$", performance_scalability.handle_evaluate_capacity_headroom, True),
     ("GET", r"^/api/v1/performance/circuit-breakers/(?P<id>[^/]+)$", performance_scalability.handle_get_circuit_breaker, True),
     ("POST", r"^/api/v1/performance/circuit-breakers/(?P<id>[^/]+)/trip$", performance_scalability.handle_trip_circuit_breaker, True),
     ("POST", r"^/api/v1/performance/circuit-breakers/(?P<id>[^/]+)/reset$", performance_scalability.handle_reset_circuit_breaker, True),
     ("GET", r"^/api/v1/performance/audit-ledger/verify$", performance_scalability.handle_verify_perf_audit_ledger, True),

     # Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance (Prompt 55)
     ("GET", r"^/api/v1/tenant-governance/tenants$", tenant_governance.handle_list_tenants, True),
     ("POST", r"^/api/v1/tenant-governance/tenants/provision$", tenant_governance.handle_provision_tenant, True),
     ("GET", r"^/api/v1/tenant-governance/tenants/(?P<id>[^/]+)$", tenant_governance.handle_get_tenant, True),
     ("POST", r"^/api/v1/tenant-governance/tenants/(?P<id>[^/]+)/transition$", tenant_governance.handle_transition_tenant, True),
     ("GET", r"^/api/v1/tenant-governance/tenants/(?P<id>[^/]+)/offboarding-impact$", tenant_governance.handle_get_offboarding_impact, True),
     ("POST", r"^/api/v1/tenant-governance/tenants/(?P<id>[^/]+)/export$", tenant_governance.handle_export_tenant_data, True),
     ("GET", r"^/api/v1/tenant-governance/tenants/(?P<id>[^/]+)/entitlements$", tenant_governance.handle_get_entitlements, True),
     ("PATCH", r"^/api/v1/tenant-governance/tenants/(?P<id>[^/]+)/entitlements$", tenant_governance.handle_update_entitlements, True),
     ("GET", r"^/api/v1/tenant-governance/tenants/(?P<id>[^/]+)/quotas/(?P<resource>[^/]+)$", tenant_governance.handle_check_quota, True),
     ("POST", r"^/api/v1/tenant-governance/break-glass$", tenant_governance.handle_create_break_glass_ticket, True),
     ("GET", r"^/api/v1/tenant-governance/break-glass$", tenant_governance.handle_list_break_glass_tickets, True),
     ("POST", r"^/api/v1/tenant-governance/break-glass/(?P<id>[^/]+)/revoke$", tenant_governance.handle_revoke_break_glass_ticket, True),
     ("POST", r"^/api/v1/tenant-governance/validate-relationship$", tenant_governance.handle_validate_relationship, True),
     ("GET", r"^/api/v1/tenant-governance/audit-ledger/verify$", tenant_governance.handle_verify_saas_audit_ledger, True),

     # Prompt 56: Enterprise Backup, Disaster Recovery & Verified Restore Engine
     ("POST", r"^/api/v1/dr/coordinated-backups$", backup_restore.handle_create_coordinated_backup, True),
     ("GET", r"^/api/v1/dr/coordinated-backups$", backup_restore.handle_list_coordinated_backups, True),
     ("GET", r"^/api/v1/dr/coordinated-backups/(?P<id>[^/]+)$", backup_restore.handle_get_coordinated_backup, True),
     ("POST", r"^/api/v1/dr/coordinated-backups/(?P<id>[^/]+)/verify$", backup_restore.handle_verify_backup_manifest, True),
     ("POST", r"^/api/v1/dr/pitr-markers$", backup_restore.handle_record_pitr_marker, True),
     ("GET", r"^/api/v1/dr/pitr-markers$", backup_restore.handle_list_pitr_markers, True),
     ("POST", r"^/api/v1/dr/verified-restore-drills$", backup_restore.handle_execute_verified_restore_drill, True),
     ("GET", r"^/api/v1/dr/verified-restore-drills$", backup_restore.handle_list_restore_drills, True),
     ("GET", r"^/api/v1/dr/verified-restore-drills/(?P<id>[^/]+)$", backup_restore.handle_get_restore_drill, True),
     ("POST", r"^/api/v1/dr/verified-restore-drills/(?P<id>[^/]+)/promotion-gate$", backup_restore.handle_evaluate_promotion_gate, True),
     ("POST", r"^/api/v1/dr/retention/cleanup$", backup_restore.handle_retention_cleanup, True),
     ("GET", r"^/api/v1/dr/ledger/verify$", backup_restore.handle_verify_governance_ledger, True),
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

        # Resolve auth token (Bearer header, X-Auth-Token header, or session cookie only)
        # Security: Query-string token parameter fallback is prohibited to prevent token leakage in HTTP logs/referrers
        auth_header = headers.get("authorization") or headers.get("Authorization") or ""
        token = auth_header.replace("Bearer ", "").strip() if "Bearer " in auth_header else headers.get("x-auth-token", "")
        if not token:
            cookie_header = headers.get("cookie") or headers.get("Cookie") or ""
            for cookie_part in cookie_header.split(";"):
                cookie_part = cookie_part.strip()
                if cookie_part.startswith("session_token="):
                    token = cookie_part.partition("=")[2].strip()
                    break

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
                                req_fac_id = headers.get("x-facility-id") or headers.get("X-Facility-Id") or req["path_params"].get("facility_id")
                                req["user"] = validate_session(conn, token, requested_facility_id=req_fac_id)
                            except AuthenticationError as e:
                                e.request_id = request_id
                                return e.status_code, {"Content-Type": "application/json", "X-Request-Id": request_id}, json.dumps(e.to_dict()).encode("utf-8")

                        try:
                            res = handler_fn(conn, req)
                            # Support raw binary responses with custom headers (e.g. streaming PDFs, book reader)
                            if isinstance(res, tuple) and len(res) == 3:
                                status_code, custom_headers, resp_bytes = res
                                if "X-Request-Id" not in custom_headers:
                                    custom_headers["X-Request-Id"] = request_id
                                return status_code, custom_headers, resp_bytes
                            else:
                                status_code, response_data = res
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

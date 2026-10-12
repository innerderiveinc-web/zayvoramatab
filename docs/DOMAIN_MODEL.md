# Domain Model & Relational Schema Specification — ZAYVORA MATAB OS

**Version:** 1.1  
**Dialect:** ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible  
**Design Rules:** Strict foreign key integrity, UUID primary keys, timestamp audit columns, and organization-scoped tenancy on all patient and transactional tables.

---

## 1. Entity-Relationship Overview

```
 [organizations] ──1:N── [facilities] ──1:N── [user_facility_memberships] ──N:1── [users]
        │                       │
       1:N                     1:N
        │                       │
    [patients] ────────── [encounters] ───────────────┐
        │                       │                     │
       1:N                     1:N                   1:N
  [allergies]          [vitals / notes]        [unani_assessments]
        │                       │                     │
        │                      1:N                   1:N
        │               [prescriptions]         [care_plans]
        │                       │                     │
        │                      1:N                   1:N
        └─────────────── [safety_checks]       [follow_up_tasks]
                                │
                               1:N
                      [prescription_items]
```

---

## 2. Core Relational Schemas

### 2.1 Identity & Tenancy
- **`organizations`**: `id` (UUID PK), `name`, `code`, `license_number`, `profile_type` ('MATAB' | 'CLINIC' | 'HOSPITAL'), `created_at`.
- **`facilities`**: `id` (UUID PK), `organization_id` (FK), `name`, `code`, `address`, `phone`, `is_active`, `created_at`.
- **`users`**: `id` (UUID PK), `organization_id` (FK), `username`, `email`, `password_hash`, `role` ('ADMIN' | 'HAKEEM' | 'DOCTOR' | 'NURSE' | 'RECEPTIONIST' | 'PHARMACIST'), `full_name`, `is_active`, `created_at`.
- **`practitioners`**: `id` (UUID PK), `user_id` (FK), `license_type` ('BUMS' | 'MD_UNANI' | 'MBBS' | 'OTHER'), `registration_number`, `registration_council`, `digital_signature_pin_hash`, `created_at`.
- **`user_facility_memberships`**: `id` (UUID PK), `user_id` (FK), `facility_id` (FK), `role_in_facility`, `created_at`.

### 2.2 Patient Domain
- **`patients`**: `id` (UUID PK), `organization_id` (FK), `mrn` (Medical Record Number, Unique per Org), `first_name`, `last_name`, `dob`, `gender` ('MALE' | 'FEMALE' | 'OTHER'), `phone`, `email`, `blood_group`, `emergency_contact_name`, `emergency_contact_phone`, `primary_language` ('UR' | 'HI' | 'EN'), `created_at`, `updated_at`.
- **`patient_consents`**: `id` (UUID PK), `patient_id` (FK), `consent_type` ('TREATMENT' | 'DATA_SHARING' | 'RESEARCH'), `is_granted` (BOOL), `granted_at`, `expires_at`.
- **`patient_allergies`**: `id` (UUID PK), `patient_id` (FK), `allergen_type` ('HERBAL' | 'PHARMACEUTICAL' | 'FOOD' | 'ENVIRONMENTAL'), `allergen_name`, `severity` ('MILD' | 'MODERATE' | 'SEVERE'), `reaction_description`, `recorded_at`.
- **`possible_duplicate_matches`**: `id` (UUID PK), `patient_a_id` (FK), `patient_b_id` (FK), `match_confidence` (FLOAT), `match_reasons` (TEXT), `status` ('PENDING' | 'RESOLVED_MERGED' | 'RESOLVED_DISTINCT'), `resolved_by`, `resolved_at`.

### 2.3 Encounter & Clinical Observations
- **`encounters`**: `id` (UUID PK), `organization_id` (FK), `facility_id` (FK), `patient_id` (FK), `practitioner_id` (FK), `token_number` (INT), `encounter_type` ('WALK_IN' | 'APPOINTMENT' | 'FOLLOW_UP'), `status` ('ARRIVED' | 'IN_CONSULTATION' | 'SIGNED' | 'COMPLETED' | 'CANCELLED'), `started_at`, `ended_at`, `created_at`.
- **`vitals`**: `id` (UUID PK), `encounter_id` (FK), `systolic_bp` (INT), `diastolic_bp` (INT), `pulse_bpm` (INT), `temperature_f` (FLOAT), `respiratory_rate` (INT), `weight_kg` (FLOAT), `height_cm` (FLOAT), `spo2_percent` (INT), `recorded_at`.
- **`clinical_notes`**: `id` (UUID PK), `encounter_id` (FK), `chief_complaint` (TEXT), `history_of_present_illness` (TEXT), `past_medical_history` (TEXT), `general_physical_exam` (TEXT), `systemic_exam` (TEXT), `author_id` (FK), `created_at`.

### 2.4 Unani Clinical Assessment Track
- **`unani_assessments`**: `id` (UUID PK), `encounter_id` (FK), `patient_id` (FK), `hakeem_id` (FK), `dominant_mizaj` ('DAMWI' | 'BALGHAMI' | 'SAFRAWI' | 'SAUDAWI' | 'MOTADIL'), `mizaj_secondary` (TEXT), `su_e_mizaj_type` ('SAADA' | 'MADDI' | 'NONE'), `nabz_quality` ('AZEEM' | 'SAREE' | 'MUTAWASSIT' | 'SAGHEER' | 'BATEE'), `baul_observations` (TEXT), `baraz_observations` (TEXT), `afaal_summary` (TEXT), `asbab_sittah_assessment` (JSON/TEXT), `clinical_interpretation` (TEXT), `assessment_status` ('DRAFT' | 'FINAL'), `created_at`.
- **`mizaj_questionnaire_responses`**: `id` (UUID PK), `assessment_id` (FK), `question_key` (TEXT), `selected_option` (TEXT), `score_dam` (INT), `score_balgham` (INT), `score_safra` (INT), `score_sauda` (INT).
- **`organ_axis_evaluations`**: `id` (UUID PK), `assessment_id` (FK), `axis_name` ('QALB_DIMAGH' | 'KABID_MEDA' | 'KULLIYA_MASANA' | 'RAHIM_TUKHM'), `imbalance_severity` ('NORMAL' | 'KHAFIFA' | 'MUTAWASSITA' | 'SHADEEDA'), `observed_indicators` (TEXT).

### 2.5 Modern Clinical Support Track
- **`clinical_problems`**: `id` (UUID PK), `encounter_id` (FK), `problem_name` (TEXT), `icd10_code` (TEXT), `status` ('ACTIVE' | 'RESOLVED'), `is_red_flag` (BOOL), `recorded_at`.
- **`red_flag_alerts`**: `id` (UUID PK), `encounter_id` (FK), `trigger_rule` (TEXT), `severity` ('CRITICAL' | 'URGENT'), `guidance` (TEXT), `acknowledged_by` (FK), `acknowledged_at`.
- **`investigation_orders`**: `id` (UUID PK), `encounter_id` (FK), `test_name` (TEXT), `reason` (TEXT), `status` ('ORDERED' | 'REPORTED' | 'CANCELLED'), `ordered_at`.

### 2.6 Care Plan & Usul-e-Ilaj
- **`care_plans`**: `id` (UUID PK), `encounter_id` (FK), `patient_id` (FK), `usul_e_ilaj_summary` (TEXT), `modality_flags` ('ILAJ_BIL_DAWA,ILAJ_BIL_GHIZA,ILAJ_BIT_TADBEER'), `dietary_guidelines_ghiza` (TEXT), `regimen_tadbeer_instructions` (TEXT), `created_at`.
- **`follow_up_tasks`**: `id` (UUID PK), `encounter_id` (FK), `patient_id` (FK), `due_date` (DATE), `target_objective` (TEXT), `status` ('SCHEDULED' | 'ATTENDED' | 'MISSED'), `created_at`.

### 2.7 Knowledge Catalog & Formulations
- **`knowledge_sources`**: `id` (UUID PK), `code` (e.g. 'NFUM-I'), `title`, `author_authority`, `edition`, `publication_year`, `legal_status` ('STATUTORY' | 'HISTORICAL_BENCHMARK' | 'RESEARCH').
- **`ingredients`**: `id` (UUID PK), `canonical_name` (TEXT), `unani_name` (TEXT), `botanical_name` (TEXT), `temperament_mizaj` ('HOT_DRY' | 'HOT_MOIST' | 'COLD_DRY' | 'COLD_MOIST'), `degree` (1-4), `single_dose_min_mg` (INT), `single_dose_max_mg` (INT), `is_mudabbar_required` (BOOL), `is_schedule_e1` (BOOL), `source_id` (FK).
- **`formulations`**: `id` (UUID PK), `name` (TEXT), `dosage_form` ('SAFOOF' | 'MAJOON' | 'KHAMIRA' | 'JOSHANDA' | 'ITRIFAL' | 'HAB' | 'ARQ' | 'ROGHAN'), `classical_source_id` (FK), `standard_indication` (TEXT), `standard_adult_dose` (TEXT), `is_verified` (BOOL).
- **`formulation_ingredients`**: `id` (UUID PK), `formulation_id` (FK), `ingredient_id` (FK), `quantity_mg` (INT), `is_chief_ingredient` (BOOL).
- **`safety_contraindications`**: `id` (UUID PK), `ingredient_id` (FK), `contraindication_type` ('PREGNANCY' | 'LACTATION' | 'PEDIATRIC' | 'RENAL' | 'HYPERTENSION'), `severity` ('BLOCK' | 'WARN'), `rationale` (TEXT).

### 2.8 Prescriptions & Safe Signing
- **`prescriptions`**: `id` (UUID PK), `encounter_id` (FK), `patient_id` (FK), `hakeem_id` (FK), `version_number` (INT DEFAULT 1), `parent_prescription_id` (FK NULL), `amendment_reason` (TEXT NULL), `status` ('DRAFT' | 'PREFLIGHT_PASSED' | 'PREFLIGHT_BLOCKED' | 'SIGNED' | 'DISPENSED' | 'CANCELLED'), `overall_safety_state` ('UNKNOWN' | 'PASS' | 'WARN' | 'BLOCK'), `signature_timestamp` (TIMESTAMP NULL), `signature_hash` (TEXT NULL), `created_at`.
- **`prescription_items`**: `id` (UUID PK), `prescription_id` (FK), `item_type` ('CATALOG_FORMULATION' | 'CUSTOM_COMPOUND' | 'SINGLE_HERB'), `formulation_id` (FK NULL), `custom_name` (TEXT NULL), `dosage_form` (TEXT), `dose_amount` (TEXT), `dose_unit` (TEXT), `frequency` ('OD' | 'BD' | 'TDS' | 'QID' | 'SOS'), `duration_days` (INT), `instructions` (TEXT), `anupan_vehicle` ('ARQ_GAWZABAN' | 'WATER' | 'HONEY' | 'MILK' | 'NONE').
- **`safety_check_runs`**: `id` (UUID PK), `prescription_id` (FK), `evaluated_at` (TIMESTAMP), `overall_result` ('PASS' | 'WARN' | 'BLOCK' | 'UNKNOWN'), `check_details` (JSON/TEXT), `override_rationale` (TEXT NULL), `overridden_by` (FK NULL).

### 2.9 Operations & Governance
- **`inventory_batches`**: `id` (UUID PK), `facility_id` (FK), `formulation_id` (FK NULL), `ingredient_id` (FK NULL), `batch_number` (TEXT), `mfg_date` (DATE), `expiry_date` (DATE), `quantity_remaining` (INT), `unit` (TEXT), `is_mudabbar_certified` (BOOL).
- **`audit_events`**: `id` (UUID PK), `organization_id` (FK), `facility_id` (FK), `actor_id` (FK), `action_type` (TEXT), `resource_type` (TEXT), `resource_id` (TEXT), `details` (JSON/TEXT), `client_ip` (TEXT), `prev_hash` (TEXT), `chain_hash` (TEXT), `created_at` (TIMESTAMP).
- **`feature_registry`**: `engine_id` (TEXT PK), `name` (TEXT), `version` (TEXT), `state` ('NOT_IMPLEMENTED' | 'IMPLEMENTED_NOT_CONNECTED' | 'CONNECTED_NOT_VALIDATED' | 'FUNCTIONALLY_TESTED' | 'CLINICALLY_REVIEWED' | 'PILOT_APPROVED' | 'PRODUCTION_APPROVED' | 'DISABLED_OR_DEGRADED'), `last_tested_at` (TIMESTAMP), `owner` (TEXT).

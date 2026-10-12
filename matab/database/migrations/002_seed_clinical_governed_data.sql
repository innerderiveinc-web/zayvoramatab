-- Migration 002: Seed Clinical Governed Data and Feature Registry
-- Note: All demo patients are strictly marked with [SYNTHETIC TEST RECORD - NOT REAL CLINICAL DATA]

-- 1. Default Organization & Facility
INSERT OR IGNORE INTO organizations (id, name, code, license_number, profile_type)
VALUES ('org-matab-default', 'ZAYVORA Matab Dawakhana', 'ZMD-001', 'AYUSH/DL/2026/041', 'MATAB');

INSERT OR IGNORE INTO facilities (id, organization_id, name, code, address, phone)
VALUES ('fac-matab-main', 'org-matab-default', 'Central Matab OPD', 'OPD-1', 'B-12 Dawakhana Chowk, Delhi', '+91-9876543210');

-- 2. Default Users & Practitioners
-- Password hash for 'matab123': pbkdf2_sha256 (or validated plain hash mock in test suite)
-- We store a standard sha256 hex string with salt: 'sha256$somesalt$hex'
INSERT OR IGNORE INTO users (id, organization_id, username, email, password_hash, role, full_name)
VALUES 
('usr-hakeem-1', 'org-matab-default', 'hakeem', 'hakeem@zayvora.internal', 'pbkdf2:sha256:10000$saltmatab$cfcfe0609a07d21882e815afe9d739d83223c87c3766546d5a656da687629707', 'HAKEEM', 'Hakeem Tariq Ahmad'),
('usr-recep-1', 'org-matab-default', 'reception', 'reception@zayvora.internal', 'pbkdf2:sha256:10000$saltmatab$cfcfe0609a07d21882e815afe9d739d83223c87c3766546d5a656da687629707', 'RECEPTIONIST', 'Farhan Ali (Reception)'),
('usr-pharm-1', 'org-matab-default', 'pharmacy', 'pharmacy@zayvora.internal', 'pbkdf2:sha256:10000$saltmatab$cfcfe0609a07d21882e815afe9d739d83223c87c3766546d5a656da687629707', 'PHARMACIST', 'Bilal Siddiqui (Dispensary)');

-- Practitioner Profile for Hakeem Tariq (PIN 1234 hash)
INSERT OR IGNORE INTO practitioners (id, user_id, license_type, registration_number, registration_council, digital_signature_pin_hash)
VALUES ('prac-hakeem-1', 'usr-hakeem-1', 'BUMS', 'BUMS/DEL/8921/2012', 'Delhi Bharatiya Chikitsa Parishad', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4'); -- SHA256 of '1234'

INSERT OR IGNORE INTO user_facility_memberships (id, user_id, facility_id, role_in_facility)
VALUES 
('ufm-1', 'usr-hakeem-1', 'fac-matab-main', 'SENIOR_HAKEEM'),
('ufm-2', 'usr-recep-1', 'fac-matab-main', 'FRONT_DESK'),
('ufm-3', 'usr-pharm-1', 'fac-matab-main', 'CHIEF_PHARMACIST');

-- 3. Governed Knowledge Sources
INSERT OR IGNORE INTO knowledge_sources (id, code, title, author_authority, edition, publication_year, legal_status)
VALUES
('src-nfum-1', 'NFUM-I', 'National Formulary of Unani Medicine, Part I', 'Ministry of AYUSH, Govt of India', 'Reprint 2018', 2018, 'STATUTORY'),
('src-nfum-2', 'NFUM-II', 'National Formulary of Unani Medicine, Part II', 'Ministry of AYUSH, Govt of India', 'First Edition', 2007, 'STATUTORY'),
('src-upi-1', 'UPI-I', 'Unani Pharmacopoeia of India, Part I', 'Ministry of AYUSH, Govt of India', 'Volume I-VI', 2016, 'STATUTORY'),
('src-qanun', 'QANUN-MED', 'Al-Qanun fi al-Tibb (The Canon of Medicine)', 'Ibn Sina (Avicenna)', 'English/Urdu Critical Edition', 1025, 'HISTORICAL_BENCHMARK'),
('src-bayaz', 'BAYAZ-KABIR', 'Bayaz-e-Kabir', 'Hakeem Kabiruddin', 'Vol 1 & 2 Hikmat Press', 1935, 'HISTORICAL_BENCHMARK');

-- 4. Governed Ingredients (Mufradat)
INSERT OR IGNORE INTO ingredients (id, canonical_name, unani_name, botanical_name, temperament_mizaj, degree, single_dose_min_mg, single_dose_max_mg, daily_dose_max_mg, is_mudabbar_required, is_schedule_e1, source_id)
VALUES
('ing-asgandh', 'Asgandh', 'اسگندھ ناگوری', 'Withania somnifera', 'HOT_DRY', 2, 3000, 5000, 10000, 0, 0, 'src-upi-1'),
('ing-filfil', 'Filfil Siyah', 'فلفل سیاہ', 'Piper nigrum', 'HOT_DRY', 3, 500, 1000, 2000, 0, 0, 'src-upi-1'),
('ing-zanjabeel', 'Zanjabeel', 'زنجبیل', 'Zingiber officinale', 'HOT_DRY', 3, 1000, 2000, 4000, 0, 0, 'src-upi-1'),
('ing-badam', 'Roghan Badam Shireen', 'روغن بادام شیریں', 'Prunus amygdalus', 'HOT_MOIST', 1, 5000, 15000, 30000, 0, 0, 'src-upi-1'),
('ing-kuchla', 'Kuchla (Azaarqi)', 'کچلہ مدبر', 'Strychnos nux-vomica', 'HOT_DRY', 4, 30, 125, 250, 1, 1, 'src-upi-1'),
('ing-abhal', 'Abhal', 'ابہل', 'Juniperus communis', 'HOT_DRY', 3, 1000, 3000, 6000, 0, 0, 'src-upi-1'),
('ing-tukhm-kahu', 'Tukhm-e-Kahu', 'تخم کاہو', 'Lactuca sativa', 'COLD_MOIST', 2, 3000, 6000, 12000, 0, 0, 'src-upi-1');

-- 5. Contraindications & Safety Rules
INSERT OR IGNORE INTO safety_contraindications (id, ingredient_id, contraindication_type, severity, rationale)
VALUES
('sc-abhal-preg', 'ing-abhal', 'PREGNANCY', 'BLOCK', 'Emmenagogue and abortifacient action; strictly contraindicated in all trimesters of pregnancy.'),
('sc-kuchla-raw', 'ing-kuchla', 'PEDIATRIC', 'BLOCK', 'Schedule E(1) alkaloid toxicity; prohibited in children under 12 years.'),
('sc-badam-nut', 'ing-badam', 'ALLERGY_NUT', 'BLOCK', 'Direct tree-nut allergen; severe risk of anaphylaxis in known nut allergies.');

-- 6. Formulations (Murakkabat)
INSERT OR IGNORE INTO formulations (id, name, dosage_form, classical_source_id, standard_indication, standard_adult_dose, is_verified)
VALUES
('form-safoof-mohazzil', 'Safoof-e-Mohazzil', 'SAFOOF', 'src-nfum-1', 'Obesity (Farbahi), excess phlegm (Balgham)', '5 g twice daily with Arq-e-Zeera', 1),
('form-majoon-arad', 'Majoon Arad Khurma', 'MAJOON', 'src-bayaz', 'General debility (Zof-e-Aam), Taqwiyat-e-Bah', '10 g at bedtime with warm milk', 1),
('form-sharbat-bazoori', 'Sharbat Bazoori Motadil', 'ARQ', 'src-nfum-2', 'Diuretic, liver heat (Hararat-e-Kabid), dysuria', '25 ml mixed in warm water', 1),
('form-itrifal-kishneezi', 'Itrifal Kishneezi', 'ITRIFAL', 'src-nfum-1', 'Chronic catarrh (Nazla Muzmin), headache, gastric flatulence', '7 g at night with water', 1),
('form-hab-azaarqi', 'Habb-e-Azaarqi', 'HAB', 'src-nfum-1', 'Neuralgia (Waja-ul-Asab), facial palsy (Laqwa), arthritis', '1 tablet (max 125mg Mudabbar Kuchla) OD', 1);

-- Map formulation ingredients
INSERT OR IGNORE INTO formulation_ingredients (id, formulation_id, ingredient_id, quantity_mg, is_chief_ingredient)
VALUES
('fi-1', 'form-safoof-mohazzil', 'ing-filfil', 250, 0),
('fi-2', 'form-safoof-mohazzil', 'ing-zanjabeel', 500, 1),
('fi-3', 'form-majoon-arad', 'ing-asgandh', 1000, 1),
('fi-4', 'form-majoon-arad', 'ing-badam', 1500, 0),
('fi-5', 'form-hab-azaarqi', 'ing-kuchla', 120, 1),
('fi-6', 'form-hab-azaarqi', 'ing-filfil', 100, 0);

-- 7. Synthetic Demo Patients (CLEARLY LABELED [SYNTHETIC TEST RECORD])
INSERT OR IGNORE INTO patients (id, organization_id, mrn, first_name, last_name, dob, gender, phone, email, blood_group, is_synthetic)
VALUES
('pat-syn-001', 'org-matab-default', 'MRN-SYN-001', '[SYNTHETIC] Ahmad', 'Khan', '1988-04-12', 'MALE', '+91-9911002201', 'ahmad.synthetic@test.local', 'B+', 1),
('pat-syn-002', 'org-matab-default', 'MRN-SYN-002', '[SYNTHETIC] Fatima', 'Zehra', '1995-09-24', 'FEMALE', '+91-9911002202', 'fatima.synthetic@test.local', 'O+', 1),
('pat-syn-003', 'org-matab-default', 'MRN-SYN-003', '[SYNTHETIC] Mohammad', 'Iqbal', '1972-01-15', 'MALE', '+91-9911002203', 'iqbal.synthetic@test.local', 'A+', 1);

-- Allergies for Synthetic Patients
INSERT OR IGNORE INTO patient_allergies (id, patient_id, allergen_type, allergen_name, severity, reaction_description)
VALUES
('all-1', 'pat-syn-001', 'FOOD', 'Tree Nut / Almond (Roghan Badam Shireen)', 'SEVERE', 'Urticaria and bronchospasm');

-- Queue Encounters for Synthetic Patients Today
INSERT OR IGNORE INTO encounters (id, organization_id, facility_id, patient_id, practitioner_id, token_number, encounter_type, status)
VALUES
('enc-syn-101', 'org-matab-default', 'fac-matab-main', 'pat-syn-001', 'prac-hakeem-1', 1, 'WALK_IN', 'IN_CONSULTATION'),
('enc-syn-102', 'org-matab-default', 'fac-matab-main', 'pat-syn-002', 'prac-hakeem-1', 2, 'WALK_IN', 'ARRIVED'),
('enc-syn-103', 'org-matab-default', 'fac-matab-main', 'pat-syn-003', 'prac-hakeem-1', 3, 'APPOINTMENT', 'ARRIVED');

-- Vitals and Clinical Note for enc-syn-101
INSERT OR IGNORE INTO vitals (id, encounter_id, systolic_bp, diastolic_bp, pulse_bpm, temperature_f, respiratory_rate, weight_kg, height_cm, spo2_percent)
VALUES ('vit-syn-101', 'enc-syn-101', 128, 82, 74, 98.4, 16, 78.5, 172.0, 99);

INSERT OR IGNORE INTO clinical_notes (id, encounter_id, chief_complaint, history_of_present_illness, past_medical_history, general_physical_exam, systemic_exam, author_id)
VALUES ('note-syn-101', 'enc-syn-101', 'Heaviness in stomach (Siql-e-Meda) and sluggish digestion for 2 weeks.', 'Patient reports post-prandial fullness, cold extremities, and white-coated tongue after fatty meals.', 'No hypertension, no diabetes.', 'Moderately built, pallor negative, tongue moist with whitish coat.', 'Abdomen soft, mild epigastric fullness without organomegaly.', 'usr-hakeem-1');

-- 8. Feature Registry States
INSERT OR REPLACE INTO feature_registry (engine_id, name, version, state, owner)
VALUES
('core.identity', 'Identity and Tenancy Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 'Security Lead'),
('core.tenancy', 'Organization/Facility Scope Filter', '1.1.0', 'FUNCTIONALLY_TESTED', 'Core Architecture'),
('core.audit', 'Chained Tamper-Evident Audit', '1.1.0', 'FUNCTIONALLY_TESTED', 'Governance Panel'),
('clinical.patients', 'Patient MPI and Duplicate Check', '1.1.0', 'FUNCTIONALLY_TESTED', 'Clinical Informatics'),
('clinical.encounters', 'Encounter Queue and Vitals State Machine', '1.1.0', 'FUNCTIONALLY_TESTED', 'Clinical Informatics'),
('unani.assessment', 'Mizaj and Ajnas Assessment Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 'Unani Governance Panel'),
('clinical.support', 'Modern Red Flags & Differential Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 'Safety Panel'),
('clinical.care_plan', 'Usul-e-Ilaj Care Planning Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 'Clinical Informatics'),
('prescriptions.nuskha', 'Nuskha Builder & Formulation Compiler', '1.1.0', 'FUNCTIONALLY_TESTED', 'Pharmacopoeia Panel'),
('prescriptions.safety', 'Deterministic Preflight Safety Checker', '1.1.0', 'FUNCTIONALLY_TESTED', 'Safety Panel'),
('prescriptions.sign', 'Electronic Signature & Cryptographic Fingerprinting', '1.1.0', 'FUNCTIONALLY_TESTED', 'Legal & Security'),
('prescriptions.print', 'Verified Prescription Document Generator', '1.1.0', 'FUNCTIONALLY_TESTED', 'UX Team'),
('operations.followup', 'Continuum Care & Follow-up Task Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 'Operations Lead'),
('operations.inventory', 'FEFO Batch Dispensary Inventory Engine', '1.1.0', 'FUNCTIONALLY_TESTED', 'Dispensary Team'),
('integration.abdm', 'FHIR / ABDM Adapter Connector', '1.1.0', 'CONNECTED_NOT_VALIDATED', 'Integration Lead'),
('ai.scribe', 'Contextual AI Clinical Note Scribe', '1.1.0', 'NOT_IMPLEMENTED', 'AI Safety Board'),
('hospital.ipd', 'Inpatient Ward Nursing Engine', '1.1.0', 'NOT_IMPLEMENTED', 'Hospital Operations');

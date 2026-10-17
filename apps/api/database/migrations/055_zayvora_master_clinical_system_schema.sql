-- Migration 055: ZAYVORA Master Clinical Kits, Drug Interactions & Z-MAI Scoring Schema
-- Complements existing master_organ_axes, master_protocols, master_products, and master_parhez

-- 1. Protocol Kits (K-01 to K-21 Bundled Systems)
CREATE TABLE IF NOT EXISTS protocol_kits (
    id TEXT PRIMARY KEY,
    kit_code TEXT UNIQUE NOT NULL,   -- e.g. K-01, K-02, ... K-21
    name TEXT NOT NULL,
    products_included TEXT NOT NULL,
    indication TEXT NOT NULL,
    price_min_inr INTEGER NOT NULL,
    price_max_inr INTEGER NOT NULL,
    regulatory_track TEXT NOT NULL,
    kit_type TEXT NOT NULL DEFAULT 'CLINIC', -- CLINIC, RETAIL, ADVANCED_RX
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pk_kit_code ON protocol_kits(kit_code);

-- 2. Master Herb-Drug Interaction Safety Matrix
CREATE TABLE IF NOT EXISTS herb_drug_interactions (
    id TEXT PRIMARY KEY,
    herb_name TEXT NOT NULL,
    drug_class TEXT NOT NULL,
    specific_drugs TEXT NOT NULL,
    interaction_description TEXT NOT NULL,
    severity TEXT NOT NULL,          -- HIGH, MODERATE, LOW, CONTRAINDICATED
    management_protocol TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hdi_herb ON herb_drug_interactions(herb_name);
CREATE INDEX IF NOT EXISTS idx_hdi_severity ON herb_drug_interactions(severity);

-- 3. Z-MAI Assessment Records (Patient-Encounter Clinical Scoring)
CREATE TABLE IF NOT EXISTS z_mai_assessment_records (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    encounter_id TEXT REFERENCES encounters(id) ON DELETE SET NULL,
    morphological_score INTEGER NOT NULL DEFAULT 0,
    thermoregulatory_score INTEGER NOT NULL DEFAULT 0,
    digestive_score INTEGER NOT NULL DEFAULT 0,
    metabolic_score INTEGER NOT NULL DEFAULT 0,
    psychological_score INTEGER NOT NULL DEFAULT 0,
    laboratorial_score INTEGER NOT NULL DEFAULT 0,
    dominant_mizaj TEXT NOT NULL,    -- Damawi, Safrawi, Balghami, Saudawi
    secondary_mizaj TEXT,
    primary_axis TEXT NOT NULL,      -- e.g. Jigar-Khasiya, Jigar-Banas, etc.
    secondary_axis TEXT,
    recommended_protocol_code TEXT,  -- e.g. P-01, MF-01, etc.
    assessed_by TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_zmai_patient ON z_mai_assessment_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_zmai_encounter ON z_mai_assessment_records(encounter_id);

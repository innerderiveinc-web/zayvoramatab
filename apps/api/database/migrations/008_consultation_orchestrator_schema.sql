-- Phase 8 Schema: Unified Consultation Workspace & Clinical Workflow Orchestrator
-- Dialect: ANSI SQL / SQLite 3 (WAL mode) / PostgreSQL 15+ compatible

-- 1. Encounter Section States
CREATE TABLE IF NOT EXISTS encounter_section_states (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    section_key TEXT NOT NULL, -- 'visit', 'history_observations', 'unani_assessment', 'modern_assessment', 'plan_nuskha', 'safety_review', 'finalize'
    status TEXT NOT NULL DEFAULT 'not_started', -- 'not_started', 'in_progress', 'complete', 'not_applicable', 'needs_review'
    completion_metadata_json TEXT, -- Notes, clinical rationale for N/A, timestamps, actor details
    version_number INTEGER NOT NULL DEFAULT 1,
    updated_by TEXT NOT NULL REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(encounter_id, section_key)
);

CREATE INDEX IF NOT EXISTS idx_section_states_encounter ON encounter_section_states(encounter_id, section_key);

-- 2. Encounter State Machine Transitions Audit
CREATE TABLE IF NOT EXISTS encounter_state_transitions (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    actor_id TEXT NOT NULL REFERENCES users(id),
    reason TEXT,
    transitioned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_state_transitions_encounter ON encounter_state_transitions(encounter_id, transitioned_at);

-- 3. Encounter Document Snapshots & Bundles (Immutable Output Records)
CREATE TABLE IF NOT EXISTS encounter_documents (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    document_type TEXT NOT NULL, -- 'consultation_summary', 'prescription_bundle', 'patient_instruction_sheet'
    version_number INTEGER NOT NULL DEFAULT 1,
    content_snapshot_json TEXT NOT NULL,
    document_hash TEXT NOT NULL, -- SHA-256 integrity digest
    generated_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(encounter_id, document_type, version_number)
);

CREATE INDEX IF NOT EXISTS idx_encounter_docs_encounter ON encounter_documents(encounter_id, document_type);

-- 4. Encounter Care Continuum Follow-up Tasks
CREATE TABLE IF NOT EXISTS encounter_followup_tasks (
    id TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    due_date TEXT NOT NULL, -- ISO YYYY-MM-DD
    task_description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'in_progress', 'completed', 'cancelled'
    created_by TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_followup_tasks_patient ON encounter_followup_tasks(patient_id, due_date, status);
CREATE INDEX IF NOT EXISTS idx_followup_tasks_encounter ON encounter_followup_tasks(encounter_id);

-- 5. Workflow Orchestration Idempotency Keys
CREATE TABLE IF NOT EXISTS orchestration_idempotency_keys (
    key TEXT PRIMARY KEY,
    encounter_id TEXT NOT NULL,
    action TEXT NOT NULL,
    response_payload_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_orch_idempotency_enc ON orchestration_idempotency_keys(encounter_id, action);

-- ============================================================================
-- Migration: 042_enterprise_data_lineage_schema_evolution_impact_schema.sql
-- Description: Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine Schema
-- System: ZAYVORA MATAB OS — Standalone Unani Clinic & Multi-Branch Enterprise OS
-- ============================================================================

-- 1. Governed Data & API Contracts Registry
CREATE TABLE IF NOT EXISTS lineage_contracts_registry (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    contract_key TEXT NOT NULL,
    contract_type TEXT NOT NULL CHECK(contract_type IN ('database', 'api', 'event', 'import', 'export', 'terminology', 'metric', 'configuration')),
    version TEXT NOT NULL DEFAULT '1.0.0',
    owner TEXT NOT NULL,
    schema_definition_json TEXT NOT NULL DEFAULT '{}',
    compatibility_policy TEXT NOT NULL CHECK(compatibility_policy IN ('BACKWARD', 'FORWARD', 'FULL', 'STRICT_BREAKING')) DEFAULT 'BACKWARD',
    sensitivity TEXT NOT NULL CHECK(sensitivity IN ('PUBLIC', 'INTERNAL', 'RESTRICTED_PHI', 'FINANCIAL')) DEFAULT 'INTERNAL',
    status TEXT NOT NULL CHECK(status IN ('draft', 'review', 'approved', 'retired')) DEFAULT 'approved',
    limitations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, contract_key, version)
);

CREATE INDEX IF NOT EXISTS idx_lineage_contracts_org_type ON lineage_contracts_registry(organization_id, contract_type, status);
CREATE INDEX IF NOT EXISTS idx_lineage_contracts_key ON lineage_contracts_registry(contract_key, version);

-- 2. Lineage Graph Nodes
CREATE TABLE IF NOT EXISTS lineage_nodes (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    node_key TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK(node_type IN ('domain_entity', 'db_table', 'db_column', 'api_endpoint', 'event_topic', 'workflow_rule', 'terminology_concept', 'analytics_metric', 'external_integration')),
    name TEXT NOT NULL,
    description TEXT,
    contract_id TEXT REFERENCES lineage_contracts_registry(id) ON DELETE SET NULL,
    owner TEXT NOT NULL DEFAULT 'Core Platform',
    sensitivity TEXT NOT NULL CHECK(sensitivity IN ('PUBLIC', 'INTERNAL', 'RESTRICTED_PHI', 'FINANCIAL')) DEFAULT 'INTERNAL',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, node_key)
);

CREATE INDEX IF NOT EXISTS idx_lineage_nodes_org_type ON lineage_nodes(organization_id, node_type);
CREATE INDEX IF NOT EXISTS idx_lineage_nodes_key ON lineage_nodes(node_key);

-- 3. Directed Lineage Dependencies & Evidence Edges
CREATE TABLE IF NOT EXISTS lineage_edges (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    source_node_id TEXT NOT NULL REFERENCES lineage_nodes(id) ON DELETE CASCADE,
    target_node_id TEXT NOT NULL REFERENCES lineage_nodes(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL CHECK(relationship_type IN (
        'produces', 'reads', 'writes', 'transforms', 'validates', 
        'publishes', 'subscribes_to', 'maps_to', 'aggregates_into', 
        'indexes_into', 'exports_to', 'authorizes', 'audits', 'depends_on'
    )),
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('code_reference', 'schema_fk', 'test_assertion', 'config', 'manual_audit')),
    verification_status TEXT NOT NULL CHECK(verification_status IN ('verified', 'inferred', 'unknown', 'stale', 'not_applicable')) DEFAULT 'verified',
    evidence_details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(organization_id, source_node_id, target_node_id, relationship_type)
);

CREATE INDEX IF NOT EXISTS idx_lineage_edges_source ON lineage_edges(organization_id, source_node_id);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_target ON lineage_edges(organization_id, target_node_id);
CREATE INDEX IF NOT EXISTS idx_lineage_edges_verification ON lineage_edges(verification_status);

-- 4. Schema Evolution & Lineage Change Requests
CREATE TABLE IF NOT EXISTS lineage_change_requests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    title TEXT NOT NULL,
    requester_id TEXT NOT NULL,
    contract_id TEXT NOT NULL REFERENCES lineage_contracts_registry(id) ON DELETE RESTRICT,
    source_node_id TEXT REFERENCES lineage_nodes(id) ON DELETE SET NULL,
    target_version TEXT NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('additive', 'breaking', 'semantically_breaking', 'config_change')),
    diff_payload_json TEXT NOT NULL DEFAULT '{}',
    migration_plan_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL CHECK(status IN (
        'draft', 'analysis_pending', 'review_required', 'blocked_by_unknowns', 
        'approved_for_test', 'testing', 'approved_for_release', 
        'deployed_pending_verification', 'verified', 'rejected', 'rolled_back', 'closed'
    )) DEFAULT 'draft',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_cr_org_status ON lineage_change_requests(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_lineage_cr_contract ON lineage_change_requests(contract_id);

-- 5. Change Impact Analysis Reports
CREATE TABLE IF NOT EXISTS lineage_impact_reports (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    change_request_id TEXT NOT NULL REFERENCES lineage_change_requests(id) ON DELETE CASCADE,
    direct_consumers_json TEXT NOT NULL DEFAULT '[]',
    transitive_consumers_json TEXT NOT NULL DEFAULT '[]',
    affected_apis_json TEXT NOT NULL DEFAULT '[]',
    affected_metrics_json TEXT NOT NULL DEFAULT '[]',
    compatibility_classification TEXT NOT NULL CHECK(compatibility_classification IN (
        'additive_compatible', 'conditionally_compatible', 'breaking', 'semantically_breaking', 'unassessed'
    )),
    clinical_safety_impact_flag INTEGER NOT NULL DEFAULT 0 CHECK(clinical_safety_impact_flag IN (0, 1)),
    financial_impact_flag INTEGER NOT NULL DEFAULT 0 CHECK(financial_impact_flag IN (0, 1)),
    privacy_impact_flag INTEGER NOT NULL DEFAULT 0 CHECK(privacy_impact_flag IN (0, 1)),
    recommended_release_gate TEXT NOT NULL CHECK(recommended_release_gate IN ('PROCEED', 'MANUAL_REVIEW_REQUIRED', 'BLOCKED_BY_UNKNOWNS')),
    known_unknowns_json TEXT NOT NULL DEFAULT '[]',
    evaluated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_ir_cr ON lineage_impact_reports(change_request_id);
CREATE INDEX IF NOT EXISTS idx_lineage_ir_gate ON lineage_impact_reports(recommended_release_gate);

-- 6. Multi-Stakeholder Change Reviews
CREATE TABLE IF NOT EXISTS lineage_change_reviews (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    change_request_id TEXT NOT NULL REFERENCES lineage_change_requests(id) ON DELETE CASCADE,
    reviewer_id TEXT NOT NULL,
    review_role TEXT NOT NULL CHECK(review_role IN ('CLINICAL_DIRECTOR', 'DATA_ARCHITECT', 'LEGAL_COUNSEL', 'CISO')),
    decision TEXT NOT NULL CHECK(decision IN ('approved', 'rejected', 'revision_requested')),
    rationale TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lineage_reviews_cr ON lineage_change_reviews(change_request_id);

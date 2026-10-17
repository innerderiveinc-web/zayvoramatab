# ZAYVORA MATAB OS — LINEAGE & SCHEMA EVOLUTION ARCHITECTURE SPECIFICATION
**Module:** Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine  
**Document ID:** P43-SPEC-001  
**Status:** APPROVED ARCHITECTURAL SPECIFICATION  
**Target Migration:** `042_enterprise_data_lineage_schema_evolution_impact_schema.sql`  
**Target ADR:** `ADR-062`

---

## 1. Architectural Scope & Objectives

The Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine provides continuous, auditable, and mathematically deterministic dependency mapping across all data assets of ZAYVORA MATAB OS.

It solves three critical risks in clinical healthcare systems:
1. **Unannounced Breaking Schema Evolution:** Alterations to SQLite database schemas, API JSON payloads, or event message formats that break downstream mobile apps, analytics cubes, or integration adapters.
2. **Silent Semantic Divergence:** Changes that are syntactically valid (e.g., float value remains float) but alter unit measurements, dosage ranges, contraindication thresholds, or ICD/NAMASTE mappings, introducing patient safety hazards.
3. **Optimistic False Negatives ("No Impact"):** Tooling that assumes untouched tables mean zero impact, ignoring dynamic consumers, external consumers, or untracked batch exports.

---

## 2. Core Entities & Relational Schema (Migration 042)

### 2.1 `lineage_contracts_registry`
Stores formal machine-readable contracts for schemas, APIs, events, and metrics.
- `id`: TEXT PRIMARY KEY
- `organization_id`: TEXT NOT NULL
- `contract_key`: TEXT NOT NULL (e.g., `db:patients`, `api:v1:encounters`, `event:pharmacovigilance:alert`, `metric:encounter_volume`)
- `contract_type`: TEXT NOT NULL (`database`, `api`, `event`, `import`, `export`, `terminology`, `metric`, `configuration`)
- `version`: TEXT NOT NULL (SemVer, e.g., `1.0.0`)
- `owner`: TEXT NOT NULL (Team or Role, e.g., `Core Platform`, `Clinical Directorate`)
- `schema_definition_json`: TEXT NOT NULL (JSON Schema of fields, types, required flags, units)
- `compatibility_policy`: TEXT NOT NULL (`BACKWARD`, `FORWARD`, `FULL`, `STRICT_BREAKING`)
- `sensitivity`: TEXT NOT NULL (`PUBLIC`, `INTERNAL`, `RESTRICTED_PHI`, `FINANCIAL`)
- `status`: TEXT NOT NULL (`draft`, `review`, `approved`, `retired`)
- `limitations_json`: TEXT (Known limitations or uninstrumented dynamic uses)
- `created_at`, `updated_at`: TEXT NOT NULL

### 2.2 `lineage_nodes`
Canonical nodes in the dependency graph.
- `id`: TEXT PRIMARY KEY
- `organization_id`: TEXT NOT NULL
- `node_key`: TEXT NOT NULL UNIQUE (e.g., `entity:patient`, `table:patients`, `col:patients.given_name`, `api:post_encounter`, `rule:nuskha_dosage_check`, `vocab:namaste_unani`)
- `node_type`: TEXT NOT NULL (`domain_entity`, `db_table`, `db_column`, `api_endpoint`, `event_topic`, `workflow_rule`, `terminology_concept`, `analytics_metric`, `external_integration`)
- `name`: TEXT NOT NULL
- `description`: TEXT
- `contract_id`: TEXT REFERENCES `lineage_contracts_registry`(id)
- `owner`: TEXT
- `sensitivity`: TEXT
- `metadata_json`: TEXT
- `created_at`, `updated_at`: TEXT NOT NULL

### 2.3 `lineage_edges`
Directed dependencies between lineage nodes.
- `id`: TEXT PRIMARY KEY
- `organization_id`: TEXT NOT NULL
- `source_node_id`: TEXT NOT NULL REFERENCES `lineage_nodes`(id)
- `target_node_id`: TEXT NOT NULL REFERENCES `lineage_nodes`(id)
- `relationship_type`: TEXT NOT NULL (`produces`, `reads`, `writes`, `transforms`, `validates`, `publishes`, `subscribes_to`, `maps_to`, `aggregates_into`, `indexes_into`, `exports_to`, `authorizes`, `audits`, `depends_on`)
- `evidence_type`: TEXT NOT NULL (`code_reference`, `schema_fk`, `test_assertion`, `config`, `manual_audit`)
- `verification_status`: TEXT NOT NULL (`verified`, `inferred`, `unknown`, `stale`, `not_applicable`)
- `evidence_details_json`: TEXT (File paths, line numbers, test names, commit hashes)
- `created_at`, `updated_at`: TEXT NOT NULL

### 2.4 `lineage_change_requests`
Change proposals evaluated against the lineage graph.
- `id`: TEXT PRIMARY KEY
- `organization_id`: TEXT NOT NULL
- `title`: TEXT NOT NULL
- `requester_id`: TEXT NOT NULL
- `contract_id`: TEXT NOT NULL REFERENCES `lineage_contracts_registry`(id)
- `source_node_id`: TEXT REFERENCES `lineage_nodes`(id)
- `target_version`: TEXT NOT NULL
- `change_type`: TEXT NOT NULL (`additive`, `breaking`, `semantically_breaking`, `config_change`)
- `diff_payload_json`: TEXT NOT NULL (Proposed schema/definition diff)
- `migration_plan_json`: TEXT (Rollforward and rollback strategy)
- `status`: TEXT NOT NULL (`draft`, `analysis_pending`, `review_required`, `blocked_by_unknowns`, `approved_for_test`, `testing`, `approved_for_release`, `deployed_pending_verification`, `verified`, `rejected`, `rolled_back`, `closed`)
- `created_at`, `updated_at`: TEXT NOT NULL

### 2.5 `lineage_impact_reports`
Automated impact analysis output from graph traversal.
- `id`: TEXT PRIMARY KEY
- `organization_id`: TEXT NOT NULL
- `change_request_id`: TEXT NOT NULL REFERENCES `lineage_change_requests`(id)
- `direct_consumers_json`: TEXT NOT NULL (Immediate downstream nodes)
- `transitive_consumers_json`: TEXT NOT NULL (All downstream nodes reachable up to max depth)
- `affected_apis_json`: TEXT NOT NULL (APIs impacted)
- `affected_metrics_json`: TEXT NOT NULL (Analytics cubes or metrics impacted)
- `compatibility_classification`: TEXT NOT NULL (`additive_compatible`, `conditionally_compatible`, `breaking`, `semantically_breaking`, `unassessed`)
- `clinical_safety_impact_flag`: INTEGER NOT NULL DEFAULT 0 (1 if clinical safety or dosage rules affected)
- `financial_impact_flag`: INTEGER NOT NULL DEFAULT 0 (1 if billing or pricing affected)
- `privacy_impact_flag`: INTEGER NOT NULL DEFAULT 0 (1 if restricted PHI fields affected)
- `recommended_release_gate`: TEXT NOT NULL (`PROCEED`, `MANUAL_REVIEW_REQUIRED`, `BLOCKED_BY_UNKNOWNS`)
- `known_unknowns_json`: TEXT NOT NULL (List of unverified or external consumers causing unknowns)
- `evaluated_at`: TEXT NOT NULL

### 2.6 `lineage_change_reviews`
Multi-role approval ledger with separation-of-duties enforcement.
- `id`: TEXT PRIMARY KEY
- `organization_id`: TEXT NOT NULL
- `change_request_id`: TEXT NOT NULL REFERENCES `lineage_change_requests`(id)
- `reviewer_id`: TEXT NOT NULL
- `review_role`: TEXT NOT NULL (`CLINICAL_DIRECTOR`, `DATA_ARCHITECT`, `LEGAL_COUNSEL`, `CISO`)
- `decision`: TEXT NOT NULL (`approved`, `rejected`, `revision_requested`)
- `rationale`: TEXT NOT NULL
- `reviewed_at`: TEXT NOT NULL

---

## 3. Graph Traversal Algorithms

1. **Cycle-Safe Traversal:** Traversal maintains a visited set. Re-encountering an in-path node stops further branch expansion without erroring.
2. **Depth-Bounded:** Maximum exploration depth (default 10) prevents unbounded searches.
3. **Upstream (Provenance / Root Cause):** Finds all nodes that supply data to the target node.
4. **Downstream (Impact / Blast Radius):** Finds all consumers, read models, APIs, and exports reachable from the modified node.
5. **Unknown Propagation Rule:** If any node in the downstream blast radius has `verification_status == 'unknown'` or relationship with unknown consumer, the report flags `recommended_release_gate = BLOCKED_BY_UNKNOWNS`.

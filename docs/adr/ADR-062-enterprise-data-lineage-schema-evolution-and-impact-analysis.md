# ADR-062: Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine

- **Status:** Accepted  
- **Date:** 2026-10-14  
- **Context:** Prompt 43 mandates an Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine for ZAYVORA MATAB OS to map end-to-end data dependencies across domain entities, database tables, REST APIs, asynchronous event topics, workflow rules, terminology concepts, and analytics cubes. The system must assess the blast radius of proposed schema, API, or data contract evolutions before releases are deployed. Core non-negotiables demand that "Impact unknown" is a real result (never an optimistic "no impact"), zero autonomous clinical alterations, zero fabrication of dependencies, strict separation of duties (authors cannot self-approve release gates), and zero protected health information (PHI) stored in lineage graph models.

## Decision

1. **Database Schema (Migration 042):**
   - `lineage_contracts_registry`: Machine-readable data and API contract specifications (`database`, `api`, `event`, `import`, `export`, `terminology`, `metric`, `configuration`) with SemVer versions, compatibility policies (`BACKWARD`, `FORWARD`, `FULL`, `STRICT_BREAKING`), sensitivity classifications (`PUBLIC`, `INTERNAL`, `RESTRICTED_PHI`, `FINANCIAL`), and explicit documented limitations.
   - `lineage_nodes`: Catalog of dependency graph nodes (`domain_entity`, `db_table`, `db_column`, `api_endpoint`, `event_topic`, `workflow_rule`, `terminology_concept`, `analytics_metric`, `external_integration`) referencing governing contracts.
   - `lineage_edges`: Directed dependency edges (`produces`, `reads`, `writes`, `transforms`, `validates`, `publishes`, `subscribes_to`, `maps_to`, `aggregates_into`, `indexes_into`, `exports_to`, `authorizes`, `audits`, `depends_on`) with explicit evidence types (`code_reference`, `schema_fk`, `test_assertion`, `config`, `manual_audit`) and verification status (`verified`, `inferred`, `unknown`, `stale`, `not_applicable`).
   - `lineage_change_requests`: Governed change proposal lifecycle tracking (`draft`, `analysis_pending`, `review_required`, `blocked_by_unknowns`, `approved_for_test`, `testing`, `approved_for_release`, `deployed_pending_verification`, `verified`, `rejected`, `rolled_back`, `closed`).
   - `lineage_impact_reports`: Deterministic graph traversal analysis results detailing direct consumers, transitive blast radius, affected APIs/metrics, compatibility classifications (`additive_compatible`, `conditionally_compatible`, `breaking`, `semantically_breaking`), clinical safety / financial / privacy impact flags, recommended release gates (`PROCEED`, `MANUAL_REVIEW_REQUIRED`, `BLOCKED_BY_UNKNOWNS`), and known unknowns.
   - `lineage_change_reviews`: Multi-stakeholder approval ledger (`CLINICAL_DIRECTOR`, `DATA_ARCHITECT`, `LEGAL_COUNSEL`, `CISO`) enforcing separation of duties.

2. **Domain Architecture (`EnterpriseDataLineageEngine`):**
   - Cycle-safe, depth-bounded breadth-first graph traversal for both downstream blast radius and upstream provenance tracing.
   - "Impact Unknown" Rule: Any uninstrumented dynamic caller, contract limitation, or unverified edge encountered during downstream traversal automatically sets the recommended release gate to `BLOCKED_BY_UNKNOWNS` and transitions the change request to `blocked_by_unknowns`.
   - Separation of Duties: The change request creator is strictly prevented from self-approving their release gate.
   - Clinical Safety Invariant: When the clinical safety flag is active, approval by a `CLINICAL_DIRECTOR` is mandatory prior to technical release.

3. **REST API Interface & Web UI:**
   - 17 REST API endpoints mounted under `/api/v1/lineage/` in `apps/api/router.py`.
   - Dedicated workbench in `knowledge_admin.js` under the `Data Lineage & Evolution (P43)` tab, featuring summary metrics, contract management, interactive cycle-safe dependency tracer, and change proposal impact analyzer.

## Consequences

- **Positives:** Completely eliminates blind database migrations, unannounced breaking API changes, and silent semantic drift in clinical calculations.
- **Auditing:** All schema evolutions and reviews are fully auditable with evidence paths and cryptographic identifiers.
- **Safety:** Prevents autonomous release whenever unknown external dependencies or unverified data consumers exist.

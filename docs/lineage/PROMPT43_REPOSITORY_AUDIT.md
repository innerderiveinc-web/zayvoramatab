# ZAYVORA MATAB OS — PROMPT 43 REPOSITORY AUDIT & LINEAGE DISCOVERY REPORT
**Module:** Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine  
**Status:** IMPLEMENTATION AUDIT & INVENTORY  
**Date:** 2026-10-14  
**Auditor:** Principal Software & Reliability Architect, Data Lineage & Clinical Governance Specialist

---

## 1. Executive Summary

ZAYVORA MATAB OS operates a multi-layered healthcare data platform spanning Unani clinical medicine, patient encounters, pharmacovigilance, longitudinal health records, billing, inventory, analytics, and ABDM interoperability. As the system scales to enterprise multi-branch operations, changes to database schemas, REST APIs, domain event topics, clinical decision rules, terminology vocabularies, and analytics read models present risks of unpredicted downstream breaks, semantic divergence, or clinical safety regressions.

This audit establishes the baseline evidence inventory for **Prompt 43**, identifying:
1. Producers, transformations, and consumers across the entire data estate.
2. Direct code vs. inferred relationships vs. dynamic/external unverified consumers.
3. The core design requirement: **"Impact Unknown" is an explicit high-risk classification**, never converted into an optimistic "no impact".
4. The requirement for zero fabrication and immutable clinical boundaries.

---

## 2. Inventory of Existing Data Estate & Producers/Consumers

### 2.1 Database Tables & Migrations (001 - 041)
- **Core Patient & Encounters (001-005):** `patients`, `patient_contacts`, `patient_addresses`, `encounters`, `prescriptions`, `nuskha_formulations`, `modern_clinical_assessments`.
- **Knowledge & Safety Firewalls (006-008, 017-022):** `clinical_knowledge_sources`, `unani_ontology_catalog`, `safety_contraindication_rules`, `hybrid_rag_queries`, `clinical_decision_support_runs`.
- **Operations, Billing & Multi-Branch (009-011):** `appointments`, `invoices`, `inventory_batches`, `organizations`, `facilities`.
- **Interoperability & Analytics (012, 031-032):** `fhir_bundles`, `abdm_consents`, `analytics_metrics`, `kpi_cubes`.
- **Reliability & Operations (033-039):** `command_center_alerts`, `workflow_rules`, `slo_definitions`, `incidents`, `dr_backups`, `failover_plans`.
- **Lifecycle & Master Data Governance (040-041):** `lifecycle_retention_policies`, `legal_holds`, `mdm_master_records`, `mdm_stewardship_tasks`.

### 2.2 API Contracts & Endpoints
- REST API layer exposed via `apps/api/router.py` across 30+ domain subrouters (`/api/v1/patients`, `/api/v1/encounters`, `/api/v1/mdm`, `/api/v1/lifecycle`, etc.).
- External clients include: Web Workbench SPA (`apps/web`), ABDM Gateway, Laboratory systems, Mobile clinician apps.

### 2.3 Event Queues & Asynchronous Processing
- Internal event dispatcher with topic subscriptions for pharmacovigilance alerts, timeline projection updates, audit ledger writes, and notification dispatch.

---

## 3. Evidence Classification Standards

In accordance with Prompt 43 non-negotiables, all lineage edges are classified with explicit evidence types:
1. `code_reference`: Direct, static AST or import/call reference verified in codebase.
2. `schema_fk`: Relational foreign key constraint verified in SQLite schema.
3. `test_assertion`: Direct automated integration test validating cross-component contract.
4. `config`: Explicit configuration or routing mapping.
5. `manual_audit`: Verified clinical or architectural review ledger entry.

Verification states:
- `verified`: Evidence directly exists and has been proven by static check or test.
- `inferred`: Pattern-matched or probable relationship without full runtime proof.
- `unknown`: Consumer or producer known to exist (e.g., dynamic external webhook, third-party analytics export), but exact schema contract is uninstrumented.
- `stale`: Relationship verified against an older schema version but unverified in current release.
- `not_applicable`: Deprecated edge.

---

## 4. Release Gate & Change Classification Matrix

| Compatibility Classification | Description | Default Release Gate |
|---|---|---|
| `additive_compatible` | New optional fields, non-breaking new endpoints, backward-compatible additions. | `approved_for_test` / `PROCEED` |
| `conditionally_compatible` | Deprecations with fallbacks, optional parameters, versioned migrations. | `review_required` / `MANUAL_REVIEW_REQUIRED` |
| `breaking` | Removed fields, renamed endpoints, non-null columns added without defaults, changed response formats. | `review_required` (Multi-party sign-off) |
| `semantically_breaking` | Schema unchanged syntactically, but units changed (e.g., mg to g), dosage calculation formulas altered, or ICD/NAMASTE mapping semantics redefined. | `review_required` (Clinical Director mandatory approval) |
| `unassessed` / `unknown` | Dependency graph touches unknown consumers or external integrations without explicit contract schema. | `blocked_by_unknowns` |

---

## 5. Non-Negotiable Governance Invariants
1. **Separation of Duties:** The author of a change request cannot approve their own release gate.
2. **Clinical Safety Immutability:** Finalized clinical encounter notes, signed prescriptions, and signed assessments can never have their schema or data mutated by lineage automation.
3. **Reproducibility & Zero PHI:** The lineage engine tracks schemas, contracts, and field types; it never ingests or stores Protected Health Information (PHI).

# ZAYVORA MATAB OS — PROMPT 20 REPOSITORY AUDIT
## Unani Clinical Knowledge Mapping & Organ-Axis Relationship Engine
**Phase 20 Prerequisite Inspection, Gap Analysis & Architecture Verification**

---

### 1. Repository & Runtime Architecture Inspection

The standalone repository `zayvora-matab-os` was inspected for existing clinical knowledge mapping, ontology foundations, and Organ-Axis implementations.

- **Operating Environment:** Standalone modular monolith; Python 3 runtime; SQLite 3 with WAL mode (`matab.db`) mimicking PostgreSQL ANSI SQL conventions; Zero external runtime or legacy ZAYVORA Health OS dependencies.
- **Database Migrations:** 18 migrations applied sequentially from `001_foundation_schema.sql` through `018_unani_ontology_catalog_schema.sql`.
- **Existing Prerequisite Subsystems Verified:**
  - `knowledge_sources` & `kavs_source_versions`: Governed source registry with edition, rights metadata, and SHA-256 document hashing (Prompt 17).
  - `kavs_source_locators`: Fine-grained page, chapter, section, and anchor locators (Prompt 17).
  - `kavs_source_verification_events`: Role-gated physical passage and authority verification (Prompt 17).
  - `kavs_ingestion_jobs` & `kavs_extraction_pages`: 21-state machine preserving distinct physical `pdf_page_index` and `printed_page_label` (Prompt 18).
  - `kavs_extraction_segments` & `kavs_extraction_corrections`: Verifiable text segments tracking `machine_raw` vs `human_checked` fidelity with immutable diffs (Prompt 18).
  - `knowledge_concepts`: Stable concept identity with multi-script `concept_names`, Mufradat `material_identity`, Murakkabat `catalog_formulations`, and `knowledge_assertions` (Prompt 19).
  - `concept_relations`: Typed relationship table requiring supporting assertion IDs for clinical and safety edges (Prompt 19).
  - `organ_axis_concepts` & `organ_axis_mappings`: Foundational anatomical concepts and basic contextual associations from Prompt 04.
  - `catalog_change_events` & `kavs_audit_events`: Tamper-evident append-only audit ledgers.

---

### 2. Executable Prerequisite Evidence (Prompts 17, 18, and 19)

Direct automated test execution was verified across all KAVS Foundation, Ingestion Workbench, and Unani Ontology test suites:

```bash
python3 -m unittest \
  tests/unit/test_kavs_foundation.py \
  tests/integration/test_kavs_foundation_api.py \
  tests/unit/test_kavs_ingestion_workbench.py \
  tests/integration/test_kavs_ingestion_api.py \
  tests/unit/test_unani_ontology.py \
  tests/integration/test_unani_ontology_api.py
```

**Results:**
- `test_kavs_foundation.py`: 12/12 PASSED (Source registry, locators, verification events, policy rules).
- `test_kavs_foundation_api.py`: 5/5 PASSED (REST API contract, permission checks, audit logging).
- `test_kavs_ingestion_workbench.py`: 17/17 PASSED (Magic byte checks, rights preflights, 21-state machine, high-risk scanner, drafts segregation).
- `test_kavs_ingestion_api.py`: 6/6 PASSED (REST endpoints for file uploads, pages, tables, corrections, drafts).
- `test_unani_ontology.py`: 20/20 PASSED (Concept identity, multi-script names, Mufradat ambiguity, traditional units, optimistic concurrency).
- `test_unani_ontology_api.py`: 6/6 PASSED (REST endpoints for ontology concepts, formulations, assertions, search).
- **Total Executed:** 66 tests in 3.102s, **100% PASSED**.

**Full Platform Regression Suite:**
- 302 tests across 19 modules executed in 21.566s, **100% PASSED** (0 failures, 0 errors).

---

### 3. Capability Matrix for Prompt 20 Scope

| Capability / Requirement | Current Status | Current Implementation / Gap | Strategy for Prompt 20 |
|---|---|---|---|
| Controlled Relation-Type Registry | `partially_implemented` | `concept_relations` exists in migration 018 but lacks formal predicate registry table with constraints and allowed intended uses | Implement `relation_type_registry` with subject/object type constraints, directionality, clinical actionability flag, and required reviewer roles. |
| Versioned Organ-Axis Framework Object | `not_implemented` | Migration 004 has flat `organ_axis_mappings`; lacks versioned framework metadata, purpose, and limitations | Implement `organ_axis_frameworks` (`product_navigation_model`, `traditional_model`, `research_model`, `clinical_model`) with explicit lifecycle states. |
| Organ-Axis Concept Memberships | `partially_implemented` | `organ_axis_concepts` exists; lacks typed membership (`navigation_group`, `source_documented`, `reviewed_clinical`) | Implement `organ_axis_memberships` linking concepts to frameworks with assertion links. |
| Provenance-Bound Relationship Engine | `partially_implemented` | `concept_relations` and `knowledge_assertions` exist; lacks relationship level classification and bounded traversal | Extend relationship service with explicit relationship levels (`UI/navigation grouping`, `classical-text`, `clinician-authored`, `reviewed evidence-based`, `research hypothesis`). |
| Cross-Disciplinary Concept Mappings | `partially_implemented` | `external_identifier_crosswalks` exists; lacks formal target system versioning and bidirectional mapping scopes | Implement `concept_mappings` preserving mapping type (`exact`, `broader_than`, `candidate_equivalence`, etc.) with clinician-facing decision support isolation. |
| Relationship Conflict Adjudication | `not_implemented` | No conflict detection or resolution table exists | Implement `relationship_conflicts` with conflict types, resolution states, and mandatory rationale. |
| Encounter-Scoped Hypothesis Linking | `not_implemented` | Clinicians cannot currently attach case hypotheses linked to ontology concepts in encounters | Implement `case_hypothesis_links` strictly scoped to patient encounters; forbid writeback to global ontology graph. |
| Clinician UI with Sourced Labels & Limitations | `partially_implemented` | Knowledge Admin UI exists; lacks Organ-Axis framework inspection and relationship provenance drawer | Add Organ-Axis & Clinical Knowledge Mapping view in Knowledge Admin UI. |

---

### 4. Architectural Decisions & Non-Negotiables

1. **Preserve Backward Compatibility:** The existing endpoints `/api/v1/organ-axis/concepts` and `/api/v1/organ-axis/mappings` used in clinical encounters remain functional while connecting to the new versioned framework backend.
2. **Reuse Prompt 19 Schema:** `knowledge_concepts`, `knowledge_assertions`, `kavs_extraction_segments`, and `catalog_change_events` are reused directly without duplication.
3. **No Graph Proximity Inference:** A relationship between concept A and concept B never implies a clinical relationship between concept A and concept C. Transitive closure and embedding-based link completion are strictly prohibited in clinical decision support.
4. **Organ-Axis Causality Guard:** An Organ-Axis link between Meda (Stomach) and Dimagh (Brain) represents a documented classical association or product navigation group; it does NOT prove modern neuro-gastroenterological causality or treatment efficacy unless an independent modern evidence assertion is approved.
5. **Patient Data Isolation:** Case hypotheses recorded during patient consultations reside strictly in `case_hypothesis_links` within the patient clinical record and can never mutate the global knowledge graph.

**Audit Conclusion:** Prerequisites are verified and operational. Proceeding with Migration 019, relationship type registry, domain engine, REST APIs, UI workbench, and automated test suite.

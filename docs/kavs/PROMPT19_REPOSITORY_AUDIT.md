# ZAYVORA MATAB OS — PROMPT 19 REPOSITORY AUDIT
## Unani Ontology, Canonical Terminology & Mufradat/Murakkabat Structured Catalog
**Phase 19 Prerequisite Inspection & Architecture Verification**

---

### 1. Repository & Runtime Architecture Inspection

The standalone repository `zayvora-matab-os` was inspected for existing knowledge, governance, provenance, and terminology capabilities.

- **Operating Environment:** Standalone modular monolith; Python 3 runtime; SQLite 3 with WAL mode (`matab.db`) mimicking PostgreSQL ANSI SQL conventions; Zero external runtime or legacy ZAYVORA Health OS dependencies.
- **Database Migrations:** 17 migrations applied sequentially from `001_foundation_schema.sql` through `017_kavs_source_ingestion_extraction_workbench_schema.sql`.
- **Existing Prerequisite Subsystems Verified:**
  - `knowledge_sources` & `kavs_source_versions`: Governed source registry with edition, rights metadata, and SHA-256 document hashing.
  - `kavs_source_locators`: Fine-grained page, chapter, section, and anchor locators.
  - `kavs_source_verification_events`: Role-gated physical passage and authority verification.
  - `kavs_governance_policies`: Versioned policy rules (`KAVS-POL-001`).
  - `kavs_source_files` & `kavs_rights_preflight_events`: Checksum-verified binary storage with magic byte inspection and rights preflight gates (`RETAIN_FILE`, `EXTRACT_TEXT`, `INDEX_VECTORS`, `EXPORT_REDISTRIBUTE`).
  - `kavs_ingestion_jobs` & `kavs_extraction_pages`: 21-state machine preserving distinct physical `pdf_page_index` and `printed_page_label`.
  - `kavs_extraction_segments` & `kavs_extraction_corrections`: Verifiable text segments tracking `machine_raw` vs `human_checked` fidelity with immutable before/after diffs.
  - `kavs_claim_drafts`: Candidate drafts mathematically segregated from consultation retrieval until human promotion.
  - `kavs_audit_events`: Tamper-evident append-only audit ledger.

---

### 2. Executable Prerequisite Evidence (Prompts 17 & 18)

Direct automated test execution was performed across all KAVS Foundation and Ingestion Workbench test suites:

```bash
python3 -m unittest \
  tests/unit/test_kavs_foundation.py \
  tests/integration/test_kavs_foundation_api.py \
  tests/unit/test_kavs_ingestion_workbench.py \
  tests/integration/test_kavs_ingestion_api.py
```

**Results:**
- `test_kavs_foundation.py`: 12/12 PASSED (Source registry, locators, verification events, policy rules, claim approvals, withdrawal).
- `test_kavs_foundation_api.py`: 5/5 PASSED (REST API contract, permission checks, audit logging).
- `test_kavs_ingestion_workbench.py`: 17/17 PASSED (Magic byte checks, rights preflights, 21-state machine, high-risk scanner, corrections, drafts segregation, promotion gate).
- `test_kavs_ingestion_api.py`: 6/6 PASSED (REST endpoints for file uploads, pages, tables, corrections, drafts).
- **Total Executed:** 40 tests in 2.335s, **100% PASSED**.

**Full Platform Regression Suite:**
- 276 tests across 18 modules executed in 22.586s, **100% PASSED** (0 failures, 0 errors).

---

### 3. Capability Matrix for Prompt 19 Scope

| Capability / Requirement | Current Repository Status | Evidence / Notes | Strategy for Prompt 19 |
|---|---|---|---|
| Governed Source Registry & Locators | `implemented_and_tested` | `knowledge_sources`, `kavs_source_locators` (Prompt 17) | Reuse directly as foreign key anchors for passages and assertions. |
| Text Ingestion & Extraction Segments | `implemented_and_tested` | `kavs_extraction_pages`, `kavs_extraction_segments` (Prompt 18) | Reuse segments as exact source passage grounding. |
| Audit Trail & State Transitions | `implemented_and_tested` | `kavs_audit_events`, `audit_events` | Reuse append-only pattern; emit `catalog_change_events`. |
| Canonical Concept Identity Model | `partially_implemented` | `knowledge_items` has general concepts; lacks strict distinction between concept identity vs assertions | Implement `knowledge_concepts` with `concept_type`, resolution state, and versioning. |
| Multi-Script Concept Names & Transliteration | `partially_implemented` | `aliases_json` in `knowledge_items` lacks source passage linking and review states | Implement `concept_names` with original script, language tags, transliteration scheme, and review state. |
| Mufradat (Single Material) Identity with Ambiguity | `not_implemented` | `ingredient_catalog` exists for dispensing but lacks formal taxonomic authority, identity status, or ungrounded ambiguity modeling | Implement `material_identity` with explicit `unresolved`, `candidate`, `reviewed`, `disputed` states and botanical/mineral classes. |
| Murakkabat (Formulation) Structured Catalog | `partially_implemented` | `formulations` table in Migration 003 is scoped to clinic prescriptions; lacks source-edition catalog grounding | Implement `catalog_formulations` with source edition link and dosage form classification. |
| Source-Backed Formulation Component Statements | `not_implemented` | Migration 003 `formulation_ingredients` stores raw mg integers; cannot store traditional units or unresolved materials | Implement `catalog_formulation_ingredients` preserving original notations, units (`masha`, `tola`), and component identity states. |
| Provenance-Bound Knowledge Assertions | `partially_implemented` | `knowledge_claims` exists; lacks granular typed predicates (`has_temperament`, `has_action`, etc.), exact passage quotations, and approved intended use | Implement `knowledge_assertions` with strict predicates, passage citations, and intended-use scoping. |
| Typed Concept Relations Registry | `partially_implemented` | `knowledge_relationships` exists; lacks non-inference by graph adjacency enforcement | Implement `concept_relations` requiring substantive assertions for clinical edges. |
| Modern Taxonomy Crosswalks | `not_implemented` | None exists | Implement `external_identifier_crosswalks` with mandatory mapping types (`exact`, `candidate_equivalence`, etc.) where candidate equivalence is blocked from decision support. |
| Multi-Script Explainable Search | `partially_implemented` | `KnowledgeRetrievalEngine` has hybrid search; needs separation between authoring search and clinician search | Build dedicated `OntologySearchService` with original-script, transliteration, explainable match reasons, and unapproved alias masking. |
| Reviewer Workbench for Terminology & Catalog | `not_implemented` | Only claim approval queue exists | Extend Knowledge Admin UI with Terminology & Catalog Review workbench. |

---

### 4. Architectural Decisions & Non-Negotiables

1. **No Duplicate Engines:** Rather than creating a disconnected second catalog, the new ontology tables (`knowledge_concepts`, `concept_names`, `material_identity`, `catalog_formulations`, `catalog_formulation_ingredients`, `knowledge_assertions`, `concept_relations`, `external_identifier_crosswalks`) will integrate directly with `knowledge_sources`, `kavs_source_locators`, and `kavs_extraction_segments`.
2. **Schema Separation:** To avoid breaking the existing operational dispensing module (`formulations` in migration 003), the literature/evidence catalog will use `catalog_formulations` and `catalog_formulation_ingredients`.
3. **No Automatic Equivalence:** Similar transliterations (e.g., *Asgand* vs *Ashwagandha*, or different varieties of *Terminalia*) remain distinct concepts unless linked by an approved, reviewed assertion.
4. **Preservation of Raw Notations:** Traditional units (*masha*, *tola*, *dam*, *ratti*) are never coerced to grams without an explicit, approved conversion rule.
5. **No Graph Inference:** A relationship edge between a herb and a disease in `concept_relations` never constitutes clinical evidence by itself. Every clinical assertion requires an individual, provenance-backed `knowledge_assertion`.

**Audit Conclusion:** Prerequisites 17 and 18 are 100% verified and operational. Proceeding with Migration 018, domain service, APIs, search engine, UI workbench, and comprehensive test suite.

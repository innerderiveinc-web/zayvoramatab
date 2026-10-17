# ZAYVORA MATAB OS — PROMPT 21 REPOSITORY AUDIT
## Evidence Classification, Clinical Claim Verification & Citation Validation Engine
**Phase 21 Prerequisite Inspection, Gap Analysis & Architecture Verification**

---

### 1. Repository & Runtime Architecture Inspection

The standalone repository `zayvora-matab-os` was inspected for existing evidence characterization, citation validation, claim support checking, and clinical publication gating:

- **Operating Environment:** Standalone modular monolith; Python 3 runtime; SQLite 3 with WAL mode (`matab.db`) mimicking PostgreSQL ANSI SQL conventions; Zero external runtime or legacy ZAYVORA Health OS dependencies.
- **Database Migrations:** 19 migrations applied sequentially from `001_foundation_schema.sql` through `019_unani_clinical_knowledge_mapping_organ_axis_schema.sql`.
- **Existing Prerequisite Subsystems Verified:**
  - `knowledge_sources` & `kavs_source_versions`: Governed source registry with edition, rights metadata, and SHA-256 document hashing (Prompt 17).
  - `kavs_source_locators`: Fine-grained page, chapter, section, and anchor locators (Prompt 17).
  - `kavs_source_verification_events`: Role-gated physical passage and authority verification (Prompt 17).
  - `kavs_ingestion_jobs` & `kavs_extraction_pages`: 21-state machine preserving distinct physical `pdf_page_index` and `printed_page_label` (Prompt 18).
  - `kavs_extraction_segments` & `kavs_extraction_corrections`: Verifiable text segments tracking `machine_raw` vs `human_checked` fidelity with immutable diffs (Prompt 18).
  - `knowledge_concepts`: Stable concept identity with multi-script `concept_names`, Mufradat `material_identity`, Murakkabat `catalog_formulations`, and `knowledge_assertions` (Prompt 19).
  - `relation_type_registry` & `relationship_assertions`: Governed relationship predicates and provenance assertions with bounded graph traversal (Prompt 20).
  - `organ_axis_frameworks` & `organ_axis_memberships`: Product navigation models isolated from clinical decision support (Prompt 20).
  - `relationship_conflicts`: Formal adjudication queue tracking conflicting assertions and rationale (Prompt 20).
  - `case_hypothesis_links`: Encounter-scoped clinician hypotheses isolated from global ontology (Prompt 20).

---

### 2. Executable Prerequisite Evidence (Prompts 17–20)

Automated tests across all foundational KAVS, Ingestion Workbench, Unani Ontology, and Knowledge Mapping test suites run with 100% pass rate:
- `test_kavs_foundation.py` & `test_kavs_foundation_api.py`: 17 tests PASSED.
- `test_kavs_ingestion_workbench.py` & `test_kavs_ingestion_api.py`: 23 tests PASSED.
- `test_unani_ontology.py` & `test_unani_ontology_api.py`: 26 tests PASSED.
- `test_knowledge_mapping.py` & `test_knowledge_mapping_api.py`: 23 tests PASSED.
- **Total KAVS Predecessor Tests:** 89 tests PASSED in 3.8s.
- **Full Platform Regression Suite:** 325 tests PASSED across all modules.

---

### 3. Capability Matrix for Prompt 21 Scope

| Capability / Requirement | Current Status | Current Implementation / Gap | Strategy for Prompt 21 |
|---|---|---|---|
| Atomic Claim Taxonomy Registry | `partially_implemented` | `knowledge_claims` has a basic `claim_type` field; lacks formal 14-category versioned registry | Implement `claim_type_registry` with categories A–N, allowed evidence types, and intended-use gates. |
| Claim-to-Source Passage Linking | `partially_implemented` | `knowledge_assertions` links to `source_passage_id`; lacks explicit link roles (`primary_support`, `contradictory`, `context`, etc.) | Implement `claim_source_links` linking claims/assertions to exact source passages with roles and access states. |
| Multi-Dimensional Citation Validation | `not_implemented` | No multi-dimensional validation run table exists; risk of collapsing validity into a single boolean | Implement `citation_validation_runs` tracking bibliographic identity, version status, passage fidelity, claim support, applicability, and intended use independently. |
| Support Assessment Engine | `not_implemented` | No structured support assessment with controlled outcomes (`direct_support`, `partial_support`, `contradicts_claim`, etc.) | Implement `support_assessments` capturing supported/unsupported components, qualifiers, and reviewer decisions. |
| Question-Sensitive Evidence Characterization | `partially_implemented` | `kavs_claim_verifications` has a flat `evidence_characterization` field; lacks structured study details | Implement `evidence_characterizations` capturing question type, study design, population, intervention, comparator, outcomes, and risk of bias without numeric grading. |
| Source Status Event Monitoring | `not_implemented` | No tracking of retractions, expressions of concern, or version updates affecting live claims | Implement `source_status_events` with automated propagation and suspension of dependent clinical claims. |
| Intended-Use Approval Gating | `partially_implemented` | `intended_use_approval` string exists; lacks formal time-bounded approval object with expiry and suspension | Implement `intended_use_approvals` enforcing surface restrictions, audience, conditions, and expiry/suspension. |
| Evidence Contradiction & Conflict Queue | `partially_implemented` | `relationship_conflicts` exists for ontology relations; lacks claim-level evidence conflict resolution | Implement `evidence_conflicts` with open, under review, and resolved-with-scope workflows. |
| Traditional-Use vs Modern-Evidence Distinction | `not_implemented` | UI and APIs lack standardized statement templates preventing claim laundering | Enforce distinct statement templates for traditional-source documentation vs preclinical vs observational vs interventional vs guideline. |

---

### 4. Architectural Decisions & Non-Negotiables

1. **Never Fabricate Metadata or Effect Sizes:** No sample sizes, p-values, odds ratios, or effect estimates may be invented. Missing details remain explicitly `not_reported` or `unclear`.
2. **Dimension Independence:** A valid bibliographic match never implies claim support. Support assessment is evaluated strictly against the accessible source passage.
3. **No LLM Auto-Approval:** AI-assisted validation produces `ai_proposed` draft assessments only. Human reviewer role and mandatory rationale are required for publication.
4. **No Claim Laundering:** Traditional-source documentation must never be presented as modern clinical efficacy; animal and in-vitro results must never be presented as human benefits.
5. **Fail-Closed Clinical Publication:** If citation validation fails, passage fidelity is unresolved, or a source is retracted, the claim is blocked from clinical workflows.

**Audit Conclusion:** Prerequisites are verified and operational. Proceeding with Migration 020, domain engine, REST routes, UI workbench, and test suite.

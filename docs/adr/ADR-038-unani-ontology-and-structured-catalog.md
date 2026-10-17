# ADR-038: Unani Ontology, Canonical Terminology & Mufradat/Murakkabat Structured Catalog (Prompt 19)

- **Status:** Accepted
- **Date:** October 2026
- **Context:**
  Prompt 19 defines the requirements for a source-grounded, versioned, reviewable Unani terminology and catalog layer. A fundamental problem in traditional AYUSH digital systems is the conflation of concept identity with clinical claims, the automatic merging of superficially similar transliterations, the hallucination of botanical species for unresolved vernacular names, and the premature normalization of traditional posology units. Furthermore, clinical assertions cannot be inferred merely from graph adjacency. A robust, auditable ontology and catalog layer is required that enforces strict separation between identity and claims, multi-script original wording preservation, first-class ambiguity representation for Mufradat, source-edition cataloging for Murakkabat with verbatim traditional units, and isolated review queues.

- **Decision:**
  1. **Canonical Concept Identity (`knowledge_concepts`):** Concept records represent stable identity objects (`unani_term`, `clinical_process`, `organ_or_structure`, `material`, `ingredient`, `formulation`, `dosage_form`, `preparation_method`, `assessment_concept`, `external_concept`). Identity status explicitly tracks `unresolved`, `candidate`, `resolved`, and `disputed`. Optimistic concurrency is enforced via version numbers.
  2. **Multi-Script Names & Aliases (`concept_names`):** Retains original script (`arabic`, `urdu`, `persian`, `devanagari`, `latin`), language tags (`ur`, `ar`, `fa`, `hi`, `en`), transliteration schemes, and derived normalized search tokens without overwriting original wording. Unapproved candidate aliases are strictly masked from clinician-facing queries.
  3. **Mufradat Material Identity (`material_identity`):** Single-drug substances track botanical, animal, mineral, or salt classes. Ambiguity is first-class: common names do not auto-map to Latin binomials without documented source proof and human review.
  4. **Murakkabat Formulation Catalog (`catalog_formulations`, `catalog_formulation_ingredients`):** Formulations are tied to specific source editions. Ingredient statements preserve exact traditional notations (`quantity_expression_original` e.g. "2 1/2 masha") and original units (`quantity_unit_original` e.g. "masha", "tola"). Metric normalization is forbidden without an approved conversion rule.
  5. **Provenance-Bound Knowledge Assertions (`knowledge_assertions`):** Granular assertions bound to exact source passage locators and verbatim quotations. Clinical predicates (`has_mizaj`, `has_action`, `indicated_for`, `contraindicated_in`, `has_dose`) require source passage grounding. Claims must be reviewed and approved for a specific intended use (`clinician_contextual_reference`, `formulation_catalog_reference`, `safety_firewall_rule`) before clinical exposure.
  6. **Typed Concept Relations (`concept_relations`):** Graph relations require supporting assertion IDs for clinical and safety edges. Graph adjacency is strictly barred from being interpreted as clinical evidence by itself.
  7. **Modern Taxonomy Crosswalks (`external_identifier_crosswalks`):** Maps concepts to external standards (MeSH, SNOMED-CT, POWO, IPNI). Entries marked `candidate_equivalence` are explicitly excluded from clinical decision support.
  8. **Multi-Script Explainable Search (`UnaniOntologyEngine.search_catalog`):** Supports Urdu/Arabic, transliteration, and normalized text searches. Results return explainable match reasons (`EXACT_NORMALIZED_MATCH`, `ORIGINAL_SCRIPT_MATCH`, `TRANSLITERATION_MATCH`). Clinician-facing mode filters unapproved aliases and concepts.
  9. **Append-Only Audit Ledger (`catalog_change_events`) & Review Tasks (`catalog_review_tasks`):** Every mutation records actor, timestamp, prior state, new state, and rationale. Review tasks route items to assigned roles (`UNANI_SCHOLAR`, `BOTANIST`, `PHARMACOGNOSIST`).

- **Consequences:**
  - Zero possibility of AI hallucination corrupting classical Unani concept identities or formulation recipes.
  - Complete legal and clinical traceability for all terminology and catalog recommendations.
  - Full conformance with Prompt 19 specifications.

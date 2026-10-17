# ADR-040: Evidence Classification, Clinical Claim Verification & Citation Validation Engine (Prompt 21)

- **Status:** Accepted
- **Date:** October 2026
- **Context:**
  Prompt 21 mandates an auditable governance engine that records the nature and quality of evidence provided by a source, validates whether a citation actually supports the specific claim attached to it, preserves the epistemological boundary between traditional-use documentation and modern clinical efficacy, and prevents unsupported, retracted, or misrepresented claims from surfacing in clinical workflows.
  A pervasive defect in clinical software and AI assistants is "citation decoration"—attaching real bibliographic citations that do not support the specific therapeutic claims asserted, or "claim laundering"—treating traditional usage documentation as proven modern clinical efficacy, preclinical animal/in-vitro assays as proven human clinical cures, or observational associations as established causality.
  Furthermore, collapsing validation dimensions into a single boolean `is_valid` flag obscures fatal flaws (such as valid bibliographic identity with invalid passage support, or valid passage support with a retracted publication).

- **Decision:**
  1. **Controlled Claim-Type Registry (`claim_type_registry`):** All claims are categorized into 15 mutually exclusive controlled codes across categories A through N plus Z:
     - `bibliographic_provenance` (A)
     - `source_content` (B)
     - `traditional_use_documentation` (C)
     - `terminology_identity` (D)
     - `regulatory_quality` (E)
     - `guideline_recommendation` (F)
     - `evidence_synthesis` (G)
     - `safety_information` (H)
     - `preclinical_evidence` (I)
     - `observational_clinical` (J)
     - `interventional_clinical` (K)
     - `mechanistic_causal` (L)
     - `product_framework_editorial` (M)
     - `clinical_outcome` (N)
     - `unclassified_needs_review` (Z)
     Each type governs permitted source evidence patterns, reviewer credential requirements, and intended-use surface restrictions.
  2. **Atomic Claim-Source Links (`claim_source_links`):** Claims link to specific sources, edition versions, and extracted text segments with explicit link roles (`primary_support`, `secondary_support`, `contradictory_evidence`, `context`, `background`, `methodology`, `guideline_basis`) and source access states.
  3. **Multi-Dimensional Citation Validation (`citation_validation_runs`):** Replaces binary validation with 6 independent, non-collapsible dimensions:
     - Dimension 1: Bibliographic Identity (`verified`, `mismatch`, `unresolved`, `not_checked`)
     - Dimension 2: Version and Retraction Status (`current`, `superseded`, `retracted`, `expression_of_concern`, `withdrawn`, `unverified`)
     - Dimension 3: Passage Fidelity (`exact_match`, `minor_discrepancy`, `fidelity_unresolved`, `negation_mismatch`, `locator_not_found`, `not_checked`)
     - Dimension 4: Claim Support State (`direct_support`, `partial_support`, `context_only`, `contradicts_claim`, `does_not_address_claim`, `source_unavailable`, `citation_mismatch`, `passage_not_found`, `extraction_fidelity_unresolved`, `applicability_uncertain`, `reviewer_disagreement`, `not_assessed`)
     - Dimension 5: Applicability State (`direct`, `indirect_population`, `indirect_intervention`, `indirect_outcome`, `uncertain`, `not_applicable`)
     - Dimension 6: Intended-Use State (`approved`, `unapproved`, `restricted`, `suspended`, `expired`)
  4. **Question-Sensitive Evidence Characterization without Numeric Scoring (`evidence_characterizations`):** Structured appraisal tailored to question type (`intervention`, `etiology_harm`, `diagnosis`, `prognosis`, `meaning_experience`, `traditional_lore`) with qualitative domain judgments, risk of bias, directness, and explicit preservation of missing information (`not_reported` / `unclear`). Artificial aggregate scores (e.g. 8/10) are strictly banned.
  5. **Automated Retraction Cascading (`source_status_events`):** Recording a `retraction` or `withdrawn` event on a source edition automatically identifies all dependent claims and suspends active clinical intended-use approvals with an audit-recorded condition.
  6. **Prohibition of Claim Laundering:**
     - Traditional use claims cannot be reclassified or approved as modern interventional efficacy.
     - Preclinical in-vivo/in-vitro assays cannot be approved for clinician context as proven human clinical outcomes.
     - Observational cohort studies cannot be approved as causal claims.
  7. **Fail-Closed Clinical Publication Gate (`get_clinician_context_claim`):** Requests for claims in clinician workspace surfaces evaluate intended-use approvals, retraction events, passage fidelity, and support state. Unsupported, unapproved, expired, or retracted claims immediately fail closed (`allow_clinical_action: false`, `status: FAIL_CLOSED`).
  8. **Standardized Clinical Statements:** Formatting adheres to strict epistemological templates communicating exact caveats (e.g., *"Documented in traditional Unani medical texts as [...]; formal modern clinical efficacy has not been established"*).
  9. **Evidence Conflicts & Adjudication Queue (`evidence_conflicts`):** Contradictory evidence between sources is logged in a first-class conflict queue and flagged prominently in clinical context panels until formal human scholar adjudication.

- **Consequences:**
  - Complete elimination of citation decoration and unsupported claim publishing.
  - Transparent epistemological honesty respecting the distinct identities of classical Unani literature and contemporary clinical research.
  - Fail-closed patient safety perimeter blocking retracted, superseded, or unverified claims.
  - Full adherence to Prompt 21 and the KAVS Blueprint.

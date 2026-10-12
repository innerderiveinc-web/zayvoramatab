# ADR-018: Governed Clinical Knowledge Sources, Atomic Claims, and Traceable Citations

- **Status:** Accepted
- **Date:** 2026-10-13
- **Context:**
  Clinical decision-support systems frequently suffer from hallucinated citations, ungrounded efficacy claims, and opaque evidence provenance. In traditional Unani medicine and integrative clinical environments, treating historical compendia assertions as equivalent to modern double-blind randomized clinical trials (or conversely, dismissing centuries of empirical traditional use) leads to clinical confusion and regulatory exposure. Furthermore, allowing unapproved or draft monographs to silently influence clinical charting endangers patients.
- **Decision:**
  1. **Governed Sources Registry:** All clinical references are stored in a governed registry (`knowledge_sources`) capturing source type, publisher, publication date, regulatory status, evidence grade, and SHA-256 document integrity hash.
  2. **Atomic Claims and Evidence Records:** Knowledge is partitioned into granular atomic claims (`knowledge_claims`) and structured study appraisals (`knowledge_evidence`) with risk-of-bias assessment and explicit sample size/limitations tracking.
  3. **Strict Epistemological Boundaries in Evidence Synthesis:** Traditional monograph indications are documented as classical compendium specifications and are strictly never presented as equivalent to contemporary double-blind RCTs.
  4. **Traceable Non-Fabricated Citations:** Every surfaced clinical fact must resolve to an underlying citation record linking a claim to a verified source location.
  5. **Reviewer-Gated Approval:** Only records in status `approved` by licensed clinical reviewers are returned in production clinical retrieval.
- **Consequences:**
  - Guarantees complete audit traceability and legal defensibility for all clinical decision-support recommendations.
  - Eliminates citation fabrication and maintains clear boundaries between classical empirical tradition and modern biomedical research.

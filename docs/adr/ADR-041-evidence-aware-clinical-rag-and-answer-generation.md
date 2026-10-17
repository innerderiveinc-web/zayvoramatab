# ADR-041: Evidence-Aware Clinical Knowledge Retrieval (Hybrid RAG) & Answer Generation Engine (Prompt 22)

- **Status:** Accepted
- **Date:** October 2026
- **Context:**
  Prompt 22 mandates a permission-aware, source-grounded retrieval and answer generation layer for ZAYVORA MATAB OS. A common, catastrophic flaw in LLM-powered clinical assistants is "hallucinated authority"—synthesizing persuasive medical prose decorated with superficial or irrelevant citations, inventing nonexistent clinical trials, blurring traditional usage with modern evidence, or attempting autonomous diagnosis and prescription recommendations.
  A clinical RAG engine must enforce strict trust boundaries: search relevance is not evidence; citation existence is not claim support; and model memory is never trusted over authoritative records. The engine must make uncertainty explicit, refuse to fill evidence gaps, enforce intended-use approvals server-side, and ensure that patient context never leaks into global retrieval indexes.

- **Decision:**
  1. **Controlled Query-Intent Registry (`rag_query_intent_registry`):** Every user query is resolved against a governed intent registry. Requests attempting autonomous clinical actions (such as "diagnose this patient", "which Nuskha should I prescribe", or "calculate exact dose") are immediately intercepted and flagged as `restricted_clinical_action` with mandatory abstention and routing to clinician-controlled workspaces.
  2. **Canonical Concept & Ambiguity Resolver:** Query terms are resolved against Prompt 19 approved canonical concepts and multi-script aliases. When a query term maps to multiple distinct botanical, mineral, or anatomical identities (e.g. *Kundur* referring to *Boswellia carterii* vs. *Boswellia serrata*), the system detects ambiguity, abstains from forced equivalence, and returns an explicit clarification requirement.
  3. **Permission-Aware Hybrid Retrieval:** Integrates exact identifier search, multi-script lexical token search, and structured catalog/claim lookup. Pre-filters ensure that only sources with accessible rights and claims with active intended-use approvals for the requested surface are admitted to candidate sets.
  4. **Immutable Evidence Packs (`rag_evidence_packs`):** Before drafting an answer, the system compiles a minimal, immutable-per-run evidence pack containing approved passages, claims, support assessment outcomes, and exclusion audit logs. A deterministic SHA-256 reproducibility hash is computed and stored.
  5. **Structured Answer Generation Contract (`rag_answer_runs`, `rag_answer_claims`):** Rather than returning ungrounded free text, answers are generated as structured records composed of discrete atomic claim units. Each factual claim is formatted using Prompt 21 Section 9 epistemological templates (explicitly distinguishing traditional Unani documentation, preclinical assays, and modern clinical trials) with prominent caveats.
  6. **Per-Claim Citation Binding (`rag_answer_citations`):** Every factual claim unit is bound to one or more verified source passages with exact locators and edition versions. General, paragraph-level decorative citations are strictly banned.
  7. **Deterministic Multi-Stage Post-Generation Validation:** Answers undergo hard-gate validation: schema consistency, citation existence, access permissions, source version currency, Prompt 21 support assessment status, and clinical action boundaries. Any claim failing validation fails closed.
  8. **Honest Abstention:** Queries with insufficient evidence, inaccessible sources, or unresolved conflicts return truthful abstention (`insufficient_evidence`, `source_unavailable`) rather than fabricated filler text.
  9. **Patient Context Boundary:** When invoked within a consultation encounter, patient data (e.g., age, allergies) is accessed read-only to tailor safety context. Patient data is never stored in the global retrieval index, shared telemetry, or answer caches.
  10. **Retrieval Feedback & Governance Queue (`rag_retrieval_feedback`):** Clinicians and reviewers can flag retrieval discrepancies or missing qualifiers, creating formal governance review tasks rather than permitting automated, uncontrolled model self-updating.

- **Consequences:**
  - Absolute elimination of citation decoration and LLM medical hallucination.
  - Strict preservation of the distinct identities of classical Unani documentation and contemporary biomedical trials.
  - Fail-closed patient safety perimeter blocking autonomous prescribing or dosage calculations.
  - Complete reproducibility and auditable provenance for every generated clinical knowledge answer.

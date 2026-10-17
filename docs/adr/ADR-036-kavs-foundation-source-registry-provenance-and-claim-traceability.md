# ADR-036: KAVS Foundation — Source Registry, Provenance, Locators & Claim Traceability (Phase K0 + K1)

- **Status:** Accepted
- **Date:** October 2026
- **Context:**
  Prompt 17 defines the implementation requirements for Phase K0 and K1 of the Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS). The framework mandates strict proscription against inventing or hallucinating clinical knowledge, Unani concepts, dosages, or source page numbers. Clinical claims must possess complete provenance grounded in authentic primary sources, with fine-grained locators (page, chapter, section, anchor range), formal verification events, versioned governance policies, an atomic claim review workflow, and an append-only audit trail. Unreviewed drafts must be mathematically blocked from live clinician-facing retrieval.

- **Decision:**
  1. **Governed Source Registry & Versioning:** Implemented in `knowledge_sources` and `kavs_source_versions` with SHA-256 document hashing, statutory licensing statuses (`STATUTORY_AYUSH_OPEN`, `PUBLIC_DOMAIN`, `LICENSED_INTERNAL`, `METADATA_AND_EXCERPT_ONLY`), and authorized operational scopes.
  2. **Exact Source Locators (`kavs_source_locators`):** Fine-grained locators linking versions to exact page numbers, page labels, chapters, sections, subsections, paragraphs/tables, article DOIs, anchor ranges, and discrete verification states (`UNVERIFIED`, `VERIFIED_PHYSICAL_PASSAGE`, `VERIFIED_DIGITAL_ANCHOR`, `DISPUTED`).
  3. **Discrete Source Verification Events (`kavs_source_verification_events`):** Audited verification checks (`METADATA_VERIFICATION`, `PUBLISHER_AUTHORITY`, `DOCUMENT_INTEGRITY_HASH`, `EDITION_REVISION`, `RIGHTS_USAGE`, `PASSAGE_FIDELITY`) with role-based signing by authenticated Unani scholars and governance leads.
  4. **Knowledge Governance Policy Registry (`kavs_governance_policies`):** Versioned, document-hashed governance policies (`KAVS-POL-001`, `1.0.0`) dictating evidence thresholds and dual-expert sign-off requirements.
  5. **Atomic Claim Review Workflow:** Claims start strictly in `DRAFT`. State transitions (`UNDER_REVIEW` -> `APPROVED` / `REJECTED` / `WITHDRAWN`) enforce 5-dimension verification records (`kavs_claim_verifications`) before approval. Rejection and withdrawal require mandatory justifications.
  6. **Retrieval Safety Invariant:** Live consultation retrieval (`/api/v1/kavs/retrieve`) strictly excludes unreviewed/draft claims, returning `insufficient_information: true` when no verified claims exist within authorized scope.
  7. **Tamper-Evident Append-Only Audit Ledger (`kavs_audit_events`):** Permanently logs all KAVS state changes (`SOURCE_REGISTERED`, `SOURCE_VERSIONED`, `RIGHTS_REVIEWED`, `LOCATOR_CREATED`, `LOCATOR_VERIFIED`, `VERIFICATION_RECORDED`, `POLICY_REGISTERED`, `CLAIM_CREATED`, `CLAIM_APPROVED`, `CLAIM_REJECTED`, `CLAIM_WITHDRAWN`).
  8. **Zero Legacy Dependencies:** All capabilities operate exclusively inside the new standalone repository.

- **Consequences:**
  - Absolute legal and clinical defensibility of all recommendations surfaced to AYUSH practitioners.
  - Zero possibility of AI hallucination entering the consultation decision loop.
  - Full conformance with Prompt 17 Phase K0 + K1 specifications.

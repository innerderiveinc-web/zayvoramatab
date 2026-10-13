# ADR-035: Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS)

## Status
**ACCEPTED** (Implementation verified against Migration 015 & automated test suite)

## Context
In healthcare operating systems—specifically autonomous AYUSH and Unani clinical systems—relying on probabilistic Large Language Models (LLMs) or ungrounded generative AI to synthesize clinical knowledge, drug compositions, dosages, herb-drug interactions, or diagnostic contraindications introduces unacceptable risks of clinical hallucination and medical malpractice.

Furthermore, traditional medicine frameworks (such as Unani Tibb) often have classical terminology and historical indications that cannot be arbitrarily translated into modern biomedical terms without qualified clinical review. Similarly, classical compendia cannot be treated as modern empirical proof of efficacy without separate evidence characterization.

## Decision
We have designed and implemented the **Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS)** as an independent, deterministic evidence layer inside ZAYVORA MATAB OS:

1. **Strict Proscription of Autonomous AI Publishing:**
   AI models may only assist with text extraction, transcription, and candidate entity recognition. All extracted elements are marked as unverified drafts and must pass human expert review before publication.

2. **Five Independent Verification Dimensions:**
   Trust is decomposed into 5 orthogonal dimensions stored explicitly per claim:
   - **Source Authenticity:** `unverified`, `metadata_verified`, `document_integrity_verified`, `publisher_or_authority_verified`, `disputed`.
   - **Extraction Fidelity:** `not_checked`, `machine_extracted`, `human_checked`, `correction_required`, `unreadable`.
   - **Evidence Characterization:** Typed classification separating classical compendia from randomized trials, guidelines, or preclinical studies.
   - **Clinical Review State:** `not_reviewed`, `review_in_progress`, `changes_requested`, `approved_for_defined_use`, `rejected`, `review_expired`.
   - **Intended-Use Authorization:** Role- and population-scoped authorization (`historical_reference_only`, `educational_reference`, `clinician_contextual_reference`, `formulary_definition`, `safety_alert_rule`, `not_authorized_for_clinical_use`).

3. **Source Versioning & Rights Verification:**
   Statutory compendia (NFUM, UPI, CCRUM Treatment Guidelines) are versioned with publisher integrity hashes and explicit copyright/licensing records (`kavs_source_rights_reviews`).

4. **Page-Anchored Extraction Segments:**
   Extracts retain exact physical page and table anchors with OCR confidence scores; formula weights and dosages must be checked by humans.

5. **Evidence Contradiction Graphs:**
   Contradicting trials and documented clinical limitations are explicitly linked to claims rather than omitted.

6. **Immutable Knowledge Releases:**
   Consultation-time retrieval operates against cryptographically fingerprinted releases (`manifest_hash`), ensuring clinical decisions are made against immutable evidence versions.

7. **Change-Impact Dependency Tracing:**
   When a source or claim is amended, downstream clinical rules and formulations are traced and flagged for remediation.

8. **Grounded Retrieval with Honest Caveats:**
   Queries without verified backing return `insufficient_information: true` and an explicit disclaimer, preventing false clinical certainty.

## Consequences
- **Positive:** Zero AI hallucinations in clinical decision-making; complete auditability of clinical claims; statutory compliance with AYUSH pharmacopoeial guidelines; explicit evidence boundaries.
- **Negative:** Content ingestion requires formal human expert workflows; cannot ingest unstructured third-party data without verified rights reviews.

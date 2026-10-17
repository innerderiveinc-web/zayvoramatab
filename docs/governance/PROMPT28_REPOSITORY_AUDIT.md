# ZAYVORA MATAB OS — Prompt 28 Repository Pre-Implementation Audit
## Clinical Knowledge Governance, Rule Versioning & Controlled Safety-Rule Release Engine

**Document Type:** Pre-Implementation Architectural & Codebase Audit  
**Product:** ZAYVORA MATAB OS — Standalone Clinic/Hospital Operating System  
**Phase:** 28 — Governance Lifecycle for Clinical Knowledge, Safety Rules, Evidence Updates, Approvals, Release, Monitoring, and Rollback  
**Date:** October 2026  
**Status:** Pre-Flight Verified  

---

## 1. Executive Summary & Purpose

Prompt 28 establishes the unified **Clinical Knowledge Governance, Rule Versioning & Controlled Safety-Rule Release Engine** for ZAYVORA MATAB OS. In clinical software for both traditional Unani Tibb and contemporary medicine, updating a safety rule, drug interaction threshold, differential diagnosis trigger, or outcome instrument cannot be treated as a casual code commit or unverified data insert.

### Non-Negotiable Tenets
1. **Never fabricate clinical knowledge or governance evidence:** Every rule rationale, clinical assertion, reviewer credential, test result, and approval record must be genuine.
2. **No direct-to-production clinical changes:** All clinical artifacts must proceed through a formal state machine (`draft` -> `submitted_for_review` -> `review_approved` -> `technical_validation_passed` -> `release_approved` -> `deployed_verification_pending` -> `active`).
3. **No automatic approval by AI:** AI may draft change proposals or diff summaries, but cannot approve, sign, activate, or roll back clinical rules.
4. **Separation of clinical validity from technical validity:** Passing unit tests or valid JSON schemas does not prove medical accuracy; explicit clinical domain review is required.
5. **Exact version resolution & non-rewriting of history:** Historical patient encounters and signed prescriptions must permanently record the exact rule/knowledge release used and never be retroactively rewritten.
6. **Tested rollback & emergency kill-switch:** Rollback and suspension must be real, tested, and verifiable.

---

## 2. Codebase Audit of Existing Foundations (Prompts 01–27)

| Phase / Component | Existing Capability | Governance Integration Status |
|---|---|---|
| **Prompts 17–19 (KAVS & Catalog)** | Sources, citations, and canonical Unani concepts stored in DB with provenance hashes | Needs lifecycle integration: source updates must trigger versioned governance |
| **Prompt 20 (Knowledge Mapping)** | Organ-axis framework and clinical concept relationships | Requires rule-dependency mapping before relationship modifications |
| **Prompt 21 (Evidence Verification)** | Claim-to-source support assessments and verification states | Claim approvals must gate dependent clinical rule activation |
| **Prompt 22 (Clinical RAG)** | Retrieval-answer generation policies and permission sets | Policy updates must be versioned and approval-bound |
| **Prompt 23 (CDS Orchestrator)** | Rule-triggered advisory cards and clinician override workflows | Rules must be managed as governed declarative artifacts rather than static code |
| **Prompt 24 (Data Quality)** | Deterministic completeness rules and freshness policies | Rule registry must be governed by change release lifecycle |
| **Prompt 26 (Outcomes Engine)** | Measurement instruments, scoring methods, and protocols | Instruments must have governed lifecycle states (`DRAFT`, `APPROVED`, `SUSPENDED`) |
| **Prompt 27 (Pharmacovigilance)** | Safety surveillance cases, causality reviews, and disabled regulatory profiles | Regulatory profiles and signal criteria must be governed artifacts |

---

## 3. Architecture for Phase 28

1. **Governed Artifacts Master Table (`governed_artifacts`):**
   - Universal envelope for 23 controlled artifact types (`clinical_rule`, `safety_rule`, `source_record`, `canonical_concept`, `outcome_instrument`, etc.).
   - Stores `stable_key`, `owning_domain`, `criticality_class`, and `current_lifecycle_state`.
2. **Immutable Artifact Versions (`governed_artifact_versions`):**
   - Immutable version records with `payload_manifest_hash` (SHA-256), derivation diff, supporting evidence links, and applicable scopes.
3. **Lifecycle State Machine & Transitions (`governed_artifact_transitions`):**
   - Enforces sequential progression: `draft` -> `submitted_for_review` -> `review_approved` -> `technical_validation_passed` -> `release_candidate` -> `release_approved` -> `deployed` -> `active`.
   - Rejection, suspension, and withdrawal states with mandatory human rationale.
4. **Declarative Clinical & Safety Rule Specifications (`clinical_rule_definitions`):**
   - Typed condition grammar (no arbitrary executable code / eval).
   - Explicit evaluation states: `triggered`, `not_triggered_within_scope`, `incomplete_input`, `rule_unavailable`, `evaluation_error`.
   - Sandboxed test execution harness with mandatory trigger/non-trigger fixtures (`rule_test_executions`).
5. **Dependency & Impact Analysis Engine (`governance_impact_analyses`):**
   - Traces dependent claims, rules, CDS cards, and active encounters prior to release.
6. **Immutable Release Manifests & Controlled Deployment (`governance_releases`):**
   - Multi-party approval bound to cryptographic manifest hash.
   - Runtime active version verification, canary/shadow staging, and tested one-click rollback.
7. **Runtime Version Resolution Ledger (`governance_runtime_resolutions`):**
   - Pins exact release and rule versions used during clinical encounters for non-repudiable auditability.

---

## 4. Audit Sign-off

The repository audit verifies that all required persistence, domain engine, and API foundations are ready for Migration 027 and `ClinicalKnowledgeGovernanceEngine`.

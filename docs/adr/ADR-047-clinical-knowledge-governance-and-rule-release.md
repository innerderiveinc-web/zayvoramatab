# ADR-047: Clinical Knowledge Governance, Rule Versioning & Controlled Safety-Rule Release Engine (Prompt 28)

## Status
Accepted

## Context
In clinical environments, software safety checks, contraindicated drug combinations, herbal processing (Mudabbar) requirements, outcome instruments, and diagnostic heuristics directly impact patient care. Historically, updates to rules in healthcare software have occurred as untracked code commits or unreviewed database inserts, risking catastrophic patient safety events, lack of reproducibility, and absence of rollback mechanisms.

Prompt 28 establishes a strict governance lifecycle where no AI-generated, developer-authored, or imported clinical content may silently become active in clinical workflows without passing multi-gate review, sandboxed testing, cryptographic manifest binding, runtime verification, and rollback capability.

## Decision
1. **Migration 027 Persistence:**
   - `governed_artifacts`: Universal envelope tracking 23 artifact types across 6 criticality classes (`EDITORIAL`, `TERMINOLOGY_IDENTITY`, `EVIDENCE_CLAIM`, `CLINICAL_BEHAVIOR`, `REGULATORY_SAFETY`, `EMERGENCY_PATCH`) and 17 lifecycle states.
   - `governed_artifact_versions`: Immutable version records with canonical SHA-256 payload manifest hashes, diff summaries, and supporting evidence references.
   - `governed_artifact_transitions`: Append-only transition audit ledger enforcing role-separated state progression.
   - `governed_clinical_rules`: Typed declarative rules with sandboxed condition expressions, explicit output states (`triggered`, `not_triggered_within_scope`, `incomplete_input`, etc.), and test fixtures.
   - `rule_test_executions`: Verification test results logging latency and pass/fail states.
   - `governance_releases`: Immutable release packages with manifest hashing, multi-party approvals, canary/shadow staging modes, and runtime verification gates.
   - `governance_impact_analyses`: Dependency graphs identifying affected rules, APIs, and active encounters.
   - `governance_runtime_resolutions`: Encounter-level pinning of active release and rule versions for historical reproducibility.
2. **Domain Engine (`ClinicalKnowledgeGovernanceEngine`):**
   - Disallows self-approval by authors for high-risk clinical artifacts.
   - Rejects arbitrary code execution strings (`eval`) in favor of typed declarative ASTs.
   - Enforces fail-closed semantics: manifest hash mismatch aborts deployment and sets state to `HASH_MISMATCH`.
   - Supports verified one-click rollback and emergency suspension kill-switches.
3. **REST APIs:**
   - 15 endpoints mounted under `/api/v1/governance/*` with strict permission checks.

## Consequences
- **Positive:**
  - Complete elimination of unreviewed direct-to-production clinical changes.
  - Provable tamper-evident release integrity via SHA-256 manifest hashing.
  - Historical encounters permanently retain exact rule versions used during consultations.
- **Negative / Trade-offs:**
  - Additional operational overhead requiring formal multi-gate review before rules become active.

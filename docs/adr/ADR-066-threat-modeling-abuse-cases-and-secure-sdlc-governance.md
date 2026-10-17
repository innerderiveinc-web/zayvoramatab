# ADR-066: Threat Modeling, Abuse-Case Analysis & Secure Development Lifecycle (SDLC) Governance Engine

- **Status:** Accepted  
- **Date:** 2026-10-14  
- **Context:** Prompt 47 mandates a Threat Modeling, Abuse-Case Analysis & Secure SDLC Governance Engine for ZAYVORA MATAB OS to identify security, privacy, and clinical-workflow threats during architecture and design, convert material risks into testable controls, and govern them through coding, release, and post-deployment review. Core non-negotiables demand: (1) Threat models must follow actual architecture and real database tables; (2) Threats altering, suppressing, or misrouting clinical information require explicit clinical-hazard review; (3) Hard clinical non-negotiables: no threat-modeling tool or residual risk acceptance may bypass patient consent, clinician electronic PIN signatures, drug safety firewalls, or tenant isolation; (4) Governed residual risk acceptances must mandate $\le 90$-day expirations, business justifications, compensating controls, and designated risk owners; (5) Fail-closed SDLC release gates: missing threat models, stale architectures, unmitigated critical/high threats, or uncompleted clinical/privacy reviews must evaluate to `BLOCKED` or `STALE_MODEL`, never an optimistic `PASS`; (6) Zero raw secrets and zero PHI in threat artifacts, diagrams, or logs; and (7) Continuous SHA-256 hash chaining for all threat modeling and SDLC audit records.

## Decision

1. **Database Schema (Migration 046):**
   - `threat_models_registry`: Canonical subsystem threat model registry tracking model code, title, subsystem scope, repository revision, deployment version, owner role, review dates, stale detection flags (`is_stale`), and lifecycle states (`draft`, `discovery`, `review_required`, `mitigation_in_progress`, `residual_risk_review`, `approved_for_scope`, `stale`, `retired`).
   - `threat_trust_boundaries`: Trust boundaries inventory tracking source, destination, protocol, auth mechanism, encryption status, data classifications (`TIER_1_CREDENTIALS` through `TIER_5_OPERATIONAL`), and verifiable evidence status (`verified_in_code`, `verified_in_config`, `verified_in_test`, `runtime_verified`, `inferred`, `unknown`).
   - `threat_abuse_cases`: Abuse case catalogue categorized using STRIDE-Plus-Clinical-Hazard (`SPOOFING`, `TAMPERING`, `REPUDIATION`, `INFO_DISCLOSURE`, `DENIAL_OF_SERVICE`, `ELEVATION_OF_PRIVILEGE`, `CLINICAL_HAZARD`, `SUPPLY_CHAIN`), severity, clinical safety hazard classifications (`DIRECT_HARM_PRESCRIBING_ERROR`, `DIAGNOSTIC_TAMPERING_MISROUTING`, etc.), and lifecycle statuses (`identified` through `closed_with_evidence`).
   - `threat_testable_controls`: Traceable control mappings linking abuse cases to concrete `enforcement_code_path`, `test_suite_reference`, and verification status (`VERIFIED_IN_TEST`).
   - `threat_residual_risk_decisions`: Governed risk acceptance ledger enforcing maximum 90-day expiry, designated risk owner approval, and hard clinical non-negotiables (strictly forbidding risk acceptance for prescribing harm).
   - `sdlc_change_reviews`: Change review and pre-deployment release gate evaluation ledger recording repository revision, target subsystem, classification (`HIGH_IMPACT_CLINICAL`, `HIGH_IMPACT_PRIVACY`, etc.), security/clinical/privacy review statuses, and gate verdicts (`PASS`, `BLOCKED`, `CONDITIONAL_PASS`, `STALE_MODEL`).
   - `threat_sdlc_audit_ledger`: Append-only, SHA-256 hash-chained threat modeling and SDLC audit trail.

2. **Domain Architecture (`EnterpriseThreatModelingSDLCService`):**
   - **STRIDE-Plus-Clinical-Hazard Analysis:** Classifies threat scenarios across technical and clinical dimensions, maintaining explicit traceability to active code and automated tests.
   - **Automated Stale-Model Detector:** Evaluates review cadence due dates and repository revision changes, transitioning expired models to `stale` (`is_stale = 1`).
   - **Governed Residual Risk Acceptance Engine:** Rejects any risk acceptance attempt on direct prescribing hazards or tenant isolation; validates 90-day maximum lifetime.
   - **Deterministic SDLC Release Gate Evaluator:** Enforces that target subsystems possess an active, non-stale `approved_for_scope` threat model, checks that all P0/P1 abuse cases are verified mitigated or covered by an unexpired residual risk decision, and ensures mandatory security, clinical, and privacy review approvals are present before issuing a `PASS` verdict.

3. **REST API Interface & Web UI:**
   - 22 REST API endpoints mounted under `/api/v1/threat-modeling/` in `apps/api/router.py`.
   - Dedicated workbench in `apps/web/static/js/views/knowledge_admin.js` under the `Threat Modeling & SDLC (P47)` tab, featuring executive KPI badges, invariant banners, stale model evaluation triggers, threat model registry, abuse cases explorer, testable controls map, SDLC change reviews manager, and tamper-evident audit ledger.

## Consequences

- **Positives:** Establishes formal, testable threat modeling directly integrated into the software development lifecycle and CI/CD release gates.
- **Clinical Safety Assurance:** High-impact clinical changes are strictly prevented from deploying without explicit Clinical Safety Officer approval.
- **Fail-Closed Engineering:** Untested, stale, or unmodeled subsystems evaluate to `BLOCKED` or `STALE_MODEL`, eliminating paper approvals or unverified release claims.

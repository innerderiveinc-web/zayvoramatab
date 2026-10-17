# ZAYVORA MATAB OS — PROMPT 47 REPOSITORY AUDIT
## Threat Modeling, Abuse-Case Analysis & Secure Development Lifecycle (SDLC) Governance Engine

**Date:** 2026-10-14  
**Auditor:** Principal Security Architect, Application Security Engineer, Secure SDLC Lead, Privacy Engineer, Platform Engineer & Clinical Software Risk Analyst  
**Subsystems Inspected:** Patient Identity, Clinical Encounters, Prescription & Nuskha Signing, CDS & Safety Firewalls, Unani KAVS & RAG Assistant, ABDM/FHIR Interoperability, Identity & PAM, Configuration & Secrets, Data Lifecycle, Security Posture.

---

## 1. Executive Summary & Audit Context

Threat modeling in a clinical operating system cannot be an abstract diagramming exercise or a static compliance badge. In ZAYVORA MATAB OS:
1. **Threats must follow actual architecture:** Models must reflect real database tables, domain service code paths, and REST API routes rather than imagined microservices.
2. **Clinical hazard governance is non-negotiable:** Security threats that alter, suppress, misroute, or falsely present clinical information directly affect patient life and clinical safety. Technical security reviews cannot substitute for qualified clinical safety reviews.
3. **Defense in depth & least privilege:** Client-side flags, UI omissions, or unverified headers are never accepted as authorization. Server-side enforcement with strict tenancy and role resolution is mandatory.
4. **Zero secrets and zero PHI in threat artifacts:** Threat models, attack paths, abuse cases, and audit logs must never expose patient identities, clinical narratives, or credential secrets.
5. **Fail-closed SDLC release gates:** Missing threat models, stale architectures, unmitigated critical/high threats, or uncompleted clinical/privacy reviews must halt release deployment (`BLOCKED` or `STALE_MODEL`, never an optimistic `PASS`).

---

## 2. Actual Subsystems, Trust Boundaries & Asset Inventory

### 2.1 Subsystem Inventory
| Subsystem Scope | Primary Domain Module | Core Relational Tables | Clinical / Data Classification | Status |
| :--- | :--- | :--- | :--- | :--- |
| **`CLINICAL_CDS_AND_PRESCRIPTIONS`** | `cds_orchestrator.py`, `safety_firewall.py` | `prescriptions`, `prescription_items`, `cds_runs`, `cds_cards`, `clinical_signoffs` | TIER_1 (PIN hashes), TIER_2 (Prescription & Safety PHI) | `IMPLEMENTED` |
| **`PATIENT_IDENTITY_AND_REGISTRY`** | `data_governance.py`, `patient.py` | `patients`, `patient_identifiers`, `mdm_duplicate_candidate_reviews`, `patient_merges` | TIER_2 (Demographic & Clinical PHI) | `IMPLEMENTED` |
| **`UNANI_KAVS_AND_RAG`** | `clinical_rag.py`, `kavs.py`, `ontology.py` | `kavs_sources`, `knowledge_concepts`, `rag_evidence_packs`, `rag_answer_runs` | TIER_3 (Governed Clinical Knowledge & Formulations) | `IMPLEMENTED` |
| **`INTEROPERABILITY_ABDM_FHIR`** | `interoperability.py` | `abdm_consent_requests`, `abdm_consent_artefacts`, `inbound_record_reconciliations` | TIER_2 (Health Information Exchange PHI) | `IMPLEMENTED` |
| **`IDENTITY_AND_PAM`** | `identity_governance.py`, `security_governance.py` | `identity_principals`, `identity_jit_elevations`, `identity_break_glass_sessions` | TIER_1 (Session tokens, password hashes, PAM grants) | `IMPLEMENTED` |
| **`CONFIG_AND_SECRETS`** | `config_governance.py` | `config_settings_catalog`, `config_secret_references`, `config_secret_rotations` | TIER_1 (Secret Manager References, Key Metadata) | `IMPLEMENTED` |
| **`DATA_LIFECYCLE_AND_RETENTION`** | `data_lifecycle.py` | `data_lifecycle_policies`, `data_lifecycle_legal_holds`, `data_lifecycle_operations` | TIER_2 (Clinical Retentions, Archival Snapshots) | `IMPLEMENTED` |
| **`SECURITY_POSTURE_AND_VULNS`** | `security_posture.py` | `security_assets_inventory`, `security_controls_registry`, `security_vulnerability_findings` | TIER_4 (Compliance, CVEs, Verification Logs) | `IMPLEMENTED` |

### 2.2 Real Trust Boundaries
1. **TB-01: Public / Browser Client $\leftrightarrow$ API Gateway & Middleware**
   - Protocol: HTTPS / TLS 1.3, JSON REST API.
   - Auth: Session tokens, HTTP Authorization header, IP rate limiting.
   - Boundary: Untrusted client browser to trusted web backend.
2. **TB-02: API Handler $\leftrightarrow$ Domain Service & Authorization Middleware**
   - Auth: Server-enforced RBAC (`require_permission`), multi-tenant facility resolution.
   - Boundary: Request parsing to business logic execution.
3. **TB-03: Domain Service $\leftrightarrow$ SQLite Relational Database Engine**
   - Protocol: Parameterized SQL bindings (`?`).
   - Boundary: Domain logic to persistent transactional storage.
4. **TB-04: AI / CDS Orchestrator $\leftrightarrow$ Clinician Attestation & Signing**
   - Non-Negotiable: Zero autonomous AI signing. PIN verification required for finalization.
   - Boundary: Algorithmic decision support recommendations to human clinician authority.
5. **TB-05: Internal System $\leftrightarrow$ ABDM National Health Gateway / External Connectors**
   - Protocol: Mutual TLS / JWT / Webhooks with HMAC verification.
   - Boundary: Regulated internal hospital enclave to external national digital health infrastructure.
6. **TB-06: Routine Staff Roles $\leftrightarrow$ Privileged Administration / PAM JIT**
   - Auth: Dual-custody approval, 15–240 minute TTL, clinical firewall prohibiting prescribing acts.
   - Boundary: Front-desk / staff identity to elevated systems operator.

---

## 3. Existing Security Policies, SDLC Controls & Gap Analysis

### 3.1 Existing Foundations:
- `docs/security/threat-model.md`: Foundation STRIDE analysis covering credential brute force, tenant injection, unlogged actions, and optimistic concurrency.
- `docs/security/THREAT_MODEL_P30.md`: Threat actors, credential tiers, incident response playbooks, and break-glass containment.
- `apps/api/domains/security_posture.py` (Prompt 46): Continuous SCA, secret leak detection, API headers, Dockerfile checks, and fail-closed release gates.
- `apps/api/domains/identity_governance.py` (Prompt 45): PAM JIT elevation, break-glass containment, SoD toxic rules, two-phase remediation.

### 3.2 Gaps Identified (To be Resolved in Prompt 47):
1. **No Versioned Threat-Model Registry:** Threat models are stored as static Markdown documents without versioned lifecycle tracking (`draft`, `discovery`, `review_required`, `mitigation_in_progress`, `residual_risk_review`, `approved_for_scope`, `stale`, `retired`).
2. **Absence of Subsystem-Level Threat-to-Control Traceability:** Threat models do not map abuse cases directly to database foreign keys, enforcement code paths (`apps.api.domains.*`), and automated verification tests.
3. **Missing Tripartite Review Governance:** No formalized structure separates Technical Security approval, Clinical Safety review, and Privacy review on high-impact architectural changes.
4. **Lack of Automated Stale-Model Detection:** When underlying architecture, data flows, routes, or dependencies change, threat models do not automatically flag as `is_stale = 1`.
5. **No SDLC Change Intake & Gate Evaluation Engine:** Release pipelines lack a pre-deployment gate that validates whether a change request has an active, non-stale threat model and that all P0/P1 abuse cases are either verified mitigated in automated tests or covered by an unexpired residual risk acceptance.

---

## 4. Implementation Blueprint (Prompt 47)

1. **Migration 046:**
   - `threat_models_registry`
   - `threat_trust_boundaries`
   - `threat_abuse_cases`
   - `threat_testable_controls`
   - `threat_residual_risk_decisions`
   - `sdlc_change_reviews`
   - `threat_sdlc_audit_ledger`
2. **Domain Engine (`EnterpriseThreatModelingSDLCService`):**
   - Subsystem threat model lifecycle state machine.
   - Abuse-case registry with STRIDE + Clinical Safety Hazard classification.
   - Traceable controls linking threats to code paths and automated test suites.
   - Governed residual risk decisions with mandatory 90-day expiry and clinical safety non-negotiables.
   - Stale model detection comparing reviewed repository revisions and timestamps.
   - Deterministic SDLC change review gate evaluation.
   - Chained SHA-256 tamper-evident audit ledger.
3. **REST API Routes (22 Endpoints):**
   - Mount `/api/v1/threat-modeling/` under `apps/api/router.py`.
4. **Web UI Workbench:**
   - Dedicated `Threat Modeling & SDLC (P47)` console in `apps/web/static/js/views/knowledge_admin.js`.
5. **Verification Suite:**
   - Comprehensive unit and integration test suites covering abuse cases, clinical firewalls, gate evaluations, and audit chaining.

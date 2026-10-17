# ZAYVORA MATAB OS — Architectural Duplication & Consolidation Analysis

**Audit Version:** 1.0.0 (Prompt 50 Repository-Wide Baseline)  
**Objective:** Identify overlapping domain models, duplicate subsystems, competing state machines, and consolidation opportunities across Prompts 1–49 to ensure architectural elegance and maintainability for V1.

---

## 1. Audit Ledger Subsystems & Hash-Chaining Consolidation

### 1.1. Current State
Across the 48 database migrations, five separate audit ledger tables were introduced to satisfy specific compliance and governance requirements:
1. `clinical_audit_ledger` (Prompt 31, Migration 028) — General clinical actions, encounter updates, prescription events.
2. `security_audit_ledger` (Prompt 46, Migration 045) — Security scanner executions, vulnerability status changes, gate evaluations.
3. `threat_sdlc_audit_ledger` (Prompt 47, Migration 046) — Threat model updates, abuse case mitigations, SDLC change reviews.
4. `clinical_safety_audit_ledger` (Prompt 48, Migration 047) — Hazard state transitions, GSN safety case modifications, clinical sign-offs.
5. `test_qualification_audit_ledger` (Prompt 49, Migration 048) — Test execution runs, quarantine classifications, release candidate verdicts.

### 1.2. Architectural Evaluation
- **Commonality:** All five tables share an identical schema structure: `record_id`, `tenant_id`, `event_type`, `actor_id`, `actor_role`, `payload_json`, `timestamp`, `previous_hash`, `record_hash`.
- **Cryptographic Hash Chaining:** All five engines use exact identical SHA-256 canonical JSON digest computation (`compute_chain_hash()`).
- **Isolation Rationale:** Partitioning audit records into domain-specific ledgers prevents lock contention during high-frequency clinical writes and simplifies regulatory scoping (e.g., providing AYUSH auditors with `clinical_audit_ledger` without exposing internal SDLC threat logs).
- **V1 Consolidation Verdict:**
  - **Maintain table partitioning at the storage layer:** Prevents cross-domain schema coupling and ensures independent audit trail verification.
  - **Unify core hashing utilities:** Ensure all domain services import from a single shared cryptographic helper (`apps/api/core/audit_chain.py`) rather than maintaining independent hash calculation snippets.

---

## 2. Configuration & Secrets Management

### 2.1. Current State
- `apps/api/core/config.py`: Environment variable loading using standard Python `os.getenv()` with default fallbacks.
- `043_enterprise_config_secrets_environment_governance_schema.sql` (Prompt 43): Dynamic database-backed configuration registry and secrets metadata tracking (`config_keys`, `secret_metadata`).

### 2.2. Architectural Evaluation
- **Conflict Risk:** Having both static `.env` settings and dynamic database-backed settings can cause ambiguity regarding the authoritative source of truth.
- **Resolution Strategy:**
  - **Bootstrapping Parameters:** Core infrastructure parameters (`DATABASE_URL`, `JWT_SECRET`, `PORT`, `ENVIRONMENT`) remain strictly environment-variable driven via `apps/api/core/config.py`.
  - **Operational & Feature Flags:** Dynamic runtime parameters (consultation stepper timers, rate limit thresholds, canary percentages, feature flags) are read from the database-backed configuration service with in-memory caching.
  - Zero plain-text secret storage in the database: only secret metadata, rotation timestamps, and cryptographic fingerprints are persisted.

---

## 3. RBAC, ABAC & Permissions Governance

### 3.1. Current State
- `apps/api/core/permissions.py`: Central repository defining all 50+ permission constants (e.g., `PATIENT_READ`, `PRESCRIPTION_SIGN`, `SAFETY_FIREWALL_OVERRIDE`, `AUDIT_LEDGER_VIEW`).
- Role mappings: `doctor`, `pharmacist`, `cashier`, `nurse`, `compliance_officer`, `admin`.
- Alias resolution: Domain engines from Prompts 46–49 utilize permission aliases that map cleanly to existing canonical roles without permission fragmentation.

### 3.2. V1 Consolidation Verdict
- **No Conflict:** Centralized permission mapping in `apps/api/core/permissions.py` is healthy, coherent, and verified by passing authorization tests.

---

## 4. Unani Clinical Knowledge Representations

### 4.1. Current State
Four separate knowledge schemas exist across the repository:
1. `unani_monographs` (`006_clinical_knowledge_schema.sql`) — Single and compound formulation definitions.
2. `unani_ontology_nodes` (`018_unani_ontology_catalog_schema.sql`) — Hierarchical taxonomy of classical Unani terms (Amraz, Alamat, Asbab, Mahiyyat).
3. `organ_axes` (`019_unani_clinical_knowledge_mapping_organ_axis_schema.sql`) — Systems-biology organ networks (Dimagh, Qalb, Jigar, Kulliya).
4. `rag_documents` (`021_clinical_rag_hybrid_retrieval_answer_generation_schema.sql`) — Indexed text chunks with citation locators.

### 4.2. Architectural Evaluation
- **Complementary Roles:** Rather than competing, these representations serve distinct functional requirements:
  - `unani_monographs`: Authoritative posology, temperaments, and substitutes used by the prescribing safety firewall.
  - `unani_ontology_nodes`: Standardized controlled terminology used for structured clinical documentation and ICD crosswalks.
  - `organ_axes`: Diagnostic reasoning network used for holistic mizaj dyscrasia evaluation.
  - `rag_documents`: Evidence retrieval repository for clinical question-answering with exact source locators.
- **V1 Consolidation Verdict:** Maintain the relational foreign key links between `unani_monographs` and `unani_ontology_nodes` (via `ontology_node_id`) to ensure seamless data integrity across all four models.

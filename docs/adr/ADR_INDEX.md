# Architecture Decision Records (ADRs) — ZAYVORA MATAB OS

---

## ADR-001: Standalone Architecture and Zero Runtime Dependency on Legacy Health OS

- **Status:** Accepted
- **Context:** The predecessor ZAYVORA Health OS was an expansive multi-package monorepo containing numerous experimental graph engines, simulated client fallbacks, and shared microservices. For practicing Hakeems and clinical deployments, this introduced significant instability, complex deployment requirements, and cascading failure modes.
- **Decision:** Build ZAYVORA MATAB OS as a completely independent, standalone product. It must maintain its own source repository, database schema, domain engines, REST APIs, authentication, and deployment lifecycle. It will not communicate with legacy private endpoints or import code from `zayvora-health-os-production-latest.zip`. Any future integration with external hospital systems or ZAYVORA networks must be an optional, versioned, disabled-by-default adapter.
- **Consequences:** Eliminates external runtime failures, allows local clinic server deployment without Internet access, reduces attack surface, and ensures complete operational autonomy.

---

## ADR-002: Relational-First Persistence over Vector/Graph Stores

- **Status:** Accepted
- **Context:** Graph databases and vector stores were previously proposed for unified clinical knowledge and patient records. However, clinical encounters, prescriptions, stock inventory, and user identities require strict ACID guarantees, foreign-key referential integrity, and atomic transactions.
- **Decision:** The relational database (SQLite in WAL mode for Matab/Clinic edge nodes, PostgreSQL for multi-site hospitals) is the single authoritative source of truth for all clinical transactions, patient data, prescriptions, and audit events. Graph or vector stores may only be utilized as read-only auxiliary indexes for literature search and similarity retrieval.
- **Consequences:** Ensures non-repudiation, bulletproof referential integrity, zero data loss during power outages on edge hardware, and simplified backup/restore workflows.

---

## ADR-003: Deterministic Safety Preflight Engine with Fail-Closed Semantics

- **Status:** Accepted
- **Context:** Prescribing in Unani medicine requires strict checking of ingredient toxicities, Mudabbar processing rules, Schedule E(1) hazardous botanicals/minerals, pediatric/pregnancy contraindications, and known herb-drug interactions. Relying on non-deterministic LLM evaluation introduces safety risks.
- **Decision:** Implement a deterministic, rule-based safety preflight engine running server-side prior to prescription finalization. The engine evaluates:
  1. Ingredient duplication across polyherbal formulations.
  2. Maximum single and daily dosage limits.
  3. Patient allergy cross-reactivity.
  4. Pregnancy, lactation, and age-based contraindications.
  5. Schedule E(1) and detoxification (Tadbeer/Mudabbar) requirements.
  6. Verified herb-drug interactions.
  The engine outputs one of four discrete states: `PASS`, `WARN`, `BLOCK`, and `UNKNOWN`. Any rule evaluation yielding `BLOCK` prevents signing. Critical missing safety datasets yield `UNKNOWN` and invoke a fail-closed policy requiring documented clinical override.
- **Consequences:** Protects patients from known adverse drug events, eliminates AI hallucinations from the safety perimeter, and provides defensible legal and clinical audit trails.

---

## ADR-004: Immutable Prescription Versioning and Cryptographic Hashing

- **Status:** Accepted
- **Context:** Prescriptions are legal medical orders. In legacy systems, prescription records were frequently updated in-place, risking silent overwrites and loss of historical accountability.
- **Decision:** Prescriptions are immutable upon signature. Any subsequent amendment or modification creates a new prescription version (e.g., `v2`, `v3`) referencing the previous version with a stated clinical justification. Each signed version generates a cryptographic SHA-256 fingerprint encompassing patient ID, practitioner credential, timestamp, formulation items, dosages, instructions, and preflight outcome.
- **Consequences:** Full regulatory compliance with medical record tampering laws, complete audit reproducibility, and verifiable print/dispensing integrity.

---

## ADR-005: Single 3-Zone Consultation Canvas UX

- **Status:** Accepted
- **Context:** Traditional EHRs force clinicians through 10–15 disconnected tabs (demographics, vitals, notes, labs, diagnosis, pharmacy), resulting in high cognitive burden, prolonged consultation times, and charting fatigue.
- **Decision:** Design the primary encounter workspace as a unified **Single Consultation Canvas** structured into three functional zones:
  - **Zone 1 (Patient Context - Collapsible):** Patient identity, OPD token, allergies, active medications, vital history, and prior visit summary. Always accessible.
  - **Zone 2 (Main Clinical Workspace):** Step-by-step progressive flow: Chief Complaint & History -> Vitals & Exam -> Parallel Assessment -> Usul-e-Ilaj Care Plan -> Nuskha Formulation Builder -> Clinician Review & Sign.
  - **Zone 3 (Contextual Guidance Rail - Collapsible):** Real-time safety preflight results, Unani source citations, red flag indicators, and optional advisory suggestions. Never obscures the main charting area.
- **Consequences:** Dramatic reduction in click count (target <5 minutes per complete Unani consultation), zero navigation drift, and high adoption among senior practitioners.

---

## ADR-006: Parallel Unani and Modern Clinical Assessment Tracks

- **Status:** Accepted
- **Context:** Conflating Unani concepts (e.g., *Su-e-Mizaj Maddi*, *Ghalba-e-Dam*) with modern biomedical diagnoses (e.g., Essential Hypertension, Type 2 Diabetes) leads to conceptual confusion and regulatory risk. Conversely, ignoring modern diagnostic terms compromises patient safety and referral readiness.
- **Decision:** Maintain two distinct, parallel assessment tracks within every clinical encounter:
  1. **Unani Assessment Track:** Mizaj evaluation (Damwi, Balghami, Safrawi, Saudawi), Ajnas-e-Ashara parameters, Nabz (pulse), Baul (urine), Baraz (stool), Afaal (functions), and Asbab-e-Sittah الضرورية.
  2. **Modern Clinical Track:** Biomedical findings, differential diagnostic candidates, clinical red flags (e.g., acute chest pain, neurological deficit), investigation orders, and emergency referral triggers.
  Mapping between tracks is strictly informational via reviewed, versioned ontologies and must never represent a Unani score as an independent biomedical diagnosis.
- **Consequences:** Respects the integrity of classical Unani philosophy while providing modern patient safety and hospital interoperability.

---

## ADR-007: Clinical Governance, Source Provenance and Human Signing Authority

- **Status:** Accepted
- **Context:** Medical misinformation, unverified traditional claims, and autonomous AI prescribing threaten clinical validity and patient safety.
- **Decision:** Every clinical monograph, formulation rule, and dose threshold in MATAB OS must be linked to an explicit source record with bibliographic metadata (classical text, pharmacopoeia edition, section, page, and reviewer ID). No generative AI model is permitted to publish directly into the approved knowledge base. AI tools may only propose drafts for authorized human clinicians. Only authorized human practitioners with valid credentials can sign prescriptions or discharge encounters.
- **Consequences:** Complete provenance tracking, compliance with AYUSH / National Medical Commission standards, and unambiguous legal liability boundaries.

---

## ADR-008: Feature and Engine Capability Registry (8-State Lifecycle)

- **Status:** Accepted
- **Context:** Complex health software frequently suffers from "mock drift" where UI components appear functional but point to stubbed backends, or where untested features are exposed as production-ready.
- **Decision:** MATAB OS implements a server-side Feature & Engine Capability Registry. Every subsystem, clinical engine, and module must report one of eight explicit lifecycle states:
  1. `NOT_IMPLEMENTED`
  2. `IMPLEMENTED_NOT_CONNECTED`
  3. `CONNECTED_NOT_VALIDATED`
  4. `FUNCTIONALLY_TESTED`
  5. `CLINICALLY_REVIEWED`
  6. `PILOT_APPROVED`
  7. `PRODUCTION_APPROVED`
  8. `DISABLED_OR_DEGRADED`
  The frontend reads this registry to dynamically gate features. A module is only made available in clinical workflows if it has achieved at least `FUNCTIONALLY_TESTED` (for dev/demo) or `PRODUCTION_APPROVED` (for live clinical mode).
- **Consequences:** Total transparency in system readiness, zero silent mock fallbacks on clinical screens, and defensible release gatekeeping.

---

## ADR-006 (Implementation): Deterministic Duplicate Detection and Human-Controlled Resolution
- **Status:** Accepted
- **File:** [ADR-006-deterministic-duplicate-detection.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-006-deterministic-duplicate-detection.md)
- **Context:** Automated record merging can corrupt drug allergy profiles or mix clinical histories across patients.
- **Decision:** Employ 3 deterministic matching rules (phone match, identifier match, name+DOB match); enforce registration conflict interlock requiring operator override with human reason; strictly prohibit automatic data merging.

---

## ADR-007 (Implementation): Explicit, Unassumed Patient Consent Management
- **Status:** Accepted
- **File:** [ADR-007-explicit-unassumed-consent.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-007-explicit-unassumed-consent.md)
- **Context:** ABDM and privacy standards require explicit consent for treatment, communications, and data sharing.
- **Decision:** Zero assumed consent by default; purpose-specific consent tracking (`GENERAL_CARE`, `COMMUNICATION_SMS`, `COMMUNICATION_WHATSAPP`, `DATA_SHARING_RESEARCH`, `EXTERNAL_REFERRAL`); auditable withdrawal with mandatory reason.

---

## ADR-008 (Implementation): Encounter Lifecycle State Machine and Concurrency Control
- **Status:** Accepted
- **File:** [ADR-008-encounter-lifecycle-concurrency.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-008-encounter-lifecycle-concurrency.md)
- **Context:** Multiple clinic stations editing records concurrently risks dirty writes and bypassed clinical workflows.
- **Decision:** Finite state machine (`DRAFT` -> `IN_PROGRESS` -> `COMPLETED`/`CANCELLED`); optimistic concurrency control using integer `version` columns on patients and encounters; automatic daily facility token allocation.

---

## ADR-009: Versioned Formulation Catalog and Monograph Provenance
- **Status:** Accepted
- **File:** [ADR-009-versioned-formulation-catalog.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-009-versioned-formulation-catalog.md)
- **Context:** Classical Unani medicines (Murakkabat) require strict historical provenance, version tracking, and toxicity verification.
- **Decision:** Separate formulation identity from versioned monographs (`MONOGRAPH_DRAFT` -> `REVIEWED_STANDARD`); enforce Mudabbar (detoxification) flags at the schema layer; tag all development seed fixtures as `[Synthetic]`.

---

## ADR-010: Fail-Closed Deterministic Safety Preflight Engine
- **Status:** Accepted
- **File:** [ADR-010-fail-closed-safety-preflight.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-010-fail-closed-safety-preflight.md)
- **Context:** Automated prescribing requires transparent, deterministic checks for allergen conflicts, max dosages, and toxic compounds.
- **Decision:** Rule-based deterministic engine classifying findings as `BLOCKER` (hard stop) or `WARNING` (mandatory clinician rationale required to override); strictly fail-closed on execution error.

---

## ADR-011: Immutable Signed Prescription Snapshots and Cryptographic Fingerprints
- **Status:** Accepted
- **File:** [ADR-011-immutable-signed-prescription-snapshots.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-011-immutable-signed-prescription-snapshots.md)
- **Context:** Prescriptions are legally binding clinical orders that must resist retroactive tampering.
- **Decision:** Separate drafting from explicit clinician electronic signing; generate canonical JSON snapshots with SHA-256 digital signature digests; lock signed orders and require formal amendment lifecycle for corrections.

---

## ADR-012: Structured Unani Clinical Assessment, Semantic States, and Clinician Finalisation
- **Status:** Accepted
- **File:** [ADR-012-structured-unani-clinical-assessment.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-012-structured-unani-clinical-assessment.md)
- **Context:** Temperamental assessment (Mizaj), functional indicators (Afaal), and six essential causes (Asbab-e-Sittah) must be documented without autonomous algorithmic overreach.
- **Decision:** Sole clinician diagnostic authority (zero machine diagnosis); 4 explicit semantic states (`ASSESSED`, `NOT_ASSESSED`, `NOT_APPLICABLE`, `UNOBTAINABLE`); template versioning (`TMPL-UNANI-CORE`); SHA-256 finalisation digest with formal amendment tracking.

---

## ADR-013: Organ-Axis Contextual Association Layer and Fail-Closed Empty State
- **Status:** Accepted
- **File:** [ADR-013-organ-axis-contextual-association-layer.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-013-organ-axis-contextual-association-layer.md)
- **Context:** Multi-organ interactions (e.g., Stomach-Brain axis) require classical Unani literature references and must not hallucinate unverified relationships.
- **Decision:** Governed concepts and reviewed mappings with classical citations; honest fail-closed empty state (`FAIL_CLOSED_UNREVIEWED`) when querying unreviewed organ pairs; explicit clinician acknowledgement.

---

## ADR-014: Governed Usul-e-Ilaj Treatment Principles, Care Plans, and Prescription Linkage
- **Status:** Accepted
- **File:** [ADR-014-governed-usul-e-ilaj-care-plans.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-014-governed-usul-e-ilaj-care-plans.md)
- **Context:** Treatment principles (Tanqia-e-Mawad, Ta'deel-e-Mizaj, Taghdhiya, Ilaj-bil-Tadbir) must guide clinical care while maintaining a strict boundary against automatic drug ordering.
- **Decision:** Governed treatment principles vocabulary; modular care plan items with priority and cautions; prescription linkage indicates clinical intent only and does NOT sign or dispense medication; cross-patient linkage strictly blocked (HTTP 409).


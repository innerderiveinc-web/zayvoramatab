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

---

## ADR-015: Dual-Lane Clinical Assessment Architecture (Modern Biomedical and Unani Separation)
- **Status:** Accepted
- **File:** [ADR-015-modern-clinical-assessment-lane.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-015-modern-clinical-assessment-lane.md)
- **Context:** Conflating modern biomedical diagnostic findings with Unani temperamental evaluations risks clinical confusion and regulatory exposure.
- **Decision:** Dedicated modern clinical assessment lane operating alongside the Unani assessment in the Consultation workspace; separate domain tables; zero cross-lane overwrites; unified encounter timeline tracking.

---

## ADR-016: Deterministic Clinical Rule Evaluation, Red Flag Safety and Fail-Closed Governance
- **Status:** Accepted
- **File:** [ADR-016-governed-differential-and-red-flag-rules.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-016-governed-differential-and-red-flag-rules.md)
- **Context:** Non-deterministic or silent ML models risk false reassurance in critical situations like acute coronary syndromes or sepsis.
- **Decision:** Deterministic rules engine with fail-closed semantics (`CONTENT_UNAVAILABLE` on empty catalog, `INCOMPLETE` on missing vitals); explainable differential candidates with supporting/contradicting findings; mandatory clinician acknowledgment of red flags.

---

## ADR-017: Investigation Considerations, Referral Records, and Cryptographic Sign-Off
- **Status:** Accepted
- **File:** [ADR-017-investigation-and-referral-safety.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-017-investigation-and-referral-safety.md)
- **Context:** Decision support must not trigger unauthorized diagnostic orders, and completed clinical assessments must resist retroactive tampering.
- **Decision:** Investigation considerations enforce a strict non-ordering contract (`is_order: false`); governed referral records with urgency tiers; clinician PIN electronic signing generating SHA-256 canonical snapshot digests; formal amendment lifecycle.

---

## ADR-018: Governed Clinical Knowledge Sources, Atomic Claims, and Traceable Citations
- **Status:** Accepted
- **File:** [ADR-018-governed-knowledge-sources-and-claims.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-018-governed-knowledge-sources-and-claims.md)
- **Context:** AI hallucination of citations and ungrounded traditional claims undermines clinical validity.
- **Decision:** Governed sources registry with SHA-256 document hashing; atomic claims and structured evidence records; strict epistemological separation of classical monographs from modern RCT trials; zero ungrounded citations.

---

## ADR-019: Hybrid Retrieval, Transliteration Normalization, and Clinical Context Boundaries
- **Status:** Accepted
- **File:** [ADR-019-hybrid-retrieval-and-transliteration.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-019-hybrid-retrieval-and-transliteration.md)
- **Context:** Multi-dialect clinical workflows in Unani and modern medicine require robust transliteration without overstepping into autonomous prescribing.
- **Decision:** Hybrid search combining canonical match, alias index, transliteration synonym dictionaries, and relevance scoring; encounter context retrieval with non-prescribing boundary; reviewer-only approval lifecycle.

---

## ADR-020: Deterministic Clinical Safety Firewall, Substance Identity, and Fail-Closed Evaluation
- **Status:** Accepted
- **File:** [ADR-020-deterministic-clinical-safety-firewall.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-020-deterministic-clinical-safety-firewall.md)
- **Context:** Prescribing toxic botanicals or conflicting medications without deterministic checks risks severe adverse events.
- **Decision:** Deterministic safety rule engine; fail-closed on ambiguous or unmapped substances; non-overridable critical blocks on documented allergies and unpurified Schedule E(1) toxins; server-side re-evaluation immediately before electronic signing.

---

## ADR-021: Auditable Preflight Overrides, Honest Coverage Summary, and Non-Safe Semantics
- **Status:** Accepted
- **File:** [ADR-021-auditable-overrides-and-coverage-summary.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-021-auditable-overrides-and-coverage-summary.md)
- **Context:** Reassuring green "safe" badges create false security, while silent dismissals destroy audit accountability.
- **Decision:** Explicit coverage report detailing checks run, skipped, and dataset limitations; "no applicable alert found" semantics rather than "safe"; mandatory clinician rationale for overridable findings; preflight invalidation on material prescription edits.

---

## ADR-022: Unified Consultation Workspace & Server-Authoritative Workflow Orchestrator
- **Status:** Accepted
- **File:** [ADR-022-unified-consultation-orchestrator.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-022-unified-consultation-orchestrator.md)
- **Context:** Fragmented multi-module views create cognitive fatigue for practicing Hakeems, while relying on frontend status flags compromises clinical safety.
- **Decision:** 7-section guided single-canvas consultation workspace; server-authoritative encounter state machine with audited transitions; mandatory clinical justification for marking sections not applicable; deterministic server sign-off gating; debounced autosave with optimistic concurrency control.

---

## ADR-023: Consultation Output Document Bundle & Care Continuum Follow-up
- **Status:** Accepted
- **File:** [ADR-023-consultation-document-bundle-and-followup.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-023-consultation-document-bundle-and-followup.md)
- **Context:** Completed clinical consultations require tamper-evident legal and patient artifacts alongside integrated follow-up care continuity.
- **Decision:** Atomic PIN-verified consultation finalization generating immutable document snapshots (`consultation_summary`, `prescription_bundle`, `patient_instruction_sheet`) with SHA-256 cryptographic digests, integrated follow-up task scheduling, and idempotency protection.

---

## ADR-024: Versioned Follow-up Plans, Operational Task Invariants, and Consent-Governed Transactional Outbox
- **Status:** Accepted
- **File:** [ADR-024-care-continuity-and-consent-governed-outbox.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-024-care-continuity-and-consent-governed-outbox.md)
- **Context:** Post-consultation care continuity requires versioned follow-up plans, strict task completion rules, conflict-free repeat appointment booking, and consent-governed patient communications without leaking sensitive diagnoses.
- **Decision:** Immutable version history on follow-up plans (`follow_up_plan_versions`); operational task state machine prohibiting completion via reminder dispatch and requiring logged contact attempts before `unable_to_reach`; practitioner slot-locking and non-mutating linked `FOLLOW_UP` encounter creation; minimum-necessary privacy filtering, quiet-hour deferral, send-time consent re-verification, and HMAC-verified idempotent webhook ingestion.

---

## ADR-025: Non-Causal Longitudinal Outcome Tracking, Unit/Method Compatibility Guards, and Adverse Effect Escalation
- **Status:** Accepted
- **File:** [ADR-025-non-causal-outcome-trends-and-adverse-effect-escalation.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-025-non-causal-outcome-trends-and-adverse-effect-escalation.md)
- **Context:** Longitudinal outcome tracking must avoid scientifically invalid causal efficacy claims, prevent mixed-unit/method trend distortions, isolate unverified AI drafts, and escalate severe adverse events immediately.
- **Decision:** Enforce non-causal longitudinal disclaimers (`claims_causal_efficacy: false`); halt trend comparison with `cannot_compare_reliably` when units or measurement methods diverge; exclude `AI_DRAFT_UNVERIFIED` records from verified clinical trends; automatically escalate severe or life-threatening adverse effect reports into urgent clinical review tasks.

---

## ADR-026: Clinic Operations Scheduling, OPD Queue Governance, and Exact-Decimal Billing
- **Status:** Accepted
- **File:** [ADR-026-clinic-operations-scheduling-queue-and-exact-decimal-billing.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-026-clinic-operations-scheduling-queue-and-exact-decimal-billing.md)
- **Context:** Front-desk scheduling, waiting-room token queues, and patient billing require deterministic conflict prevention, public privacy protection, and exact monetary arithmetic.
- **Decision:** Unique `slot_lock_key` double-booking prevention with automatic slot release on cancellation and conflict detection on schedule/leave changes; duplicate active queue token prevention (`active_patient_queue_lock`), clinical role gating for urgent queue priority, and `PUBLIC_SAFE_TOKEN_ONLY` waiting-room display; `Decimal`-only billing rejecting floats and CVV/PAN data, immutable finalized invoice snapshots, honest failed/unknown payment tracking, and idempotent payment/refund reconciliation.

---

## ADR-027: FEFO Pharmacy Inventory Ledger and Signed-Prescription Dispensing
- **Status:** Accepted
- **File:** [ADR-027-fefo-inventory-ledger-and-signed-prescription-dispensing.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-027-fefo-inventory-ledger-and-signed-prescription-dispensing.md)
- **Context:** Dispensary stock management and prescription fulfillment must preserve batch traceability, prevent expired/quarantined dispensing, and respect clinician signing authority.
- **Decision:** Append-only `inventory_movements` ledger with FEFO batch ordering and optimistic concurrency; hard block on dispensing unsigned/draft prescriptions (`UNSIGNED_PRESCRIPTION_CANNOT_DISPENSE`), expired/quarantined batches (`BATCH_EXPIRED_OR_QUARANTINED`), or unauthorized substitutions (`UNAUTHORIZED_SUBSTITUTION_PROHIBITED`); preserve signed prescription cryptographic immutability upon dispensing.

---

## ADR-028: Multi-Branch Organization Hierarchy and Scope-Aware RBAC/ABAC
- **Status:** Accepted
- **File:** [ADR-028-multi-branch-hierarchy-and-scoped-rbac-abac.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-028-multi-branch-hierarchy-and-scoped-rbac-abac.md)
- **Context:** Multi-branch clinics and hospital networks require organization hierarchy management, per-branch staff role assignments, strict tenant/facility isolation, and immediate revocation.
- **Decision:** Cycle-safe organization hierarchy (`_detect_org_hierarchy_cycle`); per-facility role/permission resolution via `staff_assignments` and `require_scoped_permission`; immediate next-request revocation without altering historical clinical attribution; facility activation health checks and lifecycle suspension enforcement.

---

## ADR-029: Inter-Facility Transfers, Layered Configuration Inheritance, and Single-Clinic Migration
- **Status:** Accepted
- **File:** [ADR-029-inter-facility-transfers-config-inheritance-and-single-clinic-migration.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-029-inter-facility-transfers-config-inheritance-and-single-clinic-migration.md)
- **Context:** Multi-branch operations require controlled patient transfers, cross-facility continuity governance, layered configuration with security floors, module prerequisite validation, and zero-data-loss migration from single-clinic deployments.
- **Decision:** Two-step inter-facility transfer workflow (`requested` -> `accepted` -> `completed`) preserving source encounters; policy-driven cross-facility continuity and human-reviewed patient merges; 4-tier configuration inheritance with version rollback and plaintext secret prohibition; module prerequisite DAG validation; repeatable `DRY_RUN`/`EXECUTE` single-clinic migration engine.

---

## ADR-030: Inpatient ADT State Machine, Bed Concurrency Locking & Discharge Fingerprints
- **Status:** Accepted
- **File:** [ADR-030-inpatient-adt-bed-concurrency-and-discharge-fingerprints.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-030-inpatient-adt-bed-concurrency-and-discharge-fingerprints.md)
- **Context:** Inpatient hospital wards and Regimenal Therapy units require deterministic bed allocation, location transfer history, and legally binding discharge summaries.
- **Decision:** Database-level `active_stay_lock TEXT UNIQUE` in `ipd_beds` preventing concurrent bed double-allocation; strict 8-state ADT state machine; inter-ward clinical handovers recorded in `ipd_handover_records`; mandatory discharge section checklist (`course_in_hospital`, `follow_up_plan_summary`, `return_precautions`); and clinician PIN digital signing generating immutable SHA-256 fingerprints in `ipd_discharge_summary_versions`.

---

## ADR-031: HL7 FHIR R4 Bundles, ABDM Interoperability & Purpose-Aware Consent Ledger
- **Status:** Accepted
- **File:** [ADR-031-fhir-r4-abdm-interoperability-and-consent-ledger.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-031-fhir-r4-abdm-interoperability-and-consent-ledger.md)
- **Context:** Interoperability with ABDM national digital health infrastructure and external hospitals requires compliant FHIR R4 bundles, patient consent validation, and preservation of Unani medical concepts without lossy degradation.
- **Decision:** Provider-independent FHIR R4 validator and Document Bundle exporter (`OPConsultation`, `DischargeSummary`, `DiagnosticReport`) across 14 supported resources; terminology mappings with explicit equivalence levels (`INEXACT_LOSSY`) and custom Unani extensions preserving classical provenance; purpose-aware consent verification (`data_sharing_consents`) blocking unauthorized data exchange; and transparent readiness state machine (`CONTRACT_TESTED_HARNESS`, `EXTERNAL_SANDBOX_VALIDATED`, `PRODUCTION_APPROVED`) with contract-accurate ABDM test harness.

---

## ADR-032: Production Readiness Gate, Security & Privacy Audit, and Clinical Safety Sign-Off
- **Status:** Accepted
- **File:** [ADR-032-production-readiness-gate-security-privacy-clinical-safety.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-032-production-readiness-gate-security-privacy-clinical-safety.md)
- **Context:** Following completion of Prompts 01 through 12, an empirical audit and quality gate was required to verify real implementation fidelity, fail-closed safety preflight, zero runtime dependency on legacy code, database backup resilience, and operational runbook readiness.
- **Decision:** Establish an evidence-based production readiness gate: verify 100% of the 188+ automated tests, enforce fail-closed safety preflight with zero autonomous AI signing, mandate SQLite WAL `VACUUM INTO` online hot backups with `PRAGMA integrity_check`, strictly demarcate external interoperability maturity states, produce 12 comprehensive audit artifacts in `docs/production-readiness/`, and require multi-stakeholder clinical and technical go-live sign-offs.

---

## ADR-033: Controlled Pilot Launch, 13-Stage Clinic Onboarding & Clinical Safety Governance
- **Status:** Accepted
- **File:** [ADR-033-controlled-pilot-launch-clinic-onboarding-and-safety-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-033-controlled-pilot-launch-clinic-onboarding-and-safety-governance.md)
- **Context:** Transitioning to real-patient clinic pilots requires server-side scope enforcement, readiness gates, 13-stage facility onboarding, role-based training, governed data migration, support triage, and independent clinical safety escalation.
- **Decision:** Enforce versioned pilot scope server-side (`enforce_pilot_scope`); evaluate eligibility gates on backend (`evaluate_pilot_eligibility`); require 13-stage onboarding progression; provide zero-mutation `DRY_RUN` data migration; track role-based training with synthetic scenarios; separate routine tickets from emergency `clinical_safety_incident_queue`; support non-destructive P0 pause/stop conditions; and generate formal review packs with continue/pause/stop recommendations.

---

## ADR-034: Post-Pilot Evaluation, Adoption Scorecard & Scale Decision Framework
- **Status:** Accepted
- **File:** [ADR-034-post-pilot-evaluation-adoption-scorecard-and-expansion-decision-framework.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-034-post-pilot-evaluation-adoption-scorecard-and-expansion-decision-framework.md)
- **Context:** Following the execution of controlled clinic pilots, an evidence-based mechanism is required to evaluate whether the system should continue its limited pilot, expand within scope, scale to additional clinics, enable specific modules, pause for remediation, or stop/roll back.
- **Decision:** Implement versioned evaluation master records (`pilot_evaluations`), verified evidence source tracking, a 14-metric adoption and reliability scorecard across 8 domain categories with explicit `UNAVAILABLE` telemetry handling, descriptive clinical outcomes classification without efficacy inference, sanitized feedback triage without patient PHI, non-downgrade incident re-review blocking expansion on open P0s, 8 independent expansion proposals evaluated across 11 gates, tripartite sign-off (Clinical, Operations, Security) for scale approval, and mandatory retest evidence references before remediation actions can close.

---

## ADR-035: Knowledge Authenticity, Verification & Clinical Safety Framework (KAVS)
- **Status:** Accepted
- **File:** [ADR-035-knowledge-authenticity-verification-and-clinical-safety-framework.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-035-knowledge-authenticity-verification-and-clinical-safety-framework.md)
- **Context:** Autonomous AYUSH systems require genuine, auditable clinical evidence without probabilistic generative AI hallucinations or unverified automated claim publishing.
- **Decision:** Implement KAVS with 5 independent verification dimensions (Source Authenticity, Extraction Fidelity, Evidence Characterization, Clinical Review State, Intended-Use Authorization); statutory rights reviews; page-anchored extraction segments with OCR confidence scoring; evidence contradiction graphs; immutable cryptographic releases (`manifest_hash`); change-impact dependency tracing; and consultation-time contextual retrieval with deterministic citation resolvability and honest `insufficient_information` caveats.

---

## ADR-036: KAVS Foundation — Source Registry, Provenance, Locators & Claim Traceability (Phase K0 + K1)
- **Status:** Accepted
- **File:** [ADR-036-kavs-foundation-source-registry-provenance-and-claim-traceability.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-036-kavs-foundation-source-registry-provenance-and-claim-traceability.md)
- **Context:** Prompt 17 specifies the concrete implementation of Phase K0 and K1 of KAVS: source registry, exact physical/digital page locators, discrete verification events, versioned governance policies, atomic claim review workflows, and an append-only audit trail.
- **Decision:** Build `kavs_source_locators`, `kavs_source_verification_events`, `kavs_governance_policies`, and `kavs_audit_events` schemas (Migration 016); extend `KAVSEngine` with fine-grained locator verification, source authenticity checks, versioned policy management, and atomic claim lifecycle transitions (`DRAFT` -> `UNDER_REVIEW` -> `APPROVED` / `REJECTED` / `WITHDRAWN`); mandate 5-dimension verification records before claim approval; enforce consultation retrieval firewall blocking unreviewed drafts; and provide a restricted Knowledge Admin UI with an append-only audit ledger.

---

## ADR-037: KAVS Phase K2–K3 — Verified Source Ingestion, OCR Fidelity & Claim Extraction Workbench
- **Status:** Accepted
- **File:** [ADR-037-kavs-source-ingestion-extraction-workbench.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-037-kavs-source-ingestion-extraction-workbench.md)
- **Context:** Prompt 18 defines the implementation requirements for Phase K2 and K3 of KAVS: source rights preflight verification, cryptographic file integrity checking (SHA-256 + magic bytes), a server-authoritative 21-state ingestion lifecycle, explicit disambiguation between physical PDF page indices and printed page numbers, automated high-risk clinical pattern detection (posology numerals, historical Unani units, botanical taxonomy, safety contraindications), a human-supervised transcription correction workbench, and candidate claim drafting mathematically quarantined from live consultation retrieval until dual-human clinical promotion.
- **Decision:** Implement Migration 017 with tables `kavs_rights_preflight_events`, `kavs_source_files`, `kavs_ingestion_job_events`, `kavs_extraction_pages`, `kavs_extraction_tables`, `kavs_extraction_corrections`, `kavs_claim_drafts`, and `kavs_adapter_registry`; build engine operations for rights preflight, checksum-validated file uploads, 21-state machine transitions, automated high-risk regex scanning, human transcription corrections, and candidate draft segregation with promotion gates requiring underlying segment `human_checked` fidelity; mount 24 REST API endpoints; and add the Ingestion & Extraction Workbench tab to the Knowledge Admin UI.

---

## ADR-038: Unani Ontology, Canonical Terminology & Mufradat/Murakkabat Structured Catalog (Prompt 19)
- **Status:** Accepted
- **File:** [ADR-038-unani-ontology-and-structured-catalog.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-038-unani-ontology-and-structured-catalog.md)
- **Context:** Prompt 19 mandates a source-grounded, versioned, reviewable Unani terminology and catalog layer, requiring strict separation between concept identity and clinical claims, multi-script original wording preservation, first-class ambiguity representation for Mufradat, source-edition cataloging for Murakkabat with verbatim traditional units, graph edge non-inference, and isolated review queues.
- **Decision:** Implement Migration 018 (`knowledge_concepts`, `concept_names`, `material_identity`, `catalog_formulations`, `catalog_formulation_ingredients`, `knowledge_assertions`, `concept_relations`, `external_identifier_crosswalks`, `catalog_change_events`, `catalog_review_tasks`); build `UnaniOntologyEngine` with optimistic concurrency, multi-script Arabic/Urdu diacritic-aware normalization, explainable search, and clinician safety isolation; mount 17 REST endpoints; and integrate the Unani Ontology & Catalog tab into the Knowledge Admin UI.

---

## ADR-039: Unani Clinical Knowledge Mapping & Organ-Axis Relationship Engine (Prompt 20)
- **Status:** Accepted
- **File:** [ADR-039-unani-clinical-knowledge-mapping-and-organ-axis.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-039-unani-clinical-knowledge-mapping-and-organ-axis.md)
- **Context:** Prompt 20 mandates a source-grounded, carefully governed mapping layer for Unani concepts, clinical observations, organ/system concepts, and the product's Organ-Axis framework, strictly prohibiting relationship inflation, transitive clinical inference, unreviewed crosswalk equality, or leakage of encounter hypotheses into global ontology.
- **Decision:** Implement Migration 019 (`relation_type_registry`, `relationship_assertions`, `organ_axis_frameworks`, `organ_axis_memberships`, `concept_mappings`, `relationship_conflicts`, `case_hypothesis_links`); build `KnowledgeMappingEngine` with controlled predicates, provenance assertion enforcement, versioned product navigation model isolation, crosswalk candidate equivalence quarantining, formal conflict adjudication queue, protected encounter hypothesis linking, and bounded graph traversal with hard depth limits and non-inference warnings; mount 21 REST endpoints; and integrate Organ-Axis & Relations tab into the Knowledge Admin UI.

---

## ADR-040: Evidence Classification, Clinical Claim Verification & Citation Validation Engine (Prompt 21)
- **Status:** Accepted
- **File:** [ADR-040-evidence-classification-and-citation-validation.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-040-evidence-classification-and-citation-validation.md)
- **Context:** Prompt 21 mandates an auditable evidence characterization and claim validation engine preventing citation decoration, unverified claim publishing, and claim laundering (e.g., reinterpreting traditional documentation as proven modern clinical efficacy, or preclinical in-vitro assays as human cure).
- **Decision:** Implement Migration 020 (`claim_type_registry`, `claim_source_links`, `citation_validation_runs`, `support_assessments`, `evidence_characterizations`, `source_status_events`, `intended_use_approvals`, `evidence_conflicts`); build `EvidenceVerificationEngine` with 15 controlled claim categories, 6-dimensional independent citation validation, non-numeric question-sensitive evidence appraisal, automated retraction cascade suspension, fail-closed clinician publication gating (`allow_clinical_action: false`), epistemological statement generation, and conflict adjudication queue; mount 20 REST API endpoints; and integrate Evidence & Citations tab into the Knowledge Admin UI.

---

## ADR-041: Evidence-Aware Clinical Knowledge Retrieval (Hybrid RAG) & Clinician Answer Generation Engine (Prompt 22)
- **Status:** Accepted
- **File:** [ADR-041-evidence-aware-clinical-rag-and-answer-generation.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-041-evidence-aware-clinical-rag-and-answer-generation.md)
- **Context:** Prompt 22 mandates a permission-aware, source-grounded retrieval and answer generation layer for ZAYVORA MATAB OS, strictly eliminating hallucinated clinical authority, citation decoration, blurred epistemological categories, and autonomous prescribing/dosing.
- **Decision:** Implement Migration 021 (`rag_query_intent_registry`, `rag_evidence_packs`, `rag_answer_runs`, `rag_answer_claims`, `rag_answer_citations`, `rag_retrieval_feedback`, `rag_eval_dataset`); build `ClinicalRAGEngine` with controlled query intent registry, canonical concept resolver with multi-script search and botanical/mineral ambiguity detection, permission-aware hybrid retrieval with live retraction checking, immutable evidence packs with SHA-256 reproducibility hashes, atomic structured claim generation using epistemological templates, mandatory per-claim citation binding with exact locators, multi-stage post-generation validation pipeline (schema, citation existence, access, version, retraction, boundary), honest abstention (`insufficient_evidence`, `restricted_clinical_action`, `material_identity_ambiguous`), patient encounter isolation, and governance feedback resolution queue; mount 11 REST API endpoints; and integrate Clinical RAG & Assistant tab into the Knowledge Admin UI.

---

## ADR-042: Clinical Decision Support (CDS) Orchestrator & Clinician Approval Workflow (Prompt 23)
- **Status:** Accepted
- **File:** [ADR-042-clinical-decision-support-orchestrator-and-clinician-approval.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-042-clinical-decision-support-orchestrator-and-clinician-approval.md)
- **Context:** Prompt 23 mandates a governed clinical workflow orchestrator and clinician approval engine for ZAYVORA MATAB OS, eliminating alert fatigue, preventing autonomous prescribing/diagnosing, coordinating patient observations with safety firewall checks and verified evidence, and enforcing cryptographic non-repudiation and append-only post-signature amendments.
- **Decision:** Implement Migration 022 (`cds_policy_registry`, `cds_runs`, `cds_cards`, `cds_reviews`, `safety_evaluation_refs`, `clinical_signoffs`, `encounter_amendments`, `workflow_events`); build `CDSOrchestratorEngine` with 8-state encounter finite state machine, version-bound CDS evaluations, typed decision-support cards with triggering inputs and rule/evidence links, mandatory clinician review actions with documented rationale for warnings/blockers, 6-dimension readiness gate (patient identity, clinical assessment, CDS blockers, safety firewall, version currency, signer authorization), PIN-verified cryptographic signing with SHA-256 fingerprinting, post-signature append-only amendments, emergency administrative kill switch, and patient context isolation; mount 13 REST API endpoints; and integrate CDS Orchestrator & Approval tab into the Knowledge Admin UI.

---

## ADR-043: Clinical Workflow Intelligence, Missing-Information Detection & Data-Quality Engine (Prompt 24)
- **Status:** Accepted
- **File:** [ADR-043-clinical-workflow-intelligence-and-data-quality-engine.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-043-clinical-workflow-intelligence-and-data-quality-engine.md)
- **Context:** Prompt 24 mandates a deterministic data quality and workflow-completeness engine detecting missing information, inconsistent values, stale data, unresolved duplicates, and invalid units, distinguishing administrative completeness from clinical adequacy and routing remediation by role.
- **Decision:** Implement Migration 023 (`dq_rule_registry`, `dq_freshness_policies`, `dq_evaluations`, `dq_findings`, `dq_field_provenance`, `dq_reconciliation_decisions`); build `DataQualityEngine` with canonical 7-state missingness classification (`MISSING`, `UNKNOWN`, `NOT_RECORDED`, `NOT_ASSESSED`, `DECLINED_BY_PATIENT`, `NOT_APPLICABLE`, `UNAVAILABLE`), governed rule registry across 6 categories, field-specific freshness policies with age tracking, physiological range and unit validators, transparent role-based remediation queues (`FRONT_DESK`, `TRIAGE_NURSE`, `CLINICIAN`, `PHARMACIST`, `ADMIN`), blocker deferral prevention, clinician-attributed conflict reconciliation ledger with mandatory rationale, and data quality workflow readiness gating; mount 11 REST API endpoints; and integrate Data Quality & Missingness tab into the Knowledge Admin UI.

---

## ADR-044: Clinical Encounter Timeline, Longitudinal Patient Intelligence & Continuity-of-Care Engine (Prompt 25)
- **Status:** Accepted
- **File:** [ADR-044-clinical-encounter-timeline-and-longitudinal-intelligence.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-044-clinical-encounter-timeline-and-longitudinal-intelligence.md)
- **Context:** Prompt 25 mandates a longitudinal patient timeline, clinical intelligence, and continuity-of-care engine for ZAYVORA MATAB OS, requiring true temporal context (`occurred_at` vs `recorded_at`), explicit temporal precision (`YEAR`, `MONTH`, `DAY`, `EXACT_TIMESTAMP`), epistemological stream separation (Unani vs Modern vs Medication vs Investigation vs Care Continuity), immutable projection of encounters into timeline events, a longitudinal medication ledger tracking state transitions (`ACTIVE`, `DISCONTINUED`, `COMPLETED`, `PAUSED`), actionable care continuity task orchestration with contact attempts, clinician-reviewed timeline summaries without hallucination, zero patient data leakage into global RAG indexes, and fail-safe clinical safety non-negotiables.
- **Decision:** Implement Migration 024 (`patient_timeline_events`, `care_continuity_tasks`, `medication_status_ledger`, `timeline_summary_runs`); build `PatientTimelineEngine` with multi-stream lane classification, chronological ordering, encounter-to-timeline projection sync, longitudinal medication ledger lifecycle management, care continuity task lifecycle with contact attempt logs and completion tracking, draft summary generation with mandatory clinician review gate, and zero patient data leakage; mount 11 REST API endpoints; and integrate Longitudinal Timeline & Care tab into the Knowledge Admin UI.

---

## ADR-045: Clinical Outcome Tracking, Treatment Response Measurement & Longitudinal Evaluation Engine (Prompt 26)
- **Status:** Accepted
- **File:** [ADR-045-clinical-outcome-tracking-and-longitudinal-evaluation.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-045-clinical-outcome-tracking-and-longitudinal-evaluation.md)
- **Context:** Prompt 26 mandates a governed clinical outcome measurement capability, baseline designation, compatibility preflight engine, exposure tracking without causal overclaim, verified instrument scoring, and human review gates—preventing missing-value imputation, false causal conclusions, or invented success thresholds.
- **Decision:** Implement Migration 025 (`care_episodes`, `outcome_concepts`, `measurement_instruments`, `outcome_protocols`, `outcome_protocol_runs`, `outcome_observations`, `instrument_scoring_runs`, `outcome_comparisons`, `treatment_exposure_contexts`, `outcome_interpretations`, `outcome_aggregate_reports`); build `ClinicalOutcomesEngine` with strict separation between raw observations, calculated measures, and clinical interpretations, compatibility checks across 8 dimensions, non-causal exposure tracking, and aggregate reporting with cell suppression ($\ge 5$); mount 19 REST API endpoints; and integrate Outcomes & Evaluation tab into the Knowledge Admin UI.

---

## ADR-046: Clinical Safety Surveillance, Adverse Event Management & Pharmacovigilance Workflow (Prompt 27)
- **Status:** Accepted
- **File:** [ADR-046-clinical-safety-surveillance-and-pharmacovigilance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-046-clinical-safety-surveillance-and-pharmacovigilance.md)
- **Context:** Prompt 27 mandates a traceable, privacy-protective safety-event workflow for recording and managing adverse events, suspected medicine-related reactions, product-quality concerns, medication errors, near misses, and clinical safety incidents.
- **Decision:** Implement Migration 026 (`safety_events`, `safety_event_products`, `safety_event_triages`, `safety_event_investigations`, `safety_event_actions`, `safety_event_reports`, `pharmacovigilance_signals`); build `PharmacovigilanceEngine` with governed 4-tier severity triage, WHO-UMC causality appraisal, cluster signal detection with disproportionate reporting ratios (PRR), action verification gates, and statutory safety reporting formats; mount 20 REST API endpoints.

---

## ADR-047: Clinical Knowledge Governance, Rule Versioning & Controlled Safety-Rule Release Engine (Prompt 28)
- **Status:** Accepted
- **File:** [ADR-047-clinical-knowledge-governance-and-rule-release.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-047-clinical-knowledge-governance-and-rule-release.md)
- **Context:** Prompt 28 mandates an end-to-end governance and release system ensuring no AI-generated, developer-authored, or imported clinical content silently becomes active in clinical workflows without multi-gate review, sandboxed testing, cryptographic manifest binding, runtime verification, and rollback capability.
- **Decision:** Implement Migration 027 (`governed_artifacts`, `governed_artifact_versions`, `governed_artifact_transitions`, `governed_clinical_rules`, `rule_test_executions`, `governance_releases`, `governance_impact_analyses`, `governance_runtime_resolutions`); build `ClinicalKnowledgeGovernanceEngine` with 17 lifecycle states, role-separated authoring/review/approval, AST-safe sandboxed rule evaluation, multi-party release manifests with SHA-256 bindings, verified one-click rollback, and encounter-level version pinning; mount 15 REST API endpoints.

---

## ADR-048: Clinical Audit, Accountability, Compliance Evidence & Tamper-Evident Event Ledger (Prompt 29)
- **Status:** Accepted
- **File:** [ADR-048-clinical-audit-and-tamper-evident-ledger.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-048-clinical-audit-and-tamper-evident-ledger.md)
- **Context:** Prompt 29 mandates an auditable, immutable, cryptographically verifiable event ledger proving whether an event occurred, when it occurred, who authorized it, what inputs were present, and whether any byte has been modified since it was recorded.
- **Decision:** Implement Migration 028 (`clinical_ledger_events`, `audit_annotations`, `audit_integrity_checkpoints`, `audit_retention_policies`, `audit_legal_holds`, `audit_evidence_exports`); build `ClinicalAuditLedgerEngine` with continuous SHA-256 hash chaining ($H_i = \text{SHA-256}(C_i \parallel H_{i-1})$) from genesis hash, strict data minimization and secret sanitization, fail-closed protection for gated consequential actions, append-only dispute annotations with no silent history mutation, non-destructive integrity sweep diagnostics, statutory retention policies, legal holds, and purpose-bound compliance export package generation; mount 9 REST API endpoints; and integrate the Audit Ledger & Integrity Console into the Knowledge Admin UI.

---

## ADR-049: Enterprise Security, Privacy, Consent & Identity Access Governance Engine (Prompt 30)
- **Status:** Accepted
- **File:** [ADR-049-enterprise-security-privacy-consent-and-access-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-049-enterprise-security-privacy-consent-and-access-governance.md)
- **Context:** Prompt 30 mandates a unified enterprise security control plane enforcing server-side authorization on every path, idle session controls, step-up authentication, professional credential lifecycle gating, governed consent capture and withdrawal, time-limited delegation, and audited break-glass workflows bound to Prompt 29's cryptographic ledger.
- **Decision:** Implement Migration 029 (`security_principals`, `user_sessions`, `clinician_credential_registry`, `consent_authority_records`, `delegated_access_grants`, `break_glass_events`, `access_review_campaigns`, `access_review_decisions`, `security_policy_registry`); build `SecurityGovernanceEngine` with step-up authentication, clinician license verification gatekeeper, purpose-bound patient consent evaluation, time-limited break-glass emergency grants with mandatory post-access review, periodic role recertification campaigns, and continuous SHA-256 audit ledger integration; mount 21 REST API endpoints; and integrate the Security & Privacy Governance Console into the web frontend.

---

## ADR-050: Enterprise Interoperability, FHIR APIs & ABDM Data Exchange Engine (Prompt 31)
- **Status:** Accepted
- **File:** [ADR-050-enterprise-interoperability-fhir-and-abdm-data-exchange.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-050-enterprise-interoperability-fhir-and-abdm-data-exchange.md)
- **Context:** Prompt 31 mandates a standards-compliant, auditable, and clinically safe interoperability layer for ZAYVORA MATAB OS supporting pinned FHIR R4.0.1 profiles (`ndhm.in#6.5.0`), non-lossy Unani terminology preservation, ABDM M1–M4 workflows, inbound record staging with clinician reconciliation, durable outbox delivery, and cryptographic audit ledger integration.
- **Decision:** Implement Migration 030 (`interop_specification_registry`, `interop_terminology_mappings`, `abdm_consent_requests`, `abdm_consent_artefacts`, `inbound_record_reconciliations`, `interop_transfer_outbox`, `interop_webhook_verifications`); build `EnterpriseInteroperabilityEngine` with pinned specification registry, Unani concept preservation, deterministic NRCeS DocumentBundle generation (Composition first entry), ABHA M1 identity linking, M2 care-context privacy, M3 consent artefact scope gatekeeper, M4 registry checks, clinician reconciliation queue, durable outbox, replay-safe webhooks, and continuous SHA-256 audit ledger event logging; mount 23 REST API endpoints; and integrate the Interoperability & ABDM console into the web frontend.

---

## ADR-051: Enterprise Integration Monitoring, API Reliability, Queue Management & Interoperability Operations Engine (Prompt 32)
- **Status:** Accepted
- **File:** [ADR-051-enterprise-integration-monitoring-queue-management-and-reliability.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-051-enterprise-integration-monitoring-queue-management-and-reliability.md)
- **Context:** Prompt 32 mandates an enterprise-grade integration reliability, monitoring, and operations management engine for ZAYVORA MATAB OS. In clinical environments, naive integrations lead to dangerous duplicate orders, unmanaged failures, and data exposure in log streams.
- **Decision:** Implement Migration 031 (`integration_jobs`, `integration_attempts`, `integration_inbox_events`, `integration_reconciliations`, `dead_letter_items`, `connector_health_snapshots`, `integration_circuit_breakers`); build `IntegrationOperationsEngine` enforcing a strict 20-state machine, idempotency for side effects, first-class `outcome_unknown` handling requiring formal reconciliation before retrying, bounded exponential backoff with jitter and retry budgets, structured dead-letter queue with safe replay eligibility, automated circuit breakers shielding external partners, inbound callback deduplication, pre-retry consent and authorization re-verification, and zero PHI in telemetry; mount 16 REST API endpoints; and integrate the Integration Operations & Reliability console into the web frontend.

---

## ADR-052: Enterprise Analytics, Operational Intelligence & Clinical Governance Dashboards (Prompt 33)
- **Status:** Accepted
- **File:** [ADR-052-enterprise-analytics-operational-intelligence-and-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-052-enterprise-analytics-operational-intelligence-and-governance.md)
- **Context:** Prompt 33 mandates trustworthy, role-aware operational analytics and clinical governance dashboards using canonical operational records and governed metric definitions. In clinical operating systems, naive analytics engines frequently fabricate numbers, conflate process documentation with clinical efficacy, publish polarizing clinician leaderboards, desynchronize from canonical ledgers, or leak protected health information in reports.
- **Decision:** Implement Migration 032 (`governed_metric_definitions`, `metric_calculation_runs`, `metric_reconciliation_exceptions`, `analytics_export_audit`); build `EnterpriseAnalyticsEngine` deriving figures strictly from canonical tables (`appointments`, `queue_tokens`, `encounters`, `invoices`, `payments`, `payment_refunds`, `inventory_batches`, `care_continuity_tasks`, `safety_cases`, `governed_artifacts`, `clinical_ledger_events`, `integration_jobs`), enforcing a strict non-causal policy with mandatory caveats, banning public clinician leaderboards, computing financial metrics with decimal precision ($\text{Net Collections} = \sum\text{Payments} - \sum\text{Refunds}$), tracking metric governance lifecycles (`draft` $\to$ `review` $\to$ `approved` $\to$ `retired`), stripping PHI from exports while generating SHA-256 tamper-evident audit receipts, and explicitly communicating data freshness and watermarks; mount 16 REST API endpoints; and integrate the Enterprise Analytics & Governance console into the web frontend.

---

## ADR-053: Clinical Operations Command Center, Capacity Planning & Workflow Bottleneck Intelligence (Prompt 34)
- **Status:** Accepted
- **File:** [ADR-053-clinical-operations-command-center-and-capacity-planning.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-053-clinical-operations-command-center-and-capacity-planning.md)
- **Context:** Prompt 34 mandates a reliable operational command center, capacity planning engine, and workflow bottleneck intelligence service for ZAYVORA MATAB OS. Traditional operational tools often conflate queue elapsed durations with clinical triage acuity scores, rank clinicians pejoratively by consultation speed, guess missing capacity values, expose patient PHI on shared wallboards, or pollute production records with what-if simulations.
- **Decision:** Implement Migration 033 (`command_center_threshold_rules`, `operational_alerts`, `capacity_scenarios`, `operational_action_audit`); build `ClinicalCommandCenterEngine` enforcing pure operations scoping without evaluating clinical efficacy, strictly decoupling queue elapsed timers from triage acuity, banning clinician speed rankings, computing deterministic capacity slots solely from configured working calendars ($\text{Slots} = \sum (\text{shift} - \text{breaks} - \text{blocks}) // (\text{slot} + \text{buffer})$), strictly segregating what-if simulations into `capacity_scenarios`, providing zero-PHI privacy-preserving wallboard mode (`wallboard_mode=true`), comparing stages against approved threshold rules with transparent factual reasons, and auditing human-in-the-loop operational actions into `operational_action_audit`; mount 11 REST API endpoints; and integrate the Operations Command Center console into the web frontend.

---

## ADR-054: Clinical Workflow Automation, Rules Engine & Human-Approved Task Orchestration (Prompt 35)
- **Status:** Accepted
- **File:** [ADR-054-clinical-workflow-automation-and-task-orchestration.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-054-clinical-workflow-automation-and-task-orchestration.md)
- **Context:** Prompt 35 mandates a deterministic, version-controlled rules and workflow automation engine for ZAYVORA MATAB OS. In healthcare, automated systems must never make autonomous clinical judgments, execute arbitrary dynamic code, violate patient communication preferences, duplicate side effects, or bypass human approval gates on sensitive operational actions.
- **Decision:** Implement Migration 034 (`workflow_rules`, `workflow_rule_versions`, `automation_events`, `workflow_planned_actions`, `workflow_action_attempts`); build `WorkflowAutomationEngine` strictly bounded to administrative tasks with zero autonomous clinical actions, fail-closed deterministic condition evaluation across 10 allowlisted operators with zero `eval`/`exec`, dry-run sandbox isolation, pre-flight communication consent checks, SHA-256 payload hash locking (`payload_hash`) on sensitive actions awaiting human approval, and complete attempt audit trails; seed Workflows A–F; mount 12 REST API endpoints; and integrate the Workflow Automation & Human Approval console into the web frontend.

---

## ADR-055: Enterprise Workflow Intelligence, SLA Governance & Exception Resolution Engine (Prompt 36)
- **Status:** Accepted
- **File:** [ADR-055-enterprise-sla-governance-and-exception-resolution.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-055-enterprise-sla-governance-and-exception-resolution.md)
- **Context:** Prompt 36 mandates a governed, explainable way to define operational service expectations (SLAs), detect workflow exceptions, assign ownership, track timers with pause/resume support, escalate unresolved work, and verify resolutions—without creating competing task engines or autonomous clinical decision-making.
- **Decision:** Implement Migration 035 (`sla_policies`, `sla_policy_versions`, `workflow_exceptions`, `sla_pause_intervals`, `sla_escalation_events`); build `SlaGovernanceEngine` strictly bounded to operational administrative scope with zero autonomous clinical actions, fail-closed deterministic timer calculation (`ON_TRACK`, `AT_RISK`, `BREACHED`, `PAUSED`, `UNMEASURABLE`), cryptographic deduplication, pause ledger accounting, multi-stage zero-PHI escalations, allowed resolution codes, separation of duties on verification, and operational pulse monitoring; seed starter policies 001–007; mount 19 REST API endpoints under `/api/v1/sla/`; and integrate the SLA Governance & Exception Resolution console into the web frontend.

---

## ADR-056: Enterprise Workflow Simulation, Failure Injection & Recovery Validation Engine (Prompt 37)
- **Status:** Accepted
- **File:** [ADR-056-enterprise-workflow-simulation-and-failure-injection.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-056-enterprise-workflow-simulation-and-failure-injection.md)
- **Context:** Prompt 37 mandates an enterprise workflow simulation, failure injection, and recovery validation engine for ZAYVORA MATAB OS to validate error handling, idempotency, retries, circuit breakers, and clinical safety boundaries before production deployment.
- **Decision:** Implement Migration 036 (`simulation_scenarios`, `simulation_scenario_versions`, `simulation_runs`, `simulation_step_executions`, `simulation_assertions`, `simulation_release_gates`); build `WorkflowSimulationEngine` enforcing a hard production lockout (`ENVIRONMENT == 'production'` raises HTTP 403 Forbidden), sandbox side-effect suppression (zero real network calls), zero autonomous clinical prescribing/dosing guardrails, cryptographic namespace isolation (`namespace_prefix = f"sim-{uuid.hex[:6]}"`) with idempotent teardown, separation of duties on high-risk scenario approval, and release gate verification against persisted canonical assertions; seed starter scenarios 001–006; mount 11 REST API endpoints under `/api/v1/simulation/`; and integrate the Simulation & Faults console into the web frontend.

---

## ADR-057: Production Release Engineering, Deployment Governance, Feature Flags & Rollback Orchestration (Prompt 38)
- **Status:** Accepted
- **File:** [ADR-057-production-release-engineering-and-rollback-orchestration.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-057-production-release-engineering-and-rollback-orchestration.md)
- **Context:** Prompt 38 mandates a governed, observable, and auditable production release engineering and feature flagging framework for ZAYVORA MATAB OS across development, test, staging, pilot, and production environments, with controlled feature activation and verified recovery paths.
- **Decision:** Implement Migration 037 (`release_manifests`, `release_gate_evaluations`, `feature_flags`, `feature_flag_audit`, `deployment_executions`, `rollback_executions`); build `ReleaseGovernanceEngine` enforcing immutable release manifests with cryptographic build provenance (SHA-256 digests and Git commit/branch references), strict separation of duties preventing release authors from self-approving their own production releases, zero secrets or PHI in persisted manifests or configuration diffs (`[REDACTED_SECRET]`), fail-closed server-side feature flags with cohort targeting, instantaneous emergency kill-switches, and automated deployment promotions with preflight and smoke verifications, backed by verified rollback strategies (`DISABLE_FEATURE`, `ROLLBACK_ARTIFACT`, `ROLL_FORWARD`, `CONTAIN`) with side-effect tracking; seed starter flags and initial release manifest; mount 15 REST API endpoints under `/api/v1/releases/` and `/api/v1/flags/`; and integrate the Releases & Flags workbench into the web frontend.

---

## ADR-058: Production Observability, Incident Response, SLO Governance & Reliability Operations (Prompt 39)
- **Status:** Accepted
- **File:** [ADR-058-production-observability-incident-response-and-slo-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-058-production-observability-incident-response-and-slo-governance.md)
- **Context:** Prompt 39 mandates trustworthy production telemetry, actionable alerting, incident response coordination, SLO governance with error budgets, and safe remediation guardrails for ZAYVORA MATAB OS without exposing patient data or allowing operational automation to bypass clinical authority.
- **Decision:** Implement Migration 038 (`observability_service_catalog`, `observability_telemetry_metrics`, `observability_alert_definitions`, `observability_alert_instances`, `observability_slo_registry`, `observability_incidents`, `observability_incident_timeline`, `observability_remediation_actions`); build `ObservabilityReliabilityEngine` enforcing four-tier health assessment (`/health/live`, `/health/ready`, `/observability/diagnostics/deep`, workflow correctness), bounded low-cardinality metric dimensions, strict zero-PHI/secrets sanitization, deduplicated alert firing with actionable runbooks and auto-resolution, 9-stage incident lifecycle management with mandatory resolution verification evidence, mathematically governed SLO error budgets with burn rate tracking, and allowlisted, reversible remediation actions bounded by 300s cooldowns and a strict prohibition against mutating clinical data; seed baseline catalog, alerts, and SLOs; mount 21 REST API endpoints under `/api/v1/observability/`; and integrate the Observability & Incidents workbench into the web frontend.

---

## ADR-059: Disaster Recovery, Business Continuity, Backup/Restore Verification & Resilience Engineering (Prompt 40)
- **Status:** Accepted
- **File:** [ADR-059-disaster-recovery-business-continuity-and-resilience-engineering.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-059-disaster-recovery-business-continuity-and-resilience-engineering.md)
- **Context:** Prompt 40 mandates safe, verifiable recovery from infrastructure failure, accidental deletion, corrupted data, failed releases, and integration outages for ZAYVORA MATAB OS without risking live clinical systems, exposing patient data, or bypassing clinical authority.
- **Decision:** Implement Migration 039 (`dr_domain_criticality_catalog`, `dr_backup_catalog`, `dr_restore_drill_executions`, `dr_business_continuity_runbooks`, `dr_downtime_reconciliation_records`); build `DisasterRecoveryContinuityEngine` enforcing governed BIA criticality policies across 12 domains, live online non-blocking database backups via SQLite streaming backup with SHA-256 digests and PRAGMA integrity verification, a 7-step isolated restore drill pipeline with hard production lockouts, offline downtime runbooks with duplicate reference detection, and a clinician-supervised paper reconciliation queue; seed baseline domains, runbooks, and sample reconciliation record; mount 13 REST API endpoints under `/api/v1/dr/`; and integrate the Disaster Recovery & Continuity workbench into the web frontend.

---

## ADR-060: Enterprise Data Lifecycle, Retention, Archival & Secure Deletion Governance Engine (Prompt 41)
- **Status:** Accepted
- **File:** [ADR-060-enterprise-data-lifecycle-retention-archival-and-secure-deletion.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-060-enterprise-data-lifecycle-retention-archival-and-secure-deletion.md)
- **Context:** Prompt 41 mandates an enterprise data lifecycle, retention, archival, and secure deletion governance framework for ZAYVORA MATAB OS to govern records from creation through retention, archival, legal holds, and disposal with traceability, privacy, and clinical-record integrity.
- **Decision:** Implement Migration 040 (`data_lifecycle_inventory_catalog`, `data_lifecycle_policies`, `data_lifecycle_legal_holds`, `data_lifecycle_evaluation_runs`, `data_lifecycle_operations`, `data_lifecycle_requests`); build `EnterpriseDataLifecycleEngine` enforcing multi-store reach across database tables, filesystem artifacts, and caches, statutory 7-year minimum clinical retention with strict prohibition of physical row deletion on signed clinical encounters and prescriptions (restricted/archival transition only), active legal hold precedence strictly freezing disposal and archival, side-effect free deterministic dry-runs, and a data subject privacy rights pipeline with mandatory identity verification and closure evidence; seed 14 data categories, 5 starter approved policies, and baseline legal hold; mount 15 REST API endpoints under `/api/v1/lifecycle/`; and integrate the Data Lifecycle & Retention workbench into the web frontend.

---

## ADR-061: Enterprise Data Governance, Master Data Management & Data Quality Stewardship Engine (Prompt 42)
- **Status:** Accepted
- **File:** [ADR-061-enterprise-data-governance-master-data-and-quality-stewardship.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-061-enterprise-data-governance-master-data-and-quality-stewardship.md)
- **Context:** Prompt 42 mandates an enterprise-level Master Data Management (MDM), Data Governance & Data Quality Stewardship Engine for ZAYVORA MATAB OS to establish consistent, accountable, and auditable maintenance of core clinical, operational, and Unani master records.
- **Decision:** Implement Migration 041 (`mdm_master_entities_catalog`, `mdm_data_quality_rules`, `mdm_data_quality_scans`, `mdm_data_quality_findings`, `mdm_duplicate_candidate_reviews`, `mdm_patient_cross_references`, `mdm_terminology_mappings`, `mdm_import_batches`, `mdm_import_records`, `mdm_stewardship_cases`, `mdm_stewardship_case_events`); build `EnterpriseMasterDataGovernanceEngine` enforcing zero automatic patient merges, clinical immutability on finalized encounters and prescriptions, multi-attribute explainable duplicate scoring, reversible master cross-reference linking, governed Unani-to-biomedical terminology stewardship with mandatory limitation caveats, a versioned 9-dimension DQ rule catalog, staged bulk imports with dry-run validation, and actionable stewardship cases; seed master entities catalog, 9-dimension DQ rules, terminology mappings, and sample stewardship case; mount 25 REST API endpoints under `/api/v1/mdm/`; and integrate the Master Data & Data Quality workbench into the web frontend.

---

## ADR-062: Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine (Prompt 43)
- **Status:** Accepted
- **File:** [ADR-062-enterprise-data-lineage-schema-evolution-and-impact-analysis.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-062-enterprise-data-lineage-schema-evolution-and-impact-analysis.md)
- **Context:** Prompt 43 mandates an Enterprise Data Lineage, Schema Evolution & Change Impact Analysis Engine for ZAYVORA MATAB OS to map end-to-end data dependencies across domain entities, database tables, REST APIs, asynchronous event topics, workflow rules, terminology concepts, and analytics cubes, assessing blast radius and release gates before changes are released.
- **Decision:** Implement Migration 042 (`lineage_contracts_registry`, `lineage_nodes`, `lineage_edges`, `lineage_change_requests`, `lineage_impact_reports`, `lineage_change_reviews`); build `EnterpriseDataLineageEngine` enforcing that "Impact unknown" is a real result (never an optimistic "no impact") blocking releases via `BLOCKED_BY_UNKNOWNS`, cycle-safe depth-bounded graph traversal in downstream and upstream directions, zero autonomous clinical alterations, strict separation of duties preventing change request authors from self-approving release gates, mandatory Clinical Director review when clinical safety flags are active, and zero PHI in graph nodes or reports; seed baseline data contracts, lineage nodes, verified edges, and sample change request; mount 17 REST API endpoints under `/api/v1/lineage/`; and integrate the Data Lineage & Evolution workbench into the web frontend.

---

## ADR-063: Enterprise Configuration, Secrets & Environment Governance Engine (Prompt 44)
- **Status:** Accepted
- **File:** [ADR-063-enterprise-configuration-secrets-and-environment-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-063-enterprise-configuration-secrets-and-environment-governance.md)
- **Context:** Prompt 44 mandates an Enterprise Configuration, Secrets & Environment Governance Engine for ZAYVORA MATAB OS to govern runtime configuration, secret storage/rotation, environment separation boundaries, feature flags, and controlled configuration changes without exposing credentials or weakening clinical, privacy, or tenant controls.
- **Decision:** Implement Migration 043 (`config_settings_catalog`, `config_environments_registry`, `config_secret_references`, `config_secret_rotations`, `config_change_proposals`, `config_drift_scans`, `config_drift_findings`, `config_audit_ledger`); build `EnterpriseConfigGovernanceEngine` enforcing zero secret exposure in code, database, logs, or UI (externalized secret manager metadata pointers only), deterministic fail-closed production startup preflight rejecting insecure default keys or weak credentials, strict environment isolation perimeters preventing test/synthetic crosstalk with production databases or external gateways, provider-aware multi-phase dual-secret rotation (`planned` $\to$ `prepared` $\to$ `updated` $\to$ `verified` $\to$ `old_retired`) with immediate urgent compromise containment, strict separation of duties preventing proposal authors from self-approving configuration releases, public client configuration filtering (`PUBLIC_CLIENT` scope only), and automated runtime drift detection; seed baseline environments, settings catalog, secret references, sample proposal, and bootstrap audit entry; mount 24 REST API endpoints under `/api/v1/config/`; and integrate the Config & Secrets workbench into the web frontend.

---

## ADR-064: Enterprise Identity Governance, Privileged Access Management & Access Certification Engine (Prompt 45)
- **Status:** Accepted
- **File:** [ADR-064-enterprise-identity-governance-pam-access-certification.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-064-enterprise-identity-governance-pam-access-certification.md)
- **Context:** Prompt 45 mandates an Enterprise Identity Governance, Privileged Access Management (PAM) & Access Certification Engine for ZAYVORA MATAB OS to govern human and machine identities, role assignments, privileged permissions, service accounts, emergency break-glass sessions, and periodic access certifications.
---

## ADR-065: Enterprise Security Posture, Vulnerability Governance & Security Control Verification Engine (Prompt 46)
- **Status:** Accepted
- **File:** [ADR-065-enterprise-security-posture-and-vulnerability-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-065-enterprise-security-posture-and-vulnerability-governance.md)
- **Context:** Prompt 46 mandates an Enterprise Security Posture, Vulnerability Governance & Security Control Verification Engine for ZAYVORA MATAB OS to discover, prioritize, remediate, and verify security risks across application code, dependencies, configuration, APIs, containers, and database operations with verifiable evidence, strict secret redaction, and fail-closed release gates.
- **Decision:** Implement Migration 045 (`security_assets_inventory`, `security_controls_registry`, `security_vulnerability_findings`, `security_control_executions`, `security_exceptions_ledger`, `security_release_gate_evaluations`, `security_audit_ledger`); build `EnterpriseSecurityPostureEngine` enforcing verifiable evidence over static badges (every control tracks scope, tool/version, freshness within 24h, and explicit limitations), zero secret disclosure (strict regex redaction across code, logs, findings, and UI), non-intrusive local and CI verification without fuzzing or exploiting production, fail-closed release gates (`BLOCKED` or `STALE` if checks are missing/outdated, and blocking on unmitigated P0/P1 findings), clinical non-negotiables preservation (suppressions never bypass patient consent, clinician PIN signatures, drug safety firewalls, or tenant boundaries), governed time-limited exceptions ledger (mandatory expiration $\le 90$ days, business justification, compensating controls, risk owner sign-off, and automatic expiration), 5 built-in verification scanners (SCA dependencies, secret leaks, API authorization/headers, container/IaC, and SQL injection/parameterization), and SHA-256 chained audit ledger; seed 6 baseline security assets, 5 controls, 1 baseline finding, 1 approved exception, and bootstrap audit entry; mount 19 REST API endpoints under `/api/v1/security-posture/`; and integrate the Security Posture & Vulnerabilities workbench into the web frontend.

---

## ADR-066: Threat Modeling, Abuse-Case Analysis & Secure Development Lifecycle (SDLC) Governance Engine (Prompt 47)
- **Status:** Accepted
- **File:** [ADR-066-threat-modeling-abuse-cases-and-secure-sdlc-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-066-threat-modeling-abuse-cases-and-secure-sdlc-governance.md)
- **Context:** Prompt 47 mandates a Threat Modeling, Abuse-Case Analysis & Secure SDLC Governance Engine for ZAYVORA MATAB OS to identify security, privacy, and clinical-workflow threats during architecture and design, convert material risks into testable controls, and govern them through coding, release, and post-deployment review.
- **Decision:** Implement Migration 046 (`threat_models_registry`, `threat_trust_boundaries`, `threat_abuse_cases`, `threat_testable_controls`, `threat_residual_risk_decisions`, `sdlc_change_reviews`, `threat_sdlc_audit_ledger`); build `EnterpriseThreatModelingSDLCService` enforcing that threat models reflect real database tables and domain code, STRIDE-Plus-Clinical-Hazard threat categorization, automated stale-model detection based on review cadences and repository revisions, hard clinical non-negotiables (strictly rejecting residual risk acceptances for direct harm prescribing hazards or tenant boundary bypasses), governed residual risk acceptances ($\le 90$ days TTL, compensating controls, designated risk owner approvals), and deterministic SDLC change review gates (evaluating to `PASS`, `BLOCKED`, `CONDITIONAL_PASS`, `STALE_MODEL`); seed baseline threat model, trust boundary, abuse case, testable control, change review, and bootstrap audit entry; mount 22 REST API endpoints under `/api/v1/threat-modeling/`; and integrate the Threat Modeling & SDLC workbench into the web frontend.

---

## ADR-067: Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine (Prompt 48)
- **Status:** Accepted
- **File:** [ADR-067-clinical-safety-case-hazard-analysis-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-067-clinical-safety-case-hazard-analysis-governance.md)
- **Context:** Prompt 48 mandates an Enterprise Clinical Safety Case, Hazard Analysis & Safety Control Verification Engine for ZAYVORA MATAB OS to identify clinical hazards, define safety requirements and controls, connect controls to executable test verifications, and govern release decisions for safety-relevant functionality.
- **Decision:** Implement Migration 047 (`clinical_intended_use_registry`, `clinical_hazard_register`, `safety_requirements_catalog`, `safety_control_verifications`, `clinical_safety_cases`, `clinical_safety_incidents`, `safety_release_gate_evaluations`, `clinical_safety_audit_ledger`); build `EnterpriseClinicalSafetyCaseEngine` enforcing bounded intended use baselines, human clinician PIN authority, continuous test verification linkage, fail-closed release gates, and GSN safety cases; mount 26 REST API endpoints under `/api/v1/safety-case/`; and integrate the Clinical Safety Cases workbench into the web frontend.

---

## ADR-068: End-to-End Test Automation, Regression Testing & Release Qualification Engine (Prompt 49)
- **Status:** Accepted
- **File:** [ADR-068-end-to-end-test-automation-regression-release-qualification.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-068-end-to-end-test-automation-regression-release-qualification.md)
- **Context:** Prompt 49 mandates an End-to-End Test Automation, Regression Testing & Release Qualification Engine for ZAYVORA MATAB OS to build reliable, repeatable automated verification for real application workflows and create an evidence-based release qualification process.
- **Decision:** Implement Migration 048 (`test_automation_suites_catalog`, `test_execution_runs`, `test_flakiness_and_quarantine_register`, `release_qualification_profiles`, `release_candidate_qualifications`, `test_automation_defect_register`, `test_qualification_audit_ledger`); build `EnterpriseTestAutomationReleaseQualificationEngine` enforcing real database persistence over shallow toast assertions, deterministic synthetic environment isolation with time injection seams, strict pharmacopoeial grounding of clinical dosage/toxicity fixtures (NFUM/UPI), governed flakiness quarantine with root-cause classifications and strict 14-day SLA dates, fail-closed release gate decisions (`QUALIFIED`, `BLOCKED`, `STALE_EVIDENCE`) across DEV/STAGING/PROD profiles, bidirectional defect-to-hazard traceability with automated stack trace sanitization, and tamper-evident SHA-256 audit chaining; seed baseline test suites, execution run, quarantine record, 3 qualification profiles, candidate qualification, defect record, and bootstrap audit entry; mount 24 REST API endpoints under `/api/v1/test-qualification/`; and integrate the Test Automation & Release Qualification workbench into the web frontend.

---

## ADR-069: Independent V1 Codebase Gap Audit, Prompt-to-Code Traceability & Evidence-Based Execution Plan (Prompt 50)
- **Status:** Accepted
- **File:** [ADR-069-independent-v1-codebase-gap-audit-and-execution-plan.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-069-independent-v1-codebase-gap-audit-and-execution-plan.md)
- **Context:** Prompt 50 mandates an independent repository-wide codebase gap audit across Prompts 1–49 to establish what is genuinely implemented, what works, what is mocked, what is missing, and which changes are necessary to make V1 safe, coherent, and releasable.
- **Decision:** Formally record the verification of all 840 automated tests passing with 0 failures across 48 database migrations; adopt the 49-row Prompt-to-Code Traceability Matrix (Table A); adopt the bounded V1 Single-Facility Matab Outpatient (OPD) scope definition with explicit deferral of inpatient, multi-hospital cloud federation, and live ABDM bridge to subsequent phases; register the 4 P0 items and 5 P1 items in `P0_P1_GAP_REGISTER.md`; classify the release recommendation as `CONDITIONAL PILOT CANDIDATE (Single-Facility Matab OPD)`; and adopt the dependency-ordered Phased Execution Roadmap (Phases 0 to 6).

---

## ADR-070: Accessibility, Localization, Right-to-Left (RTL) UI & Clinical Human-Factors Engine (Prompt 51)
- **Status:** Accepted
- **File:** [ADR-070-accessibility-localization-rtl-and-clinical-human-factors.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-070-accessibility-localization-rtl-and-clinical-human-factors.md)
- **Context:** Prompt 51 mandates an Enterprise Accessibility, Localization, Right-to-Left (RTL) UI & Clinical Human-Factors Validation Engine for ZAYVORA MATAB OS to make supported clinical workflows accessible, understandable, and usable across languages, writing directions, devices, and user contexts—without compromising clinical meaning, obscuring diagnostic uncertainty, or bypassing safety controls.
- **Decision:** Implement Migration 049 (`i18n_locales`, `i18n_translation_catalogs`, `i18n_clinical_glossary`, `user_a11y_preferences`, `a11y_accessibility_audits`, `human_factors_validation_scenarios`, `a11y_human_factors_audit_ledger`); build `AccessibilityLocalizationEngine` enforcing Tabib authority over safety-critical translations, WCAG 2.1 AA audit tracking, NASA-TLX cognitive workload validation, and SHA-256 tamper-evident audit chaining; update design system with multilingual font stacks, high-contrast theme, accessible skip-link, focus rings, and native RTL logical properties; create client `i18n.js` engine; mount 15 REST API endpoints under `/api/v1/a11y-i18n/`; and integrate the Accessibility & Human Factors workbench into the web frontend.

---

## ADR-071: API & Integration Certification, Contract Testing & Developer Governance Engine (Prompt 52)
- **Status:** Accepted
- **File:** [ADR-071-api-integration-certification-contract-testing-developer-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-071-api-integration-certification-contract-testing-developer-governance.md)
- **Context:** Prompt 52 mandates an Enterprise API & Integration Certification, Contract Testing & Developer Governance Engine for ZAYVORA MATAB OS to establish a verifiable, secure, and maintainable integration layer for internal APIs, developer credentials, webhooks, and external clinical providers.
- **Decision:** Implement Migration 050 (`api_integrations_catalog`, `api_contract_definitions`, `api_developer_keys`, `api_idempotency_store`, `api_webhook_subscriptions`, `api_webhook_deliveries`, `api_inbound_webhook_receipts`, `api_integration_certifications`, `api_developer_governance_ledger`); build `ApiIntegrationCertificationEngine` enforcing 6-level evidence hierarchies (`CONTRACT_DEFINED`, `MOCK_TESTED`, `CONTRACT_TESTED`, `SANDBOX_VERIFIED`, `PRODUCTION_SMOKE_VERIFIED`, `UNVERIFIED`), automated contract drift detection against runtime router endpoints, developer API key hashing with IP allowlisting, strict idempotency replay protection, inbound HMAC signature verification with timestamp skew tolerance ($\le 300\text{s}$), outbound webhook SSRF shielding against private RFC 1918/loopback destinations, and SHA-256 tamper-evident governance ledger chaining; mount 16 REST API endpoints under `/api/v1/api-governance/`; and integrate the API & Developer Governance workbench into the web frontend.

---

## ADR-072: Enterprise Performance, Scalability & Capacity Engineering Engine (Prompt 54)
- **Status:** Accepted
- **File:** [ADR-072-enterprise-performance-scalability-capacity-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-072-enterprise-performance-scalability-capacity-governance.md)
- **Context:** Prompt 54 mandates an Enterprise Performance, Scalability & Capacity Engineering Engine for ZAYVORA MATAB OS to establish an evidence-based performance engineering process covering application latency, database query efficiency, background job capacity, integration throughput, resource limits, capacity planning, dependency circuit-breaking, and graceful degradation under load without vanity or fabricated metrics.
- **Decision:** Implement Migration 051 (`perf_benchmark_scenarios`, `perf_benchmark_runs`, `perf_slow_query_registry`, `perf_capacity_profiles`, `perf_circuit_breaker_states`, `perf_governance_audit_ledger`); build `PerformanceScalabilityEngine` enforcing linear-interpolation deterministic percentiles ($p_{50}, p_{95}, p_{99}$), fail-closed SLA status evaluation (`PASS`, `WARNING`, `BREACH`), slow-query fingerprinting with index advisory, operational headroom sizing with graceful degradation triggers (`ENABLE_READ_STALE_AND_DEFER_ANALYTICS` and `THROTTLE_NEW_SESSIONS_AND_QUEUE`), dependency circuit-breaking (`CLOSED`, `OPEN`, `HALF_OPEN`), in-process live microbenchmark runner, and SHA-256 tamper-evident governance ledger chaining; seed 5 baseline scenarios, baseline capacity profile, 3 circuit breakers, and genesis audit block; mount 14 REST API endpoints under `/api/v1/performance/`; and integrate the Performance & Capacity workbench into the web frontend.

---

## ADR-073: Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance Engine (Prompt 55)
- **Status:** Accepted
- **File:** [ADR-073-enterprise-multitenant-isolation-saas-governance.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-073-enterprise-multitenant-isolation-saas-governance.md)
- **Context:** Prompt 55 mandates an Enterprise Multi-Tenant Isolation, Tenant Lifecycle & SaaS Governance Engine for ZAYVORA MATAB OS to enforce mathematically verifiable tenant boundaries, fail-closed tenant context resolution, controlled lifecycle state transitions, cross-tenant IDOR shielding, sanitized data exports, time-bounded break-glass access, quota enforcement, and tamper-evident audit chaining.
- **Decision:** Implement Migration 052 (`saas_tenant_lifecycle`, `saas_tenant_entitlements`, `saas_break_glass_tickets`, `saas_governance_audit_ledger`); build `TenantGovernanceEngine` enforcing fail-closed tenant resolution derived strictly from authenticated session/membership, explicit 5-state lifecycle transitions (`PROVISIONING` -> `ACTIVE` <-> `SUSPENDED` -> `OFFBOARDING` -> `DECOMMISSIONED`) with automatic session purge on suspension/decommission, cross-tenant entity ownership and relationship validation (`validate_entity_ownership`, `validate_cross_tenant_relationship`), offboarding impact calculation with clinical blocker checks, sanitized tenant data export with CSV formula injection defense (`=`, `+`, `-`, `@`, `\t`, `\r`), time-bounded support break-glass sessions ($\le 60$m max TTL) with approved reason codes and instant revocation, plan tier entitlements and resource quota checks, and SHA-256 chained blockchain audit ledger rooted at genesis block `SGL-GENESIS-0001`; mount 14 REST API endpoints under `/api/v1/tenant-governance/`; and integrate the Tenant & SaaS Governance workbench into the web frontend.

---

## ADR-074: Enterprise Backup, Disaster Recovery, Business Continuity & Verified Restore Engine (Prompt 56)
- **Status:** Accepted
- **File:** [ADR-074-enterprise-backup-disaster-recovery-verified-restore.md](file:///Users/irfanashraf/Downloads/zayvora%20matab%20os/docs/adr/ADR-074-enterprise-backup-disaster-recovery-verified-restore.md)
- **Context:** Prompt 56 mandates an Enterprise Backup, Disaster Recovery, Business Continuity & Verified Restore Engine for ZAYVORA MATAB OS to establish evidence-based disaster recovery, signed cryptographic manifests with chain of custody, Point-in-Time Recovery (PITR) markers, 7-phase isolated restore drills with side-effect suppression, multi-tenant boundary preservation, promotion gatekeepers, immutable retention locks, and tamper-evident blockchain audit ledgers.
- **Decision:** Implement Migration 053 (`dr_backup_manifests`, `dr_pitr_recovery_points`, `dr_isolated_restore_verifications`, `dr_governance_audit_ledger`); build `BackupRestoreEngine` providing online zero-downtime SQLite WAL backups, companion signed `.manifest.json` generation with physical file and signature tamper detection, PITR checkpoint markers with passive WAL flushes, comprehensive 7-phase isolated sandbox restore drills with hard outbound side-effect suppression (`outbound_messaging_suppressed`, `payments_suppressed`, `webhooks_suppressed`, `production_queues_paused`), technical PRAGMA integrity checks, foreign key checks, clinical invariant checks, tenant isolation validation, empirical RTO/RPO calculation in seconds against approved targets ($RTO \le 900\text{s}$, $RPO \le 300\text{s}$), fail-closed production promotion gatekeeper requiring documented officer approval, retention lifecycle management with immutable lock protection against ransomware, and SHA-256 chained blockchain governance ledger rooted at genesis block `DGL-GENESIS-0001`; mount 12 REST API endpoints under `/api/v1/dr/`; and integrate the Backup & Restore workbench into the web frontend.




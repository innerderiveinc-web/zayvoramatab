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






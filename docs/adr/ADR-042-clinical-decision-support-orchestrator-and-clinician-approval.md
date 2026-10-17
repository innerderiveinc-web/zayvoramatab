# ADR-042: Clinical Decision Support (CDS) Orchestrator & Clinician Approval Workflow (Prompt 23)

- **Status:** Accepted
- **Date:** October 2026
- **Context:**
  Prompt 23 mandates a governed clinical workflow orchestrator and clinician approval engine for ZAYVORA MATAB OS. A pervasive hazard in clinical software is either silent automation (systems prescribing, diagnosing, or dispensing without accountable human review) or alert fatigue (flooding clinicians with unranked, noisy popups that become ignored). Furthermore, clinical encounters must possess strict legal, temporal, and clinical non-repudiation: once signed, an encounter record and its attached prescription cannot be mutated in place; any subsequent modification requires a formalized, justified amendment.
  The orchestrator coordinates inputs from the patient record, clinician observations, Unani and modern assessment lanes, governed knowledge (Prompts 17–22), and safety checks (Prompt 07), synthesizes structured decision-support cards, and enforces a mandatory multi-dimension readiness gate before cryptographic signature.

- **Decision:**
  1. **Encounter Workflow State Machine:** Enforces a deterministic finite state machine (`scheduled` -> `arrived` -> `in_consultation` -> `assessment_in_progress` -> `decision_support_active` -> `treatment_planning` -> `ready_to_finalize` -> `signed` / `amended` / `cancelled`). Prohibits illegal state transitions, skips, or race conditions.
  2. **Governed Decision-Support Policies (`cds_policy_registry`):** All decision-support checks are backed by versioned, reviewed clinical policies with explicit intent, triggers, severity levels (`INFO`, `WARNING`, `CRITICAL`, `BLOCKER`), and safety rules.
  3. **Exact Encounter-Version Evaluation (`cds_runs`):** Decision support evaluations are bound to the exact immutable snapshot/version of the encounter and its active assessments/prescriptions. Any clinician change increments the encounter version and flags stale runs.
  4. **Typed Decision-Support Cards (`cds_cards`):** Findings are delivered as structured cards categorizing safety warnings, dosing checks, organ-axis considerations, and diagnostic differential gaps. Each card details triggering inputs, rule references, evidence links, and explicit limitations/uncertainties.
  5. **Explicit Clinician Review Actions (`cds_reviews`):** Decision-support cards cannot be dismissed blindly. Actions (`ACCEPTED`, `DISMISSED_WITH_REASON`, `MODIFIED`, `DEFERRED`) require clinician attribution and documented clinical rationale for all warnings and blockers.
  6. **Six-Dimension Readiness Gate:** Prior to finalizing an encounter, the orchestrator evaluates six mandatory dimensions:
     - D1: Patient Identity & Demographics Confirmed
     - D2: Clinical Assessments Complete or Justified (Unani or Modern documented)
     - D3: CDS Blocking Cards Resolved (zero unreviewed BLOCKER cards)
     - D4: Safety Firewall Cleared on Prescription (overall status != 'BLOCK')
     - D5: Encounter Version Currency (no stale preflights)
     - D6: Signer Authorization (clinician role authorized with configured signing PIN)
  7. **Cryptographic Attestation & Non-Repudiation (`clinical_signoffs`):** Clinician sign-off requires separate PIN verification against `practitioner_profiles`. The system computes deterministic SHA-256 hashes of the encounter state and prescription snapshot, locking them into an immutable signed state.
  8. **Post-Signature Formal Amendments (`encounter_amendments`):** Direct modification of a signed encounter or prescription is prohibited. Changes must be recorded as append-only formal amendments requiring clinical justification, change summaries, and fresh attestation.
  9. **Emergency Governance Kill Switch:** Administrative control allowing authorized safety governance to immediately pause decision-support card generation while preserving core manual consultation, documentation, and signing workflows.
  10. **Zero Patient Context Leakage:** Decision-support evaluation data and patient facts are strictly isolated; zero patient data is leaked to shared caches, logs, or external models.

- **Consequences:**
  - Zero autonomous prescribing or machine-generated signing; human clinical accountability is preserved at all gates.
  - Audit-grade reproducibility: every recommendation, override, rationale, and signature is cryptographically verifiable.
  - Fail-closed enforcement: encounters with unresolved contraindications or blockers cannot be finalized or dispensed.

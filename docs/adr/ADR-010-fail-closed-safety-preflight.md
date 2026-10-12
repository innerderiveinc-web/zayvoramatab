# ADR-010: Fail-Closed Deterministic Safety Preflight Engine

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 03)

---

## 1. Context and Problem Statement

Clinical prescribing carries significant patient safety risks, including:
- Known patient allergen conflicts (e.g., patient allergic to honey prescribed an Arq or Majun containing honey as base).
- Exceeding daily maximum recommended doses.
- Unpurified toxic compounds (lack of required Mudabbar detoxification).
- Severe herb-herb or drug-herb contraindications.

Traditional systems either execute black-box algorithmic scores that lack auditability or allow clinicians to bypass safety checks silently.

## 2. Decision

1. **Deterministic Rule Engine Architecture:**
   - The safety preflight engine executes transparent, deterministic rules defined in code and database tables.
   - It executes without external runtime dependencies or probabilistic black-box inference models.
2. **Severity Classification:**
   - `BLOCKER`: Hard stop prohibiting electronic signing until the offending item is corrected or removed (e.g. uncertified Mudabbar toxin, known severe allergen conflict).
   - `WARNING`: Clinical precaution (e.g. high normal dose, age-adjusted cautionary note) that requires an explicit, authenticated clinician override rationale before signing.
3. **Fail-Closed Policy:**
   - If a safety preflight evaluation throws an exception, encounters unresolvable metadata, or fails database connectivity, it must return a `BLOCKER` finding (`PREFLIGHT_EXECUTION_FAILURE`). It must never fail open.
4. **Audit Trail for Warning Overrides:**
   - Overriding a `WARNING` creates a persistent record in `prescription_validation_findings` recording the clinician ID, timestamp, and justification rationale.

## 3. Consequences

### Positive:
- Clinicians cannot accidentally dispense known allergens or uncertified toxins.
- All safety overrides are fully documented and legally attributable.
- The engine operates reliably without internet connectivity or external proprietary APIs.

### Negative / Trade-offs:
- Strict preflight enforcement adds a mandatory validation step to the prescription authoring workflow.

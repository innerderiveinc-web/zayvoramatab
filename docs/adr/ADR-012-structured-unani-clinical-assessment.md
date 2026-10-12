# ADR-012: Structured Unani Clinical Assessment, Semantic States, and Clinician Finalisation

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 04)

---

## 1. Context and Problem Statement

Unani-Tibb clinical decision-making relies on evaluating the patient's temperament (Mizaj), physiological functions (Afaal), and six essential causes (Asbab-e-Sittah Zaruriyyah).
Two critical architectural failure modes exist in conventional medical software:
1. **Autonomous diagnostic overreach:** The software attempts to infer a definitive Mizaj score or disease diagnosis using algorithmic heuristics, bypassing human clinical responsibility.
2. **Binary form completion:** Systems force clinicians to fill every field or record empty values as negative findings, failing to distinguish between an unasked question, an unobtainable finding (e.g. acute patient), and an assessed negative finding.

## 2. Decision

1. **Human Clinician Authority — Zero Autonomous Diagnosis:**
   - The system serves purely as structured clinical documentation and decision support.
   - It records the clinician's evaluated primary Mizaj (`DAMAWI`, `BALGHAMI`, `SAFRAWI`, `SAWDAWI`, `MOTADIL`), dominance level (`MILD`, `MODERATE`, `SEVERE`), and diagnostic reasoning.
   - The engine does not generate autonomous temperamental classifications.
2. **Explicit Semantic States per Domain / Observation:**
   - Every observation supports four distinct semantic states:
     - `ASSESSED`: Directly observed and verified during the encounter.
     - `NOT_ASSESSED`: Deliberately deferred or not examined.
     - `NOT_APPLICABLE`: Irrelevant to the patient's presentation or encounter scope.
     - `UNOBTAINABLE`: Cannot be captured due to patient state, emergency, or lack of instrumentation.
   - Blank or unrecorded fields are never silently converted into "normal" clinical findings.
3. **Template Versioning and Classical Source Provenance:**
   - Assessments reference governed templates (`TMPL-UNANI-CORE`) linked to specific version IDs and bibliographic citations (e.g., Al-Qanun fi al-Tibb).
4. **Finalisation and Cryptographic Snapshot:**
   - Clinician finalisation (`POST /api/v1/unani-assessments/{id}/finalise`) computes a SHA-256 integrity hash across all recorded domains, responses, and conclusions, creating an immutable historical record.
   - Formal amendments require providing a clinical justification note and spawn a tracked version successor.

## 3. Consequences

### Positive:
- Legally unambiguous clinical attribution: the clinician retains sole diagnostic authority.
- Nuanced documentation supporting classical Unani epistemology alongside modern medical record integrity.
- Auditable provenance showing which classical texts or templates guided the assessment.

### Negative / Trade-offs:
- Requires structured documentation during consultations rather than unstructured free-form narrative notes alone.

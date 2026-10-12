# ADR-016: Deterministic Clinical Rule Evaluation, Red Flag Safety and Fail-Closed Governance

- **Status:** Accepted
- **Date:** 2026-10-13
- **Context:**
  Modern clinical decision support systems frequently suffer from "black box" machine learning models or heuristic evaluators that provide false reassurance when clinical data is incomplete, or that silently default to "low risk" when rule catalogs fail to load. In high-risk ambulatory and emergency scenarios (acute coronary syndrome, malignant hypertension, severe sepsis, acute stroke), non-deterministic or overly lenient systems place patients at severe risk. Furthermore, differential diagnostic considerations must explain their underlying logic rather than presenting an authoritative machine diagnosis.
- **Decision:**
  1. **Strict Deterministic Safety Rules:** Implement a purely deterministic, rule-based clinical engine (`ClinicalRulesEngine`) operating on versioned, governed rule definitions (`RULE-RF-001` through `RULE-RF-004`, `RULE-DDX-001`, `RULE-DDX-002`, `RULE-INV-001`, etc.).
  2. **Fail-Closed Governance:**
     - If the rule catalog is empty or unapproved, the engine fails closed with status `CONTENT_UNAVAILABLE` or `INCOMPLETE`. It never produces an ungrounded "clear" or "low risk" assessment.
     - If vital observations are missing or vital inputs needed for an alert rule are not recorded, the engine tracks missing inputs explicitly (`missing_vital_inputs`) and returns safety status `INCOMPLETE` rather than suppressing warnings.
  3. **Zero Autonomous Diagnoses (Explainable Candidates Only):** Differential diagnostic considerations are returned as advisory candidates with an explainable contract:
     - Supporting clinical findings.
     - Contradicting or refuting findings.
     - Missing or required investigations/observations.
     - Source guideline citations with version and status.
     - Explicit clinical limitations disclaimer.
  4. **Human Clinician In-the-Loop:** Red flags demand explicit acknowledgment with documented clinical action. Differential candidates require active clinician decision (`CONFIRMED`, `PROVISIONAL`, `RULED_OUT`, `IGNORED`).
- **Consequences:**
  - Eliminates silent safety bypasses and AI hallucinations in clinical risk triage.
  - Guarantees full legal and ethical auditability, establishing that clinical authority resides solely with the licensed human practitioner.

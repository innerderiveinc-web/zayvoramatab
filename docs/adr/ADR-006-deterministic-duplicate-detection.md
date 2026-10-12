# ADR-006: Deterministic Duplicate Detection and Human-Controlled Resolution (Strictly No Automatic Merge)

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 02)

---

## 1. Context and Problem Statement

In clinic and hospital environments, duplicate patient records are a frequent challenge resulting from variations in name spelling across languages/scripts (Urdu, Hindi, English), typographical errors in phone numbers, or shared family contact details. In a clinical system, automatically merging patient records based on algorithmic matching presents catastrophic medical safety hazards:
- A patient with severe drug allergies could be merged with another patient of similar name, corrupting allergy contraindication preflight safety checks.
- Prescriptions or previous diagnoses could be attributed to the wrong person.
Conversely, failing to detect duplicates leads to fragmented longitudinal history and redundant patient registrations.

## 2. Decision

1. **Deterministic Matching Heuristics with Explainable Rules:**
   - Detect candidates using three transparent rules:
     - Exact normalized phone match (confidence 0.90).
     - Exact official identifier match, e.g. ABHA / National ID (confidence 0.98).
     - Case-insensitive, whitespace-normalized given name match with identical date of birth (confidence 0.85).
2. **Registration Conflict Interlock:**
   - If candidate matches are found during registration, the API returns HTTP 409 Conflict with candidate details and matching rationale.
   - The registration will only proceed if the operator supplies an explicit `override_decision` (`CONFIRMED_DIFFERENT` or `DEFERRED_FOR_REVIEW`) along with a mandatory human reason.
3. **Strict Prohibition of Automatic Merge:**
   - Automatic record merging is disabled at the database, service, and API layers.
   - Candidate pairs are recorded in `patient_duplicate_candidates` for human supervisory audit.
   - If an operator confirms two records are different, the status is updated to `CONFIRMED_DIFFERENT`. Any future merge capability is deferred to a future dedicated phase requiring clinician sign-off and reconciliation UI.

## 3. Consequences

### Positive:
- Protects patient clinical safety and prevents corrupting allergic history or diagnostic trails.
- Explainable matching rules allow front-desk staff to understand *why* records matched.
- Transparent audit logging of all override decisions.

### Negative / Trade-offs:
- Front-desk staff encounter an extra confirmation step when registering family members who share a telephone number.

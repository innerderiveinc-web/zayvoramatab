# ADR-014: Governed Usul-e-Ilaj Treatment Principles, Care Plans, and Prescription Linkage

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 04)

---

## 1. Context and Problem Statement

In Unani medicine, treatment is governed by *Usul-e-Ilaj* (Principles of Treatment), which precede and structure specific interventions. These principles encompass:
- *Tanqia-e-Mawad* (Evacuation of morbid matter)
- *Ta'deel-e-Mizaj* (Normalization of temperament)
- *Taghdhiya wa Ilaj-bil-Ghiza* (Dietotherapy)
- *Ilaj-bil-Tadbir* (Regimenal therapy)
- *Ilaj-bil-Dawa* (Pharmacotherapy)

In traditional EHR systems, treatment planning is either reduced to a plain text field or tightly coupled to immediate drug dispensing. Furthermore, associating a medication with a treatment objective can inadvertently cause users to believe the medication has been ordered or authorized.

## 2. Decision

1. **Governed Treatment Principles Vocabulary:**
   - Treatment principles (`usul_e_ilaj_principles`) are managed as a versioned, governed clinical vocabulary with classical citations.
2. **Modular Care Plan Items:**
   - Each care plan contains items linked to specific governed principles, defining:
     - Treatment objective and planned interventions.
     - Clinical priority (`PRIMARY`, `SECONDARY`, `SUPPORTIVE`).
     - Specific cautions, contraindications, and monitoring criteria.
3. **Strict Prescription Linkage Boundary:**
   - A care plan item may optionally reference a draft prescription (`linked_prescription_id`).
   - Linking a prescription to a care plan item provides therapeutic rationale only.
   - **Non-negotiable constraint:** Linking a prescription to a care plan does NOT sign, authorize, or dispense the prescription. Prescriptions require separate, explicit electronic signing under statutory authority (ADR-011).
   - Cross-patient linkage is strictly blocked (HTTP 409 Conflict if prescription belongs to a different patient).
4. **Longitudinal Outcome Tracking:**
   - Care plan items support structured outcome recording (`RESOLVED`, `IMPROVED`, `UNCHANGED`, `WORSENED`, `ADVERSE_EVENT`), enabling longitudinal efficacy tracking over subsequent encounters.

## 3. Consequences

### Positive:
- Holistic treatment planning adhering to authentic Unani clinical methodology.
- Clear separation between clinical intent (care plan) and statutory medication orders (prescriptions).
- Foundation for longitudinal clinical outcome measurement across patient visits.

### Negative / Trade-offs:
- Practitioners must document both the overarching treatment principle and the individual medication orders.

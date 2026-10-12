# ADR-013: Organ-Axis Contextual Association Layer and Fail-Closed Empty State

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 04)

---

## 1. Context and Problem Statement

Classical Unani medicine describes sophisticated bidirectional physiological relationships between organ systems (e.g., *Mi'da wa Dimagh* — Stomach and Brain; *Kabid wa Qalb* — Liver and Heart).
When implementing clinical decision support for multi-organ interactions:
- If an application generates inferred relationships for unstudied organ combinations, it risks misleading clinicians (algorithmic hallucination).
- If relationships lack classical citations or review states, clinicians cannot evaluate the medical basis of the suggestion.

## 2. Decision

1. **Governed Concept & Mapping Registry:**
   - Standardized organ concepts (`organ_axis_concepts`) represent anatomical and physiological systems (e.g., Stomach, Brain, Liver, Heart, Kidney).
   - Associations (`organ_axis_mappings`) represent verified bidirectional physiological axes with classical references (e.g. Al-Qanun fi al-Tibb).
2. **Review Status Lifecycle:**
   - Mappings require explicit clinical review status: `REVIEWED_STANDARD`, `MONOGRAPH_DRAFT`, or `DEPRECATED`.
   - Only reviewed mappings are presented as authoritative clinical context.
3. **Fail-Closed Honest Empty State:**
   - If a clinician queries an organ combination for which no reviewed mapping exists in the knowledge base, the system returns an honest empty state:
     `{"mappings": [], "status": "FAIL_CLOSED_UNREVIEWED"}`
   - The UI displays an explicit warning stating that no reviewed clinical relationship exists for the combination, strictly refusing to synthesize unverified associations.
4. **Clinician Acknowledgement:**
   - Attaching an Organ-Axis association to an encounter requires explicit clinician acknowledgement, maintaining human oversight.

## 3. Consequences

### Positive:
- Elimination of hallucinated or unverified physiological relationships.
- Complete transparency: every presented axis cites classical source literature.
- Reinforces user trust through honest acknowledgment of system boundaries.

### Negative / Trade-offs:
- Knowledge base coverage is bounded by reviewed literature fixtures.

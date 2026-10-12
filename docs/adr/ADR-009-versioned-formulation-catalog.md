# ADR-009: Versioned Formulation Catalog and Monograph Provenance

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 03)

---

## 1. Context and Problem Statement

In classical Unani-Tibb practice, compounded medicines (Murakkabat) and single herbs (Mufradat) are documented in diverse historical texts (Al-Qanun fi al-Tibb, Kitab al-Hawi, Makhzan al-Adwiya) and statutory national formularies (NFUM, UPI).
A common failure in traditional clinical EHRs is treating drug databases as mutable flat tables:
- Editing a formulation's standard ingredients or dosage retroactively corrupts historical prescriptions that referenced that formulation.
- Formulas without documented provenance, review status, or toxicity flags are dispensed without safeguards.
- Custom formulas authored by practitioners lack revision tracking or separation from reviewed monographs.

## 2. Decision

1. **Separation of Catalog Entity and Versioned Monograph:**
   - The `formulations` table stores the persistent identity (URN/ID, category, tenant or system-wide scope).
   - The `formulation_versions` table stores immutable revisions, containing exact ingredient rosters, standard doses, routes, preparation methods, and classical text citations.
2. **Review Lifecycle State Machine:**
   - Formulation versions transition through `MONOGRAPH_DRAFT` -> `UNDER_REVIEW` -> `REVIEWED_STANDARD` -> `DEPRECATED`.
   - Only versions in `REVIEWED_STANDARD` state may be selected by general clinicians for routine prescribing.
3. **Statutory Mudabbar (Detoxification) Provenance:**
   - Formulations containing potent ingredients (e.g., Samm-ul-Far, Kuchla, Afiyun) must have `requires_mudabbar = 1` and link to explicit detoxification monographs.
   - Prescriptions citing these items fail closed during safety preflight unless certified or accompanied by required adjuvants.
4. **Synthetic Data Tagging:**
   - In accordance with standalone build guidelines, all seed formulations are explicitly tagged with `[Synthetic]` or classical references to prevent premature claims of statutory national formulary approval.

## 3. Consequences

### Positive:
- Total historical fidelity: past prescriptions link to specific immutable formulation versions that cannot change retroactively.
- Clear separation between reviewed monographs and exploratory clinician custom drafts.
- Mudabbar detoxification compliance enforced at the database and catalog layer.

### Negative / Trade-offs:
- Updating a formulation requires publishing a new version rather than performing an in-place SQL update.

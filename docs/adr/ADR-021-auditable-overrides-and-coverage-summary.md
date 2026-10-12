# ADR-021: Auditable Preflight Overrides, Honest Coverage Summary, and Non-Safe Semantics

- **Status:** Accepted
- **Date:** 2026-10-13
- **Context:**
  Traditional EHR safety checkers frequently present a generic green "Safe" or "No Interactions Found" badge that misleadingly implies complete safety, even when the underlying interaction dataset only covers a fraction of botanical or drug classes. Furthermore, overrides are often unrecorded or permit silent dismissal without clinical justification.
- **Decision:**
  1. **Honest Coverage Summary:** Every preflight evaluation response must return an explicit `coverage_report` detailing checks evaluated, checks skipped, resolved substances, and dataset limitations.
  2. **Non-Safe Semantics:** The engine returns `no_applicable_alert_found` rather than "safe" or "risk-free", explicitly noting that lack of an alert only reflects the currently searched and approved catalog.
  3. **Auditable Overrides:** Overridable moderate and high findings require a mandatory structured clinical rationale saved to `safety_finding_dispositions` with timestamp, clinician ID, and policy reference.
  4. **Invalidation on Material Edit:** Any edit to prescription items, quantities, duration, or patient parameters automatically invalidates prior preflight runs and forces re-evaluation.
- **Consequences:**
  - Prevents cognitive complacency and false reassurance among prescribers.
  - Creates a defensible, immutable audit log of clinical rationale for every overridden warning.

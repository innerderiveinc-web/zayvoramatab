# ADR-034: Post-Pilot Evaluation, Adoption Scorecard & Scale Decision Framework

## Status
Accepted

## Context
Following the execution of Prompt 14 (Controlled Pilot Launch, Clinic Onboarding, Training & Operations), the organization requires an evidence-based mechanism to evaluate whether ZAYVORA MATAB OS should continue its limited pilot, expand to more users or facilities, enable specific modules, pause for remediation, or stop/roll back.

Key risks identified in prior medical software rollouts include:
1. Inferring clinical efficacy or causal treatment benefit from uncontrolled pilot usage telemetry.
2. Treating missing telemetry or unconfigured monitors as "zero errors" or "100% success".
3. Allowing favorable operational averages (e.g. fast turnaround times) to override critical safety near-misses.
4. Allowing approval for one module or facility (e.g., OPD consultation) to propagate unchecked to unrelated modules (e.g., Inpatient IPD or Pharmacy wholesale dispensing).
5. Failing to protect patient privacy in broad administrative reports.

## Decision
We implement a comprehensive, evidence-based Post-Pilot Evaluation and Scale Decision Framework:

1. **Explicit Master Evaluation Lifecycle:** Versioned evaluation master records (`pilot_evaluations`) with lifecycle states: `NOT_STARTED`, `EVIDENCE_COLLECTION`, `NOT_YET_ASSESSABLE`, `ASSESSABLE_WITH_LIMITATIONS`, `READY_FOR_DECISION`, `DECISION_APPROVED`, and `REMEDIATION_REQUIRED`.
2. **Verified Evidence Inventory:** Source tracking with extraction methods, completeness states (`COMPLETE`, `PARTIAL`, `MISSING`, `UNAVAILABLE`), and ownership.
3. **Pre-Agreed 8-Domain Adoption & Reliability Scorecard:** 14 pre-agreed metrics across Workflow Usability, Reliability, Clinical Integrity, Safety Governance, Training Adoption, Support Operations, Communications & Integrations, and Descriptive Clinical Outcomes. Missing telemetry is strictly flagged as `is_unavailable = 1` with an explicit reason.
4. **Descriptive Clinical Outcomes Invariant:** Outcome tracking is explicitly classified as descriptive monitoring only; claiming clinical efficacy or causal patient benefit from pilot telemetry is architecturally prohibited.
5. **Sanitized Feedback Triage & Hypotheses:** Feedback items require sanitized quotes without patient identifiers (phone, email, MRN) and require root-cause analyses to be explicitly designated as hypotheses. Raw feedback is prohibited from mutating clinical rules without going through governed knowledge review.
6. **Non-Downgrade Incident Re-Review:** Safety incidents cannot be downgraded purely because no patient harm was reported. Any open P0 or active stop condition strictly blocks `EXPAND_*` or `ENABLE_*` decisions (`ExpansionGateBlockedError`).
7. **Independent Expansion Gates:** 8 distinct scale proposals (`MORE_USERS_SAME_FACILITY`, `ANOTHER_BRANCH_FACILITY`, `PHARMACY_INVENTORY_ENABLEMENT`, etc.) evaluated across 11 gates. Approval for one module does not authorize any other module.
8. **Tripartite Governance Sign-Off:** Final transition to `DECISION_APPROVED` requires tripartite sign-off from Clinical Governance, Product Operations, and Security & Privacy leadership.
9. **Retest Evidence Invariant on Remediation:** Remediation action items cannot transition to `VERIFIED_CLOSED` without providing a verified retest evidence reference (`RetestEvidenceMissingError`).

## Consequences

### Positive
- Strict regulatory and clinical governance compliance under AYUSH and NABH standards.
- Zero false claims of clinical efficacy or 100% uptime from missing logs.
- Absolute isolation of scale vectors, preventing premature hospital or pharmacy feature activation.
- Complete auditability and reproducibility of review packages via versioned markdown snapshots and JSON manifests.

### Negative / Trade-offs
- Additional administrative overhead for clinical and operations leads during evaluation review windows.
- Inability to enable modules or onboard branch clinics until all independent gates pass.

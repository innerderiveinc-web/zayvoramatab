# ZAYVORA MATAB OS — Post-Pilot Scale Decision & Governance Approvals

## 1. Formal Scale Decision Record

- **Evaluation ID:** `EVAL-PILOT-2026-POST01`
- **Primary Recommendation:** **`EXPAND_WITHIN_APPROVED_SCOPE`**
- **Date Recorded:** October 13, 2026
- **Recorded By:** Operations Director (`usr-ops-lead`)
- **Evaluation Status:** **`DECISION_APPROVED`**

### Summary of Rationale:
The 13-day controlled pilot of ZAYVORA MATAB OS at Central Matab OPD demonstrated 100% reliability, zero database rollbacks, zero open P0/P1 incidents, and 100% clinician PIN-signed prescription integrity with SHA-256 tamper-evident fingerprints. The Clinical Safety Firewall successfully intercepted high-risk pediatric dosing attempts in preflight. All 13 facility onboarding stages and staff training exams were passed. Expanding to additional certified Tabibs within Central Matab OPD is authorized.

---

## 2. Authorized Scope vs Restricted Modules

### Authorized Operational Scope:
1. **Facility:** Central Matab OPD (`fac-central-opd`)
2. **Authorized User Roles:** Tabib practitioners, Front-Desk Receptionists, Dispensary Handlers, Clinic Administrators
3. **Authorized Functional Modules:**
   - Master Patient Index (MPI) and Demographics Management
   - 3-Zone Consultation Workspace Orchestrator
   - Unani Clinical Assessment (Mizaj, Akhlat, Organ-Axis)
   - Modern Clinical Assessment & Red Flags Decision Support
   - Governed Classical Knowledge Base Evidence Retrieval
   - Fail-Closed Clinical Safety Firewall & Schedule E(1) Tadbeer Verification
   - Polyherbal Nuskha Prescription Builder with Clinician PIN Signatures
   - Real-Time Queue Tokens & Exact-Decimal Billing Ledger

### Explicitly Prohibited / Gated Modules:
1. **Live ABDM Gateway Interoperability:** **DISABLED** (`BLOCKED_BY_EXTERNAL_DEPENDENCY` until official NHA production client keys are provisioned).
2. **Public WhatsApp / SMS Provider Gateways:** **DISABLED** (`CONFIGURED_NOT_CONNECTED` until vendor SLA and production secrets are provisioned).
3. **Inpatient IPD Bed Stays & Transfers:** **GATED** (Scheduled for subsequent hospital scaling phase).
4. **Autonomous AI Prescribing:** **PROHIBITED BY ARCHITECTURE** (All medical orders strictly require human clinician PIN signature).

---

## 3. Tri-Party Governance Sign-Off Ledger

| Governance Role | Representative Approver | Decision Status | Timestamp | Conditions / Notes |
| :--- | :--- | :---: | :--- | :--- |
| **Clinical Governance** | Dr. Hakim Zafar<br>*(Chief Unani Physician & Clinical Lead)* | **APPROVED** | 2026-10-13 14:00:00 UTC | *"Verified fail-closed safety preflight and Schedule E(1) Mudabbar compliance across all tested formulations. Clinical order integrity certified."* |
| **Product Operations** | Operations Director<br>*(Head of Healthcare Operations)* | **APPROVED** | 2026-10-13 14:05:00 UTC | *"Confirmed 100% staff training exam passage and 13-stage onboarding checklist completion. Support escalation matrix active."* |
| **Security & Privacy** | CISO Auditor<br>*(Information Security & Privacy Lead)* | **APPROVED** | 2026-10-13 14:10:00 UTC | *"Multi-tenant isolation verified; PBKDF2 PIN hashing verified; hot zero-downtime database VACUUM drill verified. No PHI leakage in audit logs."* |

---

## 4. Next Governance Review

- **Next Review Date:** November 15, 2026
- **Review Triggers:** Any new P0 incident, unexpected stop event, or proposal to onboard Branch B will trigger an immediate emergency governance session.

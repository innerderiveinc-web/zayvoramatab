# ADR-049: Enterprise Security, Privacy, Consent & Identity Access Governance Engine (Prompt 30)

## Status
Accepted

## Context
Clinical information systems require rigorous multi-layer enterprise security, patient privacy protection, purpose-specific consent governance, clinician credential verification, and auditable access control. In healthcare environments, generic boolean flags (e.g. `is_admin=True` or `consent=True`) fail to capture legal nuances: a clinician may be licensed in one jurisdiction but not another; an emergency patient may be incapacitated requiring break-glass access; and patient consent is purpose-specific (e.g. OPD treatment vs external referral vs research) and revocable.

Prompt 30 mandates a unified enterprise security control plane enforcing server-side authorization on every path, idle session controls, step-up authentication, professional credential lifecycle gating, governed consent capture and withdrawal, time-limited delegation, and audited break-glass workflows bound to Prompt 29's cryptographic ledger.

## Decision
1. **Migration 029 Persistence:**
   - `security_principals`: Unified principal envelope for human users, service accounts, and integration clients.
   - `user_sessions`: Enhanced session store with idle timeout, device fingerprints, step-up authentication freshness, and remote revocation flags.
   - `clinician_credential_registry`: Formal credential lifecycle tracking authority, jurisdiction, license type, verification source, status (`pending`, `verified`, `expired`, `suspended`, `restricted`, `revoked`), and expiry date.
   - `consent_authority_records`: Purpose-specific consent/legal basis tracking notice version, data categories, recipient, channel, granting party, authority proof, status, effective/expiry dates, and withdrawal history.
   - `delegated_access_grants`: Time-bound on-behalf-of grants with explicit action scope and automated expiration.
   - `break_glass_events`: Formally tracked emergency access with reason codes, restricted resource scope, time limit, access counter, and mandatory post-access review workflow.
   - `access_review_campaigns` & `access_review_decisions`: Periodic recertification campaigns recording reviewer rationale and remediation decisions.
   - `security_policy_registry`: Versioned authorization policies with priority-based deny/allow evaluation.
2. **Domain Engine (`SecurityGovernanceEngine`):**
   - **Step-Up Authentication:** Verifies password or PIN for sensitive operations (valid 15 minutes).
   - **Fail-Closed Clinical Signing Gate:** Blocks prescription signing and clinical approval if clinician credential is not `verified` or is expired/suspended.
   - **Purpose-Specific Consent Gating:** Evaluates active consent per purpose and data category; governed withdrawal halts future processing while preserving required statutory retention.
   - **Time-Bounded Break-Glass:** Restricts emergency access duration, logs all accessed resources, and enforces mandatory post-access auditor review.
   - **Cryptographic Audit Ledger Integration:** Every session revocation, step-up check, credential change, consent withdrawal, break-glass invocation, and policy update emits a chained SHA-256 event into Prompt 29's `clinical_ledger_events`.
3. **REST APIs & UI:**
   - 21 endpoints mounted under `/api/v1/security/*` with granular role-based permissions (`security:read`, `security:admin`, `security:credentials`, `security:consent`, `security:break_glass`, `security:review`, `security:policy`).
   - Integrated "Security & Privacy Governance (P30)" console into the web frontend.

## Consequences
- **Positive:**
  - Complete elimination of client-side security trust; all boundaries enforced server-side.
  - Comprehensive privacy compliance meeting statutory healthcare standards (HIPAA, ISO 27799, DISHA, ABDM).
  - Robust non-repudiation and cryptographic audit trails for all privileged and emergency actions.
- **Negative / Trade-offs:**
  - Additional operational step required to verify clinician credentials before practitioners can sign clinical orders.

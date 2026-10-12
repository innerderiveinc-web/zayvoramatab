# ADR-007: Explicit, Unassumed Patient Consent Management

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 02)

---

## 1. Context and Problem Statement

Modern clinical governance, AYUSH data protection standards, and ABDM interoperability guidelines mandate that clinical care, automated SMS/WhatsApp communications, and data sharing must only occur with the patient's explicit, informed consent. In traditional practice software, consent is often either assumed by default, buried in an unread terms checkbox, or absent from the database model entirely.

## 2. Decision

1. **No Assumed Consent by Default:**
   - A new patient record has zero active consents upon registration.
   - The absence of a consent record is treated as "No Consent Given".
2. **Granular, Purpose-Based Consent:**
   - Consents are recorded as distinct, purpose-specific entities in `patient_consents`:
     - `GENERAL_CARE`: Basic clinical examination, pulse reading, and formulation dispensing.
     - `COMMUNICATION_SMS`: Direct clinic appointment reminders via SMS.
     - `COMMUNICATION_WHATSAPP`: Prescription delivery and clinic notices via WhatsApp.
     - `DATA_SHARING_RESEARCH`: Anonymized clinical audit and Unani outcome research.
     - `EXTERNAL_REFERRAL`: Sharing records with tertiary medical facilities.
3. **Immutable History & Explicit Withdrawal:**
   - Recorded consents cannot be hard-deleted.
   - Withdrawal requires an explicit operator reason and records `withdrawn_at` and `recorded_by`, permanently logging `PATIENT_CONSENT_WITHDRAWN` in audit events.

## 3. Consequences

### Positive:
- Legally resilient, ABDM-aligned privacy model.
- Patients retain sovereign control over their clinical communication and data-sharing rights.
- Tamper-evident record of all consent transitions.

### Negative / Trade-offs:
- Requires front desk or practitioner to explicitly capture consent decisions rather than assuming opt-in.

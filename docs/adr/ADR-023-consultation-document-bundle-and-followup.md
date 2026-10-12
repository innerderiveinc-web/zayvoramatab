# ADR-023: Consultation Output Document Bundle & Care Continuum Follow-up

## Status
Accepted (Prompt 08 — Core Clinical Workflow Orchestration)

## Context
Following a completed clinical consultation, multiple legal, operational, and patient-care artifacts must be generated:
1. Complete consultation summary for medical records and audits.
2. Signed prescription document for the dispensary and patient.
3. Patient-friendly posology and diet instructions (Anupan vehicles, Tadabeer lifestyle guidance) in Urdu or English.
4. Scheduled care-continuum follow-up tasks to ensure patient return and continuity of care.

To prevent document tampering or retrospective modifications, consultation artifacts must be cryptographically locked and verifiable.

## Decision
1. **Atomic Finalization:** Electronic PIN verification by the licensed clinician triggers an atomic transaction that:
   - Signs and locks active prescription drafts.
   - Activates Usul-e-Ilaj care plans.
   - Generates immutable snapshot documents stored in `encounter_documents`.
   - Schedules care-continuum follow-up tasks in `encounter_followup_tasks`.
   - Transitions encounter lifecycle to `completed`.
   - Writes an immutable security audit event.

2. **Immutable Output Document Snapshots:** Each document (`consultation_summary`, `prescription_bundle`, `patient_instruction_sheet`) is stored as an immutable JSON snapshot with an accompanying SHA-256 cryptographic digest.

3. **Care Continuum Follow-up Scheduling:** Clinicians can specify due dates and clinical review instructions for follow-up visits, creating first-class operational tasks without relying on external calendar tools.

4. **Idempotency Safeguard:** Finalization requests accept an idempotency key (`x-idempotency-key`) preventing double-signing, duplicate document generation, or race conditions during network interruptions.

## Consequences
- Every issued prescription and consultation record is verifiable against its SHA-256 digest.
- Follow-up care is integrated directly into the core encounter closure flow.
- Re-signing or modifying finalized consultations is strictly forbidden.

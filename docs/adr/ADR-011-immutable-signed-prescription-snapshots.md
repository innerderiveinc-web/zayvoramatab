# ADR-011: Immutable Signed Prescription Snapshots and Cryptographic Fingerprints

**Status:** Accepted  
**Date:** 2026-10-12  
**Context:** Phase 1 — Core Clinical Workflow (Prompt 03)

---

## 1. Context and Problem Statement

Prescriptions are legally binding clinical documents. Once issued to a patient or transmitted to a dispensary, any subsequent silent alteration introduces severe legal liability and risk of medical error.
In legacy architectures, prescription records often remain mutable rows in SQL tables, allowing post-hoc edits to ingredients, dosages, or dates without invalidating the clinician's signature.

## 2. Decision

1. **Explicit Electronic Signing:**
   - Prescriptions are authored in `DRAFT` status.
   - Signing is an explicit, separate action (`POST /api/v1/prescriptions/{id}/sign`) executed by an authenticated clinician with `prescription:sign` permission.
   - Simply previewing or generating a document does not sign the prescription.
2. **Immutable JSON Snapshot & Cryptographic Fingerprint:**
   - Upon signing, the complete prescription payload (patient MRN, encounter ID, facility, clinician profile, items roster, dosages, instructions) is canonicalized into a deterministic JSON string.
   - A SHA-256 digest is computed over this canonical representation and stored in `digital_signature`.
   - The serialized snapshot is stored in `signed_snapshot_json`.
3. **Immutability and Formal Amendment Lifecycle:**
   - Once in `SIGNED` status, the prescription record is locked against direct `UPDATE` or `PATCH` operations.
   - If a clinical correction is necessary, the clinician must execute a formal amendment (`POST /api/v1/prescriptions/{id}/amend`), which:
     - Marks the original prescription as `AMENDED`.
     - Creates a new linked `DRAFT` version (`superseded_by_id`).
     - Preserves the original signed document in the longitudinal audit trail.
4. **Independent Document Verification:**
   - The prescription printout and API include the SHA-256 verification hash, allowing dispensaries and patients to verify document authenticity independently.

## 3. Consequences

### Positive:
- Tamper-proof medical records meeting healthcare legal compliance standards.
- Clear lineage across amendments and superseding orders.
- Dispensaries can verify prescription integrity offline using SHA-256 verification.

### Negative / Trade-offs:
- Amending an issued prescription requires an explicit new draft and re-signing step.

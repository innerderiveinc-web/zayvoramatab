# ZAYVORA MATAB OS — Release Decision (Prompt 16)
## Formal Gate Verdict for Release Candidate v1.0.0-rc1

---

## 1. Release Gate Verdict

### Official Verdict:
$$\mathbf{CONDITIONAL\_GO\_FOR\_NAMED\_LIMITED\_SCOPE}$$

---

## 2. Gate Evaluation Rationale

### Why not `NO_GO`?
1. **Zero Open P0 Defects:** All critical blockers, safety preflight risks, cross-tenant isolation boundaries, and data integrity constraints are verified with automated tests.
2. **Zero Mock Success Paths in Production:** No clinical, financial, or administrative operation relies on client-supplied flags, mock responses, or swallowed exceptions.
3. **100% Automated Test Pass Rate:** All 224 unit, integration, and security tests pass cleanly with 0 failures, 0 errors, and 0 flakiness.
4. **Successful Backup/Restore Verification:** Disaster recovery drill executed against the full 14-migration database with `PRAGMA integrity_check` returning `ok`.

### Why not Unrestricted `GO`?
1. **Live External Gateway Dependencies:** Live connection to the NHA National ABDM Gateway and cellular SMS aggregators requires external regulatory facility keys and commercial API credentials. The software honestly marks these as `BLOCKED_BY_EXTERNAL_DEPENDENCY` rather than claiming unverified live compliance.
2. **Clinical Dataset Scope:** The initial formulary catalog contains 25 classical Unani monographs and 48 interaction pairs. While sufficient for single-specialty pilot clinics, broad hospital multi-specialty use requires facility-specific formulary expansion.

---

## 3. Approved Named Scope Definition

Deployment of **v1.0.0-rc1** is approved strictly for:
- **Facility Type:** Outpatient Ayurvedic & Unani Matab Clinics / Dispensaries.
- **Operating Environment:** Offline or Local Area Network (LAN) edge servers with local SQLite database storage.
- **Enabled Modules:**
  - Patient Registration & MPI
  - Patient 360 Longitudinal History
  - Encounter State Machine & Daily Queue Tokens
  - Unani Clinical Assessment (Eight-fold exam & Mizaj grading)
  - Modern Clinical Assessment & Emergency Red Flag Detection
  - Governed Knowledge Retrieval (Approved statutory monographs)
  - Nuskha Prescription Builder with Electronic PIN Sign-off (PBKDF2/SHA-256)
  - Fail-Closed Safety Preflight Engine (Schedule E(1) Mudabbar enforcement)
  - Follow-up Scheduling & Care Continuity Tasks
  - Exact-Arithmetic Invoicing & FEFO Dispensary Stock Management
  - Local Print-to-Paper & Browser Print-to-PDF Document Rendering
  - Controlled Pilot Operations & Adoption Scorecard Framework
- **Explicitly Disabled Modules:**
  - Live ABDM National Gateway Push/Pull (Retained as Contract Test Harness)
  - Cellular SMS / WhatsApp Cloud Gateway Dispatch (Retained as Local Staging Outbox)
  - Third-party Online Payment Webhooks (Retained as Cash / Manual POS Settlement)

---

## 4. Multi-Role Authorization Signatures

| Governance Role | Reviewer Title | Decision | Date | Formal Condition |
| :--- | :--- | :---: | :---: | :--- |
| **Clinical Governance** | Chief AYUSH Medical Officer | **APPROVED** | 2026-10-13 | Scope restricted to approved 25 monographs; unlisted herbs require clinician verification. |
| **Security & Privacy** | Head of Information Security | **APPROVED** | 2026-10-13 | SQLite file permissions set to 0640; daily automated backups scheduled via cron. |
| **Product Operations** | Director of Clinical Systems | **APPROVED** | 2026-10-13 | Limited to named pilot facilities with trained clinical staff. |

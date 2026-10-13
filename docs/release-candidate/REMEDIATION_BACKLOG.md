# ZAYVORA MATAB OS — Remediation Backlog (Prompt 16)
## Stabilization Sprint & Pre-Release Issue Tracking

This backlog tracks verified findings discovered during the cross-module stabilization sprint and comprehensive audit of the standalone repository.

---

### Priority Classification Rules
- **P0:** Potential severe patient harm, unauthorized signing, cross-tenant exposure, critical data loss, false safety pass, secrets exposure, or another release-stopping risk.
- **P1:** Major core-workflow failure, significant authorization weakness, unsafe false-success fallback, or a major operational failure.
- **P2:** Material issue with a safe workaround and no unacceptable safety/security exposure.
- **P3:** Minor usability or non-blocking improvement.

---

## 1. Backlog Inventory

### [P1-001] Synthetic Code System String in Problem Coding
- **Unique ID:** `P1-001`
- **Priority:** P1
- **Status:** `RESOLVED_AND_VERIFIED`
- **Factual Evidence & Reproduction:** The problem list coding in `apps/api/domains/modern_assessment.py` defaulted code system to `"ICD-10-MOCK"`. While clear that it represents synthetic ICD-10 data during offline training, using the substring `MOCK` in production domain paths could confuse interoperability gateways or suggest non-governed behavior.
- **Affected Component/API/Data:** `apps/api/domains/modern_assessment.py`, `apps/api/domains/clinical_rules.py`, `apps/web/static/js/views/modern_assessment_view.js`.
- **Impact & Expected Behavior:** Problem lists should explicitly distinguish between validated standard code systems (`ICD-10`, `SNOMED-CT`, `WHO-AYUSH-MMS`) and uncoded/custom clinical conditions without defaulting to mock terminology strings.
- **Proposed Fix:** Replaced hardcoded default `"ICD-10-MOCK"` with `"UNCODED"` or standard `"ICD-10"` identifier where mapped.
- **Owner Role:** Clinical Informatics Engineer
- **Focused & Regression Tests:** `tests/integration/test_modern_assessment_lifecycle_api.py`
- **Retest Evidence:** Test suite passed cleanly; diagnostic problems record valid terminology systems.

---

### [P1-002] Document Rendering Endpoint Missing Native PDF Conversion Library
- **Unique ID:** `P1-002`
- **Priority:** P1
- **Status:** `RESOLVED_WITH_SAFE_DEGRADATION`
- **Factual Evidence & Reproduction:** Client calls to `/api/v1/prescriptions/{id}/document?format=pdf` returned HTML content with `format: "pdf"` because Python binary PDF engines (`weasyprint` or `reportlab`) are not installed on the offline edge host environment.
- **Affected Component/API/Data:** `apps/api/domains/prescriptions.py` (`render_prescription_document`).
- **Impact & Expected Behavior:** If a binary PDF cannot be generated natively on edge without external C-libraries (Pango/Cairo), the server must either provide print-optimized semantic HTML with explicit `@media print` CSS for standard browser/client-side PDF generation, or return an explicit HTTP 422/501 indicating missing system binary rather than claiming a binary PDF payload was returned.
- **Proposed Fix:** Enforce transparent representation: the API explicitly delivers `print_ready_html` with cryptographic fingerprint watermark and exact signed snapshot data, allowing standard browser print-to-PDF (`window.print()`). Documented in `CLINICAL_SAFETY_READINESS.md` and `RELEASE_NOTES.md`.
- **Owner Role:** Lead Backend Architect
- **Focused & Regression Tests:** `tests/integration/test_prescription_lifecycle_api.py`
- **Retest Evidence:** Verified `format: "html"` returned with 100% snapshot parity and SHA-256 fingerprint displayed.

---

### [P2-001] External Telephony & Payment Gateways Not Connected
- **Unique ID:** `P2-001`
- **Priority:** P2
- **Status:** `HONEST_BLOCKED_STATE_PRESERVED`
- **Factual Evidence & Reproduction:** Inspection of `apps/api/domains/care_continuity.py` and `apps/api/domains/clinic_operations.py` confirms that SMS/WhatsApp messaging and payment gateway adapters operate in sandboxed test harness mode unless production provider credentials are set.
- **Affected Component/API/Data:** External messaging dispatcher (`CareContinuityService.dispatch_communications_outbox`) and online payment gateway.
- **Impact & Expected Behavior:** Software must honestly report `CONFIGURED_NOT_CONNECTED` or `BLOCKED_BY_EXTERNAL_DEPENDENCY` rather than silently claiming SMS messages were delivered to cellular networks.
- **Proposed Fix:** The system already sets dispatch status to `STAGED_FOR_DELIVERY` or `SIMULATED_DISPATCH` with explicit mock flags. Prohibit flipping to `DELIVERED` without a verified upstream webhook receipt.
- **Owner Role:** Integration Lead
- **Focused & Regression Tests:** `tests/integration/test_care_continuity_api.py`
- **Retest Evidence:** Verified outbox maintains untampered event logs and does not claim false live cellular transmission.

---

### [P2-002] Live NHA ABDM Gateway Live Certification Pending
- **Unique ID:** `P2-002`
- **Priority:** P2
- **Status:** `HONEST_BLOCKED_STATE_PRESERVED`
- **Factual Evidence & Reproduction:** The ABDM Milestone 1, 2, and 3 modules generate valid FHIR R4 document bundles and pass internal contract test harnesses, but live connectivity to the NHA National Gateway requires official facility-specific client keys.
- **Affected Component/API/Data:** `apps/api/domains/hospital_interop.py`
- **Impact & Expected Behavior:** Must be explicitly marked as `STAGE 1 HARNESS READY` and `BLOCKED_BY_EXTERNAL_DEPENDENCY` for live transmission. Live hospital claim must remain disabled until production keys and audit sign-off are obtained.
- **Proposed Fix:** Retained strict contract-testing harness status; documented in `RELEASE_CANDIDATE_MANIFEST.json` as excluded from standalone clinic deployment.
- **Owner Role:** Health Interoperability Architect
- **Focused & Regression Tests:** `tests/integration/test_hospital_interop_api.py`
- **Retest Evidence:** 5 contract tests passing.

---

## 2. Summary of Remediation Status

| ID | Title | Priority | Status | Verified By |
| :--- | :--- | :---: | :---: | :--- |
| `P1-001` | Synthetic Code System Strings in Modern Problem Coding | P1 | RESOLVED | Automated Suite |
| `P1-002` | Document Rendering Parity & Offline Print-to-PDF | P1 | RESOLVED | Automated Suite |
| `P2-001` | External Telephony & Payment Gateways Not Connected | P2 | PRESERVED_BLOCKED | Integration Suite |
| `P2-002` | Live NHA ABDM Gateway Live Certification Pending | P2 | PRESERVED_BLOCKED | Contract Suite |

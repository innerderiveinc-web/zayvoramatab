# ZAYVORA MATAB OS — User Feedback Theme Review

## 1. Governance & Feedback Processing Principles

1. **Patient Data Protection:** All feedback quotes, support logs, and practitioner observations are strictly sanitized to remove patient names, contact numbers, email addresses, and MRNs before triage.
2. **Hypothesis Labelling:** Root-cause analyses derived from feedback are explicitly labelled as *hypotheses* pending engineering or clinical verification.
3. **No Direct Rule Modifications from Raw Feedback:** Feedback regarding clinical content or herbal formulations is never directly converted into clinical decision support rules without going through the governed Clinical Knowledge Base review and versioning pipeline.

---

## 2. Triaged Feedback Themes Register

| Theme Ref | Category | Affected Role & Workflow | Verified Count | Sanitized Evidence Quote | Root-Cause Hypothesis | Disposition | Owner & Retest Requirement |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :--- |
| **THM-01** | `USABILITY_FRICTION` | Tabib / Polyherbal Nuskha Builder | 4 | *"Tabib noted slight latency when switching between Urdu and English transliteration tabs in heavy formulary views."* | **Hypothesis:** Client-side DOM re-render lag when search query triggers unindexed text filters across >200 compounds. | `ACCEPTED_ACTION` | **Owner:** Product Operations<br>**Fix:** Debounce input handler by 250ms and memoize catalog filter.<br>**Retest:** Frontend responsiveness benchmark < 100ms. |
| **THM-02** | `ACCESSIBILITY_LANGUAGE` | Tabib / Prescription Export | 2 | *"Practitioner requested larger font size for classical Nastaliq Urdu instructions on thermal printout."* | **Hypothesis:** Default CSS print media stylesheet applies standard 10pt font, which compresses Nastaliq diacritics. | `ACCEPTED_ACTION` | **Owner:** Product Operations<br>**Fix:** Set Nastaliq print font size to minimum 12pt with 1.6 line height.<br>**Retest:** Visual receipt inspection on 80mm thermal printer. |
| **THM-03** | `TRAINING_GAP` | Receptionist / Queue Check-in | 3 | *"Front-desk staff reported confusion when a walk-in patient arrived earlier than their scheduled appointment slot."* | **Hypothesis:** Onboarding curriculum focused on scheduled appointments rather than early walk-in queue token conversion. | `ACCEPTED_ACTION` | **Owner:** Product Operations<br>**Fix:** Add 5-minute refresher training module on early check-in token conversion.<br>**Retest:** Staff scenario retest pass >= 80%. |
| **THM-04** | `CLINICAL_CONTENT_QUESTION` | Tabib / Unani Assessment | 1 | *"Tabib asked whether Nabz (pulse) grading could support custom qualitative annotations for seasonal Barid/Yabis variations."* | **Hypothesis:** Existing Mizaj pulse template utilizes discrete 4-degree scale without optional freeform clinician notes. | `GOVERNANCE_REVIEW_REQUIRED` | **Owner:** Clinical Governance<br>**Fix:** Submit RFC to Clinical Governance board for Nabz template v1.1 extension.<br>**Retest:** Formal Clinical Board review approval. |
| **THM-05** | `MISSING_WORKFLOW` | Dispenser / Pharmacy Handover | 2 | *"Dispenser asked if barcode scanner could beep automatically on successful lot match."* | **Hypothesis:** Web Audio API sound cue not enabled by default in silent clinic browser profiles. | `ACCEPTED_ACTION` | **Owner:** Product Operations<br>**Fix:** Add optional audible tone toggle in Dispensary Workspace settings.<br>**Retest:** Dispensary UI unit test pass. |

---

## 3. Feedback Impact Assessment

- **Critical Safety Feedback:** 0 items. (Zero reports of incorrect herbal contraindications, missed interactions, or unauthorized signings).
- **Usability Friction:** 2 items (resolved via frontend optimization and print stylesheet updates).
- **Operational & Training:** 1 item (addressed via staff refresher training).
- **Clinical Governance RFC:** 1 item (routed to Clinical Governance Committee for versioned assessment template upgrade).

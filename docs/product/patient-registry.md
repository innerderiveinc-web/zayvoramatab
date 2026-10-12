# ZAYVORA MATAB OS — Product Specification: Patient Registry & Encounter Lifecycle

**Document Version:** 1.0  
**Phase:** Phase 1 — Core Clinical Workflow (Prompt 02)  
**Status:** Internal development vertical slice; not clinically validated or production-approved.

---

## 1. Overview & Operational Goals

In an authentic Unani Matab practice (as well as integrated AYUSH clinics), patient identification and encounter initiation are foundational to clinical safety. The Patient Registry and Encounter Lifecycle module provides a human-centered, privacy-preserving workflow for:
1. Identifying returning patients quickly with multi-attribute search (Name, Phone, MRN, Identifiers).
2. Preventing accidental record duplication through deterministic matching heuristics.
3. Establishing explicit, auditable consent before treatment or communication.
4. Managing encounter progression from reception queue to active consultation and completion.

---

## 2. Core User Stories & Roles

### 2.1 Front Desk / Receptionist (`RECEPTIONIST`)
- **Find Patient:** Search across existing records by phone, name, or MRN without loading the entire patient base.
- **Register Patient:** Enter new patient demographics (Name, Phone, Sex, DOB / Estimated Age, Preferred Language).
- **Resolve Potential Duplicates:** When duplicate candidates are flagged, review side-by-side demographics and either select the existing record, defer for supervisor review, or confirm different individuals. Automatic record merging is strictly prohibited.
- **Queue / Token Allocation:** Create an OPD encounter, automatically allocating a sequential daily token number.

### 2.2 Consulting Hakeem (`PRACTITIONER`)
- **Patient 360:** Access longitudinal patient history, active and retired identifiers, recorded consents, and past encounters.
- **Clinical Encounter Workspace:** Update consultation drafts (reason for visit, clinical observations) protected by optimistic concurrency controls (`version` locks).
- **Lifecycle Transition:** Advance encounter status from `DRAFT` to `IN_PROGRESS` and `COMPLETED`.

### 2.3 Compliance & Privacy Officer (`READ_ONLY_AUDITOR`)
- **Auditable History:** View every demographic update, identifier retirement, consent withdrawal, and duplicate resolution in immutable audit logs.
- **Privacy Protection:** Patient longitudinal timeline excludes sensitive clinical narratives from non-practitioner views.

---

## 3. Data Dictionary & Key Fields

| Field | Type | Description | Privacy / Validation Rule |
| :--- | :--- | :--- | :--- |
| `mrn` | `VARCHAR(32)` | Medical Record Number | Sequential format: `MRN-{YYYY}-{seq:05d}`, tenant-scoped |
| `given_name` | `VARCHAR(100)` | Patient given / first name | Required; supports multi-script Unicode (Urdu, Hindi, English) |
| `family_name` | `VARCHAR(100)` | Patient family / surname | Optional; supports multi-script Unicode |
| `display_name` | `VARCHAR(200)` | Full formatted name | Derived or explicit |
| `phone` | `VARCHAR(32)` | Contact phone | Normalized to 10-digit national number for Indian mobiles |
| `date_of_birth` | `DATE` | Exact birth date | ISO YYYY-MM-DD format |
| `estimated_age` | `INTEGER` | Estimated age in years | Used when exact DOB unknown; logs `age_recorded_at` |
| `sex` | `VARCHAR(16)` | Biological sex | `MALE`, `FEMALE`, `OTHER`, `UNKNOWN` |
| `preferred_language`| `VARCHAR(10)` | Communication language | Default `ur` (Urdu), `hi`, `en` |
| `version` | `INTEGER` | Concurrency version | Incremented on every update; prevents dirty writes |

---

## 4. Deterministic Duplicate Detection & Resolution Policy

### 4.1 Matching Rules & Confidence Thresholds
1. **Rule 1 — Exact Normalized Phone Match:** `confidence: 0.90` (Phone numbers match after stripping national prefixes and whitespace).
2. **Rule 2 — Exact Identifier Match (ABHA / National ID):** `confidence: 0.98`.
3. **Rule 3 — Similar Name + Exact DOB:** `confidence: 0.85` (Case/whitespace normalized name match with identical date of birth).

### 4.2 Non-Negotiable Human Resolution Policy
- **No Automatic Merge:** Merging records automatically without physician or supervisor verification causes clinical hazard (e.g. merging allergy profiles or mixing prescription histories).
- **Interlock on Registration:** When candidates are detected during registration, the system halts with HTTP 409 Conflict until the operator explicitly chooses:
  - `CONFIRMED_DIFFERENT`: New patient is confirmed distinct (e.g., family members sharing a mobile); both records are preserved and linked in the candidate queue.
  - `DEFERRED_FOR_REVIEW`: Registration is flagged for supervisory audit.
  - Select Existing: Registration is discarded, and the existing Patient 360 is opened.

---

## 5. Explicit Patient Consent Protocol

- **Never Assume Consent:** Consent is never defaulted or opt-out.
- **Purposes Supported:** `GENERAL_CARE`, `COMMUNICATION_SMS`, `COMMUNICATION_WHATSAPP`, `DATA_SHARING_RESEARCH`, `EXTERNAL_REFERRAL`.
- **Status Lifecycle:** `GRANTED` -> `WITHDRAWN` (or `REFUSED`).
- **Withdrawal Requirement:** Withdrawing consent requires an explicit reason and timestamp, preserving full audit history.

---

## 6. Encounter Lifecycle & State Machine

```
   [DRAFT]  ----(Start Consultation)---->  [IN_PROGRESS]  ----(Complete)---->  [COMPLETED]
      |                                         |
      +-------------(Cancel with reason)--------+-----------------------------> [CANCELLED]
```

- `DRAFT`: Created at front desk upon patient arrival. Receives daily facility token number.
- `IN_PROGRESS`: Clinician opens encounter and begins consultation.
- `COMPLETED`: Encounter finished; consultation ended timestamp recorded. Record becomes immutable.
- `CANCELLED`: Permitted from `DRAFT` or `IN_PROGRESS`. Requires mandatory cancellation reason.

# MASTER DATA MANAGEMENT & DATA QUALITY SPECIFICATION
## ZAYVORA MATAB OS — Enterprise Data Governance Engine (Prompt 42)

**Document Code:** SPEC-MDM-042  
**Classification:** Core Clinical Architecture Specification  
**Authority:** Clinical Data Governance Committee, Chief Medical Information Officer, Lead Architect  

---

## 1. Domain Entities & Canonical Authority

Master records in ZAYVORA MATAB OS are categorized into canonical entities governed by `mdm_master_entities_catalog`. Each entity specifies:
- `entity_type`: Unique identifier (`patient`, `facility`, `practitioner`, `formulation`, `terminology_concept`, `encounter`).
- `display_name`: Human-readable label.
- `canonical_table`: Authoritative database table.
- `authoritative_source`: Primary source of truth (`EMR_PRIMARY`, `REGULATORY_REGISTRY`, `NATIONAL_PORTAL`, `SYSTEM_CORE`).
- `survivorship_rule`: Strategy used when reconciling attributes (`MOST_RECENT_VALIDATED`, `CLINICAL_SUPERVISOR_DECISION`, `SOURCE_SYSTEM_PRIORITY`, `MANUAL_STIPULATION`).
- `normalization_rules`: JSON specifications for name cleaning, phone formatting, identifier sanitization.

---

## 2. 9-Dimensional Data Quality Rule Architecture

All enterprise data quality evaluations adhere to 9 formal dimensions:

| Dimension | Scope & Verification Criteria | Example Rule |
|---|---|---|
| **1. Completeness** | Mandatory field presence, absence of sentinel blanks or empty string surrogates. | `RULE_PATIENT_MANDATORY_CONTACT`: Active patient must have at least one reachable phone or address. |
| **2. Validity** | Format, syntax, regex conformances, valid ranges, date bounds. | `RULE_VALID_PHONE_FORMAT`: E.164 phone numbers (10 to 15 digits). |
| **3. Uniqueness** | Single master entity per real-world individual, zero duplicate national IDs within tenant. | `RULE_UNIQUE_NATIONAL_ID`: National health IDs (e.g. ABHA) must be globally unique per patient. |
| **4. Consistency** | Logical cross-field and cross-record coherence. | `RULE_ENCOUNTER_DATES_LOGICAL`: Encounter closed_at must be >= started_at. |
| **5. Referential Integrity** | Foreign key dependencies, dangling reference prohibition, tenant boundary alignment. | `RULE_ENCOUNTER_PATIENT_EXISTS`: Encounter patient_id must resolve to an active patient record in the same organization. |
| **6. Timeliness** | Freshness of clinical data, vitals, and operational queues. | `RULE_CLINICAL_VITALS_FRESHNESS`: Vitals older than 48 hours flagged as stale during active consultations. |
| **7. Provenance Coverage** | Attribution, source tracking, authored_by, and timestamp completeness. | `RULE_PROVENANCE_REQUIRED`: Every clinical observation must record author_id and source_type. |
| **8. Conformance** | Adherence to standardized schemas, codes, and enum sets. | `RULE_GENDER_CONFORMANCE`: Patient gender must adhere to standard ISO/HL7 codes (`M`, `F`, `O`, `U`). |
| **9. Reconciliation** | Accounting equality across inventory, billing, dispense ledgers, and audit logs. | `RULE_DISPENSE_INVENTORY_MATCH`: Dispensed items must strictly decrement recorded batch inventory. |

---

## 3. Probabilistic & Deterministic Duplicate Candidate Scoring

Duplicate candidate detection evaluates a multi-feature vector:
1. **Name Matching:** Exact match (weight: 0.30), Normalized phonetic/token overlap (weight: 0.20).
2. **Phone Number:** Exact normalized E.164 match (weight: 0.25).
3. **Date of Birth:** Exact match (weight: 0.25) or year-only match (weight: 0.10).
4. **Gender:** Matching gender (multiplier 1.0; mismatch penalty -0.30).
5. **Address/Postal Code:** Exact postal code / locality match (weight: 0.10).

**Score Categorization:**
- `score >= 0.85`: High Confidence Match -> Flagged for `awaiting_identity_review`.
- `0.65 <= score < 0.85`: Probable Match -> Flagged for `triaged` stewardship.
- `score < 0.65`: Low Confidence / Distinct -> Unlinked.

### Zero Automatic Merge Non-Negotiable
- **Rule:** Under no circumstance will the system auto-merge patients.
- **Resolution States:** `pending`, `under_review`, `confirmed_duplicate`, `confirmed_distinct`, `false_positive`.
- **Reversible Linking:** Confirmed duplicates can be soft-linked using `mdm_patient_cross_references` (establishing master alias pointers) without destroying or mutating underlying historical records.

---

## 4. Controlled Terminology Stewardship

Unani medicine operates on distinct philosophical and clinical foundations (*Mizaj*, *Akhlat*, *Arwah*, *Quwa*, *Af'al*). Bridging Unani concepts with modern biomedical vocabularies (ICD-10, SNOMED-CT, LOINC) requires strict governance:
- **Mapping Types:**
  - `exact`: Semantic identity (rare, strictly proven).
  - `narrow`: Modern term is narrower in scope than Unani concept.
  - `broad`: Modern term is broader in scope.
  - `approximate`: Pragmatic clinical correlation for reporting/billing.
  - `unmapped`: Concept has no modern equivalent and must be preserved verbatim.
- **Governance Attributes:**
  - `clinical_scope`: Explicit clinical domain (e.g. `gastroenterology`, `rheumatology`).
  - `limitations`: Mandatory clinical caveats detailing where the equivalence breaks down.
  - `review_status`: `draft`, `review`, `approved`, `provisional`, `rejected`, `deprecated`.
  - `reviewed_by`: Credentialed Unani Tabib / Medical Officer.

---

## 5. Governed Bulk Import Lifecycle

1. **Staging:** Data is uploaded into `mdm_import_batches` with raw rows stored in `mdm_import_records` (`status = 'staged'`).
2. **Validation / Dry-Run:** Batch is evaluated against data quality rules and schema constraints without persisting into production tables (`status = 'validated_dry_run'`).
3. **Review & Approval:** Data steward reviews validation errors, warning rates, and duplicate candidate projections.
4. **Idempotent Commit:** Only valid records are committed into canonical tables (`patients`, etc.) using deterministic keys, idempotency tokens, and audit ledger entries (`status = 'committed'`).

---

## 6. Data Stewardship Workflow Engine

Stewardship cases (`mdm_stewardship_cases`) track actionable data quality issues:
- **Status Lifecycle:** `open` -> `triaged` -> `assigned` -> `awaiting_source` -> `awaiting_clinical_review` -> `awaiting_identity_review` -> `approved_for_change` -> `resolved` / `rejected` / `blocked` / `closed`.
- **Events & Audit:** Every state transition records an `mdm_stewardship_case_events` record with user ID, rationale, and state payload.

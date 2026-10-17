# ZAYVORA MATAB OS — KNOWLEDGE AUTHENTICITY, VERIFICATION & CLINICAL SAFETY (KAVS)
## Source Governance, Provenance & Verification Policy
**Document Reference:** `KAVS-POL-001`  
**Version:** `1.0.0`  
**Effective Date:** `2026-01-01`  
**Classification:** Governed Clinical Architecture Standard  
**Mandate:** Non-Negotiable Knowledge Integrity Policy

---

## 1. Absolute Knowledge Integrity Principles

### 1.1 Non-Fabrication Invariant
Under no circumstances may any clinical recommendation, Unani therapeutic principle, drug/herb identity, formulation ratio, ingredient quantity, dosage, route, duration, indication, contraindication, drug interaction, guideline, citation, or page locator be invented, fabricated, or hallucinated by artificial intelligence, application code, database seed scripts, or developers.

### 1.2 Separation of AI Assistance from Clinical Authority
AI systems (including Large Language Models, OCR pipelines, and extraction engines) may assist with text transcription, document translation, syntactic entity normalization, and indexing **only when strictly tethered to verified primary source material**.
- All AI-extracted content is designated as `DRAFT` / `UNVERIFIED`.
- No AI output may enter the authoritative clinical release stream or be served to clinicians in consultation retrieval without explicit, authenticated human expert review and formal sign-off.

---

## 2. The Five Independent Verification Dimensions

To prevent false confidence or conflation between academic validity and clinical applicability, every atomic clinical claim is appraised across five distinct, non-overlapping dimensions:

| Dimension | Permissible Enumerated Values | Governance Standard |
| :--- | :--- | :--- |
| **A. Source Authenticity** | `unverified`, `metadata_verified`, `document_integrity_verified`, `publisher_or_authority_verified`, `disputed` | Confirms the physical or cryptographic authenticity of the source document, edition, and publisher registry. |
| **B. Extraction Fidelity** | `not_checked`, `machine_extracted`, `human_checked`, `correction_required`, `unreadable` | Verifies that the extracted text matches the exact words and meaning of the physical or digital source anchor without distortion. |
| **C. Evidence Characterization** | `traditional_description`, `official_specification`, `regulatory_requirement`, `clinical_guideline_recommendation`, `systematic_review_meta_analysis`, `randomized_trial`, `observational_human_research`, `case_report_series`, `preclinical_in_vitro_animal`, `expert_consensus`, `mechanistic_rationale`, `unknown_insufficient` | Objectively classifies the nature and methodology of the evidence without inflating traditional texts to clinical trials or vice versa. |
| **D. Clinical Review State** | `not_reviewed`, `review_in_progress`, `changes_requested`, `approved_for_defined_use`, `rejected`, `review_expired` | Reflects the human review workflow state conducted by qualified scholars and clinicians. |
| **E. Intended-Use Authorization** | `historical_reference_only`, `educational_reference`, `clinician_contextual_reference`, `formulary_definition`, `safety_alert_rule`, `clinical_decision_support`, `not_authorized_for_clinical_use` | Governs the precise clinical context in which the claim may be surfaced to practitioners. |

---

## 3. Dual-Expert Governance Review Protocol

### 3.1 Reviewer Role Specialization
Reviewers must hold authenticated credentials matching the domain of appraisal:
- **UNANI_SCHOLAR (Hakim):** Validates classical treatise philology, mizaj, af'aal, traditional posology, musleh (correctives), and badal (substitutes).
- **BIOMEDICAL_CLINICIAN (MBBS/MD):** Evaluates clinical trials, safety red flags, toxicology, and drug-herb interactions.
- **PHARMACOGNOSIST / BOTANIST:** Confirms botanical taxonomy, binomial nomenclature, adulteration risks, and pharmacopoeial specifications.
- **GOVERNANCE_LEAD:** Confirms statutory rights, licensing, and compliance with the Drugs and Cosmetics Act (AYUSH technical regulations).

### 3.2 Dual Review Requirements
Claims slated for `safety_alert_rule` or `clinical_decision_support` authorization require dual sign-off:
1. Lead appraisal by a credentialed Unani Scholar or Pharmacognosist.
2. Secondary independent appraisal by a Biomedical Clinician or Governance Lead.

---

## 4. Source Registry, Rights & Exact Locators

### 4.1 Permissible Source Classes
1. **Statutory AYUSH Compendia:** Unani Pharmacopoeia of India (UPI), National Formulary of Unani Medicine (NFUM), Ayurvedic/Siddha statutory counterparts.
2. **Classical Authorities:** Canon of Medicine (Ibn Sina), Kitab al-Hawi (al-Razi), Kitab al-Kulyat (Ibn Rushd), Kamil al-Sina'a (al-Majusi), Makhzan al-Mufradat (Kabiruddin).
3. **Peer-Reviewed Scientific Literature:** Indexed medical journals, Cochrane systematic reviews, ICMR/CSIR studies.
4. **Regulatory Gazettes & Orders:** Ministry of AYUSH, CDSCO, WHO traditional medicine guidelines.

### 4.2 Exact Locator Mandate
Every registered citation must resolve to an exact physical or digital locator:
- Page number / Folio number (with edition and print year).
- Chapter, section, and subsection title.
- Monograph entry or paragraph anchor.
- Digital SHA-256 document checksum where digital files are retained.

---

## 5. Consultation Retrieval & Release Integrity

### 5.1 Retrieval Safety Firewall
The consultation retrieval engine (`KAVSEngine.retrieve_verified_clinical_context`) enforces strict filtering:
- Draft, unreviewed, disputed, or deprecated claims are strictly excluded from clinician searches.
- If no verified knowledge exists for a queried drug or concept, the system explicitly returns `insufficient_information: true` with a mandatory clinical caveat: *"No verified clinical claims found for the query within approved scope. Does NOT imply absence of clinical significance."*
- Fabricated default values or unverified fallback statements are strictly prohibited.

### 5.2 Immutable Release Packaging
Live consultation workspaces only consume claims published in an **Immutable Knowledge Release** (`kavs_knowledge_releases`). Each release is cryptographically fingerprinted using a SHA-256 manifest hash of all included claims and verification records. Releases may be formally withdrawn (`WITHDRAWN`) with mandatory root-cause justification in the event of new safety evidence.

---

## 6. Audit & Governance Enforcement

All KAVS operations (source registration, locator creation, verification recording, claim transitions, release publishing, and policy updates) generate tamper-evident, append-only entries in `kavs_audit_events`.
Audit records are permanently preserved and accessible to regulatory auditors and institutional clinical governance boards.

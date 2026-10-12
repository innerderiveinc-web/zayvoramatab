# Clinical Knowledge & Formulary Governance — ZAYVORA MATAB OS

**Version:** 1.1  
**Scope:** Knowledge Ingestion, Formulary Lifecycle, Safety Rule Validation, and Clinical Authority Boundaries.  

---

## 1. Governance Board & Authority Hierarchy

All clinical knowledge in ZAYVORA MATAB OS is governed by a dual-disciplinary panel:
1. **Unani Governance Panel (UGP):** Qualified Tabibs/Hakeems with postgraduate Unani qualifications (MD/BUMS) and pharmacopoeia experience.
2. **Modern Clinical Safety Panel (MCSP):** General physicians/pharmacologists reviewing red-flag rules, herb-drug interactions, and toxicology thresholds.

### 1.1 Approved Knowledge Source Hierarchy

Every monograph, formulation, single drug (*Mufrad*), and compound drug (*Murakkab*) record in MATAB OS must cite a primary authorized source from the approved catalog:

| Authority Tier | Source Title / Authority | Permitted Usage |
|---|---|---|
| **Tier 1 (Statutory)** | National Formulary of Unani Medicine (NFUM) Parts I-VI | Standard Murakkabat formulations, permissible doses, standard processing. |
| **Tier 1 (Statutory)** | Unani Pharmacopoeia of India (UPI) Parts I-II | Botanical identity, macroscopic/microscopic standards, single drug assay. |
| **Tier 2 (Classical Benchmark)** | *Al-Qanun fi al-Tibb* (Avicenna / Ibn Sina) | Theoretical foundation of Mizaj, Akhlat, Afaal, and Asbab-e-Sittah. |
| **Tier 2 (Classical Benchmark)** | *Kitab al-Hawi fi al-Tibb* (Al-Razi / Rhazes) | Differential clinical observations, therapeutic strategies. |
| **Tier 2 (Classical Benchmark)** | *Bayaz-e-Kabir* (Hakeem Kabiruddin) | Practical formulation recipes, adjuvants (*Badal*), and corrective agents (*Musleh*). |
| **Tier 3 (Modern Evidence)** | CCRUM (Central Council for Research in Unani Medicine) Monographs | Clinical trials, safety evaluations, standardized extracts. |
| **Tier 3 (Toxicology Registry)** | Drugs & Cosmetics Rules (Schedule E(1) Poisonous Substances) | Poisonous herbal/mineral list requiring strict Mudabbar detoxification. |

---

## 2. Monograph Ingestion & Review Workflow

No clinical knowledge can be injected directly from an LLM or unverified web scraper into the MATAB OS production database. All knowledge entities adhere to this strict state lifecycle:

```
[ EXTRACTED / DRAFT ]
         │
         ▼
[ STRUCTURAL VALIDATION ]  ─── Fail ───► [ REJECTED ]
         │
         ▼
[ EXPERT CLINICAL REVIEW ] (UGP / MCSP sign-off with license ID)
         │
         ▼
[ APPROVED FOR PILOT ]
         │
         ▼
[ PRODUCTION APPROVED ]    ─── Superseded ───► [ ARCHIVED / RETIRED ]
```

### 2.1 Metadata Schema for Every Knowledge Record
- `entity_id`: UUIDv4 canonical identifier.
- `canonical_name`: Standardized botanical or classical Unani name (e.g., *Safoof-e-Mohazzil*, *Asgandh / Withania somnifera*).
- `transliteration`: Urdu, Arabic, Hindi, and English variants.
- `source_id`: Reference to authorized source (e.g., `SRC-NFUM-PART1-P142`).
- `source_edition`: Year / Volume / Edition.
- `reviewer_id`: Practitioner ID of the certifying clinical reviewer.
- `review_date`: ISO 8601 timestamp of formal verification.
- `dose_min` & `dose_max`: Statutory dosage range per intake with standardized SI units (`mg`, `g`, `ml`, `ratti`, `masha` mapped deterministically to metric).
- `mudabbar_required`: Boolean flag indicating mandatory detoxification before compounding (e.g., for *Kuchla / Strychnos nux-vomica*, *Azaarqi*).
- `schedule_e1`: Boolean flag denoting hazardous substance under Schedule E(1).
- `contraindications`: Age groups, trimester of pregnancy, renal/hepatic impairments.

---

## 3. Prescribing Safety Invariants

1. **Non-Extrapolation Rule:** If a formulation or dosage has not been verified in an approved source for a specific demographic (e.g., infants < 1 year), the system **MUST NOT** extrapolate a theoretical dose. It must flag `UNKNOWN_SAFETY_DATA` and demand direct clinician confirmation.
2. **Corrective Agent (*Musleh*) Alerting:** Where classical literature designates a mandatory *Musleh* for a potent ingredient (e.g., *Filfil Siyah* or *Zanjabeel* for heavy gums), the Nuskha compiler warns the Hakeem if the corrective agent is absent.
3. **Detoxification (*Tadbeer-e-Adviyah*) Check:** Any formulation containing raw Schedule E(1) substances cannot be finalized unless the clinician explicitly selects a verified *Mudabbar* batch or certifies laboratory detoxification.
4. **Adverse Event Escalation:** Any documented adverse event recorded during follow-up is immediately linked to the specific prescription item version and highlighted in subsequent consultations for that patient and formulary review queues.

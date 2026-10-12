# ZAYVORA MATAB OS — Unani Clinical Assessment, Organ-Axis & Usul-e-Ilaj Documentation

**Document Status:** Internal Development Documentation  
**Product Version:** Standalone MATAB OS Phase 1 (Prompt 04)  
**Notice:** Internal development vertical slice only — not clinically validated and not approved for autonomous decision-making.

---

## 1. Clinical Design Principles

ZAYVORA MATAB OS implements Unani-Tibb clinical workflows under strict adherence to the following axioms:

1. **Human Clinician Authority:** The system provides documentation tools and contextual knowledge lookup. It **never** infers a definitive Mizaj, diagnoses a disease, or prescribes autonomously.
2. **Four-State Semantic Completeness:** Every clinical observation supports four distinct states:
   - `ASSESSED`: Verified by clinical examination or history during the current encounter.
   - `NOT_ASSESSED`: Intentionally deferred or omitted.
   - `NOT_APPLICABLE`: Irrelevant to the current encounter presentation.
   - `UNOBTAINABLE`: Could not be captured due to patient state or lack of instrumentation.
   *Empty or unrecorded fields are never silently converted into "normal" findings.*
3. **Fail-Closed Organ-Axis Association:** The system only presents reviewed classical relationships between organ systems. When queried on an unverified organ pair, it presents an honest empty state (`FAIL_CLOSED_UNREVIEWED`), strictly refusing to synthesize unreviewed associations.
4. **Governed Treatment Principles (Usul-e-Ilaj):** Treatment principles precede medication orders. Linking a prescription draft to a care plan provides therapeutic context only and **never** auto-signs or releases medication.

---

## 2. Assessment Domain Hierarchy

### 2.1 Mizaj (Temperamental Assessment / مزاج)
- **Primary Mizaj:** `DAMAWI` (Sanguine / دموی), `BALGHAMI` (Phlegmatic / بلغمی), `SAFRAWI` (Choleric / صفراوی), `SAWDAWI` (Melancholic / سوداوی), `MOTADIL` (Balanced / معتدل).
- **Dominance Level:** `MILD`, `MODERATE`, `SEVERE`.
- **Qualitative Observations:** Tactile temperature, pulse volume, skin moisture, body habitus, complexion, sleep quality, and psychological demeanor.

### 2.2 Afaal (Functional Observations & Signs / افعال)
- **Hazm (Digestion / هضم):** Appetite, postprandial fullness, gastric fire.
- **Nabz (Pulse / نبض):** Rate, fullness, rhythm, compressibility, vessel tension.
- **Baul (Urine / بول):** Color, clarity, sediment, frequency.
- **Baraz (Stool / براز):** Consistency, frequency, transit time.
- **Naum-o-Yaqzah (Sleep & Wakefulness / نوم و يقظہ):** Duration, restful quality, nocturnal awakenings.
- **Tanaffus (Respiration / تنفس):** Rhythm, effort, breathlessness.

### 2.3 Asbab-e-Sittah Zaruriyyah (Six Essential Causes / اسباب ستہ ضروریہ)
- **Hawa (Air & Climate / ہوا):** Ambient temperature, seasonal factors, air quality.
- **Makul-o-Mashrub (Food & Beverage / ماکول و مشروب):** Diet composition, thermal nature of foods, meal regularity.
- **Harkat-o-Sukun Badani (Bodily Movement & Rest / حرکت و سکون بدنی):** Physical activity, exertion, sedentary patterns.
- **Harkat-o-Sukun Nafsani (Psychic Movement / حرکت و سکون نفسانی):** Emotions, stress, grief, anger, anxiety.
- **Naum-o-Yaqzah (Sleep & Wakefulness):** Sleep hygiene, circadian rhythm.
- **Ihtibas-o-Istifragh (Retention & Evacuation / احتباس و استفراغ):** Elimination efficiency, morbid matter retention.

---

## 3. Organ-Axis Contextual Association Engine

Unani medicine recognizes physiological interdependence between organ systems. The Organ-Axis service provides contextual lookup against reviewed classical references:

- **Primary Concepts:** Mi'da (Stomach), Dimagh (Brain), Kabid (Liver), Qalb (Heart), Kulliya (Kidney).
- **Classical Associations:**
  - *Mi'da wa Dimagh (Gastro-Cerebral Axis):* Vapors (*Bukharaat*) arising from digestive dysfunction affecting cerebral clarity, headache, and mood. Cited from *Al-Qanun fi al-Tibb [Synthetic]*.
  - *Kabid wa Qalb (Hepato-Cardiac Axis):* Sanguification and humor distribution affecting vital spirit (*Ruh Hayawani*).
- **Fail-Closed Behavior:** If a user selects an unreviewed combination (e.g. Brain and Kidney without a validated literature monograph), the system outputs:
  ```json
  {
    "mappings": [],
    "status": "FAIL_CLOSED_UNREVIEWED",
    "message": "No reviewed Organ-Axis clinical relationship exists for this combination in the verified knowledge base."
  }
  ```

---

## 4. Usul-e-Ilaj Treatment Principles & Care Plan Lifecycle

### 4.1 Treatment Principles Vocabulary
- **Tanqia-e-Mawad (تنقیۂ مواد):** Evacuation of accumulated morbid humors (Munzij followed by Mushil).
- **Ta'deel-e-Mizaj (تعدیلِ مزاج):** Normalization of temperament using foods or remedies possessing contrary qualities (*Ilaj-bil-Zidd*).
- **Taghdhiya wa Ilaj-bil-Ghiza (علاج بالغذأ):** Nutritional and dietary regimen modifications.
- **Ilaj-bil-Tadbir (علاج بالتدبیر):** Regimenal therapies including Hijama (cupping), Daluk (massage), Hammam (bath), and Riyazat (exercise).
- **Ilaj-bil-Dawa (علاج بالدواء):** Pharmacotherapy using single (Mufradat) or compounded (Murakkabat) formulations.

### 4.2 Care Plan to Prescription Decoupling
- A care plan item may link to a draft prescription (`linked_prescription_id`).
- Linking associates clinical intent with medication orders.
- **Critical Policy:** Linking does **NOT** sign or issue the prescription. Prescriptions require separate, explicit electronic signing with SHA-256 digital signature under statutory authority.
- Cross-patient prescription linkage is blocked with HTTP 409 Conflict.

### 4.3 Longitudinal Outcome Recording
Outcomes recorded per care plan item support:
- `RESOLVED`: Complete resolution of target symptom/humoral imbalance.
- `IMPROVED`: Partial symptomatic improvement; continuation or step-down indicated.
- `UNCHANGED`: No clinical change; reassessment required.
- `WORSENED`: Clinical deterioration; emergency review or regimen revision.
- `ADVERSE_EVENT`: Suspected adverse reaction; mandatory review.

---

## 5. Security & Tenancy Isolation

- All assessment, organ-axis, and care plan queries require valid JWT authentication with proper RBAC scopes (`assessment:read`, `assessment:finalise`, `care_plan:create`, etc.).
- Tenant facilities are strictly isolated. Practitioners cannot query or modify clinical assessments belonging to other clinic organizations.
- Finalised assessments generate SHA-256 cryptographic digests, ensuring tamper-evident persistence across the clinical record.

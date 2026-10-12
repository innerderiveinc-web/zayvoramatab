# ADR-019: Hybrid Retrieval, Transliteration Normalization, and Clinical Context Boundaries

- **Status:** Accepted
- **Date:** 2026-10-13
- **Context:**
  Practicing Hakeems and clinical staff frequently query clinical concepts using diverse languages, English, Urdu, Hindi, and colloquial transliterations (e.g., *Safra* / *Yellow Bile*, *Balgham* / *Phlegm*, *Su'al* / *Cough*, *Su-e-Hazm* / *Dyspepsia*, *Sana Makki* / *Senna*). Exact-match keyword searches fail across these transliteration boundaries. Additionally, when searching based on patient encounter context (symptoms, vital signs, medications), the retrieval engine must never overreach into autonomous drug ordering.
- **Decision:**
  1. **Hybrid Retrieval with Transliteration Expansion:** Combine canonical matching, alias matching, multi-lingual transliteration synonym dictionaries, and relevance scoring to ensure robust multi-dialect clinical search.
  2. **Encounter Context Retrieval Contract:** Contextual retrieval consumes permitted patient facts (age, symptoms, vital signs, active medications, Unani Mizaj) and returns relevant Unani monographs, modern guidelines, safety precautions, and citations.
  3. **Strict Non-Prescribing Perimeter:** Retrieval results carry an explicit non-prescribing boundary (`prescribing_disclaimer`), functioning strictly as informational decision-support for the licensed human practitioner.
- **Consequences:**
  - Dramatically improves clinician ergonomics across multi-lingual AYUSH and modern terminology.
  - Maintains a strict ethical and legal separation between informational retrieval and clinician prescribing authority.

# ADR-015: Dual-Lane Clinical Assessment Architecture (Modern Biomedical and Unani Separation)

- **Status:** Accepted
- **Date:** 2026-10-13
- **Context:**
  In integrative and traditional medical settings (Matabs and AYUSH clinics), practitioners evaluate patients using both classical Unani diagnostic principles (Mizaj, Afaal, Asbab-e-Sittah الضرورية, Nabz, Baul, Baraz) and modern biomedical clinical observations (vital signs, physical examination, symptom triage, differential diagnosis, red flags). Conflating these two paradigms into a single unified record or allowing modern diagnostic suggestions to overwrite Unani temperamental conclusions causes conceptual pollution, legal ambiguities, and clinical confusion. Conversely, isolating them into completely separate tools impedes comprehensive clinical judgment and referral safety.
- **Decision:**
  1. **Dual-Lane Encounter Architecture:** Implement the Modern Clinical Assessment as a distinct, dedicated workspace lane alongside the Unani Assessment within the same clinical encounter.
  2. **Zero Cross-Lane Overwrite:** Modern clinical observations, problem lists, differential candidates, and red flags exist in their own domain tables (`modern_clinical_assessments`, `clinical_observations`, `clinical_problems`, `differential_candidates`, `red_flag_events`) and never overwrite or mutate Unani assessment tables (`unani_clinical_assessments`, `unani_assessment_items`, `organ_axis_mappings`).
  3. **Shared Context without Collapsing:** Both lanes share common encounter-level metadata (patient demographics, visit token, vital observations) and appear chronologically within the Patient 360 timeline, but retain independent versioning, status lifecycles, and signing authority.
- **Consequences:**
  - Preserves classical Unani epistemological integrity while ensuring modern patient safety, structured symptom capture, and hospital referral readiness.
  - Allows multi-disciplinary clinic environments where modern biomedical findings and traditional temperamental assessments coexist transparently.

# ADR-020: Deterministic Clinical Safety Firewall, Substance Identity, and Fail-Closed Evaluation

- **Status:** Accepted
- **Date:** 2026-10-13
- **Context:**
  Clinical prescribing in integrative medicine (Unani and AYUSH) entails multi-factorial risks: Schedule E(1) toxic botanicals (e.g. *Azaraqi / Kuchla*), severe botanical/nut allergies (e.g. *Badam*), drug-drug interactions (e.g. *Digoxin* hypokalemia exacerbation by anthraquinone laxatives like *Senna*), and therapeutic ingredient duplication across polyherbal formulations. Non-deterministic heuristic or LLM-driven safety evaluation introduces hallucinated reassurance and catastrophic silent passes.
- **Decision:**
  1. **Deterministic Rule Engine:** All preflight evaluations execute purely deterministic code against versioned, reviewed rules (`safety_rules`, `interaction_records`, `normalized_substances`).
  2. **Fail-Closed on Ambiguity:** If an ingredient or drug identity is ambiguous or unmapped, the engine outputs an `unable_to_assess` or `action_required` finding. It never defaults to an automatic "pass".
  3. **Non-Negotiable Critical Blocks:** Critical safety alerts (e.g. active documented patient anaphylactic allergy, uncertified Schedule E(1) toxins) carry `is_overridable = 0` and strictly forbid clinician override at the database layer (HTTP 409 Conflict).
  4. **Strict Re-evaluation at Electronic Signing:** The prescription signing endpoint independently re-executes server-side safety preflight immediately prior to locking. It rejects client-supplied safety statuses and blocks signing if any unresolved critical findings exist.
- **Consequences:**
  - Guarantees zero silent bypass of critical patient hazards.
  - Ensures full clinical non-repudiation and medico-legal accountability under AYUSH and medical council standards.

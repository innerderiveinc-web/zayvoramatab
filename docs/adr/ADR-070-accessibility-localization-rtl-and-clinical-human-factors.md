# ADR-070: Accessibility, Localization, Right-to-Left (RTL) UI & Clinical Human-Factors Validation Engine (Prompt 51)

- **Status:** Accepted
- **Date:** 2026-10-15
- **Auditor & Author Roles:** Principal Frontend Engineer, Accessibility Specialist, Localization/i18n Architect, Clinical Human-Factors Engineer

---

## Context
Prompt 51 mandates an Enterprise Accessibility, Localization, Right-to-Left (RTL) UI & Clinical Human-Factors Validation Engine for ZAYVORA MATAB OS to make supported clinical workflows accessible, understandable, and usable across languages, writing directions, devices, and user contexts—without compromising clinical meaning, obscuring diagnostic uncertainty, or bypassing safety controls.

Core non-negotiables demand:
1. **Accessibility is Functional Behavior:** Semantic HTML structure, explicit ARIA roles/landmarks, full keyboard navigation (no keyboard traps), visible focus rings with 2px offset, and screen-reader announcements.
2. **True Localization Beyond Strings:** Centralized catalogs for English (`en`), Urdu RTL (`ur`), and Hindi (`hi`), locale-aware date/number/currency formatting, text expansion/wrapping, and bilingual typography font stacks.
3. **RTL Directional Integrity:** Native document and component-level right-to-left layout (`dir="rtl"`) without mechanical string reversal, logical spacing properties, and bidirectional text isolation (`<bdi>`) for LTR tokens (patient IDs, URLs, phone numbers, dosages).
4. **Governed Clinical Glossary & Tabib Review Gate:** Absolute prohibition against unreviewed machine translation of safety-critical clinical terms, posology ceilings, toxic herb warnings, or consent language. Clinical terms must be reviewed and digitally attested by licensed Tabibs/Hakeems.
5. **Clinical Human-Factors Validation:** Measurement of cognitive workload (NASA-TLX), alert fatigue avoidance, task completion rates, and confirmation dialog clarity for consequential or irreversible clinical actions.
6. **Tamper-Evident Chained Audit Trail:** Continuous SHA-256 hash chaining of all localization, glossary, accessibility audit, and human-factors scenario events.

---

## Decision

1. **Database Persistence (Migration 049):**
   - `i18n_locales`: Registry of supported languages (`en`, `ur`, `hi`), directions (`ltr`, `rtl`), scripts (`Latn`, `Arab`, `Deva`), and completion percentages.
   - `i18n_translation_catalogs`: Namespaced translation catalogs (`common`, `clinical`, `safety`, `billing`, `inventory`, `triage`) with source English strings, localized text, status (`draft`, `reviewed`, `approved`), safety-critical flags, and reviewer attribution.
   - `i18n_clinical_glossary`: Governed Unani clinical terminology crosswalk linking classical Arabic/Urdu terms to Roman transliteration, Hindi (Devanagari), and modern biomedical equivalents, requiring Tabib digital approval.
   - `user_a11y_preferences`: Per-user accessibility preferences (preferred locale, font scale factor, high contrast mode, reduced motion, screen reader optimization).
   - `a11y_accessibility_audits`: WCAG 2.1 AA audit runs capturing contrast, keyboard operability, ARIA landmarks, label/error associations, and focus management across desktop, tablet, and mobile profiles.
   - `human_factors_validation_scenarios`: Empirical usability test scenarios measuring task completion, completion time, clinical error counts, alert fatigue ratings, and NASA-TLX cognitive workload scores.
   - `a11y_human_factors_audit_ledger`: SHA-256 tamper-evident hash-chained audit log.

2. **Domain Service Architecture (`AccessibilityLocalizationEngine`):**
   - Enforces Tabib/Safety Officer authority for approving safety-critical translations.
   - Centralizes locale formatting for dates (`Intl.DateTimeFormat`), numerals (`Intl.NumberFormat`), and currency (INR).
   - Validates WCAG 2.1 AA compliance rules and tracks clinical human-factors workload scores.
   - Enforces cryptographic hash chaining with automated tamper verification.

3. **Frontend Implementation & Design System:**
   - Design Tokens (`apps/web/static/css/tokens.css`): Added multilingual font stacks (`Noto Nastaliq Urdu`, `Noto Sans Devanagari`), high-visibility focus ring tokens, and high-contrast theme overrides.
   - App Shell Styles (`apps/web/static/css/shell.css`): Added `.skip-to-content` link, `.sr-only` accessibility utility, `:focus-visible` styling, native RTL logical styling (`[dir="rtl"]`), and `@media (prefers-reduced-motion)` support.
   - Client i18n Engine (`apps/web/static/js/i18n.js`): Client-side translation manager with parameter interpolation, locale switching, and bidirectional isolation (`<bdi>`).
   - App Shell View (`apps/web/static/js/views/shell.js`): Added accessible skip link, language switcher dropdown, ARIA landmarks, and keyboard-accessible navigation.
   - Admin Workbench (`apps/web/static/js/views/knowledge_admin.js`): Integrated "Accessibility, Localization & Human Factors (P51)" tab with KPI summaries, locales catalog, clinical glossary, WCAG 2.1 AA audit center, and human-factors scenario tracker.

4. **REST API Interface & Permissions:**
   - Mounted 15 REST API endpoints under `/api/v1/a11y-i18n/` in `apps/api/router.py`.
   - Registered 7 granular permission aliases in `apps/api/core/permissions.py` (`a11y:read`, `a11y:manage`, `a11y:audit_execute`, `a11y:human_factors_evaluate`, `i18n:read`, `i18n:manage`, `i18n:review`).

---

## Consequences

- **Positive:**
  - Enables full, native multilingual usability for classical Unani practitioners in Urdu (RTL) and Hindi alongside English.
  - Guarantees WCAG 2.1 AA accessibility across keyboard, screen-reader, and low-vision contexts.
  - Prevents alert fatigue and preserves clinical clarity through empirical human-factors testing and cognitive workload tracking.
  - Maintains strict epistemological boundaries: traditional concepts are not distorted or replaced by unvetted automated translations.
- **Constraints:**
  - Additional language translations require explicit human Tabib review before approval.
  - Third-party browser extensions or external translation tools must not override server-authoritative clinical terms.

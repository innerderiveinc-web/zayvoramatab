/**
 * Prescriptions View — Honest Future Phase State
 */

export function renderPrescriptions(container) {
  container.innerHTML = `
    <div style="margin-bottom: 1.25rem;">
      <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Prescriptions & Formulary</h1>
      <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
        Deterministic Safety Preflight, Nuskha Compiler & Immutable Electronic Signing.
      </p>
    </div>

    <div class="unimplemented-banner">
      <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📜</div>
      <h3>Nuskha Builder & Safety Preflight Available in Phase 3</h3>
      <p>
        The statutory formulary catalog (NFUM, UPI), Mudabbar toxin checking, deterministic allergen/overdose preflight, and cryptographic signing will connect in <strong>Phase 3</strong>.
      </p>
      <div style="display: flex; gap: 0.5rem; justify-content: center;">
        <span class="badge badge-warning">Capability: clinical.safety_preflight</span>
        <span class="badge badge-danger">State: NOT_IMPLEMENTED</span>
      </div>
    </div>
  `;
}

/**
 * Consultation View — Honest Future Phase State
 */

export function renderConsultation(container) {
  container.innerHTML = `
    <div style="margin-bottom: 1.25rem;">
      <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Clinical Consultation Canvas</h1>
      <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
        Unified 3-Zone Encounter Workspace for Unani & Modern Clinical Charting.
      </p>
    </div>

    <div class="unimplemented-banner">
      <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🩺</div>
      <h3>Consultation Canvas Available in Phase 2</h3>
      <p>
        The single 3-Zone Consultation Canvas (Zone 1 Patient Context, Zone 2 Step-by-Step Clinical Charting, Zone 3 Guidance Rail) is scheduled for connection in <strong>Phase 2</strong>.
      </p>
      <div style="display: flex; gap: 0.5rem; justify-content: center;">
        <span class="badge badge-warning">Capability: clinical.consultation</span>
        <span class="badge badge-danger">State: NOT_IMPLEMENTED</span>
      </div>
    </div>
  `;
}

/**
 * Follow-ups View — Honest Future Phase State
 */

export function renderFollowups(container) {
  container.innerHTML = `
    <div style="margin-bottom: 1.25rem;">
      <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Follow-ups & Continuum Care</h1>
      <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
        Patient Monitoring Cohorts, Recalls, and Adverse Event Surveillance.
      </p>
    </div>

    <div class="unimplemented-banner">
      <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📅</div>
      <h3>Care Continuum Queues Available in Phase 4</h3>
      <p>
        Chronic disease cohort follow-ups, reminder tasks, and adverse event surveillance are scheduled for connection in <strong>Phase 4</strong>.
      </p>
      <div style="display: flex; gap: 0.5rem; justify-content: center;">
        <span class="badge badge-warning">Capability: operations.followups</span>
        <span class="badge badge-danger">State: NOT_IMPLEMENTED</span>
      </div>
    </div>
  `;
}

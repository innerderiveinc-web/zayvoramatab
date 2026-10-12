/**
 * Patients View — Foundation Entry Point
 */

import { state } from "../state.js";

export function renderPatients(container) {
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
      <div>
        <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Patients Directory</h1>
        <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
          Master Patient Index entry point (Foundation phase).
        </p>
      </div>
    </div>

    <div class="card">
      <div style="display: flex; gap: 0.75rem;">
        <input type="text" class="form-input" placeholder="Search Patients by Name, Phone, or MRN..." />
        <button class="btn btn-secondary">Search</button>
      </div>
    </div>

    <div class="unimplemented-banner">
      <div style="font-size: 2rem; margin-bottom: 0.5rem;">👥</div>
      <h3>Patient Registration & Timeline</h3>
      <p>
        The Master Patient Index, duplicate warning heuristics, and longitudinal Patient 360 will be fully connected in <strong>Phase 2 (Patient & Encounter Slice)</strong>.
      </p>
      <span class="badge badge-warning">Scheduled for Phase 2</span>
    </div>
  `;
}

// ZAYVORA MATAB OS — Prescriptions Destination

import { state } from "../state.js";
import { translations } from "../i18n.js";
import { api } from "../api.js";

export async function renderPrescriptions(container) {
  const t = translations[state.currentLang] || translations.en;
  container.innerHTML = `<div class="card"><p>Loading prescription register...</p></div>`;

  try {
    const qData = await api.get("/api/v1/encounters/queue");
    const encounters = qData.queue || [];

    let rowsHtml = "";
    for (const enc of encounters) {
      if (enc.prescription_id) {
        rowsHtml += `
          <tr>
            <td><strong>#${enc.token_number}</strong></td>
            <td>
              <strong>${enc.first_name} ${enc.last_name || ""}</strong>
              <div style="font-size:0.75rem; color:var(--color-text-muted);">${enc.mrn}</div>
            </td>
            <td>${enc.chief_complaint || "—"}</td>
            <td>
              <span class="badge ${enc.prescription_status === 'SIGNED' ? 'badge-pass' : 'badge-warn'}">
                ${enc.prescription_status || 'DRAFT'}
              </span>
            </td>
            <td>
              <button class="btn btn-primary btn-sm view-print-btn" data-pr-id="${enc.prescription_id}">
                🖨️ View & Print
              </button>
            </td>
          </tr>
        `;
      }
    }

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <div>
          <h1 style="font-size: 1.5rem; color: var(--color-primary-dark);">${t.nav_prescriptions}</h1>
          <p style="color: var(--color-text-muted); font-size: 0.9rem;">Signed orders, drafts & verified immutable records</p>
        </div>
      </div>

      <div class="card">
        <table class="data-table">
          <thead>
            <tr>
              <th>Token</th>
              <th>Patient</th>
              <th>Clinical Indication</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || '<tr><td colspan="5" style="text-align: center;">No prescription records today.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;

    container.querySelectorAll(".view-print-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const prId = btn.getAttribute("data-pr-id");
        window.open(`/api/v1/prescriptions/${prId}/print`, "_blank");
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color: red;">Error: ${err.message}</p></div>`;
  }
}

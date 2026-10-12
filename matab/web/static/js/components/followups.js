// ZAYVORA MATAB OS — Follow-ups Destination (Care Continuum)

import { state } from "../state.js";
import { translations } from "../i18n.js";
import { api } from "../api.js";

export async function renderFollowups(container) {
  const t = translations[state.currentLang] || translations.en;
  container.innerHTML = `<div class="card"><p>Loading follow-up tasks...</p></div>`;

  try {
    const data = await api.get("/api/v1/operations/follow-ups");
    const tasks = data.follow_ups || [];

    let rowsHtml = "";
    tasks.forEach(task => {
      rowsHtml += `
        <tr>
          <td><strong>${task.due_date}</strong></td>
          <td>
            <strong>${task.first_name} ${task.last_name || ""}</strong>
            <div style="font-size: 0.75rem; color: var(--color-text-muted);">${task.mrn} | ${task.phone}</div>
          </td>
          <td>${task.target_objective}</td>
          <td><span class="badge badge-unknown">${task.status}</span></td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="alert('Follow-up task marked as reviewed.')">
              Mark Complete
            </button>
          </td>
        </tr>
      `;
    });

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <div>
          <h1 style="font-size: 1.5rem; color: var(--color-primary-dark);">${t.nav_followups}</h1>
          <p style="color: var(--color-text-muted); font-size: 0.9rem;">Continuum care reviews, chronic cohort monitoring & adverse event surveillance</p>
        </div>
      </div>

      <div class="card">
        <table class="data-table">
          <thead>
            <tr>
              <th>Due Date</th>
              <th>Patient</th>
              <th>Clinical Target</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || '<tr><td colspan="5" style="text-align: center;">No follow-up tasks scheduled.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color: red;">Error: ${err.message}</p></div>`;
  }
}

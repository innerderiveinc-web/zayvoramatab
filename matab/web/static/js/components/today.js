// ZAYVORA MATAB OS — Today Destination (Command Center)

import { state } from "../state.js";
import { translations } from "../i18n.js";
import { api } from "../api.js";

export async function renderToday(container) {
  const t = translations[state.currentLang] || translations.en;
  container.innerHTML = `<div class="card"><p>Loading OPD queue...</p></div>`;

  try {
    const data = await api.get("/api/v1/encounters/queue");
    const queue = data.queue || [];
    const nextPatient = queue.find(q => q.status === "ARRIVED" || q.status === "IN_CONSULTATION");

    let nextPatientHtml = "";
    if (nextPatient) {
      nextPatientHtml = `
        <div class="card" style="border-left: 6px solid var(--color-primary); background: #fdfbf7;">
          <div class="card-header">
            <div>
              <span class="badge badge-pass" style="font-size: 0.85rem; margin-bottom: 0.25rem;">
                ${t.token} #${nextPatient.token_number}
              </span>
              <h2 class="card-title" style="font-size: 1.3rem;">
                ${nextPatient.first_name} ${nextPatient.last_name || ""}
              </h2>
              <span class="mrn-badge">MRN: ${nextPatient.mrn} | 📞 ${nextPatient.phone}</span>
            </div>
            <button id="startConsultBtn" class="btn btn-primary" data-enc-id="${nextPatient.id}">
              🩺 ${t.start_consultation}
            </button>
          </div>
          <div>
            <strong>${t.chief_complaint}:</strong> 
            <span>${nextPatient.chief_complaint || "Walk-in consultation awaiting charting."}</span>
          </div>
        </div>
      `;
    } else {
      nextPatientHtml = `
        <div class="card" style="text-align: center; padding: 2rem;">
          <p style="color: var(--color-text-muted); font-size: 1.1rem;">No patients waiting in queue right now.</p>
        </div>
      `;
    }

    let rowsHtml = "";
    queue.forEach(item => {
      const isCurrent = item.id === nextPatient?.id;
      const statusBadge = item.status === "SIGNED" 
        ? `<span class="badge badge-pass">${t.status_signed}</span>`
        : item.status === "IN_CONSULTATION" 
          ? `<span class="badge badge-warn">${t.status_in_consult}</span>`
          : `<span class="badge badge-unknown">${t.status_arrived}</span>`;

      rowsHtml += `
        <tr style="${isCurrent ? 'background: #f0fdf4;' : ''}">
          <td><strong>#${item.token_number}</strong></td>
          <td>
            <strong>${item.first_name} ${item.last_name || ""}</strong>
            ${item.is_synthetic ? '<span class="badge badge-unknown" style="font-size:0.6rem;">SYNTHETIC</span>' : ''}
            <div style="font-size: 0.75rem; color: var(--color-text-muted);">${item.mrn}</div>
          </td>
          <td>${item.phone}</td>
          <td>${item.chief_complaint || "—"}</td>
          <td>${statusBadge}</td>
          <td>
            <button class="btn btn-secondary btn-sm select-encounter-btn" data-enc-id="${item.id}">
              Open Chart
            </button>
          </td>
        </tr>
      `;
    });

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <div>
          <h1 style="font-size: 1.5rem; color: var(--color-primary-dark);">${t.queue_heading}</h1>
          <p style="color: var(--color-text-muted); font-size: 0.9rem;">Live waiting list & OPD tokens for today</p>
        </div>
        <button id="issueTokenBtn" class="btn btn-secondary">
          + Issue Walk-in Token
        </button>
      </div>

      ${nextPatientHtml}

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Waiting Queue (${queue.length})</h3>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Token</th>
              <th>Patient</th>
              <th>Phone</th>
              <th>Complaint</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || '<tr><td colspan="6" style="text-align: center;">Queue is empty.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;

    // Event Listeners
    const startConsultBtn = container.querySelector("#startConsultBtn");
    if (startConsultBtn) {
      startConsultBtn.addEventListener("click", () => {
        const encId = startConsultBtn.getAttribute("data-enc-id");
        loadAndOpenEncounter(encId);
      });
    }

    container.querySelectorAll(".select-encounter-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const encId = btn.getAttribute("data-enc-id");
        loadAndOpenEncounter(encId);
      });
    });

    const issueTokenBtn = container.querySelector("#issueTokenBtn");
    if (issueTokenBtn) {
      issueTokenBtn.addEventListener("click", () => {
        state.setActiveTab("patients");
      });
    }

  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color: red;">Failed to load queue: ${err.message}</p></div>`;
  }
}

async function loadAndOpenEncounter(encId) {
  try {
    const data = await api.get(`/api/v1/encounters/${encId}`);
    state.setActiveEncounter(data.encounter);
    state.setActiveTab("consultation");
  } catch (e) {
    alert("Error loading encounter: " + e.message);
  }
}

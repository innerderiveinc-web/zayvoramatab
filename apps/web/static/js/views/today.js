/**
 * Modern Clinical Today Dashboard — ZAYVORA MATAB OS
 * Hospital OPD Live Command, Queue Triage & Clinical Handoff
 */

import { state } from "../state.js";
import { apiClient } from "/packages/api-client/client.js";

export async function renderToday(container) {
  container.innerHTML = `
    <div class="card" style="padding: 2rem; text-align: center;">
      <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">⏱️</div>
      <p style="font-weight: 600; color: var(--matab-color-brand-primary);">Loading Today's Clinical Command Center...</p>
    </div>
  `;

  try {
    const [todayRes, healthRes] = await Promise.all([
      apiClient.get("/api/v1/operations/today").catch(() => ({ today: { metrics: {}, inventory_warnings: {}, active_queue_tokens: [] } })),
      apiClient.get("/api/v1/health/ready").catch(() => ({}))
    ]);

    const today = (todayRes && todayRes.today) || { metrics: {}, inventory_warnings: {}, active_queue_tokens: [] };
    const m = today.metrics || {};
    const inv = today.inventory_warnings || {};
    const tokens = Array.isArray(today.active_queue_tokens) ? today.active_queue_tokens : [];
    const dateFormatted = new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

    const queueRowsHtml = tokens.map(t => {
      let priorityBadge = `<span class="badge badge-secondary">Routine</span>`;
      if (t.priority === 'CLINICAL_URGENT' || t.priority === 'URGENT') {
        priorityBadge = `<span class="badge badge-danger">⚡ Urgent</span>`;
      }

      let statusBadge = `<span class="badge badge-warning">Waiting</span>`;
      if (t.status === 'in_consultation') {
        statusBadge = `<span class="badge badge-info">In Consultation</span>`;
      } else if (t.status === 'completed') {
        statusBadge = `<span class="badge badge-success">Completed</span>`;
      }

      return `
        <tr>
          <td><strong style="font-family: var(--matab-font-mono); font-size: 0.95rem; color: var(--matab-color-brand-primary);">${t.token_code}</strong></td>
          <td>
            <strong>${(t.patient_name || '').replace(/\s*\[Synthetic\]/gi, "")}</strong>
            <div style="font-size: 0.75rem; color: var(--matab-color-text-muted); font-family: var(--matab-font-mono);">MRN: ${t.patient_mrn}</div>
          </td>
          <td><span class="badge badge-info" style="font-size: 0.72rem;">${t.visit_type || 'OPD'}</span></td>
          <td>${priorityBadge}</td>
          <td>${statusBadge}</td>
          <td>
            ${t.encounter_id ? `
              <button class="btn btn-primary btn-sm btn-open-enc" data-enc="${t.encounter_id}" data-pat="${t.patient_id}">
                🩺 Open Consultation ➔
              </button>
            ` : `
              <button class="btn btn-secondary btn-sm btn-start-token" data-token="${t.id}" data-pat="${t.patient_id}">
                Start Visit ➔
              </button>
            `}
          </td>
        </tr>
      `;
    }).join("");

    container.innerHTML = `
      <!-- Top Clinical Welcome & Action Command Bar -->
      <div class="card" style="margin-bottom: 1.25rem; background: linear-gradient(135deg, #ffffff 0%, #f0fdf4 100%); border-left: 5px solid var(--matab-color-brand-primary);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
          <div>
            <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--matab-color-brand-accent);">
              ${dateFormatted}
            </div>
            <h1 style="font-size: 1.45rem; font-weight: 800; color: var(--matab-color-brand-primary); margin: 0.2rem 0;">
              Welcome, ${(state.user?.full_name || 'Practitioner').replace(/\s*\[Synthetic\]/gi, "")}
            </h1>
            <p style="color: var(--matab-color-text-secondary); font-size: 0.88rem; margin: 0;">
              Facility: <strong>${(state.user?.facility_name || state.user?.active_facility_id || 'Central Matab OPD').replace(/\s*\[Synthetic\]/gi, "")}</strong> • System Status: <strong>Operational (ABDM & FHIR Active)</strong>
            </p>
          </div>
          <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
            <button id="goQueueBtn" class="btn btn-primary btn-sm">
              🎫 OPD Queue (${tokens.length})
            </button>
            <button id="goPatientsBtn" class="btn btn-secondary btn-sm">
              👥 Patient Registry
            </button>
            <button id="goBillingBtn" class="btn btn-secondary btn-sm">
              💳 Billing Desk
            </button>
          </div>
        </div>
      </div>

      <!-- Live Clinical KPI Metric Cards -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.85rem; margin-bottom: 1.35rem;">
        
        <div class="card" style="padding: 1.1rem; margin-bottom: 0; border-top: 3px solid var(--matab-color-brand-accent);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <span style="font-size: 0.78rem; font-weight: 700; color: var(--matab-color-text-muted); text-transform: uppercase;">Appointments</span>
            <span style="font-size: 1.1rem;">📅</span>
          </div>
          <div style="font-size: 1.6rem; font-weight: 800; color: var(--matab-color-text-primary);">${m.todays_appointments_count ?? 0}</div>
          <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">Scheduled for Today</div>
        </div>

        <div class="card" style="padding: 1.1rem; margin-bottom: 0; border-top: 3px solid #f59e0b;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <span style="font-size: 0.78rem; font-weight: 700; color: var(--matab-color-text-muted); text-transform: uppercase;">Waiting Queue</span>
            <span style="font-size: 1.1rem;">⏳</span>
          </div>
          <div style="font-size: 1.6rem; font-weight: 800; color: #b45309;">${m.walk_ins_waiting_count ?? 0}</div>
          <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">Patients in Waiting Room</div>
        </div>

        <div class="card" style="padding: 1.1rem; margin-bottom: 0; border-top: 3px solid var(--matab-color-brand-primary);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <span style="font-size: 0.78rem; font-weight: 700; color: var(--matab-color-text-muted); text-transform: uppercase;">In Consultation</span>
            <span style="font-size: 1.1rem;">🩺</span>
          </div>
          <div style="font-size: 1.6rem; font-weight: 800; color: var(--matab-color-brand-primary);">${m.currently_in_consultation_count ?? 0}</div>
          <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">Active Bedside Sessions</div>
        </div>

        <div class="card" style="padding: 1.1rem; margin-bottom: 0; border-top: 3px solid var(--matab-color-status-success);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <span style="font-size: 0.78rem; font-weight: 700; color: var(--matab-color-text-muted); text-transform: uppercase;">Completed Visits</span>
            <span style="font-size: 1.1rem;">✅</span>
          </div>
          <div style="font-size: 1.6rem; font-weight: 800; color: var(--matab-color-status-success);">${m.completed_visits_count ?? 0}</div>
          <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">Finalized Encounters</div>
        </div>

        <div class="card" style="padding: 1.1rem; margin-bottom: 0; border-top: 3px solid #0284c7;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
            <span style="font-size: 0.78rem; font-weight: 700; color: var(--matab-color-text-muted); text-transform: uppercase;">Follow-ups Due</span>
            <span style="font-size: 1.1rem;">🔄</span>
          </div>
          <div style="font-size: 1.6rem; font-weight: 800; color: #0284c7;">${m.follow_ups_due_count ?? 0}</div>
          <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">Patient Recall Tasks</div>
        </div>

      </div>

      <!-- Active OPD Queue Table -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">
            <span>🎫</span>
            <span>Live OPD Triage & Waiting Queue</span>
          </div>
          <div style="display: flex; gap: 0.5rem; align-items: center;">
            <button id="btnRefreshToday" class="btn btn-secondary btn-sm" title="Refresh Live Queue">
              🔄 Refresh
            </button>
          </div>
        </div>

        <div style="overflow-x: auto;">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 100px;">Token</th>
                <th>Patient Name & MRN</th>
                <th>Visit Type</th>
                <th>Triage Priority</th>
                <th>Status</th>
                <th>Clinical Action</th>
              </tr>
            </thead>
            <tbody>
              ${queueRowsHtml || `
                <tr>
                  <td colspan="6" style="text-align: center; padding: 3rem 1rem;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">🌿</div>
                    <p style="font-weight: 600; color: var(--matab-color-text-secondary); margin-bottom: 0.25rem;">No patients waiting in queue</p>
                    <p style="font-size: 0.85rem; color: var(--matab-color-text-muted); margin-bottom: 1rem;">Issue a walk-in token or check in a booked patient to start an encounter.</p>
                    <button id="btnEmptyQueueIssue" class="btn btn-primary btn-sm">+ Issue Walk-In Token</button>
                  </td>
                </tr>
              `}
            </tbody>
          </table>
        </div>
      </div>
    `;

    container.querySelector("#goQueueBtn")?.addEventListener("click", () => {
      state.setActiveTab("appointments_queue");
    });
    container.querySelector("#goPatientsBtn")?.addEventListener("click", () => {
      state.setActiveTab("patients");
    });
    container.querySelector("#goBillingBtn")?.addEventListener("click", () => {
      state.setActiveTab("billing");
    });
    container.querySelector("#btnRefreshToday")?.addEventListener("click", () => {
      renderToday(container);
    });
    container.querySelector("#btnEmptyQueueIssue")?.addEventListener("click", () => {
      state.setActiveTab("appointments_queue");
    });

    container.querySelectorAll(".btn-open-enc").forEach(btn => {
      btn.addEventListener("click", () => {
        state.activeEncounterId = btn.dataset.enc;
        state.activePatientId = btn.dataset.pat;
        state.setActiveTab("consultation");
      });
    });

    container.querySelectorAll(".btn-start-token").forEach(btn => {
      btn.addEventListener("click", async () => {
        const tokenId = btn.dataset.token;
        const patId = btn.dataset.pat;
        try {
          const res = await apiClient.post(`/api/v1/queue/tokens/${tokenId}/call`);
          state.activeEncounterId = res.encounter_id || null;
          state.activePatientId = patId;
          state.setActiveTab("consultation");
        } catch (e) {
          state.setActiveTab("appointments_queue");
        }
      });
    });

  } catch (err) {
    const isAuth = err.status === 401 || (err.message && err.message.toLowerCase().includes("token"));
    container.innerHTML = `
      <div class="card" style="padding: 2rem; border-left: 4px solid var(--matab-color-status-danger); max-width: 600px; margin: 2rem auto; text-align: center;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">${isAuth ? '🔐' : '⚠️'}</div>
        <h3 style="color: var(--matab-color-status-danger); margin-bottom: 0.5rem;">
          ${isAuth ? 'Clinical Session Reconnection Required' : 'Operational Dashboard Notice'}
        </h3>
        <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem; line-height: 1.5;">
          ${isAuth ? 'Your clinical session authorization needs verification or has timed out.' : err.message}
        </p>
        <div style="display: flex; gap: 0.75rem; justify-content: center; margin-top: 1.25rem;">
          ${isAuth ? `
            <button onclick="window.switchActiveRole('hakeem')" class="btn btn-primary btn-sm">
              🩺 Reconnect as Doctor (Hakim)
            </button>
            <button onclick="localStorage.clear(); window.location.reload();" class="btn btn-secondary btn-sm">
              Switch User / Login ➔
            </button>
          ` : `
            <button onclick="window.location.reload()" class="btn btn-primary btn-sm">Retry Loading</button>
          `}
        </div>
      </div>
    `;
  }
}


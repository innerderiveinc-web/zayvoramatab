/**
 * Today Operational Dashboard View — Phase 10 Clinic Operations OS
 * Displays live actionable metrics backed by authorized database records.
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export async function renderToday(container) {
  container.innerHTML = `<div class="card"><p>Loading Today Operational Dashboard...</p></div>`;

  try {
    const [todayRes, healthRes] = await Promise.all([
      apiClient.get("/api/v1/operations/today"),
      apiClient.get("/api/v1/health/ready")
    ]);

    const today = todayRes.today || { metrics: {}, inventory_warnings: {}, active_queue_tokens: [] };
    const m = today.metrics || {};
    const inv = today.inventory_warnings || {};
    const tokens = today.active_queue_tokens || [];

    const queueRowsHtml = tokens.map(t => `
      <tr>
        <td><strong><code>${t.token_code}</code></strong></td>
        <td>${t.patient_name} <small style="color: var(--matab-color-text-muted);">(${t.patient_mrn})</small></td>
        <td><span class="badge badge-info">${t.visit_type}</span></td>
        <td><strong>${t.status}</strong></td>
        <td>
          ${t.encounter_id ? `<button class="btn btn-primary btn-sm btn-open-enc" data-enc="${t.encounter_id}" data-pat="${t.patient_id}">Open Consultation ➔</button>` : '—'}
        </td>
      </tr>
    `).join("");

    container.innerHTML = `
      <div class="card" style="margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h2 style="font-size: 1.3rem; color: var(--matab-color-brand-primary); margin-bottom: 0.2rem;">
            Today's Clinic Operations — ${state.user?.full_name || 'Staff'} (${today.role_view || 'USER'})
          </h2>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.85rem;">
            Data as of <code>${today.data_as_of || 'now'}</code> • Migrations Applied: <strong>${healthRes.migrations_applied}</strong>
          </p>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button id="goQueueBtn" class="btn btn-primary btn-sm">Appointments & Queue ➔</button>
          <button id="goBillingBtn" class="btn btn-secondary btn-sm">Billing ➔</button>
        </div>
      </div>

      <!-- Actionable Today Metrics -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 0.75rem; margin-bottom: 1.25rem;">
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Today's Appointments</div>
          <div style="font-size: 1.45rem; font-weight: 700;">${m.todays_appointments_count ?? 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Walk-Ins Waiting</div>
          <div style="font-size: 1.45rem; font-weight: 700; color: var(--matab-color-brand-accent);">${m.walk_ins_waiting_count ?? 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">In Consultation</div>
          <div style="font-size: 1.45rem; font-weight: 700; color: var(--matab-color-brand-primary);">${m.currently_in_consultation_count ?? 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Completed Visits</div>
          <div style="font-size: 1.45rem; font-weight: 700; color: var(--matab-color-status-success);">${m.completed_visits_count ?? 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Payment Tasks Pending</div>
          <div style="font-size: 1.45rem; font-weight: 700;">${m.payment_tasks_awaiting_action_count ?? 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Follow-ups Due</div>
          <div style="font-size: 1.45rem; font-weight: 700;">${m.follow_ups_due_count ?? 0}</div>
        </div>
        ${inv.enabled ? `
          <div class="card" style="padding: 0.9rem;">
            <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Low Stock / Near Expiry</div>
            <div style="font-size: 1.45rem; font-weight: 700;">${inv.low_stock_count ?? 0} / ${inv.near_expiry_count ?? 0}</div>
          </div>
        ` : ''}
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Operational Errors</div>
          <div style="font-size: 1.45rem; font-weight: 700; color: ${(m.operational_errors_count || 0) > 0 ? 'var(--matab-color-status-danger)' : 'inherit'};">${m.operational_errors_count ?? 0}</div>
        </div>
      </div>

      <!-- Active OPD Queue -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Active OPD Queue & Consultation Handoff</h3>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Token</th>
              <th>Patient</th>
              <th>Type</th>
              <th>Status</th>
              <th>Clinical Handoff</th>
            </tr>
          </thead>
          <tbody>
            ${queueRowsHtml || '<tr><td colspan="5" style="text-align:center;">No active OPD queue tokens for today yet.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;

    container.querySelector("#goQueueBtn")?.addEventListener("click", () => {
      state.setActiveTab("appointments_queue");
    });
    container.querySelector("#goBillingBtn")?.addEventListener("click", () => {
      state.setActiveTab("billing");
    });

    container.querySelectorAll(".btn-open-enc").forEach(btn => {
      btn.addEventListener("click", () => {
        state.activeEncounterId = btn.dataset.enc;
        state.activePatientId = btn.dataset.pat;
        state.setActiveTab("consultation");
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color:red;">Error loading Today Dashboard: ${err.message}</p></div>`;
  }
}

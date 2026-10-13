/**
 * Phase 10 Frontend Views: Clinic Operations OS
 * - Appointments & OPD Waiting Queue Workspace (Front-Desk & Clinician)
 * - Exact-Decimal Billing, Invoicing, Payments, Receipts & Collections
 * - FEFO Dispensary Inventory Ledger & Signed-Prescription Dispensing
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

/**
 * 1. Appointments & OPD Waiting Queue Workspace
 */
export async function renderAppointmentsQueue(container) {
  container.innerHTML = `<div class="card"><p>Loading Appointments & OPD Queue...</p></div>`;
  try {
    const todayStr = new Date().toISOString().slice(0, 10);
    const [availRes, apptsRes, queueRes] = await Promise.all([
      apiClient.get(`/api/v1/scheduling/availability?practitioner_id=usr-hakeem-1&date=${todayStr}`),
      apiClient.get(`/api/v1/appointments?date=${todayStr}`),
      apiClient.get(`/api/v1/queue?queue_date=${todayStr}`)
    ]);

    const avail = availRes.availability || { slots: [] };
    const appts = apptsRes.appointments || [];
    const queue = queueRes.queue || { tokens: [] };

    const tokenRowsHtml = (queue.tokens || []).map(t => `
      <tr>
        <td><strong><code>${t.token_code}</code></strong></td>
        <td>${t.patient_name} <small style="color: var(--matab-color-text-muted);">(${t.patient_mrn})</small></td>
        <td><span class="badge badge-info">${t.visit_type}</span></td>
        <td><span class="badge ${t.priority === 'CLINICAL_URGENT' ? 'badge-danger' : 'badge-secondary'}">${t.priority}</span></td>
        <td><strong>${t.status}</strong></td>
        <td style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
          ${t.status === 'waiting' ? `<button class="btn btn-secondary btn-sm btn-call-tok" data-id="${t.id}">Call</button>` : ''}
          ${(t.status === 'waiting' || t.status === 'called') ? `<button class="btn btn-primary btn-sm btn-start-tok" data-id="${t.id}" data-enc="${t.encounter_id || ''}" data-pat="${t.patient_id}">Start Consultation</button>` : ''}
          ${t.status === 'in_consultation' ? `
            <button class="btn btn-primary btn-sm btn-open-consult" data-enc="${t.encounter_id || ''}" data-pat="${t.patient_id}">Open Workspace</button>
            <button class="btn btn-secondary btn-sm btn-complete-tok" data-id="${t.id}">Complete</button>
          ` : ''}
        </td>
      </tr>
    `).join("");

    const apptRowsHtml = appts.map(a => `
      <tr>
        <td><code>${a.start_at.slice(11, 16)} - ${a.end_at.slice(11, 16)}</code></td>
        <td><strong>${a.patient_name}</strong> (${a.patient_mrn})</td>
        <td>${a.appointment_type}</td>
        <td>${a.reason_category}</td>
        <td><span class="badge badge-info">${a.status}</span></td>
        <td>
          ${(a.status === 'booked' || a.status === 'confirmed') ? `<button class="btn btn-primary btn-sm btn-checkin-appt" data-id="${a.id}">Check In ➔ Token</button>` : ''}
        </td>
      </tr>
    `).join("");

    container.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
          <h1 style="font-size: 1.35rem; color: var(--matab-color-brand-primary);">Appointments & OPD Waiting Queue</h1>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary);">
            Backend-validated slot scheduling, walk-in token issuance, and direct handoff to Consultation Workspace.
          </p>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button id="btnIssueWalkinToken" class="btn btn-primary">+ Issue Walk-In Token</button>
          <button id="btnBookApptModal" class="btn btn-secondary">+ Book Appointment</button>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 0.75rem; margin-bottom: 1.25rem;">
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Available Slots Today</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: var(--matab-color-status-success);">${avail.available_count || 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Waiting in Queue</div>
          <div style="font-size: 1.4rem; font-weight: 700;">${queue.waiting_count || 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">In Consultation</div>
          <div style="font-size: 1.4rem; font-weight: 700; color: var(--matab-color-brand-primary);">${queue.in_consultation_count || 0}</div>
        </div>
        <div class="card" style="padding: 0.9rem;">
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Completed Today</div>
          <div style="font-size: 1.4rem; font-weight: 700;">${queue.completed_count || 0}</div>
        </div>
      </div>

      <div class="card" style="margin-bottom: 1.25rem;">
        <div class="card-header">
          <h3 class="card-title">Live OPD Token Queue (${todayStr})</h3>
          <span class="badge badge-success">Privacy-Safe Public Display Supported</span>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Token</th>
              <th>Patient</th>
              <th>Visit Type</th>
              <th>Priority</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${tokenRowsHtml || '<tr><td colspan="6" style="text-align:center;">No active tokens in queue today.</td></tr>'}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Today's Scheduled Appointments (${appts.length})</h3>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Slot Time</th>
              <th>Patient</th>
              <th>Type</th>
              <th>Category</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${apptRowsHtml || '<tr><td colspan="6" style="text-align:center;">No appointments booked for today.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;

    container.querySelector("#btnIssueWalkinToken")?.addEventListener("click", async () => {
      try {
        await apiClient.post("/api/v1/queue/tokens", {
          patient_id: "pat-syn-001",
          practitioner_id: "usr-hakeem-1",
          visit_type: "WALK_IN",
          priority: "NORMAL"
        });
        renderAppointmentsQueue(container);
      } catch (err) {
        alert(err.message);
      }
    });

    container.querySelector("#btnBookApptModal")?.addEventListener("click", async () => {
      const firstAvail = (avail.slots || []).find(s => s.is_available);
      if (!firstAvail) {
        alert("No available slot found today.");
        return;
      }
      try {
        await apiClient.post("/api/v1/appointments", {
          patient_id: "pat-syn-003",
          practitioner_id: "usr-hakeem-1",
          start_at: firstAvail.start_at,
          end_at: firstAvail.end_at,
          appointment_type: "INITIAL_CONSULTATION",
          reason_category: "GENERAL_CONSULTATION"
        });
        renderAppointmentsQueue(container);
      } catch (err) {
        alert(err.message);
      }
    });

    container.querySelectorAll(".btn-checkin-appt").forEach(btn => {
      btn.addEventListener("click", async () => {
        try {
          await apiClient.post(`/api/v1/appointments/${btn.dataset.id}/check-in`, {});
          renderAppointmentsQueue(container);
        } catch (err) {
          alert(err.message);
        }
      });
    });

    container.querySelectorAll(".btn-call-tok").forEach(btn => {
      btn.addEventListener("click", async () => {
        await apiClient.post(`/api/v1/queue/tokens/${btn.dataset.id}/call`, {});
        renderAppointmentsQueue(container);
      });
    });

    container.querySelectorAll(".btn-start-tok").forEach(btn => {
      btn.addEventListener("click", async () => {
        await apiClient.post(`/api/v1/queue/tokens/${btn.dataset.id}/start`, {});
        if (btn.dataset.enc) {
          state.activeEncounterId = btn.dataset.enc;
          state.activePatientId = btn.dataset.pat;
          state.setActiveTab("consultation");
        } else {
          renderAppointmentsQueue(container);
        }
      });
    });

    container.querySelectorAll(".btn-open-consult").forEach(btn => {
      btn.addEventListener("click", () => {
        state.activeEncounterId = btn.dataset.enc;
        state.activePatientId = btn.dataset.pat;
        state.setActiveTab("consultation");
      });
    });

    container.querySelectorAll(".btn-complete-tok").forEach(btn => {
      btn.addEventListener("click", async () => {
        await apiClient.post(`/api/v1/queue/tokens/${btn.dataset.id}/complete`, {});
        renderAppointmentsQueue(container);
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color:red;">Error loading queue: ${err.message}</p></div>`;
  }
}

/**
 * 2. Billing, Invoices, Payments & Daily Collections View
 */
export async function renderBillingView(container) {
  container.innerHTML = `<div class="card"><p>Loading Clinic Billing & Collections...</p></div>`;
  try {
    const [feesRes, invRes, repRes] = await Promise.all([
      apiClient.get("/api/v1/billing/fee-catalog"),
      apiClient.get("/api/v1/billing/invoices"),
      apiClient.get("/api/v1/billing/reports/collections")
    ]);

    const fees = feesRes.fee_catalog || [];
    const invoices = invRes.invoices || [];
    const report = repRes.collections_report || {};

    const invRowsHtml = invoices.map(i => `
      <tr>
        <td><strong><code>${i.invoice_number}</code></strong></td>
        <td>${i.patient_name} (${i.patient_mrn})</td>
        <td>${i.currency} ${i.total_decimal}</td>
        <td>${i.currency} ${i.paid_decimal}</td>
        <td><strong>${i.currency} ${i.balance_due_decimal}</strong></td>
        <td><span class="badge ${i.status === 'PAID' ? 'badge-success' : 'badge-info'}">${i.status}</span></td>
        <td style="display:flex; gap:0.35rem;">
          ${i.status === 'DRAFT' ? `<button class="btn btn-secondary btn-sm btn-fin-inv" data-id="${i.id}">Finalize</button>` : ''}
          ${(i.status === 'FINALIZED' || i.status === 'PARTIALLY_PAID') ? `<button class="btn btn-primary btn-sm btn-pay-inv" data-id="${i.id}" data-bal="${i.balance_due_decimal}">Record Cash Payment</button>` : ''}
        </td>
      </tr>
    `).join("");

    container.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
        <div>
          <h1 style="font-size:1.35rem; color:var(--matab-color-brand-primary);">Clinic Billing, Receipts & Reconciliation</h1>
          <p style="font-size:0.85rem; color:var(--matab-color-text-secondary);">
            Exact-decimal invoicing, immutable finalized snapshots, and auditable payment reconciliation.
          </p>
        </div>
        <button id="btnCreateQuickInvoice" class="btn btn-primary">+ Create Consultation Invoice (INR 300.00)</button>
      </div>

      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:0.75rem; margin-bottom:1.25rem;">
        <div class="card" style="padding:0.9rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-muted);">Gross Collections</div>
          <div style="font-size:1.3rem; font-weight:700; color:var(--matab-color-status-success);">INR ${report.gross_collections_decimal || '0.00'}</div>
        </div>
        <div class="card" style="padding:0.9rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-muted);">Total Refunds</div>
          <div style="font-size:1.3rem; font-weight:700;">INR ${report.total_refunds_decimal || '0.00'}</div>
        </div>
        <div class="card" style="padding:0.9rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-muted);">Net Collections</div>
          <div style="font-size:1.3rem; font-weight:700; color:var(--matab-color-brand-primary);">INR ${report.net_collections_decimal || '0.00'}</div>
        </div>
        <div class="card" style="padding:0.9rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-muted);">Outstanding Balance</div>
          <div style="font-size:1.3rem; font-weight:700;">INR ${report.outstanding_balance_decimal || '0.00'}</div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Invoices (${invoices.length})</h3>
          <span class="badge badge-info">Fee Catalog Items: ${fees.length}</span>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Invoice #</th>
              <th>Patient</th>
              <th>Total</th>
              <th>Paid</th>
              <th>Balance Due</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${invRowsHtml || '<tr><td colspan="7" style="text-align:center;">No invoices created yet.</td></tr>'}
          </tbody>
        </table>
      </div>
    `;

    container.querySelector("#btnCreateQuickInvoice")?.addEventListener("click", async () => {
      try {
        await apiClient.post("/api/v1/billing/invoices", {
          patient_id: "pat-syn-001",
          auto_finalize: true,
          lines: [
            {
              description: "Initial Unani Consultation (Matab OPD)",
              quantity_decimal: "1.00",
              unit_price_decimal: "300.00"
            }
          ]
        });
        renderBillingView(container);
      } catch (err) {
        alert(err.message);
      }
    });

    container.querySelectorAll(".btn-fin-inv").forEach(btn => {
      btn.addEventListener("click", async () => {
        await apiClient.post(`/api/v1/billing/invoices/${btn.dataset.id}/finalize`, {});
        renderBillingView(container);
      });
    });

    container.querySelectorAll(".btn-pay-inv").forEach(btn => {
      btn.addEventListener("click", async () => {
        await apiClient.post("/api/v1/billing/payments", {
          invoice_id: btn.dataset.id,
          amount_decimal: btn.dataset.bal,
          payment_method: "CASH",
          provider_status: "POSTED"
        });
        renderBillingView(container);
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color:red;">Error loading billing: ${err.message}</p></div>`;
  }
}

/**
 * 3. Pharmacy / Dispensary Inventory & Signed-Prescription Dispensing View
 */
export async function renderInventoryView(container) {
  container.innerHTML = `<div class="card"><p>Loading Dispensary Inventory & FEFO Batches...</p></div>`;
  try {
    const [stockRes, batchesRes] = await Promise.all([
      apiClient.get("/api/v1/inventory/stock"),
      apiClient.get("/api/v1/inventory/batches")
    ]);

    const stock = stockRes.stock || { items: [] };
    const batches = batchesRes.batches || [];

    const itemRowsHtml = (stock.items || []).map(it => `
      <tr>
        <td><code>${it.sku}</code></td>
        <td><strong>${it.name}</strong></td>
        <td>${it.dosage_form}</td>
        <td><strong>${it.dispensable_quantity_decimal} ${it.unit}</strong></td>
        <td>${it.fefo_suggested_batch_number ? `<code>${it.fefo_suggested_batch_number}</code> (Exp: ${it.fefo_suggested_expiry})` : '—'}</td>
        <td><span class="badge ${it.is_low_stock ? 'badge-danger' : 'badge-success'}">${it.is_low_stock ? 'LOW STOCK' : 'ADEQUATE'}</span></td>
      </tr>
    `).join("");

    const batchRowsHtml = batches.map(b => `
      <tr>
        <td><code>${b.batch_number}</code></td>
        <td>${b.item_name}</td>
        <td>${b.expiry_date}</td>
        <td>${b.quantity_on_hand_decimal} ${b.item_unit}</td>
        <td><span class="badge ${b.is_dispensable ? 'badge-success' : 'badge-danger'}">${b.status}${b.is_expired ? ' (EXPIRED)' : ''}</span></td>
      </tr>
    `).join("");

    container.innerHTML = `
      <div style="margin-bottom: 1rem;">
        <h1 style="font-size: 1.35rem; color: var(--matab-color-brand-primary);">Dispensary Inventory & FEFO Batch Ledger</h1>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary);">
          ${stock.compliance_disclaimer || ''}
        </p>
      </div>

      <div class="card" style="margin-bottom: 1.25rem;">
        <div class="card-header">
          <h3 class="card-title">Stock on Hand & FEFO Suggestions</h3>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Item Name</th>
              <th>Form</th>
              <th>Dispensable Qty</th>
              <th>FEFO Suggested Batch</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>${itemRowsHtml}</tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Batch / Lot Traceability (${batches.length})</h3>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Batch #</th>
              <th>Medicine</th>
              <th>Expiry Date</th>
              <th>On Hand</th>
              <th>Dispensability</th>
            </tr>
          </thead>
          <tbody>${batchRowsHtml}</tbody>
        </table>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color:red;">Inventory unavailable: ${err.message}</p></div>`;
  }
}

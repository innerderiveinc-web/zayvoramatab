/**
 * Care Continuity, Follow-up Work Queue, Patient Communications & Outcome Tracking View (Phase 9)
 * Separates Follow-up Plans, Operational Tasks, Appointments, Consent-Governed Communications,
 * and Non-Causal Longitudinal Outcomes / Adverse Effects.
 */

import { apiClient } from "../../../../../packages/api-client/client.js";
import { state } from "../state.js";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export async function renderFollowups(container) {
  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.25rem; flex-wrap:wrap; gap:0.75rem;">
      <div>
        <h1 style="font-size:1.4rem; color:var(--matab-color-brand-primary); margin:0;">
          Care Continuity, Follow-ups &amp; Outcomes
        </h1>
        <p style="color:var(--matab-color-text-secondary); font-size:0.88rem; margin:0.25rem 0 0 0;">
          Versioned Follow-up Plans &bull; Outreach Work Queue &bull; Consent-Governed Reminders &bull; Non-Causal Outcome Trends &bull; Adverse Effect Surveillance
        </p>
      </div>
      <div style="display:flex; gap:0.5rem;">
        <span class="badge badge-success">clinical.care_continuity: ACTIVE</span>
        <span class="badge badge-info">operations.patient_communications: SANDBOX</span>
      </div>
    </div>
    <div id="continuityRoot">Loading care continuity workspace...</div>
  `;

  const root = container.querySelector("#continuityRoot");
  await loadContinuityDashboard(root);
}

async function loadContinuityDashboard(root) {
  try {
    const [queueRes, analyticsRes, templatesRes, outcomeDefsRes] = await Promise.all([
      apiClient.get("/api/v1/follow-up/queue"),
      apiClient.get("/api/v1/follow-up/analytics"),
      apiClient.get("/api/v1/patient-communications/templates"),
      apiClient.get("/api/v1/outcomes/definitions")
    ]);

    const queueItems = queueRes.queue_items || [];
    const redacted = Boolean(queueRes.clinical_details_redacted);
    const urgentAdrs = queueRes.pending_adverse_effect_reviews || [];
    const analytics = analyticsRes.analytics || {};
    const templates = (templatesRes.templates || []).filter((t) => t.approval_status === "approved");
    const outcomeDefs = outcomeDefsRes.definitions || [];

    root.innerHTML = `
      ${redacted ? `
        <div style="background:#eff6ff; border:1px solid #93c5fd; color:#1e3a8a; padding:0.75rem 1rem; border-radius:6px; margin-bottom:1rem; font-size:0.85rem;">
          <strong>Privacy Filter Active (Front-Desk / Reception Role):</strong> Clinical diagnoses, problem lists, and medication details are redacted. Showing minimum-necessary scheduling and outreach fields only.
        </div>
      ` : ""}

      <!-- Analytics Summary Strip -->
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:0.75rem; margin-bottom:1.25rem;">
        <div class="card" style="padding:0.85rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-secondary); text-transform:uppercase;">Open Follow-up Tasks</div>
          <div style="font-size:1.5rem; font-weight:700; color:var(--matab-color-brand-primary);">${queueItems.length}</div>
        </div>
        <div class="card" style="padding:0.85rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-secondary); text-transform:uppercase;">Completed Tasks</div>
          <div style="font-size:1.5rem; font-weight:700; color:#15803d;">${(analytics.tasks_by_status || {}).completed || 0}</div>
        </div>
        <div class="card" style="padding:0.85rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-secondary); text-transform:uppercase;">Messages Sent / Suppressed</div>
          <div style="font-size:1.5rem; font-weight:700;">
            ${(analytics.messages_by_status || {}).sent || 0} / <span style="color:#b45309;">${(analytics.messages_by_status || {}).suppressed || 0}</span>
          </div>
        </div>
        <div class="card" style="padding:0.85rem;">
          <div style="font-size:0.75rem; color:var(--matab-color-text-secondary); text-transform:uppercase;">Pending Adverse Effects</div>
          <div style="font-size:1.5rem; font-weight:700; color:${urgentAdrs.length ? "#b91c1c" : "#374151"};">${urgentAdrs.length}</div>
        </div>
      </div>

      ${urgentAdrs.length > 0 ? `
        <div class="card" style="border-left:4px solid #dc2626; margin-bottom:1.25rem; padding:1rem;">
          <h3 style="margin:0 0 0.5rem 0; color:#dc2626; font-size:1rem;">Urgent Adverse Effect Escalations Requiring Clinical Review</h3>
          <div style="display:flex; flex-direction:column; gap:0.5rem;">
            ${urgentAdrs.map((adr) => `
              <div style="display:flex; justify-content:space-between; align-items:center; background:#fef2f2; padding:0.6rem 0.85rem; border-radius:4px;">
                <div>
                  <strong>${escapeHtml(adr.patient_name)} (${escapeHtml(adr.patient_mrn)})</strong> &mdash;
                  Suspected: <code>${escapeHtml(adr.suspected_medication)}</code> |
                  Severity: <span class="badge badge-danger">${escapeHtml(adr.patient_reported_severity)}</span>
                  <div style="font-size:0.82rem; color:#7f1d1d;">${escapeHtml(adr.patient_description)} (Causality: ${escapeHtml(adr.causality_assessment)})</div>
                </div>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ""}

      <div style="display:grid; grid-template-columns: 1.5fr 1fr; gap:1.25rem; align-items:start;">
        <!-- Left Column: Follow-up Work Queue -->
        <div class="card" style="padding:1rem;">
          <h3 style="margin:0 0 0.75rem 0; font-size:1.05rem;">Follow-up &amp; Missed-Visit Outreach Queue</h3>
          ${queueItems.length === 0 ? `
            <p style="color:var(--matab-color-text-secondary); font-size:0.9rem;">No open follow-up tasks in queue.</p>
          ` : `
            <div style="display:flex; flex-direction:column; gap:0.75rem;">
              ${queueItems.map((item) => `
                <div style="border:1px solid var(--matab-color-border); border-radius:6px; padding:0.85rem;">
                  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.35rem;">
                    <div>
                      <strong>${escapeHtml(item.patient_name)}</strong>
                      <span style="font-size:0.8rem; color:var(--matab-color-text-secondary);">(${escapeHtml(item.patient_mrn)} &bull; ${escapeHtml(item.patient_phone)})</span>
                    </div>
                    <div style="display:flex; gap:0.35rem;">
                      <span class="badge ${item.priority === "urgent" ? "badge-danger" : "badge-warning"}">${escapeHtml(item.priority)}</span>
                      <span class="badge badge-info">${escapeHtml(item.status)}</span>
                    </div>
                  </div>
                  <div style="font-size:0.85rem; margin-bottom:0.35rem;">
                    <strong>Due:</strong> ${escapeHtml(item.due_at)} |
                    <strong>Channel:</strong> ${escapeHtml(item.planned_channel)} |
                    <strong>Contact Attempts:</strong> ${item.contact_attempts_count || 0}
                  </div>
                  <div style="font-size:0.83rem; color:var(--matab-color-text-secondary); margin-bottom:0.6rem;">
                    ${escapeHtml(item.clinical_context_summary || item.purpose)}
                  </div>
                  <div style="display:flex; gap:0.4rem; flex-wrap:wrap;">
                    <button class="btn btn-secondary btn-sm" data-action="log-attempt" data-task-id="${escapeHtml(item.id)}">
                      Log Call Attempt
                    </button>
                    <button class="btn btn-secondary btn-sm" data-action="send-reminder" data-task-id="${escapeHtml(item.id)}" data-patient-id="${escapeHtml(item.patient_id)}" data-patient-name="${escapeHtml(item.patient_name)}" data-due="${escapeHtml(item.due_at)}">
                      Send Governed Reminder (Does Not Complete Task)
                    </button>
                    <button class="btn btn-secondary btn-sm" data-action="mark-unreachable" data-task-id="${escapeHtml(item.id)}">
                      Mark Unable to Reach
                    </button>
                    <button class="btn btn-primary btn-sm" data-action="inspect-patient" data-patient-id="${escapeHtml(item.patient_id)}">
                      Continuity &amp; Outcomes
                    </button>
                  </div>
                </div>
              `).join("")}
            </div>
          `}
        </div>

        <!-- Right Column: Quick Continuity Actions & Patient Inspector -->
        <div style="display:flex; flex-direction:column; gap:1rem;">
          <div class="card" style="padding:1rem;">
            <h3 style="margin:0 0 0.75rem 0; font-size:1rem;">Create Follow-up Task / Outreach</h3>
            <form id="newFollowupTaskForm" style="display:flex; flex-direction:column; gap:0.6rem;">
              <input type="text" name="patient_id" placeholder="Patient ID (e.g. pat-synth-1)" value="pat-synth-1" class="form-input" required />
              <input type="date" name="due_at" value="2026-10-25" class="form-input" required />
              <input type="text" name="purpose" placeholder="Follow-up purpose (e.g. 2-week Dyspepsia review)" class="form-input" required />
              <select name="priority" class="form-input">
                <option value="routine">Routine Priority</option>
                <option value="high">High Priority</option>
                <option value="urgent">Urgent Priority</option>
              </select>
              <button type="submit" class="btn btn-primary">Create Follow-up Task</button>
            </form>
          </div>

          <div class="card" style="padding:1rem;" id="patientContinuityInspector">
            <h3 style="margin:0 0 0.5rem 0; font-size:1rem;">Patient Continuity &amp; Non-Causal Outcome Trends</h3>
            <p style="font-size:0.83rem; color:var(--matab-color-text-secondary);">
              Select "Continuity &amp; Outcomes" on any queue item to inspect longitudinal trends, communication consent, and adverse effect reports.
            </p>
          </div>
        </div>
      </div>
    `;

    // Bind form & button handlers
    const form = root.querySelector("#newFollowupTaskForm");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        try {
          await apiClient.post("/api/v1/follow-up/tasks", {
            patient_id: fd.get("patient_id"),
            due_at: fd.get("due_at"),
            purpose: fd.get("purpose"),
            priority: fd.get("priority")
          });
          await loadContinuityDashboard(root);
        } catch (err) {
          alert(err.message || "Failed to create follow-up task");
        }
      });
    }

    root.querySelectorAll("[data-action='log-attempt']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const taskId = btn.getAttribute("data-task-id");
        try {
          await apiClient.post(`/api/v1/follow-up/tasks/${taskId}/contact-attempts`, {
            channel: "phone_call",
            attempt_outcome: "no_answer",
            notes: "Front-desk outreach call attempted; no answer."
          });
          await loadContinuityDashboard(root);
        } catch (err) {
          alert(err.message || "Failed to log contact attempt");
        }
      });
    });

    root.querySelectorAll("[data-action='send-reminder']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const taskId = btn.getAttribute("data-task-id");
        const patientId = btn.getAttribute("data-patient-id");
        const patientName = btn.getAttribute("data-patient-name");
        const due = btn.getAttribute("data-due");
        const tplCode = templates.length ? templates[0].template_code : "TPL-APPT-REMINDER-EN";
        try {
          const res = await apiClient.post("/api/v1/patient-communications/send", {
            patient_id: patientId,
            task_id: taskId,
            template_code: tplCode,
            placeholders: {
              patient_name: patientName,
              facility_name: "Central Matab OPD",
              appointment_date: due,
              clinic_phone: "+91-9800000001"
            }
          });
          alert(`Message status: ${res.message.status}${res.message.suppression_reason ? " (" + res.message.suppression_reason + ")" : ""}. Task remains open.`);
          await loadContinuityDashboard(root);
        } catch (err) {
          alert(err.message || "Failed to dispatch reminder");
        }
      });
    });

    root.querySelectorAll("[data-action='mark-unreachable']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const taskId = btn.getAttribute("data-task-id");
        try {
          await apiClient.post(`/api/v1/follow-up/tasks/${taskId}/transition`, {
            to_status: "unable_to_reach",
            reason: "Multiple outreach attempts unanswered"
          });
          await loadContinuityDashboard(root);
        } catch (err) {
          alert(err.message || "Cannot mark unable_to_reach without documented contact attempts");
        }
      });
    });

    root.querySelectorAll("[data-action='inspect-patient']").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const patientId = btn.getAttribute("data-patient-id");
        const inspector = root.querySelector("#patientContinuityInspector");
        if (inspector) {
          await renderPatientContinuityPanel(inspector, patientId, outcomeDefs);
        }
      });
    });
  } catch (err) {
    root.innerHTML = `<div class="card" style="color:#b91c1c; padding:1rem;">Error loading continuity dashboard: ${escapeHtml(err.message)}</div>`;
  }
}

async function renderPatientContinuityPanel(panel, patientId, outcomeDefs) {
  panel.innerHTML = `Loading continuity summary for ${escapeHtml(patientId)}...`;
  try {
    const res = await apiClient.get(`/api/v1/patients/${patientId}/follow-up-summary`);
    const summary = res.continuity_summary;
    const prefs = summary.communication_preferences || {};
    const outcomes = summary.outcomes_summary || {};
    const series = outcomes.series || [];

    panel.innerHTML = `
      <h3 style="margin:0 0 0.5rem 0; font-size:1rem;">
        Continuity Summary: ${escapeHtml(summary.patient.full_name)} (${escapeHtml(summary.patient.mrn)})
      </h3>
      <div style="font-size:0.82rem; margin-bottom:0.75rem; background:#f8fafc; padding:0.6rem; border-radius:4px;">
        <strong>Communication Consent:</strong>
        Channel: <code>${escapeHtml(prefs.preferred_channel)}</code> |
        Opt-Out: <strong>${prefs.opt_out_status ? "OPTED OUT (Automated Blocked)" : "Active Opt-In"}</strong> |
        Quiet Hours: ${escapeHtml(prefs.quiet_hours_start)}&ndash;${escapeHtml(prefs.quiet_hours_end)}
      </div>

      ${summary.clinical_details_redacted ? `
        <div style="font-size:0.82rem; color:#1e3a8a;">Clinical outcome series redacted for current role.</div>
      ` : `
        <div style="margin-bottom:0.75rem;">
          <strong style="font-size:0.85rem;">Longitudinal Outcome Trends:</strong>
          <div style="font-size:0.75rem; color:#64748b; margin-bottom:0.4rem;">
            ${escapeHtml(outcomes.causal_attribution_disclaimer || "Observational trend only; does not establish causal treatment efficacy.")}
          </div>
          ${series.length === 0 ? `<div style="font-size:0.82rem; color:#64748b;">No outcomes recorded yet.</div>` : series.map((s) => `
            <div style="border:1px solid #e2e8f0; border-radius:4px; padding:0.5rem; margin-bottom:0.4rem; font-size:0.82rem;">
              <strong>${escapeHtml(s.definition_name)}</strong>:
              <span class="badge badge-info">${escapeHtml(s.trend_status)}</span>
              ${s.delta !== null && s.delta !== undefined ? `(Delta: ${s.delta} ${escapeHtml(s.unit || "")})` : ""}
              <div style="font-size:0.75rem; color:#475569;">${escapeHtml(s.comparability_reason)}</div>
            </div>
          `).join("")}
        </div>
      `}
    `;
  } catch (err) {
    panel.innerHTML = `<div style="color:#b91c1c; font-size:0.85rem;">Failed to load summary: ${escapeHtml(err.message)}</div>`;
  }
}

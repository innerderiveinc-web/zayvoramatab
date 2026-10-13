/**
 * Phase 11 View: Enterprise Multi-Branch, Multi-Doctor & Hospital Administration Workspace
 * Separate role-protected administration area backed by real Phase 11 APIs.
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export async function renderEnterpriseAdmin(container) {
  const user = state.user;
  const activeFacId = user?.active_facility_id || "fac-central-opd";
  const orgId = user?.organization_id || "org-matab-default";

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 1rem;">
      <div>
        <h2 style="margin:0;">🏛️ Enterprise Multi-Branch & Hospital Administration</h2>
        <div style="font-size:0.85rem; color:#4b5563;">
          Organization Hierarchy, Branch Lifecycle, Scoped Staff Assignments, Inter-Facility Transfers, Layered Config & Integrations
        </div>
      </div>
      <div style="display:flex; gap:0.5rem;">
        <button id="btnRunMigrationDryRun" class="btn btn-secondary btn-sm">🔍 Single-Clinic Migration Check</button>
        <button id="btnRefreshEnterprise" class="btn btn-primary btn-sm">🔄 Refresh</button>
      </div>
    </div>

    <div id="enterpriseAlertBox" style="display:none; margin-bottom:1rem;" class="card"></div>

    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1rem;">
      <!-- 1. Organization Overview & Continuity Policy -->
      <div class="card">
        <h3 style="margin-top:0;">1. Organization & Continuity Policy</h3>
        <div id="orgOverviewPanel">Loading organization...</div>
      </div>

      <!-- 2. Facilities, Branches & Activation Health -->
      <div class="card">
        <h3 style="margin-top:0;">2. Facilities, Branches & Departments</h3>
        <div id="facilitiesPanel">Loading facilities...</div>
      </div>

      <!-- 3. Scoped Staff & Practitioner Assignments -->
      <div class="card">
        <h3 style="margin-top:0;">3. Scoped Staff Assignments</h3>
        <div id="assignmentsPanel">Loading assignments...</div>
      </div>

      <!-- 4. Inter-Facility Transfer Work Queue -->
      <div class="card">
        <h3 style="margin-top:0;">4. Inter-Facility Transfers & Referrals</h3>
        <div id="transfersPanel">Loading transfers...</div>
      </div>

      <!-- 5. Layered Configuration & Module Entitlements -->
      <div class="card">
        <h3 style="margin-top:0;">5. Inherited Config & Module Entitlements</h3>
        <div id="configModulesPanel">Loading configuration & modules...</div>
      </div>

      <!-- 6. Hospital Integrations & Enterprise Audit -->
      <div class="card">
        <h3 style="margin-top:0;">6. Hospital Integrations & Audit Trail</h3>
        <div id="integrationsAuditPanel">Loading integrations & audit...</div>
      </div>
    </div>
  `;

  const alertBox = container.querySelector("#enterpriseAlertBox");
  function showBanner(msg, isError = false) {
    alertBox.style.display = "block";
    alertBox.style.borderLeft = isError ? "4px solid #dc2626" : "4px solid #059669";
    alertBox.innerHTML = `<strong>${isError ? "⚠️ Alert:" : "✅ Status:"}</strong> ${msg}`;
  }

  async function loadAll() {
    try {
      const [orgRes, facRes, assignRes, trfRes, cfgRes, modRes, intgRes, audRes] = await Promise.all([
        apiClient.get(`/api/v1/organizations/${orgId}`),
        apiClient.get("/api/v1/facilities"),
        apiClient.get(`/api/v1/facilities/${activeFacId}/assignments`).catch(() => ({ assignments: [] })),
        apiClient.get("/api/v1/transfers").catch(() => ({ transfers: [] })),
        apiClient.get(`/api/v1/facilities/${activeFacId}/configuration`),
        apiClient.get(`/api/v1/facilities/${activeFacId}/modules`),
        apiClient.get("/api/v1/integrations/connectors").catch(() => ({ connectors: [] })),
        apiClient.get("/api/v1/admin/audit-events").catch(() => ({ audit_events: [] })),
      ]);

      const org = orgRes.organization;
      container.querySelector("#orgOverviewPanel").innerHTML = `
        <div style="font-size:0.9rem; line-height:1.6;">
          <div><strong>Name:</strong> ${org.name} (<code>${org.code}</code>)</div>
          <div><strong>Lifecycle Status:</strong> <span class="badge badge-success">${org.lifecycle_status.toUpperCase()}</span></div>
          <div><strong>Deployment Mode:</strong> <code>${org.deployment_mode}</code></div>
          <div><strong>Cross-Facility Continuity Policy:</strong> <code>${org.cross_facility_continuity_policy}</code></div>
          <div><strong>Org Admin Clinical Note Access:</strong> <code>${org.org_admin_clinical_note_access ? "ENABLED" : "RESTRICTED (Default Safe)"}</code></div>
          <div><strong>Timezone:</strong> ${org.timezone} | <strong>Branches:</strong> ${org.facilities_count}</div>
        </div>
      `;

      const facilities = facRes.facilities || [];
      container.querySelector("#facilitiesPanel").innerHTML = `
        <div style="font-size:0.85rem;">
          ${facilities.map(f => `
            <div style="padding:0.5rem; border-bottom:1px solid #e5e7eb;">
              <div style="display:flex; justify-content:space-between;">
                <strong>${f.name} (<code>${f.code}</code>)</strong>
                <span class="badge">${(f.lifecycle_status || "active").toUpperCase()}</span>
              </div>
              <div style="color:#6b7280;">Type: ${f.facility_type || "MATAB"} | Departments: ${(f.departments || []).length}</div>
              <div style="margin-top:0.35rem; display:flex; gap:0.4rem;">
                <button class="btn btn-secondary btn-sm btn-check-fac" data-fac="${f.id}">Health Check</button>
              </div>
            </div>
          `).join("")}
        </div>
      `;

      container.querySelectorAll(".btn-check-fac").forEach(btn => {
        btn.addEventListener("click", async () => {
          const fid = btn.getAttribute("data-fac");
          try {
            const hc = await apiClient.get(`/api/v1/facilities/${fid}/activation-check`);
            showBanner(`Facility ${fid} Activation Readiness: ${hc.health_check.ready_for_activation ? "READY" : "BLOCKED"} (${hc.health_check.checks.map(c => `${c.check}=${c.passed}`).join(", ")})`);
          } catch (e) {
            showBanner(e.message, true);
          }
        });
      });

      const assignments = assignRes.assignments || [];
      container.querySelector("#assignmentsPanel").innerHTML = `
        <div style="font-size:0.85rem;">
          <div><strong>Active Scoped Assignments (${activeFacId}):</strong> ${assignments.length}</div>
          ${assignments.slice(0, 6).map(a => `
            <div style="padding:0.4rem 0; border-bottom:1px solid #f3f4f6;">
              <strong>${a.full_name}</strong> — <code>${a.role_code}</code> (${a.assignment_type})
              <span class="badge">${a.status}</span>
            </div>
          `).join("") || `<div style="color:#6b7280; margin-top:0.4rem;">Using organization-wide role memberships.</div>`}
        </div>
      `;

      const transfers = trfRes.transfers || [];
      container.querySelector("#transfersPanel").innerHTML = `
        <div style="font-size:0.85rem;">
          <div><strong>Transfer Work Queue:</strong> ${transfers.length} record(s)</div>
          ${transfers.slice(0, 5).map(t => `
            <div style="padding:0.4rem 0; border-bottom:1px solid #f3f4f6;">
              <div><strong>${t.patient_name}</strong> (${t.originating_facility_name} → ${t.receiving_facility_name})</div>
              <div>Urgency: <code>${t.urgency}</code> | Status: <strong>${t.status.toUpperCase()}</strong></div>
            </div>
          `).join("") || `<div style="color:#6b7280; margin-top:0.4rem;">No pending inter-facility transfers.</div>`}
        </div>
      `;

      const cfg = cfgRes.configuration;
      const mods = modRes.modules || [];
      container.querySelector("#configModulesPanel").innerHTML = `
        <div style="font-size:0.85rem;">
          <div><strong>Config Version:</strong> v${cfg.current_version} | <strong>PIN Sign-off Enforced:</strong> <code>${cfg.effective_configuration.require_clinician_pin_for_signoff}</code></div>
          <div style="margin-top:0.5rem;"><strong>Facility Module Entitlements:</strong></div>
          <div style="display:flex; flex-wrap:wrap; gap:0.35rem; margin-top:0.35rem;">
            ${mods.map(m => `
              <span class="badge ${m.is_enabled ? "badge-success" : ""}" title="Prerequisites: ${(m.prerequisites || []).join(", ") || "none"}">
                ${m.module_key}: ${m.is_enabled ? "ON" : "OFF"}
              </span>
            `).join("")}
          </div>
        </div>
      `;

      const connectors = intgRes.connectors || [];
      const audits = audRes.audit_events || [];
      container.querySelector("#integrationsAuditPanel").innerHTML = `
        <div style="font-size:0.85rem;">
          <div><strong>Integration Connectors:</strong></div>
          ${connectors.map(c => `
            <div style="padding:0.3rem 0; border-bottom:1px solid #f3f4f6;">
              <strong>${c.name}</strong> (<code>${c.connector_type}</code>) — <span class="badge">${c.lifecycle_state}</span>
              <div style="color:#6b7280; font-size:0.78rem;">Secret Ref: <code>${c.secret_ref_uri || "None"}</code></div>
            </div>
          `).join("")}
          <div style="margin-top:0.6rem;"><strong>Recent Enterprise Audit Events (${audits.length}):</strong></div>
          ${audits.slice(0, 4).map(ev => `
            <div style="font-size:0.78rem; color:#374151; padding:0.2rem 0;">
              [${ev.outcome}] <code>${ev.action_type}</code> on ${ev.target_entity_type} (${ev.actor_username || "system"})
            </div>
          `).join("")}
        </div>
      `;
    } catch (err) {
      showBanner(err.message || "Failed to load enterprise administration data", true);
    }
  }

  container.querySelector("#btnRefreshEnterprise").addEventListener("click", loadAll);
  container.querySelector("#btnRunMigrationDryRun").addEventListener("click", async () => {
    try {
      const res = await apiClient.post("/api/v1/admin/single-clinic-migration", {
        default_facility_id: activeFacId,
        mode: "DRY_RUN",
      });
      const mig = res.migration;
      showBanner(
        `Single-Clinic Migration Dry-Run: ${mig.status} | Counts Reconciled: ${mig.counts_reconciled} | Orphans: ${mig.orphans_detected.length}`
      );
    } catch (e) {
      showBanner(e.message, true);
    }
  });

  await loadAll();
}

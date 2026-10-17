/**
 * Phase 11 View: Enterprise Multi-Branch, Multi-Doctor & Hospital Administration Workspace
 * Separate role-protected administration area backed by real Phase 11 APIs.
 */

import { state } from "../state.js";
import { apiClient } from "/packages/api-client/client.js";


export async function renderEnterpriseAdmin(container) {
  const user = state.user;
  const activeFacId = user?.active_facility_id || "fac-central-opd";
  const orgId = user?.organization_id || "org-matab-default";

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem;">
      <div>
        <h2 style="margin:0;">🏛️ Enterprise Multi-Branch & Hospital Administration</h2>
        <div style="font-size:0.85rem; color:#4b5563;">
          Organization Hierarchy, Branch Lifecycle, Scoped Staff Assignments, Inter-Facility Transfers, Layered Config & Integrations
        </div>
      </div>
      <div style="display:flex; gap:0.5rem; flex-wrap: wrap;">
        <button id="btnOpenAddStaffModal" class="btn btn-primary btn-sm">➕ Add Doctor / Staff Member</button>
        <button id="btnRunMigrationDryRun" class="btn btn-secondary btn-sm">🔍 Migration Check</button>
        <button id="btnRefreshEnterprise" class="btn btn-secondary btn-sm">🔄 Refresh</button>
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
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
          <h3 style="margin:0;">3. Clinical Staff & User Accounts</h3>
          <button id="btnCardAddStaff" class="btn btn-primary btn-sm" style="font-size:0.75rem; padding:0.25rem 0.55rem;">➕ Add Staff</button>
        </div>
        <div id="assignmentsPanel">Loading staff accounts...</div>
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

    <div id="staffModalContainer"></div>
  `;

  const alertBox = container.querySelector("#enterpriseAlertBox");
  function showBanner(msg, isError = false) {
    alertBox.style.display = "block";
    alertBox.style.borderLeft = isError ? "4px solid #dc2626" : "4px solid #059669";
    alertBox.innerHTML = `<strong>${isError ? "⚠️ Alert:" : "✅ Status:"}</strong> ${msg}`;
  }

  let cachedFacilities = [];

  async function loadAll() {
    try {
      const [orgRes, facRes, assignRes, trfRes, cfgRes, modRes, intgRes, audRes, usersRes] = await Promise.all([
        apiClient.get(`/api/v1/organizations/${orgId}`),
        apiClient.get("/api/v1/facilities"),
        apiClient.get(`/api/v1/facilities/${activeFacId}/assignments`).catch(() => ({ assignments: [] })),
        apiClient.get("/api/v1/transfers").catch(() => ({ transfers: [] })),
        apiClient.get(`/api/v1/facilities/${activeFacId}/configuration`),
        apiClient.get(`/api/v1/facilities/${activeFacId}/modules`),
        apiClient.get("/api/v1/integrations/connectors").catch(() => ({ connectors: [] })),
        apiClient.get("/api/v1/admin/audit-events").catch(() => ({ audit_events: [] })),
        apiClient.get("/api/v1/users").catch(() => ({ users: [] }))
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
      cachedFacilities = facilities;
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

      const users = usersRes.users || [];
      const roleIcons = {
        PRACTITIONER: "🩺",
        RECEPTIONIST: "📋",
        PHARMACIST: "💊",
        CASHIER: "💳",
        ORG_ADMIN: "🏛️",
        INVENTORY_MANAGER: "📦",
        READ_ONLY_AUDITOR: "🔍"
      };

      container.querySelector("#assignmentsPanel").innerHTML = `
        <div style="font-size:0.85rem;">
          <div style="display:flex; justify-content:space-between; margin-bottom:0.4rem;">
            <strong>Active Staff Accounts (${users.length}):</strong>
            <span style="font-size:0.75rem; color:#6b7280;">Facility: ${activeFacId}</span>
          </div>
          <div style="max-height: 240px; overflow-y: auto;">
            ${users.map(u => `
              <div style="padding:0.45rem 0.2rem; border-bottom:1px solid #f3f4f6; display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <strong>${roleIcons[u.role_code] || "👤"} ${u.full_name}</strong>
                  <div style="color:#6b7280; font-size:0.75rem;"><code>${u.username}</code> ${u.email ? '• ' + u.email : ''}</div>
                </div>
                <span class="badge ${u.role_code === 'PRACTITIONER' ? 'badge-success' : (u.role_code === 'ORG_ADMIN' ? 'badge-info' : 'badge-secondary')}">
                  ${u.role_code || 'STAFF'}
                </span>
              </div>
            `).join("") || `<div style="color:#6b7280;">No staff accounts found.</div>`}
          </div>
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

  function openAddStaffModal(facilities) {
    const modalBox = container.querySelector("#staffModalContainer");
    modalBox.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-box" style="max-width: 520px;">
          <div class="modal-header">
            <h3 style="margin: 0; display: flex; align-items: center; gap: 0.5rem; font-size: 1.15rem;">
              <span>➕</span> Provision New Clinical Staff
            </h3>
            <button type="button" class="btn btn-secondary btn-sm" id="btnCloseStaffModal" style="padding: 0.2rem 0.5rem;">✕</button>
          </div>
          <form id="addStaffForm">
            <div class="modal-body" style="padding: 1.25rem; max-height: 70vh; overflow-y: auto;">
              <div style="background: var(--matab-color-brand-surface); border: 1px solid var(--matab-color-brand-subtle); padding: 0.75rem; border-radius: var(--matab-radius-md); font-size: 0.82rem; color: var(--matab-color-brand-primary); margin-bottom: 1rem;">
                Create authorized practitioner or operational staff accounts with Role-Based Access Control (RBAC).
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                <div class="form-group" style="grid-column: span 2;">
                  <label class="form-label">Full Name & Clinical Designation *</label>
                  <input type="text" id="staffFullName" class="form-input" placeholder="e.g. Dr. Hakeem Mohammad Imran" required />
                </div>

                <div class="form-group">
                  <label class="form-label">Login Username *</label>
                  <input type="text" id="staffUsername" class="form-input" placeholder="e.g. dr.imran" autocomplete="username" required />
                </div>

                <div class="form-group">
                  <label class="form-label">System Role *</label>
                  <select id="staffRoleCode" class="form-select">
                    <option value="PRACTITIONER">🩺 Hakim / Doctor (Physician)</option>
                    <option value="RECEPTIONIST">📋 Front Desk / Receptionist</option>
                    <option value="PHARMACIST">💊 Pharmacist / Dispensary</option>
                    <option value="CASHIER">💳 Cashier / Billing</option>
                    <option value="ORG_ADMIN">🏛️ Hospital Admin / Director</option>
                    <option value="INVENTORY_MANAGER">📦 Inventory Manager</option>
                    <option value="READ_ONLY_AUDITOR">🔍 Compliance Auditor</option>
                  </select>
                </div>

                <div class="form-group">
                  <label class="form-label">Official Email</label>
                  <input type="email" id="staffEmail" class="form-input" placeholder="e.g. imran@matab.org" />
                </div>

                <div class="form-group">
                  <label class="form-label">Initial Password *</label>
                  <input type="password" id="staffPassword" class="form-input" value="matab123" required minlength="6" />
                </div>

                <div class="form-group" style="grid-column: span 2;">
                  <label class="form-label">Assigned Facility *</label>
                  <select id="staffFacilityId" class="form-select">
                    ${facilities.map(f => `<option value="${f.id}">${f.name} (${f.code})</option>`).join("")}
                  </select>
                </div>
              </div>

              <div id="staffErrorBox" style="display: none; background: var(--matab-color-status-danger-bg); color: var(--matab-color-status-danger); border: 1px solid var(--matab-color-status-danger-border); padding: 0.65rem; border-radius: var(--matab-radius-md); font-size: 0.82rem; margin-top: 0.75rem;"></div>
            </div>
            <div class="modal-footer" style="padding: 0.75rem 1.25rem; display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button type="button" class="btn btn-secondary" id="btnCancelStaffModal">Cancel</button>
              <button type="submit" class="btn btn-primary" id="btnSubmitStaff">
                Provision Staff Account ➔
              </button>
            </div>
          </form>
        </div>
      </div>
    `;

    const closeModal = () => { modalBox.innerHTML = ""; };
    modalBox.querySelector("#btnCloseStaffModal").addEventListener("click", closeModal);
    modalBox.querySelector("#btnCancelStaffModal").addEventListener("click", closeModal);

    modalBox.querySelector("#addStaffForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errBox = modalBox.querySelector("#staffErrorBox");
      const submitBtn = modalBox.querySelector("#btnSubmitStaff");
      errBox.style.display = "none";
      submitBtn.disabled = true;
      submitBtn.textContent = "Creating Account...";

      const payload = {
        full_name: modalBox.querySelector("#staffFullName").value.trim(),
        username: modalBox.querySelector("#staffUsername").value.trim(),
        role_code: modalBox.querySelector("#staffRoleCode").value,
        email: modalBox.querySelector("#staffEmail").value.trim() || null,
        password: modalBox.querySelector("#staffPassword").value,
        facility_id: modalBox.querySelector("#staffFacilityId").value
      };

      try {
        await apiClient.post("/api/v1/users", payload);
        closeModal();
        if (window.showToast) {
          window.showToast(`Staff member '${payload.full_name}' provisioned successfully!`, "success");
        }
        await loadAll();
      } catch (err) {
        errBox.textContent = err.message || "Failed to create user account.";
        errBox.style.display = "block";
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "Provision Staff Account ➔";
      }
    });
  }

  container.querySelector("#btnRefreshEnterprise").addEventListener("click", loadAll);
  container.querySelector("#btnOpenAddStaffModal")?.addEventListener("click", () => openAddStaffModal(cachedFacilities));
  container.querySelector("#btnCardAddStaff")?.addEventListener("click", () => openAddStaffModal(cachedFacilities));

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

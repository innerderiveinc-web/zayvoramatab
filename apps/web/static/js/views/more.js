/**
 * More Hub — Organization, Facilities, Team, Audit Viewer & Capability Registry
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export async function renderMore(container) {
  container.innerHTML = `<div class="card"><p>Loading governance and operations hub...</p></div>`;

  try {
    const [facData, capsData] = await Promise.all([
      apiClient.get("/api/v1/facilities"),
      apiClient.get("/api/v1/system/capabilities")
    ]);

    const facilities = facData.facilities || [];
    const capabilities = capsData.capabilities || [];
    const hasAuditPerm = state.user?.permissions?.includes("audit:read") || state.user?.roles?.includes("ORG_ADMIN");
    const hasUsersPerm = state.user?.permissions?.includes("users:manage") || state.user?.roles?.includes("ORG_ADMIN");

    let auditRowsHtml = "";
    if (hasAuditPerm) {
      try {
        const auditData = await apiClient.get("/api/v1/audit?limit=25");
        const events = auditData.audit_events || [];
        auditRowsHtml = events.map(e => `
          <tr>
            <td><code>${e.created_at}</code></td>
            <td><strong>${e.action_type}</strong></td>
            <td>${e.target_entity_type}: ${e.target_entity_id}</td>
            <td><span class="badge ${e.outcome === 'SUCCESS' ? 'badge-success' : 'badge-danger'}">${e.outcome}</span></td>
            <td><span style="font-family: monospace; font-size: 0.75rem;">${e.request_id ? e.request_id.slice(0, 8) + '...' : '—'}</span></td>
          </tr>
        `).join("");
      } catch (e) {
        auditRowsHtml = `<tr><td colspan="5" style="color: red;">Error fetching audit log: ${e.message}</td></tr>`;
      }
    }

    let capsRowsHtml = capabilities.map(c => {
      const stateBadge = c.status === "FUNCTIONALLY_TESTED"
        ? `<span class="badge badge-success">${c.status}</span>`
        : `<span class="badge badge-danger">${c.status}</span>`;

      return `
        <tr>
          <td><code>${c.engine_id}</code></td>
          <td><strong>${c.name}</strong></td>
          <td>${c.version}</td>
          <td>${stateBadge}</td>
          <td>${c.health_reason || '—'}</td>
        </tr>
      `;
    }).join("");

    let facRowsHtml = facilities.map(f => `
      <tr>
        <td><strong>${f.name}</strong></td>
        <td><code>${f.code}</code></td>
        <td>${f.address || '—'}</td>
        <td>${f.phone || '—'}</td>
        <td><span class="badge badge-success">Active</span></td>
      </tr>
    `).join("");

    container.innerHTML = `
      <div style="margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: flex-end;">
        <div>
          <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Administration & System Governance</h1>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
            Tenancy configuration, facility scopes, audit trail, capability registry, and clinical knowledge.
          </p>
        </div>
        <div>
          <button id="btnOpenKnowledgeAdmin" class="btn btn-primary">Open Clinical Knowledge Admin</button>
        </div>
      </div>

      <!-- Facilities Card -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Facilities (${facilities.length})</h3>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Facility Name</th>
              <th>Code</th>
              <th>Address</th>
              <th>Phone</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>${facRowsHtml}</tbody>
        </table>
      </div>

      <!-- Capability Registry Card -->
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">Server Capability Registry (Controlled Vocabulary)</h3>
        </div>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-muted); margin-bottom: 0.75rem;">
          Unimplemented clinical modules are strictly seeded as NOT_IMPLEMENTED and prohibited from false representation.
        </p>
        <table class="data-table">
          <thead>
            <tr>
              <th>Engine ID</th>
              <th>Module Name</th>
              <th>Version</th>
              <th>Status</th>
              <th>Status Note</th>
            </tr>
          </thead>
          <tbody>${capsRowsHtml}</tbody>
        </table>
      </div>

      <!-- Append-Only Audit Trail Card -->
      ${hasAuditPerm ? `
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Append-Only Security Audit Trail</h3>
            <span class="badge badge-info">Tenant Scoped</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>Action Type</th>
                <th>Target</th>
                <th>Outcome</th>
                <th>Request ID</th>
              </tr>
            </thead>
            <tbody>${auditRowsHtml || '<tr><td colspan="5" style="text-align: center;">No audit events recorded yet.</td></tr>'}</tbody>
          </table>
        </div>
      ` : ''}
    `;

    document.getElementById("btnOpenKnowledgeAdmin")?.addEventListener("click", () => {
      import("./knowledge_admin.js").then(mod => {
        mod.renderKnowledgeAdmin(container);
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color: red;">Failed to load hub: ${err.message}</p></div>`;
  }
}

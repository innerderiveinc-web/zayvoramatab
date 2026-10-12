/**
 * Today View — Phase 1 Foundation Readiness & Honest Empty State
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export async function renderToday(container) {
  container.innerHTML = `
    <div class="card" style="margin-bottom: 1.25rem;">
      <h2 style="font-size: 1.3rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
        Welcome, ${state.user?.full_name || 'Practitioner'}
      </h2>
      <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
        Phase 1 Independent Platform Foundation — Technical readiness and session status.
      </p>
    </div>

    <!-- Honest Empty Queue State (Strict Rule: Do not invent fake patient queues in Phase 1) -->
    <div class="card" style="text-align: center; padding: 2.5rem 1.5rem;">
      <div style="font-size: 2rem; margin-bottom: 0.5rem;">📋</div>
      <h3 style="color: var(--matab-color-text-secondary); margin-bottom: 0.5rem;">No Clinical OPD Queue Active</h3>
      <p style="color: var(--matab-color-text-muted); font-size: 0.9rem; max-width: 500px; margin: 0 auto 1.25rem auto;">
        You are operating in the Phase 1 Foundation environment. Clinical patient encounters, queue tokens, and active charting will connect in Phase 2.
      </p>
      <div style="display: flex; gap: 0.75rem; justify-content: center;">
        <button id="inspectCapabilitiesBtn" class="btn btn-secondary">
          Inspect Capability Registry ➔
        </button>
      </div>
    </div>

    <!-- System Readiness Status Card -->
    <div class="card" id="readinessCard">
      <div class="card-header">
        <h3 class="card-title">System Liveness & Readiness</h3>
        <button id="refreshHealthBtn" class="btn btn-secondary btn-sm">Refresh Check</button>
      </div>
      <div id="readinessContent">
        <p style="font-size: 0.85rem; color: var(--matab-color-text-muted);">Probing /api/v1/health/ready...</p>
      </div>
    </div>
  `;

  // Attach button handlers
  container.querySelector("#inspectCapabilitiesBtn").addEventListener("click", () => {
    state.setActiveTab("more");
  });

  const readinessContent = container.querySelector("#readinessContent");
  async function checkReadiness() {
    try {
      const data = await apiClient.get("/api/v1/health/ready");
      readinessContent.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem;">
          <div style="background: var(--matab-color-bg-muted); padding: 0.75rem; border-radius: var(--matab-radius-md);">
            <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Database Connection</div>
            <strong style="color: var(--matab-color-status-success);">Connected (ACID Transactions)</strong>
          </div>
          <div style="background: var(--matab-color-bg-muted); padding: 0.75rem; border-radius: var(--matab-radius-md);">
            <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Schema Migrations</div>
            <strong>${data.migrations_applied} Applied</strong>
          </div>
          <div style="background: var(--matab-color-bg-muted); padding: 0.75rem; border-radius: var(--matab-radius-md);">
            <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Multi-Tenant Isolation</div>
            <strong style="color: var(--matab-color-brand-accent);">Server-Enforced</strong>
          </div>
        </div>
      `;
    } catch (err) {
      readinessContent.innerHTML = `
        <div style="background: var(--matab-color-status-danger-bg); color: var(--matab-color-status-danger); padding: 0.75rem; border-radius: var(--matab-radius-md); font-size: 0.85rem;">
          ⚠️ Health check failed: ${err.message} (Request ID: ${err.requestId || 'N/A'})
        </div>
      `;
    }
  }

  container.querySelector("#refreshHealthBtn").addEventListener("click", checkReadiness);
  checkReadiness();
}

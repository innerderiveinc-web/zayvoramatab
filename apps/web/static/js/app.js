/**
 * Main Web Application Bootstrap
 */

import { state } from "./state.js";
import { apiClient } from "/packages/api-client/client.js";
import { renderLogin } from "./views/login.js";
import { renderShell } from "./views/shell.js";
import { renderToday } from "./views/today.js";
import { renderPatients } from "./views/patients.js";
import { renderConsultation } from "./views/consultation.js";
import { renderPrescriptions } from "./views/prescriptions.js";
import { renderFollowups } from "./views/followups.js";
import { renderAppointmentsQueue, renderBillingView, renderInventoryView } from "./views/operations.js";
import { renderEnterpriseAdmin } from "./views/enterprise_admin.js";
import { renderHospitalInterop } from "./views/hospital_interop.js";
import { renderPilotLaunch } from "./views/pilot_launch.js";
import { renderPostPilotEvaluation } from "./views/post_pilot_evaluation.js";
import { renderLibrary } from "./views/library.js";
import { renderMore } from "./views/more.js";

// Session Recovery Hook on 401
window.__MATAB_ON_UNAUTHORIZED__ = () => {
  state.setUser(null);
  const root = document.getElementById("appRoot");
  if (root) renderLogin(root, onLoginSuccess);
};


// Global Clinical UI Dialogs & Toast Notifications
window.showToast = function(message, type = "info", duration = 3500) {
  let container = document.getElementById("matabToastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "matabToastContainer";
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const icons = {
    success: "✓",
    error: "⚠️",
    warning: "⚡",
    info: "ℹ️"
  };
  const toast = document.createElement("div");
  toast.className = `toast-message toast-${type}`;
  toast.innerHTML = `
    <span style="font-size: 1.15rem; line-height: 1;">${icons[type] || "ℹ️"}</span>
    <span style="flex: 1; word-break: break-word; line-height: 1.35;">${message}</span>
    <button type="button" style="background: none; border: none; font-size: 1.1rem; cursor: pointer; color: var(--matab-color-text-muted); padding: 0 0.25rem; line-height: 1;" onclick="this.parentElement.remove()">✕</button>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    setTimeout(() => toast.remove(), 250);
  }, duration);
};

window.alert = function(msg) {
  if (typeof msg !== "string") msg = String(msg);
  const lower = msg.toLowerCase();
  const isErr = lower.includes("fail") || lower.includes("error") || lower.includes("invalid") || lower.includes("required");
  const isSuccess = lower.includes("success") || lower.includes("completed") || msg.includes("✓") || lower.includes("recorded") || lower.includes("saved");
  const type = isErr ? "error" : (isSuccess ? "success" : "info");
  window.showToast(msg, type);
};

window.openPromptModal = function({
  title = "Clinical Input",
  message = "Please provide clinical notes or rationale:",
  defaultValue = "",
  placeholder = "",
  confirmText = "Confirm",
  cancelText = "Cancel",
  required = false
}) {
  return new Promise((resolve) => {
    const existing = document.getElementById("matabGlobalPromptModal");
    if (existing) existing.remove();

    const backdrop = document.createElement("div");
    backdrop.id = "matabGlobalPromptModal";
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal-box" style="max-width: 480px;">
        <div class="modal-header">
          <h3 style="margin: 0; font-size: 1.05rem;">${title}</h3>
          <button type="button" class="btn btn-secondary btn-sm" id="matabPromptClose" style="padding: 0.2rem 0.5rem;">✕</button>
        </div>
        <div class="modal-body" style="padding: 1.25rem;">
          <p style="margin-top: 0; margin-bottom: 0.75rem; color: var(--matab-color-text-secondary); font-size: 0.9rem; line-height: 1.4;">${message}</p>
          <input type="text" id="matabPromptInput" class="form-input" style="width: 100%; box-sizing: border-box;" value="${(defaultValue || '').replace(/"/g, '&quot;')}" placeholder="${placeholder}" />
          <div id="matabPromptError" style="display: none; color: var(--matab-color-status-danger); font-size: 0.8rem; margin-top: 0.4rem; font-weight: 600;">This field is required.</div>
        </div>
        <div class="modal-footer" style="padding: 0.75rem 1.25rem;">
          <button type="button" class="btn btn-secondary btn-sm" id="matabPromptCancel">${cancelText}</button>
          <button type="button" class="btn btn-primary btn-sm" id="matabPromptSubmit">${confirmText}</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    const input = document.getElementById("matabPromptInput");
    input.focus();
    input.select();

    const cleanup = () => backdrop.remove();

    const submit = () => {
      const val = input.value.trim();
      if (required && !val) {
        document.getElementById("matabPromptError").style.display = "block";
        input.focus();
        return;
      }
      cleanup();
      resolve(val);
    };

    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submit();
      } else if (e.key === "Escape") {
        cleanup();
        resolve(null);
      }
    });

    document.getElementById("matabPromptSubmit").onclick = submit;
    document.getElementById("matabPromptCancel").onclick = () => { cleanup(); resolve(null); };
    document.getElementById("matabPromptClose").onclick = () => { cleanup(); resolve(null); };
  });
};

window.openConfirmModal = function({
  title = "Clinical Confirmation",
  message = "Are you sure you want to proceed with this clinical action?",
  confirmText = "Proceed",
  cancelText = "Cancel",
  danger = false
}) {
  return new Promise((resolve) => {
    const existing = document.getElementById("matabGlobalConfirmModal");
    if (existing) existing.remove();

    const backdrop = document.createElement("div");
    backdrop.id = "matabGlobalConfirmModal";
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal-box" style="max-width: 440px;">
        <div class="modal-header">
          <h3 style="margin: 0; font-size: 1.05rem; color: ${danger ? 'var(--matab-color-status-danger)' : 'var(--matab-color-brand-primary)'};">${title}</h3>
          <button type="button" class="btn btn-secondary btn-sm" id="matabConfirmClose" style="padding: 0.2rem 0.5rem;">✕</button>
        </div>
        <div class="modal-body" style="padding: 1.25rem;">
          <p style="margin: 0; color: var(--matab-color-text-secondary); font-size: 0.9rem; line-height: 1.5;">${message}</p>
        </div>
        <div class="modal-footer" style="padding: 0.75rem 1.25rem;">
          <button type="button" class="btn btn-secondary btn-sm" id="matabConfirmCancel">${cancelText}</button>
          <button type="button" class="btn ${danger ? 'btn-danger' : 'btn-primary'} btn-sm" id="matabConfirmSubmit">${confirmText}</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);

    const cleanup = () => backdrop.remove();

    document.getElementById("matabConfirmSubmit").onclick = () => { cleanup(); resolve(true); };
    document.getElementById("matabConfirmCancel").onclick = () => { cleanup(); resolve(false); };
    document.getElementById("matabConfirmClose").onclick = () => { cleanup(); resolve(false); };
  });
};

window.switchActiveRole = async function(username, password = "matab123") {
  const root = document.getElementById("appRoot");
  if (!root) return;
  try {
    const res = await apiClient.post("/api/v1/auth/login", { username, password });
    apiClient.setToken(res.token);
    localStorage.setItem("matab_token", res.token);
    const meData = await apiClient.get("/api/v1/auth/me").catch(() => null);
    const user = meData?.user || res.user;
    state.setUser(user);
    const targetTab = getInitialTabForUser(user);
    lastRenderedTab = null;
    state.activeTab = targetTab;
    renderAppShell(root);
    const roleLabel = (user.roles?.[0] || 'Staff').replace(/_/g, ' ');
    window.showToast(`Active Session: ${user.full_name || username} (${roleLabel})`, "success");
  } catch (err) {
    window.showToast("Failed to switch role: " + (err.message || err), "error");
    try { renderAppShell(root); } catch(e) {}
  }
};


async function init() {
  const root = document.getElementById("appRoot");
  if (!root) return;

  // Immediate failsafe: If still showing initializing after 1.5s, force clean render
  const splashTimer = setTimeout(() => {
    if (root.innerHTML.includes("Initializing Clinical Workspace")) {
      console.warn("Bootstrap splash timer expired, falling back to login screen");
      renderLogin(root, onLoginSuccess);
    }
  }, 1200);

  try {
    const storedToken = apiClient.getToken();

    if (!storedToken) {
      clearTimeout(splashTimer);
      if (!document.getElementById("loginForm")) {
        renderLogin(root, onLoginSuccess);
      }
      return;
    }

    try {
      const meData = await apiClient.get("/api/v1/auth/me");
      clearTimeout(splashTimer);
      state.setUser(meData.user);
      const targetTab = state.activeTab || getInitialTabForUser(meData.user);
      state.activeTab = targetTab;
      renderAppShell(root);
    } catch (err) {
      clearTimeout(splashTimer);
      apiClient.setToken("");
      state.setUser(null);
      renderLogin(root, onLoginSuccess);
    }
  } catch (fatalErr) {
    console.error("Application bootstrap error:", fatalErr);
    root.innerHTML = `
      <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #064e3b; padding: 1.5rem; font-family: sans-serif;">
        <div style="max-width: 480px; width: 100%; padding: 2rem; background: #ffffff; border-radius: 12px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1); text-align: center;">
          <div style="font-size: 2.5rem; margin-bottom: 0.75rem;">🌿</div>
          <h2 style="color: #0f766e; margin-bottom: 0.5rem; font-size: 1.25rem;">ZAYVORA MATAB OS</h2>
          <p style="color: #64748b; font-size: 0.85rem; margin-bottom: 1rem;">Clinical Session Reconnection:</p>
          <div style="background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 0.75rem; border-radius: 8px; font-size: 0.8rem; margin-bottom: 1.25rem; text-align: left;">
            ${fatalErr.message || fatalErr}
          </div>
          <button onclick="localStorage.clear(); window.location.reload();" style="background: #0f766e; color: #ffffff; border: none; padding: 0.6rem 1.2rem; border-radius: 6px; font-size: 0.85rem; font-weight: 600; cursor: pointer;">
            Launch Clean Clinical Session ➔
          </button>
        </div>
      </div>
    `;
  }
}

function getInitialTabForUser(user) {
  const roles = new Set(user?.roles || []);
  if (roles.has("RECEPTIONIST")) return "appointments_queue";
  if (roles.has("PHARMACIST") || roles.has("INVENTORY_MANAGER")) return "inventory";
  if (roles.has("CASHIER")) return "billing";
  return "today";
}

async function onLoginSuccess(user) {
  if (user && user.token && apiClient) {
    apiClient.setToken(user.token);
  }
  try {
    const meData = await apiClient.get("/api/v1/auth/me").catch(() => null);
    state.setUser(meData?.user || user);
  } catch {
    state.setUser(user);
  }
  const targetTab = getInitialTabForUser(state.user || user);
  lastRenderedTab = null;
  state.activeTab = targetTab;
  const root = document.getElementById("appRoot");
  if (root) {
    renderAppShell(root);
  }
}

// Expose global launcher for seamless index.html instant sign in
window.__LAUNCH_MATAB_SHELL__ = onLoginSuccess;

function onLogoutSuccess() {
  apiClient.setToken("");
  state.setUser(null);
  lastRenderedTab = null;
  const root = document.getElementById("appRoot");
  renderLogin(root, onLoginSuccess);
}


let lastRenderedTab = null;
let isSubscribed = false;

function renderAppShell(root) {
  renderShell(root, (tab) => {
    state.setActiveTab(tab);
    renderCurrentTab(tab, true);
  }, onLogoutSuccess);

  renderCurrentTab(state.activeTab, true);

  if (!isSubscribed) {
    isSubscribed = true;
    state.subscribe(() => {
      renderCurrentTab(state.activeTab, false);
    });
  }
}

async function renderCurrentTab(tab, force = false) {
  const content = document.getElementById("pageContent");
  if (!content) return;
  if (!force && lastRenderedTab === tab) return;
  lastRenderedTab = tab;

  // Render clear, responsive loading skeleton while rendering view
  content.innerHTML = `
    <div style="padding: 2.5rem; text-align: center; color: var(--matab-color-brand-primary);">
      <div style="font-size: 1.5rem; margin-bottom: 0.5rem;">⏱️</div>
      <p style="font-weight: 600; color: var(--matab-color-brand-primary);">
        Loading ${tab.replace(/_/g, ' ')} workspace...
      </p>
    </div>
  `;

  try {
    switch (tab) {
      case "today":
        await renderToday(content);
        break;
      case "patients":
        renderPatients(content);
        break;
      case "appointments_queue":
        await renderAppointmentsQueue(content);
        break;
      case "consultation":
        await renderConsultation(content);
        break;
      case "prescriptions":
        await renderPrescriptions(content);
        break;
      case "followups":
        await renderFollowups(content);
        break;
      case "billing":
        await renderBillingView(content);
        break;
      case "inventory":
        await renderInventoryView(content);
        break;
      case "hospital_interop":
        await renderHospitalInterop(content);
        break;
      case "enterprise_admin":
        await renderEnterpriseAdmin(content);
        break;
      case "pilot_launch":
        await renderPilotLaunch(content);
        break;
      case "pilot_evaluation":
        await renderPostPilotEvaluation(content);
        break;
      case "library":
        await renderLibrary(content);
        break;
      case "more":
        await renderMore(content);
        break;
      default:
        await renderToday(content);
    }
  } catch (renderErr) {
    console.error(`Error rendering tab '${tab}':`, renderErr);
    content.innerHTML = `
      <div class="card" style="padding: 2rem; border-left: 4px solid var(--matab-color-status-danger); margin: 1rem 0;">
        <h3 style="color: var(--matab-color-status-danger); margin-top: 0;">Error Loading Workspace (${tab})</h3>
        <p style="color: var(--matab-color-text-secondary); margin-bottom: 1rem;">${renderErr.message || renderErr}</p>
        <button class="btn btn-secondary btn-sm" onclick="window.location.reload()">Reload Application</button>
      </div>
    `;
  }
}

if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

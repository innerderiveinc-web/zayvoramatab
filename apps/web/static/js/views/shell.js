/**
 * Role-Aware App Shell View — Phase 10 Clinic Operations OS
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export function renderShell(container, onNavigate, onLogout) {
  const user = state.user;
  const perms = new Set(user?.permissions || []);
  const roles = new Set(user?.roles || []);
  const isAdmin = roles.has("ORG_ADMIN") || roles.has("CLINIC_ADMIN");

  const showPatients = isAdmin || perms.has("patients:read") || perms.has("patient:read");
  const showQueue = isAdmin || perms.has("appointments:read") || perms.has("queue:read");
  const showConsultation = isAdmin || perms.has("encounters:write") || roles.has("PRACTITIONER");
  const showPrescriptions = isAdmin || perms.has("prescription:read");
  const showFollowups = isAdmin || perms.has("followup:read");
  const showBilling = isAdmin || perms.has("billing:read");
  const showInventory = isAdmin || perms.has("inventory:read") || perms.has("dispensing:read");
  const showHospitalInterop = isAdmin || roles.has("PRACTITIONER") || roles.has("NURSE") || perms.has("ipd:admission_read") || perms.has("lab:order_read");
  const showEnterpriseAdmin = isAdmin || roles.has("READ_ONLY_AUDITOR") || perms.has("enterprise:org_manage") || perms.has("enterprise:facility_manage");
  const showPilotLaunch = isAdmin || roles.has("PRACTITIONER") || perms.has("org:manage") || perms.has("org:view");

  container.innerHTML = `
    <div class="env-banner">
      <span>⚠️</span>
      <span>Synthetic Development Environment (Phase 12 Hospital Workflows, FHIR R4 & ABDM Interop) — Real Backend Persistence & Audit Enabled</span>
    </div>

    <header class="app-header">
      <div class="brand-section">
        <div class="brand-title">
          <span>🌿</span>
          <span>ZAYVORA MATAB OS</span>
          <span class="brand-badge">${user?.org_profile || "MATAB"}</span>
        </div>
        <div style="font-size: 0.85rem; opacity: 0.9;">
          🏢 ${user?.org_name || "ZAYVORA Dawakhana"}
        </div>
      </div>

      <div class="header-user-section">
        <div class="user-tag">
          <span>👤</span>
          <span>${user?.full_name || "Practitioner"}</span>
          <span class="badge badge-success">${user?.roles?.[0] || "USER"}</span>
        </div>
        <button id="logoutBtn" class="btn btn-secondary btn-sm" style="color: #ffffff; background: rgba(255,255,255,0.2);">
          Sign Out
        </button>
      </div>
    </header>

    <nav class="nav-bar">
      <button class="nav-tab ${state.activeTab === "today" ? "active" : ""}" data-tab="today">
        <span>⏱️</span>
        <span>Today</span>
      </button>
      ${showPatients ? `
      <button class="nav-tab ${state.activeTab === "patients" ? "active" : ""}" data-tab="patients">
        <span>👥</span>
        <span>Patients</span>
      </button>` : ''}
      ${showQueue ? `
      <button class="nav-tab ${state.activeTab === "appointments_queue" ? "active" : ""}" data-tab="appointments_queue">
        <span>🎫</span>
        <span>Appointments & Queue</span>
      </button>` : ''}
      ${showConsultation ? `
      <button class="nav-tab ${state.activeTab === "consultation" ? "active" : ""}" data-tab="consultation">
        <span>🩺</span>
        <span>Consultation</span>
      </button>` : ''}
      ${showPrescriptions ? `
      <button class="nav-tab ${state.activeTab === "prescriptions" ? "active" : ""}" data-tab="prescriptions">
        <span>📜</span>
        <span>Prescriptions</span>
      </button>` : ''}
      ${showFollowups ? `
      <button class="nav-tab ${state.activeTab === "followups" ? "active" : ""}" data-tab="followups">
        <span>📅</span>
        <span>Follow-ups</span>
      </button>` : ''}
      ${showBilling ? `
      <button class="nav-tab ${state.activeTab === "billing" ? "active" : ""}" data-tab="billing">
        <span>💳</span>
        <span>Billing</span>
      </button>` : ''}
      ${showInventory ? `
      <button class="nav-tab ${state.activeTab === "inventory" ? "active" : ""}" data-tab="inventory">
        <span>📦</span>
        <span>Inventory</span>
      </button>` : ''}
      ${showHospitalInterop ? `
      <button class="nav-tab ${state.activeTab === "hospital_interop" ? "active" : ""}" data-tab="hospital_interop">
        <span>🏥</span>
        <span>Hospital & Interop</span>
      </button>` : ''}
      ${showEnterpriseAdmin ? `
      <button class="nav-tab ${state.activeTab === "enterprise_admin" ? "active" : ""}" data-tab="enterprise_admin">
        <span>🏛️</span>
        <span>Enterprise Admin</span>
      </button>` : ''}
      ${showPilotLaunch ? `
      <button class="nav-tab ${state.activeTab === "pilot_launch" ? "active" : ""}" data-tab="pilot_launch">
        <span>🚀</span>
        <span>Pilot Launch</span>
      </button>
      <button class="nav-tab ${state.activeTab === "pilot_evaluation" ? "active" : ""}" data-tab="pilot_evaluation">
        <span>⚖️</span>
        <span>Post-Pilot Review</span>
      </button>` : ''}
      <button class="nav-tab ${state.activeTab === "more" ? "active" : ""}" data-tab="more">
        <span>⚙️</span>
        <span>Reports & Settings</span>
      </button>
    </nav>

    <main id="pageContent" class="main-content"></main>
  `;

  container.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      state.setActiveTab(target);
      onNavigate(target);
    });
  });

  container.querySelector("#logoutBtn").addEventListener("click", async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch (e) {}
    localStorage.removeItem("matab_token");
    onLogout();
  });
}

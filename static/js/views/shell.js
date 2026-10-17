/**
 * Modern Hospital App Shell View — ZAYVORA MATAB OS
 * Phase 10 Unified Clinical Operations Environment
 */

import { state } from "../state.js";
import { apiClient } from "/packages/api-client/client.js";
import { i18n } from "../i18n.js";

export function renderShell(container, onNavigate, onLogout) {
  const user = state.user;
  const currentLocale = i18n.getLocale();
  const perms = new Set(user?.permissions || []);
  const roles = new Set(user?.roles?.length ? user.roles : ["HAKEEM", "DOCTOR", "PRACTITIONER", "ORG_ADMIN"]);
  const isAdmin = roles.has("ORG_ADMIN") || roles.has("CLINIC_ADMIN") || roles.has("ADMIN") || roles.has("SUPER_ADMIN");
  const isPractitioner = roles.has("PRACTITIONER") || roles.has("HAKEEM") || roles.has("DOCTOR") || roles.has("TABIB");
  const isReceptionist = roles.has("RECEPTIONIST") || roles.has("FRONT_DESK");
  const isPharmacist = roles.has("PHARMACIST");
  const isCashier = roles.has("CASHIER");
  const isInventory = roles.has("INVENTORY_MANAGER");

  const showPatients = isAdmin || isPractitioner || isReceptionist || perms.has("patients:read") || perms.has("patient:read");
  const showQueue = isAdmin || isPractitioner || isReceptionist || perms.has("appointments:read") || perms.has("queue:read");
  const showConsultation = isAdmin || isPractitioner || perms.has("encounters:write");
  const showPrescriptions = isAdmin || isPractitioner || isPharmacist || perms.has("prescription:read");
  const showFollowups = isAdmin || isPractitioner || isReceptionist || perms.has("followup:read");
  const showBilling = isAdmin || isCashier || isReceptionist || perms.has("billing:read");
  const showInventory = isAdmin || isPharmacist || isInventory || perms.has("inventory:read") || perms.has("dispensing:read");
  const showHospitalInterop = isAdmin || roles.has("NURSE") || perms.has("ipd:admission_read");
  const showEnterpriseAdmin = isAdmin || roles.has("READ_ONLY_AUDITOR");
  const showPilotLaunch = isAdmin;

  container.innerHTML = `
    <a href="#pageContent" class="skip-to-content">${i18n.t("skip_to_content", "Skip to main content")}</a>

    <!-- Top Command & Status Bar -->
    <header class="app-header" role="banner">
      <div class="brand-section">
        <div class="brand-title">
          <span style="font-size: 1.4rem;">🌿</span>
          <span>${i18n.t("app_title", "ZAYVORA MATAB OS")}</span>
          <span class="brand-badge">${user?.org_profile || "MATAB"}</span>
        </div>
        
        <div class="header-meta-pill">
          <span class="status-dot-pulse" title="System Operational"></span>
          <span>${(user?.org_name || "ZAYVORA Matab & Hospital").replace(/\s*\[Synthetic\]/gi, "")}</span>
          <span style="opacity: 0.6;">|</span>
          <span style="font-size: 0.75rem; color: #a7f3d0;">HL7 FHIR & ABDM Active</span>
        </div>
      </div>

      <div class="header-user-section" style="display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap;">
        <!-- 1-Click Fast Role Switcher -->
        <div style="display: flex; gap: 0.25rem; align-items: center; background: rgba(0,0,0,0.2); padding: 0.2rem 0.35rem; border-radius: var(--matab-radius-md);">
          <span style="font-size: 0.7rem; color: #a7f3d0; font-weight: 700; text-transform: uppercase; margin-right: 0.15rem;">Role:</span>
          <button type="button" class="btn btn-sm btn-quick-switch-role ${isPractitioner ? 'btn-primary' : 'btn-secondary'}" data-user="hakeem" style="font-size: 0.72rem; padding: 0.2rem 0.45rem;">
            🩺 Doctor
          </button>
          <button type="button" class="btn btn-sm btn-quick-switch-role ${isReceptionist ? 'btn-primary' : 'btn-secondary'}" data-user="reception" style="font-size: 0.72rem; padding: 0.2rem 0.45rem;">
            📋 Front Desk
          </button>
          <button type="button" class="btn btn-sm btn-quick-switch-role ${isPharmacist ? 'btn-primary' : 'btn-secondary'}" data-user="pharmacy" style="font-size: 0.72rem; padding: 0.2rem 0.45rem;">
            💊 Pharmacy
          </button>
          <button type="button" class="btn btn-sm btn-quick-switch-role ${isAdmin ? 'btn-primary' : 'btn-secondary'}" data-user="admin" style="font-size: 0.72rem; padding: 0.2rem 0.45rem;">
            🏛️ Admin
          </button>
        </div>

        <!-- Multilingual Locale Selector -->
        <div>
          <label for="langSelect" class="sr-only">${i18n.t("language_selector", "Select Language")}</label>
          <select id="langSelect" class="form-control" style="width: auto; min-height: 32px; padding: 0.15rem 0.5rem; background: rgba(255,255,255,0.15); color: #ffffff; border: 1px solid rgba(255,255,255,0.3); border-radius: var(--matab-radius-sm); font-size: 0.78rem; font-weight: 600; cursor: pointer;">
            <option value="en" ${currentLocale === "en" ? "selected" : ""} style="color: #0f172a;">English (EN)</option>
            <option value="ur" ${currentLocale === "ur" ? "selected" : ""} style="color: #0f172a;">اردو (Urdu)</option>
            <option value="hi" ${currentLocale === "hi" ? "selected" : ""} style="color: #0f172a;">हिन्दी (Hindi)</option>
          </select>
        </div>

        <!-- Clinician Profile Chip -->
        <div class="user-tag" role="status" style="padding: 0.25rem 0.6rem;">
          <span aria-hidden="true" style="font-size: 0.95rem;">🩺</span>
          <span style="font-weight: 600; font-size: 0.85rem;">${(user?.full_name || "Practitioner").replace(/\s*\[Synthetic\]/gi, "")}</span>
          <span class="badge badge-success" style="font-size: 0.68rem; padding: 0.12rem 0.4rem;">${user?.roles?.[0] || "USER"}</span>
        </div>

        <button id="logoutBtn" class="btn btn-secondary btn-sm" aria-label="${i18n.t("sign_out", "Sign Out")}" style="color: #ffffff; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3); padding: 0.25rem 0.6rem; font-size: 0.78rem;">
          <span>🚪</span> ${i18n.t("sign_out", "Sign Out")}
        </button>
      </div>
    </header>

    <!-- Sleek Navigation Tabs -->
    <nav class="nav-bar" role="navigation" aria-label="Main Navigation" id="mainNavBar">
      <button class="nav-tab ${state.activeTab === "today" ? "active" : ""}" data-tab="today" aria-label="${i18n.t("today", "Today")}">
        <span aria-hidden="true">⏱️</span>
        <span>${i18n.t("today", "Today")}</span>
      </button>

      ${showPatients ? `
      <button class="nav-tab ${state.activeTab === "patients" ? "active" : ""}" data-tab="patients">
        <span>👥</span>
        <span>Patients</span>
      </button>` : ''}

      ${showQueue ? `
      <button class="nav-tab ${state.activeTab === "appointments_queue" ? "active" : ""}" data-tab="appointments_queue">
        <span>🎫</span>
        <span>OPD Queue</span>
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
        <span>Dispensary</span>
      </button>` : ''}

      ${showHospitalInterop ? `
      <button class="nav-tab ${state.activeTab === "hospital_interop" ? "active" : ""}" data-tab="hospital_interop">
        <span>🏥</span>
        <span>Hospital & Interop</span>
      </button>` : ''}

      ${showEnterpriseAdmin ? `
      <button class="nav-tab ${state.activeTab === "enterprise_admin" ? "active" : ""}" data-tab="enterprise_admin">
        <span>🏛️</span>
        <span>Administration</span>
      </button>` : ''}

      ${showPilotLaunch ? `
      <button class="nav-tab ${state.activeTab === "pilot_launch" ? "active" : ""}" data-tab="pilot_launch">
        <span>🚀</span>
        <span>Facility Onboarding</span>
      </button>
      <button class="nav-tab ${state.activeTab === "pilot_evaluation" ? "active" : ""}" data-tab="pilot_evaluation">
        <span>⚖️</span>
        <span>Clinical Scorecard</span>
      </button>` : ''}

      <button class="nav-tab ${state.activeTab === "library" ? "active" : ""}" data-tab="library">
        <span>📚</span>
        <span>Tibb Library</span>
      </button>

      <button class="nav-tab ${state.activeTab === "more" ? "active" : ""}" data-tab="more">
        <span>⚙️</span>
        <span>Governance & Settings</span>
      </button>
    </nav>

    <main id="pageContent" class="main-content"></main>
  `;

  // Function to sync active tab highlight
  function syncActiveTabHighlight(targetTab) {
    container.querySelectorAll(".nav-tab").forEach(tab => {
      if (tab.getAttribute("data-tab") === targetTab) {
        tab.classList.add("active");
        tab.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      } else {
        tab.classList.remove("active");
      }
    });
  }

  container.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      state.setActiveTab(target);
      syncActiveTabHighlight(target);
      onNavigate(target);
    });
  });

  container.querySelector("#langSelect")?.addEventListener("change", (e) => {
    const newLocale = e.target.value;
    i18n.setLocale(newLocale);
    renderShell(container, onNavigate, onLogout);
    onNavigate(state.activeTab);
  });

  container.querySelectorAll(".btn-quick-switch-role").forEach(btn => {
    btn.addEventListener("click", async () => {
      const u = btn.dataset.user;
      btn.style.opacity = "0.7";
      btn.textContent = "Switching...";
      if (typeof window.switchActiveRole === "function") {
        await window.switchActiveRole(u);
      }
    });
  });

  container.querySelector("#logoutBtn")?.addEventListener("click", async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch (e) {}
    localStorage.removeItem("matab_token");
    onLogout();
  });
}

// ZAYVORA MATAB OS — Application Shell Component

import { state } from "../state.js";
import { translations } from "../i18n.js";
import { api } from "../api.js";

export function renderShell(container) {
  const t = translations[state.currentLang] || translations.en;
  const user = state.user;

  container.innerHTML = `
    <header class="app-header">
      <div class="brand-section">
        <div class="brand-title">
          <span>🌿</span>
          <span>${t.app_title}</span>
          <span class="brand-badge">${user?.org_profile || "MATAB"}</span>
        </div>
        <div class="facility-label">📍 ${user?.org_name || "ZAYVORA Matab Dawakhana"}</div>
      </div>
      <div class="header-actions">
        <div class="lang-selector">
          <select id="langSelect" class="btn btn-secondary btn-sm">
            <option value="en" ${state.currentLang === "en" ? "selected" : ""}>English</option>
            <option value="ur" ${state.currentLang === "ur" ? "selected" : ""}>اردو (Urdu)</option>
            <option value="hi" ${state.currentLang === "hi" ? "selected" : ""}>हिन्दी (Hindi)</option>
          </select>
        </div>
        <div class="user-badge">
          <span>👤</span>
          <span>${user?.full_name || "Practitioner"}</span>
          <span class="badge badge-pass">${user?.role || "HAKEEM"}</span>
        </div>
        <button id="logoutBtn" class="btn btn-secondary btn-sm">Sign Out</button>
      </div>
    </header>

    <nav class="nav-bar">
      <button class="nav-tab ${state.activeTab === "today" ? "active" : ""}" data-tab="today">
        <span>⏱️</span>
        <span>${t.nav_today}</span>
      </button>
      <button class="nav-tab ${state.activeTab === "patients" ? "active" : ""}" data-tab="patients">
        <span>👥</span>
        <span>${t.nav_patients}</span>
      </button>
      <button class="nav-tab ${state.activeTab === "consultation" ? "active" : ""}" data-tab="consultation">
        <span>🩺</span>
        <span>${t.nav_consultation}</span>
        ${state.activeEncounter ? '<span class="tab-badge">Active</span>' : ''}
      </button>
      <button class="nav-tab ${state.activeTab === "prescriptions" ? "active" : ""}" data-tab="prescriptions">
        <span>📜</span>
        <span>${t.nav_prescriptions}</span>
      </button>
      <button class="nav-tab ${state.activeTab === "followups" ? "active" : ""}" data-tab="followups">
        <span>📅</span>
        <span>${t.nav_followups}</span>
      </button>
      <button class="nav-tab ${state.activeTab === "more" ? "active" : ""}" data-tab="more">
        <span>⚙️</span>
        <span>${t.nav_more}</span>
      </button>
    </nav>

    <main id="mainContainer" class="main-content"></main>
  `;

  // Attach Event Handlers
  container.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      state.setActiveTab(target);
    });
  });

  const langSelect = container.querySelector("#langSelect");
  if (langSelect) {
    langSelect.addEventListener("change", (e) => {
      state.setLanguage(e.target.value);
    });
  }

  const logoutBtn = container.querySelector("#logoutBtn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      try {
        await api.post("/api/v1/auth/logout");
      } catch (e) {}
      api.setToken("");
      window.location.reload();
    });
  }
}

/**
 * Role-Aware App Shell View
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export function renderShell(container, onNavigate, onLogout) {
  const user = state.user;

  container.innerHTML = `
    <div class="env-banner">
      <span>⚠️</span>
      <span>Synthetic Development Environment (Phase 1 Foundation) — Real Backend Persistence & Audit Enabled</span>
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
      <button class="nav-tab ${state.activeTab === "patients" ? "active" : ""}" data-tab="patients">
        <span>👥</span>
        <span>Patients</span>
      </button>
      <button class="nav-tab ${state.activeTab === "consultation" ? "active" : ""}" data-tab="consultation">
        <span>🩺</span>
        <span>Consultation</span>
      </button>
      <button class="nav-tab ${state.activeTab === "prescriptions" ? "active" : ""}" data-tab="prescriptions">
        <span>📜</span>
        <span>Prescriptions</span>
      </button>
      <button class="nav-tab ${state.activeTab === "followups" ? "active" : ""}" data-tab="followups">
        <span>📅</span>
        <span>Follow-ups</span>
      </button>
      <button class="nav-tab ${state.activeTab === "more" ? "active" : ""}" data-tab="more">
        <span>⚙️</span>
        <span>More</span>
      </button>
    </nav>

    <main id="pageContent" class="main-content"></main>
  `;

  // Attach tab navigation
  container.querySelectorAll(".nav-tab").forEach(tab => {
    tab.addEventListener("click", () => {
      const target = tab.getAttribute("data-tab");
      state.setActiveTab(target);
      onNavigate(target);
    });
  });

  // Attach logout handler
  container.querySelector("#logoutBtn").addEventListener("click", async () => {
    try {
      await apiClient.post("/api/v1/auth/logout");
    } catch (e) {}
    localStorage.removeItem("matab_token");
    onLogout();
  });
}

/**
 * Main Web Application Bootstrap
 */

import { state } from "./state.js";
import { apiClient } from "../../../../packages/api-client/client.js";
import { renderLogin } from "./views/login.js";
import { renderShell } from "./views/shell.js";
import { renderToday } from "./views/today.js";
import { renderPatients } from "./views/patients.js";
import { renderConsultation } from "./views/consultation.js";
import { renderPrescriptions } from "./views/prescriptions.js";
import { renderFollowups } from "./views/followups.js";
import { renderAppointmentsQueue, renderBillingView, renderInventoryView } from "./views/operations.js";
import { renderMore } from "./views/more.js";

async function init() {
  const root = document.getElementById("appRoot");
  const storedToken = localStorage.getItem("matab_token");

  if (!storedToken) {
    renderLogin(root, onLoginSuccess);
    return;
  }

  apiClient.setToken(storedToken);

  try {
    const meData = await apiClient.get("/api/v1/auth/me");
    state.setUser(meData.user);
    renderAppShell(root);
  } catch (err) {
    localStorage.removeItem("matab_token");
    renderLogin(root, onLoginSuccess);
  }
}

function onLoginSuccess(user) {
  state.setUser(user);
  const root = document.getElementById("appRoot");
  renderAppShell(root);
}

function onLogoutSuccess() {
  state.setUser(null);
  const root = document.getElementById("appRoot");
  renderLogin(root, onLoginSuccess);
}

function renderAppShell(root) {
  renderShell(root, renderCurrentTab, onLogoutSuccess);
  renderCurrentTab(state.activeTab);

  state.subscribe(() => {
    renderCurrentTab(state.activeTab);
  });
}

function renderCurrentTab(tab) {
  const content = document.getElementById("pageContent");
  if (!content) return;

  switch (tab) {
    case "today":
      renderToday(content);
      break;
    case "patients":
      renderPatients(content);
      break;
    case "appointments_queue":
      renderAppointmentsQueue(content);
      break;
    case "consultation":
      renderConsultation(content);
      break;
    case "prescriptions":
      renderPrescriptions(content);
      break;
    case "followups":
      renderFollowups(content);
      break;
    case "billing":
      renderBillingView(content);
      break;
    case "inventory":
      renderInventoryView(content);
      break;
    case "more":
      renderMore(content);
      break;
    default:
      renderToday(content);
  }
}

window.addEventListener("DOMContentLoaded", init);

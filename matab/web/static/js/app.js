// ZAYVORA MATAB OS — Main Application Bootstrap

import { state } from "./state.js";
import { api } from "./api.js";
import { renderShell } from "./components/shell.js";
import { renderToday } from "./components/today.js";
import { renderPatients } from "./components/patients.js";
import { renderCanvas } from "./components/canvas.js";
import { renderPrescriptions } from "./components/prescriptions.js";
import { renderFollowups } from "./components/followups.js";
import { renderMore } from "./components/more.js";

async function initApp() {
  const root = document.getElementById("app");
  const token = api.getToken();

  if (!token) {
    renderLoginScreen(root);
    return;
  }

  try {
    const meData = await api.get("/api/v1/auth/me");
    state.setUser(meData.user);

    // Initial Shell Mount
    renderShell(root);
    mountActiveTab();

    // Subscribe to state updates
    state.subscribe(() => {
      renderShell(root);
      mountActiveTab();
    });

  } catch (err) {
    console.warn("Session invalid or expired:", err);
    api.setToken("");
    renderLoginScreen(root);
  }
}

function mountActiveTab() {
  const container = document.getElementById("mainContainer");
  if (!container) return;

  switch (state.activeTab) {
    case "today":
      renderToday(container);
      break;
    case "patients":
      renderPatients(container);
      break;
    case "consultation":
      renderCanvas(container);
      break;
    case "prescriptions":
      renderPrescriptions(container);
      break;
    case "followups":
      renderFollowups(container);
      break;
    case "more":
      renderMore(container);
      break;
    default:
      renderToday(container);
  }
}

function renderLoginScreen(root) {
  root.innerHTML = `
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #064e3b; padding: 1.5rem;">
      <div class="card" style="max-width: 420px; width: 100%; padding: 2rem; box-shadow: var(--shadow-lg);">
        <div style="text-align: center; margin-bottom: 1.5rem;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🌿</div>
          <h1 style="font-size: 1.4rem; color: #064e3b; margin-bottom: 0.25rem;">ZAYVORA MATAB OS</h1>
          <p style="font-size: 0.85rem; color: var(--color-text-muted);">
            Unani-First Clinical Operating System (v1.1)
          </p>
        </div>

        <form id="loginForm">
          <div class="form-group">
            <label class="form-label">Username</label>
            <input type="text" id="usernameInput" class="form-input" value="hakeem" required />
          </div>
          <div class="form-group">
            <label class="form-label">Password</label>
            <input type="password" id="passwordInput" class="form-input" value="matab123" required />
          </div>
          
          <div id="loginError" style="color: red; font-size: 0.8rem; margin-bottom: 0.75rem; display: none;"></div>

          <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 0.5rem;">
            Sign In to Matab ➔
          </button>
        </form>

        <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--color-border); font-size: 0.75rem; color: var(--color-text-muted); text-align: center;">
          Demo accounts: <code>hakeem</code> (PIN: <code>1234</code>) | <code>reception</code> | <code>pharmacy</code><br />
          Password: <code>matab123</code>
        </div>
      </div>
    </div>
  `;

  const form = root.querySelector("#loginForm");
  const errEl = root.querySelector("#loginError");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errEl.style.display = "none";
    const username = form.querySelector("#usernameInput").value.trim();
    const password = form.querySelector("#passwordInput").value;

    try {
      const res = await api.post("/api/v1/auth/login", { username, password });
      api.setToken(res.token);
      state.setUser(res.user);
      initApp();
    } catch (err) {
      errEl.textContent = err.message || "Invalid credentials";
      errEl.style.display = "block";
    }
  });
}

// Start Application on DOM Load
window.addEventListener("DOMContentLoaded", initApp);

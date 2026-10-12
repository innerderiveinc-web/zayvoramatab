/**
 * Login Screen View
 */

import { apiClient } from "../../../../packages/api-client/client.js";
import { state } from "../state.js";

export function renderLogin(container, onLoginSuccess) {
  container.innerHTML = `
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--matab-color-brand-primary); padding: 1.5rem;">
      <div class="card" style="max-width: 440px; width: 100%; padding: 2rem; box-shadow: 0 10px 25px rgba(0,0,0,0.2);">
        <div style="text-align: center; margin-bottom: 1.5rem;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🌿</div>
          <h1 style="font-size: 1.35rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
            ZAYVORA MATAB OS
          </h1>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-muted);">
            Phase 1 Platform Foundation (Multi-Tenant Core)
          </p>
        </div>

        <form id="loginForm">
          <div class="form-group">
            <label class="form-label" for="usernameInput">Username *</label>
            <input type="text" id="usernameInput" class="form-input" value="hakeem" required />
          </div>
          
          <div class="form-group">
            <label class="form-label" for="passwordInput">Password *</label>
            <input type="password" id="passwordInput" class="form-input" value="matab123" required />
          </div>

          <div id="loginErrorBox" style="display: none; background: var(--matab-color-status-danger-bg); color: var(--matab-color-status-danger); padding: 0.5rem; border-radius: var(--matab-radius-sm); font-size: 0.8rem; margin-bottom: 0.75rem;"></div>

          <button type="submit" id="submitLoginBtn" class="btn btn-primary" style="width: 100%; margin-top: 0.5rem;">
            Sign In to Matab OS ➔
          </button>
        </form>

        <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--matab-color-border-subtle); font-size: 0.75rem; color: var(--matab-color-text-muted); text-align: center;">
          <strong>Synthetic Test Accounts (Dev Seed):</strong><br />
          <code>admin</code> (Org Admin) | <code>hakeem</code> (Practitioner)<br />
          <code>reception</code> (Front Desk) | <code>auditor</code> (Read-Only)<br />
          Default Password: <code>matab123</code>
        </div>
      </div>
    </div>
  `;

  const form = container.querySelector("#loginForm");
  const errBox = container.querySelector("#loginErrorBox");
  const submitBtn = container.querySelector("#submitLoginBtn");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errBox.style.display = "none";
    submitBtn.disabled = true;
    submitBtn.textContent = "Authenticating...";

    const username = form.querySelector("#usernameInput").value.trim();
    const password = form.querySelector("#passwordInput").value;

    try {
      const res = await apiClient.post("/api/v1/auth/login", { username, password });
      apiClient.setToken(res.token);
      localStorage.setItem("matab_token", res.token);
      onLoginSuccess(res.user);
    } catch (err) {
      errBox.textContent = err.message || "Authentication failed.";
      errBox.style.display = "block";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Sign In to Matab OS ➔";
    }
  });
}

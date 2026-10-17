/**
 * Modern Clinical Login Screen — ZAYVORA MATAB OS
 * Hospital Information & Clinical Decision Support System
 */

import { apiClient } from "/packages/api-client/client.js";
import { state } from "../state.js";


export function renderLogin(container, onLoginSuccess) {
  container.innerHTML = `
    <div style="min-height: 100vh; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle at 50% 20%, #065f46 0%, #064e3b 60%, #022c22 100%); padding: 1.5rem;">
      <div class="card" style="max-width: 460px; width: 100%; padding: 2.25rem; border-radius: var(--matab-radius-xl); box-shadow: var(--matab-shadow-xl); border: 1px solid rgba(255, 255, 255, 0.2); background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(12px);">
        
        <div style="text-align: center; margin-bottom: 1.75rem;">
          <div style="display: inline-flex; align-items: center; justify-content: center; width: 56px; height: 56px; border-radius: 50%; background: var(--matab-color-brand-surface); border: 2px solid var(--matab-color-brand-subtle); font-size: 1.75rem; margin-bottom: 0.75rem; box-shadow: var(--matab-shadow-xs);">
            🌿
          </div>
          <h1 style="font-size: 1.4rem; font-weight: 800; color: var(--matab-color-brand-primary); margin-bottom: 0.35rem; letter-spacing: -0.01em;">
            ZAYVORA MATAB OS
          </h1>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); line-height: 1.4;">
            Clinical Information & Bedside Decision Support System<br />
            <span style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Integrated Unani Medicine & Biomedical Health Records</span>
          </p>
        </div>

        <!-- 1-Click Role Switcher Quick Access -->
        <div style="margin-bottom: 1.25rem;">
          <label style="display: block; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--matab-color-text-muted); margin-bottom: 0.5rem; text-align: center;">
            ⚡ Quick Role Access
          </label>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.45rem;">
            <button type="button" class="btn btn-secondary btn-sm btn-quick-role" data-user="hakeem" data-pass="matab123" style="font-size: 0.78rem; padding: 0.45rem 0.5rem; justify-content: flex-start; cursor: pointer;">
              <span>🩺</span> <strong>Hakim / Doctor</strong>
            </button>
            <button type="button" class="btn btn-secondary btn-sm btn-quick-role" data-user="pharmacy" data-pass="matab123" style="font-size: 0.78rem; padding: 0.45rem 0.5rem; justify-content: flex-start; cursor: pointer;">
              <span>💊</span> <strong>Pharmacist</strong>
            </button>
            <button type="button" class="btn btn-secondary btn-sm btn-quick-role" data-user="admin" data-pass="matab123" style="font-size: 0.78rem; padding: 0.45rem 0.5rem; justify-content: flex-start; cursor: pointer;">
              <span>🏛️</span> <strong>Admin / Director</strong>
            </button>
            <button type="button" class="btn btn-secondary btn-sm btn-quick-role" data-user="reception" data-pass="matab123" style="font-size: 0.78rem; padding: 0.45rem 0.5rem; justify-content: flex-start; cursor: pointer;">
              <span>📋</span> <strong>Front Desk</strong>
            </button>
          </div>
        </div>

        <form id="loginForm">
          <div class="form-group">
            <label class="form-label" for="usernameInput">Clinical Username</label>
            <input type="text" id="usernameInput" class="form-input" value="hakeem" autocomplete="username" required />
          </div>
          
          <div class="form-group" style="margin-bottom: 1.25rem;">
            <label class="form-label" for="passwordInput">Password / Credentials</label>
            <input type="password" id="passwordInput" class="form-input" value="matab123" autocomplete="current-password" required />
          </div>

          <div id="loginErrorBox" style="display: none; background: var(--matab-color-status-danger-bg); color: var(--matab-color-status-danger); border: 1px solid var(--matab-color-status-danger-border); padding: 0.65rem; border-radius: var(--matab-radius-md); font-size: 0.82rem; margin-bottom: 1rem;"></div>

          <button type="submit" id="submitLoginBtn" class="btn btn-primary" style="width: 100%; padding: 0.75rem 1rem; font-size: 0.95rem; font-weight: 700; border-radius: var(--matab-radius-md);">
            Sign In to Clinical Workspace ➔
          </button>
        </form>

        <div style="margin-top: 1rem; text-align: center;">
          <button type="button" id="btnOpenRegisterModal" class="btn btn-secondary btn-sm" style="width: 100%; border-style: dashed; padding: 0.55rem; font-size: 0.82rem; justify-content: center; background: #ffffff;">
            <span>🏢</span> <strong>Register New Matab / Clinic (Onboard Facility)</strong>
          </button>
        </div>

        <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--matab-color-border-subtle); display: flex; align-items: center; justify-content: space-between; font-size: 0.72rem; color: var(--matab-color-text-muted);">
          <span style="display: inline-flex; align-items: center; gap: 0.35rem;">
            <span style="width: 6px; height: 6px; border-radius: 50%; background: #22c55e;"></span>
            ABDM & HL7 FHIR Gateway Active
          </span>
          <span>ZAYVORA Hospital OS • Enterprise Edition 2026.1</span>
        </div>
      </div>
    </div>

    <!-- Register Clinic Modal Placeholder -->
    <div id="registerClinicModalContainer"></div>
  `;

  const form = container.querySelector("#loginForm");
  const errBox = container.querySelector("#loginErrorBox");
  const submitBtn = container.querySelector("#submitLoginBtn");
  const userInput = container.querySelector("#usernameInput");
  const passInput = container.querySelector("#passwordInput");

  async function performLogin(username, password, triggeredBtn = null) {
    errBox.style.display = "none";
    submitBtn.disabled = true;
    submitBtn.textContent = "Verifying Credentials...";
    if (triggeredBtn) {
      triggeredBtn.style.opacity = "0.7";
      triggeredBtn.setAttribute("data-original-text", triggeredBtn.innerHTML);
      triggeredBtn.innerHTML = `<span>⏳</span> <strong>Logging in...</strong>`;
    }

    try {
      const res = await apiClient.post("/api/v1/auth/login", { username, password });
      apiClient.setToken(res.token);
      localStorage.setItem("matab_token", res.token);
      if (typeof onLoginSuccess === "function") {
        await onLoginSuccess(res.user);
      }
    } catch (err) {
      console.error("Login flow error:", err);
      errBox.textContent = err.message || "Authentication failed. Please check your credentials.";
      errBox.style.display = "block";
      if (triggeredBtn && triggeredBtn.dataset.originalText) {
        triggeredBtn.innerHTML = triggeredBtn.dataset.originalText;
        triggeredBtn.style.opacity = "1";
      }
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Sign In to Clinical Workspace ➔";
    }
  }

  // Expose global launcher so index.html inline script can directly invoke shell mounting
  window.__LAUNCH_MATAB_SHELL__ = onLoginSuccess;

  // Quick Role selection buttons — 1-click immediate access!
  container.querySelectorAll(".btn-quick-role").forEach(btn => {
    btn.addEventListener("click", async () => {
      const u = btn.dataset.user;
      const p = btn.dataset.pass;
      userInput.value = u;
      passInput.value = p;
      await performLogin(u, p, btn);
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    await performLogin(userInput.value.trim(), passInput.value);
  });

  // Self-Service Clinic Registration Modal
  const btnOpenRegister = container.querySelector("#btnOpenRegisterModal");
  const modalContainer = container.querySelector("#registerClinicModalContainer");

  btnOpenRegister?.addEventListener("click", () => {
    modalContainer.innerHTML = `
      <div class="modal-backdrop" id="modalBackdropRegister">
        <div class="modal-box" style="max-width: 560px;">
          <div class="modal-header">
            <h3 style="margin: 0; display: flex; align-items: center; gap: 0.5rem; font-size: 1.15rem;">
              <span>🏢</span> Register New Matab / Hospital
            </h3>
            <button type="button" class="btn btn-secondary btn-sm" id="btnCloseRegisterModal" style="padding: 0.2rem 0.5rem;">✕</button>
          </div>
          <form id="clinicRegisterForm">
            <div class="modal-body" style="padding: 1.25rem; max-height: 70vh; overflow-y: auto;">
              <div style="background: var(--matab-color-brand-surface); border: 1px solid var(--matab-color-brand-subtle); padding: 0.75rem; border-radius: var(--matab-radius-md); font-size: 0.82rem; color: var(--matab-color-brand-primary); margin-bottom: 1rem; line-height: 1.4;">
                Establish a new clinical tenant, configure the primary OPD facility, and provision your Hospital Director root account.
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                <div class="form-group" style="grid-column: span 2;">
                  <label class="form-label">Hospital / Matab Name *</label>
                  <input type="text" id="regOrgName" class="form-input" placeholder="e.g. Al-Hikmah Unani Medical Center" required />
                </div>

                <div class="form-group">
                  <label class="form-label">Clinic Code Slug *</label>
                  <input type="text" id="regOrgCode" class="form-input" placeholder="e.g. HIKMAH-01" style="text-transform: uppercase;" required />
                </div>

                <div class="form-group">
                  <label class="form-label">Facility Profile *</label>
                  <select id="regProfileType" class="form-select">
                    <option value="MATAB">Matab / Unani OPD</option>
                    <option value="HOSPITAL">Integrated AYUSH Hospital</option>
                    <option value="CLINIC">Daycare & Wellness Clinic</option>
                  </select>
                </div>

                <div class="form-group" style="grid-column: span 2;">
                  <label class="form-label">Director / Administrator Full Name *</label>
                  <input type="text" id="regAdminName" class="form-input" placeholder="e.g. Dr. Hakeem Salman Khan" required />
                </div>

                <div class="form-group">
                  <label class="form-label">Admin Username *</label>
                  <input type="text" id="regAdminUsername" class="form-input" placeholder="e.g. hakeem.salman" autocomplete="username" required />
                </div>

                <div class="form-group">
                  <label class="form-label">Official Email</label>
                  <input type="email" id="regAdminEmail" class="form-input" placeholder="e.g. admin@hikmah.org" />
                </div>

                <div class="form-group" style="grid-column: span 2;">
                  <label class="form-label">Admin Password * (Min 6 chars)</label>
                  <input type="password" id="regAdminPassword" class="form-input" placeholder="Enter secure administrator password" autocomplete="new-password" required minlength="6" />
                </div>
              </div>

              <div id="regErrorBox" style="display: none; background: var(--matab-color-status-danger-bg); color: var(--matab-color-status-danger); border: 1px solid var(--matab-color-status-danger-border); padding: 0.65rem; border-radius: var(--matab-radius-md); font-size: 0.82rem; margin-top: 0.75rem;"></div>
            </div>
            <div class="modal-footer" style="padding: 0.75rem 1.25rem; display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button type="button" class="btn btn-secondary" id="btnCancelRegister">Cancel</button>
              <button type="submit" class="btn btn-primary" id="btnSubmitRegister">
                Register Matab & Launch OS ➔
              </button>
            </div>
          </form>
        </div>
      </div>
    `;

    const regForm = modalContainer.querySelector("#clinicRegisterForm");
    const regErrBox = modalContainer.querySelector("#regErrorBox");
    const regSubmitBtn = modalContainer.querySelector("#btnSubmitRegister");
    const closeBtn = modalContainer.querySelector("#btnCloseRegisterModal");
    const cancelBtn = modalContainer.querySelector("#btnCancelRegister");

    const closeRegisterModal = () => { modalContainer.innerHTML = ""; };
    closeBtn.addEventListener("click", closeRegisterModal);
    cancelBtn.addEventListener("click", closeRegisterModal);

    // Auto-slugify clinic code based on name
    modalContainer.querySelector("#regOrgName").addEventListener("input", (e) => {
      const codeInput = modalContainer.querySelector("#regOrgCode");
      if (!codeInput.dataset.manuallyEdited) {
        const words = e.target.value.trim().split(/\s+/).filter(Boolean);
        if (words.length > 0) {
          codeInput.value = words.slice(0, 3).map(w => w.slice(0, 4).toUpperCase()).join("-") + "-01";
        }
      }
    });

    modalContainer.querySelector("#regOrgCode").addEventListener("input", () => {
      modalContainer.querySelector("#regOrgCode").dataset.manuallyEdited = "true";
    });

    regForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      regErrBox.style.display = "none";
      regSubmitBtn.disabled = true;
      regSubmitBtn.textContent = "Deploying Clinic & Establishing Tenant...";

      const payload = {
        org_name: modalContainer.querySelector("#regOrgName").value.trim(),
        org_code: modalContainer.querySelector("#regOrgCode").value.trim().toUpperCase(),
        profile_type: modalContainer.querySelector("#regProfileType").value,
        admin_name: modalContainer.querySelector("#regAdminName").value.trim(),
        admin_username: modalContainer.querySelector("#regAdminUsername").value.trim(),
        admin_email: modalContainer.querySelector("#regAdminEmail").value.trim(),
        admin_password: modalContainer.querySelector("#regAdminPassword").value
      };

      try {
        const res = await apiClient.post("/api/v1/auth/register-clinic", payload);
        apiClient.setToken(res.token);
        localStorage.setItem("matab_token", res.token);
        closeRegisterModal();
        if (window.showToast) {
          window.showToast("Clinic successfully registered! Launching workspace...", "success");
        }
        onLoginSuccess(res.user);
      } catch (err) {
        regErrBox.textContent = err.message || "Failed to register clinic. Please verify inputs.";
        regErrBox.style.display = "block";
      } finally {
        regSubmitBtn.disabled = false;
        regSubmitBtn.textContent = "Register Matab & Launch OS ➔";
      }
    });
  });
}

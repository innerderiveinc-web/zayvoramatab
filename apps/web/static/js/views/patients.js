/**
 * Patients View — Master Patient Index, Search, Registration, Duplicate Resolution, Patient 360 & Timeline
 */

import { apiClient } from "/packages/api-client/client.js";
import { state } from "../state.js";

let currentSearchQuery = "";
let searchDebounceTimer = null;

export function renderPatients(container, targetPatientId = null) {
  if (targetPatientId) {
    renderPatient360(container, targetPatientId);
    return;
  }

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.75rem;">
      <div>
        <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Patient Registry</h1>
        <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
          Master Patient Index, Scoped Search & Longitudinal Patient 360
        </p>
      </div>
      <div>
        <button id="btn-open-register" class="btn btn-primary">
          <span style="font-size: 1.1rem;">+</span> Register New Patient
        </button>
      </div>
    </div>

    <!-- Scoped Search Box -->
    <div class="card" style="margin-bottom: 1.25rem;">
      <div style="display: flex; gap: 0.75rem; align-items: center;">
        <div style="flex: 1; position: relative;">
          <input 
            type="text" 
            id="patient-search-input" 
            class="form-input" 
            placeholder="Search by Name (English/Urdu/Hindi), Phone, or MRN..." 
            value="${escapeHtml(currentSearchQuery)}"
          />
        </div>
        <button id="btn-clear-search" class="btn btn-secondary">Clear</button>
      </div>
    </div>

    <!-- Search Results / Directory Table -->
    <div class="card" id="patient-results-card">
      <div id="patient-results-loading" style="display: none; padding: 2rem; text-align: center; color: var(--matab-color-text-secondary);">
        Searching patient directory...
      </div>
      <div id="patient-results-container"></div>
    </div>

    <div id="modal-container"></div>
  `;

  const searchInput = container.querySelector("#patient-search-input");
  const clearBtn = container.querySelector("#btn-clear-search");
  const registerBtn = container.querySelector("#btn-open-register");

  registerBtn.addEventListener("click", () => openRegisterModal(container));

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    currentSearchQuery = "";
    loadPatients(container, "");
  });

  searchInput.addEventListener("input", (e) => {
    currentSearchQuery = e.target.value.trim();
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      loadPatients(container, currentSearchQuery);
    }, 250);
  });

  // Initial load
  loadPatients(container, currentSearchQuery);
}

async function loadPatients(container, query = "") {
  const resultsContainer = container.querySelector("#patient-results-container");
  const loading = container.querySelector("#patient-results-loading");
  if (!resultsContainer) return;

  loading.style.display = "block";
  resultsContainer.innerHTML = "";

  try {
    const data = await apiClient.get("/api/v1/patients", { q: query, limit: 25 });
    loading.style.display = "none";

    if (!data.patients || data.patients.length === 0) {
      resultsContainer.innerHTML = `
        <div style="text-align: center; padding: 2.5rem 1rem; color: var(--matab-color-text-secondary);">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">🔍</div>
          <p style="font-weight: 600; margin-bottom: 0.5rem;">No matching patient records found</p>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-muted); margin-bottom: 1rem;">
            Try a different search term or register a new patient.
          </p>
          <button id="btn-empty-register" class="btn btn-primary btn-sm">+ Register Patient</button>
        </div>
      `;
      const emptyRegBtn = resultsContainer.querySelector("#btn-empty-register");
      if (emptyRegBtn) {
        emptyRegBtn.addEventListener("click", () => openRegisterModal(container));
      }
      return;
    }

    resultsContainer.innerHTML = `
      <div style="overflow-x: auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>MRN</th>
              <th>Patient Name</th>
              <th>Age / DOB</th>
              <th>Sex</th>
              <th>Contact Phone</th>
              <th>Status</th>
              <th style="text-align: right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${data.patients.map(p => `
              <tr>
                <td><code style="font-weight: 700; color: var(--matab-color-brand-primary);">${p.mrn}</code></td>
                <td>
                  <strong>${escapeHtml(p.display_name)}</strong>
                  ${p.preferred_language ? `<span style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-left: 0.35rem;">(${p.preferred_language.toUpperCase()})</span>` : ""}
                </td>
                <td>${formatAgeDob(p)}</td>
                <td><span class="badge badge-info">${p.sex || "UNKNOWN"}</span></td>
                <td>${p.primary_phone ? escapeHtml(p.primary_phone) : '<span style="color: var(--matab-color-text-muted);">None</span>'}</td>
                <td>
                  <span class="badge ${p.status === 'ACTIVE' ? 'badge-success' : 'badge-warning'}">
                    ${p.status}
                  </span>
                </td>
                <td style="text-align: right; white-space: nowrap;">
                  <button class="btn btn-secondary btn-sm btn-open-360" data-id="${p.id}">
                    Patient 360
                  </button>
                  <button class="btn btn-primary btn-sm btn-new-enc" data-id="${p.id}">
                    New Visit
                  </button>
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      </div>
      <div style="margin-top: 0.75rem; font-size: 0.8rem; color: var(--matab-color-text-muted); text-align: right;">
        Showing ${data.patients.length} of ${data.total} patient records
      </div>
    `;

    resultsContainer.querySelectorAll(".btn-open-360").forEach(btn => {
      btn.addEventListener("click", () => {
        renderPatient360(container, btn.getAttribute("data-id"));
      });
    });

    resultsContainer.querySelectorAll(".btn-new-enc").forEach(btn => {
      btn.addEventListener("click", async () => {
        const patientId = btn.getAttribute("data-id");
        const pData = await apiClient.get(`/api/v1/patients/${patientId}`);
        openNewEncounterModal(container, pData.patient, () => {
          renderPatient360(container, patientId);
        });
      });
    });

  } catch (err) {
    loading.style.display = "none";
    resultsContainer.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load patients: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

// -------------------------------------------------------------
// PATIENT 360 & LONGITUDINAL TIMELINE
// -------------------------------------------------------------

async function renderPatient360(container, patientId) {
  container.innerHTML = `
    <div style="padding: 2rem; text-align: center; color: var(--matab-color-text-secondary);">
      Loading Patient 360...
    </div>
  `;

  try {
    const data = await apiClient.get(`/api/v1/patients/${patientId}`);
    const p = data.patient;

    container.innerHTML = `
      <!-- Back Header -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.75rem;">
        <div>
          <button id="btn-back-dir" class="btn btn-secondary btn-sm" style="margin-bottom: 0.5rem;">
            ← Back to Patient Directory
          </button>
          <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
            <h1 style="font-size: 1.5rem; color: var(--matab-color-brand-primary); margin: 0;">
              ${escapeHtml(p.display_name)}
            </h1>
            <code style="background: var(--matab-color-bg-muted); padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700;">
              ${p.mrn}
            </code>
            <span class="badge ${p.status === 'ACTIVE' ? 'badge-success' : 'badge-warning'}">${p.status}</span>
          </div>
          <div style="color: var(--matab-color-text-secondary); font-size: 0.85rem; margin-top: 0.25rem;">
            ${formatAgeDob(p)} • Sex: <strong>${p.sex}</strong> • Language: <strong>${(p.preferred_language || "ur").toUpperCase()}</strong>
          </div>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button id="btn-edit-demo" class="btn btn-secondary">
            ✎ Edit Demographics
          </button>
          <button id="btn-p360-new-enc" class="btn btn-primary">
            + New Encounter
          </button>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="tab-group">
        <button class="tab-btn active" data-tab="overview">Overview & Demographics</button>
        <button class="tab-btn" data-tab="timeline">Longitudinal Timeline</button>
        <button class="tab-btn" data-tab="consents">Consents & Preferences</button>
        <button class="tab-btn" data-tab="duplicates">Duplicate Resolution</button>
      </div>

      <div id="tab-content-area"></div>
      <div id="modal-container"></div>
    `;

    container.querySelector("#btn-back-dir").addEventListener("click", () => {
      renderPatients(container);
    });

    container.querySelector("#btn-edit-demo").addEventListener("click", () => {
      openEditDemographicsModal(container, p, () => renderPatient360(container, patientId));
    });

    container.querySelector("#btn-p360-new-enc").addEventListener("click", () => {
      openNewEncounterModal(container, p, () => renderPatient360(container, patientId));
    });

    const tabBtns = container.querySelectorAll(".tab-btn");
    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        tabBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        renderTab(container, btn.getAttribute("data-tab"), data);
      });
    });

    // Default Tab
    renderTab(container, "overview", data);

  } catch (err) {
    container.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load Patient 360: ${escapeHtml(err.message)}
      </div>
      <button class="btn btn-secondary" onclick="window.location.reload()">Reload</button>
    `;
  }
}

function renderTab(container, tabName, data) {
  const contentArea = container.querySelector("#tab-content-area");
  const p = data.patient;

  if (tabName === "overview") {
    contentArea.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.25rem;">
        
        <!-- Demographics Card -->
        <div class="card">
          <h3 style="font-size: 1.05rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem;">
            👤 Demographics
          </h3>
          <table class="data-table" style="font-size: 0.85rem;">
            <tr><th style="width: 40%;">Full Given Name</th><td>${escapeHtml(p.given_name)}</td></tr>
            <tr><th>Family / Last Name</th><td>${escapeHtml(p.family_name || "—")}</td></tr>
            <tr><th>Display Name</th><td>${escapeHtml(p.display_name)}</td></tr>
            <tr><th>Date of Birth</th><td>${p.date_of_birth || "Not recorded (Estimated age used)"}</td></tr>
            <tr><th>Estimated Age</th><td>${p.estimated_age ? `${p.estimated_age} years (Recorded: ${p.age_recorded_at ? p.age_recorded_at.split('T')[0] : ''})` : "—"}</td></tr>
            <tr><th>Sex at Birth</th><td>${p.sex}</td></tr>
            <tr><th>Preferred Language</th><td>${(p.preferred_language || "ur").toUpperCase()}</td></tr>
            <tr><th>Record Version</th><td><span class="badge badge-info">v${p.version}</span></td></tr>
          </table>
        </div>

        <!-- Contacts Card -->
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <h3 style="font-size: 1.05rem; color: var(--matab-color-brand-primary); margin: 0;">
              📞 Contact Points
            </h3>
          </div>
          ${data.contacts.length === 0 ? `
            <p style="color: var(--matab-color-text-muted); font-size: 0.85rem;">No contacts recorded.</p>
          ` : `
            <table class="data-table" style="font-size: 0.85rem;">
              <thead><tr><th>Type</th><th>Value</th><th>Use</th></tr></thead>
              <tbody>
                ${data.contacts.map(c => `
                  <tr>
                    <td><strong>${c.contact_type}</strong> ${c.is_preferred ? '<span class="badge badge-success">Primary</span>' : ''}</td>
                    <td>${escapeHtml(c.contact_value)}</td>
                    <td>${c.use || "MOBILE"}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          `}
        </div>

        <!-- Identifiers Card -->
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <h3 style="font-size: 1.05rem; color: var(--matab-color-brand-primary); margin: 0;">
              🪪 Identifiers
            </h3>
            <button id="btn-add-id" class="btn btn-secondary btn-sm">+ Add Identifier</button>
          </div>
          ${data.identifiers.length === 0 ? `
            <p style="color: var(--matab-color-text-muted); font-size: 0.85rem;">No external identifiers registered.</p>
          ` : `
            <table class="data-table" style="font-size: 0.85rem;">
              <thead><tr><th>Type</th><th>Identifier</th><th>Status</th><th>Action</th></tr></thead>
              <tbody>
                ${data.identifiers.map(id => `
                  <tr style="${id.is_retired ? 'opacity: 0.6; text-decoration: line-through;' : ''}">
                    <td><strong>${id.identifier_type}</strong></td>
                    <td><code>${escapeHtml(id.identifier_value)}</code></td>
                    <td>
                      ${id.is_retired 
                        ? `<span class="badge badge-danger">Retired (${escapeHtml(id.retired_reason || '')})</span>` 
                        : '<span class="badge badge-success">Active</span>'
                      }
                    </td>
                    <td>
                      ${!id.is_retired ? `
                        <button class="btn btn-secondary btn-sm btn-retire-id" data-id="${id.id}" style="font-size: 0.75rem; padding: 0.15rem 0.4rem;">
                          Retire
                        </button>
                      ` : "—"}
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          `}
        </div>

        <!-- Primary Address -->
        <div class="card">
          <h3 style="font-size: 1.05rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem;">
            📍 Address
          </h3>
          ${data.addresses.length === 0 ? `
            <p style="color: var(--matab-color-text-muted); font-size: 0.85rem;">No address recorded.</p>
          ` : `
            <p style="font-size: 0.9rem; line-height: 1.6;">
              ${escapeHtml(data.addresses[0].address_line1 || "")}<br/>
              ${data.addresses[0].address_line2 ? `${escapeHtml(data.addresses[0].address_line2)}<br/>` : ""}
              ${escapeHtml(data.addresses[0].city || "")}, ${escapeHtml(data.addresses[0].state || "")} ${escapeHtml(data.addresses[0].postal_code || "")}<br/>
              <strong>${escapeHtml(data.addresses[0].country || "IN")}</strong>
            </p>
          `}
        </div>

      </div>
    `;

    const addIdBtn = contentArea.querySelector("#btn-add-id");
    if (addIdBtn) {
      addIdBtn.addEventListener("click", () => {
        openAddIdentifierModal(container, p.id, () => renderPatient360(container, p.id));
      });
    }

    contentArea.querySelectorAll(".btn-retire-id").forEach(btn => {
      btn.addEventListener("click", () => {
        const idId = btn.getAttribute("data-id");
        openRetireIdentifierModal(container, p.id, idId, () => renderPatient360(container, p.id));
      });
    });

  } else if (tabName === "timeline") {
    renderTimelineTab(contentArea, p.id);
  } else if (tabName === "consents") {
    renderConsentsTab(container, contentArea, p.id, data.consents);
  } else if (tabName === "duplicates") {
    renderDuplicatesTab(container, contentArea, p.id);
  }
}

async function renderTimelineTab(contentArea, patientId) {
  contentArea.innerHTML = `
    <div style="padding: 1.5rem; text-align: center; color: var(--matab-color-text-secondary);">
      Loading longitudinal timeline...
    </div>
  `;

  try {
    const data = await apiClient.get(`/api/v1/patients/${patientId}/timeline`);
    if (!data.timeline || data.timeline.length === 0) {
      contentArea.innerHTML = `
        <div class="card" style="text-align: center; padding: 3rem 1rem;">
          <div style="font-size: 2rem; margin-bottom: 0.5rem;">📜</div>
          <p style="font-weight: 600; color: var(--matab-color-text-secondary);">No timeline events recorded yet</p>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-muted);">
            Create a new encounter or record a consent decision to begin the longitudinal clinical history.
          </p>
        </div>
      `;
      return;
    }

    contentArea.innerHTML = `
      <div class="timeline-list">
        ${data.timeline.map(item => `
          <div class="timeline-item">
            <div class="timeline-dot"></div>
            <div class="timeline-card">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem; flex-wrap: wrap; gap: 0.5rem;">
                <div>
                  <strong style="color: var(--matab-color-brand-primary); font-size: 0.95rem;">
                    ${escapeHtml(item.title)}
                  </strong>
                  <span class="badge ${getStatusBadgeClass(item.status)}" style="margin-left: 0.5rem;">
                    ${item.status}
                  </span>
                </div>
                <div style="font-size: 0.8rem; color: var(--matab-color-text-muted);">
                  ${formatTimestamp(item.timestamp)}
                </div>
              </div>
              <div style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 0.25rem;">
                Facility: <strong>${escapeHtml(item.facility_name)}</strong> • Actor: <strong>${escapeHtml(item.actor_name)}</strong>
              </div>
              ${item.details && item.details.reason_for_visit ? `
                <div style="background: var(--matab-color-bg-muted); padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem; margin-top: 0.5rem;">
                  <strong>Chief Complaint:</strong> ${escapeHtml(item.details.reason_for_visit)}
                </div>
              ` : ""}
              ${item.details && item.details.cancellation_reason ? `
                <div style="background: #fef2f2; color: #991b1b; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.85rem; margin-top: 0.5rem;">
                  <strong>Cancellation Reason:</strong> ${escapeHtml(item.details.cancellation_reason)}
                </div>
              ` : ""}
            </div>
          </div>
        `).join("")}
      </div>
    `;

  } catch (err) {
    contentArea.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load timeline: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderConsentsTab(container, contentArea, patientId, consents) {
  contentArea.innerHTML = `
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <div>
          <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin: 0;">
            Consent & Communication Preferences
          </h3>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">
            Explicit, unassumed consent records. Blank values are never interpreted as opt-in.
          </p>
        </div>
        <button id="btn-record-consent" class="btn btn-primary btn-sm">+ Record Consent</button>
      </div>

      ${consents.length === 0 ? `
        <div class="alert-box alert-warning">
          No consent recorded. By policy, automated communications and data sharing are inactive.
        </div>
      ` : `
        <table class="data-table">
          <thead>
            <tr>
              <th>Purpose</th>
              <th>Status</th>
              <th>Recorded At</th>
              <th>Method</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${consents.map(c => `
              <tr>
                <td><strong>${escapeHtml(c.purpose.replace(/_/g, " "))}</strong></td>
                <td>
                  <span class="badge ${c.status === 'GRANTED' ? 'badge-success' : c.status === 'WITHDRAWN' ? 'badge-danger' : 'badge-warning'}">
                    ${c.status}
                  </span>
                </td>
                <td>${formatTimestamp(c.recorded_at)}</td>
                <td>${escapeHtml(c.source_method || "VERBAL_PATIENT")}</td>
                <td>
                  ${c.status === 'GRANTED' ? `
                    <button class="btn btn-secondary btn-sm btn-withdraw-consent" data-id="${c.id}" style="font-size: 0.75rem; padding: 0.2rem 0.5rem;">
                      Withdraw
                    </button>
                  ` : c.withdrawal_reason ? `<span style="font-size: 0.8rem; color: var(--matab-color-text-muted);">${escapeHtml(c.withdrawal_reason)}</span>` : "—"}
                </td>
              </tr>
            `).join("")}
          </tbody>
        </table>
      `}
    </div>
  `;

  contentArea.querySelector("#btn-record-consent").addEventListener("click", () => {
    openRecordConsentModal(container, patientId, () => renderPatient360(container, patientId));
  });

  contentArea.querySelectorAll(".btn-withdraw-consent").forEach(btn => {
    btn.addEventListener("click", () => {
      const consentId = btn.getAttribute("data-id");
      openWithdrawConsentModal(container, patientId, consentId, () => renderPatient360(container, patientId));
    });
  });
}

async function renderDuplicatesTab(container, contentArea, patientId) {
  contentArea.innerHTML = `
    <div style="padding: 1.5rem; text-align: center; color: var(--matab-color-text-secondary);">
      Checking duplicate resolution queue...
    </div>
  `;

  try {
    const data = await apiClient.get(`/api/v1/patients/${patientId}/duplicate-candidates`);
    const candidates = data.duplicate_candidates || [];

    contentArea.innerHTML = `
      <div class="card">
        <div style="margin-bottom: 1rem;">
          <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin: 0;">
            Deterministic Duplicate Resolution Queue
          </h3>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">
            Potential duplicate matches flagged by deterministic clinical heuristics. Automatic merges are strictly prohibited.
          </p>
        </div>

        ${candidates.length === 0 ? `
          <div class="alert-box alert-success">
            ✓ No duplicate candidate records flagged for this patient.
          </div>
        ` : `
          <div style="display: flex; flex-direction: column; gap: 1rem;">
            ${candidates.map(c => `
              <div style="border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-md); padding: 1rem; background: ${c.status === 'PENDING_REVIEW' ? '#fffbeb' : '#f8fafc'};">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
                  <div>
                    <strong>Flagged Candidate:</strong> 
                    <span style="font-size: 1.05rem; font-weight: 700; color: var(--matab-color-brand-primary);">
                      ${escapeHtml(c.candidate_name)}
                    </span>
                    (MRN: <code>${escapeHtml(c.candidate_mrn)}</code>)
                  </div>
                  <div>
                    <span class="badge ${c.status === 'PENDING_REVIEW' ? 'badge-warning' : 'badge-info'}">
                      ${c.status.replace(/_/g, " ")}
                    </span>
                  </div>
                </div>

                <div style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 0.5rem;">
                  Confidence Score: <strong>${Math.round(c.match_score * 100)}%</strong> • Triggered Rules: <code>${escapeHtml(c.match_rules)}</code>
                </div>

                ${c.review_notes ? `
                  <div style="font-size: 0.8rem; background: rgba(0,0,0,0.05); padding: 0.35rem 0.6rem; border-radius: 4px; margin-bottom: 0.5rem;">
                    <strong>Review Notes:</strong> ${escapeHtml(c.review_notes)}
                  </div>
                ` : ""}

                ${c.status === 'PENDING_REVIEW' ? `
                  <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
                    <button class="btn btn-secondary btn-sm btn-resolve-diff" data-id="${c.id}">
                      ✓ Confirm Different Person
                    </button>
                    <button class="btn btn-secondary btn-sm btn-resolve-defer" data-id="${c.id}">
                      ⏱ Defer For Review
                    </button>
                  </div>
                ` : ""}
              </div>
            `).join("")}
          </div>
        `}
      </div>
    `;

    contentArea.querySelectorAll(".btn-resolve-diff").forEach(btn => {
      btn.addEventListener("click", () => {
        resolveDuplicate(container, patientId, btn.getAttribute("data-id"), "CONFIRMED_DIFFERENT");
      });
    });

    contentArea.querySelectorAll(".btn-resolve-defer").forEach(btn => {
      btn.addEventListener("click", () => {
        resolveDuplicate(container, patientId, btn.getAttribute("data-id"), "DEFERRED");
      });
    });

  } catch (err) {
    contentArea.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load duplicate queue: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

async function resolveDuplicate(container, patientId, candidateId, decision) {
  const notes = prompt(`Enter resolution justification for ${decision.replace(/_/g, " ")}:`, "Human operator verified separate clinical identities");
  if (notes === null) return;

  try {
    await apiClient.post(`/api/v1/patients/${patientId}/duplicate-resolutions/${candidateId}`, {
      decision,
      notes: notes.trim()
    });
    alert("Duplicate resolution recorded successfully.");
    renderPatient360(container, patientId);
  } catch (err) {
    alert(`Failed to resolve duplicate: ${err.message}`);
  }
}

// -------------------------------------------------------------
// REGISTRATION MODAL WITH DUPLICATE RESOLUTION INTERLOCK
// -------------------------------------------------------------

function openRegisterModal(container) {
  const modalContainer = container.querySelector("#modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Register New Patient</h3>
          <button id="modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div id="modal-alert-area"></div>
          
          <form id="patient-reg-form">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
              <div class="form-group">
                <label class="form-label">Given Name *</label>
                <input type="text" id="reg-given-name" class="form-input" placeholder="e.g. Tariq / طارق" required />
              </div>
              <div class="form-group">
                <label class="form-label">Family / Last Name</label>
                <input type="text" id="reg-family-name" class="form-input" placeholder="e.g. Ahmad / احمد" />
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">Contact Mobile Number *</label>
              <input type="tel" id="reg-phone" class="form-input" placeholder="e.g. +91 98765 43210" required />
              <div style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-top: 0.25rem;">
                International and localized formats supported. Normalized automatically.
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
              <div class="form-group">
                <label class="form-label">Date of Birth</label>
                <input type="date" id="reg-dob" class="form-input" />
              </div>
              <div class="form-group">
                <label class="form-label">Or Estimated Age (Years)</label>
                <input type="number" id="reg-est-age" class="form-input" min="0" max="130" placeholder="e.g. 45" />
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
              <div class="form-group">
                <label class="form-label">Sex at Birth *</label>
                <select id="reg-sex" class="form-select">
                  <option value="MALE">Male</option>
                  <option value="FEMALE">Female</option>
                  <option value="OTHER">Other</option>
                  <option value="UNKNOWN">Unknown / Not Recorded</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Preferred Language</label>
                <select id="reg-lang" class="form-select">
                  <option value="ur">Urdu (اردو)</option>
                  <option value="hi">Hindi (हिंदी)</option>
                  <option value="en">English</option>
                </select>
              </div>
            </div>

            <div class="form-group">
              <label class="form-label">National / ABHA Identifier (Optional)</label>
              <input type="text" id="reg-national-id" class="form-input" placeholder="e.g. ABHA-1234 or Aadhaar Ref" />
            </div>

            <div class="form-group">
              <label class="form-label">Residential Address</label>
              <input type="text" id="reg-address" class="form-input" placeholder="Street, Locality, City" />
            </div>

            <div class="form-group" style="background: var(--matab-color-bg-muted); padding: 0.75rem; border-radius: var(--matab-radius-md);">
              <label style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; cursor: pointer;">
                <input type="checkbox" id="reg-consent-care" checked />
                <span>Patient explicitly requested Unani medical care (General Care Consent)</span>
              </label>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button id="modal-cancel" class="btn btn-secondary">Cancel</button>
          <button id="modal-submit-reg" class="btn btn-primary">Save & Open Patient 360</button>
        </div>
      </div>
    </div>
  `;

  const closeBtn = modalContainer.querySelector("#modal-close");
  const cancelBtn = modalContainer.querySelector("#modal-cancel");
  const submitBtn = modalContainer.querySelector("#modal-submit-reg");
  const alertArea = modalContainer.querySelector("#modal-alert-area");

  const closeModal = () => { modalContainer.innerHTML = ""; };
  closeBtn.addEventListener("click", closeModal);
  cancelBtn.addEventListener("click", closeModal);

  submitBtn.addEventListener("click", () => submitPatientRegistration(container, null));

  async function submitPatientRegistration(container, overrideDecision = null, overrideNotes = "") {
    alertArea.innerHTML = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Validating...";

    const givenName = modalContainer.querySelector("#reg-given-name").value.trim();
    const familyName = modalContainer.querySelector("#reg-family-name").value.trim();
    const phone = modalContainer.querySelector("#reg-phone").value.trim();
    const dob = modalContainer.querySelector("#reg-dob").value.trim();
    const estAgeVal = modalContainer.querySelector("#reg-est-age").value.trim();
    const sex = modalContainer.querySelector("#reg-sex").value;
    const lang = modalContainer.querySelector("#reg-lang").value;
    const nationalId = modalContainer.querySelector("#reg-national-id").value.trim();
    const address = modalContainer.querySelector("#reg-address").value.trim();
    const consentCare = modalContainer.querySelector("#reg-consent-care").checked ? "GRANTED" : "REFUSED";

    if (!givenName || !phone) {
      alertArea.innerHTML = `<div class="alert-box alert-danger">Given name and contact phone are required.</div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = "Save & Open Patient 360";
      return;
    }

    const payload = {
      given_name: givenName,
      family_name: familyName || null,
      phone: phone,
      date_of_birth: dob || null,
      estimated_age: estAgeVal ? parseInt(estAgeVal, 10) : null,
      sex: sex,
      preferred_language: lang,
      national_id: nationalId || null,
      address_line1: address || null,
      consent_general_care: consentCare
    };

    if (overrideDecision) {
      payload.override_decision = overrideDecision;
      payload.override_notes = overrideNotes;
    }

    try {
      const resp = await apiClient.post("/api/v1/patients", payload);
      closeModal();
      renderPatient360(container, resp.patient.id);
    } catch (err) {
      submitBtn.disabled = false;
      submitBtn.textContent = "Save & Open Patient 360";

      if (err.status === 409 && err.details && err.details.duplicate_candidates) {
        const candidates = err.details.duplicate_candidates;
        // Render Duplicate Interlock UI
        alertArea.innerHTML = `
          <div class="alert-box alert-warning">
            <h4 style="margin-bottom: 0.35rem; color: #92400e;">⚠️ Potential Duplicate Patient Detected</h4>
            <p style="font-size: 0.85rem; margin-bottom: 0.75rem;">
              The system found ${candidates.length} matching patient record(s) based on phone number or name.
              Automatic merges are prohibited. Please review:
            </p>
            ${candidates.map(c => `
              <div style="background: #ffffff; border: 1px solid #fde68a; border-radius: 4px; padding: 0.65rem; margin-bottom: 0.5rem; font-size: 0.85rem;">
                <strong>${escapeHtml(c.candidate_patient.display_name)}</strong> (MRN: <code>${c.candidate_patient.mrn}</code>)
                <br/><span style="color: var(--matab-color-text-muted); font-size: 0.8rem;">Reason: ${escapeHtml(c.explanation)} • Confidence: ${Math.round(c.match_score * 100)}%</span>
                <div style="margin-top: 0.5rem;">
                  <button class="btn btn-secondary btn-sm btn-open-existing" data-id="${c.candidate_patient.id}">
                    Open Existing Record
                  </button>
                </div>
              </div>
            `).join("")}
            <div style="margin-top: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap;">
              <button id="btn-confirm-diff" class="btn btn-primary btn-sm">
                Confirm This is a Different Person & Save
              </button>
              <button id="btn-defer-review" class="btn btn-secondary btn-sm">
                Defer for Supervisory Review
              </button>
            </div>
          </div>
        `;

        alertArea.querySelectorAll(".btn-open-existing").forEach(btn => {
          btn.addEventListener("click", () => {
            closeModal();
            renderPatient360(container, btn.getAttribute("data-id"));
          });
        });

        alertArea.querySelector("#btn-confirm-diff").addEventListener("click", () => {
          submitPatientRegistration(container, "CONFIRMED_DIFFERENT", "Human operator confirmed distinct patient identity at registration");
        });

        alertArea.querySelector("#btn-defer-review").addEventListener("click", () => {
          submitPatientRegistration(container, "DEFERRED_FOR_REVIEW", "Registration saved but deferred for identity team resolution");
        });

      } else {
        alertArea.innerHTML = `
          <div class="alert-box alert-danger">
            ${escapeHtml(err.message)}
          </div>
        `;
      }
    }
  }
}

// -------------------------------------------------------------
// EDIT DEMOGRAPHICS MODAL (OPTIMISTIC CONCURRENCY)
// -------------------------------------------------------------

function openEditDemographicsModal(container, patient, onUpdated) {
  const modalContainer = container.querySelector("#modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Edit Patient Demographics</h3>
          <button id="modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div id="edit-alert-area"></div>
          <form id="edit-demo-form">
            <input type="hidden" id="edit-version" value="${patient.version}" />
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
              <div class="form-group">
                <label class="form-label">Given Name *</label>
                <input type="text" id="edit-given-name" class="form-input" value="${escapeHtml(patient.given_name)}" required />
              </div>
              <div class="form-group">
                <label class="form-label">Family Name</label>
                <input type="text" id="edit-family-name" class="form-input" value="${escapeHtml(patient.family_name || '')}" />
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
              <div class="form-group">
                <label class="form-label">Date of Birth</label>
                <input type="date" id="edit-dob" class="form-input" value="${patient.date_of_birth || ''}" />
              </div>
              <div class="form-group">
                <label class="form-label">Estimated Age</label>
                <input type="number" id="edit-est-age" class="form-input" value="${patient.estimated_age || ''}" />
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
              <div class="form-group">
                <label class="form-label">Sex *</label>
                <select id="edit-sex" class="form-select">
                  <option value="MALE" ${patient.sex === 'MALE' ? 'selected' : ''}>Male</option>
                  <option value="FEMALE" ${patient.sex === 'FEMALE' ? 'selected' : ''}>Female</option>
                  <option value="OTHER" ${patient.sex === 'OTHER' ? 'selected' : ''}>Other</option>
                  <option value="UNKNOWN" ${patient.sex === 'UNKNOWN' ? 'selected' : ''}>Unknown</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Status *</label>
                <select id="edit-status" class="form-select">
                  <option value="ACTIVE" ${patient.status === 'ACTIVE' ? 'selected' : ''}>Active</option>
                  <option value="INACTIVE" ${patient.status === 'INACTIVE' ? 'selected' : ''}>Inactive</option>
                </select>
              </div>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button id="modal-cancel" class="btn btn-secondary">Cancel</button>
          <button id="modal-submit-edit" class="btn btn-primary">Update Demographics</button>
        </div>
      </div>
    </div>
  `;

  const closeModal = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#modal-close").addEventListener("click", closeModal);
  modalContainer.querySelector("#modal-cancel").addEventListener("click", closeModal);

  const submitBtn = modalContainer.querySelector("#modal-submit-edit");
  const alertArea = modalContainer.querySelector("#edit-alert-area");

  submitBtn.addEventListener("click", async () => {
    alertArea.innerHTML = "";
    submitBtn.disabled = true;

    const payload = {
      version: parseInt(modalContainer.querySelector("#edit-version").value, 10),
      given_name: modalContainer.querySelector("#edit-given-name").value.trim(),
      family_name: modalContainer.querySelector("#edit-family-name").value.trim() || null,
      date_of_birth: modalContainer.querySelector("#edit-dob").value || null,
      estimated_age: modalContainer.querySelector("#edit-est-age").value ? parseInt(modalContainer.querySelector("#edit-est-age").value, 10) : null,
      sex: modalContainer.querySelector("#edit-sex").value,
      status: modalContainer.querySelector("#edit-status").value
    };

    try {
      await apiClient.request("PATCH", `/api/v1/patients/${patient.id}`, payload);
      closeModal();
      onUpdated();
    } catch (err) {
      submitBtn.disabled = false;
      if (err.status === 409) {
        alertArea.innerHTML = `
          <div class="alert-box alert-danger">
            <strong>Concurrency Conflict:</strong> Another user updated this record. Please cancel, reload, and apply your changes again.
          </div>
        `;
      } else {
        alertArea.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
      }
    }
  });
}

// -------------------------------------------------------------
// NEW ENCOUNTER MODAL & LIFECYCLE WORKSPACE
// -------------------------------------------------------------

function openNewEncounterModal(container, patient, onCreated) {
  const modalContainer = container.querySelector("#modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box">
        <div class="modal-header">
          <h3>Create Clinical Encounter</h3>
          <button id="modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div id="enc-alert-area"></div>
          
          <div style="background: var(--matab-color-bg-muted); padding: 0.75rem; border-radius: var(--matab-radius-md); margin-bottom: 1rem;">
            Patient: <strong>${escapeHtml(patient.display_name)}</strong> (<code>${patient.mrn}</code>)
          </div>

          <form id="new-enc-form">
            <div class="form-group">
              <label class="form-label">Encounter Type *</label>
              <select id="enc-type" class="form-select">
                <option value="OPD_VISIT">OPD Visit (General Consultation)</option>
                <option value="FOLLOW_UP">Follow-up Visit</option>
                <option value="TELECONSULT">Teleconsultation</option>
                <option value="EMERGENCY">Emergency / Acute Triage</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Reason for Visit / Chief Complaint</label>
              <textarea id="enc-reason" class="form-input" rows="3" placeholder="e.g. Headache, epigastric distress, joint pain..."></textarea>
            </div>
          </form>
        </div>
        <div class="modal-footer">
          <button id="modal-cancel" class="btn btn-secondary">Cancel</button>
          <button id="modal-submit-enc" class="btn btn-primary">Start Encounter</button>
        </div>
      </div>
    </div>
  `;

  const closeModal = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#modal-close").addEventListener("click", closeModal);
  modalContainer.querySelector("#modal-cancel").addEventListener("click", closeModal);

  const submitBtn = modalContainer.querySelector("#modal-submit-enc");
  const alertArea = modalContainer.querySelector("#enc-alert-area");

  submitBtn.addEventListener("click", async () => {
    alertArea.innerHTML = "";
    submitBtn.disabled = true;

    const payload = {
      encounter_type: modalContainer.querySelector("#enc-type").value,
      reason_for_visit: modalContainer.querySelector("#enc-reason").value.trim() || null
    };

    try {
      const resp = await apiClient.post(`/api/v1/patients/${patient.id}/encounters`, payload);
      closeModal();
      openEncounterLifecycleWorkspace(container, resp.encounter, onCreated);
    } catch (err) {
      submitBtn.disabled = false;
      alertArea.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
    }
  });
}

function openEncounterLifecycleWorkspace(container, encounter, onDone) {
  const modalContainer = container.querySelector("#modal-container");
  renderWorkspace();

  function renderWorkspace() {
    modalContainer.innerHTML = `
      <div class="modal-backdrop">
        <div class="modal-box" style="max-width: 680px;">
          <div class="modal-header">
            <div>
              <h3>Encounter Setup & Lifecycle Workspace</h3>
              <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary);">
                Token #${encounter.token_number} • ${encounter.facility_name}
              </div>
            </div>
            <button id="ws-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
          </div>
          <div class="modal-body">
            <div id="ws-alert-area"></div>

            <div style="display: flex; justify-content: space-between; align-items: center; background: var(--matab-color-bg-muted); padding: 0.85rem; border-radius: var(--matab-radius-md); margin-bottom: 1rem;">
              <div>
                Patient: <strong>${escapeHtml(encounter.patient_name)}</strong> (<code>${encounter.patient_mrn}</code>)
              </div>
              <div>
                Status: <span class="badge ${getStatusBadgeClass(encounter.status)}">${encounter.status}</span>
              </div>
            </div>

            <!-- Honest Consultation Boundary Banner -->
            <div class="unimplemented-banner" style="padding: 1.5rem 1rem; margin-bottom: 1.25rem;">
              <h4 style="color: var(--matab-color-text-secondary); margin-bottom: 0.25rem;">
                📋 Clinical Documentation Scheduled for Phase 3
              </h4>
              <p style="font-size: 0.85rem; margin-bottom: 0;">
                Full 3-zone clinical charting, Mizaj scoring, and electronic Nuskha prescription signing will be connected in <strong>Phase 3 (Nuskha & Safety Slice)</strong>.
              </p>
            </div>

            ${encounter.reason_for_visit ? `
              <div style="margin-bottom: 1rem;">
                <label class="form-label">Chief Complaint / Reason for Visit:</label>
                <div style="background: #ffffff; border: 1px solid var(--matab-color-border-subtle); padding: 0.6rem 0.85rem; border-radius: 4px; font-size: 0.9rem;">
                  ${escapeHtml(encounter.reason_for_visit)}
                </div>
              </div>
            ` : ""}

            <div class="card" style="margin-bottom: 1rem;">
              <h4 style="font-size: 0.95rem; margin-bottom: 0.75rem; color: var(--matab-color-brand-primary);">
                Encounter Lifecycle Actions
              </h4>
              <div style="display: flex; gap: 0.75rem; flex-wrap: wrap;">
                ${encounter.status === 'DRAFT' ? `
                  <button id="btn-trans-inprog" class="btn btn-primary btn-sm">
                    ▶ Start Consultation (In Progress)
                  </button>
                  <button id="btn-trans-cancel" class="btn btn-secondary btn-sm" style="color: #991b1b;">
                    ✕ Cancel Visit
                  </button>
                ` : ""}

                ${encounter.status === 'IN_PROGRESS' ? `
                  <button id="btn-trans-complete" class="btn btn-primary btn-sm">
                    ✓ Complete Encounter
                  </button>
                  <button id="btn-trans-cancel" class="btn btn-secondary btn-sm" style="color: #991b1b;">
                    ✕ Cancel Visit
                  </button>
                ` : ""}

                ${encounter.status === 'COMPLETED' || encounter.status === 'CANCELLED' ? `
                  <p style="font-size: 0.85rem; color: var(--matab-color-text-muted);">
                    This encounter has reached terminal state (<strong>${encounter.status}</strong>). No further state transitions allowed.
                  </p>
                ` : ""}
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button id="ws-done" class="btn btn-secondary">Close Workspace</button>
          </div>
        </div>
      </div>
    `;

    const closeWs = () => {
      modalContainer.innerHTML = "";
      if (onDone) onDone();
    };

    modalContainer.querySelector("#ws-close").addEventListener("click", closeWs);
    modalContainer.querySelector("#ws-done").addEventListener("click", closeWs);

    const alertArea = modalContainer.querySelector("#ws-alert-area");

    const inProgBtn = modalContainer.querySelector("#btn-trans-inprog");
    if (inProgBtn) {
      inProgBtn.addEventListener("click", () => doTransition("IN_PROGRESS"));
    }

    const compBtn = modalContainer.querySelector("#btn-trans-complete");
    if (compBtn) {
      compBtn.addEventListener("click", () => doTransition("COMPLETED"));
    }

    const cancelBtn = modalContainer.querySelector("#btn-trans-cancel");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        const reason = prompt("Enter required reason for encounter cancellation:", "Patient requested rescheduling");
        if (reason && reason.trim()) {
          doTransition("CANCELLED", reason.trim());
        }
      });
    }

    async function doTransition(newStatus, cancelReason = null) {
      alertArea.innerHTML = "";
      try {
        const resp = await apiClient.post(`/api/v1/encounters/${encounter.id}/transition`, {
          status: newStatus,
          version: encounter.version,
          cancellation_reason: cancelReason
        });
        encounter = resp.encounter;
        renderWorkspace();
      } catch (err) {
        alertArea.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
      }
    }
  }
}

// -------------------------------------------------------------
// IDENTIFIERS & CONSENT MODALS
// -------------------------------------------------------------

function openAddIdentifierModal(container, patientId, onAdded) {
  const modalContainer = container.querySelector("#modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box" style="max-width: 480px;">
        <div class="modal-header">
          <h3>Add Patient Identifier</h3>
          <button id="modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div id="id-alert-area"></div>
          <div class="form-group">
            <label class="form-label">Identifier Type *</label>
            <select id="new-id-type" class="form-select">
              <option value="NATIONAL_ID">National ID / Aadhaar Ref</option>
              <option value="ABHA">ABHA Health ID</option>
              <option value="PASSPORT">Passport</option>
              <option value="DRIVING_LICENSE">Driving License</option>
              <option value="OTHER">Other System ID</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Identifier Value *</label>
            <input type="text" id="new-id-val" class="form-input" placeholder="e.g. ABHA-9912-3841" required />
          </div>
          <div class="form-group">
            <label class="form-label">Assigning Authority / Issuer</label>
            <input type="text" id="new-id-issuer" class="form-input" placeholder="e.g. GOVT / NDHM" />
          </div>
        </div>
        <div class="modal-footer">
          <button id="modal-cancel" class="btn btn-secondary">Cancel</button>
          <button id="modal-submit-id" class="btn btn-primary">Add Identifier</button>
        </div>
      </div>
    </div>
  `;

  const closeModal = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#modal-close").addEventListener("click", closeModal);
  modalContainer.querySelector("#modal-cancel").addEventListener("click", closeModal);

  modalContainer.querySelector("#modal-submit-id").addEventListener("click", async () => {
    const alertArea = modalContainer.querySelector("#id-alert-area");
    alertArea.innerHTML = "";

    const idType = modalContainer.querySelector("#new-id-type").value;
    const idVal = modalContainer.querySelector("#new-id-val").value.trim();
    const issuer = modalContainer.querySelector("#new-id-issuer").value.trim();

    if (!idVal) {
      alertArea.innerHTML = `<div class="alert-box alert-danger">Identifier value is required.</div>`;
      return;
    }

    try {
      await apiClient.post(`/api/v1/patients/${patientId}/identifiers`, {
        identifier_type: idType,
        identifier_value: idVal,
        issuer: issuer || null
      });
      closeModal();
      onAdded();
    } catch (err) {
      alertArea.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
    }
  });
}

function openRetireIdentifierModal(container, patientId, identifierId, onRetired) {
  const reason = prompt("Enter justification for retiring this identifier (e.g. Entered in error / Replaced):", "Entered in error");
  if (!reason || !reason.trim()) return;

  apiClient.post(`/api/v1/patients/${patientId}/identifiers/${identifierId}/retire`, { reason: reason.trim() })
    .then(() => {
      alert("Identifier retired successfully.");
      onRetired();
    })
    .catch(err => {
      alert(`Failed to retire identifier: ${err.message}`);
    });
}

function openRecordConsentModal(container, patientId, onRecorded) {
  const modalContainer = container.querySelector("#modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box" style="max-width: 480px;">
        <div class="modal-header">
          <h3>Record Explicit Patient Consent</h3>
          <button id="modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div id="cns-alert-area"></div>
          <div class="form-group">
            <label class="form-label">Processing Purpose *</label>
            <select id="new-cns-purpose" class="form-select">
              <option value="GENERAL_CARE">General Unani Clinical Care</option>
              <option value="COMMUNICATION_SMS">Appointment SMS Notifications</option>
              <option value="COMMUNICATION_WHATSAPP">WhatsApp Prescription Delivery</option>
              <option value="DATA_SHARING_RESEARCH">Anonymized Unani Research Registry</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Patient Decision *</label>
            <select id="new-cns-status" class="form-select">
              <option value="GRANTED">Granted (Opt-In)</option>
              <option value="REFUSED">Refused (Opt-Out)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Source / Collection Method</label>
            <select id="new-cns-method" class="form-select">
              <option value="VERBAL_PATIENT">Verbal Patient Request (Front Desk)</option>
              <option value="WRITTEN_FORM">Signed Physical Form</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button id="modal-cancel" class="btn btn-secondary">Cancel</button>
          <button id="modal-submit-cns" class="btn btn-primary">Record Decision</button>
        </div>
      </div>
    </div>
  `;

  const closeModal = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#modal-close").addEventListener("click", closeModal);
  modalContainer.querySelector("#modal-cancel").addEventListener("click", closeModal);

  modalContainer.querySelector("#modal-submit-cns").addEventListener("click", async () => {
    const alertArea = modalContainer.querySelector("#cns-alert-area");
    alertArea.innerHTML = "";

    try {
      await apiClient.post(`/api/v1/patients/${patientId}/consents`, {
        purpose: modalContainer.querySelector("#new-cns-purpose").value,
        status: modalContainer.querySelector("#new-cns-status").value,
        source_method: modalContainer.querySelector("#new-cns-method").value
      });
      closeModal();
      onRecorded();
    } catch (err) {
      alertArea.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
    }
  });
}

function openWithdrawConsentModal(container, patientId, consentId, onWithdrawn) {
  const reason = prompt("Enter patient's reason for withdrawing consent:", "Patient verbal request to withdraw");
  if (!reason || !reason.trim()) return;

  apiClient.post(`/api/v1/patients/${patientId}/consents/${consentId}/withdraw`, { reason: reason.trim() })
    .then(() => {
      alert("Consent withdrawn successfully.");
      onWithdrawn();
    })
    .catch(err => {
      alert(`Failed to withdraw consent: ${err.message}`);
    });
}

// -------------------------------------------------------------
// HELPERS
// -------------------------------------------------------------

function formatAgeDob(patient) {
  if (patient.date_of_birth) {
    const birthYear = parseInt(patient.date_of_birth.split("-")[0], 10);
    const approxAge = new Date().getFullYear() - birthYear;
    return `${approxAge}y (${patient.date_of_birth})`;
  } else if (patient.estimated_age) {
    return `${patient.estimated_age}y (Estimated)`;
  }
  return "Unknown";
}

function formatTimestamp(ts) {
  if (!ts) return "—";
  return ts.replace("T", " ").split(".")[0];
}

function getStatusBadgeClass(status) {
  if (status === "COMPLETED" || status === "GRANTED" || status === "ACTIVE") return "badge-success";
  if (status === "IN_PROGRESS" || status === "DRAFT") return "badge-info";
  if (status === "CANCELLED" || status === "WITHDRAWN" || status === "REFUSED") return "badge-danger";
  return "badge-warning";
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

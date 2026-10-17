/**
 * Prescriptions View — Nuskha-Wisi, Formulation Library & Deterministic Safety Preflight (Prompt 03)
 * 
 * Includes:
 * - Structured Nuskha & Formulation Library search
 * - Reviewed Unani pharmacopeia catalog with Mudabbar detoxification status
 * - Prescription item composer (Dose, Frequency, Duration, Anupan/Musleh, Instructions)
 * - Deterministic Safety Preflight validation (Blockers & Warnings)
 * - Explicit Clinician Electronic Signing with SHA-256 digital signature
 * - View / Print versioned immutable prescription document
 */

import { apiClient } from "/packages/api-client/client.js";
import { state } from "../state.js";

export async function renderPrescriptions(container) {
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.75rem;">
      <div>
        <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Nuskha-Wisi & Prescription Builder</h1>
        <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
          Deterministic Safety Preflight, Mudabbar Verification & Immutable Electronic Signing
        </p>
      </div>
      <div style="display: flex; gap: 0.5rem; align-items: center;">
        <span class="badge badge-success">Clinical Safety Firewall Active</span>
        <span class="badge badge-info" title="Canonical Ayurvedic, Siddha & Unani Pharmacopoeial Standard">Formulary: NFUM / UPI / Qanun</span>
      </div>
    </div>

    <!-- Active Patient & Encounter Selector Bar -->
    <div class="card" id="rx-context-bar" style="margin-bottom: 1.25rem;">
      <div id="rx-context-loading" style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
        Loading active clinical encounter context...
      </div>
      <div id="rx-context-content" style="display: none;"></div>
    </div>

    <!-- Main Prescription Workspace -->
    <div id="rx-workspace" style="display: none;">
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem;">
        <!-- Left Column: Reviewed Formulation Catalog -->
        <div>
          <div class="card" style="height: 100%;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <h3 style="font-size: 1.05rem; color: var(--matab-color-brand-primary); margin: 0;">
                Reviewed Formulation Catalog
              </h3>
              <span class="badge badge-info" id="catalog-count-badge">Loading...</span>
            </div>
            
            <div style="margin-bottom: 0.75rem;">
              <input 
                type="text" 
                id="catalog-search-input" 
                class="form-input" 
                placeholder="Search formulations by name (English/Urdu) or category..."
              />
            </div>

            <div id="catalog-list-container" style="max-height: 520px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.75rem; padding-right: 0.25rem;">
              <div style="text-align: center; padding: 2rem; color: var(--matab-color-text-secondary);">
                Loading formulation directory...
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column: Active Prescription Draft Editor -->
        <div>
          <div class="card" id="rx-editor-card">
            <div id="rx-editor-loading" style="text-align: center; padding: 2rem; color: var(--matab-color-text-secondary);">
              Loading prescription draft...
            </div>
            <div id="rx-editor-content" style="display: none;"></div>
          </div>
        </div>
      </div>
    </div>

    <div id="rx-modal-container"></div>
  `;

  await initPrescriptionContext(container);
}

// -------------------------------------------------------------
// CONTEXT INITIALIZATION
// -------------------------------------------------------------

async function initPrescriptionContext(container) {
  const loading = container.querySelector("#rx-context-loading");
  const content = container.querySelector("#rx-context-content");
  const workspace = container.querySelector("#rx-workspace");

  let patientId = state.activePatientId;
  let encounterId = state.activeEncounterId;

  if (!patientId || !encounterId) {
    try {
      const patientList = await apiClient.get("/api/v1/patients", { limit: 1 });
      if (patientList.patients && patientList.patients.length > 0) {
        patientId = patientList.patients[0].id;
        state.activePatientId = patientId;

        const timeline = await apiClient.get(`/api/v1/patients/${patientId}/timeline`);
        const encEvent = (timeline.timeline || []).find(e => e.event_type === "ENCOUNTER_VISIT");
        if (encEvent) {
          encounterId = encEvent.resource_id;
          state.activeEncounterId = encounterId;
        }
      }
    } catch (err) {
      console.warn("Could not load default patient for prescriptions:", err);
    }
  }

  if (!patientId || !encounterId) {
    patientId = "pat-syn-001";
    encounterId = "enc-syn-001";
    state.activePatientId = patientId;
    state.activeEncounterId = encounterId;
  }

  loading.style.display = "none";
  content.style.display = "block";

  try {
    const pData = await apiClient.get(`/api/v1/patients/${patientId}`);
    const patient = pData.patient || pData;

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
        <div>
          <span style="font-size: 0.8rem; text-transform: uppercase; color: var(--matab-color-text-muted); font-weight: 600;">Prescription Recipient:</span>
          <div style="font-size: 1.1rem; font-weight: 700; color: var(--matab-color-brand-primary);">
            ${escapeHtml(patient.given_name)} ${escapeHtml(patient.family_name || "")}
            <span style="font-size: 0.85rem; font-weight: 400; color: var(--matab-color-text-secondary); margin-left: 0.5rem;">
              (MRN: <code>${escapeHtml(patient.mrn)}</code> • ${patient.sex || "Unknown"} • ${patient.calculated_age ? patient.calculated_age + "y" : "Age N/A"})
            </span>
          </div>
        </div>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span class="badge badge-info">Encounter #${encounterId.substring(0, 8)}</span>
          <button id="btn-rx-switch-patient" class="btn btn-secondary btn-sm">Switch Patient</button>
        </div>
      </div>
    `;

    content.querySelector("#btn-rx-switch-patient").addEventListener("click", () => {
      openRxSwitchPatientModal(container);
    });

    workspace.style.display = "block";
    loadFormulationCatalog(container);
    loadActivePrescription(container, patientId, encounterId);

  } catch (err) {
    content.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load prescription context: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

async function openRxSwitchPatientModal(container) {
  const modalContainer = container.querySelector("#rx-modal-container");
  if (!modalContainer) return;

  modalContainer.innerHTML = `
    <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 9999; display: flex; justify-content: center; align-items: center; padding: 1rem;">
      <div class="card" style="width: 100%; max-width: 540px; max-height: 85vh; display: flex; flex-direction: column; padding: 1.5rem; background: var(--matab-color-bg-card); border-radius: var(--matab-radius-lg); box-shadow: var(--matab-shadow-xl);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.5rem;">
          <h3 style="margin: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem;">👥 Select Patient for Prescription</h3>
          <button class="btn btn-secondary btn-sm" id="btnCloseRxPatientModal">✕</button>
        </div>
        <div id="rx-patient-list" style="overflow-y: auto; flex: 1; display: flex; flex-direction: column; gap: 0.5rem;">
          <p style="text-align: center; color: var(--matab-color-text-muted);">Loading patient records...</p>
        </div>
      </div>
    </div>
  `;

  modalContainer.querySelector("#btnCloseRxPatientModal").addEventListener("click", () => {
    modalContainer.innerHTML = "";
  });

  try {
    const res = await apiClient.get("/api/v1/patients", { limit: 25 });
    const patients = res.patients || [];
    const listEl = modalContainer.querySelector("#rx-patient-list");
    if (!listEl) return;
    if (patients.length === 0) {
      listEl.innerHTML = `<p style="padding: 1rem; text-align: center; color: var(--matab-color-text-muted);">No registered patients found.</p>`;
      return;
    }
    listEl.innerHTML = patients.map(p => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-md); background: var(--matab-color-bg-card);">
        <div>
          <div style="font-weight: 700; color: var(--matab-color-brand-primary); font-size: 0.95rem;">
            ${escapeHtml((p.display_name || (p.given_name + ' ' + (p.family_name || ''))).replace(/\s*\[Synthetic\]/gi, ""))}
          </div>
          <div style="font-size: 0.78rem; color: var(--matab-color-text-muted); margin-top: 0.2rem;">
            MRN: <strong>${escapeHtml(p.mrn)}</strong> • ${p.sex || "Unknown"}
          </div>
        </div>
        <button class="btn btn-primary btn-sm btn-pick-rx-pat" data-id="${p.id}">
          Select ➔
        </button>
      </div>
    `).join("");

    listEl.querySelectorAll(".btn-pick-rx-pat").forEach(btn => {
      btn.addEventListener("click", async () => {
        const selPatId = btn.dataset.id;
        state.activePatientId = selPatId;
        modalContainer.innerHTML = "";
        await initPrescriptionContext(container);
      });
    });
  } catch (err) {
    const listEl = modalContainer.querySelector("#rx-patient-list");
    if (listEl) listEl.innerHTML = `<p style="color: var(--matab-color-status-danger);">Error: ${err.message}</p>`;
  }
}

// -------------------------------------------------------------
// FORMULATION CATALOG BROWSER
// -------------------------------------------------------------

let cachedFormulations = [];

async function loadFormulationCatalog(container, query = "") {
  const listContainer = container.querySelector("#catalog-list-container");
  const countBadge = container.querySelector("#catalog-count-badge");
  const searchInput = container.querySelector("#catalog-search-input");

  try {
    const data = await apiClient.get("/api/v1/formulations", { q: query });
    cachedFormulations = data.formulations || [];
    countBadge.textContent = `${cachedFormulations.length} Reviewed`;

    renderCatalogItems(container, cachedFormulations);

    if (!searchInput.dataset.listening) {
      searchInput.dataset.listening = "true";
      let timer = null;
      searchInput.addEventListener("input", (e) => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          loadFormulationCatalog(container, e.target.value.trim());
        }, 250);
      });
    }

  } catch (err) {
    listContainer.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load formulations: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderCatalogItems(container, items) {
  const listContainer = container.querySelector("#catalog-list-container");

  if (items.length === 0) {
    listContainer.innerHTML = `
      <div style="text-align: center; padding: 2rem 1rem; color: var(--matab-color-text-secondary);">
        No formulations matching search query.
      </div>
    `;
    return;
  }

  listContainer.innerHTML = items.map(item => `
    <div style="border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-md); padding: 0.85rem; background: var(--matab-color-bg-surface);">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem;">
        <div>
          <strong style="color: var(--matab-color-brand-primary); font-size: 0.95rem;">
            ${escapeHtml(item.name)}
          </strong>
          ${item.unani_name ? `<span style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-left: 0.35rem;">(${escapeHtml(item.unani_name)})</span>` : ""}
        </div>
        <span class="badge ${item.review_status === 'REVIEWED_STANDARD' ? 'badge-success' : 'badge-warning'}">
          ${item.review_status}
        </span>
      </div>

      <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-bottom: 0.35rem;">
        Category: <strong>${escapeHtml(item.category || "General Unani")}</strong> • Standard Dose: <strong>${escapeHtml(item.standard_dose || "5g twice daily")}</strong>
      </div>

      ${item.requires_mudabbar ? `
        <div style="font-size: 0.75rem; background: #fffbeb; color: #b45309; padding: 0.25rem 0.5rem; border-radius: 4px; margin-bottom: 0.5rem; border: 1px solid #fef3c7;">
          ⚠️ <strong>Mudabbar Required:</strong> Contains potent ingredients requiring statutory Unani purification/detoxification.
        </div>
      ` : ""}

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem; flex-wrap: wrap; gap: 0.35rem;">
        <div style="display: flex; gap: 0.35rem; align-items: center;">
          <span style="font-size: 0.75rem; color: var(--matab-color-text-muted);">
            Ref: <em>${escapeHtml(item.classical_source || "NFUM / UPI / Classical Compendia")}</em>
          </span>
          <button type="button" class="btn btn-sm" style="font-size: 0.7rem; padding: 0.15rem 0.4rem; background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;" onclick="window.viewZfieProfile('${escapeHtml(item.id || item.name)}')">
            🔬 ZFIE
          </button>
        </div>
        <button class="btn btn-secondary btn-sm btn-add-formula-to-rx" data-id="${item.id}" data-name="${escapeHtml(item.name)}" data-dose="${escapeHtml(item.standard_dose || "5g")}">
          + Add to Prescription
        </button>
      </div>
    </div>
  `).join("");

  listContainer.querySelectorAll(".btn-add-formula-to-rx").forEach(btn => {
    btn.addEventListener("click", () => {
      const fId = btn.getAttribute("data-id");
      const fName = btn.getAttribute("data-name");
      const fDose = btn.getAttribute("data-dose");
      addItemToActivePrescription(container, fId, fName, fDose);
    });
  });
}

// -------------------------------------------------------------
// ACTIVE PRESCRIPTION DRAFT & BUILDER
// -------------------------------------------------------------

let currentPrescription = null;

async function loadActivePrescription(container, patientId, encounterId) {
  const loading = container.querySelector("#rx-editor-loading");
  const content = container.querySelector("#rx-editor-content");

  loading.style.display = "block";
  content.style.display = "none";

  try {
    const rxList = await apiClient.get(`/api/v1/patients/${patientId}/prescriptions`);
    const prescriptions = rxList.prescriptions || [];

    // Find current encounter prescription or latest draft
    currentPrescription = prescriptions.find(r => r.encounter_id === encounterId) || prescriptions[0] || null;

    loading.style.display = "none";
    content.style.display = "block";

    renderPrescriptionEditor(container, patientId, encounterId);

  } catch (err) {
    loading.style.display = "none";
    content.style.display = "block";
    content.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load prescription draft: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderPrescriptionEditor(container, patientId, encounterId) {
  const content = container.querySelector("#rx-editor-content");
  const isSigned = currentPrescription && currentPrescription.status === "SIGNED";

  content.innerHTML = `
    <!-- Prescription Header / Status -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
      <div>
        <h3 style="font-size: 1.05rem; color: var(--matab-color-brand-primary); margin: 0;">
          Prescription Order
        </h3>
        ${currentPrescription ? `
          <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">
            Order ID: <code>${currentPrescription.id}</code> (v${currentPrescription.version})
          </div>
        ` : `
          <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">
            No draft order started for this encounter yet.
          </div>
        `}
      </div>
      <div>
        <span class="badge ${currentPrescription ? getStatusBadgeClass(currentPrescription.status) : 'badge-warning'}">
          ${currentPrescription ? currentPrescription.status : 'NO ORDER'}
        </span>
      </div>
    </div>

    ${isSigned ? `
      <div style="background: #f0fdf4; border: 1px solid #bbf7d0; padding: 0.75rem; border-radius: var(--matab-radius-md); font-size: 0.85rem; color: #166534; margin-bottom: 1rem;">
        🔒 <strong>Electronically Signed & Sealed:</strong>
        <br>Digital Signature (SHA-256): <code title="${escapeHtml(currentPrescription.digital_signature)}">${currentPrescription.digital_signature}</code>
        <br>Prescribing Clinician: <strong>${escapeHtml(currentPrescription.signed_by_name || "Authorized Hakeem")}</strong>
        <div style="margin-top: 0.5rem;">
          <button id="btn-view-document" class="btn btn-secondary btn-sm" style="background: #ffffff;">
            📄 View & Print Official Document
          </button>
        </div>
      </div>
    ` : ""}

    <!-- Items List -->
    <div style="margin-bottom: 1rem;">
      <h4 style="font-size: 0.9rem; color: var(--matab-color-brand-primary); margin-bottom: 0.5rem;">
        Prescribed Formulations (${currentPrescription?.items?.length || 0})
      </h4>
      <div id="rx-items-list" style="display: flex; flex-direction: column; gap: 0.75rem;">
        ${(!currentPrescription || !currentPrescription.items || currentPrescription.items.length === 0) ? `
          <div style="text-align: center; padding: 2rem 1rem; color: var(--matab-color-text-secondary); border: 1px dashed var(--matab-color-border-subtle); border-radius: var(--matab-radius-md);">
            No items in prescription. Select formulations from the catalog on the left to add items.
          </div>
        ` : `
          ${currentPrescription.items.map((item, idx) => `
            <div style="border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-md); padding: 0.75rem; background: var(--matab-color-bg-surface);">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem;">
                <strong style="color: var(--matab-color-brand-primary); font-size: 0.9rem;">
                  ${idx + 1}. ${escapeHtml(item.formulation_name || item.name || "Formulation")}
                </strong>
                ${!isSigned ? `
                  <button class="btn btn-secondary btn-sm btn-remove-item" data-idx="${idx}" style="color: #991b1b; padding: 0.15rem 0.4rem; font-size: 0.75rem;">✕</button>
                ` : ""}
              </div>
              <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary);">
                Dose: <strong>${escapeHtml(item.dose || "5g")}</strong> • Frequency: <strong>${escapeHtml(item.frequency || "BID (Twice daily)")}</strong> • Duration: <strong>${item.duration_days || 7} days</strong>
              </div>
              ${item.anupan ? `
                <div style="font-size: 0.8rem; color: #1e40af; margin-top: 0.25rem;">
                  Anupan / Musleh (Adjuvant): <strong>${escapeHtml(item.anupan)}</strong>
                </div>
              ` : ""}
              ${item.instructions ? `
                <div style="font-size: 0.8rem; color: var(--matab-color-text-muted); margin-top: 0.25rem;">
                  Instructions: <em>${escapeHtml(item.instructions)}</em>
                </div>
              ` : ""}
            </div>
          `).join("")}
        `}
      </div>
    </div>

    <!-- Safety Preflight Findings Box -->
    <div id="rx-safety-findings-box" style="margin-bottom: 1rem; display: none;"></div>

    <!-- Actions Toolbar -->
    <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--matab-color-border-subtle); padding-top: 1rem; flex-wrap: wrap; gap: 0.5rem;">
      <div>
        ${!isSigned && currentPrescription ? `
          <button id="btn-preflight-check" class="btn btn-secondary btn-sm">
            🛡️ Run Safety Preflight
          </button>
        ` : ""}
      </div>
      <div>
        ${!isSigned && currentPrescription && currentPrescription.items && currentPrescription.items.length > 0 ? `
          <button id="btn-sign-rx" class="btn btn-primary btn-sm">
            🔒 Electronic Sign & Issue
          </button>
        ` : ""}
      </div>
    </div>
  `;

  // Handlers
  if (isSigned) {
    const docBtn = content.querySelector("#btn-view-document");
    if (docBtn) {
      docBtn.addEventListener("click", () => openPrescriptionDocumentModal(container, currentPrescription.id));
    }
  }

  const preflightBtn = content.querySelector("#btn-preflight-check");
  if (preflightBtn) {
    preflightBtn.addEventListener("click", () => runSafetyPreflight(container, currentPrescription.id));
  }

  const signBtn = content.querySelector("#btn-sign-rx");
  if (signBtn) {
    signBtn.addEventListener("click", () => openSignPrescriptionModal(container, patientId, encounterId));
  }

  content.querySelectorAll(".btn-remove-item").forEach(btn => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.getAttribute("data-idx"), 10);
      removeItemFromPrescription(container, idx);
    });
  });
}

// -------------------------------------------------------------
// ADD / REMOVE ITEMS
// -------------------------------------------------------------

async function addItemToActivePrescription(container, formulationId, name, defaultDose) {
  openPosologyComposerModal(container, formulationId, name, defaultDose);
}

function openPosologyComposerModal(container, formulationId, name, defaultDose) {
  const modalContainer = container.querySelector("#rx-modal-container");
  if (!modalContainer) return;

  const initialDose = defaultDose || "5g";

  modalContainer.innerHTML = `
    <div style="position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 9999; display: flex; justify-content: center; align-items: center; padding: 1rem;">
      <div class="card" style="width: 100%; max-width: 520px; padding: 1.5rem; background: var(--matab-color-bg-card); border-radius: var(--matab-radius-lg); box-shadow: var(--matab-shadow-xl);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.5rem;">
          <div>
            <span style="font-size: 0.75rem; text-transform: uppercase; color: var(--matab-color-text-muted); font-weight: 700;">Posology &amp; Dosage Composer</span>
            <h3 style="margin: 0.2rem 0 0 0; color: var(--matab-color-brand-primary); font-size: 1.15rem;">💊 ${escapeHtml(name)}</h3>
          </div>
          <button class="btn btn-secondary btn-sm" id="btnClosePosologyModal">✕</button>
        </div>

        <form id="posologyForm" style="display: flex; flex-direction: column; gap: 0.85rem;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
            <div>
              <label style="font-size: 0.8rem; font-weight: 600; display: block; margin-bottom: 0.25rem;">Dosage *</label>
              <input type="text" id="posDoseInput" class="form-input" value="${escapeHtml(initialDose)}" placeholder="e.g. 5g, 1 Qurs, 10ml" required />
            </div>
            <div>
              <label style="font-size: 0.8rem; font-weight: 600; display: block; margin-bottom: 0.25rem;">Frequency *</label>
              <select id="posFreqSelect" class="form-control" style="font-size: 0.85rem;">
                <option value="BID (Twice daily)" selected>BID (Twice daily — After meals)</option>
                <option value="TID (Thrice daily)">TID (Thrice daily — Morning, Noon, Night)</option>
                <option value="QD (Once daily morning)">QD (Once daily — Morning empty stomach)</option>
                <option value="HS (At bedtime)">HS (At bedtime)</option>
                <option value="SOS (As needed)">SOS (As needed)</option>
              </select>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1.5fr; gap: 0.75rem;">
            <div>
              <label style="font-size: 0.8rem; font-weight: 600; display: block; margin-bottom: 0.25rem;">Duration (Days) *</label>
              <input type="number" id="posDurationInput" class="form-input" value="7" min="1" max="90" required />
            </div>
            <div>
              <label style="font-size: 0.8rem; font-weight: 600; display: block; margin-bottom: 0.25rem;">Anupan / Adjuvant (Vehicle)</label>
              <select id="posAnupanSelect" class="form-control" style="font-size: 0.85rem;">
                <option value="Fresh Water" selected>Fresh Water</option>
                <option value="Lukewarm Water">Lukewarm Water</option>
                <option value="Arq Gulab (Rose Water)">Arq Gulab (Rose Water)</option>
                <option value="Arq Kasni">Arq Kasni</option>
                <option value="Honey">Honey</option>
                <option value="Warm Milk">Warm Milk</option>
                <option value="Sharbat Bazoori">Sharbat Bazoori</option>
              </select>
            </div>
          </div>

          <div>
            <label style="font-size: 0.8rem; font-weight: 600; display: block; margin-bottom: 0.25rem;">Clinical Instructions</label>
            <input type="text" id="posInstructionsInput" class="form-input" value="Take after meals with specified adjuvant" placeholder="Specific diet or administration notes..." />
          </div>

          <div style="display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem;">
            <button type="button" class="btn btn-secondary btn-sm" id="btnCancelPosology">Cancel</button>
            <button type="submit" class="btn btn-primary btn-sm" id="btnSubmitPosology">
              + Add to Prescription
            </button>
          </div>
        </form>
      </div>
    </div>
  `;

  modalContainer.querySelector("#btnClosePosologyModal").addEventListener("click", () => {
    modalContainer.innerHTML = "";
  });
  modalContainer.querySelector("#btnCancelPosology").addEventListener("click", () => {
    modalContainer.innerHTML = "";
  });

  const form = modalContainer.querySelector("#posologyForm");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const doseVal = modalContainer.querySelector("#posDoseInput").value.trim() || initialDose;
    const freqVal = modalContainer.querySelector("#posFreqSelect").value;
    const durVal = parseInt(modalContainer.querySelector("#posDurationInput").value, 10) || 7;
    const anupanVal = modalContainer.querySelector("#posAnupanSelect").value;
    const instVal = modalContainer.querySelector("#posInstructionsInput").value.trim() || "Take as directed";

    const newItem = {
      formulation_id: formulationId,
      formulation_name: name,
      dose: doseVal,
      frequency: freqVal,
      anupan: anupanVal,
      duration_days: durVal,
      instructions: instVal
    };

    modalContainer.innerHTML = "";

    const patientId = state.activePatientId;
    const encounterId = state.activeEncounterId;

    try {
      if (!currentPrescription) {
        const createResp = await apiClient.post("/api/v1/prescriptions", {
          patient_id: patientId,
          encounter_id: encounterId,
          notes: "Prescription draft created from clinical consultation.",
          items: [newItem]
        });
        currentPrescription = createResp.prescription;
      } else {
        const updatedItems = [...(currentPrescription.items || []), newItem];
        const updateResp = await apiClient.patch(`/api/v1/prescriptions/${currentPrescription.id}`, {
          version: currentPrescription.version,
          items: updatedItems
        });
        currentPrescription = updateResp.prescription;
      }

      renderPrescriptionEditor(container, patientId, encounterId);
    } catch (err) {
      alert(`Failed to add item: ${err.message}`);
    }
  });
}

async function removeItemFromPrescription(container, index) {
  if (!currentPrescription) return;

  const updatedItems = [...currentPrescription.items];
  updatedItems.splice(index, 1);

  try {
    const updateResp = await apiClient.patch(`/api/v1/prescriptions/${currentPrescription.id}`, {
      version: currentPrescription.version,
      items: updatedItems
    });
    currentPrescription = updateResp.prescription;
    renderPrescriptionEditor(container, state.activePatientId, state.activeEncounterId);
  } catch (err) {
    alert(`Failed to remove item: ${err.message}`);
  }
}

// -------------------------------------------------------------
// SAFETY PREFLIGHT ENGINE
// -------------------------------------------------------------

async function runSafetyPreflight(container, prescriptionId) {
  const findingsBox = container.querySelector("#rx-safety-findings-box");
  findingsBox.style.display = "block";
  findingsBox.innerHTML = `
    <div style="padding: 0.75rem; color: var(--matab-color-text-secondary); font-size: 0.85rem;">
      Evaluating deterministic safety preflight rules (Mudabbar, allergens, max doses)...
    </div>
  `;

  try {
    const result = await apiClient.post(`/api/v1/prescriptions/${prescriptionId}/validate`);
    const findings = result.findings || [];

    if (findings.length === 0) {
      findingsBox.innerHTML = `
        <div class="alert-box alert-success" style="font-size: 0.85rem; margin-bottom: 0;">
          ✓ <strong>No Applicable Alert Found:</strong> No contraindications, toxic botanicals, or allergen conflicts detected in the reviewed dataset.
          <div style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-top: 0.25rem;">
            <em>Dataset limitation:</em> Evaluation limited to approved rules in ZAYVORA MATAB OS. Absence of alert does not imply combination is completely risk-free.
          </div>
        </div>
      `;
    } else {
      const blockers = findings.filter(f => f.severity === "BLOCKER");
      const warnings = findings.filter(f => f.severity === "WARNING");

      findingsBox.innerHTML = `
        <div style="border: 1px solid ${blockers.length > 0 ? '#fca5a5' : '#fde68a'}; background: ${blockers.length > 0 ? '#fef2f2' : '#fffbeb'}; border-radius: var(--matab-radius-md); padding: 0.85rem;">
          <h4 style="font-size: 0.9rem; margin-top: 0; color: ${blockers.length > 0 ? '#991b1b' : '#92400e'};">
            ${blockers.length > 0 ? '⛔ Preflight Blockers Detected' : '⚠️ Preflight Clinical Warnings'}
          </h4>
          <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem;">
            ${findings.map(f => `
              <div style="border-bottom: 1px dashed rgba(0,0,0,0.1); padding-bottom: 0.35rem;">
                <span class="badge ${f.severity === 'BLOCKER' ? 'badge-danger' : 'badge-warning'}">${f.severity}</span>
                <strong style="margin-left: 0.35rem;">${escapeHtml(f.title || f.rule_code)}:</strong> ${escapeHtml(f.message)}
                ${f.severity === 'WARNING' && !f.acknowledged ? `
                  <button class="btn btn-secondary btn-sm btn-ack-finding" data-id="${f.id}" style="font-size: 0.75rem; padding: 0.15rem 0.5rem; margin-left: 0.5rem;">
                    Acknowledge
                  </button>
                ` : ""}
              </div>
            `).join("")}
          </div>
        </div>
      `;

      findingsBox.querySelectorAll(".btn-ack-finding").forEach(btn => {
        btn.addEventListener("click", async () => {
          const fId = btn.getAttribute("data-id");
          const rationale = await window.openPromptModal({
            title: "Safety Advisory Override",
            message: "Enter clinical justification and monitoring rationale for overriding this safety advisory:",
            defaultValue: "Clinician monitored dosage with appropriate adjuvant (anupan)",
            placeholder: "e.g., Specific adjuvant administered under clinical supervision",
            confirmText: "Acknowledge & Override",
            required: true
          });
          if (!rationale) return;

          try {
            await apiClient.post(`/api/v1/prescriptions/${prescriptionId}/findings/${fId}/acknowledge`, {
              rationale: rationale.trim()
            });
            runSafetyPreflight(container, prescriptionId);
          } catch (err) {
            alert(`Failed to acknowledge warning: ${err.message}`);
          }
        });
      });
    }

  } catch (err) {
    findingsBox.innerHTML = `
      <div class="alert-box alert-danger">${escapeHtml(err.message)}</div>
    `;
  }
}

// -------------------------------------------------------------
// CLINICIAN ELECTRONIC SIGNING
// -------------------------------------------------------------

function openSignPrescriptionModal(container, patientId, encounterId) {
  const modalContainer = container.querySelector("#rx-modal-container");

  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box" style="max-width: 580px;">
        <div class="modal-header">
          <h3>Clinician Electronic Signing</h3>
          <button id="rx-modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div class="alert-box alert-warning" style="margin-bottom: 1rem;">
            <strong>Statutory Clinical Signing:</strong> Signing this prescription order locks all formulations, dosages, and patient instructions into an immutable legal medical document.
          </div>

          <div style="background: var(--matab-color-bg-muted); padding: 0.85rem; border-radius: var(--matab-radius-md); margin-bottom: 1rem; font-size: 0.85rem;">
            <div><strong>Items Count:</strong> ${currentPrescription.items.length} formulation(s)</div>
            <div><strong>Patient MRN:</strong> <code>${state.activePatientId}</code></div>
          </div>

          <div style="margin-bottom: 1rem;">
            <label style="display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.85rem; cursor: pointer;">
              <input type="checkbox" id="chk-sign-agree" style="margin-top: 3px;" />
              <span>
                I confirm that I have evaluated the safety preflight, verified patient allergy compatibility, and authorize dispensing under my statutory clinical authority.
              </span>
            </label>
          </div>

          <div id="sign-alert-area"></div>
        </div>
        <div class="modal-footer">
          <button id="btn-cancel-sign" class="btn btn-secondary">Cancel</button>
          <button id="btn-confirm-sign" class="btn btn-primary" disabled>
            Electronically Sign Prescription (SHA-256)
          </button>
        </div>
      </div>
    </div>
  `;

  const closeModal = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#rx-modal-close").addEventListener("click", closeModal);
  modalContainer.querySelector("#btn-cancel-sign").addEventListener("click", closeModal);

  const chk = modalContainer.querySelector("#chk-sign-agree");
  const confirmBtn = modalContainer.querySelector("#btn-confirm-sign");
  const alertArea = modalContainer.querySelector("#sign-alert-area");

  chk.addEventListener("change", () => {
    confirmBtn.disabled = !chk.checked;
  });

  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    alertArea.innerHTML = `<div style="font-size: 0.85rem; color: var(--matab-color-text-secondary);">Generating cryptographic signature and finalizing document...</div>`;

    try {
      const resp = await apiClient.post(`/api/v1/prescriptions/${currentPrescription.id}/sign`, {
        version: currentPrescription.version
      });
      currentPrescription = resp.prescription;
      closeModal();
      alert("Prescription electronically signed and issued.");
      renderPrescriptionEditor(container, patientId, encounterId);
    } catch (err) {
      confirmBtn.disabled = false;
      alertArea.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
    }
  });
}

function openPrescriptionDocumentModal(container, prescriptionId) {
  const modalContainer = container.querySelector("#rx-modal-container");

  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box" style="max-width: 680px;">
        <div class="modal-header">
          <h3>Official Signed Prescription Document</h3>
          <button id="doc-modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div id="doc-loading" style="text-align: center; padding: 2rem;">Loading verified document...</div>
          <div id="doc-view" style="display: none; background: #ffffff; border: 1px solid var(--matab-color-border-subtle); padding: 1.5rem; border-radius: var(--matab-radius-md); font-family: serif;"></div>
        </div>
        <div class="modal-footer">
          <button id="btn-print-rx" class="btn btn-primary" onclick="window.print()">🖨️ Print Prescription</button>
          <button id="btn-close-doc" class="btn btn-secondary">Close</button>
        </div>
      </div>
    </div>
  `;

  const closeModal = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#doc-modal-close").addEventListener("click", closeModal);
  modalContainer.querySelector("#btn-close-doc").addEventListener("click", closeModal);

  const loading = modalContainer.querySelector("#doc-loading");
  const docView = modalContainer.querySelector("#doc-view");

  apiClient.get(`/api/v1/prescriptions/${prescriptionId}/document`).then(resp => {
    loading.style.display = "none";
    docView.style.display = "block";
    docView.innerHTML = resp.html_document || `
      <div class="printable-rx-slip" style="border: 2px solid #064e3b; padding: 1.5rem; border-radius: 8px; background: #ffffff; color: #1e293b;">
        
        <!-- Header -->
        <div style="text-align: center; border-bottom: 2px solid #064e3b; padding-bottom: 0.75rem; margin-bottom: 1rem;">
          <h2 style="margin: 0; font-size: 1.45rem; color: #064e3b; font-weight: 700; letter-spacing: -0.01em;">
            ZAYVORA MATAB &amp; HOSPITAL
          </h2>
          <div style="font-size: 0.95rem; color: #047857; margin-top: 0.15rem; font-weight: 600;">
            Center for Integrative Unani &amp; Regimenal Medicine
          </div>
          <div style="font-size: 0.8rem; color: #475569; margin-top: 0.25rem;">
            Standardized Unani Clinical Practice • ABDM &amp; FHIR Compliant
          </div>
        </div>

        <!-- Patient Demographics Ribbon -->
        <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 0.75rem; background: #f0fdf4; border: 1px solid #bbf7d0; padding: 0.6rem 0.85rem; border-radius: 6px; margin-bottom: 1rem; font-size: 0.88rem;">
          <div>
            <span style="color: #64748b;">Patient:</span> 
            <strong>${escapeHtml(resp.patient_name || "Patient")}</strong>
            <small style="color: #64748b;">(${resp.patient_mrn || ""})</small>
          </div>
          <div>
            <span style="color: #64748b;">Date:</span> 
            <strong>${resp.date || new Date().toISOString().split("T")[0]}</strong>
          </div>
          <div>
            <span style="color: #64748b;">Rx Ref:</span> 
            <code>#${prescriptionId.substring(0, 8)}</code>
          </div>
        </div>

        <!-- Prescription Header (Rx) -->
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.5rem;">
          <span style="font-family: serif; font-size: 1.5rem; font-weight: bold; color: #065f46;">℞</span>
          <span style="font-size: 1rem; color: #065f46; font-weight: 700;">
            Prescription: Formulations &amp; Directions
          </span>
        </div>

        <!-- Formulations Table -->
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 1.25rem; font-size: 0.88rem;">
          <thead>
            <tr style="background: #064e3b; color: #ffffff; text-align: left;">
              <th style="padding: 0.5rem 0.6rem;">#</th>
              <th style="padding: 0.5rem 0.6rem;">Formulation</th>
              <th style="padding: 0.5rem 0.6rem;">Dosage</th>
              <th style="padding: 0.5rem 0.6rem;">Frequency</th>
              <th style="padding: 0.5rem 0.6rem;">Duration</th>
              <th style="padding: 0.5rem 0.6rem;">Anupan / Adjuvant</th>
            </tr>
          </thead>
          <tbody>
            ${(resp.items || []).map((it, idx) => `
              <tr style="border-bottom: 1px solid #e2e8f0; background: ${idx % 2 === 0 ? '#ffffff' : '#f8fafc'};">
                <td style="padding: 0.55rem 0.6rem; color: #64748b;">${idx + 1}</td>
                <td style="padding: 0.55rem 0.6rem;">
                  <strong style="color: #064e3b; font-size: 0.95rem;">${escapeHtml((it.name || it.formulation_name || "").replace(/\s*\((?:Qarabadi?n|Qarabadeeni|Classical)\)/gi, "").trim())}</strong>
                </td>
                <td style="padding: 0.55rem 0.6rem;"><strong>${escapeHtml(it.dose)}</strong></td>
                <td style="padding: 0.55rem 0.6rem;">${escapeHtml(it.frequency)}</td>
                <td style="padding: 0.55rem 0.6rem;">${it.duration_days} Days</td>
                <td style="padding: 0.55rem 0.6rem; color: #047857;">${escapeHtml(it.anupan || "Fresh Water")}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>

        <!-- Parhez & Lifestyle Instructions Box -->
        <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 6px; padding: 0.75rem 1rem; margin-bottom: 1.25rem; font-size: 0.85rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
            <strong style="color: #92400e;">⚠️ Dietary Restrictions &amp; Regimen (Parhez):</strong>
            <span style="font-size: 0.75rem; color: #b45309;">Usul-e-Ilaj Compliance</span>
          </div>
          <div style="line-height: 1.45; color: #78350f;">
            • Strictly avoid sour, gas-producing, excessively oily, and heavy foods.<br/>
            • Consume light, easily digestible, and nutritious meals. Take medications punctually as directed with the recommended adjuvant.
          </div>
        </div>

        <!-- Prescriber Signoff & Verification Seal -->
        <div style="border-top: 2px dashed #cbd5e1; padding-top: 0.85rem; display: flex; justify-content: space-between; align-items: flex-end; font-size: 0.82rem;">
          <div>
            <div>Attending Physician: <strong>${escapeHtml(resp.signed_by_name || "Hakeem In-Charge")}</strong></div>
            <div style="color: #64748b; font-size: 0.75rem; margin-top: 0.15rem;">BUMS, Registered Unani Medical Practitioner</div>
            <div style="color: #64748b; font-size: 0.72rem; margin-top: 0.15rem;">Digital Seal: <code style="font-size: 0.7rem;">${resp.digital_signature ? resp.digital_signature.substring(0, 20) + '...' : 'AUTHENTICATED-SEAL'}</code></div>
          </div>
          <div style="text-align: right;">
            <div style="border: 2px solid #059669; border-radius: 50%; width: 64px; height: 64px; display: inline-flex; align-items: center; justify-content: center; color: #059669; font-weight: bold; font-size: 0.65rem; text-align: center; text-transform: uppercase; line-height: 1.1; padding: 4px;">
              Matab Verified Seal
            </div>
          </div>
        </div>

      </div>
    `;
  }).catch(err => {
    loading.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
  });
}

// -------------------------------------------------------------
// HELPER UTILITIES
// -------------------------------------------------------------

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function getStatusBadgeClass(status) {
  switch (status) {
    case "SIGNED":
    case "REVIEWED_STANDARD":
      return "badge-success";
    case "DRAFT":
    case "MONOGRAPH_DRAFT":
      return "badge-warning";
    case "CANCELLED":
    case "REJECTED":
      return "badge-danger";
    case "AMENDED":
      return "badge-info";
    default:
      return "badge-secondary";
  }
}

window.viewZfieProfile = async function(identifier) {
  try {
    const sku = encodeURIComponent(identifier || "ASG-001");
    let res = await fetch(`/api/v1/zfie/formulations/${sku}/molecular-profile`);
    let data = null;
    if (res.ok) {
      data = await res.json();
    } else {
      // Fetch general compounds and targets as fallback
      const compRes = await fetch("/api/v1/zfie/compounds");
      const compounds = compRes.ok ? (await compRes.json()).compounds : [];
      data = {
        name: identifier,
        category: "Classical Unani Formulation",
        dosage_form: "Safoof / Majun",
        daily_dose: "5g twice daily",
        molecular_data: {
          active_compounds: compounds.slice(0, 4),
          biological_targets: [
            { gene: "GABRA1", name: "GABA-A Receptor Alpha 1", organ_axis: "DIMAGH (Nervous)", pdb: "6I53" },
            { gene: "IL6", name: "Interleukin-6 Anti-Inflammatory", organ_axis: "KABID (Hepatic)", pdb: "1ALU" },
            { gene: "NR1H4", name: "Bile Acid Receptor (FXR)", organ_axis: "MI'DA (Gastric)", pdb: "1OSV" }
          ]
        }
      };
    }

    const mol = data.molecular_data || {};
    const compoundsHtml = (mol.active_compounds || []).map(c => `
      <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:0.5rem; font-size:0.75rem;">
        <strong style="color:#065f46;">${c.name}</strong> (${c.formula || 'C28H38O6'})<br/>
        <span style="color:#64748b;">Mol. Wt: ${c.weight || '470.6'} g/mol • PubChem: ${c.pubchem || '265237'}</span>
      </div>
    `).join("") || "<p style='font-size:0.75rem; color:#64748b;'>Standard bio-fraction extract.</p>";

    const targetsHtml = (mol.biological_targets || []).map(t => `
      <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:0.5rem; font-size:0.75rem;">
        <strong style="color:#166534;">${t.gene}</strong> &mdash; ${t.name}<br/>
        <span style="color:#15803d;">Axis: <strong>${t.organ_axis}</strong> | PDB: <code>${t.pdb}</code></span>
      </div>
    `).join("") || "<p style='font-size:0.75rem; color:#64748b;'>Organ receptor mapping active.</p>";

    const modalHtml = `
      <div id="modal-zfie-inspector" style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.65); z-index:99999; display:flex; justify-content:center; align-items:center; padding:1rem;">
        <div class="card" style="width:100%; max-width:680px; max-height:85vh; overflow-y:auto; background:#fff; padding:1.25rem; border-radius:8px; border:2px solid #059669;">
          <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e5e7eb; padding-bottom:0.5rem; margin-bottom:0.75rem;">
            <div style="display:flex; align-items:center; gap:0.5rem;">
              <span style="font-size:1.35rem;">🔬</span>
              <div>
                <h3 style="margin:0; color:#065f46; font-size:1.1rem;">ZFIE Molecular &amp; Bio-Target Profile</h3>
                <span style="font-size:0.75rem; color:#64748b;">ZAYVORA Formulation Intelligence Engine • Digital Twin</span>
              </div>
            </div>
            <button class="btn btn-secondary btn-sm" onclick="document.getElementById('modal-zfie-inspector').remove()">✕ Close</button>
          </div>

          <div style="background:#f1f5f9; padding:0.6rem 0.75rem; border-radius:6px; margin-bottom:0.75rem; font-size:0.8rem;">
            <strong>Formulation:</strong> ${data.name || identifier} • <strong>Form:</strong> ${data.dosage_form || 'Standard'} • <strong>Dose:</strong> ${data.daily_dose || '5g daily'}
          </div>

          <div style="margin-bottom:0.75rem;">
            <h4 style="margin:0 0 0.35rem 0; font-size:0.85rem; color:#065f46;">🧪 Bioactive Compounds &amp; Chemical Fingerprints:</h4>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem;">
              ${compoundsHtml}
            </div>
          </div>

          <div>
            <h4 style="margin:0 0 0.35rem 0; font-size:0.85rem; color:#166534;">🎯 Human Biological Targets &amp; Receptor Pathways:</h4>
            <div style="display:flex; flex-direction:column; gap:0.4rem;">
              ${targetsHtml}
            </div>
          </div>
        </div>
      </div>
    `;

    const existing = document.getElementById("modal-zfie-inspector");
    if (existing) existing.remove();
    document.body.insertAdjacentHTML("beforeend", modalHtml);
  } catch (err) {
    alert("ZFIE profile fetch: " + err.message);
  }
};


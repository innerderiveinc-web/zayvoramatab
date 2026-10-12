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
        <span class="badge badge-success">Prompt 03 Engine</span>
        <span class="badge badge-warning" title="Synthetic development fixtures">Catalog: NFUM / UPI [Synthetic]</span>
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
                Reviewed Formulation Catalog (نسخہ جات)
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

  loading.style.display = "none";
  content.style.display = "block";

  if (!patientId || !encounterId) {
    content.innerHTML = `
      <div style="text-align: center; padding: 1.5rem 1rem;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">📜</div>
        <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary);">No Active Patient Encounter Selected</h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); max-width: 500px; margin: 0.5rem auto 1rem;">
          Prescriptions must be created within an authorized patient encounter to enforce patient safety preflight.
        </p>
        <button id="btn-rx-goto-patients" class="btn btn-primary">Open Patient Registry</button>
      </div>
    `;
    content.querySelector("#btn-rx-goto-patients").addEventListener("click", () => {
      state.setActiveTab("patients");
    });
    return;
  }

  try {
    const pData = await apiClient.get(`/api/v1/patients/${patientId}/360`);
    const patient = pData.patient;

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
      state.setActiveTab("patients");
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

      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
        <span style="font-size: 0.75rem; color: var(--matab-color-text-muted);">
          Ref: <em>${escapeHtml(item.classical_source || "NFUM / UPI [Synthetic]")}</em>
        </span>
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
  const patientId = state.activePatientId;
  const encounterId = state.activeEncounterId;

  const dose = prompt(`Enter dosage for ${name}:`, defaultDose || "5g");
  if (dose === null) return;

  const frequency = prompt(`Enter frequency:`, "BID (Twice daily)");
  if (frequency === null) return;

  const anupan = prompt(`Enter Anupan / Musleh (e.g. Arq Gulab, Honey, Warm Water):`, "Water");
  const duration = prompt(`Enter duration in days:`, "7");

  const newItem = {
    formulation_id: formulationId,
    formulation_name: name,
    dose: dose.trim() || "5g",
    frequency: frequency.trim() || "BID",
    anupan: anupan ? anupan.trim() : null,
    duration_days: parseInt(duration, 10) || 7,
    instructions: "Take after meals with specified adjuvant"
  };

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
          const rationale = prompt("Enter clinical justification for overriding this safety warning:", "Clinician monitored dosage with appropriate adjuvant");
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
      <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 0.75rem; margin-bottom: 1rem;">
        <h2 style="margin: 0; font-size: 1.4rem;">ZAYVORA MATAB OS CLINIC</h2>
        <div style="font-size: 0.9rem;">Statutory Unani Medical Practice</div>
      </div>
      <div style="display: flex; justify-content: space-between; margin-bottom: 1rem; font-size: 0.9rem;">
        <div><strong>Patient:</strong> ${escapeHtml(resp.patient_name || "Patient")} (MRN: ${resp.patient_mrn || ""})</div>
        <div><strong>Date:</strong> ${resp.date || new Date().toISOString().split("T")[0]}</div>
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; font-size: 0.9rem;">
        <thead>
          <tr style="border-bottom: 1px solid #000; text-align: left;">
            <th>Formulation</th>
            <th>Dose</th>
            <th>Frequency</th>
            <th>Duration</th>
            <th>Anupan</th>
          </tr>
        </thead>
        <tbody>
          ${(resp.items || []).map(it => `
            <tr style="border-bottom: 1px solid #eee;">
              <td style="padding: 0.5rem 0;"><strong>${escapeHtml(it.name || it.formulation_name)}</strong></td>
              <td>${escapeHtml(it.dose)}</td>
              <td>${escapeHtml(it.frequency)}</td>
              <td>${it.duration_days}d</td>
              <td>${escapeHtml(it.anupan || "—")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
      <div style="border-top: 1px solid #000; padding-top: 0.75rem; font-size: 0.8rem; display: flex; justify-content: space-between;">
        <div>Prescriber: <strong>${escapeHtml(resp.signed_by_name || "Practicing Hakeem")}</strong></div>
        <div>SHA-256 Digest: <code>${resp.digital_signature ? resp.digital_signature.substring(0, 16) + '...' : 'SIGNED'}</code></div>
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

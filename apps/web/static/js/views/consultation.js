/**
 * Consultation View — Unani Clinical Assessment & Usul-e-Ilaj Planner (Prompt 04)
 * 
 * Includes:
 * - Patient context & active encounter tracking
 * - Unani assessment editor (Mizaj, Afaal, Asbab-e-Sittah Zaruriyyah)
 * - Semantic states per observation (ASSESSED, NOT_ASSESSED, NOT_APPLICABLE, UNOBTAINABLE)
 * - Classical Organ-Axis context review with honest fail-closed empty state
 * - Usul-e-Ilaj treatment principles and care plan builder with prescription linkage
 * - Explicit clinician finalisation (SHA-256 integrity hash) and governed amendment lifecycle
 */

import { apiClient } from "/packages/api-client/client.js";
import { state } from "../state.js";

export async function renderConsultation(container) {
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.75rem;">
      <div>
        <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Unani Clinical Assessment & Care Plan</h1>
        <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
          Clinician-Governed Mizaj Assessment, Organ-Axis Context & Usul-e-Ilaj Planner
        </p>
      </div>
      <div style="display: flex; gap: 0.5rem; align-items: center;">
        <span class="badge badge-success">Prompt 04 Engine</span>
        <span class="badge badge-warning" title="Synthetic development fixtures">Catalog: Al-Qanun [Synthetic]</span>
      </div>
    </div>

    <!-- Active Patient & Encounter Selector / Context Bar -->
    <div class="card" id="consultation-context-bar" style="margin-bottom: 1.25rem;">
      <div id="context-bar-loading" style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
        Loading active encounter context...
      </div>
      <div id="context-bar-content" style="display: none;"></div>
    </div>

    <!-- Main Consultation Workspace (Rendered once encounter is active) -->
    <div id="consultation-workspace" style="display: none;">
      <!-- Navigation Sub-tabs -->
      <div style="display: flex; gap: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle); margin-bottom: 1.25rem;">
        <button id="tab-btn-unani" class="btn btn-secondary btn-sm" style="border-bottom-left-radius: 0; border-bottom-right-radius: 0; border-bottom: 2px solid var(--matab-color-brand-primary); font-weight: 600;">
          1. Unani Assessment (Mizaj & Afaal)
        </button>
        <button id="tab-btn-organ-axis" class="btn btn-secondary btn-sm" style="border-bottom-left-radius: 0; border-bottom-right-radius: 0;">
          2. Organ-Axis Context Review
        </button>
        <button id="tab-btn-care-plan" class="btn btn-secondary btn-sm" style="border-bottom-left-radius: 0; border-bottom-right-radius: 0;">
          3. Usul-e-Ilaj Care Plan
        </button>
      </div>

      <!-- Tab Content Panes -->
      <div id="pane-unani" class="consultation-pane"></div>
      <div id="pane-organ-axis" class="consultation-pane" style="display: none;"></div>
      <div id="pane-care-plan" class="consultation-pane" style="display: none;"></div>
    </div>

    <div id="consultation-modal-container"></div>
  `;

  await initConsultationContext(container);
}

// -------------------------------------------------------------
// ENCOUNTER CONTEXT & SELECTOR
// -------------------------------------------------------------

async function initConsultationContext(container) {
  const loading = container.querySelector("#context-bar-loading");
  const content = container.querySelector("#context-bar-content");
  const workspace = container.querySelector("#consultation-workspace");

  let patientId = state.activePatientId;
  let encounterId = state.activeEncounterId;

  // If no patient/encounter in state, try to find the most recent encounter or prompt user
  if (!patientId || !encounterId) {
    try {
      const patientList = await apiClient.get("/api/v1/patients", { limit: 1 });
      if (patientList.patients && patientList.patients.length > 0) {
        patientId = patientList.patients[0].id;
        state.activePatientId = patientId;
        
        // Find recent encounter
        const timeline = await apiClient.get(`/api/v1/patients/${patientId}/timeline`);
        const encEvent = (timeline.timeline || []).find(e => e.event_type === "ENCOUNTER_VISIT");
        if (encEvent) {
          encounterId = encEvent.resource_id;
          state.activeEncounterId = encounterId;
        }
      }
    } catch (err) {
      console.warn("Could not prefetch default patient/encounter:", err);
    }
  }

  loading.style.display = "none";
  content.style.display = "block";

  if (!patientId || !encounterId) {
    content.innerHTML = `
      <div style="text-align: center; padding: 1.5rem 1rem;">
        <div style="font-size: 2rem; margin-bottom: 0.5rem;">🩺</div>
        <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary);">No Active Patient Encounter Selected</h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); max-width: 500px; margin: 0.5rem auto 1rem;">
          Unani clinical assessments and care plans must be documented within an active, authorized patient encounter.
        </p>
        <button id="btn-goto-patients" class="btn btn-primary">Open Patient Registry</button>
      </div>
    `;
    content.querySelector("#btn-goto-patients").addEventListener("click", () => {
      state.setActiveTab("patients");
    });
    return;
  }

  // Load patient and encounter details
  try {
    const pData = await apiClient.get(`/api/v1/patients/${patientId}/360`);
    const patient = pData.patient;

    content.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
        <div>
          <span style="font-size: 0.8rem; text-transform: uppercase; color: var(--matab-color-text-muted); font-weight: 600;">Active Clinical Subject:</span>
          <div style="font-size: 1.1rem; font-weight: 700; color: var(--matab-color-brand-primary);">
            ${escapeHtml(patient.given_name)} ${escapeHtml(patient.family_name || "")}
            <span style="font-size: 0.85rem; font-weight: 400; color: var(--matab-color-text-secondary); margin-left: 0.5rem;">
              (MRN: <code>${escapeHtml(patient.mrn)}</code> • ${patient.sex || "Unknown"} • ${patient.calculated_age ? patient.calculated_age + "y" : "Age N/A"})
            </span>
          </div>
        </div>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span class="badge badge-info">Encounter #${encounterId.substring(0, 8)}</span>
          <button id="btn-switch-patient" class="btn btn-secondary btn-sm">Switch Patient</button>
        </div>
      </div>
    `;

    content.querySelector("#btn-switch-patient").addEventListener("click", () => {
      state.setActiveTab("patients");
    });

    // Show workspace
    workspace.style.display = "block";
    setupWorkspaceTabs(container, patientId, encounterId);

  } catch (err) {
    content.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load patient encounter context: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function setupWorkspaceTabs(container, patientId, encounterId) {
  const btnUnani = container.querySelector("#tab-btn-unani");
  const btnOrgan = container.querySelector("#tab-btn-organ-axis");
  const btnCare = container.querySelector("#tab-btn-care-plan");

  const paneUnani = container.querySelector("#pane-unani");
  const paneOrgan = container.querySelector("#pane-organ-axis");
  const paneCare = container.querySelector("#pane-care-plan");

  function switchTab(activeBtn, activePane) {
    [btnUnani, btnOrgan, btnCare].forEach(b => {
      b.style.borderBottom = "none";
      b.style.fontWeight = "normal";
    });
    [paneUnani, paneOrgan, paneCare].forEach(p => p.style.display = "none");

    activeBtn.style.borderBottom = "2px solid var(--matab-color-brand-primary)";
    activeBtn.style.fontWeight = "600";
    activePane.style.display = "block";
  }

  btnUnani.addEventListener("click", () => {
    switchTab(btnUnani, paneUnani);
    loadUnaniAssessmentPane(container, paneUnani, patientId, encounterId);
  });

  btnOrgan.addEventListener("click", () => {
    switchTab(btnOrgan, paneOrgan);
    loadOrganAxisPane(container, paneOrgan, patientId, encounterId);
  });

  btnCare.addEventListener("click", () => {
    switchTab(btnCare, paneCare);
    loadCarePlanPane(container, paneCare, patientId, encounterId);
  });

  // Default active pane
  loadUnaniAssessmentPane(container, paneUnani, patientId, encounterId);
}

// -------------------------------------------------------------
// PANE 1: UNANI CLINICAL ASSESSMENT (MIZAJ, AFAAL, ASBAB)
// -------------------------------------------------------------

async function loadUnaniAssessmentPane(container, pane, patientId, encounterId) {
  pane.innerHTML = `
    <div style="padding: 2rem; text-align: center; color: var(--matab-color-text-secondary);">
      Loading Unani clinical assessment & template...
    </div>
  `;

  try {
    // 1. Fetch template catalog
    const tmplData = await apiClient.get("/api/v1/unani/templates");
    const templates = tmplData.templates || [];
    const coreTemplate = templates[0];

    // 2. Fetch existing assessments for this patient
    const assessList = await apiClient.get(`/api/v1/patients/${patientId}/unani-assessments`);
    const patientAssessments = assessList.assessments || [];
    
    // Find current encounter assessment or latest draft
    let currentAssessment = patientAssessments.find(a => a.encounter_id === encounterId) || patientAssessments[0] || null;

    renderUnaniAssessmentForm(container, pane, patientId, encounterId, coreTemplate, currentAssessment);

  } catch (err) {
    pane.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load Unani assessment: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderUnaniAssessmentForm(container, pane, patientId, encounterId, template, assessment) {
  const isFinalised = assessment && (assessment.status === "FINALISED" || assessment.status === "AMENDED");
  const isDraft = !assessment || assessment.status === "DRAFT";

  pane.innerHTML = `
    <!-- Top Status & Provenance Bar -->
    <div class="card" style="margin-bottom: 1.25rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <strong>Assessment Status:</strong> 
          <span class="badge ${assessment ? getStatusBadgeClass(assessment.status) : 'badge-warning'}">
            ${assessment ? assessment.status : 'NOT STARTED'}
          </span>
          ${assessment ? `<span style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-left: 0.5rem;">ID: <code>${assessment.id}</code> (v${assessment.version})</span>` : ""}
        </div>
        <div style="font-size: 0.8rem; color: var(--matab-color-text-muted);">
          Template: <strong>${escapeHtml(template?.title || "Core Unani Template")}</strong> • Source: <em>Al-Qanun fi al-Tibb [Synthetic]</em>
        </div>
      </div>
      ${isFinalised && assessment?.integrity_hash ? `
        <div style="margin-top: 0.75rem; background: #f0fdf4; border: 1px solid #bbf7d0; padding: 0.5rem 0.75rem; border-radius: 4px; font-size: 0.8rem; color: #166534;">
          🔒 <strong>Clinician Cryptographic Finalisation:</strong> SHA-256 Digest <code>${escapeHtml(assessment.integrity_hash)}</code>
          <br>Signed by clinician <strong>${escapeHtml(assessment.signed_by_name || "Authorized Hakeem")}</strong> at ${escapeHtml(assessment.finalised_at || "")}
        </div>
      ` : ""}
    </div>

    <!-- Assessment Form -->
    <form id="unani-assessment-form">
      <!-- Section 1: Clinician Assessed Mizaj -->
      <div class="card" style="margin-bottom: 1.25rem;">
        <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
          1. Mizaj (Temperamental Assessment / مزاج)
        </h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
          Document your direct clinical evaluation of the patient's dominant temperament. Autonomous machine scoring is strictly disabled.
        </p>

        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.75rem;">
          <div class="form-group">
            <label class="form-label">Primary Mizaj *</label>
            <select id="mizaj-primary" class="form-select" ${isFinalised ? 'disabled' : ''} required>
              <option value="DAMAWI" ${assessment?.primary_mizaj === 'DAMAWI' ? 'selected' : ''}>Damawi (Sanguine / دموی)</option>
              <option value="BALGHAMI" ${assessment?.primary_mizaj === 'BALGHAMI' ? 'selected' : ''}>Balghami (Phlegmatic / بلغمی)</option>
              <option value="SAFRAWI" ${assessment?.primary_mizaj === 'SAFRAWI' ? 'selected' : ''}>Safrawi (Choleric / صفراوی)</option>
              <option value="SAWDAWI" ${assessment?.primary_mizaj === 'SAWDAWI' ? 'selected' : ''}>Sawdawi (Melancholic / سوداوی)</option>
              <option value="MOTADIL" ${assessment?.primary_mizaj === 'MOTADIL' ? 'selected' : ''}>Motadil (Balanced / معتدل)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Dominance Level</label>
            <select id="mizaj-dominance" class="form-select" ${isFinalised ? 'disabled' : ''}>
              <option value="MILD" ${assessment?.dominance_level === 'MILD' ? 'selected' : ''}>Mild</option>
              <option value="MODERATE" ${(!assessment || assessment?.dominance_level === 'MODERATE') ? 'selected' : ''}>Moderate</option>
              <option value="SEVERE" ${assessment?.dominance_level === 'SEVERE' ? 'selected' : ''}>Severe</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Observation Semantic State</label>
            <select id="mizaj-state" class="form-select" ${isFinalised ? 'disabled' : ''}>
              <option value="ASSESSED">ASSESSED (Direct clinical observation)</option>
              <option value="NOT_ASSESSED">NOT_ASSESSED (Deferred)</option>
              <option value="NOT_APPLICABLE">NOT_APPLICABLE</option>
              <option value="UNOBTAINABLE">UNOBTAINABLE (Patient acute state)</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Qualitative Clinical Findings & Observations</label>
          <textarea id="mizaj-notes" class="form-input" rows="2" placeholder="e.g. Skin warm & moist, pulse bounding, ruddy complexion, sleep undisturbed..." ${isFinalised ? 'disabled' : ''}>${escapeHtml(assessment?.qualitative_findings || "")}</textarea>
        </div>
      </div>

      <!-- Section 2: Afaal (Functional Observations) -->
      <div class="card" style="margin-bottom: 1.25rem;">
        <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
          2. Afaal & Dalail-e-Mizaj (Functional Signs & Physiological Indicators / افعال)
        </h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
          Functional observations across digestion, pulse, excretions, and sleep patterns.
        </p>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
          <div class="form-group">
            <label class="form-label">Hazm (Digestion / هضم)</label>
            <input type="text" id="af-hazm" class="form-input" placeholder="e.g. Good appetite, mild postprandial heaviness" value="${escapeHtml(assessment?.responses?.hazm || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Nabz (Pulse Characteristics / نبض)</label>
            <input type="text" id="af-nabz" class="form-input" placeholder="e.g. Rate 76 bpm, full volume, regular rhythm" value="${escapeHtml(assessment?.responses?.nabz || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Baul (Urine / بول)</label>
            <input type="text" id="af-baul" class="form-input" placeholder="e.g. Straw yellow, clear, normal specific gravity" value="${escapeHtml(assessment?.responses?.baul || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Baraz (Stool / براز)</label>
            <input type="text" id="af-baraz" class="form-input" placeholder="e.g. Soft formed, regular daily evacuation" value="${escapeHtml(assessment?.responses?.baraz || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Naum-o-Yaqzah (Sleep / نوم و يقظہ)</label>
            <input type="text" id="af-naum" class="form-input" placeholder="e.g. 7 hours restful nocturnal sleep" value="${escapeHtml(assessment?.responses?.naum || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Tanaffus (Respiration / تنفس)</label>
            <input type="text" id="af-tanaffus" class="form-input" placeholder="e.g. Eupneic, no dyspnea or wheezing" value="${escapeHtml(assessment?.responses?.tanaffus || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>
        </div>
      </div>

      <!-- Section 3: Asbab-e-Sittah Zaruriyyah (Six Essential Causes) -->
      <div class="card" style="margin-bottom: 1.25rem;">
        <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
          3. Asbab-e-Sittah Zaruriyyah (Six Essential Factors / اسباب ستہ ضروریہ)
        </h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
          Environmental, dietary, psychological and lifestyle context affecting temperament.
        </p>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
          <div class="form-group">
            <label class="form-label">Hawa (Ambient Air & Climate / ہوا)</label>
            <input type="text" id="as-hawa" class="form-input" placeholder="e.g. Warm humid urban environment" value="${escapeHtml(assessment?.responses?.hawa || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Makul-o-Mashrub (Food & Beverage / ماکول و مشروب)</label>
            <input type="text" id="as-diet" class="form-input" placeholder="e.g. Excessive spicy food, irregular tea intake" value="${escapeHtml(assessment?.responses?.diet || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Harkat-o-Sukun Badani (Bodily Movement & Rest / حرکت و سکون بدنی)</label>
            <input type="text" id="as-activity" class="form-input" placeholder="e.g. Sedentary desk work, minimal exercise" value="${escapeHtml(assessment?.responses?.activity || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>

          <div class="form-group">
            <label class="form-label">Harkat-o-Sukun Nafsani (Psychic Movement / حرکت و سکون نفسانی)</label>
            <input type="text" id="as-psychic" class="form-input" placeholder="e.g. Work-related stress, mild anxiety" value="${escapeHtml(assessment?.responses?.psychic || "")}" ${isFinalised ? 'disabled' : ''} />
          </div>
        </div>
      </div>

      <!-- Section 4: Clinical Reasoning & Diagnostic Uncertainty -->
      <div class="card" style="margin-bottom: 1.25rem;">
        <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
          4. Clinical Reasoning & Uncertainty
        </h3>
        
        <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 1rem; margin-bottom: 0.75rem;">
          <div class="form-group">
            <label class="form-label">Diagnostic Confidence</label>
            <select id="diag-confidence" class="form-select" ${isFinalised ? 'disabled' : ''}>
              <option value="PROVISIONAL" ${assessment?.confidence === 'PROVISIONAL' ? 'selected' : ''}>PROVISIONAL (Awaiting follow-up)</option>
              <option value="DEFINITIVE" ${assessment?.confidence === 'DEFINITIVE' ? 'selected' : ''}>DEFINITIVE (Established clinical pattern)</option>
              <option value="SUSPECTED" ${assessment?.confidence === 'SUSPECTED' ? 'selected' : ''}>SUSPECTED (Differential consideration)</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Clinical Synthesis & Diagnostic Rationale *</label>
            <textarea id="diag-reasoning" class="form-input" rows="2" placeholder="Record your clinical rationale, differential considerations, and basis for temperament diagnosis..." ${isFinalised ? 'disabled' : ''}>${escapeHtml(assessment?.clinical_reasoning || "")}</textarea>
          </div>
        </div>
      </div>

      <!-- Actions Bar -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 1rem;">
        <div>
          ${isFinalised ? `
            <button type="button" id="btn-amend-assessment" class="btn btn-secondary">
              ✏️ Author Formal Clinical Amendment
            </button>
          ` : `
            <button type="button" id="btn-save-draft" class="btn btn-secondary">
              💾 Save Draft Assessment
            </button>
          `}
        </div>
        <div>
          ${isDraft ? `
            <button type="button" id="btn-finalise-assessment" class="btn btn-primary">
              🔒 Clinician Sign-off & Finalise
            </button>
          ` : `
            <span class="badge badge-success">✓ Finalised & Immutably Fingerprinted</span>
          `}
        </div>
      </div>
    </form>
  `;

  // Attach Handlers
  const saveDraftBtn = pane.querySelector("#btn-save-draft");
  if (saveDraftBtn) {
    saveDraftBtn.addEventListener("click", () => doSaveAssessment(container, pane, patientId, encounterId, template, assessment, false));
  }

  const finaliseBtn = pane.querySelector("#btn-finalise-assessment");
  if (finaliseBtn) {
    finaliseBtn.addEventListener("click", () => openFinaliseModal(container, patientId, encounterId, template, assessment));
  }

  const amendBtn = pane.querySelector("#btn-amend-assessment");
  if (amendBtn) {
    amendBtn.addEventListener("click", () => openAmendModal(container, patientId, encounterId, assessment));
  }
}

async function doSaveAssessment(container, pane, patientId, encounterId, template, existingAssessment, autoFinalise = false) {
  const primaryMizaj = pane.querySelector("#mizaj-primary").value;
  const dominanceLevel = pane.querySelector("#mizaj-dominance").value;
  const qualitativeNotes = pane.querySelector("#mizaj-notes").value.trim();
  const reasoning = pane.querySelector("#diag-reasoning").value.trim();
  const confidence = pane.querySelector("#diag-confidence").value;

  const responses = {
    hazm: pane.querySelector("#af-hazm")?.value.trim() || null,
    nabz: pane.querySelector("#af-nabz")?.value.trim() || null,
    baul: pane.querySelector("#af-baul")?.value.trim() || null,
    baraz: pane.querySelector("#af-baraz")?.value.trim() || null,
    naum: pane.querySelector("#af-naum")?.value.trim() || null,
    tanaffus: pane.querySelector("#af-tanaffus")?.value.trim() || null,
    hawa: pane.querySelector("#as-hawa")?.value.trim() || null,
    diet: pane.querySelector("#as-diet")?.value.trim() || null,
    activity: pane.querySelector("#as-activity")?.value.trim() || null,
    psychic: pane.querySelector("#as-psychic")?.value.trim() || null,
  };

  const payload = {
    template_version_id: template?.current_version_id || "tmpl-v1",
    primary_mizaj: primaryMizaj,
    dominance_level: dominanceLevel,
    qualitative_findings: qualitativeNotes,
    clinical_reasoning: reasoning,
    confidence: confidence,
    responses: responses
  };

  try {
    let saved;
    if (existingAssessment) {
      payload.version = existingAssessment.version;
      const resp = await apiClient.patch(`/api/v1/unani-assessments/${existingAssessment.id}`, payload);
      saved = resp.assessment;
    } else {
      const resp = await apiClient.post(`/api/v1/encounters/${encounterId}/unani-assessments`, payload);
      saved = resp.assessment;
    }

    if (!autoFinalise) {
      alert("Unani Assessment draft saved successfully.");
      loadUnaniAssessmentPane(container, pane, patientId, encounterId);
    }
    return saved;
  } catch (err) {
    alert(`Failed to save assessment: ${err.message}`);
    return null;
  }
}

function openFinaliseModal(container, patientId, encounterId, template, assessment) {
  const modalContainer = container.querySelector("#consultation-modal-container");
  const pane = container.querySelector("#pane-unani");

  const primaryMizaj = pane.querySelector("#mizaj-primary").value;
  const dominanceLevel = pane.querySelector("#mizaj-dominance").value;
  const reasoning = pane.querySelector("#diag-reasoning").value.trim();

  if (!reasoning) {
    alert("Please provide Clinical Synthesis & Diagnostic Rationale before finalising.");
    return;
  }

  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-box" style="max-width: 600px;">
        <div class="modal-header">
          <h3>Clinician Assessment Finalisation</h3>
          <button id="modal-close" style="background: none; border: none; font-size: 1.25rem; cursor: pointer;">✕</button>
        </div>
        <div class="modal-body">
          <div class="alert-box alert-warning" style="margin-bottom: 1rem;">
            <strong>Irreversible Clinical Action:</strong> Finalising this assessment creates an immutable snapshot. Future changes require formal amendment tracking.
          </div>

          <div style="background: var(--matab-color-bg-muted); padding: 0.85rem; border-radius: var(--matab-radius-md); margin-bottom: 1rem; font-size: 0.85rem;">
            <div><strong>Assessed Mizaj:</strong> ${primaryMizaj} (${dominanceLevel})</div>
            <div><strong>Template:</strong> ${template?.title || "Core Unani Template"}</div>
            <div><strong>Clinical Reasoning:</strong> ${escapeHtml(reasoning)}</div>
          </div>

          <div style="margin-bottom: 1rem;">
            <label style="display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.85rem; cursor: pointer;">
              <input type="checkbox" id="chk-confirm-signing" style="margin-top: 3px;" />
              <span>
                I confirm that this assessment is based on my direct clinical evaluation and professional judgement. I understand that the system does not autonomously validate or modify this clinical finding.
              </span>
            </label>
          </div>

          <div id="finalise-alert-area"></div>
        </div>
        <div class="modal-footer">
          <button id="btn-cancel-finalise" class="btn btn-secondary">Cancel</button>
          <button id="btn-confirm-finalise" class="btn btn-primary" disabled>
            Sign & Seal Assessment (SHA-256)
          </button>
        </div>
      </div>
    </div>
  `;

  const closeModal = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#modal-close").addEventListener("click", closeModal);
  modalContainer.querySelector("#btn-cancel-finalise").addEventListener("click", closeModal);

  const chk = modalContainer.querySelector("#chk-confirm-signing");
  const confirmBtn = modalContainer.querySelector("#btn-confirm-finalise");
  const alertArea = modalContainer.querySelector("#finalise-alert-area");

  chk.addEventListener("change", () => {
    confirmBtn.disabled = !chk.checked;
  });

  confirmBtn.addEventListener("click", async () => {
    confirmBtn.disabled = true;
    alertArea.innerHTML = `<div style="color: var(--matab-color-text-secondary); font-size: 0.85rem;">Saving draft and computing cryptographic snapshot...</div>`;

    // 1. Ensure saved
    const saved = await doSaveAssessment(container, pane, patientId, encounterId, template, assessment, true);
    if (!saved) {
      confirmBtn.disabled = false;
      return;
    }

    // 2. Finalise
    try {
      await apiClient.post(`/api/v1/unani-assessments/${saved.id}/finalise`, {
        version: saved.version,
        notes: "Clinician confirmed independent evaluation and finalized temperament assessment."
      });
      closeModal();
      alert("Assessment finalized and cryptographically sealed.");
      loadUnaniAssessmentPane(container, pane, patientId, encounterId);
    } catch (err) {
      confirmBtn.disabled = false;
      alertArea.innerHTML = `<div class="alert-box alert-danger">${escapeHtml(err.message)}</div>`;
    }
  });
}

function openAmendModal(container, patientId, encounterId, assessment) {
  const justification = prompt("Enter required clinical justification for amending this finalized assessment:", "New clinical findings observed upon follow-up examination");
  if (!justification || !justification.trim()) return;

  apiClient.post(`/api/v1/unani-assessments/${assessment.id}/amend`, {
    justification_reason: justification.trim(),
    version: assessment.version
  }).then(resp => {
    alert("New amendment draft created successfully.");
    const pane = container.querySelector("#pane-unani");
    loadUnaniAssessmentPane(container, pane, patientId, encounterId);
  }).catch(err => {
    alert(`Failed to amend assessment: ${err.message}`);
  });
}

// -------------------------------------------------------------
// PANE 2: ORGAN-AXIS CONTEXTUAL REVIEW (HONEST EMPTY STATE)
// -------------------------------------------------------------

async function loadOrganAxisPane(container, pane, patientId, encounterId) {
  pane.innerHTML = `
    <div style="padding: 2rem; text-align: center; color: var(--matab-color-text-secondary);">
      Loading Organ-Axis concept registry and reviewed relationships...
    </div>
  `;

  try {
    const conceptsData = await apiClient.get("/api/v1/organ-axis/concepts");
    const concepts = conceptsData.concepts || [];

    const mappingsData = await apiClient.get("/api/v1/organ-axis/mappings");
    const mappings = mappingsData.mappings || [];

    renderOrganAxisWorkspace(container, pane, concepts, mappings, patientId, encounterId);

  } catch (err) {
    pane.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load Organ-Axis knowledge base: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderOrganAxisWorkspace(container, pane, concepts, mappings, patientId, encounterId) {
  pane.innerHTML = `
    <div class="card" style="margin-bottom: 1.25rem;">
      <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
        Organ-Axis Contextual Association Review
      </h3>
      <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
        Explore classical Unani physiological relationships between organ systems (e.g. Mi'da & Dimagh / Stomach & Brain).
        This layer presents reviewed contextual associations only. If no verified mapping exists, the system fails closed with an honest empty state.
      </p>

      <div style="display: grid; grid-template-columns: 1fr 1fr auto; gap: 0.75rem; align-items: flex-end; margin-bottom: 1rem;">
        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Primary Organ System</label>
          <select id="axis-primary" class="form-select">
            <option value="">-- Select Primary Organ --</option>
            ${concepts.map(c => `
              <option value="${c.id}">${escapeHtml(c.name)} (${escapeHtml(c.unani_name || "")})</option>
            `).join("")}
          </select>
        </div>

        <div class="form-group" style="margin-bottom: 0;">
          <label class="form-label">Associated Secondary Organ</label>
          <select id="axis-secondary" class="form-select">
            <option value="">-- Select Secondary Organ --</option>
            ${concepts.map(c => `
              <option value="${c.id}">${escapeHtml(c.name)} (${escapeHtml(c.unani_name || "")})</option>
            `).join("")}
          </select>
        </div>

        <div>
          <button id="btn-search-axis" class="btn btn-primary">Check Reviewed Axis</button>
        </div>
      </div>
    </div>

    <!-- Results Display -->
    <div id="axis-results-container">
      <div class="card" style="margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem;">
          Verified Knowledge Base Mappings (${mappings.length})
        </h4>
        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          ${mappings.map(m => `
            <div style="border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-md); padding: 0.85rem; background: var(--matab-color-bg-surface);">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.25rem;">
                <strong>${escapeHtml(m.axis_name)}</strong>
                <span class="badge badge-success">${m.review_status}</span>
              </div>
              <div style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 0.5rem;">
                ${escapeHtml(m.clinical_implication || "Contextual association between primary and secondary organ functions.")}
              </div>
              <div style="font-size: 0.8rem; color: var(--matab-color-text-muted);">
                Classical Citation: <em>${escapeHtml(m.source_citation || "Al-Qanun fi al-Tibb [Synthetic]")}</em>
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    </div>
  `;

  const btnSearch = pane.querySelector("#btn-search-axis");
  const selPrimary = pane.querySelector("#axis-primary");
  const selSecondary = pane.querySelector("#axis-secondary");
  const resultsContainer = pane.querySelector("#axis-results-container");

  btnSearch.addEventListener("click", () => {
    const pId = selPrimary.value;
    const sId = selSecondary.value;

    if (!pId || !sId) {
      alert("Please select both primary and secondary organ systems to evaluate.");
      return;
    }

    const matched = mappings.filter(m => 
      (m.primary_concept_id === pId && m.secondary_concept_id === sId) ||
      (m.primary_concept_id === sId && m.secondary_concept_id === pId)
    );

    if (matched.length === 0) {
      resultsContainer.innerHTML = `
        <div class="card" style="border-left: 4px solid var(--matab-color-border-focus);">
          <div style="display: flex; gap: 0.75rem; align-items: flex-start;">
            <div style="font-size: 1.5rem;">⚠️</div>
            <div>
              <h4 style="margin: 0 0 0.25rem 0; font-size: 1rem; color: var(--matab-color-text-primary);">
                No Reviewed Organ-Axis Mapping Available
              </h4>
              <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin: 0 0 0.5rem 0;">
                No reviewed clinical relationship exists in the verified knowledge base for this organ pair.
                The system intentionally declines to generate unverified clinical associations.
              </p>
              <span class="badge badge-warning">State: FAIL_CLOSED_UNREVIEWED</span>
            </div>
          </div>
        </div>
      `;
    } else {
      resultsContainer.innerHTML = `
        <div class="card" style="margin-bottom: 1.25rem; border-left: 4px solid var(--matab-color-brand-primary);">
          <h4 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem;">
            ✓ Reviewed Clinical Organ-Axis Relationship Found
          </h4>
          ${matched.map(m => `
            <div style="background: var(--matab-color-bg-muted); padding: 0.85rem; border-radius: var(--matab-radius-md);">
              <div style="font-weight: 700; font-size: 1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.25rem;">
                ${escapeHtml(m.axis_name)}
              </div>
              <div style="font-size: 0.85rem; margin-bottom: 0.5rem;">
                ${escapeHtml(m.clinical_implication)}
              </div>
              <div style="font-size: 0.8rem; color: var(--matab-color-text-muted);">
                Reference: <em>${escapeHtml(m.source_citation || "Al-Qanun fi al-Tibb [Synthetic]")}</em>
              </div>
            </div>
          `).join("")}
        </div>
      `;
    }
  });
}

// -------------------------------------------------------------
// PANE 3: USUL-E-ILAJ CARE PLAN BUILDER
// -------------------------------------------------------------

async function loadCarePlanPane(container, pane, patientId, encounterId) {
  pane.innerHTML = `
    <div style="padding: 2rem; text-align: center; color: var(--matab-color-text-secondary);">
      Loading Usul-e-Ilaj principles & encounter care plans...
    </div>
  `;

  try {
    const princData = await apiClient.get("/api/v1/usul-e-ilaj/principles");
    const principles = princData.principles || [];

    const planList = await apiClient.get(`/api/v1/patients/${patientId}/care-plans`);
    const carePlans = planList.care_plans || [];
    let currentPlan = carePlans.find(cp => cp.encounter_id === encounterId) || carePlans[0] || null;

    // Also fetch draft prescriptions for this patient to allow linkage
    const rxList = await apiClient.get(`/api/v1/patients/${patientId}/prescriptions`);
    const patientPrescriptions = rxList.prescriptions || [];

    renderCarePlanWorkspace(container, pane, principles, currentPlan, patientPrescriptions, patientId, encounterId);

  } catch (err) {
    pane.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load Care Plan: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderCarePlanWorkspace(container, pane, principles, carePlan, prescriptions, patientId, encounterId) {
  pane.innerHTML = `
    <div class="card" style="margin-bottom: 1.25rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem;">
        <div>
          <h3 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin: 0;">
            Usul-e-Ilaj Treatment Principles & Care Plan (علاج کا طریقہ)
          </h3>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin: 0.25rem 0 0 0;">
            Clinician-directed principles of care (Diet, Evacuation, Regimen, Medication) linked to active encounter.
          </p>
        </div>
        <div>
          <span class="badge ${carePlan ? getStatusBadgeClass(carePlan.status) : 'badge-warning'}">
            ${carePlan ? carePlan.status : 'NO CARE PLAN'}
          </span>
        </div>
      </div>

      <div class="alert-box alert-info" style="font-size: 0.85rem; margin-bottom: 1rem;">
        ℹ️ <strong>Prescription Linkage Disclaimer:</strong> Linking a prescription draft to a care plan item provides therapeutic rationale. It does <strong>not</strong> authorize or sign the prescription. Prescriptions require separate, explicit clinician electronic signing.
      </div>

      <!-- Add New Principle Item Section -->
      <div style="background: var(--matab-color-bg-muted); padding: 1rem; border-radius: var(--matab-radius-md); margin-bottom: 1.25rem;">
        <h4 style="font-size: 0.95rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem;">
          + Add Governed Treatment Principle
        </h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Usul-e-Ilaj Principle *</label>
            <select id="cp-principle-select" class="form-select">
              ${principles.map(p => `
                <option value="${p.id}">${escapeHtml(p.name)} (${escapeHtml(p.unani_name || "")})</option>
              `).join("")}
            </select>
          </div>

          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Priority</label>
            <select id="cp-priority-select" class="form-select">
              <option value="PRIMARY">PRIMARY (Primary Therapeutic Focus)</option>
              <option value="SECONDARY">SECONDARY (Supportive Principle)</option>
              <option value="SUPPORTIVE">SUPPORTIVE (Lifestyle / Preventive)</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Treatment Objective & Planned Interventions *</label>
          <textarea id="cp-objective-input" class="form-input" rows="2" placeholder="e.g. Evacuation of excessive phlegmatic humor (Tanqia-e-Balgham) through dietary modification and gentle Munzij..."></textarea>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Cautions / Contraindications</label>
            <input type="text" id="cp-cautions-input" class="form-input" placeholder="e.g. Avoid strong purgatives in elderly or debility" />
          </div>

          <div class="form-group" style="margin-bottom: 0;">
            <label class="form-label">Link Draft Prescription (Optional)</label>
            <select id="cp-link-rx-select" class="form-select">
              <option value="">-- No Prescription Linked --</option>
              ${prescriptions.map(rx => `
                <option value="${rx.id}">Rx #${rx.id.substring(0, 8)} (${rx.status}) - ${rx.items_count || 1} items</option>
              `).join("")}
            </select>
          </div>
        </div>

        <button id="btn-add-plan-item" class="btn btn-primary btn-sm">+ Add Principle to Care Plan</button>
      </div>

      <!-- Current Items List -->
      <h4 style="font-size: 0.95rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem;">
        Care Plan Principles & Interventions (${carePlan?.items?.length || 0})
      </h4>
      <div id="care-plan-items-list">
        ${(!carePlan || !carePlan.items || carePlan.items.length === 0) ? `
          <div style="text-align: center; padding: 2rem 1rem; color: var(--matab-color-text-secondary); background: var(--matab-color-bg-surface); border: 1px dashed var(--matab-color-border-subtle); border-radius: var(--matab-radius-md);">
            No treatment principles documented for this care plan yet. Use the form above to add governed principles.
          </div>
        ` : `
          <div style="display: flex; flex-direction: column; gap: 0.75rem;">
            ${carePlan.items.map((item, idx) => `
              <div style="border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-md); padding: 0.85rem; background: var(--matab-color-bg-surface);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem;">
                  <div>
                    <span style="font-weight: 700; color: var(--matab-color-brand-primary);">
                      ${idx + 1}. ${escapeHtml(item.principle_name || item.principle_id)}
                    </span>
                    <span class="badge badge-info" style="margin-left: 0.5rem;">${item.priority || "PRIMARY"}</span>
                  </div>
                  <div>
                    <span class="badge ${getStatusBadgeClass(item.status || 'ACTIVE')}">${item.status || 'ACTIVE'}</span>
                  </div>
                </div>
                <div style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 0.5rem;">
                  <strong>Objective:</strong> ${escapeHtml(item.treatment_objective)}
                </div>
                ${item.cautions ? `
                  <div style="font-size: 0.8rem; color: #991b1b; margin-bottom: 0.35rem;">
                    <strong>Caution:</strong> ${escapeHtml(item.cautions)}
                  </div>
                ` : ""}
                ${item.linked_prescription_id ? `
                  <div style="font-size: 0.8rem; background: #eff6ff; padding: 0.25rem 0.5rem; border-radius: 4px; color: #1e40af; display: inline-block;">
                    🔗 Linked Prescription: <code>${item.linked_prescription_id}</code>
                  </div>
                ` : ""}
              </div>
            `).join("")}
          </div>
        `}
      </div>
    </div>
  `;

  const btnAddItem = pane.querySelector("#btn-add-plan-item");
  btnAddItem.addEventListener("click", async () => {
    const principleId = pane.querySelector("#cp-principle-select").value;
    const priority = pane.querySelector("#cp-priority-select").value;
    const objective = pane.querySelector("#cp-objective-input").value.trim();
    const cautions = pane.querySelector("#cp-cautions-input").value.trim();
    const linkedRxId = pane.querySelector("#cp-link-rx-select").value;

    if (!objective) {
      alert("Please specify the Treatment Objective & Planned Interventions.");
      return;
    }

    btnAddItem.disabled = true;

    try {
      // 1. Create or ensure care plan exists
      let activePlanId = carePlan?.id;
      if (!activePlanId) {
        const createResp = await apiClient.post(`/api/v1/encounters/${encounterId}/care-plans`, {
          title: "Unani Integrated Care Plan",
          general_notes: "Initial clinical care plan authored by attending practitioner."
        });
        activePlanId = createResp.care_plan.id;
      }

      // 2. Add or update items
      const existingItems = carePlan?.items || [];
      const newItems = [...existingItems, {
        principle_id: principleId,
        treatment_objective: objective,
        priority: priority,
        cautions: cautions || null,
        linked_prescription_id: linkedRxId || null
      }];

      await apiClient.patch(`/api/v1/care-plans/${activePlanId}`, {
        version: carePlan ? carePlan.version : 1,
        items: newItems
      });

      alert("Treatment principle added to care plan.");
      loadCarePlanPane(container, pane, patientId, encounterId);

    } catch (err) {
      btnAddItem.disabled = false;
      alert(`Failed to save care plan item: ${err.message}`);
    }
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
    case "FINALISED":
    case "ACTIVE":
    case "COMPLETED":
    case "GRANTED":
      return "badge-success";
    case "DRAFT":
    case "PROVISIONAL":
    case "PENDING_REVIEW":
      return "badge-warning";
    case "CANCELLED":
    case "DISCONTINUED":
    case "WITHDRAWN":
      return "badge-danger";
    case "AMENDED":
      return "badge-info";
    default:
      return "badge-secondary";
  }
}

// ZAYVORA MATAB OS — Single Consultation Canvas (3-Zone Encounter Workspace)

import { state } from "../state.js";
import { translations } from "../i18n.js";
import { api } from "../api.js";

let currentStep = 1; // 1: History, 2: Vitals, 3: Assessment, 4: Care Plan, 5: Nuskha, 6: Sign
let draftedItems = [];
let availableFormulations = [];

export async function renderCanvas(container) {
  const t = translations[state.currentLang] || translations.en;
  const enc = state.activeEncounter;

  if (!enc) {
    container.innerHTML = `
      <div class="card" style="text-align: center; padding: 3rem;">
        <h2>No Active Consultation Selected</h2>
        <p style="color: var(--color-text-muted); margin: 1rem 0;">
          Select a patient from the Today waiting queue or issue a new token from the Patients directory.
        </p>
        <button id="goToTodayBtn" class="btn btn-primary">Go to Today's Queue</button>
      </div>
    `;
    container.querySelector("#goToTodayBtn")?.addEventListener("click", () => state.setActiveTab("today"));
    return;
  }

  // Load formulary catalog if not loaded
  if (availableFormulations.length === 0) {
    try {
      const fData = await api.get("/api/v1/knowledge/formulations");
      availableFormulations = fData.formulations || [];
    } catch (e) {}
  }

  // Initialize draft items from active prescription if present
  if (enc.prescription?.items && draftedItems.length === 0) {
    draftedItems = enc.prescription.items.map(it => ({
      item_name: it.item_name || it.custom_name,
      formulation_id: it.formulation_id,
      dosage_form: it.dosage_form || "SAFOOF",
      dose_amount: it.dose_amount || "5",
      dose_unit: it.dose_unit || "g",
      frequency: it.frequency || "BD",
      duration_days: it.duration_days || 7,
      anupan_vehicle: it.anupan_vehicle || "WATER",
      instructions: it.instructions || "After meals"
    }));
  }

  // Render 3-Zone Canvas Structure
  container.innerHTML = `
    <div class="canvas-layout">
      <!-- Zone 1: Patient Context (Left Rail) -->
      <aside class="canvas-zone-1" id="zone1Context"></aside>

      <!-- Zone 2: Main Clinical Work Area (Center Stepper) -->
      <section class="canvas-zone-2" id="zone2Workspace"></section>

      <!-- Zone 3: Contextual Guidance Rail (Right Rail) -->
      <aside class="canvas-zone-3" id="zone3Guidance"></aside>
    </div>
  `;

  renderZone1(container.querySelector("#zone1Context"), enc);
  renderZone2(container.querySelector("#zone2Workspace"), enc);
  renderZone3(container.querySelector("#zone3Guidance"), enc);
}

function renderZone1(el, enc) {
  const t = translations[state.currentLang] || translations.en;
  const allergies = enc.allergies || [];
  const vitals = enc.vitals;

  let allergiesHtml = allergies.length
    ? allergies.map(a => `<div class="allergy-alert-box">⚠️ ${a.allergen_name} (${a.severity})</div>`).join("")
    : `<div style="font-size: 0.8rem; color: var(--color-text-muted); margin-top: 0.5rem;">${t.no_known_allergies}</div>`;

  el.innerHTML = `
    <div class="patient-avatar-box">
      <div class="avatar-circle">${enc.first_name[0]}</div>
      <div class="patient-header-info">
        <h3>${enc.first_name} ${enc.last_name || ""}</h3>
        <span class="mrn-badge">MRN: ${enc.mrn}</span>
      </div>
    </div>
    
    <div style="font-size: 0.85rem; margin-bottom: 0.75rem;">
      <div><strong>Token:</strong> #${enc.token_number} (${enc.encounter_type})</div>
      <div><strong>Phone:</strong> ${enc.phone}</div>
      <div><strong>Gender / DOB:</strong> ${enc.gender} / ${enc.dob || "—"}</div>
      ${enc.blood_group ? `<div><strong>Blood Group:</strong> ${enc.blood_group}</div>` : ''}
    </div>

    <hr style="border: none; border-top: 1px solid var(--color-border); margin: 0.75rem 0;" />

    <div style="font-size: 0.85rem;">
      <strong>${t.allergies}:</strong>
      ${allergiesHtml}
    </div>

    <hr style="border: none; border-top: 1px solid var(--color-border); margin: 0.75rem 0;" />

    <div style="font-size: 0.85rem;">
      <strong>Latest Vitals:</strong>
      ${vitals ? `
        <div style="margin-top: 0.35rem; color: var(--color-text-main);">
          BP: ${vitals.systolic_bp || "—"}/${vitals.diastolic_bp || "—"} mmHg<br />
          Pulse: ${vitals.pulse_bpm || "—"} bpm | SpO2: ${vitals.spo2_percent || "—"}%<br />
          Temp: ${vitals.temperature_f || "—"}°F | Wt: ${vitals.weight_kg || "—"} kg
        </div>
      ` : '<div style="color: var(--color-text-muted); margin-top: 0.25rem;">No vitals recorded yet.</div>'}
    </div>
  `;
}

function renderZone2(el, enc) {
  const t = translations[state.currentLang] || translations.en;

  const steps = [
    { num: 1, title: t.chief_complaint },
    { num: 2, title: t.vitals_exam },
    { num: 3, title: t.unani_assessment },
    { num: 4, title: t.care_plan },
    { num: 5, title: t.nuskha_builder },
    { num: 6, title: t.review_sign }
  ];

  let stepperHtml = steps.map(s => `
    <div class="step-indicator ${currentStep === s.num ? 'active' : ''} ${currentStep > s.num ? 'completed' : ''}" data-step="${s.num}">
      <div class="step-num">${s.num}</div>
      <span>${s.title}</span>
    </div>
  `).join("");

  el.innerHTML = `
    <div class="clinical-stepper">${stepperHtml}</div>
    <div id="stepContentArea"></div>
  `;

  // Attach stepper click handlers
  el.querySelectorAll(".step-indicator").forEach(btn => {
    btn.addEventListener("click", () => {
      currentStep = parseInt(btn.getAttribute("data-step"));
      renderZone2(el, enc);
      renderZone3(document.querySelector("#zone3Guidance"), enc);
    });
  });

  const contentArea = el.querySelector("#stepContentArea");
  renderStepContent(contentArea, enc, currentStep);
}

function renderStepContent(container, enc, step) {
  const t = translations[state.currentLang] || translations.en;

  if (step === 1) {
    // Step 1: Chief Complaint & History
    container.innerHTML = `
      <form id="historyForm">
        <div class="form-group">
          <label class="form-label">${t.chief_complaint} *</label>
          <input type="text" id="chiefComplaintInput" class="form-input" 
            value="${enc.clinical_notes?.chief_complaint || ''}" 
            placeholder="e.g. Heaviness in stomach (Siql-e-Meda) and indigestion for 2 weeks" required />
        </div>
        <div class="form-group">
          <label class="form-label">History of Present Illness (HPI)</label>
          <textarea id="hpiInput" class="form-textarea" placeholder="Onset, duration, severity, dietary triggers...">${enc.clinical_notes?.history_of_present_illness || ''}</textarea>
        </div>
        <div class="form-group">
          <label class="form-label">Past Medical & Medication History</label>
          <textarea id="pmhInput" class="form-textarea" placeholder="Previous illnesses, chronic conditions, current drugs...">${enc.clinical_notes?.past_medical_history || ''}</textarea>
        </div>
        <div style="display: flex; justify-content: flex-end;">
          <button type="submit" class="btn btn-primary">Save & Continue to Vitals ➔</button>
        </div>
      </form>
    `;

    container.querySelector("#historyForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          chief_complaint: container.querySelector("#chiefComplaintInput").value,
          history_of_present_illness: container.querySelector("#hpiInput").value,
          past_medical_history: container.querySelector("#pmhInput").value
        };
        await api.put(`/api/v1/encounters/${enc.id}/notes`, payload);
        enc.clinical_notes = { ...enc.clinical_notes, ...payload };
        currentStep = 2;
        renderZone2(document.querySelector("#zone2Workspace"), enc);
      } catch (err) {
        alert("Error saving notes: " + err.message);
      }
    });

  } else if (step === 2) {
    // Step 2: Vitals & Exam
    container.innerHTML = `
      <form id="vitalsForm">
        <h4 style="margin-bottom: 0.75rem; color: var(--color-primary-dark);">Vital Signs</h4>
        <div class="vitals-grid">
          <div class="form-group">
            <label class="form-label">Systolic BP</label>
            <input type="number" id="vBpSys" class="form-input" placeholder="mmHg" value="${enc.vitals?.systolic_bp || ''}" />
          </div>
          <div class="form-group">
            <label class="form-label">Diastolic BP</label>
            <input type="number" id="vBpDia" class="form-input" placeholder="mmHg" value="${enc.vitals?.diastolic_bp || ''}" />
          </div>
          <div class="form-group">
            <label class="form-label">Pulse (bpm)</label>
            <input type="number" id="vPulse" class="form-input" placeholder="bpm" value="${enc.vitals?.pulse_bpm || ''}" />
          </div>
          <div class="form-group">
            <label class="form-label">Temp (°F)</label>
            <input type="number" step="0.1" id="vTemp" class="form-input" placeholder="98.6" value="${enc.vitals?.temperature_f || ''}" />
          </div>
          <div class="form-group">
            <label class="form-label">SpO2 (%)</label>
            <input type="number" id="vSpo2" class="form-input" placeholder="98" value="${enc.vitals?.spo2_percent || ''}" />
          </div>
          <div class="form-group">
            <label class="form-label">Weight (kg)</label>
            <input type="number" step="0.5" id="vWeight" class="form-input" placeholder="kg" value="${enc.vitals?.weight_kg || ''}" />
          </div>
        </div>

        <div class="form-group" style="margin-top: 1rem;">
          <label class="form-label">Physical Examination Observations</label>
          <textarea id="examInput" class="form-textarea" placeholder="Tongue appearance, pallor, abdominal tenderness...">${enc.clinical_notes?.general_physical_exam || ''}</textarea>
        </div>

        <div style="display: flex; justify-content: space-between;">
          <button type="button" class="btn btn-secondary prev-step-btn">⬅ Previous</button>
          <button type="submit" class="btn btn-primary">Save & Continue to Assessment ➔</button>
        </div>
      </form>
    `;

    container.querySelector(".prev-step-btn").addEventListener("click", () => {
      currentStep = 1;
      renderZone2(document.querySelector("#zone2Workspace"), enc);
    });

    container.querySelector("#vitalsForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          systolic_bp: parseInt(container.querySelector("#vBpSys").value) || null,
          diastolic_bp: parseInt(container.querySelector("#vBpDia").value) || null,
          pulse_bpm: parseInt(container.querySelector("#vPulse").value) || null,
          temperature_f: parseFloat(container.querySelector("#vTemp").value) || null,
          spo2_percent: parseInt(container.querySelector("#vSpo2").value) || null,
          weight_kg: parseFloat(container.querySelector("#vWeight").value) || null
        };
        await api.put(`/api/v1/encounters/${enc.id}/vitals`, payload);
        enc.vitals = { ...enc.vitals, ...payload };
        renderZone1(document.querySelector("#zone1Context"), enc);
        currentStep = 3;
        renderZone2(document.querySelector("#zone2Workspace"), enc);
        renderZone3(document.querySelector("#zone3Guidance"), enc);
      } catch (err) {
        alert("Error saving vitals: " + err.message);
      }
    });

  } else if (step === 3) {
    // Step 3: Parallel Unani & Modern Assessment
    const selectedMizaj = enc.unani_assessment?.dominant_mizaj || "BALGHAMI";

    container.innerHTML = `
      <form id="assessmentForm">
        <h4 style="margin-bottom: 0.75rem; color: var(--color-primary-dark);">Unani Mizaj Evaluation</h4>
        <div class="mizaj-cards-grid">
          <div class="mizaj-card ${selectedMizaj === 'DAMWI' ? 'selected' : ''}" data-mizaj="DAMWI">
            <div class="mizaj-name">🩸 Damwi (Sanguine)</div>
            <div class="mizaj-quality">Hot & Moist (Haar Ratab)</div>
          </div>
          <div class="mizaj-card ${selectedMizaj === 'BALGHAMI' ? 'selected' : ''}" data-mizaj="BALGHAMI">
            <div class="mizaj-name">💧 Balghami (Phlegmatic)</div>
            <div class="mizaj-quality">Cold & Moist (Barid Ratab)</div>
          </div>
          <div class="mizaj-card ${selectedMizaj === 'SAFRAWI' ? 'selected' : ''}" data-mizaj="SAFRAWI">
            <div class="mizaj-name">🔥 Safrawi (Choleric)</div>
            <div class="mizaj-quality">Hot & Dry (Haar Yabis)</div>
          </div>
          <div class="mizaj-card ${selectedMizaj === 'SAUDAWI' ? 'selected' : ''}" data-mizaj="SAUDAWI">
            <div class="mizaj-name">🌑 Saudawi (Melancholic)</div>
            <div class="mizaj-quality">Cold & Dry (Barid Yabis)</div>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
          <div class="form-group">
            <label class="form-label">Nabz (Pulse Quality)</label>
            <select id="nabzSelect" class="form-select">
              <option value="MUTAWASSIT">Mutawassit (Normal / Moderate)</option>
              <option value="AZEEM">Azeem (Large / Strong)</option>
              <option value="SAREE">Saree (Rapid)</option>
              <option value="SAGHEER">Sagheer (Feeble / Thin)</option>
              <option value="BATEE">Batee (Slow / Sluggish)</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Su-e-Mizaj Category</label>
            <select id="sueMizajSelect" class="form-select">
              <option value="NONE">None / Balanced</option>
              <option value="MADDI" selected>Maddi (With Humoral Excess)</option>
              <option value="SAADA">Saada (Simple Temperament Shift)</option>
            </select>
          </div>
        </div>

        <div class="form-group">
          <label class="form-label">Clinical Interpretation (Tashkhees)</label>
          <textarea id="interpretationInput" class="form-textarea" placeholder="e.g. Su-e-Mizaj Balghami Maddi affecting digestive faculty">${enc.unani_assessment?.clinical_interpretation || ''}</textarea>
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 1rem;">
          <button type="button" class="btn btn-secondary prev-step-btn">⬅ Previous</button>
          <button type="submit" class="btn btn-primary">Save & Continue to Care Plan ➔</button>
        </div>
      </form>
    `;

    // Mizaj card click toggles
    let chosenMizaj = selectedMizaj;
    container.querySelectorAll(".mizaj-card").forEach(card => {
      card.addEventListener("click", () => {
        container.querySelectorAll(".mizaj-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        chosenMizaj = card.getAttribute("data-mizaj");
      });
    });

    container.querySelector(".prev-step-btn").addEventListener("click", () => {
      currentStep = 2;
      renderZone2(document.querySelector("#zone2Workspace"), enc);
    });

    container.querySelector("#assessmentForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          encounter_id: enc.id,
          patient_id: enc.patient_id,
          dominant_mizaj: chosenMizaj,
          su_e_mizaj_type: container.querySelector("#sueMizajSelect").value,
          nabz_quality: container.querySelector("#nabzSelect").value,
          clinical_interpretation: container.querySelector("#interpretationInput").value
        };
        await api.post("/api/v1/unani-assessments", payload);
        enc.unani_assessment = { ...enc.unani_assessment, ...payload };
        currentStep = 4;
        renderZone2(document.querySelector("#zone2Workspace"), enc);
      } catch (err) {
        alert("Error saving assessment: " + err.message);
      }
    });

  } else if (step === 4) {
    // Step 4: Usul-e-Ilaj Care Plan
    container.innerHTML = `
      <form id="carePlanForm">
        <div class="form-group">
          <label class="form-label">Usul-e-Ilaj Therapeutic Objective *</label>
          <input type="text" id="usulSummaryInput" class="form-input" 
            value="${enc.care_plan?.usul_e_ilaj_summary || 'Tadeel-e-Mizaj via warming digestives and Tanqiya-e-Balgham.'}" required />
        </div>
        <div class="form-group">
          <label class="form-label">Dietary Directives (Ilaj-bil-Ghiza)</label>
          <textarea id="dietInput" class="form-textarea" placeholder="Foods to favor, foods to restrict...">${enc.care_plan?.dietary_guidelines_ghiza || 'Warm water, ginger infusion, black pepper; avoid heavy cold dairy.'}</textarea>
        </div>
        <div class="form-group">
          <label class="form-label">Regimen Therapies (Ilaj-bit-Tadbeer Instructions)</label>
          <textarea id="regimenInput" class="form-textarea" placeholder="Riyazat (light exercise), Daluk (massage), Hijama...">${enc.care_plan?.regimen_tadbeer_instructions || 'Moderate physical exercise (Riyazat) 20 mins daily.'}</textarea>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 1rem;">
          <button type="button" class="btn btn-secondary prev-step-btn">⬅ Previous</button>
          <button type="submit" class="btn btn-primary">Save & Continue to Nuskha Builder ➔</button>
        </div>
      </form>
    `;

    container.querySelector(".prev-step-btn").addEventListener("click", () => {
      currentStep = 3;
      renderZone2(document.querySelector("#zone2Workspace"), enc);
    });

    container.querySelector("#carePlanForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          encounter_id: enc.id,
          patient_id: enc.patient_id,
          usul_e_ilaj_summary: container.querySelector("#usulSummaryInput").value,
          dietary_guidelines_ghiza: container.querySelector("#dietInput").value,
          regimen_tadbeer_instructions: container.querySelector("#regimenInput").value
        };
        await api.post("/api/v1/care-plans", payload);
        enc.care_plan = { ...enc.care_plan, ...payload };
        currentStep = 5;
        renderZone2(document.querySelector("#zone2Workspace"), enc);
      } catch (err) {
        alert("Error saving care plan: " + err.message);
      }
    });

  } else if (step === 5) {
    // Step 5: Nuskha Formulation Builder
    let itemsRowsHtml = "";
    draftedItems.forEach((it, idx) => {
      itemsRowsHtml += `
        <div class="nuskha-item-row">
          <div>
            <strong>${it.item_name}</strong>
            <span class="badge badge-pass" style="font-size:0.65rem;">${it.dosage_form}</span>
          </div>
          <div>${it.dose_amount} ${it.dose_unit} (${it.frequency})</div>
          <div>${it.duration_days} days</div>
          <div>Vehicle: ${it.anupan_vehicle}</div>
          <button type="button" class="btn btn-secondary btn-sm remove-item-btn" data-index="${idx}">✕</button>
        </div>
      `;
    });

    let formularyOptions = availableFormulations.map(f => `
      <option value="${f.id}" data-name="${f.name}" data-form="${f.dosage_form}" data-dose="${f.standard_adult_dose}">
        ${f.name} (${f.dosage_form}) - ${f.standard_indication || ''}
      </option>
    `).join("");

    container.innerHTML = `
      <div>
        <h4 style="margin-bottom: 0.75rem; color: var(--color-primary-dark);">Prescription Formulations (${draftedItems.length})</h4>
        
        <div id="draftItemsList" style="margin-bottom: 1.25rem;">
          ${itemsRowsHtml || '<p style="color: var(--color-text-muted);">No items added to formulation yet.</p>'}
        </div>

        <div class="card" style="background: var(--color-bg-surface); padding: 1rem;">
          <h5 style="margin-bottom: 0.5rem;">+ Add Approved Formulation from Catalog</h5>
          <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 0.5rem; margin-bottom: 0.5rem;">
            <div>
              <label class="form-label">Formulation</label>
              <select id="catalogFormSelect" class="form-select">
                ${formularyOptions}
              </select>
            </div>
            <div>
              <label class="form-label">Dose & Unit</label>
              <div style="display: flex; gap: 0.25rem;">
                <input type="number" id="addDoseAmount" class="form-input" value="5" style="width: 60px;" />
                <select id="addDoseUnit" class="form-select">
                  <option value="g">g</option>
                  <option value="mg">mg</option>
                  <option value="ml">ml</option>
                  <option value="masha">masha</option>
                </select>
              </div>
            </div>
            <div>
              <label class="form-label">Frequency</label>
              <select id="addFrequency" class="form-select">
                <option value="BD">BD (Twice daily)</option>
                <option value="OD">OD (Once daily)</option>
                <option value="TDS">TDS (Thrice daily)</option>
                <option value="HS">HS (Bedtime)</option>
              </select>
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.5rem;">
            <div>
              <label class="form-label">Duration (Days)</label>
              <input type="number" id="addDuration" class="form-input" value="7" />
            </div>
            <div>
              <label class="form-label">Anupan (Vehicle)</label>
              <select id="addVehicle" class="form-select">
                <option value="WATER">Water / Lukewarm water</option>
                <option value="WARM_MILK">Warm Milk</option>
                <option value="HONEY">Honey</option>
                <option value="ARQ_GAWZABAN">Arq-e-Gawzaban</option>
              </select>
            </div>
            <div style="display: flex; align-items: flex-end;">
              <button type="button" id="addItemBtn" class="btn btn-primary" style="width: 100%;">+ Add Item</button>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 1.5rem;">
          <button type="button" class="btn btn-secondary prev-step-btn">⬅ Previous</button>
          <button type="button" id="saveDraftAndPreflightBtn" class="btn btn-primary">Save Draft & Run Preflight ➔</button>
        </div>
      </div>
    `;

    container.querySelector(".prev-step-btn").addEventListener("click", () => {
      currentStep = 4;
      renderZone2(document.querySelector("#zone2Workspace"), enc);
    });

    container.querySelectorAll(".remove-item-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-index"));
        draftedItems.splice(idx, 1);
        renderStepContent(container, enc, 5);
        renderZone3(document.querySelector("#zone3Guidance"), enc);
      });
    });

    container.querySelector("#addItemBtn").addEventListener("click", () => {
      const select = container.querySelector("#catalogFormSelect");
      const chosenOption = select.options[select.selectedIndex];
      const formId = select.value;
      const formName = chosenOption.getAttribute("data-name");
      const dosageForm = chosenOption.getAttribute("data-form");

      draftedItems.push({
        formulation_id: formId,
        item_name: formName,
        dosage_form: dosageForm,
        dose_amount: container.querySelector("#addDoseAmount").value,
        dose_unit: container.querySelector("#addDoseUnit").value,
        frequency: container.querySelector("#addFrequency").value,
        duration_days: parseInt(container.querySelector("#addDuration").value) || 7,
        anupan_vehicle: container.querySelector("#addVehicle").value,
        instructions: "As directed"
      });

      renderStepContent(container, enc, 5);
      renderZone3(document.querySelector("#zone3Guidance"), enc);
    });

    container.querySelector("#saveDraftAndPreflightBtn").addEventListener("click", async () => {
      if (draftedItems.length === 0) {
        alert("Please add at least one formulation item to the prescription.");
        return;
      }
      try {
        const res = await api.post("/api/v1/prescriptions", {
          encounter_id: enc.id,
          patient_id: enc.patient_id,
          items: draftedItems
        });
        enc.prescription = res.prescription;
        currentStep = 6;
        renderZone2(document.querySelector("#zone2Workspace"), enc);
        renderZone3(document.querySelector("#zone3Guidance"), enc);
      } catch (err) {
        alert("Preflight error: " + err.message);
      }
    });

  } else if (step === 6) {
    // Step 6: Review & Electronic Sign
    const pr = enc.prescription;
    const isSigned = pr?.status === "SIGNED";
    const safetyState = pr?.overall_safety_state || "UNKNOWN";

    let itemsTable = (pr?.items || draftedItems).map(it => `
      <tr>
        <td><strong>${it.item_name}</strong></td>
        <td>${it.dosage_form}</td>
        <td>${it.dose_amount} ${it.dose_unit}</td>
        <td>${it.frequency} (${it.duration_days} days)</td>
        <td>${it.anupan_vehicle}</td>
      </tr>
    `).join("");

    container.innerHTML = `
      <div>
        <h4 style="margin-bottom: 0.75rem; color: var(--color-primary-dark);">Pre-Signing Clinical Review</h4>
        
        <table class="data-table" style="margin-bottom: 1.25rem;">
          <thead>
            <tr>
              <th>Formulation</th>
              <th>Form</th>
              <th>Dosage</th>
              <th>Frequency</th>
              <th>Vehicle</th>
            </tr>
          </thead>
          <tbody>${itemsTable}</tbody>
        </table>

        ${isSigned ? `
          <div class="card" style="background: #f0fdf4; border-color: #bbf7d0; text-align: center; padding: 1.5rem;">
            <h3 style="color: #166534;">✅ Prescription Signed & Verified</h3>
            <p style="font-size: 0.85rem; margin-top: 0.35rem;">
              Timestamp: ${pr.signature_timestamp}<br />
              <span class="print-hash">SHA-256: ${pr.signature_hash}</span>
            </p>
            <button id="printPrescriptionBtn" class="btn btn-primary" style="margin-top: 1rem;">
              🖨️ Print Prescription Document
            </button>
          </div>
        ` : `
          <div class="card" style="border: 2px solid ${safetyState === 'BLOCK' ? 'var(--color-safety-block)' : 'var(--color-primary)'};">
            <h4 style="margin-bottom: 0.5rem;">Electronic Signature Authorization</h4>
            <p style="font-size: 0.85rem; color: var(--color-text-muted); margin-bottom: 1rem;">
              Signing creates an immutable clinical record and generates a tamper-evident SHA-256 fingerprint.
            </p>

            ${safetyState === 'BLOCK' ? `
              <div class="allergy-alert-box" style="margin-bottom: 1rem;">
                ⛔ SIGNING BLOCKED: Critical safety preflight violations must be resolved before signing.
              </div>
            ` : ''}

            ${safetyState === 'UNKNOWN' ? `
              <div class="form-group">
                <label class="form-label">Clinical Override Justification *</label>
                <input type="text" id="overrideInput" class="form-input" placeholder="Required because safety rule is UNKNOWN" />
              </div>
            ` : ''}

            <div style="display: flex; gap: 0.75rem; align-items: flex-end;">
              <div class="form-group" style="margin-bottom: 0;">
                <label class="form-label">${t.pin_label} *</label>
                <input type="password" id="signingPinInput" class="form-input" placeholder="Enter PIN (e.g. 1234)" style="width: 200px;" ${safetyState === 'BLOCK' ? 'disabled' : ''} />
              </div>
              <button id="signPrescriptionBtn" class="btn btn-primary" ${safetyState === 'BLOCK' ? 'disabled' : ''}>
                ✍️ ${t.sign_button}
              </button>
            </div>
          </div>
        `}

        <div style="display: flex; justify-content: flex-start; margin-top: 1.5rem;">
          <button type="button" class="btn btn-secondary prev-step-btn">⬅ Back to Nuskha Builder</button>
        </div>
      </div>
    `;

    container.querySelector(".prev-step-btn").addEventListener("click", () => {
      currentStep = 5;
      renderZone2(document.querySelector("#zone2Workspace"), enc);
    });

    const signBtn = container.querySelector("#signPrescriptionBtn");
    if (signBtn) {
      signBtn.addEventListener("click", async () => {
        const pin = container.querySelector("#signingPinInput").value.trim();
        const override = container.querySelector("#overrideInput")?.value.trim();
        if (!pin) {
          alert("Please enter your Practitioner PIN.");
          return;
        }
        try {
          const res = await api.post(`/api/v1/prescriptions/${pr.id}/sign`, {
            pin,
            override_rationale: override
          });
          enc.prescription = res.prescription;
          enc.status = "SIGNED";
          renderZone2(document.querySelector("#zone2Workspace"), enc);
          renderZone3(document.querySelector("#zone3Guidance"), enc);
        } catch (err) {
          alert("Signing failed: " + err.message);
        }
      });
    }

    const printBtn = container.querySelector("#printPrescriptionBtn");
    if (printBtn) {
      printBtn.addEventListener("click", () => {
        openPrintModal(pr.id);
      });
    }
  }
}

async function renderZone3(el, enc) {
  const pr = enc.prescription;
  const safetyState = pr?.overall_safety_state || "PASS";

  el.innerHTML = `
    <h4 style="margin-bottom: 0.75rem; color: var(--color-primary-dark);">Contextual Guidance</h4>

    <div class="guidance-box ${safetyState === 'BLOCK' ? 'alert-block' : safetyState === 'WARN' ? 'alert-warn' : ''}">
      <div class="guidance-title">🛡️ Safety Preflight: <span class="badge ${safetyState === 'PASS' ? 'badge-pass' : safetyState === 'BLOCK' ? 'badge-block' : 'badge-warn'}">${safetyState}</span></div>
      <p style="font-size: 0.8rem; margin-top: 0.25rem;">
        ${safetyState === 'PASS' ? 'No adverse interactions, toxic botanical limits, or documented allergies violated.' : ''}
        ${safetyState === 'BLOCK' ? 'Critical contraindication or documented allergy conflict identified.' : ''}
        ${safetyState === 'WARN' ? 'Cautionary warnings detected in posology or mild interactions.' : ''}
      </p>
    </div>

    <div class="guidance-box">
      <div class="guidance-title">📚 Governed Classical Citations</div>
      <ul style="padding-left: 1rem; font-size: 0.75rem; margin-top: 0.25rem;">
        <li><strong>NFUM Part I (p. 112):</strong> Safoof-e-Mohazzil formulation standards.</li>
        <li><strong>UPI Vol I:</strong> Withania somnifera posology ceiling (10g/day).</li>
        <li><strong>Schedule E(1):</strong> Mudabbar required for Strychnos nux-vomica.</li>
      </ul>
    </div>
  `;
}

async function openPrintModal(prescriptionId) {
  try {
    const data = await api.get(`/api/v1/prescriptions/${prescriptionId}/print`);
    const pData = data.printable_prescription;
    const pr = pData.prescription;
    const pt = pData.patient;
    const fc = pData.facility;

    const modalWindow = window.open("", "_blank", "width=800,height=900");
    modalWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Prescription — ${pt.name}</title>
        <style>
          body { font-family: sans-serif; padding: 25px; line-height: 1.5; color: #111; }
          .header { border-bottom: 2px solid #064e3b; padding-bottom: 10px; display: flex; justify-content: space-between; }
          .rx { font-size: 24pt; font-weight: bold; margin: 15px 0 5px 0; color: #064e3b; }
          table { width: 100%; border-collapse: collapse; margin: 15px 0; }
          th, td { border-bottom: 1px solid #ddd; padding: 8px 6px; text-align: left; font-size: 10pt; }
          th { background: #f0fdf4; }
          .footer { margin-top: 40px; border-top: 1px dashed #999; padding-top: 10px; font-size: 8pt; color: #555; }
        </style>
      </head>
      <body>
        <div class="header">
          <div>
            <h2 style="margin: 0; color: #064e3b;">${fc.org_name}</h2>
            <div style="font-size: 10pt;">${fc.facility_name} | ${fc.address}</div>
            <div style="font-size: 9pt;">📞 ${fc.phone}</div>
          </div>
          <div style="text-align: right; font-size: 9pt;">
            <strong>Hakeem Tariq Ahmad (BUMS)</strong><br />
            Reg: ${pData.verification.reg_no}<br />
            Council: ${pData.verification.council}
          </div>
        </div>

        <div style="margin: 15px 0; font-size: 10pt; background: #fafafa; padding: 10px; border-radius: 4px;">
          <strong>Patient:</strong> ${pt.name} | <strong>MRN:</strong> ${pt.mrn} | <strong>Gender/Age:</strong> ${pt.gender} (${pt.dob})
        </div>

        <div class="rx">℞</div>

        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Formulation / Item</th>
              <th>Form</th>
              <th>Dose</th>
              <th>Frequency</th>
              <th>Vehicle (Anupan)</th>
            </tr>
          </thead>
          <tbody>
            ${pr.items.map((it, i) => `
              <tr>
                <td>${i+1}</td>
                <td><strong>${it.item_name}</strong></td>
                <td>${it.dosage_form}</td>
                <td>${it.dose_amount} ${it.dose_unit}</td>
                <td>${it.frequency} (${it.duration_days} days)</td>
                <td>${it.anupan_vehicle}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>

        <div class="footer">
          <div><strong>Signed Electronically:</strong> ${pData.verification.signed_at}</div>
          <div><strong>Cryptographic Hash (SHA-256):</strong> <code>${pData.verification.signature_hash}</code></div>
          <div><em>This prescription is immutable and verified by ZAYVORA MATAB OS v1.1.</em></div>
        </div>

        <script>
          window.print();
        </script>
      </body>
      </html>
    `);
    modalWindow.document.close();
  } catch (e) {
    alert("Print error: " + e.message);
  }
}

// ZAYVORA MATAB OS — Patients Destination (MPI & Patient 360)

import { state } from "../state.js";
import { translations } from "../i18n.js";
import { api } from "../api.js";

export async function renderPatients(container) {
  const t = translations[state.currentLang] || translations.en;

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
      <div>
        <h1 style="font-size: 1.5rem; color: var(--color-primary-dark);">${t.nav_patients}</h1>
        <p style="color: var(--color-text-muted); font-size: 0.9rem;">Master Patient Index, Duplicate Prevention & Patient 360</p>
      </div>
      <button id="showAddPatientBtn" class="btn btn-primary">+ ${t.add_patient}</button>
    </div>

    <!-- Search Section -->
    <div class="card">
      <div style="display: flex; gap: 0.75rem;">
        <input type="text" id="patientSearchInput" class="form-input" placeholder="${t.search_patients}" />
        <button id="patientSearchBtn" class="btn btn-secondary">Search</button>
      </div>
    </div>

    <!-- Patient List Table -->
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">Registered Patients</h3>
      </div>
      <div id="patientTableContainer">
        <p>Loading patient directory...</p>
      </div>
    </div>

    <!-- Add Patient Modal Container -->
    <div id="addPatientModal"></div>

    <!-- Patient 360 Drawer Container -->
    <div id="patient360Container"></div>
  `;

  const searchInput = container.querySelector("#patientSearchInput");
  const searchBtn = container.querySelector("#patientSearchBtn");
  const tableContainer = container.querySelector("#patientTableContainer");

  async function loadPatients(query = "") {
    try {
      const data = await api.get(`/api/v1/patients?q=${encodeURIComponent(query)}`);
      const patients = data.patients || [];

      let rowsHtml = "";
      patients.forEach(p => {
        rowsHtml += `
          <tr>
            <td>
              <strong>${p.first_name} ${p.last_name || ""}</strong>
              ${p.is_synthetic ? '<span class="badge badge-unknown" style="font-size:0.6rem;">SYNTHETIC</span>' : ''}
            </td>
            <td><span class="mrn-badge">${p.mrn}</span></td>
            <td>${p.phone}</td>
            <td>${p.gender} / ${p.dob || "—"}</td>
            <td><span class="badge badge-pass">${p.visit_count || 0} visits</span></td>
            <td style="display: flex; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm view-360-btn" data-patient-id="${p.id}">
                Patient 360
              </button>
              <button class="btn btn-primary btn-sm start-visit-btn" data-patient-id="${p.id}">
                + Issue Token
              </button>
            </td>
          </tr>
        `;
      });

      tableContainer.innerHTML = `
        <table class="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>MRN</th>
              <th>Phone</th>
              <th>Demographics</th>
              <th>Visits</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${rowsHtml || '<tr><td colspan="6" style="text-align: center;">No patients found.</td></tr>'}
          </tbody>
        </table>
      `;

      // Event Listeners for rows
      tableContainer.querySelectorAll(".view-360-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          openPatient360(btn.getAttribute("data-patient-id"));
        });
      });

      tableContainer.querySelectorAll(".start-visit-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          issueTokenForPatient(btn.getAttribute("data-patient-id"));
        });
      });

    } catch (e) {
      tableContainer.innerHTML = `<p style="color: red;">Error loading patients: ${e.message}</p>`;
    }
  }

  searchBtn.addEventListener("click", () => loadPatients(searchInput.value));
  searchInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter") loadPatients(searchInput.value);
  });

  // Initial load
  loadPatients();

  // Add Patient Modal Trigger
  container.querySelector("#showAddPatientBtn").addEventListener("click", () => {
    openAddPatientModal(container.querySelector("#addPatientModal"), () => loadPatients());
  });
}

function openAddPatientModal(modalContainer, onSaved) {
  modalContainer.innerHTML = `
    <div class="modal-overlay">
      <div class="modal-container">
        <div class="card-header">
          <h3 class="card-title">Register New Patient</h3>
          <button id="closeModalBtn" class="btn btn-secondary btn-sm">✕</button>
        </div>
        <form id="newPatientForm">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
            <div class="form-group">
              <label class="form-label">First Name *</label>
              <input type="text" id="npFirstName" class="form-input" required />
            </div>
            <div class="form-group">
              <label class="form-label">Last Name</label>
              <input type="text" id="npLastName" class="form-input" />
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
            <div class="form-group">
              <label class="form-label">Mobile Number *</label>
              <input type="tel" id="npPhone" class="form-input" placeholder="+91-..." required />
            </div>
            <div class="form-group">
              <label class="form-label">Date of Birth</label>
              <input type="date" id="npDob" class="form-input" />
            </div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
            <div class="form-group">
              <label class="form-label">Gender *</label>
              <select id="npGender" class="form-select">
                <option value="MALE">Male</option>
                <option value="FEMALE">Female</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Blood Group</label>
              <select id="npBloodGroup" class="form-select">
                <option value="">Unknown</option>
                <option value="A+">A+</option>
                <option value="B+">B+</option>
                <option value="O+">O+</option>
                <option value="AB+">AB+</option>
                <option value="A-">A-</option>
                <option value="B-">B-</option>
                <option value="O-">O-</option>
                <option value="AB-">AB-</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">Known Allergies (e.g. Roghan Badam, Nut, Dust)</label>
            <input type="text" id="npAllergies" class="form-input" placeholder="Optional comma-separated allergens" />
          </div>

          <div id="duplicateWarningArea" style="display: none; margin-bottom: 1rem;"></div>

          <div style="display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem;">
            <button type="button" id="cancelModalBtn" class="btn btn-secondary">Cancel</button>
            <button type="submit" id="savePatientBtn" class="btn btn-primary">Save Patient</button>
          </div>
        </form>
      </div>
    </div>
  `;

  const form = modalContainer.querySelector("#newPatientForm");
  const close = () => { modalContainer.innerHTML = ""; };
  modalContainer.querySelector("#closeModalBtn").addEventListener("click", close);
  modalContainer.querySelector("#cancelModalBtn").addEventListener("click", close);

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const firstName = form.querySelector("#npFirstName").value.trim();
    const lastName = form.querySelector("#npLastName").value.trim();
    const phone = form.querySelector("#npPhone").value.trim();
    const dob = form.querySelector("#npDob").value;
    const gender = form.querySelector("#npGender").value;
    const bloodGroup = form.querySelector("#npBloodGroup").value;
    const allergyText = form.querySelector("#npAllergies").value.trim();

    const allergies = allergyText ? allergyText.split(",").map(a => ({
      allergen_type: "HERBAL",
      allergen_name: a.trim(),
      severity: "MODERATE"
    })) : [];

    const payload = {
      first_name: firstName,
      last_name: lastName,
      phone,
      dob,
      gender,
      blood_group: bloodGroup,
      allergies
    };

    try {
      await api.post("/api/v1/patients", payload);
      close();
      onSaved();
    } catch (err) {
      if (err.code === "CONFLICT") {
        // Show Duplicate Warning with Force Override Option
        const warnArea = modalContainer.querySelector("#duplicateWarningArea");
        warnArea.style.display = "block";
        warnArea.innerHTML = `
          <div class="allergy-alert-box" style="background: #fffbeb; border-color: #fde68a; color: #92400e;">
            <strong>⚠️ Potential Duplicate Detected!</strong>
            <p>A patient with phone ${phone} already exists.</p>
            <button type="button" id="forceOverrideBtn" class="btn btn-secondary btn-sm" style="margin-top: 0.5rem;">
              Confirm and Register Anyway (Override)
            </button>
          </div>
        `;
        warnArea.querySelector("#forceOverrideBtn").addEventListener("click", async () => {
          try {
            await api.post("/api/v1/patients?override_duplicate=true", payload);
            close();
            onSaved();
          } catch (e2) {
            alert("Error: " + e2.message);
          }
        });
      } else {
        alert("Registration failed: " + err.message);
      }
    }
  });
}

async function issueTokenForPatient(patientId) {
  try {
    const res = await api.post("/api/v1/encounters", {
      patient_id: patientId,
      encounter_type: "WALK_IN"
    });
    alert(`OPD Token #${res.encounter.token_number} issued successfully!`);
    state.setActiveEncounter(res.encounter);
    state.setActiveTab("consultation");
  } catch (err) {
    alert("Failed to issue token: " + err.message);
  }
}

async function openPatient360(patientId) {
  const container = document.querySelector("#patient360Container");
  if (!container) return;

  container.innerHTML = `<div class="modal-overlay"><div class="modal-container"><p>Loading Patient 360 record...</p></div></div>`;

  try {
    const data = await api.get(`/api/v1/patients/${patientId}/360`);
    const p = data.patient_360;

    let allergiesHtml = p.allergies.length 
      ? p.allergies.map(a => `<span class="badge badge-block" style="margin-right: 0.35rem;">⚠️ ${a.allergen_name} (${a.severity})</span>`).join("")
      : '<span style="color: var(--color-text-muted);">No documented allergies</span>';

    let visitsHtml = p.encounters.length
      ? p.encounters.map(e => `
          <div class="card" style="margin-bottom: 0.5rem; padding: 0.75rem;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
              <strong>Token #${e.token_number} (${e.encounter_type})</strong>
              <span style="color: var(--color-text-muted);">${e.created_at}</span>
            </div>
            <div style="font-size: 0.9rem; margin-top: 0.25rem;">Complaint: ${e.chief_complaint || "—"}</div>
            ${e.systolic_bp ? `<div style="font-size: 0.8rem; color: var(--color-text-muted);">BP: ${e.systolic_bp}/${e.diastolic_bp} | Pulse: ${e.pulse_bpm} bpm</div>` : ''}
          </div>
        `).join("")
      : '<p style="color: var(--color-text-muted);">No previous visit history.</p>';

    let rxHtml = p.prescriptions.length
      ? p.prescriptions.map(pr => `
          <div class="card" style="margin-bottom: 0.5rem; padding: 0.75rem; border-left: 4px solid var(--color-primary-light);">
            <div style="display: flex; justify-content: space-between; font-size: 0.85rem;">
              <strong>Prescription v${pr.version_number} (${pr.status})</strong>
              <span class="badge ${pr.overall_safety_state === 'PASS' ? 'badge-pass' : 'badge-warn'}">${pr.overall_safety_state}</span>
            </div>
            <div style="font-size: 0.85rem; margin-top: 0.35rem;">
              Items: ${pr.items.map(it => it.item_name).join(", ") || "No items"}
            </div>
            ${pr.signature_hash ? `<div class="print-hash" style="margin-top: 0.25rem; font-size: 0.65rem;">SHA-256: ${pr.signature_hash}</div>` : ''}
          </div>
        `).join("")
      : '<p style="color: var(--color-text-muted);">No past prescriptions on record.</p>';

    container.innerHTML = `
      <div class="modal-overlay">
        <div class="modal-container" style="max-width: 800px;">
          <div class="card-header">
            <div>
              <h2 class="card-title">${p.first_name} ${p.last_name || ""}</h2>
              <span class="mrn-badge">MRN: ${p.mrn} | 📞 ${p.phone} | ${p.gender} (${p.dob || "—"})</span>
            </div>
            <button id="close360Btn" class="btn btn-secondary btn-sm">✕ Close</button>
          </div>

          <div style="margin-bottom: 1rem;">
            <strong>Allergies:</strong><br />
            ${allergiesHtml}
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
              <h4 style="margin-bottom: 0.5rem; color: var(--color-primary-dark);">Consultation History</h4>
              ${visitsHtml}
            </div>
            <div>
              <h4 style="margin-bottom: 0.5rem; color: var(--color-primary-dark);">Prescription History</h4>
              ${rxHtml}
            </div>
          </div>
        </div>
      </div>
    `;

    container.querySelector("#close360Btn").addEventListener("click", () => {
      container.innerHTML = "";
    });

  } catch (err) {
    alert("Error fetching Patient 360: " + err.message);
    container.innerHTML = "";
  }
}

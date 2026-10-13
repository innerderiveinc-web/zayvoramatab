/**
 * Phase 12 Hospital Workflows & Interoperability View:
 * IPD/ADT, Bed Board, Lab Orders & Results, Referrals, FHIR R4 & ABDM Gateway
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export async function renderHospitalInterop(container) {
  const user = state.user;
  container.innerHTML = `
    <div class="header-card" style="margin-bottom: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
        <div>
          <h2 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <span>🏥</span>
            <span>Hospital Workflows & Interoperability</span>
          </h2>
          <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.9rem;">
            Inpatient ADT, Bed Management, Laboratory Orders, Clinical Referrals, FHIR R4 & ABDM Gateway
          </p>
        </div>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
          <span class="badge" style="background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; font-weight: 600;">
            ABDM State: CONTRACT_TESTED_HARNESS
          </span>
          <span class="badge" style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1;">
            FHIR R4 v4.0.1
          </span>
        </div>
      </div>
      
      <div style="display: flex; gap: 0.5rem; margin-top: 1.25rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem;">
        <button id="tabIpdBtn" class="btn btn-sm btn-primary">🛏️ Inpatient ADT & Bed Board</button>
        <button id="tabLabBtn" class="btn btn-sm btn-secondary">🔬 Laboratory / LIS</button>
        <button id="tabRefBtn" class="btn btn-sm btn-secondary">📋 Hospital Referrals</button>
        <button id="tabFhirAbdmBtn" class="btn btn-sm btn-secondary">🌐 FHIR R4 & ABDM Gateway</button>
      </div>
    </div>

    <div id="hospitalSubViewContent">
      <div style="text-align: center; padding: 2rem; color: #94a3b8;">Loading Hospital Workflows...</div>
    </div>
  `;

  const subView = container.querySelector("#hospitalSubViewContent");
  const tabIpd = container.querySelector("#tabIpdBtn");
  const tabLab = container.querySelector("#tabLabBtn");
  const tabRef = container.querySelector("#tabRefBtn");
  const tabFhirAbdm = container.querySelector("#tabFhirAbdmBtn");

  function setSubTab(activeBtn) {
    [tabIpd, tabLab, tabRef, tabFhirAbdm].forEach(b => {
      b.className = b === activeBtn ? "btn btn-sm btn-primary" : "btn btn-sm btn-secondary";
    });
  }

  tabIpd.addEventListener("click", () => {
    setSubTab(tabIpd);
    renderIpdSubView(subView);
  });
  tabLab.addEventListener("click", () => {
    setSubTab(tabLab);
    renderLabSubView(subView);
  });
  tabRef.addEventListener("click", () => {
    setSubTab(tabRef);
    renderReferralsSubView(subView);
  });
  tabFhirAbdm.addEventListener("click", () => {
    setSubTab(tabFhirAbdm);
    renderFhirAbdmSubView(subView);
  });

  // Default to IPD view
  renderIpdSubView(subView);
}

async function renderIpdSubView(el) {
  try {
    const [dashboardResp, admissionsResp] = await Promise.all([
      apiClient.get("/api/v1/ipd/occupancy-dashboard"),
      apiClient.get("/api/v1/ipd/admissions")
    ]);
    const dashboard = dashboardResp.dashboard || {};
    const admissions = admissionsResp.admissions || [];

    el.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
        <div class="card" style="padding: 1rem; border-left: 4px solid #3b82f6;">
          <div style="color: #64748b; font-size: 0.85rem;">Total Hospital Beds</div>
          <div style="font-size: 1.75rem; font-weight: 700; color: #1e293b;">${dashboard.total_beds || 0}</div>
        </div>
        <div class="card" style="padding: 1rem; border-left: 4px solid #10b981;">
          <div style="color: #64748b; font-size: 0.85rem;">Available Beds</div>
          <div style="font-size: 1.75rem; font-weight: 700; color: #10b981;">${dashboard.available_beds || 0}</div>
        </div>
        <div class="card" style="padding: 1rem; border-left: 4px solid #f59e0b;">
          <div style="color: #64748b; font-size: 0.85rem;">Occupied Beds</div>
          <div style="font-size: 1.75rem; font-weight: 700; color: #f59e0b;">${dashboard.occupied_beds || 0}</div>
        </div>
        <div class="card" style="padding: 1rem; border-left: 4px solid #8b5cf6;">
          <div style="color: #64748b; font-size: 0.85rem;">Occupancy Rate</div>
          <div style="font-size: 1.75rem; font-weight: 700; color: #8b5cf6;">${dashboard.occupancy_rate_percent || 0}%</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;">
        <div>
          <div class="card" style="padding: 1.25rem; margin-bottom: 1.5rem;">
            <h3 style="margin-top: 0; font-size: 1.1rem;">🛏️ Ward Bed Matrix</h3>
            <div style="display: flex; flex-direction: column; gap: 1rem;">
              ${(dashboard.wards || []).map(w => `
                <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; background: #fafafa;">
                  <div style="display: flex; justify-content: space-between; margin-bottom: 0.75rem;">
                    <strong>${w.ward_name} (${w.ward_code})</strong>
                    <span class="badge" style="background: #e2e8f0;">${w.occupied_beds}/${w.total_beds} Occupied</span>
                  </div>
                  <div style="display: flex; flex-wrap: wrap; gap: 0.75rem;">
                    ${(w.beds || []).map(b => {
                      const color = b.operational_status === "available" ? "#10b981" : b.operational_status === "occupied" ? "#f59e0b" : "#64748b";
                      return `
                        <div style="border: 2px solid ${color}; border-radius: 6px; padding: 0.5rem 0.75rem; background: #fff; min-width: 110px;">
                          <div style="font-weight: 600; font-size: 0.9rem;">${b.bed_code}</div>
                          <div style="font-size: 0.75rem; color: #64748b;">${b.bed_category}</div>
                          <span style="font-size: 0.75rem; color: ${color}; font-weight: 600; text-transform: uppercase;">${b.operational_status}</span>
                        </div>
                      `;
                    }).join('')}
                  </div>
                </div>
              `).join('') || '<div style="color: #94a3b8;">No wards or beds configured.</div>'}
            </div>
          </div>

          <div class="card" style="padding: 1.25rem;">
            <h3 style="margin-top: 0; font-size: 1.1rem;">📋 Inpatient Admissions</h3>
            <div style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                <thead>
                  <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; color: #64748b;">
                    <th style="padding: 0.5rem;">Admission ID</th>
                    <th style="padding: 0.5rem;">Patient</th>
                    <th style="padding: 0.5rem;">Ward / Bed</th>
                    <th style="padding: 0.5rem;">Urgency</th>
                    <th style="padding: 0.5rem;">Status</th>
                    <th style="padding: 0.5rem;">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  ${admissions.map(a => `
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                      <td style="padding: 0.5rem; font-family: monospace;">${a.id.slice(0, 8)}...</td>
                      <td style="padding: 0.5rem;"><strong>${a.patient_name || a.patient_id}</strong></td>
                      <td style="padding: 0.5rem;">${a.ward_name || '-'} / ${a.bed_code || '-'}</td>
                      <td style="padding: 0.5rem;"><span class="badge ${a.urgency === 'EMERGENCY' ? 'badge-danger' : 'badge-info'}">${a.urgency}</span></td>
                      <td style="padding: 0.5rem;"><span class="badge ${a.status === 'admitted' ? 'badge-success' : 'badge-warning'}">${a.status}</span></td>
                      <td style="padding: 0.5rem;">
                        <button class="btn btn-xs btn-outline view-adm-btn" data-id="${a.id}">View</button>
                      </td>
                    </tr>
                  `).join('') || '<tr><td colspan="6" style="padding: 1rem; text-align: center; color: #94a3b8;">No active inpatient admissions.</td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div>
          <div class="card" style="padding: 1.25rem;">
            <h3 style="margin-top: 0; font-size: 1.1rem;">➕ Request Inpatient Admission</h3>
            <form id="newAdmissionForm" style="display: flex; flex-direction: column; gap: 0.75rem;">
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Patient ID</label>
                <input type="text" id="admPatientId" class="input" placeholder="pat-..." required style="width: 100%;" />
              </div>
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Urgency</label>
                <select id="admUrgency" class="input" style="width: 100%;">
                  <option value="ROUTINE">Routine</option>
                  <option value="URGENT">Urgent</option>
                  <option value="EMERGENCY">Emergency</option>
                </select>
              </div>
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Admission Type</label>
                <select id="admType" class="input" style="width: 100%;">
                  <option value="ELECTIVE">Elective</option>
                  <option value="OBSERVATION">Observation</option>
                  <option value="REGIMENAL_INPATIENT">Regimenal Inpatient (Ilaj-bil-Tadbeer)</option>
                </select>
              </div>
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Reason for Admission</label>
                <textarea id="admReason" class="input" rows="2" placeholder="Clinical indication..." required style="width: 100%;"></textarea>
              </div>
              <button type="submit" class="btn btn-primary" style="margin-top: 0.5rem;">Submit Request</button>
            </form>
          </div>
        </div>
      </div>
    `;

    el.querySelector("#newAdmissionForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          patient_id: el.querySelector("#admPatientId").value.trim(),
          urgency: el.querySelector("#admUrgency").value,
          admission_type: el.querySelector("#admType").value,
          reason_for_admission: el.querySelector("#admReason").value.trim(),
        };
        await apiClient.post("/api/v1/ipd/admissions", payload);
        alert("Admission request submitted successfully.");
        renderIpdSubView(el);
      } catch (err) {
        alert("Error: " + (err.message || err.detail || "Failed to create admission"));
      }
    });

  } catch (err) {
    el.innerHTML = `<div class="card alert alert-danger">Failed to load IPD dashboard: ${err.message}</div>`;
  }
}

async function renderLabSubView(el) {
  try {
    const [catResp, ordersResp] = await Promise.all([
      apiClient.get("/api/v1/lab/catalog"),
      apiClient.get("/api/v1/lab/orders")
    ]);
    const catalog = catResp.catalog_items || [];
    const orders = ordersResp.lab_orders || [];

    el.innerHTML = `
      <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;">
        <div>
          <div class="card" style="padding: 1.25rem; margin-bottom: 1.5rem;">
            <h3 style="margin-top: 0; font-size: 1.1rem;">🧪 Laboratory Orders & LIS Feeds</h3>
            <div style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                <thead>
                  <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; color: #64748b;">
                    <th style="padding: 0.5rem;">Order #</th>
                    <th style="padding: 0.5rem;">Patient ID</th>
                    <th style="padding: 0.5rem;">Tests</th>
                    <th style="padding: 0.5rem;">Priority</th>
                    <th style="padding: 0.5rem;">Status</th>
                  </tr>
                </thead>
                <tbody>
                  ${orders.map(o => `
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                      <td style="padding: 0.5rem; font-weight: 600;">${o.order_number}</td>
                      <td style="padding: 0.5rem;">${o.patient_id}</td>
                      <td style="padding: 0.5rem;">${(o.tests || []).map(t => t.test_name || t.test_code).join(', ') || '-'}</td>
                      <td style="padding: 0.5rem;"><span class="badge ${o.priority === 'STAT' ? 'badge-danger' : 'badge-info'}">${o.priority}</span></td>
                      <td style="padding: 0.5rem;"><span class="badge ${o.status === 'final' ? 'badge-success' : 'badge-warning'}">${o.status}</span></td>
                    </tr>
                  `).join('') || '<tr><td colspan="5" style="padding: 1rem; text-align: center; color: #94a3b8;">No lab orders found.</td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div class="card" style="padding: 1.25rem;">
            <h3 style="margin-top: 0; font-size: 1.1rem;">🔬 Governed Laboratory Test Catalog</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem;">
              ${catalog.map(item => `
                <div style="border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.75rem; background: #fff;">
                  <div style="font-weight: 600;">${item.name}</div>
                  <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 0.5rem;">LOINC: ${item.loinc_code || 'Unmapped'} | ${item.category}</div>
                  <div style="font-size: 0.85rem;"><strong>Ref:</strong> ${item.reference_range_text || `${item.ref_range_low} - ${item.ref_range_high} ${item.default_unit}`}</div>
                  ${item.critical_low || item.critical_high ? `
                    <div style="font-size: 0.8rem; color: #dc2626; font-weight: 600; margin-top: 0.25rem;">
                      Critical: &lt;${item.critical_low || '-'} / &gt;${item.critical_high || '-'} ${item.default_unit}
                    </div>
                  ` : ''}
                </div>
              `).join('') || '<div style="color: #94a3b8;">No catalog items configured.</div>'}
            </div>
          </div>
        </div>

        <div>
          <div class="card" style="padding: 1.25rem;">
            <h3 style="margin-top: 0; font-size: 1.1rem;">📥 Record Lab Result (Manual / LIS)</h3>
            <form id="recordResultForm" style="display: flex; flex-direction: column; gap: 0.75rem;">
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Order ID</label>
                <input type="text" id="resOrderId" class="input" placeholder="ord-..." required style="width: 100%;" />
              </div>
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Patient ID</label>
                <input type="text" id="resPatientId" class="input" placeholder="pat-..." required style="width: 100%;" />
              </div>
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Test Code</label>
                <input type="text" id="resTestCode" class="input" placeholder="LAB-K" required style="width: 100%;" />
              </div>
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Result Value</label>
                <input type="text" id="resValue" class="input" placeholder="4.2" required style="width: 100%;" />
              </div>
              <div>
                <label style="font-size: 0.85rem; font-weight: 600;">Unit</label>
                <input type="text" id="resUnit" class="input" placeholder="mmol/L" required style="width: 100%;" />
              </div>
              <button type="submit" class="btn btn-primary" style="margin-top: 0.5rem;">Save & Validate Result</button>
            </form>
          </div>
        </div>
      </div>
    `;

    el.querySelector("#recordResultForm").addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const payload = {
          order_id: el.querySelector("#resOrderId").value.trim(),
          patient_id: el.querySelector("#resPatientId").value.trim(),
          test_code: el.querySelector("#resTestCode").value.trim(),
          test_name: el.querySelector("#resTestCode").value.trim(),
          result_value: el.querySelector("#resValue").value.trim(),
          unit: el.querySelector("#resUnit").value.trim(),
          performing_lab_name: "Central Matab Diagnostic Lab",
        };
        const res = await apiClient.post("/api/v1/lab/results", payload);
        alert(`Lab result recorded. Abnormal flag: ${res.lab_result?.abnormal_flag || 'NORMAL'}`);
        renderLabSubView(el);
      } catch (err) {
        alert("Error: " + (err.message || err.detail || "Failed to record lab result"));
      }
    });

  } catch (err) {
    el.innerHTML = `<div class="card alert alert-danger">Failed to load Laboratory view: ${err.message}</div>`;
  }
}

async function renderReferralsSubView(el) {
  try {
    const referralsResp = await apiClient.get("/api/v1/hospital-referrals");
    const referrals = referralsResp.referrals || [];

    el.innerHTML = `
      <div class="card" style="padding: 1.25rem;">
        <h3 style="margin-top: 0; font-size: 1.1rem;">📋 Structured Hospital Referrals</h3>
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
            <thead>
              <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; color: #64748b;">
                <th style="padding: 0.5rem;">Referral ID</th>
                <th style="padding: 0.5rem;">Patient ID</th>
                <th style="padding: 0.5rem;">Type</th>
                <th style="padding: 0.5rem;">Clinical Question</th>
                <th style="padding: 0.5rem;">Status</th>
                <th style="padding: 0.5rem;">Actions</th>
              </tr>
            </thead>
            <tbody>
              ${referrals.map(r => `
                <tr style="border-bottom: 1px solid #f1f5f9;">
                  <td style="padding: 0.5rem; font-family: monospace;">${r.id.slice(0, 8)}...</td>
                  <td style="padding: 0.5rem;">${r.patient_id}</td>
                  <td style="padding: 0.5rem;"><span class="badge badge-info">${r.referral_type}</span></td>
                  <td style="padding: 0.5rem; max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${r.clinical_question || '-'}</td>
                  <td style="padding: 0.5rem;"><span class="badge ${r.status === 'completed' ? 'badge-success' : 'badge-warning'}">${r.status}</span></td>
                  <td style="padding: 0.5rem;">
                    ${r.status === 'sent' || r.status === 'received' ? `
                      <button class="btn btn-xs btn-primary accept-ref-btn" data-id="${r.id}">Accept</button>
                    ` : ''}
                    ${r.status === 'accepted' ? `
                      <button class="btn btn-xs btn-success close-ref-btn" data-id="${r.id}">Close Loop</button>
                    ` : ''}
                  </td>
                </tr>
              `).join('') || '<tr><td colspan="6" style="padding: 1rem; text-align: center; color: #94a3b8;">No referrals recorded.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    `;

    el.querySelectorAll(".accept-ref-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        try {
          await apiClient.post(`/api/v1/hospital-referrals/${btn.dataset.id}/accept`, {});
          alert("Referral accepted.");
          renderReferralsSubView(el);
        } catch (e) {
          alert("Error: " + e.message);
        }
      });
    });

    el.querySelectorAll(".close-ref-btn").forEach(btn => {
      btn.addEventListener("click", async () => {
        try {
          await apiClient.post(`/api/v1/hospital-referrals/${btn.dataset.id}/close`, {
            closure_outcome: "Consultation note received and treatment plan adjusted.",
          });
          alert("Referral closed successfully.");
          renderReferralsSubView(el);
        } catch (e) {
          alert("Error: " + e.message);
        }
      });
    });

  } catch (err) {
    el.innerHTML = `<div class="card alert alert-danger">Failed to load Referrals: ${err.message}</div>`;
  }
}

async function renderFhirAbdmSubView(el) {
  el.innerHTML = `
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
      <div class="card" style="padding: 1.25rem;">
        <h3 style="margin-top: 0; font-size: 1.1rem;">🌐 FHIR R4 Bundle Exporter</h3>
        <p style="color: #64748b; font-size: 0.85rem;">
          Generate HL7 FHIR R4 / NRCeS ABDM compliant document bundles with active patient consent verification.
        </p>
        <form id="fhirExportForm" style="display: flex; flex-direction: column; gap: 0.75rem;">
          <div>
            <label style="font-size: 0.85rem; font-weight: 600;">Patient ID</label>
            <input type="text" id="fhirPatientId" class="input" placeholder="pat-..." required style="width: 100%;" />
          </div>
          <div>
            <label style="font-size: 0.85rem; font-weight: 600;">Bundle Type</label>
            <select id="fhirBundleType" class="input" style="width: 100%;">
              <option value="OPConsultation">OPConsultation (Prescription + Assessment)</option>
              <option value="DischargeSummary">DischargeSummary (Inpatient Stay)</option>
              <option value="DiagnosticReport">DiagnosticReport (Laboratory Results)</option>
            </select>
          </div>
          <div>
            <label style="font-size: 0.85rem; font-weight: 600;">Consent Artifact ID (Optional)</label>
            <input type="text" id="fhirConsentId" class="input" placeholder="cst-..." style="width: 100%;" />
          </div>
          <button type="submit" class="btn btn-primary" style="margin-top: 0.5rem;">Generate FHIR R4 Bundle</button>
        </form>

        <div id="fhirExportOutput" style="margin-top: 1rem; display: none;">
          <h4 style="margin: 0 0 0.5rem 0; font-size: 0.95rem;">Export Output</h4>
          <pre id="fhirJsonBlock" style="background: #1e293b; color: #f8fafc; padding: 0.75rem; border-radius: 6px; font-size: 0.8rem; max-height: 250px; overflow: auto;"></pre>
        </div>
      </div>

      <div class="card" style="padding: 1.25rem;">
        <h3 style="margin-top: 0; font-size: 1.1rem;">🛡️ ABDM Gateway Harness Verification</h3>
        <p style="color: #64748b; font-size: 0.85rem;">
          Simulate an incoming ABDM Gateway data push/callback under contract-tested conditions.
        </p>
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.75rem; font-size: 0.85rem; margin-bottom: 1rem;">
          <div><strong>Gateway Readiness Status:</strong> <span class="badge badge-info">CONTRACT_TESTED_HARNESS</span></div>
          <div style="margin-top: 0.25rem; color: #64748b;">
            Live external gateway sync remains in <code>BLOCKED_BY_EXTERNAL_DEPENDENCY</code> until production NHA client credentials and sandbox IP whitelist are provisioned.
          </div>
        </div>
        <button id="runAbdmHarnessBtn" class="btn btn-secondary">Simulate ABDM Data Flow Request</button>
        <div id="abdmHarnessOutput" style="margin-top: 1rem; display: none;">
          <pre id="abdmJsonBlock" style="background: #1e293b; color: #f8fafc; padding: 0.75rem; border-radius: 6px; font-size: 0.8rem; max-height: 250px; overflow: auto;"></pre>
        </div>
      </div>
    </div>
  `;

  el.querySelector("#fhirExportForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const payload = {
        patient_id: el.querySelector("#fhirPatientId").value.trim(),
        bundle_type: el.querySelector("#fhirBundleType").value,
        consent_id: el.querySelector("#fhirConsentId").value.trim() || undefined,
      };
      const res = await apiClient.post("/api/v1/interop/fhir/export", payload);
      const outDiv = el.querySelector("#fhirExportOutput");
      const codeBlock = el.querySelector("#fhirJsonBlock");
      outDiv.style.display = "block";
      codeBlock.textContent = JSON.stringify(res.bundle, null, 2);
    } catch (err) {
      alert("FHIR Export Error: " + (err.message || err.detail || "Export failed"));
    }
  });

  el.querySelector("#runAbdmHarnessBtn").addEventListener("click", async () => {
    try {
      const payload = {
        transaction_id: "txn-harness-" + Date.now(),
        data_push_url: "https://dev.abdm.gov.in/data/receive",
        hip_id: "IN070001",
        hiu_id: "IN070002",
        consent_id: "cst-abdm-valid",
      };
      const res = await apiClient.post("/api/v1/interop/abdm/harness-request", payload);
      const outDiv = el.querySelector("#abdmHarnessOutput");
      const codeBlock = el.querySelector("#abdmJsonBlock");
      outDiv.style.display = "block";
      codeBlock.textContent = JSON.stringify(res.abdm_response, null, 2);
    } catch (err) {
      alert("ABDM Harness Error: " + (err.message || err.detail || "Harness invocation failed"));
    }
  });
}

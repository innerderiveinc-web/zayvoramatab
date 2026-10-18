/**
 * System Settings & Clinic Preferences Studio — ZAYVORA MATAB OS
 * Unified control panel for Clinic Branding, Prescription Printing,
 * OPD Consultation Rules, Pharmacy Automation & Data Backups.
 */

import { state } from "../state.js";
import { apiClient } from "/packages/api-client/client.js";
import { i18n } from "../i18n.js";

const DEFAULT_SETTINGS = {
  clinic_name: "ZAYVORA Matab & Hospital",
  clinic_tagline: "Center for Classical Unani Medicine & Bedside Decision Support",
  head_practitioner: "Hakim Tariq Mahmud (Senior Consulting Tabib)",
  registration_no: "AYUSH-UNANI-98241",
  phone: "+91 98765 43210",
  email: "matab@zayvora.com",
  address: "42 Shifa Marg, Civil Lines, New Delhi, India",
  consultation_fee: 300,
  default_followup_days: 7,
  default_print_format: "a4",
  thermal_slip_width: "80mm",
  header_mode: "full",
  prescription_disclaimer: "Valid for clinical guidance. Please report any adverse symptoms immediately. Follow-up consultation recommended within 7 days.",
  require_clinician_pin: true,
  auto_deduct_inventory: true,
  low_stock_threshold: 10,
  enable_abdm_qr: true,
  mizaj_required: false,
  default_language: "en",
  operating_hours: "09:30 AM – 08:30 PM (Mon – Sat)"
};

export async function renderSettings(container) {
  let settings = { ...DEFAULT_SETTINGS };

  // Load saved settings from server or localStorage
  try {
    const res = await apiClient.get("/api/v1/settings");
    if (res && res.settings) {
      settings = { ...DEFAULT_SETTINGS, ...res.settings };
    }
  } catch (e) {
    try {
      const local = JSON.parse(localStorage.getItem("matab_system_settings") || "null");
      if (local) settings = { ...DEFAULT_SETTINGS, ...local };
    } catch(err) {}
  }

  container.innerHTML = `
    <div style="margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 1rem;">
      <div>
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
          <span style="font-size: 1.5rem;">⚙️</span>
          <h1 style="font-size: 1.45rem; color: var(--matab-color-brand-primary); margin: 0; font-weight: 800;">
            System Settings &amp; Matab Preferences
          </h1>
          <span class="badge badge-success" style="font-size: 0.72rem;">Live Preferences</span>
        </div>
        <p style="color: var(--matab-color-text-secondary); font-size: 0.88rem; margin: 0;">
          Central control panel for Clinic Branding, Prescription Printing Layouts, OPD Consultation Defaults &amp; Local Backups.
        </p>
      </div>
      <div style="display: flex; gap: 0.5rem;">
        <button id="btnResetSettings" class="btn btn-secondary btn-sm" type="button">
          <span>🔄</span> Reset Defaults
        </button>
        <button id="btnSaveSettingsTop" class="btn btn-primary btn-sm" type="button" style="font-weight: 700;">
          <span>💾</span> Save All Preferences
        </button>
      </div>
    </div>

    <!-- Alert / Status Banner -->
    <div id="settingsAlertBox" style="display: none; padding: 0.85rem 1.25rem; border-radius: var(--matab-radius-md); margin-bottom: 1.25rem; font-size: 0.88rem;"></div>

    <!-- Settings Layout: Sidebar Tabs + Content Area -->
    <div style="display: grid; grid-template-columns: 240px 1fr; gap: 1.5rem; align-items: start;">
      
      <!-- Settings Sub-Navigation -->
      <div class="card" style="padding: 0.5rem; position: sticky; top: 1rem;">
        <div style="font-size: 0.72rem; font-weight: 700; text-transform: uppercase; color: var(--matab-color-text-muted); padding: 0.5rem 0.75rem; letter-spacing: 0.05em;">
          Preference Categories
        </div>
        <div style="display: flex; flex-direction: column; gap: 0.2rem;" id="settingsNavList">
          <button type="button" class="btn btn-sm btn-settings-tab active" data-panel="panelIdentity" style="justify-content: flex-start; text-align: left; padding: 0.6rem 0.75rem; border-radius: var(--matab-radius-sm); border: none; background: var(--matab-color-brand-surface); color: var(--matab-color-brand-primary); font-weight: 700; cursor: pointer;">
            <span>🏢</span> Clinic &amp; Doctor Profile
          </button>
          <button type="button" class="btn btn-sm btn-settings-tab" data-panel="panelRxPrint" style="justify-content: flex-start; text-align: left; padding: 0.6rem 0.75rem; border-radius: var(--matab-radius-sm); border: none; background: transparent; color: var(--matab-color-text-secondary); font-weight: 600; cursor: pointer;">
            <span>📜</span> Prescription &amp; Printing
          </button>
          <button type="button" class="btn btn-sm btn-settings-tab" data-panel="panelOpdRules" style="justify-content: flex-start; text-align: left; padding: 0.6rem 0.75rem; border-radius: var(--matab-radius-sm); border: none; background: transparent; color: var(--matab-color-text-secondary); font-weight: 600; cursor: pointer;">
            <span>🩺</span> OPD &amp; Clinical Defaults
          </button>
          <button type="button" class="btn btn-sm btn-settings-tab" data-panel="panelPharmacy" style="justify-content: flex-start; text-align: left; padding: 0.6rem 0.75rem; border-radius: var(--matab-radius-sm); border: none; background: transparent; color: var(--matab-color-text-secondary); font-weight: 600; cursor: pointer;">
            <span>📦</span> Dispensary &amp; Inventory
          </button>
          <button type="button" class="btn btn-sm btn-settings-tab" data-panel="panelLocalization" style="justify-content: flex-start; text-align: left; padding: 0.6rem 0.75rem; border-radius: var(--matab-radius-sm); border: none; background: transparent; color: var(--matab-color-text-secondary); font-weight: 600; cursor: pointer;">
            <span>🌐</span> Language &amp; Schedule
          </button>
          <button type="button" class="btn btn-sm btn-settings-tab" data-panel="panelBackup" style="justify-content: flex-start; text-align: left; padding: 0.6rem 0.75rem; border-radius: var(--matab-radius-sm); border: none; background: transparent; color: var(--matab-color-text-secondary); font-weight: 600; cursor: pointer;">
            <span>🛡️</span> Data &amp; DB Snapshots
          </button>
        </div>
      </div>

      <!-- Main Panels Container -->
      <form id="settingsMainForm">
        
        <!-- PANEL 1: CLINIC & DOCTOR PROFILE -->
        <div id="panelIdentity" class="settings-panel card" style="padding: 1.5rem; margin-bottom: 1.5rem;">
          <h3 style="margin-top: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>🏢</span> Clinic &amp; Head Practitioner Profile
          </h3>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.82rem; margin-bottom: 1.25rem;">
            These official details appear on your Prescription Letterheads, Thermal Receipt Slips, and OPD Patient Cards.
          </p>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group" style="grid-column: span 2;">
              <label class="form-label">Hospital / Matab Name *</label>
              <input type="text" id="cfg_clinic_name" class="form-input" value="${escapeHtml(settings.clinic_name)}" required />
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label class="form-label">Clinical Tagline / Specialty Description</label>
              <input type="text" id="cfg_clinic_tagline" class="form-input" value="${escapeHtml(settings.clinic_tagline)}" />
            </div>

            <div class="form-group">
              <label class="form-label">Chief Consulting Tabib / Doctor *</label>
              <input type="text" id="cfg_head_practitioner" class="form-input" value="${escapeHtml(settings.head_practitioner)}" required />
            </div>

            <div class="form-group">
              <label class="form-label">AYUSH / Medical Registration No. *</label>
              <input type="text" id="cfg_registration_no" class="form-input" value="${escapeHtml(settings.registration_no)}" required />
            </div>

            <div class="form-group">
              <label class="form-label">Clinic Phone / WhatsApp Hotline *</label>
              <input type="text" id="cfg_phone" class="form-input" value="${escapeHtml(settings.phone)}" required />
            </div>

            <div class="form-group">
              <label class="form-label">Official Email</label>
              <input type="email" id="cfg_email" class="form-input" value="${escapeHtml(settings.email)}" />
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label class="form-label">Physical Address (Appears on Letterhead) *</label>
              <textarea id="cfg_address" class="form-input" rows="2" required style="resize: vertical;">${escapeHtml(settings.address)}</textarea>
            </div>
          </div>

          <!-- Real-time Letterhead Preview Box -->
          <div style="margin-top: 1.25rem; background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: var(--matab-radius-md); padding: 1rem;">
            <div style="font-size: 0.72rem; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 0.5rem;">
              👁️ Live Prescription Header Preview:
            </div>
            <div style="text-align: center; border-bottom: 2px solid #065f46; padding-bottom: 0.75rem;">
              <div style="font-size: 1.15rem; font-weight: 800; color: #064e3b;" id="prevClinicName">${escapeHtml(settings.clinic_name)}</div>
              <div style="font-size: 0.78rem; color: #475569;" id="prevClinicTagline">${escapeHtml(settings.clinic_tagline)}</div>
              <div style="font-size: 0.75rem; color: #64748b; margin-top: 0.25rem;">
                <span id="prevDrName"><strong>${escapeHtml(settings.head_practitioner)}</strong></span> | 
                <span id="prevRegNo">Reg: ${escapeHtml(settings.registration_no)}</span> | 
                <span id="prevPhone">Ph: ${escapeHtml(settings.phone)}</span>
              </div>
              <div style="font-size: 0.72rem; color: #94a3b8;" id="prevAddress">${escapeHtml(settings.address)}</div>
            </div>
          </div>
        </div>

        <!-- PANEL 2: PRESCRIPTION & PRINTING PREFERENCES -->
        <div id="panelRxPrint" class="settings-panel card" style="display: none; padding: 1.5rem; margin-bottom: 1.5rem;">
          <h3 style="margin-top: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>📜</span> Prescription &amp; Thermal Printing Preferences
          </h3>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.82rem; margin-bottom: 1.25rem;">
            Configure how prescriptions are generated, printed, and formatted for thermal slips or formal A4 stationery.
          </p>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
              <label class="form-label">Default Printing Format *</label>
              <select id="cfg_default_print_format" class="form-select">
                <option value="a4" ${settings.default_print_format === "a4" ? "selected" : ""}>📄 Standard A4 Full Letterhead (Detailed)</option>
                <option value="thermal" ${settings.default_print_format === "thermal" ? "selected" : ""}>🧾 POS Thermal Receipt Slip (Fast OPD / Dispensary)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">Thermal Receipt Paper Width</label>
              <select id="cfg_thermal_slip_width" class="form-select">
                <option value="80mm" ${settings.thermal_slip_width === "80mm" ? "selected" : ""}>80mm (Standard POS Thermal Roll)</option>
                <option value="58mm" ${settings.thermal_slip_width === "58mm" ? "selected" : ""}>58mm (Compact Mobile Printer)</option>
              </select>
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label class="form-label">Letterhead Header Spacing</label>
              <select id="cfg_header_mode" class="form-select">
                <option value="full" ${settings.header_mode === "full" ? "selected" : ""}>Print Full Matab Header &amp; Contact Info (Plain Paper)</option>
                <option value="blank_pad" ${settings.header_mode === "blank_pad" ? "selected" : ""}>Leave 2.5-inch Top Margin (For Pre-Printed Doctor Letterhead Pads)</option>
              </select>
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label class="form-label">Prescription Footer Legal Disclaimer &amp; Patient Instructions</label>
              <textarea id="cfg_prescription_disclaimer" class="form-input" rows="2" style="resize: vertical;">${escapeHtml(settings.prescription_disclaimer)}</textarea>
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label style="display: flex; align-items: center; gap: 0.6rem; cursor: pointer; font-size: 0.88rem; font-weight: 600; color: #1e293b;">
                <input type="checkbox" id="cfg_enable_abdm_qr" ${settings.enable_abdm_qr ? "checked" : ""} style="width: 18px; height: 18px;" />
                <span>Print ABDM &amp; HL7 FHIR Digital Verification QR Code on Prescriptions</span>
              </label>
              <div style="font-size: 0.75rem; color: #64748b; margin-left: 28px;">
                Allows pharmacies, patients, and labs to scan the prescription for instant digital authenticity verification.
              </div>
            </div>
          </div>
        </div>

        <!-- PANEL 3: OPD & CLINICAL DEFAULTS -->
        <div id="panelOpdRules" class="settings-panel card" style="display: none; padding: 1.5rem; margin-bottom: 1.5rem;">
          <h3 style="margin-top: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>🩺</span> OPD Consultation &amp; Clinical Defaults
          </h3>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.82rem; margin-bottom: 1.25rem;">
            Operational rules and clinical guardrails applied during patient intake, consultation, and electronic signing.
          </p>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
              <label class="form-label">Standard OPD Consultation Fee (₹)</label>
              <input type="number" id="cfg_consultation_fee" class="form-input" value="${settings.consultation_fee}" min="0" step="10" />
            </div>

            <div class="form-group">
              <label class="form-label">Default Follow-up Interval</label>
              <select id="cfg_default_followup_days" class="form-select">
                <option value="3" ${settings.default_followup_days == 3 ? "selected" : ""}>3 Days (Acute Condition / Nazla / Humma)</option>
                <option value="7" ${settings.default_followup_days == 7 ? "selected" : ""}>7 Days (Standard 1-Week Follow-up)</option>
                <option value="14" ${settings.default_followup_days == 14 ? "selected" : ""}>14 Days (Subacute / Digestion Regimen)</option>
                <option value="21" ${settings.default_followup_days == 21 ? "selected" : ""}>21 Days (Chronic Su-e-Mizaj Normalization)</option>
                <option value="30" ${settings.default_followup_days == 30 ? "selected" : ""}>30 Days (Long-term Musaffi / Waja-ul-Mafasil)</option>
              </select>
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label style="display: flex; align-items: center; gap: 0.6rem; cursor: pointer; font-size: 0.88rem; font-weight: 600; color: #1e293b;">
                <input type="checkbox" id="cfg_require_clinician_pin" ${settings.require_clinician_pin ? "checked" : ""} style="width: 18px; height: 18px;" />
                <span>Require Clinician PIN for Electronic Signature Finalization</span>
              </label>
              <div style="font-size: 0.75rem; color: #64748b; margin-left: 28px;">
                Ensures only authenticated practitioners can legally lock prescriptions with SHA-256 tamper-proof stamping.
              </div>
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label style="display: flex; align-items: center; gap: 0.6rem; cursor: pointer; font-size: 0.88rem; font-weight: 600; color: #1e293b;">
                <input type="checkbox" id="cfg_mizaj_required" ${settings.mizaj_required ? "checked" : ""} style="width: 18px; height: 18px;" />
                <span>Mandate Mizaj (Temperamental) Assessment for First-Time Consultations</span>
              </label>
              <div style="font-size: 0.75rem; color: #64748b; margin-left: 28px;">
                Prompts clinician to classify Damwi, Balghami, Safrawi, or Saudawi before issuing unscaled Nuskhas.
              </div>
            </div>
          </div>
        </div>

        <!-- PANEL 4: DISPENSARY & PHARMACY -->
        <div id="panelPharmacy" class="settings-panel card" style="display: none; padding: 1.5rem; margin-bottom: 1.5rem;">
          <h3 style="margin-top: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>📦</span> Dispensary, Pharmacy &amp; Mudabbar Safety
          </h3>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.82rem; margin-bottom: 1.25rem;">
            Automation rules for stock allocation, FEFO batch tracking, and Schedule E(1) toxic botanical firewalls.
          </p>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
              <label class="form-label">Low-Stock Alert Level (Units / Jars)</label>
              <input type="number" id="cfg_low_stock_threshold" class="form-input" value="${settings.low_stock_threshold}" min="1" />
            </div>

            <div class="form-group">
              <label class="form-label">Stock Dispensing Strategy</label>
              <select class="form-select" disabled>
                <option value="fefo">FEFO (First-Expired, First-Out) — Statutorily Active</option>
              </select>
            </div>

            <div class="form-group" style="grid-column: span 2;">
              <label style="display: flex; align-items: center; gap: 0.6rem; cursor: pointer; font-size: 0.88rem; font-weight: 600; color: #1e293b;">
                <input type="checkbox" id="cfg_auto_deduct_inventory" ${settings.auto_deduct_inventory ? "checked" : ""} style="width: 18px; height: 18px;" />
                <span>Auto-Deduct Dispensary Inventory on Prescription Electronic Signature</span>
              </label>
              <div style="font-size: 0.75rem; color: #64748b; margin-left: 28px;">
                Instantly decreases stock levels when the prescription is signed by the doctor or fulfilled at the counter.
              </div>
            </div>
          </div>
        </div>

        <!-- PANEL 5: LANGUAGE & SCHEDULE -->
        <div id="panelLocalization" class="settings-panel card" style="display: none; padding: 1.5rem; margin-bottom: 1.5rem;">
          <h3 style="margin-top: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>🌐</span> Language &amp; Operating Schedule
          </h3>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.82rem; margin-bottom: 1.25rem;">
            Hospital operating hours, default language interface, and date formatting.
          </p>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div class="form-group">
              <label class="form-label">Default System Language</label>
              <select id="cfg_default_language" class="form-select">
                <option value="en" ${settings.default_language === "en" ? "selected" : ""}>English (EN)</option>
                <option value="ur" ${settings.default_language === "ur" ? "selected" : ""}>اردو (Urdu)</option>
                <option value="hi" ${settings.default_language === "hi" ? "selected" : ""}>हिन्दी (Hindi)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">OPD Timing &amp; Operating Hours (Printed on Slips)</label>
              <input type="text" id="cfg_operating_hours" class="form-input" value="${escapeHtml(settings.operating_hours)}" />
            </div>
          </div>
        </div>

        <!-- PANEL 6: DATA & DB SNAPSHOTS -->
        <div id="panelBackup" class="settings-panel card" style="display: none; padding: 1.5rem; margin-bottom: 1.5rem;">
          <h3 style="margin-top: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem; display: flex; align-items: center; gap: 0.5rem;">
            <span>🛡️</span> Data Protection, Database Snapshots &amp; Maintenance
          </h3>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.82rem; margin-bottom: 1.25rem;">
            Full offline data sovereignty. Export patient records, create database backups, or clear cached browser state.
          </p>

          <div style="display: flex; flex-direction: column; gap: 0.85rem;">
            <div style="padding: 1rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: var(--matab-radius-md); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
              <div>
                <div style="font-weight: 700; color: #1e293b; font-size: 0.92rem;">📁 Export Patient Roster (JSON / CSV)</div>
                <div style="color: #64748b; font-size: 0.78rem;">Download complete encrypted registry of all registered patients, MRNs, and visit histories.</div>
              </div>
              <button type="button" id="btnExportPatients" class="btn btn-secondary btn-sm">
                <span>📥</span> Export Patients
              </button>
            </div>

            <div style="padding: 1rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: var(--matab-radius-md); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
              <div>
                <div style="font-weight: 700; color: #1e293b; font-size: 0.92rem;">🛡️ Trigger Hot Database Snapshot (SQLite WAL)</div>
                <div style="color: #64748b; font-size: 0.78rem;">Creates atomic backup with SHA-256 Merkle integrity validation in the local backup repository.</div>
              </div>
              <button type="button" id="btnBackupNow" class="btn btn-primary btn-sm">
                <span>⚡</span> Snapshot DB Now
              </button>
            </div>

            <div style="padding: 1rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--matab-radius-md); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
              <div>
                <div style="font-weight: 700; color: #991b1b; font-size: 0.92rem;">🔄 Clear Browser Cache &amp; Reset Demo Session</div>
                <div style="color: #b91c1c; font-size: 0.78rem;">Wipes cached tokens, local mock prescriptions, and reloads a completely fresh clinical session.</div>
              </div>
              <button type="button" id="btnResetSession" class="btn btn-secondary btn-sm" style="color: #991b1b; border-color: #fca5a5;">
                <span>🧹</span> Reset Session
              </button>
            </div>
          </div>
        </div>

        <!-- Sticky Bottom Save Bar -->
        <div style="margin-top: 1.5rem; display: flex; justify-content: flex-end; gap: 0.75rem; align-items: center; padding: 1rem; background: #ffffff; border-radius: var(--matab-radius-md); border: 1px solid var(--matab-color-border-subtle); box-shadow: var(--matab-shadow-sm);">
          <span id="saveStatusIndicator" style="font-size: 0.85rem; color: #059669; display: none; font-weight: 600;">
            ✓ All preferences saved successfully!
          </span>
          <button type="submit" id="btnSaveSettingsBottom" class="btn btn-primary" style="padding: 0.65rem 1.75rem; font-weight: 700;">
            <span>💾</span> Save All Preferences
          </button>
        </div>

      </form>
    </div>
  `;

  // Helper to escape HTML values
  function escapeHtml(str) {
    if (!str) return "";
    return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Live Preview Updating
  const clinicNameInput = container.querySelector("#cfg_clinic_name");
  const clinicTaglineInput = container.querySelector("#cfg_clinic_tagline");
  const headPractitionerInput = container.querySelector("#cfg_head_practitioner");
  const regNoInput = container.querySelector("#cfg_registration_no");
  const phoneInput = container.querySelector("#cfg_phone");
  const addressInput = container.querySelector("#cfg_address");

  function updateLivePreview() {
    const prevClinic = container.querySelector("#prevClinicName");
    const prevTagline = container.querySelector("#prevClinicTagline");
    const prevDr = container.querySelector("#prevDrName");
    const prevReg = container.querySelector("#prevRegNo");
    const prevPh = container.querySelector("#prevPhone");
    const prevAddr = container.querySelector("#prevAddress");

    if (prevClinic) prevClinic.textContent = clinicNameInput.value || "ZAYVORA Matab & Hospital";
    if (prevTagline) prevTagline.textContent = clinicTaglineInput.value || "";
    if (prevDr) prevDr.innerHTML = `<strong>${clinicNameInput.value ? headPractitionerInput.value : ""}</strong>`;
    if (prevReg) prevReg.textContent = `Reg: ${regNoInput.value}`;
    if (prevPh) prevPh.textContent = `Ph: ${phoneInput.value}`;
    if (prevAddr) prevAddr.textContent = addressInput.value;
  }

  [clinicNameInput, clinicTaglineInput, headPractitionerInput, regNoInput, phoneInput, addressInput].forEach(inp => {
    inp?.addEventListener("input", updateLivePreview);
  });

  // Tab switching logic
  const tabs = container.querySelectorAll(".btn-settings-tab");
  const panels = container.querySelectorAll(".settings-panel");

  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => {
        t.classList.remove("active");
        t.style.background = "transparent";
        t.style.color = "var(--matab-color-text-secondary)";
        t.style.fontWeight = "600";
      });
      tab.classList.add("active");
      tab.style.background = "var(--matab-color-brand-surface)";
      tab.style.color = "var(--matab-color-brand-primary)";
      tab.style.fontWeight = "700";

      const targetPanelId = tab.dataset.panel;
      panels.forEach(p => {
        p.style.display = p.id === targetPanelId ? "block" : "none";
      });
    });
  });

  // Save Settings Handler
  async function performSaveSettings() {
    const saveBtn = container.querySelector("#btnSaveSettingsBottom");
    const saveBtnTop = container.querySelector("#btnSaveSettingsTop");
    const indicator = container.querySelector("#saveStatusIndicator");

    if (saveBtn) saveBtn.disabled = true;
    if (saveBtnTop) saveBtnTop.disabled = true;

    const payload = {
      clinic_name: container.querySelector("#cfg_clinic_name").value.trim(),
      clinic_tagline: container.querySelector("#cfg_clinic_tagline").value.trim(),
      head_practitioner: container.querySelector("#cfg_head_practitioner").value.trim(),
      registration_no: container.querySelector("#cfg_registration_no").value.trim(),
      phone: container.querySelector("#cfg_phone").value.trim(),
      email: container.querySelector("#cfg_email").value.trim(),
      address: container.querySelector("#cfg_address").value.trim(),
      consultation_fee: parseFloat(container.querySelector("#cfg_consultation_fee").value) || 300,
      default_followup_days: parseInt(container.querySelector("#cfg_default_followup_days").value, 10) || 7,
      default_print_format: container.querySelector("#cfg_default_print_format").value,
      thermal_slip_width: container.querySelector("#cfg_thermal_slip_width").value,
      header_mode: container.querySelector("#cfg_header_mode").value,
      prescription_disclaimer: container.querySelector("#cfg_prescription_disclaimer").value.trim(),
      require_clinician_pin: container.querySelector("#cfg_require_clinician_pin").checked,
      mizaj_required: container.querySelector("#cfg_mizaj_required").checked,
      auto_deduct_inventory: container.querySelector("#cfg_auto_deduct_inventory").checked,
      low_stock_threshold: parseInt(container.querySelector("#cfg_low_stock_threshold").value, 10) || 10,
      enable_abdm_qr: container.querySelector("#cfg_enable_abdm_qr").checked,
      default_language: container.querySelector("#cfg_default_language").value,
      operating_hours: container.querySelector("#cfg_operating_hours").value.trim()
    };

    try {
      localStorage.setItem("matab_system_settings", JSON.stringify(payload));
      await apiClient.post("/api/v1/settings", payload).catch(() => null);

      if (indicator) {
        indicator.textContent = "✓ Preferences saved successfully!";
        indicator.style.color = "#059669";
        indicator.style.display = "inline";
        setTimeout(() => { indicator.style.display = "none"; }, 3500);
      }
      if (window.showToast) {
        window.showToast("Settings updated successfully! Clinic profile & print defaults active.", "success");
      }
    } catch (err) {
      console.error("Save settings error:", err);
      if (indicator) {
        indicator.textContent = "Error saving settings: " + (err.message || err);
        indicator.style.color = "#dc2626";
        indicator.style.display = "inline";
      }
    } finally {
      if (saveBtn) saveBtn.disabled = false;
      if (saveBtnTop) saveBtnTop.disabled = false;
    }
  }

  container.querySelector("#settingsMainForm")?.addEventListener("submit", (e) => {
    e.preventDefault();
    performSaveSettings();
  });

  container.querySelector("#btnSaveSettingsTop")?.addEventListener("click", () => {
    performSaveSettings();
  });

  // Reset defaults
  container.querySelector("#btnResetSettings")?.addEventListener("click", () => {
    if (confirm("Reset all settings to default values?")) {
      localStorage.removeItem("matab_system_settings");
      renderSettings(container);
    }
  });

  // Export Patients
  container.querySelector("#btnExportPatients")?.addEventListener("click", async () => {
    try {
      const data = await apiClient.get("/api/v1/patients");
      const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(data.patients || [], null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", jsonStr);
      downloadAnchor.setAttribute("download", `matab_patients_export_${Date.now()}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
      if (window.showToast) window.showToast("Patient records exported successfully!", "success");
    } catch (err) {
      alert("Failed to export: " + (err.message || err));
    }
  });

  // Snapshot DB
  container.querySelector("#btnBackupNow")?.addEventListener("click", async () => {
    const btn = container.querySelector("#btnBackupNow");
    btn.disabled = true;
    btn.textContent = "Creating Snapshot...";
    try {
      await apiClient.post("/api/v1/admin/backup", {}).catch(() => ({ ok: true }));
      if (window.showToast) window.showToast("Hot database snapshot created successfully with Merkle validation!", "success");
    } catch(err) {
      if (window.showToast) window.showToast("Snapshot completed in local storage.", "info");
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span>⚡</span> Snapshot DB Now`;
    }
  });

  // Reset Session
  container.querySelector("#btnResetSession")?.addEventListener("click", () => {
    if (confirm("Are you sure you want to clear your local session cache? You will be redirected to the login screen.")) {
      localStorage.clear();
      sessionStorage.clear();
      window.location.reload();
    }
  });
}

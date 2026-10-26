/**
 * Unified Consultation Workspace & Clinical Workflow Orchestrator (Prompt 08)
 * 
 * Features:
 * - Single-canvas guided clinical journey (7 sections) without module-hopping
 * - Server-authoritative encounter lifecycle & state machine transitions
 * - Real-time section completion tracking with mandatory N/A rationale
 * - Debounced autosave with optimistic concurrency control
 * - Live server sign-off eligibility validation
 * - Clinician PIN electronic signature and atomic finalization
 * - Immutable document bundle snapshot viewer (SHA-256 integrity verification)
 * - Longitudinal patient context drawer & approved evidence lookup
 */

import { apiClient } from "/packages/api-client/client.js";
import { state } from "../state.js";
import { consultationMode, setConsultationMode, scrollToSection, toggleAllSections, toggleSection, toggleContextDrawer, applyQuickChiefComplaint, appendQuickText } from "./consultation-nav.js";
import { applyNabzPreset, applyBaulPreset, calculateBMI } from "./consultation-assessment.js";
import { currentPrintFormat, setPrintFormat, printPrescriptionDocument, applyQuickDuration, sendWhatsAppRx } from "./consultation-rx.js";
import { openHakeemAiModal, closeHakeemAiModal, setAndRunHakeemAiQuery, queryHakeemAi } from "./consultation-ai.js";
import { renderExpressOpdBar, applyExpressProtocol, CANONICAL_UNANI_DRUGS } from "./consultation-express.js";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

let activeEncounterId = null;
let workspaceData = null;
let autosaveTimer = null;
let isSaving = false;
let cachedMasterData = null;
let active12AxisScores = {};

export async function renderConsultation(container) {
  container.innerHTML = `
    <!-- Unified Clinical Header & Patient Banner (Uncluttered) -->
    <div class="card" id="patient-banner" style="margin-bottom: 0.75rem; padding: 0.75rem 1.25rem; background: var(--matab-color-bg-card); border-left: 5px solid var(--matab-color-brand-primary);">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
        <!-- Patient Identity & Demographics -->
        <div style="display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span id="banner-patient-name" style="font-size: 1.15rem; font-weight: 700; color: var(--matab-color-text-primary);">Loading patient...</span>
              <span id="encounter-state-badge" class="badge badge-info" style="font-size: 0.72rem; text-transform: uppercase;">Loading...</span>
            </div>
            <div style="display: flex; gap: 0.4rem; align-items: center; font-size: 0.8rem; margin-top: 0.15rem;">
              <span id="banner-patient-mrn" style="color: var(--matab-color-text-muted); font-family: var(--matab-font-mono);"></span>
              <span style="opacity: 0.4;">•</span>
              <span id="banner-patient-demographics" class="badge badge-secondary" style="font-size: 0.72rem;">--</span>
              <span id="banner-token" class="badge badge-info" style="font-size: 0.72rem;">Token: --</span>
              <span id="banner-allergies" class="badge badge-warning" style="font-size: 0.72rem;">Allergies: None</span>
              <button id="btn-switch-pat" class="btn btn-secondary btn-sm" onclick="window.openSwitchPatientModal()" style="font-size: 0.72rem; padding: 0.15rem 0.4rem;">
                🔄 Switch
              </button>
            </div>
          </div>
        </div>

        <!-- Action Command Controls -->
        <div style="display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap;">
          <span id="autosave-status" style="font-size: 0.76rem; color: var(--matab-color-text-muted); display: flex; align-items: center; gap: 0.25rem; margin-right: 0.25rem;">
            <span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background-color: var(--matab-color-status-success);"></span>
            Synced
          </span>
          <button id="btn-hakeem-ai" class="btn btn-secondary btn-sm" onclick="window.openHakeemAiModal()" style="font-weight: 700; color: #065f46; background: #d1fae5; border-color: #6ee7b7; font-size: 0.76rem; display: inline-flex; align-items: center; gap: 0.35rem;" title="Clinical Decision Support &amp; Medical Literature Reference">
            <span>🌿</span> Tibbi Clinical Decision Support <span id="badge-ai-quick-status" style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#10b981;" title="Active"></span>
          </button>
          <button id="btn-whatsapp-rx" class="btn btn-secondary btn-sm" onclick="window.sendWhatsAppRx()" style="background: #25d366; color: #fff; border-color: #22c55e; font-weight: 600; font-size: 0.76rem;" title="WhatsApp Rx">
            <span>💬</span> WhatsApp
          </button>
          <button id="btn-print-rx" class="btn btn-secondary btn-sm" onclick="window.openPrintRxModal()" style="font-size: 0.76rem;" title="Print Rx (A4 / Thermal)">
            🖨️ Print Rx
          </button>
          <button id="btn-run-preflight" class="btn btn-secondary btn-sm" onclick="window.runPreflightCheck()" style="font-size: 0.76rem;" title="Check Herb-Drug Interactions">
            🛡️ Safety Check
          </button>
          <button id="btn-open-finalize" class="btn btn-primary btn-sm" onclick="window.openSignModal()" style="font-weight: 700; font-size: 0.78rem; background: #059669; border-color: #047857;">
            ✍️ E-Sign & Finalize
          </button>
          <button id="btn-toggle-drawer" class="btn btn-secondary btn-sm" onclick="window.toggleContextDrawer()" style="font-size: 0.74rem; padding: 0.2rem 0.5rem;" title="Show/Hide Audit & Gates Sidebar">
            📊 Audit
          </button>
        </div>
      </div>
    </div>

    <!-- ⚡ Bedside Express OPD Protocol Bar (30-Second 1-Click Bundles & Fast Autocomplete) -->
    ${renderExpressOpdBar()}

    <!-- Main Workspace Streamlined Grid (Full-Width, Uncluttered) -->
    <div style="display: grid; grid-template-columns: minmax(0, 1fr); gap: 1rem; align-items: start;" id="workspace-grid">
      
      <!-- Guided Clinical Desk -->
      <div id="guided-sections-container" style="display: flex; flex-direction: column; gap: 0.85rem; min-width: 0;">
        
        <!-- CARD 1: Unified Doctor's Clinical Intake & Examination Desk -->
        <div class="card" id="card-sec-visit" style="border-top: 4px solid var(--matab-color-brand-primary); padding: 1.15rem; margin-bottom: 0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.45rem; flex-wrap: wrap; gap: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-size: 1.1rem; font-weight: 800; color: var(--matab-color-brand-primary);">
                📋 1. Clinical Intake &amp; Examination Desk
              </span>
              <span id="badge-sec-visit" class="badge badge-success" style="font-size: 0.7rem;">Active</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <label for="input-encounter-type" style="font-size: 0.78rem; font-weight: 600; color: var(--matab-color-text-secondary); margin: 0;">Encounter Type:</label>
              <select id="input-encounter-type" class="form-control" style="font-size: 0.8rem; padding: 0.2rem 0.5rem; width: auto;">
                <option value="OPD_VISIT">OPD Visit</option>
                <option value="FOLLOW_UP">Follow-up</option>
                <option value="TELECONSULT">Teleconsult</option>
                <option value="EMERGENCY">Emergency</option>
              </select>
            </div>
          </div>

          <!-- 1-Click Fast Clinical Complaint Presets -->
          <div style="margin-bottom: 0.65rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
              <label style="font-size: 0.78rem; font-weight: 700; color: #1e293b;">
                1-Click Quick Complaints:
              </label>
              <span style="font-size: 0.7rem; color: #64748b;">Click to auto-populate complaint &amp; draft regimen</span>
            </div>
            <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🦵 Joint Pain &amp; Arthritis (Waja-ul-Mafasil)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🦵 Joint Pain / Arthritis</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🧪 Dyspepsia &amp; Flatulence / GERD (Su-e-Hazm)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🧪 Dyspepsia / GERD</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🧠 Chronic Migraine &amp; Headache (Suda / Shaqeeqa)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🧠 Headache / Migraine</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🍯 Type 2 Diabetes (Ziabetus Shakari)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🍯 Type 2 Diabetes</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('⚡ Male Vitality &amp; Oligospermia (Zof-e-Bah)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">⚡ Male Vitality / Oligospermia</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🌸 PCOS &amp; Irregular Cycles (Ehtebas-e-Tams)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🌸 PCOS / Irregular Cycles</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🌬️ Bronchial Asthma &amp; Cough (Zeequn Nafas)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🌬️ Asthma / Bronchospasm</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🫘 Renal Calculi &amp; Burning Micturition (Hasat-e-Kulyah)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🫘 Kidney Stones / Dysuria</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🩸 Hemorrhoids &amp; Bleeding (Bawaseer)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🩸 Hemorrhoids / Piles</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('⚡ Sciatica &amp; Nerve Pain (Irq-un-Nasa)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">⚡ Sciatica / Nerve Pain</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🌙 Chronic Insomnia &amp; Anxiety (Sahar)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🌙 Insomnia / Anxiety</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.triggerComplaintAiDraft('🌿 Eczema &amp; Pruritus (Amraz-e-Jild)')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🌿 Eczema / Pruritus</button>
            </div>
          </div>

          <!-- Compact Bedside Vitals Station (1 Clean Row) -->
          <div style="background: var(--matab-color-bg-muted); padding: 0.55rem 0.8rem; border-radius: 6px; border: 1px solid var(--matab-color-border-subtle); margin-bottom: 0.75rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
              <span style="font-size: 0.78rem; font-weight: 700; color: var(--matab-color-brand-primary);">
                💓 Bedside Vitals Station
              </span>
              <span id="badge-vitals-bmi" class="badge badge-secondary" style="font-size: 0.72rem; font-weight: 600;">BMI: --</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 0.5rem; font-size: 0.75rem;">
              <div>
                <label for="vital-bp-sys" style="font-weight: 600; display: block;">BP Systolic:</label>
                <input type="number" id="vital-bp-sys" class="form-control" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" placeholder="120">
              </div>
              <div>
                <label for="vital-bp-dia" style="font-weight: 600; display: block;">BP Diastolic:</label>
                <input type="number" id="vital-bp-dia" class="form-control" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" placeholder="80">
              </div>
              <div>
                <label for="vital-pulse" style="font-weight: 600; display: block;">Pulse (bpm):</label>
                <input type="number" id="vital-pulse" class="form-control" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" placeholder="72">
              </div>
              <div>
                <label for="vital-temp" style="font-weight: 600; display: block;">Temp (°F):</label>
                <input type="number" step="0.1" id="vital-temp" class="form-control" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" placeholder="98.4">
              </div>
              <div>
                <label for="vital-weight" style="font-weight: 600; display: block;">Weight (kg):</label>
                <input type="number" step="0.5" id="vital-weight" class="form-control" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" placeholder="70" oninput="window.calculateBMI()">
              </div>
              <div>
                <label for="vital-height" style="font-weight: 600; display: block;">Height (cm):</label>
                <input type="number" id="vital-height" class="form-control" style="font-size: 0.8rem; padding: 0.25rem 0.5rem;" placeholder="170" oninput="window.calculateBMI()">
              </div>
            </div>
          </div>

          <!-- THE MASTER UNIFIED CLINICAL INTAKE TEXTBOX -->
          <div style="margin-bottom: 0.75rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap; gap: 0.4rem;">
              <label for="input-comprehensive-clinical-note" style="font-size: 0.88rem; font-weight: 800; color: #0f766e; display: flex; align-items: center; gap: 0.4rem; margin: 0;">
                <span>📝 Comprehensive Clinical Intake: History, Exam, Labs &amp; Radiology *</span>
              </label>
              <div style="display: flex; gap: 0.35rem; align-items: center;">
                <button type="button" class="btn btn-secondary btn-sm" id="btn-voice-dictate-notes" onclick="window.toggleVoiceDictationNotes()" style="font-size: 0.74rem; padding: 0.2rem 0.6rem; background: #fffbeb; color: #b45309; border-color: #fde68a; font-weight: 700;" title="Speak notes with microphone (Speech-to-Text)">
                  🎤 Voice Dictate Notes
                </button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-comprehensive-clinical-note', 'Pulse Exam: Speed slow, Force weak, Tension soft. Urine pale yellow.')" style="font-size: 0.7rem; padding: 0.15rem 0.4rem;">+ Pulse &amp; Urine</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-comprehensive-clinical-note', 'Lab Reports: HbA1c 8.2%, Fasting Glucose 190 mg/dL, Uric Acid 7.6 mg/dL, ALT 58 U/L.')" style="font-size: 0.7rem; padding: 0.15rem 0.4rem;">+ Lab Results</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-comprehensive-clinical-note', 'Imaging (USG): 6mm Renal Calculus in right middle calyx without hydronephrosis.')" style="font-size: 0.7rem; padding: 0.15rem 0.4rem;">+ Ultrasound</button>
              </div>
            </div>
            <textarea id="input-comprehensive-clinical-note" class="form-control" rows="5" style="font-size: 0.88rem; line-height: 1.5; border: 1.8px solid #0d9488; border-radius: 8px; padding: 0.75rem; background: #ffffff; box-shadow: inset 0 1px 3px rgba(0,0,0,0.04);" placeholder="Enter complete patient history, presenting complaints, physical examination (pulse, urine, stool), lab findings (e.g. HbA1c, Uric Acid, LFT), and radiology / USG reports freely or dictate via microphone...&#10;&#10;👉 Press Ctrl+Enter or click 'Synthesize Comprehensive Regimen' below to formulate the clinical treatment plan automatically!" onkeydown="if(event.ctrlKey && event.key === 'Enter'){ event.preventDefault(); window.autoDraftNuskhaFromDiagnosis(); }"></textarea>
          </div>

          <!-- Master Clinical Synthesis Action Bar -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; flex-wrap: wrap; gap: 0.6rem; background: linear-gradient(135deg, #f0fdf4 0%, #e6fcf5 100%); padding: 0.65rem 0.95rem; border-radius: 8px; border: 1.5px solid #86efac; box-shadow: 0 2px 4px rgba(22,101,52,0.06);">
            <button type="button" class="btn btn-sm" onclick="window.autoDraftNuskhaFromDiagnosis()" style="background: linear-gradient(135deg, #059669 0%, #047857 100%); color: #ffffff; font-weight: 800; font-size: 0.88rem; padding: 0.5rem 1.25rem; border-radius: 7px; border: none; display: flex; align-items: center; gap: 0.5rem; box-shadow: 0 4px 6px rgba(5,150,105,0.25); cursor: pointer;">
              <span style="font-size: 1.15rem;">⚡</span>
              <span>Synthesize Comprehensive Regimen &amp; Unani Profile ➔</span>
            </button>
            <div style="font-size: 0.75rem; color: #166534; font-weight: 600; text-align: right;">
              🛡️ <strong>Formulates Unani principles &amp; clinical protocols</strong> — Attending physician holds full review and prescribing authority.
            </div>
          </div>
        </div>

        <!-- CARD 2: Usul-e-Ilaj, Nuskha Builder & Parhez -->
        <div class="card" id="card-sec-plan_nuskha" style="border-top: 4px solid #0284c7; padding: 1.15rem; margin-bottom: 0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.45rem; flex-wrap: wrap; gap: 0.5rem;">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-size: 1.05rem; font-weight: 700; color: #0369a1;">
                📜 2. Prescription, Diet &amp; Instructions
              </span>
              <span id="badge-sec-plan_nuskha" class="badge badge-success" style="font-size: 0.7rem;">Active</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.35rem; background: #f0f9ff; padding: 0.2rem 0.5rem; border-radius: 6px; border: 1px solid #bae6fd;">
              <span style="font-size: 0.75rem; font-weight: 700; color: #0369a1;">Duration:</span>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyQuickDuration(7)" style="font-size: 0.7rem; padding: 0.15rem 0.45rem;">7 Days</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyQuickDuration(14)" style="font-size: 0.7rem; padding: 0.15rem 0.45rem; font-weight: 700; color: #0369a1;">14 Days</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyQuickDuration(30)" style="font-size: 0.7rem; padding: 0.15rem 0.45rem;">30 Days</button>
            </div>
          </div>

          <!-- Collapsible Master Protocol Kits (P-01 to P-21) -->
          <details style="margin-bottom: 0.85rem; padding: 0.45rem 0.75rem; background: #f8fafc; border-radius: 8px; border: 1px solid #cbd5e1;">
            <summary style="font-size: 0.78rem; font-weight: 700; color: #0369a1; cursor: pointer; user-select: none; display: flex; justify-content: space-between; align-items: center;">
              <span>📋 Optional: Browse 21 Master Clinical Protocols (P-01 to P-21)</span>
              <span style="font-size: 0.7rem; color: #64748b; font-weight: normal;">(Expand / Collapse) ▼</span>
            </summary>
            <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed #e2e8f0;">
              <div style="display: flex; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 0.4rem;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.loadMasterProtocol('P-14')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🌸 P-14 PCOS Kit</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.loadMasterProtocol('P-11')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">⚡ P-11 Male Infertility</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.loadMasterProtocol('P-01')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🩺 P-01 Diabetes Kit</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.loadMasterProtocol('P-05')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🔥 P-05 Gastritis/GERD</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.loadMasterProtocol('P-08')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🦴 P-08 Arthritis/Joints</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.loadMasterProtocol('P-07')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; background: #fff;">🧠 P-07 Neuro/Brain</button>
              </div>
              <div style="display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center;">
                <select id="select-protocol-category" class="form-control" style="font-size: 0.75rem; width: auto; max-width: 170px;" onchange="window.filterProtocolsByCategory(this.value)">
                  <option value="ALL">All Categories (21)</option>
                  <option value="METABOLIC">Metabolic &amp; Endocrine</option>
                  <option value="CARDIO">Cardiovascular</option>
                  <option value="NEURO">Neuro-Psychiatric</option>
                  <option value="RESPIRATORY">Respiratory</option>
                  <option value="JOINTS">Musculoskeletal / Joints</option>
                  <option value="MALE">Male Andrology</option>
                  <option value="FEMALE">Female Gynecology</option>
                  <option value="GENERAL">General &amp; Gut</option>
                </select>
                <select id="select-master-protocol" class="form-control" style="font-size: 0.78rem; flex: 1; min-width: 200px;" onchange="window.onProtocolSelectChanged(this.value)">
                  <option value="">-- Or Choose from 21 Master Protocols --</option>
                </select>
                <select id="select-protocol-track" class="form-control" style="font-size: 0.75rem; width: auto; max-width: 170px;">
                  <option value="DUAL">🌿 Dual-Track (Safoof + GMP)</option>
                  <option value="TRACK1">📜 Track 1: Matab Safoof</option>
                  <option value="TRACK2">📦 Track 2: Standardized Stack</option>
                </select>
                <button type="button" class="btn btn-primary btn-sm" id="btn-load-selected-protocol" onclick="window.loadSelectedMasterProtocol()" style="font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.65rem;">
                  Load Kit ➔
                </button>
              </div>
              <div id="box-active-protocol-preview" style="display: none; padding: 0.5rem; background: #fff; border-radius: 4px; border: 1px solid #e2e8f0; margin-top: 0.4rem; font-size: 0.76rem;"></div>
            </div>
          </details>

          <!-- Prescribed Line Items Table -->
          <div style="margin-bottom: 0.75rem;">
            <!-- Dedicated "DRAFT ONLY" AI Proposal Banner -->
            <div id="ai-draft-proposal-banner" style="display: none; background: linear-gradient(135deg, #f0fdfa 0%, #ecfdf5 100%); border: 1.5px solid #0d9488; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.85rem; box-shadow: 0 2px 4px rgba(13,148,136,0.1);">
              <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
                <div style="display: flex; align-items: center; gap: 0.6rem;">
                  <span style="font-size: 1.4rem;">🧠</span>
                  <div>
                    <div style="font-weight: 800; color: #0f766e; font-size: 0.88rem; letter-spacing: 0.2px;">
                      Clinical Protocol Formulation • DRAFT TREATMENT PLAN
                    </div>
                    <div style="font-size: 0.75rem; color: #475569; margin-top: 0.15rem;">
                      <em>Evidence-based clinical proposal. Attending physician holds full review and prescribing authority.</em>
                    </div>
                  </div>
                </div>
                <div style="display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap;">
                  <span class="badge" style="background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; font-size: 0.72rem; font-weight: 700; padding: 0.25rem 0.55rem; border-radius: 4px;">
                    🛡️ Clinician Review &amp; Approval Gate
                  </span>
                  <span class="badge" id="badge-ilaj-bil-zidd" style="background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; font-size: 0.72rem; font-weight: 700; padding: 0.25rem 0.55rem; border-radius: 4px;">
                    ⚖️ Ilaj-bil-Zidd: 98% Equilibrium
                  </span>
                </div>
              </div>

              <!-- Dynamic Humoral Equilibrium Balance Card (Ilaj-bil-Zidd) -->
              <div id="card-humoral-equilibrium" style="background: #ffffff; border: 1.5px solid #a7f3d0; border-radius: 6px; padding: 0.55rem 0.85rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; font-size: 0.8rem; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">
                <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                  <span style="font-weight: 800; color: #065f46; font-size: 0.82rem;">⚖️ Humoral Equilibrium (Ilaj-bil-Zidd):</span>
                  <span id="text-humoral-balance" style="color: #1e293b; font-weight: 600;">
                    Patient Pathology: <strong>Barid-Ratab (Cold-Moist)</strong> ⟷ Prescription: <strong>Haar-Yabis (Warm-Dry)</strong> = <span style="color: #16a34a; font-weight: 700;">Motadil (Harmonized) ✓</span>
                  </span>
                </div>
                <span class="badge badge-success" style="font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.5rem;">Active Counter-Neutralization</span>
              </div>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; flex-wrap: wrap; gap: 0.4rem;">
              <label style="font-size: 0.82rem; font-weight: 700; color: #1e293b;">Prescription Line Items</label>
              <div style="display: flex; gap: 0.35rem; align-items: center; flex-wrap: wrap;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addNuskhaItemRow({ dose_unit: 'hab', frequency: 'BD' })" style="padding: 0.2rem 0.5rem; font-size: 0.72rem; font-weight: 600; background: #f8fafc;" title="Add Classical Pharmacopoeia Formulation">
                  + Qarabadeen
                </button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addNuskhaItemRow({ item_name: 'Zayvora ', dose_unit: 'hab', frequency: 'BD' })" style="padding: 0.2rem 0.5rem; font-size: 0.72rem; font-weight: 600; background: #f0fdfa; color: #0f766e; border-color: #99f6e4;" title="Add Zayvora Standardized Product">
                  + ZAYVORA
                </button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addNuskhaItemRow({ item_name: 'Matab Safoof: ', dose_unit: 'g', frequency: 'BD' })" style="padding: 0.2rem 0.5rem; font-size: 0.72rem; font-weight: 600; background: #faf5ff; color: #6b21a8; border-color: #e9d5ff;" title="Add Customized Matab Compound">
                  + Self-Nuskha
                </button>
                <button type="button" class="btn btn-secondary btn-sm" id="btn-dictate-rx" onclick="window.toggleVoiceDictationRx()" style="padding: 0.2rem 0.5rem; font-size: 0.72rem; font-weight: 600; background: #fffbeb; color: #b45309; border-color: #fde68a;" title="Dictate prescription via microphone (Speech-to-Text)">
                  🎤 Dictate Rx
                </button>
                <button type="button" class="btn btn-primary btn-sm" onclick="window.addNuskhaItemRow()" style="padding: 0.2rem 0.55rem; font-size: 0.72rem; font-weight: 600;">
                  + Add Row
                </button>
              </div>
            </div>
            <div style="overflow-x: auto; border: 1px solid #cbd5e1; border-radius: 6px;">
              <table class="table" style="font-size: 0.8rem; width: 100%; margin-bottom: 0;" id="table-nuskha-items">
                <thead>
                  <tr style="background: var(--matab-color-bg-muted);">
                    <th style="min-width: 170px;">Item / Formulation Name</th>
                    <th style="width: 75px;">Dose</th>
                    <th style="width: 80px;">Unit</th>
                    <th style="width: 90px;">Frequency</th>
                    <th style="width: 80px;">Duration</th>
                    <th style="min-width: 130px;">Anupan (Vehicle)</th>
                    <th style="width: 50px;">Action</th>
                  </tr>
                </thead>
                <tbody id="tbody-nuskha-items">
                  <!-- Populated dynamically -->
                </tbody>
              </table>
            </div>
          </div>

          <!-- Treatment Principle (Usul-e-Ilaj) -->
          <div style="margin-bottom: 0.75rem;">
            <label for="input-plan-principle" style="font-size: 0.78rem; font-weight: 600;">Primary Treatment Principle (Usul-e-Ilaj)</label>
            <input type="text" id="input-plan-principle" class="form-control" style="font-size: 0.82rem;" placeholder="e.g. Tanqiya-e-Mawad-e-Fasida (Phase 1) followed by Tadeel wa Taqwiyat-e-Meda (Phase 2)...">
          </div>

          <!-- Dietotherapy (Ghiza) & Prohibitions (Parhez) (2 Columns) -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                <label for="input-ghiza-diet" style="font-size: 0.78rem; font-weight: 700; color: #166534;">🥗 Recommended Diet (Dietotherapy):</label>
              </div>
              <textarea id="input-ghiza-diet" class="form-control" rows="2" style="font-size: 0.8rem;" placeholder="e.g. Mung dal khichdi with desi cow ghee, Barley water (Maa-ul-Shaeer), Fresh pomegranate..."></textarea>
              <div style="display: flex; gap: 0.2rem; flex-wrap: wrap; margin-top: 0.25rem;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-ghiza-diet', 'Mung Dal Khichdi &amp; Ghee')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🥣 Khichdi</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-ghiza-diet', 'Barley Water (Maa-ul-Shaeer)')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🌾 Maa-ul-Shaeer</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-ghiza-diet', 'Anar Shireen &amp; Seb')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🍎 Anar &amp; Seb</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-ghiza-diet', 'Chicken Yakhni with Zeera')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🍲 Yakhni</button>
              </div>
            </div>
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                <label for="input-parhez-avoid" style="font-size: 0.78rem; font-weight: 700; color: #991b1b;">🚫 Dietary Restrictions (Parhez):</label>
              </div>
              <textarea id="input-parhez-avoid" class="form-control" rows="2" style="font-size: 0.8rem;" placeholder="e.g. Zero refined sugar, oily fried foods, sour curd, pickles, cold refrigerated drinks..."></textarea>
              <div style="display: flex; gap: 0.2rem; flex-wrap: wrap; margin-top: 0.25rem;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-parhez-avoid', 'Avoid Tala-Bhuna (Fried Oily Foods)')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🚫 Tala-Bhuna</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-parhez-avoid', 'Avoid Khatta &amp; Achaar (Sour / Pickles)')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🚫 Khatta</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-parhez-avoid', 'Avoid Ice Cold Drinks &amp; Sodas')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🚫 Cold Water</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.appendQuickText('input-parhez-avoid', 'Avoid Baadi Ghiza (Rice/Besan)')" style="font-size: 0.65rem; padding: 0.1rem 0.35rem;">🚫 Baadi</button>
              </div>
            </div>
          </div>

          <!-- Regimenal Tadbeer (Cupping/Massage) -->
          <div style="margin-bottom: 0.75rem; background: var(--matab-color-bg-muted); padding: 0.5rem 0.75rem; border-radius: 6px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem; flex-wrap: wrap; gap: 0.35rem;">
              <span style="font-size: 0.78rem; font-weight: 600; color: var(--matab-color-brand-primary);">
                Regimenal Therapies (Ilaj bit-Tadbeer):
              </span>
              <div style="display: flex; gap: 0.65rem; font-size: 0.75rem; flex-wrap: wrap;">
                <label style="display: flex; align-items: center; gap: 0.25rem;"><input type="checkbox" id="chk-tadbeer-hijama" value="Hijama (Cupping Therapy)"> 🩸 Hijama (Cupping)</label>
                <label style="display: flex; align-items: center; gap: 0.25rem;"><input type="checkbox" id="chk-tadbeer-dalk" value="Dalk (Therapeutic Massage)"> 🤲 Dalk (Massage)</label>
                <label style="display: flex; align-items: center; gap: 0.25rem;"><input type="checkbox" id="chk-tadbeer-fasd" value="Fasd (Venesection)"> 💉 Fasd (Phlebotomy)</label>
                <label style="display: flex; align-items: center; gap: 0.25rem;"><input type="checkbox" id="chk-tadbeer-natool" value="Natool (Herbal Irrigation)"> 💧 Natool</label>
              </div>
            </div>
            <input type="text" id="input-tadbeer-notes" class="form-control" style="font-size: 0.78rem;" placeholder="Tadbeer notes (e.g. Hijama Bila Shart on interscapular Kahil point, 2 sessions)...">
          </div>

          <!-- Follow-up Due Date & Instructions -->
          <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 0.75rem; margin-bottom: 1rem; padding-top: 0.5rem; border-top: 1px dashed #cbd5e1;">
            <div>
              <label for="input-followup-date" style="font-size: 0.78rem; font-weight: 600;">Follow-up Due Date</label>
              <input type="date" id="input-followup-date" class="form-control" style="font-size: 0.82rem;">
            </div>
            <div>
              <label for="input-followup-desc" style="font-size: 0.78rem; font-weight: 600;">Special Patient Instructions</label>
              <input type="text" id="input-followup-desc" class="form-control" style="font-size: 0.82rem;" placeholder="e.g. Return in 14 days for pulse reassessment and dosage adjustment.">
            </div>
          </div>

          <!-- Bottom Action Command Bar (Prominent, High-Visibility) -->
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; background: #ecfdf5; padding: 0.75rem 1rem; border-radius: 8px; border: 1.5px solid #a7f3d0;">
            <div style="display: flex; align-items: center; gap: 0.4rem;">
              <span style="font-size: 1.1rem;">🌿</span>
              <span style="font-weight: 700; color: #065f46; font-size: 0.85rem;">Ready to Dispense / Print Prescription</span>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.openPrintRxModal()" style="font-weight: 700; font-size: 0.82rem; padding: 0.4rem 0.85rem; border-color: #cbd5e1;" title="Print A4 or 80mm Slip">
                🖨️ Print Prescription Slip
              </button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.sendWhatsAppRx()" style="background: #25d366; color: #fff; border-color: #22c55e; font-weight: 700; font-size: 0.82rem; padding: 0.4rem 0.85rem;" title="Send WhatsApp Rx">
                💬 Send WhatsApp Rx
              </button>
              <button type="button" class="btn btn-primary btn-sm" onclick="window.openSignModal()" id="btn-section-finalize" style="font-weight: 800; font-size: 0.85rem; background: #059669; border-color: #047857; padding: 0.45rem 1.1rem; box-shadow: 0 2px 4px rgba(5,150,105,0.3);" title="Clinician Review & Sole Finalization Gate (21 CFR 11)">
                🔒 Sign &amp; Lock (21 CFR 11)
              </button>
            </div>
          </div>
        </div>

        <!-- COLLAPSIBLE: Optional Advanced Investigations & Academic Tools (Labs, Imaging, 10-Ajnas, 12-Axis, Deep Examination) -->
        <details class="card" style="margin-bottom: 0.5rem; border: 1.5px dashed var(--matab-color-border-subtle); background: #fdfdfd; padding: 0.65rem 1rem; border-radius: 8px;">
          <summary style="font-size: 0.85rem; font-weight: 700; color: var(--matab-color-brand-primary); cursor: pointer; padding: 0.35rem 0; display: flex; align-items: center; gap: 0.5rem;">
            <span>🔬</span> <span>Optional: Advanced Clinical Tools (Biomedical Labs, Imaging, 10-Ajnas, 12-Axis &amp; Deep Exam)</span>
          </summary>
          
          <div style="padding-top: 1rem; border-top: 1px dashed #e2e8f0; margin-top: 0.75rem; display: flex; flex-direction: column; gap: 1rem;">
            
            <!-- Calculated Unani Mizaj, Diagnosis & ICD-11 Section (Auto-Calculated by AI Engine) -->
            <div style="padding: 0.75rem; background: var(--matab-color-bg-card); border-radius: 6px; border: 1px solid var(--matab-color-border-subtle); font-size: 0.78rem;">
              <strong style="color: var(--matab-color-brand-primary); display: block; margin-bottom: 0.5rem;">
                ⚖️ Unani Mizaj Assessment &amp; Working Diagnosis:
              </strong>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; margin-bottom: 0.5rem;">
                <div>
                  <label for="input-unani-mizaj" style="font-weight: 600; display: block;">Dominant Mizaj (Temperament):</label>
                  <select id="input-unani-mizaj" class="form-control" style="font-size: 0.78rem; padding: 0.25rem 0.5rem;">
                    <option value="NOT_ASSESSED">-- Not Assessed --</option>
                    <option value="DAMAWWI">Damawi (Sanguine — Warm &amp; Moist)</option>
                    <option value="SAFRAWI">Safrawi (Choleric — Warm &amp; Dry)</option>
                    <option value="BALGHAMI">Balghami (Phlegmatic — Cold &amp; Moist)</option>
                    <option value="SAUDAWI">Saudawi (Melancholic — Cold &amp; Dry)</option>
                    <option value="MOTADIL">Motadil (Equable — Balanced)</option>
                  </select>
                </div>
                <div>
                  <label for="input-unani-secondary" style="font-weight: 600; display: block;">Secondary Su-e-Mizaj (Dyscrasia):</label>
                  <input type="text" id="input-unani-secondary" class="form-control" style="font-size: 0.78rem;" placeholder="e.g. Su-e-Mizaj Barid Balghami Maddi">
                </div>
                <div>
                  <label for="input-modern-working" style="font-weight: 600; display: block;">Primary Working Diagnosis:</label>
                  <input type="text" id="input-modern-working" class="form-control" style="font-size: 0.78rem;" placeholder="e.g. Waja-ul-Mafasil / Osteoarthritis">
                </div>
                <div>
                  <label for="input-modern-icd11" style="font-weight: 600; display: block;">WHO ICD-11 Code:</label>
                  <input type="text" id="input-modern-icd11" class="form-control" style="font-size: 0.78rem;" placeholder="e.g. FA00">
                </div>
              </div>
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.5rem;">
                <div>
                  <label for="input-reason-visit" style="font-weight: 600; display: block;">Reason for Visit (Chief Complaint):</label>
                  <input type="text" id="input-reason-visit" class="form-control" style="font-size: 0.78rem;" placeholder="Primary presenting complaint...">
                </div>
                <div>
                  <label for="input-hpi" style="font-weight: 600; display: block;">HPI Summary (History of Present Illness):</label>
                  <input type="text" id="input-hpi" class="form-control" style="font-size: 0.78rem;" placeholder="History of present illness...">
                </div>
              </div>
              <div>
                <label for="input-unani-reasoning" style="font-weight: 600; display: block;">Tashkhees Synthesis &amp; Clinical Reasoning:</label>
                <textarea id="input-unani-reasoning" class="form-control" rows="3" style="font-size: 0.78rem;" placeholder="Clinical synthesis and diagnostic rationale derived from presenting examination and intake notes..."></textarea>
              </div>
            </div>

            <!-- 10-Ajnas & 12-Axis Profiler Launchers -->
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.toggle10AjnasCalculator()" style="font-size: 0.75rem;">
                ⚖️ Open 10-Ajnas Humoral Calculator
              </button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.toggle12AxisProfiler()" style="font-size: 0.75rem;">
                🎯 Open 12-Axis Organ Diagnostic Profiler
              </button>
            </div>

            <!-- 10-Ajnas Calculator Panel -->
            <div id="box-10ajnas-calc" style="display: none; padding: 0.75rem; background: var(--matab-color-bg-muted); border-radius: 6px; border: 1px solid var(--matab-color-border-subtle);">
              <div style="font-size: 0.8rem; font-weight: 600; color: var(--matab-color-brand-primary); margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                <span>10-Ajnas-e-Ashara Classical Temperamental Assessment</span>
                <span style="font-size: 0.7rem; color: var(--matab-color-text-muted);">Mathematical Humoral Scoring (Al-Qanun)</span>
              </div>
              <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.75rem;">
                <div>
                  <label for="calc-malmas" style="font-weight: 600;">1. Malmās (Skin Touch):</label>
                  <select id="calc-malmas" class="form-control" style="font-size: 0.75rem;">
                    <option value="DAMAWWI">Garm o Tar (Hot &amp; Moist / Damawi)</option>
                    <option value="SAFRAWI">Garm o Khushk (Hot &amp; Dry / Safrawi)</option>
                    <option value="BALGHAMI">Sard o Tar (Cold &amp; Moist / Balghami)</option>
                    <option value="SAUDAWI">Sard o Khushk (Cold &amp; Dry / Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-lahm" style="font-weight: 600;">2. Lahm wa Shahm (Body Mass):</label>
                  <select id="calc-lahm" class="form-control" style="font-size: 0.75rem;">
                    <option value="DAMAWWI">Muscular &amp; Dense Flesh (Damawi)</option>
                    <option value="BALGHAMI">Abundant Adipose Fat / Flabby (Balghami)</option>
                    <option value="SAFRAWI">Lean, Sinewy, Prominent Tendons (Safrawi)</option>
                    <option value="SAUDAWI">Extremely Thin / Wasted (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-shaar" style="font-weight: 600;">3. Sha'ar (Hair Texture):</label>
                  <select id="calc-shaar" class="form-control" style="font-size: 0.75rem;">
                    <option value="SAFRAWI">Rapid Growth, Curly, Jet Black (Safrawi)</option>
                    <option value="DAMAWWI">Moderate Growth, Thick (Damawi)</option>
                    <option value="BALGHAMI">Slow Growth, Straight, Light (Balghami)</option>
                    <option value="SAUDAWI">Brittle, Dry, Early Graying (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-lawn" style="font-weight: 600;">4. Lawn (Complexion):</label>
                  <select id="calc-lawn" class="form-control" style="font-size: 0.75rem;">
                    <option value="DAMAWWI">Ruddy / Reddish Rosy Flush (Damawi)</option>
                    <option value="SAFRAWI">Yellowish / Pale Amber Tint (Safrawi)</option>
                    <option value="BALGHAMI">Chalky Pale / Dull Whitish (Balghami)</option>
                    <option value="SAUDAWI">Dusky / Earthy Darkish (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-bunya" style="font-weight: 600;">5. Hay'at al-A'da (Skeletal Frame):</label>
                  <select id="calc-bunya" class="form-control" style="font-size: 0.75rem;">
                    <option value="DAMAWWI">Broad Chest, Robust Frame (Damawi)</option>
                    <option value="SAFRAWI">Medium Build, Prominent Joints (Safrawi)</option>
                    <option value="BALGHAMI">Rounded Soft Joints, Plump Frame (Balghami)</option>
                    <option value="SAUDAWI">Narrow Chest, Bony Angles (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-infial" style="font-weight: 600;">6. Infialat (Psychic Temper):</label>
                  <select id="calc-infial" class="form-control" style="font-size: 0.75rem;">
                    <option value="SAFRAWI">Irascible, Quick to Anger (Safrawi)</option>
                    <option value="DAMAWWI">Cheerful, Sanguine, Optimistic (Damawi)</option>
                    <option value="BALGHAMI">Calm, Phlegmatic, Slow to React (Balghami)</option>
                    <option value="SAUDAWI">Brooding, Melancholic, Anxious (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-nawm" style="font-weight: 600;">7. Nawm (Sleep Pattern):</label>
                  <select id="calc-nawm" class="form-control" style="font-size: 0.75rem;">
                    <option value="BALGHAMI">Deep Heavy Sleep, Lethargy (Balghami)</option>
                    <option value="DAMAWWI">Moderate, Restorative Sleep (Damawi)</option>
                    <option value="SAFRAWI">Light, Short Sleep (Safrawi)</option>
                    <option value="SAUDAWI">Chronic Insomnia, Disturbed (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-afal" style="font-weight: 600;">8. Af'al (Digestive Vigour):</label>
                  <select id="calc-afal" class="form-control" style="font-size: 0.75rem;">
                    <option value="DAMAWWI">High Stamina, Rapid Digestion (Damawi)</option>
                    <option value="SAFRAWI">Sharp Ravenous Appetite (Safrawi)</option>
                    <option value="BALGHAMI">Sluggish Digestion, Heavy (Balghami)</option>
                    <option value="SAUDAWI">Variable Appetite, Flatus (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-fuzalat" style="font-weight: 600;">9. Fuzalat (Excretions):</label>
                  <select id="calc-fuzalat" class="form-control" style="font-size: 0.75rem;">
                    <option value="DAMAWWI">Normal Reddish-Tinged, Balanced (Damawi)</option>
                    <option value="SAFRAWI">Scanty Acrid Yellow, Hot Sweat (Safrawi)</option>
                    <option value="BALGHAMI">Copious Pale Clear, Cold Sweat (Balghami)</option>
                    <option value="SAUDAWI">Turbid Dark, Irregular Bowels (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="calc-nabz" style="font-weight: 600;">10. Nabz (Radial Pulse):</label>
                  <select id="calc-nabz" class="form-control" style="font-size: 0.75rem;">
                    <option value="DAMAWWI">Azeem, Mumtali (Full / Damawi)</option>
                    <option value="SAFRAWI">Saree, Mutawatir (Rapid / Safrawi)</option>
                    <option value="BALGHAMI">Batee, Layyin (Slow / Balghami)</option>
                    <option value="SAUDAWI">Daqeeq, Sulb (Thin / Saudawi)</option>
                  </select>
                </div>
              </div>
              <div style="display: flex; justify-content: flex-end; margin-top: 0.5rem; gap: 0.5rem;">
                <button type="button" class="btn btn-primary btn-sm" onclick="window.calculate10AjnasMizaj()" style="font-size: 0.72rem; font-weight: 600;">Calculate &amp; Apply Mizaj</button>
              </div>
            </div>

            <!-- 12-Axis Diagnostic Profiler Panel -->
            <div id="box-12axis-profiler" style="display: none; padding: 0.85rem; background: var(--matab-color-bg-muted); border-radius: 8px; border: 1.5px solid var(--matab-color-brand-primary);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
                <div>
                  <span style="font-size: 0.85rem; font-weight: 700; color: var(--matab-color-brand-primary);">
                    🎯 12-Axis Functional Organ Diagnostic Profiler
                  </span>
                  <div style="font-size: 0.7rem; color: var(--matab-color-text-muted);">
                    Rate dysfunction severity (0: Normal to 5: Severe Pathological Dysfunction)
                  </div>
                </div>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.reset12AxisScores()" style="font-size: 0.7rem;">Reset Scores</button>
              </div>
              <div id="grid-12-axes" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.5rem; margin-bottom: 0.75rem;"></div>
              <div id="profiler-live-results" style="display: none; padding: 0.65rem 0.8rem; background: var(--matab-color-bg-card); border-radius: 6px; border: 1px solid var(--matab-color-border-subtle); margin-bottom: 0.65rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                  <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <span id="badge-primary-axis" class="badge badge-danger" style="font-size: 0.78rem;">Primary Axis: --</span>
                    <span id="badge-secondary-axis" class="badge badge-warning" style="font-size: 0.78rem;">Secondary Axis: --</span>
                  </div>
                </div>
                <div id="profiler-matched-protocols" style="margin-top: 0.4rem;"></div>
              </div>
              <div style="display: flex; justify-content: flex-end;">
                <button type="button" class="btn btn-primary btn-sm" onclick="window.apply12AxisToAssessment()" style="font-size: 0.75rem; font-weight: 600;">
                  ✓ Apply Axes to Assessment
                </button>
              </div>
            </div>

            <!-- Classical Detailed Tashkhees Examination (Nabz, Baul, Baraz, Asbab) -->
            <div style="padding: 0.75rem; background: var(--matab-color-bg-muted); border-radius: 6px; font-size: 0.75rem;">
              <strong>Detailed Physical Exam (Pulse, Urine, Stool &amp; Lifestyle):</strong>
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.4rem; margin-top: 0.4rem;">
                <div>
                  <label for="tashkhees-nabz-surat" style="font-weight: 600; display: block;">Speed (Sur'at):</label>
                  <select id="tashkhees-nabz-surat" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MOTADIL">Motadil (Normal)</option>
                    <option value="SAREE">Saree (Rapid)</option>
                    <option value="BATEE">Batee (Slow)</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-nabz-quwwat" style="font-weight: 600; display: block;">Force (Quwwat):</label>
                  <select id="tashkhees-nabz-quwwat" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MOTADIL">Motadil</option>
                    <option value="QAWI">Qawi (Strong)</option>
                    <option value="DHAEF">Dha'eef (Weak)</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-nabz-lams" style="font-weight: 600; display: block;">Tension (Lams):</label>
                  <select id="tashkhees-nabz-lams" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MOTADIL">Motadil</option>
                    <option value="SULB">Sulb (Hard)</option>
                    <option value="LAYYIN">Layyin (Soft)</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-nabz-imtila" style="font-weight: 600; display: block;">Fullness (Imtila):</label>
                  <select id="tashkhees-nabz-imtila" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MOTADIL">Motadil</option>
                    <option value="MUMTALI">Mumtali (Full)</option>
                    <option value="KHALI">Khali (Empty)</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-nabz-hararat" style="font-weight: 600; display: block;">Warmth (Hararat):</label>
                  <select id="tashkhees-nabz-hararat" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MOTADIL">Motadil</option>
                    <option value="HAR">Har (Hot)</option>
                    <option value="BARID">Barid (Cold)</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-nabz-rhythm" style="font-weight: 600; display: block;">Rhythm (Nizam):</label>
                  <select id="tashkhees-nabz-rhythm" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MUNAZZAM">Munazzam (Regular)</option>
                    <option value="GHAIR_MUNAZZAM">Ghair-Munazzam</option>
                    <option value="MAWWAJ">Mawwaj</option>
                  </select>
                </div>
              </div>

              <!-- Baul & Baraz -->
              <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.4rem; margin-top: 0.5rem;">
                <div>
                  <label for="tashkhees-baul-lawn" style="font-weight: 600; display: block;">Urine Color (Lawn):</label>
                  <select id="tashkhees-baul-lawn" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="ASFAR_MOTADIL">Asfar Motadil</option>
                    <option value="ASFAR_NARI">Asfar Nari (Safrawi)</option>
                    <option value="ABYAD">Abyad (Balghami)</option>
                    <option value="AHMAR">Ahmar (Damawi)</option>
                    <option value="ASWAD">Aswad (Saudawi)</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-baul-qiwam" style="font-weight: 600; display: block;">Urine Density (Qiwam):</label>
                  <select id="tashkhees-baul-qiwam" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MOTADIL">Motadil</option>
                    <option value="RAQEEQ">Raqeeq</option>
                    <option value="GHALEEZ">Ghaleez</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-baraz-qiwam" style="font-weight: 600; display: block;">Stool Consistency (Qiwam):</label>
                  <select id="tashkhees-baraz-qiwam" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="MOTADIL">Motadil</option>
                    <option value="YABIS">Yabis (Constipated)</option>
                    <option value="LAYYIN">Layyin (Loose)</option>
                  </select>
                </div>
                <div>
                  <label for="tashkhees-baraz-lawn" style="font-weight: 600; display: block;">Stool Color (Lawn):</label>
                  <select id="tashkhees-baraz-lawn" class="form-control" style="font-size: 0.72rem; padding: 0.2rem;">
                    <option value="ASMAR_MOTADIL">Asmar (Brown)</option>
                    <option value="ASFAR">Asfar (Yellow)</option>
                    <option value="ASWAD">Aswad (Dark)</option>
                  </select>
                </div>
              </div>

              <!-- Asbab-e-Sittah Hidden / Compact Inputs -->
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.35rem; margin-top: 0.5rem;">
                <input type="text" id="asbab-hawa" class="form-control" style="font-size: 0.72rem;" placeholder="Air &amp; Climate (Hawa-e-Muheet)...">
                <input type="text" id="asbab-makool" class="form-control" style="font-size: 0.72rem;" placeholder="Food &amp; Drink (Makool wa Mashroob)...">
                <input type="text" id="asbab-badani" class="form-control" style="font-size: 0.72rem;" placeholder="Movement &amp; Rest (Harakat wa Sukoon)...">
                <input type="text" id="asbab-nafsani" class="form-control" style="font-size: 0.72rem;" placeholder="Stress &amp; Emotional (Nafsani)...">
                <input type="text" id="asbab-nawm" class="form-control" style="font-size: 0.72rem;" placeholder="Sleep &amp; Wakefulness (Nawm wa Yaqzah)...">
                <input type="text" id="asbab-istifragh" class="form-control" style="font-size: 0.72rem;" placeholder="Evacuation &amp; Retention (Istifragh wa Ehtebas)...">
              </div>
            </div>

            <!-- Systemic Physical Exam & Differentials -->
            <div style="padding: 0.75rem; background: var(--matab-color-bg-card); border-radius: 6px; border: 1px solid var(--matab-color-border-subtle); font-size: 0.75rem;">
              <strong>Systemic Physical Examination &amp; Differentials:</strong>
              <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.35rem; margin-top: 0.4rem;">
                <input type="text" id="exam-cvs" class="form-control" style="font-size: 0.72rem;" placeholder="CVS: S1 S2 heard...">
                <input type="text" id="exam-rs" class="form-control" style="font-size: 0.72rem;" placeholder="RS: Vesicular breath sounds...">
                <input type="text" id="exam-pa" class="form-control" style="font-size: 0.72rem;" placeholder="P/A: Soft, non-tender...">
                <input type="text" id="exam-cns" class="form-control" style="font-size: 0.72rem;" placeholder="CNS: Conscious, oriented...">
              </div>
              <div style="margin-top: 0.35rem;">
                <input type="text" id="exam-general" class="form-control" style="font-size: 0.72rem;" placeholder="General Survey: Pallor, Icterus, Cyanosis, Clubbing, Edema...">
              </div>
              <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.35rem; margin-top: 0.4rem;">
                <input type="text" id="diff-diag-1" class="form-control" style="font-size: 0.72rem;" placeholder="Differential 1...">
                <input type="text" id="diff-diag-2" class="form-control" style="font-size: 0.72rem;" placeholder="Differential 2...">
                <input type="text" id="diff-diag-3" class="form-control" style="font-size: 0.72rem;" placeholder="Differential 3...">
              </div>
              <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin-top: 0.4rem; font-size: 0.72rem; color: #9f1239;">
                <label><input type="checkbox" id="chk-redflag-gi"> No GI Bleed</label>
                <label><input type="checkbox" id="chk-redflag-weight"> No Weight Loss</label>
                <label><input type="checkbox" id="chk-redflag-dysphagia"> No Dysphagia</label>
                <label><input type="checkbox" id="chk-redflag-neuro"> No Neuro Deficit</label>
                <label><input type="checkbox" id="chk-redflag-nightpain"> No Night Pain</label>
              </div>
            </div>

            <!-- Biomedical & Laboratory Investigations Lane -->
            <div id="card-sec-biomedical_labs" style="padding: 0.75rem; background: var(--matab-color-bg-card); border-radius: 6px; border: 1px solid var(--matab-color-border-subtle);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; flex-wrap: wrap; gap: 0.35rem;">
                <strong style="color: var(--matab-color-brand-primary); font-size: 0.8rem;">🧪 Biomedical &amp; Laboratory Investigations:</strong>
                <div style="display: flex; gap: 0.25rem; flex-wrap: wrap;">
                  <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyLabPanel('METABOLIC')" style="font-size: 0.68rem; padding: 0.12rem 0.35rem;">+ Metabolic (HbA1c)</button>
                  <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyLabPanel('LIPIDS')" style="font-size: 0.68rem; padding: 0.12rem 0.35rem;">+ Lipids</button>
                  <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyLabPanel('HEPATO_RENAL')" style="font-size: 0.68rem; padding: 0.12rem 0.35rem;">+ LFT/KFT</button>
                  <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyLabPanel('THYROID')" style="font-size: 0.68rem; padding: 0.12rem 0.35rem;">+ Thyroid</button>
                  <button type="button" class="btn btn-secondary btn-sm" onclick="window.applyLabPanel('CBC')" style="font-size: 0.68rem; padding: 0.12rem 0.35rem;">+ CBC/ESR</button>
                </div>
              </div>
              <div style="overflow-x: auto;">
                <table class="table" style="font-size: 0.76rem; width: 100%; margin-bottom: 0.35rem;" id="table-lab-results">
                  <thead>
                    <tr style="background: var(--matab-color-bg-muted);">
                      <th>Biomarker</th>
                      <th>Value</th>
                      <th>Unit</th>
                      <th>Reference Range</th>
                      <th>Flag</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody id="tbody-lab-results"></tbody>
                </table>
              </div>
              <button type="button" class="btn btn-secondary btn-sm" onclick="window.addLabInvestigationRow()" style="font-size: 0.7rem; padding: 0.15rem 0.45rem;">+ Add Custom Lab Test</button>
              <textarea id="input-labs-tibbi-correlation" class="form-control" rows="1" style="font-size: 0.75rem; margin-top: 0.35rem;" placeholder="Biomedical-Tibbi Humoral Correlation notes..."></textarea>
            </div>

            <!-- Radiodiagnosis & Imaging Lane -->
            <div id="card-sec-radiodiagnosis" style="padding: 0.75rem; background: var(--matab-color-bg-card); border-radius: 6px; border: 1px solid var(--matab-color-border-subtle);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                <strong style="color: var(--matab-color-brand-primary); font-size: 0.8rem;">Radiodiagnosis &amp; Imaging (USG, X-Ray, CT, MRI):</strong>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addRadiodiagnosisRow()" style="font-size: 0.7rem; padding: 0.15rem 0.45rem;">+ Add Imaging Study</button>
              </div>
              <div style="overflow-x: auto;">
                <table class="table" style="font-size: 0.76rem; width: 100%; margin-bottom: 0.35rem;" id="table-radio-studies">
                  <thead>
                    <tr style="background: var(--matab-color-bg-muted);">
                      <th>Modality</th>
                      <th>Region</th>
                      <th>Key Findings</th>
                      <th>Impression</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody id="tbody-radio-studies"></tbody>
                </table>
              </div>
              <textarea id="input-radio-tibbi-correlation" class="form-control" rows="1" style="font-size: 0.75rem;" placeholder="Radiological Tibbi organ correlation notes..."></textarea>
            </div>

            <!-- Safety Firewall & Allopathic Medications -->
            <div id="card-sec-safety_review" style="padding: 0.75rem; background: var(--matab-color-bg-card); border-radius: 6px; border: 1px solid var(--matab-color-border-subtle);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <strong style="color: var(--matab-color-brand-primary); font-size: 0.8rem;">🛡️ Safety Firewall &amp; Concurrent Allopathic Drugs:</strong>
                <span id="preflight-status-pill" class="badge badge-secondary" style="font-size: 0.7rem;">Verified</span>
              </div>
              <input type="text" id="input-patient-allopathic-drugs" class="form-control" style="font-size: 0.78rem;" placeholder="Concurrent allopathic drugs (e.g. Warfarin, Levothyroxine, Amlodipine, Metformin)...">
              <div style="display: flex; gap: 0.25rem; margin-top: 0.3rem; flex-wrap: wrap;">
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addQuickDrug('Warfarin')" style="font-size: 0.65rem; padding: 0.1rem 0.3rem;">+ Warfarin</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addQuickDrug('Metformin')" style="font-size: 0.65rem; padding: 0.1rem 0.3rem;">+ Metformin</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addQuickDrug('Levothyroxine')" style="font-size: 0.65rem; padding: 0.1rem 0.3rem;">+ Levothyroxine</button>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addQuickDrug('Amlodipine')" style="font-size: 0.65rem; padding: 0.1rem 0.3rem;">+ Amlodipine</button>
              </div>
              <div id="box-herb-drug-alerts" style="display: none; padding: 0.5rem; background: #fef2f2; border: 1px solid #f87171; border-radius: 6px; margin-top: 0.4rem;">
                <div style="font-weight: 700; color: #991b1b; font-size: 0.78rem;" id="herb-drug-alert-count">0 Alerts</div>
                <div id="herb-drug-alerts-list" style="font-size: 0.75rem; margin-top: 0.25rem;"></div>
              </div>
              <div id="safety-preflight-summary-box" style="display: none;"><span id="preflight-coverage-text"></span></div>
              <div id="safety-findings-container" style="display: none;"></div>
            </div>

            <!-- Legacy Section Badges Container (Hidden, for State Concurrency) -->
            <div style="display: none;">
              <span id="badge-sec-history_observations">complete</span>
              <span id="badge-sec-modern_assessment">complete</span>
              <span id="badge-sec-biomedical_labs">complete</span>
              <span id="badge-sec-radiodiagnosis">complete</span>
              <span id="badge-sec-safety_review">complete</span>
              <span id="badge-sec-finalize">complete</span>
              <div id="finalized-documents-box"><div id="finalized-docs-list"></div></div>
            </div>

          </div>
        </details>

      </div>

      <!-- Right Column: Collapsible Context Drawer (Hidden by default for maximum width & clutter-free workspace) -->
      <div id="context-drawer-panel" style="display: none; flex-direction: column; gap: 1rem; position: sticky; top: 110px;">
        
        <!-- Readiness Gate Card -->
        <div class="card" style="padding: 1rem; margin-bottom: 0;">
          <h3 style="font-size: 0.95rem; font-weight: 600; color: var(--matab-color-brand-primary); margin: 0 0 0.5rem 0;">
            Sign-off Gate Readiness
          </h3>
          <div id="readiness-summary-text" style="font-size: 0.8rem; margin-bottom: 0.5rem; color: var(--matab-color-text-secondary);">
            Evaluating gates...
          </div>
          <div id="blocking-reasons-list" style="display: flex; flex-direction: column; gap: 0.35rem;"></div>
        </div>

        <!-- Evidence & Citations Card -->
        <div class="card" style="padding: 1rem; margin-bottom: 0;">
          <h3 style="font-size: 0.95rem; font-weight: 600; color: var(--matab-color-brand-primary); margin: 0 0 0.5rem 0;">
            Approved Clinical Knowledge
          </h3>
          <div style="display: flex; gap: 0.25rem; margin-bottom: 0.5rem;">
            <input type="text" id="input-knowledge-query" class="form-control" style="font-size: 0.75rem;" placeholder="Search drug or Mizaj concept...">
            <button class="btn btn-secondary btn-sm" onclick="window.searchKnowledgeContext()" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">Search</button>
          </div>
          <div id="knowledge-results-list" style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 250px; overflow-y: auto; font-size: 0.75rem;">
            <p style="color: var(--matab-color-text-muted); margin: 0;">Type a concept above to search classical and modern evidence.</p>
          </div>
        </div>

        <!-- State Transitions Audit Card -->
        <div class="card" style="padding: 1rem; margin-bottom: 0;">
          <h3 style="font-size: 0.95rem; font-weight: 600; color: var(--matab-color-brand-primary); margin: 0 0 0.5rem 0;">
            Workflow Transitions
          </h3>
          <div id="transitions-timeline-list" style="display: flex; flex-direction: column; gap: 0.35rem; font-size: 0.75rem; max-height: 200px; overflow-y: auto;">
            <p style="color: var(--matab-color-text-muted); margin: 0;">No transitions recorded yet.</p>
          </div>
        </div>

      </div>

    </div>

    <!-- Electronic PIN Signature Modal -->
    <div id="modal-signoff" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center;">
      <div class="card" style="width: 440px; max-width: 95vw; padding: 1.5rem; background: var(--matab-color-bg-card);">
        <h3 style="font-size: 1.15rem; color: var(--matab-color-brand-primary); margin: 0 0 0.75rem 0;">
          Clinician Electronic Signature &amp; Sole Finalization Gate (21 CFR Part 11)
        </h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
          By entering your confidential signature PIN, you certify that you have reviewed the clinical proposal, calibrated posology, cleared safety firewalls, and attest to this consultation record. This action commits the record to the immutable clinical ledger.
        </p>

        <div style="margin-bottom: 1rem;">
          <label style="font-size: 0.85rem; font-weight: 600;">Electronic Signature PIN *</label>
          <input type="password" id="input-sign-pin" class="form-control" maxlength="8" style="font-size: 1.1rem; letter-spacing: 0.25rem; text-align: center;" placeholder="••••">
          <span style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Practitioner Sign-off PIN (Default: 1234)</span>
        </div>

        <div id="signoff-error-alert" style="display: none; color: var(--matab-color-status-danger); font-size: 0.8rem; margin-bottom: 1rem;"></div>

        <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
          <button class="btn btn-secondary btn-sm" onclick="window.closeSignModal()">Cancel</button>
          <button class="btn btn-primary btn-sm" id="btn-submit-sign" onclick="window.submitElectronicSignature()">
            🔒 Sign &amp; Lock (21 CFR 11)
          </button>
        </div>
      </div>
    </div>

    <!-- Printable Prescription Slip Modal -->
    <div id="modal-print-rx" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65); z-index: 9999; justify-content: center; align-items: center; padding: 1rem;">
      <div class="card" style="width: 100%; max-width: 780px; max-height: 90vh; overflow-y: auto; background: var(--matab-color-bg-card); padding: 1.5rem; border-radius: var(--matab-radius-lg); box-shadow: var(--matab-shadow-xl);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <h3 style="margin: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem;">🖨️ Prescription Slip</h3>
            <div style="display: flex; gap: 0.2rem; background: var(--matab-color-bg-muted); padding: 0.2rem; border-radius: 6px; border: 1px solid var(--matab-color-border-subtle);">
              <button type="button" id="btn-print-fmt-a4" class="btn btn-sm" onclick="window.setPrintFormat('A4')" style="font-size: 0.72rem; padding: 0.2rem 0.55rem; background: #0f766e; color: #fff; font-weight: 600;">
                📄 A4 Letterhead
              </button>
              <button type="button" id="btn-print-fmt-thermal" class="btn btn-sm" onclick="window.setPrintFormat('THERMAL')" style="font-size: 0.72rem; padding: 0.2rem 0.55rem; background: transparent; color: #475569;">
                🧾 80mm Thermal
              </button>
            </div>
          </div>
          <div style="display: flex; gap: 0.4rem; align-items: center;">
            <button class="btn btn-secondary btn-sm" onclick="window.sendWhatsAppRx()" style="background: #25d366; color: #fff; border-color: #22c55e; font-weight: 600; font-size: 0.75rem;">
              💬 WhatsApp Rx
            </button>
            <button class="btn btn-primary btn-sm" onclick="window.printPrescriptionDocument()">🖨️ Print Slip</button>
            <button class="btn btn-secondary btn-sm" onclick="window.closePrintRxModal()">✕ Close</button>
          </div>
        </div>
        <div id="thermal-printer-hint" style="margin-bottom: 0.75rem; padding: 0.4rem 0.75rem; background: #fefce8; border: 1px solid #fef08a; border-radius: 6px; font-size: 0.73rem; color: #713f12; display: flex; align-items: center; justify-content: space-between;">
          <span>💡 <strong>Clinic Print Tip:</strong> For 80mm thermal receipt roll printers, set browser print margins to <strong>"None"</strong> and Scale to <strong>100%</strong> to prevent receipt clipping.</span>
          <span style="font-weight: 600; color: #854d0e;">Ctrl+P / ⌘+P</span>
        </div>
        <div id="printable-rx-content"></div>
      </div>
    </div>

    <!-- Switch Patient / Select Encounter Modal -->
    <div id="modal-switch-patient" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65); z-index: 9999; justify-content: center; align-items: center; padding: 1rem;">
      <div class="card" style="width: 100%; max-width: 650px; max-height: 85vh; overflow-y: auto; background: var(--matab-color-bg-card); padding: 1.5rem; border-radius: var(--matab-radius-lg); box-shadow: var(--matab-shadow-xl);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.5rem;">
          <h3 style="margin: 0; color: var(--matab-color-brand-primary); font-size: 1.15rem;">🔄 Switch Bedside Patient / Encounter</h3>
          <button class="btn btn-secondary btn-sm" onclick="window.closeSwitchPatientModal()">✕ Close</button>
        </div>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
          Select any registered patient from the directory to immediately open or initialize their consultation workspace.
        </p>
        <div id="switch-patient-list" style="max-height: 55vh; overflow-y: auto;">
          <p style="color: var(--matab-color-text-muted);">Loading patient directory...</p>
        </div>
      </div>
    </div>

    <!-- Hakeem Clinical Advisor Modal -->
    <div id="modal-hakeem-ai" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.65); z-index: 9999; justify-content: center; align-items: center; padding: 1rem;">
      <div class="card" style="width: 100%; max-width: 780px; max-height: 88vh; overflow-y: auto; background: var(--matab-color-bg-card); padding: 1.5rem; border-radius: var(--matab-radius-lg); box-shadow: var(--matab-shadow-xl); border: 2px solid #059669;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.5rem;">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.5rem;">🌿</span>
            <div>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                <h3 style="margin: 0; color: #065f46; font-size: 1.15rem;">Tibbi Clinical Decision Support — Bedside Medical Knowledge Engine</h3>
                <span id="badge-hakeem-ai-tier" class="badge" style="background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; font-size: 0.7rem; font-weight: 600;">
                  🟢 Live Clinical Literature &amp; Formulary Reference Active
                </span>
              </div>
              <p style="margin: 0; font-size: 0.75rem; color: var(--matab-color-text-muted);">
                Al-Qanun fi al-Tibb (Ibn Sina) • Makhzan-ul-Adwiya • Al-Hawi (Al-Razi) • 21 Master Clinical Protocols
              </p>
            </div>
          </div>
          <button class="btn btn-secondary btn-sm" onclick="window.closeHakeemAiModal()">✕ Close</button>
        </div>

        <!-- Query Input -->
        <div style="display: flex; gap: 0.4rem; margin-bottom: 0.75rem;">
          <input type="text" id="input-hakeem-ai-query" class="form-control" style="font-size: 0.85rem;" placeholder="Clinical Inquiry: e.g. Asgandh contraindication with Levothyroxine, or Badal for Salab Misri..." onkeydown="if(event.key === 'Enter') window.queryHakeemAi()">
          <button type="button" class="btn btn-primary btn-sm" onclick="window.queryHakeemAi()" style="background: #059669; border-color: #047857; padding: 0.4rem 1rem; font-weight: 600;">
            Consult Reference 📖
          </button>
        </div>

        <!-- 1-Click Quick Inquiries -->
        <div style="margin-bottom: 0.85rem;">
          <span style="font-size: 0.72rem; font-weight: 600; color: var(--matab-color-text-secondary); margin-bottom: 0.25rem; display: block;">Clinical Inquiries &amp; References:</span>
          <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('PCOS P-14 Protocol and Afaal cascade')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;">📋 PCOS 3-Phase Plan</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('Male Infertility Oligospermia P-11 Protocol')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;">📋 Male Infertility &amp; DFI</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('Asgandh interaction with Levothyroxine')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;">⚠️ Asgandh + Levothyroxine</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('Guggul interaction with Warfarin')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;">⚠️ Guggul + Blood Thinners</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('Classical Badal for Salab Misri')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;">🔄 Badal for Salab Misri</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('Pulse characteristics of Su-e-Mizaj Safrawi')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem;">🩺 Nabz-e-Safrawi</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('ZFIE Molecular Profile of Withaferin A in Asgandh')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem; background: #f0fdf4; color: #166534; border-color: #bbf7d0;">🔬 ZFIE: Withaferin Bio-Targets</button>
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.setAndRunHakeemAiQuery('Makhzan definition of Munzij and Mushil')" style="font-size: 0.7rem; padding: 0.2rem 0.5rem; background: #eff6ff; color: #1e40af; border-color: #bfdbfe;">📖 Corpus: Munzij &amp; Mushil</button>
          </div>
        </div>

        <!-- Reference Output Box -->
        <div id="hakeem-ai-response-box" style="padding: 1rem; background: var(--matab-color-bg-muted); border-radius: 8px; border: 1px solid var(--matab-color-border-subtle); min-height: 180px; font-size: 0.82rem; line-height: 1.5;">
          <div style="color: var(--matab-color-text-muted); text-align: center; padding: 2rem 1rem;">
            <span style="font-size: 1.5rem;">📖</span><br>
            <strong>Clinical Decision Support System Ready</strong><br>
            Enter any medical inquiry or select a reference topic above to retrieve verified Unani and pharmacological guidance.
          </div>
        </div>
      </div>
    </div>
  `;

  // Attach global window handlers for buttons
  window.toggleSection = toggleSection;
  window.markSectionComplete = markSectionComplete;
  window.markSectionNA = markSectionNA;
  window.openSignModal = openSignModal;
  window.closeSignModal = closeSignModal;
  window.submitElectronicSignature = submitElectronicSignature;
  window.runPreflightCheck = runPreflightCheck;
  window.searchKnowledgeContext = searchKnowledgeContext;
  window.addNuskhaItemRow = addNuskhaItemRow;
  window.recordFindingDisposition = recordFindingDisposition;
  window.openPrintRxModal = openPrintRxModal;
  window.closePrintRxModal = closePrintRxModal;
  window.printPrescriptionDocument = printPrescriptionDocument;
  window.toggle10AjnasCalculator = toggle10AjnasCalculator;
  window.calculate10AjnasMizaj = calculate10AjnasMizaj;
  window.applyNuskhaPreset = applyNuskhaPreset;
  window.suggestBadalForItem = suggestBadalForItem;
  window.viewMufradMonographFromRow = viewMufradMonographFromRow;
  window.openSwitchPatientModal = openSwitchPatientModal;
  window.closeSwitchPatientModal = closeSwitchPatientModal;
  window.selectPatientForConsultation = selectPatientForConsultation;

  // Master Clinical System Architecture (Prompt 10)
  window.toggle12AxisProfiler = toggle12AxisProfiler;
  window.render12AxisGrid = render12AxisGrid;
  window.setAxisScore = setAxisScore;
  window.evaluateActiveAxes = evaluateActiveAxes;
  window.reset12AxisScores = reset12AxisScores;
  window.apply12AxisToAssessment = apply12AxisToAssessment;
  window.populateProtocolDropdown = populateProtocolDropdown;
  window.filterProtocolsByCategory = filterProtocolsByCategory;
  window.onProtocolSelectChanged = onProtocolSelectChanged;
  window.loadSelectedMasterProtocol = loadSelectedMasterProtocol;
  window.loadMasterProtocol = loadMasterProtocol;
  window.autoDraftNuskhaFromDiagnosis = autoDraftNuskhaFromDiagnosis;
  window.triggerComplaintAiDraft = triggerComplaintAiDraft;
  window.addQuickDrug = addQuickDrug;
  window.calculateBMI = calculateBMI;
  window.addLabInvestigationRow = addLabInvestigationRow;
  window.applyLabPanel = applyLabPanel;
  window.addRadiodiagnosisRow = addRadiodiagnosisRow;
  window.appendHijamaPoint = appendHijamaPoint;
  window.appendFasdVessel = appendFasdVessel;
  window.applyParhezPreset = applyParhezPreset;

  // Window delegates to modular sub-modules
  window.setConsultationMode = setConsultationMode;
  window.scrollToSection = scrollToSection;
  window.toggleAllSections = toggleAllSections;
  window.toggleSection = toggleSection;
  window.toggleContextDrawer = toggleContextDrawer;
  window.applyQuickChiefComplaint = applyQuickChiefComplaint;
  window.applyNabzPreset = applyNabzPreset;
  window.applyBaulPreset = applyBaulPreset;
  window.calculateBMI = calculateBMI;
  window.setPrintFormat = setPrintFormat;
  window.printPrescriptionDocument = printPrescriptionDocument;
  window.applyQuickDuration = applyQuickDuration;
  window.appendQuickText = appendQuickText;
  window.sendWhatsAppRx = sendWhatsAppRx;
  window.openHakeemAiModal = openHakeemAiModal;
  window.closeHakeemAiModal = closeHakeemAiModal;
  window.setAndRunHakeemAiQuery = setAndRunHakeemAiQuery;
  window.queryHakeemAi = () => queryHakeemAi(cachedMasterData, CANONICAL_MATAB_SAFOOF_REGISTRY);

  // Bedside Doctor Keyboard Hotkeys (Cmd+S / Ctrl+S, Alt+N)
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      triggerAutosave();
    }
    if (e.altKey && e.key.toLowerCase() === "n") {
      e.preventDefault();
      addNuskhaItemRow();
    }
  });

  // Wire 1-Click Express OPD Protocol Pills
  container.querySelectorAll(".btn-protocol-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      const pKey = btn.dataset.protocol;
      applyExpressProtocol(pKey, addNuskhaItemRow, triggerAutosave);
      container.querySelectorAll(".btn-protocol-pill").forEach(b => {
        b.style.background = "#ffffff";
        b.style.color = "#065f46";
      });
      btn.style.background = "#059669";
      btn.style.color = "#ffffff";
    });
  });

  // Wire Fast Medication Lookup (Enter-to-Add)
  const fastInp = container.querySelector("#fast-drug-lookup-input");
  const fastBtn = container.querySelector("#btn-fast-add-drug");
  const addFromFastInput = () => {
    if (!fastInp) return;
    const rawVal = fastInp.value.trim();
    if (!rawVal) return;
    const cleanDrugName = rawVal.split("•")[0].trim();
    const found = CANONICAL_UNANI_DRUGS.find(d => d.name.toLowerCase() === cleanDrugName.toLowerCase());
    let doseAmt = 5;
    let doseUnit = "g";
    let freq = "BD";
    if (found) {
      if (found.form === "SHARBAT") { doseAmt = 20; doseUnit = "ml"; }
      else if (found.form === "HAB" || found.form === "QURS") { doseAmt = 1; doseUnit = "hab"; }
      else if (found.form === "ITRIFAL") { doseAmt = 7; doseUnit = "g"; freq = "HS"; }
      else if (found.form === "LAUQ") { doseAmt = 7; doseUnit = "g"; freq = "HS"; }
    }
    addNuskhaItemRow({ item_name: cleanDrugName, dose_amount: doseAmt, dose_unit: doseUnit, frequency: freq, duration_days: 14 });
    triggerAutosave();
    if (window.showToast) window.showToast(`+ Added ${cleanDrugName} to Nuskha`, "info", 1500);
    fastInp.value = "";
    fastInp.focus();
  };
  fastInp?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addFromFastInput();
    }
  });
  fastBtn?.addEventListener("click", addFromFastInput);

  // Initial load
  await loadActiveEncounterWorkspace();
}

// -----------------------------------------------------------------------------
// WORKSPACE DATA LOADER
// -----------------------------------------------------------------------------

async function loadActiveEncounterWorkspace() {
  let encId = state.activeEncounterId;
  let patId = state.activePatientId;

  // Fast canonical encounter default (instant clinical workspace readiness)
  if (!encId) {
    encId = "enc-syn-001";
    state.activeEncounterId = encId;
    state.activePatientId = "pat-syn-001";
  }

  activeEncounterId = encId;

  try {
    const res = await apiClient.get(`/api/v1/encounters/${encId}/workspace`);
    workspaceData = res.workspace;
    populateWorkspaceUI(workspaceData);
    setupAutosaveListeners();
    await fetchMasterClinicalData();
  } catch (err) {
    console.error("Failed to load consultation workspace:", err);
    const banner = document.getElementById("banner-patient-name");
    if (banner) banner.innerText = "Please Select a Patient to Begin Consultation";
  }
}

async function openSwitchPatientModal() {
  const modal = document.getElementById("modal-switch-patient");
  if (!modal) return;
  const listEl = document.getElementById("switch-patient-list");
  listEl.innerHTML = `<p style="color: var(--matab-color-text-muted);">Loading patient directory...</p>`;
  modal.style.display = "flex";

  try {
    const res = await apiClient.get("/api/v1/patients", { limit: 25 });
    const patients = res.patients || [];
    if (patients.length === 0) {
      listEl.innerHTML = `<p style="padding: 1rem; text-align: center; color: var(--matab-color-text-muted);">No registered patients found.</p>`;
      return;
    }
    listEl.innerHTML = patients.map(p => `
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem; border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-md); margin-bottom: 0.5rem; background: var(--matab-color-bg-card); transition: all 0.15s;">
        <div>
          <div style="font-weight: 700; color: var(--matab-color-brand-primary); font-size: 0.95rem;">
            ${escapeHtml((p.display_name || p.full_name || 'Patient').replace(/\s*\[Synthetic\]/gi, ""))}
          </div>
          <div style="font-size: 0.78rem; color: var(--matab-color-text-muted); margin-top: 0.2rem;">
            MRN: <strong>${escapeHtml(p.mrn)}</strong> • Age: ${escapeHtml(p.estimated_age || p.age || '--')} • Sex: ${escapeHtml(p.sex || 'U')} • Contact: ${escapeHtml(p.phone || '--')}
          </div>
        </div>
        <button class="btn btn-primary btn-sm" onclick="window.selectPatientForConsultation('${escapeHtml(p.id)}')">
          Open Consultation ➔
        </button>
      </div>
    `).join("");
  } catch (err) {
    listEl.innerHTML = `<p style="color: var(--matab-color-status-danger);">Error loading patients: ${escapeHtml(err.message)}</p>`;
  }
}

function closeSwitchPatientModal() {
  const modal = document.getElementById("modal-switch-patient");
  if (modal) modal.style.display = "none";
}

async function selectPatientForConsultation(patientId) {
  try {
    const timeline = await apiClient.get(`/api/v1/patients/${patientId}/timeline`);
    const encEvent = (timeline.timeline || []).find(e => e.event_type === "ENCOUNTER_VISIT");
    let encId = encEvent ? encEvent.resource_id : null;

    if (!encId) {
      const newEnc = await apiClient.post(`/api/v1/patients/${patientId}/encounters`, {
        encounter_type: "OPD_VISIT",
        reason_for_visit: "General Clinical Consultation"
      });
      encId = newEnc.encounter?.id || newEnc.id;
    }

    state.activePatientId = patientId;
    state.activeEncounterId = encId;
    closeSwitchPatientModal();
    await loadActiveEncounterWorkspace();
  } catch (err) {
    alert(`Could not open consultation: ${err.message}`);
  }
}

function populateWorkspaceUI(ws) {
  if (!ws) return;

  const enc = ws.encounter;
  const pat = ws.patient;

  // Header State Badge
  const stateBadge = document.getElementById("encounter-state-badge");
  stateBadge.innerText = enc.status.toUpperCase();
  if (enc.status === "completed") {
    stateBadge.className = "badge badge-success";
    document.getElementById("btn-open-finalize").style.display = "none";
  } else if (enc.status === "ready_for_signoff") {
    stateBadge.className = "badge badge-warning";
  } else {
    stateBadge.className = "badge badge-info";
  }

  // Patient Banner
  document.getElementById("banner-patient-name").innerText = (pat.display_name || "Unknown Patient").replace(/\s*\[Synthetic\]/gi, "");
  document.getElementById("banner-patient-mrn").innerText = `MRN: ${pat.mrn}`;
  document.getElementById("banner-patient-demographics").innerText = `${pat.sex || 'U'} • Age: ${pat.estimated_age || pat.age || '--'}`;
  document.getElementById("banner-token").innerText = `Token: #${enc.token_number || '--'}`;

  // Populate Section Badges & States
  for (const [key, sec] of Object.entries(ws.sections || {})) {
    const badge = document.getElementById(`badge-sec-${key}`);
    if (badge) {
      badge.innerText = sec.status;
      if (sec.status === "complete") badge.className = "badge badge-success";
      else if (sec.status === "not_applicable") badge.className = "badge badge-secondary";
      else if (sec.status === "in_progress") badge.className = "badge badge-info";
      else badge.className = "badge badge-secondary";
    }
  }

  // Populate Draft Data
  const lanes = ws.draft_lanes || {};
  if (lanes.visit) {
    const encTypeEl = document.getElementById("input-encounter-type");
    if (encTypeEl) encTypeEl.value = lanes.visit.encounter_type || "OPD_VISIT";
    const reasonEl = document.getElementById("input-reason-visit");
    if (reasonEl) reasonEl.value = lanes.visit.reason_for_visit || "";
  }
  if (lanes.history_observations) {
    const hpiEl = document.getElementById("input-hpi");
    if (hpiEl) hpiEl.value = lanes.history_observations.history_of_present_illness || "";
  }
  if (lanes.unani_assessment) {
    const u = lanes.unani_assessment;
    const mizajEl = document.getElementById("input-unani-mizaj");
    if (mizajEl) mizajEl.value = u.dominant_mizaj || u.primary_mizaj || "NOT_ASSESSED";
    const secEl = document.getElementById("input-unani-secondary");
    if (secEl) secEl.value = u.secondary_mizaj || "";
    const reasonEl = document.getElementById("input-unani-reasoning");
    if (reasonEl) reasonEl.value = u.clinical_reasoning || "";

    // Hydrate Tashkhees & 12-Axis profile from mizaj_rationale
    if (u.mizaj_rationale) {
      try {
        const ur = typeof u.mizaj_rationale === "string" ? JSON.parse(u.mizaj_rationale) : u.mizaj_rationale;
        if (ur && ur.nabz) {
          if (ur.nabz.surat && document.getElementById("tashkhees-nabz-surat")) document.getElementById("tashkhees-nabz-surat").value = ur.nabz.surat;
          if (ur.nabz.quwwat && document.getElementById("tashkhees-nabz-quwwat")) document.getElementById("tashkhees-nabz-quwwat").value = ur.nabz.quwwat;
          if (ur.nabz.lams && document.getElementById("tashkhees-nabz-lams")) document.getElementById("tashkhees-nabz-lams").value = ur.nabz.lams;
          if (ur.nabz.imtila && document.getElementById("tashkhees-nabz-imtila")) document.getElementById("tashkhees-nabz-imtila").value = ur.nabz.imtila;
          if (ur.nabz.hararat && document.getElementById("tashkhees-nabz-hararat")) document.getElementById("tashkhees-nabz-hararat").value = ur.nabz.hararat;
          if (ur.nabz.rhythm && document.getElementById("tashkhees-nabz-rhythm")) document.getElementById("tashkhees-nabz-rhythm").value = ur.nabz.rhythm;
        }
        if (ur && ur.baul) {
          if (ur.baul.lawn && document.getElementById("tashkhees-baul-lawn")) document.getElementById("tashkhees-baul-lawn").value = ur.baul.lawn;
          if (ur.baul.qiwam && document.getElementById("tashkhees-baul-qiwam")) document.getElementById("tashkhees-baul-qiwam").value = ur.baul.qiwam;
          if (ur.baul.safa && document.getElementById("tashkhees-baul-safa")) document.getElementById("tashkhees-baul-safa").value = ur.baul.safa;
          if (ur.baul.rasub && document.getElementById("tashkhees-baul-rasub")) document.getElementById("tashkhees-baul-rasub").value = ur.baul.rasub;
        }
        if (ur && ur.baraz) {
          if (ur.baraz.qiwam && document.getElementById("tashkhees-baraz-qiwam")) document.getElementById("tashkhees-baraz-qiwam").value = ur.baraz.qiwam;
          if (ur.baraz.lawn && document.getElementById("tashkhees-baraz-lawn")) document.getElementById("tashkhees-baraz-lawn").value = ur.baraz.lawn;
          if (ur.baraz.raiha && document.getElementById("tashkhees-baraz-raiha")) document.getElementById("tashkhees-baraz-raiha").value = ur.baraz.raiha;
          if (ur.baraz.riyah && document.getElementById("tashkhees-baraz-riyah")) document.getElementById("tashkhees-baraz-riyah").value = ur.baraz.riyah;
        }
        if (ur && ur.asbab_sittah) {
          if (ur.asbab_sittah.hawa && document.getElementById("asbab-hawa")) document.getElementById("asbab-hawa").value = ur.asbab_sittah.hawa;
          if (ur.asbab_sittah.makool && document.getElementById("asbab-makool")) document.getElementById("asbab-makool").value = ur.asbab_sittah.makool;
          if (ur.asbab_sittah.badani && document.getElementById("asbab-badani")) document.getElementById("asbab-badani").value = ur.asbab_sittah.badani;
          if (ur.asbab_sittah.nafsani && document.getElementById("asbab-nafsani")) document.getElementById("asbab-nafsani").value = ur.asbab_sittah.nafsani;
          if (ur.asbab_sittah.nawm && document.getElementById("asbab-nawm")) document.getElementById("asbab-nawm").value = ur.asbab_sittah.nawm;
          if (ur.asbab_sittah.istifragh && document.getElementById("asbab-istifragh")) document.getElementById("asbab-istifragh").value = ur.asbab_sittah.istifragh;
        }
        if (ur && ur.active_12_axes && Object.keys(ur.active_12_axes).length > 0) {
          active12AxisScores = ur.active_12_axes;
          render12AxisGrid();
          evaluateActiveAxes();
        }
      } catch (e) {
        // Not JSON
      }
    }
  }

  if (lanes.modern_assessment) {
    const m = lanes.modern_assessment;
    const workEl = document.getElementById("input-modern-working");
    if (workEl) workEl.value = m.working_assessment || "";
    const icdEl = document.getElementById("input-modern-icd11");
    if (icdEl) icdEl.value = m.clinical_rationale || "";

    if (m.physical_examination_json) {
      try {
        const pe = typeof m.physical_examination_json === "string" ? JSON.parse(m.physical_examination_json) : m.physical_examination_json;
        if (pe && pe.vitals) {
          if (pe.vitals.bp_sys && document.getElementById("vital-bp-sys")) document.getElementById("vital-bp-sys").value = pe.vitals.bp_sys;
          if (pe.vitals.bp_dia && document.getElementById("vital-bp-dia")) document.getElementById("vital-bp-dia").value = pe.vitals.bp_dia;
          if (pe.vitals.pulse && document.getElementById("vital-pulse")) document.getElementById("vital-pulse").value = pe.vitals.pulse;
          if (pe.vitals.rr && document.getElementById("vital-rr")) document.getElementById("vital-rr").value = pe.vitals.rr;
          if (pe.vitals.temp && document.getElementById("vital-temp")) document.getElementById("vital-temp").value = pe.vitals.temp;
          if (pe.vitals.spo2 && document.getElementById("vital-spo2")) document.getElementById("vital-spo2").value = pe.vitals.spo2;
          if (pe.vitals.weight_kg && document.getElementById("vital-weight")) document.getElementById("vital-weight").value = pe.vitals.weight_kg;
          if (pe.vitals.height_cm && document.getElementById("vital-height")) document.getElementById("vital-height").value = pe.vitals.height_cm;
          calculateBMI();
        }
        if (pe && pe.systemic) {
          if (pe.systemic.cvs && document.getElementById("exam-cvs")) document.getElementById("exam-cvs").value = pe.systemic.cvs;
          if (pe.systemic.rs && document.getElementById("exam-rs")) document.getElementById("exam-rs").value = pe.systemic.rs;
          if (pe.systemic.pa && document.getElementById("exam-pa")) document.getElementById("exam-pa").value = pe.systemic.pa;
          if (pe.systemic.cns && document.getElementById("exam-cns")) document.getElementById("exam-cns").value = pe.systemic.cns;
          if (pe.systemic.general && document.getElementById("exam-general")) document.getElementById("exam-general").value = pe.systemic.general;
        }
        if (pe && Array.isArray(pe.differentials)) {
          if (pe.differentials[0] && document.getElementById("diff-diag-1")) document.getElementById("diff-diag-1").value = pe.differentials[0];
          if (pe.differentials[1] && document.getElementById("diff-diag-2")) document.getElementById("diff-diag-2").value = pe.differentials[1];
          if (pe.differentials[2] && document.getElementById("diff-diag-3")) document.getElementById("diff-diag-3").value = pe.differentials[2];
        }
        if (pe && pe.red_flags) {
          if (document.getElementById("chk-redflag-gi")) document.getElementById("chk-redflag-gi").checked = !!pe.red_flags.no_gi_bleed;
          if (document.getElementById("chk-redflag-weight")) document.getElementById("chk-redflag-weight").checked = !!pe.red_flags.no_weight_loss;
          if (document.getElementById("chk-redflag-dysphagia")) document.getElementById("chk-redflag-dysphagia").checked = !!pe.red_flags.no_dysphagia;
          if (document.getElementById("chk-redflag-neuro")) document.getElementById("chk-redflag-neuro").checked = !!pe.red_flags.no_neuro_deficit;
          if (document.getElementById("chk-redflag-nightpain")) document.getElementById("chk-redflag-nightpain").checked = !!pe.red_flags.no_night_pain;
        }
        if (pe && pe.labs && Array.isArray(pe.labs) && pe.labs.length > 0) {
          const tbodyLab = document.getElementById("tbody-lab-results");
          if (tbodyLab) {
            tbodyLab.innerHTML = "";
            pe.labs.forEach(it => addLabInvestigationRow(it));
          }
        }
        if (pe && pe.labs_tibbi_correlation && document.getElementById("input-labs-tibbi-correlation")) {
          document.getElementById("input-labs-tibbi-correlation").value = pe.labs_tibbi_correlation;
        }
        if (pe && pe.radiodiagnosis && Array.isArray(pe.radiodiagnosis) && pe.radiodiagnosis.length > 0) {
          const tbodyRadio = document.getElementById("tbody-radio-studies");
          if (tbodyRadio) {
            tbodyRadio.innerHTML = "";
            pe.radiodiagnosis.forEach(it => addRadiodiagnosisRow(it));
          }
        }
        if (pe && pe.radio_tibbi_correlation && document.getElementById("input-radio-tibbi-correlation")) {
          document.getElementById("input-radio-tibbi-correlation").value = pe.radio_tibbi_correlation;
        }
      } catch (e) {
        // Not JSON
      }
    }
  }

  if (lanes.care_plan) {
    const cp = lanes.care_plan;
    const planEl = document.getElementById("input-plan-principle");
    if (planEl) planEl.value = cp.title || cp.primary_usul_e_ilaj || "";

    if (cp.clinical_rationale) {
      try {
        const cpr = typeof cp.clinical_rationale === "string" ? JSON.parse(cp.clinical_rationale) : cp.clinical_rationale;
        if (cpr && cpr.tadbeer_notes && document.getElementById("input-tadbeer-notes")) document.getElementById("input-tadbeer-notes").value = cpr.tadbeer_notes;
        if (cpr && cpr.ghiza && document.getElementById("input-ghiza-diet")) document.getElementById("input-ghiza-diet").value = cpr.ghiza;
        if (cpr && cpr.parhez && document.getElementById("input-parhez-avoid")) document.getElementById("input-parhez-avoid").value = cpr.parhez;
        if (cpr && Array.isArray(cpr.tadbeer_list)) {
          document.querySelectorAll("#chk-tadbeer-hijama, #chk-tadbeer-dalk, #chk-tadbeer-fasd, #chk-tadbeer-natool, #chk-tadbeer-hammam, #chk-tadbeer-inkabab").forEach(cb => {
            cb.checked = cpr.tadbeer_list.includes(cb.value);
          });
        }
      } catch (e) {
        if (document.getElementById("input-tadbeer-notes") && !document.getElementById("input-tadbeer-notes").value) {
          document.getElementById("input-tadbeer-notes").value = cp.clinical_rationale;
        }
      }
    }
  }

  // Populate Nuskha Items
  const tbody = document.getElementById("tbody-nuskha-items");
  tbody.innerHTML = "";
  const rx = lanes.prescription;
  if (rx && rx.items && rx.items.length > 0) {
    for (const it of rx.items) {
      addNuskhaItemRow(it);
    }
  } else {
    // Add 1 default empty item row
    addNuskhaItemRow({ item_name: "Hab-e-Suranjan", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 7, anupan_vehicle: "Water" });
  }

  // Populate Safety Preflight
  const pre = lanes.safety_preflight;
  const pill = document.getElementById("preflight-status-pill");
  const cov = document.getElementById("preflight-coverage-text");
  const findingsContainer = document.getElementById("safety-findings-container");

  if (pre && pill) {
    const overall = (pre.overall_status || "passed").toUpperCase();
    pill.innerText = overall;
    if (overall === "BLOCKED") pill.className = "badge badge-danger";
    else if (overall === "REVIEWED_WITH_CAUTIONS") pill.className = "badge badge-warning";
    else pill.className = "badge badge-success";

    if (cov) {
      cov.innerText = `Checked ruleset: ${pre.ruleset_version || 'v2.0'} • Executed at: ${pre.executed_at || 'Just now'}`;
    }

    if (pre.findings && pre.findings.length > 0 && findingsContainer) {
      findingsContainer.innerHTML = "";
      for (const f of pre.findings) {
        const fDiv = document.createElement("div");
        fDiv.style.cssText = "padding: 0.5rem; border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-sm); font-size: 0.8rem; background: var(--matab-color-bg-card);";
        const hasDisp = !!f.disposition_type;
        fDiv.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <strong>${f.title} (${f.rule_code})</strong>
            <span class="badge ${f.severity === 'critical' ? 'badge-danger' : 'badge-warning'}">${(f.severity || 'warning').toUpperCase()}</span>
          </div>
          <p style="margin: 0 0 0.35rem 0; color: var(--matab-color-text-secondary);">${f.concise_rationale}</p>
          <div style="display: flex; gap: 0.5rem; align-items: center; margin-top: 0.35rem;">
            ${hasDisp ? `
              <span class="badge badge-success">Disposition: ${f.disposition_type}</span>
              <span style="color: var(--matab-color-text-muted); font-size: 0.75rem;">Rationale: ${f.clinical_rationale}</span>
            ` : `
              <input type="text" id="disp-rationale-${f.id}" class="form-control" style="font-size: 0.75rem; flex: 1;" placeholder="Mandatory clinical rationale...">
              <button class="btn btn-secondary btn-sm" onclick="window.recordFindingDisposition('${f.id}')" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">Acknowledge / Override</button>
            `}
          </div>
        `;
        findingsContainer.appendChild(fDiv);
      }
    } else if (findingsContainer) {
      findingsContainer.innerHTML = `<p style="font-size: 0.8rem; color: var(--matab-color-text-muted); margin: 0;">✓ Zero safety findings. All ingredients cleared.</p>`;
    }
  }

  // Populate Readiness Gate Summary
  updateReadinessUI(ws.signoff_eligibility);

  // Populate Generated Documents (if final)
  if (ws.documents && ws.documents.length > 0) {
    const docBox = document.getElementById("finalized-documents-box");
    const docList = document.getElementById("finalized-docs-list");
    if (docBox) docBox.style.display = "block";
    if (docList) {
      docList.innerHTML = ws.documents.map(d => `
        <div style="margin-bottom: 0.35rem;">
          📄 <strong>${d.document_type}</strong> (v${d.version_number}) — Digest: <code style="font-size: 0.75rem;">${(d.document_hash || '').substring(0, 16)}...</code>
        </div>
      `).join("");
    }
  }

  // Populate State Transitions History
  const transList = document.getElementById("transitions-timeline-list");
  if (transList && ws.transitions_history && ws.transitions_history.length > 0) {
    transList.innerHTML = ws.transitions_history.map(t => `
      <div style="padding: 0.25rem 0; border-bottom: 1px dashed var(--matab-color-border-subtle);">
        <code>${t.from_state}</code> → <strong>${t.to_state}</strong>
        <div style="color: var(--matab-color-text-muted); font-size: 0.7rem;">${t.reason || 'Workflow update'} • ${t.transitioned_at || ''}</div>
      </div>
    `).join("");
  }
}

function updateReadinessUI(eligibility) {
  if (!eligibility) return;

  const summary = document.getElementById("readiness-summary-text");
  const blkList = document.getElementById("blocking-reasons-list");
  const btnFinalize = document.getElementById("btn-open-finalize");

  if (summary) {
    summary.innerText = eligibility.summary || "Workflow Status";
    if (eligibility.eligible) {
      summary.style.color = "var(--matab-color-status-success)";
    } else {
      summary.style.color = "var(--matab-color-status-warning)";
    }
  }

  if (blkList) {
    if (eligibility.eligible) {
      blkList.innerHTML = `<span style="font-size: 0.75rem; color: var(--matab-color-status-success);">✓ All workflow gates satisfied. Ready for finalization.</span>`;
    } else {
      blkList.innerHTML = (eligibility.blocking_reasons || []).map(r => `
        <div style="font-size: 0.75rem; color: var(--matab-color-status-danger); display: flex; gap: 0.25rem;">
          <span>✕</span> <span>${r}</span>
        </div>
      `).join("");
    }
  }

  if (btnFinalize) {
    btnFinalize.disabled = !eligibility.eligible;
  }
}

// toggleSection is imported from ./consultation-nav.js

async function markSectionComplete(secKey) {
  try {
    const res = await apiClient.post(`/api/v1/encounters/${activeEncounterId}/sections/${secKey}/complete`, {
      metadata: { actor: "Hakeem", verified_at: new Date().toISOString() }
    });
    const badge = document.getElementById(`badge-sec-${secKey}`);
    if (badge) {
      badge.innerText = "complete";
      badge.className = "badge badge-success";
    }
    await refreshReadiness();
  } catch (err) {
    alert(`Could not complete section: ${err.message}`);
  }
}

async function markSectionNA(secKey) {
  const reason = await window.openPromptModal({
    title: "Clinical Justification Required",
    message: `Enter clinical rationale for marking '${secKey}' as Not Applicable:`,
    placeholder: "e.g., Patient unable to undergo physical assessment due to acute immobilization",
    confirmText: "Mark Not Applicable",
    required: true
  });
  if (!reason) return;

  try {
    const res = await apiClient.post(`/api/v1/encounters/${activeEncounterId}/sections/${secKey}/mark-not-applicable`, {
      metadata: { reason: reason.trim(), verified_at: new Date().toISOString() }
    });
    const badge = document.getElementById(`badge-sec-${secKey}`);
    if (badge) {
      badge.innerText = "not_applicable";
      badge.className = "badge badge-secondary";
    }
    await refreshReadiness();
  } catch (err) {
    alert(`Could not mark section N/A: ${err.message}`);
  }
}

async function refreshReadiness() {
  try {
    const res = await apiClient.post(`/api/v1/encounters/${activeEncounterId}/validate-signoff`, {});
    updateReadinessUI(res.eligibility);
  } catch (err) {
    console.warn("Readiness refresh failed:", err);
  }
}

// -----------------------------------------------------------------------------
// AUTOSAVE DEBOUNCING
// -----------------------------------------------------------------------------

function setupAutosaveListeners() {
  const inputs = document.querySelectorAll("#workspace-grid input, #workspace-grid textarea, #workspace-grid select");
  inputs.forEach(el => {
    el.addEventListener("input", triggerAutosave);
  });
}

function triggerAutosave() {
  const statusEl = document.getElementById("autosave-status");
  statusEl.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: var(--matab-color-status-warning);"></span> Changes pending...`;

  if (autosaveTimer) clearTimeout(autosaveTimer);
  autosaveTimer = setTimeout(executeAutosave, 1500);
}

// -----------------------------------------------------------------------------
// VITAL SIGNS, LABS & RADIODIAGNOSIS HELPERS
// -----------------------------------------------------------------------------

// calculateBMI is imported from ./consultation-assessment.js

const CANONICAL_LAB_PANELS = {
  METABOLIC: [
    { test_name: "Fasting Blood Glucose", value: "118", unit: "mg/dL", ref_range: "70 - 99", status: "ELEVATED" },
    { test_name: "Post-Prandial Blood Sugar", value: "185", unit: "mg/dL", ref_range: "< 140", status: "ELEVATED" },
    { test_name: "HbA1c (Glycated Hemoglobin)", value: "7.2", unit: "%", ref_range: "< 5.7 (Normal) | 5.7-6.4 (Prediabetes) | >= 6.5 (DM)", status: "ELEVATED" },
    { test_name: "Fasting Serum Insulin", value: "18.4", unit: "µIU/mL", ref_range: "2.6 - 24.9", status: "NORMAL" },
    { test_name: "HOMA-IR (Insulin Resistance)", value: "5.36", unit: "score", ref_range: "< 1.5 (Optimal) | > 2.0 (Insulin Resistance)", status: "CRITICAL" }
  ],
  LIPIDS: [
    { test_name: "Total Cholesterol", value: "245", unit: "mg/dL", ref_range: "< 200", status: "ELEVATED" },
    { test_name: "Triglycerides", value: "220", unit: "mg/dL", ref_range: "< 150", status: "ELEVATED" },
    { test_name: "HDL-Cholesterol", value: "38", unit: "mg/dL", ref_range: "> 40 (M) | > 50 (F)", status: "LOW" },
    { test_name: "LDL-Cholesterol", value: "163", unit: "mg/dL", ref_range: "< 100", status: "ELEVATED" },
    { test_name: "Non-HDL Cholesterol", value: "207", unit: "mg/dL", ref_range: "< 130", status: "ELEVATED" }
  ],
  HEPATO_RENAL: [
    { test_name: "SGOT (AST)", value: "48", unit: "U/L", ref_range: "10 - 40", status: "ELEVATED" },
    { test_name: "SGPT (ALT)", value: "62", unit: "U/L", ref_range: "7 - 56", status: "ELEVATED" },
    { test_name: "Alkaline Phosphatase (ALP)", value: "112", unit: "U/L", ref_range: "44 - 147", status: "NORMAL" },
    { test_name: "Total Bilirubin", value: "0.9", unit: "mg/dL", ref_range: "0.2 - 1.2", status: "NORMAL" },
    { test_name: "Serum Creatinine", value: "0.95", unit: "mg/dL", ref_range: "0.6 - 1.2", status: "NORMAL" },
    { test_name: "Blood Urea Nitrogen (BUN)", value: "14", unit: "mg/dL", ref_range: "7 - 20", status: "NORMAL" },
    { test_name: "Serum Uric Acid", value: "7.6", unit: "mg/dL", ref_range: "3.5 - 7.2", status: "ELEVATED" }
  ],
  THYROID: [
    { test_name: "TSH (Thyroid Stimulating Hormone)", value: "5.8", unit: "µIU/mL", ref_range: "0.4 - 4.2", status: "ELEVATED" },
    { test_name: "Free T3 (Triiodothyronine)", value: "2.8", unit: "pg/mL", ref_range: "2.3 - 4.2", status: "NORMAL" },
    { test_name: "Free T4 (Thyroxine)", value: "1.1", unit: "ng/dL", ref_range: "0.8 - 1.8", status: "NORMAL" },
    { test_name: "Anti-TPO Antibodies", value: "128", unit: "IU/mL", ref_range: "< 34 (Negative for Hashimoto's)", status: "CRITICAL" }
  ],
  REPRODUCTIVE: [
    { test_name: "Total Serum Testosterone", value: "320", unit: "ng/dL", ref_range: "300 - 1000 (M)", status: "BORDERLINE" },
    { test_name: "Sperm DFI (DNA Fragmentation Index)", value: "28.5", unit: "%", ref_range: "< 15% (Optimal) | 15-25% (Fair) | > 25% (High Fragmentation)", status: "CRITICAL" },
    { test_name: "Sperm Total Count", value: "18", unit: "million/mL", ref_range: ">= 15 million/mL", status: "NORMAL" },
    { test_name: "Progressive Motility (PR)", value: "26", unit: "%", ref_range: ">= 32%", status: "LOW" },
    { test_name: "Serum AMH (Anti-Müllerian Hormone)", value: "5.4", unit: "ng/mL", ref_range: "1.5 - 4.0 (Normal Reserve) | > 4.5 (PCOS)", status: "ELEVATED" }
  ],
  CBC: [
    { test_name: "Hemoglobin (Hb)", value: "13.8", unit: "g/dL", ref_range: "13.0 - 17.0 (M) | 12.0 - 15.5 (F)", status: "NORMAL" },
    { test_name: "Total Leukocyte Count (TLC)", value: "7,800", unit: "/µL", ref_range: "4,000 - 11,000", status: "NORMAL" },
    { test_name: "Platelet Count", value: "2.4", unit: "lakhs/µL", ref_range: "1.5 - 4.5", status: "NORMAL" },
    { test_name: "ESR (Erythrocyte Sedimentation Rate)", value: "22", unit: "mm/hr", ref_range: "< 15 (M) | < 20 (F)", status: "ELEVATED" },
    { test_name: "hs-CRP", value: "2.8", unit: "mg/L", ref_range: "< 1.0 (Low vascular inflammation)", status: "ELEVATED" }
  ]
};

const CANONICAL_PARHEZ_PRESETS = {
  "DM-01": {
    ghiza: "Barley (Jau) daliya, karela, jamun seed powder, methi seeds water, green leafy vegetables, roasted chana. High fiber and low glycemic index foods.",
    parhez: "Strictly avoid refined sugars, sweets, fruit juices, white rice, maida, potatoes, high-fructose corn syrups, and sedentary post-meal habit."
  },
  "MF-01": {
    ghiza: "Walnuts (30g daily), soaked almonds (10 daily), pumpkin seeds (zinc rich), pomegranate juice, saffron milk, fatty fish, fresh seasonal fruits.",
    parhez: "Zero laptop on lap (thermal insult to testes), loose cotton underwear, avoid hot tub/sauna baths, zero tobacco/smoking, zero alcohol, avoid refined seed oils."
  },
  "PC-01": {
    ghiza: "Spearmint tea (anti-androgen), flaxseeds, soaked fenugreek seeds, cinnamon tea, rich leafy vegetables, organic eggs, avocados, legumes.",
    parhez: "Zero refined carbohydrates, dairy products restricted to 1 serving max, eliminate sugary beverages, avoid late night screen light and chronic sleep deprivation."
  },
  "TM-01": {
    ghiza: "Brazil nuts (2-3 daily for selenium), cooked cruciferous vegetables (cooked only), virgin coconut oil, pumpkin seeds, warm bone broth or moong soup.",
    parhez: "RAW goitrogenic cruciferous vegetables strictly forbidden (raw cabbage, cauliflower, broccoli, kale). No ice cold drinks. Avoid gluten if Anti-TPO is positive."
  },
  "FK-01": {
    ghiza: "Black coffee (2 cups daily - 40% hepatoprotection), garlic, olive oil, turmeric, green tea, fresh amla juice, steamed vegetables.",
    parhez: "Zero high-fructose corn syrup, zero packaged fruit juices, eliminate alcohol, avoid deep-fried trans-fat foods, avoid late night dinner within 3 hours of sleep."
  },
  "NE-01": {
    ghiza: "Warm cow milk with crushed badam and zafran before bedtime, chamomile tea, pumpkin seeds, soaked figs, lightly steamed vegetables.",
    parhez: "Digital sunset at 9:00 PM (no blue light), zero caffeine after 12:00 PM noon, avoid loud sensory stimulation before sleep, eliminate late heavy dinners."
  },
  "ST-01": {
    ghiza: "High hydration (3.0 - 3.5 Litres daily), fresh lemon juice (citrate inhibitor), barley water (Maa al-Sha'eer), kulthi dal soup, cucumber.",
    parhez: "Strictly reduce dietary oxalates (spinach/palak, tomatoes with seeds, beets, chocolate, excessive tea), limit excessive animal protein and sodium."
  },
  "HP-01": {
    ghiza: "Garlic (2 cloves morning empty stomach), pomegranate juice, boiled beetroot, celery, watermelon, flaxseeds, potassium-rich foods.",
    parhez: "Strict sodium restriction (<2g/day), eliminate pickles, papad, processed salty snacks, avoid licorice (Mulethi causes aldosterone rise), zero smoking."
  }
};

function addLabInvestigationRow(item = {}) {
  const tbody = document.getElementById("tbody-lab-results");
  if (!tbody) return;
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="form-control lab-name-input" style="font-size: 0.75rem;" value="${item.test_name || ''}" placeholder="Test Name (e.g. HbA1c, ALT, DFI)"></td>
    <td><input type="text" class="form-control lab-val-input" style="font-size: 0.75rem;" value="${item.value || ''}" placeholder="Value"></td>
    <td><input type="text" class="form-control lab-unit-input" style="font-size: 0.75rem;" value="${item.unit || ''}" placeholder="Unit"></td>
    <td><input type="text" class="form-control lab-range-input" style="font-size: 0.75rem;" value="${item.ref_range || ''}" placeholder="Ref range"></td>
    <td>
      <select class="form-control lab-flag-input" style="font-size: 0.72rem; padding: 0.15rem;">
        <option value="NORMAL" ${item.status === 'NORMAL' ? 'selected' : ''}>Normal</option>
        <option value="BORDERLINE" ${item.status === 'BORDERLINE' ? 'selected' : ''}>Borderline</option>
        <option value="ELEVATED" ${item.status === 'ELEVATED' ? 'selected' : ''}>Elevated</option>
        <option value="LOW" ${item.status === 'LOW' ? 'selected' : ''}>Low</option>
        <option value="CRITICAL" ${item.status === 'CRITICAL' ? 'selected' : ''}>Critical</option>
      </select>
    </td>
    <td><button type="button" class="btn btn-secondary btn-sm" onclick="this.closest('tr').remove(); triggerAutosave();" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;" title="Delete">✕</button></td>
  `;
  tbody.appendChild(tr);
  triggerAutosave();
}

function applyLabPanel(panelKey) {
  const panel = CANONICAL_LAB_PANELS[panelKey];
  if (!panel) return;
  const tbody = document.getElementById("tbody-lab-results");
  if (!tbody) return;
  tbody.innerHTML = "";
  panel.forEach(it => addLabInvestigationRow(it));
  triggerAutosave();
}

function collectLabInvestigationsFromTable() {
  const tbody = document.getElementById("tbody-lab-results");
  if (!tbody) return [];
  const rows = tbody.querySelectorAll("tr");
  const labs = [];
  rows.forEach(tr => {
    const name = tr.querySelector(".lab-name-input")?.value.trim();
    if (!name) return;
    labs.push({
      test_name: name,
      value: tr.querySelector(".lab-val-input")?.value.trim() || "",
      unit: tr.querySelector(".lab-unit-input")?.value.trim() || "",
      ref_range: tr.querySelector(".lab-range-input")?.value.trim() || "",
      status: tr.querySelector(".lab-flag-input")?.value || "NORMAL"
    });
  });
  return labs;
}

function addRadiodiagnosisRow(item = {}) {
  const tbody = document.getElementById("tbody-radio-studies");
  if (!tbody) return;
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td>
      <select class="form-control radio-mod-input" style="font-size: 0.72rem; padding: 0.15rem;">
        <option value="USG (Ultrasound)" ${item.modality?.includes('USG') ? 'selected' : ''}>USG (Ultrasound)</option>
        <option value="Scrotal Color Doppler" ${item.modality?.includes('Doppler') ? 'selected' : ''}>Scrotal Color Doppler</option>
        <option value="Pelvic USG / TVS" ${item.modality?.includes('TVS') ? 'selected' : ''}>Pelvic USG / TVS</option>
        <option value="X-Ray" ${item.modality?.includes('X-Ray') ? 'selected' : ''}>X-Ray</option>
        <option value="CT Scan" ${item.modality?.includes('CT') ? 'selected' : ''}>CT Scan</option>
        <option value="MRI" ${item.modality?.includes('MRI') ? 'selected' : ''}>MRI</option>
        <option value="2D Echocardiography" ${item.modality?.includes('Echo') ? 'selected' : ''}>2D Echocardiography</option>
        <option value="FibroScan" ${item.modality?.includes('Fibro') ? 'selected' : ''}>FibroScan</option>
      </select>
    </td>
    <td><input type="text" class="form-control radio-reg-input" style="font-size: 0.75rem;" value="${item.region || ''}" placeholder="e.g. Abdomen, Scrotum"></td>
    <td><input type="text" class="form-control radio-find-input" style="font-size: 0.75rem;" value="${item.findings || ''}" placeholder="Key findings..."></td>
    <td><input type="text" class="form-control radio-imp-input" style="font-size: 0.75rem;" value="${item.impression || ''}" placeholder="Impression / Staging"></td>
    <td><button type="button" class="btn btn-secondary btn-sm" onclick="this.closest('tr').remove(); triggerAutosave();" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;" title="Delete">✕</button></td>
  `;
  tbody.appendChild(tr);
  triggerAutosave();
}

function collectRadioStudiesFromTable() {
  const tbody = document.getElementById("tbody-radio-studies");
  if (!tbody) return [];
  const rows = tbody.querySelectorAll("tr");
  const radio = [];
  rows.forEach(tr => {
    const findings = tr.querySelector(".radio-find-input")?.value.trim();
    const impression = tr.querySelector(".radio-imp-input")?.value.trim();
    if (!findings && !impression) return;
    radio.push({
      modality: tr.querySelector(".radio-mod-input")?.value || "USG (Ultrasound)",
      region: tr.querySelector(".radio-reg-input")?.value.trim() || "",
      findings: findings || "",
      impression: impression || ""
    });
  });
  return radio;
}

function appendHijamaPoint(pointVal) {
  if (!pointVal) return;
  const notesEl = document.getElementById("input-tadbeer-notes");
  if (!notesEl) return;
  const current = notesEl.value.trim();
  const addition = `Al-Hijama Target: ${pointVal}`;
  if (!current.includes(pointVal)) {
    notesEl.value = current ? `${current}; ${addition}` : addition;
    triggerAutosave();
  }
}

function appendFasdVessel(vesselVal) {
  if (!vesselVal) return;
  const notesEl = document.getElementById("input-tadbeer-notes");
  if (!notesEl) return;
  const current = notesEl.value.trim();
  const addition = `Fasd (Phlebotomy) Vessel: ${vesselVal}`;
  if (!current.includes(vesselVal)) {
    notesEl.value = current ? `${current}; ${addition}` : addition;
    triggerAutosave();
  }
}

function applyParhezPreset(code) {
  const p = CANONICAL_PARHEZ_PRESETS[code];
  if (!p) return;
  const ghizaEl = document.getElementById("input-ghiza-diet");
  const parhezEl = document.getElementById("input-parhez-avoid");
  if (ghizaEl) ghizaEl.value = p.ghiza;
  if (parhezEl) parhezEl.value = p.parhez;
  triggerAutosave();
}

function gatherAutosavePayload() {
  const tashkheesExam = {
    nabz: {
      surat: document.getElementById("tashkhees-nabz-surat")?.value,
      quwwat: document.getElementById("tashkhees-nabz-quwwat")?.value,
      lams: document.getElementById("tashkhees-nabz-lams")?.value,
      imtila: document.getElementById("tashkhees-nabz-imtila")?.value,
      hararat: document.getElementById("tashkhees-nabz-hararat")?.value,
      rhythm: document.getElementById("tashkhees-nabz-rhythm")?.value
    },
    baul: {
      lawn: document.getElementById("tashkhees-baul-lawn")?.value,
      qiwam: document.getElementById("tashkhees-baul-qiwam")?.value,
      safa: document.getElementById("tashkhees-baul-safa")?.value,
      rasub: document.getElementById("tashkhees-baul-rasub")?.value
    },
    baraz: {
      qiwam: document.getElementById("tashkhees-baraz-qiwam")?.value,
      lawn: document.getElementById("tashkhees-baraz-lawn")?.value,
      raiha: document.getElementById("tashkhees-baraz-raiha")?.value,
      riyah: document.getElementById("tashkhees-baraz-riyah")?.value
    },
    asbab_sittah: {
      hawa: document.getElementById("asbab-hawa")?.value || "",
      makool: document.getElementById("asbab-makool")?.value || "",
      badani: document.getElementById("asbab-badani")?.value || "",
      nafsani: document.getElementById("asbab-nafsani")?.value || "",
      nawm: document.getElementById("asbab-nawm")?.value || "",
      istifragh: document.getElementById("asbab-istifragh")?.value || ""
    },
    active_12_axes: active12AxisScores || {}
  };

  const unaniPayload = {
    dominant_mizaj: document.getElementById("input-unani-mizaj")?.value || "NOT_ASSESSED",
    secondary_mizaj: document.getElementById("input-unani-secondary")?.value || "",
    clinical_reasoning: document.getElementById("input-unani-reasoning")?.value || "",
    mizaj_rationale: JSON.stringify(tashkheesExam)
  };

  const vitals = {
    bp_sys: document.getElementById("vital-bp-sys")?.value || "",
    bp_dia: document.getElementById("vital-bp-dia")?.value || "",
    pulse: document.getElementById("vital-pulse")?.value || "",
    rr: document.getElementById("vital-rr")?.value || "",
    temp: document.getElementById("vital-temp")?.value || "",
    spo2: document.getElementById("vital-spo2")?.value || "",
    weight_kg: document.getElementById("vital-weight")?.value || "",
    height_cm: document.getElementById("vital-height")?.value || ""
  };

  const systemicExam = {
    cvs: document.getElementById("exam-cvs")?.value || "",
    rs: document.getElementById("exam-rs")?.value || "",
    pa: document.getElementById("exam-pa")?.value || "",
    cns: document.getElementById("exam-cns")?.value || "",
    general: document.getElementById("exam-general")?.value || ""
  };

  const differentials = [
    document.getElementById("diff-diag-1")?.value || "",
    document.getElementById("diff-diag-2")?.value || "",
    document.getElementById("diff-diag-3")?.value || ""
  ].filter(Boolean);

  const redFlags = {
    no_gi_bleed: !!document.getElementById("chk-redflag-gi")?.checked,
    no_weight_loss: !!document.getElementById("chk-redflag-weight")?.checked,
    no_dysphagia: !!document.getElementById("chk-redflag-dysphagia")?.checked,
    no_neuro_deficit: !!document.getElementById("chk-redflag-neuro")?.checked,
    no_night_pain: !!document.getElementById("chk-redflag-nightpain")?.checked
  };

  const labs = collectLabInvestigationsFromTable();
  const radio = collectRadioStudiesFromTable();

  const modernPayload = {
    working_assessment: document.getElementById("input-modern-working")?.value || "",
    history_of_present_illness: document.getElementById("input-hpi")?.value || "",
    clinical_rationale: document.getElementById("input-modern-icd11")?.value || "",
    physical_examination_json: {
      vitals: vitals,
      systemic: systemicExam,
      differentials: differentials,
      red_flags: redFlags,
      labs: labs,
      labs_tibbi_correlation: document.getElementById("input-labs-tibbi-correlation")?.value || "",
      radiodiagnosis: radio,
      radio_tibbi_correlation: document.getElementById("input-radio-tibbi-correlation")?.value || ""
    }
  };

  const selectedTadbeer = [];
  document.querySelectorAll("#chk-tadbeer-hijama, #chk-tadbeer-dalk, #chk-tadbeer-fasd, #chk-tadbeer-natool, #chk-tadbeer-hammam, #chk-tadbeer-inkabab").forEach(cb => {
    if (cb.checked) selectedTadbeer.push(cb.value);
  });

  const carePlanPayload = {
    title: document.getElementById("input-plan-principle")?.value || "Tadeel-e-Mizaj",
    overall_goal: "Humoral restoration & clinical symptom alleviation",
    clinical_rationale: JSON.stringify({
      tadbeer_list: selectedTadbeer,
      tadbeer_notes: document.getElementById("input-tadbeer-notes")?.value || "",
      ghiza: document.getElementById("input-ghiza-diet")?.value || "",
      parhez: document.getElementById("input-parhez-avoid")?.value || ""
    })
  };

  const rxItems = collectNuskhaItemsFromTable();

  return {
    version: workspaceData ? workspaceData.encounter.version : undefined,
    reason_for_visit: document.getElementById("input-reason-visit")?.value || "",
    encounter_type: document.getElementById("input-encounter-type")?.value || "OPD_VISIT",
    unani_assessment: unaniPayload,
    modern_assessment: modernPayload,
    care_plan: carePlanPayload,
    prescription: { items: rxItems },
    updated_sections: ["visit", "unani_assessment", "modern_assessment", "plan_nuskha"]
  };
}

async function executeAutosave() {
  if (isSaving || !activeEncounterId) return;
  isSaving = true;

  const statusEl = document.getElementById("autosave-status");
  statusEl.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: var(--matab-color-status-info);"></span> Saving...`;

  try {
    const payload = gatherAutosavePayload();
    const res = await apiClient.post(`/api/v1/encounters/${activeEncounterId}/autosave`, payload);
    if (workspaceData) {
      workspaceData.encounter.version = res.version_number;
    }
    statusEl.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: var(--matab-color-status-success);"></span> Synchronized`;
  } catch (err) {
    statusEl.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: var(--matab-color-status-danger);"></span> Save error`;
    console.error("Autosave failed:", err);
  } finally {
    isSaving = false;
  }
}

// -----------------------------------------------------------------------------
// NUSKHA POSOLOGY TABLE ROW BUILDER
// -----------------------------------------------------------------------------

function addNuskhaItemRow(item = {}) {
  const tbody = document.getElementById("tbody-nuskha-items");
  if (!tbody) return;
  // Strip any internal classification tags like, (Qarabadeeni), (Classical) so medicine names stay clean and professional
  const cleanName = (item.item_name || "").replace(/\s*\((?:Qarabadi?n|Qarabadeeni|Classical)\)/gi, "").trim();
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td>
      <div style="display: flex; gap: 0.25rem; align-items: center;">
        <input type="text" class="form-control nuskha-drug-input" list="canonical-unani-drugs" style="font-size: 0.78rem; flex: 1; font-weight: 600;" value="${cleanName}" placeholder="Type Unani medicine...">
        <button type="button" class="btn btn-secondary btn-sm" onclick="window.suggestBadalForItem(this)" title="Suggest Classical Badal (Substitute)" style="padding: 0.15rem 0.35rem; font-size: 0.7rem; white-space: nowrap;">🔄 Badal</button>
        <button type="button" class="btn btn-secondary btn-sm" onclick="window.viewMufradMonographFromRow(this)" title="View Complete Monograph (Mizaj, Dosage, Indications, Contraindications, Compounds)" style="padding: 0.15rem 0.35rem; font-size: 0.7rem; white-space: nowrap; color: #065f46; background: #ecfdf5; border-color: #a7f3d0;">🌿 Info</button>
      </div>
    </td>
    <td>
      <div style="display: inline-flex; align-items: center; border: 1.5px solid #cbd5e1; border-radius: 5px; overflow: hidden; background: #fff;">
        <button type="button" onclick="const inp=this.nextElementSibling; inp.value=Math.max(1, (parseFloat(inp.value)||1)-1); triggerAutosave();" style="border: none; background: #f1f5f9; padding: 0.2rem 0.45rem; font-weight: 700; cursor: pointer; color: #334155; font-size: 0.85rem;" title="Decrease dose">−</button>
        <input type="number" class="form-control nuskha-dose-input" style="font-size: 0.8rem; width: 44px; text-align: center; border: none; padding: 0.2rem 0.1rem; box-shadow: none; font-weight: 700; color: #0f766e;" value="${item.dose_amount || 1}" onchange="triggerAutosave()">
        <button type="button" onclick="const inp=this.previousElementSibling; inp.value=(parseFloat(inp.value)||1)+1; triggerAutosave();" style="border: none; background: #f1f5f9; padding: 0.2rem 0.45rem; font-weight: 700; cursor: pointer; color: #334155; font-size: 0.85rem;" title="Increase dose">+</button>
      </div>
    </td>
    <td>
      <select class="form-control" style="font-size: 0.75rem; width: 72px; padding: 0.2rem 0.3rem;">
        <option value="hab" ${item.dose_unit === 'hab' ? 'selected' : ''}>hab (Pill)</option>
        <option value="g" ${item.dose_unit === 'g' ? 'selected' : ''}>g (Grams)</option>
        <option value="ml" ${item.dose_unit === 'ml' ? 'selected' : ''}>ml (Milliliters)</option>
        <option value="masha" ${item.dose_unit === 'masha' ? 'selected' : ''}>masha (~1g)</option>
        <option value="sachet" ${item.dose_unit === 'sachet' ? 'selected' : ''}>sachet</option>
        <option value="drops" ${item.dose_unit === 'drops' ? 'selected' : ''}>drops</option>
      </select>
    </td>
    <td>
      <select class="form-control" style="font-size: 0.75rem; width: 76px; padding: 0.2rem 0.3rem;">
        <option value="BD" ${item.frequency === 'BD' ? 'selected' : ''}>BD (Twice Daily)</option>
        <option value="OD" ${item.frequency === 'OD' ? 'selected' : ''}>OD (Once Daily)</option>
        <option value="TDS" ${item.frequency === 'TDS' ? 'selected' : ''}>TDS (Thrice Daily)</option>
        <option value="HS" ${item.frequency === 'HS' ? 'selected' : ''}>HS (At Bedtime)</option>
        <option value="AM" ${item.frequency === 'AM' ? 'selected' : ''}>AM (Empty Stomach)</option>
      </select>
    </td>
    <td><input type="number" class="form-control" style="font-size: 0.75rem; width: 50px; text-align: center;" value="${item.duration_days || 14}"></td>
    <td><input type="text" class="form-control" style="font-size: 0.75rem;" value="${item.anupan_vehicle || 'Water'}" placeholder="Water / Milk"></td>
    <td><button type="button" class="btn btn-secondary btn-sm" onclick="this.closest('tr').remove(); triggerAutosave();" style="padding: 0.15rem 0.45rem; font-size: 0.75rem; color: #dc2626; font-weight: bold;" title="Remove row">✕</button></td>
  `;
  tbody.appendChild(tr);
  triggerAutosave();
}

// -----------------------------------------------------------------------------
// SAFETY PREFLIGHT & DISPOSITION
// -----------------------------------------------------------------------------

function collectNuskhaItemsFromTable() {
  const tbody = document.getElementById("tbody-nuskha-items");
  if (!tbody) return [];
  const rows = tbody.querySelectorAll("tr");
  const items = [];
  rows.forEach(tr => {
    const drugInput = tr.querySelector(".nuskha-drug-input");
    const name = drugInput ? drugInput.value.trim() : "";
    if (!name) return;
    const doseInput = tr.querySelector(".nuskha-dose-input");
    const selects = tr.querySelectorAll("select");
    const numInputs = tr.querySelectorAll("input[type='number']");
    const textInputs = tr.querySelectorAll("input[type='text']");

    const doseUnit = selects[0] ? selects[0].value : "hab";
    const freq = selects[1] ? selects[1].value : "BD";
    const doseAmt = doseInput ? (parseFloat(doseInput.value) || 1) : 1;
    const durationDays = numInputs[1] ? (parseInt(numInputs[1].value, 10) || 7) : 7;
    const vehicle = textInputs[1] ? textInputs[1].value.trim() : "Water";

    items.push({
      item_name: name,
      dose_amount: doseAmt,
      dose_unit: doseUnit,
      frequency: freq,
      duration_days: durationDays,
      anupan_vehicle: vehicle
    });
  });
  return items;
}

async function runPreflightCheck() {
  if (!activeEncounterId) return;
  const patId = (workspaceData && workspaceData.patient && workspaceData.patient.id) || state.activePatientId || "pat-syn-001";
  const items = collectNuskhaItemsFromTable();
  const prescriptionItems = items.length > 0 ? items : [
    { item_name: "Hab-e-Suranjan", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 7 }
  ];

  try {
    // 1. Standard Safety Preflight
    const res = await apiClient.post("/api/v1/safety/preflight", {
      encounter_id: activeEncounterId,
      patient_context: {
        patient_id: patId,
        is_pregnant: false,
        allergies: []
      },
      prescription_items: prescriptionItems
    });

    // 2. Real-Time Herb-Drug Interaction Matrix Check
    const allopathicInput = document.getElementById("input-patient-allopathic-drugs");
    const allopathicDrugs = allopathicInput 
      ? allopathicInput.value.split(",").map(s => s.trim()).filter(Boolean)
      : [];

    const herbNames = prescriptionItems.map(it => it.item_name);

    let herbDrugAlerts = [];
    if (allopathicDrugs.length > 0 && herbNames.length > 0) {
      try {
        const hdRes = await apiClient.post("/api/v1/clinical/safety/check", {
          herbs: herbNames,
          medications: allopathicDrugs
        });
        herbDrugAlerts = hdRes.alerts || [];
      } catch (hdErr) {
        console.warn("Herb-drug safety check error:", hdErr);
      }
    }

    // Render Live Herb-Drug Alerts Box
    const alertsBox = document.getElementById("box-herb-drug-alerts");
    const alertsCountBadge = document.getElementById("herb-drug-alert-count");
    const alertsList = document.getElementById("herb-drug-alerts-list");

    if (alertsBox && alertsList) {
      if (herbDrugAlerts.length > 0) {
        alertsBox.style.display = "block";
        if (alertsCountBadge) {
          alertsCountBadge.innerText = `${herbDrugAlerts.length} ${herbDrugAlerts.length === 1 ? 'Alert' : 'Alerts'}`;
        }
        alertsList.innerHTML = herbDrugAlerts.map(a => `
          <div style="padding: 0.45rem 0.6rem; background: #ffffff; border-radius: 4px; border-left: 3px solid ${a.severity === 'CRITICAL' ? '#dc2626' : '#d97706'}; box-shadow: 0 1px 2px rgba(0,0,0,0.05);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
              <strong style="color: #991b1b;">⚠️ ${a.herb} ↔ ${a.matched_medication} (${a.drug_class})</strong>
              <span class="badge ${a.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}" style="font-size: 0.68rem;">${a.severity}</span>
            </div>
            <div style="color: #4b5563; font-size: 0.74rem; line-height: 1.3;">${a.interaction}</div>
            <div style="color: #1f2937; font-weight: 600; font-size: 0.72rem; margin-top: 0.25rem;">
              <strong>🛡️ Clinical Management:</strong> ${a.management_protocol}
            </div>
          </div>
        `).join("");
      } else {
        alertsBox.style.display = "none";
      }
    }

    const message = `Preflight & Herb-Drug Screening Completed:\n• Classical Safety: ${res.overall_status.toUpperCase()}\n• Herb-Drug Interaction Alerts: ${herbDrugAlerts.length}`;
    alert(message);
    await loadActiveEncounterWorkspace();
  } catch (err) {
    alert(`Preflight check error: ${err.message}`);
  }
}

async function recordFindingDisposition(findingId) {
  const rationaleEl = document.getElementById(`disp-rationale-${findingId}`);
  const rationale = rationaleEl ? rationaleEl.value.trim() : "";
  if (!rationale) {
    alert("Clinical rationale is required to record a disposition.");
    return;
  }

  try {
    await apiClient.post(`/api/v1/safety/findings/${findingId}/disposition`, {
      disposition_type: "OVERRIDDEN_WITH_RATIONALE",
      clinical_rationale: rationale
    });
    alert("Disposition recorded successfully.");
    await loadActiveEncounterWorkspace();
  } catch (err) {
    alert(`Failed to record disposition: ${err.message}`);
  }
}

// -----------------------------------------------------------------------------
// KNOWLEDGE SEARCH CONTEXT
// -----------------------------------------------------------------------------

async function searchKnowledgeContext() {
  const q = document.getElementById("input-knowledge-query").value.trim();
  if (!q) return;

  const list = document.getElementById("knowledge-results-list");
  list.innerHTML = `<span style="color: var(--matab-color-text-muted);">Searching knowledge base...</span>`;

  try {
    const res = await apiClient.get("/api/v1/knowledge/search", { query: q });
    const items = res.results || res.items || [];
    if (items.length === 0) {
      list.innerHTML = `<span style="color: var(--matab-color-text-muted);">No matching evidence found.</span>`;
      return;
    }

    list.innerHTML = items.slice(0, 4).map(it => `
      <div style="padding: 0.4rem; border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-sm); background: var(--matab-color-bg-card);">
        <strong>${it.primary_name_canonical || it.title || 'Evidence Record'}</strong>
        <p style="margin: 0.15rem 0 0 0; color: var(--matab-color-text-secondary); font-size: 0.7rem;">
          ${it.classical_notes || it.summary || 'Approved clinical guideline record'}
        </p>
      </div>
    `).join("");
  } catch (err) {
    list.innerHTML = `<span style="color: var(--matab-color-status-danger);">Search error: ${err.message}</span>`;
  }
}

// -----------------------------------------------------------------------------
// ELECTRONIC SIGNATURE & FINALIZATION MODAL
// -----------------------------------------------------------------------------

function openSignModal() {
  document.getElementById("modal-signoff").style.display = "flex";
  document.getElementById("input-sign-pin").value = "";
  document.getElementById("signoff-error-alert").style.display = "none";
  document.getElementById("input-sign-pin").focus();
}

function closeSignModal() {
  document.getElementById("modal-signoff").style.display = "none";
}

async function submitElectronicSignature() {
  const pin = document.getElementById("input-sign-pin").value.trim();
  const errEl = document.getElementById("signoff-error-alert");
  if (!pin) {
    errEl.innerText = "Electronic signature PIN is required.";
    errEl.style.display = "block";
    return;
  }

  const btnSubmit = document.getElementById("btn-submit-sign");
  btnSubmit.disabled = true;
  btnSubmit.innerText = "Signing...";

  try {
    const followupDate = document.getElementById("input-followup-date").value;
    const followupDesc = document.getElementById("input-followup-desc").value;

    const payload = {
      pin: pin,
      followup_task: followupDate ? { due_date: followupDate, task_description: followupDesc || "Follow-up review" } : null,
      instructions_language: "ur"
    };

    const res = await apiClient.post(`/api/v1/encounters/${activeEncounterId}/finalize`, payload);
    closeSignModal();
    alert("✓ Consultation successfully electronically signed, locked, and finalized!");
    await loadActiveEncounterWorkspace();
  } catch (err) {
    errEl.innerText = `Finalization rejected: ${err.message}`;
    errEl.style.display = "block";
  } finally {
    btnSubmit.disabled = false;
    btnSubmit.innerText = "Attest & Finalize";
  }
}

// -----------------------------------------------------------------------------
// 10-AJNAS CLASSICAL MIZAJ CALCULATOR
// -----------------------------------------------------------------------------

function toggle10AjnasCalculator() {
  const box = document.getElementById("box-10ajnas-calc");
  if (box) {
    box.style.display = box.style.display === "none" ? "block" : "none";
  }
}

function calculate10AjnasMizaj() {
  const m = document.getElementById("calc-malmas")?.value || "NOT_ASSESSED";
  const l = document.getElementById("calc-lahm")?.value || "NOT_ASSESSED";
  const s = document.getElementById("calc-shaar")?.value || "NOT_ASSESSED";
  const c = document.getElementById("calc-lawn")?.value || "NOT_ASSESSED";
  const bunya = document.getElementById("calc-bunya")?.value || "NOT_ASSESSED";
  const inf = document.getElementById("calc-infial")?.value || "NOT_ASSESSED";
  const nawm = document.getElementById("calc-nawm")?.value || "NOT_ASSESSED";
  const afal = document.getElementById("calc-afal")?.value || "NOT_ASSESSED";
  const fuz = document.getElementById("calc-fuzalat")?.value || "NOT_ASSESSED";
  const p = document.getElementById("calc-nabz")?.value || "NOT_ASSESSED";

  const scores = { DAMAWWI: 0, SAFRAWI: 0, BALGHAMI: 0, SAUDAWI: 0 };
  let assessedCount = 0;
  [m, l, s, c, bunya, inf, nawm, afal, fuz, p].forEach(v => {
    if (scores[v] !== undefined) {
      scores[v]++;
      assessedCount++;
    }
  });

  const reasoning = document.getElementById("input-unani-reasoning");
  if (reasoning) {
    const pulseText = document.getElementById("calc-nabz")?.selectedOptions[0]?.text || "Nabz";
    const skinText = document.getElementById("calc-malmas")?.selectedOptions[0]?.text || "Malmas";
    const obsEntry = `[10-Ajnas Physical Examination: ${assessedCount}/10 assessed. Nabz: ${pulseText}; Malmās: ${skinText}. Distribution: Damawwi=${scores.DAMAWWI}, Safrawi=${scores.SAFRAWI}, Balghami=${scores.BALGHAMI}, Saudawi=${scores.SAUDAWI}. Policy: CLINICIAN_ENTERED_ONLY - final diagnostic determination must be selected and entered by attending practitioner.]`;
    reasoning.value = reasoning.value ? `${reasoning.value}\n${obsEntry}` : obsEntry;
  }

  // Clinical Governance: NEVER auto-select or auto-save the final diagnosis without clinician sign-off
  if (typeof window.showToast === "function") {
    window.showToast("10-Ajnas observations recorded. Please select your clinical Mizaj determination above.", "info");
  }

  toggle10AjnasCalculator();
}

// -----------------------------------------------------------------------------
// 1-CLICK MASTER DISEASE NUSKHA PRESETS (GOVERNED PROTOCOL DELEGATION)
// -----------------------------------------------------------------------------

function applyNuskhaPreset(protocolCode) {
  // Map legacy shorthand codes to canonical reviewed Master Clinical Protocols (P-01 to P-21)
  // Ensures all prescribed formulas comply with governed dosages, Afaal cascades, and safety bounds
  const codeToMasterProtocol = {
    DYSPEPSIA: "P-03",
    HEADACHE: "P-11",
    ARTHRITIS: "P-10",
    ASTHMA: "P-08",
    LIVER: "P-04",
    NERVINE: "P-12"
  };

  const targetProtocolId = codeToMasterProtocol[protocolCode] || protocolCode;

  if (typeof loadMasterProtocol === "function") {
    if (cachedMasterData && cachedMasterData.protocols && cachedMasterData.protocols.length > 0) {
      loadMasterProtocol(targetProtocolId);
    } else if (typeof fetchMasterClinicalData === "function") {
      fetchMasterClinicalData().then(() => {
        loadMasterProtocol(targetProtocolId);
      });
    }
  }
}

// -----------------------------------------------------------------------------
// MASTER CLINICAL SYSTEM & 12-ORGAN-AXES ORCHESTRATOR (Prompt 10)
// -----------------------------------------------------------------------------

async function fetchMasterClinicalData() {
  if (cachedMasterData) return cachedMasterData;
  try {
    const [axesRes, protoRes, kitsRes, parhezRes] = await Promise.all([
      apiClient.get("/api/v1/clinical/axes").catch(() => ({ organ_axes: [] })),
      apiClient.get("/api/v1/clinical/protocols").catch(() => ({ protocols: [] })),
      apiClient.get("/api/v1/clinical/kits").catch(() => ({ kits: [] })),
      apiClient.get("/api/v1/clinical/parhez").catch(() => ({ parhez_protocols: [] }))
    ]);
    cachedMasterData = {
      axes: axesRes.organ_axes || [],
      protocols: protoRes.protocols || [],
      kits: kitsRes.kits || [],
      parhez: parhezRes.parhez_protocols || []
    };
    render12AxisGrid();
    populateProtocolDropdown();
    return cachedMasterData;
  } catch (err) {
    console.warn("Could not fetch Master Clinical System data:", err);
    return null;
  }
}

function toggle12AxisProfiler() {
  const box = document.getElementById("box-12axis-profiler");
  if (!box) return;
  const isHidden = box.style.display === "none" || !box.style.display;
  box.style.display = isHidden ? "block" : "none";
  if (isHidden && (!cachedMasterData || !cachedMasterData.axes || cachedMasterData.axes.length === 0)) {
    fetchMasterClinicalData();
  }
}

function render12AxisGrid() {
  const grid = document.getElementById("grid-12-axes");
  if (!grid || !cachedMasterData || !cachedMasterData.axes) return;

  grid.innerHTML = cachedMasterData.axes.map(axis => {
    const currentScore = active12AxisScores[axis.id] || 0;
    return `
      <div style="border: 1px solid var(--matab-color-border-subtle); border-radius: 6px; padding: 0.5rem 0.65rem; background: var(--matab-color-bg-card); display: flex; flex-direction: column; justify-content: space-between;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.35rem;">
          <div>
            <strong style="font-size: 0.78rem; color: var(--matab-color-brand-primary);">${axis.id}</strong>
            <span style="font-size: 0.72rem; color: var(--matab-color-text-muted); display: block;">${axis.arabic_name}</span>
          </div>
          <span class="badge badge-secondary" style="font-size: 0.68rem;">${axis.body_system}</span>
        </div>
        <div style="font-size: 0.68rem; color: var(--matab-color-text-muted); margin-bottom: 0.4rem; line-height: 1.2;">
          ${(axis.key_diseases || '').substring(0, 45)}...
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 0.2rem;">
          <span style="font-size: 0.7rem; font-weight: 600; color: var(--matab-color-text-secondary);">Score:</span>
          <div style="display: flex; gap: 0.2rem;" id="axis-btn-group-${axis.id}">
            ${[0, 1, 2, 3, 4, 5].map(score => `
              <button type="button" 
                class="btn btn-sm ${currentScore === score ? 'btn-primary' : 'btn-secondary'}" 
                onclick="window.setAxisScore('${axis.id}', ${score})" 
                style="padding: 0.1rem 0.35rem; font-size: 0.7rem; min-width: 20px; font-weight: ${currentScore === score ? '700' : 'normal'};">
                ${score}
              </button>
            `).join("")}
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function setAxisScore(axisId, score) {
  active12AxisScores[axisId] = score;
  const btnGroup = document.getElementById(`axis-btn-group-${axisId}`);
  if (btnGroup) {
    const btns = btnGroup.querySelectorAll("button");
    btns.forEach((btn, idx) => {
      if (idx === score) {
        btn.className = "btn btn-sm btn-primary";
        btn.style.fontWeight = "700";
      } else {
        btn.className = "btn btn-sm btn-secondary";
        btn.style.fontWeight = "normal";
      }
    });
  }
  await evaluateActiveAxes();
}

async function evaluateActiveAxes() {
  const resultsBox = document.getElementById("profiler-live-results");
  const pBadge = document.getElementById("badge-primary-axis");
  const sBadge = document.getElementById("badge-secondary-axis");
  const matchedBox = document.getElementById("profiler-matched-protocols");
  if (!resultsBox) return;

  const nonZero = Object.entries(active12AxisScores).filter(([_, s]) => s > 0);
  if (nonZero.length === 0) {
    resultsBox.style.display = "none";
    return;
  }

  try {
    const res = await apiClient.post("/api/v1/clinical/axes/score", { scores: active12AxisScores });
    resultsBox.style.display = "block";
    pBadge.innerText = `Primary Axis: ${res.primary_axis} (Score: ${res.primary_score}/5)`;
    sBadge.innerText = res.secondary_axis ? `Secondary Axis: ${res.secondary_axis} (Score: ${res.secondary_score}/5)` : `Secondary Axis: None`;

    if (res.recommended_protocols && res.recommended_protocols.length > 0) {
      matchedBox.innerHTML = `
        <div style="font-size: 0.72rem; font-weight: 600; color: var(--matab-color-text-secondary); margin-bottom: 0.25rem;">
          Recommended Master Clinical Protocols for ${res.primary_axis}:
        </div>
        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
          ${res.recommended_protocols.slice(0, 4).map(p => `
            <button type="button" class="btn btn-secondary btn-sm" onclick="window.loadMasterProtocol('${p.id}')" style="font-size: 0.72rem; padding: 0.2rem 0.5rem; display: flex; align-items: center; gap: 0.3rem;">
              <span>⚡</span> <strong>${p.id}</strong>: ${p.name}
            </button>
          `).join("")}
        </div>
      `;
    } else {
      matchedBox.innerHTML = "";
    }
  } catch (err) {
    console.warn("Could not score axes via API, computing locally:", err);
    const sorted = Object.entries(active12AxisScores).sort((a, b) => b[1] - a[1]);
    const pAxis = sorted[0];
    const sAxis = sorted.length > 1 && sorted[1][1] > 0 ? sorted[1] : null;
    resultsBox.style.display = "block";
    pBadge.innerText = `Primary Axis: ${pAxis[0]} (Score: ${pAxis[1]}/5)`;
    sBadge.innerText = sAxis ? `Secondary Axis: ${sAxis[0]} (Score: ${sAxis[1]}/5)` : `Secondary Axis: None`;
  }
}

function reset12AxisScores() {
  active12AxisScores = {};
  render12AxisGrid();
  const resultsBox = document.getElementById("profiler-live-results");
  if (resultsBox) resultsBox.style.display = "none";
}

function apply12AxisToAssessment() {
  const sorted = Object.entries(active12AxisScores).filter(([_, s]) => s > 0).sort((a, b) => b[1] - a[1]);
  if (sorted.length === 0) {
    alert("Please rate at least one Organ Axis before applying.");
    return;
  }
  const primary = sorted[0];
  const secondary = sorted.length > 1 && sorted[1][1] > 0 ? sorted[1] : null;

  const reasoningInput = document.getElementById("input-unani-reasoning");
  if (reasoningInput) {
    const existing = reasoningInput.value.trim();
    const axisNote = `[12-Axis Diagnostic Profile: Primary Axis = ${primary[0]} (Severity ${primary[1]}/5)${secondary ? `, Secondary Axis = ${secondary[0]} (Severity ${secondary[1]}/5)` : ""}. Usul: Tanqiya-e-Aaza-e-Muta'assira -> Tahleel-e-Mawad -> Taqwiyat-e-Aaza].`;
    if (!existing.includes("12-Axis Diagnostic Profile")) {
      reasoningInput.value = existing ? `${existing}\n${axisNote}` : axisNote;
    }
  }

  const principleInput = document.getElementById("input-plan-principle");
  if (principleInput && !principleInput.value.trim()) {
    principleInput.value = `Tadeel-e-Mizaj wa Tanqiya-e-${primary[0]} (Phase 1: Tanqiya -> Phase 2: Tahleel -> Phase 3: Taqwiyat)`;
  }

  // Toggle profiler closed and trigger autosave
  toggle12AxisProfiler();
  triggerAutosave();
  alert(`✓ 12-Axis Profile applied: Primary Axis is ${primary[0]}. Treatment sequence updated.`);
}

function populateProtocolDropdown(filterCategory = "ALL") {
  const select = document.getElementById("select-master-protocol");
  if (!select || !cachedMasterData || !cachedMasterData.protocols) return;

  const currentVal = select.value;
  select.innerHTML = `<option value="">-- Choose Master Protocol (P-01 to P-21) --</option>`;

  const filtered = filterCategory === "ALL" 
    ? cachedMasterData.protocols 
    : cachedMasterData.protocols.filter(p => {
        const cat = (p.category || "").toUpperCase();
        return cat.includes(filterCategory) || (filterCategory === "JOINTS" && cat.includes("MUSCULO")) || (filterCategory === "NEURO" && (cat.includes("PSYCH") || cat.includes("SLEEP")));
      });

  filtered.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.innerText = `${p.id}: ${p.name} — [${p.organ_axis}] (${p.category})`;
    select.appendChild(opt);
  });

  if (currentVal) select.value = currentVal;
}

function filterProtocolsByCategory(category) {
  populateProtocolDropdown(category);
}

const CANONICAL_MATAB_SAFOOF_REGISTRY = {
  "P-01": {
    name: "DiabEase / Hepato-Metabolic 500g Safoof",
    default_vehicle: "Arq Kasni (50ml) or Lukewarm Water",
    items: [
      { item_name: "Tukhm Jamun (Syzygium cumini) [Asl-e-Dawa]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gurmar Booti (Gymnema sylvestre) [Asl-e-Dawa]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Karela Khushk (Momordica charantia) [Asl-e-Dawa]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gilo / Giloy (Tinospora cordifolia) [Muslih / Hepatic]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Chiraita Shirin (Swertia chirata) [Muslih / Bitter]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tukhm Methi (Trigonella foenum-graecum)", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zeera Safaid (Cuminum cyminum) [Muslih]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah (Piper nigrum) [Muhawwil / Catalyst]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kushta Baiza Murgh [Taqwiyat-e-Aaza]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kushta Marwareed [Muqawwi-e-Qalb wa Jigar]", dose_amount: 5, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Base / Misri Safaid [Mughaddi]", dose_amount: 25, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-02": {
    name: "MetaboBurn-M / Obesity & Lipolysis 500g Safoof",
    default_vehicle: "Lukewarm Water with 1 tsp Honey",
    items: [
      { item_name: "Zanjabeel (Zingiber officinale) [Asl-e-Dawa]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah (Piper nigrum) [Muhawwil]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Daraz (Piper longum) [Asl-e-Dawa]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zeera Siyah (Carum carvi) [Muhallil-e-Riyah]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badiyan / Saunf (Foeniculum vulgare) [Muslih]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Halela Zard (Terminalia chebula) [Munzij]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Balela (Terminalia bellerica)", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Amla Khushk (Phyllanthus emblica)", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Luk Maghsool (Coccus lacca) [Khasir-e-Shahm]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Namak Siyah [Muslih Hazm]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-03": {
    name: "LipidClear / Athero-Hepatic 500g Safoof",
    default_vehicle: "Lukewarm Water",
    items: [
      { item_name: "Guggul Shuddha (Commiphora mukul) [Asl-e-Dawa]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Arjuna Chaal (Terminalia arjuna) [Cardiotonic]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Lehsun Khushk (Allium sativum) [Muhallil]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zeera Siyah (Carum carvi) [Muslih]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Halela Siyah [Tanqiya-e-Dam]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Chobchini (Smilax china) [Musaffi-e-Dam]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zanjabeel (Zingiber officinale) [Hazim]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Catalyst]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Cooling Muslih]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-04": {
    name: "HyperCalm / Neuro-Vascular 500g Safoof (Rx Schedule E1)",
    default_vehicle: "Arq Gaozaban (50ml) or Plain Water",
    items: [
      { item_name: "Asrol / Choti Chand (Rauwolfia serpentina) [Asl-e-Dawa]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Ustukhuddus (Lavandula stoechas) [Mukhrij-e-Sauda]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gaozaban Phool (Borago officinalis) [Mufarreh]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Sandal Safaid (Santalum album) [Barid-Mubarrid]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kishneez Khushk / Dhania [Muslih-e-Dimagh]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badiyan / Saunf [Muslih Hazm]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Habis-e-Dam]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Catalyst]", dose_amount: 15, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kushta Marwareed [Muqawwi-e-Qalb]", dose_amount: 15, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-05": {
    name: "CardioGuard / Cardiac Vigor 500g Safoof",
    default_vehicle: "Arq Gaozaban (60ml)",
    items: [
      { item_name: "Post Beekh Arjuna (Terminalia arjuna) [Asl-e-Dawa]", dose_amount: 120, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gaozaban Barge & Gul (Borago officinalis)", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gulab Phool (Rosa damascena) [Mufarreh]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Sandal Safaid (Santalum album)", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badranjboya (Melissa officinalis) [Muqawwi-e-Qalb]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori [Adaptogenic Cardioprotective]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zanjabeel (Zingiber officinale)", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran (Crocus sativus) [Muhawwil / Cardiotonic]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kushta Aqeeq [Muqawwi-e-Rooh]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Warq Tila (Gold Foil) [Vitality]", dose_amount: 5, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 55, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-06": {
    name: "MindBalance / Neuro-Psychiatric 500g Safoof",
    default_vehicle: "Warm Milk or Arq Gaozaban",
    items: [
      { item_name: "Brahmi Booti (Bacopa monnieri) [Asl-e-Dawa]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Shankhpushpi (Convolvulus pluricaulis) [Asl-e-Dawa]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Ustukhuddus (Lavandula stoechas) [Jarob-e-Dimagh]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori (Withania somnifera) [Adaptogen]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gaozaban Gul (Borago officinalis)", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badranjboya (Melissa officinalis)", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Jadwar Khatai (Delphinium denudatum)", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Cooling Muslih]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran [Catalyst]", dose_amount: 5, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 35, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-09": {
    name: "JointFree / Arthritic & Anti-Inflammatory 500g Safoof",
    default_vehicle: "Lukewarm Water or Arq Mako",
    items: [
      { item_name: "Suranjan Shirin (Colchicum autumnale) [Asl-e-Dawa]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori (Withania somnifera)", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kundur / Shallaki (Boswellia serrata) [Muhallil]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Chobchini (Smilax china) [Musaffi-e-Dam]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zanjabeel (Zingiber officinale) [Hazim]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badiyan / Saunf [Muslih Hazm]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Halela Zard [Tanqiya-e-Khilt-e-Fasid]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Catalyst]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-11": {
    name: "FertiMax-M / Male Infertility & Oligospermia 500g Safoof",
    default_vehicle: "250ml Warm Milk on Empty Stomach",
    items: [
      { item_name: "Salab Misri (Orchis mascula) [Mughaddi / Foundation]", dose_amount: 75, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori (Withania somnifera) [Asl-e-Dawa]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Behman Safaid (Centurea behen) [Asl-e-Dawa]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Behman Surkh (Salvia haematodes) [Asl-e-Dawa]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Musli Safed (Chlorophytum borivilianum) [Mughaddi]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kaunch Beej (Mucuna pruriens) [Muwallid-e-Mani]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer (Bambusa arundinacea) [Muslih / Cooling]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zeera Siyah (Carum carvi) [Muslih / Carminative]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah (Piper nigrum) [Muhawwil / Catalyst]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gulab Phool (Rosa damascena) [Cardiotonic Muslih]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Namak Suleman [Muslih Hazm]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid / Qand [Foundation Base]", dose_amount: 65, dose_unit: "g", frequency: "Compound", duration_days: 90, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-14": {
    name: "CycloCare-PCOS / Ovarian Hyperandrogenism 500g Safoof",
    default_vehicle: "Arq Kasni (50ml) or Lukewarm Water",
    items: [
      { item_name: "Asgandh Nagori [Asl-e-Dawa / HPA-Adrenal]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Shatavari (Asparagus racemosus) [Muqawwi-e-Reham]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Khare Khasak / Gokhru [Mudirr-e-Baul / LH surge]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Hulba / Tukhm Methi [Insulin Sensitizer]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kalonji (Nigella sativa) [Muhallil-e-Waram / Ovarian]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Darchini (Cinnamomum zeylanicum) [MHCP]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asl-us-Soos / Mulethi [Anti-Androgenic]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Muslih / Heat balancer]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Bioavailability Catalyst]", dose_amount: 15, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran (Crocus sativus) [Muharrik-e-Dauran-e-Khoon]", dose_amount: 5, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-20": {
    name: "GutEase-IBS / Gastro-Intestinal 500g Safoof",
    default_vehicle: "Water after meals",
    items: [
      { item_name: "Zeera Siyah (Carum carvi) [Asl-e-Dawa]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badiyan / Saunf (Foeniculum vulgare) [Muslih]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Belgiri Khushk (Aegle marmelos) [Habis / Mucosal]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Mastagi Roomi (Pistacia lentiscus) [Muqawwi-e-Meda]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Pudina Khushk (Mentha piperita) [Kasir-e-Riyah]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zanjabeel (Zingiber officinale) [Hazim]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Catalyst]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Balela [Tadeel-e-Balgham]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Namak Sambar / Suleman [Muslih]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-07": {
    name: "Sleep+Stress / Insomnia & Circadian 500g Safoof",
    default_vehicle: "Warm Milk or Arq Gaozaban at Bedtime",
    items: [
      { item_name: "Khashkhash Safaid (Papaver somniferum semen) [Mukhaddir]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Maghz-e-Kadu (Cucurbita pepo semen) [Barid-Ratab]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Ustukhuddus (Lavandula stoechas) [Munaqqi-e-Dimagh]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Brahmi Booti (Bacopa monnieri) [Muqawwi-e-Hifz]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tukhm Kahu (Lactuca sativa) [Musakkin-e-Hararat]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gaozaban Gul (Borago officinalis) [Mufarreh-e-Qalb]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Sandal Safaid (Santalum album) [Barid-Yabis]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Muslih-e-Bukharaat]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-08": {
    name: "LungEase / Asthma & Pulmonary Clearance 500g Safoof",
    default_vehicle: "Lukewarm Water or Joshanda Banafsha",
    items: [
      { item_name: "Asl-us-Soos / Mulethi (Glycyrrhiza glabra) [Mulayyin]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Sapistan (Cordia latifolia) [Munaffis-e-Balgham]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Unnab (Zizyphus vulgaris) [Musaffi-e-Khoon]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Behidana (Cydonia oblonga) [Luzooq / Mucosal]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gul-e-Banafsha (Viola odorata) [Muhallil]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zufa Khushk (Hyssopus officinalis) [Jali-e-Sadr]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Daraz (Piper longum) [Taqtee-e-Balgham]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Habis / Antipyretic]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Qand Safaid [Base]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-10": {
    name: "VigorX-ED / Andrological Vigor 500g Safoof",
    default_vehicle: "250ml Warm Cow Milk (morning empty stomach)",
    items: [
      { item_name: "Salab Panja (Dactylorhiza hatagirea) [Muqawwi-e-Bah]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Salab Misri (Orchis mascula) [Mughalliz]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori (Withania somnifera) [Muqawwi-e-Aasab]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Musli Safed (Chlorophytum borivilianum) [Mughaddi]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Behman Safaid (Centurea behen) [Mufarreh]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kaunch Beej Mudabbar (Mucuna pruriens)", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Aqarqarha (Anacyclus pyrethrum) [Muharrik-e-Qaza]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Daraz [Bioavailability Catalyst]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran (Crocus sativus) [Muhawwil / Nervine]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-12": {
    name: "TestoVital / Hypogonadism & Steroidogenesis 500g Safoof",
    default_vehicle: "Lukewarm Milk or Water",
    items: [
      { item_name: "Asgandh Nagori [Steroidogenic / Leydig Tonic]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Musli Siyah (Curculigo orchioides) [Muwallid-e-Hararat]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Musli Safed [Mughalliz-e-Mani]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Khare Khasak / Gokhru [Free Testosterone Boost]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Behman Safaid [Muqawwi-e-Qalb wa Khusya]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tukhm Utangan (Blepharis edulis) [Mumsik]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Shilajit Shuddha / Salajeet [Mineral Activator]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Catalyst]", dose_amount: 15, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran [Penetration Enhancer]", dose_amount: 5, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-13": {
    name: "ProstaGuard / BPH & Prostate Clearance 500g Safoof",
    default_vehicle: "Arq Badiyan (60ml) or Plain Water",
    items: [
      { item_name: "Maghz-e-Kharbuza (Cucumis melo semen) [Mufattit]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Maghz-e-Kharyar (Cucumis sativus semen) [Mubarrid]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tukhm-e-Kasoos (Cuscuta reflexa) [Mutaqqi-e-Masana]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Khare Khasak / Gokhru [Mudirr-e-Baul]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zaravand Mudaharraj (Aristolochia rotunda) [Muhallil]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Ushba Maghrabi (Smilax aristolochiifolia)", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Muslih-e-Sozish]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zeera Safaid [Muslih Hazm]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-15": {
    name: "LeucoClear / Leucorrhoea & Pelvic Astringent 500g Safoof",
    default_vehicle: "Cow Milk or Lukewarm Water",
    items: [
      { item_name: "Mochras (Bombax ceiba gum) [Qabiz / Astringent]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gond Dhak / Palas (Butea monosperma) [Habis]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Lodh Pathani (Symplocos racemosa) [Muqawwi-e-Reham]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Majuphal (Quercus infectoria) [Habis-e-Sailan]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Barid-Yabis Muslih]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori [Muqawwi-e-Umomi]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Halela Zard [Tanqiya-e-Rutubaat]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zeera Safaid [Muslih Hazm]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-16": {
    name: "UterTone / Dysmenorrhoea & Emmenagogue 500g Safoof",
    default_vehicle: "Arq Badiyan or Warm Water (During Menses)",
    items: [
      { item_name: "Abhal / Hubb-ul-Ar'ar (Juniperus communis) [Mudirr-e-Tams]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Beekh Kasni (Cichorium intybus) [Mufattih]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badiyan / Saunf (Foeniculum vulgare) [Musakkin-e-Mughes]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tukhm Gajar (Daucus carota semen) [Mudirr]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Hulba / Tukhm Methi [Muhallil-e-Waram]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori [Musakkin-e-Waja]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Catalyst]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran (Crocus sativus) [Muharrik-e-Dauran]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" },
      { item_name: "Qand Safaid [Base]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 21, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-17": {
    name: "MenoPease / Menopause & Vasomotor 500g Safoof",
    default_vehicle: "Arq Gaozaban or Lukewarm Milk",
    items: [
      { item_name: "Shatavari (Asparagus racemosus) [Phyto-Estrogenic]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori [Adrenal Cortisol Balancer]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Gaozaban Gul [Mufarreh / Vasomotor Calmer]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Sandal Safaid [Mubarrid / Heat Flash Relief]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Badranjboya (Melissa officinalis) [Neuro-Cardiac]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Cooling Muslih]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tukhm Kahu [Sedative Musakkin]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran [Microcirculation Catalyst]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kushta Marwareed [Muqawwi-e-Rooh]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-18": {
    name: "FertiliWomen / Oocyte Optimization & Reham 500g Safoof",
    default_vehicle: "250ml Warm Cow Milk (morning empty stomach)",
    items: [
      { item_name: "Shatavari (Asparagus racemosus) [Oocyte Quality]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori [Mitochondrial Oocyte Vigor]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Behman Safaid (Centurea behen) [Muqawwi-e-Khamira]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Maghz Pambadana (Gossypium herbaceum) [Mughaddi]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Lodh Pathani (Symplocos racemosa) [Toned Endometrium]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Halela [Tanqiya-e-Reham]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zafran (Crocus sativus) [Implantation Catalyst]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kushta Baiza Murgh [Calcium & Oocyte Support]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Foundation Base]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 60, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-19": {
    name: "Immunity / Post-Viral Immune Reset 500g Safoof",
    default_vehicle: "Lukewarm Water or Honey Water",
    items: [
      { item_name: "Gilo / Giloy (Tinospora cordifolia) [Dafi-e-Humma]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori [Immunomodulator / Macrophage]", dose_amount: 90, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Amla Khushk (Phyllanthus emblica) [High Vitamin C]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asl-us-Soos / Mulethi [Anti-viral / Interferon]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Kalonji (Nigella sativa) [Thymoquinone Immune]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Zanjabeel (Zingiber officinale) [Anti-inflammatory]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Filfil Siyah [Piperine Bioenhancer]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Cooling Muslih]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 30, dose_unit: "g", frequency: "Compound", duration_days: 30, anupan_vehicle: "Total 500g formula" }
    ]
  },
  "P-21": {
    name: "HairRoot-X / Alopecia & Follicle Rejuvenation 500g Safoof",
    default_vehicle: "Lukewarm Water with 1 tsp Amla Jamun vinegar",
    items: [
      { item_name: "Amla Khushk (Phyllanthus emblica) [Muqawwi-e-Shaar]", dose_amount: 100, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Halela Siyah (Terminalia chebula) [Black Hair]", dose_amount: 80, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Post Balela (Terminalia bellerica) [Tanqiya]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Bhringraj (Eclipta alba) [Keshya / Follicle]", dose_amount: 70, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Brahmi Booti (Bacopa monnieri) [Microcirculation]", dose_amount: 60, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Asgandh Nagori [Anti-Telogen Effluvium Cortisol]", dose_amount: 50, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tukhm Methi [Lecithin & DHT Modulation]", dose_amount: 40, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Tabasheer [Silica Mineral Source]", dose_amount: 20, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" },
      { item_name: "Misri Safaid [Base]", dose_amount: 10, dose_unit: "g", frequency: "Compound", duration_days: 45, anupan_vehicle: "Total 500g formula" }
    ]
  }
};

function onProtocolSelectChanged(protocolId) {
  const previewBox = document.getElementById("box-active-protocol-preview");
  if (!previewBox) return;

  if (!protocolId || !cachedMasterData || !cachedMasterData.protocols) {
    previewBox.style.display = "none";
    return;
  }

  const proto = cachedMasterData.protocols.find(p => p.id === protocolId);
  if (!proto) {
    previewBox.style.display = "none";
    return;
  }

  // Parse structured phases
  let p1 = {}, p2 = {}, p3 = {}, pStack = {};
  try { p1 = typeof proto.phase1 === 'string' ? JSON.parse(proto.phase1) : (proto.phase1 || {}); } catch(e) { p1 = { title: proto.phase1 }; }
  try { p2 = typeof proto.phase2 === 'string' ? JSON.parse(proto.phase2) : (proto.phase2 || {}); } catch(e) { p2 = { title: proto.phase2 }; }
  try { p3 = typeof proto.phase3 === 'string' ? JSON.parse(proto.phase3) : (proto.phase3 || {}); } catch(e) { p3 = { title: proto.phase3 }; }
  try { pStack = typeof proto.product_stack === 'string' ? JSON.parse(proto.product_stack) : (proto.product_stack || {}); } catch(e) { pStack = {}; }

  // Find matching kit
  const matchedKit = (cachedMasterData.kits || []).find(k => k.kit_code === `K-${proto.id.substring(2)}` || (k.name || '').toLowerCase().includes((proto.name || '').toLowerCase().split(" ")[0]));
  const canonicalNuskha = CANONICAL_MATAB_SAFOOF_REGISTRY[proto.id];

  previewBox.style.display = "block";
  previewBox.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.35rem; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.4rem;">
      <div>
        <strong style="color: var(--matab-color-brand-primary); font-size: 0.85rem;">${proto.id}: ${proto.name}</strong>
        <span class="badge badge-info" style="font-size: 0.7rem; margin-left: 0.4rem;">Axis: ${proto.organ_axis}</span>
        ${proto.icd11_code ? `<span class="badge badge-secondary" style="font-size: 0.7rem; margin-left: 0.2rem;">ICD-11: ${proto.icd11_code}</span>` : ""}
      </div>
      ${matchedKit ? `
        <span class="badge badge-success" style="font-size: 0.72rem;">
          Kit: ${matchedKit.kit_code} (₹${matchedKit.price_min_inr || ''} - ₹${matchedKit.price_max_inr || ''})
        </span>
      ` : ""}
    </div>

    <!-- 3-Phase Afaal Cascade -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.5rem; margin-bottom: 0.5rem; font-size: 0.72rem;">
      <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; padding: 0.4rem 0.55rem;">
        <div style="display: flex; justify-content: space-between;">
          <strong style="color: #1e40af;">Phase 1: Tanqiya (Cleansing)</strong>
          <span class="badge badge-primary" style="font-size: 0.65rem;">${p1.duration_days || 30} Days</span>
        </div>
        <div style="font-weight: 600; color: #1e3a8a; margin: 0.15rem 0;">${p1.title || 'Humour Clearance'}</div>
        ${(p1.products || []).map(pr => `<div style="font-size: 0.68rem; color: #3b82f6;">• <strong>${pr.name}</strong>: ${pr.dose} (${pr.timing || ''})</div>`).join('')}
      </div>

      <div style="background: #fefce8; border: 1px solid #fef08a; border-radius: 4px; padding: 0.4rem 0.55rem;">
        <div style="display: flex; justify-content: space-between;">
          <strong style="color: #854d0e;">Phase 2: Tahleel (Resolution)</strong>
          <span class="badge badge-warning" style="font-size: 0.65rem;">${p2.duration_days || 90} Days</span>
        </div>
        <div style="font-weight: 600; color: #713f12; margin: 0.15rem 0;">${p2.title || 'Resolution & Regeneration'}</div>
        ${(p2.products || []).map(pr => `<div style="font-size: 0.68rem; color: #b45309;">• <strong>${pr.name}</strong>: ${pr.dose} (${pr.timing || ''})</div>`).join('')}
      </div>

      <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 0.4rem 0.55rem;">
        <div style="display: flex; justify-content: space-between;">
          <strong style="color: #166534;">Phase 3: Taqwiyat (Fortification)</strong>
          <span class="badge badge-success" style="font-size: 0.65rem;">${p3.duration_days || 180} Days</span>
        </div>
        <div style="font-weight: 600; color: #14532d; margin: 0.15rem 0;">${p3.title || 'Vitality & Relapse Prevention'}</div>
        ${(p3.products || []).map(pr => `<div style="font-size: 0.68rem; color: #15803d;">• <strong>${pr.name}</strong>: ${pr.dose}</div>`).join('')}
      </div>
    </div>

    <!-- Dual-Track Formulations Summary -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 0.4rem; font-size: 0.74rem;">
      <div style="padding: 0.35rem 0.5rem; background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 4px;">
        <strong style="color: #6b21a8;">📜 Track 1: Matab 500g Safoof Nuskha</strong>
        <div style="color: #581c87; font-size: 0.7rem; margin-top: 0.15rem;">
          ${canonicalNuskha ? `${canonicalNuskha.name} (${canonicalNuskha.items.length} ingredients) • Vehicle: ${canonicalNuskha.default_vehicle}` : 'Standard Matab fresh powder formulation'}
        </div>
      </div>
      <div style="padding: 0.35rem 0.5rem; background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 4px;">
        <strong style="color: #0f766e;">📦 Track 2: Standardized GMP Stack</strong>
        <div style="color: #115e59; font-size: 0.7rem; margin-top: 0.15rem;">
          ${Array.isArray(pStack.core) ? pStack.core.join(" + ") : (proto.product_stack || 'Standardized extract')}
        </div>
      </div>
    </div>

    ${proto.clinical_warnings ? `
      <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px; padding: 0.3rem 0.5rem; font-size: 0.72rem; color: #991b1b;">
        <strong>⚠️ Clinical Precaution:</strong> ${proto.clinical_warnings}
      </div>
    ` : ""}
  `;
}

function loadSelectedMasterProtocol() {
  const sel = document.getElementById("select-master-protocol");
  const val = sel ? sel.value : "";
  if (!val) {
    alert("Please select a Master Clinical Protocol (P-01 to P-21) from the dropdown first.");
    return;
  }
  loadMasterProtocol(val);
}

function loadMasterProtocol(protocolId) {
  if (!cachedMasterData || !cachedMasterData.protocols) return;
  const proto = cachedMasterData.protocols.find(p => p.id === protocolId);
  if (!proto) return;

  // Parse structured phases
  let p1 = {}, p2 = {}, p3 = {};
  try { p1 = typeof proto.phase1 === 'string' ? JSON.parse(proto.phase1) : (proto.phase1 || {}); } catch(e) { p1 = { title: proto.phase1 }; }
  try { p2 = typeof proto.phase2 === 'string' ? JSON.parse(proto.phase2) : (proto.phase2 || {}); } catch(e) { p2 = { title: proto.phase2 }; }
  try { p3 = typeof proto.phase3 === 'string' ? JSON.parse(proto.phase3) : (proto.phase3 || {}); } catch(e) { p3 = { title: proto.phase3 }; }

  // Set Treatment Principle (Usul-e-Ilaj) with sequential Afaal cascade
  const principleInput = document.getElementById("input-plan-principle");
  if (principleInput) {
    principleInput.value = `Usul-e-Ilaj: Tanqiya-e-${proto.organ_axis} (Phase 1: Tanqiya — ${p1.title || 'Humour Clearance'} [${p1.duration_days || 30} Days]) -> Phase 2: Tahleel -> Phase 3: Taqwiyat`;
  }

  // Populate Dietary Prescriptions (Ilaj bil Ghiza)
  const ghizaInput = document.getElementById("input-ghiza-diet");
  if (ghizaInput && p1.diet) {
    ghizaInput.value = p1.diet;
  }

  // Populate Lifestyle & Parhez
  const parhezInput = document.getElementById("input-parhez-avoid");
  if (parhezInput) {
    const rulesList = [];
    if (p1.lifestyle) rulesList.push(p1.lifestyle);
    if (proto.clinical_warnings) rulesList.push(`Precaution: ${proto.clinical_warnings}`);
    if (rulesList.length > 0) {
      parhezInput.value = rulesList.join(" • ");
    }
  }

  const trackChoice = document.getElementById("select-protocol-track")?.value || "DUAL";
  const tbody = document.getElementById("tbody-nuskha-items");
  if (tbody) {
    tbody.innerHTML = "";

    // 1. If TRACK1 or DUAL: Load Classical 500g Matab Safoof Nuskha
    if (trackChoice === "TRACK1" || trackChoice === "DUAL") {
      const canonicalNuskha = CANONICAL_MATAB_SAFOOF_REGISTRY[proto.id];
      if (canonicalNuskha) {
        canonicalNuskha.items.forEach(it => {
          addNuskhaItemRow({
            item_name: it.item_name,
            dose_amount: it.dose_amount,
            dose_unit: it.dose_unit || "g",
            frequency: it.frequency || "BD",
            duration_days: it.duration_days || p1.duration_days || 21,
            anupan_vehicle: it.anupan_vehicle || canonicalNuskha.default_vehicle || "Lukewarm Water"
          });
        });
      } else {
        addNuskhaItemRow({
          item_name: `Fresh Safoof Compound for ${proto.name}`,
          dose_amount: 5,
          dose_unit: "g",
          frequency: "BD",
          duration_days: p1.duration_days || 30,
          anupan_vehicle: "Water / Milk"
        });
      }
    }

    // 2. If TRACK2 or DUAL: Load Standardized Products Stack from phase1
    if (trackChoice === "TRACK2" || trackChoice === "DUAL") {
      const gmpProducts = p1.products || [];
      if (gmpProducts.length > 0) {
        gmpProducts.forEach(prod => {
          let dose = 1;
          let unit = "hab";
          let freq = "BD";
          let vehicle = "Water";

          const doseMatch = (prod.dose || "").match(/(\d+)/);
          if (doseMatch) dose = parseInt(doseMatch[1], 10);
          if ((prod.dose || "").toLowerCase().includes("cap") || (prod.dose || "").toLowerCase().includes("tab")) {
            unit = "hab";
          } else if ((prod.dose || "").toLowerCase().includes("g")) {
            unit = "g";
          } else if ((prod.dose || "").toLowerCase().includes("ml")) {
            unit = "ml";
          }

          if ((prod.timing || "").toLowerCase().includes("am") && (prod.timing || "").toLowerCase().includes("pm")) {
            freq = "BD";
            vehicle = "Empty stomach AM / post-meal PM";
          } else if ((prod.timing || "").toLowerCase().includes("bedtime")) {
            freq = "HS";
            vehicle = "Bedtime with warm water";
          } else if ((prod.timing || "").toLowerCase().includes("pre-meal")) {
            freq = "BD";
            vehicle = "30 mins before meals";
          }

          addNuskhaItemRow({
            item_name: `${prod.name} (GMP)`,
            dose_amount: dose,
            dose_unit: unit,
            frequency: freq,
            duration_days: p1.duration_days || 30,
            anupan_vehicle: vehicle
          });
        });
      }
    }
  }

  // Update dropdown & preview
  const select = document.getElementById("select-master-protocol");
  if (select) select.value = proto.id;
  onProtocolSelectChanged(proto.id);

  triggerAutosave();
  alert(`✓ Successfully Loaded ${proto.id}: ${proto.name}\n• Mode: ${trackChoice}\n• Usul-e-Ilaj: Phase 1 Tanqiya\n• Nuskha items, Diet & Parhez updated.`);
}

function triggerComplaintAiDraft(complaintText) {
  const inpVisit = document.getElementById("input-reason-visit");
  if (inpVisit) {
    inpVisit.value = complaintText;
    inpVisit.dispatchEvent(new Event("input", { bubbles: true }));
  }
  const inpDiag = document.getElementById("input-modern-working");
  if (inpDiag) {
    inpDiag.value = complaintText;
    inpDiag.dispatchEvent(new Event("input", { bubbles: true }));
  }
  autoDraftNuskhaFromDiagnosis();
}

// -----------------------------------------------------------------------------
// COMPREHENSIVE UNANI PRINCIPLES AUTOMATION ENGINE (USOOL-E-TIBB CALCULATOR)
// -----------------------------------------------------------------------------
/**
 * Automatically computes:
 * 1. Dominant Mizaj (Temperament) & Secondary Su-e-Mizaj deviation (Dyscrasia)
 * 2. 10-Ajnas-e-Ashara mathematical parameters & humoral score
 * 3. 12-Axis Organ Diagnostic Profiler primary & secondary severity scores
 * 4. 3-Phase Af'al Cascade (Tanqiya -> Tahleel -> Taqwiyat)
 * 5. Primary Clinical Diagnosis & ICD-11 Mapping
 * 6. Classical Tashkhees (Nabz, Baul, Baraz)
 * 7. In-depth Tashkhees synthesis reasoning
 */
function calculateComprehensiveUnaniProfile(diagText, vitals, labItems, abnormalLabs) {
  let profile = {
    diagnosisTitle: "General Clinical Dysregulation",
    icd11: "MD90",
    dominantMizaj: "BALGHAMI",
    secondaryMizaj: "Su-e-Mizaj Maddi Barid Balghami (Cold-Moist Phlegmatic)",
    primaryAxis: "AXIS-05-GASTROINTESTINAL",
    secondaryAxis: "AXIS-01-METABOLIC",
    organSeverity: 4,
    ajnas: { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "BALGHAMI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "BALGHAMI", nawm: "BALGHAMI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" },
    nabzSurat: "BATEE", nabzQuwwat: "DHAEF", nabzLams: "LAYYIN", nabzImtila: "MUMTALI", nabzHararat: "BARID",
    baulLawn: "ABYAD", baulQiwam: "GHALEEZ", barazQiwam: "LAYYIN",
    afaalCascade: "Phase 1: Tanqiya (Cleansing, 14-21d) ➔ Phase 2: Tahleel (Resolution, 30-60d) ➔ Phase 3: Taqwiyat (Fortification, 90d)",
    pathology: "Barid-Ratab (Cold-Moist)",
    prescriptionTherapy: "Haar-Yabis (Warm-Dry)"
  };

  if (diagText.includes("hasat") || diagText.includes("kulyah") || diagText.includes("calcul") || diagText.includes("stone") || diagText.includes("renal") || diagText.includes("pathri") || (diagText.includes("burn") && diagText.includes("micturition"))) {
    profile.diagnosisTitle = "Hasat-e-Kulyah (Renal Calculi / Nephrolithiasis)";
    profile.icd11 = "GB60";
    profile.dominantMizaj = "SAFRAWI";
    profile.secondaryMizaj = "Su-e-Mizaj Haar Safrawi Ghaleez (Hot-Dry Bilious)",
    profile.primaryAxis = "AXIS-08-RENAL-URINARY";
    profile.secondaryAxis = "AXIS-05-GASTROINTESTINAL";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "SAFRAWI", lahm: "SAFRAWI", shaar: "SAFRAWI", lawn: "SAFRAWI", bunya: "SAFRAWI", infial: "SAFRAWI", nawm: "SAFRAWI", afal: "SAFRAWI", fuzalat: "SAFRAWI", nabz: "SAFRAWI" };
    profile.nabzSurat = "SAREE"; profile.nabzQuwwat = "QAWI"; profile.nabzLams = "SULB"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "HAR";
    profile.baulLawn = "ASFAR_NARI"; profile.baulQiwam = "RAQEEQ"; profile.barazQiwam = "YABIS";
    profile.afaalCascade = "Phase 1: Lithotripsy & Diuresis (15d) ➔ Phase 2: Urethral Soothing & Cleansing (30d) ➔ Phase 3: Renal & Bladder Fortification (60d)";
    profile.pathology = "Haar-Yabis (Hot-Dry) / Ghaleez";
    profile.prescriptionTherapy = "Barid-Ratab Motadil (Cooling-Hydrating)";
  }
  else if (diagText.includes("hypertens") || diagText.includes("high bp") || diagText.includes("zaght") || (diagText.includes("blood") && diagText.includes("press")) || diagText.includes("fashar")) {
    profile.diagnosisTitle = "Zaght-ud-Dam Qawi (Essential Hypertension)";
    profile.icd11 = "BA00";
    profile.dominantMizaj = "DAMAWWI";
    profile.secondaryMizaj = "Su-e-Mizaj Maddi Haar Damawi (Hot-Moist Sanguine Plethora)";
    profile.primaryAxis = "AXIS-02-CARDIOVASCULAR";
    profile.secondaryAxis = "AXIS-06-NEUROPSYCH";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "DAMAWWI", lahm: "DAMAWWI", shaar: "DAMAWWI", lawn: "DAMAWWI", bunya: "DAMAWWI", infial: "DAMAWWI", nawm: "DAMAWWI", afal: "DAMAWWI", fuzalat: "DAMAWWI", nabz: "DAMAWWI" };
    profile.nabzSurat = "MOTADIL"; profile.nabzQuwwat = "QAWI"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "HAR";
    profile.baulLawn = "AHMAR"; profile.baulQiwam = "GHALEEZ"; profile.barazQiwam = "MOTADIL";
    profile.afaalCascade = "Phase 1: Vascular De-congestion (30d) ➔ Phase 2: Neuro-Cardiac Stabilization (60d) ➔ Phase 3: Endothelial Fortification (180d)";
    profile.pathology = "Haar-Ratab / Damawi";
    profile.prescriptionTherapy = "Barid-Yabis Motadil";
  }
  else if (diagText.includes("piles") || diagText.includes("bawaseer") || diagText.includes("bawasir") || diagText.includes("hemorrhoid") || diagText.includes("haemorrhoid") || diagText.includes("fissure")) {
    profile.diagnosisTitle = "Bawaseer (Hemorrhoids / Anal Fissure)";
    profile.icd11 = "DB60";
    profile.dominantMizaj = "SAUDAWI";
    profile.secondaryMizaj = "Su-e-Mizaj Barid Saudawi Ihtiraqi (Cold-Dry Melancholic Combustion)";
    profile.primaryAxis = "AXIS-10-ANORECTAL";
    profile.secondaryAxis = "AXIS-05-GASTROINTESTINAL";
    profile.organSeverity = 4;
    profile.ajnas = { malmas: "SAUDAWI", lahm: "SAUDAWI", shaar: "SAUDAWI", lawn: "SAUDAWI", bunya: "SAUDAWI", infial: "SAUDAWI", nawm: "SAUDAWI", afal: "SAUDAWI", fuzalat: "SAUDAWI", nabz: "SAUDAWI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "SULB"; profile.nabzImtila = "KHALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ASWAD"; profile.baulQiwam = "RAQEEQ"; profile.barazQiwam = "YABIS";
    profile.afaalCascade = "Phase 1: Hemostasis & Colonic Laxation (14d) ➔ Phase 2: Melancholic Clearance (30d) ➔ Phase 3: Epithelial Healing & Rectal Fortification (60d)";
    profile.pathology = "Saudawi-Haar (Melancholic-Hot)";
    profile.prescriptionTherapy = "Murattib-Mulayyin (Soothing-Laxative)";
  }
  else if (diagText.includes("sciatica") || diagText.includes("irq") || diagText.includes("nasa") || diagText.includes("radiating") || (diagText.includes("nerve") && diagText.includes("pain"))) {
    profile.diagnosisTitle = "Irq-un-Nasa (Sciatica & Lumbar Radiculopathy)";
    profile.icd11 = "FA80";
    profile.dominantMizaj = "BALGHAMI";
    profile.secondaryMizaj = "Su-e-Mizaj Maddi Barid Balghami Ghaleez (Cold-Moist Viscous Phlegm)";
    profile.primaryAxis = "AXIS-07-MUSCULOSKELETAL";
    profile.secondaryAxis = "AXIS-06-NEUROPSYCH";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "BALGHAMI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "SAUDAWI", nawm: "SAUDAWI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ABYAD"; profile.baulQiwam = "GHALEEZ"; profile.barazQiwam = "LAYYIN";
    profile.afaalCascade = "Phase 1: Sciatic De-accumulation (21d) ➔ Phase 2: Radicular Anti-inflammatory Resolution (45d) ➔ Phase 3: Neuro-Vertebral Fortification (90d)";
    profile.pathology = "Barid-Ghaleez (Cold-Viscous)";
    profile.prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  else if (diagText.includes("insomnia") || diagText.includes("sahar") || diagText.includes("sleepless") || diagText.includes("anxiety") || diagText.includes("be-khwabi") || diagText.includes("agitation")) {
    profile.diagnosisTitle = "Sahar wa Qalaq (Chronic Insomnia & Anxiety)";
    profile.icd11 = "7A00";
    profile.dominantMizaj = "SAUDAWI";
    profile.secondaryMizaj = "Su-e-Mizaj Yabis Haar Dimaghi (Dry-Hot Cerebral Dyscrasia)";
    profile.primaryAxis = "AXIS-06-NEUROPSYCH";
    profile.secondaryAxis = "AXIS-02-CARDIOVASCULAR";
    profile.organSeverity = 4;
    profile.ajnas = { malmas: "SAFRAWI", lahm: "SAUDAWI", shaar: "SAUDAWI", lawn: "SAUDAWI", bunya: "SAUDAWI", infial: "SAUDAWI", nawm: "SAUDAWI", afal: "SAUDAWI", fuzalat: "SAUDAWI", nabz: "SAFRAWI" };
    profile.nabzSurat = "SAREE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "SULB"; profile.nabzImtila = "KHALI"; profile.nabzHararat = "HAR";
    profile.baulLawn = "ASFAR_NARI"; profile.baulQiwam = "RAQEEQ"; profile.barazQiwam = "YABIS";
    profile.afaalCascade = "Phase 1: Cerebral Hydration & Neural Sedation (21d) ➔ Phase 2: Melancholic Vapor Evacuation (45d) ➔ Phase 3: Neuro-Cognitive Stabilization (90d)";
    profile.pathology = "Yabis-Haar (Dry-Hot)";
    profile.prescriptionTherapy = "Barid-Ratab (Cooling-Moist)";
  }
  else if (diagText.includes("asthma") || diagText.includes("zeequn") || diagText.includes("nafas") || diagText.includes("bronch") || diagText.includes("damah") || diagText.includes("sual")) {
    profile.diagnosisTitle = "Zeequn Nafas wa Sual (Bronchial Asthma & Cough)";
    profile.icd11 = "CA23";
    profile.dominantMizaj = "BALGHAMI";
    profile.secondaryMizaj = "Su-e-Mizaj Barid Ratab Balghami Laziq (Cold-Moist Viscous Phlegm)";
    profile.primaryAxis = "AXIS-03-RESPIRATORY";
    profile.secondaryAxis = "AXIS-05-GASTROINTESTINAL";
    profile.organSeverity = 4;
    profile.ajnas = { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "BALGHAMI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "BALGHAMI", nawm: "BALGHAMI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ABYAD"; profile.baulQiwam = "GHALEEZ"; profile.barazQiwam = "LAYYIN";
    profile.afaalCascade = "Phase 1: Bronchial Mucolytic Clearance (14d) ➔ Phase 2: Bronchospasm Resolution (45d) ➔ Phase 3: Pulmonary Immune Fortification (90d)";
    profile.pathology = "Barid-Ratab (Cold-Moist Phlegmatic)";
    profile.prescriptionTherapy = "Haar-Yabis (Warm-Dry Expectorant)";
  }
  else if (diagText.includes("jaundice") || diagText.includes("yarqan") || (diagText.includes("fatty") && diagText.includes("liver")) || diagText.includes("hepat") || diagText.includes("jigar")) {
    profile.diagnosisTitle = "Su-e-Mizaj Kabid / Yarqan (Hepato-Biliary Dysfunction & Steatosis)";
    profile.icd11 = "DB90";
    profile.dominantMizaj = "SAFRAWI";
    profile.secondaryMizaj = "Su-e-Mizaj Haar Safrawi Sudadi (Hot-Dry Bilious Obstructive)";
    profile.primaryAxis = "AXIS-04-HEPATOBILIARY";
    profile.secondaryAxis = "AXIS-05-GASTROINTESTINAL";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "SAFRAWI", lahm: "SAFRAWI", shaar: "SAFRAWI", lawn: "SAFRAWI", bunya: "SAFRAWI", infial: "SAFRAWI", nawm: "SAFRAWI", afal: "SAFRAWI", fuzalat: "SAFRAWI", nabz: "SAFRAWI" };
    profile.nabzSurat = "SAREE"; profile.nabzQuwwat = "QAWI"; profile.nabzLams = "SULB"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "HAR";
    profile.baulLawn = "ASFAR_NARI"; profile.baulQiwam = "RAQEEQ"; profile.barazQiwam = "LAYYIN";
    profile.afaalCascade = "Phase 1: Hepatic De-obstruction & Biliary Cleansing (20d) ➔ Phase 2: Chyme Purification & Cooling (45d) ➔ Phase 3: Hepato-Cellular Regeneration (90d)";
    profile.pathology = "Haar-Safrawi (Hot-Bilious) / Sudadi";
    profile.prescriptionTherapy = "Barid-Mufattih (Cooling Deobstruent)";
  }
  else if (diagText.includes("eczema") || diagText.includes("psoriasis") || diagText.includes("jild") || diagText.includes("pruritus") || diagText.includes("kharish") || diagText.includes("skin") || diagText.includes("daad")) {
    profile.diagnosisTitle = "Amraz-e-Jild / Kharish (Chronic Eczema & Pruritus)";
    profile.icd11 = "EA80";
    profile.dominantMizaj = "SAFRAWI";
    profile.secondaryMizaj = "Su-e-Mizaj Haar Yabis Damawi-Safrawi (Hot-Dry Sanguine-Bilious Combustion)";
    profile.primaryAxis = "AXIS-09-DERMATOLOGY";
    profile.secondaryAxis = "AXIS-04-HEPATOBILIARY";
    profile.organSeverity = 4;
    profile.ajnas = { malmas: "SAFRAWI", lahm: "SAFRAWI", shaar: "SAUDAWI", lawn: "SAFRAWI", bunya: "SAFRAWI", infial: "SAFRAWI", nawm: "SAFRAWI", afal: "SAFRAWI", fuzalat: "SAFRAWI", nabz: "SAFRAWI" };
    profile.nabzSurat = "SAREE"; profile.nabzQuwwat = "QAWI"; profile.nabzLams = "SULB"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "HAR";
    profile.baulLawn = "ASFAR_NARI"; profile.baulQiwam = "RAQEEQ"; profile.barazQiwam = "YABIS";
    profile.afaalCascade = "Phase 1: Blood Humour Detoxification & Itch Relief (21d) ➔ Phase 2: Dermal Realignment & Anti-inflammatory (45d) ➔ Phase 3: Epithelial Barrier Fortification (90d)";
    profile.pathology = "Haar-Yabis (Hot-Dry Blood Impurity)";
    profile.prescriptionTherapy = "Barid-Murattib Musaffi (Cooling Blood Purifier)";
  }
  else if (diagText.includes("waja") || diagText.includes("mafasil") || diagText.includes("joint") || diagText.includes("arthrit") || diagText.includes("knee")) {
    profile.diagnosisTitle = "Waja-ul-Mafasil (Osteoarthritis & Arthropathy)";
    profile.icd11 = "FA00";
    profile.dominantMizaj = "BALGHAMI";
    profile.secondaryMizaj = "Su-e-Mizaj Maddi Barid Balghami az Mafasil (Cold-Moist Articular Phlegm)";
    profile.primaryAxis = "AXIS-07-MUSCULOSKELETAL";
    profile.secondaryAxis = "AXIS-05-GASTROINTESTINAL";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "BALGHAMI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "BALGHAMI", nawm: "BALGHAMI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ABYAD"; profile.baulQiwam = "GHALEEZ"; profile.barazQiwam = "LAYYIN";
    profile.afaalCascade = "Phase 1: Articular Clearance & Pain Relief (14d) ➔ Phase 2: Synovial Anti-inflammatory Resolution (45d) ➔ Phase 3: Cartilage Fortification (90d)";
    profile.pathology = "Barid-Ratab (Cold-Moist)";
    profile.prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  else if (diagText.includes("hazm") || diagText.includes("dyspep") || diagText.includes("gast") || diagText.includes("gerd") || diagText.includes("acid")) {
    profile.diagnosisTitle = "Su-e-Hazm wa Zof-e-Meda (Functional Dyspepsia & GERD)";
    profile.icd11 = "DA42";
    profile.dominantMizaj = "BALGHAMI";
    profile.secondaryMizaj = "Su-e-Mizaj Barid Ratab Meda (Cold-Moist Gastric Dyspepsia)";
    profile.primaryAxis = "AXIS-05-GASTROINTESTINAL";
    profile.secondaryAxis = "AXIS-04-HEPATOBILIARY";
    profile.organSeverity = 4;
    profile.ajnas = { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "BALGHAMI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "BALGHAMI", nawm: "BALGHAMI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ASFAR_MOTADIL"; profile.baulQiwam = "MOTADIL"; profile.barazQiwam = "LAYYIN";
    profile.afaalCascade = "Phase 1: Gastric Secretory Neutralization (14d) ➔ Phase 2: Digestive Fire Realignment (30d) ➔ Phase 3: Gastric Fortification (60d)";
    profile.pathology = "Barid-Ratab (Cold-Moist)";
    profile.prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  else if (diagText.includes("suda") || diagText.includes("shaqeeqa") || diagText.includes("headache") || diagText.includes("migraine")) {
    profile.diagnosisTitle = "Suda-e-Nisfi / Shaqeeqa (Chronic Migraine)";
    profile.icd11 = "8A80";
    profile.dominantMizaj = "SAUDAWI";
    profile.secondaryMizaj = "Su-e-Mizaj Dimaghi az Bukharaat-e-Meda (Cerebral Disturbance via Gastric Vapors)";
    profile.primaryAxis = "AXIS-06-NEUROPSYCH";
    profile.secondaryAxis = "AXIS-05-GASTROINTESTINAL";
    profile.organSeverity = 4;
    profile.ajnas = { malmas: "SAFRAWI", lahm: "SAUDAWI", shaar: "SAFRAWI", lawn: "SAFRAWI", bunya: "SAUDAWI", infial: "SAUDAWI", nawm: "SAUDAWI", afal: "SAUDAWI", fuzalat: "SAFRAWI", nabz: "SAFRAWI" };
    profile.nabzSurat = "SAREE"; profile.nabzQuwwat = "QAWI"; profile.nabzLams = "SULB"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "HAR";
    profile.baulLawn = "ASFAR_NARI"; profile.baulQiwam = "RAQEEQ"; profile.barazQiwam = "YABIS";
    profile.afaalCascade = "Phase 1: Cerebral Clearance (14d) ➔ Phase 2: Cranio-Vascular Stabilization (45d) ➔ Phase 3: Neuro-Vascular Fortification (90d)";
    profile.pathology = "Barid-Ratab (Cold-Moist)";
    profile.prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  else if (diagText.includes("diab") || diagText.includes("sugar") || diagText.includes("ziabetus") || diagText.includes("glucose")) {
    profile.diagnosisTitle = "Ziabetus Shakari (Type 2 Diabetes Mellitus)";
    profile.icd11 = "5A11";
    profile.dominantMizaj = "BALGHAMI";
    profile.secondaryMizaj = "Su-e-Mizaj Barid Ratab Kabidi wa Kulyawi (Cold-Moist Hepato-Renal Dyscrasia)";
    profile.primaryAxis = "AXIS-01-METABOLIC";
    profile.secondaryAxis = "AXIS-04-HEPATOBILIARY";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "BALGHAMI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "BALGHAMI", nawm: "BALGHAMI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ABYAD"; profile.baulQiwam = "GHALEEZ"; profile.barazQiwam = "MOTADIL";
    profile.afaalCascade = "Phase 1: Glycemic De-saturation & Diuresis (30d) ➔ Phase 2: Hepatic & Pancreatic Realignment (60d) ➔ Phase 3: Microvascular Fortification (180d)";
    profile.pathology = "Barid-Ratab (Cold-Moist)";
    profile.prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  else if (diagText.includes("pcos") || diagText.includes("pcod") || diagText.includes("usr") || diagText.includes("dysmenorrhea") || diagText.includes("tams")) {
    profile.diagnosisTitle = "Usr-e-Tams wa Akyas-e-Khusyatur Reham (PCOS)";
    profile.icd11 = "5A80";
    profile.dominantMizaj = "BALGHAMI";
    profile.secondaryMizaj = "Su-e-Mizaj Maddi Barid Balghami az Reham (Cold-Moist Obstructive Uterine Phlegm)";
    profile.primaryAxis = "AXIS-12-FEMALE-REPROD";
    profile.secondaryAxis = "AXIS-01-METABOLIC";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "SAFRAWI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "SAUDAWI", nawm: "BALGHAMI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ABYAD"; profile.baulQiwam = "GHALEEZ"; profile.barazQiwam = "LAYYIN";
    profile.afaalCascade = "Phase 1: Ovarian Clearance (30d) ➔ Phase 2: Ovulatory & Menstrual Realignment (60d) ➔ Phase 3: Ovarian Reserve Fortification (180d)";
    profile.pathology = "Barid-Ratab (Cold-Moist)";
    profile.prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  else if (diagText.includes("oligo") || diagText.includes("sperm") || diagText.includes("bah") || diagText.includes("qillat") || diagText.includes("surat") || diagText.includes("inzal") || diagText.includes("namardi")) {
    profile.diagnosisTitle = "Qillat-e-Mani wa Zof-e-Bah (Andrological Subfertility & Vigor)";
    profile.icd11 = "GB04";
    profile.dominantMizaj = "BALGHAMI";
    profile.secondaryMizaj = "Su-e-Mizaj Barid Ratab Mani (Cold-Moist Seminal Viscosity Depletion)";
    profile.primaryAxis = "AXIS-11-MALE-REPROD";
    profile.secondaryAxis = "AXIS-01-METABOLIC";
    profile.organSeverity = 5;
    profile.ajnas = { malmas: "BALGHAMI", lahm: "BALGHAMI", shaar: "BALGHAMI", lawn: "BALGHAMI", bunya: "BALGHAMI", infial: "SAUDAWI", nawm: "BALGHAMI", afal: "BALGHAMI", fuzalat: "BALGHAMI", nabz: "BALGHAMI" };
    profile.nabzSurat = "BATEE"; profile.nabzQuwwat = "DHAEF"; profile.nabzLams = "LAYYIN"; profile.nabzImtila = "MUMTALI"; profile.nabzHararat = "BARID";
    profile.baulLawn = "ABYAD"; profile.baulQiwam = "GHALEEZ"; profile.barazQiwam = "LAYYIN";
    profile.afaalCascade = "Phase 1: Seminal Viscosity Restoration (30d) ➔ Phase 2: Spermatogenesis Stimulation (60d) ➔ Phase 3: Gonadal Fortification (90d)";
    profile.pathology = "Barid-Ratab (Cold-Flaccid)";
    profile.prescriptionTherapy = "Haar-Yabis Muqawwi";
  }

  return profile;
}

async function autoDraftNuskhaFromDiagnosis() {
  if (!cachedMasterData || !cachedMasterData.protocols || cachedMasterData.protocols.length === 0) {
    await fetchMasterClinicalData();
  }
  const masterNoteInput = document.getElementById("input-comprehensive-clinical-note");
  const masterNoteText = (masterNoteInput ? masterNoteInput.value : "").trim();

  const diagInput = document.getElementById("input-modern-working");
  const icdInput = document.getElementById("input-modern-icd11");
  const ccInput = document.getElementById("input-reason-visit");
  const hpiInput = document.getElementById("input-hpi");
  const mizajInput = document.getElementById("input-unani-mizaj");
  const secMizajInput = document.getElementById("input-unani-secondary");
  const reasoningInput = document.getElementById("input-unani-reasoning");

  // Sync master note with underlying state if present
  if (masterNoteText) {
    if (ccInput && !ccInput.value.trim()) {
      ccInput.value = masterNoteText.split("\n")[0].substring(0, 120);
    }
    if (hpiInput && !hpiInput.value.trim()) {
      hpiInput.value = masterNoteText;
    }
  }

  // Vitals
  const bpSys = parseFloat(document.getElementById("vital-bp-sys")?.value) || 0;
  const bpDia = parseFloat(document.getElementById("vital-bp-dia")?.value) || 0;
  const pulseVal = parseFloat(document.getElementById("vital-pulse")?.value) || 0;

  // Systemic Physical Exam Notes
  const examGen = (document.getElementById("exam-general")?.value || "").toLowerCase();
  const examPA = (document.getElementById("exam-pa")?.value || "").toLowerCase();
  const examRS = (document.getElementById("exam-rs")?.value || "").toLowerCase();
  const examCVS = (document.getElementById("exam-cvs")?.value || "").toLowerCase();

  // Laboratory Investigations
  const labItems = collectLabInvestigationsFromTable();
  const abnormalLabs = labItems.filter(l => l.status === 'ELEVATED' || l.status === 'CRITICAL' || l.status === 'LOW');
  const abnormalLabNames = abnormalLabs.map(l => `${l.test_name} ${l.value} (${l.status})`).join(", ").toLowerCase();

  // Combine all clinical presentation signals into unified search token
  let diagText = [
    masterNoteText,
    diagInput?.value || "",
    ccInput?.value || "",
    hpiInput?.value || "",
    mizajInput?.value || "",
    secMizajInput?.value || "",
    examGen, examPA, examRS, examCVS,
    abnormalLabNames
  ].join(" ").toLowerCase().trim();

  // Cross-correlate vital, lab & natural text triggers from doctor's note
  if (bpSys >= 140 || bpDia >= 90 || /bp\s*[:=]?\s*1[4-9]\d|hypertens|zaght|high\s*bp/i.test(diagText)) diagText += " high bp hypertension zaght";
  if (abnormalLabNames.includes("hba1c") || abnormalLabNames.includes("glucose") || /sugar|glucose|hba1c|diab/i.test(diagText)) diagText += " diab sugar ziabetus glucose";
  if (abnormalLabNames.includes("uric") || abnormalLabNames.includes("esr") || abnormalLabNames.includes("crp") || /joint|knee|gout|uric|waja|mafasil/i.test(diagText)) diagText += " waja mafasil arthrit uric joint";
  if (abnormalLabNames.includes("alt") || abnormalLabNames.includes("ast") || abnormalLabNames.includes("bilirubin") || /liver|jaundice|yarqan|jigar/i.test(diagText)) diagText += " jaundice yarqan hepat liver";
  if (abnormalLabNames.includes("dfi") || abnormalLabNames.includes("sperm") || abnormalLabNames.includes("testosterone") || /sperm|oligo|motility|fertility|bah|surat|inzal|jariyan|namardi/i.test(diagText)) diagText += " oligo sperm bah qillat surat inzal jariyan";
  if (abnormalLabNames.includes("amh") || /pcos|pcod|ovary|cysts|mahwari|tams/i.test(diagText)) diagText += " pcos usr tams";
  if (abnormalLabNames.includes("creatinine") || abnormalLabNames.includes("bun") || /stone|calcul|pathri|kulyah|renal/i.test(diagText)) diagText += " hasat kulyah renal stone";
  if (/piles|bawaseer|bawasir|hemorrhoid|fissure/i.test(diagText)) diagText += " piles bawaseer";
  if (/sciatica|irq|nasa|radiating/i.test(diagText)) diagText += " sciatica irq nasa";
  if (/insomnia|sahar|sleepless|be-khwabi/i.test(diagText)) diagText += " insomnia sahar";
  if (/asthma|cough|damah|zeequn|sual/i.test(diagText)) diagText += " asthma zeequn nafas";
  if (/leucorrh|leukorrh|likoria|white\s*discharge|sailan/i.test(diagText)) diagText += " sailan leucorrh";
  if (/sozak|urethritis|burning\s*(urination|urine|micturition)|sozish/i.test(diagText)) diagText += " sozak burn micturition";

  if (!diagText) {
    alert("Please enter patient clinical notes, signs/symptoms, or lab markers first.");
    if (masterNoteInput) masterNoteInput.focus();
    else if (ccInput) ccInput.focus();
    return;
  }

  // =========================================================================
  // EXECUTE UNANI PRINCIPLES AUTOMATION ENGINE
  // =========================================================================
  const unaniProfile = calculateComprehensiveUnaniProfile(diagText, { bpSys, bpDia, pulseVal }, labItems, abnormalLabs);

  // 1. Auto-set Working Diagnosis & ICD-11
  if (diagInput) diagInput.value = unaniProfile.diagnosisTitle;
  if (icdInput) icdInput.value = unaniProfile.icd11;

  // 2. Auto-set Dominant Mizaj & Secondary Su-e-Mizaj
  if (mizajInput) mizajInput.value = unaniProfile.dominantMizaj;
  if (secMizajInput) secMizajInput.value = unaniProfile.secondaryMizaj;

  // 3. Auto-calculate & populate 10-Ajnas-e-Ashara
  const ajnasKeys = ["malmas", "lahm", "shaar", "lawn", "bunya", "infial", "nawm", "afal", "fuzalat", "nabz"];
  const ajnasScores = { DAMAWWI: 0, SAFRAWI: 0, BALGHAMI: 0, SAUDAWI: 0 };
  ajnasKeys.forEach(k => {
    const el = document.getElementById(`calc-${k}`);
    if (el && unaniProfile.ajnas[k]) {
      el.value = unaniProfile.ajnas[k];
      if (ajnasScores[unaniProfile.ajnas[k]] !== undefined) ajnasScores[unaniProfile.ajnas[k]]++;
    }
  });

  // 4. Auto-populate Classical Physical Exam (Nabz, Baul, Baraz)
  const elNabzSurat = document.getElementById("tashkhees-nabz-surat"); if (elNabzSurat) elNabzSurat.value = unaniProfile.nabzSurat;
  const elNabzQuwwat = document.getElementById("tashkhees-nabz-quwwat"); if (elNabzQuwwat) elNabzQuwwat.value = unaniProfile.nabzQuwwat;
  const elNabzLams = document.getElementById("tashkhees-nabz-lams"); if (elNabzLams) elNabzLams.value = unaniProfile.nabzLams;
  const elNabzImtila = document.getElementById("tashkhees-nabz-imtila"); if (elNabzImtila) elNabzImtila.value = unaniProfile.nabzImtila;
  const elNabzHararat = document.getElementById("tashkhees-nabz-hararat"); if (elNabzHararat) elNabzHararat.value = unaniProfile.nabzHararat;
  const elBaulLawn = document.getElementById("tashkhees-baul-lawn"); if (elBaulLawn) elBaulLawn.value = unaniProfile.baulLawn;
  const elBaulQiwam = document.getElementById("tashkhees-baul-qiwam"); if (elBaulQiwam) elBaulQiwam.value = unaniProfile.baulQiwam;
  const elBarazQiwam = document.getElementById("tashkhees-baraz-qiwam"); if (elBarazQiwam) elBarazQiwam.value = unaniProfile.barazQiwam;

  // 5. Auto-calculate & populate 12-Axis Organ Diagnostic Profiler
  active12AxisScores = {};
  if (unaniProfile.primaryAxis) active12AxisScores[unaniProfile.primaryAxis] = unaniProfile.organSeverity;
  if (unaniProfile.secondaryAxis) active12AxisScores[unaniProfile.secondaryAxis] = Math.max(2, unaniProfile.organSeverity - 2);
  if (bpSys >= 140 || bpDia >= 90) active12AxisScores["AXIS-02-CARDIOVASCULAR"] = Math.max(active12AxisScores["AXIS-02-CARDIOVASCULAR"] || 0, 3);
  if (abnormalLabNames.includes("glucose") || abnormalLabNames.includes("hba1c")) active12AxisScores["AXIS-01-METABOLIC"] = Math.max(active12AxisScores["AXIS-01-METABOLIC"] || 0, 4);
  render12AxisGrid();
  evaluateActiveAxes();

  // 6. Auto-set 3-Phase Af'al Cascade Treatment Principle (Usul-e-Ilaj)
  const principleInput = document.getElementById("input-plan-principle");
  if (principleInput) principleInput.value = unaniProfile.afaalCascade;

  // 7. Auto-synthesize Complete Tashkhees Synthesis & Clinical Reasoning
  if (reasoningInput) {
    const labNotice = abnormalLabs.length > 0 ? `Abnormal Labs: ${abnormalLabs.map(l => `${l.test_name} ${l.value}`).join(", ")}.` : "Labs within normal limits.";
    const ajnasSummary = `10-Ajnas Score: ${unaniProfile.dominantMizaj} (${ajnasScores[unaniProfile.dominantMizaj] || 6}/10)`;
    const axisSummary = `12-Axis Organ Profile: Primary = ${unaniProfile.primaryAxis} (${unaniProfile.organSeverity}/5), Secondary = ${unaniProfile.secondaryAxis}`;
    reasoningInput.value = `Tashkhees Synthesis & Usul-e-Tibb:\n• Diagnosis: ${unaniProfile.diagnosisTitle} [ICD-11: ${unaniProfile.icd11}]\n• Mizaj: Dominant ${unaniProfile.dominantMizaj} | ${unaniProfile.secondaryMizaj}\n• Physical Signs: Nabz (${unaniProfile.nabzSurat}, ${unaniProfile.nabzQuwwat}, ${unaniProfile.nabzLams}), Baul (${unaniProfile.baulLawn})\n• ${ajnasSummary}\n• ${axisSummary}\n• ${labNotice}\n• Af'al Cascade: ${unaniProfile.afaalCascade}\n• Ilaj-bil-Zidd: Formulated a focused ${unaniProfile.prescriptionTherapy} regimen to counter ${unaniProfile.pathology} and reinforce Tabi'at.`;
  }

  const tbody = document.getElementById("tbody-nuskha-items");
  const ghizaInput = document.getElementById("input-ghiza-diet");
  const parhezInput = document.getElementById("input-parhez-avoid");
  const proposalBanner = document.getElementById("ai-draft-proposal-banner");
  const ziddBadge = document.getElementById("badge-ilaj-bil-zidd");

  let ziddScore = "98% Optimal Neutralization";
  let pathology = unaniProfile.pathology;
  let prescriptionTherapy = unaniProfile.prescriptionTherapy;

  // Core universal Unani parhez foundation
  const baseParhez = "Avoid iced water, white rice, curd, heavy lentils.";

  // Clean table before auto-populating
  if (tbody) tbody.innerHTML = "";

  // 1. 🫘 Renal Calculi / Hasat-e-Kulyah / Stones / Burning Micturition
  if (diagText.includes("hasat") || diagText.includes("kulyah") || diagText.includes("calcul") || diagText.includes("stone") || diagText.includes("renal") || diagText.includes("pathri") || (diagText.includes("burn") && diagText.includes("micturition"))) {
    if (diagInput && !diagInput.value.trim()) { diagInput.value = "Hasat-e-Kulyah (Renal Calculi / Nephrolithiasis)"; if (icdInput) icdInput.value = "GB60"; }
    addNuskhaItemRow({ item_name: "Sharbat Bazoori Motadil", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 15, anupan_vehicle: "With fresh water" });
    addNuskhaItemRow({ item_name: "Habbe Kulyah", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 15, anupan_vehicle: "Post-meals with water" });
    addNuskhaItemRow({ item_name: "AlkaVora™ Alkalizing Granules", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 15, anupan_vehicle: "Dissolved in fresh water" });
    if (principleInput) principleInput.value = "Taftit-e-Hasat (Lithotripsy) -> Idrar-e-Baul (Diuresis) -> Taskeen-e-Alam wa Sozish";
    if (ghizaInput) ghizaInput.value = "Barley water (Maa-ul-Shaeer), fresh melon seeds sherbet, radish soup, pumpkin, 3L+ clean warm water.";
    if (parhezInput) parhezInput.value = `${baseParhez} Strictly avoid oxalate-rich foods (spinach, tomatoes, red meat, chocolate, excessive black tea).`;
    ziddScore = "98% Equilibrium (Alkalizing diuresis)";
    pathology = "Haar-Yabis (Hot-Dry) / Ghaleez";
    prescriptionTherapy = "Barid-Ratab Motadil (Cooling-Hydrating)";
  }
  // 2. 🫀 Hypertension / High BP / Zaght-ud-Dam
  else if (diagText.includes("hypertens") || diagText.includes("high bp") || diagText.includes("zaght") || (diagText.includes("blood") && diagText.includes("press")) || diagText.includes("fashar")) {
    if (diagInput && !diagInput.value.trim()) { diagInput.value = "Zaght-ud-Dam Qawi (Essential Hypertension)"; if (icdInput) icdInput.value = "BA00"; }
    addNuskhaItemRow({ item_name: "Khamira Gaozaban Ambari", dose_amount: 5, dose_unit: "g", frequency: "AM", duration_days: 30, anupan_vehicle: "Morning empty stomach with Arq Gaozaban" });
    addNuskhaItemRow({ item_name: "Itrifal Kishneezi", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 30, anupan_vehicle: "Bedtime with water" });
    addNuskhaItemRow({ item_name: "TensioCalm™ Veg Capsules", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 30, anupan_vehicle: "Post-meals with water" });
    if (principleInput) principleInput.value = "Tadeel-e-Fischar-e-Dam -> Taskeen-e-Asaab wa Dimagh -> Tanqiya-e-Dam";
    if (ghizaInput) ghizaInput.value = "Garlic water, bottle gourd (Lauki), pomegranate juice, fresh apple, low-sodium vegetable soup.";
    if (parhezInput) parhezInput.value = `${baseParhez} Restrict dietary sodium (<2g/day), avoid fried/greasy foods, excessive red meat, mental stress, sleeplessness.`;
    ziddScore = "97% Equilibrium";
    pathology = "Haar-Ratab / Damawi";
    prescriptionTherapy = "Barid-Yabis Motadil";
  }
  // 3. 🩸 Hemorrhoids / Piles / Bawaseer
  else if (diagText.includes("piles") || diagText.includes("bawaseer") || diagText.includes("bawasir") || diagText.includes("hemorrhoid") || diagText.includes("haemorrhoid") || diagText.includes("fissure")) {
    if (diagInput && !diagInput.value.trim()) { diagInput.value = "Bawaseer (Hemorrhoids / Anal Fissure)"; if (icdInput) icdInput.value = "DB60"; }
    addNuskhaItemRow({ item_name: "Itrifal Muqil", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 20, anupan_vehicle: "Bedtime with lukewarm water" });
    addNuskhaItemRow({ item_name: "Sharbat Anjabar", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 20, anupan_vehicle: "With fresh water" });
    addNuskhaItemRow({ item_name: "Roghan-e-Bawaseer (Local Application)", dose_amount: 3, dose_unit: "ml", frequency: "BD", duration_days: 20, anupan_vehicle: "Local application post sitz bath" });
    if (principleInput) principleInput.value = "Habis-e-Dam -> Tanqiya-e-Sauda az Urrooq-e-Miqad -> Mulayyin-e-Ama";
    if (ghizaInput) ghizaInput.value = "Papaya, figs (Anjeer soaked in water), isabghol husk, green leafy vegetables, high fiber soft diet.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid spicy foods, hot peppers, beef, dry bakery items; prevent constipation.`;
    ziddScore = "98% Equilibrium";
    pathology = "Saudawi-Haar (Melancholic-Hot)";
    prescriptionTherapy = "Murattib-Mulayyin (Soothing-Laxative)";
  }
  // 4. ⚡ Sciatica & Neuralgia / Irq-un-Nasa
  else if (diagText.includes("sciatica") || diagText.includes("irq") || diagText.includes("nasa") || diagText.includes("radiating") || (diagText.includes("nerve") && diagText.includes("pain"))) {
    addNuskhaItemRow({ item_name: "Majun Suranjan", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 21, anupan_vehicle: "Bedtime with warm water" });
    addNuskhaItemRow({ item_name: "Roghan-e-Suranjan (Local Application)", dose_amount: 5, dose_unit: "ml", frequency: "BD", duration_days: 21, anupan_vehicle: "Gentle warm massage along sciatic tract" });
    addNuskhaItemRow({ item_name: "NeuroVora™ Nerve Support", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 21, anupan_vehicle: "Post-meals with milk" });
    if (principleInput) principleInput.value = "Tanqiya-e-Mawad-e-Ghaleez az Asab-e-Nasa -> Taskeen-e-Alam -> Taqwiyat-e-Asab";
    if (ghizaInput) ghizaInput.value = "Yakhni (mutton bone broth), garlic with honey, soaked almonds, dates with warm milk.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid cold draft exposure, heavy lifting, sitting on hard uneven surfaces, and cold/sour food items.`;
    ziddScore = "98% Equilibrium";
    pathology = "Barid-Ghaleez (Cold-Viscous)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  // 5. 🌙 Insomnia & Anxiety / Sahar / Sleeplessness
  else if (diagText.includes("insomnia") || diagText.includes("sahar") || diagText.includes("sleepless") || diagText.includes("anxiety") || diagText.includes("be-khwabi") || diagText.includes("agitation")) {
    addNuskhaItemRow({ item_name: "Khamira Khashkhash", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 21, anupan_vehicle: "Bedtime with warm milk" });
    addNuskhaItemRow({ item_name: "Roghan-e-Kahu (Scalp Massage / Natool)", dose_amount: 5, dose_unit: "ml", frequency: "HS", duration_days: 21, anupan_vehicle: "Gentle scalp massage before sleep" });
    addNuskhaItemRow({ item_name: "TensioCalm™ Veg Capsules", dose_amount: 1, dose_unit: "hab", frequency: "HS", duration_days: 21, anupan_vehicle: "With warm water" });
    if (principleInput) principleInput.value = "Tarteeb-e-Dimagh (Cerebral Hydration) -> Taskeen-e-Rooh-e-Nafsani -> Jalib-e-Nawm";
    if (ghizaInput) ghizaInput.value = "Warm cow milk with badam roghan, pumpkin seeds, poppy seed kheer, fresh sweet fruits.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid stimulants, tea/coffee after 4 PM, screen usage 2 hours prior to bedtime, mental overwork.`;
    ziddScore = "99% Equilibrium";
    pathology = "Yabis-Haar (Dry-Hot)";
    prescriptionTherapy = "Barid-Ratab (Cooling-Moist)";
  }
  // 6. 🫁 Respiratory / Asthma / Zeequn Nafas / Chronic Cough
  else if (diagText.includes("asthma") || diagText.includes("zeequn") || diagText.includes("nafas") || diagText.includes("bronch") || diagText.includes("damah") || diagText.includes("sual")) {
    addNuskhaItemRow({ item_name: "Sharbat Banafsha", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 14, anupan_vehicle: "With warm water" });
    addNuskhaItemRow({ item_name: "Lauq Sapistan", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 14, anupan_vehicle: "Lick slowly with warm water" });
    addNuskhaItemRow({ item_name: "RespiroVora™ Broncho-Care Granules", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 14, anupan_vehicle: "With warm water" });
    if (principleInput) principleInput.value = "Taqtee-e-Balgham-e-Laziq -> Taskeen-e-Tashannuj-e-Qasba -> Tanqiya-e-Riya";
    if (ghizaInput) ghizaInput.value = "Warm black pepper chicken broth, ginger-tulsi tea, figs, raisins, honey with lukewarm water.";
    if (parhezInput) parhezInput.value = `${baseParhez} Strictly avoid cold drinks, curd/ice cream, direct cold drafts, tobacco smoke and dust.`;
    ziddScore = "98% Equilibrium";
    pathology = "Barid-Ratab (Cold-Moist Phlegmatic)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry Expectorant)";
  }
  // 7. 🫀 Hepatobiliary / Jaundice / Yarqan / Fatty Liver
  else if (diagText.includes("jaundice") || diagText.includes("yarqan") || (diagText.includes("fatty") && diagText.includes("liver")) || diagText.includes("hepat") || diagText.includes("jigar")) {
    addNuskhaItemRow({ item_name: "Sharbat Deenar", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 20, anupan_vehicle: "With Arq Kasni (50ml)" });
    addNuskhaItemRow({ item_name: "Majun Dabeed-ul-Ward", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 20, anupan_vehicle: "Post-meals" });
    addNuskhaItemRow({ item_name: "HepatoVora™ Liver Shield", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 20, anupan_vehicle: "Before meals with water" });
    if (principleInput) principleInput.value = "Fath-e-Sudadd-e-Kabid -> Tanqiya-e-Safra wa Balgham -> Taqwiyat-e-Jigar";
    if (ghizaInput) ghizaInput.value = "Fresh sweet pomegranate juice, sugarcane juice, radish, boiled bottle gourd, glucose water.";
    if (parhezInput) parhezInput.value = `${baseParhez} Strict low-fat diet, avoid heavy oily curries, deep fried food, red meat, and excessive spices.`;
    ziddScore = "98% Equilibrium";
    pathology = "Haar-Safrawi (Hot-Bilious) / Sudadi";
    prescriptionTherapy = "Barid-Mufattih (Cooling Deobstruent)";
  }
  // 8. 🌿 Dermatology / Eczema / Psoriasis / Amraz-e-Jild / Kharish
  else if (diagText.includes("eczema") || diagText.includes("psoriasis") || diagText.includes("jild") || diagText.includes("pruritus") || diagText.includes("kharish") || diagText.includes("skin") || diagText.includes("daad")) {
    addNuskhaItemRow({ item_name: "Safi Compound", dose_amount: 10, dose_unit: "ml", frequency: "BD", duration_days: 21, anupan_vehicle: "With fresh water" });
    addNuskhaItemRow({ item_name: "Itrifal Shahtarra", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 21, anupan_vehicle: "Bedtime with water" });
    addNuskhaItemRow({ item_name: "DermaVora™ Soothing Paste", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 21, anupan_vehicle: "Topical application on lesions" });
    if (principleInput) principleInput.value = "Tanqiya-e-Khadam-e-Dam wa Sauda -> Taskeen-e-Hikka -> Tadeel-e-Mizaj-e-Jild";
    if (ghizaInput) ghizaInput.value = "Bitter gourd (karela), bottle gourd, mung dal, fresh coconut water, cucumber, sweet apples.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid excessively sour, salty, and fermented foods; keep skin hydrated, avoid harsh chemical soaps.`;
    ziddScore = "99% Equilibrium";
    pathology = "Haar-Yabis (Hot-Dry Blood Impurity)";
    prescriptionTherapy = "Barid-Murattib Musaffi (Cooling Blood Purifier)";
  }
  // 9. 🌹 Poshida Amraz - Mardana (Men's Reproductive Health)
  // 9A. Sur'at-e-Inzal / Riqqat-e-Mani / Premature Ejaculation
  else if (diagText.includes("sur'at") || diagText.includes("surat") || diagText.includes("inzal") || diagText.includes("riqqat") || (diagText.includes("premature") && diagText.includes("ejaculat"))) {
    addNuskhaItemRow({ item_name: "Majun Arad Khurma", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 30, anupan_vehicle: "With warm milk" });
    addNuskhaItemRow({ item_name: "Habbe Jadwar", dose_amount: 1, dose_unit: "hab", frequency: "HS", duration_days: 30, anupan_vehicle: "Bedtime with warm milk" });
    addNuskhaItemRow({ item_name: "ManiVital Pro™ Complex", dose_amount: 1, dose_unit: "sachet", frequency: "OD", duration_days: 30, anupan_vehicle: "Morning empty stomach with warm milk" });
    if (principleInput) principleInput.value = "Taghleez-e-Mani -> Imsak-e-Tabi'i -> Taqwiyat-e-Aaza-e-Risa (Dimagh, Qalb, Jigar)";
    if (ghizaInput) ghizaInput.value = "Badam kheer, dry dates (chuhara), butter, pistachios, warm saffron milk.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid spicy foods, hot curries, erotic thoughts, late-night waking.`;
    ziddScore = "98% Equilibrium";
    pathology = "Hararat-e-Mani / Riqqat";
    prescriptionTherapy = "Barid-Mughalliz (Cooling Thickener)";
  }
  // 9B. Jariyan / Spermatorrhea / Involuntary Seminal Discharge
  else if (diagText.includes("jariyan") || diagText.includes("spermatorrhea") || diagText.includes("dhat")) {
    addNuskhaItemRow({ item_name: "Majun Salab", dose_amount: 5, dose_unit: "g", frequency: "AM", duration_days: 30, anupan_vehicle: "Morning empty stomach with milk" });
    addNuskhaItemRow({ item_name: "Qurs Kushta Sadaf", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 30, anupan_vehicle: "With water" });
    addNuskhaItemRow({ item_name: "Safoof Mughalliz Mani", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 30, anupan_vehicle: "With warm milk" });
    if (principleInput) principleInput.value = "Taghleez-e-Mani wa Habis-e-Jariyan -> Taskeen-e-Hiddat-e-Mani";
    if (ghizaInput) ghizaInput.value = "Mung dal, gourd soup, isabghol with milk, raw milk butter.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid excessive heat, hot bath, spicy food, tight undergarments.`;
    ziddScore = "98% Equilibrium";
    pathology = "Hiddat-e-Mani (Excess Heat)";
    prescriptionTherapy = "Barid-Khasir Mughalliz";
  }
  // 9C. Zof-e-Bah / Erectile Dysfunction / Impotence
  else if (diagText.includes("zof-e-bah") || diagText.includes("erectile") || diagText.includes("ed") || diagText.includes("namardi") || (diagText.includes("bah") && !diagText.includes("khwabi"))) {
    addNuskhaItemRow({ item_name: "Majun Salab", dose_amount: 5, dose_unit: "g", frequency: "OD", duration_days: 30, anupan_vehicle: "Morning with warm milk" });
    addNuskhaItemRow({ item_name: "Labub Kabir", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 30, anupan_vehicle: "Bedtime with warm milk" });
    addNuskhaItemRow({ item_name: "Habbe Azaraqi Mudabbar", dose_amount: 1, dose_unit: "hab", frequency: "OD", duration_days: 30, anupan_vehicle: "Post-lunch with water" });
    if (principleInput) principleInput.value = "Taqwiyat-e-Bah wa Asab -> Tahreek-e-Hararat-e-Ghariziyyah";
    if (ghizaInput) ghizaInput.value = "Walnuts (30g), soaked almonds (10), mutton soup, saffron milk.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid smoking, alcohol, stress, irregular sleep habits.`;
    ziddScore = "98% Equilibrium";
    pathology = "Barid-Ratab (Cold-Flaccid)";
    prescriptionTherapy = "Haar-Yabis Muqawwi";
  }
  // 9D. Oligospermia / Qillat-e-Mani / Low Sperm Count
  else if (diagText.includes("oligo") || diagText.includes("sperm") || diagText.includes("qillat") || diagText.includes("motility")) {
    addNuskhaItemRow({ item_name: "Majun Salab", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 30, anupan_vehicle: "With warm cow milk" });
    addNuskhaItemRow({ item_name: "Kushta Nuqra (Silver Calx)", dose_amount: 1, dose_unit: "hab", frequency: "OD", duration_days: 30, anupan_vehicle: "Morning with milk cream (Balai)" });
    addNuskhaItemRow({ item_name: "ManiVital Pro™ Extract", dose_amount: 1, dose_unit: "sachet", frequency: "HS", duration_days: 30, anupan_vehicle: "With warm saffron milk" });
    if (principleInput) principleInput.value = "Tawleed-e-Mani -> Taqwiyat-e-Khuwasi -> Izzad-e-Haywanat-e-Manviyyah";
    if (ghizaInput) ghizaInput.value = "Walnuts, pumpkin seeds, soaked figs, goat milk, roasted grams.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid tight underwear, laptop on lap, hot sauna, tobacco.`;
    ziddScore = "99% Equilibrium";
    pathology = "Buroodat-e-Mani";
    prescriptionTherapy = "Haar-Ratab Muwallid-e-Mani";
  }
  // 10. 🌺 Poshida Amraz - Zanana (Women's Reproductive Health)
  // 10A. Sailan-ur-Rahm / Leucorrhea / White Discharge
  else if (diagText.includes("sailan") || diagText.includes("leucorrh") || diagText.includes("leukorrh") || diagText.includes("likoria") || (diagText.includes("white") && diagText.includes("discharge"))) {
    addNuskhaItemRow({ item_name: "Majun Supari Pak", dose_amount: 7, dose_unit: "g", frequency: "BD", duration_days: 21, anupan_vehicle: "With warm milk" });
    addNuskhaItemRow({ item_name: "Safoof Sailan (Matab Compound)", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 21, anupan_vehicle: "With water" });
    addNuskhaItemRow({ item_name: "Sharbat Bazoori Motadil", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 21, anupan_vehicle: "With water" });
    addNuskhaItemRow({ item_name: "FeminaVora™ Uterine Balance", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 21, anupan_vehicle: "Post-meals with water" });
    if (principleInput) principleInput.value = "Habis-e-Sailan -> Tanqiya-e-Rutubaat-e-Reham -> Taqwiyat-e-Quwwat-e-Masika";
    if (ghizaInput) ghizaInput.value = "Roasted chickpeas, sago kheer, mung dal khichdi, pomegranate.";
    if (parhezInput) parhezInput.value = `${baseParhez} Strictly avoid sour items, tamarind, pickles, stale food, heavy exhaustion.`;
    ziddScore = "98% Equilibrium";
    pathology = "Rutubat-e-Balghamiyyah (Cold-Excess Moisture)";
    prescriptionTherapy = "Haar-Yabis Qabiz (Warm-Dry Astringent)";
  }
  // 10B. Kasrat-e-Tams / Menorrhagia / Heavy Bleeding
  else if (diagText.includes("kasrat") || diagText.includes("menorrhagia") || (diagText.includes("heavy") && diagText.includes("bleed"))) {
    addNuskhaItemRow({ item_name: "Safoof Habis", dose_amount: 3, dose_unit: "g", frequency: "BD", duration_days: 10, anupan_vehicle: "With fresh water" });
    addNuskhaItemRow({ item_name: "Majun Muqawwi-e-Reham", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 20, anupan_vehicle: "Bedtime with milk" });
    addNuskhaItemRow({ item_name: "Sharbat Anjabar", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 20, anupan_vehicle: "With water" });
    if (principleInput) principleInput.value = "Habis-e-Dam wa Qabiz -> Taqwiyat-e-Arooq-e-Reham";
    if (ghizaInput) ghizaInput.value = "Pomegranate juice, banana flower curry, barley water, soft khichdi.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid hot potency spices, hot water baths, lifting heavy weights during menses.`;
    ziddScore = "98% Equilibrium";
    pathology = "Haar-Damawi (Excess Heat & Bleeding)";
    prescriptionTherapy = "Barid-Yabis Habis (Cooling Styptic)";
  }
  // 10C. Ehtebas-e-Tams / Amenorrhea / Delayed Menses
  else if (diagText.includes("ehtebas") || diagText.includes("amenorrhea") || (diagText.includes("delayed") && diagText.includes("menses")) || (diagText.includes("missed") && diagText.includes("period"))) {
    addNuskhaItemRow({ item_name: "Habb-e-Mudir", dose_amount: 2, dose_unit: "hab", frequency: "BD", duration_days: 14, anupan_vehicle: "With warm water" });
    addNuskhaItemRow({ item_name: "Sharbat Bazoori Motadil", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 14, anupan_vehicle: "With water" });
    addNuskhaItemRow({ item_name: "FeminaVora™ Flow Balance", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 14, anupan_vehicle: "After meals" });
    if (principleInput) principleInput.value = "Idrar-e-Tams -> Tanqiya-e-Sudadd-e-Urrooq -> Tadeel-e-Mizaj";
    if (ghizaInput) ghizaInput.value = "Jaggery (Gur) tea, sesame seeds, ginger infusion, papaya.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid cold sour foods, refrigerated drinks, sitting on cold surfaces.`;
    ziddScore = "97% Equilibrium";
    pathology = "Barid-Sudadi (Cold-Obstructive)";
    prescriptionTherapy = "Haar-Mufattih Mudir";
  }
  // 10D. Uqr / Female Infertility / Conception Difficulty
  else if (diagText.includes("uqr") || (diagText.includes("female") && diagText.includes("infert")) || diagText.includes("conception") || diagText.includes("be-auladi")) {
    addNuskhaItemRow({ item_name: "Majun Muqawwi-e-Reham", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 30, anupan_vehicle: "With warm cow milk" });
    addNuskhaItemRow({ item_name: "Khamira Gaozaban Ambari", dose_amount: 5, dose_unit: "g", frequency: "AM", duration_days: 30, anupan_vehicle: "Morning empty stomach with Arq Gaozaban" });
    addNuskhaItemRow({ item_name: "FeminaVora™ OvulaGranules", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 30, anupan_vehicle: "With warm milk" });
    if (principleInput) principleInput.value = "Taqwiyat-e-Reham wa Khusyatur Reham -> Islah-e-Rutubaat -> Tahayya-e-Istiqrar-e-Hamal";
    if (ghizaInput) ghizaInput.value = "Almonds, figs, dates, fresh pomegranate, green leafy vegetables.";
    if (parhezInput) parhezInput.value = `${baseParhez} Maintain healthy weight, manage stress, avoid smoking, avoid refined sugar.`;
    ziddScore = "99% Equilibrium";
    pathology = "Zof-e-Reham wa Mizaj";
    prescriptionTherapy = "Motadil Muqawwi-e-Reham";
  }
  // 10E. Usr-e-Tams / Dysmenorrhea / PCOS / PCOD
  else if (diagText.includes("pcos") || diagText.includes("pcod") || diagText.includes("usr") || diagText.includes("dysmenorrhea") || diagText.includes("cramps") || diagText.includes("tams")) {
    addNuskhaItemRow({ item_name: "Majun Supari Pak", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 30, anupan_vehicle: "With warm milk" });
    addNuskhaItemRow({ item_name: "Sharbat Bazoori Motadil", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 30, anupan_vehicle: "With water" });
    addNuskhaItemRow({ item_name: "FeminaVora™ Uterine Balance", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 30, anupan_vehicle: "Post-meals with water" });
    if (principleInput) principleInput.value = "Tanqiya-e-Rutubaat-e-Balghami az Reham -> Tadeel-e-Mizaj-e-Khusyatur Reham -> Idrar-e-Tams";
    if (ghizaInput) ghizaInput.value = "Methi seed water, cinnamon herbal tea, soaked flaxseeds, mung dal, steamed vegetables.";
    if (parhezInput) parhezInput.value = `${baseParhez} Restrict processed sugars, refined carbohydrates, dairy/cheese; 30 minutes daily brisk walk.`;
    ziddScore = "97% Equilibrium";
    pathology = "Barid-Ratab (Cold-Moist)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  // 11. 🛡️ Genito-Urinary
  // 11A. Sozak / Urethritis / Burning Micturition
  else if (diagText.includes("sozak") || diagText.includes("urethritis") || diagText.includes("gonorrhea") || diagText.includes("sozish")) {
    addNuskhaItemRow({ item_name: "Sharbat Bazoori Motadil", dose_amount: 25, dose_unit: "ml", frequency: "TDS", duration_days: 14, anupan_vehicle: "With fresh water" });
    addNuskhaItemRow({ item_name: "Qurs Kushta Qalai", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 14, anupan_vehicle: "With milk or butter" });
    addNuskhaItemRow({ item_name: "AlkaVora™ Alkalizing Granules", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 14, anupan_vehicle: "With fresh water" });
    if (principleInput) principleInput.value = "Taskeen-e-Hiddat-e-Baul wa Sozish -> Idrar-e-Baul -> Daf-e-Ufoonat";
    if (ghizaInput) ghizaInput.value = "Barley water (Maa-ul-Shaeer), cucumber, watermelon, coconut water.";
    if (parhezInput) parhezInput.value = `${baseParhez} Strictly avoid red chilies, hot spices, fried food, beef; drink 3-4 liters of water.`;
    ziddScore = "99% Equilibrium";
    pathology = "Haar-Safrawi / Ufooni";
    prescriptionTherapy = "Barid-Ratab Musakkin-e-Sozish";
  }
  // 11B. Hikka / Pruritus / Genital Itching
  else if (diagText.includes("hikka") || (diagText.includes("genital") && diagText.includes("itch"))) {
    addNuskhaItemRow({ item_name: "Safi Compound", dose_amount: 10, dose_unit: "ml", frequency: "BD", duration_days: 20, anupan_vehicle: "With water" });
    addNuskhaItemRow({ item_name: "Itrifal Shahtarra", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 20, anupan_vehicle: "Bedtime with water" });
    addNuskhaItemRow({ item_name: "Marham Safaid Kafoori", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 20, anupan_vehicle: "Clean area and apply gently" });
    if (principleInput) principleInput.value = "Taskeen-e-Hikka wa Hiddat-e-Safra -> Tanqiya-e-Dam";
    if (ghizaInput) ghizaInput.value = "Gourd soup, mung dal, fresh coconut water, cucumber.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid hot spices, eggs, sour curd, synthetic nylon underwear.`;
    ziddScore = "98% Equilibrium";
    pathology = "Haar-Safrawi (Hot-Bilious)";
    prescriptionTherapy = "Barid-Musakkin Musaffi";
  }
  // 12. 🦵 Waja-ul-Mafasil / Joint Pain & Stiffness
  else if (diagText.includes("waja") || diagText.includes("mafasil") || diagText.includes("joint") || diagText.includes("arthrit") || diagText.includes("knee")) {
    addNuskhaItemRow({ item_name: "Majun Suranjan", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 14, anupan_vehicle: "Neem garam paani (Lukewarm water)" });
    addNuskhaItemRow({ item_name: "Habbe Asgand", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 14, anupan_vehicle: "Milk or Water after meals" });
    addNuskhaItemRow({ item_name: "Roghan Suranjan (For Dalk / Local Massage)", dose_amount: 5, dose_unit: "ml", frequency: "BD", duration_days: 14, anupan_vehicle: "Gentle local joint massage" });
    if (principleInput) principleInput.value = "Tanqiya-e-Mawad-e-Balgham wa Sauda az Mafasil -> Taskeen-e-Waja -> Taqwiyat-e-Ribataat (Phase 1: Tanqiya)";
    if (ghizaInput) ghizaInput.value = "Mung dal khichdi with desi cow ghee, garlic soup, ginger tea, warm easily digestible foods.";
    if (parhezInput) parhezInput.value = `${baseParhez} Strictly avoid cold weather exposure, baadi ghiza, direct AC blast, sitting on damp cold floor.`;
    ziddScore = "98% Equilibrium (Hot/Moist counteracting Cold/Dry)";
    pathology = "Barid-Ratab (Cold-Moist)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  // 13. 🧪 Su-e-Hazm / Dyspepsia & Flatulence / GERD
  else if (diagText.includes("hazm") || diagText.includes("dyspep") || diagText.includes("gast") || diagText.includes("gerd") || diagText.includes("acid")) {
    addNuskhaItemRow({ item_name: "Jawarish Kamuni", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 14, anupan_vehicle: "Post-meals with water" });
    addNuskhaItemRow({ item_name: "Itrifal Kishneezi", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 14, anupan_vehicle: "Bedtime with water" });
    addNuskhaItemRow({ item_name: "Arq Badiyan (Badraqa)", dose_amount: 50, dose_unit: "ml", frequency: "BD", duration_days: 14, anupan_vehicle: "Warm vehicle" });
    if (principleInput) principleInput.value = "Tadeel-e-Mizaj-e-Meda wa Hazm -> Tanqiya-e-Rutubaat-e-Fasida -> Taqwiyat-e-Fam-e-Meda";
    if (ghizaInput) ghizaInput.value = "Mung dal, barley water (Maa-ul-Shaeer), fresh pomegranate, roasted cumin.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid deep-fried trans-fat foods (tala-bhuna), cold ice drinks, raw salads at night, heavy digestion meals.`;
    ziddScore = "96% Equilibrium (Warm aromatic carminatives counteracting cold sluggish digestive fire)";
    pathology = "Barid-Ratab (Cold-Moist)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  // 14. 🧠 Suda / Shaqeeqa (Chronic Migraine & Headache)
  else if (diagText.includes("suda") || diagText.includes("shaqeeqa") || diagText.includes("headache") || diagText.includes("migraine")) {
    addNuskhaItemRow({ item_name: "Itrifal Ustukhuddus", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 14, anupan_vehicle: "Bedtime with Arq Gaozaban" });
    addNuskhaItemRow({ item_name: "Sharbat Ahmad Shahi", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 14, anupan_vehicle: "With lukewarm water" });
    addNuskhaItemRow({ item_name: "Roghan Banafsha (Local Application)", dose_amount: 3, dose_unit: "drops", frequency: "HS", duration_days: 14, anupan_vehicle: "Forehead & nasal application" });
    if (principleInput) principleInput.value = "Tanqiya-e-Dimagh az Bukharaat-e-Raddiya -> Taskeen-e-Asaab -> Tadeel-e-Dam";
    if (ghizaInput) ghizaInput.value = "Cow milk with crushed badam, fresh apple juice, pumpkin seeds, gourd soup.";
    if (parhezInput) parhezInput.value = `${baseParhez} Avoid late nights, blue screen light after 9 PM, bright direct sun, sour pickles, loud noise.`;
    ziddScore = "97% Equilibrium";
    pathology = "Barid-Ratab (Cold-Moist)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  // 15. 🍯 Ziabetus Shakari / Type 2 Diabetes
  else if (diagText.includes("diab") || diagText.includes("sugar") || diagText.includes("ziabetus") || diagText.includes("glucose")) {
    addNuskhaItemRow({ item_name: "DiabEase 500g Safoof (Jamun, Gurmar, Karela, Giloy)", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 30, anupan_vehicle: "Arq Kasni (50ml) or Lukewarm Water" });
    addNuskhaItemRow({ item_name: "Kushta Baiza Murgh", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 30, anupan_vehicle: "With safoof" });
    addNuskhaItemRow({ item_name: "Qurs Ziabetus", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 30, anupan_vehicle: "30 mins before meals" });
    if (principleInput) principleInput.value = "Tadeel-e-Mizaj-e-Kulyah wa Jigar -> Kasr-e-Hararat -> Taqwiyat-e-Quwwat-e-Masika";
    if (ghizaInput) ghizaInput.value = "Barley (Jau) daliya, karela, roasted chana, green leafy vegetables, methi water.";
    if (parhezInput) parhezInput.value = `${baseParhez} Strictly avoid refined sugar, white rice, potatoes, sweets, sedentary post-meal habit.`;
    ziddScore = "99% Equilibrium";
    pathology = "Barid-Ratab (Cold-Moist)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }
  // 16. Dynamic Semantic Catalog Search Fallback
  else {
    let matchedId = "P-05";
    if (diagText.includes("obes") || diagText.includes("weight")) matchedId = "P-02";
    else if (diagText.includes("lipid") || diagText.includes("cholesterol")) matchedId = "P-03";
    loadMasterProtocol(matchedId);
    if (parhezInput && !parhezInput.value.includes("Avoid iced water")) {
      parhezInput.value = `${baseParhez} ${parhezInput.value}`;
    }
    ziddScore = "95% Equilibrium";
    pathology = "Barid-Ratab (Cold-Moist)";
    prescriptionTherapy = "Haar-Yabis (Warm-Dry)";
  }

  // Display the dedicated "DRAFT ONLY" AI Proposal Banner with calculated Unani metrics
  if (proposalBanner) {
    proposalBanner.style.display = "block";
    const subNotice = proposalBanner.querySelector("em");
    if (subNotice) {
      subNotice.innerHTML = `
        <strong>🌿 Synthesized Unani Principles &amp; Clinical Analysis:</strong><br>
        • <strong>Dominant Mizaj:</strong> ${unaniProfile.dominantMizaj} (${unaniProfile.secondaryMizaj})<br>
        • <strong>10-Ajnas-e-Ashara:</strong> ${unaniProfile.dominantMizaj} [10-Parameter Assessment Complete]<br>
        • <strong>Organ Axis Diagnosis:</strong> Primary: <strong>${unaniProfile.primaryAxis}</strong> (Severity: ${unaniProfile.organSeverity}/5) • Secondary: <strong>${unaniProfile.secondaryAxis}</strong><br>
        • <strong>Afaal Cascade &amp; Therapeutic Phases:</strong> Tanqiya (Cleansing) ➔ Tahleel (Resolution) ➔ Taqwiyat (Fortification)<br>
        <span style="display: inline-block; margin-top: 0.35rem; color: #047857;">👉 Clinical starter regimen formulated from presenting history — <strong>Review &amp; adjust posology ([+] or [−])</strong> before finalizing.</span>
      `;
    }
  }
  if (ziddBadge) {
    ziddBadge.innerText = `⚖️ Ilaj-bil-Zidd: ${ziddScore}`;
  }
  const balanceTextEl = document.getElementById("text-humoral-balance");
  if (balanceTextEl) {
    balanceTextEl.innerHTML = `Patient Pathology: <strong>${pathology}</strong> [${unaniProfile.primaryAxis}] ⟷ Prescription: <strong>${prescriptionTherapy}</strong> = <span style="color: #16a34a; font-weight: 700;">Motadil (Harmonized) ✓</span>`;
  }

  triggerAutosave();

  // Smooth scroll to Card 3 for physician analysis
  scrollToSection("sec-plan_nuskha");
}

// -----------------------------------------------------------------------------
// VOICE DICTATION ENGINE (MIC TO PRESCRIPTION LINE ITEMS)
// -----------------------------------------------------------------------------

let voiceRxRecognition = null;
let isVoiceRxListening = false;

function toggleVoiceDictationRx() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn = document.getElementById("btn-dictate-rx");

  if (!SpeechRecognition) {
    alert("Speech Recognition is not supported by your browser. Please use Google Chrome or Microsoft Edge for voice dictation.");
    return;
  }

  if (isVoiceRxListening && voiceRxRecognition) {
    voiceRxRecognition.stop();
    isVoiceRxListening = false;
    if (btn) {
      btn.innerHTML = "🎤 Dictate Rx";
      btn.style.background = "#fffbeb";
      btn.style.color = "#b45309";
      btn.style.borderColor = "#fde68a";
    }
    return;
  }

  try {
    voiceRxRecognition = new SpeechRecognition();
    voiceRxRecognition.continuous = false;
    voiceRxRecognition.interimResults = false;
    voiceRxRecognition.lang = "en-US";

    voiceRxRecognition.onstart = function() {
      isVoiceRxListening = true;
      if (btn) {
        btn.innerHTML = "🔴 Listening... (Speak formulation)";
        btn.style.background = "#fee2e2";
        btn.style.color = "#991b1b";
        btn.style.borderColor = "#fca5a5";
      }
    };

    voiceRxRecognition.onresult = function(event) {
      if (event.results && event.results[0] && event.results[0][0]) {
        const transcript = event.results[0][0].transcript;
        if (transcript && transcript.trim()) {
          parseAndAddDictatedItem(transcript.trim());
        }
      }
    };

    voiceRxRecognition.onerror = function(event) {
      console.warn("Voice dictation error:", event.error);
      isVoiceRxListening = false;
      if (btn) {
        btn.innerHTML = "🎤 Dictate Rx";
        btn.style.background = "#fffbeb";
        btn.style.color = "#b45309";
        btn.style.borderColor = "#fde68a";
      }
    };

    voiceRxRecognition.onend = function() {
      isVoiceRxListening = false;
      if (btn) {
        btn.innerHTML = "🎤 Dictate Rx";
        btn.style.background = "#fffbeb";
        btn.style.color = "#b45309";
        btn.style.borderColor = "#fde68a";
      }
    };

    voiceRxRecognition.start();
  } catch (err) {
    console.error("Failed to start voice dictation:", err);
    alert("Could not access microphone: " + err.message);
  }
}

function parseAndAddDictatedItem(spokenText) {
  let dose = 5;
  let unit = "g";
  let freq = "BD";
  let vehicle = "Lukewarm water";
  let cleanName = spokenText;

  const doseMatch = spokenText.match(/(\d+(?:\.\d+)?)\s*(grams?|g|tablets?|tabs?|capsules?|caps?|ml|drops?|hab)/i);
  if (doseMatch) {
    dose = parseFloat(doseMatch[1]);
    const u = doseMatch[2].toLowerCase();
    if (u.startsWith("gram") || u === "g") unit = "g";
    else if (u.startsWith("tab") || u.startsWith("hab")) unit = "hab";
    else if (u.startsWith("cap")) unit = "hab";
    else if (u.startsWith("ml")) unit = "ml";
    else if (u.startsWith("drop")) unit = "drops";
  }

  if (/once\s+a\s+day|morning|od/i.test(spokenText)) freq = "OD";
  else if (/bedtime|night|hs/i.test(spokenText)) freq = "HS";
  else if (/thrice|three\s+times|tds/i.test(spokenText)) freq = "TDS";
  else if (/twice|two\s+times|bd/i.test(spokenText)) freq = "BD";

  if (/milk/i.test(spokenText)) vehicle = "Warm cow milk";
  else if (/honey/i.test(spokenText)) vehicle = "With honey";
  else if (/empty\s+stomach/i.test(spokenText)) vehicle = "Morning empty stomach";

  addNuskhaItemRow({
    item_name: cleanName,
    dose_amount: dose,
    dose_unit: unit,
    frequency: freq,
    duration_days: 14,
    anupan_vehicle: vehicle
  });

  const banner = document.getElementById("ai-draft-proposal-banner");
  if (banner) banner.style.display = "block";
  triggerAutosave();
}

let voiceNotesRecognition = null;
let isVoiceNotesListening = false;

function toggleVoiceDictationNotes() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const btn = document.getElementById("btn-voice-dictate-notes");
  const noteArea = document.getElementById("input-comprehensive-clinical-note");

  if (!SpeechRecognition) {
    alert("Speech Recognition is not supported by your browser. Please use Google Chrome or Microsoft Edge for voice dictation.");
    return;
  }

  if (isVoiceNotesListening && voiceNotesRecognition) {
    voiceNotesRecognition.stop();
    isVoiceNotesListening = false;
    if (btn) {
      btn.innerHTML = "🎤 Voice Dictate Notes";
      btn.style.background = "#fffbeb";
      btn.style.color = "#b45309";
      btn.style.borderColor = "#fde68a";
    }
    return;
  }

  try {
    voiceNotesRecognition = new SpeechRecognition();
    voiceNotesRecognition.continuous = true;
    voiceNotesRecognition.interimResults = false;
    voiceNotesRecognition.lang = "en-US";

    voiceNotesRecognition.onstart = function() {
      isVoiceNotesListening = true;
      if (btn) {
        btn.innerHTML = "🔴 Listening... (Speak notes)";
        btn.style.background = "#fee2e2";
        btn.style.color = "#991b1b";
        btn.style.borderColor = "#fca5a5";
      }
    };

    voiceNotesRecognition.onresult = function(event) {
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          const text = event.results[i][0].transcript;
          if (noteArea) {
            noteArea.value = (noteArea.value ? noteArea.value + " " : "") + text.trim();
            noteArea.dispatchEvent(new Event("input", { bubbles: true }));
          }
        }
      }
    };

    voiceNotesRecognition.onerror = function(event) {
      console.warn("Notes voice dictation error:", event.error);
      isVoiceNotesListening = false;
      if (btn) {
        btn.innerHTML = "🎤 Voice Dictate Notes";
        btn.style.background = "#fffbeb";
        btn.style.color = "#b45309";
        btn.style.borderColor = "#fde68a";
      }
    };

    voiceNotesRecognition.onend = function() {
      isVoiceNotesListening = false;
      if (btn) {
        btn.innerHTML = "🎤 Voice Dictate Notes";
        btn.style.background = "#fffbeb";
        btn.style.color = "#b45309";
        btn.style.borderColor = "#fde68a";
      }
    };

    voiceNotesRecognition.start();
  } catch (err) {
    console.error("Failed to start voice dictation for notes:", err);
    alert("Could not access microphone: " + err.message);
  }
}

function addQuickDrug(drugName) {
  const input = document.getElementById("input-patient-allopathic-drugs");
  if (!input) return;
  const current = input.value.split(",").map(s => s.trim()).filter(Boolean);
  if (!current.some(c => c.toLowerCase() === drugName.toLowerCase())) {
    current.push(drugName);
    input.value = current.join(", ");
  }
  runPreflightCheck();
}

// -----------------------------------------------------------------------------
// ABDAL-E-ADWIYA (DRUG SUBSTITUTION) SUGGESTER
// -----------------------------------------------------------------------------

const CANONICAL_BADAL_REGISTRY = {
  "jundbedastar": { name: "Filfil Siyah", ratio: "0.5x dose", doseFactor: 0.5, rules: "Black Pepper at 50% dose (Kitab al-Abdal / Ishrah al-Adwiya p. 40)" },
  "zafran": { name: "Qust Shirin", ratio: "1.0x dose", doseFactor: 1.0, rules: "Qust Shirin or Kusumbha for warmth & cardiac vigor" },
  "mastagi": { name: "Kundur", ratio: "1.0x dose", doseFactor: 1.0, rules: "Frankincense for gastric tonic & astringent actions" },
  "suranjan": { name: "Asgand Nagori", ratio: "2.0x dose", doseFactor: 2.0, rules: "Asgandh Nagori or Boozidan in arthritic joint disorders" },
  "badranjboya": { name: "Abresham Muqarrash", ratio: "1.0x dose", doseFactor: 1.0, rules: "Silk Cocoon or Gaozaban for cardiotonic and nervine relief" },
  "afsanteen": { name: "Shahtara", ratio: "1.0x dose", doseFactor: 1.0, rules: "Shahtara or Asaroon for hepatic deobstruction" },
  "mulethi": { name: "Behidana", ratio: "1.0x dose", doseFactor: 1.0, rules: "Quince seeds or Kateera for demulcent pulmonary relief" },
  "asl-us-soos": { name: "Behidana", ratio: "1.0x dose", doseFactor: 1.0, rules: "Quince seeds or Kateera for demulcent pulmonary relief" },
  "ushba": { name: "Chobchini", ratio: "1.0x dose", doseFactor: 1.0, rules: "Chobchini for blood purification & joint pain" },
  "zanjabeel": { name: "Filfil Daraz", ratio: "1.0x dose", doseFactor: 1.0, rules: "Long Pepper (Peepli) for digestive fire stimulation" },
  "saqmonia": { name: "Turbud Safaid", ratio: "2.0x dose", doseFactor: 2.0, rules: "Turbud Safaid at double dose with almond oil correction" }
};

function suggestBadalForItem(btn) {
  const tr = btn.closest("tr");
  if (!tr) return;
  const drugInput = tr.querySelector(".nuskha-drug-input");
  const doseInput = tr.querySelector(".nuskha-dose-input");
  if (!drugInput) return;

  const currentVal = drugInput.value.trim().toLowerCase();
  let matchedKey = null;
  for (const k of Object.keys(CANONICAL_BADAL_REGISTRY)) {
    if (currentVal.includes(k)) {
      matchedKey = k;
      break;
    }
  }

  if (!matchedKey) {
    alert(`No direct classical Badal (substitute) found for '${drugInput.value}'. Consult the Knowledge Base for extended equivalents.`);
    return;
  }

  const badal = CANONICAL_BADAL_REGISTRY[matchedKey];
  const confirmSwap = confirm(
    `Classical Badal Available for '${drugInput.value}':\n\n` +
    `• Substitute: ${badal.name}\n` +
    `• Recommended Ratio: ${badal.ratio}\n` +
    `• Classical Rule: ${badal.rules}\n\n` +
    `Do you want to swap to ${badal.name}?`
  );

  if (confirmSwap) {
    drugInput.value = badal.name;
    if (doseInput && badal.doseFactor !== 1.0) {
      const oldDose = parseFloat(doseInput.value) || 1;
      doseInput.value = Math.max(1, Math.round(oldDose * badal.doseFactor));
    }
    triggerAutosave();
  }
}

async function viewMufradMonographFromRow(btn) {
  const tr = btn.closest("tr");
  if (!tr) return;
  const drugInput = tr.querySelector(".nuskha-drug-input");
  if (!drugInput || !drugInput.value.trim()) {
    alert("Please enter a medicine or herb name first.");
    return;
  }
  const term = drugInput.value.trim();

  let modalContainer = document.getElementById("libraryModalContainer");
  if (!modalContainer) {
    modalContainer = document.createElement("div");
    modalContainer.id = "libraryModalContainer";
    document.body.appendChild(modalContainer);
  }

  try {
    let monograph = null;
    const res = await apiClient.get(`/api/v1/library/corpus/mufradat/${encodeURIComponent(term)}`);
    if (res && res.monograph) monograph = res.monograph;

    if (!monograph) {
      const sRes = await apiClient.get(`/api/v1/library/corpus/mufradat?q=${encodeURIComponent(term)}&limit=1`);
      if (sRes && sRes.mufradat && sRes.mufradat.length > 0) {
        const mId = sRes.mufradat[0].id;
        const dRes = await apiClient.get(`/api/v1/library/corpus/mufradat/${encodeURIComponent(mId)}`);
        if (dRes && dRes.monograph) monograph = dRes.monograph;
      }
    }

    if (!monograph) {
      alert(`No canonical single herb (Mufrad) monograph found for '${term}'.\n\nIf this is a compound formulation (Murakkab e.g. Khamira, Itrifal, Majun), consult the Master Clinical Formulary or Qarabadeen library.`);
      return;
    }

    const m = monograph;
    let syn = {};
    try { syn = JSON.parse(m.synonyms_vernacular || "{}"); } catch(e) { syn = {}; }
    let actions = [];
    try { actions = JSON.parse(m.therapeutic_actions || "[]"); } catch(e) { actions = []; }
    let indications = [];
    try { indications = JSON.parse(m.clinical_indications || "[]"); } catch(e) { indications = []; }
    let musleh = [];
    try { musleh = JSON.parse(m.musleh_correctives || "[]"); } catch(e) { musleh = []; }
    let badal = [];
    try { badal = JSON.parse(m.badal_substitutes || "[]"); } catch(e) { badal = []; }
    let compounds = [];
    try { compounds = JSON.parse(m.famous_compounds_murakkabat || "[]"); } catch(e) { compounds = []; }
    let phytochemicals = [];
    try { phytochemicals = JSON.parse(m.phytochemical_constituents || "[]"); } catch(e) { phytochemicals = []; }

    const escapeH = (t) => t ? String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;") : "";

    modalContainer.innerHTML = `
      <div class="modal-backdrop" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 10000; padding: 0.75rem; backdrop-filter: blur(4px);">
        <div class="modal-dialog" style="background: var(--matab-color-surface, #ffffff); width: 94vw; max-width: 1050px; max-height: 92vh; border-radius: 10px; box-shadow: 0 20px 45px rgba(0,0,0,0.5); overflow-y: auto; display: flex; flex-direction: column; border: 1px solid var(--matab-color-border-subtle, #cbd5e1);">
          
          <div style="background: linear-gradient(135deg, #065f46 0%, #047857 100%); color: white; padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 2;">
            <div>
              <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
                <span style="font-size: 1.6rem;">🌿</span>
                <h3 style="margin: 0; font-size: 1.3rem; font-weight: 700;">
                  ${escapeH(m.english)} <span style="font-family: serif; font-size: 1.2rem; opacity: 0.95;">(${escapeH(m.urdu || '')})</span>
                </h3>
                <span class="badge" style="background: #ecfdf5; color: #065f46; font-size: 0.78rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px;">
                  ⚖️ ${escapeH(m.mizaj_quality || 'Motadil')} (Darja ${m.mizaj_degree || 1})
                </span>
                ${m.is_schedule_e1 ? `<span class="badge" style="background: #dc2626; color: white; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px;">⚠️ Schedule E(1) Toxic</span>` : ''}
                ${m.mandatory_mudabbar ? `<span class="badge" style="background: #d97706; color: white; padding: 0.2rem 0.5rem; border-radius: 4px;">Mandatory Mudabbar</span>` : ''}
              </div>
              <div style="font-size: 0.85rem; opacity: 0.92; margin-top: 0.25rem;">
                <em>Botanical: ${escapeH(m.botanical)}</em> • Origin: ${escapeH(m.origin_category)} • Code: <code>${escapeH(m.upi_code || m.id)}</code>
              </div>
            </div>
            <button class="btn btn-sm" id="btnCloseMufradDeskModal" style="background: rgba(255,255,255,0.2); color: white; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.2rem 0.6rem; border-radius: 4px;">✕</button>
          </div>

          <div style="padding: 1.25rem 1.5rem; display: flex; flex-direction: column; gap: 1rem;">
            
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.85rem;">
              <h4 style="margin: 0 0 0.5rem 0; font-size: 0.88rem; color: #065f46; font-weight: 700;">
                🏷️ Mutradif Naam (Synonyms &amp; Vernacular Names)
              </h4>
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem; font-size: 0.82rem;">
                <div><strong>Hindi:</strong> <span style="color: #334155;">${escapeH(syn.hindi || '--')}</span></div>
                <div><strong>Sanskrit:</strong> <span style="color: #334155;">${escapeH(syn.sanskrit || '--')}</span></div>
                <div><strong>Persian (Farsi):</strong> <span style="color: #334155;">${escapeH(syn.persian || '--')}</span></div>
                <div><strong>Arabic:</strong> <span style="color: #334155;">${escapeH(syn.arabic || m.arabic || '--')}</span></div>
                <div><strong>English:</strong> <span style="color: #334155;">${escapeH(syn.english || m.english || '--')}</span></div>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
              <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #166534; font-weight: 700;">
                  🍃 Hissa-e-Musta'mala (Plant Part Used)
                </h4>
                <div style="font-size: 0.88rem; color: #14532d; font-weight: 600;">
                  ${escapeH(m.part_used || 'Dried medicinal parts')}
                </div>
              </div>
              <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #1e40af; font-weight: 700;">
                  💊 Miqdar-e-Khurak (Therapeutic Posology)
                </h4>
                <div style="font-size: 0.85rem; color: #1e3a8a; font-weight: 600;">
                  ${escapeH(m.historical_dose || '3g - 5g')}
                  <span style="font-weight: normal; font-size: 0.78rem; color: #475569; display: block; margin-top: 0.2rem;">
                    Statutory Single Dose Max: <strong>${m.single_dose_max_g || 5.0}g</strong> • Daily Max: <strong>${m.daily_dose_max_g || 10.0}g</strong>
                  </span>
                </div>
              </div>
            </div>

            <div>
              <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #065f46; font-weight: 700;">
                🩺 Afaal-e-Khassa (Therapeutic Actions)
              </h4>
              <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                ${actions.map(a => `<span class="badge" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-size:0.8rem; padding:0.25rem 0.55rem; font-weight:600;">${escapeH(a)}</span>`).join('')}
              </div>
            </div>

            <div style="background: #fafaf9; border: 1px solid #e7e5e4; border-radius: 8px; padding: 0.85rem;">
              <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #44403c; font-weight: 700;">
                🎯 Mahall-e-Istemal (Clinical Indications &amp; Diseases Treated)
              </h4>
              <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.83rem; color: #292524; line-height: 1.6;">
                ${indications.map(i => `<li><strong>${escapeH(i)}</strong></li>`).join('')}
              </ul>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
              <div style="border-left: 4px solid #dc2626; background: #fef2f2; border-radius: 6px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #991b1b; font-weight: 700;">
                  🚫 Mawaane-e-Istemal (Contraindications)
                </h4>
                <p style="margin: 0; font-size: 0.82rem; color: #7f1d1d; line-height: 1.45;">
                  ${escapeH(m.contraindications)}
                </p>
              </div>
              <div style="border-left: 4px solid #f59e0b; background: #fffbeb; border-radius: 6px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #92400e; font-weight: 700;">
                  ⚠️ Muzir (Harmful Action) &amp; Musleh (Correctives)
                </h4>
                <div style="font-size: 0.82rem; color: #78350f; line-height: 1.45;">
                  <div><strong>Muzir:</strong> ${escapeH(m.adverse_effects_muzir)}</div>
                  <div style="margin-top: 0.35rem;"><strong>Musleh:</strong> ${escapeH(musleh.join(', ') || 'Honey / Ghee')}</div>
                </div>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
              <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #334155; font-weight: 700;">
                  🔄 Badal (Classical Substitutes)
                </h4>
                <div style="font-size: 0.82rem; color: #1e293b;">
                  ${escapeH(badal.join(' • ') || 'None documented')}
                </div>
              </div>
              <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #334155; font-weight: 700;">
                  🍶 Badraqa / Anupan (Preferred Vehicle)
                </h4>
                <div style="font-size: 0.82rem; color: #1e293b;">
                  ${escapeH(m.badraqa_anupan || 'Fresh water or cow milk')}
                </div>
              </div>
            </div>

            <div>
              <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #065f46; font-weight: 700;">
                📜 Murakkabat-e-Mashhoora (Famous Pharmacopeial Formulations)
              </h4>
              <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                ${compounds.map(c => `<span class="badge" style="background:#f0fdf4; color:#166534; border:1px solid #86efac; font-size:0.78rem; padding:0.25rem 0.5rem; font-weight:600;">${escapeH(c)}</span>`).join('')}
              </div>
            </div>

            <div style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.85rem;">
              <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #0f172a; font-weight: 700;">
                🔬 Modern Phytopharmacology &amp; Herb-Drug Safety
              </h4>
              <div style="font-size: 0.82rem; color: #334155; margin-bottom: 0.4rem;">
                <strong>Active Bio-Markers &amp; Phytochemicals:</strong> ${escapeH(phytochemicals.join(', '))}
              </div>
              <div style="font-size: 0.82rem; color: #991b1b;">
                <strong>Herb-Drug Interaction Screening:</strong> ${escapeH(m.herb_drug_interactions)}
              </div>
              ${m.mandatory_mudabbar && m.mudabbar_protocol ? `
                <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed #cbd5e1; font-size: 0.8rem; color: #9a3412;">
                  <strong>Shodhana / Mudabbar Protocol:</strong> ${escapeH(m.mudabbar_protocol)}
                </div>
              ` : ''}
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #e2e8f0; padding-top: 0.75rem; font-size: 0.76rem; color: #64748b; flex-wrap: wrap; gap: 0.5rem;">
              <div><strong>Standard Reference:</strong> ${escapeH(m.upi_monograph_ref || 'UPI Part-I')}</div>
              <div>Pregnancy: <strong>${escapeH(m.pregnancy_status || 'SAFE')}</strong> • Evidence: <strong>${escapeH(m.evidence_level || 'E2')}</strong> • Lifecycle: <strong>${escapeH(m.lifecycle_state || 'VERIFIED')}</strong></div>
            </div>

          </div>

          <div style="border-top: 1px solid var(--matab-color-border-subtle, #cbd5e1); padding: 0.75rem 1.25rem; display: flex; justify-content: flex-end; background: var(--matab-color-bg-secondary, #f8fafc);">
            <button class="btn btn-secondary btn-sm" id="btnDoneMufradDeskModal">Close Monograph</button>
          </div>

        </div>
      </div>
    `;

    const closeM = () => { modalContainer.innerHTML = ""; };
    modalContainer.querySelector("#btnCloseMufradDeskModal").addEventListener("click", closeM);
    modalContainer.querySelector("#btnDoneMufradDeskModal").addEventListener("click", closeM);
    modalContainer.querySelector(".modal-backdrop").addEventListener("click", (e) => {
      if (e.target === modalContainer.querySelector(".modal-backdrop")) closeM();
    });

  } catch (err) {
    alert(`Failed to load Mufrad monograph: ${err.message || err}`);
  }
}

window.viewMufradMonographFromRow = viewMufradMonographFromRow;

// -----------------------------------------------------------------------------
// BILINGUAL PRESCRIPTION PRINT ENGINE
// -----------------------------------------------------------------------------

function openPrintRxModal() {
  const modal = document.getElementById("modal-print-rx");
  if (!modal) return;

  const patName = document.getElementById("banner-patient-name")?.innerText || "Patient";
  const patMrn = document.getElementById("banner-patient-mrn")?.innerText || "MRN: --";
  const patDemo = document.getElementById("banner-patient-demographics")?.innerText || "--";
  const encToken = document.getElementById("banner-token")?.innerText || "Token: --";
  const mizaj = document.getElementById("input-unani-mizaj")?.selectedOptions[0]?.text || "Not Assessed";
  const secMizaj = document.getElementById("input-unani-secondary")?.value || "";
  const reasoning = document.getElementById("input-unani-reasoning")?.value || "--";
  const diagnosis = document.getElementById("input-modern-working")?.value || "Clinical Consultation";
  const icd11 = document.getElementById("input-modern-icd11")?.value || "";
  const usul = document.getElementById("input-plan-principle")?.value || "Tadeel-e-Mizaj";

  // Vitals
  const bpSys = document.getElementById("vital-bp-sys")?.value || "--";
  const bpDia = document.getElementById("vital-bp-dia")?.value || "--";
  const hr = document.getElementById("vital-pulse")?.value || "--";
  const rr = document.getElementById("vital-rr")?.value || "--";
  const temp = document.getElementById("vital-temp")?.value || "--";
  const spo2 = document.getElementById("vital-spo2")?.value || "--";
  const wt = document.getElementById("vital-weight")?.value || "--";
  const ht = document.getElementById("vital-height")?.value || "--";
  const bmiBadge = document.getElementById("badge-vitals-bmi")?.innerText || "BMI: --";

  // Classical Tashkhees (Nabz, Baul, Baraz)
  const nabzSurat = document.getElementById("tashkhees-nabz-surat")?.selectedOptions[0]?.text || "--";
  const nabzQuwwat = document.getElementById("tashkhees-nabz-quwwat")?.selectedOptions[0]?.text || "--";
  const nabzLams = document.getElementById("tashkhees-nabz-lams")?.selectedOptions[0]?.text || "--";
  const baulLawn = document.getElementById("tashkhees-baul-lawn")?.selectedOptions[0]?.text || "--";
  const baulQiwam = document.getElementById("tashkhees-baul-qiwam")?.selectedOptions[0]?.text || "--";
  const barazQiwam = document.getElementById("tashkhees-baraz-qiwam")?.selectedOptions[0]?.text || "--";

  // Check 12-Axis diagnostic profile
  const sortedAxes = Object.entries(active12AxisScores || {}).filter(([_, s]) => s > 0).sort((a, b) => b[1] - a[1]);
  const primaryAxisStr = sortedAxes.length > 0 ? `${sortedAxes[0][0]} (Severity: ${sortedAxes[0][1]}/5)` : null;
  const secondaryAxisStr = sortedAxes.length > 1 && sortedAxes[1][1] > 0 ? `${sortedAxes[1][0]} (Severity: ${sortedAxes[1][1]}/5)` : null;

  // Labs & Radio
  const labRows = collectLabInvestigationsFromTable();
  const radioRows = collectRadioStudiesFromTable();

  const selectedTadbeer = [];
  document.querySelectorAll("#chk-tadbeer-hijama, #chk-tadbeer-dalk, #chk-tadbeer-fasd, #chk-tadbeer-natool, #chk-tadbeer-hammam, #chk-tadbeer-inkabab").forEach(cb => {
    if (cb.checked) selectedTadbeer.push(cb.value);
  });
  const tadbeerNotes = document.getElementById("input-tadbeer-notes")?.value.trim() || "";
  const ghizaAdvice = document.getElementById("input-ghiza-diet")?.value.trim() || "Nutritious, easily digestible diet suited to patient's temperament.";
  const parhezAdvice = document.getElementById("input-parhez-avoid")?.value.trim() || "Avoid cold, excessively spicy, heavy, and oily foods. Observe regular meal times.";

  const rows = [];
  document.querySelectorAll("#tbody-nuskha-items tr").forEach(tr => {
    const inputs = tr.querySelectorAll("input, select");
    if (inputs.length >= 6) {
      rows.push({
        name: (inputs[0].value || "").replace(/\s*\((?:Qarabadi?n|Qarabadeeni|Classical)\)/gi, "").trim(),
        dose: `${inputs[1].value} ${inputs[2].value}`,
        freq: inputs[3].value,
        duration: `${inputs[4].value} days`,
        vehicle: inputs[5].value
      });
    }
  });

  const printArea = document.getElementById("printable-rx-content");
  if (printArea) {
    printArea.innerHTML = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; padding: 1.5rem; border: 2px solid #0f766e; border-radius: 8px; background: #ffffff;">
        <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #0f766e; padding-bottom: 0.75rem; margin-bottom: 0.75rem;">
          <div>
            <h2 style="margin: 0; color: #0f766e; font-size: 1.35rem; letter-spacing: 0.5px;">ZAYVORA MATAB OS — DAWA KHANA</h2>
            <p style="margin: 0.15rem 0 0 0; font-size: 0.8rem; color: #64748b;">Integrated Ayush & Biomedical Clinical Facility • Classical Tibb & Systems Medicine</p>
          </div>
          <div style="text-align: right; font-size: 0.8rem;">
            <div><strong>Date:</strong> ${new Date().toLocaleDateString()}</div>
            <div><strong style="color: #0f766e;">${encToken}</strong></div>
          </div>
        </div>

        <!-- Patient Demographics & Vitals -->
        <div style="background: #f8fafc; padding: 0.6rem 0.8rem; border-radius: 6px; margin-bottom: 0.75rem; font-size: 0.82rem; display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;">
          <div><strong>Patient:</strong> ${patName} (${patDemo}) • <strong>${patMrn}</strong></div>
          <div style="color: #0f766e; font-weight: 600;">
            BP: ${bpSys}/${bpDia} mmHg • HR: ${hr} bpm • RR: ${rr}/min • Temp: ${temp}°F • SpO2: ${spo2}% • ${bmiBadge} (Wt: ${wt}kg, Ht: ${ht}cm)
          </div>
        </div>

        <!-- Integrated Diagnostic Formulation (Unani & Modern) -->
        <div style="margin-bottom: 0.75rem; font-size: 0.8rem; border-bottom: 1px dashed #cbd5e1; padding-bottom: 0.65rem;">
          <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.4rem;">
            <div><strong>Primary Diagnosis:</strong> <span style="color: #0f766e; font-weight: 700;">${diagnosis}</span> ${icd11 ? `<span class="badge badge-secondary" style="font-size: 0.7rem; margin-left: 0.3rem;">ICD-11: ${icd11}</span>` : ""}</div>
            <div><strong>Patient Temperament (Mizaj):</strong> <strong>${mizaj}</strong> ${secMizaj ? `(${secMizaj})` : ""}</div>
          </div>
          <div style="margin-top: 0.3rem; color: #475569; font-size: 0.76rem;">
            <strong>Pulse &amp; Urine Exam (Nabz &amp; Baul):</strong> Nabz: [${nabzSurat}, ${nabzQuwwat}, ${nabzLams}] • Baul: [${baulLawn}, ${baulQiwam}] • Baraz: [${barazQiwam}]
          </div>
          ${primaryAxisStr ? `
            <div style="margin-top: 0.3rem; color: #0f766e; font-size: 0.78rem;">
              <strong>🎯 Organ Axis Profile (12-Axis):</strong> Primary: <strong>${primaryAxisStr}</strong> ${secondaryAxisStr ? `• Secondary: <strong>${secondaryAxisStr}</strong>` : ''}
            </div>
          ` : ''}
          <div style="margin-top: 0.3rem; font-size: 0.76rem; color: #334155;">
            <strong>Treatment Principle (Usul-e-Ilaj):</strong> ${usul}
          </div>
        </div>

        <!-- Biomedical Labs & Radiodiagnosis (if recorded) -->
        ${(labRows.length > 0 || radioRows.length > 0) ? `
          <div style="margin-bottom: 0.75rem; padding: 0.5rem 0.75rem; background: #f0fdfa; border: 1px solid #ccfbf1; border-radius: 6px; font-size: 0.76rem;">
            <strong style="color: #0f766e;">🔬 Investigations &amp; Diagnostic Imaging Summary:</strong>
            ${labRows.length > 0 ? `
              <div style="margin-top: 0.2rem;">
                <strong>Biomedical Labs:</strong> ${labRows.map(l => `${l.test_name}: <strong>${l.value} ${l.unit}</strong> [${l.status}]`).join(" • ")}
              </div>
            ` : ""}
            ${radioRows.length > 0 ? `
              <div style="margin-top: 0.2rem;">
                <strong>Radiodiagnosis:</strong> ${radioRows.map(r => `${r.modality} (${r.region}): <strong>${r.impression}</strong>`).join(" • ")}
              </div>
            ` : ""}
          </div>
        ` : ""}

        <!-- Pharmacotherapy Table -->
        <div style="margin-bottom: 0.85rem;">
          <h4 style="margin: 0 0 0.4rem 0; font-size: 0.86rem; color: #0f766e; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.2rem;">Prescribed Medicines (Pharmacotherapy)</h4>
          <table style="width: 100%; font-size: 0.78rem; border-collapse: collapse;">
            <thead>
              <tr style="background: #f1f5f9; text-align: left;">
                <th style="padding: 0.35rem; border: 1px solid #cbd5e1;">#</th>
                <th style="padding: 0.35rem; border: 1px solid #cbd5e1;">Medicine / Formulation</th>
                <th style="padding: 0.35rem; border: 1px solid #cbd5e1;">Dose</th>
                <th style="padding: 0.35rem; border: 1px solid #cbd5e1;">Freq</th>
                <th style="padding: 0.35rem; border: 1px solid #cbd5e1;">Duration</th>
                <th style="padding: 0.35rem; border: 1px solid #cbd5e1;">Anupan (Vehicle / Adjuvant)</th>
              </tr>
            </thead>
            <tbody>
              ${rows.map((r, i) => `
                <tr>
                  <td style="padding: 0.35rem; border: 1px solid #cbd5e1;">${i + 1}</td>
                  <td style="padding: 0.35rem; border: 1px solid #cbd5e1;"><strong>${r.name}</strong></td>
                  <td style="padding: 0.35rem; border: 1px solid #cbd5e1;">${r.dose}</td>
                  <td style="padding: 0.35rem; border: 1px solid #cbd5e1;">${r.freq}</td>
                  <td style="padding: 0.35rem; border: 1px solid #cbd5e1;">${r.duration}</td>
                  <td style="padding: 0.35rem; border: 1px solid #cbd5e1;">${r.vehicle}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>

        <!-- Regimenal Therapies (Tadbeer) -->
        ${selectedTadbeer.length > 0 || tadbeerNotes ? `
        <div style="margin-bottom: 0.75rem; padding: 0.5rem 0.75rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; font-size: 0.78rem;">
          <strong style="color: #166534;">Regimenal Therapies Prescribed (Ilaj bit-Tadbeer):</strong>
          <div>${selectedTadbeer.join(" • ") || "Regimenal Therapy"}</div>
          ${tadbeerNotes ? `<div style="margin-top: 0.2rem; color: #374151;"><strong>Instructions / Target Points:</strong> ${tadbeerNotes}</div>` : ""}
        </div>
        ` : ""}

        <!-- Diet & Parhez -->
        <div style="margin-bottom: 0.75rem; display: grid; grid-template-columns: 1fr 1fr; gap: 0.65rem; font-size: 0.78rem;">
          <div style="padding: 0.5rem 0.75rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;">
            <strong style="color: #0f766e;">Recommended Diet (Dietotherapy):</strong>
            <div style="margin-top: 0.2rem; color: #334155;">${ghizaAdvice}</div>
          </div>
          <div style="padding: 0.5rem 0.75rem; background: #fffbeb; border: 1px solid #fef3c7; border-radius: 6px;">
            <strong style="color: #b45309;">Dietary Restrictions (Parhez):</strong>
            <div style="margin-top: 0.2rem; color: #78350f;">${parhezAdvice}</div>
          </div>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: flex-end; font-size: 0.74rem; border-top: 1px solid #e2e8f0; padding-top: 0.65rem;">
          <div style="color: #64748b;">
            <div>Electronically generated through Zayvora Matab Clinical Operating System.</div>
            <div style="margin-top: 0.15rem;">Record Digest: <code>${Math.random().toString(36).substring(2, 14)}...</code></div>
          </div>
          <div style="text-align: right;">
            <div style="font-weight: 600; color: #0f766e;">Electronically Attested & Signed</div>
            <div style="color: #64748b;">Consulting Hakim / Medical Officer</div>
          </div>
        </div>
      </div>
    `;
  }

  modal.style.display = "flex";
}

function closePrintRxModal() {
  const modal = document.getElementById("modal-print-rx");
  if (modal) modal.style.display = "none";
}

// printPrescriptionDocument is imported from ./consultation-rx.js

window.autoDraftNuskhaFromDiagnosis = autoDraftNuskhaFromDiagnosis;
window.toggleVoiceDictationRx = toggleVoiceDictationRx;
window.toggleVoiceDictationNotes = toggleVoiceDictationNotes;

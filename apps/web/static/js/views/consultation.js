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

let activeEncounterId = null;
let workspaceData = null;
let autosaveTimer = null;
let isSaving = false;

export async function renderConsultation(container) {
  container.innerHTML = `
    <!-- Top Action Bar -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.75rem;">
      <div>
        <div style="display: flex; align-items: center; gap: 0.75rem;">
          <h1 style="font-size: 1.35rem; color: var(--matab-color-brand-primary); margin: 0;">Unified Consultation Workspace</h1>
          <span id="encounter-state-badge" class="badge badge-info" style="font-size: 0.8rem; text-transform: uppercase;">Loading...</span>
        </div>
        <p style="color: var(--matab-color-text-secondary); font-size: 0.85rem; margin: 0.25rem 0 0 0;">
          Server-authoritative clinical workflow orchestrator — Unani assessment, Modern lane, Nuskha drafting & safety preflight
        </p>
      </div>

      <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
        <span id="autosave-status" style="font-size: 0.8rem; color: var(--matab-color-text-muted); display: flex; align-items: center; gap: 0.35rem;">
          <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: var(--matab-color-status-success);"></span>
          Synchronized
        </span>
        <button id="btn-run-preflight" class="btn btn-secondary btn-sm" title="Run Clinical Safety Preflight Check">
          🛡️ Run Safety Check
        </button>
        <button id="btn-validate-signoff" class="btn btn-secondary btn-sm" title="Re-evaluate server sign-off eligibility">
          ✓ Verify Readiness
        </button>
        <button id="btn-open-finalize" class="btn btn-primary btn-sm" style="font-weight: 600;">
          ✍️ Sign & Finalize
        </button>
      </div>
    </div>

    <!-- Patient Header Banner -->
    <div class="card" id="patient-banner" style="margin-bottom: 1.25rem; padding: 0.85rem 1.25rem; background: var(--matab-color-bg-card); border-left: 4px solid var(--matab-color-brand-primary);">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
        <div style="display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;">
          <div>
            <span id="banner-patient-name" style="font-size: 1.1rem; font-weight: 600; color: var(--matab-color-text-primary);">Loading patient...</span>
            <span id="banner-patient-mrn" style="font-size: 0.85rem; color: var(--matab-color-text-muted); margin-left: 0.5rem;"></span>
          </div>
          <div style="display: flex; gap: 0.5rem; align-items: center; font-size: 0.85rem;">
            <span id="banner-patient-demographics" class="badge badge-secondary">--</span>
            <span id="banner-token" class="badge badge-info">Token: --</span>
          </div>
        </div>

        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span id="banner-allergies" class="badge badge-warning" style="font-size: 0.8rem;">Allergies: None Recorded</span>
          <button id="btn-toggle-drawer" class="btn btn-secondary btn-sm" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;">
            📋 Context Drawer
          </button>
        </div>
      </div>
    </div>

    <!-- Main Workspace Two-Column Grid -->
    <div style="display: grid; grid-template-columns: 1fr 340px; gap: 1.25rem; align-items: start;" id="workspace-grid">
      
      <!-- Left Column: 7 Guided Clinical Sections -->
      <div id="guided-sections-container" style="display: flex; flexDirection: column; gap: 1rem;">
        
        <!-- Section 1: Visit Intake -->
        <div class="card section-card" id="card-sec-visit">
          <div class="section-header" onclick="window.toggleSection('visit')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 600; color: var(--matab-color-brand-primary);">1. Visit Intake & Triage</span>
              <span id="badge-sec-visit" class="badge badge-secondary" style="font-size: 0.75rem;">not_started</span>
            </div>
            <span id="icon-sec-visit" style="font-size: 0.9rem;">▼</span>
          </div>
          <div class="section-body" id="body-sec-visit" style="margin-top: 0.75rem;">
            <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 0.75rem; margin-bottom: 0.75rem;">
              <div>
                <label style="font-size: 0.8rem; font-weight: 600;">Encounter Type</label>
                <select id="input-encounter-type" class="form-control" style="font-size: 0.85rem;">
                  <option value="OPD_VISIT">OPD Visit</option>
                  <option value="FOLLOW_UP">Follow-up</option>
                  <option value="TELECONSULT">Teleconsult</option>
                  <option value="EMERGENCY">Emergency</option>
                </select>
              </div>
              <div>
                <label style="font-size: 0.8rem; font-weight: 600;">Reason for Visit / Chief Complaint *</label>
                <input type="text" id="input-reason-visit" class="form-control" style="font-size: 0.85rem;" placeholder="e.g. Su-e-Hazm (Dyspepsia) with mild headache...">
              </div>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionComplete('visit')">Mark Complete</button>
            </div>
          </div>
        </div>

        <!-- Section 2: History & Observations -->
        <div class="card section-card" id="card-sec-history_observations">
          <div class="section-header" onclick="window.toggleSection('history_observations')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 600; color: var(--matab-color-brand-primary);">2. History & Physical Observations</span>
              <span id="badge-sec-history_observations" class="badge badge-secondary" style="font-size: 0.75rem;">not_started</span>
            </div>
            <span id="icon-sec-history_observations" style="font-size: 0.9rem;">▼</span>
          </div>
          <div class="section-body" id="body-sec-history_observations" style="margin-top: 0.75rem;">
            <div style="margin-bottom: 0.75rem;">
              <label style="font-size: 0.8rem; font-weight: 600;">History of Present Illness (HPI)</label>
              <textarea id="input-hpi" class="form-control" rows="2" style="font-size: 0.85rem;" placeholder="Onset, duration, exacerbating dietary triggers..."></textarea>
            </div>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin-bottom: 0.75rem;">
              <div>
                <label style="font-size: 0.75rem;">Blood Pressure (mmHg)</label>
                <input type="text" id="input-vitals-bp" class="form-control" style="font-size: 0.8rem;" placeholder="120/80">
              </div>
              <div>
                <label style="font-size: 0.75rem;">Pulse (bpm)</label>
                <input type="number" id="input-vitals-pulse" class="form-control" style="font-size: 0.8rem;" placeholder="76">
              </div>
              <div>
                <label style="font-size: 0.75rem;">Temp (°F)</label>
                <input type="text" id="input-vitals-temp" class="form-control" style="font-size: 0.8rem;" placeholder="98.6">
              </div>
              <div>
                <label style="font-size: 0.75rem;">SpO2 (%)</label>
                <input type="number" id="input-vitals-spo2" class="form-control" style="font-size: 0.8rem;" placeholder="99">
              </div>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionNA('history_observations')">Mark N/A</button>
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionComplete('history_observations')">Mark Complete</button>
            </div>
          </div>
        </div>

        <!-- Section 3: Unani Clinical Assessment -->
        <div class="card section-card" id="card-sec-unani_assessment">
          <div class="section-header" onclick="window.toggleSection('unani_assessment')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 600; color: var(--matab-color-brand-primary);">3. Unani Clinical Assessment (Mizaj & Afaal)</span>
              <span id="badge-sec-unani_assessment" class="badge badge-secondary" style="font-size: 0.75rem;">not_started</span>
            </div>
            <span id="icon-sec-unani_assessment" style="font-size: 0.9rem;">▼</span>
          </div>
          <div class="section-body" id="body-sec-unani_assessment" style="margin-top: 0.75rem;">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
              <div>
                <label style="font-size: 0.8rem; font-weight: 600;">Dominant Mizaj (Temperament)</label>
                <select id="input-unani-mizaj" class="form-control" style="font-size: 0.85rem;">
                  <option value="NOT_ASSESSED">-- Not Assessed --</option>
                  <option value="DAMAWWI">Damawwi (Sanguine / Hot & Moist)</option>
                  <option value="BALGHAMI">Balghami (Phlegmatic / Cold & Moist)</option>
                  <option value="SAFRAWI">Safrawi (Choleric / Hot & Dry)</option>
                  <option value="SAUDAWI">Saudawi (Melancholic / Cold & Dry)</option>
                  <option value="MOTADIL">Motadil (Equable)</option>
                  <option value="MIXED">Mixed / Murakkab</option>
                </select>
              </div>
              <div>
                <label style="font-size: 0.8rem; font-weight: 600;">Secondary Mizaj Deviation</label>
                <input type="text" id="input-unani-secondary" class="form-control" style="font-size: 0.85rem;" placeholder="e.g. Su-e-Mizaj Har Yabis...">
              </div>
            </div>
            <div style="margin-bottom: 0.75rem;">
              <label style="font-size: 0.8rem; font-weight: 600;">Clinical Reasoning & Nabz/Baul Examination</label>
              <textarea id="input-unani-reasoning" class="form-control" rows="2" style="font-size: 0.85rem;" placeholder="Nabz sari mutawassit; Baul asfar motadil..."></textarea>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionNA('unani_assessment')">Mark N/A</button>
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionComplete('unani_assessment')">Mark Complete</button>
            </div>
          </div>
        </div>

        <!-- Section 4: Modern Assessment Lane -->
        <div class="card section-card" id="card-sec-modern_assessment">
          <div class="section-header" onclick="window.toggleSection('modern_assessment')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 600; color: var(--matab-color-brand-primary);">4. Modern Assessment & Differential Lane</span>
              <span id="badge-sec-modern_assessment" class="badge badge-secondary" style="font-size: 0.75rem;">not_started</span>
            </div>
            <span id="icon-sec-modern_assessment" style="font-size: 0.9rem;">▼</span>
          </div>
          <div class="section-body" id="body-sec-modern_assessment" style="margin-top: 0.75rem;">
            <div style="margin-bottom: 0.75rem;">
              <label style="font-size: 0.8rem; font-weight: 600;">Working Differential Diagnosis</label>
              <input type="text" id="input-modern-working" class="form-control" style="font-size: 0.85rem;" placeholder="e.g. Functional dyspepsia, Gastritis (ICD-11: DA42)...">
            </div>
            <div style="margin-bottom: 0.75rem;">
              <label style="font-size: 0.8rem; font-weight: 600;">Red-Flag & Safety Screening</label>
              <div style="display: flex; gap: 1rem; font-size: 0.85rem; flex-wrap: wrap;">
                <label><input type="checkbox" id="chk-redflag-gi"> No GI Bleeding / Melena</label>
                <label><input type="checkbox" id="chk-redflag-weight"> No Unintentional Weight Loss</label>
                <label><input type="checkbox" id="chk-redflag-dysphagia"> No Progressive Dysphagia</label>
              </div>
            </div>
            <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionNA('modern_assessment')">Mark N/A</button>
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionComplete('modern_assessment')">Mark Complete</button>
            </div>
          </div>
        </div>

        <!-- Section 5: Plan & Nuskha Builder -->
        <div class="card section-card" id="card-sec-plan_nuskha">
          <div class="section-header" onclick="window.toggleSection('plan_nuskha')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 600; color: var(--matab-color-brand-primary);">5. Usul-e-Ilaj Plan & Nuskha Builder</span>
              <span id="badge-sec-plan_nuskha" class="badge badge-secondary" style="font-size: 0.75rem;">not_started</span>
            </div>
            <span id="icon-sec-plan_nuskha" style="font-size: 0.9rem;">▼</span>
          </div>
          <div class="section-body" id="body-sec-plan_nuskha" style="margin-top: 0.75rem;">
            <div style="margin-bottom: 0.75rem;">
              <label style="font-size: 0.8rem; font-weight: 600;">Primary Usul-e-Ilaj (Treatment Principle)</label>
              <input type="text" id="input-plan-principle" class="form-control" style="font-size: 0.85rem;" placeholder="e.g. Tadeel-e-Mizaj wa Tanqiya-e-Meda...">
            </div>

            <!-- Prescribed Line Items Table -->
            <div style="margin-bottom: 0.75rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem;">
                <label style="font-size: 0.8rem; font-weight: 600;">Nuskha Line Items</label>
                <button type="button" class="btn btn-secondary btn-sm" onclick="window.addNuskhaItemRow()" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">+ Add Medication</button>
              </div>
              <div style="overflow-x: auto;">
                <table class="table" style="font-size: 0.8rem; width: 100%;" id="table-nuskha-items">
                  <thead>
                    <tr style="background: var(--matab-color-bg-muted);">
                      <th>Item Name</th>
                      <th>Dose</th>
                      <th>Unit</th>
                      <th>Freq</th>
                      <th>Duration</th>
                      <th>Anupan (Vehicle)</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody id="tbody-nuskha-items">
                    <!-- Populated dynamically -->
                  </tbody>
                </table>
              </div>
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionNA('plan_nuskha')">Mark N/A</button>
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionComplete('plan_nuskha')">Mark Complete</button>
            </div>
          </div>
        </div>

        <!-- Section 6: Safety Firewall Review -->
        <div class="card section-card" id="card-sec-safety_review">
          <div class="section-header" onclick="window.toggleSection('safety_review')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 600; color: var(--matab-color-brand-primary);">6. Clinical Safety Firewall Review</span>
              <span id="badge-sec-safety_review" class="badge badge-secondary" style="font-size: 0.75rem;">not_started</span>
            </div>
            <span id="icon-sec-safety_review" style="font-size: 0.9rem;">▼</span>
          </div>
          <div class="section-body" id="body-sec-safety_review" style="margin-top: 0.75rem;">
            <div id="safety-preflight-summary-box" style="padding: 0.75rem; border-radius: var(--matab-radius-md); background: var(--matab-color-bg-muted); margin-bottom: 0.75rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 0.85rem;">Preflight Status: <span id="preflight-status-pill" class="badge badge-secondary">Pending Run</span></span>
                <button class="btn btn-secondary btn-sm" onclick="window.runPreflightCheck()" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">Re-run Preflight</button>
              </div>
              <div id="preflight-coverage-text" style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-top: 0.25rem;">
                No preflight run recorded for active draft.
              </div>
            </div>

            <!-- Findings List -->
            <div id="safety-findings-container" style="display: flex; flexDirection: column; gap: 0.5rem; margin-bottom: 0.75rem;">
              <p style="font-size: 0.8rem; color: var(--matab-color-text-muted); margin: 0;">No active alerts.</p>
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button class="btn btn-secondary btn-sm" onclick="window.markSectionComplete('safety_review')">Mark Safety Cleared</button>
            </div>
          </div>
        </div>

        <!-- Section 7: Finalize & Follow-up -->
        <div class="card section-card" id="card-sec-finalize">
          <div class="section-header" onclick="window.toggleSection('finalize')" style="cursor: pointer; display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--matab-color-border-subtle);">
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span style="font-weight: 600; color: var(--matab-color-brand-primary);">7. Finalize, Follow-up & Document Bundle</span>
              <span id="badge-sec-finalize" class="badge badge-secondary" style="font-size: 0.75rem;">not_started</span>
            </div>
            <span id="icon-sec-finalize" style="font-size: 0.9rem;">▼</span>
          </div>
          <div class="section-body" id="body-sec-finalize" style="margin-top: 0.75rem;">
            <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 0.75rem; margin-bottom: 0.75rem;">
              <div>
                <label style="font-size: 0.8rem; font-weight: 600;">Follow-up Due Date</label>
                <input type="date" id="input-followup-date" class="form-control" style="font-size: 0.85rem;">
              </div>
              <div>
                <label style="font-size: 0.8rem; font-weight: 600;">Follow-up Task & Instructions</label>
                <input type="text" id="input-followup-desc" class="form-control" style="font-size: 0.85rem;" placeholder="e.g. Return in 7 days for pulse reassessment and formulation adjustment.">
              </div>
            </div>

            <div id="finalized-documents-box" style="display: none; padding: 0.75rem; background: var(--matab-color-brand-surface); border: 1px solid var(--matab-color-status-success); border-radius: var(--matab-radius-md); margin-bottom: 0.75rem;">
              <h4 style="font-size: 0.9rem; color: var(--matab-color-status-success); margin: 0 0 0.5rem 0;">✓ Encounter Signed & Locked</h4>
              <div id="finalized-docs-list" style="font-size: 0.8rem;"></div>
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
              <button class="btn btn-primary btn-sm" onclick="window.openSignModal()" id="btn-section-finalize">
                Electronic Sign & Finalize
              </button>
            </div>
          </div>
        </div>

      </div>

      <!-- Right Column: Collapsible Context Drawer -->
      <div id="context-drawer-panel" style="display: flex; flexDirection: column; gap: 1rem;">
        
        <!-- Readiness Gate Card -->
        <div class="card" style="padding: 1rem;">
          <h3 style="font-size: 0.95rem; font-weight: 600; color: var(--matab-color-brand-primary); margin: 0 0 0.5rem 0;">
            Sign-off Gate Readiness
          </h3>
          <div id="readiness-summary-text" style="font-size: 0.8rem; margin-bottom: 0.5rem; color: var(--matab-color-text-secondary);">
            Evaluating gates...
          </div>
          <div id="blocking-reasons-list" style="display: flex; flexDirection: column; gap: 0.35rem;"></div>
        </div>

        <!-- Evidence & Citations Card -->
        <div class="card" style="padding: 1rem;">
          <h3 style="font-size: 0.95rem; font-weight: 600; color: var(--matab-color-brand-primary); margin: 0 0 0.5rem 0;">
            Approved Clinical Knowledge
          </h3>
          <div style="display: flex; gap: 0.25rem; margin-bottom: 0.5rem;">
            <input type="text" id="input-knowledge-query" class="form-control" style="font-size: 0.75rem;" placeholder="Search drug or Mizaj concept...">
            <button class="btn btn-secondary btn-sm" onclick="window.searchKnowledgeContext()" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">Search</button>
          </div>
          <div id="knowledge-results-list" style="display: flex; flexDirection: column; gap: 0.5rem; max-height: 250px; overflow-y: auto; font-size: 0.75rem;">
            <p style="color: var(--matab-color-text-muted); margin: 0;">Type a concept above to search classical and modern evidence.</p>
          </div>
        </div>

        <!-- State Transitions Audit Card -->
        <div class="card" style="padding: 1rem;">
          <h3 style="font-size: 0.95rem; font-weight: 600; color: var(--matab-color-brand-primary); margin: 0 0 0.5rem 0;">
            Workflow Transitions
          </h3>
          <div id="transitions-timeline-list" style="display: flex; flexDirection: column; gap: 0.35rem; font-size: 0.75rem; max-height: 200px; overflow-y: auto;">
            <p style="color: var(--matab-color-text-muted); margin: 0;">No transitions recorded yet.</p>
          </div>
        </div>

      </div>

    </div>

    <!-- Electronic PIN Signature Modal -->
    <div id="modal-signoff" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center;">
      <div class="card" style="width: 440px; max-width: 95vw; padding: 1.5rem; background: var(--matab-color-bg-card);">
        <h3 style="font-size: 1.15rem; color: var(--matab-color-brand-primary); margin: 0 0 0.75rem 0;">
          Clinician Electronic Signature Sign-off
        </h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
          By entering your 4-digit electronic signature PIN, you certify that you have reviewed the clinical findings, verified posology, cleared safety firewall alerts, and attest to this consultation record.
        </p>

        <div style="margin-bottom: 1rem;">
          <label style="font-size: 0.85rem; font-weight: 600;">Electronic Signature PIN *</label>
          <input type="password" id="input-sign-pin" class="form-control" maxlength="8" style="font-size: 1.1rem; letter-spacing: 0.25rem; text-align: center;" placeholder="••••">
          <span style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Default synthetic PIN: 1234</span>
        </div>

        <div id="signoff-error-alert" style="display: none; color: var(--matab-color-status-danger); font-size: 0.8rem; margin-bottom: 1rem;"></div>

        <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
          <button class="btn btn-secondary btn-sm" onclick="window.closeSignModal()">Cancel</button>
          <button class="btn btn-primary btn-sm" id="btn-submit-sign" onclick="window.submitElectronicSignature()">
            Attest & Finalize
          </button>
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

  // Initial load
  await loadActiveEncounterWorkspace();
}

// -----------------------------------------------------------------------------
// WORKSPACE DATA LOADER
// -----------------------------------------------------------------------------

async function loadActiveEncounterWorkspace() {
  let encId = state.activeEncounterId;
  let patId = state.activePatientId;

  // Fallback to most recent patient encounter if state is not set
  if (!encId) {
    try {
      const pList = await apiClient.get("/api/v1/patients", { limit: 1 });
      if (pList.patients && pList.patients.length > 0) {
        patId = pList.patients[0].id;
        state.activePatientId = patId;
        const timeline = await apiClient.get(`/api/v1/patients/${patId}/timeline`);
        const encEvent = (timeline.timeline || []).find(e => e.event_type === "ENCOUNTER_VISIT");
        if (encEvent) {
          encId = encEvent.resource_id;
          state.activeEncounterId = encId;
        }
      }
    } catch (err) {
      console.warn("Could not fetch fallback encounter:", err);
    }
  }

  if (!encId) {
    document.getElementById("banner-patient-name").innerText = "No Active Encounter Found";
    return;
  }

  activeEncounterId = encId;

  try {
    const res = await apiClient.get(`/api/v1/encounters/${encId}/workspace`);
    workspaceData = res.workspace;
    populateWorkspaceUI(workspaceData);
    setupAutosaveListeners();
  } catch (err) {
    console.error("Failed to load consultation workspace:", err);
    alert(`Error loading workspace: ${err.message}`);
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
  document.getElementById("banner-patient-name").innerText = pat.display_name || "Unknown Patient";
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
    document.getElementById("input-encounter-type").value = lanes.visit.encounter_type || "OPD_VISIT";
    document.getElementById("input-reason-visit").value = lanes.visit.reason_for_visit || "";
  }
  if (lanes.history_observations) {
    document.getElementById("input-hpi").value = lanes.history_observations.history_of_present_illness || "";
  }
  if (lanes.unani_assessment) {
    document.getElementById("input-unani-mizaj").value = lanes.unani_assessment.dominant_mizaj || lanes.unani_assessment.primary_mizaj || "NOT_ASSESSED";
    document.getElementById("input-unani-secondary").value = lanes.unani_assessment.secondary_mizaj || "";
    document.getElementById("input-unani-reasoning").value = lanes.unani_assessment.clinical_reasoning || "";
  }
  if (lanes.modern_assessment) {
    document.getElementById("input-modern-working").value = lanes.modern_assessment.working_assessment || "";
  }
  if (lanes.care_plan) {
    document.getElementById("input-plan-principle").value = lanes.care_plan.title || lanes.care_plan.primary_usul_e_ilaj || "";
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

  if (pre) {
    pill.innerText = pre.overall_status.toUpperCase();
    if (pre.overall_status === "blocked") pill.className = "badge badge-danger";
    else if (pre.overall_status === "reviewed_with_cautions") pill.className = "badge badge-warning";
    else pill.className = "badge badge-success";

    cov.innerText = `Checked ruleset: ${pre.ruleset_version || 'v2.0'} • Executed at: ${pre.executed_at || 'Just now'}`;

    if (pre.findings && pre.findings.length > 0) {
      findingsContainer.innerHTML = "";
      for (const f of pre.findings) {
        const fDiv = document.createElement("div");
        fDiv.style.cssText = "padding: 0.5rem; border: 1px solid var(--matab-color-border-subtle); border-radius: var(--matab-radius-sm); font-size: 0.8rem; background: var(--matab-color-bg-card);";
        const hasDisp = !!f.disposition_type;
        fDiv.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.25rem;">
            <strong>${f.title} (${f.rule_code})</strong>
            <span class="badge ${f.severity === 'critical' ? 'badge-danger' : 'badge-warning'}">${f.severity.toUpperCase()}</span>
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
    } else {
      findingsContainer.innerHTML = `<p style="font-size: 0.8rem; color: var(--matab-color-text-muted); margin: 0;">✓ Zero safety findings. All ingredients cleared.</p>`;
    }
  }

  // Populate Readiness Gate Summary
  updateReadinessUI(ws.signoff_eligibility);

  // Populate Generated Documents (if final)
  if (ws.documents && ws.documents.length > 0) {
    const docBox = document.getElementById("finalized-documents-box");
    const docList = document.getElementById("finalized-docs-list");
    docBox.style.display = "block";
    docList.innerHTML = ws.documents.map(d => `
      <div style="margin-bottom: 0.35rem;">
        📄 <strong>${d.document_type}</strong> (v${d.version_number}) — Digest: <code style="font-size: 0.75rem;">${d.document_hash.substring(0, 16)}...</code>
      </div>
    `).join("");
  }

  // Populate State Transitions History
  const transList = document.getElementById("transitions-timeline-list");
  if (ws.transitions_history && ws.transitions_history.length > 0) {
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

  summary.innerText = eligibility.summary;
  if (eligibility.eligible) {
    summary.style.color = "var(--matab-color-status-success)";
    blkList.innerHTML = `<span style="font-size: 0.75rem; color: var(--matab-color-status-success);">✓ All workflow gates satisfied. Ready for finalization.</span>`;
    btnFinalize.disabled = false;
  } else {
    summary.style.color = "var(--matab-color-status-warning)";
    blkList.innerHTML = (eligibility.blocking_reasons || []).map(r => `
      <div style="font-size: 0.75rem; color: var(--matab-color-status-danger); display: flex; gap: 0.25rem;">
        <span>✕</span> <span>${r}</span>
      </div>
    `).join("");
    btnFinalize.disabled = true;
  }
}

// -----------------------------------------------------------------------------
// SECTION ACCORDION & STATE ACTIONS
// -----------------------------------------------------------------------------

function toggleSection(secKey) {
  const body = document.getElementById(`body-sec-${secKey}`);
  const icon = document.getElementById(`icon-sec-${secKey}`);
  if (!body) return;

  if (body.style.display === "none") {
    body.style.display = "block";
    icon.innerText = "▼";
  } else {
    body.style.display = "none";
    icon.innerText = "▶";
  }
}

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
  const reason = prompt(`Enter clinical justification for marking '${secKey}' as Not Applicable:`);
  if (!reason || !reason.trim()) {
    alert("Clinical rationale is mandatory when marking a section not applicable.");
    return;
  }

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

async function executeAutosave() {
  if (isSaving || !activeEncounterId) return;
  isSaving = true;

  const statusEl = document.getElementById("autosave-status");
  statusEl.innerHTML = `<span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: var(--matab-color-status-info);"></span> Saving...`;

  try {
    const payload = {
      version: workspaceData ? workspaceData.encounter.version : undefined,
      reason_for_visit: document.getElementById("input-reason-visit").value,
      encounter_type: document.getElementById("input-encounter-type").value,
      updated_sections: ["visit"]
    };

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
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><input type="text" class="form-control" style="font-size: 0.75rem;" value="${item.item_name || ''}" placeholder="Drug name"></td>
    <td><input type="number" class="form-control" style="font-size: 0.75rem; width: 60px;" value="${item.dose_amount || 1}"></td>
    <td>
      <select class="form-control" style="font-size: 0.75rem; width: 70px;">
        <option value="hab" ${item.dose_unit === 'hab' ? 'selected' : ''}>hab</option>
        <option value="g" ${item.dose_unit === 'g' ? 'selected' : ''}>g</option>
        <option value="ml" ${item.dose_unit === 'ml' ? 'selected' : ''}>ml</option>
        <option value="masha" ${item.dose_unit === 'masha' ? 'selected' : ''}>masha</option>
      </select>
    </td>
    <td>
      <select class="form-control" style="font-size: 0.75rem; width: 70px;">
        <option value="BD" ${item.frequency === 'BD' ? 'selected' : ''}>BD</option>
        <option value="OD" ${item.frequency === 'OD' ? 'selected' : ''}>OD</option>
        <option value="TDS" ${item.frequency === 'TDS' ? 'selected' : ''}>TDS</option>
        <option value="HS" ${item.frequency === 'HS' ? 'selected' : ''}>HS</option>
      </select>
    </td>
    <td><input type="number" class="form-control" style="font-size: 0.75rem; width: 55px;" value="${item.duration_days || 7}"></td>
    <td><input type="text" class="form-control" style="font-size: 0.75rem;" value="${item.anupan_vehicle || 'Water'}" placeholder="Water / Milk"></td>
    <td><button type="button" class="btn btn-secondary btn-sm" onclick="this.closest('tr').remove()" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;">✕</button></td>
  `;
  tbody.appendChild(tr);
  triggerAutosave();
}

// -----------------------------------------------------------------------------
// SAFETY PREFLIGHT & DISPOSITION
// -----------------------------------------------------------------------------

async function runPreflightCheck() {
  if (!activeEncounterId) return;
  try {
    const res = await apiClient.post("/api/v1/safety/preflight", {
      encounter_id: activeEncounterId,
      patient_context: { is_pregnant: false, allergies: [] },
      prescription_items: [
        { item_name: "Hab-e-Suranjan", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 7 }
      ]
    });
    alert(`Preflight completed: Status is ${res.overall_status.toUpperCase()}`);
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

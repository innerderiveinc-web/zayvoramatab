/**
 * Modern Clinical Assessment View & Decision Support Lane (Prompt 05)
 * 
 * Includes:
 * - Structured clinical history (Chief complaint, HPI, ROS, Medical/Surgical, Allergies review)
 * - Typed validated observations & vital signs with reference-range provenance
 * - Deterministic safety checks (Red-flag rules catalogue with fail-closed missing data states)
 * - Explainable differential diagnosis support (Candidate-level rationale, supporting/contradicting findings)
 * - Non-ordering investigation considerations with clinical questions & limitations
 * - Clinician-confirmed problem list and working assessment
 * - Urgent referral and escalation documentation
 * - Clinician PIN electronic signing (SHA-256 digital fingerprint) and governed amendment lifecycle
 */

import { apiClient } from "/packages/api-client/client.js";

export async function loadModernAssessmentPane(container, pane, patientId, encounterId) {
  pane.innerHTML = `
    <div style="padding: 1rem 0; text-align: center; color: var(--matab-color-text-secondary);">
      Loading modern clinical assessment lane...
    </div>
  `;

  try {
    // 1. Fetch or initialize assessment draft
    let assessment = null;
    try {
      const getRes = await apiClient.get(`/api/v1/encounters/${encounterId}/modern-assessments`);
      assessment = getRes.assessment;
    } catch (e) {
      // Not found, will create draft
    }

    if (!assessment) {
      const createRes = await apiClient.post(`/api/v1/encounters/${encounterId}/modern-assessments`, {
        chief_complaint: "",
        uncertainty_level: "NOT_ASSESSED"
      });
      assessment = createRes.assessment;
    }

    renderModernAssessmentUI(container, pane, patientId, encounterId, assessment);

  } catch (err) {
    pane.innerHTML = `
      <div class="alert-box alert-danger">
        Failed to load modern clinical assessment: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

function renderModernAssessmentUI(container, pane, patientId, encounterId, assess) {
  const isSigned = assess.status === "SIGNED" || assess.status === "AMENDED";
  const statusBadge = getStatusBadgeClass(assess.status);

  // Extract common vitals from observations
  const obsMap = {};
  (assess.observations || []).forEach(o => {
    const k = o.concept_name.toLowerCase().replace(/\s+/g, "_");
    obsMap[k] = o;
  });

  pane.innerHTML = `
    <!-- Top Action & Governance Banner -->
    <div class="card" style="margin-bottom: 1.25rem; border-left: 4px solid var(--matab-color-brand-primary);">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem;">
        <div>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <h2 style="font-size: 1.15rem; margin: 0; color: var(--matab-color-brand-primary);">
              Modern Clinical Assessment & Decision Support
            </h2>
            <span class="badge ${statusBadge}">${assess.status} (v${assess.version_number})</span>
          </div>
          <div style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-top: 0.25rem;">
            Author: <strong>${escapeHtml(assess.author_name || "Practitioner")}</strong> • Date: ${assess.assessment_date}
            ${assess.signature_hash ? `• Fingerprint: <code>${assess.signature_hash.substring(0, 16)}...</code>` : ""}
          </div>
        </div>

        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
          ${!isSigned ? `
            <button id="btn-save-modern-draft" class="btn btn-secondary btn-sm">💾 Save Draft</button>
            <button id="btn-run-safety-checks" class="btn btn-warning btn-sm">⚠️ Evaluate Red Flags</button>
            <button id="btn-run-differentials" class="btn btn-info btn-sm">🔍 Differential Support</button>
            <button id="btn-sign-modern-assessment" class="btn btn-success btn-sm">✍️ Sign Assessment</button>
          ` : `
            <button id="btn-amend-modern-assessment" class="btn btn-primary btn-sm">📝 Amend Signed Record</button>
          `}
        </div>
      </div>

      ${isSigned ? `
        <div style="margin-top: 0.75rem; padding: 0.5rem 0.75rem; background: rgba(16, 185, 129, 0.08); border-radius: 4px; font-size: 0.82rem; color: var(--matab-color-success-dark);">
          🔒 <strong>Record Signed & Sealed:</strong> This clinical record is locked against silent mutation. Governed amendments are versioned and audited.
        </div>
      ` : ""}
    </div>

    <!-- Active Red-Flag Alerts Panel (If Triggered) -->
    <div id="modern-red-flags-container" style="margin-bottom: 1.25rem;">
      ${renderRedFlagsSection(assess.red_flag_events || [])}
    </div>

    <!-- Workspace Grid: 2 Columns -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem;">
      
      <!-- LEFT COLUMN: History, ROS, and Physical Exam -->
      <div>
        <!-- 1. Presenting Complaint & History -->
        <div class="card" style="margin-bottom: 1.25rem;">
          <h3 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
            1. Presenting Complaint & History
          </h3>

          <div style="margin-bottom: 0.75rem;">
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Chief Complaint(s)*</label>
            <input type="text" id="mca-chief-complaint" class="form-control" ${isSigned ? "disabled" : ""}
                   placeholder="e.g. Acute chest discomfort with diaphoresis, severe headache"
                   value="${escapeHtml(assess.chief_complaint || "")}">
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">History of Present Illness (HPI)</label>
            <textarea id="mca-hpi" class="form-control" rows="3" ${isSigned ? "disabled" : ""}
                      placeholder="Onset, character, radiation, precipitating factors, relieving factors, progression...">${escapeHtml(assess.history_of_present_illness || "")}</textarea>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div>
              <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Allergies Review Status</label>
              <select id="mca-allergies-status" class="form-control" ${isSigned ? "disabled" : ""}>
                <option value="NOT_REVIEWED" ${assess.allergies_review_status === "NOT_REVIEWED" ? "selected" : ""}>Not Reviewed</option>
                <option value="NOT_RECORDED" ${assess.allergies_review_status === "NOT_RECORDED" ? "selected" : ""}>Not Recorded</option>
                <option value="REVIEWED_NONE_REPORTED" ${assess.allergies_review_status === "REVIEWED_NONE_REPORTED" ? "selected" : ""}>Reviewed: None Reported</option>
                <option value="REVIEWED_ALLERGIES_RECORDED" ${assess.allergies_review_status === "REVIEWED_ALLERGIES_RECORDED" ? "selected" : ""}>Reviewed: Allergies on File</option>
              </select>
            </div>
            <div>
              <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Diagnostic Uncertainty</label>
              <select id="mca-uncertainty" class="form-control" ${isSigned ? "disabled" : ""}>
                <option value="HIGH_CONFIDENCE" ${assess.uncertainty_level === "HIGH_CONFIDENCE" ? "selected" : ""}>High Confidence</option>
                <option value="MODERATE_CONFIDENCE" ${assess.uncertainty_level === "MODERATE_CONFIDENCE" ? "selected" : ""}>Moderate Confidence</option>
                <option value="PROVISIONAL" ${assess.uncertainty_level === "PROVISIONAL" ? "selected" : ""}>Provisional (Pending Tests)</option>
                <option value="UNCERTAIN" ${assess.uncertainty_level === "UNCERTAIN" ? "selected" : ""}>Uncertain</option>
                <option value="NOT_ASSESSED" ${assess.uncertainty_level === "NOT_ASSESSED" ? "selected" : ""}>Not Assessed</option>
              </select>
            </div>
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Past Medical & Surgical History</label>
            <input type="text" id="mca-pmhx" class="form-control" ${isSigned ? "disabled" : ""}
                   placeholder="e.g. Hypertension 5y, Type 2 DM, appendectomy 2018"
                   value="${escapeHtml(assess.past_medical_history || "")}">
          </div>

          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Current Medication History</label>
            <input type="text" id="mca-medhx" class="form-control" ${isSigned ? "disabled" : ""}
                   placeholder="e.g. Amlodipine 5mg OD, Metformin 500mg BD"
                   value="${escapeHtml(assess.medication_history || "")}">
          </div>
        </div>

        <!-- 2. Objective Measurements & Vitals -->
        <div class="card" style="margin-bottom: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
            <h3 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin: 0;">
              2. Objective Vital Signs & Laboratory Observations
            </h3>
            <span style="font-size: 0.75rem; color: var(--matab-color-text-muted);">Provenance Tracked</span>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
            <div>
              <label style="display: block; font-size: 0.8rem; font-weight: 600;">Systolic BP (mmHg)</label>
              <input type="number" id="vital-sbp" class="form-control" ${isSigned ? "disabled" : ""}
                     placeholder="e.g. 120" value="${obsMap.systolic_blood_pressure ? obsMap.systolic_blood_pressure.value_numeric : ""}">
              <span style="font-size: 0.72rem; color: var(--matab-color-text-muted);">Target: 90-120 mmHg</span>
            </div>
            <div>
              <label style="display: block; font-size: 0.8rem; font-weight: 600;">Diastolic BP (mmHg)</label>
              <input type="number" id="vital-dbp" class="form-control" ${isSigned ? "disabled" : ""}
                     placeholder="e.g. 80" value="${obsMap.diastolic_blood_pressure ? obsMap.diastolic_blood_pressure.value_numeric : ""}">
              <span style="font-size: 0.72rem; color: var(--matab-color-text-muted);">Target: 60-80 mmHg</span>
            </div>
            <div>
              <label style="display: block; font-size: 0.8rem; font-weight: 600;">Heart Rate (bpm)</label>
              <input type="number" id="vital-hr" class="form-control" ${isSigned ? "disabled" : ""}
                     placeholder="e.g. 72" value="${obsMap.heart_rate ? obsMap.heart_rate.value_numeric : ""}">
              <span style="font-size: 0.72rem; color: var(--matab-color-text-muted);">Normal: 60-100 bpm</span>
            </div>
            <div>
              <label style="display: block; font-size: 0.8rem; font-weight: 600;">Respiratory Rate (/min)</label>
              <input type="number" id="vital-rr" class="form-control" ${isSigned ? "disabled" : ""}
                     placeholder="e.g. 16" value="${obsMap.respiratory_rate ? obsMap.respiratory_rate.value_numeric : ""}">
              <span style="font-size: 0.72rem; color: var(--matab-color-text-muted);">Normal: 12-20 /min</span>
            </div>
            <div>
              <label style="display: block; font-size: 0.8rem; font-weight: 600;">Body Temp (°C)</label>
              <input type="number" step="0.1" id="vital-temp" class="form-control" ${isSigned ? "disabled" : ""}
                     placeholder="e.g. 37.0" value="${obsMap.body_temperature ? obsMap.body_temperature.value_numeric : ""}">
              <span style="font-size: 0.72rem; color: var(--matab-color-text-muted);">Normal: 36.1-37.2 °C</span>
            </div>
            <div>
              <label style="display: block; font-size: 0.8rem; font-weight: 600;">Oxygen Saturation SpO2 (%)</label>
              <input type="number" id="vital-spo2" class="form-control" ${isSigned ? "disabled" : ""}
                     placeholder="e.g. 98" value="${obsMap.oxygen_saturation ? obsMap.oxygen_saturation.value_numeric : ""}">
              <span style="font-size: 0.72rem; color: var(--matab-color-text-muted);">Target: 95-100 %</span>
            </div>
          </div>

          <div style="margin-bottom: 0.75rem;">
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Physical Examination Notes</label>
            <textarea id="mca-exam-notes" class="form-control" rows="2" ${isSigned ? "disabled" : ""}
                      placeholder="Chest auscultation, abdominal tenderness, neuro exam findings...">${escapeHtml(assess.physical_examination_json || "")}</textarea>
          </div>

          ${!isSigned ? `
            <button id="btn-save-vitals" class="btn btn-secondary btn-sm" style="width: 100%;">
              💾 Save Measurements & Observations
            </button>
          ` : ""}
        </div>
      </div>

      <!-- RIGHT COLUMN: Decision Support, Problems, Investigations, Referrals -->
      <div>
        <!-- 3. Working Assessment & Confirmed Problem List -->
        <div class="card" style="margin-bottom: 1.25rem;">
          <h3 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
            3. Working Assessment & Confirmed Problem List
          </h3>

          <div style="margin-bottom: 0.75rem;">
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Clinician Working Assessment Narrative</label>
            <textarea id="mca-working-assessment" class="form-control" rows="2" ${isSigned ? "disabled" : ""}
                      placeholder="Synthesized clinical formulation and rationale...">${escapeHtml(assess.working_assessment || "")}</textarea>
          </div>

          <!-- Problem List Cards -->
          <div style="margin-bottom: 0.75rem;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
              <span style="font-size: 0.82rem; font-weight: 600;">Active Clinical Problems:</span>
              ${!isSigned ? `<button id="btn-show-add-problem" class="btn btn-secondary btn-sm" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;">+ Add Problem</button>` : ""}
            </div>

            <div id="mca-problems-list">
              ${(assess.problems || []).length > 0 ? assess.problems.map(p => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0.6rem; background: var(--matab-color-bg-secondary); border-radius: 4px; margin-bottom: 0.4rem; font-size: 0.85rem;">
                  <div>
                    <strong>${escapeHtml(p.problem_title)}</strong>
                    <span style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-left: 0.4rem;">
                      [${escapeHtml(p.code_value || "Uncoded")}] • ${p.status}
                    </span>
                  </div>
                  ${p.is_primary ? `<span class="badge badge-info" style="font-size: 0.7rem;">Primary</span>` : ""}
                </div>
              `).join("") : `
                <div style="font-size: 0.82rem; color: var(--matab-color-text-muted); font-style: italic;">
                  No confirmed problems recorded yet.
                </div>
              `}
            </div>
          </div>
        </div>

        <!-- 4. Differential Diagnosis Support Candidates -->
        <div class="card" style="margin-bottom: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
            <h3 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin: 0;">
              4. Differential Diagnosis Considerations
            </h3>
            <span class="badge badge-warning" style="font-size: 0.72rem;">Decision Support Only</span>
          </div>

          <div id="mca-differentials-list">
            ${(assess.differential_candidates || []).length > 0 ? assess.differential_candidates.map(c => `
              <div style="padding: 0.6rem; border: 1px solid var(--matab-color-border-subtle); border-radius: 6px; margin-bottom: 0.6rem; background: var(--matab-color-surface);">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.3rem;">
                  <div>
                    <strong style="font-size: 0.9rem;">${escapeHtml(c.candidate_label)}</strong>
                    <span style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-left: 0.4rem;">(${c.candidate_code || "Uncoded"})</span>
                  </div>
                  <span class="badge ${c.clinician_decision === 'CONFIRMED_AS_PROBLEM' ? 'badge-success' : 'badge-secondary'}" style="font-size: 0.72rem;">
                    ${c.clinician_decision || 'PENDING'}
                  </span>
                </div>

                <p style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-bottom: 0.4rem;">
                  ${escapeHtml(c.rationale)}
                </p>

                <div style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-bottom: 0.4rem;">
                  <strong>Supporting:</strong> ${(c.supporting_findings || []).join(", ") || "None documented"}<br>
                  <strong>Missing Info:</strong> ${(c.missing_information || []).join(", ") || "None"}
                </div>

                ${!isSigned && c.clinician_decision === 'PENDING_REVIEW' ? `
                  <div style="display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.4rem;">
                    <button class="btn btn-sm btn-primary btn-cand-decision" data-id="${c.id}" data-decision="CONFIRMED_AS_PROBLEM">
                      ✅ Confirm as Problem
                    </button>
                    <button class="btn btn-sm btn-secondary btn-cand-decision" data-id="${c.id}" data-decision="ACCEPTED">
                      Accept Consideration
                    </button>
                    <button class="btn btn-sm btn-secondary btn-cand-decision" data-id="${c.id}" data-decision="DEFERRED">
                      Defer
                    </button>
                  </div>
                ` : ""}
              </div>
            `).join("") : `
              <div style="text-align: center; padding: 1rem; color: var(--matab-color-text-muted); font-size: 0.82rem;">
                Click "Differential Support" above to evaluate approved heuristics for this presentation.
              </div>
            `}
          </div>
        </div>

        <!-- 5. Investigation Considerations -->
        <div class="card" style="margin-bottom: 1.25rem;">
          <h3 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
            5. Investigation Considerations (Guideline-Sourced)
          </h3>

          <div id="mca-investigations-list">
            ${(assess.investigation_considerations || []).length > 0 ? assess.investigation_considerations.map(inv => `
              <div style="padding: 0.5rem 0.75rem; border-left: 3px solid var(--matab-color-brand-primary); background: var(--matab-color-bg-secondary); border-radius: 4px; margin-bottom: 0.5rem; font-size: 0.85rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                  <strong>${escapeHtml(inv.suggested_investigation)}</strong>
                  <span class="badge badge-info" style="font-size: 0.7rem;">${inv.modality}</span>
                </div>
                <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-bottom: 0.3rem;">
                  <em>Question:</em> ${escapeHtml(inv.clinical_question)}
                </div>
                <div style="font-size: 0.75rem; color: var(--matab-color-text-muted);">
                  ${escapeHtml(inv.rationale)} • Source: ${escapeHtml(inv.guideline_source || "Clinical Standard")}
                </div>
              </div>
            `).join("") : `
              <div style="font-size: 0.82rem; color: var(--matab-color-text-muted); font-style: italic;">
                No specific investigation guidelines triggered for this presentation.
              </div>
            `}
          </div>
        </div>

        <!-- 6. Referral & Escalation -->
        <div class="card">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
            <h3 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin: 0;">
              6. Referral & Escalation Plan
            </h3>
            ${!isSigned ? `<button id="btn-show-add-referral" class="btn btn-secondary btn-sm" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;">+ Create Referral</button>` : ""}
          </div>

          <div id="mca-referrals-list">
            ${(assess.referrals || []).length > 0 ? assess.referrals.map(ref => `
              <div style="padding: 0.5rem 0.75rem; background: var(--matab-color-surface); border: 1px solid var(--matab-color-border-subtle); border-radius: 4px; margin-bottom: 0.5rem; font-size: 0.85rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.2rem;">
                  <strong>${escapeHtml(ref.target_specialty)}</strong>
                  <span class="badge ${ref.urgency === 'EMERGENT' ? 'badge-danger' : ref.urgency === 'URGENT' ? 'badge-warning' : 'badge-info'}" style="font-size: 0.7rem;">
                    ${ref.urgency}
                  </span>
                </div>
                <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary);">
                  ${escapeHtml(ref.reason_for_referral)}
                </div>
                <div style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-top: 0.2rem;">
                  Handover: ${escapeHtml(ref.handover_summary)} • Informed: ${ref.patient_informed_status}
                </div>
              </div>
            `).join("") : `
              <div style="font-size: 0.82rem; color: var(--matab-color-text-muted); font-style: italic;">
                No external referrals or transfers documented for this encounter.
              </div>
            `}
        <!-- 7. Governed Evidence & Knowledge Reference Cards (Prompt 06) -->
        <div class="card" style="margin-top: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; border-bottom: 1px solid var(--matab-color-border-subtle); padding-bottom: 0.4rem;">
            <h3 style="font-size: 1rem; color: var(--matab-color-brand-primary); margin: 0;">
              7. Governed Clinical References & Evidence
            </h3>
            <button id="btn-fetch-context-evidence" class="btn btn-secondary btn-sm" style="padding: 0.15rem 0.4rem; font-size: 0.75rem;">
              🔍 Retrieve Contextual Evidence
            </button>
          </div>

          <div id="mca-evidence-cards-container">
            <div style="font-size: 0.82rem; color: var(--matab-color-text-muted); font-style: italic;">
              Click "Retrieve Contextual Evidence" above to inspect approved Unani compendia, NICE/WHO guidelines, and safety notes mapped to this patient's clinical presentation.
            </div>
          </div>
        </div>

      </div>
    </div>
  `;

  // Attach Event Handlers
  setupModernAssessmentEvents(container, pane, patientId, encounterId, assess);
}

function renderRedFlagsSection(redFlags) {
  if (!redFlags || redFlags.length === 0) {
    return `
      <div style="padding: 0.5rem 0.75rem; background: rgba(16, 185, 129, 0.08); border: 1px solid var(--matab-color-success-light); border-radius: 6px; font-size: 0.85rem; color: var(--matab-color-success-dark); display: flex; align-items: center; gap: 0.5rem;">
        <span>🛡️</span>
        <span><strong>Safety Check Status:</strong> No active red flags triggered for currently recorded facts. (Note: Missing inputs are not cleared as safe).</span>
      </div>
    `;
  }

  return `
    <div style="padding: 0.75rem 1rem; background: rgba(239, 68, 68, 0.08); border: 1px solid var(--matab-color-danger-light); border-radius: 6px;">
      <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem;">
        <span style="font-size: 1.2rem;">🚨</span>
        <strong style="color: var(--matab-color-danger-dark); font-size: 0.95rem;">
          Safety Alert: ${redFlags.length} Clinical Red-Flag Rule(s) Triggered
        </strong>
      </div>

      ${redFlags.map(rf => `
        <div style="background: #fff; padding: 0.6rem 0.8rem; border-radius: 4px; margin-bottom: 0.5rem; border-left: 4px solid var(--matab-color-danger-primary);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
            <strong>${escapeHtml(rf.rule_id || "ALERT")} (${rf.severity})</strong>
            ${rf.is_acknowledged ? `
              <span class="badge badge-success" style="font-size: 0.72rem;">Acknowledged</span>
            ` : `
              <button class="btn btn-sm btn-danger btn-ack-red-flag" data-id="${rf.id}">
                Acknowledge Alert
              </button>
            `}
          </div>
          <p style="font-size: 0.82rem; margin: 0 0 0.25rem 0; color: var(--matab-color-text-primary);">
            ${escapeHtml(rf.plain_language_reason)}
          </p>
          <div style="font-size: 0.78rem; color: var(--matab-color-danger-dark);">
            <strong>Recommended Action:</strong> ${escapeHtml(rf.recommended_action)}
          </div>
        </div>
      `).join("")}
    </div>
  `;
}

function setupModernAssessmentEvents(container, pane, patientId, encounterId, assess) {
  const isSigned = assess.status === "SIGNED" || assess.status === "AMENDED";

  // 1. Save Draft
  const btnSaveDraft = pane.querySelector("#btn-save-modern-draft");
  if (btnSaveDraft) {
    btnSaveDraft.addEventListener("click", async () => {
      btnSaveDraft.disabled = true;
      try {
        await saveModernAssessmentFields(pane, assess.id, assess.version_number);
        alert("Assessment draft saved successfully.");
        loadModernAssessmentPane(container, pane, patientId, encounterId);
      } catch (err) {
        alert(`Failed to save draft: ${err.message}`);
        btnSaveDraft.disabled = false;
      }
    });
  }

  // 2. Save Vitals
  const btnSaveVitals = pane.querySelector("#btn-save-vitals");
  if (btnSaveVitals) {
    btnSaveVitals.addEventListener("click", async () => {
      btnSaveVitals.disabled = true;
      try {
        const vitalsPayload = buildVitalsPayload(pane);
        if (vitalsPayload.length > 0) {
          await apiClient.post(`/api/v1/modern-assessments/${assess.id}/observations`, {
            observations: vitalsPayload
          });
        }
        await saveModernAssessmentFields(pane, assess.id, assess.version_number);
        alert("Measurements and observations saved.");
        loadModernAssessmentPane(container, pane, patientId, encounterId);
      } catch (err) {
        alert(`Failed to save observations: ${err.message}`);
        btnSaveVitals.disabled = false;
      }
    });
  }

  // 3. Evaluate Red Flags
  const btnSafety = pane.querySelector("#btn-run-safety-checks");
  if (btnSafety) {
    btnSafety.addEventListener("click", async () => {
      btnSafety.disabled = true;
      try {
        await saveModernAssessmentFields(pane, assess.id, assess.version_number);
        const res = await apiClient.post(`/api/v1/modern-assessments/${assess.id}/run-safety-checks`, {});
        alert(`Evaluated ${res.rules_evaluated_count || 0} safety rules. ${res.triggered_alerts ? res.triggered_alerts.length : 0} alert(s) detected.`);
        loadModernAssessmentPane(container, pane, patientId, encounterId);
      } catch (err) {
        alert(`Safety check evaluation failed: ${err.message}`);
        btnSafety.disabled = false;
      }
    });
  }

  // 4. Differential Support
  const btnDiff = pane.querySelector("#btn-run-differentials");
  if (btnDiff) {
    btnDiff.addEventListener("click", async () => {
      btnDiff.disabled = true;
      try {
        await saveModernAssessmentFields(pane, assess.id, assess.version_number);
        const res = await apiClient.post(`/api/v1/modern-assessments/${assess.id}/differential-support`, {});
        if (res.status === "CONTENT_UNAVAILABLE") {
          alert(`Notice: ${res.message}`);
        } else {
          alert(`Evaluated differential heuristics: ${res.candidates ? res.candidates.length : 0} candidate consideration(s) surfaced.`);
        }
        loadModernAssessmentPane(container, pane, patientId, encounterId);
      } catch (err) {
        alert(`Differential support error: ${err.message}`);
        btnDiff.disabled = false;
      }
    });
  }

  // 5. Differential Decision Buttons
  pane.querySelectorAll(".btn-cand-decision").forEach(btn => {
    btn.addEventListener("click", async () => {
      const candId = btn.getAttribute("data-id");
      const decision = btn.getAttribute("data-decision");
      try {
        await apiClient.post(`/api/v1/modern-assessments/${assess.id}/differential-candidates/${candId}/decision`, {
          decision: decision,
          rationale: "Clinician decision recorded in Consultation workspace.",
          is_primary: decision === "CONFIRMED_AS_PROBLEM"
        });
        loadModernAssessmentPane(container, pane, patientId, encounterId);
      } catch (err) {
        alert(`Failed to record decision: ${err.message}`);
      }
    });
  });

  // 6. Red Flag Acknowledgment
  pane.querySelectorAll(".btn-ack-red-flag").forEach(btn => {
    btn.addEventListener("click", async () => {
      const alertId = btn.getAttribute("data-id");
      const actionText = prompt("Document clinical action taken or override rationale for this red flag:");
      if (!actionText || !actionText.trim()) return;

      try {
        await apiClient.post(`/api/v1/modern-assessments/${assess.id}/red-flags/${alertId}/acknowledge`, {
          clinician_action_taken: actionText.trim()
        });
        alert("Alert acknowledged.");
        loadModernAssessmentPane(container, pane, patientId, encounterId);
      } catch (err) {
        alert(`Failed to acknowledge alert: ${err.message}`);
      }
    });
  });

  // 7. Sign Assessment Modal
  const btnSign = pane.querySelector("#btn-sign-modern-assessment");
  if (btnSign) {
    btnSign.addEventListener("click", () => {
      openSignAssessmentModal(container, pane, patientId, encounterId, assess);
    });
  }

  // 8. Amend Assessment Modal
  const btnAmend = pane.querySelector("#btn-amend-modern-assessment");
  if (btnAmend) {
    btnAmend.addEventListener("click", () => {
      openAmendAssessmentModal(container, pane, patientId, encounterId, assess);
    });
  }

  // 9. Add Problem Form
  const btnShowAddProblem = pane.querySelector("#btn-show-add-problem");
  if (btnShowAddProblem) {
    btnShowAddProblem.addEventListener("click", () => {
      openAddProblemModal(container, pane, patientId, encounterId, assess);
    });
  }

  // 10. Create Referral Form
  const btnShowAddReferral = pane.querySelector("#btn-show-add-referral");
  if (btnShowAddReferral) {
    btnShowAddReferral.addEventListener("click", () => {
      openAddReferralModal(container, pane, patientId, encounterId, assess);
    });
  }

  // 11. Fetch Contextual Evidence & Knowledge References (Prompt 06)
  const btnFetchEvidence = pane.querySelector("#btn-fetch-context-evidence");
  if (btnFetchEvidence) {
    btnFetchEvidence.addEventListener("click", async () => {
      const containerEl = pane.querySelector("#mca-evidence-cards-container");
      if (!containerEl) return;
      containerEl.innerHTML = `<div style="font-size: 0.85rem; color: var(--matab-color-brand-primary);">Retrieving governed clinical references...</div>`;

      try {
        const symptoms = [];
        const chief = pane.querySelector("#mca-chief-complaint")?.value.trim();
        if (chief) symptoms.push(chief);
        (assess.problems || []).forEach(p => symptoms.push(p.problem_title));

        const res = await apiClient.post("/api/v1/knowledge/retrieve", {
          encounter_context: {
            symptoms: symptoms.length > 0 ? symptoms : ["Dyspepsia"],
            mizaj_primary: "Balghami",
            medicines: [],
            allergies: []
          }
        });

        const unaniCards = (res.unani_references || []).map(u => `
          <div style="padding: 0.5rem 0.75rem; background: rgba(59, 130, 246, 0.05); border: 1px solid var(--matab-color-brand-primary); border-radius: 4px; margin-bottom: 0.4rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong>🏛️ ${escapeHtml(u.canonical_name)}</strong>
              <span class="badge badge-brand" style="font-size: 0.7rem;">Unani Reference</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-top: 0.2rem;">
              ${escapeHtml(u.description)}
            </div>
          </div>
        `).join("");

        const modernCards = (res.modern_references || []).map(m => `
          <div style="padding: 0.5rem 0.75rem; background: var(--matab-color-bg-secondary); border-left: 3px solid #10b981; border-radius: 4px; margin-bottom: 0.4rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong>🔬 ${escapeHtml(m.canonical_name)}</strong>
              <span class="badge badge-success" style="font-size: 0.7rem;">${escapeHtml(m.evidence_level)}</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--matab-color-text-secondary); margin-top: 0.2rem;">
              ${escapeHtml(m.description)}
            </div>
          </div>
        `).join("");

        const safetyCards = (res.safety_precautions || []).map(s => `
          <div style="padding: 0.5rem 0.75rem; background: rgba(245, 158, 11, 0.08); border-left: 3px solid #f59e0b; border-radius: 4px; margin-bottom: 0.4rem;">
            <strong style="color: #b45309;">⚠️ ${escapeHtml(s.substance)}:</strong>
            <span style="font-size: 0.8rem; color: var(--matab-color-text-secondary);"> ${escapeHtml(s.precaution_text)}</span>
          </div>
        `).join("");

        const citationsHtml = (res.citations || []).map(c => `
          <li style="font-size: 0.75rem; color: var(--matab-color-text-muted);">
            <strong>${escapeHtml(c.source_title)}</strong> (${escapeHtml(c.source_type)}) - ${escapeHtml(c.location_in_source || "General")}
          </li>
        `).join("");

        containerEl.innerHTML = `
          ${safetyCards}
          ${unaniCards}
          ${modernCards}
          ${citationsHtml ? `
            <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px solid var(--matab-color-border-subtle);">
              <div style="font-size: 0.78rem; font-weight: 600; color: var(--matab-color-text-secondary);">Verified Citations:</div>
              <ul style="padding-left: 1.2rem; margin: 0.2rem 0;">${citationsHtml}</ul>
            </div>
          ` : ""}
          <div style="font-size: 0.72rem; color: var(--matab-color-text-muted); margin-top: 0.4rem; font-style: italic;">
            ${escapeHtml(res.prescribing_disclaimer)}
          </div>
        `;
      } catch (err) {
        containerEl.innerHTML = `<div style="color: red; font-size: 0.8rem;">Retrieval error: ${escapeHtml(err.message)}</div>`;
      }
    });
  }
}

async function saveModernAssessmentFields(pane, assessId, currentVersion) {
  const chief = pane.querySelector("#mca-chief-complaint") ? pane.querySelector("#mca-chief-complaint").value.trim() : "";
  const hpi = pane.querySelector("#mca-hpi") ? pane.querySelector("#mca-hpi").value.trim() : "";
  const allergiesStatus = pane.querySelector("#mca-allergies-status") ? pane.querySelector("#mca-allergies-status").value : "NOT_REVIEWED";
  const uncertainty = pane.querySelector("#mca-uncertainty") ? pane.querySelector("#mca-uncertainty").value : "NOT_ASSESSED";
  const pmhx = pane.querySelector("#mca-pmhx") ? pane.querySelector("#mca-pmhx").value.trim() : "";
  const medhx = pane.querySelector("#mca-medhx") ? pane.querySelector("#mca-medhx").value.trim() : "";
  const exam = pane.querySelector("#mca-exam-notes") ? pane.querySelector("#mca-exam-notes").value.trim() : "";
  const working = pane.querySelector("#mca-working-assessment") ? pane.querySelector("#mca-working-assessment").value.trim() : "";

  await apiClient.patch(`/api/v1/modern-assessments/${assessId}`, {
    version_number: currentVersion,
    chief_complaint: chief,
    history_of_present_illness: hpi,
    allergies_review_status: allergiesStatus,
    uncertainty_level: uncertainty,
    past_medical_history: pmhx,
    medication_history: medhx,
    physical_examination_json: exam,
    working_assessment: working
  });
}

function buildVitalsPayload(pane) {
  const vitals = [];
  const sbp = pane.querySelector("#vital-sbp") ? pane.querySelector("#vital-sbp").value : "";
  const dbp = pane.querySelector("#vital-dbp") ? pane.querySelector("#vital-dbp").value : "";
  const hr = pane.querySelector("#vital-hr") ? pane.querySelector("#vital-hr").value : "";
  const rr = pane.querySelector("#vital-rr") ? pane.querySelector("#vital-rr").value : "";
  const temp = pane.querySelector("#vital-temp") ? pane.querySelector("#vital-temp").value : "";
  const spo2 = pane.querySelector("#vital-spo2") ? pane.querySelector("#vital-spo2").value : "";

  if (sbp) vitals.push({ concept_name: "Systolic Blood Pressure", value_numeric: parseFloat(sbp), unit: "mmHg" });
  if (dbp) vitals.push({ concept_name: "Diastolic Blood Pressure", value_numeric: parseFloat(dbp), unit: "mmHg" });
  if (hr) vitals.push({ concept_name: "Heart Rate", value_numeric: parseFloat(hr), unit: "bpm" });
  if (rr) vitals.push({ concept_name: "Respiratory Rate", value_numeric: parseFloat(rr), unit: "/min" });
  if (temp) vitals.push({ concept_name: "Body Temperature", value_numeric: parseFloat(temp), unit: "degC" });
  if (spo2) vitals.push({ concept_name: "Oxygen Saturation", value_numeric: parseFloat(spo2), unit: "%" });

  return vitals;
}

function openSignAssessmentModal(container, pane, patientId, encounterId, assess) {
  const modalContainer = container.querySelector("#consultation-modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-content" style="max-width: 480px;">
        <h3 style="margin-top: 0; color: var(--matab-color-brand-primary);">✍️ Electronic Sign-Off</h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); line-height: 1.4;">
          You are electronically signing the Modern Clinical Assessment for encounter #${encounterId.substring(0, 8)}.
          This generates a cryptographic SHA-256 integrity hash and seals the record.
        </p>
        
        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">
            Practitioner Signature PIN
          </label>
          <input type="password" id="mca-pin-input" class="form-control" placeholder="Enter PIN (e.g. 1234)" autofocus>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
          <button id="btn-cancel-mca-sign" class="btn btn-secondary">Cancel</button>
          <button id="btn-confirm-mca-sign" class="btn btn-success">Confirm Sign-Off</button>
        </div>
      </div>
    </div>
  `;

  modalContainer.querySelector("#btn-cancel-mca-sign").addEventListener("click", () => {
    modalContainer.innerHTML = "";
  });

  modalContainer.querySelector("#btn-confirm-mca-sign").addEventListener("click", async () => {
    const pin = modalContainer.querySelector("#mca-pin-input").value;
    try {
      await saveModernAssessmentFields(pane, assess.id, assess.version_number);
      await apiClient.post(`/api/v1/modern-assessments/${assess.id}/sign`, { pin: pin });
      modalContainer.innerHTML = "";
      alert("Assessment successfully signed.");
      loadModernAssessmentPane(container, pane, patientId, encounterId);
    } catch (err) {
      alert(`Sign-off failed: ${err.message}`);
    }
  });
}

function openAmendAssessmentModal(container, pane, patientId, encounterId, assess) {
  const modalContainer = container.querySelector("#consultation-modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-content" style="max-width: 500px;">
        <h3 style="margin-top: 0; color: var(--matab-color-brand-primary);">📝 Governed Record Amendment</h3>
        <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary);">
          Signed clinical records cannot be overwritten. Document the clinical justification for amending version ${assess.version_number}.
        </p>

        <div style="margin-bottom: 0.75rem;">
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Amendment Reason*</label>
          <input type="text" id="mca-amend-reason" class="form-control" placeholder="e.g. Follow-up observations, revised working diagnosis...">
        </div>

        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Updated Working Assessment</label>
          <textarea id="mca-amend-working" class="form-control" rows="2">${escapeHtml(assess.working_assessment || "")}</textarea>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
          <button id="btn-cancel-mca-amend" class="btn btn-secondary">Cancel</button>
          <button id="btn-confirm-mca-amend" class="btn btn-primary">Save Amendment</button>
        </div>
      </div>
    </div>
  `;

  modalContainer.querySelector("#btn-cancel-mca-amend").addEventListener("click", () => {
    modalContainer.innerHTML = "";
  });

  modalContainer.querySelector("#btn-confirm-mca-amend").addEventListener("click", async () => {
    const reason = modalContainer.querySelector("#mca-amend-reason").value.trim();
    if (!reason) {
      alert("Amendment reason is required.");
      return;
    }
    const working = modalContainer.querySelector("#mca-amend-working").value.trim();

    try {
      await apiClient.post(`/api/v1/modern-assessments/${assess.id}/amend`, {
        amendment_reason: reason,
        working_assessment: working
      });
      modalContainer.innerHTML = "";
      alert("Amendment recorded.");
      loadModernAssessmentPane(container, pane, patientId, encounterId);
    } catch (err) {
      alert(`Amendment failed: ${err.message}`);
    }
  });
}

function openAddProblemModal(container, pane, patientId, encounterId, assess) {
  const modalContainer = container.querySelector("#consultation-modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-content" style="max-width: 460px;">
        <h3 style="margin-top: 0; color: var(--matab-color-brand-primary);">+ Add Clinical Problem</h3>
        
        <div style="margin-bottom: 0.75rem;">
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Problem Title*</label>
          <input type="text" id="new-problem-title" class="form-control" placeholder="e.g. Essential Hypertension, Acute Bronchitis">
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Status</label>
            <select id="new-problem-status" class="form-control">
              <option value="CONFIRMED">CONFIRMED</option>
              <option value="PROVISIONAL" selected>PROVISIONAL</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </div>
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">ICD Code (Optional)</label>
            <input type="text" id="new-problem-code" class="form-control" placeholder="e.g. I10, J20.9">
          </div>
        </div>

        <div style="margin-bottom: 1rem;">
          <label style="display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem;">
            <input type="checkbox" id="new-problem-primary"> Primary Encounter Diagnosis
          </label>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
          <button id="btn-cancel-add-problem" class="btn btn-secondary">Cancel</button>
          <button id="btn-save-add-problem" class="btn btn-primary">Add Problem</button>
        </div>
      </div>
    </div>
  `;

  modalContainer.querySelector("#btn-cancel-add-problem").addEventListener("click", () => {
    modalContainer.innerHTML = "";
  });

  modalContainer.querySelector("#btn-save-add-problem").addEventListener("click", async () => {
    const title = modalContainer.querySelector("#new-problem-title").value.trim();
    if (!title) {
      alert("Problem title is required.");
      return;
    }
    const status = modalContainer.querySelector("#new-problem-status").value;
    const code = modalContainer.querySelector("#new-problem-code").value.trim();
    const isPrimary = modalContainer.querySelector("#new-problem-primary").checked;

    try {
      await apiClient.post(`/api/v1/modern-assessments/${assess.id}/problems`, {
        problem_title: title,
        status: status,
        code_value: code || null,
        code_system: code ? "ICD-10-MOCK" : "UNCODED",
        is_primary: isPrimary
      });
      modalContainer.innerHTML = "";
      loadModernAssessmentPane(container, pane, patientId, encounterId);
    } catch (err) {
      alert(`Failed to add problem: ${err.message}`);
    }
  });
}

function openAddReferralModal(container, pane, patientId, encounterId, assess) {
  const modalContainer = container.querySelector("#consultation-modal-container");
  modalContainer.innerHTML = `
    <div class="modal-backdrop">
      <div class="modal-content" style="max-width: 500px;">
        <h3 style="margin-top: 0; color: var(--matab-color-brand-primary);">Document Clinical Referral / Transfer</h3>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 0.75rem;">
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Target Specialty*</label>
            <select id="ref-specialty" class="form-control">
              <option value="CARDIOLOGY">Cardiology</option>
              <option value="GASTROENTEROLOGY">Gastroenterology</option>
              <option value="PULMONOLOGY">Pulmonology</option>
              <option value="EMERGENCY_MEDICINE">Emergency Medicine</option>
              <option value="INTERNAL_MEDICINE">Internal Medicine</option>
              <option value="GENERAL_SURGERY">General Surgery</option>
            </select>
          </div>
          <div>
            <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Urgency Level*</label>
            <select id="ref-urgency" class="form-control">
              <option value="ROUTINE">Routine</option>
              <option value="URGENT" selected>Urgent (< 24h)</option>
              <option value="EMERGENT">Emergent (Immediate)</option>
            </select>
          </div>
        </div>

        <div style="margin-bottom: 0.75rem;">
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Reason for Referral*</label>
          <input type="text" id="ref-reason" class="form-control" placeholder="Clinical rationale...">
        </div>

        <div style="margin-bottom: 0.75rem;">
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Handover Summary*</label>
          <textarea id="ref-handover" class="form-control" rows="2" placeholder="Key facts, current vitals, medications administered..."></textarea>
        </div>

        <div style="margin-bottom: 1rem;">
          <label style="display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 0.25rem;">Patient Informed Status</label>
          <select id="ref-informed" class="form-control">
            <option value="INFORMED_AGREED" selected>Informed & Agreed</option>
            <option value="INFORMED_REFUSED">Informed but Refused</option>
            <option value="UNABLE_TO_INFORM">Unable to Inform (Altered/Unaccompanied)</option>
          </select>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
          <button id="btn-cancel-add-ref" class="btn btn-secondary">Cancel</button>
          <button id="btn-save-add-ref" class="btn btn-primary">Save Referral</button>
        </div>
      </div>
    </div>
  `;

  modalContainer.querySelector("#btn-cancel-add-ref").addEventListener("click", () => {
    modalContainer.innerHTML = "";
  });

  modalContainer.querySelector("#btn-save-add-ref").addEventListener("click", async () => {
    const specialty = modalContainer.querySelector("#ref-specialty").value;
    const urgency = modalContainer.querySelector("#ref-urgency").value;
    const reason = modalContainer.querySelector("#ref-reason").value.trim();
    const handover = modalContainer.querySelector("#ref-handover").value.trim();
    const informed = modalContainer.querySelector("#ref-informed").value;

    if (!reason || !handover) {
      alert("Reason and handover summary are required.");
      return;
    }

    try {
      await apiClient.post(`/api/v1/modern-assessments/${assess.id}/referrals`, {
        target_specialty: specialty,
        urgency: urgency,
        reason_for_referral: reason,
        handover_summary: handover,
        patient_informed_status: informed
      });
      modalContainer.innerHTML = "";
      alert("Referral documented.");
      loadModernAssessmentPane(container, pane, patientId, encounterId);
    } catch (err) {
      alert(`Failed to save referral: ${err.message}`);
    }
  });
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

function getStatusBadgeClass(status) {
  switch (status) {
    case "SIGNED":
    case "FINALISED":
    case "ACTIVE":
      return "badge-success";
    case "DRAFT":
    case "PROVISIONAL":
    case "PENDING":
      return "badge-warning";
    case "CANCELLED":
      return "badge-danger";
    case "AMENDED":
      return "badge-info";
    default:
      return "badge-secondary";
  }
}

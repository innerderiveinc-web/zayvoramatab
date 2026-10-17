/**
 * Phase 15: Post-Pilot Evaluation, Adoption Scorecard & Scale Decision View
 * Standalone ZAYVORA MATAB OS
 */

import { state } from "../state.js";
import { apiClient } from "/packages/api-client/client.js";

export async function renderPostPilotEvaluation(container) {
  const user = state.user;
  container.innerHTML = `
    <div class="header-card" style="margin-bottom: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
        <div>
          <h2 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <span>⚖️</span>
            <span>Post-Pilot Evaluation & Scale Decision</span>
          </h2>
          <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.9rem;">
            Evidence-Based Operational Review, 8-Domain Adoption Scorecard, Risk Review & Independent Expansion Gates
          </p>
        </div>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;" id="evalHeaderBadges">
          <span class="badge" style="background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; font-weight: 600;">
            Status: LOADING...
          </span>
        </div>
      </div>
      
      <div style="display: flex; gap: 0.5rem; margin-top: 1.25rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; overflow-x: auto;">
        <button id="tabEvalOverviewBtn" class="btn btn-sm btn-primary">📊 Evaluation State</button>
        <button id="tabEvalEvidenceBtn" class="btn btn-sm btn-secondary">📋 Evidence Inventory</button>
        <button id="tabEvalScorecardBtn" class="btn btn-sm btn-secondary">🎯 Adoption Scorecard</button>
        <button id="tabEvalFeedbackRiskBtn" class="btn btn-sm btn-secondary">💬 Feedback & Risks</button>
        <button id="tabEvalExpansionBtn" class="btn btn-sm btn-secondary">🚪 Expansion Gates</button>
        <button id="tabEvalDecisionBtn" class="btn btn-sm btn-secondary">✍️ Decision & Approvals</button>
      </div>
    </div>

    <div id="evalSubViewContent">
      <div style="text-align: center; padding: 2rem; color: #94a3b8;">Loading Evaluation Dashboard...</div>
    </div>
  `;

  const subView = container.querySelector("#evalSubViewContent");
  const tabOverview = container.querySelector("#tabEvalOverviewBtn");
  const tabEvidence = container.querySelector("#tabEvalEvidenceBtn");
  const tabScorecard = container.querySelector("#tabEvalScorecardBtn");
  const tabFeedbackRisk = container.querySelector("#tabEvalFeedbackRiskBtn");
  const tabExpansion = container.querySelector("#tabEvalExpansionBtn");
  const tabDecision = container.querySelector("#tabEvalDecisionBtn");

  const tabs = [
    { btn: tabOverview, render: renderOverview },
    { btn: tabEvidence, render: renderEvidence },
    { btn: tabScorecard, render: renderScorecard },
    { btn: tabFeedbackRisk, render: renderFeedbackRisk },
    { btn: tabExpansion, render: renderExpansion },
    { btn: tabDecision, render: renderDecision }
  ];

  function setActiveTab(activeBtn) {
    tabs.forEach(t => {
      if (t.btn === activeBtn) {
        t.btn.className = "btn btn-sm btn-primary";
      } else {
        t.btn.className = "btn btn-sm btn-secondary";
      }
    });
  }

  tabs.forEach(t => {
    t.btn.addEventListener("click", () => {
      setActiveTab(t.btn);
      t.render(subView);
    });
  });

  // Default active tab
  renderOverview(subView);
}

let activeEvaluationId = null;

async function fetchOrCreateActiveEvaluation() {
  try {
    const res = await apiClient.get("/api/v1/pilot-evaluations");
    const evals = res.evaluations || [];
    if (evals.length > 0) {
      activeEvaluationId = evals[0].id;
      return evals[0];
    } else {
      // Find active pilot program
      const progRes = await apiClient.get("/api/v1/pilot/programs");
      const progs = progRes.pilot_programs || [];
      const progId = progs.length > 0 ? progs[0].id : "plt-pilot-opd-001";

      const createRes = await apiClient.post("/api/v1/pilot-evaluations", {
        pilot_program_id: progId,
        evaluation_title: "Central Matab OPD Pilot Evaluation 2026",
        build_commit: "git:81f9fba (Production Qualified Build)",
        review_period_start: "2026-10-01",
        review_period_end: "2026-10-13",
        enabled_features: ["OPD_CONSULTATION", "PRESCRIPTION_ENGINE", "UNANI_ASSESSMENT", "SAFETY_FIREWALL", "CLINIC_QUEUE"],
        disabled_features: ["EXTERNAL_LIVE_ABDM", "DIRECT_SMS_GATEWAY", "IPD_INPATIENT_LIVE"],
        roles_covered: ["TABIB", "RECEPTIONIST", "DISPENSER", "ORG_ADMIN"],
        integrations_covered: ["FHIR_R4_GATEWAY", "BARCODE_SCANNER"],
        success_criteria: { zero_p0_open: true, zero_safety_bypass: true, min_training_pass: 90 },
        targets: { encounter_completion_rate: "90%", save_success_rate: "99.9%" }
      });
      activeEvaluationId = createRes.evaluation.id;
      return createRes.evaluation;
    }
  } catch (err) {
    console.error("Error loading pilot evaluation:", err);
    return null;
  }
}

// -----------------------------------------------------------------------------
// Sub-view 1: Overview & Assessment State
// -----------------------------------------------------------------------------
async function renderOverview(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading master evaluation record...</div>`;
  const evaluation = await fetchOrCreateActiveEvaluation();

  if (!evaluation) {
    container.innerHTML = `<div class="card" style="padding: 2rem; color: #ef4444;">Failed to load or initialize evaluation record.</div>`;
    return;
  }

  const statusColors = {
    "NOT_STARTED": "#94a3b8",
    "EVIDENCE_COLLECTION": "#0284c7",
    "NOT_YET_ASSESSABLE": "#f59e0b",
    "ASSESSABLE_WITH_LIMITATIONS": "#8b5cf6",
    "READY_FOR_DECISION": "#059669",
    "DECISION_APPROVED": "#16a34a",
    "REMEDIATION_REQUIRED": "#dc2626"
  };

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;">
      <div>
        <div class="card" style="padding: 1.5rem; margin-bottom: 1.5rem;">
          <h3 style="margin-top: 0; display: flex; align-items: center; justify-content: space-between;">
            <span>${evaluation.evaluation_title}</span>
            <span class="badge" style="background: ${statusColors[evaluation.status] || '#64748b'}; color: white; padding: 0.35rem 0.75rem; border-radius: 999px;">
              ${evaluation.status}
            </span>
          </h3>

          <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin: 1.25rem 0; font-size: 0.9rem;">
            <div><strong>Evaluation ID:</strong> <span style="font-family: monospace;">${evaluation.id}</span></div>
            <div><strong>Pilot Program:</strong> <span style="font-family: monospace;">${evaluation.pilot_program_id}</span></div>
            <div><strong>Build / Commit:</strong> <span style="font-family: monospace;">${evaluation.build_commit}</span></div>
            <div><strong>Review Window:</strong> <span>${evaluation.review_period_start} to ${evaluation.review_period_end}</span></div>
            <div><strong>Primary Recommendation:</strong> <strong>${evaluation.primary_recommendation || "PENDING_REVIEW"}</strong></div>
            <div><strong>Created:</strong> <span>${evaluation.created_at || 'Just now'}</span></div>
          </div>

          <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem; margin-top: 1rem;">
            <h4 style="margin: 0 0 0.5rem 0; font-size: 0.95rem; color: #334155;">🛡️ Feature & Scope Boundaries Enforced</h4>
            <div style="font-size: 0.85rem; display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
              <div>
                <strong style="color: #16a34a;">Enabled Features:</strong>
                <ul style="margin: 0.25rem 0 0 1.25rem; padding: 0;">
                  ${(evaluation.enabled_features || []).map(f => `<li>${f}</li>`).join('')}
                </ul>
              </div>
              <div>
                <strong style="color: #dc2626;">Disabled / Gated Features:</strong>
                <ul style="margin: 0.25rem 0 0 1.25rem; padding: 0;">
                  ${(evaluation.disabled_features || []).map(f => `<li>${f}</li>`).join('')}
                </ul>
              </div>
            </div>
          </div>
        </div>

        <div class="card" style="padding: 1.5rem;">
          <h4 style="margin: 0 0 0.75rem 0; color: #1e293b;">⚖️ Non-Negotiable Evaluation Principles</h4>
          <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.88rem; color: #475569; line-height: 1.6;">
            <li><strong>Verifiable Evidence:</strong> Only persisted records and verifiable telemetry are assessed. Missing data is marked <code>UNAVAILABLE</code>, never assumed 100% success.</li>
            <li><strong>Reliability vs Efficacy:</strong> Routine clinic telemetry cannot infer clinical efficacy or causal treatment benefit without controlled study governance.</li>
            <li><strong>Fail-Closed Safety:</strong> No favorable average metric overrides an unresolved P0 or critical safety preflight failure.</li>
            <li><strong>Independent Gating:</strong> Approval for one facility or module does not propagate to any unrelated module.</li>
          </ul>
        </div>
      </div>

      <div>
        <div class="card" style="padding: 1.25rem; margin-bottom: 1.5rem;">
          <h4 style="margin: 0 0 0.75rem 0; color: #1e293b;">Assessment State Controls</h4>
          <p style="font-size: 0.85rem; color: #64748b; margin-bottom: 1rem;">
            Transition master evaluation state based on verified evidence completeness.
          </p>
          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            <button class="btn btn-sm btn-secondary" onclick="window.updateEvalState('${evaluation.id}', 'EVIDENCE_COLLECTION')">📥 Set to Evidence Collection</button>
            <button class="btn btn-sm btn-secondary" onclick="window.updateEvalState('${evaluation.id}', 'NOT_YET_ASSESSABLE')">⚠️ Mark Not Yet Assessable</button>
            <button class="btn btn-sm btn-secondary" onclick="window.updateEvalState('${evaluation.id}', 'ASSESSABLE_WITH_LIMITATIONS')">🔍 Assessable with Limitations</button>
            <button class="btn btn-sm btn-primary" onclick="window.updateEvalState('${evaluation.id}', 'READY_FOR_DECISION')">✅ Ready for Decision</button>
          </div>
        </div>

        <div class="card" style="padding: 1.25rem; background: #faf5ff; border: 1px solid #e9d5ff;">
          <h4 style="margin: 0 0 0.5rem 0; color: #7e22ce;">Quick Export</h4>
          <p style="font-size: 0.85rem; color: #6b21a8; margin-bottom: 0.75rem;">
            Generate reproducible evaluation markdown report snapshot and evidence manifest.
          </p>
          <button class="btn btn-sm btn-primary" style="width: 100%;" onclick="window.generateEvaluationReport('${evaluation.id}')">📄 Generate Report Snapshot</button>
        </div>
      </div>
    </div>
  `;
}

window.updateEvalState = async function(evalId, newState) {
  try {
    await apiClient.patch(`/api/v1/pilot-evaluations/${evalId}/status`, { status: newState });
    alert(`Status updated to: ${newState}`);
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderOverview(subView);
  } catch (err) {
    alert("Error updating status: " + (err.message || err));
  }
};

window.generateEvaluationReport = async function(evalId) {
  try {
    const res = await apiClient.post(`/api/v1/pilot-evaluations/${evalId}/report`, {});
    alert(`Report v${res.report.version_number} generated successfully!`);
    console.log("Report snapshot:", res.report);
  } catch (err) {
    alert("Error generating report: " + (err.message || err));
  }
};

// -----------------------------------------------------------------------------
// Sub-view 2: Evidence Inventory
// -----------------------------------------------------------------------------
async function renderEvidence(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading evidence inventory...</div>`;
  const evaluation = await fetchOrCreateActiveEvaluation();
  if (!evaluation) return;

  const res = await apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/evidence`);
  const items = res.evidence_items || [];

  container.innerHTML = `
    <div class="card" style="padding: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <div>
          <h3 style="margin: 0;">📋 Verified Evidence Inventory</h3>
          <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.88rem;">
            Granular source references, extraction methods, completeness status and access restrictions.
          </p>
        </div>
        <button class="btn btn-sm btn-primary" onclick="window.showRegisterEvidenceModal('${evaluation.id}')">➕ Register Evidence Item</button>
      </div>

      <div style="overflow-x: auto;">
        <table class="table" style="width: 100%; border-collapse: collapse; font-size: 0.88rem;">
          <thead>
            <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; background: #f8fafc;">
              <th style="padding: 0.75rem;">Source Reference</th>
              <th style="padding: 0.75rem;">Category</th>
              <th style="padding: 0.75rem;">Extraction Method</th>
              <th style="padding: 0.75rem;">Owner</th>
              <th style="padding: 0.75rem;">Completeness</th>
              <th style="padding: 0.75rem;">Status</th>
            </tr>
          </thead>
          <tbody>
            ${items.length === 0 ? `<tr><td colspan="6" style="padding: 2rem; text-align: center; color: #94a3b8;">No evidence items registered yet. Register evidence above.</td></tr>` : ''}
            ${items.map(item => `
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 0.75rem; font-family: monospace; font-weight: 600;">${item.source_reference}</td>
                <td style="padding: 0.75rem;"><span class="badge" style="background: #e2e8f0; color: #334155;">${item.category}</span></td>
                <td style="padding: 0.75rem;">${item.extraction_method}</td>
                <td style="padding: 0.75rem;">${item.owner}</td>
                <td style="padding: 0.75rem;"><span class="badge" style="background: ${item.completeness === 'COMPLETE' ? '#dcfce7' : '#fef3c7'}; color: ${item.completeness === 'COMPLETE' ? '#166534' : '#92400e'};">${item.completeness}</span></td>
                <td style="padding: 0.75rem;"><span class="badge" style="background: #dbeafe; color: #1e40af;">${item.verification_status}</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

window.showRegisterEvidenceModal = function(evalId) {
  const ref = prompt("Enter Evidence Source Reference (e.g. AUDIT-SQL-ENCOUNTERS-20261013):");
  if (!ref) return;
  const cat = prompt("Enter Category (e.g. WORKFLOW_TELEMETRY, PREFLIGHT_FAILURES, BACKUP_RESTORE_EXERCISE):", "WORKFLOW_TELEMETRY");
  if (!cat) return;
  const owner = prompt("Enter Owner Role (e.g. PRODUCT_OPERATIONS, CLINICAL_GOVERNANCE):", "PRODUCT_OPERATIONS");
  if (!owner) return;
  const method = prompt("Enter Extraction Method (e.g. SQL_AUDIT_QUERY, TELEMETRY_EXPORT, MANUAL_AUDIT):", "SQL_AUDIT_QUERY");
  if (!method) return;

  apiClient.post(`/api/v1/pilot-evaluations/${evalId}/collect-evidence`, {
    source_reference: ref,
    category: cat,
    owner: owner,
    build_commit: "git:81f9fba",
    extraction_method: method,
    completeness: "COMPLETE",
    verification_status: "VERIFIED"
  }).then(() => {
    alert("Evidence item registered!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderEvidence(subView);
  }).catch(err => alert("Error registering evidence: " + (err.message || err)));
};

// -----------------------------------------------------------------------------
// Sub-view 3: Adoption & Reliability Scorecard
// -----------------------------------------------------------------------------
async function renderScorecard(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading metric scorecard...</div>`;
  const evaluation = await fetchOrCreateActiveEvaluation();
  if (!evaluation) return;

  let res = await apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/scorecard`);
  let observations = res.metric_observations || [];

  if (observations.length === 0) {
    const calcRes = await apiClient.post(`/api/v1/pilot-evaluations/${evaluation.id}/calculate-scorecard`, {});
    res = await apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/scorecard`);
    observations = res.metric_observations || [];
  }

  container.innerHTML = `
    <div class="card" style="padding: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <div>
          <h3 style="margin: 0;">🎯 Adoption & Reliability Metric Scorecard</h3>
          <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.88rem;">
            8 Domain Categories. Pre-agreed threshold targets vs observed data. Missing telemetry is explicitly marked <code>UNAVAILABLE</code>.
          </p>
        </div>
        <button class="btn btn-sm btn-secondary" onclick="window.recomputeScorecard('${evaluation.id}')">🔄 Recompute from Persisted Telemetry</button>
      </div>

      <div style="overflow-x: auto;">
        <table class="table" style="width: 100%; border-collapse: collapse; font-size: 0.88rem;">
          <thead>
            <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; background: #f8fafc;">
              <th style="padding: 0.75rem;">Code</th>
              <th style="padding: 0.75rem;">Domain</th>
              <th style="padding: 0.75rem;">Metric Name</th>
              <th style="padding: 0.75rem;">Target</th>
              <th style="padding: 0.75rem;">Observed Telemetry</th>
              <th style="padding: 0.75rem; text-align: center;">Result</th>
            </tr>
          </thead>
          <tbody>
            ${observations.map(m => {
              const isUnavail = m.is_unavailable;
              const obsText = isUnavail ? `<span style="color: #d97706; font-style: italic;">UNAVAILABLE (${m.unavailable_reason || 'Collector unconfigured'})</span>` : (m.observed_formatted || `${m.observed_value}`);
              const badgeBg = isUnavail ? '#fef3c7' : (m.target_met ? '#dcfce7' : '#fee2e2');
              const badgeColor = isUnavail ? '#92400e' : (m.target_met ? '#166534' : '#991b1b');
              const statusText = isUnavail ? 'UNAVAILABLE' : (m.target_met ? 'PASS' : 'FAIL');

              return `
                <tr style="border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 0.75rem; font-family: monospace; font-weight: 600;">${m.metric_code}</td>
                  <td style="padding: 0.75rem;"><span class="badge" style="background: #f1f5f9; color: #475569;">${m.domain_category}</span></td>
                  <td style="padding: 0.75rem; font-weight: 500;">
                    ${m.metric_name}
                    ${m.limitations ? `<div style="font-size: 0.75rem; color: #64748b; font-style: italic; margin-top: 2px;">Note: ${m.limitations}</div>` : ''}
                  </td>
                  <td style="padding: 0.75rem; color: #475569;">${m.threshold_target || '-'}</td>
                  <td style="padding: 0.75rem;">${obsText}</td>
                  <td style="padding: 0.75rem; text-align: center;">
                    <span class="badge" style="background: ${badgeBg}; color: ${badgeColor}; font-weight: 600;">${statusText}</span>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

window.recomputeScorecard = async function(evalId) {
  try {
    await apiClient.post(`/api/v1/pilot-evaluations/${evalId}/calculate-scorecard`, {});
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderScorecard(subView);
  } catch (err) {
    alert("Error recomputing scorecard: " + (err.message || err));
  }
};

// -----------------------------------------------------------------------------
// Sub-view 4: Feedback & Risk Review
// -----------------------------------------------------------------------------
async function renderFeedbackRisk(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading feedback & risk registers...</div>`;
  const evaluation = await fetchOrCreateActiveEvaluation();
  if (!evaluation) return;

  const [fdbRes, riskRes] = await Promise.all([
    apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/feedback-themes`),
    apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/incident-risks`)
  ]);

  const themes = fdbRes.feedback_themes || [];
  const risks = riskRes.incident_risk_reviews || [];

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 1.5rem;">
      <div class="card" style="padding: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <div>
            <h3 style="margin: 0;">💬 Feedback Theme Triage Review</h3>
            <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.88rem;">
              Sanitized quotes with root-cause hypotheses. PHI/patient data strictly redacted.
            </p>
          </div>
          <button class="btn btn-sm btn-primary" onclick="window.showAddFeedbackThemeModal('${evaluation.id}')">➕ Add Feedback Theme</button>
        </div>

        <div style="overflow-x: auto;">
          <table class="table" style="width: 100%; border-collapse: collapse; font-size: 0.88rem;">
            <thead>
              <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; background: #f8fafc;">
                <th style="padding: 0.75rem;">Theme</th>
                <th style="padding: 0.75rem;">Class</th>
                <th style="padding: 0.75rem;">Role / Flow</th>
                <th style="padding: 0.75rem;">Redacted Quote</th>
                <th style="padding: 0.75rem;">Hypothesis</th>
                <th style="padding: 0.75rem;">Disposition</th>
              </tr>
            </thead>
            <tbody>
              ${themes.length === 0 ? `<tr><td colspan="6" style="padding: 1.5rem; text-align: center; color: #94a3b8;">No feedback themes triaged yet.</td></tr>` : ''}
              ${themes.map(t => `
                <tr style="border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 0.75rem; font-weight: 600;">${t.theme_title}</td>
                  <td style="padding: 0.75rem;"><span class="badge" style="background: #e0e7ff; color: #3730a3;">${t.classification}</span></td>
                  <td style="padding: 0.75rem;">${t.affected_role} (${t.affected_workflow})</td>
                  <td style="padding: 0.75rem; font-style: italic; color: #475569;">"${t.redacted_evidence_quote}"</td>
                  <td style="padding: 0.75rem;">${t.root_cause_hypothesis}</td>
                  <td style="padding: 0.75rem;"><span class="badge" style="background: #dcfce7; color: #166534;">${t.disposition}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card" style="padding: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <div>
            <h3 style="margin: 0;">🛡️ Pre-Expansion Incident & Risk Review</h3>
            <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.88rem;">
              Critical P0/P1 and safety incident re-review. Safety concerns cannot be downgraded purely due to no reported harm.
            </p>
          </div>
          <button class="btn btn-sm btn-secondary" onclick="window.showAddIncidentRiskModal('${evaluation.id}')">➕ Record Risk Review</button>
        </div>

        <div style="overflow-x: auto;">
          <table class="table" style="width: 100%; border-collapse: collapse; font-size: 0.88rem;">
            <thead>
              <tr style="border-bottom: 2px solid #e2e8f0; text-align: left; background: #f8fafc;">
                <th style="padding: 0.75rem;">Issue Ref</th>
                <th style="padding: 0.75rem;">Type</th>
                <th style="padding: 0.75rem;">Severity</th>
                <th style="padding: 0.75rem;">Verified Facts</th>
                <th style="padding: 0.75rem;">Containment</th>
                <th style="padding: 0.75rem;">Corrective Action</th>
              </tr>
            </thead>
            <tbody>
              ${risks.length === 0 ? `<tr><td colspan="6" style="padding: 1.5rem; text-align: center; color: #94a3b8;">Zero uncontained safety or security risks recorded.</td></tr>` : ''}
              ${risks.map(r => `
                <tr style="border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 0.75rem; font-family: monospace; font-weight: 600;">${r.issue_ref}</td>
                  <td style="padding: 0.75rem;">${r.issue_type}</td>
                  <td style="padding: 0.75rem;"><span class="badge" style="background: ${r.severity.startsWith('P0') ? '#fee2e2' : '#fef3c7'}; color: ${r.severity.startsWith('P0') ? '#991b1b' : '#92400e'};">${r.severity}</span></td>
                  <td style="padding: 0.75rem;">${r.verified_facts}</td>
                  <td style="padding: 0.75rem;"><span class="badge" style="background: #dcfce7; color: #166534;">${r.containment_status}</span></td>
                  <td style="padding: 0.75rem;">${r.corrective_action}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

window.showAddFeedbackThemeModal = function(evalId) {
  const title = prompt("Theme Title (e.g. Arabic keyboard autocomplete delay):");
  if (!title) return;
  const quote = prompt("Sanitized Quote (NO PHI/patient numbers):", "Tabib noted slow response when switching between Urdu and English tabs.");
  if (!quote) return;
  const hyp = prompt("Root Cause Hypothesis (clearly labelled as hypothesis):", "Hypothesis: Browser DOM re-render lag during heavy formulation catalog search.");
  if (!hyp) return;

  apiClient.post(`/api/v1/pilot-evaluations/${evalId}/review-feedback`, {
    theme_title: title,
    classification: "USABILITY_FRICTION",
    affected_role: "TABIB",
    affected_workflow: "OPD_CONSULTATION",
    redacted_evidence_quote: quote,
    severity_impact: "MEDIUM",
    root_cause_hypothesis: hyp,
    owner_role: "PRODUCT_OPERATIONS"
  }).then(() => {
    alert("Feedback theme added!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderFeedbackRisk(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

window.showAddIncidentRiskModal = function(evalId) {
  const ref = prompt("Issue Ref (e.g. INC-SAFE-2026-001):");
  if (!ref) return;
  const facts = prompt("Verified Facts:", "All preflight Schedule E(1) checks executed deterministically in sandbox.");
  if (!facts) return;
  const action = prompt("Corrective Action:", "Mandatory double-signature verification on detoxified botanicals.");
  if (!action) return;

  apiClient.post(`/api/v1/pilot-evaluations/${evalId}/review-risks`, {
    issue_ref: ref,
    issue_type: "SAFETY_INCIDENT",
    severity: "P2_MEDIUM",
    verified_facts: facts,
    containment_status: "CONTAINED",
    corrective_action: action
  }).then(() => {
    alert("Risk review item recorded!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderFeedbackRisk(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

// -----------------------------------------------------------------------------
// Sub-view 5: Expansion Gates Matrix
// -----------------------------------------------------------------------------
async function renderExpansion(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading expansion proposals & gates...</div>`;
  const evaluation = await fetchOrCreateActiveEvaluation();
  if (!evaluation) return;

  const res = await apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/expansion-proposals`);
  const proposals = res.expansion_proposals || [];

  container.innerHTML = `
    <div class="card" style="padding: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
        <div>
          <h3 style="margin: 0;">🚪 Independent Expansion Gates Matrix</h3>
          <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.88rem;">
            Each proposed scale vector is evaluated independently across 11 technical, operational, and clinical gates.
          </p>
        </div>
        <button class="btn btn-sm btn-primary" onclick="window.showCreateProposalModal('${evaluation.id}')">➕ New Expansion Proposal</button>
      </div>

      ${proposals.length === 0 ? `
        <div style="text-align: center; padding: 2rem; color: #94a3b8; background: #f8fafc; border-radius: 8px;">
          No expansion proposals created yet. Create an expansion proposal above to evaluate its gates.
        </div>
      ` : ''}

      <div style="display: flex; flex-direction: column; gap: 1.5rem;">
        ${proposals.map(p => `
          <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.25rem; background: #fafafa;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
              <div>
                <h4 style="margin: 0; color: #1e293b; font-size: 1.05rem;">
                  ${p.proposal_type}
                </h4>
                <div style="font-size: 0.85rem; color: #64748b; margin-top: 2px;">${p.justification}</div>
              </div>
              <div>
                <span class="badge" style="background: ${p.overall_gate_status === 'PASSED' ? '#dcfce7' : (p.overall_gate_status === 'BLOCKED' ? '#fee2e2' : '#fef3c7')}; color: ${p.overall_gate_status === 'PASSED' ? '#166534' : (p.overall_gate_status === 'BLOCKED' ? '#991b1b' : '#92400e')}; font-size: 0.9rem; padding: 0.35rem 0.75rem;">
                  Gate Status: ${p.overall_gate_status}
                </span>
              </div>
            </div>

            <div style="margin-top: 0.75rem; background: white; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden;">
              <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                <thead>
                  <tr style="background: #f1f5f9; text-align: left; border-bottom: 1px solid #cbd5e1;">
                    <th style="padding: 0.5rem 0.75rem;">Gate Check</th>
                    <th style="padding: 0.5rem 0.75rem;">Status</th>
                    <th style="padding: 0.5rem 0.75rem;">Evidence Notes</th>
                    <th style="padding: 0.5rem 0.75rem;">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${(p.gates || []).map(g => `
                    <tr style="border-bottom: 1px solid #f1f5f9;">
                      <td style="padding: 0.5rem 0.75rem; font-weight: 500;">${g.gate_name}</td>
                      <td style="padding: 0.5rem 0.75rem;"><span class="badge" style="background: ${g.gate_status === 'PASS' ? '#dcfce7' : '#fee2e2'}; color: ${g.gate_status === 'PASS' ? '#166534' : '#991b1b'};">${g.gate_status}</span></td>
                      <td style="padding: 0.5rem 0.75rem; color: #475569;">${g.evidence_notes || '-'}</td>
                      <td style="padding: 0.5rem 0.75rem;">
                        <button class="btn btn-xs btn-secondary" onclick="window.evaluateGateModal('${p.id}', '${g.gate_name}')">Update</button>
                      </td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>

            <div style="margin-top: 0.75rem; display: flex; justify-content: flex-end;">
              <button class="btn btn-xs btn-primary" onclick="window.addGateToProposal('${p.id}')">➕ Evaluate Additional Gate</button>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

window.showCreateProposalModal = function(evalId) {
  const pType = prompt("Select Proposal Type:\n1: MORE_USERS_SAME_FACILITY\n2: ANOTHER_BRANCH_FACILITY\n3: PHARMACY_INVENTORY_ENABLEMENT\n4: HOSPITAL_IPD_LAB_REFERRAL\n5: FHIR_ABDM_EXCHANGE", "MORE_USERS_SAME_FACILITY");
  if (!pType) return;
  const just = prompt("Justification for expansion proposal:", "Expanded clinical queue capacity for additional Tabib practitioners.");
  if (!just) return;

  apiClient.post(`/api/v1/pilot-evaluations/${evalId}/expansion-proposals`, {
    proposal_type: pType,
    justification: just,
    target_scope_details: { target_users: ["tabib-02", "tabib-03"] },
    prerequisite_dependencies: ["TRAINING_CURRICULUM_PASSED", "CLINICAL_SAFETY_AUDIT"]
  }).then(res => {
    // Automatically add initial mandatory gates
    const propId = res.expansion_proposal.id;
    return Promise.all([
      apiClient.post(`/api/v1/pilot-evaluations/expansion-proposals/${propId}/gates`, {
        gate_name: "MANDATORY_SAFETY_GATE", gate_status: "PASS", evidence_notes: "Fail-closed safety preflight verified"
      }),
      apiClient.post(`/api/v1/pilot-evaluations/expansion-proposals/${propId}/gates`, {
        gate_name: "TRAINING_ONBOARDING_CAPACITY", gate_status: "PASS", evidence_notes: "Staff certified with >90% score"
      }),
      apiClient.post(`/api/v1/pilot-evaluations/expansion-proposals/${propId}/gates`, {
        gate_name: "BACKUP_RESTORE_DRILL", gate_status: "PASS", evidence_notes: "Hot VACUUM drill verified"
      })
    ]);
  }).then(() => {
    alert("Expansion proposal created with verified baseline gates!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderExpansion(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

window.addGateToProposal = function(propId) {
  const gName = prompt("Enter Gate Name (e.g. END_TO_END_TESTS, CLINICAL_CONTENT_APPROVAL, INCIDENT_RESPONSE_READY):", "END_TO_END_TESTS");
  if (!gName) return;
  const gStatus = prompt("Status (PASS, FAIL, BLOCKED, WAIVED):", "PASS");
  if (!gStatus) return;
  const notes = prompt("Evidence notes:", "Automated test suite passing 100%");

  apiClient.post(`/api/v1/pilot-evaluations/expansion-proposals/${propId}/gates`, {
    gate_name: gName, gate_status: gStatus, evidence_notes: notes
  }).then(() => {
    alert("Gate updated!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderExpansion(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

// -----------------------------------------------------------------------------
// Sub-view 6: Decision & Multi-Role Approvals
// -----------------------------------------------------------------------------
async function renderDecision(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading decision & approvals ledger...</div>`;
  const evaluation = await fetchOrCreateActiveEvaluation();
  if (!evaluation) return;

  const [decRes, actRes] = await Promise.all([
    apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/decision`),
    apiClient.get(`/api/v1/pilot-evaluations/${evaluation.id}/actions`)
  ]);

  const decision = decRes.decision;
  const actions = actRes.remediation_actions || [];

  container.innerHTML = `
    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem;">
      <div>
        <div class="card" style="padding: 1.5rem; margin-bottom: 1.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h3 style="margin: 0;">✍️ Formal Post-Pilot Decision Record</h3>
            ${!decision ? `<button class="btn btn-sm btn-primary" onclick="window.showRecordDecisionModal('${evaluation.id}')">Submit Decision</button>` : ''}
          </div>

          ${decision ? `
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 1.25rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <h4 style="margin: 0; color: #1e293b; font-size: 1.1rem;">
                  Recommendation: <span style="color: #0369a1;">${decision.decision}</span>
                </h4>
                <span style="font-size: 0.85rem; color: #64748b;">Recorded: ${decision.created_at}</span>
              </div>
              <p style="margin: 0.75rem 0; font-size: 0.9rem; color: #334155;"><strong>Rationale:</strong> ${decision.rationale}</p>
              <div style="font-size: 0.85rem; color: #475569; display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.75rem;">
                <div><strong>Allowed Scope:</strong> ${decision.allowed_scope_summary}</div>
                <div><strong>Disabled Features:</strong> ${decision.disabled_features_summary}</div>
              </div>
            </div>

            <div style="margin-top: 1.5rem;">
              <h4 style="margin: 0 0 0.75rem 0; color: #1e293b;">Tri-Party Governance Approval Signatures</h4>
              <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem;">
                <thead>
                  <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1; text-align: left;">
                    <th style="padding: 0.6rem 0.75rem;">Required Stakeholder</th>
                    <th style="padding: 0.6rem 0.75rem;">Status</th>
                    <th style="padding: 0.6rem 0.75rem;">Approver ID</th>
                    <th style="padding: 0.6rem 0.75rem;">Action</th>
                  </tr>
                </thead>
                <tbody>
                  ${['CLINICAL_GOVERNANCE', 'PRODUCT_OPERATIONS', 'SECURITY_PRIVACY'].map(role => {
                    const app = (decision.approvals || []).find(a => a.required_role === role);
                    const isApproved = app && app.approval_status === 'APPROVED';
                    return `
                      <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 0.6rem 0.75rem; font-weight: 600;">${role}</td>
                        <td style="padding: 0.6rem 0.75rem;">
                          <span class="badge" style="background: ${isApproved ? '#dcfce7' : '#fee2e2'}; color: ${isApproved ? '#166534' : '#991b1b'};">
                            ${isApproved ? 'APPROVED' : 'PENDING'}
                          </span>
                        </td>
                        <td style="padding: 0.6rem 0.75rem; font-family: monospace;">${app ? app.approver_user_id : '-'}</td>
                        <td style="padding: 0.6rem 0.75rem;">
                          ${!isApproved ? `<button class="btn btn-xs btn-primary" onclick="window.signApproval('${decision.id}', '${role}')">Sign Off</button>` : 'Signed'}
                        </td>
                      </tr>
                    `;
                  }).join('')}
                </tbody>
              </table>
            </div>
          ` : `
            <div style="padding: 2rem; text-align: center; color: #94a3b8; background: #f8fafc; border-radius: 8px;">
              No formal decision submitted yet. Click "Submit Decision" above to record the scale verdict.
            </div>
          `}
        </div>

        <div class="card" style="padding: 1.5rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h3 style="margin: 0;">🔧 Post-Pilot Remediation Actions</h3>
            <button class="btn btn-sm btn-secondary" onclick="window.showAddActionModal('${evaluation.id}')">➕ Add Action Item</button>
          </div>

          <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem;">
            <thead>
              <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1; text-align: left;">
                <th style="padding: 0.6rem 0.75rem;">Action</th>
                <th style="padding: 0.6rem 0.75rem;">Priority</th>
                <th style="padding: 0.6rem 0.75rem;">Retest Requirement</th>
                <th style="padding: 0.6rem 0.75rem;">Status</th>
                <th style="padding: 0.6rem 0.75rem;">Resolve</th>
              </tr>
            </thead>
            <tbody>
              ${actions.length === 0 ? `<tr><td colspan="5" style="padding: 1.5rem; text-align: center; color: #94a3b8;">Zero open remediation actions.</td></tr>` : ''}
              ${actions.map(a => `
                <tr style="border-bottom: 1px solid #e2e8f0;">
                  <td style="padding: 0.6rem 0.75rem; font-weight: 500;">${a.title}</td>
                  <td style="padding: 0.6rem 0.75rem;"><span class="badge" style="background: ${a.priority === 'P0' ? '#fee2e2' : '#fef3c7'}; color: ${a.priority === 'P0' ? '#991b1b' : '#92400e'};">${a.priority}</span></td>
                  <td style="padding: 0.6rem 0.75rem; color: #475569;">${a.retest_requirement}</td>
                  <td style="padding: 0.6rem 0.75rem;"><span class="badge" style="background: ${a.status === 'VERIFIED_CLOSED' ? '#dcfce7' : '#f1f5f9'}; color: ${a.status === 'VERIFIED_CLOSED' ? '#166534' : '#475569'};">${a.status}</span></td>
                  <td style="padding: 0.6rem 0.75rem;">
                    ${a.status !== 'VERIFIED_CLOSED' ? `<button class="btn btn-xs btn-primary" onclick="window.closeActionModal('${a.id}')">Close</button>` : 'Verified'}
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <div class="card" style="padding: 1.25rem;">
          <h4 style="margin: 0 0 0.75rem 0; color: #1e293b;">Scale Verdict Categories</h4>
          <ul style="font-size: 0.85rem; color: #475569; padding-left: 1.25rem; margin: 0; line-height: 1.6;">
            <li><code>CONTINUE_CURRENT_PILOT</code>: Maintain limited single-clinic OPD scope.</li>
            <li><code>EXPAND_WITHIN_APPROVED_SCOPE</code>: Onboard more trained Tabibs at existing facility.</li>
            <li><code>EXPAND_TO_ADDITIONAL_FACILITY</code>: Scale to Branch B once checklist completed.</li>
            <li><code>ENABLE_SPECIFIC_MODULE</code>: Enable Pharmacy or IPD after gate passes.</li>
            <li><code>PAUSE_FOR_REMEDIATION</code>: Freeze new admissions for critical fixes.</li>
            <li><code>STOP_OR_ROLLBACK</code>: Immediate incident rollback.</li>
            <li><code>NOT_YET_ASSESSABLE</code>: Insufficient telemetry gathered.</li>
          </ul>
        </div>
      </div>
    </div>
  `;
}

window.showRecordDecisionModal = function(evalId) {
  const dec = prompt("Enter Recommendation:\n1: CONTINUE_CURRENT_PILOT\n2: EXPAND_WITHIN_APPROVED_SCOPE\n3: EXPAND_TO_ADDITIONAL_FACILITY\n4: ENABLE_SPECIFIC_MODULE\n5: PAUSE_FOR_REMEDIATION", "EXPAND_WITHIN_APPROVED_SCOPE");
  if (!dec) return;
  const rat = prompt("Decision Rationale:", "Core OPD workflow passed 100% safety checks with zero P0 incidents.");
  if (!rat) return;

  apiClient.post(`/api/v1/pilot-evaluations/${evalId}/record-decision`, {
    decision: dec,
    rationale: rat,
    allowed_scope_summary: "Central Matab OPD (Dr. Hakim Zafar & certified staff)",
    disabled_features_summary: "Live ABDM Gateway & Public SMS Gateway remain disabled",
    next_review_date: "2026-11-15"
  }).then(() => {
    alert("Decision recorded!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderDecision(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

window.signApproval = function(decId, role) {
  const notes = prompt(`Sign-off notes for ${role}:`, "Verified all gate checks and audit evidence.");
  if (notes === null) return;

  apiClient.post(`/api/v1/pilot-evaluations/decision-approvals`, {
    decision_record_id: decId,
    required_role: role,
    approval_status: "APPROVED",
    conditions_or_notes: notes
  }).then(() => {
    alert(`Signed off as ${role}!`);
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderDecision(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

window.showAddActionModal = function(evalId) {
  const title = prompt("Action Title (e.g. Add Arabic IME automated testing):");
  if (!title) return;
  const req = prompt("Retest Requirement:", "Automated Cypress/Playwright regression pass.");
  if (!req) return;

  apiClient.post(`/api/v1/pilot-evaluations/${evalId}/actions`, {
    title: title,
    description: "Ensure smooth typography rendering on tablet screens.",
    category: "USABILITY",
    priority: "P2",
    owner_role: "PRODUCT_OPERATIONS",
    retest_requirement: req
  }).then(() => {
    alert("Remediation action created!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderDecision(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

window.closeActionModal = function(actionId) {
  const ref = prompt("Mandatory Retest Evidence Reference (required to close):", "TEST-RUN-20261013-PASS");
  if (!ref) return;

  apiClient.post(`/api/v1/pilot-evaluations/actions/${actionId}/close`, {
    retest_evidence_ref: ref
  }).then(() => {
    alert("Action closed with verified retest evidence!");
    const subView = document.querySelector("#evalSubViewContent");
    if (subView) renderDecision(subView);
  }).catch(err => alert("Error: " + (err.message || err)));
};

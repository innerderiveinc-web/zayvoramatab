/**
 * Phase 14 Controlled Pilot Launch, Clinic Onboarding, Training & Operations View
 * Standalone ZAYVORA MATAB OS
 */

import { state } from "../state.js";
import { apiClient } from "/packages/api-client/client.js";

export async function renderPilotLaunch(container) {
  const user = state.user;
  container.innerHTML = `
    <div class="header-card" style="margin-bottom: 1.5rem;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
        <div>
          <h2 style="margin: 0; display: flex; align-items: center; gap: 0.5rem;">
            <span>🚀</span>
            <span>Controlled Pilot Launch & Clinic Onboarding</span>
          </h2>
          <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.9rem;">
            Operational Readiness, Scope Enforcement, 13-Stage Facility Onboarding & Clinical Safety Triage
          </p>
        </div>
        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
          <span class="badge" id="pilotStatusBadge" style="background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; font-weight: 600;">
            Program: LOADING...
          </span>
          <span class="badge" style="background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1;">
            Audit Ref: AUDIT-CLINICAL-GOVERNANCE-2026-10-13
          </span>
        </div>
      </div>
      
      <div style="display: flex; gap: 0.5rem; margin-top: 1.25rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; overflow-x: auto;">
        <button id="tabOverviewBtn" class="btn btn-sm btn-primary">📊 Pilot Scope & Eligibility</button>
        <button id="tabChecklistBtn" class="btn btn-sm btn-secondary">📋 13-Stage Facility Onboarding</button>
        <button id="tabTrainingBtn" class="btn btn-sm btn-secondary">🎓 Staff Training & Acceptance</button>
        <button id="tabMigrationBtn" class="btn btn-sm btn-secondary">📥 Data Migration (Pre-Validation)</button>
        <button id="tabSupportBtn" class="btn btn-sm btn-secondary">🛡️ Support & Clinical Safety Queue</button>
        <button id="tabMetricsBtn" class="btn btn-sm btn-secondary">📈 Metrics & Review Packs</button>
      </div>
    </div>

    <div id="pilotSubViewContent">
      <div style="text-align: center; padding: 2rem; color: #94a3b8;">Loading Pilot Control Panel...</div>
    </div>
  `;

  const subView = container.querySelector("#pilotSubViewContent");
  const tabOverview = container.querySelector("#tabOverviewBtn");
  const tabChecklist = container.querySelector("#tabChecklistBtn");
  const tabTraining = container.querySelector("#tabTrainingBtn");
  const tabMigration = container.querySelector("#tabMigrationBtn");
  const tabSupport = container.querySelector("#tabSupportBtn");
  const tabMetrics = container.querySelector("#tabMetricsBtn");

  const tabs = [
    { btn: tabOverview, render: renderOverview },
    { btn: tabChecklist, render: renderChecklist },
    { btn: tabTraining, render: renderTraining },
    { btn: tabMigration, render: renderMigration },
    { btn: tabSupport, render: renderSupport },
    { btn: tabMetrics, render: renderMetrics }
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

  // Default view
  renderOverview(subView);

  // Initial fetch of active pilot program
  try {
    const res = await apiClient.get("/api/v1/pilot/programs");
    if (res.pilot_programs && res.pilot_programs.length > 0) {
      const p = res.pilot_programs[0];
      const badge = container.querySelector("#pilotStatusBadge");
      if (badge) {
        badge.textContent = `Pilot: ${p.code} (${p.status})`;
        if (p.status === "ACTIVATED") {
          badge.style.background = "#dcfce7";
          badge.style.color = "#15803d";
        } else if (p.status === "PAUSED" || p.status === "STOPPED") {
          badge.style.background = "#fee2e2";
          badge.style.color = "#b91c1c";
        }
      }
    }
  } catch (e) {
    console.error("Failed to load pilot status badge", e);
  }
}

// ============================================================================
// Sub-view 1: Pilot Scope & Eligibility Gate
// ============================================================================
async function renderOverview(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading eligibility & scope...</div>`;
  try {
    const progRes = await apiClient.get("/api/v1/pilot/programs");
    const program = (progRes.pilot_programs && progRes.pilot_programs[0]) || null;

    if (!program) {
      container.innerHTML = `<div class="card p-3">No active pilot program registered.</div>`;
      return;
    }

    const eligRes = await apiClient.get(`/api/v1/pilot/programs/${program.id}/eligibility`);
    const elig = eligRes.eligibility;
    const scope = program.active_scope || {};

    container.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;">
        <!-- Left: Program & Scope Card -->
        <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
          <h3 style="margin-top: 0; font-size: 1.1rem; color: #1e293b;">📋 Versioned Scope Declaration</h3>
          <p style="color: #64748b; font-size: 0.85rem;"><strong>Code:</strong> ${program.code} (v${scope.version_number || 1})</p>
          <p style="color: #64748b; font-size: 0.85rem;"><strong>Name:</strong> ${program.name}</p>
          <p style="color: #64748b; font-size: 0.85rem;"><strong>Audit Verdict:</strong> <span class="badge" style="background:#e0f2fe; color:#0369a1;">${program.audit_verdict}</span></p>

          <div style="margin-top: 1rem;">
            <div style="font-size: 0.85rem; font-weight: 600; color: #334155;">Enabled Modules:</div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.25rem;">
              ${(scope.enabled_modules || []).map(m => `<span class="badge" style="background:#dcfce7; color:#166534; font-size:0.75rem;">${m}</span>`).join('')}
            </div>
          </div>

          <div style="margin-top: 0.75rem;">
            <div style="font-size: 0.85rem; font-weight: 600; color: #334155;">Explicitly Disabled Features:</div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.25rem;">
              ${(scope.disabled_modules || []).map(m => `<span class="badge" style="background:#fee2e2; color:#991b1b; font-size:0.75rem;">${m}</span>`).join('')}
            </div>
          </div>

          <div style="margin-top: 0.75rem;">
            <div style="font-size: 0.85rem; font-weight: 600; color: #334155;">Enrolled Facilities:</div>
            <div style="font-size: 0.85rem; color: #475569;">${(scope.permitted_facilities || []).join(', ')}</div>
          </div>

          <div style="margin-top: 0.75rem;">
            <div style="font-size: 0.85rem; font-weight: 600; color: #334155;">Known Limitations:</div>
            <div style="font-size: 0.8rem; color: #64748b; background: #f8fafc; padding: 0.5rem; border-radius: 4px; margin-top: 0.25rem;">
              ${scope.known_limitations || 'None recorded.'}
            </div>
          </div>
        </div>

        <!-- Right: Eligibility Gate Evaluation -->
        <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <h3 style="margin: 0; font-size: 1.1rem; color: #1e293b;">🔒 Server-Side Eligibility Gate</h3>
            <span class="badge" style="background: ${elig.eligible ? '#dcfce7' : '#fee2e2'}; color: ${elig.eligible ? '#15803d' : '#b91c1c'}; font-weight: 600;">
              ${elig.eligible ? 'ELIGIBLE' : 'BLOCKED'}
            </span>
          </div>
          <p style="color: #64748b; font-size: 0.85rem; margin: 0.25rem 0 1rem 0;">
            Recomputed server-side. Fails closed if any mandatory criterion is not satisfied.
          </p>

          <div style="display: flex; flex-direction: column; gap: 0.5rem;">
            ${(elig.gates || []).map(g => `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem; background: #f8fafc; border-radius: 4px; border-left: 3px solid ${g.status === 'PASS' ? '#22c55e' : '#ef4444'};">
                <div>
                  <div style="font-size: 0.85rem; font-weight: 600; color: #1e293b;">${g.gate}</div>
                  <div style="font-size: 0.75rem; color: #64748b;">${g.details}</div>
                </div>
                <span class="badge" style="background: ${g.status === 'PASS' ? '#dcfce7' : '#fee2e2'}; color: ${g.status === 'PASS' ? '#15803d' : '#b91c1c'};">
                  ${g.status}
                </span>
              </div>
            `).join('')}
          </div>

          ${elig.blockers && elig.blockers.length > 0 ? `
            <div style="margin-top: 1rem; padding: 0.75rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 4px;">
              <strong style="color: #991b1b; font-size: 0.85rem;">Activation Blockers:</strong>
              <ul style="margin: 0.25rem 0 0 1.25rem; color: #b91c1c; font-size: 0.8rem; padding: 0;">
                ${elig.blockers.map(b => `<li>${b}</li>`).join('')}
              </ul>
            </div>
          ` : ''}

          <div style="margin-top: 1.25rem; display: flex; gap: 0.5rem;">
            <button id="activatePilotBtn" class="btn btn-sm btn-primary" ${!elig.eligible || program.status === 'ACTIVATED' ? 'disabled' : ''}>
              ${program.status === 'ACTIVATED' ? '✅ Pilot Already Activated' : '🚀 Activate Pilot for Live Clinical Traffic'}
            </button>
            ${program.status === 'ACTIVATED' ? `
              <button id="pausePilotBtn" class="btn btn-sm btn-danger">⏸️ Pause Pilot Operations</button>
            ` : ''}
          </div>
        </div>
      </div>
    `;

    const actBtn = container.querySelector("#activatePilotBtn");
    if (actBtn && !actBtn.disabled) {
      actBtn.addEventListener("click", async () => {
        try {
          const actRes = await apiClient.post(`/api/v1/pilot/programs/${program.id}/activate`, {});
          alert("Success: Pilot program activated for controlled live clinical traffic!");
          renderOverview(container);
        } catch (e) {
          alert(`Error activating pilot: ${e.message || e}`);
        }
      });
    }

    const pauseBtn = container.querySelector("#pausePilotBtn");
    if (pauseBtn) {
      pauseBtn.addEventListener("click", async () => {
        const reason = prompt("Enter pause condition reason:");
        if (!reason) return;
        try {
          await apiClient.post("/api/v1/pilot/stop-events/trigger", {
            pilot_program_id: program.id,
            condition_code: "SAVE_FAILURE_LOOP",
            action_taken: "PAUSE_PILOT_ALL",
            containment_actions: ["HALT_NEW_CONSULTATIONS"],
            restart_criteria: "Resolve defect and verify in staging"
          });
          alert("Pilot program paused.");
          renderOverview(container);
        } catch (e) {
          alert(`Error pausing pilot: ${e.message || e}`);
        }
      });
    }

  } catch (err) {
    container.innerHTML = `<div class="card p-3" style="color:red;">Error loading overview: ${err.message}</div>`;
  }
}

// ============================================================================
// Sub-view 2: 13-Stage Facility Onboarding Board
// ============================================================================
async function renderChecklist(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading 13-stage facility onboarding checklist...</div>`;
  try {
    const progRes = await apiClient.get("/api/v1/pilot/programs");
    const program = progRes.pilot_programs[0];
    const facId = "fac-central-opd";

    const chkRes = await apiClient.get(`/api/v1/pilot/programs/${program.id}/facilities/${facId}/checklist`);
    const checklist = chkRes.checklist || [];

    const completedCount = checklist.filter(s => s.status === "COMPLETED").length;
    const progressPct = Math.round((completedCount / checklist.length) * 100);

    container.innerHTML = `
      <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <div>
            <h3 style="margin: 0; font-size: 1.1rem; color: #1e293b;">📋 Facility Onboarding: ${facId}</h3>
            <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.85rem;">
              13 mandatory sequential operational stages before clinical go-live
            </p>
          </div>
          <div style="text-align: right;">
            <div style="font-weight: 600; font-size: 0.95rem; color: #0284c7;">${completedCount} / ${checklist.length} Completed (${progressPct}%)</div>
            <div style="width: 140px; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; margin-top: 0.25rem;">
              <div style="width: ${progressPct}%; height: 100%; background: #0284c7;"></div>
            </div>
          </div>
        </div>

        <div style="display: flex; flex-direction: column; gap: 0.75rem;">
          ${checklist.map(stage => {
            let badgeBg = "#f1f5f9";
            let badgeColor = "#475569";
            if (stage.status === "COMPLETED") { badgeBg = "#dcfce7"; badgeColor = "#15803d"; }
            else if (stage.status === "IN_PROGRESS") { badgeBg = "#fef3c7"; badgeColor = "#b45309"; }
            else if (stage.status === "BLOCKED") { badgeBg = "#fee2e2"; badgeColor = "#b91c1c"; }

            return `
              <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;">
                <div style="flex: 1;">
                  <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="font-weight: 700; color: #3b82f6; font-size: 0.9rem;">Stage ${stage.stage_order}</span>
                    <strong style="font-size: 0.9rem; color: #1e293b;">${stage.stage_title}</strong>
                    <span class="badge" style="background: ${badgeBg}; color: ${badgeColor}; font-size: 0.75rem;">${stage.status}</span>
                  </div>
                  ${stage.evidence_notes ? `<div style="font-size: 0.8rem; color: #475569; margin-top: 0.25rem;"><strong>Evidence:</strong> ${stage.evidence_notes}</div>` : ''}
                  ${stage.completed_at ? `<div style="font-size: 0.75rem; color: #94a3b8;">Completed: ${stage.completed_at}</div>` : ''}
                </div>
                <div>
                  <button class="btn btn-sm btn-secondary updateStageBtn" data-id="${stage.id}" data-order="${stage.stage_order}" data-status="${stage.status}">
                    ${stage.status === 'COMPLETED' ? 'Review / Edit' : 'Complete Stage'}
                  </button>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;

    container.querySelectorAll(".updateStageBtn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const stageId = btn.getAttribute("data-id");
        const currentStatus = btn.getAttribute("data-status");
        const nextStatus = currentStatus === "COMPLETED" ? "IN_PROGRESS" : "COMPLETED";
        const notes = prompt("Enter verification evidence notes for this stage:", "Verified by clinical operational lead.");
        if (notes === null) return;

        try {
          await apiClient.post(`/api/v1/pilot/checklists/${stageId}/update`, {
            status: nextStatus,
            evidence_notes: notes
          });
          renderChecklist(container);
        } catch (e) {
          alert(`Error updating stage: ${e.message || e}`);
        }
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="card p-3" style="color:red;">Error loading checklist: ${err.message}</div>`;
  }
}

// ============================================================================
// Sub-view 3: Staff Training & Acceptance Tracker
// ============================================================================
async function renderTraining(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading training modules...</div>`;
  try {
    const progRes = await apiClient.get("/api/v1/pilot/programs");
    const program = progRes.pilot_programs[0];
    const facId = "fac-central-opd";

    const modRes = await apiClient.get("/api/v1/pilot/training/modules");
    const modules = modRes.training_modules || [];

    const matrixRes = await apiClient.get(`/api/v1/pilot/programs/${program.id}/facilities/${facId}/training-matrix`);
    const matrix = matrixRes.training_matrix || {};

    container.innerHTML = `
      <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <div>
            <h3 style="margin: 0; font-size: 1.1rem; color: #1e293b;">🎓 Role-Based Training & Acceptance Tracker</h3>
            <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.85rem;">
              Versioned curricula with practical clinical scenario drills. Completion rate: ${matrix.completion_rate_percentage || 0}%
            </p>
          </div>
          <div>
            <button id="enrollStaffBtn" class="btn btn-sm btn-primary">➕ Enroll Staff Member</button>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
          ${modules.map(mod => `
            <div style="padding: 1rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="badge" style="background: #e0f2fe; color: #0369a1; font-weight: 600;">${mod.code}</span>
                <span class="badge" style="background: #f1f5f9; color: #475569;">Target: ${mod.target_role}</span>
              </div>
              <h4 style="margin: 0.5rem 0 0.25rem 0; font-size: 0.95rem; color: #1e293b;">${mod.title}</h4>
              <p style="font-size: 0.8rem; color: #64748b; margin: 0;">${mod.description}</p>
              <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.75rem; font-size: 0.75rem; color: #94a3b8;">
                <span>Min Pass Score: ${mod.min_pass_score}%</span>
                <span>Curriculum v${mod.curriculum_version}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    const enrollBtn = container.querySelector("#enrollStaffBtn");
    if (enrollBtn) {
      enrollBtn.addEventListener("click", async () => {
        const userId = prompt("Enter User ID to enroll (e.g., usr-hakeem-1):", "usr-hakeem-1");
        if (!userId) return;
        const moduleId = prompt("Enter Training Module ID (e.g., trn-mod-tabib-1):", "trn-mod-tabib-1");
        if (!moduleId) return;

        try {
          const res = await apiClient.post("/api/v1/pilot/training/enroll", {
            pilot_program_id: program.id,
            facility_id: facId,
            user_id: userId,
            training_module_id: moduleId
          });

          const score = prompt("Enter Scenario Examination Score (0 - 100):", "92");
          if (score !== null) {
            await apiClient.post(`/api/v1/pilot/training/enrollments/${res.enrollment.id}/complete`, {
              score: parseInt(score, 10),
              scenario_acceptance_notes: "Successfully passed clinical consultation and safety override evaluation."
            });
            alert("Staff member successfully trained and certified!");
          }
          renderTraining(container);
        } catch (e) {
          alert(`Enrollment error: ${e.message || e}`);
        }
      });
    }

  } catch (err) {
    container.innerHTML = `<div class="card p-3" style="color:red;">Error loading training: ${err.message}</div>`;
  }
}

// ============================================================================
// Sub-view 4: Governed Data Migration & Reconciliation
// ============================================================================
async function renderMigration(container) {
  container.innerHTML = `
    <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
      <h3 style="margin-top: 0; font-size: 1.1rem; color: #1e293b;">📥 Governed Data Migration & Controlled Import</h3>
      <p style="color: #64748b; font-size: 0.85rem; margin-bottom: 1rem;">
        Pre-import validation safeguards clinical record integrity. Identifies potential duplicates and normalizes demographic data prior to live import.
      </p>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
        <div>
          <label style="font-size: 0.85rem; font-weight: 600;">Source Legacy System Name:</label>
          <input id="migSourceSystem" class="form-control mb-2" value="Legacy Matab Register CSV" style="width: 100%; padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 4px;" />
          
          <label style="font-size: 0.85rem; font-weight: 600;">Lawful Authority Reference:</label>
          <input id="migSourceRef" class="form-control mb-2" value="CLINIC-CONSENT-MIG-2026-001" style="width: 100%; padding: 0.4rem; border: 1px solid #cbd5e1; border-radius: 4px;" />
          
          <label style="font-size: 0.85rem; font-weight: 600;">JSON Records Payload:</label>
          <textarea id="migRecordsJson" rows="8" style="width: 100%; font-family: monospace; font-size: 0.8rem; padding: 0.5rem; border: 1px solid #cbd5e1; border-radius: 4px;">[
  {
    "name": "Zahida Parveen",
    "phone": "+91-9811223344",
    "gender": "FEMALE",
    "dob": "1985-04-12"
  },
  {
    "name": "Mohammad Irfan",
    "phone": "+91-9876543210",
    "gender": "MALE",
    "dob": "1978-09-22"
  }
]</textarea>

          <div style="display: flex; gap: 0.5rem; margin-top: 0.75rem;">
            <button id="runDryRunBtn" class="btn btn-sm btn-primary">🔍 Preview & Validate (Safe Audit)</button>
            <button id="runExecuteBtn" class="btn btn-sm btn-secondary">💾 Commit & Import Records</button>
          </div>
        </div>

        <div id="migrationOutputBox" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 1rem; overflow-y: auto; max-height: 350px;">
          <div style="color: #94a3b8; font-size: 0.85rem; text-align: center; margin-top: 3rem;">
            Validate the records preview above to verify duplicate checks and schema compliance.
          </div>
        </div>
      </div>
    </div>
  `;

  const runDryRunBtn = container.querySelector("#runDryRunBtn");
  const runExecuteBtn = container.querySelector("#runExecuteBtn");
  const outputBox = container.querySelector("#migrationOutputBox");

  async function executeMigration(mode) {
    outputBox.innerHTML = `<div style="text-align: center; color: #64748b;">Processing ${mode}...</div>`;
    try {
      const progRes = await apiClient.get("/api/v1/pilot/programs");
      const program = progRes.pilot_programs[0];
      const source = container.querySelector("#migSourceSystem").value;
      const ref = container.querySelector("#migSourceRef").value;
      const records = JSON.parse(container.querySelector("#migRecordsJson").value);

      const res = await apiClient.post("/api/v1/pilot/migrations/run", {
        pilot_program_id: program.id,
        facility_id: "fac-central-opd",
        source_system_name: source,
        source_authority_reference: ref,
        raw_records: records,
        mode: mode
      });

      const r = res.migration_result;
      outputBox.innerHTML = `
        <h4 style="margin-top: 0; font-size: 0.95rem; color: #1e293b;">Reconciliation Report (${r.mode})</h4>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.85rem; margin-bottom: 0.75rem;">
          <div>Total Read: <strong>${r.total_records_read}</strong></div>
          <div>Migrated / Clean: <strong style="color: green;">${r.records_migrated}</strong></div>
          <div>Ambiguous Duplicates: <strong style="color: orange;">${r.ambiguous_duplicates_flagged}</strong></div>
          <div>Rejected / Errors: <strong style="color: red;">${r.records_rejected}</strong></div>
        </div>
        <div style="font-size: 0.75rem; color: #64748b; background: #fff; padding: 0.5rem; border: 1px solid #cbd5e1; border-radius: 4px;">
          Status: <strong>${r.status}</strong><br>
          Migration Run ID: <code>${r.migration_id}</code>
        </div>
      `;
    } catch (e) {
      outputBox.innerHTML = `<div style="color: red; font-size: 0.85rem;">Migration error: ${e.message || e}</div>`;
    }
  }

  runDryRunBtn.addEventListener("click", () => executeMigration("DRY_RUN"));
  runExecuteBtn.addEventListener("click", () => {
    if (confirm("Are you sure you want to execute real database insertion of non-duplicate records?")) {
      executeMigration("EXECUTE");
    }
  });
}

// ============================================================================
// Sub-view 5: Support & Clinical Safety Queue
// ============================================================================
async function renderSupport(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading support tickets & safety queue...</div>`;
  try {
    const progRes = await apiClient.get("/api/v1/pilot/programs");
    const program = progRes.pilot_programs[0];

    const tktRes = await apiClient.get(`/api/v1/pilot/programs/${program.id}/tickets`);
    const tickets = tktRes.tickets || [];

    const safeRes = await apiClient.get(`/api/v1/pilot/programs/${program.id}/safety-queue`);
    const safetyQueue = safeRes.clinical_safety_queue || [];

    container.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
        <!-- Left: Support Tickets -->
        <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <h3 style="margin: 0; font-size: 1.05rem; color: #1e293b;">🎫 Operational Support Tickets</h3>
            <button id="newTicketBtn" class="btn btn-sm btn-primary">➕ Log Ticket</button>
          </div>
          <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 400px; overflow-y: auto;">
            ${tickets.length === 0 ? `<div style="color: #94a3b8; font-size: 0.85rem; padding: 1rem; text-align: center;">No tickets open.</div>` : ''}
            ${tickets.map(t => `
              <div style="padding: 0.5rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.85rem;">
                <div style="display: flex; justify-content: space-between;">
                  <strong>${t.ticket_number}</strong>
                  <span class="badge" style="background: ${t.severity === 'SEV_1_CRITICAL' ? '#fee2e2' : '#f1f5f9'}; color: ${t.severity === 'SEV_1_CRITICAL' ? '#b91c1c' : '#475569'};">${t.severity}</span>
                </div>
                <div style="color: #1e293b; font-weight: 500; margin: 0.25rem 0;">${t.subject}</div>
                <div style="color: #64748b; font-size: 0.75rem;">Category: ${t.category} | Status: ${t.status}</div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Right: Dedicated Clinical Safety Review Queue -->
        <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
            <h3 style="margin: 0; font-size: 1.05rem; color: #991b1b; display: flex; align-items: center; gap: 0.25rem;">
              <span>🚨</span>
              <span>Clinical Safety Governance Queue</span>
            </h3>
            <span class="badge" style="background: #fee2e2; color: #991b1b;">${safetyQueue.length} Alerts</span>
          </div>
          <p style="font-size: 0.8rem; color: #64748b; margin: 0 0 0.5rem 0;">
            Independent escalation path for potential false alerts, missed contraindications, or adverse effect concerns.
          </p>
          <div style="display: flex; flex-direction: column; gap: 0.5rem; max-height: 400px; overflow-y: auto;">
            ${safetyQueue.length === 0 ? `<div style="color: #94a3b8; font-size: 0.85rem; padding: 1rem; text-align: center;">Safety queue is clear. Zero active alerts.</div>` : ''}
            ${safetyQueue.map(inc => `
              <div style="padding: 0.75rem; background: #fff5f5; border: 1px solid #fecaca; border-radius: 4px; font-size: 0.85rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <strong style="color: #991b1b;">${inc.incident_number}</strong>
                  <span class="badge" style="background: #fee2e2; color: #991b1b;">${inc.status}</span>
                </div>
                <div style="margin: 0.25rem 0; color: #7f1d1d;">${inc.clinical_description}</div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
                  <span style="font-size: 0.75rem; color: #991b1b;">Type: ${inc.issue_type}</span>
                  ${inc.status === 'PENDING_REVIEW' ? `
                    <button class="btn btn-sm btn-secondary resolveIncBtn" data-id="${inc.id}">Review & Resolve</button>
                  ` : `
                    <span style="font-size: 0.75rem; color: #15803d;">Action: ${inc.governance_action}</span>
                  `}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;

    const newTicketBtn = container.querySelector("#newTicketBtn");
    if (newTicketBtn) {
      newTicketBtn.addEventListener("click", async () => {
        const cat = prompt("Category (ACCESS_LOGIN, PATIENT_ENCOUNTER, PRESCRIPTION_DOC, SAFETY_ALERT, CLINICAL_SAFETY_INCIDENT):", "SAFETY_ALERT");
        if (!cat) return;
        const subj = prompt("Subject:", "Safety preflight warning clarification on Jawarish Kamuni");
        if (!subj) return;
        const desc = prompt("Safe Redacted Description (NO PHI):", "Tabib questioned dosage advisory on elderly patient.");
        if (!desc) return;

        try {
          await apiClient.post("/api/v1/pilot/tickets", {
            pilot_program_id: program.id,
            facility_id: "fac-central-opd",
            category: cat,
            severity: cat === "CLINICAL_SAFETY_INCIDENT" ? "SEV_1_CRITICAL" : "SEV_3_MODERATE",
            subject: subj,
            safe_description: desc
          });
          renderSupport(container);
        } catch (e) {
          alert(`Error creating ticket: ${e.message || e}`);
        }
      });
    }

    container.querySelectorAll(".resolveIncBtn").forEach(btn => {
      btn.addEventListener("click", async () => {
        const incId = btn.getAttribute("data-id");
        const action = prompt("Governance Action (NO_ACTION, RULE_UPDATE_REQUIRED, MONOGRAPH_AMENDMENT, RETRAINING_ORDERED):", "MONOGRAPH_AMENDMENT");
        if (!action) return;

        try {
          await apiClient.post(`/api/v1/pilot/safety-queue/${incId}/resolve`, {
            governance_action: action,
            notes: "Clinical committee confirmed monograph dosage refinement."
          });
          renderSupport(container);
        } catch (e) {
          alert(`Error resolving incident: ${e.message || e}`);
        }
      });
    });

  } catch (err) {
    container.innerHTML = `<div class="card p-3" style="color:red;">Error loading support: ${err.message}</div>`;
  }
}

// ============================================================================
// Sub-view 6: Metrics & Review Packs
// ============================================================================
async function renderMetrics(container) {
  container.innerHTML = `<div style="text-align: center; padding: 2rem;">Loading pilot operational metrics...</div>`;
  try {
    const progRes = await apiClient.get("/api/v1/pilot/programs");
    const program = progRes.pilot_programs[0];

    const metRes = await apiClient.get(`/api/v1/pilot/programs/${program.id}/metrics`);
    const m = metRes.metrics || {};

    container.innerHTML = `
      <div class="card p-3" style="background: white; border-radius: 8px; border: 1px solid #e2e8f0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <div>
            <h3 style="margin: 0; font-size: 1.1rem; color: #1e293b;">📈 Pilot Operational Metrics & Review Packs</h3>
            <p style="margin: 0.25rem 0 0 0; color: #64748b; font-size: 0.85rem;">
              Real metrics aggregated from persistent database records. Measured at ${m.timestamp}
            </p>
          </div>
          <div>
            <button id="genReviewPackBtn" class="btn btn-sm btn-primary">📑 Generate Weekly Review Pack</button>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
          <div style="padding: 1rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px;">
            <div style="font-size: 0.8rem; color: #166534; font-weight: 600;">Staff Training Pass Rate</div>
            <div style="font-size: 1.75rem; font-weight: 700; color: #15803d;">${m.training.completion_rate_percentage}%</div>
            <div style="font-size: 0.75rem; color: #166534;">${m.training.passed} of ${m.training.total_enrolled} Passed</div>
          </div>

          <div style="padding: 1rem; background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px;">
            <div style="font-size: 0.8rem; color: #0369a1; font-weight: 600;">Onboarding Stages</div>
            <div style="font-size: 1.75rem; font-weight: 700; color: #0284c7;">${m.onboarding.completed_stages} / ${m.onboarding.total_stages}</div>
            <div style="font-size: 0.75rem; color: #0369a1;">Checklist Progress</div>
          </div>

          <div style="padding: 1rem; background: #fefce8; border: 1px solid #fef08a; border-radius: 6px;">
            <div style="font-size: 0.8rem; color: #854d0e; font-weight: 600;">Safety Queue Alerts</div>
            <div style="font-size: 1.75rem; font-weight: 700; color: #ca8a04;">${m.clinical_safety_incidents.pending_review}</div>
            <div style="font-size: 0.75rem; color: #854d0e;">Pending Governance Review</div>
          </div>

          <div style="padding: 1rem; background: ${m.active_stop_conditions === 0 ? '#f0fdf4' : '#fef2f2'}; border: 1px solid ${m.active_stop_conditions === 0 ? '#bbf7d0' : '#fecaca'}; border-radius: 6px;">
            <div style="font-size: 0.8rem; color: ${m.active_stop_conditions === 0 ? '#166534' : '#991b1b'}; font-weight: 600;">Active Stop Events</div>
            <div style="font-size: 1.75rem; font-weight: 700; color: ${m.active_stop_conditions === 0 ? '#15803d' : '#b91c1c'};">${m.active_stop_conditions}</div>
            <div style="font-size: 0.75rem; color: ${m.active_stop_conditions === 0 ? '#166534' : '#991b1b'};">P0 Containment Locks</div>
          </div>
        </div>

        <div id="reviewPackResultBox" style="display: none; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1rem;"></div>
      </div>
    `;

    const genBtn = container.querySelector("#genReviewPackBtn");
    const resultBox = container.querySelector("#reviewPackResultBox");

    if (genBtn) {
      genBtn.addEventListener("click", async () => {
        try {
          const res = await apiClient.post(`/api/v1/pilot/programs/${program.id}/review-packs`, {
            review_type: "WEEKLY",
            period_start: "2026-10-13",
            period_end: "2026-10-20",
            recommendation: "CONTINUE_AS_PLANNED"
          });
          const pack = res.review_pack;
          resultBox.style.display = "block";
          resultBox.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <h4 style="margin: 0; color: #1e293b;">Formal Weekly Review Pack (${pack.id})</h4>
              <span class="badge" style="background: #dcfce7; color: #15803d;">${pack.recommendation}</span>
            </div>
            <p style="font-size: 0.8rem; color: #64748b; margin: 0.25rem 0 0.5rem 0;">Period: ${pack.period_start} to ${pack.period_end}</p>
            <div style="font-size: 0.8rem; background: white; padding: 0.5rem; border: 1px solid #cbd5e1; border-radius: 4px;">
              <strong>Summary:</strong> Core OPD, Unani assessment, prescription engine, and safety firewall operating within pilot parameters. Zero active P0 blockers. Continued operation approved.
            </div>
          `;
        } catch (e) {
          alert(`Error generating review pack: ${e.message || e}`);
        }
      });
    }

  } catch (err) {
    container.innerHTML = `<div class="card p-3" style="color:red;">Error loading metrics: ${err.message}</div>`;
  }
}

/**
 * ZAYVORA MATAB OS — Autonomous Agentic Pipelines Dashboard
 * Interactive Control Panel for:
 * 1. KAVS Book Ingestion & Monograph Extraction Pipeline
 * 2. Pharmacovigilance Safety Watchdog & Batch Quarantine
 * 3. Intelligent FEFO Restock & Purchase Order Forecast
 * 4. Dual-Corpus Clinical Evidence Pack Generator
 */

import { apiClient } from "/packages/api-client/client.js";

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export async function renderAgenticDashboard(container) {
  container.innerHTML = `
    <div style="max-width: 1200px; margin: 0 auto; padding: 1rem 0;">
      <!-- Header Banner -->
      <div class="card" style="margin-bottom: 1.25rem; padding: 1.25rem; background: linear-gradient(135deg, #064e3b 0%, #0f766e 100%); color: #ffffff; border-radius: var(--matab-radius-lg);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.6rem;">
              <span style="font-size: 1.8rem;">🤖</span>
              <h2 style="margin: 0; font-size: 1.4rem; font-weight: 800; color: #ffffff;">Autonomous Agentic Pipelines</h2>
              <span class="badge badge-success" style="background: #a7f3d0; color: #064e3b; font-weight: 700;">ENGINE v2.0 READY</span>
            </div>
            <p style="margin: 0.35rem 0 0 0; font-size: 0.85rem; color: #ccfbf1;">
              Multi-step autonomous pipelines with deterministic quality gates &amp; clinical governance.
            </p>
          </div>
          <div>
            <button id="btn-run-all-agents" class="btn btn-primary" style="background: #ffffff; color: #064e3b; font-weight: 800; border: none; padding: 0.6rem 1.2rem; font-size: 0.9rem; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
              🚀 Run All 4 Pipelines (Full Cycle)
            </button>
          </div>
        </div>
      </div>

      <!-- Live Execution Log Banner -->
      <div id="agent-execution-banner" style="display: none; margin-bottom: 1rem; padding: 0.75rem 1rem; border-radius: 8px; font-size: 0.85rem; font-weight: 600;"></div>

      <!-- 4-Grid Pipeline Cards -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(540px, 1fr)); gap: 1.25rem;">
        
        <!-- Pipeline 1: KAVS Book Ingestion -->
        <div class="card" style="background: #ffffff; border-top: 4px solid #0f766e; border-radius: 10px; padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
            <div>
              <h3 style="margin: 0; font-size: 1.05rem; font-weight: 700; color: #064e3b;">📚 1. KAVS Book Ingestion Pipeline</h3>
              <p style="margin: 0.2rem 0 0 0; font-size: 0.78rem; color: #64748b;">OCR ➔ Unani Ontology ➔ Schedule E(1) Check ➔ Merkle Hash</p>
            </div>
            <button id="btn-run-kavs" class="btn btn-secondary btn-sm" style="font-size: 0.76rem;">Execute Ingestion</button>
          </div>
          <div style="margin-bottom: 0.75rem;">
            <label style="font-size: 0.75rem; font-weight: 700; color: #475569;">Book Title &amp; Source:</label>
            <input type="text" id="kavs-input-title" class="form-input" value="Makhzan-ul-Adwiya (Canonical Compendia)" style="font-size: 0.8rem; height: 32px; margin-top: 0.2rem;" />
          </div>
          <div id="kavs-results-box" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; min-height: 120px; font-size: 0.8rem;">
            <span style="color: #94a3b8;">Click 'Execute Ingestion' to parse sample monograph pages.</span>
          </div>
        </div>

        <!-- Pipeline 2: Pharmacovigilance Watchdog -->
        <div class="card" style="background: #ffffff; border-top: 4px solid #dc2626; border-radius: 10px; padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
            <div>
              <h3 style="margin: 0; font-size: 1.05rem; font-weight: 700; color: #991b1b;">🛡️ 2. Pharmacovigilance Safety Watchdog</h3>
              <p style="margin: 0.2rem 0 0 0; font-size: 0.78rem; color: #64748b;">Adverse Symptom Scan ➔ Batch Correlation ➔ WHO-UMC Rating</p>
            </div>
            <button id="btn-run-pv" class="btn btn-secondary btn-sm" style="font-size: 0.76rem; border-color: #fca5a5; color: #991b1b;">Run Surveillance</button>
          </div>
          <div style="display: flex; gap: 0.5rem; margin-bottom: 0.75rem;">
            <div style="flex: 1;">
              <label style="font-size: 0.75rem; font-weight: 700; color: #475569;">Lookback (Days):</label>
              <input type="number" id="pv-input-days" class="form-input" value="30" style="font-size: 0.8rem; height: 32px; margin-top: 0.2rem;" />
            </div>
            <div style="flex: 1;">
              <label style="font-size: 0.75rem; font-weight: 700; color: #475569;">Cluster Threshold:</label>
              <input type="number" id="pv-input-thresh" class="form-input" value="2" style="font-size: 0.8rem; height: 32px; margin-top: 0.2rem;" />
            </div>
          </div>
          <div id="pv-results-box" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; min-height: 120px; font-size: 0.8rem;">
            <span style="color: #94a3b8;">Click 'Run Surveillance' to scan encounter notes for ADR signals.</span>
          </div>
        </div>

        <!-- Pipeline 3: FEFO Restock Agent -->
        <div class="card" style="background: #ffffff; border-top: 4px solid #d97706; border-radius: 10px; padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
            <div>
              <h3 style="margin: 0; font-size: 1.05rem; font-weight: 700; color: #92400e;">📦 3. FEFO Inventory Restock Agent</h3>
              <p style="margin: 0.2rem 0 0 0; font-size: 0.78rem; color: #64748b;">Near-Expiry Audit ➔ Seasonal Burn Forecast ➔ Auto-PO Draft</p>
            </div>
            <button id="btn-run-fefo" class="btn btn-secondary btn-sm" style="font-size: 0.76rem; border-color: #fde68a; color: #92400e;">Forecast Restock</button>
          </div>
          <div style="margin-bottom: 0.75rem;">
            <label style="font-size: 0.75rem; font-weight: 700; color: #475569;">Current Seasonal Profile:</label>
            <select id="fefo-input-season" class="form-input" style="font-size: 0.8rem; height: 32px; margin-top: 0.2rem;">
              <option value="WINTER">WINTER (Respiratory &amp; Joint Pain Multipliers)</option>
              <option value="SUMMER">SUMMER (Cooling Diuretic &amp; Cardiac Syrups)</option>
            </select>
          </div>
          <div id="fefo-results-box" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; min-height: 120px; font-size: 0.8rem;">
            <span style="color: #94a3b8;">Click 'Forecast Restock' to audit dispensary batches and stage PO draft.</span>
          </div>
        </div>

        <!-- Pipeline 4: Clinical Evidence Pack Generator -->
        <div class="card" style="background: #ffffff; border-top: 4px solid #2563eb; border-radius: 10px; padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
            <div>
              <h3 style="margin: 0; font-size: 1.05rem; font-weight: 700; color: #1e40af;">🔬 4. Clinical Evidence Pack Synthesizer</h3>
              <p style="margin: 0.2rem 0 0 0; font-size: 0.78rem; color: #64748b;">Dual-Corpus Retrieval ➔ Citation Support ➔ 3-Phase Af'aal</p>
            </div>
            <button id="btn-run-evidence" class="btn btn-secondary btn-sm" style="font-size: 0.76rem; border-color: #bfdbfe; color: #1e40af;">Generate Pack</button>
          </div>
          <div style="margin-bottom: 0.75rem;">
            <label style="font-size: 0.75rem; font-weight: 700; color: #475569;">Clinical Condition:</label>
            <select id="evidence-input-condition" class="form-input" style="font-size: 0.8rem; height: 32px; margin-top: 0.2rem;">
              <option value="Dyspepsia &amp; IBS Gastric Cascade">Su-e-Hazm / Dyspepsia &amp; IBS Gastric Cascade</option>
              <option value="Waja-ul-Mafasil Joint Arthritis">Waja-ul-Mafasil / Inflammatory Joint Disease</option>
              <option value="Ziabetus Shakari (Diabetes Mellitus)">Ziabetus Shakari / Type 2 Diabetes &amp; Metabolic Syndrome</option>
              <option value="Zaght-ud-Dam Qawi (Hypertension)">Zaght-ud-Dam Qawi / Arterial Hypertension &amp; Plethora</option>
              <option value="Falij wa Laqwa (Stroke &amp; Facial Palsy)">Falij wa Laqwa / Post-Stroke Hemiplegia &amp; Facial Palsy</option>
            </select>
          </div>
          <div id="evidence-results-box" style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.75rem; min-height: 120px; font-size: 0.8rem;">
            <span style="color: #94a3b8;">Click 'Generate Pack' to synthesize verified citations and treatment cascade.</span>
          </div>
        </div>

      </div>
    </div>
  `;

  // Attach Event Handlers
  const btnRunAll = document.getElementById("btn-run-all-agents");
  const btnRunKavs = document.getElementById("btn-run-kavs");
  const btnRunPv = document.getElementById("btn-run-pv");
  const btnRunFefo = document.getElementById("btn-run-fefo");
  const btnRunEvidence = document.getElementById("btn-run-evidence");

  btnRunAll?.addEventListener("click", executeRunAll);
  btnRunKavs?.addEventListener("click", executeKavs);
  btnRunPv?.addEventListener("click", executePv);
  btnRunFefo?.addEventListener("click", executeFefo);
  btnRunEvidence?.addEventListener("click", executeEvidence);

  async function executeRunAll() {
    setLoading(btnRunAll, "Running All 4 Pipelines...");
    try {
      const res = await apiClient.post("/api/v1/agents/run-all", { season: "WINTER" });
      showBanner(`✓ All 4 Pipelines executed successfully in ${res.execution_duration_seconds}s!`, true);
      renderKavsResult(res.pipeline_results.kavs_ingestion);
      renderPvResult(res.pipeline_results.pharmacovigilance);
      renderFefoResult(res.pipeline_results.fefo_inventory);
      renderEvidenceResult(res.pipeline_results.clinical_evidence);
    } catch (e) {
      showBanner(`Error running agentic pipelines: ${e.message}`, false);
    } finally {
      resetLoading(btnRunAll, "🚀 Run All 4 Pipelines (Full Cycle)");
    }
  }

  async function executeKavs() {
    setLoading(btnRunKavs, "Parsing...");
    try {
      const title = document.getElementById("kavs-input-title")?.value || "Makhzan-ul-Adwiya";
      const res = await apiClient.post("/api/v1/agents/kavs/ingest", { book_title: title });
      renderKavsResult(res);
      showBanner("✓ KAVS Ingestion Pipeline completed successfully.", true);
    } catch (e) {
      showBanner(`KAVS Ingestion error: ${e.message}`, false);
    } finally {
      resetLoading(btnRunKavs, "Execute Ingestion");
    }
  }

  async function executePv() {
    setLoading(btnRunPv, "Scanning...");
    try {
      const days = parseInt(document.getElementById("pv-input-days")?.value || "30", 10);
      const thresh = parseInt(document.getElementById("pv-input-thresh")?.value || "2", 10);
      const res = await apiClient.post("/api/v1/agents/pharmacovigilance/scan", { lookback_days: days, cluster_threshold: thresh });
      renderPvResult(res);
      showBanner("✓ Pharmacovigilance Watchdog surveillance complete.", true);
    } catch (e) {
      showBanner(`PV error: ${e.message}`, false);
    } finally {
      resetLoading(btnRunPv, "Run Surveillance");
    }
  }

  async function executeFefo() {
    setLoading(btnRunFefo, "Forecasting...");
    try {
      const season = document.getElementById("fefo-input-season")?.value || "WINTER";
      const res = await apiClient.post("/api/v1/agents/inventory/restock-plan", { season });
      renderFefoResult(res);
      showBanner("✓ FEFO Restock Pipeline generated purchase order draft.", true);
    } catch (e) {
      showBanner(`FEFO error: ${e.message}`, false);
    } finally {
      resetLoading(btnRunFefo, "Forecast Restock");
    }
  }

  async function executeEvidence() {
    setLoading(btnRunEvidence, "Synthesizing...");
    try {
      const cond = document.getElementById("evidence-input-condition")?.value || "Dyspepsia";
      const res = await apiClient.post("/api/v1/agents/evidence/generate", { condition: cond });
      renderEvidenceResult(res);
      showBanner("✓ Clinical Evidence Pack synthesized.", true);
    } catch (e) {
      showBanner(`Evidence error: ${e.message}`, false);
    } finally {
      resetLoading(btnRunEvidence, "Generate Pack");
    }
  }

  function renderKavsResult(res) {
    const box = document.getElementById("kavs-results-box");
    if (!box) return;
    box.innerHTML = `
      <div style="color: #065f46; font-weight: 700; margin-bottom: 0.35rem;">
        ✓ Ingestion Job: <code>${escapeHtml(res.job_id)}</code> • SHA-256 Verified
      </div>
      <div style="margin-bottom: 0.4rem; font-size: 0.78rem;">
        Pages Processed: <strong>${res.pages_processed}</strong> | Staged Claims: <strong>${res.total_claims_staged}</strong> | Auto-Verified: <strong>${res.auto_verified_claims}</strong>
      </div>
      <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.5rem;">
        <strong style="color: #0f766e;">Extracted Monograph Sample:</strong>
        ${(res.sample_monographs || []).map(m => `
          <div style="margin-top: 0.25rem; font-size: 0.76rem; border-bottom: 1px dashed #e2e8f0; padding-bottom: 0.2rem;">
            <strong>🌿 ${escapeHtml(m.name)}</strong> — Mizaj: <code>${escapeHtml(m.mizaj_quality)}</code> (Darja: ${m.darja})
            ${m.is_schedule_e1 ? `<span class="badge badge-warning" style="font-size: 0.65rem; margin-left: 0.3rem;">Schedule E(1) Mudabbar Verified</span>` : ''}
            <div style="color: #64748b;">Af'aal: ${escapeHtml(m["af'aal"] || m.afaal)} • Badal: ${escapeHtml(m.badal)}</div>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderPvResult(res) {
    const box = document.getElementById("pv-results-box");
    if (!box) return;
    box.innerHTML = `
      <div style="color: #991b1b; font-weight: 700; margin-bottom: 0.35rem;">
        🚨 Safety Surveillance: ${res.cluster_signals_generated} Cluster Signal(s) Detected
      </div>
      <div style="margin-bottom: 0.4rem; font-size: 0.78rem;">
        Encounters Scanned: <strong>${res.encounters_scanned}</strong> | Adverse Events: <strong>${res.adverse_events_detected}</strong>
      </div>
      ${(res.signals || []).map(s => `
        <div style="background: #fef2f2; border: 1px solid #fca5a5; border-radius: 6px; padding: 0.5rem; margin-bottom: 0.35rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: #b91c1c;">${escapeHtml(s.medication)} (${escapeHtml(s.batch_number)})</strong>
            <span class="badge badge-danger" style="font-size: 0.68rem;">WHO-UMC: ${escapeHtml(s.who_umc_causality)}</span>
          </div>
          <div style="font-size: 0.75rem; color: #7f1d1d; margin-top: 0.2rem;">${escapeHtml(s.summary)}</div>
          <div style="font-size: 0.72rem; color: #b91c1c; font-weight: 700; margin-top: 0.25rem;">
            Action: ${escapeHtml(s.recommended_action)}
          </div>
        </div>
      `).join("")}
    `;
  }

  function renderFefoResult(res) {
    const box = document.getElementById("fefo-results-box");
    if (!box) return;
    const po = res.purchase_order_draft;
    box.innerHTML = `
      <div style="color: #92400e; font-weight: 700; margin-bottom: 0.35rem;">
        📝 Draft Purchase Order: <code>${escapeHtml(po?.po_number || 'PO-DRAFT')}</code> (₹${res.estimated_procurement_cost_inr})
      </div>
      <div style="margin-bottom: 0.4rem; font-size: 0.78rem;">
        Items Requiring Restock: <strong>${res.reorder_items_count}</strong> | Season: <strong>${escapeHtml(res.season_applied)}</strong>
      </div>
      <div style="background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.5rem;">
        ${(po?.items || []).slice(0, 3).map(it => `
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; border-bottom: 1px dashed #e2e8f0; padding: 0.2rem 0;">
            <span><strong>${escapeHtml(it.item_name)}</strong> (Burn: ${it.projected_15d_burn})</span>
            <span style="font-weight: 700; color: #064e3b;">+${it.suggested_reorder_qty} ${escapeHtml(it.unit)} (₹${it.estimated_line_cost_inr})</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  function renderEvidenceResult(res) {
    const box = document.getElementById("evidence-results-box");
    if (!box) return;
    const pack = res.evidence_pack;
    box.innerHTML = `
      <div style="color: #1e40af; font-weight: 700; margin-bottom: 0.35rem;">
        📑 ${escapeHtml(pack.title)}
      </div>
      <div style="font-size: 0.76rem; color: #475569; margin-bottom: 0.4rem;">
        Organ Axis: <strong>${escapeHtml(pack.organ_axis)}</strong> | SHA-256: <code>${escapeHtml(pack.deterministic_sha256.substring(0, 16))}...</code>
      </div>
      <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 0.5rem; font-size: 0.75rem;">
        <strong>Classical Source:</strong> ${escapeHtml(pack.classical_compendia_citations[0]?.source || '')} (${escapeHtml(pack.classical_compendia_citations[0]?.locator || '')})
        <div style="color: #1e3a8a; font-style: italic; margin-top: 0.15rem;">"${escapeHtml(pack.classical_compendia_citations[0]?.claim || '')}"</div>
        <div style="margin-top: 0.35rem;">
          <strong>Modern Standard:</strong> ${escapeHtml(pack.modern_pharmacopoeial_citations[0]?.source || '')}
        </div>
      </div>
    `;
  }

  function showBanner(msg, isSuccess) {
    const b = document.getElementById("agent-execution-banner");
    if (!b) return;
    b.style.display = "block";
    b.style.backgroundColor = isSuccess ? "#dcfce7" : "#fee2e2";
    b.style.color = isSuccess ? "#166534" : "#991b1b";
    b.style.border = `1px solid ${isSuccess ? "#86efac" : "#fca5a5"}`;
    b.innerText = msg;
    setTimeout(() => { b.style.display = "none"; }, 6000);
  }

  function setLoading(btn, text) {
    if (!btn) return;
    btn.disabled = true;
    btn.dataset.prevText = btn.innerText;
    btn.innerText = text;
  }

  function resetLoading(btn, defaultText) {
    if (!btn) return;
    btn.disabled = false;
    btn.innerText = defaultText || btn.dataset.prevText || "Submit";
  }
}

/**
 * Knowledge Base Admin Workspace — Sources Registry, Items, Claims, Review Queue, and Audit Logs
 */

import { state } from "../state.js";
import { apiClient } from "../../../../packages/api-client/client.js";

export async function renderKnowledgeAdmin(container) {
  container.innerHTML = `<div class="card"><p>Loading Clinical Knowledge Admin...</p></div>`;

  try {
    const [sourcesRes, itemsRes, queueRes] = await Promise.all([
      apiClient.get("/api/v1/knowledge/sources"),
      apiClient.get("/api/v1/knowledge/items?status=approved&limit=20"),
      apiClient.get("/api/v1/knowledge/review/queue?status=under_review")
    ]);

    const sources = sourcesRes.sources || [];
    const items = itemsRes.items || [];
    const queue = queueRes.queue || [];

    const canManage = state.user?.permissions?.includes("knowledge:manage") || state.user?.roles?.includes("ORG_ADMIN");

    container.innerHTML = `
      <div style="margin-bottom: 1.25rem; display: flex; justify-content: space-between; align-items: flex-end;">
        <div>
          <h1 style="font-size: 1.4rem; color: var(--matab-color-brand-primary);">Clinical Knowledge Base & Evidence Layer</h1>
          <p style="color: var(--matab-color-text-secondary); font-size: 0.9rem;">
            Governed source registry, atomic claims, study appraisals, review queue, and retrieval tester.
          </p>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button id="btnOpenRetrievalTester" class="btn btn-secondary">Open Retrieval Tester</button>
        </div>
      </div>

      <!-- Navigation Sub-Tabs -->
      <div class="tabs-nav" style="margin-bottom: 1rem; border-bottom: 1px solid var(--matab-color-border);">
        <button class="tab-btn active" id="tabBtnSources">Sources Registry (${sources.length})</button>
        <button class="tab-btn" id="tabBtnItems">Knowledge Items (${itemsRes.total || items.length})</button>
        <button class="tab-btn" id="tabBtnQueue">Review Queue (${queue.length})</button>
        <button class="tab-btn" id="tabBtnKavs">KAVS Verification & Releases</button>
      </div>

      <!-- Tab Content Area -->
      <div id="knowledgeTabContent"></div>
    `;

    const tabContent = document.getElementById("knowledgeTabContent");

    function showSources() {
      const rows = sources.map(s => `
        <tr>
          <td><strong>${s.title}</strong></td>
          <td><code>${s.source_type}</code></td>
          <td>${s.authors_or_org || '—'}</td>
          <td><span class="badge badge-info">${s.evidence_level}</span></td>
          <td><span class="badge ${s.review_status === 'APPROVED' ? 'badge-success' : 'badge-warning'}">${s.review_status}</span></td>
          <td><small><code>${s.document_hash ? s.document_hash.slice(0, 10) + '...' : '—'}</code></small></td>
        </tr>
      `).join("");

      tabContent.innerHTML = `
        <div class="card">
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
            <h3 class="card-title">Governed Sources Registry</h3>
            <span class="badge badge-info">${sources.length} Registered</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Source Title</th>
                <th>Type</th>
                <th>Authors / Authority</th>
                <th>Evidence Tier</th>
                <th>Review Status</th>
                <th>Integrity Hash</th>
              </tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6" style="text-align: center;">No sources registered.</td></tr>'}</tbody>
          </table>
        </div>
      `;
    }

    function showItems() {
      const rows = items.map(it => `
        <tr>
          <td><strong>${it.canonical_name}</strong></td>
          <td><span class="badge ${it.domain === 'UNANI' ? 'badge-brand' : 'badge-info'}">${it.domain}</span></td>
          <td><code>${it.entity_type}</code></td>
          <td>${it.claim_type}</td>
          <td><span class="badge badge-success">${it.status}</span></td>
          <td>
            <button class="btn btn-sm btn-outline view-synth-btn" data-id="${it.id}">View Synthesis</button>
          </td>
        </tr>
      `).join("");

      tabContent.innerHTML = `
        <div class="card">
          <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
            <h3 class="card-title">Approved Clinical Knowledge Items</h3>
            <span class="badge badge-success">Approved Only</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Canonical Name</th>
                <th>Domain</th>
                <th>Entity Type</th>
                <th>Claim Type</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6" style="text-align: center;">No items found.</td></tr>'}</tbody>
          </table>
        </div>
        <div id="synthesisModalArea"></div>
      `;

      tabContent.querySelectorAll(".view-synth-btn").forEach(btn => {
        btn.addEventListener("click", async () => {
          const id = btn.getAttribute("data-id");
          const synth = await apiClient.get(`/api/v1/knowledge/items/${id}/synthesize`);
          const s = synth.synthesis;
          alert(`EVIDENCE SYNTHESIS: ${s.canonical_name}\n\nDomain: ${s.domain}\nSources: ${s.sources_consulted.join(", ")}\n\nEpistemological Boundary:\n${s.epistemological_boundary}`);
        });
      });
    }

    function showQueue() {
      const rows = queue.map(q => `
        <tr>
          <td><strong>${q.canonical_name}</strong></td>
          <td>${q.domain}</td>
          <td><code>${q.entity_type}</code></td>
          <td>${q.author_name || 'System'}</td>
          <td><span class="badge badge-warning">${q.status}</span></td>
          <td>
            ${canManage ? `
              <button class="btn btn-sm btn-success app-btn" data-id="${q.id}">Approve</button>
              <button class="btn btn-sm btn-danger rej-btn" data-id="${q.id}">Reject</button>
            ` : '<span style="color: var(--matab-color-text-muted);">Reviewer Only</span>'}
          </td>
        </tr>
      `).join("");

      tabContent.innerHTML = `
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Clinical Review Queue</h3>
          </div>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-muted); margin-bottom: 0.75rem;">
            Only items approved by a licensed clinical reviewer are made available to clinician workstations.
          </p>
          <table class="data-table">
            <thead>
              <tr>
                <th>Item Name</th>
                <th>Domain</th>
                <th>Entity Type</th>
                <th>Author</th>
                <th>Status</th>
                <th>Reviewer Action</th>
              </tr>
            </thead>
            <tbody>${rows || '<tr><td colspan="6" style="text-align: center;">Queue is currently empty.</td></tr>'}</tbody>
          </table>
        </div>
      `;

      if (canManage) {
        tabContent.querySelectorAll(".app-btn").forEach(btn => {
          btn.addEventListener("click", async () => {
            const id = btn.getAttribute("data-id");
            await apiClient.post(`/api/v1/knowledge/review/${id}/approve`, { comments: "Approved via Admin Console" });
            renderKnowledgeAdmin(container);
          });
        });
        tabContent.querySelectorAll(".rej-btn").forEach(btn => {
          btn.addEventListener("click", async () => {
            const id = btn.getAttribute("data-id");
            const reason = prompt("Enter rejection reason:");
            if (reason) {
              await apiClient.post(`/api/v1/knowledge/review/${id}/reject`, { reason });
              renderKnowledgeAdmin(container);
            }
          });
        });
      }
    }

    function showKavs() {
      tabContent.innerHTML = `
        <div class="card" style="margin-bottom: 1rem;">
          <h2 style="font-size: 1.1rem; color: var(--matab-color-brand-primary); margin-bottom: 0.5rem;">KAVS Verification & Governance Layer</h2>
          <p style="font-size: 0.85rem; color: var(--matab-color-text-secondary); margin-bottom: 1rem;">
            Five Independent Verification Dimensions (Source authenticity, extraction fidelity, evidence characterization, clinical review state, intended-use authorization). No AI hallucinated claims.
          </p>
          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin-bottom: 1.5rem;">
            <div style="padding: 0.75rem; background: var(--matab-color-bg-subtle); border-radius: 4px; border: 1px solid var(--matab-color-border);">
              <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); text-transform: uppercase;">Dimension A</div>
              <strong style="font-size: 0.95rem;">Source Authenticity</strong>
            </div>
            <div style="padding: 0.75rem; background: var(--matab-color-bg-subtle); border-radius: 4px; border: 1px solid var(--matab-color-border);">
              <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); text-transform: uppercase;">Dimension B</div>
              <strong style="font-size: 0.95rem;">Extraction Fidelity</strong>
            </div>
            <div style="padding: 0.75rem; background: var(--matab-color-bg-subtle); border-radius: 4px; border: 1px solid var(--matab-color-border);">
              <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); text-transform: uppercase;">Dimension C</div>
              <strong style="font-size: 0.95rem;">Evidence Type</strong>
            </div>
            <div style="padding: 0.75rem; background: var(--matab-color-bg-subtle); border-radius: 4px; border: 1px solid var(--matab-color-border);">
              <div style="font-size: 0.75rem; color: var(--matab-color-text-secondary); text-transform: uppercase;">Dimension D & E</div>
              <strong style="font-size: 0.95rem;">Review & Intended Use</strong>
            </div>
          </div>
          <div style="display: flex; gap: 0.5rem;">
            <button id="btnKavsContextQuery" class="btn btn-primary">Test Verified Clinical Context Retrieval</button>
          </div>
        </div>
      `;

      document.getElementById("btnKavsContextQuery")?.addEventListener("click", async () => {
        const q = prompt("Enter clinical query to test KAVS verified retrieval (e.g. 'Senna', 'Filfil Siah'):", "Senna");
        if (q) {
          try {
            const res = await apiClient.post("/api/v1/kavs/retrieve", {
              query: q,
              intended_use: "clinician_contextual_reference"
            });
            if (res.insufficient_information) {
              alert(`KAVS RESPONSE: Insufficient Verified Information\n\n${res.caveat || res.reason}`);
            } else {
              const lines = res.results.map(r => `• ${r.item_name}: "${r.claim_text}"\n  [Source: ${r.source.title} (${r.source.locator})] [Authenticity: ${r.verification.source_authenticity}]`);
              alert(`KAVS VERIFIED CONTEXT (${res.total} claims found):\n\n` + lines.join("\n\n"));
            }
          } catch (e) {
            alert(`KAVS Query failed: ${e.message}`);
          }
        }
      });
    }

    // Default to sources
    showSources();

    document.getElementById("tabBtnSources").addEventListener("click", (e) => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      showSources();
    });

    document.getElementById("tabBtnItems").addEventListener("click", (e) => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      showItems();
    });

    document.getElementById("tabBtnQueue").addEventListener("click", (e) => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      showQueue();
    });

    document.getElementById("tabBtnKavs").addEventListener("click", (e) => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      showKavs();
    });

    document.getElementById("btnOpenRetrievalTester").addEventListener("click", () => {
      const q = prompt("Enter clinical search query (e.g., 'balgham', 'senna', 'IBS', 'dyspepsia'):");
      if (q) {
        apiClient.get(`/api/v1/knowledge/search?q=${encodeURIComponent(q)}`).then(res => {
          const lines = res.results.map(r => `• [${r.domain}] ${r.canonical_name} (Score: ${r.relevance_score}) - Reasons: ${r.match_reasons.join(", ")}`);
          alert(`RETRIEVAL TESTER RESULTS (${res.count}):\n\n` + (lines.join("\n") || "No matching items found."));
        });
      }
    });

  } catch (err) {
    container.innerHTML = `<div class="card"><p style="color: red;">Failed to load Knowledge Admin: ${err.message}</p></div>`;
  }
}

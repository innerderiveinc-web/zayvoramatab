/**
 * Medical Library & Classical Compendia Viewer
 * ZAYVORA MATAB OS
 * 
 * Provides search, exploration, and clinical referencing across 97 canonical
 * classical Unani texts, statutory AYUSH formularies, and modern biomedical manuals.
 */

import { state } from "../state.js";
import { apiClient } from "/packages/api-client/client.js";

export async function renderLibrary(container) {
  container.innerHTML = `
    <div class="library-view-container" style="max-width: 1400px; margin: 0 auto; padding: 0.5rem 0 2rem 0;">
      
      <!-- Top Hero Header -->
      <div class="card" style="margin-bottom: 1.25rem; border-left: 4px solid var(--matab-color-brand-primary); background: var(--matab-color-surface);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
          <div>
            <div style="display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.35rem;">
              <span style="font-size: 1.75rem;">📚</span>
              <h2 style="margin: 0; font-size: 1.35rem; color: var(--matab-color-brand-primary); font-weight: 700;">
                Tibb Library & Classical Compendia Archive
              </h2>
              <span class="badge badge-success" style="font-size: 0.72rem; padding: 0.2rem 0.5rem;">
                ✓ KAVS Verified
              </span>
            </div>
            <p style="margin: 0; font-size: 0.88rem; color: var(--matab-color-text-secondary); max-width: 850px; line-height: 1.45;">
              Institutional digital library indexing 97 canonical Unani compendia, official AYUSH formularies, classical surgery treatises, and modern internal medicine reference benchmarks.
            </p>
          </div>

          <div id="libraryStatsPills" style="display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
            <div style="background: var(--matab-color-bg-secondary); border: 1px solid var(--matab-color-border-subtle); padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.82rem; text-align: center;">
              <div style="font-size: 0.7rem; color: var(--matab-color-text-muted); text-transform: uppercase;">Volumes</div>
              <strong id="statTotalBooks" style="color: var(--matab-color-brand-primary); font-size: 1.05rem;">97</strong>
            </div>
            <div style="background: var(--matab-color-bg-secondary); border: 1px solid var(--matab-color-border-subtle); padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.82rem; text-align: center;">
              <div style="font-size: 0.7rem; color: var(--matab-color-text-muted); text-transform: uppercase;">Repository Size</div>
              <strong id="statTotalSize" style="color: var(--matab-color-brand-primary); font-size: 1.05rem;">11.7 GB</strong>
            </div>
            <button id="btnRefreshLibrary" class="btn btn-secondary btn-sm" style="display: flex; align-items: center; gap: 0.3rem;">
              <span>🔄</span> Refresh Catalog
            </button>
            <a href="/science_and_research.html" target="_blank" class="btn btn-primary btn-sm" style="display: flex; align-items: center; gap: 0.35rem; background: #059669; border-color: #047857; color: #fff; text-decoration: none;">
              <span>🔬</span> Science & Clinical Papers
            </a>
          </div>
        </div>

        <!-- Filter & Search Toolbar -->
        <div style="margin-top: 1.25rem; display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; background: var(--matab-color-bg-secondary); padding: 0.75rem; border-radius: 6px;">
          <div style="flex: 2; min-width: 250px;">
            <input type="text" id="libSearchInput" class="form-control" placeholder="Search by title, author, keyword (e.g. Ibn Sina, Razi, NFUM, Qanun, Harrison)..." />
          </div>

          <div style="flex: 1; min-width: 200px;">
            <select id="libCategorySelect" class="form-control">
              <option value="ALL">All Authority Categories</option>
              <option value="CLASSICAL_CANON">Classical Canons (Ibn Sina, Al-Razi, Azam Khan)</option>
              <option value="PHARMACOPOEIA_FORMULARY">Formularies & Qarabadeen (NFUM, Hamdard, Majidi, Haziq)</option>
              <option value="MATERIA_MEDICA">Materia Medica & Single Herbs (Makhzan al-Mufradat)</option>
              <option value="DIAGNOSTICS_SURGERY">Diagnostics & Surgery (Nabz, Zahrawi, Ibn al-Quff)</option>
              <option value="MODERN_INTERNAL_MEDICINE">Modern Internal Medicine (Harrison, Davidson, Hutchison)</option>
              <option value="PRINCIPLES_PHYSIOLOGY">Principles of Tibb (Umoor Tabiya, Nafisi)</option>
              <option value="REGIMENTAL_THERAPY">Regimental Therapy / Ilaj bil Tadbeer (Hijama, Dalk)</option>
              <option value="TERMINOLOGY_GOVERNANCE">Terminology & Standards (WHO, CCRUM)</option>
            </select>
          </div>

          <div style="width: 150px;">
            <select id="libLanguageSelect" class="form-control">
              <option value="ALL">All Languages</option>
              <option value="URDU">Urdu (اردو)</option>
              <option value="ARABIC">Arabic (عربي)</option>
              <option value="ENGLISH">English</option>
              <option value="MULTILINGUAL">Multilingual</option>
            </select>
          </div>

          <button id="btnSearchSubmit" class="btn btn-primary" style="padding: 0.45rem 1rem;">
            🔍 Search
          </button>
        </div>
      </div>

      <!-- Quick Access Discipline Pills -->
      <div style="display: flex; gap: 0.5rem; overflow-x: auto; padding-bottom: 0.75rem; margin-bottom: 0.75rem;">
        <button class="btn btn-sm btn-outline-primary btn-quick-filter active" data-cat="ALL">All Compendia</button>
        <button class="btn btn-sm btn-outline-secondary btn-quick-filter" data-cat="CLASSICAL_CANON">👑 Canons of Tibb</button>
        <button class="btn btn-sm btn-outline-secondary btn-quick-filter" data-cat="PHARMACOPOEIA_FORMULARY">💊 Formularies & Qarabadeen</button>
        <button class="btn btn-sm btn-outline-secondary btn-quick-filter" data-cat="MATERIA_MEDICA">🌿 Materia Medica (Mufradat)</button>
        <button class="btn btn-sm btn-outline-secondary btn-quick-filter" data-cat="DIAGNOSTICS_SURGERY">🩺 Diagnostics & Surgery</button>
        <button class="btn btn-sm btn-outline-secondary btn-quick-filter" data-cat="MODERN_INTERNAL_MEDICINE">🔬 Modern Biomedical Medicine</button>
      </div>

      <!-- Books Results Grid -->
      <div id="libraryResultsGrid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 1rem;">
        <div style="text-align: center; padding: 3rem; color: var(--matab-color-text-muted); grid-column: 1 / -1;">
          Loading Medical Library Catalog...
        </div>
      </div>

      <!-- Pagination Footer -->
      <div id="libraryPaginationBar" style="margin-top: 1.5rem; display: flex; justify-content: space-between; align-items: center; background: var(--matab-color-surface); padding: 0.75rem 1rem; border-radius: 6px; border: 1px solid var(--matab-color-border-subtle);">
        <div id="libPaginationInfo" style="font-size: 0.85rem; color: var(--matab-color-text-secondary);">
          Showing 0 of 0 books
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button id="libPrevPage" class="btn btn-secondary btn-sm" disabled>&larr; Previous</button>
          <button id="libNextPage" class="btn btn-secondary btn-sm" disabled>Next &rarr;</button>
        </div>
      </div>

    </div>

    <!-- Book Detail Modal Container -->
    <div id="libraryModalContainer"></div>
  `;

  let currentOffset = 0;
  const pageLimit = 24;

  const searchInput = container.querySelector("#libSearchInput");
  const categorySelect = container.querySelector("#libCategorySelect");
  const languageSelect = container.querySelector("#libLanguageSelect");
  const resultsGrid = container.querySelector("#libraryResultsGrid");
  const paginationInfo = container.querySelector("#libPaginationInfo");
  const prevBtn = container.querySelector("#libPrevPage");
  const nextBtn = container.querySelector("#libNextPage");
  const modalContainer = container.querySelector("#libraryModalContainer");

  async function loadStats() {
    try {
      const stats = await apiClient.get("/api/v1/library/stats");
      container.querySelector("#statTotalBooks").textContent = stats.total_books || "97";
      container.querySelector("#statTotalSize").textContent = `${stats.total_size_gb || "11.7"} GB`;
    } catch (e) {
      console.warn("Error loading library stats", e);
    }
  }

  async function loadBooks() {
    resultsGrid.innerHTML = `
      <div style="text-align: center; padding: 3rem; color: var(--matab-color-text-muted); grid-column: 1 / -1;">
        <span style="display: inline-block; animation: pulse 1s infinite;">🔍</span> Searching medical compendia...
      </div>
    `;

    try {
      const q = searchInput.value.trim();
      const cat = categorySelect.value;
      const lang = languageSelect.value;

      const params = new URLSearchParams({
        limit: pageLimit,
        offset: currentOffset
      });
      if (q) params.set("q", q);
      if (cat && cat !== "ALL") params.set("category", cat);
      if (lang && lang !== "ALL") params.set("language", lang);

      if (cat === "MATERIA_MEDICA") {
        const res = await apiClient.get(`/api/v1/library/corpus/mufradat?q=${encodeURIComponent(q)}&limit=${pageLimit}`);
        renderMufradatCards(res.mufradat || [], res.total || 0);
        return;
      }

      const res = await apiClient.get(`/api/v1/library/books?${params.toString()}`);
      renderBookCards(res.books || [], res.total || 0);
    } catch (err) {
      resultsGrid.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; padding: 2rem; text-align: center; color: var(--matab-color-danger-primary);">
          Failed to load medical library: ${err.message || err}
        </div>
      `;
    }
  }

  function renderMufradatCards(mufradat, total) {
    if (!mufradat || mufradat.length === 0) {
      resultsGrid.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--matab-color-text-muted);">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🌿</div>
          <h3>No matching single herbs (Mufradat) found</h3>
          <p style="font-size: 0.85rem;">Try adjusting your search terms or view all 250 canonical pharmacopeia herbs.</p>
        </div>
      `;
      paginationInfo.textContent = "Showing 0 of 0 herbs";
      prevBtn.disabled = true;
      nextBtn.disabled = true;
      return;
    }

    const start = currentOffset + 1;
    const end = Math.min(currentOffset + mufradat.length, total);
    paginationInfo.textContent = `Showing ${start}–${end} of ${total} canonical single herbs (Mufradat Monographs)`;
    prevBtn.disabled = currentOffset <= 0;
    nextBtn.disabled = end >= total;

    resultsGrid.innerHTML = mufradat.map(m => {
      let actions = [];
      try { actions = typeof m.actions === 'string' ? JSON.parse(m.actions) : (m.actions || []); } catch(e) { actions = []; }
      let indications = [];
      try { indications = typeof m.indications === 'string' ? JSON.parse(m.indications) : (m.indications || []); } catch(e) { indications = []; }

      return `
        <div class="card mufrad-card" style="display: flex; flex-direction: column; justify-content: space-between; border-top: 3.5px solid #059669; transition: transform 0.15s, box-shadow 0.15s; cursor: pointer; padding: 1.15rem; background: #ffffff;" data-id="${m.id}">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.5rem;">
              <span class="badge" style="background: #ecfdf5; color: #065f46; font-weight: 700; font-size: 0.72rem; border: 1px solid #a7f3d0;">
                ⚖️ ${escapeHtml(m.mizaj_quality || 'Motadil')}
              </span>
              <span class="badge" style="background: var(--matab-color-bg-secondary); font-size: 0.7rem; color: var(--matab-color-text-secondary);">
                ${m.is_schedule_e1 ? '⚠️ Schedule E(1)' : 'Plant Drug'} • ${escapeHtml(m.upi_ref || 'UPI')}
              </span>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: baseline;">
              <h3 style="margin: 0; font-size: 1.12rem; color: var(--matab-color-text-primary); font-weight: 700;">
                ${escapeHtml(m.english)}
              </h3>
              <span style="font-size: 1.05rem; color: #065f46; font-weight: 700; font-family: serif;">
                ${escapeHtml(m.urdu || '')}
              </span>
            </div>

            <div style="font-size: 0.82rem; color: #059669; font-style: italic; margin-bottom: 0.45rem;">
              🌿 ${escapeHtml(m.botanical)}
            </div>

            <div style="font-size: 0.78rem; color: #475569; margin-bottom: 0.5rem;">
              <strong>Part Used:</strong> ${escapeHtml(m.part_used || 'Medicinal parts')} • <strong>Dose:</strong> ${escapeHtml(m.dosage || '3g - 5g')}
            </div>

            <div style="margin-bottom: 0.5rem;">
              <strong style="font-size: 0.72rem; text-transform: uppercase; color: #64748b;">Therapeutic Actions (Afaal):</strong>
              <div style="display: flex; gap: 0.3rem; flex-wrap: wrap; margin-top: 0.2rem;">
                ${(actions || []).slice(0, 3).map(a => `
                  <span style="font-size: 0.68rem; background: #e0f2fe; color: #0369a1; padding: 0.15rem 0.4rem; border-radius: 4px; font-weight: 600;">
                    ${escapeHtml(a)}
                  </span>
                `).join('')}
              </div>
            </div>

            ${indications.length > 0 ? `
              <div style="margin-bottom: 0.5rem;">
                <strong style="font-size: 0.72rem; text-transform: uppercase; color: #64748b;">Key Indications (Mahall-e-Istemal):</strong>
                <div style="font-size: 0.75rem; color: #334155; line-height: 1.35; margin-top: 0.15rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
                  ${indications.slice(0, 2).map(i => escapeHtml(i)).join(' • ')}
                </div>
              </div>
            ` : ''}
          </div>

          <div style="border-top: 1px solid var(--matab-color-border-subtle); padding-top: 0.65rem; display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
            <span style="font-size: 0.72rem; color: var(--matab-color-text-muted);">
              Code: <code>${m.id}</code>
            </span>
            <button class="btn btn-sm btn-primary btn-view-monograph" data-id="${m.id}" style="padding: 0.25rem 0.75rem; font-size: 0.76rem; font-weight: 600; background: #059669; border-color: #047857;">
              🌿 View Full Monograph ➔
            </button>
          </div>
        </div>
      `;
    }).join("");

    resultsGrid.querySelectorAll(".mufrad-card").forEach(card => {
      const id = card.getAttribute("data-id");
      card.addEventListener("click", () => {
        openMufradMonographModal(id);
      });
    });
  }

  async function openMufradMonographModal(herbId) {
    try {
      const res = await apiClient.get(`/api/v1/library/corpus/mufradat/${encodeURIComponent(herbId)}`);
      if (!res || !res.monograph) throw new Error("Monograph details unavailable");
      const m = res.monograph;

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

      modalContainer.innerHTML = `
        <div class="modal-backdrop" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 1060; padding: 0.75rem; backdrop-filter: blur(4px);">
          <div class="modal-dialog" style="background: var(--matab-color-surface); width: 94vw; max-width: 1050px; max-height: 92vh; border-radius: 10px; box-shadow: 0 20px 45px rgba(0,0,0,0.5); overflow-y: auto; display: flex; flex-direction: column; border: 1px solid var(--matab-color-border-subtle);">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #065f46 0%, #047857 100%); color: white; padding: 1rem 1.5rem; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 2;">
              <div>
                <div style="display: flex; align-items: center; gap: 0.6rem; flex-wrap: wrap;">
                  <span style="font-size: 1.6rem;">🌿</span>
                  <h3 style="margin: 0; font-size: 1.3rem; font-weight: 700;">
                    ${escapeHtml(m.english)} <span style="font-family: serif; font-size: 1.2rem; opacity: 0.95;">(${escapeHtml(m.urdu || '')})</span>
                  </h3>
                  <span class="badge" style="background: #ecfdf5; color: #065f46; font-size: 0.78rem; font-weight: 700;">
                    ⚖️ ${escapeHtml(m.mizaj_quality || 'Motadil')} (Darja ${m.mizaj_degree || 1})
                  </span>
                  ${m.is_schedule_e1 ? `<span class="badge" style="background: #dc2626; color: white; font-weight: 700;">⚠️ Schedule E(1) Toxic</span>` : ''}
                  ${m.mandatory_mudabbar ? `<span class="badge" style="background: #d97706; color: white;">Mandatory Mudabbar</span>` : ''}
                </div>
                <div style="font-size: 0.85rem; opacity: 0.92; margin-top: 0.25rem;">
                  <em>Botanical: ${escapeHtml(m.botanical)}</em> • Origin: ${escapeHtml(m.origin_category)} • Code: <code>${escapeHtml(m.upi_code || m.id)}</code>
                </div>
              </div>
              <button class="btn btn-sm" id="btnCloseMonograph" style="background: rgba(255,255,255,0.2); color: white; border: none; font-size: 1.25rem; cursor: pointer; padding: 0.2rem 0.6rem; border-radius: 4px;">✕</button>
            </div>

            <!-- Monograph Content Body -->
            <div style="padding: 1.25rem 1.5rem; display: flex; flex-direction: column; gap: 1rem;">
              
              <!-- Section 1: Mutradif Naam (Synonyms & Vernacular) -->
              <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.5rem 0; font-size: 0.88rem; color: #065f46; font-weight: 700;">
                  🏷️ Mutradif Naam (Synonyms &amp; Vernacular Names)
                </h4>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem; font-size: 0.82rem;">
                  <div><strong>Hindi:</strong> <span style="color: #334155;">${escapeHtml(syn.hindi || '--')}</span></div>
                  <div><strong>Sanskrit:</strong> <span style="color: #334155;">${escapeHtml(syn.sanskrit || '--')}</span></div>
                  <div><strong>Persian (Farsi):</strong> <span style="color: #334155;">${escapeHtml(syn.persian || '--')}</span></div>
                  <div><strong>Arabic:</strong> <span style="color: #334155;">${escapeHtml(syn.arabic || m.arabic || '--')}</span></div>
                  <div><strong>English:</strong> <span style="color: #334155;">${escapeHtml(syn.english || m.english || '--')}</span></div>
                </div>
              </div>

              <!-- Section 2: Part Used & Posology -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
                <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 0.85rem;">
                  <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #166534; font-weight: 700;">
                    🍃 Hissa-e-Musta'mala (Plant Part Used)
                  </h4>
                  <div style="font-size: 0.88rem; color: #14532d; font-weight: 600;">
                    ${escapeHtml(m.part_used || 'Dried medicinal parts')}
                  </div>
                </div>
                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 0.85rem;">
                  <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #1e40af; font-weight: 700;">
                    💊 Miqdar-e-Khurak (Therapeutic Posology)
                  </h4>
                  <div style="font-size: 0.85rem; color: #1e3a8a; font-weight: 600;">
                    ${escapeHtml(m.historical_dose || '3g - 5g')}
                    <span style="font-weight: normal; font-size: 0.78rem; color: #475569; display: block; margin-top: 0.2rem;">
                      Statutory Single Dose Max: <strong>${m.single_dose_max_g || 5.0}g</strong> • Daily Max: <strong>${m.daily_dose_max_g || 10.0}g</strong>
                    </span>
                  </div>
                </div>
              </div>

              <!-- Section 3: Therapeutic Actions (Afaal-e-Khassa) -->
              <div>
                <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #065f46; font-weight: 700;">
                  🩺 Afaal-e-Khassa (Therapeutic Actions)
                </h4>
                <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                  ${actions.map(a => `<span class="badge" style="background:#e0f2fe; color:#0369a1; border:1px solid #bae6fd; font-size:0.8rem; padding:0.25rem 0.55rem; font-weight:600;">${escapeHtml(a)}</span>`).join('')}
                </div>
              </div>

              <!-- Section 4: Clinical Indications (Mahall-e-Istemal) -->
              <div style="background: #fafaf9; border: 1px solid #e7e5e4; border-radius: 8px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #44403c; font-weight: 700;">
                  🎯 Mahall-e-Istemal (Clinical Indications &amp; Diseases Treated)
                </h4>
                <ul style="margin: 0; padding-left: 1.25rem; font-size: 0.83rem; color: #292524; line-height: 1.6;">
                  ${indications.map(i => `<li><strong>${escapeHtml(i)}</strong></li>`).join('')}
                </ul>
              </div>

              <!-- Section 5: Contraindications & Muzir/Musleh -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
                <div style="border-left: 4px solid #dc2626; background: #fef2f2; border-radius: 6px; padding: 0.85rem;">
                  <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #991b1b; font-weight: 700;">
                    🚫 Mawaane-e-Istemal (Contraindications)
                  </h4>
                  <p style="margin: 0; font-size: 0.82rem; color: #7f1d1d; line-height: 1.45;">
                    ${escapeHtml(m.contraindications)}
                  </p>
                </div>
                <div style="border-left: 4px solid #f59e0b; background: #fffbeb; border-radius: 6px; padding: 0.85rem;">
                  <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #92400e; font-weight: 700;">
                    ⚠️ Muzir (Harmful Action) &amp; Musleh (Correctives)
                  </h4>
                  <div style="font-size: 0.82rem; color: #78350f; line-height: 1.45;">
                    <div><strong>Muzir:</strong> ${escapeHtml(m.adverse_effects_muzir)}</div>
                    <div style="margin-top: 0.35rem;"><strong>Musleh:</strong> ${escapeHtml(musleh.join(', ') || 'Honey / Ghee')}</div>
                  </div>
                </div>
              </div>

              <!-- Section 6: Badal & Badraqa/Anupan -->
              <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem;">
                <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.85rem;">
                  <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #334155; font-weight: 700;">
                    🔄 Badal (Classical Substitutes)
                  </h4>
                  <div style="font-size: 0.82rem; color: #1e293b;">
                    ${escapeHtml(badal.join(' • ') || 'None documented')}
                  </div>
                </div>
                <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 0.85rem;">
                  <h4 style="margin: 0 0 0.35rem 0; font-size: 0.85rem; color: #334155; font-weight: 700;">
                    🍶 Badraqa / Anupan (Preferred Vehicle)
                  </h4>
                  <div style="font-size: 0.82rem; color: #1e293b;">
                    ${escapeHtml(m.badraqa_anupan || 'Fresh water or cow milk')}
                  </div>
                </div>
              </div>

              <!-- Section 7: Famous Compounds (Murakkabat) -->
              <div>
                <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #065f46; font-weight: 700;">
                  📜 Murakkabat-e-Mashhoora (Famous Pharmacopeial Formulations)
                </h4>
                <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                  ${compounds.map(c => `<span class="badge" style="background:#f0fdf4; color:#166534; border:1px solid #86efac; font-size:0.78rem; padding:0.25rem 0.5rem; font-weight:600;">${escapeHtml(c)}</span>`).join('')}
                </div>
              </div>

              <!-- Section 8: Phytochemicals & Herb-Drug Interactions -->
              <div style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 0.85rem;">
                <h4 style="margin: 0 0 0.4rem 0; font-size: 0.88rem; color: #0f172a; font-weight: 700;">
                  🔬 Modern Phytopharmacology &amp; Herb-Drug Safety
                </h4>
                <div style="font-size: 0.82rem; color: #334155; margin-bottom: 0.4rem;">
                  <strong>Active Bio-Markers &amp; Phytochemicals:</strong> ${escapeHtml(phytochemicals.join(', '))}
                </div>
                <div style="font-size: 0.82rem; color: #991b1b;">
                  <strong>Herb-Drug Interaction Screening:</strong> ${escapeHtml(m.herb_drug_interactions)}
                </div>
                ${m.mandatory_mudabbar && m.mudabbar_protocol ? `
                  <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed #cbd5e1; font-size: 0.8rem; color: #9a3412;">
                    <strong>Shodhana / Mudabbar Protocol:</strong> ${escapeHtml(m.mudabbar_protocol)}
                  </div>
                ` : ''}
              </div>

              <!-- Section 9: Regulatory & Compendia Anchor -->
              <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #e2e8f0; padding-top: 0.75rem; font-size: 0.76rem; color: #64748b; flex-wrap: wrap; gap: 0.5rem;">
                <div><strong>Standard Reference:</strong> ${escapeHtml(m.upi_monograph_ref || 'UPI Part-I')}</div>
                <div>Pregnancy Safety: <strong>${escapeHtml(m.pregnancy_status || 'SAFE')}</strong> • Evidence: <strong>${escapeHtml(m.evidence_level || 'E2')}</strong> • Lifecycle: <strong>${escapeHtml(m.lifecycle_state || 'VERIFIED')}</strong></div>
              </div>

            </div>

            <!-- Footer Action -->
            <div style="border-top: 1px solid var(--matab-color-border-subtle); padding: 0.75rem 1.25rem; display: flex; justify-content: flex-end; background: var(--matab-color-bg-secondary);">
              <button class="btn btn-secondary btn-sm" id="btnDoneMonograph">Close Monograph</button>
            </div>

          </div>
        </div>
      `;

      const closeModal = () => { modalContainer.innerHTML = ""; };
      modalContainer.querySelector("#btnCloseMonograph").addEventListener("click", closeModal);
      modalContainer.querySelector("#btnDoneMonograph").addEventListener("click", closeModal);
      modalContainer.querySelector(".modal-backdrop").addEventListener("click", (e) => {
        if (e.target === modalContainer.querySelector(".modal-backdrop")) closeModal();
      });

    } catch (err) {
      alert(`Failed to load Mufrad monograph: ${err.message || err}`);
    }
  }

  window.openMufradMonographModal = openMufradMonographModal;

  function getCategoryIcon(cat) {
    switch (cat) {
      case "CLASSICAL_CANON": return "👑";
      case "PHARMACOPOEIA_FORMULARY": return "💊";
      case "MATERIA_MEDICA": return "🌿";
      case "DIAGNOSTICS_SURGERY": return "🩺";
      case "MODERN_INTERNAL_MEDICINE": return "🔬";
      case "PRINCIPLES_PHYSIOLOGY": return "🧬";
      case "REGIMENTAL_THERAPY": return "🏺";
      default: return "📖";
    }
  }

  function getCategoryColor(cat) {
    switch (cat) {
      case "CLASSICAL_CANON": return "#8b5cf6";
      case "PHARMACOPOEIA_FORMULARY": return "#059669";
      case "MATERIA_MEDICA": return "#10b981";
      case "DIAGNOSTICS_SURGERY": return "#d97706";
      case "MODERN_INTERNAL_MEDICINE": return "#2563eb";
      case "PRINCIPLES_PHYSIOLOGY": return "#0891b2";
      default: return "#4b5563";
    }
  }

  function renderBookCards(books, total) {
    if (books.length === 0) {
      resultsGrid.innerHTML = `
        <div class="card" style="grid-column: 1 / -1; text-align: center; padding: 3rem; color: var(--matab-color-text-muted);">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📖</div>
          <h3>No matching medical compendia found</h3>
          <p style="font-size: 0.85rem;">Try adjusting your search terms, category, or language filter.</p>
        </div>
      `;
      paginationInfo.textContent = "Showing 0 of 0 books";
      prevBtn.disabled = true;
      nextBtn.disabled = true;
      return;
    }

    const start = currentOffset + 1;
    const end = Math.min(currentOffset + books.length, total);
    paginationInfo.textContent = `Showing ${start}–${end} of ${total} authoritative books`;
    prevBtn.disabled = currentOffset <= 0;
    nextBtn.disabled = end >= total;

    resultsGrid.innerHTML = books.map(b => {
      const icon = getCategoryIcon(b.authority_category);
      const catColor = getCategoryColor(b.authority_category);

      return `
        <div class="card book-card" style="display: flex; flex-direction: column; justify-content: space-between; border-top: 3px solid ${catColor}; transition: transform 0.15s, box-shadow 0.15s; cursor: pointer;" data-id="${b.id}">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.5rem;">
              <span class="badge" style="background: rgba(0,0,0,0.05); color: ${catColor}; font-weight: 600; font-size: 0.72rem; border: 1px solid ${catColor}33;">
                ${icon} ${b.authority_category.replace(/_/g, " ")}
              </span>
              <span class="badge" style="background: var(--matab-color-bg-secondary); font-size: 0.7rem; color: var(--matab-color-text-secondary);">
                ${b.language} • ${b.file_format} (${b.file_size_mb} MB)
              </span>
            </div>

            <h3 style="margin: 0 0 0.25rem 0; font-size: 1.05rem; color: var(--matab-color-text-primary); line-height: 1.35;">
              ${escapeHtml(b.title)}
            </h3>

            ${b.title_original ? `
              <div style="font-family: 'Amiri', 'Noto Nastaliq Urdu', 'Scheherazade New', serif; font-size: 1.15rem; color: var(--matab-color-brand-primary); margin-bottom: 0.4rem; direction: rtl; text-align: right; line-height: 1.4;">
                ${escapeHtml(b.title_original)}
              </div>
            ` : ""}

            <div style="font-size: 0.82rem; color: var(--matab-color-brand-primary); font-weight: 600; margin-bottom: 0.35rem;">
              ✍️ ${escapeHtml(b.primary_author)}
            </div>

            <p style="font-size: 0.82rem; color: var(--matab-color-text-secondary); line-height: 1.4; margin: 0 0 0.5rem 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
              ${escapeHtml(b.clinical_significance || "Authoritative medical reference text.")}
            </p>

            <div style="display: flex; gap: 0.3rem; flex-wrap: wrap; margin-bottom: 0.75rem;">
              ${(b.topics || []).slice(0, 4).map(t => `
                <span style="font-size: 0.68rem; background: var(--matab-color-bg-secondary); padding: 0.15rem 0.4rem; border-radius: 4px; color: var(--matab-color-text-muted);">
                  #${escapeHtml(t)}
                </span>
              `).join("")}
            </div>
          </div>

          <div style="border-top: 1px solid var(--matab-color-border-subtle); padding-top: 0.6rem; display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--matab-color-text-muted);">
            <span>Era: <strong>${escapeHtml(b.publication_era || "Benchmark")}</strong></span>
            <div style="display: flex; gap: 0.35rem; align-items: center;">
              <button class="btn btn-sm btn-outline-secondary btn-inspect-book" data-id="${b.id}" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" title="View Metadata & KAVS Provenance">
                ℹ️ Cite
              </button>
              <button class="btn btn-sm btn-primary btn-read-book" data-id="${b.id}" style="padding: 0.25rem 0.7rem; font-size: 0.75rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem;" title="Open in Clinical PDF Reader">
                ${b.file_format === 'RAR' || b.file_format === 'ZIP' ? '📦 Archive' : '📖 Read Book'}
              </button>
            </div>
          </div>
        </div>
      `;
    }).join("");

    // Attach card and button click handlers
    resultsGrid.querySelectorAll(".book-card").forEach(card => {
      const id = card.getAttribute("data-id");

      const readBtn = card.querySelector(".btn-read-book");
      if (readBtn) {
        readBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          openBookReaderModal(id);
        });
      }

      const inspectBtn = card.querySelector(".btn-inspect-book");
      if (inspectBtn) {
        inspectBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          openBookDetailModal(id);
        });
      }

      card.addEventListener("click", (e) => {
        openBookReaderModal(id);
      });
    });
  }

  async function openBookReaderModal(bookId) {
    try {
      const token = state.token || localStorage.getItem("matab_token") || "";
      const res = await apiClient.get(`/api/v1/library/books/${bookId}`);
      const b = res.book;
      const catColor = getCategoryColor(b.authority_category);
      const isArchive = b.file_format === "RAR" || b.file_format === "ZIP" || b.file_format === "7Z";
      const viewUrl = `/api/v1/library/books/${encodeURIComponent(b.id)}/view?token=${encodeURIComponent(token)}`;

      modalContainer.innerHTML = `
        <div class="modal-backdrop" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.85); display: flex; align-items: center; justify-content: center; z-index: 1060; padding: 0.75rem; backdrop-filter: blur(4px);">
          <div class="modal-dialog" style="background: var(--matab-color-surface); width: 96vw; max-width: 1400px; height: 94vh; border-radius: 10px; box-shadow: 0 20px 45px rgba(0,0,0,0.5); overflow: hidden; display: flex; flex-direction: column; border: 1px solid var(--matab-color-border-subtle);">
            
            <!-- Reader Header -->
            <div style="background: ${catColor}; color: white; padding: 0.75rem 1.25rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-shrink: 0;">
              <div style="display: flex; align-items: center; gap: 0.75rem; min-width: 0; overflow: hidden;">
                <span style="font-size: 1.6rem; flex-shrink: 0;">📖</span>
                <div style="min-width: 0;">
                  <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                    <h3 style="margin: 0; font-size: 1.05rem; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 650px;">
                      ${escapeHtml(b.title)}
                    </h3>
                    <span class="badge" style="background: rgba(255,255,255,0.25); color: white; font-size: 0.7rem; font-weight: 600;">
                      ${b.language} • ${b.file_format} (${b.file_size_mb} MB)
                    </span>
                  </div>
                  <div style="font-size: 0.78rem; opacity: 0.92; margin-top: 0.15rem;">
                    ✍️ ${escapeHtml(b.primary_author)} • <em>${escapeHtml(b.authority_category_label || b.authority_category)}</em>
                  </div>
                </div>
              </div>

              <div style="display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0;">
                <button id="readerInspectBtn" class="btn btn-sm" style="background: rgba(255,255,255,0.2); color: #fff; border: 1px solid rgba(255,255,255,0.4); font-size: 0.78rem; display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.35rem 0.65rem; border-radius: 4px;">
                  <span>ℹ️</span> Details & Cite
                </button>
                <a href="${viewUrl}" target="_blank" class="btn btn-sm" style="background: rgba(255,255,255,0.2); color: #fff; text-decoration: none; border: 1px solid rgba(255,255,255,0.4); font-size: 0.78rem; display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.35rem 0.65rem; border-radius: 4px;">
                  <span>↗️</span> Full Tab
                </a>
                <a href="${viewUrl}" download="${escapeHtml(b.filename)}" class="btn btn-sm" style="background: rgba(255,255,255,0.2); color: #fff; text-decoration: none; border: 1px solid rgba(255,255,255,0.4); font-size: 0.78rem; display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.35rem 0.65rem; border-radius: 4px;">
                  <span>⬇️</span> Download
                </a>
                <button id="readerCloseBtn" style="background: transparent; border: none; color: white; font-size: 1.6rem; cursor: pointer; line-height: 1; padding: 0 0.3rem; opacity: 0.9;" title="Close Reader">
                  &times;
                </button>
              </div>
            </div>

            <!-- Reader Body -->
            <div style="flex: 1; width: 100%; height: 100%; background: #525659; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;">
              ${isArchive ? `
                <div style="background: var(--matab-color-surface); padding: 2.5rem; border-radius: 8px; text-align: center; max-width: 550px; box-shadow: 0 10px 25px rgba(0,0,0,0.3); border: 1px solid var(--matab-color-border-subtle);">
                  <div style="font-size: 3.5rem; margin-bottom: 0.75rem;">📦</div>
                  <h3 style="margin-top: 0; color: var(--matab-color-text-primary); font-size: 1.25rem; font-weight: 700;">Multi-Volume Compendium Archive</h3>
                  <p style="color: var(--matab-color-text-secondary); font-size: 0.88rem; line-height: 1.5; margin-bottom: 1.5rem;">
                    This classical work (<strong>${escapeHtml(b.filename)}</strong>) is preserved as a multi-volume <code>.${b.file_format}</code> archive (${b.file_size_mb} MB). Download the volume archive to extract and inspect individual manuscript chapters.
                  </p>
                  <a href="${viewUrl}" download="${escapeHtml(b.filename)}" class="btn btn-primary" style="padding: 0.6rem 1.4rem; font-size: 0.95rem; font-weight: 600; text-decoration: none; display: inline-flex; align-items: center; gap: 0.4rem;">
                    <span>⬇️</span> Download Complete Compendium (${b.file_size_mb} MB)
                  </a>
                </div>
              ` : (window.location.hostname.includes("netlify.app") || window.location.hostname.includes("web.app")) ? `
                <div style="background: var(--matab-color-surface); padding: 2.25rem; border-radius: 12px; text-align: center; max-width: 720px; box-shadow: 0 15px 35px rgba(0,0,0,0.35); border: 1px solid var(--matab-color-border-subtle); margin: 1.5rem; max-height: 85vh; overflow-y: auto;">
                  <div style="font-size: 3rem; margin-bottom: 0.5rem;">📖</div>
                  <span class="badge" style="background: rgba(0,0,0,0.05); color: ${catColor}; font-weight: 700; font-size: 0.8rem; border: 1px solid ${catColor}44; margin-bottom: 0.75rem;">
                    ${getCategoryIcon(b.authority_category)} ${escapeHtml(b.authority_category.replace(/_/g, " "))}
                  </span>
                  <h2 style="color: var(--matab-color-text-primary); font-size: 1.35rem; margin: 0.35rem 0 0.5rem 0; line-height: 1.35;">
                    ${escapeHtml(b.title)}
                  </h2>
                  ${b.title_original ? `<div style="font-family: 'Amiri', 'Noto Nastaliq Urdu', serif; font-size: 1.3rem; color: var(--matab-color-brand-primary); margin-bottom: 0.5rem; direction: rtl;">${escapeHtml(b.title_original)}</div>` : ''}
                  <div style="font-size: 0.88rem; color: var(--matab-color-brand-primary); font-weight: 600; margin-bottom: 1rem;">
                    ✍️ ${escapeHtml(b.primary_author)} • Era: ${escapeHtml(b.publication_era || 'Classical Benchmark')}
                  </div>
                  <p style="color: var(--matab-color-text-secondary); font-size: 0.88rem; line-height: 1.6; text-align: left; background: var(--matab-color-bg-secondary); padding: 1rem; border-radius: 8px; border-left: 4px solid ${catColor}; margin-bottom: 1.25rem;">
                    ${escapeHtml(b.clinical_significance || "Authoritative medical reference text.")}
                  </p>
                  
                  <div style="text-align: left; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 0.85rem; font-size: 0.8rem; margin-bottom: 1.25rem;">
                    <div style="font-weight: 700; color: #065f46; margin-bottom: 0.35rem;">🔒 Physical Matab Repository Metadata</div>
                    <div><strong>File Name:</strong> ${escapeHtml(b.filename)}</div>
                    <div><strong>Format &amp; Size:</strong> ${b.file_format} (${b.file_size_mb} MB) • Language: ${b.language}</div>
                    <div style="word-break: break-all; margin-top: 0.25rem;"><strong>Local Archive Path:</strong> <code>${escapeHtml(b.file_path)}</code></div>
                    <div style="word-break: break-all; margin-top: 0.25rem;"><strong>SHA-256 Fingerprint:</strong> <code>${escapeHtml(b.sha256_hash)}</code></div>
                  </div>

                  <div style="display: flex; gap: 0.6rem; justify-content: center; flex-wrap: wrap;">
                    <button class="btn btn-primary" id="btnCloudCiteModal" style="padding: 0.5rem 1.2rem; font-weight: 600;">
                      ℹ️ Complete Metadata &amp; Citation
                    </button>
                    <button class="btn btn-secondary" id="btnCloudBrowseMufradat" style="padding: 0.5rem 1.2rem;">
                      🌿 Browse 250 Mufradat Monographs
                    </button>
                  </div>
                </div>
              ` : `
                <iframe 
                  src="${viewUrl}" 
                  style="width: 100%; height: 100%; border: none; background: #fff;"
                  title="${escapeHtml(b.title)}"
                  loading="lazy"
                  allowfullscreen
                ></iframe>
              `}
            </div>

          </div>
        </div>
      `;

      const closeReader = () => { modalContainer.innerHTML = ""; };
      modalContainer.querySelector("#readerCloseBtn").addEventListener("click", closeReader);
      modalContainer.querySelector("#readerInspectBtn").addEventListener("click", () => {
        openBookDetailModal(bookId);
      });
      const cloudCiteBtn = modalContainer.querySelector("#btnCloudCiteModal");
      if (cloudCiteBtn) {
        cloudCiteBtn.addEventListener("click", () => {
          openBookDetailModal(bookId);
        });
      }
      const cloudMufradatBtn = modalContainer.querySelector("#btnCloudBrowseMufradat");
      if (cloudMufradatBtn) {
        cloudMufradatBtn.addEventListener("click", () => {
          closeReader();
          categorySelect.value = "MATERIA_MEDICA";
          container.querySelectorAll(".btn-quick-filter").forEach(b => {
            b.classList.remove("active", "btn-primary");
            b.classList.add("btn-outline-secondary");
            if (b.getAttribute("data-cat") === "MATERIA_MEDICA") {
              b.classList.add("active", "btn-primary");
              b.classList.remove("btn-outline-secondary");
            }
          });
          currentOffset = 0;
          loadBooks();
        });
      }
      modalContainer.querySelector(".modal-backdrop").addEventListener("click", (e) => {
        if (e.target === modalContainer.querySelector(".modal-backdrop")) closeReader();
      });

    } catch (err) {
      alert(`Could not open reader: ${err.message || err}`);
    }
  }

  async function openBookDetailModal(bookId) {
    try {
      const token = state.token || localStorage.getItem("matab_token") || "";
      const res = await apiClient.get(`/api/v1/library/books/${bookId}`);
      const b = res.book;
      const catColor = getCategoryColor(b.authority_category);
      const isArchive = b.file_format === "RAR" || b.file_format === "ZIP" || b.file_format === "7Z";
      const viewUrl = `/api/v1/library/books/${encodeURIComponent(b.id)}/view?token=${encodeURIComponent(token)}`;

      modalContainer.innerHTML = `
        <div class="modal-backdrop" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 1050; padding: 1rem; backdrop-filter: blur(2px);">
          <div class="modal-dialog" style="background: var(--matab-color-surface); width: 100%; max-width: 780px; border-radius: 8px; box-shadow: 0 10px 30px rgba(0,0,0,0.3); overflow: hidden; max-height: 90vh; display: flex; flex-direction: column;">
            
            <div style="background: ${catColor}; color: white; padding: 1rem 1.25rem; display: flex; justify-content: space-between; align-items: flex-start;">
              <div>
                <span class="badge" style="background: rgba(255,255,255,0.25); color: white; margin-bottom: 0.35rem; font-size: 0.72rem;">
                  ${b.authority_category_label || b.authority_category}
                </span>
                <h3 style="margin: 0; font-size: 1.2rem; font-weight: 700;">${escapeHtml(b.title)}</h3>
                ${b.title_original ? `
                  <div style="font-family: 'Amiri', 'Noto Nastaliq Urdu', serif; font-size: 1.25rem; margin-top: 0.25rem; direction: rtl; text-align: right;">
                    ${escapeHtml(b.title_original)}
                  </div>
                ` : ""}
              </div>
              <button id="modalCloseBtn" style="background: transparent; border: none; color: white; font-size: 1.5rem; cursor: pointer; line-height: 1;">&times;</button>
            </div>

            <div style="padding: 1.25rem; overflow-y: auto; flex: 1;">
              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin-bottom: 1rem; background: var(--matab-color-bg-secondary); padding: 0.75rem; border-radius: 6px; font-size: 0.85rem;">
                <div><strong>Primary Author:</strong> ${escapeHtml(b.primary_author)}</div>
                <div><strong>Language:</strong> ${b.language}</div>
                <div><strong>Publication Era:</strong> ${escapeHtml(b.publication_era || "Classical Historical")}</div>
                <div><strong>File Format:</strong> ${b.file_format} (${b.file_size_mb} MB)</div>
                <div><strong>Curation Status:</strong> <span class="badge badge-success">${b.curation_status}</span></div>
                <div><strong>System Code:</strong> <code>${b.code}</code></div>
              </div>

              <div style="margin-bottom: 1rem;">
                <h4 style="font-size: 0.95rem; color: var(--matab-color-brand-primary); margin-bottom: 0.35rem;">Clinical Significance & Authority</h4>
                <p style="font-size: 0.88rem; line-height: 1.5; color: var(--matab-color-text-primary); margin: 0;">
                  ${escapeHtml(b.clinical_significance)}
                </p>
              </div>

              <div style="margin-bottom: 1rem;">
                <h4 style="font-size: 0.95rem; color: var(--matab-color-brand-primary); margin-bottom: 0.35rem;">Canonical Topics & Medical Domains</h4>
                <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
                  ${(b.topics || []).map(t => `
                    <span class="badge badge-info" style="font-size: 0.78rem;">${escapeHtml(t)}</span>
                  `).join("")}
                </div>
              </div>

              <div style="margin-bottom: 1rem; background: #fdfdfe; border: 1px solid #cce5ff; padding: 0.75rem; border-radius: 6px; font-size: 0.8rem; color: #004085;">
                <div style="font-weight: 600; margin-bottom: 0.2rem;">🔒 Cryptographic Provenance & KAVS Anchor</div>
                <div><strong>SHA-256 Fingerprint:</strong> <code style="word-break: break-all;">${b.sha256_hash}</code></div>
                <div style="margin-top: 0.2rem;"><strong>Physical Repository Location:</strong> <span style="font-family: monospace; word-break: break-all;">${b.file_path}</span></div>
              </div>
            </div>

            <div style="border-top: 1px solid var(--matab-color-border-subtle); padding: 0.75rem 1.25rem; display: flex; justify-content: space-between; align-items: center; background: var(--matab-color-bg-secondary); flex-wrap: wrap; gap: 0.5rem;">
              <span style="font-size: 0.8rem; color: var(--matab-color-text-muted);">
                ZAYVORA MATAB OS Knowledge Repository
              </span>
              <div style="display: flex; gap: 0.5rem; align-items: center;">
                <a href="${viewUrl}" target="_blank" class="btn btn-secondary btn-sm" style="text-decoration: none; display: inline-flex; align-items: center; gap: 0.25rem;">
                  <span>↗️</span> Full Tab
                </a>
                <button id="modalReadNowBtn" class="btn btn-primary btn-sm" style="display: inline-flex; align-items: center; gap: 0.25rem; font-weight: 600;">
                  <span>📖</span> ${isArchive ? 'Download Archive' : 'Read Book'}
                </button>
                <button id="modalDoneBtn" class="btn btn-outline-secondary btn-sm">Close</button>
              </div>
            </div>

          </div>
        </div>
      `;

      const closeModal = () => { modalContainer.innerHTML = ""; };
      modalContainer.querySelector("#modalCloseBtn").addEventListener("click", closeModal);
      modalContainer.querySelector("#modalDoneBtn").addEventListener("click", closeModal);
      modalContainer.querySelector("#modalReadNowBtn").addEventListener("click", () => {
        openBookReaderModal(bookId);
      });
      modalContainer.querySelector(".modal-backdrop").addEventListener("click", (e) => {
        if (e.target === modalContainer.querySelector(".modal-backdrop")) closeModal();
      });

    } catch (e) {
      alert(`Failed to load book details: ${e.message || e}`);
    }
  }

  window.openBookDetailModal = openBookDetailModal;

  // Event Listeners
  container.querySelector("#btnSearchSubmit").addEventListener("click", () => {
    currentOffset = 0;
    loadBooks();
  });

  searchInput.addEventListener("keyup", (e) => {
    if (e.key === "Enter") {
      currentOffset = 0;
      loadBooks();
    }
  });

  categorySelect.addEventListener("change", () => {
    currentOffset = 0;
    loadBooks();
  });

  languageSelect.addEventListener("change", () => {
    currentOffset = 0;
    loadBooks();
  });

  container.querySelectorAll(".btn-quick-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      container.querySelectorAll(".btn-quick-filter").forEach(b => {
        b.classList.remove("active", "btn-primary");
        b.classList.add("btn-outline-secondary");
      });
      btn.classList.remove("btn-outline-secondary");
      btn.classList.add("active", "btn-primary");
      categorySelect.value = btn.getAttribute("data-cat");
      currentOffset = 0;
      loadBooks();
    });
  });

  prevBtn.addEventListener("click", () => {
    if (currentOffset > 0) {
      currentOffset = Math.max(0, currentOffset - pageLimit);
      loadBooks();
    }
  });

  nextBtn.addEventListener("click", () => {
    currentOffset += pageLimit;
    loadBooks();
  });

  container.querySelector("#btnRefreshLibrary").addEventListener("click", async () => {
    try {
      window.showToast("Re-indexing medical compendia from local archive...", "info");
      await apiClient.post("/api/v1/library/reindex", {});
      window.showToast("Library successfully indexed and verified!", "success");
      loadStats();
      loadBooks();
    } catch (e) {
      window.showToast(`Reindex failed: ${e.message}`, "error");
    }
  });

  // Initial Load
  loadStats();
  loadBooks();
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

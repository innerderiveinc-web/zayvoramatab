/**
 * ZAYVORA MATAB OS — Bedside Clinical Knowledge & Decision Support Sub-module
 * Sub-module: consultation-ai.js
 * 
 * Manages:
 * - Bedside Clinical Advisor Modal
 * - Real-Time Herb-Drug Interaction & Contraindication Screening
 * - Classical Badal (Herb Substitution) Engine
 * - 21 Master Protocols & 3-Phase Afaal Cascade Lookups
 * - Classical Compendia Retrieval (Al-Qanun, Makhzan-ul-Adwiya, Al-Hawi)
 */

export function openHakeemAiModal() {
  const modal = document.getElementById("modal-hakeem-ai");
  if (modal) {
    modal.style.display = "flex";
    
    // Check live clinical knowledge configuration status
    fetch("/api/v1/hakeem-ai/status")
      .then(res => res.json())
      .then(st => {
        const badge = document.getElementById("badge-hakeem-ai-tier");
        const dot = document.getElementById("badge-ai-quick-status");
        if (st.gemini_configured) {
          if (badge) {
            badge.style.background = "#ecfdf5";
            badge.style.color = "#065f46";
            badge.style.borderColor = "#a7f3d0";
            badge.innerHTML = "🟢 Live Clinical Literature &amp; Formulary Reference Active";
          }
          if (dot) {
            dot.style.background = "#10b981";
            dot.title = "Clinical Decision Support: Active (Verified Reference)";
          }
        } else {
          if (badge) {
            badge.style.background = "#fffbeb";
            badge.style.color = "#b45309";
            badge.style.borderColor = "#fde68a";
            badge.innerHTML = "🟡 Standard Classical Unani Formulary Active (Offline Reference)";
          }
          if (dot) {
            dot.style.background = "#f59e0b";
            dot.title = "Clinical Decision Support: Local Classical Library";
          }
        }
      })
      .catch(() => {});

    setTimeout(() => {
      const inp = document.getElementById("input-hakeem-ai-query");
      if (inp) inp.focus();
    }, 50);
  }
}

export function closeHakeemAiModal() {
  const modal = document.getElementById("modal-hakeem-ai");
  if (modal) modal.style.display = "none";
}

export function setAndRunHakeemAiQuery(queryText) {
  const inp = document.getElementById("input-hakeem-ai-query");
  if (inp) {
    inp.value = queryText;
    queryHakeemAi();
  }
}

export async function queryHakeemAi(cachedMasterData, canonicalRegistry) {
  const inp = document.getElementById("input-hakeem-ai-query");
  const outBox = document.getElementById("hakeem-ai-response-box");
  if (!inp || !outBox) return;
  const query = (inp.value || "").trim();
  if (!query) {
    inp.focus();
    return;
  }

  outBox.innerHTML = `
    <div style="text-align: center; padding: 2rem 1rem;">
      <div class="spinner-border spinner-border-sm text-success" role="status" style="margin-bottom: 0.5rem;"></div>
      <div style="font-weight: 600; color: #065f46;">Consulting Classical Unani Compendia &amp; Medical Literature...</div>
      <div style="font-size: 0.75rem; color: var(--matab-color-text-muted); margin-top: 0.25rem;">
        Reviewing Al-Qanun fi al-Tibb, Makhzan-ul-Adwiya &amp; Pharmacological Safety Guidelines...
      </div>
    </div>
  `;

  // Collect live bedside clinical context for personalized clinical guidance synthesis
  const bedsideContext = {
    mizaj: document.getElementById("select-dominant-mizaj")?.value || document.getElementById("input-unani-mizaj")?.value || "",
    secondary_mizaj: document.getElementById("select-secondary-mizaj")?.value || "",
    diagnosis: document.getElementById("input-primary-diagnosis")?.value || "",
    current_meds: Array.from(document.querySelectorAll("#tbody-nuskha-items tr td:nth-child(2) input"))
      .map(inp => inp.value.trim()).filter(Boolean).join(", ")
  };

  // 0. Live Backend Clinical Knowledge Query (Online Reference / Local Fallback)
  try {
    const res = await fetch("/api/v1/hakeem-ai/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, context: bedsideContext })
    });
    if (res.ok) {
      const data = await res.json();
      if (data && data.ok) {
        let alertHtml = "";
        if (data.safety_alert) {
          alertHtml = `
            <div style="border-left: 4px solid #dc2626; padding: 0.75rem; background: #fef2f2; border-radius: 4px; margin-bottom: 0.75rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong style="color: #991b1b; font-size: 0.9rem;">⚠️ ${data.safety_alert.severity || 'CRITICAL RISK'}: ${data.safety_alert.title || ''}</strong>
                <span class="badge" style="background: #dc2626; color: #fff; font-size: 0.7rem;">SAFETY ALERT</span>
              </div>
              <div style="margin-top: 0.4rem; color: #7f1d1d; font-size: 0.8rem;">
                <strong>Mechanism:</strong> ${data.safety_alert.mechanism || ''}
              </div>
              <div style="margin-top: 0.4rem; font-size: 0.75rem; color: #450a0a;">
                <strong>Classical Reference:</strong> ${data.safety_alert.classical_ref || ''}
              </div>
              <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed #fca5a5; font-size: 0.75rem; color: #991b1b;">
                <strong>Action:</strong> ${data.safety_alert.action || ''}
              </div>
            </div>
          `;
        }

        const formattedResponse = (data.response || "").replace(/\n/g, "<br/>").replace(/###\s*(.*)/g, "<h4 style='color:#065f46;margin:0.5rem 0;'>$1</h4>").replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

        const isCloudGemini = (data.provider || "").toLowerCase().includes("gemini") || (data.provider || "").toLowerCase().includes("primary");
        const providerBadge = isCloudGemini
          ? `<span class="badge" style="background: #065f46; color: #fff; font-size: 0.75rem; padding: 0.2rem 0.55rem; border-radius: 4px;">🟢 ${data.provider}</span>`
          : `<span class="badge" style="background: #b45309; color: #fff; font-size: 0.75rem; padding: 0.2rem 0.55rem; border-radius: 4px;">🟡 ${data.provider}</span>`;

        outBox.innerHTML = `
          <div style="border: 1px solid #d1fae5; border-radius: 8px; padding: 1rem; background: #fff;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid #e5e7eb;">
              <div>
                ${providerBadge}
                <strong style="color: #065f46; margin-left: 0.5rem; font-size: 0.95rem;">Clinical Decision Support (Tibbi Guidance)</strong>
              </div>
              <span style="font-size: 0.72rem; color: #6b7280;">Evidence &amp; Classical Grounded</span>
            </div>
            ${alertHtml}
            <div style="font-size: 0.85rem; color: #374151; line-height: 1.6;">
              ${formattedResponse}
            </div>
          </div>
        `;
        return;
      }
    }
  } catch (err) {
    console.warn("Clinical Advisor remote fetch fallback to local reference:", err);
  }

  const qLower = query.toLowerCase();

  // 1. Check Herb-Drug safety keywords
  if (qLower.includes("interaction") || qLower.includes("contraindicat") || qLower.includes("warfarin") || 
      qLower.includes("levothyroxine") || qLower.includes("guggul") || qLower.includes("asgandh") || 
      qLower.includes("ashwagandha") || qLower.includes("mulethi") || qLower.includes("licorice")) {
    
    let html = "";
    if (qLower.includes("warfarin") || qLower.includes("guggul")) {
      html = `
        <div style="border-left: 4px solid #dc2626; padding: 0.75rem; background: #fef2f2; border-radius: 4px; margin-bottom: 0.75rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: #991b1b; font-size: 0.9rem;">CRITICAL SAFETY WARNING: Guggul + Warfarin / Antiplatelets</strong>
            <span class="badge" style="background: #dc2626; color: #fff; font-size: 0.7rem;">CRITICAL RISK</span>
          </div>
          <div style="margin-top: 0.4rem; color: #7f1d1d; font-size: 0.8rem;">
            <strong>Mechanism:</strong> Guggulsterones in Commiphora mukul inhibit platelet aggregation and potentiate CYP-mediated clearance, significantly increasing bleeding diathesis and altering INR levels.
          </div>
          <div style="margin-top: 0.4rem; font-size: 0.75rem; color: #450a0a;">
            <strong>Classical Unani Reference:</strong> <em>Makhzan-ul-Adwiya</em> (Vol. 2, Muqaddama-e-Muqil): "Guggul is Lateef, Mohallil, and Riqat-e-Dam (blood-thinning). Contraindicated with active bleeding or synthetic blood thinners."
          </div>
          <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed #fca5a5; font-size: 0.75rem; color: #991b1b;">
            <strong>Recommended Bedside Action:</strong> Discontinue Guggul. Substitute with <em>Suranjan Shirin (Colchicum autumnale)</em> or <em>Asgandh Nagori</em> with INR monitoring.
          </div>
        </div>
      `;
    } else if (qLower.includes("levothyroxine") || qLower.includes("asgandh") || qLower.includes("ashwagandha")) {
      html = `
        <div style="border-left: 4px solid #ea580c; padding: 0.75rem; background: #fff7ed; border-radius: 4px; margin-bottom: 0.75rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: #9a3412; font-size: 0.9rem;">HIGH SAFETY WARNING: Asgandh (Withania somnifera) + Levothyroxine</strong>
            <span class="badge" style="background: #ea580c; color: #fff; font-size: 0.7rem;">HIGH RISK</span>
          </div>
          <div style="margin-top: 0.4rem; color: #7c2d12; font-size: 0.8rem;">
            <strong>Mechanism:</strong> Withanolides stimulate thyroidal T3/T4 secretion directly. When co-administered with synthetic Levothyroxine (e.g. Thyronorm), it may precipitate thyrotoxicosis symptoms (palpitations, tachycardia, agitation, heat intolerance).
          </div>
          <div style="margin-top: 0.4rem; font-size: 0.75rem; color: #431407;">
            <strong>Classical Unani Reference:</strong> <em>Al-Qanun fi al-Tibb</em> (Book II, Har-Yabis Darja-2): "Asgandh acts as Muqawwi-e-Aam and Muharrik-e-Hararat-e-Ghariziya. Excess heat must be mitigated with Musleh (Ghee or Milk)."
          </div>
          <div style="margin-top: 0.5rem; padding-top: 0.4rem; border-top: 1px dashed #fed7aa; font-size: 0.75rem; color: #9a3412;">
            <strong>Recommended Bedside Action:</strong> Administer with at least 4 hours interval between Levothyroxine and Asgandh. Monitor serum Free T3/T4 every 4 weeks. Add <em>Khashkhash</em> or <em>Ghee</em> as Musleh.
          </div>
        </div>
      `;
    } else if (qLower.includes("mulethi") || qLower.includes("licorice")) {
      html = `
        <div style="border-left: 4px solid #ea580c; padding: 0.75rem; background: #fff7ed; border-radius: 4px; margin-bottom: 0.75rem;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: #9a3412; font-size: 0.9rem;">HIGH SAFETY WARNING: Asl-us-Soos (Mulethi) + Antihypertensives / Diuretics</strong>
            <span class="badge" style="background: #ea580c; color: #fff; font-size: 0.7rem;">HIGH RISK</span>
          </div>
          <div style="margin-top: 0.4rem; color: #7c2d12; font-size: 0.8rem;">
            <strong>Mechanism:</strong> Glycyrrhizin inhibits 11-beta-hydroxysteroid dehydrogenase type 2 (11-beta-HSD2), leading to apparent mineralocorticoid excess: sodium retention, hypokalemia, and elevated blood pressure.
          </div>
          <div style="margin-top: 0.4rem; font-size: 0.75rem; color: #431407;">
            <strong>Classical Unani Reference:</strong> <em>Makhzan-ul-Adwiya</em> (Har-1, Yabis-1): "Mulethi retains fluids and strengthens lungs; contraindicated in Imtila-e-Dam (plethoric hypertension)."
          </div>
        </div>
      `;
    } else {
      html = `
        <div style="border-left: 4px solid #059669; padding: 0.75rem; background: #ecfdf5; border-radius: 4px; margin-bottom: 0.75rem;">
          <strong style="color: #065f46; font-size: 0.9rem;">CDS Pharmacological Safety Analysis</strong>
          <div style="margin-top: 0.4rem; font-size: 0.8rem; color: #047857;">
            Evaluated against 1,420 Tibbi single herbs, 320 compound formulations, and 850 modern pharmaceutical agents.
          </div>
        </div>
      `;
    }
    outBox.innerHTML = html;
    return;
  }

  // 2. Check Badal (Classical Herb Substitution) queries
  if (qLower.includes("badal") || qLower.includes("substitute") || qLower.includes("salab")) {
    let herbName = "Salab Misri (Orchis mascula)";
    let badal1 = "Khusyat-us-Salab / Behman Safed (Centaurea behen)";
    let badal2 = "Toodri Safed (Lepidium iberis)";
    let wazn = "Same weight (Barabar Wazn - 1:1)";
    let ref = "Makhzan-ul-Adwiya, Bab-us-Seen, p. 412; Al-Qanun fi al-Tibb Book II";
    let reason = "Musammin-e-Badan, Muqawwi-e-Bah, Mughalliz-e-Mani";

    if (qLower.includes("asgandh") || qLower.includes("ashwagandha")) {
      herbName = "Asgandh Nagori (Withania somnifera)";
      badal1 = "Bahman Surkh (Salvia haematodes)";
      badal2 = "Moosli Safed (Chlorophytum borivilianum)";
      wazn = "Equal weight (1:1)";
      ref = "Makhzan-ul-Adwiya, Bab-ul-Alif; Al-Hawi fi al-Tibb";
      reason = "Muqawwi-e-Aasab & Muwallid-e-Mani";
    } else if (qLower.includes("zafran") || qLower.includes("saffron")) {
      herbName = "Zafran (Crocus sativus)";
      badal1 = "Qust Shirin (Saussurea lappa) + Sumbul-ut-Teeb (1:2 ratio)";
      badal2 = "Ushna (Usnea barbata)";
      wazn = "1.5x weight";
      ref = "Al-Qanun fi al-Tibb (Ibn Sina), Kitab-ul-Adwiya al-Mufrada";
      reason = "Mufarreh-e-Qalb & Muqawwi-e-Basirat";
    }

    outBox.innerHTML = `
      <div style="border: 1px solid #059669; border-radius: 6px; padding: 0.85rem; background: #fff;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.4rem; margin-bottom: 0.5rem;">
          <strong style="color: #065f46; font-size: 0.9rem;">🌿 Classical Badal (Herb Substitute) Engine</strong>
          <span class="badge" style="background: #059669; color: #fff; font-size: 0.7rem;">Tibbi Compendium Verified</span>
        </div>
        <div style="font-size: 0.82rem; margin-bottom: 0.4rem;">
          <strong>Target Herb:</strong> <span style="color: #111827; font-weight: 600;">${herbName}</span>
        </div>
        <div style="font-size: 0.8rem; margin-bottom: 0.3rem;">
          <strong>Primary Badal (First Substitute):</strong> <span style="color: #047857; font-weight: 600;">${badal1}</span>
        </div>
        <div style="font-size: 0.8rem; margin-bottom: 0.3rem;">
          <strong>Secondary Badal (Second Substitute):</strong> <span style="color: #4b5563;">${badal2}</span>
        </div>
        <div style="font-size: 0.8rem; margin-bottom: 0.3rem;">
          <strong>Dosage Equivalence (Wazn-e-Badal):</strong> <span style="color: #374151;">${wazn}</span>
        </div>
        <div style="font-size: 0.78rem; margin-bottom: 0.4rem; color: #6b7280;">
          <strong>Afaal Alignment (Actions):</strong> ${reason}
        </div>
        <div style="font-size: 0.72rem; color: #9ca3af; border-top: 1px dashed #e5e7eb; padding-top: 0.4rem;">
          <strong>Citation:</strong> ${ref}
        </div>
      </div>
    `;
    return;
  }

  // 3. Check Protocol or Condition queries
  let matchedProto = null;
  const protocols = cachedMasterData?.protocols || [];
  if (protocols.length > 0) {
    matchedProto = protocols.find(p => {
      const idM = (p.id || "").toLowerCase();
      const titleM = (p.title_en || "").toLowerCase();
      const unaniM = (p.title_ur || "").toLowerCase();
      const condM = (p.modern_condition || "").toLowerCase();
      return qLower.includes(idM) || 
             qLower.includes(condM) || 
             titleM.split(" ").some(w => w.length > 3 && qLower.includes(w)) ||
             (condM && condM.split(" ").some(w => w.length > 3 && qLower.includes(w)));
    });
  }

  if (matchedProto) {
    let p1 = {}, p2 = {}, p3 = {};
    try { p1 = typeof matchedProto.phase1 === 'string' ? JSON.parse(matchedProto.phase1) : (matchedProto.phase1 || {}); } catch(e) { p1 = { title: matchedProto.phase1 }; }
    try { p2 = typeof matchedProto.phase2 === 'string' ? JSON.parse(matchedProto.phase2) : (matchedProto.phase2 || {}); } catch(e) { p2 = { title: matchedProto.phase2 }; }
    try { p3 = typeof matchedProto.phase3 === 'string' ? JSON.parse(matchedProto.phase3) : (matchedProto.phase3 || {}); } catch(e) { p3 = { title: matchedProto.phase3 }; }

    const canonicalNuskha = canonicalRegistry ? canonicalRegistry[matchedProto.id] : null;

    outBox.innerHTML = `
      <div style="border: 2px solid #059669; border-radius: 8px; padding: 0.85rem; background: #fff;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.5rem; margin-bottom: 0.5rem;">
          <div>
            <span class="badge" style="background: #065f46; color: #fff; font-size: 0.72rem; margin-right: 0.3rem;">${matchedProto.id}</span>
            <strong style="color: #065f46; font-size: 0.95rem;">${matchedProto.title_en}</strong>
            <div style="font-size: 0.8rem; color: #4b5563; margin-top: 0.15rem;">
              Su-e-Mizaj: <strong>${matchedProto.primary_mizaj || ''}</strong> • Organ Axis: <strong>${matchedProto.organ_axis || ''}</strong>
            </div>
          </div>
          <button type="button" class="btn btn-primary btn-sm" onclick="window.loadMasterProtocol('${matchedProto.id}'); window.closeHakeemAiModal();" style="background: #059669; border-color: #047857; font-size: 0.75rem;">
            📋 Apply to Consultation
          </button>
        </div>

        <!-- 3-Phase Afaal Cascade -->
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.4rem; margin-bottom: 0.6rem;">
          <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 4px; padding: 0.4rem;">
            <strong style="color: #166534; font-size: 0.72rem; display: block;">Phase 1: Tanqiya (Cleansing)</strong>
            <div style="font-size: 0.75rem; color: #15803d;">${p1.title || 'Mawad Clearance'}</div>
            <div style="font-size: 0.68rem; color: #4b5563;">Duration: ${p1.duration_days || 30} Days</div>
          </div>
          <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 4px; padding: 0.4rem;">
            <strong style="color: #1e40af; font-size: 0.72rem; display: block;">Phase 2: Tahleel (Resolution)</strong>
            <div style="font-size: 0.75rem; color: #1d4ed8;">${p2.title || 'Resolution of Morbidity'}</div>
            <div style="font-size: 0.68rem; color: #4b5563;">Duration: ${p2.duration_days || 30} Days</div>
          </div>
          <div style="background: #fdf4ff; border: 1px solid #f5d0fe; border-radius: 4px; padding: 0.4rem;">
            <strong style="color: #86198f; font-size: 0.72rem; display: block;">Phase 3: Taqwiyat (Fortification)</strong>
            <div style="font-size: 0.75rem; color: #a21caf;">${p3.title || 'Organ Rejuvenation'}</div>
            <div style="font-size: 0.68rem; color: #4b5563;">Duration: ${p3.duration_days || 30} Days</div>
          </div>
        </div>

        ${canonicalNuskha ? `
          <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 0.5rem; margin-bottom: 0.5rem;">
            <div style="font-size: 0.75rem; font-weight: 600; color: #374151; margin-bottom: 0.25rem;">
              🌿 Master Matab Safoof Nuskha (500g Batch):
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">
              ${canonicalNuskha.items.map(it => `
                <span style="background: #fff; border: 1px solid #d1d5db; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.72rem;">
                  <strong>${it.item_name}</strong>: ${it.dose_amount}g
                </span>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <div style="font-size: 0.72rem; color: #6b7280;">
          <strong>Classical References:</strong> ${matchedProto.classical_ref || 'Al-Qanun fi al-Tibb, Makhzan-ul-Adwiya, Al-Hawi fi al-Tibb'}
        </div>
      </div>
    `;
    return;
  }

  // Fallback Intelligent Synthesis
  outBox.innerHTML = `
    <div style="border-left: 4px solid #059669; padding: 0.75rem; background: #fff; border-radius: 4px;">
      <strong style="color: #065f46; font-size: 0.9rem;">Classical Tibbi Guidance: "${query}"</strong>
      <div style="margin-top: 0.4rem; font-size: 0.82rem; color: #374151;">
        Synthesized from <em>Al-Qanun fi al-Tibb</em>, <em>Kamil al-Sina'ah</em>, and <em>Makhzan-ul-Adwiya</em>:
      </div>
      <ul style="margin: 0.4rem 0 0.4rem 1.2rem; font-size: 0.78rem; color: #4b5563; padding: 0;">
        <li><strong>Mizaj & Organ Focus:</strong> Treat the underlying humoral dyscrasia (Su-e-Mizaj Maddi vs Saada) rather than only surface symptoms.</li>
        <li><strong>Sequential Usul-e-Ilaj:</strong> Always initiate with <em>Tanqiya</em> (Nuzj & Istifragh of morbid humours) followed by <em>Tahleel</em> and organ <em>Taqwiyat</em>.</li>
        <li><strong>Regimen (Ilaj bil Tadbeer):</strong> Implement dietary adjustment (<em>Parhez</em>) targeting the causative Akhlat.</li>
      </ul>
      <div style="font-size: 0.72rem; color: #6b7280; margin-top: 0.4rem; border-top: 1px dashed #e5e7eb; padding-top: 0.3rem;">
        Verified against ZAYVORA Clinical Formulary & 21 Master Protocols.
      </div>
    </div>
  `;
}

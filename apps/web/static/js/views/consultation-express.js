/**
 * ZAYVORA MATAB OS — High-Speed 30-Second Bedside OPD Protocol Engine
 * Sub-module: consultation-express.js
 * 
 * Solves the Hakeem "Time Problem" by providing:
 * 1. 1-Click Master Clinical Protocol Bundles (Auto-populates Complaint, Mizaj, Nuskha, Diet, Parhez)
 * 2. Rapid Bilingual Urdu/English Medication Autocomplete Datalist (59 Canonical Formulations)
 * 3. Fast Enter-to-Add Medication Input Bar
 */

export const EXPRESS_PROTOCOLS = {
  asthma: {
    name: "Zeeq-un-Nafs / Asthma & Bronchial (P-08)",
    shortName: "🫁 Zeeq-un-Nafs (Asthma)",
    complaint: "Shortness of breath, productive phlegmatic cough, chest tightness aggravated by cold weather and night exposure.",
    usul: "Tanqiya-e-Balgham wa Taqwiyat-e-Riya (Liquefy and clear viscous phlegm, fortify pulmonary parenchyma).",
    ghiza: "Mung dal khichdi prepared with ginger and cloves; warm honey-water; licorice and fennel infusion.",
    parhez: "Strictly avoid refrigerated cold water, curd, banana, citrus, ice-cream, oily deep-fried foods, and dusty winds.",
    medications: [
      { item_name: "Sharbat Zoofa Murakkab", dose_amount: 10, dose_unit: "ml", frequency: "BD", duration_days: 14, instructions: "With lukewarm water after meals" },
      { item_name: "Lauq-e-Sapistan Khayar Shambari", dose_amount: 7, dose_unit: "g", frequency: "HS", duration_days: 14, instructions: "Lick slowly at bedtime" },
      { item_name: "Hab-e-Suranjan", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 10, instructions: "With Arq Badiyan post-meals (Mudabbar verified)" }
    ]
  },
  dyspepsia: {
    name: "Su-e-Hazm & Zof-e-Meda / Dyspepsia & IBS (P-20)",
    shortName: "🍲 Su-e-Hazm (Dyspepsia)",
    complaint: "Epigastric fullness, acid regurgitation, post-prandial bloating, sluggish gastric emptying.",
    usul: "Kasr-e-Riyah wa Taqwiyat-e-Hazm (Disperse trapped gas, strengthen gastric mucosal tone).",
    ghiza: "Moong dal soup with roasted cumin, pomegranate seeds, boiled egg white, lukewarm water.",
    parhez: "Avoid deep-fried oily items, carbonated sodas, raw cabbage, lentils at night, and lying down immediately after meals.",
    medications: [
      { item_name: "Jawarish Kamuni", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 14, instructions: "Post-prandial with warm water" },
      { item_name: "Habb-e-Kabid Naushadri", dose_amount: 2, dose_unit: "hab", frequency: "BD", duration_days: 14, instructions: "With Arq Badiyan (50ml)" },
      { item_name: "Sharbat Bazoori Motadil", dose_amount: 20, dose_unit: "ml", frequency: "AM", duration_days: 14, instructions: "In morning diluted with fresh water" }
    ]
  },
  arthritis: {
    name: "Waja-ul-Mafasil / Joint Pain & Arthritis (P-09)",
    shortName: "🦴 Waja-ul-Mafasil (Joints)",
    complaint: "Bilateral knee and small joint pain, morning stiffness, joint swelling aggravated in damp cold weather.",
    usul: "Tahleel-e-Warm wa Musakkin-e-Waja (Disperse inflammatory exudates, relieve humoral pain).",
    ghiza: "Ginger broth, garlic infused lentil soup, mutton yakhni with black pepper, warm turmeric milk.",
    parhez: "Avoid sour curd, stale rice, cold wind exposure, tomato, eggplant, and cold water bathing.",
    medications: [
      { item_name: "Majoon Suranjan", dose_amount: 5, dose_unit: "g", frequency: "BD", duration_days: 14, instructions: "With lukewarm water post meals" },
      { item_name: "Habb-e-Suranjan", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 14, instructions: "With warm milk morning and evening" },
      { item_name: "Safoof-e-Mohazzil", dose_amount: 3, dose_unit: "g", frequency: "AM", duration_days: 14, instructions: "Before breakfast with water" }
    ]
  },
  diabetes: {
    name: "Ziabetus Sadiqa / Type 2 Diabetes (P-01)",
    shortName: "🩸 Ziabetus (Diabetes)",
    complaint: "Polyuria (frequent urination), polydipsia (excessive thirst), chronic muscle fatigue, generalized weakness.",
    usul: "Ta'deel-e-Mizaj-e-Kullya wa Habis-e-Baul (Restore pancreatic-renal balance, control polyuria).",
    ghiza: "Barley (Jau) bread, bitter gourd (karela), fenugreek (methi) greens, roasted gram, unsweetened almond milk.",
    parhez: "Zero refined sugar, sweets, potatoes, white rice, mangoes, and daytime post-meal sleeping.",
    medications: [
      { item_name: "Qurs-e-Taqwiyat-e-Quwwat-e-Baah", dose_amount: 2, dose_unit: "hab", frequency: "BD", duration_days: 30, instructions: "Before meals with water" },
      { item_name: "Sharbat Bazoori Motadil", dose_amount: 20, dose_unit: "ml", frequency: "AM", duration_days: 30, instructions: "With water before breakfast" },
      { item_name: "Safoof-e-Qawi-e-Banas", dose_amount: 3, dose_unit: "g", frequency: "BD", duration_days: 30, instructions: "With warm water 30 mins before meals" }
    ]
  },
  hypertension: {
    name: "Zaght-ud-Dam Qawi / Hypertension (P-04)",
    shortName: "⚡ Zaght-ud-Dam (BP)",
    complaint: "Occipital headache, pulsating temples, dizziness, irritability, elevated systolic blood pressure.",
    usul: "Taskeen-e-Hararat wa Tanqiya-e-Dam (Soothe cardiovascular heat, modulate vascular resistance).",
    ghiza: "Bottle gourd (lauki), coriander soup, watermelon seeds, fresh pomegranate juice, strict low-sodium diet.",
    parhez: "Strictly minimize table salt, red meat, pickles, anger/stress, and midnight screen exposure.",
    medications: [
      { item_name: "Safoof-e-Tansiyat-ud-Dam", dose_amount: 3, dose_unit: "g", frequency: "BD", duration_days: 21, instructions: "With fresh water after meals" },
      { item_name: "Khamira Gaozaban Ambari Jawaharwala", dose_amount: 5, dose_unit: "g", frequency: "AM", duration_days: 21, instructions: "Empty stomach in morning" },
      { item_name: "Sharbat Bazoori Motadil", dose_amount: 25, dose_unit: "ml", frequency: "HS", duration_days: 21, instructions: "At bedtime with water" }
    ]
  },
  insomnia: {
    name: "Sahar & Izterab / Insomnia & Stress (P-07)",
    shortName: "🧠 Sahar (Insomnia/Stress)",
    complaint: "Difficulty falling asleep, nocturnal awakenings, racing intrusive thoughts, restlessness, mental fatigue.",
    usul: "Tarteeb-e-Dimagh wa Munawwim (Moisten cerebral tissue, induce restful physiological sleep).",
    ghiza: "Almond milk, pumpkin seeds, poppy seed porridge, lettuce soup, warm cow milk at bedtime.",
    parhez: "Zero caffeine, tea, or stimulating screens after 7 PM; avoid spicy night meals.",
    medications: [
      { item_name: "Itrifal Ustukhuddus", dose_amount: 7, dose_unit: "g", frequency: "HS", duration_days: 21, instructions: "With lukewarm milk at bedtime" },
      { item_name: "Khamira Gaozaban Ambari Jawaharwala", dose_amount: 5, dose_unit: "g", frequency: "AM", duration_days: 21, instructions: "Morning empty stomach with warm milk" },
      { item_name: "Sharbat Bazoori Motadil", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 21, instructions: "Diluted with fresh water" }
    ]
  },
  immunity: {
    name: "Zof-e-Aam & Quwwat / Debility & Immunity (P-19)",
    shortName: "🛡️ Quwwat (Immunity)",
    complaint: "General physical exhaustion, lethargy, recurrent seasonal cold/flu, low stamina and convalescence.",
    usul: "Taqwiyat-e-Aaza-e-Raeesa (Fortify primary organs: brain, heart, liver).",
    ghiza: "Bone broth (Yakhni), dates soaked in milk, figs, soaked almonds, pure honey, seasonal sweet apples.",
    parhez: "Avoid skipping meals, excessive mental strain, fasting without nutrition, and stale fast food.",
    medications: [
      { item_name: "Khamira Gaozaban Ambari Jawaharwala", dose_amount: 5, dose_unit: "g", frequency: "AM", duration_days: 30, instructions: "Morning empty stomach with warm milk" },
      { item_name: "Majoon Falasfa", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 30, instructions: "Bedtime with lukewarm water" },
      { item_name: "Sharbat Faulad", dose_amount: 10, dose_unit: "ml", frequency: "BD", duration_days: 30, instructions: "After meals with water" }
    ]
  },
  pcos: {
    name: "Khuda-e-Rahim & Ehtibas / PCOS & Hormonal (P-14)",
    shortName: "🌸 PCOS & Hormonal",
    complaint: "Irregular delayed menses, facial hirsutism, cystic ovarian changes, pelvic heaviness, weight gain.",
    usul: "Idrar-e-Tams wa Tanqiya-e-Reham (Restore menstrual flow, clear ovarian phlegmatic blockages).",
    ghiza: "Cinnamon herbal infusion, soaked fenugreek seeds, roasted flax seeds, pomegranate, bottle gourd.",
    parhez: "Zero refined sugar, dairy sweets, bakery products, deep-fried snacks, and sedentary habit.",
    medications: [
      { item_name: "Habb-e-Mudir (Abhal Compound)", dose_amount: 2, dose_unit: "hab", frequency: "BD", duration_days: 14, instructions: "With lukewarm water post-meals" },
      { item_name: "Sharbat Deenar", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 14, instructions: "With water before meals" },
      { item_name: "Majoon Dabeedul Ward", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 21, instructions: "Bedtime with warm water" }
    ]
  },
  vitality: {
    name: "Zof-e-Bah & Nuqs-e-Taqat / Male Vitality (P-10)",
    shortName: "🧬 Zof-e-Bah (Vitality)",
    complaint: "Premature emission, lumbar backache, low vigour, performance exhaustion, lack of physical stamina.",
    usul: "Muqawwi-e-Bah wa Mumsik-e-Mani (Tonify reproductive vitality, consolidate seminal retention).",
    ghiza: "Almonds, walnuts, pine nuts (chilgoza), mutton soup with cloves, pure honey, saffron milk.",
    parhez: "Avoid sour foods, spicy street food, excessive tea/caffeine, smoking, and late night sleeping.",
    medications: [
      { item_name: "Majoon Arad Khurma", dose_amount: 10, dose_unit: "g", frequency: "AM", duration_days: 30, instructions: "Morning with 250ml warm milk" },
      { item_name: "Majoon Mughalliz Jawaharwali", dose_amount: 5, dose_unit: "g", frequency: "HS", duration_days: 30, instructions: "Bedtime with warm milk" },
      { item_name: "Qurs-e-Taqwiyat-e-Quwwat-e-Baah", dose_amount: 1, dose_unit: "hab", frequency: "BD", duration_days: 21, instructions: "With milk after meals" }
    ]
  },
  hair_loss: {
    name: "Intishar-e-Sha'ar / Hair Loss & Alopecia (P-21)",
    shortName: "🌿 Hair Loss (Alopecia)",
    complaint: "Excessive hair thinning, telogen shedding, dandruff, itchy scalp, dry brittle roots.",
    usul: "Inbat-e-Sha'ar wa Taqwiyat-e-Usool (Stimulate hair follicles, nourish scalp roots).",
    ghiza: "Black sesame seeds, amla murabba, spinach, soaked walnuts, lentils, fresh carrot juice.",
    parhez: "Avoid chemical shampoos, hot blow dryers, excessive junk food, and hard chlorinated water.",
    medications: [
      { item_name: "Itrifal Shahtara", dose_amount: 7, dose_unit: "g", frequency: "HS", duration_days: 30, instructions: "At bedtime with water (Blood purifier)" },
      { item_name: "Sharbat Anjabar", dose_amount: 20, dose_unit: "ml", frequency: "BD", duration_days: 21, instructions: "With fresh water in morning and evening" },
      { item_name: "Safoof-e-Munbit-e-Sha'r", dose_amount: 3, dose_unit: "g", frequency: "AM", duration_days: 30, instructions: "Morning with water" }
    ]
  }
};

export const CANONICAL_UNANI_DRUGS = [
  { name: "Sharbat Bazoori Motadil", urdu: "شربت بزوری معتدل", form: "SHARBAT", defaultDose: "20 ml BD" },
  { name: "Majoon Arad Khurma", urdu: "معجون آرد خرما", form: "MAJOON", defaultDose: "10 g AM" },
  { name: "Habb-e-Azaarqi", urdu: "حب ازارقی", form: "HAB", defaultDose: "1 hab BD" },
  { name: "Habb-e-Mudir (Abhal Compound)", urdu: "حب مدر", form: "HAB", defaultDose: "2 hab BD" },
  { name: "Jawarish Mastagi", urdu: "جوارش مصطگی", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Jawarish Kamuni", urdu: "جوارش کمونی", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Jawarish Jalinus", urdu: "جوارش جالینوس", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Jawarish Shahi", urdu: "جوارش شاہی", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Majoon Dabeedul Ward", urdu: "معجون دبید الورد", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Majoon Falasfa", urdu: "معجون فلاسفہ", form: "MAJOON", defaultDose: "5 g HS" },
  { name: "Majoon Suranjan", urdu: "معجون سورنجان", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Majoon Chobchini", urdu: "معجون چوب چینی", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Majoon Ushba", urdu: "معجون عشبہ", form: "MAJOON", defaultDose: "5 g BD" },
  { name: "Majoon Mughalliz Jawaharwali", urdu: "معجون مغلظ جواہر والی", form: "MAJOON", defaultDose: "5 g HS" },
  { name: "Itrifal Kishneezi", urdu: "اطریفل کشنیزی", form: "ITRIFAL", defaultDose: "7 g HS" },
  { name: "Itrifal Ustukhuddus", urdu: "اطریفل اسطخودوس", form: "ITRIFAL", defaultDose: "7 g HS" },
  { name: "Itrifal Shahtara", urdu: "اطریفل شاہترہ", form: "ITRIFAL", defaultDose: "7 g HS" },
  { name: "Itrifal Zamani", urdu: "اطریفل زمانی", form: "ITRIFAL", defaultDose: "7 g HS" },
  { name: "Khamira Gaozaban Ambari Jawaharwala", urdu: "خمیرہ گاؤزباں عنبری جواہر والا", form: "KHAMIRA", defaultDose: "5 g AM" },
  { name: "Khamira Marwareed", urdu: "خمیرہ مروارید", form: "KHAMIRA", defaultDose: "3 g AM" },
  { name: "Sharbat Deenar", urdu: "شربت دینار", form: "SHARBAT", defaultDose: "20 ml BD" },
  { name: "Sharbat Faulad", urdu: "شربت فولاد", form: "SHARBAT", defaultDose: "10 ml BD" },
  { name: "Sharbat Anjabar", urdu: "شربت انجبار", form: "SHARBAT", defaultDose: "20 ml BD" },
  { name: "Sharbat Zoofa Murakkab", urdu: "شربت زوفا مرکب", form: "SHARBAT", defaultDose: "10 ml BD" },
  { name: "Habb-e-Suranjan", urdu: "حب سورنجان", form: "HAB", defaultDose: "1 hab BD" },
  { name: "Habb-e-Kabid Naushadri", urdu: "حب کبد نوTrack", form: "HAB", defaultDose: "2 hab BD" },
  { name: "Lauq-e-Sapistan", urdu: "لعوق سپستان", form: "LAUQ", defaultDose: "7 g HS" },
  { name: "Safoof-e-Mohazzil", urdu: "سفوف مہزل", form: "SAFOOF", defaultDose: "3 g AM" }
];

export function renderExpressOpdBar() {
  const pillsHtml = Object.entries(EXPRESS_PROTOCOLS).map(([key, p]) => `
    <button type="button" class="btn btn-secondary btn-sm btn-protocol-pill" data-protocol="${key}" style="font-size: 0.76rem; padding: 0.25rem 0.55rem; border-radius: 20px; font-weight: 600; white-space: nowrap; border: 1px solid #10b981; background: #ffffff; color: #065f46; cursor: pointer; transition: all 0.15s ease;">
      ${p.shortName}
    </button>
  `).join("");

  const datalistHtml = CANONICAL_UNANI_DRUGS.map(d => `
    <option value="${d.name}">${d.urdu} • ${d.form} (${d.defaultDose})</option>
  `).join("");

  return `
    <!-- High-Speed Bedside OPD Protocol Banner -->
    <div id="express-opd-panel" class="card" style="margin-bottom: 0.85rem; padding: 0.85rem 1.15rem; background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%); border: 1.5px solid #10b981; border-radius: var(--matab-radius-lg); box-shadow: var(--matab-shadow-xs);">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.5rem;">
        <div style="display: flex; align-items: center; gap: 0.45rem;">
          <span style="font-size: 1.15rem;">⚡</span>
          <strong style="color: #065f46; font-size: 0.95rem;">Express Bedside OPD Protocol Bundles</strong>
          <span class="badge badge-success" style="background: #10b981; color: #ffffff; font-size: 0.68rem; padding: 0.15rem 0.4rem;">30-SECOND NUSKHA</span>
        </div>
        <div style="font-size: 0.75rem; color: #047857; font-weight: 600;">
          Click any clinical protocol below to auto-fill Complaint, Mizaj, Posology &amp; Parhez instantly.
        </div>
      </div>

      <!-- Protocol Pills Bar (Horizontal Scrollable) -->
      <div style="display: flex; gap: 0.4rem; overflow-x: auto; padding-bottom: 0.35rem; align-items: center;" id="express-protocol-pills">
        ${pillsHtml}
      </div>

      <!-- Quick Fast Search Box with Enter-to-Add -->
      <div style="display: flex; gap: 0.5rem; align-items: center; margin-top: 0.55rem; padding-top: 0.45rem; border-top: 1px dashed #a7f3d0;">
        <span style="font-size: 0.8rem; font-weight: 700; color: #065f46; white-space: nowrap;">⚡ Fast Drug Lookup:</span>
        <input type="text" id="fast-drug-lookup-input" list="canonical-unani-drugs" class="form-control" placeholder="Type medicine in Urdu or English (e.g., 'Dabeedul Ward', 'جوارش', 'Kamuni') and press Enter..." style="font-size: 0.8rem; padding: 0.3rem 0.65rem; background: #ffffff; border: 1px solid #6ee7b7; border-radius: 6px; flex: 1;" />
        <button type="button" id="btn-fast-add-drug" class="btn btn-primary btn-sm" style="font-size: 0.78rem; padding: 0.3rem 0.75rem; background: #059669; border: none; font-weight: 700;">+ Add to Nuskha</button>
      </div>

      <!-- Canonical Datalist Definition for Native Autocomplete -->
      <datalist id="canonical-unani-drugs">
        ${datalistHtml}
      </datalist>
    </div>
  `;
}

export function applyExpressProtocol(key, addNuskhaRowFn, triggerAutosaveFn) {
  const protocol = EXPRESS_PROTOCOLS[key];
  if (!protocol) return;

  // 1. Set Chief Complaint
  const complaintEl = document.getElementById("input-chief-complaint");
  if (complaintEl) complaintEl.value = protocol.complaint;

  // 2. Set Usul-e-Ilaj Principle
  const usulEl = document.getElementById("input-plan-principle");
  if (usulEl) usulEl.value = protocol.usul;

  // 3. Set Ghiza (Diet)
  const ghizaEl = document.getElementById("input-ghiza-diet");
  if (ghizaEl) ghizaEl.value = protocol.ghiza;

  // 4. Set Parhez (Dietary Restrictions)
  const parhezEl = document.getElementById("input-parhez-avoid");
  if (parhezEl) parhezEl.value = protocol.parhez;

  // 5. Populate Nuskha Posology Table
  const tbody = document.getElementById("tbody-nuskha-items");
  if (tbody && typeof addNuskhaRowFn === "function") {
    tbody.innerHTML = ""; // Clear existing rows
    protocol.medications.forEach(med => {
      addNuskhaRowFn(med);
    });
  }

  // 6. Trigger Concurrency Autosave
  if (typeof triggerAutosaveFn === "function") {
    triggerAutosaveFn();
  }

  // 7. Auto-run Preflight Safety Check
  if (typeof window.runPreflightCheck === "function") {
    window.runPreflightCheck();
  }

  if (window.showToast) {
    window.showToast(`⚡ 1-Click Protocol Applied: ${protocol.name}`, "success", 3000);
  }
}

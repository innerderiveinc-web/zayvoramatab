/**
 * ZAYVORA MATAB OS — Consultation Assessment Sub-module
 * Sub-module: consultation-assessment.js
 * 
 * Manages:
 * - 4 Classical 1-Click Nabz Presets (Damawi, Safrawi, Balghami, Saudawi)
 * - 4 Classical 1-Click Baul Presets
 * - 10-Ajnas Pulse Calculator
 * - 12-Organ Axis Diagnostic Profiler & Scoring (0-5)
 * - Modern Vital Signs & Automatic BMI Calculation
 */

export function applyNabzPreset(mizaj) {
  const suratEl = document.getElementById("tashkhees-nabz-surat");
  const quwwatEl = document.getElementById("tashkhees-nabz-quwwat");
  const lamsEl = document.getElementById("tashkhees-nabz-lams");
  const imtilaEl = document.getElementById("tashkhees-nabz-imtila");
  const hararatEl = document.getElementById("tashkhees-nabz-hararat");
  const rhythmEl = document.getElementById("tashkhees-nabz-rhythm");
  const dominantMizajEl = document.getElementById("input-unani-mizaj") || document.getElementById("select-dominant-mizaj");

  if (mizaj === "DAMAWI") {
    if (suratEl) suratEl.value = "SAREE";
    if (quwwatEl) quwwatEl.value = "QAWI";
    if (lamsEl) lamsEl.value = "MOTADIL";
    if (imtilaEl) imtilaEl.value = "MUMTALI";
    if (hararatEl) hararatEl.value = "HAR";
    if (rhythmEl) rhythmEl.value = "MUNAZZAM";
    if (dominantMizajEl) dominantMizajEl.value = "DAMAWWI";
  } else if (mizaj === "SAFRAWI") {
    if (suratEl) suratEl.value = "SAREE";
    if (quwwatEl) quwwatEl.value = "QAWI";
    if (lamsEl) lamsEl.value = "SULB";
    if (imtilaEl) imtilaEl.value = "MOTADIL";
    if (hararatEl) hararatEl.value = "HAR";
    if (rhythmEl) rhythmEl.value = "MUNAZZAM";
    if (dominantMizajEl) dominantMizajEl.value = "SAFRAWI";
  } else if (mizaj === "BALGHAMI") {
    if (suratEl) suratEl.value = "BATEE";
    if (quwwatEl) quwwatEl.value = "DHAEF";
    if (lamsEl) lamsEl.value = "LAYYIN";
    if (imtilaEl) imtilaEl.value = "MUMTALI";
    if (hararatEl) hararatEl.value = "BARID";
    if (rhythmEl) rhythmEl.value = "MUNAZZAM";
    if (dominantMizajEl) dominantMizajEl.value = "BALGHAMI";
  } else if (mizaj === "SAUDAWI") {
    if (suratEl) suratEl.value = "BATEE";
    if (quwwatEl) quwwatEl.value = "DHAEF";
    if (lamsEl) lamsEl.value = "SULB";
    if (imtilaEl) imtilaEl.value = "KHALI";
    if (hararatEl) hararatEl.value = "BARID";
    if (rhythmEl) rhythmEl.value = "GHAIR_MUNAZZAM";
    if (dominantMizajEl) dominantMizajEl.value = "SAUDAWI";
  }

  // Update Express status display if present
  const expressMizajBadge = document.getElementById("express-selected-mizaj");
  if (expressMizajBadge) {
    expressMizajBadge.innerText = `Mizaj: ${mizaj}`;
    expressMizajBadge.className = `badge badge-${mizaj.toLowerCase()}`;
  }

  if (window.triggerAutosave) window.triggerAutosave();
  if (window.showToast) window.showToast(`Applied 1-Click Nabz Preset: ${mizaj}`, "success", 1500);
}

export function applyBaulPreset(mizaj) {
  const lawnEl = document.getElementById("tashkhees-baul-lawn");
  const qiwamEl = document.getElementById("tashkhees-baul-qiwam");
  const safaEl = document.getElementById("tashkhees-baul-safa");
  const rasubEl = document.getElementById("tashkhees-baul-rasub");

  if (mizaj === "DAMAWI") {
    if (lawnEl) lawnEl.value = "AHMAR";
    if (qiwamEl) qiwamEl.value = "GHALEEZ";
    if (safaEl) safaEl.value = "MUKADDAR";
    if (rasubEl) rasubEl.value = "KUDOORAT";
  } else if (mizaj === "SAFRAWI") {
    if (lawnEl) lawnEl.value = "ASFAR_NARI";
    if (qiwamEl) qiwamEl.value = "RAQEEQ";
    if (safaEl) safaEl.value = "SAAF";
    if (rasubEl) rasubEl.value = "RASUB_LATEEF";
  } else if (mizaj === "BALGHAMI") {
    if (lawnEl) lawnEl.value = "ABYAD";
    if (qiwamEl) qiwamEl.value = "RAQEEQ";
    if (safaEl) safaEl.value = "SAAF";
    if (rasubEl) rasubEl.value = "RASUB_ABYAD";
  } else if (mizaj === "SAUDAWI") {
    if (lawnEl) lawnEl.value = "ASWAD";
    if (qiwamEl) qiwamEl.value = "GHALEEZ";
    if (safaEl) safaEl.value = "MUKADDAR";
    if (rasubEl) rasubEl.value = "RASUB_GHALEEZ";
  }
  if (window.triggerAutosave) window.triggerAutosave();
  if (window.showToast) window.showToast(`Applied Baul Preset: ${mizaj}`, "info", 1500);
}

export function calculateBMI() {
  const wtEl = document.getElementById("vital-weight") || document.getElementById("input-vital-weight");
  const htEl = document.getElementById("vital-height") || document.getElementById("input-vital-height");
  const bmiBadge = document.getElementById("badge-vitals-bmi");
  const bmiEl = document.getElementById("input-vital-bmi");
  const catEl = document.getElementById("vital-bmi-category");
  if (!wtEl || !htEl) return;

  const wt = parseFloat(wtEl.value);
  const htCm = parseFloat(htEl.value);

  if (wt > 0 && htCm > 0) {
    const htM = htCm / 100;
    const bmi = (wt / (htM * htM)).toFixed(1);
    if (bmiEl) bmiEl.value = bmi;

    let cat = "Normal";
    let color = "#166534";
    if (bmi < 18.5) { cat = "Underweight"; color = "#854d0e"; }
    else if (bmi >= 25 && bmi < 30) { cat = "Overweight"; color = "#ea580c"; }
    else if (bmi >= 30) { cat = "Obese"; color = "#dc2626"; }

    if (bmiBadge) {
      bmiBadge.innerText = `BMI: ${bmi} (${cat})`;
      bmiBadge.style.color = color;
      bmiBadge.style.fontWeight = "700";
    }
    if (catEl) {
      catEl.innerText = cat;
      catEl.style.color = color;
      catEl.style.fontWeight = "600";
    }
  }
}

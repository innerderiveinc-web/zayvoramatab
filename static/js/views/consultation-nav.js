/**
 * ZAYVORA MATAB OS — Consultation Navigation & Mode Orchestrator
 * Sub-module: consultation-nav.js
 * 
 * Manages:
 * - Express OPD Mode (60s fast track) vs Comprehensive In-Depth Investigation
 * - Sticky Quick-Nav & smooth section scrolling
 * - Accordion state (Expand All / Collapse All)
 * - Bedside Context Drawer toggle
 */

export let consultationMode = "EXPRESS"; // Default to high-speed OPD mode for busy clinics

export function setConsultationMode(mode) {
  consultationMode = mode;
  const expressBar = document.getElementById("express-opd-panel");
  const quickNav = document.getElementById("quick-nav-bar");
  const btnExpress = document.getElementById("btn-mode-express");
  const btnComp = document.getElementById("btn-mode-comprehensive");

  if (mode === "EXPRESS") {
    if (expressBar) expressBar.style.display = "block";
    if (btnExpress) {
      btnExpress.style.background = "#059669";
      btnExpress.style.color = "#ffffff";
      btnExpress.style.fontWeight = "700";
    }
    if (btnComp) {
      btnComp.style.background = "transparent";
      btnComp.style.color = "var(--matab-color-text-secondary)";
      btnComp.style.fontWeight = "normal";
    }
    // In express mode: collapse non-urgent deep sections (History, Labs, Imaging, Safety)
    const secondarySections = ["history_observations", "biomedical_labs", "radiodiagnosis", "safety_review"];
    secondarySections.forEach(secKey => {
      const card = document.getElementById(`card-sec-${secKey}`);
      if (card) card.style.display = "none";
    });
    // Ensure primary sections are visible
    ["visit", "unani_assessment", "plan_nuskha", "finalize"].forEach(secKey => {
      const card = document.getElementById(`card-sec-${secKey}`);
      const body = document.getElementById(`body-sec-${secKey}`);
      if (card) card.style.display = "block";
      if (body) body.style.display = "block";
    });
    if (window.showToast) window.showToast("⚡ Switched to Express OPD Mode (60s Streamlined)", "success", 2000);
  } else {
    // COMPREHENSIVE MODE: Show all 9 sections
    if (expressBar) expressBar.style.display = "none";
    if (btnComp) {
      btnComp.style.background = "#0284c7";
      btnComp.style.color = "#ffffff";
      btnComp.style.fontWeight = "700";
    }
    if (btnExpress) {
      btnExpress.style.background = "transparent";
      btnExpress.style.color = "var(--matab-color-text-secondary)";
      btnExpress.style.fontWeight = "normal";
    }
    const allSections = ["visit", "history_observations", "unani_assessment", "modern_assessment", "biomedical_labs", "radiodiagnosis", "plan_nuskha", "safety_review", "finalize"];
    allSections.forEach(secKey => {
      const card = document.getElementById(`card-sec-${secKey}`);
      const body = document.getElementById(`body-sec-${secKey}`);
      if (card) card.style.display = "block";
      if (body) body.style.display = "block";
    });
    if (window.showToast) window.showToast("🔬 Switched to Comprehensive Mode (9 Deep Investigation Sections)", "info", 2000);
  }
}

export function scrollToSection(secKey) {
  const card = document.getElementById(`card-sec-${secKey}`);
  const body = document.getElementById(`body-sec-${secKey}`);
  const icon = document.getElementById(`icon-sec-${secKey}`);
  if (card) {
    if (card.style.display === "none") card.style.display = "block";
    if (body && body.style.display === "none") {
      body.style.display = "block";
      if (icon) icon.innerText = "▼";
    }
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

export function toggleAllSections(expand) {
  const allCards = ["visit", "history_observations", "unani_assessment", "modern_assessment", "biomedical_labs", "radiodiagnosis", "plan_nuskha", "safety_review", "finalize"];
  allCards.forEach(secKey => {
    const card = document.getElementById(`card-sec-${secKey}`);
    const body = document.getElementById(`body-sec-${secKey}`);
    const icon = document.getElementById(`icon-sec-${secKey}`);
    if (card && card.style.display !== "none" && body) {
      body.style.display = expand ? "block" : "none";
      if (icon) icon.innerText = expand ? "▼" : "▶";
    }
  });
}

export function toggleSection(secKey) {
  const body = document.getElementById(`body-sec-${secKey}`);
  const icon = document.getElementById(`icon-sec-${secKey}`);
  if (!body) return;
  const isHidden = body.style.display === "none";
  body.style.display = isHidden ? "block" : "none";
  if (icon) icon.innerText = isHidden ? "▼" : "▶";
}

export function toggleContextDrawer() {
  const drawer = document.getElementById("context-drawer-panel");
  const grid = document.getElementById("workspace-grid");
  if (!drawer || !grid) return;
  if (drawer.style.display === "none") {
    drawer.style.display = "flex";
    grid.style.gridTemplateColumns = "minmax(0, 1fr) 350px";
  } else {
    drawer.style.display = "none";
    grid.style.gridTemplateColumns = "minmax(0, 1fr)";
  }
}

export function applyQuickChiefComplaint(complaintText) {
  const inp = document.getElementById("input-reason-visit");
  if (inp) {
    inp.value = complaintText;
    inp.dispatchEvent(new Event("input", { bubbles: true }));
  }
  if (window.showToast) window.showToast(`Selected: ${complaintText}`, "info", 1500);
}

export function appendQuickText(targetInputId, text) {
  const inp = document.getElementById(targetInputId);
  if (!inp) return;
  const current = (inp.value || "").trim();
  if (current) {
    if (!current.includes(text)) {
      inp.value = `${current} • ${text}`;
    }
  } else {
    inp.value = text;
  }
  inp.dispatchEvent(new Event("input", { bubbles: true }));
  if (window.showToast) window.showToast(`Added: ${text}`, "info", 1200);
}

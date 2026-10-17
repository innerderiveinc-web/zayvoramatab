/**
 * ZAYVORA MATAB OS — Consultation Prescription & Dispensing Sub-module
 * Sub-module: consultation-rx.js
 * 
 * Manages:
 * - Bilingual Prescription Printing: A4 Letterhead & 80mm Thermal Receipt Slip
 * - 1-Click WhatsApp Rx Transmission
 * - Quick Days Supply Presets (7, 14, 30 Days)
 * - Raw Herb Inventory Validation & Reorder Alerts
 */

export let currentPrintFormat = "A4"; // "A4" or "THERMAL"

export function setPrintFormat(format) {
  currentPrintFormat = format;
  const btnA4 = document.getElementById("btn-print-fmt-a4");
  const btnThermal = document.getElementById("btn-print-fmt-thermal");
  const previewBox = document.getElementById("printable-rx-content");

  if (format === "THERMAL") {
    if (btnThermal) {
      btnThermal.style.background = "#0f766e";
      btnThermal.style.color = "#ffffff";
    }
    if (btnA4) {
      btnA4.style.background = "transparent";
      btnA4.style.color = "#475569";
    }
    if (previewBox) {
      previewBox.style.maxWidth = "360px";
      previewBox.style.margin = "0 auto";
      previewBox.style.border = "1px dashed #94a3b8";
      previewBox.style.fontSize = "0.78rem";
    }
    document.body.classList.remove("print-mode-a4");
    document.body.classList.add("print-mode-thermal");
  } else {
    if (btnA4) {
      btnA4.style.background = "#0f766e";
      btnA4.style.color = "#ffffff";
    }
    if (btnThermal) {
      btnThermal.style.background = "transparent";
      btnThermal.style.color = "#475569";
    }
    if (previewBox) {
      previewBox.style.maxWidth = "100%";
      previewBox.style.margin = "0";
      previewBox.style.border = "2px solid #0f766e";
      previewBox.style.fontSize = "0.82rem";
    }
    document.body.classList.remove("print-mode-thermal");
    document.body.classList.add("print-mode-a4");
  }
}

export function printPrescriptionDocument(format) {
  const chosenFormat = format || currentPrintFormat;
  setPrintFormat(chosenFormat);
  setTimeout(() => {
    window.print();
  }, 100);
}

export function applyQuickDuration(days) {
  const durInputs = document.querySelectorAll("#tbody-nuskha-items tr td:nth-child(5) input");
  durInputs.forEach(inp => {
    inp.value = days;
    inp.dispatchEvent(new Event("input", { bubbles: true }));
  });
  if (window.showToast) window.showToast(`Set duration to ${days} Days for all items`, "info", 1500);
}

export function sendWhatsAppRx() {
  const patName = document.getElementById("banner-patient-name")?.innerText || "Patient";
  const patMrn = document.getElementById("banner-patient-mrn")?.innerText || "";
  const diagnosis = document.getElementById("input-diagnosis-primary")?.value || "General Consultation";
  const mizaj = document.getElementById("input-unani-mizaj")?.value || document.getElementById("select-dominant-mizaj")?.value || "Normal";
  const usul = document.getElementById("input-plan-principle")?.value || "";
  const ghiza = document.getElementById("input-ghiza-diet")?.value || "Normal balanced diet";
  const parhez = document.getElementById("input-parhez-avoid")?.value || "Avoid sour, excessively spicy, and stale foods";

  // Gather medicines
  const rxRows = [];
  const rows = document.querySelectorAll("#tbody-nuskha-items tr");
  rows.forEach((tr, i) => {
    const itemInp = tr.querySelector("td:nth-child(2) input");
    const doseInp = tr.querySelector("td:nth-child(3) input");
    const unitSel = tr.querySelector("td:nth-child(3) select");
    const freqSel = tr.querySelector("td:nth-child(4) select");
    const durInp = tr.querySelector("td:nth-child(5) input");
    const vehInp = tr.querySelector("td:nth-child(6) input");

    if (itemInp && itemInp.value.trim()) {
      rxRows.push({
        num: i + 1,
        name: (itemInp.value.trim()).replace(/\s*\((?:Qarabadi?n|Qarabadeeni|Classical)\)/gi, "").trim(),
        dose: `${doseInp?.value || '1'} ${unitSel?.value || 'g'}`,
        freq: freqSel?.value || 'BD',
        dur: `${durInp?.value || '14'}d`,
        vehicle: vehInp?.value || 'Water / Arq'
      });
    }
  });

  const medList = rxRows.map(r => `  ${r.num}. *${r.name}* — ${r.dose} (${r.freq}) for ${r.dur} [with ${r.vehicle}]`).join("\n");

  const todayStr = new Date().toLocaleDateString();

  const publicUrl = (localStorage.getItem('MATAB_PUBLIC_URL') || '').trim();
  const isLocalhost = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1');
  let recoverySection = "";
  if (publicUrl) {
    recoverySection = `📲 *Patient Recovery & Relief Check (PROMs):*\nRate your recovery online:\n${publicUrl.replace(/\/$/, '')}/proms?mrn=${patMrn || 'WALK-IN'}\n`;
  } else if (!isLocalhost) {
    recoverySection = `📲 *Patient Recovery & Relief Check (PROMs):*\nRate your recovery online:\n${window.location.origin}/proms?mrn=${patMrn || 'WALK-IN'}\n`;
  } else {
    recoverySection = `🏥 *Patient Feedback:* Recovery rating recorded at clinic reception desk during follow-up.\n`;
  }

  const msg = 
`🌿 *ZAYVORA MATAB CLINICAL OS* 🌿
*Prescription & Care Summary*
-------------------------------------
*Patient:* ${patName} (${patMrn})
*Date:* ${todayStr}
*Mizaj:* ${mizaj} | *Diagnosis:* ${diagnosis}

💊 *PRESCRIBED MEDICINES:*
${medList || "  (Routine regimen)"}

🥣 *RECOMMENDED DIET:*
${ghiza}

🚫 *FOODS STRICTLY AVOIDED (PARHEZ):*
${parhez}

🗓️ *Follow-up:* After 14 days
${recoverySection}-------------------------------------
*Matab Contact:* +91 9876543210
_Generated via Zayvora Matab OS — Authenticated Prescription_`;

  // Prompt for phone number or default
  let phone = prompt("Enter Patient WhatsApp Mobile Number (with country code, e.g. 919876543210):", "91");
  if (!phone) return;
  phone = phone.replace(/[^0-9]/g, "");
  if (phone.length < 10) {
    alert("Please enter a valid phone number with country code.");
    return;
  }

  const encoded = encodeURIComponent(msg);
  const waUrl = `https://wa.me/${phone}?text=${encoded}`;
  window.open(waUrl, "_blank");
  if (window.showToast) window.showToast("WhatsApp Prescription Generated!", "success", 2500);
}

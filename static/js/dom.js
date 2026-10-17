/**
 * ZAYVORA MATAB OS — Defensive DOM Helper Utility
 * Prevents silent runtime failures, provides safe element lookups, and guards against ID drift.
 */

export function $(id) {
  return document.getElementById(id);
}

export function $val(id, defaultVal = "") {
  const el = document.getElementById(id);
  if (!el) return defaultVal;
  return el.value !== undefined ? el.value : el.innerText;
}

export function $setVal(id, val) {
  const el = document.getElementById(id);
  if (!el) return false;
  if (el.value !== undefined) {
    el.value = val;
  } else {
    el.innerText = val;
  }
  el.dispatchEvent(new Event("input", { bubbles: true }));
  return true;
}

export function $show(id, display = "block") {
  const el = document.getElementById(id);
  if (el) el.style.display = display;
}

export function $hide(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = "none";
}

export function $text(id, text) {
  const el = document.getElementById(id);
  if (el) el.innerText = text;
}

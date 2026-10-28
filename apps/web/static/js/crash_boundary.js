/**
 * ZAYVORA MATAB OS — Global Frontend Crash Boundary & Diagnostics
 * 
 * Intercepts uncaught JavaScript errors and unhandled Promise rejections.
 * Prevents white-screen crashes, maintains a rolling diagnostics log in localStorage,
 * and renders non-blocking recovery toasts.
 */

(function () {
  const MAX_LOGS = 25;
  const STORAGE_KEY = "matab_crash_telemetry";

  function logCrash(type, details) {
    try {
      const entry = {
        type: type,
        message: details.message || String(details),
        source: details.filename || details.source || "unknown",
        lineno: details.lineno || null,
        colno: details.colno || null,
        stack: details.error ? details.error.stack : (details.reason ? details.reason.stack : null),
        url: window.location.href,
        timestamp: new Date().toISOString()
      };

      console.warn(`[MATAB CRASH BOUNDARY] Intercepted ${type}:`, entry);

      let logs = [];
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) logs = JSON.parse(raw);
      } catch (e) {
        logs = [];
      }

      logs.unshift(entry);
      if (logs.length > MAX_LOGS) logs = logs.slice(0, MAX_LOGS);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(logs));

      // Show non-intrusive warning if toast system is ready
      if (typeof window.showToast === "function") {
        const shortMsg = (entry.message || "An unexpected script error occurred.").substring(0, 100);
        window.showToast(`🛡️ Handled minor UI exception: ${shortMsg}`, "warning", 4000);
      }
    } catch (telemetryErr) {
      console.error("Crash boundary logger failed:", telemetryErr);
    }
  }

  // 1. Uncaught Synchronous Exceptions
  window.addEventListener("error", function (event) {
    if (!event) return;
    // Suppress benign resize observer loop errors
    if (event.message && event.message.includes("ResizeObserver")) return;

    logCrash("UNCAUGHT_ERROR", {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: event.error
    });
  });

  // 2. Unhandled Promise Rejections (e.g. Network drops, async failures)
  window.addEventListener("unhandledrejection", function (event) {
    if (!event) return;
    logCrash("UNHANDLED_REJECTION", {
      message: event.reason ? (event.reason.message || String(event.reason)) : "Promise rejected without reason",
      reason: event.reason
    });
  });

  // Expose global diagnostics inspect/clear for debugging
  window.__MATAB_DIAGNOSTICS__ = {
    getLogs: function () {
      try {
        return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      } catch {
        return [];
      }
    },
    clearLogs: function () {
      localStorage.removeItem(STORAGE_KEY);
      console.log("[MATAB CRASH BOUNDARY] Telemetry logs cleared.");
    }
  };
})();

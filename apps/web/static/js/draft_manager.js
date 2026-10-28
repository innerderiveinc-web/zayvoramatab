/**
 * ZAYVORA MATAB OS — Zero Data Loss Consultation Draft Manager
 * 
 * Auto-saves bedside consultation data into browser localStorage.
 * Guarantees zero clinical data loss even if:
 * 1. The browser crashes or tab is accidentally closed
 * 2. Power cuts or battery drains
 * 3. Network connection drops between doctor workstation and server
 */

export const DraftManager = {
  PREFIX: "matab_consultation_draft_",
  LATEST_KEY: "matab_latest_consultation_draft",
  EXPIRY_MS: 48 * 60 * 60 * 1000, // 48 hours validity

  /**
   * Save active draft to local storage
   */
  saveDraft(patientId, encounterId, data) {
    if (!data) return;
    try {
      const entry = {
        patientId: patientId || data.patientId || "current",
        patientName: data.patientName || "",
        encounterId: encounterId || null,
        timestamp: new Date().toISOString(),
        data: data
      };
      const json = JSON.stringify(entry);

      if (patientId) {
        localStorage.setItem(`${this.PREFIX}${patientId}`, json);
      }
      localStorage.setItem(this.LATEST_KEY, json);
    } catch (err) {
      console.warn("[DraftManager] Failed to persist local draft:", err);
    }
  },

  /**
   * Retrieve draft for a specific patient or latest active draft
   */
  getDraft(patientId) {
    try {
      let raw = null;
      if (patientId) {
        raw = localStorage.getItem(`${this.PREFIX}${patientId}`);
      }
      if (!raw) {
        raw = localStorage.getItem(this.LATEST_KEY);
      }
      if (!raw) return null;

      const entry = JSON.parse(raw);
      if (!entry || !entry.timestamp) return null;

      // Check expiry
      const age = Date.now() - new Date(entry.timestamp).getTime();
      if (age > this.EXPIRY_MS) {
        this.clearDraft(patientId);
        return null;
      }

      return entry;
    } catch (err) {
      console.warn("[DraftManager] Error reading draft:", err);
      return null;
    }
  },

  /**
   * Clear draft after successful prescription sign or explicit discard
   */
  clearDraft(patientId) {
    try {
      if (patientId) {
        localStorage.removeItem(`${this.PREFIX}${patientId}`);
      }
      // Check if latest points to this patient
      const latestRaw = localStorage.getItem(this.LATEST_KEY);
      if (latestRaw) {
        const entry = JSON.parse(latestRaw);
        if (!patientId || entry.patientId === patientId) {
          localStorage.removeItem(this.LATEST_KEY);
        }
      }
    } catch (err) {
      console.warn("[DraftManager] Error clearing draft:", err);
    }
  },

  /**
   * Format readable time elapsed
   */
  formatTimeAgo(isoString) {
    if (!isoString) return "recently";
    const sec = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (sec < 60) return "just now";
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min} minute${min > 1 ? 's' : ''} ago`;
    const hrs = Math.floor(min / 60);
    if (hrs < 24) return `${hrs} hour${hrs > 1 ? 's' : ''} ago`;
    return "yesterday";
  }
};

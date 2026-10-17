/**
 * Central State Store for MATAB OS Shell
 * Global reactive singleton with persistent localStorage hydration.
 */

if (!window.__MATAB_STATE__) {
  let initialUser = null;
  try {
    const raw = localStorage.getItem("matab_user");
    if (raw) initialUser = JSON.parse(raw);
  } catch (e) {}

  window.__MATAB_STATE__ = {
    user: initialUser,
    activeTab: localStorage.getItem("matab_active_tab") || "today",
    activePatientId: null,
    activeEncounterId: null,
    activeFacilityId: initialUser?.active_facility_id || null,
    capabilities: [],
    listeners: [],

    subscribe(fn) {
      this.listeners.push(fn);
      return () => {
        this.listeners = this.listeners.filter(l => l !== fn);
      };
    },

    notify() {
      this.listeners.forEach(fn => fn(this));
    },

    setUser(user) {
      this.user = user;
      this.activeFacilityId = user?.active_facility_id || null;
      try {
        if (user) {
          localStorage.setItem("matab_user", JSON.stringify(user));
        } else {
          localStorage.removeItem("matab_user");
        }
      } catch (e) {}
      this.notify();
    },

    setActiveTab(tab) {
      this.activeTab = tab;
      try {
        if (tab) localStorage.setItem("matab_active_tab", tab);
      } catch (e) {}
      this.notify();
    },

    setActiveFacility(facilityId) {
      this.activeFacilityId = facilityId;
      this.notify();
    },

    setActiveEncounter(patientId, encounterId) {
      this.activePatientId = patientId;
      this.activeEncounterId = encounterId;
      this.notify();
    },

    setCapabilities(caps) {
      this.capabilities = caps;
      this.notify();
    }
  };
}

export const state = window.__MATAB_STATE__;


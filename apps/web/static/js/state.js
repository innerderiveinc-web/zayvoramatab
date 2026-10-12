/**
 * Central State Store for MATAB OS Shell
 */

export const state = {
  user: null,
  activeTab: "today",
  activePatientId: null,
  activeEncounterId: null,
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
    this.notify();
  },

  setActiveTab(tab) {
    this.activeTab = tab;
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

// ZAYVORA MATAB OS — Central Reactive Application State Store

export const state = {
  user: null,
  activeTab: "today",
  activeEncounter: null,
  activePatient: null,
  currentLang: localStorage.getItem("matab_lang") || "en",
  listeners: [],

  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  },

  notify() {
    this.listeners.forEach(l => l(this));
  },

  setUser(user) {
    this.user = user;
    this.notify();
  },

  setActiveTab(tab) {
    this.activeTab = tab;
    this.notify();
  },

  setLanguage(lang) {
    this.currentLang = lang;
    localStorage.setItem("matab_lang", lang);
    this.notify();
  },

  setActiveEncounter(enc) {
    this.activeEncounter = enc;
    this.notify();
  },

  setActivePatient(pat) {
    this.activePatient = pat;
    this.notify();
  }
};

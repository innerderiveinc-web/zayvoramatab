/**
 * Client-Side Localization & Internationalization (i18n) Engine — Prompt 51.
 * Supports English (en), Urdu RTL (ur), and Hindi (hi).
 */

class I18nManager {
  constructor() {
    this.currentLocale = localStorage.getItem("matab_locale") || "en";
    this.catalogs = {
      en: {
        app_title: "ZAYVORA MATAB OS",
        sign_out: "Sign Out",
        consultation: "Clinical Consultation",
        prescriptions: "Prescriptions",
        patients: "Patients",
        inventory: "Inventory",
        billing: "Billing",
        followups: "Follow-ups",
        today: "Today",
        skip_to_content: "Skip to main content",
        language_selector: "Select Language",
        critical_safety_alert: "CRITICAL SAFETY HARD STOP: Prescribing unpurified toxic botanical is forbidden."
      },
      ur: {
        app_title: "زیوورا مطب او ایس",
        sign_out: "خروج",
        consultation: "طبی معائنہ و مشورہ",
        prescriptions: "نسخہ جات",
        patients: "مریض",
        inventory: "ادویہ و اسٹاک",
        billing: "بلنگ و رسیدات",
        followups: "نگہداشت و فالو اپ",
        today: "آج کے کام",
        skip_to_content: "براہِ راست مرکزی متن پر جائیں",
        language_selector: "زبان منتخب کریں",
        critical_safety_alert: "انتباہِ شدید: غیر مدبر زہریلی دوا کا نسخہ لکھنا قطعی طور پر ممنوع ہے۔"
      },
      hi: {
        app_title: "ज़ैवोرا मतब ओएस",
        sign_out: "लॉग आउट",
        consultation: "चिकित्सीय परामर्श",
        prescriptions: "नुस्खे",
        patients: "रोगी",
        inventory: "औषधि भंडार",
        billing: "बिलिंग व रसीद",
        followups: "अनुवर्ती देखभाल",
        today: "आज का कार्य",
        skip_to_content: "मुख्य सामग्री पर जाएं",
        language_selector: "भाषा चुनें",
        critical_safety_alert: "गंभीर सुरक्षा रोक: बिना शोधित (अमुदब्बर) विषैली औषधि लिखना पूर्णतः वर्जित है।"
      }
    };
    this.subscribers = [];
  }

  getLocale() {
    return this.currentLocale;
  }

  isRTL() {
    return this.currentLocale === "ur";
  }

  setLocale(locale) {
    if (!["en", "ur", "hi"].includes(locale)) return;
    this.currentLocale = locale;
    localStorage.setItem("matab_locale", locale);

    // Apply document-level language & direction
    document.documentElement.lang = locale;
    document.documentElement.dir = this.isRTL() ? "rtl" : "ltr";

    this.notifySubscribers();
  }

  subscribe(callback) {
    this.subscribers.push(callback);
    return () => {
      this.subscribers = this.subscribers.filter(fn => fn !== callback);
    };
  }

  notifySubscribers() {
    this.subscribers.forEach(cb => {
      try {
        cb(this.currentLocale);
      } catch (e) {
        console.error("i18n subscriber error", e);
      }
    });
  }

  t(key, defaultText = "", params = {}) {
    const localeStrings = this.catalogs[this.currentLocale] || this.catalogs.en;
    let text = localeStrings[key] || this.catalogs.en[key] || defaultText || key;

    for (const [k, v] of Object.entries(params)) {
      text = text.replace(new RegExp(`{${k}}`, "g"), v);
    }
    return text;
  }

  formatDate(dateInput, options = { year: "numeric", month: "short", day: "numeric" }) {
    if (!dateInput) return "";
    const date = typeof dateInput === "string" ? new Date(dateInput) : dateInput;
    try {
      const loc = this.currentLocale === "ur" ? "ur-PK" : (this.currentLocale === "hi" ? "hi-IN" : "en-IN");
      return new Intl.DateTimeFormat(loc, options).format(date);
    } catch (e) {
      return date.toLocaleDateString();
    }
  }

  formatNumber(number, options = {}) {
    if (number === null || number === undefined || isNaN(number)) return "";
    try {
      const loc = this.currentLocale === "ur" ? "ur-PK" : (this.currentLocale === "hi" ? "hi-IN" : "en-IN");
      return new Intl.NumberFormat(loc, options).format(number);
    } catch (e) {
      return String(number);
    }
  }

  formatCurrency(amount) {
    if (amount === null || amount === undefined || isNaN(amount)) return "₹0.00";
    try {
      const loc = this.currentLocale === "ur" ? "ur-PK" : (this.currentLocale === "hi" ? "hi-IN" : "en-IN");
      return new Intl.NumberFormat(loc, { style: "currency", currency: "INR" }).format(amount);
    } catch (e) {
      return `₹${Number(amount).toFixed(2)}`;
    }
  }

  isolateLtr(text) {
    if (!text) return "";
    return `<bdi class="bdi-token">${text}</bdi>`;
  }
}

export const i18n = new I18nManager();

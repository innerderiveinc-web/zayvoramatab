// ZAYVORA MATAB OS — API Client Module

const API_BASE = "";

export const api = {
  getToken() {
    return localStorage.getItem("matab_token") || "";
  },

  setToken(token) {
    if (token) {
      localStorage.setItem("matab_token", token);
    } else {
      localStorage.removeItem("matab_token");
    }
  },

  async request(method, path, body = null) {
    const headers = {
      "Content-Type": "application/json"
    };
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const options = {
      method,
      headers
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(`${API_BASE}${path}`, options);
      const data = await response.json().catch(() => ({}));
      
      if (!response.ok) {
        if (response.status === 401 && !path.includes("/auth/login")) {
          this.setToken("");
          window.location.reload();
        }
        const error = new Error(data.message || `HTTP ${response.status}`);
        error.code = data.code || "REQUEST_FAILED";
        error.details = data.details || {};
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (err) {
      console.error(`API Error on ${method} ${path}:`, err);
      throw err;
    }
  },

  get(path) { return this.request("GET", path); },
  post(path, body) { return this.request("POST", path, body); },
  put(path, body) { return this.request("PUT", path, body); }
};

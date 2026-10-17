/**
 * ZAYVORA MATAB OS — Unified Frontend API Client
 * Enterprise-grade persistent client with automatic token hydration and 401 recovery.
 */

export class MatabApiClient {
  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
    this.token = "";
    try {
      this.token = localStorage.getItem("matab_token") || "";
    } catch (e) {}
  }

  setToken(token) {
    this.token = token || "";
    try {
      if (token) {
        localStorage.setItem("matab_token", token);
      } else {
        localStorage.removeItem("matab_token");
      }
    } catch (e) {}
  }

  getToken() {
    try {
      const stored = localStorage.getItem("matab_token");
      if (stored) {
        this.token = stored;
        return stored;
      }
    } catch (e) {}
    return this.token || "";
  }

  async request(method, path, body = null, queryParams = {}) {
    const url = new URL(`${this.baseUrl}${path}`, window.location.origin);
    Object.keys(queryParams).forEach(key => url.searchParams.append(key, queryParams[key]));

    const reqId = (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function")
      ? crypto.randomUUID()
      : "req-" + Math.random().toString(36).substring(2, 11) + "-" + Date.now();

    const headers = {
      "Content-Type": "application/json",
      "X-Request-Id": reqId
    };

    const activeToken = this.getToken();
    if (activeToken) {
      headers["Authorization"] = `Bearer ${activeToken}`;
    }

    const options = {
      method,
      headers
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url.toString(), options);

    // If 401 Unauthorized, automatically clear invalid token and notify handler
    if (response.status === 401) {
      this.token = "";
      try {
        localStorage.removeItem("matab_token");
        localStorage.removeItem("matab_user");
      } catch (e) {}
      if (typeof window.__MATAB_ON_UNAUTHORIZED__ === "function") {
        window.__MATAB_ON_UNAUTHORIZED__();
      }
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const error = new Error(data.message || `HTTP ${response.status}`);
      error.status = response.status;
      error.code = data.code || "UNKNOWN_ERROR";
      error.requestId = data.request_id || headers["X-Request-Id"];
      error.details = data.details || {};
      throw error;
    }

    return data;
  }

  get(path, query = {}) { return this.request("GET", path, null, query); }
  post(path, body = {}) { return this.request("POST", path, body); }
  put(path, body = {}) { return this.request("PUT", path, body); }
  delete(path) { return this.request("DELETE", path); }
}

if (!window.__MATAB_API_CLIENT__) {
  window.__MATAB_API_CLIENT__ = new MatabApiClient();
}

export const apiClient = window.__MATAB_API_CLIENT__;


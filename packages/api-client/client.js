/**
 * ZAYVORA MATAB OS — Unified Frontend API Client
 */

export class MatabApiClient {
  constructor(baseUrl = "") {
    this.baseUrl = baseUrl;
    this.token = "";
  }

  setToken(token) {
    this.token = token;
  }

  async request(method, path, body = null, queryParams = {}) {
    const url = new URL(`${this.baseUrl}${path}`, window.location.origin);
    Object.keys(queryParams).forEach(key => url.searchParams.append(key, queryParams[key]));

    const headers = {
      "Content-Type": "application/json",
      "X-Request-Id": crypto.randomUUID()
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const options = {
      method,
      headers
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    const response = await fetch(url.toString(), options);
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

export const apiClient = new MatabApiClient();

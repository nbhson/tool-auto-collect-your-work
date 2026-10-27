/**
 * API client — fetch wrapper with timeout, retry, and error normalization.
 *
 * All backend calls go through here so every request gets:
 * - AbortController timeout (default 15s)
 * - Retry with exponential backoff on network errors (GET/HEAD only)
 * - Normalized ApiError with backend `detail` message
 */

/** @type {number} Default request timeout in milliseconds. */
const DEFAULT_TIMEOUT = 15000;

/** @type {number} Max retries for transient network failures. */
const MAX_RETRIES = 2;

/** @type {number} Initial retry delay (ms), doubled per attempt. */
const RETRY_DELAY = 500;

/**
 * Error thrown for any failed API call.
 */
export class ApiError extends Error {
  /**
   * @param {string} message - Human-readable error message.
   * @param {number} [status] - HTTP status code (0 for network errors).
   */
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Perform a fetch with timeout, JSON parsing and retry.
 *
 * @param {string} url - Request URL (same-origin).
 * @param {Object} [options] - Fetch options.
 * @param {string} [options.method="GET"] - HTTP method.
 * @param {Object|null} [options.body] - JSON-serializable payload.
 * @param {number} [options.timeout=DEFAULT_TIMEOUT] - Timeout in ms.
 * @param {number} [options.retries=MAX_RETRIES] - Retry attempts for network errors.
 * @returns {Promise<any>} Parsed JSON body (undefined for 204).
 * @throws {ApiError} On non-2xx response or exhausted retries.
 */
export async function apiFetch(url, { method = "GET", body, timeout = DEFAULT_TIMEOUT, retries = MAX_RETRIES } = {}) {
  const canRetry = method === "GET" || method === "HEAD";
  let lastError = null;

  for (let attempt = 0; attempt <= (canRetry(method) ? retries : 0); attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const res = await fetch(url, {
        method,
        signal: controller.signal,
        headers: body !== undefined ? { "Content-Type": "application/json" } : {},
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });

      if (!res.ok) {
        const detail = await extractErrorDetail(res);
        // Do not retry client errors
        throw new ApiError(detail, res.status);
      }
      if (res.status === 204) return undefined;
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError && err.status > 0 && err.status < 500) throw err;
      lastError = err;
      if (attempt < (canRetry(method) ? retries : 0)) {
        await sleep(RETRY_DELAY * 2 ** attempt);
        continue;
      }
      break;
    } finally {
      clearTimeout(timer);
    }
  }

  if (lastError instanceof ApiError) throw lastError;
  throw new ApiError(lastError?.message || "Network error", 0);
}

/**
 * Whether the HTTP method is safe to retry automatically.
 * @param {string} method - HTTP method.
 * @returns {boolean} True for idempotent methods.
 */
function canRetry(method) {
  return method === "GET" || method === "HEAD";
}

/**
 * Sleep for the given duration.
 * @param {number} ms - Milliseconds to wait.
 * @returns {Promise<void>}
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Extract a readable message from an error response.
 *
 * @param {Response} res - Fetch response.
 * @returns {Promise<string>} Error detail or generic message.
 */
async function extractErrorDetail(res) {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      // Pydantic validation errors
      return data.detail.map((e) => `${(e.loc || []).join(".")}: ${e.msg}`).join("; ");
    }
    if (data.detail) return String(data.detail);
    return `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

// ─── Work Logs ─────────────────────────────────────────

/**
 * Fetch paginated work logs with current filters.
 * @param {Object} state - Filter/sort state.
 * @returns {Promise<Object>} { items, total, page, page_size }
 */
export function fetchLogs(state) {
  const params = new URLSearchParams({
    page: state.page,
    page_size: state.pageSize,
    sort_by: state.sortBy,
    sort_order: state.sortOrder,
  });
  if (state.source) params.set("source", state.source);
  if (state.activityType) params.set("activity_type", state.activityType);
  if (state.dateFrom) params.set("from", state.dateFrom);
  if (state.dateTo) params.set("to", state.dateTo);
  if (state.search) params.set("search", state.search);
  return apiFetch(`/api/logs?${params}`);
}

/**
 * Fetch dashboard stats.
 * @returns {Promise<Object>} Stats object.
 */
export function fetchStats() {
  return apiFetch("/api/logs/stats");
}

/**
 * Delete a log entry.
 * @param {number} id - Log id.
 * @returns {Promise<void>}
 */
export function deleteLog(id) {
  return apiFetch(`/api/logs/${id}`, { method: "DELETE" });
}

/**
 * Create a manual work log entry.
 * @param {Object} data - Entry payload.
 * @returns {Promise<Object>} Created entry.
 */
export function createLog(data) {
  return apiFetch("/api/logs", { method: "POST", body: data });
}

/**
 * Update an existing log entry.
 * @param {number} id - Log id.
 * @param {Object} data - Fields to update.
 * @returns {Promise<Object>} Updated entry.
 */
export function updateLog(id, data) {
  return apiFetch(`/api/logs/${id}`, { method: "PATCH", body: data });
}

/**
 * Fetch a single page of logs (used by edit lookup).
 * @param {number} page - Page number.
 * @param {number} pageSize - Page size.
 * @returns {Promise<Object>} Logs list.
 */
export function fetchLogsPage(page = 1, pageSize = 200) {
  return apiFetch(`/api/logs?page=${page}&page_size=${pageSize}`);
}

// ─── Settings ──────────────────────────────────────────

/**
 * Fetch AI settings.
 * @returns {Promise<Object>} { settings: {...} }
 */
export function fetchSettings() {
  return apiFetch("/api/settings");
}

/**
 * Save settings items.
 * @param {Array<{key: string, value: string}>} items - Settings to upsert.
 * @returns {Promise<Object>} Save result.
 */
export function saveSettings(items) {
  return apiFetch("/api/settings", { method: "PUT", body: items });
}

/**
 * Test LLM provider connection and load available models.
 * @param {Object} data - { provider, api_key, base_url, model }.
 * @returns {Promise<Object>} Test result.
 */
export function testConnection(data) {
  return apiFetch("/api/settings/test", { method: "POST", body: data, timeout: 30000 });
}

// ─── AI endpoints ──────────────────────────────────────

/**
 * Classify a single log via AI.
 * @param {number} id - Log id.
 * @returns {Promise<Object>} Classification result.
 */
export function classifyLog(id) {
  return apiFetch(`/api/ai/classify/${id}`, { method: "POST", timeout: 60000 });
}

/**
 * Batch classify logs.
 * @param {number[]|null} ids - Specific log ids or null for auto.
 * @returns {Promise<Object>} Batch results.
 */
export function classifyBatch(ids = null) {
  return apiFetch("/api/ai/classify", {
    method: "POST",
    body: ids ? { log_ids: ids } : {},
    timeout: 120000,
  });
}

/**
 * Request AI summary for a date range.
 * @param {Object} data - { date_from, date_to, period }.
 * @returns {Promise<Object>} { summary, log_count }
 */
export function fetchSummary(data) {
  return apiFetch("/api/ai/summarize", { method: "POST", body: data, timeout: 90000 });
}

/**
 * Ask AI a natural-language question.
 * @param {string} query - User question.
 * @param {string|null} [dateFrom] - Optional ISO date-from.
 * @param {string|null} [dateTo] - Optional ISO date-to.
 * @returns {Promise<Object>} { answer, log_count }
 */
export function askAI(query, date_from = null, date_to = null) {
  return apiFetch("/api/ai/analyze", {
    method: "POST",
    body: { query, date_from, date_to },
    timeout: 90000,
  });
}

/**
 * Enhance a single log (rewrite description + estimate time).
 * @param {number} id - Log id.
 * @returns {Promise<Object>} Enhance result.
 */
export function enhanceLog(id) {
  return apiFetch(`/api/ai/enhance/${id}`, { method: "POST", timeout: 90000 });
}

/**
 * Batch enhance logs.
 * @returns {Promise<Object>} Batch enhance result.
 */
export function enhanceBatch() {
  return apiFetch("/api/ai/enhance", { method: "POST", body: {}, timeout: 120000 });
}

/**
 * Trigger a manual poll of all sources.
 * @returns {Promise<Object>} Poll result.
 */
export function triggerPollRequest() {
  return apiFetch("/api/poll", { method: "POST", timeout: 120000, retries: 0 });
}

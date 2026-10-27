/**
 * Data orchestration — loads logs + stats, wires them into the UI.
 */

import { state } from "./state.js";
import { fetchLogs, fetchStats } from "./api.js";
import { renderSkeleton, renderTable, renderTableError } from "./table.js";
import { renderStats } from "./stats.js";
import { toastError } from "./toast.js";

/** @type {number|null} Auto-refresh interval handle. */
let refreshTimer = null;

/**
 * Fetch logs + stats and render both. Shows skeleton while loading.
 *
 * @returns {Promise<void>}
 */
export async function loadData() {
  renderSkeleton();
  try {
    const [logsData, stats] = await Promise.all([fetchLogs(state), fetchStats()]);
    renderTable(logsData);
    renderStats(stats);
  } catch (err) {
    console.error("loadData failed:", err);
    renderTableError(err.message || "Unknown error");
    toastError(`Error loading data: ${err.message}`);
  }
}

/**
 * Refresh data from page 1.
 */
export function refreshPage() {
  state.page = 1;
  loadData();
}

/**
 * Start the 30s auto-refresh loop (skips while page is hidden).
 */
export function startAutoRefresh() {
  if (refreshTimer) return;
  refreshTimer = setInterval(() => {
    if (!document.hidden) loadData();
  }, 30000);
}

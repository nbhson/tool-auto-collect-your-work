/**
 * Application state — shared mutable state for the SPA.
 *
 * @typedef {Object} AppState
 * @property {number} page - Current page number (1-based).
 * @property {number} pageSize - Rows per page.
 * @property {string} source - Active source filter ('' = all).
 * @property {string} activityType - Active activity-type filter.
 * @property {string} dateFrom - ISO date-from filter.
 * @property {string} dateTo - ISO date-to filter.
 * @property {string} search - Search term.
 * @property {string} sortBy - Sort column.
 * @property {"asc"|"desc"} sortOrder - Sort direction.
 * @property {number} total - Total entries for current filters.
 * @property {boolean} aiEnabled - Whether AI Harness is active.
 * @property {"light"|"dark"} theme - Current UI theme.
 */

/** @type {AppState} */
export const state = {
  page: 1,
  pageSize: 50,
  source: "",
  activityType: "",
  dateFrom: "",
  dateTo: "",
  search: "",
  sortBy: "activity_timestamp",
  sortOrder: "desc",
  total: 0,
  aiEnabled: false,
  theme: "light",
};

/** ID of the log currently being edited (null = create mode). */
export let editingId = null;

/**
 * Set the currently edited log id.
 * @param {number|null} id - Log id or null for create mode.
 */
export function setEditingId(id) {
  editingId = id;
}

/**
 * Get the currently edited log id.
 * @returns {number|null} Current editing id.
 */
export function getEditingId() {
  return editingId;
}

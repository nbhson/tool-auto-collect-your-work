/**
 * Work Log Harness — Frontend entry point (Enterprise UI).
 *
 * Wires together:
 * - Dashboard: sidebar, topbar, hero, stat cards, filters, table
 * - Modal manual entry + settings
 * - Export Excel + AI actions (classify, enhance, summary, chat)
 * - Auto-refresh 30s, dark mode, command palette, keyboard shortcuts
 */

import { state, setEditingId, getEditingId } from "./state.js";
import {
  createLog,
  updateLog,
  deleteLog,
  fetchLogsPage,
  triggerPollRequest,
} from "./api.js";
import { showToast } from "./toast.js";
import { withLoading, withButtonLoading } from "./loading.js";
import { loadData, refreshPage, startAutoRefresh } from "./data.js";
import { loadTheme, toggleTheme } from "./theme.js";
import { toggleDesc } from "./table.js";
import {
  loadSettings,
  handleSettingsSave,
  onProviderChange,
  toggleApiKeyVisibility,
  testAIConnection,
} from "./settings.js";
import {
  handleClassifySingle,
  classifyUnclassified,
  handleEnhanceSingle,
  enhanceBatchAction,
  openSummaryPanel,
  closeSummaryPanel,
  generateSummary,
  toggleChatPanel,
  sendChatMessage,
  toggleAIPanel,
} from "./ai.js";

// ─── Bootstrap Modal instances ─────────────────────────

/** @type {bootstrap.Modal|null} Cached manual-entry modal instance. */
let _manualModal = null;

/** @type {bootstrap.Modal|null} Cached settings modal instance. */
let _settingsModal = null;

/**
 * Lazily create the manual-entry modal instance.
 * @returns {bootstrap.Modal} Modal instance.
 */
function getManualModal() {
  if (!_manualModal) _manualModal = new bootstrap.Modal("#manual-modal");
  return _manualModal;
}

/**
 * Lazily create the settings modal instance.
 * @returns {bootstrap.Modal} Modal instance.
 */
function getSettingsModal() {
  if (!_settingsModal) _settingsModal = new bootstrap.Modal("#settings-modal");
  return _settingsModal;
}

// ─── Modals ────────────────────────────────────────────

/**
 * Open the manual entry modal (create or edit mode).
 * @param {Object|null} [editData] - Existing log to edit, or null for create.
 */
function openModal(editData = null) {
  setEditingId(editData ? editData.id : null);
  document.getElementById("modal-title").textContent = editData
    ? "Edit Work Log"
    : "Add Manual Entry";

  if (editData) {
    document.getElementById("entry-title").value = editData.title || "";
    document.getElementById("entry-desc").value = editData.description || "";
    document.getElementById("entry-type").value = editData.activity_type || "other";
    document.getElementById("entry-project").value = editData.project || "";
    document.getElementById("entry-url").value = editData.url || "";
    document.getElementById("entry-date").value = editData.activity_timestamp
      ? new Date(editData.activity_timestamp).toISOString().slice(0, 16)
      : new Date().toISOString().slice(0, 16);
    document.getElementById("entry-hours").value = editData.time_spent_minutes
      ? Math.floor(editData.time_spent_minutes / 60)
      : 0;
    document.getElementById("entry-minutes").value = editData.time_spent_minutes
      ? editData.time_spent_minutes % 60
      : 0;
  } else {
    document.getElementById("manual-form").reset();
    document.getElementById("entry-date").value = new Date().toISOString().slice(0, 16);
    document.getElementById("entry-hours").value = 0;
    document.getElementById("entry-minutes").value = 0;
  }

  getManualModal().show();
}

/**
 * Open the manual entry modal in create mode.
 */
function openManualModal() {
  openModal();
}

/**
 * Close the manual entry modal and clear edit state.
 */
function closeManualModal() {
  getManualModal().hide();
  setEditingId(null);
}

/**
 * Open the AI settings modal (loads current settings async).
 */
function openSettingsModal() {
  getSettingsModal().show();
  loadSettings();
}

/**
 * Close the AI settings modal.
 */
function closeSettingsModal() {
  getSettingsModal().hide();
}

// ─── Sidebar / command palette / filters ───────────────

/**
 * Toggle the sidebar (mobile off-canvas or desktop expanded).
 */
function toggleSidebar() {
  const sidebar = document.getElementById("app-sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  if (!sidebar) return;
  const expanded = sidebar.getAttribute("data-expanded") === "true";
  sidebar.setAttribute("data-expanded", expanded ? "false" : "true");
  if (window.innerWidth < 768 && overlay) {
    overlay.classList.toggle("active", !expanded);
  }
}

/**
 * Open the command palette and focus its input.
 */
function openCmdPalette() {
  const backdrop = document.getElementById("cmd-backdrop");
  const modal = document.getElementById("cmd-modal");
  if (!backdrop || !modal) return;
  backdrop.classList.add("active");
  modal.classList.add("active");
  modal.setAttribute("aria-hidden", "false");
  setTimeout(() => {
    const input = document.getElementById("cmd-input");
    if (input) input.focus();
  }, 150);
}

/**
 * Close the command palette.
 */
function closeCmdPalette() {
  const backdrop = document.getElementById("cmd-backdrop");
  const modal = document.getElementById("cmd-modal");
  if (backdrop) backdrop.classList.remove("active");
  if (modal) {
    modal.classList.remove("active");
    modal.setAttribute("aria-hidden", "true");
  }
}

/**
 * Toggle the mobile filter row visibility.
 */
function toggleFilterRow() {
  const row = document.getElementById("filter-row");
  if (row) row.classList.toggle("open");
}

/**
 * Scroll the table into view on mobile (quick-filter UX).
 */
function scrollToTable() {
  if (window.innerWidth < 768) {
    document
      .querySelector(".table-card")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/**
 * Quick-filter the table by source.
 * @param {string} source - Source value ('' = all).
 */
function filterBySource(source) {
  document.getElementById("filter-source").value = source;
  applyFilters();
  scrollToTable();
}

/**
 * Reset all filters to defaults and reload.
 */
function resetFilters() {
  document.getElementById("filter-source").value = "";
  document.getElementById("filter-type").value = "";
  document.getElementById("filter-from").value = "";
  document.getElementById("filter-to").value = "";
  document.getElementById("filter-search").value = "";
  applyFilters();
}

/**
 * Read filter inputs into state and reload data from page 1.
 */
function applyFilters() {
  state.source = document.getElementById("filter-source").value;
  state.activityType = document.getElementById("filter-type").value;
  const from = document.getElementById("filter-from").value;
  const to = document.getElementById("filter-to").value;
  state.dateFrom = from ? new Date(from).toISOString() : "";
  state.dateTo = to ? new Date(`${to}T23:59:59`).toISOString() : "";
  state.search = document.getElementById("filter-search").value.trim();
  state.page = 1;
  loadData();
}

/**
 * Toggle sort column/direction and reload.
 * @param {string} column - Column name to sort by.
 */
function handleSort(column) {
  if (state.sortBy === column) {
    state.sortOrder = state.sortOrder === "asc" ? "desc" : "asc";
  } else {
    state.sortBy = column;
    state.sortOrder = "desc";
  }
  loadData();
}

// ─── CRUD actions ──────────────────────────────────────

/**
 * Handle manual entry form submit (create or update).
 * @param {Event} e - Submit event.
 */
async function handleFormSubmit(e) {
  e.preventDefault();

  const data = {
    title: document.getElementById("entry-title").value.trim(),
    description: document.getElementById("entry-desc").value.trim() || null,
    activity_type: document.getElementById("entry-type").value,
    project: document.getElementById("entry-project").value.trim() || null,
    url: document.getElementById("entry-url").value.trim() || null,
    activity_timestamp: document.getElementById("entry-date").value
      ? new Date(document.getElementById("entry-date").value).toISOString()
      : null,
    time_spent_minutes:
      parseInt(document.getElementById("entry-hours").value || "0", 10) * 60 +
      parseInt(document.getElementById("entry-minutes").value || "0", 10),
  };

  if (!data.title) {
    showToast("Title is required", "error");
    return;
  }

  const btn = document.getElementById("btn-save");
  await withButtonLoading(btn, "Saving...", async () => {
    try {
      if (getEditingId()) {
        await updateLog(getEditingId(), data);
        showToast("✅ Work log updated successfully!", "success");
      } else {
        await createLog(data);
        showToast("✅ Work log added successfully!", "success");
      }
      closeManualModal();
      loadData();
    } catch (err) {
      showToast(`❌ ${err.message}`, "error", 5000);
    }
  });
}

/**
 * Delete a log after confirmation.
 * @param {number} id - Log id.
 */
async function handleDelete(id) {
  if (!confirm("Delete this work log entry?")) return;
  await withLoading("Deleting...", async () => {
    try {
      await deleteLog(id);
      showToast("Work log deleted", "info");
      loadData();
    } catch (err) {
      showToast(`❌ ${err.message}`, "error", 5000);
    }
  });
}

/**
 * Find a log by id and open the edit modal.
 * @param {number} id - Log id.
 */
async function handleEdit(id) {
  try {
    const data = await fetchLogsPage(1, 200);
    const item = data.items.find((i) => i.id === id);
    if (item) openModal(item);
    else showToast("Work log not found", "error");
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

/**
 * Download the Excel export (optionally filtered by source).
 * @param {string} [source=""] - Optional source filter.
 */
async function handleExport(source = "") {
  const url = source ? `/api/export/excel/${source}` : "/api/export/excel";

  await withLoading("📥 Exporting Excel...", async () => {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = source
        ? `worklog_${source}_${new Date().toISOString().slice(0, 10)}.xlsx`
        : `worklog_export_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(downloadUrl);
      showToast("✅ Excel exported successfully!", "success");
    } catch (err) {
      showToast(`❌ Export failed: ${err.message}`, "error", 5000);
    }
  });
}

/**
 * Shortcut to export all logs (command palette / keyboard).
 */
function exportNow() {
  handleExport("");
}

/**
 * Trigger a manual poll of all sources with button feedback.
 */
async function triggerPoll() {
  const btn =
    document.querySelector(".hero-btn .bi-arrow-repeat")?.closest("button") ||
    document.querySelector(".topbar-btn .bi-arrow-repeat")?.closest("button");

  if (!btn) {
    await runPoll();
    return;
  }

  const origHTML = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span>';

  try {
    await runPoll();
  } finally {
    btn.disabled = false;
    btn.innerHTML = origHTML;
  }
}

/**
 * Call the poll API and refresh data.
 * @returns {Promise<void>}
 */
async function runPoll() {
  try {
    const data = await triggerPollRequest();
    if (data.status === "ok") {
      showToast("🔄 Sync completed — " + data.message, "success");
    } else {
      showToast("❌ Sync failed", "error");
    }
  } catch (err) {
    showToast(`❌ Sync error: ${err.message}`, "error", 5000);
  }
  await loadData();
}

// ─── Window handlers (for inline onclick) ──────────────

// Dropdown action wrappers (called from generated table HTML)
window.__deleteLog = handleDelete;
window.__editLog = handleEdit;
window.__classifySingle = handleClassifySingle;
window.__enhanceSingle = handleEnhanceSingle;
window.__goPage = (page) => {
  if (page < 1) return;
  state.page = page;
  loadData();
};
window.__refreshPage = refreshPage;

// Expose public names used by inline onclick handlers in index.html
window.handleDelete = handleDelete;
window.handleEdit = handleEdit;
window.handleExport = handleExport;
window.handleClassifySingle = handleClassifySingle;
window.classifyUnclassified = classifyUnclassified;
window.handleEnhanceSingle = handleEnhanceSingle;
window.enhanceBatch = enhanceBatchAction;
window.openManualModal = openManualModal;
window.closeManualModal = closeManualModal;
window.openSettingsModal = openSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.onProviderChange = onProviderChange;
window.toggleApiKeyVisibility = toggleApiKeyVisibility;
window.testAIConnection = testAIConnection;
window.openSummaryPanel = openSummaryPanel;
window.closeSummaryPanel = closeSummaryPanel;
window.generateSummary = generateSummary;
window.toggleChatPanel = toggleChatPanel;
window.sendChatMessage = sendChatMessage;
window.toggleAIPanel = toggleAIPanel;
window.triggerPoll = triggerPoll;
window.toggleSidebar = toggleSidebar;
window.toggleTheme = toggleTheme;
window.openCmdPalette = openCmdPalette;
window.closeCmdPalette = closeCmdPalette;
window.toggleFilterRow = toggleFilterRow;
window.filterBySource = filterBySource;
window.resetFilters = resetFilters;
window.exportNow = exportNow;
window.toggleDesc = toggleDesc;

// ─── Init ──────────────────────────────────────────────

/** @type {number|null} Debounce timer for the search input. */
let searchTimer = null;

/** @type {boolean} Guard against double initialization. */
let _initialized = false;

/**
 * Wire all event listeners and start the app.
 */
function init() {
  if (_initialized) return;
  _initialized = true;

  loadTheme();
  loadSettings();
  loadData();
  startAutoRefresh();

  // Filter events
  document.getElementById("filter-source")?.addEventListener("change", applyFilters);
  document.getElementById("filter-type")?.addEventListener("change", applyFilters);
  document.getElementById("filter-from")?.addEventListener("change", applyFilters);
  document.getElementById("filter-to")?.addEventListener("change", applyFilters);

  const filterSearch = document.getElementById("filter-search");
  if (filterSearch) {
    filterSearch.addEventListener("input", () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(applyFilters, 400);
    });
  }

  // Manual entry form
  document
    .querySelector("#btn-add-manual, #btn-add-manual-hero")
    ?.addEventListener("click", () => openModal());
  document.getElementById("btn-cancel")?.addEventListener("click", closeManualModal);
  document.getElementById("manual-form")?.addEventListener("submit", handleFormSubmit);
  document.getElementById("settings-form")?.addEventListener("submit", handleSettingsSave);

  // Chat
  const chatInput = document.getElementById("chat-input");
  chatInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });
  document.getElementById("btn-chat-send")?.addEventListener("click", (e) => {
    e.preventDefault();
    sendChatMessage();
  });

  // Export buttons (hero)
  document.querySelectorAll(".hero-btn .bi-download").forEach((icon) => {
    icon.closest("button")?.addEventListener("click", () => handleExport(""));
  });

  // Sortable headers
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => handleSort(th.dataset.sort));
  });

  // ─── Keyboard shortcuts ────────────────────────────
  document.addEventListener("keydown", (e) => {
    const mod = e.metaKey || e.ctrlKey;
    if (mod && e.key === "k") {
      e.preventDefault();
      const backdrop = document.getElementById("cmd-backdrop");
      if (backdrop?.classList.contains("active")) closeCmdPalette();
      else openCmdPalette();
    }
    if (e.key === "Escape") closeCmdPalette();
    if (mod && e.key === "n") {
      e.preventDefault();
      openModal();
    }
    if (mod && e.key === "e") {
      e.preventDefault();
      handleExport("");
    }
    if (mod && e.key === ",") {
      e.preventDefault();
      openSettingsModal();
    }
  });

  // Command palette: live filter + Enter runs first visible command
  const cmdInput = document.getElementById("cmd-input");
  if (cmdInput) {
    cmdInput.addEventListener("input", function () {
      const q = this.value.toLowerCase();
      document.querySelectorAll(".cmd-modal-item").forEach((item) => {
        item.style.display = item.textContent.toLowerCase().includes(q) ? "flex" : "none";
      });
    });
    cmdInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        const visible = document.querySelector(
          '.cmd-modal-item:not([style*="display: none"])'
        );
        if (visible) visible.click();
      }
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}

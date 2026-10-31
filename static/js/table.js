/**
 * Table rendering — work logs table, pagination, skeleton, description toggle.
 */

import { state } from "./state.js";
import { badgeClass, activityTypeLabel, escapeHtml, formatDate, formatTime } from "./format.js";

/** Length at which descriptions get truncated with "Read more". */
const DESC_TRUNCATE_LENGTH = 90;

/**
 * Render skeleton loading rows into the table body.
 */
export function renderSkeleton() {
  const tableBody = document.getElementById("logs-tbody");
  if (!tableBody) return;
  tableBody.innerHTML = Array.from(
    { length: 6 },
    () => `
      <tr aria-hidden="true">
        <td><div class="skeleton" style="height:16px;width:60px"></div></td>
        <td><div class="skeleton" style="height:16px;width:70px"></div></td>
        <td><div class="skeleton" style="height:16px;width:200px"></div><div class="skeleton" style="height:12px;width:140px;margin-top:6px"></div></td>
        <td><div class="skeleton" style="height:16px;width:80px"></div></td>
        <td><div class="skeleton" style="height:16px;width:120px"></div></td>
        <td><div class="skeleton" style="height:16px;width:50px"></div></td>
        <td><div class="skeleton" style="height:16px;width:40px"></div></td>
      </tr>`,
  ).join("");
}

/**
 * Render a visual error banner in the table body.
 *
 * @param {string} message - Error message to display.
 */
export function renderTableError(message) {
  const tableBody = document.getElementById("logs-tbody");
  if (!tableBody) return;
  tableBody.innerHTML = `
    <tr>
      <td colspan="7">
        <div class="text-center py-5" role="alert">
          <div style="font-size:40px;margin-bottom:8px">⚠️</div>
          <h6 class="fw-semibold">Failed to load work logs</h6>
          <p class="text-muted" style="font-size:13px">${escapeHtml(message)}</p>
          <button class="hero-btn hero-btn-primary" onclick="window.__refreshPage()">Retry</button>
        </div>
      </td>
    </tr>`;
}

/**
 * Build the description cell HTML with optional Read more/less toggle.
 * @param {Object} log - Log entry.
 * @returns {string} HTML for the description cell.
 */
function renderDescription(log) {
  if (!log.description) return "";
  const fullText = log.description;
  if (fullText.length <= DESC_TRUNCATE_LENGTH) {
    return `<div class="cell-desc">${escapeHtml(fullText)}</div>`;
  }
  const escapedShort = escapeHtml(fullText.substring(0, DESC_TRUNCATE_LENGTH));
  return `<div class="cell-desc truncated" id="desc-${log.id}" data-full="${escapeHtml(fullText)}">${escapedShort}…</div>
      <span class="desc-toggle" id="toggle-${log.id}" onclick="window.toggleDesc(${log.id})" role="button" tabindex="0">Read more</span>`;
}

/**
 * Toggle a truncated description between collapsed and expanded.
 * @param {number} id - Log id.
 */
export function toggleDesc(id) {
  const descEl = document.getElementById(`desc-${id}`);
  const toggleEl = document.getElementById(`toggle-${id}`);
  if (!descEl || !toggleEl) return;

  const isExpanded = descEl.classList.contains("expanded");
  if (isExpanded) {
    descEl.classList.remove("expanded");
    descEl.classList.add("truncated");
    toggleEl.textContent = "Read more";
  } else {
    const full = descEl.dataset.full;
    if (full) descEl.textContent = full;
    descEl.classList.remove("truncated");
    descEl.classList.add("expanded");
    toggleEl.textContent = "Read less";
  }
}

/**
 * Render the work logs table from an API response.
 *
 * @param {Object} data - { items, total, page } payload.
 * @returns {{ total: number }} Metadata stored into state.
 */
export function renderTable(data) {
  const tableBody = document.getElementById("logs-tbody");
  const tableInfo = document.getElementById("table-info");
  const pagination = document.getElementById("pagination");
  const { items, total, page } = data;
  state.total = total;

  if (!items || items.length === 0) {
    tableBody.innerHTML = `
        <tr>
          <td colspan="7">
            <div class="text-center py-5">
              <div style="font-size:48px;margin-bottom:8px" aria-hidden="true">📋</div>
              <h5 class="fw-semibold">No work logs yet</h5>
              <p class="text-muted" style="font-size:13px">Configure Jira/Bitbucket in .env or add manual entries.</p>
            </div>
          </td>
        </tr>`;
    tableInfo.textContent = "0 entries";
    pagination.innerHTML = "";
    return { total };
  }

  tableBody.innerHTML = items.map((log) => renderRow(log)).join("");

  // Initialize Bootstrap dropdowns for dynamic rows
  tableBody.querySelectorAll('[data-bs-toggle="dropdown"]').forEach((el) => {
    try {
      new bootstrap.Dropdown(el);
    } catch {
      /* Bootstrap not loaded — dropdowns degrade gracefully */
    }
  });

  const start = Math.min((page - 1) * state.pageSize + 1, total);
  const end = Math.min(page * state.pageSize, total);
  const showPlural = total !== 1 ? "entries" : "entry";
  tableInfo.textContent = `${start}–${end} of ${total} ${showPlural}`;

  renderPagination(total);
  return { total };
}

/**
 * Render a single table row.
 * @param {Object} log - Work log entry.
 * @returns {string} HTML row.
 */
function renderRow(log) {
  const aiActions = state.aiEnabled
    ? `
              <li><hr class="dropdown-divider"></li>
              <li><a class="dropdown-item" href="#" onclick="window.__classifySingle(${log.id});return false"><span class="me-2" aria-hidden="true">✨</span>Classify</a></li>
              <li><a class="dropdown-item" href="#" onclick="window.__enhanceSingle(${log.id});return false"><span class="me-2" aria-hidden="true">🪄</span>Enhance</a></li>
              `
    : "";

  const titleCell = log.url
    ? `<a href="${escapeHtml(log.url)}" target="_blank" rel="noopener" title="${escapeHtml(log.title)}">${escapeHtml(log.title)}</a>`
    : `<span title="${escapeHtml(log.title)}">${escapeHtml(log.title)}</span>`;

  return `
      <tr>
        <td><span class="${badgeClass(log.source)}">${escapeHtml(log.source)}</span></td>
        <td><span class="type-badge">${activityTypeLabel(log.activity_type)}</span></td>
        <td class="cell-title">
          ${titleCell}
          ${renderDescription(log)}
        </td>
        <td>${escapeHtml(log.project || "-")}</td>
        <td class="cell-date">${formatDate(log.activity_timestamp)}</td>
        <td class="cell-time${log.time_spent_minutes ? " has-value" : ""}">${formatTime(log.time_spent_minutes)}</td>
        <td class="cell-actions">
          <div class="dropdown">
            <button class="row-action-btn dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false" aria-label="Actions for: ${escapeHtml(log.title)}" title="Actions"><i class="bi bi-three-dots-vertical" aria-hidden="true"></i></button>
            <ul class="dropdown-menu dropdown-menu-end" style="min-width:160px;font-size:13px;padding:4px">
              <li><a class="dropdown-item" href="#" onclick="window.__editLog(${log.id});return false"><i class="bi bi-pencil me-2" aria-hidden="true"></i>Edit</a></li>
              <li><a class="dropdown-item" href="#" onclick="window.__deleteLog(${log.id});return false"><i class="bi bi-trash me-2" aria-hidden="true"></i>Delete</a></li>
              ${aiActions}
            </ul>
          </div>
        </td>
      </tr>`;
}

/**
 * Render pagination controls.
 * @param {number} total - Total entries.
 */
export function renderPagination(total) {
  const pagination = document.getElementById("pagination");
  const totalPages = Math.ceil(total / state.pageSize);
  if (totalPages <= 1) {
    pagination.innerHTML =
      '<div class="text-muted text-center" style="font-size:12px">All entries shown</div>';
    return;
  }

  let html = '<ul class="pagination pagination-sm justify-content-center mb-0">';

  html += `<li class="page-item ${state.page <= 1 ? "disabled" : ""}">
      <a class="page-link" href="#" onclick="window.__goPage(${state.page - 1});return false;" aria-label="Previous page">
        <span aria-hidden="true">&laquo;</span>
      </a>
    </li>`;

  const maxVisible = 5;
  let startPage = Math.max(1, state.page - Math.floor(maxVisible / 2));
  const endPage = Math.min(totalPages, startPage + maxVisible - 1);
  if (endPage - startPage + 1 < maxVisible) {
    startPage = Math.max(1, endPage - maxVisible + 1);
  }

  if (startPage > 1) {
    html += `<li class="page-item"><a class="page-link" href="#" onclick="window.__goPage(1);return false;">1</a></li>`;
    if (startPage > 2) {
      html += '<li class="page-item disabled"><a class="page-link" href="#">&hellip;</a></li>';
    }
  }

  for (let i = startPage; i <= endPage; i++) {
    html += `<li class="page-item ${i === state.page ? "active" : ""}">
        <a class="page-link" href="#" onclick="window.__goPage(${i});return false;" aria-label="Page ${i}"${i === state.page ? ' aria-current="page"' : ""}>${i}</a>
      </li>`;
  }

  if (endPage < totalPages) {
    if (endPage < totalPages - 1) {
      html += '<li class="page-item disabled"><a class="page-link" href="#">&hellip;</a></li>';
    }
    html += `<li class="page-item"><a class="page-link" href="#" onclick="window.__goPage(${totalPages});return false;">${totalPages}</a></li>`;
  }

  html += `<li class="page-item ${state.page >= totalPages ? "disabled" : ""}">
      <a class="page-link" href="#" onclick="window.__goPage(${state.page + 1});return false;" aria-label="Next page">
        <span aria-hidden="true">&raquo;</span>
      </a>
    </li>`;

  html += "</ul>";
  pagination.innerHTML = html;
}

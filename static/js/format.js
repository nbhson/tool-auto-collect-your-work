/**
 * Formatting helpers — dates, durations, labels, and HTML escaping.
 */

/**
 * Format an ISO datetime string as dd/mm/yyyy HH:mm.
 * @param {string} isoStr - ISO date string.
 * @returns {string} Formatted date or "" if empty.
 */
export function formatDate(isoStr) {
  if (!isoStr) return "";
  const d = new Date(isoStr);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Format minutes as a compact human string ("90m", "1h 30m", "2h").
 * @param {number} minutes - Minutes value.
 * @returns {string} Formatted duration or "-" when empty.
 */
export function formatTime(minutes) {
  if (!minutes) return "-";
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

/**
 * CSS class for a source badge.
 * @param {string} source - Log source.
 * @returns {string} Class name.
 */
export function badgeClass(source) {
  return `source-badge sb-${source}`;
}

/**
 * Human label for an activity type.
 * @param {string} type - Raw activity type.
 * @returns {string} Display label.
 */
export function activityTypeLabel(type) {
  const labels = {
    ticket_update: "Update",
    comment: "Comment",
    estimation_change: "Estimation",
    status_change: "Status",
    assignee_change: "Assignee",
    worklog: "Worklog",
    commit: "Commit",
    push: "Push",
    pr_create: "PR Create",
    pr_merge: "PR Merge",
    pr_close: "PR Close",
    pr_comment: "PR Comment",
    pr_approve: "PR Approve",
    local_commit: "Local Commit",
    issue_create: "Issue Create",
    issue_close: "Issue Close",
    meeting: "Meeting",
    code_review: "Code Review",
    research: "Research",
    other: "Other",
  };
  return labels[type] || type;
}

/**
 * Escape a string for safe HTML interpolation.
 * @param {string|null|undefined} str - Raw string.
 * @returns {string} HTML-escaped string.
 */
export function escapeHtml(str) {
  if (!str) return "";
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

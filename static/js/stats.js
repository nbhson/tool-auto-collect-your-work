/**
 * Stats rendering — animated counters and sparklines.
 */

/** Width of the sparkline SVG. */
const SPARK_W = 120;
/** Height of the sparkline SVG. */
const SPARK_H = 28;

/**
 * Render dashboard stat cards from stats payload.
 *
 * @param {Object} stats - Stats from /api/logs/stats.
 */
export function renderStats(stats) {
  const counters = [
    ["stat-total", stats.total_logs, ""],
    ["stat-time", stats.total_time_hours, "h"],
    ["stat-today", stats.today_time_hours, "h"],
    ["stat-week", stats.week_time_hours, "h"],
    ["stat-github", stats.github_logs, ""],
    ["stat-jira", stats.jira_logs, ""],
    ["stat-bitbucket", stats.bitbucket_logs, ""],
    ["stat-git", stats.git_logs, ""],
    ["stat-manual", stats.manual_logs, ""],
  ];

  counters.forEach(([id, value, suffix]) => {
    const val = parseInt(value, 10) || 0;
    animateCounter(id, val, suffix);
  });

  if (stats.daily_counts && stats.daily_counts.length > 0) {
    renderSparkline("sparkline-total", stats.daily_counts, "#4F46E5");
  }

  if (stats.trend_percent !== undefined) {
    const trendEl = document.getElementById("stat-trend-total");
    if (trendEl) {
      trendEl.style.display = "inline-flex";
      const dir = stats.trend_percent >= 0 ? "up" : "down";
      trendEl.className = `stat-trend ${dir}`;
      const label = trendEl.querySelector("span:last-child");
      if (label) label.textContent = Math.abs(stats.trend_percent) + "%";
    }
  }
}

/**
 * Render an inline SVG sparkline into a container.
 *
 * @param {string} elemId - Target element id.
 * @param {number[]} data - Data points.
 * @param {string} [color="#4F46E5"] - Stroke color.
 */
export function renderSparkline(elemId, data, color = "#4F46E5") {
  const container = document.getElementById(elemId);
  if (!container || !data || data.length < 2) return;

  const min = Math.min(...data, 0);
  const max = Math.max(...data, 1);
  const range = max - min || 1;

  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * SPARK_W;
    const y = SPARK_H - ((v - min) / range) * (SPARK_H - 4) - 2;
    return `${x},${y}`;
  });
  const pathD = pts.reduce((acc, p, i) => acc + (i === 0 ? "M" : "L") + p, "");
  container.innerHTML = `<svg width="${SPARK_W}" height="${SPARK_H}" viewBox="0 0 ${SPARK_W} ${SPARK_H}" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="${pathD}" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.8"/>
      <path d="${pathD}" stroke="${color}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" fill="none" opacity="0.12"/>
    </svg>`;
}

/**
 * Animate a numeric counter element with ease-out.
 * @param {string} elemId - Target element id.
 * @param {number} target - Final value.
 * @param {string} [suffix=""] - Suffix appended to the number (e.g. "h").
 */
export function animateCounter(elemId, target, suffix = "") {
  const el = document.getElementById(elemId);
  if (!el) return;

  const duration = 800;
  const startTime = performance.now();

  /**
   * Ease-out animation step.
   * @param {number} currentTime - Timestamp from rAF.
   */
  function step(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(target * eased);
    el.textContent = current + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

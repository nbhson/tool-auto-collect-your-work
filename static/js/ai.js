/**
 * AI Harness actions — classify, enhance, summary, and chat.
 */

import { state } from "./state.js";
import { classifyLog, classifyBatch, fetchSummary, askAI, enhanceLog, enhanceBatch } from "./api.js";
import { showToast } from "./toast.js";
import { withLoading } from "./loading.js";
import { loadData } from "./data.js";
import { escapeHtml } from "./format.js";

/**
 * Classify a single log via AI and refresh the table.
 * @param {number} logId - Log id.
 */
export async function handleClassifySingle(logId) {
  await withLoading("✨ Classifying entry...", async () => {
    try {
      const result = await classifyLog(logId);
      showToast(
        `✨ Classified: "${result.category}" (${Math.round(result.confidence * 100)}% confidence)`,
        "success"
      );
      loadData();
    } catch (err) {
      showToast(`❌ ${err.message}`, "error", 5000);
    }
  });
}

/**
 * Batch-classify all unclassified manual entries.
 */
export async function classifyUnclassified() {
  const btn = document.getElementById("btn-ai-classify");
  btn.disabled = true;
  btn.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> Classifying...';

  try {
    await withLoading("✨ Auto-classifying entries...", async () => {
      const result = await classifyBatch();
      const count = result.results ? result.results.length : 0;
      const highConf = result.results
        ? result.results.filter((r) => r.confidence > 0.5).length
        : 0;
      showToast(`✨ Classified ${count} entries (${highConf} with high confidence)`, "success");
      loadData();
    });
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-magic"></i> Auto-Classify';
  }
}

/**
 * Enhance a single log (rewrite description + estimate time).
 * @param {number} logId - Log id.
 */
export async function handleEnhanceSingle(logId) {
  if (!confirm("🪄 AI Enhance this entry? (rewrite description + estimate time)")) return;
  await withLoading("🪄 Enhancing entry...", async () => {
    try {
      await enhanceLog(logId);
      await loadData();
      showToast("✅ Entry enhanced!", "success");
    } catch (err) {
      showToast(`❌ ${err.message}`, "error", 5000);
    }
  });
}

/**
 * Batch-enhance logs missing descriptions or time estimates.
 */
export async function enhanceBatchAction() {
  const btn = document.getElementById("btn-ai-enhance");
  if (!btn) return;
  btn.disabled = true;
  btn.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> Enhancing...';
  try {
    await enhanceBatch();
    await loadData();
    showToast("✅ Batch enhance complete!", "success");
  } catch (err) {
    showToast(`❌ ${err.message}`, "error", 5000);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-wand"></i> Auto-Enhance';
  }
}

/**
 * Update the AI status badge visibility.
 */
export function updateAIStatusBadge() {
  const inlineBadge = document.getElementById("ai-status-inline");
  if (state.aiEnabled) {
    if (inlineBadge) inlineBadge.style.display = "inline-flex";
  } else if (inlineBadge) {
    inlineBadge.style.display = "none";
  }
}

// ─── Summary panel ─────────────────────────────────────

/**
 * Open the AI summary panel with a default 7-day range.
 */
export function openSummaryPanel() {
  const summaryPanel = document.getElementById("summary-panel");
  if (!summaryPanel) return;
  summaryPanel.style.display = "block";

  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
  document.getElementById("summary-from").value = weekAgo;
  document.getElementById("summary-to").value = today;
  document.getElementById("summary-result").innerHTML =
    '<span class="text-muted fst-italic">Click Generate to create AI summary.</span>';
  summaryPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Close the AI summary panel.
 */
export function closeSummaryPanel() {
  const summaryPanel = document.getElementById("summary-panel");
  if (summaryPanel) summaryPanel.style.display = "none";
}

/**
 * Generate an AI summary for the selected date range.
 */
export async function generateSummary() {
  const resultDiv = document.getElementById("summary-result");
  if (!resultDiv) return;
  resultDiv.innerHTML =
    '<div class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></div> Generating...';

  const from = document.getElementById("summary-from").value;
  const to = document.getElementById("summary-to").value;

  try {
    const data = await fetchSummary({
      date_from: from ? new Date(from).toISOString() : null,
      date_to: to ? new Date(to + "T23:59:59").toISOString() : null,
      period: "daily",
    });
    resultDiv.innerHTML = `<strong>📊 ${data.log_count} entries found</strong>\n\n${escapeHtml(data.summary)}`;
  } catch (err) {
    resultDiv.innerHTML = `<span style="color:#dc3545">❌ ${escapeHtml(err.message)}</span>`;
  }
}

// ─── Chat panel ────────────────────────────────────────

/**
 * Toggle the AI chat panel visibility.
 */
export function toggleChatPanel() {
  const chatPanel = document.getElementById("chat-panel");
  if (!chatPanel) return;
  if (chatPanel.style.display === "none" || chatPanel.style.display === "") {
    chatPanel.style.display = "block";
    chatPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  } else {
    chatPanel.style.display = "none";
  }
}

/**
 * Append a chat message bubble to the chat log.
 * @param {string} content - HTML content of the message.
 * @param {"user"|"bot"} [role="bot"] - Message author.
 */
function addChatMessage(content, role = "bot") {
  const container = document.getElementById("chat-messages");
  if (!container) return;
  const msg = document.createElement("div");
  msg.className = `chat-msg ${role}`;
  msg.setAttribute("role", "log");
  msg.innerHTML = content;
  container.appendChild(msg);
  container.scrollTop = container.scrollHeight;
}

/** @type {boolean} Whether a chat request is in flight. */
let chatBusy = false;

/**
 * Send the current chat input value to the AI.
 */
export async function sendChatMessage() {
  if (chatBusy) return;
  const input = document.getElementById("chat-input");
  const query = input.value.trim();
  if (!query) return;

  chatBusy = true;
  addChatMessage(escapeHtml(query), "user");
  input.value = "";
  addChatMessage("⏳ Thinking...", "bot");

  const msgs = document.getElementById("chat-messages");
  const thinkingMsg = msgs ? msgs.lastElementChild : null;

  try {
    const data = await askAI(query);
    if (thinkingMsg) thinkingMsg.remove();
    addChatMessage(escapeHtml(data.answer), "bot");
  } catch (err) {
    if (thinkingMsg) thinkingMsg.remove();
    addChatMessage(`❌ Error: ${escapeHtml(err.message)}`, "bot");
  } finally {
    chatBusy = false;
  }
}

/**
 * Toggle the AI Harness panel body visibility.
 */
export function toggleAIPanel() {
  const body = document.getElementById("ai-body");
  const toggle = document.getElementById("ai-toggle-icon");
  if (!body) return;
  const isHidden = body.style.display === "none" || body.style.display === "";
  body.style.display = isHidden ? "block" : "none";
  if (toggle) toggle.style.transform = isHidden ? "rotate(0deg)" : "rotate(-180deg)";
}

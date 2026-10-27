/**
 * AI Settings modal — provider presets, save/test connection, model dropdown.
 */

import { state } from "./state.js";
import { fetchSettings, saveSettings, testConnection } from "./api.js";
import { showToast } from "./toast.js";
import { withButtonLoading } from "./loading.js";

/** Provider presets shown in the settings modal. */
export const PROVIDER_PRESETS = {
  openai: {
    base_url: "https://api.openai.com/v1",
    model: "gpt-4o",
    key_hint:
      'Get key at <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">platform.openai.com/api-keys</a>',
    model_hint: "Models: gpt-4o, gpt-4o-mini, gpt-4-turbo",
  },
  gemini: {
    base_url: "https://generativelanguage.googleapis.com/v1beta/openai/",
    model: "gemini-2.0-flash",
    key_hint:
      'Get free API key at <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a>',
    model_hint: "Models: gemini-2.0-flash, gemini-2.5-pro, gemini-1.5-pro",
  },
  anthropic: {
    base_url: "https://api.anthropic.com/v1",
    model: "claude-sonnet-4-20250514",
    key_hint:
      'Get key at <a href="https://console.anthropic.com" target="_blank" rel="noopener">console.anthropic.com</a>',
    model_hint: "Models: claude-sonnet-4-20250514, claude-3-5-sonnet-20241022",
  },
  openrouter: {
    base_url: "https://openrouter.ai/api/v1",
    model: "openai/gpt-4o",
    key_hint: 'Get key at <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">openrouter.ai/keys</a>',
    model_hint: "Thousands of models available",
  },
  deepseek: {
    base_url: "https://api.deepseek.com",
    model: "deepseek-chat",
    key_hint:
      'Get key at <a href="https://platform.deepseek.com" target="_blank" rel="noopener">platform.deepseek.com</a>',
    model_hint: "Models: deepseek-chat, deepseek-reasoner",
  },
  custom: {
    base_url: "",
    model: "",
    key_hint: "Enter your API key",
    model_hint: "Enter any OpenAI-compatible model name",
  },
};

/**
 * Update the settings form when the provider changes (URL/model presets + hints).
 */
export function onProviderChange() {
  const provider = document.getElementById("setting-ai-provider").value;
  const preset = PROVIDER_PRESETS[provider];
  if (!preset) return;

  const urlField = document.getElementById("setting-ai-base-url");
  if (
    urlField &&
    (!urlField.value ||
      Object.keys(PROVIDER_PRESETS).some((p) => PROVIDER_PRESETS[p].base_url === urlField.value))
  ) {
    urlField.value = preset.base_url;
  }

  const modelField = document.getElementById("setting-ai-model");
  if (
    modelField &&
    (!modelField.value ||
      Object.keys(PROVIDER_PRESETS).some((p) => PROVIDER_PRESETS[p].model === modelField.value))
  ) {
    modelField.value = preset.model;
  }

  const hint = document.getElementById("ai-key-hint");
  if (hint && preset.key_hint) hint.innerHTML = preset.key_hint;

  const modelHint = document.getElementById("ai-model-hint");
  if (modelHint && preset.model_hint) modelHint.textContent = preset.model_hint;
}

/**
 * Toggle API key input visibility between password and text.
 */
export function toggleApiKeyVisibility() {
  const keyField = document.getElementById("setting-ai-api-key");
  const icon = document.querySelector("#btn-toggle-key i");
  if (keyField.type === "password") {
    keyField.type = "text";
    if (icon) icon.className = "bi bi-eye-slash";
  } else {
    keyField.type = "password";
    if (icon) icon.className = "bi bi-eye";
  }
}

/**
 * Load settings from the API and populate the form.
 *
 * @returns {Promise<void>}
 */
export async function loadSettings() {
  try {
    const data = await fetchSettings();
    const s = data.settings || {};

    setFieldValue("setting-ai-enabled", s.ai_enabled || "false");
    setFieldValue("setting-ai-provider", s.ai_provider || "openai");
    setFieldValue("setting-ai-api-key", s.ai_api_key || "");
    setFieldValue("setting-ai-base-url", s.ai_base_url || "");
    setFieldValue("setting-ai-model", s.ai_model || "");

    onProviderChange();

    state.aiEnabled = s.ai_enabled === "true" && !!s.ai_api_key;
    updateAIUI();
  } catch {
    console.warn("Settings load deferred (may load later).");
  }
}

/**
 * Set a field value if the element exists.
 * @param {string} id - Element id.
 * @param {string} value - Value to set.
 */
function setFieldValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.value = value;
}

/**
 * Update AI status badges in the UI based on state.aiEnabled.
 */
export function updateAIUI() {
  const inlineBadge = document.getElementById("ai-status-inline");
  const topBadge = document.getElementById("ai-status-badge");
  if (state.aiEnabled) {
    if (inlineBadge) inlineBadge.style.display = "inline-flex";
    if (topBadge) topBadge.style.display = "inline-flex";
  } else {
    if (inlineBadge) inlineBadge.style.display = "none";
    if (topBadge) topBadge.style.display = "none";
  }
}

/**
 * Handle the settings form submit — save all fields.
 * @param {Event} e - Submit event.
 */
export async function handleSettingsSave(e) {
  e.preventDefault();

  const items = [
    { key: "ai_enabled", value: document.getElementById("setting-ai-enabled").value },
    { key: "ai_provider", value: document.getElementById("setting-ai-provider").value },
    { key: "ai_api_key", value: document.getElementById("setting-ai-api-key").value },
    { key: "ai_base_url", value: document.getElementById("setting-ai-base-url").value },
    { key: "ai_model", value: document.getElementById("setting-ai-model").value },
  ];

  const btn = document.getElementById("btn-save-settings");
  await withButtonLoading(btn, "Saving...", async () => {
    try {
      await saveSettings(items);
      showToast("✅ AI settings saved!", "success");
      closeSettingsModal();
      await loadSettings();
    } catch (err) {
      showToast(`❌ ${err.message}`, "error", 5000);
    }
  });
}

/**
 * Test the LLM connection and populate the model dropdown on success.
 */
export async function testAIConnection() {
  const btn = document.getElementById("btn-test-ai");
  const result = document.getElementById("ai-test-result");
  const modelStatus = document.getElementById("model-load-status");

  btn.disabled = true;
  btn.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> Testing...';
  result.textContent = "";
  result.style.color = "#64748b";
  if (modelStatus) modelStatus.textContent = "";

  const data = {
    provider: document.getElementById("setting-ai-provider").value,
    api_key: document.getElementById("setting-ai-api-key").value,
    base_url: document.getElementById("setting-ai-base-url").value,
    model: document.getElementById("setting-ai-model").value,
  };

  if (!data.api_key) {
    showTestResult("⚠️ Please enter an API key first", "#dc3545");
    resetTestButton(btn);
    return;
  }

  try {
    const res = await testConnection(data);
    if (res.status === "success") {
      const connMsg =
        res.models && res.models.length > 0
          ? `✅ Connected! Found ${res.models.length} models`
          : `✅ Connected!${res.response ? ` Response: "${res.response}"` : ""}`;
      showTestResult(connMsg, "#28a745");

      if (res.models && res.models.length > 0) {
        populateModelDropdown(res.models, res.suggested_model);
        if (modelStatus) {
          modelStatus.textContent = `✅ Loaded ${res.models.length} models`;
          modelStatus.style.color = "#28a745";
        }
      } else if (modelStatus) {
        modelStatus.textContent =
          "ℹ️ No models list available. You can type the model name manually.";
        modelStatus.style.color = "#64748b";
      }
    } else {
      showTestResult(`❌ ${res.message || "Connection failed"}`, "#dc3545");
      restoreModelInput();
    }
  } catch (err) {
    showTestResult(`❌ ${err.message}`, "#dc3545");
    restoreModelInput();
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-plug me-1"></i>Test Connection & Load Models';
  }
}

/**
 * Show the test-connection result message.
 * @param {string} text - Message.
 * @param {string} color - CSS color.
 */
function showTestResult(text, color) {
  const result = document.getElementById("ai-test-result");
  if (result) {
    result.textContent = text;
    result.style.color = color;
  }
}

/**
 * Replace the model text input with a select dropdown of available models.
 * @param {Array<{id: string, owned_by: string}>} models - Available models.
 * @param {string} suggested - Recommended model id.
 */
function populateModelDropdown(models, suggested) {
  const wrapper = document.getElementById("model-input-wrapper");
  const currentVal = document.getElementById("setting-ai-model").value;

  let html = '<select class="form-select" id="setting-ai-model">';
  for (const m of models) {
    const selected = m.id === suggested || m.id === currentVal ? "selected" : "";
    const label = m.owned_by ? `${m.id} (${m.owned_by})` : m.id;
    html += `<option value="${escapeHtml(m.id)}" ${selected}>${escapeHtml(label)}</option>`;
  }
  html += '<option value="__custom__">✦ Custom model...</option>';
  html += "</select>";

  wrapper.innerHTML = html;

  const select = document.getElementById("setting-ai-model");
  select.addEventListener("change", function () {
    if (this.value === "__custom__") {
      const manual = prompt("Enter model name:");
      if (manual) {
        const opt = document.createElement("option");
        opt.value = manual;
        opt.textContent = `✦ ${manual}`;
        opt.selected = true;
        this.insertBefore(opt, this.querySelector('[value="__custom__"]'));
      } else {
        this.selectedIndex = 0;
      }
    }
  });

  const hint = document.getElementById("ai-model-hint");
  if (hint) {
    hint.textContent = `✅ ${models.length} models loaded from API. Select or choose "Custom model..." to type manually.`;
  }
}

/**
 * Restore the plain text input for the model field.
 */
function restoreModelInput() {
  const wrapper = document.getElementById("model-input-wrapper");
  const select = document.getElementById("setting-ai-model");
  const currentVal = select ? select.value : "";
  wrapper.innerHTML = `<input type="text" class="form-control" id="setting-ai-model" placeholder="gpt-4o (click Test Connection to load models)" value="${currentVal}" />`;
}

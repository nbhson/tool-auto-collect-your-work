/**
 * Loading state helpers — overlay + per-button spinners.
 */

/** @type {number} Count of concurrent loading operations. */
let loadingStack = 0;

/**
 * Show the global loading overlay.
 * @param {string} [message="Processing..."] - Message displayed under the spinner.
 */
export function showLoading(message = "Processing...") {
  loadingStack++;
  const overlay = document.getElementById("loading-overlay");
  const text = document.getElementById("loading-text");
  if (overlay && text) {
    text.textContent = message;
    overlay.classList.add("active");
    overlay.setAttribute("aria-hidden", "false");
  }
}

/**
 * Hide the global loading overlay (reference-counted).
 */
export function hideLoading() {
  loadingStack = Math.max(0, loadingStack - 1);
  if (loadingStack === 0) {
    const overlay = document.getElementById("loading-overlay");
    if (overlay) {
      overlay.classList.remove("active");
      overlay.setAttribute("aria-live", "polite");
    }
  }
}

/**
 * Run an async function while showing the loading overlay.
 *
 * @template T
 * @param {string} message - Loading message.
 * @param {() => Promise<T>} fn - Async operation.
 * @returns {Promise<T>} Result of fn.
 */
export async function withLoading(message, fn) {
  showLoading(message);
  try {
    return await fn();
  } finally {
    hideLoading();
  }
}

/**
 * Run an async function with the button in a loading (disabled + spinner) state.
 *
 * @param {HTMLButtonElement|null} btn - Button element.
 * @param {string} loadingText - Text shown while loading.
 * @param {function(): Promise<any>} fn - Async operation.
 * @returns {Promise<any>} Result of fn.
 */
export async function withButtonLoading(btn, loadingText, fn) {
  if (!btn) return fn();
  const origHTML = btn.innerHTML;
  const origDisabled = btn.disabled;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" aria-hidden="true"></span> ${loadingText}`;
  try {
    return await fn();
  } finally {
    btn.disabled = origDisabled;
    btn.innerHTML = origHTML;
  }
}

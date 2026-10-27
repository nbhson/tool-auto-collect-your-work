/**
 * Toast notifications — success / error / info feedback.
 */

/**
 * Show a toast notification.
 *
 * @param {string} message - HTML-escaped or trusted message to display.
 * @param {"success"|"error"|"info"} [type="info"] - Toast type (color coded).
 * @param {number} [duration=3500] - Auto-dismiss delay in ms.
 */
export function showToast(message, type = "info", duration = 3500) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast-custom ${type}`;
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", type === "error" ? "assertive" : "polite");
  toast.innerHTML = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/**
 * Show a success toast.
 * @param {string} message - Message text.
 */
export function toastSuccess(message) {
  showToast(message, "success");
}

/**
 * Show an error toast.
 * @param {string} message - Error message.
 */
export function toastError(message) {
  showToast(`❌ ${message}`, "error", 5000);
}

/**
 * Show an info toast.
 * @param {string} message - Message text.
 */
export function toastInfo(message) {
  showToast(message, "info");
}

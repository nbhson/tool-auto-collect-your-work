/**
 * Theme handling — light/dark toggle with localStorage persistence.
 */

import { state } from "./state.js";

/** localStorage key for the theme preference. */
const THEME_KEY = "wlh-theme";

/**
 * Load the persisted theme and apply it to the document.
 */
export function loadTheme() {
  try {
    state.theme = localStorage.getItem(THEME_KEY) || "light";
  } catch {
    state.theme = "light";
  }
  applyTheme();
}

/**
 * Apply the current theme to <html> and update the toggle icon.
 */
function applyTheme() {
  document.documentElement.setAttribute("data-theme", state.theme);
  const icon = document.querySelector("#theme-toggle-btn i");
  if (icon) {
    icon.className = state.theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
  }
  const toggleBtn = document.getElementById("theme-toggle-btn");
  if (toggleBtn) {
    toggleBtn.setAttribute(
      "aria-label",
      state.theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
    );
  }
}

/**
 * Persist the theme choice (best effort).
 */
function saveTheme() {
  try {
    localStorage.setItem(THEME_KEY, state.theme);
  } catch {
    /* localStorage unavailable — theme won't persist */
  }
}

/**
 * Toggle between light and dark theme.
 */
export function toggleTheme() {
  state.theme = state.theme === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", state.theme);
  saveTheme();
}

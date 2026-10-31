// @ts-check
import globals from "globals";

/** @type {import("eslint").Linter.Config[]} */
export default [
  {
    ignores: ["node_modules/**", ".venv/**"],
  },
  {
    files: ["static/js/**/*.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      globals: {
        ...globals.browser,
        bootstrap: "readonly", // Bootstrap 5 global (loaded via CDN)
      },
    },
    rules: {
      "no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "no-undef": "error",
      eqeqeq: ["error", "smart"],
      "prefer-const": "error",
      "no-var": "error",
    },
  },
];

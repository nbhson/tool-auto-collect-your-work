# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-10-27

### Added

**Backend**

- `core/` package: custom exception hierarchy (`AppError`, `NotFoundError`, `ValidationError`,
  `ExternalServiceError`, `ConfigurationError`, `AIServiceError`) with automatic HTTP status
  mapping via `register_exception_handlers(app)`.
- Structured logging (`core/logging_config.py`) with JSON formatter, configurable via
  `LOG_LEVEL`; validated logs router now returns 422 for invalid date filters instead of
  silently ignoring them.
- Polling resilience: shared `request_with_retry` helper (`pollers/http.py`) with exponential
  backoff, `Retry-After` header support, and `POLLER_MAX_RETRIES` / `POLLER_INITIAL_DELAY`
  configuration.
- `services/settings_service.py` to deduplicate settings lookup logic.
- Test suite: **53 unit tests** covering routers, pollers, exceptions, and export
  (`pytest tests/`).
- Python tooling: `pyproject.toml` (ruff + pytest config), `requirements-dev.txt`.

**Frontend**

- Vanilla JS ES modules (no build step) in `static/js/`: `api.js` (fetch with
  AbortController timeout + GET retry), `state.js`, `toast.js`, `loading.js`, `format.js`,
  `stats.js`, `table.js`, `data.js`, `theme.js`, `settings.js`, `ai.js`, `main.js`.
- Toast notifications replace all `alert()` calls; global loading overlay with
  `withLoading` / `withButtonLoading` helpers.
- Frontend tooling: `package.json` (ESLint 9 + Prettier), `eslint.config.mjs`, `.prettierrc`,
  `.prettierignore`.

**UI/UX**

- Dark mode with persisted preference and system-preference detection.
- Loading skeletons, spinners, and button loading states.
- Accessibility: skip link, `:focus-visible` rings, ARIA labels/live regions,
  `prefers-reduced-motion` support, screen-reader-only utility class.

### Changed

- `/api/poll` now polls **all** configured sources (github, jira, bitbucket, git_hooks)
  instead of only GitHub; unconfigured sources return `"disabled"`. Response shape
  (`{status, results, message}`) is unchanged — the new keys are additive/backward compatible.
- `export.py` uses `Depends(get_db)` for proper dependency injection.
- Frontend entry point moved from `static/script.js` (1410-line IIFE) to
  `static/js/main.js` + modules; all inline `onclick` handlers still work via `window.*`
  exposure.
- Cache-bust query params bumped to `?v=2.0.0`.

### Fixed

- Settings router had a bottom-of-file `httpx` import that could shadow the top-level import.
- Duplicate `renderSparkline`, `renderDescription`, and `saveTheme` definitions in the
  monolithic script were consolidated into single module implementations.
- Export buttons did not disable during download; poll button now shows a spinner and
  restores its original content in `finally`.

## [1.x] — Previous releases

See git history (`git log`) for changes prior to this changelog.

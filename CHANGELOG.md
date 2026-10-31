# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.1] - 2026-10-31

### Fixed

**Backend**

- `GET /api/logs/stats`: tính đầu tuần bằng `timedelta(days=weekday)` thay vì
  `replace(day=...)` — bản cũ gây `ValueError` khi đầu tuần rơi trước ngày 1-3 của tháng.
- Thêm `jinja2` vào `requirements.txt` (runtime dependency) — `routers/web.py` dùng
  `Jinja2Templates` nhưng trước đây chỉ có trong môi trường dev, app crash khi boot
  với venv sạch.
- `routers/logs.py`: `WorkLogOut` dùng `model_config = ConfigDict(from_attributes=True)`
  thay cho `class Config` (bị phản đối trong Pydantic v2).

**Frontend**

- `api.js`: sửa bug gọi boolean như hàm — `const canRetry` (boolean) shadow hàm
  `canRetry(method)` khiến mọi request throw `TypeError`. Đổi thành biến `retryable`
  và xoá hàm thừa.
- `settings.js`: thêm `import { escapeHtml }` bị thiếu (ReferenceError khi load danh
  sách models); định nghĩa `resetTestButton()` bị thiếu (ReferenceError khi API key
  trống); gọi `window.closeSettingsModal()` tường minh thay vì phụ thuộc global ẩn.
- `eslint.config.mjs`: dùng preset `globals.browser` thay danh sách global thủ công
  (trước đây thiếu `localStorage`, `URLSearchParams`, `performance`,
  `requestAnimationFrame`, `prompt`, ...) — 13 ESLint errors → 0.
- Chạy `prettier --write` toàn bộ JS/CSS/HTML; tăng cache-bust lên `?v=2.0.1`.

### Changed

- Thêm `core/utils.py` với `utc_now()` — thay 17 chỗ lặp pattern
  `datetime.now(UTC).replace(tzinfo=None)`.
- `routers/poll.py`: gộp 3 khối try/except trùng lặp vào helper `_run_poller()`.

### Added

- Unit tests cho `config.py` (14 tests), `app.py` (9 tests) và `core/utils.py`
  (3 tests) — tổng số test 53 → 77.

### Dependencies

- Minor bumps (đã verify với toàn bộ test suite trên Python 3.12 & 3.13):
  fastapi 0.115.6 → 0.162.0, uvicorn 0.34.0 → 0.54.0, sqlalchemy 2.0.36 → 2.1.6,
  apscheduler 3.10.4 → 3.11.3, python-dotenv 1.0.1 → 1.2.4, python-multipart
  0.0.19 → 0.0.32; pytest 8.3.4 → 9.1.1, pytest-asyncio 0.25.2 → 1.4.1,
  pytest-cov 6.0.0 → 7.1.0, ruff 0.8.6 → 0.17.3.

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

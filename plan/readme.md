# Plan — tool-auto-collect-your-work

App thu thập công việc tự động: Python/FastAPI (routers, services, pollers, database) + frontend JS, pytest.

## Baseline audit (00:44, 28-10-2026)
- Tests: ✅ **53 pass** (7 files), 1 warning deprecation (starlette testclient httpx)
- Lint: ❌ **ruff: 29 lỗi** (24 fixable tự động)
- Chú ý: `worklog.db` (SQLite) nằm trong thư mục repo — cần xác nhận .gitignore

## Roadmap
### P0 (chặn)
- [ ] `ruff check --fix` + sửa tay phần còn lại → 0 lỗi
- [ ] Kiểm tra `.gitignore` có bao phủ `worklog.db`, `__pycache__`, `.venv`
- [ ] Pin/khắc phục warning deprecation testclient

### P1 (chất lượng)
- [ ] Audit routers/services: error handling, validation input, auth
- [ ] Audit pollers: retry, timeout, idempotency (đã có dedup PR/issue)
- [ ] Coverage test

### P2 (hardening)
- [ ] CI workflow (pytest + ruff)
- [ ] Docs: kiến trúc + hướng dẫn chạy

## Self-review log
- _0:44_ Audit lần 1: 53/53 pass, ruff 29 lỗi.

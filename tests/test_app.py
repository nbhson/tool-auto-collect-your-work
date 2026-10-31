"""Tests cho app.py — cấu trúc app, routers, lifespan, exception handlers."""

from fastapi.testclient import TestClient

EXPECTED_API_PATHS = {
    "/api/logs",
    "/api/logs/stats",
    "/api/export/excel",
    "/api/export/excel/{source}",
    "/api/settings",
    "/api/settings/test",
    "/api/ai/classify/{log_id}",
    "/api/ai/classify",
    "/api/ai/summarize",
    "/api/ai/analyze",
    "/api/poll",
}


class TestAppStructure:
    """App FastAPI được tạo đúng với metadata và routers đầy đủ."""

    def test_app_metadata(self, client):
        from app import app

        assert app.title == "Work Log Harness"
        assert app.version == "1.1.0"

    def test_all_api_routes_registered(self, client):
        from app import app

        paths = set(app.openapi()["paths"])
        missing = EXPECTED_API_PATHS - paths
        assert not missing, f"Thiếu endpoints: {missing}"

    def test_static_files_mounted(self, client):
        from app import app

        mounts = [r.path for r in app.routes if r.__class__.__name__ == "Mount"]
        assert "/static" in mounts

    def test_index_page_served(self, client):
        """GET / trả về HTML dashboard."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Work Log" in resp.text

    def test_static_assets_served(self, client):
        resp = client.get("/static/js/main.js")
        assert resp.status_code == 200

    def test_unknown_api_returns_404(self, client):
        resp = client.get("/api/unknown-endpoint")
        assert resp.status_code == 404


class TestLifespan:
    """Lifespan khởi tạo DB + scheduler (mock) khi boot qua TestClient."""

    def test_app_boots_and_serves(self, client: TestClient):
        # Fixture `client` chạy đủ lifespan: init_db + start_scheduler
        resp = client.get("/api/logs/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_logs" in data
        assert "total_time_hours" in data


class TestErrorHandling:
    """AppError được map thành JSON response đúng status code."""

    def test_not_found_error_returns_404_json(self, client):
        resp = client.patch("/api/logs/999999999", json={"title": "x"})
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "NotFoundError"
        assert "detail" in body

    def test_validation_error_on_bad_date(self, client):
        resp = client.get("/api/logs", params={"from": "not-a-date"})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "ValidationError"

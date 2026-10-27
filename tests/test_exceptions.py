"""Unit tests for custom exceptions and error handling."""

from datetime import UTC, datetime

from core.exceptions import (
    AIServiceError,
    AppError,
    ConfigurationError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Verify exception hierarchy and status codes."""

    def test_base_error(self):
        err = AppError("Something went wrong")
        assert err.status_code == 500
        assert err.detail == "Something went wrong"
        assert err.to_dict() == {
            "error": "AppError",
            "detail": "Something went wrong",
        }

    def test_not_found_error(self):
        err = NotFoundError("Log not found")
        assert err.status_code == 404
        assert isinstance(err, AppError)

    def test_validation_error(self):
        err = ValidationError("Bad input")
        assert err.status_code == 422
        assert isinstance(err, AppError)

    def test_external_service_error(self):
        err = ExternalServiceError("GitHub API down")
        assert err.status_code == 502

    def test_configuration_error(self):
        err = ConfigurationError("Missing JIRA_URL")
        assert err.status_code == 500

    def test_ai_service_error(self):
        err = AIServiceError("LLM timeout")
        assert err.status_code == 502

    def test_extra_data(self):
        err = NotFoundError("Not found", extra={"resource": "log", "id": 123})
        data = err.to_dict()
        assert data["extra"] == {"resource": "log", "id": 123}

    def test_default_detail(self):
        err = NotFoundError()
        assert err.detail == "Resource not found."


class TestExceptionHTTPResponses:
    """Test that exceptions map to proper HTTP responses."""

    def test_404_response(self, client):
        """NotFoundError maps to 404 with error field."""
        resp = client.delete("/api/logs/99999")
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"] == "NotFoundError"
        assert "detail" in data

    def test_422_response(self, client):
        """ValidationError maps to 422."""
        resp = client.get("/api/export/excel/not_a_source")
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"] == "ValidationError"

    def test_400_response_ai_disabled(self, client, db_session):
        """ConfigurationError when AI is not configured."""
        from database.models import WorkLog

        log = WorkLog(
            source="manual",
            activity_type="meeting",
            title="Test",
            activity_timestamp=datetime.now(UTC).replace(tzinfo=None),
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        # AI is not enabled → ConfigurationError (500)
        resp = client.post(f"/api/ai/classify/{log.id}")
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "ConfigurationError"

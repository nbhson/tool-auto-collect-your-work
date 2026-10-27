"""Custom application exceptions with HTTP status codes."""

from typing import Any


class AppError(Exception):
    """Base application exception."""

    status_code: int = 500
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None, extra: dict[str, Any] | None = None):
        super().__init__(detail or self.detail)
        if detail:
            self.detail = detail
        self.extra = extra or {}

    def to_dict(self) -> dict[str, Any]:
        result = {"error": self.__class__.__name__, "detail": self.detail}
        if self.extra:
            result["extra"] = self.extra
        return result


class NotFoundError(AppError):
    """Resource not found."""

    status_code = 404
    detail = "Resource not found."


class ValidationError(AppError):
    """Input validation failed."""

    status_code = 422
    detail = "Validation error."


class ExternalServiceError(AppError):
    """Error calling external service (GitHub, Jira, etc.)."""

    status_code = 502
    detail = "External service error."


class ConfigurationError(AppError):
    """Missing or invalid configuration."""

    status_code = 500
    detail = "Configuration error."


class AIServiceError(AppError):
    """AI/LLM service error."""

    status_code = 502
    detail = "AI service error."


def register_exception_handlers(app):
    """Register custom exception handlers with FastAPI app."""
    from fastapi.responses import JSONResponse

    @app.exception_handler(AppError)
    async def app_error_handler(request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request, exc: Exception):
        import logging

        logging.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": "InternalServerError", "detail": "An unexpected error occurred."},
        )

"""Core package: custom exceptions and shared utilities."""

from core.exceptions import (
    AIServiceError,
    AppError,
    ConfigurationError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
    register_exception_handlers,
)

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationError",
    "ExternalServiceError",
    "ConfigurationError",
    "AIServiceError",
    "register_exception_handlers",
]

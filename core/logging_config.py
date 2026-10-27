"""Structured logging configuration for Work Log Harness."""

import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Include extra fields set via LogRecord kw_args
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "message",
                "exc_info",
                "exc_text",
                "stack_info",
                "thread",
                "threadName",
                "relativeCreated",
                "extra_data",
            ) and not key.startswith("_"):
                log_data[key] = _serialize_value(value)

        result = " ".join(
            f"{k}={v}"
            for k, v in log_data.items()
            if k not in ("timestamp", "level", "logger", "message")
        )
        if result:
            return f"{log_data['timestamp']} [{log_data['level']}] {log_data['logger']} {log_data['message']} | {result}"
        return f"{log_data['timestamp']} [{log_data['level']}] {log_data['logger']} {log_data['message']}"


def _serialize_value(value: Any) -> Any:
    """Serialize a value for logging."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dict__"):
        return str(value)
    try:
        return repr(value)
    except Exception:
        return str(type(value).__name__)


def setup_logging(level: str = "INFO") -> None:
    """Configure logging for the application.

    Uses structured text format (readable, machine-parseable).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

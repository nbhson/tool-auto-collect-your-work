"""Shared HTTP client helper with retry + exponential backoff for pollers."""

import contextlib
import logging
import time
from typing import Any

import httpx

from config import config

logger = logging.getLogger(__name__)

# Retry settings — defaults
MAX_RETRIES: int = 3
INITIAL_DELAY: float = 1.0  # seconds
BACKOFF_FACTOR: float = 2.0
MAX_DELAY: float = 30.0


def _get_retry_config() -> tuple[int, float, float, float]:
    """Return (max_retries, initial_delay, backoff_factor, max_delay) from config."""
    return (
        getattr(config, "POLLER_MAX_RETRIES", MAX_RETRIES),
        getattr(config, "POLLER_INITIAL_DELAY", INITIAL_DELAY),
        BACKOFF_FACTOR,
        MAX_DELAY,
    )


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    auth: tuple[str, str] | None = None,
    timeout: float = 15.0,
    log_name: str = "HTTP",
) -> httpx.Response:
    """Perform an HTTP request with exponential backoff retry.

    Retries on connection errors and 5xx responses.
    Respects Retry-After header on 429 responses.
    """
    max_retries, initial_delay, backoff_factor, max_delay = _get_retry_config()

    delay = initial_delay
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            transport = httpx.HTTPTransport(retries=0)
            client = httpx.Client(timeout=timeout, transport=transport)

            try:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json,
                    auth=auth,
                )

                # Retry on 5xx and 429
                if response.status_code >= 500:
                    last_error = httpx.HTTPStatusError(
                        f"{log_name} {method} {url} → {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    # Check Retry-After header
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        with contextlib.suppress(ValueError):
                            delay = min(float(retry_after), max_delay)
                    elif attempt < max_retries:
                        delay = min(delay * backoff_factor, max_delay)
                    logger.warning(
                        "%s attempt %d failed: %s. Retrying in %.1fs...",
                        log_name,
                        attempt + 1,
                        last_error,
                        delay,
                    )
                    client.close()
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                    continue

                return response
            finally:
                client.close()

        except httpx.HTTPError as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    "%s attempt %d error: %s. Retrying in %.1fs...",
                    log_name,
                    attempt + 1,
                    e,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                break

    # All retries exhausted
    raise last_error or RuntimeError(f"{log_name} request failed after {max_retries + 1} attempts")

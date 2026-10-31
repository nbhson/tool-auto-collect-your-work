"""Tests cho core/utils.py."""

from datetime import datetime

from core.utils import utc_now


def test_utc_now_returns_datetime():
    assert isinstance(utc_now(), datetime)


def test_utc_now_is_naive():
    """utc_now trả về naive datetime (không tzinfo) — khớp cách DB lưu."""
    assert utc_now().tzinfo is None


def test_utc_now_close_to_real_utc():
    from datetime import UTC

    before = datetime.now(UTC).replace(tzinfo=None)
    result = utc_now()
    after = datetime.now(UTC).replace(tzinfo=None)
    assert before <= result <= after

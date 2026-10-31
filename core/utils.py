"""Tiện ích dùng chung cho toàn ứng dụng."""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Trả về thời điểm hiện tại theo UTC (naive datetime, không timezone).

    DB lưu naive UTC timestamp — helper này thay cho pattern lặp lại:
    ``datetime.now(UTC).replace(tzinfo=None)``.
    """
    return datetime.now(UTC).replace(tzinfo=None)

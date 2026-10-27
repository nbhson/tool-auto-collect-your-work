"""Shared settings service — get/set AppSetting values from DB.

Used by routers to avoid duplicating _get_setting logic.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from database.models import AppSetting

logger = logging.getLogger(__name__)


def get_setting(db: Session, key: str) -> str:
    """Get a setting value, returns empty string if not found."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else ""


def set_setting(db: Session, key: str, value: str) -> None:
    """Upsert a single setting."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    existing = db.query(AppSetting).filter(AppSetting.key == key).first()
    if existing:
        existing.value = value
        existing.updated_at = now
    else:
        db.add(AppSetting(key=key, value=value, updated_at=now))


def get_settings_dict(db: Session, *keys: str) -> dict[str, str]:
    """Get multiple settings as a dict."""
    rows = db.query(AppSetting).filter(AppSetting.key.in_(keys)).all()
    return {row.key: row.value for row in rows}


def mask_api_key(api_key: str) -> str:
    """Mask an API key for safe display."""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "***"
    return api_key[:8] + "****"

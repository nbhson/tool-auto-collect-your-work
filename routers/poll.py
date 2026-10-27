"""Poll Now endpoint — trigger background pollers thủ công.

Chạy đồng bộ tất cả pollers, trả về kết quả từng nguồn.
"""

import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["poll"])


@router.post("/poll")
def trigger_poll() -> dict[str, Any]:
    """Trigger tất cả pollers ngay lập tức.

    Chạy đồng bộ, trả về kết quả mỗi poller sau khi hoàn thành.
    """
    from config import config
    from pollers.bitbucket import poll_bitbucket
    from pollers.git_hook_reader import read_git_hooks
    from pollers.github import poll_github
    from pollers.jira import poll_jira

    results: dict[str, str] = {}

    # ─── GitHub ─────────────────────────────────────
    if config.GITHUB_TOKEN:
        try:
            poll_github()
            results["github"] = "ok"
        except Exception as e:
            logger.error("GitHub poll error: %s", e)
            results["github"] = f"error: {e}"
    else:
        results["github"] = "disabled"

    # ─── Jira ──────────────────────────────────────
    if config.JIRA_URL and config.JIRA_API_TOKEN:
        try:
            poll_jira()
            results["jira"] = "ok"
        except Exception as e:
            logger.error("Jira poll error: %s", e)
            results["jira"] = f"error: {e}"
    else:
        results["jira"] = "disabled"

    # ─── Bitbucket ─────────────────────────────────
    if config.BITBUCKET_USERNAME and config.BITBUCKET_APP_PASSWORD and config.BITBUCKET_WORKSPACE:
        try:
            poll_bitbucket()
            results["bitbucket"] = "ok"
        except Exception as e:
            logger.error("Bitbucket poll error: %s", e)
            results["bitbucket"] = f"error: {e}"
    else:
        results["bitbucket"] = "disabled"

    # ─── Git hooks ─────────────────────────────────
    try:
        read_git_hooks()
        results["git_hooks"] = "ok"
    except Exception as e:
        logger.error("Git hook read error: %s", e)
        results["git_hooks"] = f"error: {e}"

    successful = [k for k, v in results.items() if v == "ok"]
    failed = [k for k, v in results.items() if v.startswith("error:")]

    return {
        "status": "ok",
        "results": results,
        "message": (
            f"Sync complete: {len(successful)} sources OK"
            + (f", {len(failed)} failed ({', '.join(failed)})" if failed else "")
        ),
    }

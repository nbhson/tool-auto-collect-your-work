"""Poll Now endpoint — trigger background pollers thủ công.

Chạy đồng bộ tất cả pollers, trả về kết quả từng nguồn.
"""

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["poll"])


def _run_poller(
    name: str, enabled: bool, poll_fn: Callable[[], None], results: dict[str, str]
) -> None:
    """Chạy một poller và ghi kết quả vào ``results``.

    Lỗi poller được ghi log và báo trong results — không làm fail request.
    """
    if not enabled:
        results[name] = "disabled"
        return
    try:
        poll_fn()
        results[name] = "ok"
    except Exception as e:
        logger.error("%s poll error: %s", name.capitalize(), e)
        results[name] = f"error: {e}"


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

    _run_poller(
        "github",
        bool(config.GITHUB_TOKEN),
        poll_github,
        results,
    )
    _run_poller(
        "jira",
        bool(config.JIRA_URL and config.JIRA_API_TOKEN),
        poll_jira,
        results,
    )
    _run_poller(
        "bitbucket",
        bool(
            config.BITBUCKET_USERNAME
            and config.BITBUCKET_APP_PASSWORD
            and config.BITBUCKET_WORKSPACE
        ),
        poll_bitbucket,
        results,
    )
    # Git hooks luôn chạy (đọc file local, không cần config)
    _run_poller("git_hooks", True, read_git_hooks, results)

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

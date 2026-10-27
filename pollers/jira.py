"""Jira API poller — lấy danh sách issue đã update gần đây.

Sử dụng Jira Cloud REST API v3 để query các issue mà current user
đã có hoạt động (status change, assignee change, estimation change,
comment, v.v.) kể từ lần poll trước.

Cập nhật (24/07/2026):
  - JQL rộng: lấy tất cả issue trong project đã được update
    (không còn filter assignee=currentUser())
  - Fix: first-run since = now - 24h (trước kia = now → 0 results)
  - Ghi nhận tất cả field changes: status, assignee, estimation,
    summary, description, priority
  - Filter changelog theo user hiện tại (displayName / accountId)
  - Filter comments theo user hiện tại
"""

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from config import config
from database.db import SessionLocal
from database.models import WorkLog
from pollers.http import request_with_retry

logger = logging.getLogger("pollers.jira")

STATE_FILE = Path(__file__).resolve().parent.parent / "poller_state.json"


def _get_last_run() -> datetime | None:
    """Lấy thời điểm poll thành công gần nhất."""
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text())
        ts = data.get("jira_last_run")
        if ts:
            return datetime.fromisoformat(ts)
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def _save_last_run(dt: datetime) -> None:
    """Ghi thời điểm poll thành công."""
    data = {}
    if STATE_FILE.exists():
        with contextlib.suppress(json.JSONDecodeError):
            data = json.loads(STATE_FILE.read_text())
    data["jira_last_run"] = dt.isoformat()
    STATE_FILE.write_text(json.dumps(data, indent=2))


def _get_current_user(auth: tuple, base_url: str) -> dict:
    """Lấy thông tin user hiện tại từ Jira /rest/api/3/myself."""
    try:
        resp = request_with_retry(
            "GET",
            f"{base_url}/rest/api/3/myself",
            auth=auth,
            timeout=15,
            log_name="Jira",
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error("Could not determine current user: %s", e)
        return {}


def poll_jira() -> None:
    """Hàm chính được scheduler gọi định kỳ."""
    if not config.JIRA_URL or not config.JIRA_API_TOKEN:
        return

    auth = (config.JIRA_EMAIL, config.JIRA_API_TOKEN)
    base_url = config.JIRA_URL.rstrip("/")

    # ─── Lấy thông tin user hiện tại → dùng để filter changelog ──
    current_user = _get_current_user(auth, base_url)
    user_display = current_user.get("displayName", "")
    user_account = current_user.get("accountId", "")

    # ─── Tính 'since' timestamp ──────────────────────────────────
    last_run = _get_last_run()
    if last_run is None:
        # Lần đầu — lấy dữ liệu 24h gần nhất (fix: trước kia = now)
        since = datetime.now(UTC) - timedelta(hours=24)
    else:
        # Cộng thêm 2 phút overlap để không miss data
        since = last_run - timedelta(minutes=2)

    since_str = since.strftime("%Y-%m-%d %H:%M")

    # ─── JQL ─────────────────────────────────────────────────────
    # JQL rộng: tất cả issue trong project đã được update
    # Không filter assignee nữa — changelog sẽ được filter riêng
    if config.JIRA_PROJECT:
        jql = f"project={config.JIRA_PROJECT} AND updated>='{since_str}'"
    else:
        jql = f"updated>='{since_str}'"

    # Nếu không xác định được user → fallback assignee filter để tránh noise
    if not user_display and not user_account:
        jql = f"assignee=currentUser() AND {jql}"

    try:
        response = request_with_retry(
            "GET",
            f"{base_url}/rest/api/3/search",
            auth=auth,
            params={
                "jql": jql,
                "expand": "changelog",
                "maxResults": 50,
                "fields": "summary,updated,status,timeestimate,comment,project,assignee,priority",
            },
            timeout=30,
            log_name="Jira",
        )
        response.raise_for_status()
        data = response.json()

        db = SessionLocal()
        try:
            now = datetime.now(UTC).replace(tzinfo=None)
            new_count = 0

            for issue in data.get("issues", []):
                issue_key = issue.get("key", "")
                fields = issue.get("fields", {})
                changelog = issue.get("changelog", {}).get("histories", [])
                project_key = fields.get("project", {}).get("key", config.JIRA_PROJECT)

                # ─── Xử lý changelog ──────────────────────────
                for history in changelog:
                    author = history.get("author", {})
                    author_name = author.get("displayName", "")
                    author_id = author.get("accountId", "")

                    # Filter: chỉ ghi nhận thay đổi do user hiện tại thực hiện
                    # (thử match bằng accountId nếu displayName không khớp)
                    if (
                        user_display
                        and author_name
                        and author_name != user_display
                        and (not user_account or not author_id or author_id != user_account)
                    ):
                        continue

                    created = history.get("created", "")
                    try:
                        ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        ts = ts.replace(tzinfo=None)
                    except (ValueError, TypeError):
                        ts = now

                    # Xử lý từng field change trong history item
                    for item in history.get("items", []):
                        field = item.get("field", "")
                        from_str = item.get("fromString", "") or ""
                        to_str = item.get("toString", "") or ""

                        field_slug = field.replace(" ", "_").lower()
                        ext_id = f"{issue_key}_change_{history.get('id', '')}_{field_slug}"

                        # Kiểm tra trùng lặp
                        exists = db.query(WorkLog).filter(WorkLog.external_id == ext_id).first()
                        if exists:
                            continue

                        log = None

                        if field == "status":
                            log = WorkLog(
                                source="jira",
                                activity_type="status_change",
                                title=f"{issue_key}: {from_str} → {to_str}",
                                description=(
                                    f"Status changed from '{from_str}' to '{to_str}' "
                                    f"by {author_name}"
                                ),
                                project=project_key,
                                url=f"{base_url}/browse/{issue_key}",
                                activity_timestamp=ts,
                                time_spent_minutes=0,
                                external_id=ext_id,
                                created_at=now,
                            )

                        elif field in ("timeestimate", "timetracking", "timeoriginalestimate"):
                            log = WorkLog(
                                source="jira",
                                activity_type="estimation_change",
                                title=(
                                    f"{issue_key}: Estimation "
                                    f"{from_str or 'none'} → {to_str or 'none'}"
                                ),
                                description=(
                                    f"Estimation changed from '{from_str or 'none'}' "
                                    f"to '{to_str or 'none'}' by {author_name}"
                                ),
                                project=project_key,
                                url=f"{base_url}/browse/{issue_key}",
                                activity_timestamp=ts,
                                time_spent_minutes=0,
                                external_id=ext_id,
                                created_at=now,
                            )

                        elif field == "assignee":
                            log = WorkLog(
                                source="jira",
                                activity_type="assignee_change",
                                title=(
                                    f"{issue_key}: "
                                    f"{from_str or 'Unassigned'} → {to_str or 'Unassigned'}"
                                ),
                                description=(
                                    f"Assignee changed from '{from_str or 'unassigned'}' "
                                    f"to '{to_str or 'unassigned'}' by {author_name}"
                                ),
                                project=project_key,
                                url=f"{base_url}/browse/{issue_key}",
                                activity_timestamp=ts,
                                time_spent_minutes=0,
                                external_id=ext_id,
                                created_at=now,
                            )

                        elif field in ("summary", "description", "priority"):
                            log = WorkLog(
                                source="jira",
                                activity_type="ticket_update",
                                title=f"{issue_key}: {field} updated",
                                description=(
                                    f"Field '{field}' changed "
                                    f"by {author_name}: "
                                    f"'{from_str[:100] or ''}' → '{to_str[:100] or ''}'"
                                ),
                                project=project_key,
                                url=f"{base_url}/browse/{issue_key}",
                                activity_timestamp=ts,
                                time_spent_minutes=0,
                                external_id=ext_id,
                                created_at=now,
                            )

                        if log:
                            db.add(log)
                            new_count += 1

            # ─── Fetch comments ──────────────────────────────
            issue_keys = [i["key"] for i in data.get("issues", [])]
            comment_count = _fetch_comments(db, base_url, auth, issue_keys, user_display, now)
            new_count += comment_count

            if new_count > 0:
                db.commit()
                logger.info("Captured %d new activities", new_count)
                print(f"[Jira Poller] ✓ Captured {new_count} new activities")

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        _save_last_run(datetime.now(UTC).replace(tzinfo=None))

    except httpx.HTTPStatusError as e:
        logger.error(
            "HTTP Error: %s — %s",
            e.response.status_code,
            e.response.text[:200],
        )
        print(f"[Jira Poller] HTTP Error: {e.response.status_code} — {e.response.text[:200]}")
    except httpx.RequestError as e:
        logger.error("Connection Error: %s", e)
        print(f"[Jira Poller] Connection Error: {e}")
    except Exception as e:
        logger.exception("Unexpected Error: %s", e)
        print(f"[Jira Poller] Unexpected Error: {e}")


def _fetch_comments(
    db,
    base_url: str,
    auth: tuple,
    issue_keys: list[str],
    user_display: str,
    now: datetime,
) -> int:
    """Fetch comments mới — chỉ lấy comment của user hiện tại."""
    count = 0
    for key in issue_keys:
        try:
            resp = request_with_retry(
                "GET",
                f"{base_url}/rest/api/3/issue/{key}/comment",
                auth=auth,
                params={"orderBy": "-created", "maxResults": 50},
                timeout=15,
                log_name="Jira",
            )
            if resp.status_code != 200:
                continue
            comments = resp.json().get("comments", [])
            for comment in comments:
                author_info = comment.get("author", {})
                author_name = author_info.get("displayName", "")

                # Chỉ lấy comment của user hiện tại
                if user_display and author_name and author_name != user_display:
                    continue

                created = comment.get("created", "")
                try:
                    ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    ts = ts.replace(tzinfo=None)
                except (ValueError, TypeError):
                    continue

                comment_id = comment.get("id", "")
                external_id = f"{key}_comment_{comment_id}"
                exists = db.query(WorkLog).filter(WorkLog.external_id == external_id).first()
                if exists:
                    continue

                body = comment.get("body", "")
                text = _extract_adf_text(body) if isinstance(body, dict) else str(body)[:500]

                log = WorkLog(
                    source="jira",
                    activity_type="comment",
                    title=f"{key}: Commented on {key}",
                    description=text[:500],
                    project=config.JIRA_PROJECT or "",
                    url=f"{base_url}/browse/{key}?focusedCommentId={comment_id}",
                    activity_timestamp=ts,
                    time_spent_minutes=0,
                    external_id=external_id,
                    created_at=now,
                )
                db.add(log)
                count += 1
        except httpx.HTTPError:
            continue
    return count


def _extract_adf_text(adf: dict) -> str:
    """Trích xuất plain text từ Atlassian Document Format."""
    texts = []

    def _walk(node):
        if isinstance(node, dict):
            if node.get("type") == "text" and "text" in node:
                texts.append(node["text"])
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf)
    return " ".join(texts)[:500]

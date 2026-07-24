"""Bitbucket Server + Cloud API poller — lấy commits, PRs, activities gần đây.

Hỗ trợ:
  - Bitbucket Server / Data Center (REST API v1.0)
  - Bitbucket Cloud (REST API v2.0) — backward compatible

Tự động phát hiện loại instance dựa trên format của BITBUCKET_WORKSPACE:
  - URL dạng https://host/projects/PROJ → Bitbucket Server
  - Slug dạng workspace-name → Bitbucket Cloud (code cũ)
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

from config import config
from database.db import SessionLocal
from database.models import WorkLog


STATE_FILE = Path(__file__).resolve().parent.parent / "poller_state.json"


# ═══════════════════════════════════════════════════════════
#  Helpers chung
# ═══════════════════════════════════════════════════════════

def _get_last_run() -> Optional[datetime]:
    """Lấy thời điểm poll thành công gần nhất."""
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text())
        ts = data.get("bitbucket_last_run")
        if ts:
            return datetime.fromisoformat(ts)
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def _save_last_run(dt: datetime) -> None:
    """Ghi thời điểm poll thành công."""
    data = {}
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    data["bitbucket_last_run"] = dt.isoformat()
    STATE_FILE.write_text(json.dumps(data, indent=2))


def _parse_workspace() -> dict:
    """Phân tích BITBUCKET_WORKSPACE.

    Returns:
        {"type": "server", "base_url": str, "project": str}
        | {"type": "cloud", "workspace": str}
        | {"type": "unknown"}
    """
    ws = config.BITBUCKET_WORKSPACE.strip()
    if not ws:
        return {"type": "unknown"}

    # Bitbucket Server URL: https://host/projects/PROJ_KEY
    m = re.match(r'(https?://[^/]+)/projects/([A-Za-z0-9_]+)', ws)
    if m:
        return {
            "type": "server",
            "base_url": m.group(1),
            "project": m.group(2),
        }

    # Cloud slug
    return {"type": "cloud", "workspace": ws}


def _to_epoch_millis(dt: Optional[datetime]) -> Optional[int]:
    """Chuyển datetime → epoch milliseconds (int)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _from_epoch_millis(ms: int) -> datetime:
    """Chuyển epoch milliseconds → datetime (naive UTC)."""
    return datetime.fromtimestamp(ms / 1000)


# ═══════════════════════════════════════════════════════════
#  Entry point — phát hiện Server / Cloud
# ═══════════════════════════════════════════════════════════

def poll_bitbucket() -> None:
    """Hàm chính được scheduler gọi định kỳ."""
    ws_info = _parse_workspace()

    if ws_info["type"] == "unknown":
        if config.BITBUCKET_WORKSPACE:
            print(
                "[Bitbucket] Could not parse BITBUCKET_WORKSPACE="
                f"'{config.BITBUCKET_WORKSPACE}'"
            )
        else:
            print("[Bitbucket] No workspace configured, skipping")
        return

    if ws_info["type"] == "cloud":
        _poll_cloud(ws_info["workspace"])
        return

    _poll_server(ws_info)


# ═══════════════════════════════════════════════════════════
#  Bitbucket Server / Data Center
# ═══════════════════════════════════════════════════════════

def _get_current_user_server(auth: tuple, api_base: str) -> Optional[dict]:
    """Lấy thông tin authenticated user từ Bitbucket Server."""
    try:
        resp = httpx.get(
            f"{api_base}/user", auth=auth, timeout=15
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"[Bitbucket Server] Could not get current user: {e}")
        return None


def _poll_server(ws_info: dict) -> None:
    """Poll Bitbucket Server / Data Center REST API v1.0."""
    if not config.BITBUCKET_USERNAME or not config.BITBUCKET_APP_PASSWORD:
        print("[Bitbucket Server] Username or password missing, skipping")
        return

    auth = (config.BITBUCKET_USERNAME, config.BITBUCKET_APP_PASSWORD)
    base_url = ws_info["base_url"]
    project = ws_info["project"]
    api_base = f"{base_url}/rest/api/1.0"

    # ─── Current user ───────────────────────────────────
    current_user = _get_current_user_server(auth, api_base)
    user_name = (current_user or {}).get("name", "")
    user_display = (current_user or {}).get("displayName", "")
    user_email = (current_user or {}).get("emailAddress", "")

    # ─── Tính 'since' ────────────────────────────────────
    last_run = _get_last_run()
    if last_run is None:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
    else:
        since = last_run - timedelta(minutes=2)
    since_epoch = _to_epoch_millis(since) or 0

    now = datetime.utcnow()

    db = SessionLocal()
    try:
        new_count = 0

        # ─── Lấy repos ─────────────────────────────────
        repos = _server_get_repos(api_base, project, auth)
        if not repos:
            print(f"[Bitbucket Server] No repos found in project '{project}'")
            db.close()
            _save_last_run(now)
            return

        for repo in repos:
            repo_slug = repo.get("slug", "")
            repo_name = repo.get("name", repo_slug)
            if not repo_slug:
                continue

            repo_url_base = (
                f"{base_url}/projects/{project}/repos/{repo_slug}"
            )

            # ─── Commits ──────────────────────────────
            commits = _server_get_commits(
                api_base, project, repo_slug, auth, since_epoch
            )
            for commit in commits:
                try:
                    cnt = _process_server_commit(
                        db, commit, repo_name, repo_slug,
                        repo_url_base, user_name, user_display,
                        user_email, now, project,
                    )
                    new_count += cnt
                except Exception as e:
                    print(
                        f"[Bitbucket Server] Error processing commit "
                        f"in {repo_slug}: {e}"
                    )

            # ─── Pull Requests ─────────────────────────
            prs = _server_get_pull_requests(
                api_base, project, repo_slug, auth
            )
            for pr in prs:
                try:
                    cnt = _process_server_pr(
                        db, pr, repo_name, repo_slug,
                        repo_url_base, api_base, project,
                        user_name, user_display, user_email,
                        since_epoch, now, auth,
                    )
                    new_count += cnt
                except Exception as e:
                    print(
                        f"[Bitbucket Server] Error processing PR "
                        f"in {repo_slug}: {e}"
                    )

        if new_count > 0:
            db.commit()
            print(
                f"[Bitbucket Server] ✓ Captured {new_count} "
                f"new activities in project '{project}'"
            )

    except Exception as e:
        db.rollback()
        print(f"[Bitbucket Server] Error: {e}")
    finally:
        db.close()

    _save_last_run(now)


def _is_user_match(
    author_email: str, author_name: str,
    user_email: str, user_name: str, user_display: str,
) -> bool:
    """Kiểm tra author có khớp với user hiện tại không."""
    if not author_email and not author_name:
        return True  # Không có thông tin → lấy tất cả
    if user_email and author_email and user_email == author_email:
        return True
    if user_name and author_name and user_name == author_name:
        return True
    if user_display and author_name and user_display == author_name:
        return True
    return False


def _process_server_commit(
    db, commit: dict, repo_name: str, repo_slug: str,
    repo_url_base: str, user_name: str, user_display: str,
    user_email: str, now: datetime, project: str,
) -> int:
    """Xử lý một commit từ Bitbucket Server."""
    commit_hash = commit.get("id", "")
    if not commit_hash:
        return 0

    author = commit.get("author", {}) or {}
    author_email = author.get("emailAddress", "")
    author_name = author.get("name", "")

    if not _is_user_match(
        author_email, author_name,
        user_email, user_name, user_display,
    ):
        return 0

    ts_millis = commit.get("committerTimestamp", 0)
    try:
        ts = _from_epoch_millis(ts_millis)
    except (ValueError, TypeError):
        ts = now

    msg = commit.get("message", "")
    first_line = (msg.split("\n", 1)[0] if "\n" in msg else msg)[:100]

    external_id = f"bb_commit_{commit_hash}"
    exists = (
        db.query(WorkLog)
        .filter(WorkLog.external_id == external_id)
        .first()
    )
    if exists:
        return 0

    log = WorkLog(
        source="bitbucket",
        activity_type="commit",
        title=f"[{repo_name}] {first_line}",
        description=msg[:500],
        project=f"{project}/{repo_name}",
        url=f"{repo_url_base}/commits/{commit_hash}",
        activity_timestamp=ts,
        time_spent_minutes=0,
        external_id=external_id,
        created_at=now,
    )
    db.add(log)
    return 1


def _process_server_pr(
    db, pr: dict, repo_name: str, repo_slug: str,
    repo_url_base: str, api_base: str, project_key: str,
    user_name: str, user_display: str, user_email: str,
    since_epoch: int, now: datetime, auth_cred,
) -> int:
    """Xử lý một Pull Request và các activities từ Bitbucket Server."""
    pr_id = pr.get("id", 0)
    pr_title = pr.get("title", "")
    pr_state = pr.get("state", "OPEN")
    pr_updated = pr.get("updatedDate", 0)

    # Bỏ qua PR không có update gần đây
    if pr_updated < since_epoch:
        return 0

    pr_count = 0

    # ─── PR event (create / merge) ──────────────────────
    pr_author = pr.get("author", {}) or {}
    pr_user = pr_author.get("user", {}) or {}
    pr_author_name = pr_user.get("name", "")
    pr_author_email = pr_user.get("emailAddress", "")
    pr_author_display = pr_user.get("displayName", "")

    # Chỉ ghi nhận PR do user tạo
    if _is_user_match(
        pr_author_email, pr_author_name,
        user_email, user_name, user_display,
    ):
        ext_id = f"bb_pr_{repo_slug}_{pr_id}"
        exists = (
            db.query(WorkLog)
            .filter(WorkLog.external_id == ext_id)
            .first()
        )
        if not exists:
            ts = _from_epoch_millis(pr.get("createdDate", pr_updated))
            activity = "pr_create" if pr_state == "OPEN" else "pr_merge"
            log = WorkLog(
                source="bitbucket",
                activity_type=activity,
                title=f"[{repo_name}] PR #{pr_id}: {pr_title}",
                description=(
                    f"Pull Request #{pr_id} ({pr_state})"
                    f" — {pr_title}"
                ),
                project=f"{project_key}/{repo_name}",
                url=f"{repo_url_base}/pull-requests/{pr_id}",
                activity_timestamp=ts,
                time_spent_minutes=0,
                external_id=ext_id,
                created_at=now,
            )
            db.add(log)
            pr_count += 1

    # ─── PR Activities (comments, approvals) ────────────
    activities = _server_get_pr_activities(
        api_base, project_key, repo_slug, pr_id, auth_cred,
    )
    for act in activities:
        try:
            cnt = _process_server_activity(
                db, act, repo_name, repo_slug, pr_id,
                pr_title, repo_url_base, project_key,
                user_name, user_display, user_email,
                since_epoch, now,
            )
            pr_count += cnt
        except Exception as e:
            print(
                f"[Bitbucket Server] Error processing activity "
                f"for PR #{pr_id}: {e}"
            )

    return pr_count


def _process_server_activity(
    db, act: dict, repo_name: str, repo_slug: str,
    pr_id: int, pr_title: str, repo_url_base: str,
    project_key: str, user_name: str, user_display: str,
    user_email: str, since_epoch: int, now: datetime,
) -> int:
    """Xử lý một PR activity (comment, approve, merge)."""
    act_user = act.get("user", {}) or {}
    act_author_name = act_user.get("name", "")
    act_author_display = act_user.get("displayName", "")
    act_author_email = act_user.get("emailAddress", "")

    # Chỉ lấy activity của user hiện tại
    if not _is_user_match(
        act_author_email, act_author_name or act_author_display,
        user_email, user_name, user_display,
    ):
        return 0

    act_created = act.get("createdDate", 0)
    if act_created < since_epoch:
        return 0

    act_action = act.get("action", "")
    act_id = act.get("id", 0)
    display_name = act_author_display or act_author_name or "Unknown"

    if act_action == "COMMENTED":
        comment = act.get("comment", {}) or {}
        comment_text = comment.get("text", "")[:500]
        ext_id = f"bb_pr_comment_{repo_slug}_{pr_id}_{act_id}"
        exists = (
            db.query(WorkLog)
            .filter(WorkLog.external_id == ext_id)
            .first()
        )
        if exists:
            return 0

        ts = _from_epoch_millis(act_created)
        log = WorkLog(
            source="bitbucket",
            activity_type="pr_comment",
            title=(
                f"[{repo_name}] PR #{pr_id}: "
                f"{display_name} commented"
            ),
            description=comment_text or f"Comment on PR #{pr_id}",
            project=f"{project_key}/{repo_name}",
            url=f"{repo_url_base}/pull-requests/{pr_id}",
            activity_timestamp=ts,
            time_spent_minutes=0,
            external_id=ext_id,
            created_at=now,
        )
        db.add(log)
        return 1

    elif act_action == "APPROVED":
        ext_id = f"bb_pr_approve_{repo_slug}_{pr_id}_{act_id}"
        exists = (
            db.query(WorkLog)
            .filter(WorkLog.external_id == ext_id)
            .first()
        )
        if exists:
            return 0

        ts = _from_epoch_millis(act_created)
        log = WorkLog(
            source="bitbucket",
            activity_type="pr_approve",
            title=(
                f"[{repo_name}] PR #{pr_id}: "
                f"{display_name} approved"
            ),
            description=(
                f"Pull Request #{pr_id} approved "
                f"by {display_name}"
            ),
            project=f"{project_key}/{repo_name}",
            url=f"{repo_url_base}/pull-requests/{pr_id}",
            activity_timestamp=ts,
            time_spent_minutes=0,
            external_id=ext_id,
            created_at=now,
        )
        db.add(log)
        return 1

    elif act_action == "MERGED":
        ext_id = f"bb_pr_merge_{repo_slug}_{pr_id}_{act_id}"
        exists = (
            db.query(WorkLog)
            .filter(WorkLog.external_id == ext_id)
            .first()
        )
        if exists:
            return 0

        ts = _from_epoch_millis(act_created)
        log = WorkLog(
            source="bitbucket",
            activity_type="pr_merge",
            title=(
                f"[{repo_name}] PR #{pr_id}: "
                f"{display_name} merged"
            ),
            description=(
                f"Pull Request #{pr_id} merged "
                f"by {display_name}"
            ),
            project=f"{project_key}/{repo_name}",
            url=f"{repo_url_base}/pull-requests/{pr_id}",
            activity_timestamp=ts,
            time_spent_minutes=0,
            external_id=ext_id,
            created_at=now,
        )
        db.add(log)
        return 1

    return 0


# ─── Server API calls ──────────────────────────────────────

def _server_get_repos(api_base: str, project: str, auth_cred) -> list:
    """GET /projects/{project}/repos — paginated."""
    repos = []
    url = f"{api_base}/projects/{project}/repos"
    params = {"limit": 100, "start": 0}
    try:
        while url:
            resp = httpx.get(
                url, auth=auth_cred, params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            repos.extend(data.get("values", []))
            if data.get("isLastPage", True):
                break
            params["start"] = data.get("nextPageStart", 0)
    except httpx.HTTPError as e:
        print(f"[Bitbucket Server] Error fetching repos: {e}")
    return repos


def _server_get_commits(
    api_base: str, project: str, repo: str,
    auth_cred, since_epoch: int,
) -> list:
    """GET /projects/{project}/repos/{repo}/commits — with since filter."""
    commits = []
    url = (
        f"{api_base}/projects/{project}/repos/{repo}/commits"
    )
    params = {"limit": 50, "since": since_epoch, "start": 0}
    try:
        while url:
            resp = httpx.get(
                url, auth=auth_cred, params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            commits.extend(data.get("values", []))
            if data.get("isLastPage", True):
                break
            params["start"] = data.get("nextPageStart", 0)
    except httpx.HTTPError as e:
        print(
            f"[Bitbucket Server] Error fetching commits "
            f"for {repo}: {e}"
        )
    return commits


def _server_get_pull_requests(
    api_base: str, project: str, repo: str, auth_cred,
) -> list:
    """GET /projects/{project}/repos/{repo}/pull-requests — all states."""
    prs = []
    url = (
        f"{api_base}/projects/{project}/repos/{repo}"
        "/pull-requests"
    )
    params = {"limit": 50, "state": "ALL", "start": 0}
    try:
        while url:
            resp = httpx.get(
                url, auth=auth_cred, params=params, timeout=30
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            prs.extend(data.get("values", []))
            if data.get("isLastPage", True):
                break
            params["start"] = data.get("nextPageStart", 0)
    except httpx.HTTPError as e:
        print(
            f"[Bitbucket Server] Error fetching PRs "
            f"for {repo}: {e}"
        )
    return prs


def _server_get_pr_activities(
    api_base: str, project: str, repo: str,
    pr_id: int, auth_cred,
) -> list:
    """GET /projects/{project}/repos/{repo}/pull-requests/{prId}/activities."""
    activities = []
    url = (
        f"{api_base}/projects/{project}/repos/{repo}"
        f"/pull-requests/{pr_id}/activities"
    )
    params = {"limit": 100, "start": 0}
    try:
        while url:
            resp = httpx.get(
                url, auth=auth_cred, params=params, timeout=30
            )
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            data = resp.json()
            activities.extend(data.get("values", []))
            if data.get("isLastPage", True):
                break
            params["start"] = data.get("nextPageStart", 0)
    except httpx.HTTPError as e:
        print(
            f"[Bitbucket Server] Error fetching activities "
            f"for PR #{pr_id}: {e}"
        )
    return activities


# ═══════════════════════════════════════════════════════════
#  Bitbucket Cloud (backward compatible)
# ═══════════════════════════════════════════════════════════

def _poll_cloud(workspace: str) -> None:
    """Poll Bitbucket Cloud REST API v2 — backward compatible."""
    if not config.BITBUCKET_USERNAME or not config.BITBUCKET_APP_PASSWORD:
        return

    auth_cred = (config.BITBUCKET_USERNAME, config.BITBUCKET_APP_PASSWORD)
    base_url = "https://api.bitbucket.org/2.0"

    last_run = _get_last_run()
    since_dt = datetime.now(timezone.utc)
    if last_run is None:
        since = (since_dt - timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
    else:
        since = (
            last_run.replace(tzinfo=timezone.utc)
            - timedelta(minutes=2)
        ).strftime("%Y-%m-%dT%H:%M:%S")

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        new_count = 0

        repos = _cloud_get_repos(auth_cred, workspace, base_url)

        for repo in repos:
            repo_name = repo.get("slug", repo.get("name", "unknown"))
            repo_full = f"{workspace}/{repo_name}"

            # ─── Commits ────────────────────────────
            commits = _cloud_get_commits(
                auth_cred, workspace, repo_name, base_url, since
            )
            for commit in commits:
                commit_hash = commit.get("hash", "")
                if not commit_hash:
                    continue

                author_info = commit.get("author", {})
                author_raw = (
                    author_info.get("raw", "")
                    if isinstance(author_info, dict)
                    else str(author_info)
                )

                if (
                    config.BITBUCKET_USERNAME
                    and config.BITBUCKET_USERNAME not in author_raw
                ):
                    continue

                date_str = commit.get("date", "")
                try:
                    ts = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                    ts = ts.replace(tzinfo=None)
                except (ValueError, TypeError):
                    ts = now

                summary = commit.get("summary", {})
                msg = (
                    summary.get("raw", "")
                    if isinstance(summary, dict)
                    else str(summary)
                )

                external_id = f"bb_commit_{commit_hash}"
                exists = (
                    db.query(WorkLog)
                    .filter(WorkLog.external_id == external_id)
                    .first()
                )
                if exists:
                    continue

                log = WorkLog(
                    source="bitbucket",
                    activity_type="commit",
                    title=f"[{repo_name}] {msg[:100]}",
                    description=msg[:500],
                    project=repo_full,
                    url=(
                        f"https://bitbucket.org/{workspace}"
                        f"/{repo_name}/commits/{commit_hash}"
                    ),
                    activity_timestamp=ts,
                    time_spent_minutes=0,
                    external_id=external_id,
                    created_at=now,
                )
                db.add(log)
                new_count += 1

            # ─── Pull Requests ──────────────────────
            prs = _cloud_get_pull_requests(
                auth_cred, workspace, repo_name, base_url, since
            )
            for pr in prs:
                pr_id = pr.get("id", "")
                title = pr.get("title", "")
                state = pr.get("state", "")

                date_str = pr.get("updated_on", "")
                try:
                    ts = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                    ts = ts.replace(tzinfo=None)
                except (ValueError, TypeError):
                    ts = now

                external_id = f"bb_pr_{repo_name}_{pr_id}"
                exists = (
                    db.query(WorkLog)
                    .filter(WorkLog.external_id == external_id)
                    .first()
                )
                if exists:
                    continue

                log = WorkLog(
                    source="bitbucket",
                    activity_type=(
                        "pr_create" if state == "OPEN" else "pr_merge"
                    ),
                    title=(
                        f"[{repo_name}] PR #{pr_id}: {title}"
                    ),
                    description=(
                        f"Pull Request #{pr_id} ({state})"
                        f" — {title}"
                    ),
                    project=repo_full,
                    url=(
                        f"https://bitbucket.org/{workspace}"
                        f"/{repo_name}/pull-requests/{pr_id}"
                    ),
                    activity_timestamp=ts,
                    time_spent_minutes=0,
                    external_id=external_id,
                    created_at=now,
                )
                db.add(log)
                new_count += 1

        if new_count > 0:
            db.commit()

        _save_last_run(datetime.utcnow())

    except Exception as e:
        db.rollback()
        print(f"[Bitbucket Cloud] Error: {e}")
    finally:
        db.close()


def _cloud_get_repos(auth_cred, workspace: str, base_url: str) -> list:
    repos = []
    url = f"{base_url}/repositories/{workspace}"
    params = {"pagelen": 50, "role": "member"}
    try:
        while url:
            resp = httpx.get(
                url, auth=auth_cred, params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            repos.extend(data.get("values", []))
            url = data.get("next", "")
            params = None
    except httpx.HTTPError as e:
        print(f"[Bitbucket Cloud] Error fetching repos: {e}")
    return repos


def _cloud_get_commits(
    auth_cred, workspace: str, repo: str,
    base_url: str, since: str,
) -> list:
    commits = []
    url = f"{base_url}/repositories/{workspace}/{repo}/commits"
    try:
        resp = httpx.get(
            url,
            auth=auth_cred,
            params={"pagelen": 20},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        commits = data.get("values", [])
    except httpx.HTTPError as e:
        print(
            f"[Bitbucket Cloud] Error fetching commits "
            f"for {repo}: {e}"
        )
    return commits


def _cloud_get_pull_requests(
    auth_cred, workspace: str, repo: str,
    base_url: str, since: str,
) -> list:
    prs = []
    url = (
        f"{base_url}/repositories/{workspace}/{repo}"
        "/pullrequests"
    )
    try:
        resp = httpx.get(
            url,
            auth=auth_cred,
            params={"pagelen": 10, "state": "ALL"},
            timeout=30,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        prs = data.get("values", [])
    except httpx.HTTPError as e:
        print(
            f"[Bitbucket Cloud] Error fetching PRs "
            f"for {repo}: {e}"
        )
    return prs

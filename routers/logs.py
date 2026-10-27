"""REST API cho WorkLog CRUD + thống kê."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.exceptions import NotFoundError, ValidationError
from database.db import get_db
from database.models import WorkLog
from services.ai_service import AIService
from services.settings_service import get_setting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/logs", tags=["logs"])


# ─── Schemas ───────────────────────────────────────────


class WorkLogCreate(BaseModel):
    """Schema cho manual entry form."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(None, max_length=10000)
    activity_type: str = Field(default="other", max_length=50)
    project: str | None = Field(None, max_length=100)
    url: str | None = Field(None, max_length=1000)
    activity_timestamp: datetime | None = None
    time_spent_minutes: int = Field(default=0, ge=0, le=60 * 24 * 30)

    model_config = {"str_strip_whitespace": True}


class WorkLogOut(BaseModel):
    """Schema trả về cho client."""

    id: int
    source: str
    activity_type: str
    title: str
    description: str | None = None
    project: str | None = None
    url: str | None = None
    activity_timestamp: datetime
    time_spent_minutes: int
    external_id: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class WorkLogList(BaseModel):
    """Kết quả phân trang."""

    items: list[WorkLogOut]
    total: int
    page: int
    page_size: int


class StatsOut(BaseModel):
    """Thống kê nhanh."""

    total_logs: int
    total_time_hours: float
    jira_logs: int
    bitbucket_logs: int
    github_logs: int
    git_logs: int
    manual_logs: int
    today_time_hours: float
    week_time_hours: float


# ─── Endpoints ─────────────────────────────────────────


@router.get("", response_model=WorkLogList)
def list_logs(
    source: str | None = Query(None, description="Filter by source"),
    activity_type: str | None = Query(None, description="Filter by activity type"),
    project: str | None = Query(None, description="Filter by project"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    search: str | None = Query(None, description="Search in title/description"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort_by: str = Query(
        "activity_timestamp",
        pattern="^(activity_timestamp|created_at|source|title)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """Lấy danh sách work logs với bộ lọc và phân trang."""
    q = db.query(WorkLog)

    if source:
        q = q.filter(WorkLog.source == source)
    if activity_type:
        q = q.filter(WorkLog.activity_type == activity_type)
    if project:
        q = q.filter(WorkLog.project.ilike(f"%{project}%"))
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            q = q.filter(WorkLog.activity_timestamp >= dt_from)
        except ValueError as err:
            raise ValidationError(
                f"Invalid date_from format: {date_from}. Use ISO format."
            ) from err
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            q = q.filter(WorkLog.activity_timestamp <= dt_to)
        except ValueError as err:
            raise ValidationError(f"Invalid date_to format: {date_to}. Use ISO format.") from err
    if search:
        search_term = f"%{search}%"
        q = q.filter(
            WorkLog.title.ilike(search_term)
            | WorkLog.description.ilike(search_term)
            | WorkLog.project.ilike(search_term)
        )

    total = q.count()

    sort_col = getattr(WorkLog, sort_by, WorkLog.activity_timestamp)
    if sort_order == "desc":
        sort_col = sort_col.desc()
    q = q.order_by(sort_col)

    offset = (page - 1) * page_size
    items = q.offset(offset).limit(page_size).all()

    return WorkLogList(
        items=[WorkLogOut.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=WorkLogOut, status_code=201)
async def create_log(entry: WorkLogCreate, db: Session = Depends(get_db)):
    """Tạo manual work log entry. Tự động AI enhance nếu harness đang bật."""
    log = WorkLog(
        source="manual",
        activity_type=entry.activity_type,
        title=entry.title,
        description=entry.description,
        project=entry.project,
        url=entry.url,
        activity_timestamp=entry.activity_timestamp or datetime.now(UTC).replace(tzinfo=None),
        time_spent_minutes=entry.time_spent_minutes,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(log)
    db.commit()
    db.refresh(log)

    # Auto-enhance nếu AI harness đang enabled
    try:
        enabled = get_setting(db, "ai_enabled")
        api_key = get_setting(db, "ai_api_key")
        if enabled == "true" and api_key:
            svc = AIService(
                provider=get_setting(db, "ai_provider") or "openai",
                api_key=api_key,
                base_url=get_setting(db, "ai_base_url"),
                model=get_setting(db, "ai_model"),
            )
            result = await svc.enhance_log(
                title=log.title,
                description=log.description or "",
                activity_type=log.activity_type,
            )
            conf = result.get("confidence", 0)
            if conf > 0.5:
                if result.get("enhanced_description"):
                    log.description = result["enhanced_description"]
                est = result.get("estimated_minutes", 0)
                if est > 0 and log.time_spent_minutes == 0:
                    log.time_spent_minutes = est
                db.commit()
                db.refresh(log)
    except Exception:
        # Silent — không block user nếu AI lỗi
        logger.exception("AI auto-enhance failed for log %s", log.id)

    return WorkLogOut.model_validate(log)


@router.delete("/{log_id}", status_code=204)
def delete_log(log_id: int, db: Session = Depends(get_db)):
    """Xoá một work log entry."""
    log = db.query(WorkLog).filter(WorkLog.id == log_id).first()
    if not log:
        raise NotFoundError("Work log not found")
    db.delete(log)
    db.commit()


@router.patch("/{log_id}", response_model=WorkLogOut)
def update_log(
    log_id: int,
    updates: WorkLogCreate,
    db: Session = Depends(get_db),
):
    """Cập nhật một work log (vd: sửa time spent)."""
    log = db.query(WorkLog).filter(WorkLog.id == log_id).first()
    if not log:
        raise NotFoundError("Work log not found")

    log.title = updates.title
    log.description = updates.description
    log.activity_type = updates.activity_type
    log.project = updates.project
    log.url = updates.url
    log.activity_timestamp = updates.activity_timestamp or datetime.now(UTC).replace(tzinfo=None)
    log.time_spent_minutes = updates.time_spent_minutes

    db.commit()
    db.refresh(log)
    return WorkLogOut.model_validate(log)


@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    """Thống kê nhanh cho dashboard."""
    now = datetime.now(UTC).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Lùi về thứ 2 (Monday)
    week_start = week_start.replace(day=week_start.day - week_start.weekday())

    total = db.query(func.count(WorkLog.id)).scalar() or 0
    total_time = db.query(func.coalesce(func.sum(WorkLog.time_spent_minutes), 0)).scalar() or 0

    def count_by_source(source: str) -> int:
        return db.query(func.count(WorkLog.id)).filter(WorkLog.source == source).scalar() or 0

    def time_since(start: datetime) -> float:
        result = (
            db.query(func.coalesce(func.sum(WorkLog.time_spent_minutes), 0))
            .filter(WorkLog.activity_timestamp >= start)
            .scalar()
            or 0
        )
        return round(result / 60, 1)

    return StatsOut(
        total_logs=total,
        total_time_hours=round(total_time / 60, 1),
        jira_logs=count_by_source("jira"),
        bitbucket_logs=count_by_source("bitbucket"),
        github_logs=count_by_source("github"),
        git_logs=count_by_source("git"),
        manual_logs=count_by_source("manual"),
        today_time_hours=time_since(today_start),
        week_time_hours=time_since(week_start),
    )

"""Application CRM 服务（Phase 5）。

原则：CRM 只消费 Phase 2-4 的评估结果，不修改核心事实/评分模型。
状态流转受 APPLICATION_STATUS_TRANSITIONS 约束——正向推进、终止态封死、
非法跳转显式 409（含允许的目标状态提示），不静默改写。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Job
from app.models.enums import APPLICATION_STATUS_TRANSITIONS, can_transition_application
from app.schemas.application import (
    ApplicationCreate,
    ApplicationJobBrief,
    ApplicationOut,
    ApplicationUpdate,
)


class ApplicationTransitionError(ValueError):
    """非法状态流转。"""


class ApplicationExistsError(ValueError):
    """该岗位已存在申请记录。"""


def _now() -> datetime:
    return datetime.now(UTC)


def get_application_or_404(db: Session, application_id: int) -> Application:
    app = db.get(Application, application_id)
    if app is None:
        raise LookupError(f"申请不存在: {application_id}")
    return app


def get_application_by_job(db: Session, job_id: int) -> Application | None:
    return db.scalars(select(Application).where(Application.job_id == job_id)).first()


def job_brief(db: Session, job_id: int) -> ApplicationJobBrief | None:
    job = db.get(Job, job_id)
    if job is None:
        return None
    evaluation = job.latest_evaluation
    return ApplicationJobBrief(
        id=job.id,
        title=job.title,
        organization_name=job.organization.name if job.organization else None,
        department=job.department,
        city=job.city,
        deadline=job.deadline,
        total_score=evaluation.total_score if evaluation else None,
        recommendation_level=evaluation.recommendation_level if evaluation else None,
    )


def to_out(db: Session, app: Application) -> ApplicationOut:
    return ApplicationOut.from_model(app, job_brief(db, app.job_id))


def create_application(db: Session, job_id: int, payload: ApplicationCreate) -> Application:
    if db.get(Job, job_id) is None:
        raise LookupError(f"岗位不存在: {job_id}")
    if get_application_by_job(db, job_id) is not None:
        raise ApplicationExistsError(f"岗位 {job_id} 已存在申请记录")
    app = Application(
        job_id=job_id,
        status=payload.status,
        priority=payload.priority,
        # 只有明确以 applied 状态建档才记录投递时间；直接建为
        # interview/offer 等历史态时 applied_at 保持 null —— 未知比猜"现在"更正确
        applied_at=_now() if payload.status == "applied" else None,
        resume_version=payload.resume_version,
        cover_letter_version=payload.cover_letter_version,
        contact=payload.contact,
        notes=payload.notes,
        next_action=payload.next_action,
        next_action_date=payload.next_action_date,
    )
    db.add(app)
    db.flush()
    return app


def update_application(db: Session, app: Application, payload: ApplicationUpdate) -> Application:
    data = payload.model_dump(exclude_unset=True)
    new_status = data.get("status")
    if new_status is not None and new_status != app.status:
        if not can_transition_application(app.status, new_status):
            raise ApplicationTransitionError(
                f"申请状态不允许从 '{app.status}' 流转到 '{new_status}'；"
                f"允许的目标状态: {sorted(APPLICATION_STATUS_TRANSITIONS.get(app.status, set()))}"
            )
        # 投递时间只在真正进入 applied 时记录（Phase 5.1 P0：contacting 是洽联，
        # 不是投递——否则 9 月 1 日联系 PI 会被永久写成 9 月 1 日投递）
        if new_status == "applied" and app.applied_at is None:
            app.applied_at = _now()
    for field, value in data.items():
        setattr(app, field, value)
    db.flush()
    return app


def delete_application(db: Session, app: Application) -> None:
    db.delete(app)
    db.flush()


def list_applications(
    db: Session,
    *,
    status: str | None = None,
    q: str | None = None,
    sort: str = "updated_at",
) -> list[Application]:
    stmt = select(Application).join(Job, Application.job_id == Job.id)
    if status:
        stmt = stmt.where(Application.status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Application.next_action.ilike(like)
            | Application.notes.ilike(like)
            | Application.contact.ilike(like)
            | Job.title.ilike(like)
            | Job.department.ilike(like)
        )
    if sort == "next_action_date":
        stmt = stmt.order_by(Application.next_action_date.is_(None), Application.next_action_date)
    elif sort == "priority":
        stmt = stmt.order_by(Application.priority.is_(None), Application.priority.desc())
    else:
        stmt = stmt.order_by(Application.updated_at.desc())
    return list(db.scalars(stmt))

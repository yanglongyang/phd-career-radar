"""Dashboard 汇总：今日新增 / 待查看 / 高匹配 / 重点关注 / 各流程状态计数 + Top Jobs。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_scoring_config
from app.models import Job, JobEvaluation
from app.schemas.dashboard import DashboardCounts, DashboardOut
from app.schemas.evaluation import JobEvaluationOut
from app.schemas.job import JobListItem
from app.schemas.organization import OrganizationBrief
from app.services.jobs import latest_evaluations_subquery, top_jobs


def build_dashboard(db: Session) -> DashboardOut:
    now = datetime.now(UTC)
    today = now.date()

    def count(where=None) -> int:
        stmt = select(func.count()).select_from(Job)
        if where is not None:
            stmt = stmt.where(where)
        return db.execute(stmt).scalar_one()

    counts = DashboardCounts(
        new_today=count(func.date(Job.first_seen_at) == today.isoformat()),
        to_review=count(Job.status.in_(["new", "reviewing"])),
        focus=count(Job.status == "shortlisted"),
        preparing=count(Job.status == "preparing"),
        applied=count(Job.status == "applied"),
        interviewing=count(Job.status == "interviewing"),
        offer=count(Job.status == "offer"),
    )

    # 高匹配：最新评估的推荐等级属于配置的高匹配集合（默认 S/A）
    high_levels = tuple(get_scoring_config().get("high_match_levels") or ["S", "A"])
    sub = latest_evaluations_subquery()
    ev = aliased(JobEvaluation)
    counts.high_match = db.execute(
        select(func.count())
        .select_from(Job)
        .outerjoin(sub, sub.c.job_id == Job.id)
        .outerjoin(ev, ev.id == sub.c.eval_id)
        .where(ev.recommendation_level.in_(high_levels))
    ).scalar_one()

    def to_item(job: Job, evaluation: JobEvaluation | None) -> JobListItem:
        return JobListItem(
            id=job.id,
            title=job.title,
            department=job.department,
            job_category=job.job_category,
            province=job.province,
            city=job.city,
            status=job.status,
            position_nature=job.position_nature,
            salary_text=job.salary_text,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            deadline=job.deadline,
            first_seen_at=job.first_seen_at,
            source=job.source,
            user_rating=job.user_rating,
            organization=(
                OrganizationBrief(
                    id=job.organization.id,
                    name=job.organization.name,
                    organization_type=job.organization.organization_type,
                    province=job.organization.province,
                    city=job.organization.city,
                )
                if job.organization
                else None
            ),
            evaluation=JobEvaluationOut.from_model(evaluation) if evaluation else None,
        )

    return DashboardOut(
        counts=counts,
        top_jobs=[to_item(job, evaluation) for job, evaluation in top_jobs(db, limit=5)],
    )

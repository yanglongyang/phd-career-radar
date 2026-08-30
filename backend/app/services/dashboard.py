"""Dashboard 汇总（Phase 2.1 修正数据来源）。

- new_today / to_review / focus：来自 Job 的信息筛选状态（JobDisposition）。
- preparing / applied / interviewing / offer：来自 Application 的求职流程状态，
  Job 不再承担求职流程语义。面试中 = 笔试 + 两轮面试阶段。
- top_jobs：排除 ignored/closed 与推荐等级 X 的岗位。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.core.config import get_scoring_config
from app.models import Application, Job, JobEvaluation
from app.schemas.dashboard import DashboardCounts, DashboardOut
from app.schemas.evaluation import JobEvaluationOut
from app.schemas.job import JobListItem
from app.schemas.organization import OrganizationBrief
from app.services.jobs import latest_evaluations_subquery, top_jobs

# Application 状态 → Dashboard"面试中"统计口径（含 HR 沟通阶段，Phase 2.1.1）
INTERVIEWING_STATUSES = ("written_test", "interview_1", "interview_2", "hr")


def build_dashboard(db: Session) -> DashboardOut:
    now = datetime.now(UTC)
    today = now.date()

    def job_count(where=None) -> int:
        stmt = select(func.count()).select_from(Job)
        if where is not None:
            stmt = stmt.where(where)
        return db.execute(stmt).scalar_one()

    def application_count(where) -> int:
        return db.execute(
            select(func.count()).select_from(Application).where(where)
        ).scalar_one()

    counts = DashboardCounts(
        new_today=job_count(func.date(Job.first_seen_at) == today.isoformat()),
        to_review=job_count(Job.status.in_(["new", "reviewing"])),
        focus=job_count(Job.status == "shortlisted"),
        preparing=application_count(Application.status == "preparing"),
        applied=application_count(Application.status == "applied"),
        interviewing=application_count(Application.status.in_(INTERVIEWING_STATUSES)),
        offer=application_count(Application.status == "offer"),
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
            salary_currency=job.salary_currency,
            salary_period=job.salary_period,
            guaranteed_salary_min=job.guaranteed_salary_min,
            guaranteed_salary_max=job.guaranteed_salary_max,
            variable_salary_min=job.variable_salary_min,
            variable_salary_max=job.variable_salary_max,
            advertised_total_min=job.advertised_total_min,
            advertised_total_max=job.advertised_total_max,
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

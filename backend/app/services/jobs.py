"""岗位服务：创建（含去重）、更新（含版本捕获）、删除（保留组织级证据）、列表查询。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, aliased

from app.core.fingerprint import (
    content_hash,
    description_similarity,
    job_fingerprint,
    normalize_org_name,
)
from app.models import AcademicJobDetails, Evidence, Job, JobEvaluation, JobVersion, Organization
from app.schemas.academic import AcademicJobDetailsUpdate
from app.schemas.job import JobCreate, JobUpdate

# 这些字段变化时保存 JobVersion（历史快照），不覆盖旧数据
VERSIONED_FIELDS = ("description_raw", "salary_text", "salary_min", "salary_max", "deadline")

# 触发指纹重算的字段
FINGERPRINT_FIELDS = ("title", "department", "city")

DUPLICATE_DESCRIPTION_SIMILARITY = 0.92


def _now() -> datetime:
    return datetime.now(UTC)


# 四轴字段：显式 null 一律归一为 "unknown"（数据库 NOT NULL，不存在第二套未知）
AXIS_FIELDS = ("establishment_status", "tenure_status", "contract_type", "funding_source")


def apply_academic_details(details: AcademicJobDetails, payload: AcademicJobDetailsUpdate) -> None:
    """把 Update payload 应用到 AcademicJobDetails（部分更新语义 + 四轴 null 归一）。"""
    data = payload.model_dump(exclude_unset=True)
    for axis in AXIS_FIELDS:
        if axis in payload.model_fields_set and data[axis] is None:
            data[axis] = "unknown"
    for field, value in data.items():
        setattr(details, field, value)


def get_or_create_organization(
    db: Session, name: str, defaults: dict | None = None
) -> Organization:
    norm = normalize_org_name(name)
    for org in db.scalars(select(Organization)):
        if normalize_org_name(org.name) == norm:
            return org
    values = dict(defaults or {})
    org = Organization(name=name, **{k: v for k, v in values.items() if v is not None})
    db.add(org)
    db.flush()
    return org


def resolve_organization(db: Session, payload) -> Organization | None:
    if getattr(payload, "organization_id", None):
        return db.get(Organization, payload.organization_id)
    name = getattr(payload, "organization_name", None)
    if name:
        return get_or_create_organization(
            db, name, defaults={"province": payload.province, "city": payload.city}
        )
    return None


def compute_fingerprint(org: Organization | None, department: str | None, title: str, city: str | None) -> str:
    return job_fingerprint(org.name if org else "", department, title, city)


def find_duplicate(
    db: Session,
    *,
    fingerprint: str,
    organization_id: int | None,
    description: str | None,
    exclude_job_id: int | None = None,
) -> Job | None:
    """去重：指纹完全一致，或同单位且公告文本高度相似。URL 不作为唯一判据。"""
    q = select(Job).where(Job.fingerprint == fingerprint)
    if exclude_job_id:
        q = q.where(Job.id != exclude_job_id)
    hit = db.scalars(q).first()
    if hit:
        return hit
    if organization_id and description:
        q2 = select(Job).where(Job.organization_id == organization_id)
        if exclude_job_id:
            q2 = q2.where(Job.id != exclude_job_id)
        for other in db.scalars(q2):
            if description_similarity(description, other.description_raw or "") >= DUPLICATE_DESCRIPTION_SIMILARITY:
                return other
    return None


def create_job(db: Session, payload: JobCreate) -> tuple[Job, Job | None]:
    org = resolve_organization(db, payload)
    fp = compute_fingerprint(org, payload.department, payload.title, payload.city)
    duplicate = find_duplicate(
        db,
        fingerprint=fp,
        organization_id=org.id if org else None,
        description=payload.description_raw,
    )
    job = Job(
        source=payload.source,
        source_job_id=payload.source_job_id,
        source_url=payload.source_url,
        fingerprint=fp,
        title=payload.title,
        organization_id=org.id if org else None,
        department=payload.department,
        job_category=payload.job_category,
        country=payload.country,
        province=payload.province,
        city=payload.city,
        description_raw=payload.description_raw,
        description_clean=payload.description_clean,
        posted_at=payload.posted_at,
        deadline=payload.deadline,
        employment_type=payload.employment_type,
        salary_text=payload.salary_text,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        salary_currency=payload.salary_currency,
        salary_period=payload.salary_period,
        guaranteed_salary_min=payload.guaranteed_salary_min,
        guaranteed_salary_max=payload.guaranteed_salary_max,
        variable_salary_min=payload.variable_salary_min,
        variable_salary_max=payload.variable_salary_max,
        advertised_total_min=payload.advertised_total_min,
        advertised_total_max=payload.advertised_total_max,
        degree_requirement=payload.degree_requirement,
        experience_requirement=payload.experience_requirement,
        status=payload.status,
        first_seen_at=_now(),
        last_seen_at=_now(),
    )
    if payload.academic_details is not None:
        details = AcademicJobDetails(job_id=job.id)
        apply_academic_details(details, payload.academic_details)
        job.academic_details = details
        db.add(details)
    db.add(job)
    db.flush()
    return job, duplicate


def get_job_or_404(db: Session, job_id: int) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise LookupError(f"岗位不存在: {job_id}")
    return job


def delete_job(db: Session, job: Job) -> None:
    """删除岗位但不破坏组织风评库：Evidence 的 job_id 置空后保留历史，
    其余关联（评估/申请/版本/高校详情）随岗位级联删除。"""
    db.execute(update(Evidence).where(Evidence.job_id == job.id).values(job_id=None))
    db.delete(job)
    db.flush()


def update_job(db: Session, job: Job, payload: JobUpdate) -> Job:
    data = payload.model_dump(exclude_unset=True)

    # 组织归属单独处理（organization_name 写入便利字段）
    org_changed = False
    if "organization_name" in data:
        new_name = data.pop("organization_name")
        current_name = job.organization.name if job.organization else ""
        if new_name and normalize_org_name(current_name) != normalize_org_name(new_name):
            org = get_or_create_organization(db, new_name)
            job.organization_id = org.id
            org_changed = True
    data.pop("organization_id", None)  # 直接改 id 的场景 V0.1 不开放，避免悬挂引用

    changes: list[dict] = []
    # 在应用变更前先取旧值快照，JobVersion 保存的是变更前的内容
    old_snapshot = {f: getattr(job, f) for f in VERSIONED_FIELDS}
    for field, new_value in data.items():
        old_value = getattr(job, field)
        if old_value == new_value:
            continue
        if field in VERSIONED_FIELDS:
            changes.append({"field": field, "old": _serialize(old_value), "new": _serialize(new_value)})
        setattr(job, field, new_value)

    if changes:
        db.add(
            JobVersion(
                job_id=job.id,
                content_hash=content_hash(
                    old_snapshot["description_raw"], old_snapshot["salary_text"], old_snapshot["deadline"]
                ),
                description=old_snapshot["description_raw"],
                salary_text=old_snapshot["salary_text"],
                deadline=old_snapshot["deadline"],
                changes_json=changes,
                captured_at=_now(),
            )
        )

    if org_changed or any(f in data for f in FINGERPRINT_FIELDS):
        job.fingerprint = compute_fingerprint(
            job.organization, job.department, job.title, job.city
        )

    job.updated_at = _now()
    db.flush()
    return job


def _serialize(value) -> str | None:
    if value is None:
        return None
    return str(value)


def latest_evaluations_subquery():
    return (
        select(JobEvaluation.job_id, func.max(JobEvaluation.id).label("eval_id"))
        .group_by(JobEvaluation.job_id)
        .subquery()
    )


SORT_COLUMNS = {
    "total_score": lambda e: e.total_score,
    "region": lambda e: e.region_score,
    "reputation": lambda e: e.reputation_score,
}


def list_jobs(
    db: Session,
    *,
    q: str | None = None,
    job_category: str | None = None,
    status: str | None = None,
    province: str | None = None,
    city: str | None = None,
    organization_id: int | None = None,
    recommendation: str | None = None,
    risk_level: str | None = None,
    confidence: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    sort: str = "first_seen_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Job, JobEvaluation | None]], int]:
    le = latest_evaluations_subquery()
    ev = aliased(JobEvaluation)
    stmt = (
        select(Job, ev)
        .outerjoin(le, le.c.job_id == Job.id)
        .outerjoin(ev, ev.id == le.c.eval_id)
    )

    if q:
        like = f"%{q}%"
        stmt = stmt.where(Job.title.ilike(like) | Job.department.ilike(like))
    if job_category:
        stmt = stmt.where(Job.job_category == job_category)
    if status:
        stmt = stmt.where(Job.status == status)
    if province:
        stmt = stmt.where(Job.province == province)
    if city:
        stmt = stmt.where(Job.city == city)
    if organization_id:
        stmt = stmt.where(Job.organization_id == organization_id)
    if recommendation:
        stmt = stmt.where(ev.recommendation_level == recommendation)
    if risk_level:
        stmt = stmt.where(ev.risk_level == risk_level)
    if confidence:
        stmt = stmt.where(ev.confidence_level == confidence)
    if min_score is not None:
        stmt = stmt.where(ev.total_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(ev.total_score <= max_score)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    if sort in SORT_COLUMNS:
        col = SORT_COLUMNS[sort](ev)
    elif sort == "deadline":
        col = Job.deadline
    elif sort == "created_at":
        col = Job.created_at
    else:
        col = Job.first_seen_at

    stmt = stmt.order_by(col.is_(None), col.desc() if order == "desc" else col.asc(), Job.id.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    rows: list[tuple[Job, JobEvaluation | None]] = [
        (job, evaluation) for job, evaluation in db.execute(stmt)
    ]
    return rows, total


def top_jobs(db: Session, limit: int = 5) -> list[tuple[Job, JobEvaluation | None]]:
    """Top Jobs：排除已忽略/已关闭与触发硬性排除(X)的岗位，按综合分排序。"""
    le = latest_evaluations_subquery()
    ev = aliased(JobEvaluation)
    stmt = (
        select(Job, ev)
        .outerjoin(le, le.c.job_id == Job.id)
        .outerjoin(ev, ev.id == le.c.eval_id)
        .where(ev.total_score.isnot(None))
        .where(Job.status.notin_(["ignored", "closed"]))
        .where(or_(ev.recommendation_level.is_(None), ev.recommendation_level != "X"))
        .order_by(ev.total_score.desc(), Job.id.desc())
        .limit(limit)
    )
    return [(job, evaluation) for job, evaluation in db.execute(stmt)]


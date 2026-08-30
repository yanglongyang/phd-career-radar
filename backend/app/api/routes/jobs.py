from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.db.session import get_db
from app.models import JobEvaluation
from app.schemas.evaluation import JobEvaluationOut
from app.schemas.job import (
    JobCreate,
    JobDetailOut,
    JobListItem,
    JobListPage,
    JobSort,
    JobUpdate,
    JobVersionOut,
)
from app.schemas.organization import OrganizationBrief
from app.services import jobs as job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_list_item(job, evaluation) -> JobListItem:
    org = job.organization
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
                id=org.id,
                name=org.name,
                organization_type=org.organization_type,
                province=org.province,
                city=org.city,
            )
            if org
            else None
        ),
        evaluation=JobEvaluationOut.from_model(evaluation) if evaluation else None,
    )


def _to_detail(job) -> JobDetailOut:
    latest = job.latest_evaluation
    data = _to_list_item(job, latest).model_dump()
    data.update(
        country=job.country,
        description_raw=job.description_raw,
        description_clean=job.description_clean,
        posted_at=job.posted_at,
        employment_type=job.employment_type,
        degree_requirement=job.degree_requirement,
        experience_requirement=job.experience_requirement,
        source_url=job.source_url,
        user_priority=job.user_priority,
        user_notes=job.user_notes,
        fingerprint=job.fingerprint,
        created_at=job.created_at,
        updated_at=job.updated_at,
        versions=[
            JobVersionOut(
                id=v.id,
                content_hash=v.content_hash,
                description=v.description,
                salary_text=v.salary_text,
                deadline=v.deadline,
                changes=list(v.changes_json or []),
                captured_at=v.captured_at,
            )
            for v in sorted(job.versions, key=lambda x: x.captured_at, reverse=True)
        ],
        has_version_changes=any((v.changes_json or []) for v in job.versions),
    )
    return JobDetailOut(**data)


@router.get("", response_model=JobListPage)
def list_jobs(
    q: str | None = Query(None, description="搜索岗位名/院系"),
    job_category: str | None = None,
    status: str | None = None,
    province: str | None = None,
    city: str | None = None,
    organization_id: int | None = None,
    recommendation: str | None = Query(None, description="S/A/B/C/D/X"),
    risk_level: str | None = Query(None, description="low/medium/high/critical"),
    confidence: str | None = Query(None, description="low/medium/high"),
    min_score: float | None = None,
    max_score: float | None = None,
    sort: JobSort = JobSort.first_seen_at,
    order: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows, total = job_service.list_jobs(
        db,
        q=q,
        job_category=job_category,
        status=status,
        province=province,
        city=city,
        organization_id=organization_id,
        recommendation=recommendation,
        risk_level=risk_level,
        confidence=confidence,
        min_score=min_score,
        max_score=max_score,
        sort=sort.value,
        order=order,
        page=page,
        page_size=page_size,
    )
    return JobListPage(
        items=[_to_list_item(job, evaluation) for job, evaluation in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=JobDetailOut, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    job, duplicate = job_service.create_job(db, payload)
    if duplicate is not None and not payload.allow_duplicate:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "message": "发现疑似重复岗位（指纹一致或同单位且公告高度相似）",
                "duplicate_of": {
                    "id": duplicate.id,
                    "title": duplicate.title,
                    "organization": duplicate.organization.name if duplicate.organization else None,
                },
            },
        )
    db.commit()
    db.refresh(job)
    return _to_detail(job)


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _to_detail(job)


@router.patch("/{job_id}", response_model=JobDetailOut)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)):
    try:
        job = job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    job = job_service.update_job(db, job, payload)
    db.commit()
    db.refresh(job)
    return _to_detail(job)


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    try:
        job = job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    db.delete(job)
    db.commit()


@router.get("/{job_id}/evaluations", response_model=list[JobEvaluationOut])
def list_evaluations(job_id: int, db: Session = Depends(get_db)):
    try:
        job = job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    rows = db.scalars(
        select(JobEvaluation).where(JobEvaluation.job_id == job.id)
    ).all()
    return [JobEvaluationOut.from_model(e) for e in sorted(rows, key=lambda x: x.id, reverse=True)]


@router.post("/{job_id}/evaluate")
def evaluate_job(job_id: int, db: Session = Depends(get_db)):
    """Phase 4 接入。此处先给出明确的不可用状态，避免静默伪造评估。"""
    try:
        job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if get_provider() is None:
        raise HTTPException(
            status_code=503,
            detail="AI 未配置：请在 .env 中设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL",
        )
    raise HTTPException(status_code=503, detail="AI 评估将在 Phase 4 提供（Provider 已就绪）")

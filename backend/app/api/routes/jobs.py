from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.provider import AIError
from app.api.deps import get_ai_provider
from app.db.session import get_db
from app.models import JobEvaluation
from app.models.academic_job_details import AcademicJobDetails
from app.schemas.academic import AcademicJobDetailsOut, AcademicJobDetailsUpdate
from app.schemas.evaluation import JobEvaluationOut
from app.schemas.extraction import MAX_TEXT_CHARS, ExtractionPreviewOut, ExtractionRequest
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
from app.services import evaluation as evaluation_service
from app.services import jobs as job_service
from app.services.web import PageFetchError, fetch_url_text

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
        academic_details=(
            AcademicJobDetailsOut.model_validate(job.academic_details)
            if job.academic_details
            else None
        ),
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
    job_service.delete_job(db, job)  # Evidence 保留，job_id 置空
    db.commit()


@router.get("/{job_id}/academic-details", response_model=AcademicJobDetailsOut | None)
def get_academic_details(job_id: int, db: Session = Depends(get_db)):
    """高校岗位专用字段。企业岗位返回 null。"""
    try:
        job = job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if job.academic_details is None:
        return None
    return AcademicJobDetailsOut.model_validate(job.academic_details)


@router.patch("/{job_id}/academic-details", response_model=AcademicJobDetailsOut)
def update_academic_details(
    job_id: int, payload: AcademicJobDetailsUpdate, db: Session = Depends(get_db)
):
    """Upsert：不存在则创建。部分更新。

    Phase 2.1.1：四轴（establishment/tenure/contract/funding）显式传 null
    归一化为 "unknown" —— 数据库列 NOT NULL，不存在第二套 null 未知。
    """
    try:
        job = job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    details = job.academic_details
    if details is None:
        details = AcademicJobDetails(job_id=job.id)
        job.academic_details = details
        db.add(details)
    job_service.apply_academic_details(details, payload)
    db.commit()
    db.refresh(details)
    return AcademicJobDetailsOut.model_validate(details)


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


@router.post("/extract-preview", response_model=ExtractionPreviewOut)
def extract_preview(
    payload: ExtractionRequest, provider=Depends(get_ai_provider)
):
    """粘贴公告文本或 URL → AI 结构化解析 → 返回预览（不写数据库）。

    用户在预览中逐项确认/修正后，通过 POST /api/jobs（含嵌套 academic_details）
    原子保存。解析失败或 AI 未配置时给出明确错误，不伪造结果。"""
    # 请求校验（422）→ AI 配置检查（503）→ AI 调用错误（502），失败快速且语义明确
    source_type = "url" if payload.text is None else "text"
    text = payload.text
    if text is None:
        try:
            text = fetch_url_text(payload.url)  # type: ignore[arg-type]
        except PageFetchError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    if len(text.strip()) < 50:
        raise HTTPException(status_code=422, detail="公告正文过短（少于 50 字符），请检查内容")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"正文过长（{len(text)} 字符，上限 {MAX_TEXT_CHARS}），请缩小到具体招聘公告",
        )
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="AI 未配置：请在 .env 中设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 后重试",
        )
    try:
        extraction, prompt_version = provider.extract_job(text.strip())
    except AIError as e:
        raise HTTPException(status_code=502, detail=f"AI 解析失败：{e}") from e
    return ExtractionPreviewOut(
        # provenance 随预览返回：前端保存时以此为准，避免来源串单
        source_type=source_type,
        source_url=payload.url if source_type == "url" else None,
        source_text=text.strip(),
        extraction=extraction,
        provider=provider.name,
        model=getattr(provider, "model", None),
        prompt_version=prompt_version,
    )


@router.post("/{job_id}/evaluate", response_model=JobEvaluationOut)
def evaluate_job(
    job_id: int,
    db: Session = Depends(get_db),
    provider=Depends(get_ai_provider),
):
    """AI 评估（Phase 4）：后端构造 context → 调 AI → 规则引擎 finalize → 入库。

    同一份 context 既发给模型也存为 input_snapshot（可复现）；评估数据不一致时
    拒绝保存（409），AI 未配置 503，AI 调用/输出失败 502 —— 不伪造结果。"""
    try:
        job = job_service.get_job_or_404(db, job_id)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="AI 未配置：请在 .env 中设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 后重试",
        )
    try:
        evaluation = evaluation_service.evaluate_job(db, job, provider)
    except AIError as e:
        raise HTTPException(status_code=502, detail=f"AI 评估失败：{e}") from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    db.commit()
    db.refresh(evaluation)
    return JobEvaluationOut.from_model(evaluation)

"""Collector API（V0.2）：立即检查 / 运行历史 / Inbox 审核 / AI Extraction bridge。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_ai_provider
from app.collectors.config import load_enabled_sources, load_sources
from app.db.session import get_db
from app.models import CollectorRun, DiscoveredJob
from app.schemas.collector import (
    CollectorRunOut,
    DiscoveredJobListPage,
    DiscoveredJobOut,
    DiscoveredJobUpdate,
)
from app.services import collector_runner

router = APIRouter(tags=["collectors"])


def _run_to_out(run: CollectorRun) -> CollectorRunOut:
    return CollectorRunOut(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        trigger=run.trigger,
        source_count=run.source_count,
        completed_source_count=run.completed_source_count,
        discovered_count=run.discovered_count,
        new_count=run.new_count,
        duplicate_count=run.duplicate_count,
        possible_duplicate_count=run.possible_duplicate_count,
        filtered_count=run.filtered_count,
        failed_source_count=run.failed_source_count,
        items=[
            {
                "id": i.id,
                "source_id": i.source_id,
                "source_name": i.source_name,
                "status": i.status,
                "started_at": i.started_at,
                "finished_at": i.finished_at,
                "fetched_count": i.fetched_count,
                "new_count": i.new_count,
                "duplicate_count": i.duplicate_count,
                "possible_duplicate_count": i.possible_duplicate_count,
                "filtered_count": i.filtered_count,
                "error_message": i.error_message,
            }
            for i in run.items
        ],
    )


def _discovered_to_out(d: DiscoveredJob) -> DiscoveredJobOut:
    return DiscoveredJobOut(
        id=d.id,
        source_id=d.source_id,
        source_name=d.source_name,
        source_job_id=d.source_job_id,
        source_url=d.source_url,
        canonical_url=d.canonical_url,
        title_raw=d.title_raw,
        description_raw=d.description_raw,
        published_at_raw=d.published_at_raw,
        organization_hint=d.organization_hint,
        location_hint=d.location_hint,
        status=d.status,
        discovered_at=d.discovered_at,
        last_seen_at=d.last_seen_at,
        first_run_id=d.first_run_id,
        last_run_id=d.last_run_id,
        possible_duplicate_of_id=d.possible_duplicate_of_id,
        duplicate_reason=d.duplicate_reason,
        imported_job_id=d.imported_job_id,
        raw_payload=d.raw_payload_json,
    )


@router.post("/collectors/run", response_model=CollectorRunOut)
def run_collectors(db: Session = Depends(get_db)):
    """立即执行一次 enabled sources（同步执行，返回完整 summary 含 source 级状态）。"""
    try:
        sources = load_enabled_sources()
    except Exception as e:  # noqa: BLE001 —— 配置错误明确报错
        raise HTTPException(status_code=422, detail=f"sources.yaml 配置错误：{e}") from e
    run = collector_runner.run_collectors(db, sources)
    db.commit()
    db.refresh(run)
    return _run_to_out(run)


@router.get("/collectors/runs", response_model=list[CollectorRunOut])
def list_runs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = db.scalars(
        select(CollectorRun)
        .options(selectinload(CollectorRun.items))
        .order_by(CollectorRun.id.desc())
        .limit(limit)
    ).all()
    return [_run_to_out(r) for r in rows]


@router.get("/collectors/runs/{run_id}", response_model=CollectorRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(CollectorRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"运行不存在: {run_id}")
    return _run_to_out(run)


@router.get("/collectors/sources")
def list_source_configs():
    """展示 sources.yaml 当前配置（含 enabled 状态）。"""
    try:
        sources = load_sources()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"sources.yaml 配置错误：{e}") from e
    return [
        {
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "enabled": s.enabled,
            "category": s.category,
            "organization": s.organization,
            "url": s.url,
        }
        for s in sources
    ]


@router.get("/discovered-jobs", response_model=DiscoveredJobListPage)
def list_discovered(
    status: str | None = Query(None),
    source_id: str | None = Query(None),
    organization: str | None = Query(None),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(DiscoveredJob)
    if status:
        stmt = stmt.where(DiscoveredJob.status == status)
    if source_id:
        stmt = stmt.where(DiscoveredJob.source_id == source_id)
    if organization:
        stmt = stmt.where(DiscoveredJob.organization_hint.ilike(f"%{organization}%"))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(DiscoveredJob.title_raw.ilike(like) | DiscoveredJob.organization_hint.ilike(like))
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.scalars(
        stmt.order_by(DiscoveredJob.last_seen_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return DiscoveredJobListPage(
        items=[_discovered_to_out(d) for d in rows], total=total
    )


@router.get("/discovered-jobs/{job_id}", response_model=DiscoveredJobOut)
def get_discovered(job_id: int, db: Session = Depends(get_db)):
    row = db.get(DiscoveredJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"招聘材料不存在: {job_id}")
    return _discovered_to_out(row)


@router.patch("/discovered-jobs/{job_id}", response_model=DiscoveredJobOut)
def update_discovered(job_id: int, payload: DiscoveredJobUpdate, db: Session = Depends(get_db)):
    row = db.get(DiscoveredJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"招聘材料不存在: {job_id}")
    if payload.status is not None:
        row.status = payload.status
    db.commit()
    db.refresh(row)
    return _discovered_to_out(row)


@router.post("/discovered-jobs/{job_id}/extract")
def extract_discovered(job_id: int, db: Session = Depends(get_db), provider=Depends(get_ai_provider)):
    """接入现有 Phase 3 AI Extraction：DiscoveredJob 正文 → 结构化 preview。

    不创建正式 Job —— 用户仍需走现有 Preview → 确认 → Save 流程。"""
    row = db.get(DiscoveredJob, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"招聘材料不存在: {job_id}")
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="AI 未配置：请在 .env 中设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 后重试",
        )
    text = row.description_raw or row.title_raw or ""
    if len(text.strip()) < 10:
        raise HTTPException(status_code=422, detail="该招聘材料缺少可解析的正文（未抓取 detail）")
    from app.api.routes.jobs import extract_preview
    from app.schemas.extraction import ExtractionRequest

    preview = extract_preview(ExtractionRequest(text=text.strip()), provider)
    # 状态推进：new/possible_duplicate → reviewing（用户开始处理）
    if row.status in ("new", "possible_duplicate"):
        row.status = "reviewing"
        db.commit()
    return preview

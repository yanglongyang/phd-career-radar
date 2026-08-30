"""Evidence CRUD API（Phase 6）。

Evidence 是事实资产：创建/更新/删除都带完整 provenance；
删除时同步清理 EvaluationEvidence 关联，不留悬挂引用。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import EvaluationEvidence, Evidence, Job, Organization
from app.schemas.evidence import EvidenceCreate, EvidenceOut, EvidenceUpdate

router = APIRouter(prefix="/evidence", tags=["evidence"])


def _get_or_404(db: Session, evidence_id: int) -> Evidence:
    row = db.get(Evidence, evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"证据不存在: {evidence_id}")
    return row


@router.get("", response_model=list[EvidenceOut])
def list_evidence(
    organization_id: int | None = Query(None),
    job_id: int | None = Query(None),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
):
    stmt = select(Evidence).order_by(Evidence.id)
    if organization_id is not None:
        stmt = stmt.where(Evidence.organization_id == organization_id)
    if job_id is not None:
        stmt = stmt.where(Evidence.job_id == job_id)
    if category:
        stmt = stmt.where(Evidence.category == category)
    return db.scalars(stmt).all()


@router.post("/jobs/{job_id}", response_model=EvidenceOut, status_code=201)
def create_job_evidence(job_id: int, payload: EvidenceCreate, db: Session = Depends(get_db)):
    """在岗位下创建证据；未显式提供 organization 时自动继承岗位所属单位。"""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"岗位不存在: {job_id}")
    org_id = payload.organization_id or job.organization_id
    row = Evidence(job_id=job_id, organization_id=org_id, **payload.model_dump(exclude={"organization_id"}))
    row.organization_id = org_id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/organizations/{org_id}", response_model=EvidenceOut, status_code=201)
def create_organization_evidence(org_id: int, payload: EvidenceCreate, db: Session = Depends(get_db)):
    """组织级风评证据（长期资产，不随岗位删除）。"""
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail=f"单位不存在: {org_id}")
    row = Evidence(organization_id=org_id, **payload.model_dump(exclude={"organization_id"}))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{evidence_id}", response_model=EvidenceOut)
def update_evidence(evidence_id: int, payload: EvidenceUpdate, db: Session = Depends(get_db)):
    """部分更新：省略字段 = 不修改。历史评估的 Evidence 审计展示来自
    input_snapshot 快照，因此这里的编辑不会漂移历史评估的审计记录。"""
    row = _get_or_404(db, evidence_id)
    for field, value in payload.model_dump(exclude_unset=True, exclude={"organization_id"}).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: int, db: Session = Depends(get_db)):
    row = _get_or_404(db, evidence_id)
    # 先清理评估关联，避免悬挂引用
    db.execute(sa_delete(EvaluationEvidence).where(EvaluationEvidence.evidence_id == evidence_id))
    db.delete(row)
    db.commit()


@router.get("/organizations/{org_id}", response_model=list[EvidenceOut])
def list_organization_evidence(org_id: int, db: Session = Depends(get_db)):
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail=f"单位不存在: {org_id}")
    return db.scalars(
        select(Evidence)
        .where(Evidence.organization_id == org_id, Evidence.job_id.is_(None))
        .order_by(Evidence.id)
    ).all()

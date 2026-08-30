"""Evidence CRUD API（Phase 6）。

Evidence 是事实资产：创建/更新/删除都带完整 provenance；
删除时同步清理 EvaluationEvidence 关联，不留悬挂引用。
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import EvaluationEvidence, Evidence, Job, Organization
from app.schemas.evidence import EvidenceCreate, EvidenceOut, EvidenceUpdate
from app.services.evidence import validate_repost_chain

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
    """在岗位下创建证据。organization 恒为岗位所属单位（不接受伪造归属）。"""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"岗位不存在: {job_id}")
    validate_repost_chain(db, evidence_id=None, repost_of=payload.repost_of_evidence_id,
                          organization_id=job.organization_id)
    row = Evidence(job_id=job_id, organization_id=job.organization_id,
                   **payload.model_dump(exclude={"organization_id"}))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/organizations/{org_id}", response_model=EvidenceOut, status_code=201)
def create_organization_evidence(org_id: int, payload: EvidenceCreate, db: Session = Depends(get_db)):
    """组织级风评证据（长期资产，不随岗位删除）。"""
    if db.get(Organization, org_id) is None:
        raise HTTPException(status_code=404, detail=f"单位不存在: {org_id}")
    validate_repost_chain(db, evidence_id=None, repost_of=payload.repost_of_evidence_id,
                          organization_id=org_id)
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
    validate_repost_chain(db, evidence_id=row.id, repost_of=payload.repost_of_evidence_id,
                          organization_id=row.organization_id)
    for field, value in payload.model_dump(exclude_unset=True, exclude={"organization_id"}).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{evidence_id}", status_code=204)
def delete_evidence(evidence_id: int, db: Session = Depends(get_db)):
    """Phase 6.1 P0-3：已参与任何评估的证据不允许硬删除 —— 删除会破坏
    "input_snapshot Evidence = EvaluationEvidence links" 的 Phase 4 冻结不变量。
    只有从未参与评估的证据才可删除。"""
    row = _get_or_404(db, evidence_id)
    used = db.scalars(
        select(EvaluationEvidence.evidence_id).where(
            EvaluationEvidence.evidence_id == evidence_id
        )
    ).first()
    if used is not None:
        raise HTTPException(
            status_code=409,
            detail="该证据已用于历史评估，不能删除：评估审计链（input_snapshot 与关联记录）必须保留",
        )
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

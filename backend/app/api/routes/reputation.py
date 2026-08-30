"""Reputation 聚合 API（Phase 6）：确定性统计 + 可选 AI 主题综合。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.ai.provider import AIError
from app.api.deps import get_ai_provider
from app.db.session import get_db
from app.models import Organization
from app.schemas.reputation import ReputationReportOut
from app.services import reputation as reputation_service

router = APIRouter(prefix="/organizations/{org_id}/reputation", tags=["reputation"])


def _org_or_404(db: Session, org_id: int) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail=f"单位不存在: {org_id}")
    return org


@router.get("", response_model=ReputationReportOut)
def get_reputation_report(
    org_id: int,
    department: str | None = Query(None, description="限定院系（校级证据仍纳入）"),
    db: Session = Depends(get_db),
):
    """纯确定性风评报告：逐主题来源数/独立来源数/等级/时间跨度 + eligibility + 情报线索。"""
    org = _org_or_404(db, org_id)
    return reputation_service.build_report(db, org, department)


@router.post("/synthesize", response_model=ReputationReportOut)
def synthesize_reputation(
    org_id: int,
    department: str | None = Query(None),
    db: Session = Depends(get_db),
    provider=Depends(get_ai_provider),
):
    """在确定性报告之上叠加 AI 主题叙述综合（AI 只写结论，数字来自统计层）。"""
    org = _org_or_404(db, org_id)
    if provider is None:
        raise HTTPException(
            status_code=503,
            detail="AI 未配置：请在 .env 中设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 后重试",
        )
    try:
        report = reputation_service.synthesize_report(db, org, provider, department)
    except AIError as e:
        raise HTTPException(status_code=502, detail=f"AI 风评综合失败：{e}") from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return report

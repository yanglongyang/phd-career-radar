"""JobEvaluation 输出模型：数据库 JSON 列转成数组字段。"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models import JobEvaluation


class RiskItemOut(BaseModel):
    type: str
    severity: str
    reason: str
    evidence_ids: list[int] = Field(default_factory=list)


class EvaluationEvidenceBrief(BaseModel):
    """本次评估实际使用的证据摘要（Evaluation Audit 展示用）。"""

    id: int
    claim: str
    evidence_level: str
    source_type: str | None = None
    scope_level: str | None = None
    stance: str | None = None


class JobEvaluationOut(BaseModel):
    id: int
    job_id: int
    total_score: float | None = None       # provisional：缺失维度重新归一化
    score_coverage: float | None = None    # 0-100 评分覆盖度

    fit_score: float | None = None
    career_stability_score: float | None = None
    research_resources_score: float | None = None
    region_score: float | None = None
    compensation_score: float | None = None
    reputation_score: float | None = None
    workload_score: float | None = None
    long_term_score: float | None = None

    recommendation_level: str | None = None
    risk_level: str | None = None
    confidence_level: str | None = None

    summary: str | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)        # legacy 文本，兼容保留
    risk_items: list[RiskItemOut] = Field(default_factory=list)  # 结构化风险
    unknowns: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    hard_filters_triggered: list[str] = Field(default_factory=list)

    provider: str | None = None
    evaluation_version: str
    prompt_version: str | None = None
    model: str | None = None
    evaluated_at: datetime

    # ---- Evaluation Audit（Phase 4）----
    profile_hash: str | None = None
    scoring_config_hash: str | None = None
    region_config_hash: str | None = None
    evidence_items: list[EvaluationEvidenceBrief] = Field(default_factory=list)

    @classmethod
    def from_model(cls, e: "JobEvaluation") -> "JobEvaluationOut":
        return cls(
            id=e.id,
            job_id=e.job_id,
            total_score=e.total_score,
            score_coverage=e.score_coverage,
            fit_score=e.fit_score,
            career_stability_score=e.career_stability_score,
            research_resources_score=e.research_resources_score,
            region_score=e.region_score,
            compensation_score=e.compensation_score,
            reputation_score=e.reputation_score,
            workload_score=e.workload_score,
            long_term_score=e.long_term_score,
            recommendation_level=e.recommendation_level,
            risk_level=e.risk_level,
            confidence_level=e.confidence_level,
            summary=e.summary,
            strengths=list(e.strengths_json or []),
            weaknesses=list(e.weaknesses_json or []),
            risks=list(e.risks_json or []),
            risk_items=[
                RiskItemOut.model_validate(item) for item in (e.risk_items_json or [])
            ],
            unknowns=list(e.unknowns_json or []),
            questions=list(e.questions_json or []),
            hard_filters_triggered=list(e.hard_filters_json or []),
            provider=e.provider,
            evaluation_version=e.evaluation_version,
            prompt_version=e.prompt_version,
            model=e.model,
            evaluated_at=e.evaluated_at,
            profile_hash=e.profile_hash,
            scoring_config_hash=e.scoring_config_hash,
            region_config_hash=e.region_config_hash,
            evidence_items=[
                EvaluationEvidenceBrief(
                    id=link.evidence.id,
                    claim=link.evidence.claim,
                    evidence_level=link.evidence.evidence_level,
                    source_type=link.evidence.source_type,
                    scope_level=link.evidence.scope_level,
                    stance=link.evidence.stance,
                )
                for link in e.evidence_links
            ],
        )

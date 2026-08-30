from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.evaluation_evidence import EvaluationEvidence
    from app.models.job import Job


class JobEvaluation(Base):
    """岗位评估（Phase 2.1 加固）。

    语义分工：
    - AI 负责：维度分数、risk_level/risk_items、unknowns、confidence（事实判断）。
    - 后端规则引擎负责：total_score（provisional）、score_coverage、
      recommendation_level（唯一权威来源）。
    - 审计：保存 provider/model/prompt_version + Profile/评分/地区配置的
      快照与哈希 + 实际使用的 Evidence 关联，保证历史评估可复现。
    """

    __tablename__ = "job_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)

    # 由后端确定性计算，不由 AI 输出
    total_score: Mapped[float | None] = mapped_column(Float)  # provisional：缺失维度重新归一化
    score_coverage: Mapped[float | None] = mapped_column(Float)  # 0-100，已评分维度的权重占比

    fit_score: Mapped[float | None] = mapped_column(Float)
    career_stability_score: Mapped[float | None] = mapped_column(Float)
    research_resources_score: Mapped[float | None] = mapped_column(Float)
    region_score: Mapped[float | None] = mapped_column(Float)
    compensation_score: Mapped[float | None] = mapped_column(Float)
    reputation_score: Mapped[float | None] = mapped_column(Float)
    workload_score: Mapped[float | None] = mapped_column(Float)
    long_term_score: Mapped[float | None] = mapped_column(Float)

    # 后端规则引擎依据 total/risk/hard_filters 计算，AI 无决定权
    recommendation_level: Mapped[str | None] = mapped_column(String(2))  # S/A/B/C/D/X
    risk_level: Mapped[str | None] = mapped_column(String(16))           # low/medium/high/critical
    confidence_level: Mapped[str | None] = mapped_column(String(16))     # low/medium/high

    summary: Mapped[str | None] = mapped_column(Text)

    strengths_json: Mapped[list | None] = mapped_column(JSON)
    weaknesses_json: Mapped[list | None] = mapped_column(JSON)
    risks_json: Mapped[list | None] = mapped_column(JSON)        # legacy 文本列表，兼容保留
    risk_items_json: Mapped[list | None] = mapped_column(JSON)   # 结构化风险条目
    unknowns_json: Mapped[list | None] = mapped_column(JSON)
    questions_json: Mapped[list | None] = mapped_column(JSON)
    hard_filters_json: Mapped[list | None] = mapped_column(JSON)  # 触发的硬性过滤项

    # ---- 审计字段（Phase 2.1）----
    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    evaluation_version: Mapped[str] = mapped_column(String(32), default="v1")

    profile_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    profile_hash: Mapped[str | None] = mapped_column(String(64))
    scoring_config_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    scoring_config_hash: Mapped[str | None] = mapped_column(String(64))
    region_config_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    region_config_hash: Mapped[str | None] = mapped_column(String(64))
    input_snapshot_json: Mapped[dict | None] = mapped_column(JSON)  # AI 实际看到的输入快照

    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped["Job"] = relationship(back_populates="evaluations")
    evidence_links: Mapped[list["EvaluationEvidence"]] = relationship(
        back_populates="evaluation", cascade="all, delete-orphan"
    )

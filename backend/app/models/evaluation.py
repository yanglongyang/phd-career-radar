from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.job import Job


class JobEvaluation(Base):
    """AI 结构化评估。总分与推荐等级分开：信息不足反映在 confidence/unknowns，不人为压分。"""

    __tablename__ = "job_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)

    total_score: Mapped[float | None] = mapped_column(Float)

    fit_score: Mapped[float | None] = mapped_column(Float)
    career_stability_score: Mapped[float | None] = mapped_column(Float)
    research_resources_score: Mapped[float | None] = mapped_column(Float)
    region_score: Mapped[float | None] = mapped_column(Float)
    compensation_score: Mapped[float | None] = mapped_column(Float)
    reputation_score: Mapped[float | None] = mapped_column(Float)
    workload_score: Mapped[float | None] = mapped_column(Float)
    long_term_score: Mapped[float | None] = mapped_column(Float)

    recommendation_level: Mapped[str | None] = mapped_column(String(2))  # S/A/B/C/D/X
    risk_level: Mapped[str | None] = mapped_column(String(16))           # low/medium/high/critical
    confidence_level: Mapped[str | None] = mapped_column(String(16))     # low/medium/high

    summary: Mapped[str | None] = mapped_column(Text)

    strengths_json: Mapped[list | None] = mapped_column(JSON)
    weaknesses_json: Mapped[list | None] = mapped_column(JSON)
    risks_json: Mapped[list | None] = mapped_column(JSON)
    unknowns_json: Mapped[list | None] = mapped_column(JSON)
    questions_json: Mapped[list | None] = mapped_column(JSON)
    hard_filters_json: Mapped[list | None] = mapped_column(JSON)  # 触发的硬性过滤项

    evaluation_version: Mapped[str] = mapped_column(String(32), default="v1")
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))

    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="evaluations")

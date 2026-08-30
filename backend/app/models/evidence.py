from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.job import Job
from app.models.organization import Organization


class Evidence(Base):
    """事实与风评证据。官方政策与网络讨论分开记录，逐条带来源与证据等级。"""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)

    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)

    # 风评分类：assessment_pressure / salary_fulfillment / startup_funding_fulfillment /
    # administrative_burden / teaching_load / young_faculty_turnover / promotion_environment /
    # department_management / research_collaboration / student_resources / other / fact
    category: Mapped[str] = mapped_column(String(64), default="other")

    claim: Mapped[str] = mapped_column(Text)  # 这条证据声称什么

    source_type: Mapped[str | None] = mapped_column(String(64))   # official/forum/zhihu/xiaohongshu/maimai/...
    source_url: Mapped[str | None] = mapped_column(String(1024))
    source_title: Mapped[str | None] = mapped_column(String(256))

    evidence_level: Mapped[str] = mapped_column(String(1), default="C")  # A/B/C/D
    published_at: Mapped[date | None] = mapped_column(Date)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confidence: Mapped[str | None] = mapped_column(String(16))  # low/medium/high

    raw_excerpt: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job | None] = relationship(back_populates="evidence")
    organization: Mapped[Organization | None] = relationship()

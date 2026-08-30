from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.job import Job


class JobVersion(Base):
    """招聘公告变更历史：JD/薪资/截止日期变化时保存旧内容快照与变更清单，不覆盖旧数据。"""

    __tablename__ = "job_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)

    content_hash: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    salary_text: Mapped[str | None] = mapped_column(String(256))
    deadline: Mapped[date | None] = mapped_column(Date)

    changes_json: Mapped[list | None] = mapped_column(JSON)  # [{field, old, new}]
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped[Job] = relationship(back_populates="versions")

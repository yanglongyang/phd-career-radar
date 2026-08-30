from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.job import Job


class Application(Base):
    """申请 CRM。状态流转受 APPLICATION_STATUS_TRANSITIONS 约束；每个岗位一条申请记录。"""

    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True, index=True)

    status: Mapped[str] = mapped_column(String(32), default="new")
    priority: Mapped[int | None] = mapped_column()

    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    resume_version: Mapped[str | None] = mapped_column(String(64))
    cover_letter_version: Mapped[str | None] = mapped_column(String(64))
    contact: Mapped[str | None] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)

    next_action: Mapped[str | None] = mapped_column(String(256))
    next_action_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    job: Mapped[Job] = relationship(back_populates="applications")

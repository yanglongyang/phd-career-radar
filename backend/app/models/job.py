from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import JobCategory, JobDisposition, PositionNature

if TYPE_CHECKING:
    from app.models.academic_job_details import AcademicJobDetails
    from app.models.application import Application
    from app.models.evaluation import JobEvaluation
    from app.models.evidence import Evidence
    from app.models.job_import_record import JobImportRecord
    from app.models.job_version import JobVersion
    from app.models.organization import Organization


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    source: Mapped[str] = mapped_column(String(64), default="manual")
    source_job_id: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)

    title: Mapped[str] = mapped_column(String(256))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    department: Mapped[str | None] = mapped_column(String(256))

    job_category: Mapped[str] = mapped_column(String(32), default=JobCategory.other.value)
    country: Mapped[str | None] = mapped_column(String(64))
    province: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(64), index=True)

    description_raw: Mapped[str | None] = mapped_column(Text)
    description_clean: Mapped[str | None] = mapped_column(Text)

    posted_at: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employment_type: Mapped[str | None] = mapped_column(String(64))
    # legacy / 派生展示字段：聘用事实的正交表达见 academic_details
    position_nature: Mapped[str] = mapped_column(String(32), default=PositionNature.unknown.value)

    salary_text: Mapped[str | None] = mapped_column(String(256))
    # legacy / compatibility：语义模糊（单位/币种/固定-浮动不明），新代码优先用下方标准化字段
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)

    # ---- 薪资标准化字段（Phase 2.1）----
    salary_currency: Mapped[str | None] = mapped_column(String(8))     # CNY/USD/...；None = 未知
    salary_period: Mapped[str | None] = mapped_column(String(16))      # year/month/day/hour；None = 未知
    guaranteed_salary_min: Mapped[float | None] = mapped_column(Float)  # 固定收入
    guaranteed_salary_max: Mapped[float | None] = mapped_column(Float)
    variable_salary_min: Mapped[float | None] = mapped_column(Float)    # 绩效/浮动
    variable_salary_max: Mapped[float | None] = mapped_column(Float)
    advertised_total_min: Mapped[float | None] = mapped_column(Float)   # 广告口径总包
    advertised_total_max: Mapped[float | None] = mapped_column(Float)

    degree_requirement: Mapped[str | None] = mapped_column(String(128))
    experience_requirement: Mapped[str | None] = mapped_column(String(128))

    # 信息筛选状态（JobDisposition）；求职流程状态在 applications 表
    status: Mapped[str] = mapped_column(String(32), default=JobDisposition.new.value, index=True)

    # 用户最终决策字段 — 与 AI 评估完全分开，AI 不得覆盖
    user_rating: Mapped[int | None] = mapped_column()      # 1-5
    user_priority: Mapped[int | None] = mapped_column()    # 1-10
    user_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    organization: Mapped["Organization"] = relationship(lazy="joined")
    academic_details: Mapped["AcademicJobDetails | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    evaluations: Mapped[list["JobEvaluation"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    # Evidence 不随 Job 级联删除：组织级风评证据是长期资产，删岗位只把 job_id 置空
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="job")
    applications: Mapped[list["Application"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    versions: Mapped[list["JobVersion"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    import_records: Mapped[list["JobImportRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def latest_evaluation(self) -> "JobEvaluation | None":
        if not self.evaluations:
            return None
        return max(self.evaluations, key=lambda e: e.id)

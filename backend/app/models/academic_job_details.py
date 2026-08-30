"""高校岗位专用事实（Phase 2.1 P0）。

与企业岗位无关的字段集中在一对一扩展表，避免 jobs 表膨胀成 70 列大表。
所有 bool 字段允许 None（None = 未知，不得猜测）；文本字段保存公告原文表述。
四个聘用体系维度（establishment / tenure / contract / funding）互相正交，
例如 "非事业编 + 预聘副教授 + 6 年固定期限 + 学校经费" 可以同时表达。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import (
    ContractType,
    EstablishmentStatus,
    FundingSource,
    TenureStatus,
)


class AcademicJobDetails(Base):
    __tablename__ = "academic_job_details"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id"), unique=True, index=True
    )

    # ---- 编制 / 聘用体系（正交四轴）----
    establishment_status: Mapped[str] = mapped_column(
        String(32), default=EstablishmentStatus.unknown.value
    )
    tenure_status: Mapped[str] = mapped_column(
        String(32), default=TenureStatus.unknown.value
    )
    contract_type: Mapped[str] = mapped_column(
        String(32), default=ContractType.unknown.value
    )
    funding_source: Mapped[str] = mapped_column(
        String(32), default=FundingSource.unknown.value
    )

    # ---- 聘期与考核 ----
    contract_years: Mapped[int | None] = mapped_column(Integer)
    first_contract_period: Mapped[str | None] = mapped_column(String(128))  # 首聘周期
    is_up_or_out: Mapped[bool | None] = mapped_column()  # None = 未知
    midterm_review: Mapped[str | None] = mapped_column(Text)   # 中期考核
    final_review: Mapped[str | None] = mapped_column(Text)     # 聘期考核
    publication_requirements: Mapped[str | None] = mapped_column(Text)
    grant_requirements: Mapped[str | None] = mapped_column(Text)    # 基金要求
    teaching_requirements: Mapped[str | None] = mapped_column(Text)
    admin_requirements: Mapped[str | None] = mapped_column(Text)

    # ---- 职业身份与发展 ----
    current_title: Mapped[str | None] = mapped_column(String(128))
    promotion_path: Mapped[str | None] = mapped_column(Text)
    independent_pi: Mapped[bool | None] = mapped_column()

    # ---- 科研资源 ----
    lab_space: Mapped[str | None] = mapped_column(Text)
    startup_funding: Mapped[str | None] = mapped_column(Text)        # 启动经费（原文）
    startup_funding_terms: Mapped[str | None] = mapped_column(Text)  # 到账方式

    # ---- 学生资源 ----
    can_supervise_master: Mapped[bool | None] = mapped_column()
    can_supervise_phd: Mapped[bool | None] = mapped_column()
    master_quota: Mapped[str | None] = mapped_column(String(128))
    phd_quota: Mapped[str | None] = mapped_column(String(128))

    # ---- 收入与住房（V0.1 保存原文，不做金额解析）----
    fixed_income: Mapped[str | None] = mapped_column(Text)
    performance_income: Mapped[str | None] = mapped_column(Text)
    housing_settlement: Mapped[str | None] = mapped_column(Text)        # 安家费
    housing_subsidy: Mapped[str | None] = mapped_column(Text)           # 住房补贴
    talent_housing: Mapped[str | None] = mapped_column(Text)            # 人才房
    regional_talent_subsidy: Mapped[str | None] = mapped_column(Text)   # 地方人才补贴

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    job: Mapped["Job"] = relationship(back_populates="academic_details")  # noqa: F821

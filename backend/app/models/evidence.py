from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow
from app.models.enums import EvidenceScope, Stance

if TYPE_CHECKING:
    from app.models.job import Job
    from app.models.organization import Organization


class Evidence(Base):
    """事实与风评证据。官方政策与网络讨论分开记录，逐条带来源与证据等级。

    Phase 2.1 provenance 增强：可记录第一手/转述、独立来源分组、转载关系、
    立场与作用域（学校 ≠ 院系 ≠ 课题组）。删除 Job 时 Evidence 保留
    （服务层把 job_id 置空），不损坏单位风评库。
    """

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
    source_author: Mapped[str | None] = mapped_column(String(128))  # 公开来源标识（用户名/机构名）

    # provenance：true=明确第一手经历 / false=明确转述 / None=无法判断
    is_firsthand: Mapped[bool | None] = mapped_column(Boolean)
    # 独立来源分组键：同一信息源（含其转载）共享同一 key，如 "zhihu_user_abc_story_2025"
    independence_key: Mapped[str | None] = mapped_column(String(128), index=True)
    # 明确转载自另一条证据时指向其 id
    repost_of_evidence_id: Mapped[int | None] = mapped_column(ForeignKey("evidence.id"))

    stance: Mapped[str] = mapped_column(String(16), default=Stance.unknown.value)

    # 作用域：学校/院系/课题组/岗位 级别的风评可能完全不同
    scope_level: Mapped[str] = mapped_column(String(16), default=EvidenceScope.unknown.value)
    scope_name: Mapped[str | None] = mapped_column(String(256))  # 例：化学学院

    evidence_level: Mapped[str] = mapped_column(String(1), default="C")  # A/B/C/D
    published_at: Mapped[date | None] = mapped_column(Date)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    confidence: Mapped[str | None] = mapped_column(String(16))  # low/medium/high

    raw_excerpt: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped["Job | None"] = relationship(back_populates="evidence")
    organization: Mapped["Organization | None"] = relationship()
    repost_of: Mapped["Evidence | None"] = relationship(remote_side=[id])

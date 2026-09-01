from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    # V0.3 允许值：university / research_institute / state_owned / enterprise / hospital / other。
    # 与 DiscoveredJob.sector 含义接近但生命周期不同：sector 是发现阶段的来源 hint
    # （发现时冻结）；organization_type 是正式 Job 入库后的确认事实。
    # 不做后台任务自动同步覆盖用户已确认的 Organization 数据。
    organization_type: Mapped[str | None] = mapped_column(String(64))
    province: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(64))
    official_url: Mapped[str | None] = mapped_column(String(1024))
    career_url: Mapped[str | None] = mapped_column(String(1024))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

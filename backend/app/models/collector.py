"""Collector V0.2 模型：运行审计（CollectorRun / CollectorRunItem）+ Inbox（DiscoveredJob）。

职责边界（规格第一节）：
- Collector 只负责"发现可能包含招聘信息的公开材料"，输出 DiscoveredJob（Inbox）；
- 一条 DiscoveredJob ≠ 一个正式 Job（一份公告可含多个岗位）；
- 正式 Job 只能由用户确认后的 AI Extraction Preview 流程创建；
- DiscoveredJob.status 独立于 Job.status（不复用冻结阶段的岗位状态）。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class CollectorRun(Base):
    """一次"检查招聘更新"的完整审计。"""

    __tablename__ = "collector_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(24), default="running")  # running/completed/partial_failure/failed
    trigger: Mapped[str] = mapped_column(String(16), default="manual")

    source_count: Mapped[int] = mapped_column(Integer, default=0)
    completed_source_count: Mapped[int] = mapped_column(Integer, default=0)

    discovered_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    possible_duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    filtered_count: Mapped[int] = mapped_column(Integer, default=0)
    recency_skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_source_count: Mapped[int] = mapped_column(Integer, default=0)

    items: Mapped[list["CollectorRunItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class CollectorRunItem(Base):
    """一次运行中单个 source 的结果（UI 显示 source 级状态）。"""

    __tablename__ = "collector_run_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("collector_runs.id"), index=True)

    source_id: Mapped[str] = mapped_column(String(64))
    source_name: Mapped[str] = mapped_column(String(128))

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(16), default="running")  # running/success/failed/skipped

    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    new_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    possible_duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    filtered_count: Mapped[int] = mapped_column(Integer, default=0)
    recency_skipped_count: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(String(500))  # 长度限制，不存敏感头

    run: Mapped[CollectorRun] = relationship(back_populates="items")


class DiscoveredJob(Base):
    """招聘发现 Inbox：Collector 的唯一产出，等待用户审核。

    确定性去重（same source_job_id / same canonical URL / same fingerprint）
    只更新 last_seen；possible duplicate 只标记不合并。
    """

    __tablename__ = "discovered_jobs"
    __table_args__ = (
        UniqueConstraint("source_id", "source_job_id", name="uq_discovered_source_job"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    source_id: Mapped[str] = mapped_column(String(64), index=True)
    source_name: Mapped[str] = mapped_column(String(128))
    source_job_id: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str] = mapped_column(String(1024))

    canonical_url: Mapped[str | None] = mapped_column(String(1024), unique=True, index=True)
    # 确定性 fingerprint（Level 3，无稳定 source_job_id 时）：normalize(org)+normalize(title)+path
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)

    title_raw: Mapped[str | None] = mapped_column(String(512))
    description_raw: Mapped[str | None] = mapped_column(Text)
    published_at_raw: Mapped[str | None] = mapped_column(String(64))

    organization_hint: Mapped[str | None] = mapped_column(String(256))
    location_hint: Mapped[str | None] = mapped_column(String(128))

    content_hash: Mapped[str | None] = mapped_column(String(64))

    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    # new / reviewing / ignored / imported / possible_duplicate

    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    first_run_id: Mapped[int | None] = mapped_column(Integer)
    last_run_id: Mapped[int | None] = mapped_column(Integer)

    possible_duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("discovered_jobs.id"), index=True
    )
    duplicate_reason: Mapped[str | None] = mapped_column(String(256))

    raw_payload_json: Mapped[dict | None] = mapped_column(JSON)  # 抓取元信息

    imported_job_id: Mapped[int | None] = mapped_column(Integer)  # 用户确认后创建的正式 Job id

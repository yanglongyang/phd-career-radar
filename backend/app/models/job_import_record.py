"""AI 导入审计（Phase 3.1）。

记录一次岗位导入的完整 provenance：来源方式、AI 解析原始输出（未经用户修改）、
用户确认后的最终 payload、模型与 Prompt 版本、正文哈希。
没有这条记录，"这些字段是 AI 解析的还是我手改的"将永远无法回答。
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, utcnow


class JobImportRecord(Base):
    __tablename__ = "job_import_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)

    ingestion_method: Mapped[str] = mapped_column(String(16))  # text/url/manual
    source_url: Mapped[str | None] = mapped_column(String(1024))

    provider: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(64))

    extraction_json: Mapped[dict | None] = mapped_column(JSON)        # AI 原始解析输出
    confirmed_payload_json: Mapped[dict | None] = mapped_column(JSON)  # 用户确认后的最终 payload
    source_text_hash: Mapped[str | None] = mapped_column(String(64))   # SHA-256(description_raw)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    job: Mapped["Job"] = relationship(back_populates="import_records")  # noqa: F821

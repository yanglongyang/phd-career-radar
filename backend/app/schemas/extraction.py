"""AI 解析预览（Phase 3）：粘贴/URL → AI 结构化 → 用户确认 → 保存。

本端点只产出预览、不写数据库；保存走 POST /api/jobs（含嵌套 academic_details）。
"""

from pydantic import BaseModel, Field

from app.ai.schemas import JobExtractionOut


class ExtractionRequest(BaseModel):
    text: str | None = Field(default=None, description="招聘公告全文")
    url: str | None = Field(default=None, description="公告链接（可公开访问）")


class ExtractionPreviewOut(BaseModel):
    source_text: str                      # AI 实际解析的正文（URL 抓取时为提取后的文本）
    extraction: JobExtractionOut          # 结构化结果（含 unknowns）
    provider: str
    model: str | None
    prompt_version: str

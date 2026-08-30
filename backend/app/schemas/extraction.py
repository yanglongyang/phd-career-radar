"""AI 解析预览（Phase 3）：粘贴/URL → AI 结构化 → 用户确认 → 保存。

本端点只产出预览、不写数据库；保存走 POST /api/jobs（含嵌套 academic_details）。
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.ai.schemas import JobExtractionOut

# 送给 AI 的正文上限（字符）：内存与 token 成本双重保护，超限明确报错
MAX_TEXT_CHARS = 100_000


class ExtractionRequest(BaseModel):
    """text 与 url 必须二选一：都不传或同时传都是 422，不静默挑一个。"""

    text: str | None = Field(default=None, max_length=MAX_TEXT_CHARS, description="招聘公告全文")
    url: str | None = Field(default=None, max_length=2048, description="公告链接（可公开访问）")

    @model_validator(mode="after")
    def _exactly_one(self) -> "ExtractionRequest":
        if (self.text is None) == (self.url is None):
            raise ValueError("text 与 url 必须提供且只能提供一个")
        return self


class ExtractionPreviewOut(BaseModel):
    source_type: Literal["text", "url"]   # 本次解析的来源类型
    source_url: str | None                # url 来源时的链接；text 来源为 null
    source_text: str                      # AI 实际解析的正文（URL 抓取时为提取后的文本）
    extraction: JobExtractionOut          # 结构化结果（含 unknowns）
    provider: str
    model: str | None
    prompt_version: str


class ImportAuditIn(BaseModel):
    """AI 导入审计：保存岗位时随 JobCreate 提交，由后端持久化（Phase 3.1）。"""

    ingestion_method: Literal["text", "url", "manual"]
    source_url: str | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    extraction_json: dict | None = None   # AI 原始结构化输出（未经用户修改）

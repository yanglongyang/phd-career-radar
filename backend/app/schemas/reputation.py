"""Reputation 聚合的输出 Schema（Phase 6）。

数字（来源数、独立来源数、等级分布、时间跨度、eligibility）全部由后端
确定性统计产生；AI 只提供主题叙述结论（ai_conclusion），二者在此合并。
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ReputationTopicStat(BaseModel):
    topic: str
    positive_sources: int = Field(ge=0)
    negative_sources: int = Field(ge=0)
    independent_sources: int = Field(ge=0)
    evidence_levels: list[str] = Field(default_factory=list)
    time_start: str | None = None
    time_end: str | None = None
    eligible_for_scoring: bool
    eligible_reason: str
    evidence_ids: list[int] = Field(default_factory=list)
    ai_conclusion: str | None = None  # AI 叙述结论（synthesize 后填充）


class ReputationClueItem(BaseModel):
    """情报线索：有参考价值但按策略不进入定量评分的证据。"""

    evidence_id: int
    claim: str
    reason: str  # 为什么不进计量（scope 未标明 / lab 级 / 单一独立来源不足等）


class ReputationReportOut(BaseModel):
    organization_id: int
    organization_name: str
    department: str | None = None
    topics: list[ReputationTopicStat] = Field(default_factory=list)
    clues: list[ReputationClueItem] = Field(default_factory=list)
    overall_confidence: str  # low/medium/high：任一 eligible 主题 → medium，否则 low
    synthesized_by_ai: bool = False
    prompt_version: str | None = None
    generated_at: datetime

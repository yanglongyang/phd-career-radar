from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EvidenceLevelLiteral = Literal["A", "B", "C", "D"]
StanceLiteral = Literal["positive", "negative", "mixed", "neutral", "unknown"]
ScopeLiteral = Literal["organization", "department", "lab", "job", "unknown"]

# 风评分类（Phase 6 聚合用）+ fact（官方事实）
EVIDENCE_CATEGORIES = [
    "fact",
    "assessment_pressure",
    "salary_fulfillment",
    "startup_funding_fulfillment",
    "administrative_burden",
    "teaching_load",
    "young_faculty_turnover",
    "promotion_environment",
    "department_management",
    "research_collaboration",
    "student_resources",
    "other",
]


class EvidenceCreate(BaseModel):
    claim: str = Field(min_length=1)
    category: str = "other"
    source_type: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_author: str | None = None
    is_firsthand: bool | None = None          # true=第一手 / false=转述 / None=无法判断
    independence_key: str | None = None       # 同一信息源（含转载）共享同一分组键
    repost_of_evidence_id: int | None = None
    stance: StanceLiteral = "unknown"
    scope_level: ScopeLiteral = "unknown"
    scope_name: str | None = None
    evidence_level: EvidenceLevelLiteral = "C"
    published_at: date | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    raw_excerpt: str | None = None
    organization_id: int | None = None


class EvidenceUpdate(BaseModel):
    """部分更新：全字段可选；省略 = 不修改。"""

    claim: str | None = Field(default=None, min_length=1)
    category: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_author: str | None = None
    is_firsthand: bool | None = None
    independence_key: str | None = None
    repost_of_evidence_id: int | None = None
    stance: StanceLiteral | None = None
    scope_level: ScopeLiteral | None = None
    scope_name: str | None = None
    evidence_level: EvidenceLevelLiteral | None = None
    published_at: date | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    raw_excerpt: str | None = None


class EvidenceOut(BaseModel):
    id: int
    job_id: int | None = None
    organization_id: int | None = None
    category: str
    claim: str
    source_type: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    source_author: str | None = None
    is_firsthand: bool | None = None
    independence_key: str | None = None
    repost_of_evidence_id: int | None = None
    stance: str
    scope_level: str
    scope_name: str | None = None
    evidence_level: str
    published_at: date | None = None
    collected_at: datetime
    confidence: str | None = None
    raw_excerpt: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

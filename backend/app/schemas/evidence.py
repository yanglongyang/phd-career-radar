from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

EvidenceLevelLiteral = Literal["A", "B", "C", "D"]

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
    evidence_level: EvidenceLevelLiteral = "C"
    published_at: date | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    raw_excerpt: str | None = None
    organization_id: int | None = None


class EvidenceOut(BaseModel):
    id: int
    job_id: int | None = None
    organization_id: int | None = None
    category: str
    claim: str
    source_type: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    evidence_level: str
    published_at: date | None = None
    collected_at: datetime
    confidence: str | None = None
    raw_excerpt: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

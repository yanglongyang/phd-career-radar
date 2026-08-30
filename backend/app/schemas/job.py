from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.evaluation import JobEvaluationOut
from app.schemas.organization import OrganizationBrief

JobCategoryLiteral = Literal[
    "university_faculty",
    "university_research",
    "postdoc",
    "research_institute",
    "industry_rnd",
    "other",
]
PositionNatureLiteral = Literal[
    "permanent", "tenure", "tenure_track", "pre_tenure",
    "fixed_term", "postdoc", "pi_funded", "unknown",
]
JobStatusLiteral = Literal[
    "new", "reviewing", "shortlisted", "preparing", "applied",
    "interviewing", "offer", "closed", "ignored",
]


class JobSort(StrEnum):
    total_score = "total_score"
    first_seen_at = "first_seen_at"
    deadline = "deadline"
    region = "region"
    reputation = "reputation"
    created_at = "created_at"


class JobCreate(BaseModel):
    """手工新建岗位（Phase 2）。AI 粘贴解析在 Phase 3 提供。"""

    title: str = Field(min_length=1, max_length=256)

    organization_id: int | None = None
    organization_name: str | None = None  # 按名称自动查找/创建单位
    department: str | None = None

    job_category: JobCategoryLiteral = "other"
    country: str | None = None
    province: str | None = None
    city: str | None = None

    description_raw: str | None = None
    description_clean: str | None = None

    posted_at: date | None = None
    deadline: date | None = None

    employment_type: str | None = None
    position_nature: PositionNatureLiteral = "unknown"

    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None

    degree_requirement: str | None = None
    experience_requirement: str | None = None

    source: str = "manual"
    source_job_id: str | None = None
    source_url: str | None = None

    status: JobStatusLiteral = "new"

    allow_duplicate: bool = False  # 去重冲突时由用户确认仍要创建


class JobUpdate(BaseModel):
    """部分更新。description_raw/salary_text/deadline 变化会自动保存 JobVersion。"""

    title: str | None = Field(default=None, min_length=1, max_length=256)
    organization_id: int | None = None
    organization_name: str | None = None
    department: str | None = None

    job_category: JobCategoryLiteral | None = None
    country: str | None = None
    province: str | None = None
    city: str | None = None

    description_raw: str | None = None
    description_clean: str | None = None

    posted_at: date | None = None
    deadline: date | None = None

    employment_type: str | None = None
    position_nature: PositionNatureLiteral | None = None

    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None

    degree_requirement: str | None = None
    experience_requirement: str | None = None

    source_url: str | None = None
    status: JobStatusLiteral | None = None

    # 用户最终决策字段，独立于 AI 评估
    user_rating: int | None = Field(default=None, ge=1, le=5)
    user_priority: int | None = Field(default=None, ge=1, le=10)
    user_notes: str | None = None


class JobListItem(BaseModel):
    id: int
    title: str
    department: str | None = None
    job_category: str
    province: str | None = None
    city: str | None = None
    status: str
    position_nature: str
    salary_text: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    deadline: date | None = None
    first_seen_at: datetime
    source: str
    user_rating: int | None = None
    organization: OrganizationBrief | None = None
    evaluation: JobEvaluationOut | None = None


class JobVersionOut(BaseModel):
    id: int
    content_hash: str
    description: str | None = None
    salary_text: str | None = None
    deadline: date | None = None
    changes: list[dict] = []
    captured_at: datetime


class JobDetailOut(JobListItem):
    country: str | None = None
    description_raw: str | None = None
    description_clean: str | None = None
    posted_at: date | None = None
    employment_type: str | None = None
    degree_requirement: str | None = None
    experience_requirement: str | None = None
    source_url: str | None = None
    user_priority: int | None = None
    user_notes: str | None = None
    fingerprint: str
    created_at: datetime
    updated_at: datetime

    versions: list[JobVersionOut] = []
    has_version_changes: bool = False


class JobListPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[JobListItem]
    total: int
    page: int
    page_size: int

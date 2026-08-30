from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.academic import AcademicJobDetailsOut, AcademicJobDetailsUpdate
from app.schemas.evaluation import JobEvaluationOut
from app.schemas.extraction import ImportAuditIn
from app.schemas.organization import OrganizationBrief

JobCategoryLiteral = Literal[
    "university_faculty",
    "university_research",
    "postdoc",
    "research_institute",
    "industry_rnd",
    "other",
]
# legacy 字段：仅信息筛选状态；求职流程状态（preparing/applied/...）由 Application 负责
JobDispositionLiteral = Literal["new", "reviewing", "shortlisted", "ignored", "closed"]
SalaryCurrencyLiteral = Literal["CNY", "USD", "EUR", "GBP", "unknown"]
SalaryPeriodLiteral = Literal["year", "month", "day", "hour", "unknown"]


class JobSort(StrEnum):
    total_score = "total_score"
    first_seen_at = "first_seen_at"
    deadline = "deadline"
    region = "region"
    reputation = "reputation"
    created_at = "created_at"


class JobCreate(BaseModel):
    """手工新建岗位 / AI 解析确认后的保存。

    extra="forbid"：未知字段显式 422，不静默忽略（透明优先于兼容）。"""

    model_config = ConfigDict(extra="forbid")

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

    salary_text: str | None = None
    salary_min: float | None = None   # legacy / compatibility
    salary_max: float | None = None   # legacy / compatibility
    salary_currency: SalaryCurrencyLiteral | None = None
    salary_period: SalaryPeriodLiteral | None = None
    guaranteed_salary_min: float | None = None
    guaranteed_salary_max: float | None = None
    variable_salary_min: float | None = None
    variable_salary_max: float | None = None
    advertised_total_min: float | None = None
    advertised_total_max: float | None = None

    degree_requirement: str | None = None
    experience_requirement: str | None = None

    source: str = "manual"
    source_job_id: str | None = None
    source_url: str | None = None

    status: JobDispositionLiteral = "new"

    # AI 解析确认后随岗位原子入库（Phase 3）；手工新建可不传
    academic_details: AcademicJobDetailsUpdate | None = None

    # AI 导入审计（Phase 3.1）：AI 流程保存时必传，手工新建不传
    import_audit: ImportAuditIn | None = None

    allow_duplicate: bool = False  # 去重冲突时由用户确认仍要创建


class JobUpdate(BaseModel):
    """部分更新。description_raw/salary_text/deadline 变化会自动保存 JobVersion。"""

    model_config = ConfigDict(extra="forbid")

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

    salary_text: str | None = None
    salary_min: float | None = None   # legacy / compatibility
    salary_max: float | None = None   # legacy / compatibility
    salary_currency: SalaryCurrencyLiteral | None = None
    salary_period: SalaryPeriodLiteral | None = None
    guaranteed_salary_min: float | None = None
    guaranteed_salary_max: float | None = None
    variable_salary_min: float | None = None
    variable_salary_max: float | None = None
    advertised_total_min: float | None = None
    advertised_total_max: float | None = None

    degree_requirement: str | None = None
    experience_requirement: str | None = None

    source_url: str | None = None
    status: JobDispositionLiteral | None = None

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
    salary_currency: str | None = None
    salary_period: str | None = None
    guaranteed_salary_min: float | None = None
    guaranteed_salary_max: float | None = None
    variable_salary_min: float | None = None
    variable_salary_max: float | None = None
    advertised_total_min: float | None = None
    advertised_total_max: float | None = None
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
    changes: list[dict] = Field(default_factory=list)
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

    versions: list[JobVersionOut] = Field(default_factory=list)
    has_version_changes: bool = False
    academic_details: AcademicJobDetailsOut | None = None


class JobListPage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[JobListItem]
    total: int
    page: int
    page_size: int

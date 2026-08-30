"""Application CRM 的 API Schema（Phase 5）。

CRM 只消费 Phase 2-4 的评估结果，不修改核心事实/评分模型。
extra="forbid"：未知字段显式 422，不静默忽略。
"""

from datetime import date, datetime
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from app.models.application import Application

ApplicationStatusLiteral = Literal[
    "new", "reviewed", "shortlist", "contacting", "preparing", "applied",
    "written_test", "interview_1", "interview_2", "hr", "offer",
    "rejected", "withdrawn", "ignored",
]


class ApplicationCreate(BaseModel):
    """创建申请（每岗位一条）。status 缺省 new，也可以直接指定起始状态。"""

    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatusLiteral = "new"
    priority: int | None = Field(default=None, ge=1, le=10)
    resume_version: str | None = Field(default=None, max_length=64)
    cover_letter_version: str | None = Field(default=None, max_length=64)
    contact: str | None = Field(default=None, max_length=256)
    notes: str | None = None
    next_action: str | None = Field(default=None, max_length=256)
    next_action_date: date | None = None


class ApplicationUpdate(BaseModel):
    """部分更新。status 变化受 APPLICATION_STATUS_TRANSITIONS 流转表约束。

    status 不允许显式传 null：省略 = 不修改，null = 422（状态列 NOT NULL，
    显式失败优于 IntegrityError/500，Phase 5.1）。"""

    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatusLiteral | None = None

    @model_validator(mode="after")
    def _status_not_explicit_null(self) -> "ApplicationUpdate":
        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("status 不允许置空；请省略该字段或提供合法状态")
        return self
    priority: int | None = Field(default=None, ge=1, le=10)
    resume_version: str | None = Field(default=None, max_length=64)
    cover_letter_version: str | None = Field(default=None, max_length=64)
    contact: str | None = Field(default=None, max_length=256)
    notes: str | None = None
    next_action: str | None = Field(default=None, max_length=256)
    next_action_date: date | None = None


class ApplicationJobBrief(BaseModel):
    id: int
    title: str
    organization_name: str | None = None
    department: str | None = None
    city: str | None = None
    deadline: date | None = None
    total_score: float | None = None
    recommendation_level: str | None = None


class ApplicationOut(BaseModel):
    id: int
    job_id: int
    status: str
    priority: int | None = None
    applied_at: datetime | None = None
    resume_version: str | None = None
    cover_letter_version: str | None = None
    contact: str | None = None
    notes: str | None = None
    next_action: str | None = None
    next_action_date: date | None = None
    created_at: datetime
    updated_at: datetime
    job: ApplicationJobBrief | None = None
    allowed_next_statuses: list[str] = Field(default_factory=list)

    @classmethod
    def from_model(cls, app: "Application", job_brief: "ApplicationJobBrief | None" = None) -> "ApplicationOut":
        from app.models.enums import APPLICATION_STATUS_TRANSITIONS

        return cls(
            id=app.id,
            job_id=app.job_id,
            status=app.status,
            priority=app.priority,
            applied_at=app.applied_at,
            resume_version=app.resume_version,
            cover_letter_version=app.cover_letter_version,
            contact=app.contact,
            notes=app.notes,
            next_action=app.next_action,
            next_action_date=app.next_action_date,
            created_at=app.created_at,
            updated_at=app.updated_at,
            job=job_brief,
            allowed_next_statuses=sorted(
                APPLICATION_STATUS_TRANSITIONS.get(app.status, set())
            ),
        )


class ApplicationListPage(BaseModel):
    items: list["ApplicationOut"]
    total: int

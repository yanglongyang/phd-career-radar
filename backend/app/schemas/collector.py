"""Collector / Inbox API Schema（V0.2）。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DiscoveredStatusLiteral = Literal[
    "new", "reviewing", "ignored", "imported", "possible_duplicate"
]


class CollectorRunSummary(BaseModel):
    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    trigger: str
    source_count: int
    completed_source_count: int
    discovered_count: int
    new_count: int
    duplicate_count: int
    possible_duplicate_count: int
    filtered_count: int
    recency_skipped_count: int
    failed_source_count: int


class CollectorRunItemOut(BaseModel):
    id: int
    source_id: str
    source_name: str
    sector: str = "other"
    status: str
    started_at: datetime
    finished_at: datetime | None
    fetched_count: int
    new_count: int
    duplicate_count: int
    possible_duplicate_count: int
    filtered_count: int
    recency_skipped_count: int
    error_message: str | None = None


class CollectorRunOut(CollectorRunSummary):
    items: list[CollectorRunItemOut] = Field(default_factory=list)


class DiscoveredJobOut(BaseModel):
    id: int
    source_id: str
    source_name: str
    sector: str = "other"
    source_job_id: str | None = None
    source_url: str
    canonical_url: str | None = None
    title_raw: str | None = None
    description_raw: str | None = None
    published_at_raw: str | None = None
    organization_hint: str | None = None
    location_hint: str | None = None
    status: str
    discovered_at: datetime
    last_seen_at: datetime
    first_run_id: int | None = None
    last_run_id: int | None = None
    possible_duplicate_of_id: int | None = None
    duplicate_reason: str | None = None
    imported_job_id: int | None = None
    raw_payload: dict | None = None


class DiscoveredJobUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    status: DiscoveredStatusLiteral | None = None


class DiscoveredJobListPage(BaseModel):
    items: list[DiscoveredJobOut]
    total: int

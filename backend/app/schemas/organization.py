from datetime import datetime

from pydantic import BaseModel


class OrganizationBrief(BaseModel):
    id: int
    name: str
    organization_type: str | None = None
    province: str | None = None
    city: str | None = None


class OrganizationCreate(BaseModel):
    name: str
    organization_type: str | None = None
    province: str | None = None
    city: str | None = None
    official_url: str | None = None
    career_url: str | None = None
    notes: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    organization_type: str | None = None
    province: str | None = None
    city: str | None = None
    official_url: str | None = None
    career_url: str | None = None
    notes: str | None = None


class OrganizationOut(OrganizationBrief):
    official_url: str | None = None
    career_url: str | None = None
    notes: str | None = None
    job_count: int = 0
    created_at: datetime
    updated_at: datetime

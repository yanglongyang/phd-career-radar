"""AcademicJobDetails 的 API Schema（Phase 2.1）。

Update Schema 用 Literal 校验取值；exclude_unset 支持部分更新，
显式传 null 表示"未知/待确认"，与产品原则一致。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ContractTypeLiteral = Literal["open_ended", "fixed_term", "unknown"]
EstablishmentLiteral = Literal["established", "non_established", "unknown"]
FundingSourceLiteral = Literal["university", "department", "pi", "external", "mixed", "unknown"]
TenureLiteral = Literal["tenured", "tenure_track", "non_tenure", "unknown"]


class AcademicJobDetailsOut(BaseModel):
    establishment_status: str
    tenure_status: str
    contract_type: str
    funding_source: str

    contract_years: int | None = None
    first_contract_period: str | None = None
    is_up_or_out: bool | None = None
    midterm_review: str | None = None
    final_review: str | None = None
    publication_requirements: str | None = None
    grant_requirements: str | None = None
    teaching_requirements: str | None = None
    admin_requirements: str | None = None

    current_title: str | None = None
    promotion_path: str | None = None
    independent_pi: bool | None = None

    lab_space: str | None = None
    startup_funding: str | None = None
    startup_funding_terms: str | None = None

    can_supervise_master: bool | None = None
    can_supervise_phd: bool | None = None
    master_quota: str | None = None
    phd_quota: str | None = None

    fixed_income: str | None = None
    performance_income: str | None = None
    housing_settlement: str | None = None
    housing_subsidy: str | None = None
    talent_housing: str | None = None
    regional_talent_subsidy: str | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AcademicJobDetailsUpdate(BaseModel):
    establishment_status: EstablishmentLiteral | None = None
    tenure_status: TenureLiteral | None = None
    contract_type: ContractTypeLiteral | None = None
    funding_source: FundingSourceLiteral | None = None

    contract_years: int | None = Field(default=None, ge=0, le=30)
    first_contract_period: str | None = Field(default=None, max_length=128)
    is_up_or_out: bool | None = None
    midterm_review: str | None = None
    final_review: str | None = None
    publication_requirements: str | None = None
    grant_requirements: str | None = None
    teaching_requirements: str | None = None
    admin_requirements: str | None = None

    current_title: str | None = Field(default=None, max_length=128)
    promotion_path: str | None = None
    independent_pi: bool | None = None

    lab_space: str | None = None
    startup_funding: str | None = None
    startup_funding_terms: str | None = None

    can_supervise_master: bool | None = None
    can_supervise_phd: bool | None = None
    master_quota: str | None = Field(default=None, max_length=128)
    phd_quota: str | None = Field(default=None, max_length=128)

    fixed_income: str | None = None
    performance_income: str | None = None
    housing_settlement: str | None = None
    housing_subsidy: str | None = None
    talent_housing: str | None = None
    regional_talent_subsidy: str | None = None

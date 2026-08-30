"""AI 输出 Schema：所有 AI 返回必须通过 Pydantic 校验，不合法自动重试一次，仍失败则报错，
不允许把伪造结果写入数据库。

Phase 2.1 权责划分：AI 只做事实判断（维度分数、风险、信息缺口、置信度），
不再输出 recommendation_level / total_score / score_coverage ——
这些是确定性派生值，只由后端规则引擎计算（见 services/evaluation.py）。
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Score = int

ReputationTopicLiteral = Literal[
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


class JobExtractionOut(BaseModel):
    """粘贴/抓取的招聘公告 → 结构化岗位。公告未提及的字段必须为 null，不得猜测。"""

    title: str
    organization: str | None = None
    department: str | None = None
    job_category: Literal[
        "university_faculty", "university_research", "postdoc",
        "research_institute", "industry_rnd", "other",
    ] = "other"
    country: str | None = None
    province: str | None = None
    city: str | None = None
    employment_type: str | None = None
    posted_at: str | None = None
    deadline: str | None = None
    salary_text: str | None = None
    salary_currency: Literal["CNY", "USD", "EUR", "GBP", "unknown"] | None = None
    salary_period: Literal["year", "month", "day", "hour", "unknown"] | None = None
    degree_requirement: str | None = None
    experience_requirement: str | None = None

    # 高校岗位专用字段 —— 缺失一律 null，与 AcademicJobDetails 对齐
    # 四轴只有一套"未知"表示：字符串 "unknown"（Phase 2.1.1 去除 null 语义）
    establishment_status: Literal[
        "established", "non_established", "unknown"
    ] = "unknown"                 # 是否事业编
    tenure_status: Literal[
        "tenured", "tenure_track", "non_tenure", "unknown"
    ] = "unknown"                 # 长聘体系
    contract_type: Literal[
        "open_ended", "fixed_term", "unknown"
    ] = "unknown"                 # 合同期限类型
    funding_source: Literal[
        "university", "department", "pi", "external", "mixed", "unknown"
    ] = "unknown"                 # 经费来源
    is_up_or_out: bool | None = None              # 是否非升即走
    contract_years: int | None = None             # 合同年限
    first_contract_period: str | None = None      # 首聘周期
    midterm_review: str | None = None             # 中期考核
    final_review: str | None = None               # 聘期考核
    publication_requirements: str | None = None   # 论文要求
    grant_requirements: str | None = None         # 基金要求
    teaching_requirements: str | None = None      # 教学要求
    admin_requirements: str | None = None         # 行政要求
    current_title: str | None = None              # 当前职称
    promotion_path: str | None = None             # 晋升路径
    independent_pi: bool | None = None            # 独立PI资格
    lab_space: str | None = None                  # 实验室空间
    startup_funding: str | None = None            # 启动经费
    startup_funding_terms: str | None = None      # 启动经费到账方式
    can_supervise_master: bool | None = None      # 硕士招生资格
    can_supervise_phd: bool | None = None         # 博士招生资格
    master_quota: str | None = None               # 硕士指标
    phd_quota: str | None = None                  # 博士指标
    fixed_income: str | None = None               # 固定收入
    performance_income: str | None = None         # 绩效收入
    housing_settlement: str | None = None         # 安家费
    housing_subsidy: str | None = None            # 住房补贴
    talent_housing: str | None = None             # 人才房
    regional_talent_subsidy: str | None = None    # 地方人才补贴

    unknowns: list[str] = Field(default_factory=list)  # 重要的信息缺口


class EvaluationScores(BaseModel):
    fit: Score | None = None
    career_stability: Score | None = None
    research_resources: Score | None = None
    region: Score | None = None
    compensation: Score | None = None
    reputation: Score | None = None
    workload: Score | None = None
    long_term: Score | None = None

    @model_validator(mode="after")
    def _check_range(self) -> "EvaluationScores":
        for name, value in self.model_dump().items():
            if value is not None and not (0 <= value <= 100):
                raise ValueError(f"scores.{name} 必须在 0-100 之间，收到 {value}")
        return self


class RiskItem(BaseModel):
    """结构化风险条目：severity 供后端规则引擎使用，evidence_ids 指向依据。"""

    type: str
    severity: Literal["low", "medium", "high", "critical"]
    reason: str
    evidence_ids: list[int] = Field(default_factory=list)


class JobEvaluationOut(BaseModel):
    """AI 岗位评估输出（Phase 2.1 契约）。

    注意：不包含 recommendation_level / total_score / score_coverage，
    它们由后端 deterministic 规则引擎从 scores + risk + hard_filters 派生。
    """

    summary: str = ""
    scores: EvaluationScores = Field(default_factory=EvaluationScores)
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    risk_items: list[RiskItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)  # legacy 文本，兼容保留
    unknowns: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"

    @field_validator("scores", mode="before")
    @classmethod
    def _scores_must_be_object(cls, v):
        if not isinstance(v, dict):
            raise ValueError("scores 必须是对象")
        return v


class ReputationTopicOut(BaseModel):
    """风评聚合的单主题结论：不输出绝对化判断，逐主题给出正/负来源数与证据等级。"""

    topic: ReputationTopicLiteral
    positive_sources: int = Field(ge=0)
    negative_sources: int = Field(ge=0)
    independent_sources: int = Field(ge=0)
    evidence_levels: list[Literal["A", "B", "C", "D"]] = Field(default_factory=list)
    time_start: str | None = None
    time_end: str | None = None
    conclusion: str


class ReputationSummaryOut(BaseModel):
    topics: list[ReputationTopicOut] = Field(default_factory=list)
    overall_note: str = ""
    confidence: Literal["low", "medium", "high"] = "low"

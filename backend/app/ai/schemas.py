"""AI 输出 Schema：所有 AI 返回必须通过 Pydantic 校验，不合法自动重试一次，仍失败则报错，
不允许把伪造结果写入数据库。

Phase 2.1 权责划分：AI 只做事实判断（维度分数、风险、信息缺口、置信度），
不再输出 recommendation_level / total_score / score_coverage ——
这些是确定性派生值，只由后端规则引擎计算（见 services/evaluation.py）。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    model_config = ConfigDict(extra="forbid")

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
    """AI 只输出七个维度；region 由后端 Region Engine（用户配置）唯一决定，
    不给模型"发表一个不会被使用的分数"的机会（Phase 4.1.1）。"""

    model_config = ConfigDict(extra="forbid")
    fit: Score | None = None
    career_stability: Score | None = None
    research_resources: Score | None = None
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

    model_config = ConfigDict(extra="forbid")

    type: str
    severity: Literal["low", "medium", "high", "critical"]
    reason: str
    evidence_ids: list[int] = Field(default_factory=list)


class JobEvaluationOut(BaseModel):
    """AI 岗位评估输出（Phase 2.1 契约）。

    model_config = ConfigDict(extra="forbid")

    注意：不包含 recommendation_level / total_score / score_coverage，
    它们由后端 deterministic 规则引擎从 scores + risk + hard_filters 派生。
    """

    summary: str = ""
    # Phase 4.1：risk_level / confidence / scores 必填 —— 模型漏字段触发重试，
    # 而不是被 Pydantic 静默补成 medium（"没输出风险" != "明确判断中风险"）
    scores: EvaluationScores
    risk_level: Literal["low", "medium", "high", "critical"]
    risk_items: list[RiskItem] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)  # legacy 文本，兼容保留
    unknowns: list[str] = Field(default_factory=list)
    questions_to_ask: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"]

    model_config = ConfigDict(extra="forbid")

    @field_validator("scores", mode="before")
    @classmethod
    def _scores_must_be_object(cls, v):
        if not isinstance(v, dict):
            raise ValueError("scores 必须是对象")
        return v


class ReputationTopicConclusion(BaseModel):
    """AI 输出的单主题叙述结论。来源数/等级/时间跨度等数字一律由后端确定性
    统计填充（Phase 6），AI 不得也不需要输出任何计数。"""

    model_config = ConfigDict(extra="forbid")

    topic: ReputationTopicLiteral
    conclusion: str


class ReputationSynthesisOut(BaseModel):
    """AI 主题综合输出：只做叙述性聚合（发现主题、总结冲突与一致性）。

    Phase 6.1：不包含 confidence / overall_note —— overall_confidence 由
    后端确定性规则（任一 eligible 主题 → medium，否则 low）唯一决定，
    AI 不得把确定性 low 拔高成 high。"""

    model_config = ConfigDict(extra="forbid")

    topics: list[ReputationTopicConclusion] = Field(default_factory=list)

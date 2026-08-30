"""AI 输出 Schema：所有 AI 返回必须通过 Pydantic 校验，不合法自动重试一次，仍失败则报错，
不允许把伪造结果写入数据库。"""

from typing import Literal

from pydantic import BaseModel, model_validator

Score = int


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
    position_nature: Literal[
        "permanent", "tenure", "tenure_track", "pre_tenure",
        "fixed_term", "postdoc", "pi_funded", "unknown",
    ] = "unknown"
    employment_type: str | None = None
    posted_at: str | None = None
    deadline: str | None = None
    salary_text: str | None = None
    degree_requirement: str | None = None
    experience_requirement: str | None = None

    # 高校岗位专用字段（第九节）—— 缺失一律 null
    is_establishment: bool | None = None          # 是否事业编
    is_tenure: bool | None = None                 # 是否长聘
    is_tenure_track: bool | None = None           # 是否预聘
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
    can_supervise_students: bool | None = None    # 研究生招生资格
    master_quota: str | None = None               # 硕士指标
    phd_quota: str | None = None                  # 博士指标
    annual_salary: str | None = None              # 年薪
    fixed_income: str | None = None               # 固定收入
    performance_income: str | None = None         # 绩效收入
    housing_settlement: str | None = None         # 安家费
    housing_subsidy: str | None = None            # 住房补贴
    talent_housing: str | None = None             # 人才房
    regional_talent_subsidy: str | None = None    # 地方人才补贴

    unknowns: list[str] = []  # 重要的信息缺口


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


class JobEvaluationOut(BaseModel):
    """AI 岗位评估输出（第十八节 Schema）。"""

    summary: str = ""
    recommendation_level: Literal["S", "A", "B", "C", "D", "X"]
    scores: EvaluationScores = EvaluationScores()
    strengths: list[str] = []
    weaknesses: list[str] = []
    risks: list[str] = []
    unknowns: list[str] = []
    questions_to_ask: list[str] = []
    confidence: Literal["low", "medium", "high"] = "medium"


class ReputationSummaryOut(BaseModel):
    """风评聚合输出（第十三节）：不输出绝对化判断，逐主题给出正/负来源数与证据等级。"""

    topics: list[dict] = []
    overall_note: str = ""
    confidence: Literal["low", "medium", "high"] = "low"

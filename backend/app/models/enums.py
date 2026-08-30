"""枚举常量。数据库列统一存字符串（便于迁移），枚举用于取值约束。

Phase 2.1 领域模型加固：
- JobDisposition 只承担岗位信息筛选状态；求职流程状态由 ApplicationStatus 唯一负责。
- PositionNature 降级为 legacy / 派生展示字段，不再作为高校聘用事实的唯一来源；
  事实由 AcademicJobDetails 的四根正交轴（establishment/tenure/contract/funding）表达。
"""

from enum import StrEnum


class JobCategory(StrEnum):
    university_faculty = "university_faculty"    # 高校教学科研岗
    university_research = "university_research"  # 高校专职科研岗
    postdoc = "postdoc"                          # 博士后
    research_institute = "research_institute"    # 科研院所
    industry_rnd = "industry_rnd"                # 企业研发
    other = "other"


class PositionNature(StrEnum):
    """DEPRECATED（legacy / 派生展示字段）：单一枚举无法表达
    "无事业编 + 预聘副教授 + 固定期限合同 + 学校经费" 这类组合事实。
    保留仅为兼容旧数据读取与 UI 展示；新事实写入 AcademicJobDetails。"""

    permanent = "permanent"
    tenure = "tenure"
    tenure_track = "tenure_track"
    pre_tenure = "pre_tenure"
    fixed_term = "fixed_term"
    postdoc = "postdoc"
    pi_funded = "pi_funded"
    unknown = "unknown"  # 公告未说明时必须为 unknown，不得猜测


class EstablishmentStatus(StrEnum):
    """是否事业编。事业编 ≠ 长聘，是独立维度。"""

    established = "established"
    non_established = "non_established"
    unknown = "unknown"


class TenureStatus(StrEnum):
    """长聘体系状态。"""

    tenured = "tenured"
    tenure_track = "tenure_track"
    non_tenure = "non_tenure"
    unknown = "unknown"


class ContractType(StrEnum):
    """合同期限类型。可与 tenure_track 并存（预聘 + 固定期限合同）。"""

    open_ended = "open_ended"
    fixed_term = "fixed_term"
    unknown = "unknown"


class FundingSource(StrEnum):
    """聘用经费来源。"""

    university = "university"
    department = "department"
    pi = "pi"
    external = "external"
    mixed = "mixed"
    unknown = "unknown"


class JobDisposition(StrEnum):
    """岗位信息筛选状态（Job.status）。求职流程（准备投递/已投递/面试/Offer）
    属于 Application.status，不再出现在 Job 上。"""

    new = "new"
    reviewing = "reviewing"
    shortlisted = "shortlisted"
    ignored = "ignored"
    closed = "closed"


class RecommendationLevel(StrEnum):
    S = "S"  # 强烈建议重点关注
    A = "A"  # 值得认真申请
    B = "B"  # 可以申请
    C = "C"  # 作为备选
    D = "D"  # 优先级较低
    X = "X"  # 触发硬性排除条件


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ConfidenceLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class EvidenceLevel(StrEnum):
    A = "A"  # 正式公告/官方文件/合同条款
    B = "B"  # 多个相互独立的在职/离职人员公开陈述
    C = "C"  # 知乎/小红书/脉脉/论坛等单个或少量帖子
    D = "D"  # 无法确认来源的转述


class Stance(StrEnum):
    """证据对该主张的立场。"""

    positive = "positive"
    negative = "negative"
    mixed = "mixed"
    neutral = "neutral"
    unknown = "unknown"


class EvidenceScope(StrEnum):
    """风评作用域：学校风评和院系风评可能完全不同。"""

    organization = "organization"
    department = "department"
    lab = "lab"
    job = "job"
    unknown = "unknown"


class ApplicationStatus(StrEnum):
    new = "new"
    reviewed = "reviewed"
    shortlist = "shortlist"
    contacting = "contacting"
    preparing = "preparing"
    applied = "applied"
    written_test = "written_test"
    interview_1 = "interview_1"
    interview_2 = "interview_2"
    hr = "hr"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"
    ignored = "ignored"


# 申请状态合法流转表（正向推进 + 终止态不再流转）
APPLICATION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new": {"reviewed", "shortlist", "ignored"},
    "reviewed": {"shortlist", "contacting", "preparing", "rejected", "ignored"},
    "shortlist": {"contacting", "preparing", "rejected", "withdrawn", "ignored"},
    "contacting": {"preparing", "applied", "rejected", "withdrawn"},
    "preparing": {"applied", "withdrawn", "rejected", "ignored"},
    "applied": {"written_test", "interview_1", "hr", "offer", "rejected", "withdrawn"},
    "written_test": {"interview_1", "hr", "offer", "rejected", "withdrawn"},
    "interview_1": {"interview_2", "hr", "offer", "rejected", "withdrawn"},
    "interview_2": {"hr", "offer", "rejected", "withdrawn"},
    "hr": {"offer", "rejected", "withdrawn"},
    "offer": {"withdrawn"},
    "rejected": set(),
    "withdrawn": set(),
    "ignored": set(),
}


def can_transition_application(old: str, new: str) -> bool:
    if old == new:
        return True
    return new in APPLICATION_STATUS_TRANSITIONS.get(old, set())

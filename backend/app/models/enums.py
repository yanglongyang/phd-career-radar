"""枚举常量。数据库列统一存字符串（便于迁移），枚举用于取值约束。"""

from enum import StrEnum


class JobCategory(StrEnum):
    university_faculty = "university_faculty"    # 高校教学科研岗
    university_research = "university_research"  # 高校专职科研岗
    postdoc = "postdoc"                          # 博士后
    research_institute = "research_institute"    # 科研院所
    industry_rnd = "industry_rnd"                # 企业研发
    other = "other"


class PositionNature(StrEnum):
    permanent = "permanent"        # 事业编/长聘
    tenure = "tenure"              # 长聘
    tenure_track = "tenure_track"  # 预聘/非升即走
    pre_tenure = "pre_tenure"      # 预聘期内
    fixed_term = "fixed_term"      # 合同制
    postdoc = "postdoc"
    pi_funded = "pi_funded"        # PI 经费聘用
    unknown = "unknown"            # 公告未说明时必须为 unknown，不得猜测


class JobStatus(StrEnum):
    new = "new"
    reviewing = "reviewing"
    shortlisted = "shortlisted"
    preparing = "preparing"
    applied = "applied"
    interviewing = "interviewing"
    offer = "offer"
    closed = "closed"
    ignored = "ignored"


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


# 申请状态合法流转表（正向推进 + 任意终止态可回到部分状态）
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

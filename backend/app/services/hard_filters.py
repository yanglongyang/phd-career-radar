"""Hard Filters：用户配置的硬性排除条件，触发时推荐等级置为 X。
偏好一律来自 config/profile.yaml，代码不替用户做决定。
不确定的信息（如薪资未知/单位不明）不触发过滤，只会进入 unknowns —— 不得猜单位。

minimum_salary 的口径为 CNY 万元/年：仅当岗位具备 guaranteed_salary_max
且 salary_currency=CNY、salary_period=year 时才可比较；
广告口径总包（advertised/legacy salary_max）含绩效，不用于硬性过滤。

Phase 2.1.1：legacy position_nature 不再参与任何过滤判断 ——
PI 经费判定只看 AcademicJobDetails.funding_source；
reject_high_risk_tenure_track 在评估时具备完整条件后真正执行
（tenure_status=tenure_track 且有效风险达到 high/critical）。
"""

from __future__ import annotations

from app.core.config import get_profile_config
from app.core.fingerprint import normalize_text


def check_hard_filters(job, profile: dict | None = None, risk_level: str | None = None) -> list[str]:
    profile = profile if profile is not None else get_profile_config()
    hf = profile.get("hard_filters") or {}
    triggered: list[str] = []

    regions = {normalize_text(r) for r in (hf.get("unacceptable_regions") or [])}
    if regions:
        for loc in (job.city, job.province):
            if loc and normalize_text(loc) in regions:
                triggered.append("unacceptable_regions")
                break

    triggered.extend(_salary_filter_hits(job, hf))

    details = getattr(job, "academic_details", None)

    if hf.get("reject_pi_funded") and details is not None and details.funding_source == "pi":
        triggered.append("reject_pi_funded")

    if hf.get("reject_postdoc") and job.job_category == "postdoc":
        triggered.append("reject_postdoc")

    if hf.get("reject_high_risk_tenure_track") and _is_high_risk_tenure_track(details, risk_level):
        triggered.append("reject_high_risk_tenure_track")

    return triggered


def _is_high_risk_tenure_track(details, risk_level: str | None) -> bool:
    return (
        risk_level in ("high", "critical")
        and details is not None
        and details.tenure_status == "tenure_track"
    )


def _salary_filter_hits(job, hf: dict) -> list[str]:
    minimum_salary = hf.get("minimum_salary")
    if minimum_salary is None:
        return []
    # 单位不明确（currency/period 缺失或非 CNY 年薪）→ 不触发，进入 unknowns
    if job.salary_currency != "CNY" or job.salary_period != "year":
        return []
    guaranteed_max = job.guaranteed_salary_max
    if guaranteed_max is None:
        return []
    if guaranteed_max < float(minimum_salary):
        return ["minimum_salary"]
    return []

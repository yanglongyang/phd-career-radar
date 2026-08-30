"""Hard Filters：用户配置的硬性排除条件，触发时推荐等级置为 X。
偏好一律来自 config/profile.yaml，代码不替用户做决定。
不确定的信息（如薪资未知）不触发过滤，只会进入 unknowns。"""

from __future__ import annotations

from app.core.config import get_profile_config
from app.core.fingerprint import normalize_text


def check_hard_filters(job, profile: dict | None = None) -> list[str]:
    profile = profile if profile is not None else get_profile_config()
    hf = profile.get("hard_filters") or {}
    triggered: list[str] = []

    regions = {normalize_text(r) for r in (hf.get("unacceptable_regions") or [])}
    if regions:
        for loc in (job.city, job.province):
            if loc and normalize_text(loc) in regions:
                triggered.append("unacceptable_regions")
                break

    min_salary = hf.get("minimum_salary")
    if min_salary is not None and job.salary_max is not None and job.salary_max < float(min_salary):
        triggered.append("minimum_salary")

    if hf.get("reject_pi_funded") and job.position_nature == "pi_funded":
        triggered.append("reject_pi_funded")

    if hf.get("reject_postdoc") and (job.job_category == "postdoc" or job.position_nature == "postdoc"):
        triggered.append("reject_postdoc")

    # reject_high_risk_tenure_track 依赖 AI 风险评估结果，在 Phase 4 评估流程中判定
    return triggered

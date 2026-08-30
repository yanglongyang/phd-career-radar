"""地区服务：城市/省份 → 偏好层级 → 基准分。层级归属全部来自 regions.yaml，代码不预置城市。

Phase 2.1 语义修正：neutral（用户明确表示中立）与 unrated（用户没有评价过）分开。
未配置的城市/省份 → tier=unrated，score=None；不自动给 50 分替用户猜测偏好。
"""

from __future__ import annotations

from app.core.config import get_regions_config, get_scoring_config
from app.core.fingerprint import normalize_text

_TIERS = ("preferred", "acceptable", "neutral", "avoid")
UNRATED = "unrated"


def get_region_tier(province: str | None, city: str | None, cfg: dict | None = None) -> str:
    cfg = cfg if cfg is not None else get_regions_config()
    for tier in _TIERS:
        names = {normalize_text(n) for n in (cfg.get(tier) or [])}
        if city and normalize_text(city) in names:
            return tier
        if province and normalize_text(province) in names:
            return tier
    return UNRATED


def get_region_score(
    province: str | None, city: str | None, cfg: dict | None = None
) -> float | None:
    """地区基准分（0-100）。城市/省份均未提供，或层级为 unrated 时返回 None。"""
    if not province and not city:
        return None
    tier = get_region_tier(province, city, cfg)
    if tier == UNRATED:
        return None
    scores = get_scoring_config().get("region_tier_scores") or {}
    return float(scores.get(tier, 50))

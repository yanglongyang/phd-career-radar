"""地区服务：城市/省份 → 偏好层级 → 基准分。层级归属全部来自 regions.yaml，代码不预置城市。"""

from __future__ import annotations

from app.core.config import get_regions_config, get_scoring_config
from app.core.fingerprint import normalize_text

_TIERS = ("preferred", "acceptable", "neutral", "avoid")


def get_region_tier(province: str | None, city: str | None, cfg: dict | None = None) -> str:
    cfg = cfg if cfg is not None else get_regions_config()
    for tier in _TIERS:
        names = {normalize_text(n) for n in (cfg.get(tier) or [])}
        if city and normalize_text(city) in names:
            return tier
        if province and normalize_text(province) in names:
            return tier
    return "unknown"


def get_region_score(province: str | None, city: str | None) -> float | None:
    """地区基准分（0-100）。城市/省份均未提供时返回 None。"""
    if not province and not city:
        return None
    tier = get_region_tier(province, city)
    scores = get_scoring_config().get("region_tier_scores") or {}
    return float(scores.get(tier, 50))

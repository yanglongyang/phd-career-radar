"""评分服务：加权总分、推荐等级（考虑硬性过滤/风险/可信度封顶）。"""

from app.core.config import get_scoring_config

LEVEL_ORDER = ["D", "C", "B", "A", "S"]


def _min_level(a: str, b: str) -> str:
    return a if LEVEL_ORDER.index(a) <= LEVEL_ORDER.index(b) else b


def compute_total(dimension_scores: dict[str, float | None], weights: dict[str, float] | None = None) -> float | None:
    """加权总分。信息不足的维度不参与计算并重新归一化权重 —— 不因信息缺失人为压分；
    信息缺失应反映在 confidence / unknowns。全部维度缺失时返回 None。"""
    weights = weights or get_scoring_config().get("scoring", {})
    present = {k: float(v) for k, v in dimension_scores.items() if v is not None and k in weights}
    if not present:
        return None
    total_weight = sum(weights[k] for k in present)
    if total_weight <= 0:
        return None
    return round(sum(weights[k] * score for k, score in present.items()) / total_weight, 1)


def recommend_level(
    total_score: float | None,
    *,
    risk_level: str | None = None,
    confidence: str | None = None,
    hard_filter_hits: list[str] | None = None,
    cfg: dict | None = None,
) -> str | None:
    """推荐等级：先按总分阈值定档，再按风险/可信度封顶；触发硬性过滤直接 X。
    total_score 为 None（完全无法评分）时不给出推荐等级。"""
    cfg = cfg if cfg is not None else get_scoring_config().get("recommendation", {})
    if hard_filter_hits:
        return "X"
    if total_score is None:
        return None

    thresholds = cfg.get("thresholds") or {"S": 85, "A": 75, "B": 65, "C": 50}
    level = "D"
    for lv in ("S", "A", "B", "C"):
        if total_score >= thresholds.get(lv, 0):
            level = lv
            break

    risk_cap = (cfg.get("risk_cap") or {}).get(risk_level or "")
    if risk_cap:
        level = _min_level(level, risk_cap)

    confidence_cap = (cfg.get("confidence_cap") or {}).get(confidence or "")
    if confidence_cap:
        level = _min_level(level, confidence_cap)

    return level

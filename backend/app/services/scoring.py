"""评分服务（Phase 2.1 语义修正）。

- compute_total 产生的是 **provisional weighted score**：缺失维度不参与权重并对
  剩余权重重新归一化 —— 它不是"完整信息条件下的确定总分"，必须与
  score_coverage 一起展示。
- compute_coverage：已评分维度的权重之和 / 全部配置权重之和 × 100。
- recommend_level：最终推荐等级的唯一权威来源是本规则引擎（AI 不输出等级）。
  只考虑 provisional score、risk cap、hard filters；confidence 不默认封顶
  （信息不足 ≠ 岗位价值低，置信度独立展示）。
"""

from app.core.config import get_scoring_config

LEVEL_ORDER = ["D", "C", "B", "A", "S"]


def _min_level(a: str, b: str) -> str:
    return a if LEVEL_ORDER.index(a) <= LEVEL_ORDER.index(b) else b


def compute_total(
    dimension_scores: dict[str, float | None], weights: dict[str, float] | None = None
) -> float | None:
    """Provisional weighted score：信息不足的维度不参与计算并重新归一化权重 ——
    不因信息缺失人为压分；信息缺失应反映在 score_coverage / unknowns / confidence。
    全部维度缺失时返回 None。"""
    weights = weights or get_scoring_config().get("scoring", {})
    present = {k: float(v) for k, v in dimension_scores.items() if v is not None and k in weights}
    if not present:
        return None
    total_weight = sum(weights[k] for k in present)
    if total_weight <= 0:
        return None
    return round(sum(weights[k] * score for k, score in present.items()) / total_weight, 1)


def compute_coverage(
    dimension_scores: dict[str, float | None], weights: dict[str, float] | None = None
) -> float:
    """评分覆盖度（0-100）：已有有效评分维度的权重之和 / 所有配置权重之和 × 100。
    用于识别"高分但信息很少"的虚假精度，例如只评了 fit=95 时 coverage 只有 20。"""
    weights = weights or get_scoring_config().get("scoring", {})
    if not weights:
        return 0.0
    present_weight = sum(
        weights[k] for k, v in dimension_scores.items() if v is not None and k in weights
    )
    return round(present_weight / sum(weights.values()) * 100, 1)


def recommend_level(
    total_score: float | None,
    *,
    risk_level: str | None = None,
    confidence: str | None = None,
    hard_filter_hits: list[str] | None = None,
    cfg: dict | None = None,
) -> str | None:
    """推荐等级：先按总分阈值定档，再按风险封顶；触发硬性过滤直接 X。
    confidence 仅当配置显式提供 confidence_cap 时才封顶（V0.1 默认关闭：
    信息不足影响"这个判断有多可信"，不影响岗位价值判断）。
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

    # V0.1 默认 confidence_cap 为空 dict —— 信息不足不降级
    confidence_cap = (cfg.get("confidence_cap") or {}).get(confidence or "")
    if confidence_cap:
        level = _min_level(level, confidence_cap)

    return level

"""评估规则引擎（Phase 2.1/2.1.1，Phase 4 接入用）。

职责划分（唯一权威来源）：
- AI 输出：维度分数、risk_level/risk_items、unknowns、confidence —— 事实判断。
- 本模块（deterministic backend）：effective risk、total_score(provisional)、
  score_coverage、hard_filters、recommendation_level —— 最终等级只能由这里计算。

Phase 2.1.1 一致性强约束：
- effective_risk = max(AI 声明 risk_level, 各 risk_items.severity)，防止
  "条目 critical 但 overall medium" 绕过封顶；推荐等级使用 effective_risk。
- risk_items.evidence_ids ⊆ 本次 evaluation evidence_ids ⊆ 数据库真实存在的
  Evidence。任何引用脱离本次评估的证据 → 拒绝保存，保证结论可追溯。
- input_snapshot 为必填：任何 AI 评估必须保存完整输入快照，否则无法复现。

本模块不发起任何 AI 调用；真实的 "调 AI → 校验 → finalize" 流程在 Phase 4 实现。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.schemas import JobEvaluationOut as AIEvaluationOut
from app.core.config import get_profile_config, get_regions_config, get_scoring_config
from app.core.hash import stable_json_hash
from app.models import Evidence, Job, JobEvaluation
from app.models.evaluation_evidence import EvaluationEvidence
from app.services.hard_filters import check_hard_filters
from app.services.scoring import compute_coverage, compute_total, recommend_level

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def compute_effective_risk(ai_output: AIEvaluationOut) -> str:
    """整体风险等级由 backend 派生：max(AI 声明 risk_level, 各 risk_items.severity)。"""
    level = ai_output.risk_level
    for item in ai_output.risk_items:
        if SEVERITY_ORDER.get(item.severity, 0) > SEVERITY_ORDER.get(level, 0):
            level = item.severity
    return level


def config_snapshots(profile: dict | None = None) -> dict:
    """当前生效配置的快照与哈希，用于评估审计。profile 允许调用方注入（测试/批量重评）。"""
    profile_cfg = profile if profile is not None else get_profile_config()
    scoring = get_scoring_config()
    regions = get_regions_config()
    return {
        "profile": profile_cfg,
        "profile_hash": stable_json_hash(profile_cfg),
        "scoring_config": scoring,
        "scoring_config_hash": stable_json_hash(scoring),
        "region_config": regions,
        "region_config_hash": stable_json_hash(regions),
    }


def finalize_evaluation(
    db: Session,
    job: Job,
    *,
    ai_output: AIEvaluationOut,
    dimension_scores: dict[str, float | None],
    evidence_ids: list[int] | None = None,
    input_snapshot: dict,
    profile: dict | None = None,
    provider_name: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    evaluation_version: str = "v1",
) -> JobEvaluation:
    """把 AI 的结构化判断与后端规则引擎的派生结果合成为一条可审计的评估记录。

    dimension_scores 由调用方合成（AI 维度分 + 地区基准分等），本函数只做
    确定性计算与持久化。任何一致性校验失败都会抛错拒绝保存，不静默降级。
    """
    provided_ids = list(dict.fromkeys(evidence_ids or []))
    _validate_evidence_consistency(db, provided_ids, ai_output)

    snapshots = config_snapshots(profile)
    effective_risk = compute_effective_risk(ai_output)
    hard_filter_hits = check_hard_filters(job, profile=profile, risk_level=effective_risk)
    total = compute_total(dimension_scores)
    coverage = compute_coverage(dimension_scores)
    recommendation = recommend_level(
        total,
        risk_level=effective_risk,
        confidence=ai_output.confidence,
        hard_filter_hits=hard_filter_hits,
    )

    evaluation = JobEvaluation(
        job_id=job.id,
        total_score=total,
        score_coverage=coverage,
        fit_score=dimension_scores.get("fit"),
        career_stability_score=dimension_scores.get("career_stability"),
        research_resources_score=dimension_scores.get("research_resources"),
        region_score=dimension_scores.get("region"),
        compensation_score=dimension_scores.get("compensation"),
        reputation_score=dimension_scores.get("reputation"),
        workload_score=dimension_scores.get("workload"),
        long_term_score=dimension_scores.get("long_term"),
        recommendation_level=recommendation,
        risk_level=effective_risk,  # backend 派生的有效风险，非 AI 原始声明
        confidence_level=ai_output.confidence,
        summary=ai_output.summary or None,
        strengths_json=list(ai_output.strengths),
        weaknesses_json=list(ai_output.weaknesses),
        risks_json=list(ai_output.risks),
        risk_items_json=[item.model_dump() for item in ai_output.risk_items],
        unknowns_json=list(ai_output.unknowns),
        questions_json=list(ai_output.questions_to_ask),
        hard_filters_json=hard_filter_hits,
        provider=provider_name,
        model=model,
        prompt_version=prompt_version,
        evaluation_version=evaluation_version,
        profile_snapshot_json=snapshots["profile"],
        profile_hash=snapshots["profile_hash"],
        scoring_config_snapshot_json=snapshots["scoring_config"],
        scoring_config_hash=snapshots["scoring_config_hash"],
        region_config_snapshot_json=snapshots["region_config"],
        region_config_hash=snapshots["region_config_hash"],
        input_snapshot_json=input_snapshot,
    )
    db.add(evaluation)
    db.flush()

    for evidence_id in provided_ids:
        db.add(EvaluationEvidence(evaluation_id=evaluation.id, evidence_id=evidence_id))
    db.flush()
    return evaluation


def _validate_evidence_consistency(
    db: Session, provided_ids: list[int], ai_output: AIEvaluationOut
) -> None:
    """risk_items.evidence_ids ⊆ 本次 evaluation evidence_ids ⊆ 真实存在的 Evidence。"""
    if provided_ids:
        existing = set(
            db.scalars(select(Evidence.id).where(Evidence.id.in_(provided_ids)))
        )
        missing = set(provided_ids) - existing
        if missing:
            raise ValueError(
                f"evidence_ids 引用了不存在的证据: {sorted(missing)}，拒绝保存评估"
            )

    for item in ai_output.risk_items:
        unprovided = [eid for eid in item.evidence_ids if eid not in provided_ids]
        if unprovided:
            raise ValueError(
                f"风险条目 '{item.type}' 引用了未提供给本次评估的证据 {unprovided}；"
                "结论必须能追溯到本次评估实际使用的 Evidence，拒绝保存"
            )

"""评估规则引擎（Phase 2.1，Phase 4 接入用）。

职责划分（唯一权威来源）：
- AI 输出：维度分数、risk_level/risk_items、unknowns、confidence —— 事实判断。
- 本模块（deterministic backend）：total_score(provisional)、score_coverage、
  hard_filters、recommendation_level —— 最终等级只能由这里计算，换模型不漂移。

本模块不发起任何 AI 调用；真实的 "调 AI → 校验 → finalize" 流程在 Phase 4 实现。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.schemas import JobEvaluationOut as AIEvaluationOut
from app.core.config import get_profile_config, get_regions_config, get_scoring_config
from app.core.hash import stable_json_hash
from app.models import Evidence, Job, JobEvaluation
from app.models.evaluation_evidence import EvaluationEvidence
from app.services.hard_filters import check_hard_filters
from app.services.scoring import compute_coverage, compute_total, recommend_level


def config_snapshots() -> dict:
    """当前生效配置的快照与哈希，用于评估审计。"""
    profile = get_profile_config()
    scoring = get_scoring_config()
    regions = get_regions_config()
    return {
        "profile": profile,
        "profile_hash": stable_json_hash(profile),
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
    input_snapshot: dict | None = None,
    provider_name: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    evaluation_version: str = "v1",
) -> JobEvaluation:
    """把 AI 的结构化判断与后端规则引擎的派生结果合成为一条可审计的评估记录。

    dimension_scores 由调用方合成（AI 维度分 + 地区基准分等），本函数只做
    确定性计算与持久化。"""
    snapshots = config_snapshots()
    hard_filter_hits = check_hard_filters(job)
    total = compute_total(dimension_scores)
    coverage = compute_coverage(dimension_scores)
    recommendation = recommend_level(
        total,
        risk_level=ai_output.risk_level,
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
        risk_level=ai_output.risk_level,
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

    for evidence_id in evidence_ids or []:
        if db.get(Evidence, evidence_id) is not None:
            db.add(EvaluationEvidence(evaluation_id=evaluation.id, evidence_id=evidence_id))
    db.flush()
    return evaluation

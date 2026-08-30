"""AI 岗位评估编排（Phase 4 / 4.1）。

流程与权责：
1. `build_evaluation_context()`：由后端自动构造真实 AI 输入（profile/job/region/
   evidence/hard_filters 五键）—— 同一份 dict 既发给模型、又原样存入
   input_snapshot，保证"数据库里保存的和模型实际看到的是同一份东西"。
   - job 含 organization 与 JD 正文（description_raw/clean），fit 等维度有真实依据；
   - evidence 按 scope 严格分层过滤（job / organization / department / lab），
     同校不同学院、同校其他岗位的证据不会串入。
2. `evaluate_job()`：调 provider（Pydantic 校验 + 失败重试一次）→ 确定性合成
   dimension_scores → `finalize_evaluation()` 落库。
   - region 分数只由用户配置决定（unrated → null），AI 不得覆盖；
   - 无可用 Evidence 时强制 reputation=null，不靠 Prompt 自觉。
3. `finalize_evaluation()`（deterministic backend）：effective risk、
   total_score(provisional)、score_coverage、hard_filters、recommendation_level
   —— 最终等级只能由这里计算。

本模块不直接发 HTTP；Provider 由调用方注入，测试可注入 FakeProvider。
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.provider import LLMProvider
from app.ai.schemas import JobEvaluationOut as AIEvaluationOut
from app.core.config import get_profile_config, get_regions_config, get_scoring_config
from app.core.fingerprint import normalize_text
from app.core.hash import stable_json_hash
from app.models import Evidence, Job, JobEvaluation  # noqa: F401
from app.models.evaluation_evidence import EvaluationEvidence
from app.services.hard_filters import check_hard_filters
from app.services.regions import get_region_score, get_region_tier
from app.services.scoring import compute_coverage, compute_total, recommend_level

SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}

REQUIRED_SNAPSHOT_KEYS = {"profile", "job", "region", "evidence", "hard_filters"}


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


def evidence_in_scope(job: Job, evidence: Evidence) -> bool:
    """Evidence 作用域分层规则（Phase 4.1 P0-2）。

    - 明确绑定当前岗位（job_id 匹配）→ 纳入，无论 scope 标注是什么；
    - 绑定了其他岗位 → 即使单位相同也不复用（job_id 优先于 organization_id）；
    - 只挂单位的证据按 scope_level 分层：
      * organization / unknown → 纳入（单位级通用风评；unknown 不猜具体院系）
      * department → 仅当 scope_name 归一化后等于当前岗位的院系
      * lab → 不纳入（Job 没有实验室身份，不猜归属）
    """
    if evidence.job_id == job.id:
        return True
    if evidence.job_id is not None:
        return False  # 绑定其他岗位
    if job.organization_id is None or evidence.organization_id != job.organization_id:
        return False
    if evidence.scope_level in ("organization", "unknown"):
        return True
    if evidence.scope_level == "department":
        return normalize_text(evidence.scope_name) == normalize_text(job.department or "")
    return False  # lab 及未知层级且无岗位绑定的，一律不猜


def _job_context_dict(job: Job) -> dict:
    """岗位结构化信息（含单位、JD 正文与高校四轴事实）→ AI 可读 dict。"""
    org = job.organization
    details = job.academic_details
    academic = {}
    if details is not None:
        academic = {
            "establishment_status": details.establishment_status,
            "tenure_status": details.tenure_status,
            "contract_type": details.contract_type,
            "funding_source": details.funding_source,
            "contract_years": details.contract_years,
            "is_up_or_out": details.is_up_or_out,
            "midterm_review": details.midterm_review,
            "final_review": details.final_review,
            "publication_requirements": details.publication_requirements,
            "grant_requirements": details.grant_requirements,
            "teaching_requirements": details.teaching_requirements,
            "admin_requirements": details.admin_requirements,
            "current_title": details.current_title,
            "promotion_path": details.promotion_path,
            "independent_pi": details.independent_pi,
            "lab_space": details.lab_space,
            "startup_funding": details.startup_funding,
            "startup_funding_terms": details.startup_funding_terms,
            "can_supervise_master": details.can_supervise_master,
            "can_supervise_phd": details.can_supervise_phd,
            "master_quota": details.master_quota,
            "phd_quota": details.phd_quota,
            "fixed_income": details.fixed_income,
            "performance_income": details.performance_income,
            "housing_settlement": details.housing_settlement,
            "housing_subsidy": details.housing_subsidy,
            "talent_housing": details.talent_housing,
            "regional_talent_subsidy": details.regional_talent_subsidy,
        }
    return {
        "title": job.title,
        "organization": (
            {"id": org.id, "name": org.name, "organization_type": org.organization_type}
            if org
            else None
        ),
        "department": job.department,
        # JD 正文是 fit / research_resources / long_term 维度的核心输入
        "description_raw": job.description_raw,
        "description_clean": job.description_clean,
        "source_url": job.source_url,
        "job_category": job.job_category,
        "country": job.country,
        "province": job.province,
        "city": job.city,
        "employment_type": job.employment_type,
        "degree_requirement": job.degree_requirement,
        "experience_requirement": job.experience_requirement,
        "salary_text": job.salary_text,
        "salary_currency": job.salary_currency,
        "salary_period": job.salary_period,
        "guaranteed_salary_min": job.guaranteed_salary_min,
        "guaranteed_salary_max": job.guaranteed_salary_max,
        "variable_salary_min": job.variable_salary_min,
        "variable_salary_max": job.variable_salary_max,
        "advertised_total_min": job.advertised_total_min,
        "advertised_total_max": job.advertised_total_max,
        "deadline": str(job.deadline) if job.deadline else None,
        "academic_details": academic or None,
    }


def build_evaluation_context(db: Session, job: Job, profile: dict | None = None) -> dict:
    """构造真实 AI 输入。返回的 dict 同时作为 user message 与 input_snapshot。"""
    profile_cfg = profile if profile is not None else get_profile_config()

    # 候选集放宽到岗位 + 单位，scope 分层在 Python 里精确过滤（Phase 4.1）；
    # 按 id 排序保证 snapshot 输入稳定（真正的 Evidence selection/ranking 属 Phase 6）。
    if job.organization_id is not None:
        candidates = db.scalars(
            select(Evidence)
            .where(
                or_(
                    Evidence.job_id == job.id,
                    Evidence.organization_id == job.organization_id,
                )
            )
            .order_by(Evidence.id)
        ).all()
    else:
        candidates = db.scalars(
            select(Evidence).where(Evidence.job_id == job.id).order_by(Evidence.id)
        ).all()
    evidence_list = [
        {
            "id": ev.id,
            "claim": ev.claim,
            "category": ev.category,
            "evidence_level": ev.evidence_level,
            "stance": ev.stance,
            "scope_level": ev.scope_level,
            "scope_name": ev.scope_name,
            "is_firsthand": ev.is_firsthand,
            "independence_key": ev.independence_key,
            "source_type": ev.source_type,
            "source_author": ev.source_author,
            "published_at": str(ev.published_at) if ev.published_at else None,
        }
        for ev in candidates
        if evidence_in_scope(job, ev)
    ]

    tier = get_region_tier(job.province, job.city)
    return {
        "profile": profile_cfg,
        "job": _job_context_dict(job),
        "region": {
            "tier": tier,
            "score": get_region_score(job.province, job.city),
            "note": "score 为用户地区偏好基准分；unrated 表示用户未评价该地区",
        },
        "evidence": evidence_list,
        "hard_filters": profile_cfg.get("hard_filters") or {},
    }


def validate_input_snapshot(snapshot: object) -> None:
    """审计强约束：input_snapshot 必须是非空 dict 且包含全部五键（值可为空集合）。"""
    if not isinstance(snapshot, dict) or not snapshot:
        raise ValueError("input_snapshot 必须是非空 dict，拒绝保存评估")
    missing = REQUIRED_SNAPSHOT_KEYS - set(snapshot)
    if missing:
        raise ValueError(f"input_snapshot 缺少键: {sorted(missing)}，拒绝保存评估")


def _validate_evidence_consistency(
    db: Session, job: Job, provided_ids: list[int], ai_output: AIEvaluationOut
) -> None:
    """risk_items.evidence_ids ⊆ 本次 evaluation evidence_ids ⊆ 作用域内的真实 Evidence。"""
    if provided_ids:
        rows = db.scalars(select(Evidence).where(Evidence.id.in_(provided_ids))).all()
        found = {ev.id for ev in rows}
        missing = set(provided_ids) - found
        if missing:
            raise ValueError(
                f"evidence_ids 引用了不存在的证据: {sorted(missing)}，拒绝保存评估"
            )
        for ev in rows:
            if not evidence_in_scope(job, ev):
                raise ValueError(
                    f"Evidence #{ev.id} 不属于当前岗位/单位/院系作用域，拒绝用于本次评估"
                )
    for item in ai_output.risk_items:
        unprovided = [eid for eid in item.evidence_ids if eid not in provided_ids]
        if unprovided:
            raise ValueError(
                f"风险条目 '{item.type}' 引用了未提供给本次评估的证据 {unprovided}；"
                "结论必须能追溯到本次评估实际使用的 Evidence，拒绝保存"
            )


def evaluate_job(
    db: Session,
    job: Job,
    provider: LLMProvider,
    profile: dict | None = None,
) -> JobEvaluation:
    """完整评估编排：构造 context → 调 AI → 确定性合成 → finalize 落库。"""
    context = build_evaluation_context(db, job, profile)
    validate_input_snapshot(context)
    ai_output, prompt_version = provider.evaluate_job(context)

    # 维度分确定性合成（Phase 4.1）：
    # - region 只由用户配置决定（unrated → null），AI 不得覆盖；
    # - 无可用 Evidence 时强制 reputation=null，不靠 Prompt 自觉。
    scores = ai_output.scores.model_dump()
    scores.pop("region", None)
    if not context["evidence"]:
        scores["reputation"] = None
    dimension_scores = {**scores, "region": context["region"]["score"]}
    evidence_ids = [e["id"] for e in context["evidence"]]

    return finalize_evaluation(
        db,
        job,
        ai_output=ai_output,
        dimension_scores=dimension_scores,
        evidence_ids=evidence_ids,
        input_snapshot=context,
        profile=profile,
        provider_name=provider.name,
        model=getattr(provider, "model", None),
        prompt_version=prompt_version,
    )


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
    validate_input_snapshot(input_snapshot)
    provided_ids = list(dict.fromkeys(evidence_ids or []))
    _validate_evidence_consistency(db, job, provided_ids, ai_output)

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

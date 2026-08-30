import pytest
from sqlalchemy.exc import IntegrityError

from app.ai.schemas import JobEvaluationOut
from app.core.hash import stable_json_hash
from app.models import Evidence, Job, JobEvaluation
from app.services.evaluation import compute_effective_risk, finalize_evaluation

INPUT_SNAPSHOT = {"profile": {}, "job": {"title": "青年研究员"}, "evidence": []}


def _make_ai_output(risk_level="high", item_severity=None, item_evidence_ids=None) -> JobEvaluationOut:
    risk_items = []
    if item_severity is not None:
        risk_items.append(
            {
                "type": "up_or_out",
                "severity": item_severity,
                "reason": "预聘制，未找到官方考核文件",
                "evidence_ids": item_evidence_ids or [],
            }
        )
    return JobEvaluationOut.model_validate(
        {
            "summary": "岗位与研究方向高度相关，但预聘考核要求需要进一步核实。",
            "scores": {"fit": 90, "region": 80, "career_stability": None},
            "risk_level": risk_level,
            "risk_items": risk_items,
            "strengths": ["研究方向匹配"],
            "unknowns": ["首聘周期"],
            "questions_to_ask": ["未通过考核后的处理方式？"],
            "confidence": "medium",
        }
    )


def test_stable_json_hash_is_deterministic():
    a = {"profile": {"skills": ["NMR", "HPLC"]}, "city": "南京"}
    b = {"city": "南京", "profile": {"skills": ["NMR", "HPLC"]}}
    assert stable_json_hash(a) == stable_json_hash(b)
    assert stable_json_hash(a) != stable_json_hash({"city": "南京"})
    assert len(stable_json_hash(a)) == 64  # SHA-256 hex


def test_effective_risk_is_max_of_declared_and_items():
    """Phase 2.1.1 P0-3：overall 与条目 severity 矛盾时取更严者。"""
    assert compute_effective_risk(_make_ai_output(risk_level="medium")) == "medium"
    assert compute_effective_risk(_make_ai_output(risk_level="medium", item_severity="critical")) == "critical"
    assert compute_effective_risk(_make_ai_output(risk_level="critical", item_severity="low")) == "critical"


def test_finalize_computes_total_coverage_recommendation(client, sample_job, db_session):
    """fit(20) + region(15) 已评分 → coverage = 35；
    effective risk = max(high 声明, high 条目) = high → 85.7 阈值 S 被封顶到 C。"""
    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(risk_level="high", item_severity="high"),
        dimension_scores={"fit": 90, "region": 80, "career_stability": None},
        input_snapshot=INPUT_SNAPSHOT,
        provider_name="openai_compatible",
        model="test-model",
        prompt_version="job_evaluation_v1",
    )
    db_session.commit()
    assert evaluation.total_score == 85.7
    assert evaluation.score_coverage == 35.0
    assert evaluation.recommendation_level == "C"  # 85.7 本应是 S，有效风险 high 封顶 C
    assert evaluation.risk_level == "high"
    assert evaluation.risk_items_json[0]["type"] == "up_or_out"
    assert evaluation.provider == "openai_compatible"


def test_item_critical_cannot_hide_behind_medium_overall(client, sample_job, db_session):
    """条目 critical + overall medium → 有效风险 critical，S 被封顶到 D。"""
    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(risk_level="medium", item_severity="critical"),
        dimension_scores={"fit": 90},
        input_snapshot=INPUT_SNAPSHOT,
    )
    db_session.commit()
    assert evaluation.risk_level == "critical"
    assert evaluation.recommendation_level == "D"


def test_finalize_stores_config_snapshots(client, sample_job, db_session):
    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(),
        dimension_scores={"fit": 90},
        input_snapshot=INPUT_SNAPSHOT,
    )
    db_session.commit()
    assert evaluation.profile_snapshot_json is not None
    assert evaluation.profile_hash == stable_json_hash(evaluation.profile_snapshot_json)
    assert evaluation.scoring_config_hash == stable_json_hash(evaluation.scoring_config_snapshot_json)
    assert evaluation.region_config_hash == stable_json_hash(evaluation.region_config_snapshot_json)
    assert evaluation.input_snapshot_json == INPUT_SNAPSHOT


def test_finalize_links_evidence(client, sample_job, db_session):
    """EvaluationEvidence 关联：评估能回答"当时用了哪些 Evidence"。"""
    from app.models import EvaluationEvidence

    evidence = Evidence(
        job_id=sample_job["id"],
        organization_id=sample_job["organization"]["id"],
        claim="该岗位为预聘制，聘期三年",
        category="fact",
        evidence_level="A",
        source_type="official",
    )
    db_session.add(evidence)
    db_session.commit()

    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(),
        dimension_scores={"fit": 90},
        input_snapshot=INPUT_SNAPSHOT,
        evidence_ids=[evidence.id],
    )
    db_session.commit()

    links = db_session.query(EvaluationEvidence).filter_by(evaluation_id=evaluation.id).all()
    assert len(links) == 1
    assert links[0].evidence_id == evidence.id
    # 同一评估重复关联同一证据会被唯一约束阻止
    db_session.add(EvaluationEvidence(evaluation_id=evaluation.id, evidence_id=evidence.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_finalize_rejects_risk_item_evidence_not_provided(client, sample_job, db_session):
    """Phase 2.1.1 P0-2：risk 条目引用了未提供给本次评估的证据 → 拒绝保存。"""
    with pytest.raises(ValueError, match="未提供给本次评估"):
        finalize_evaluation(
            db_session,
            db_session.get(Job, sample_job["id"]),
            ai_output=_make_ai_output(item_severity="high", item_evidence_ids=[1]),
            dimension_scores={"fit": 90},
            input_snapshot=INPUT_SNAPSHOT,
            evidence_ids=None,
        )
    assert db_session.query(JobEvaluation).count() == 0

    # 正常路径：引用的证据在 provided 集合内 → 通过
    evidence = Evidence(job_id=sample_job["id"], claim="预聘制聘期三年", evidence_level="A")
    db_session.add(evidence)
    db_session.commit()
    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(item_severity="high", item_evidence_ids=[evidence.id]),
        dimension_scores={"fit": 90},
        input_snapshot=INPUT_SNAPSHOT,
        evidence_ids=[evidence.id],
    )
    db_session.commit()
    assert evaluation.risk_items_json[0]["evidence_ids"] == [evidence.id]


def test_finalize_rejects_nonexistent_evidence(client, sample_job, db_session):
    """evidence_ids 引用数据库不存在的证据 → 拒绝保存。"""
    with pytest.raises(ValueError, match="不存在的证据"):
        finalize_evaluation(
            db_session,
            db_session.get(Job, sample_job["id"]),
            ai_output=_make_ai_output(),
            dimension_scores={"fit": 90},
            input_snapshot=INPUT_SNAPSHOT,
            evidence_ids=[999999],
        )
    assert db_session.query(JobEvaluation).count() == 0


def test_finalize_requires_input_snapshot(client, sample_job, db_session):
    """审计强约束：input_snapshot 必填，忘传直接报错而不是静默入库。"""
    with pytest.raises(TypeError):
        finalize_evaluation(
            db_session,
            db_session.get(Job, sample_job["id"]),
            ai_output=_make_ai_output(),
            dimension_scores={"fit": 90},
        )


def test_reject_high_risk_tenure_track_hard_filter(client, sample_job, db_session):
    """Phase 2.1.1：开关打开 + 预聘 + 有效风险 high → 推荐等级 X。"""
    client.patch(
        f"/api/jobs/{sample_job['id']}/academic-details",
        json={"tenure_status": "tenure_track"},
    )
    profile = {"hard_filters": {"reject_high_risk_tenure_track": True}}
    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(risk_level="high", item_severity="high"),
        dimension_scores={"fit": 90, "region": 80},
        input_snapshot=INPUT_SNAPSHOT,
        profile=profile,
    )
    db_session.commit()
    assert evaluation.hard_filters_json == ["reject_high_risk_tenure_track"]
    assert evaluation.recommendation_level == "X"
    # 审计快照记录的是本次评估实际使用的 profile（含被触发的开关）
    assert evaluation.profile_snapshot_json == profile


def test_evaluation_persists_via_db(client, sample_job, db_session):
    job = db_session.get(Job, sample_job["id"])
    finalize_evaluation(
        db_session, job, ai_output=_make_ai_output(),
        dimension_scores={"fit": 90}, input_snapshot=INPUT_SNAPSHOT,
    )
    db_session.commit()
    assert db_session.query(JobEvaluation).count() == 1
    evaluations = client.get(f"/api/jobs/{sample_job['id']}/evaluations").json()
    assert evaluations[0]["score_coverage"] == 20.0
    assert evaluations[0]["recommendation_level"] is not None  # 后端计算，非 AI 输出

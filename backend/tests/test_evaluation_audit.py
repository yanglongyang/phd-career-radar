import pytest
from sqlalchemy.exc import IntegrityError

from app.ai.schemas import JobEvaluationOut
from app.core.hash import stable_json_hash
from app.models import Evidence, Job, JobEvaluation
from app.services.evaluation import finalize_evaluation


def _make_ai_output() -> JobEvaluationOut:
    return JobEvaluationOut.model_validate(
        {
            "summary": "岗位与研究方向高度相关，但预聘考核要求需要进一步核实。",
            "scores": {"fit": 90, "region": 80, "career_stability": None},
            "risk_level": "high",
            "risk_items": [
                {"type": "up_or_out", "severity": "high", "reason": "预聘制，未找到官方考核文件", "evidence_ids": [1]}
            ],
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


def test_finalize_computes_total_coverage_recommendation(client, sample_job, db_session):
    """fit(20) + region(15) 已评分 → coverage = 35；
    risk=high 封顶：provisional (90*20+80*15)/35 = 85.7 → 阈值 S → 封顶 C。"""
    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(),
        dimension_scores={"fit": 90, "region": 80, "career_stability": None},
        provider_name="openai_compatible",
        model="test-model",
        prompt_version="job_evaluation_v1",
    )
    db_session.commit()
    assert evaluation.total_score == 85.7
    assert evaluation.score_coverage == 35.0
    assert evaluation.recommendation_level == "C"  # 85.7 本应是 S，高风险封顶 C
    assert evaluation.risk_level == "high"
    assert evaluation.risk_items_json[0]["type"] == "up_or_out"
    assert evaluation.provider == "openai_compatible"


def test_finalize_stores_config_snapshots(client, sample_job, db_session):
    evaluation = finalize_evaluation(
        db_session,
        db_session.get(Job, sample_job["id"]),
        ai_output=_make_ai_output(),
        dimension_scores={"fit": 90},
    )
    db_session.commit()
    assert evaluation.profile_snapshot_json is not None
    assert evaluation.profile_hash == stable_json_hash(evaluation.profile_snapshot_json)
    assert evaluation.scoring_config_hash == stable_json_hash(evaluation.scoring_config_snapshot_json)
    assert evaluation.region_config_hash == stable_json_hash(evaluation.region_config_snapshot_json)
    assert evaluation.input_snapshot_json is None


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


def test_evaluation_persists_via_db(client, sample_job, db_session):
    job = db_session.get(Job, sample_job["id"])
    finalize_evaluation(db_session, job, ai_output=_make_ai_output(), dimension_scores={"fit": 90})
    db_session.commit()
    assert db_session.query(JobEvaluation).count() == 1
    evaluations = client.get(f"/api/jobs/{sample_job['id']}/evaluations").json()
    assert evaluations[0]["score_coverage"] == 20.0
    assert evaluations[0]["recommendation_level"] is not None  # 后端计算，非 AI 输出

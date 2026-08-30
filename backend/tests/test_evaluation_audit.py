import pytest
from sqlalchemy.exc import IntegrityError

from app.ai.provider import LLMProvider
from app.ai.schemas import JobEvaluationOut
from app.ai.schemas import JobEvaluationOut as AIEvalOut
from app.core.hash import stable_json_hash
from app.models import Evidence, Job, JobEvaluation
from app.services.evaluation import (
    compute_effective_risk,
    evaluate_job,
    finalize_evaluation,
)

INPUT_SNAPSHOT = {
    "profile": {},
    "job": {"title": "青年研究员"},
    "region": {"tier": "unrated", "score": None},
    "evidence": [],
    "hard_filters": {},
}


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


def test_finalize_rejects_incomplete_snapshot(client, sample_job, db_session):
    """Phase 4 Step 0：input_snapshot 必须含五键（profile/job/region/evidence/hard_filters）。"""
    for bad in (
        {"profile": {}, "job": {}},  # 缺键
        {},  # 空
        "not-a-dict",  # 非法类型
    ):
        with pytest.raises(ValueError, match="input_snapshot"):
            finalize_evaluation(
                db_session,
                db_session.get(Job, sample_job["id"]),
                ai_output=_make_ai_output(),
                dimension_scores={"fit": 90},
                input_snapshot=bad,
            )
    assert db_session.query(JobEvaluation).count() == 0


def test_finalize_rejects_out_of_scope_evidence(client, sample_job, db_session):
    """Phase 4 Step 0：Evidence 必须属于当前岗位或其单位，跨岗位证据拒绝。"""
    other_job = client.post(
        "/api/jobs",
        json={"title": "别家岗位", "organization_name": "另一所大学",
              "description_raw": "另一个岗位的公告正文，用于作用域测试。"},
    ).json()
    foreign = Evidence(job_id=other_job["id"], claim="别家单位的证据", evidence_level="C")
    db_session.add(foreign)
    db_session.commit()
    with pytest.raises(ValueError, match="不属于当前岗位"):
        finalize_evaluation(
            db_session,
            db_session.get(Job, sample_job["id"]),
            ai_output=_make_ai_output(),
            dimension_scores={"fit": 90},
            input_snapshot=INPUT_SNAPSHOT,
            evidence_ids=[foreign.id],
        )


def test_region_dimension_falls_back_to_baseline(client, sample_job, db_session, monkeypatch):
    """AI 未给 region 分时，编排层用地区基准分合成（这里 mock 为 preferred 基准 90）。"""
    monkeypatch.setattr("app.services.evaluation.get_region_score", lambda p, c: 90.0)

    class _Provider(LLMProvider):
        name = "fake_region"
        model = "m"

        def evaluate_job(self, context: dict):
            return (
                AIEvalOut.model_validate(
                    {"summary": "", "scores": {"fit": 80, "region": None},
                     "risk_level": "medium", "confidence": "medium"}
                ),
                "job_evaluation_v1",
            )

        def extract_job(self, jd_text: str):
            raise NotImplementedError

        def summarize_reputation(self, evidence: list[dict]):
            raise NotImplementedError

    evaluation = evaluate_job(
        db_session, db_session.get(Job, sample_job["id"]), _Provider()
    )
    db_session.commit()
    assert evaluation.region_score == 90.0
    # fit(20) + region(15) → coverage 35；(80*20+90*15)/35 = 84.3
    assert evaluation.total_score == 84.3


def test_evaluate_job_full_flow(client, sample_job, db_session):
    """Phase 4 全链路：context 自动构造 → AI → finalize → 落库 → 审计完整。"""
    from app.ai.provider import LLMProvider
    from app.ai.schemas import JobEvaluationOut as AIEvalOut
    from app.services.evaluation import evaluate_job

    class FakeEvalProvider(LLMProvider):
        name = "fake_eval"
        model = "fake-model-4"

        def __init__(self):
            self.seen_contexts = []

        def evaluate_job(self, context: dict):
            self.seen_contexts.append(context)
            return (
                AIEvalOut.model_validate(
                    {
                        "summary": "岗位匹配度高，但预聘考核需要核实。",
                        "scores": {"fit": 90, "region": None, "career_stability": 70},
                        "risk_level": "medium",
                        "risk_items": [
                            {"type": "up_or_out", "severity": "high",
                             "reason": "预聘制考核文件缺失", "evidence_ids": []}
                        ],
                        "strengths": ["研究方向匹配"],
                        "unknowns": ["首聘周期"],
                        "questions_to_ask": ["考核未通过如何处理？"],
                        "confidence": "medium",
                    }
                ),
                "job_evaluation_v1",
            )

        def extract_job(self, jd_text: str):
            raise NotImplementedError

        def summarize_reputation(self, evidence: list[dict]):
            raise NotImplementedError

    provider = FakeEvalProvider()
    job = db_session.get(Job, sample_job["id"])
    evaluation = evaluate_job(db_session, job, provider)
    db_session.commit()

    # 同一份 context 发给模型并存为 input_snapshot
    assert provider.seen_contexts == [evaluation.input_snapshot_json]
    ctx = evaluation.input_snapshot_json
    for key in ("profile", "job", "region", "evidence", "hard_filters"):
        assert key in ctx
    assert ctx["job"]["title"] == sample_job["title"]
    # region 合成：AI null → 系统基准（regions.yaml 全空 → unrated → None）
    assert evaluation.region_score is None
    # fit(20)+career_stability(15) → coverage 35；(90*20+70*15)/35 = 81.4
    assert evaluation.total_score == 81.4
    assert evaluation.score_coverage == 35.0
    # effective risk = max(medium, item high) = high → 81.4 阈值 A 封顶 C
    assert evaluation.risk_level == "high"
    assert evaluation.recommendation_level == "C"

    # API 可读且审计字段完整
    data = client.get(f"/api/jobs/{sample_job['id']}/evaluations").json()[0]
    assert data["provider"] == "fake_eval"
    assert data["model"] == "fake-model-4"
    assert data["prompt_version"] == "job_evaluation_v1"
    assert data["profile_hash"]
    assert data["scoring_config_hash"]
    assert data["region_config_hash"]
    assert data["evidence_items"] == []  # 本岗位暂无 Evidence


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

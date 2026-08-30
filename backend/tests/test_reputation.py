"""Phase 6 / 6.1：Evidence CRUD 与风评聚合（确定性统计 + AI 叙述综合）测试。"""

import pytest

from app.ai.provider import LLMProvider
from app.ai.schemas import JobEvaluationOut as AIEvalOut
from app.ai.schemas import ReputationSynthesisOut
from app.models import EvaluationEvidence, Evidence, Job
from app.services.evaluation import evaluate_job
from app.services.evidence import RepostChainError, validate_repost_chain
from tests.conftest import JOB_PAYLOAD


@pytest.fixture()
def sample_job_with_evidence(client):
    """岗位 + 组织。"""
    job = client.post("/api/jobs", json=JOB_PAYLOAD).json()
    org_id = job["organization"]["id"]
    return job, org_id


def _evidence(client, org_id, **kwargs):
    base = {"claim": "启动经费到账偏慢", "category": "startup_funding_fulfillment",
            "evidence_level": "C", "source_type": "forum", "stance": "negative",
            "scope_level": "organization"}
    base.update(kwargs)
    resp = client.post(f"/api/evidence/organizations/{org_id}", json=base)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _job_evidence(client, job_id, **kwargs):
    base = {"claim": "岗位级证据", "category": "fact",
            "evidence_level": "A", "source_type": "official", "stance": "neutral",
            "scope_level": "job"}
    base.update(kwargs)
    resp = client.post(f"/api/evidence/jobs/{job_id}", json=base)
    assert resp.status_code == 201, resp.text
    return resp.json()


class _Provider(LLMProvider):
    """可复用的最小 Fake Provider（evaluation / reputation 按需启用）。"""

    name = "fake"
    model = "m"

    def __init__(self, evaluation_output=None, reputation_output=None):
        self.seen_contexts = []
        self.evaluation_output = evaluation_output
        self.reputation_output = reputation_output

    def evaluate_job(self, context: dict):
        self.seen_contexts.append(context)
        if self.evaluation_output is None:
            raise NotImplementedError
        return AIEvalOut.model_validate(self.evaluation_output), "job_evaluation_v1"

    def summarize_reputation(self, context: dict):
        self.seen_contexts.append(context)
        if self.reputation_output is None:
            raise NotImplementedError
        return ReputationSynthesisOut.model_validate(self.reputation_output), "reputation_summary_v2"

    def extract_job(self, jd_text):
        raise NotImplementedError


# ---------- Evidence CRUD ----------

def test_create_job_evidence_inherits_organization(client, sample_job_with_evidence):
    job, org_id = sample_job_with_evidence
    resp = client.post(
        f"/api/evidence/jobs/{job['id']}",
        json={"claim": "公告写明聘期六年", "category": "fact", "evidence_level": "A",
              "source_type": "official", "stance": "neutral"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["job_id"] == job["id"]
    assert data["organization_id"] == org_id  # 自动继承岗位所属单位


def test_job_evidence_cannot_forge_organization(client, sample_job_with_evidence):
    """岗位证据的 organization 恒为岗位所属单位，不接受伪造归属。"""
    job, org_id = sample_job_with_evidence
    resp = client.post(
        f"/api/evidence/jobs/{job['id']}",
        json={"claim": "伪造归属尝试", "organization_id": 999},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["organization_id"] == org_id
    assert data["organization_id"] != 999


def test_create_organization_evidence_and_list(client, sample_job_with_evidence):
    job, org_id = sample_job_with_evidence
    created = _evidence(client, org_id, independence_key="zhihu_user_a")
    listed = client.get(f"/api/evidence/organizations/{org_id}").json()
    assert all(item["job_id"] is None for item in listed)
    assert any(item["id"] == created["id"] for item in listed)


def test_patch_evidence_partial_update(client, sample_job_with_evidence):
    _, org_id = sample_job_with_evidence
    ev = _evidence(client, org_id)
    resp = client.patch(f"/api/evidence/{ev['id']}", json={"claim": "到账约 3-6 个月"})
    assert resp.status_code == 200
    assert resp.json()["claim"] == "到账约 3-6 个月"
    assert resp.json()["evidence_level"] == "C"  # 未提供则不变


def test_patch_evidence_not_nullable_explicit_null_422(client, sample_job_with_evidence):
    """Phase 6.1：claim/category/stance/scope_level/evidence_level 显式 null → 422。"""
    _, org_id = sample_job_with_evidence
    ev = _evidence(client, org_id)
    for field in ("claim", "category", "stance", "scope_level", "evidence_level"):
        resp = client.patch(f"/api/evidence/{ev['id']}", json={field: None})
        assert resp.status_code == 422, field
    # 可空字段显式 null 合法
    assert client.patch(
        f"/api/evidence/{ev['id']}", json={"raw_excerpt": None}
    ).status_code == 200


def test_evidence_extra_field_rejected(client, sample_job_with_evidence):
    _, org_id = sample_job_with_evidence
    resp = client.post(
        f"/api/evidence/organizations/{org_id}", json={"claim": "x", "bogus": 1}
    )
    assert resp.status_code == 422


# ---------- repost 链校验 ----------

def test_repost_chain_validation(client, sample_job_with_evidence, db_session):
    _, org_id = sample_job_with_evidence
    root = _evidence(client, org_id, independence_key="root_src")
    root_id = root["id"]

    # 自身转载 / 目标不存在 / 跨单位
    with pytest.raises(RepostChainError, match="自身"):
        validate_repost_chain(db_session, evidence_id=root_id, repost_of=root_id,
                              organization_id=org_id)
    with pytest.raises(RepostChainError, match="不存在"):
        validate_repost_chain(db_session, evidence_id=None, repost_of=999999,
                              organization_id=org_id)
    other_org = client.post("/api/organizations", json={"name": "另一所大学"}).json()["id"]
    with pytest.raises(RepostChainError, match="跨单位"):
        validate_repost_chain(db_session, evidence_id=None, repost_of=root_id,
                              organization_id=other_org)

    # 合法转载后形成循环：root → b → c，再把 root 的转载指向 c 构成环
    b = _evidence(client, org_id, repost_of_evidence_id=root_id)
    c = _evidence(client, org_id, repost_of_evidence_id=b["id"])
    with pytest.raises(RepostChainError):
        client.patch(f"/api/evidence/{root_id}", json={"repost_of_evidence_id": c["id"]})
    assert client.get(f"/api/evidence?organization_id={org_id}").json() is not None


# ---------- 确定性风评统计 ----------

def test_aggregate_counts_and_eligibility(client, sample_job_with_evidence):
    """独立来源去重、组级 stance 保守归类、等级、时间跨度与 eligibility。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="src_a", stance="negative", published_at="2024-03-01")
    _evidence(client, org_id, independence_key="src_a", stance="positive", published_at="2024-06-01")
    _evidence(client, org_id, independence_key="src_b", evidence_level="B", stance="negative",
              published_at="2026-01-15")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    topic = next(t for t in report["topics"] if t["topic"] == "startup_funding_fulfillment")
    assert topic["independent_sources"] == 2
    # 组级 stance：src_a 组内一负即负（保守），src_b 负 → 2 负 0 正
    assert topic["positive_sources"] == 0
    assert topic["negative_sources"] == 2
    assert set(topic["evidence_levels"]) >= {"B", "C"}
    assert topic["eligible_for_scoring"] is True
    assert topic["time_start"] == "2024-03-01"
    assert topic["time_end"] == "2026-01-15"


def test_single_source_topic_is_ineligible_clue_only(client, sample_job_with_evidence):
    """单条 C 级帖子是情报线索，不能自动变成定量风评分依据。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="lonely_src")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    topic = next(t for t in report["topics"] if t["topic"] == "startup_funding_fulfillment")
    assert topic["independent_sources"] == 1
    assert topic["eligible_for_scoring"] is False
    assert "仅作情报参考" in topic["eligible_reason"]


def test_two_independent_c_sources_still_ineligible(client, sample_job_with_evidence):
    """两个独立源但全是 C 级 → 仍不进入定量评分。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="c1")
    _evidence(client, org_id, independence_key="c2")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    topic = next(t for t in report["topics"] if t["topic"] == "startup_funding_fulfillment")
    assert topic["independent_sources"] == 2
    assert topic["eligible_for_scoring"] is False


def test_unknown_scope_downgraded_to_clue(client, sample_job_with_evidence):
    """Phase 6 核心策略：unknown scope 不能自动升级成全校通用证据。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, claim="不知道是学院还是学校的说法",
              scope_level="unknown", independence_key="unknown_1")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    assert all(t["independent_sources"] == 0 for t in report["topics"]) or report["topics"] == []
    assert any("仅作情报线索" in c["reason"] for c in report["clues"])
    assert report["overall_confidence"] == "low"


def test_repost_follows_source_across_topic_subset(client, sample_job_with_evidence, db_session):
    """Phase 6.1 P0-4：同一 root 的两个转载，即使 root 不在当前主题
    （root category=other），independent_sources 仍必须 = 1。"""
    from app.services.reputation import aggregate_topics, canonical_source_keys

    _, org_id = sample_job_with_evidence
    root = _evidence(client, org_id, claim="原帖（other 类）", category="other")
    root_id = root["id"]
    repost1 = _evidence(client, org_id, claim="转载一", repost_of_evidence_id=root_id)
    repost2 = _evidence(client, org_id, claim="转载二", repost_of_evidence_id=root_id)

    db_session.commit()
    canonical = canonical_source_keys(db_session, org_id)
    # root 无 key → root 自成 canonical；两个转载跟随 root
    assert canonical[repost1["id"]] == canonical[repost2["id"]] == f"evidence_{root_id}"

    rows = db_session.query(Evidence).filter(
        Evidence.id.in_([repost1["id"], repost2["id"]])
    ).all()
    topics = aggregate_topics(rows, canonical)  # 只喂 topic 子集（root 不在其中）
    topic = next(t for t in topics if t.topic == "startup_funding_fulfillment")
    assert topic.independent_sources == 1  # 不再被误拆成 2


def test_department_scope_semantics(client, sample_job_with_evidence):
    """Phase 6.1 P0-2：department=None 只统计 org scope；department=X 合并匹配院系。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, claim="校级证据", scope_level="organization",
              independence_key="org1", evidence_level="B")
    _evidence(client, org_id, claim="化学学院证据", scope_level="department",
              scope_name="化学学院", independence_key="chem1", evidence_level="B")
    _evidence(client, org_id, claim="医学院证据", scope_level="department",
              scope_name="医学院", independence_key="med1", evidence_level="B")

    # 不指定院系：只统计 org scope，两个院系证据都降为线索
    listed = client.get(f"/api/evidence?organization_id={org_id}").json()
    id_by_claim = {e["claim"]: e["id"] for e in listed}
    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    org_topic = next(
        t for t in report["topics"] if id_by_claim["校级证据"] in t["evidence_ids"]
    )
    assert id_by_claim["化学学院证据"] not in org_topic["evidence_ids"]
    assert id_by_claim["医学院证据"] not in org_topic["evidence_ids"]
    clues_reasons = [c["reason"] for c in report["clues"]]
    assert sum("未指定院系" in r for r in clues_reasons) == 2

    # 指定化学学院：校级 + 化学学院纳入，医学院线索
    report = client.get(
        f"/api/organizations/{org_id}/reputation", params={"department": "化学学院"}
    ).json()
    assert any("医学院" in c["claim"] for c in report["clues"])
    chem_topic = next(
        t for t in report["topics"] if id_by_claim["化学学院证据"] in t["evidence_ids"]
    )
    assert id_by_claim["医学院证据"] not in chem_topic["evidence_ids"]


# ---------- AI 主题综合 ----------

def test_synthesize_merges_ai_conclusions_with_deterministic_counts(
    client, sample_job_with_evidence, monkeypatch
):
    """AI 只写结论；来源数/等级/eligibility 等数字仍来自确定性统计；
    overall_confidence 由确定性规则唯一决定（AI 无置信度字段）。"""
    from app.api.deps import get_ai_provider

    _, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="src_a")
    _evidence(client, org_id, independence_key="src_b", evidence_level="B")

    deterministic = client.get(f"/api/organizations/{org_id}/reputation").json()
    assert deterministic["overall_confidence"] == "medium"  # 2 独立源含 B

    provider = _Provider(
        reputation_output={
            "topics": [
                {"topic": "startup_funding_fulfillment",
                 "conclusion": "统计显示启动经费到账偏慢的反馈较多，建议核实到账条款。"}
            ]
        }
    )
    client.app.dependency_overrides[get_ai_provider] = lambda: provider
    try:
        resp = client.post(f"/api/organizations/{org_id}/reputation/synthesize")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["synthesized_by_ai"] is True
        assert data["prompt_version"] == "reputation_summary_v2"
        assert data["overall_confidence"] == deterministic["overall_confidence"]
        topic = next(t for t in data["topics"] if t["topic"] == "startup_funding_fulfillment")
        assert topic["independent_sources"] == 2  # 数字来自统计层
        assert topic["ai_conclusion"].startswith("统计显示")
        assert provider.seen_contexts[0]["statistics"][0]["independent_sources"] == 2
    finally:
        client.app.dependency_overrides.pop(get_ai_provider, None)


def test_synthesize_requires_ai(client, sample_job_with_evidence):
    _, org_id = sample_job_with_evidence
    assert client.post(f"/api/organizations/{org_id}/reputation/synthesize").status_code == 503


def test_deterministic_report_never_calls_ai(client, sample_job_with_evidence):
    """GET 报告是纯确定性统计，不需要 AI 配置。"""
    _, org_id = sample_job_with_evidence
    _evidence(client, org_id)
    resp = client.get(f"/api/organizations/{org_id}/reputation")
    assert resp.status_code == 200
    assert resp.json()["synthesized_by_ai"] is False


# ---------- Evaluation 集成：eligibility 唯一权威 ----------

def test_single_c_org_evidence_does_not_unlock_reputation(
    client, sample_job_with_evidence, db_session
):
    """单条 C 组织级证据 → Reputation ineligible → Evaluation reputation=null。"""
    job, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="single_c")
    provider = _Provider(
        evaluation_output={
            "summary": "", "scores": {"fit": 80, "reputation": 85},
            "risk_level": "medium", "confidence": "medium",
        }
    )
    evaluation = evaluate_job(db_session, db_session.get(Job, job["id"]), provider)
    db_session.commit()
    assert provider.seen_contexts[0]["evidence"][0]["eligible_for_reputation_scoring"] is False
    assert evaluation.reputation_score is None


def test_job_level_fact_never_unlocks_reputation(client, sample_job_with_evidence, db_session):
    """job-level A 级官方事实（聘期六年）不能解锁"学校风评 70 分"。"""
    job, _ = sample_job_with_evidence
    _job_evidence(client, job["id"], claim="公告写明聘期六年")
    provider = _Provider(
        evaluation_output={
            "summary": "", "scores": {"fit": 80, "reputation": 70},
            "risk_level": "medium", "confidence": "high",
        }
    )
    evaluation = evaluate_job(db_session, db_session.get(Job, job["id"]), provider)
    db_session.commit()
    assert provider.seen_contexts[0]["evidence"][0]["eligible_for_reputation_scoring"] is False
    assert evaluation.reputation_score is None


def test_eligible_topic_evidence_allows_reputation_score(
    client, sample_job_with_evidence, db_session
):
    """B + C 两个独立源（组织级）→ eligible → Evaluation reputation 可保留。"""
    job, org_id = sample_job_with_evidence
    _evidence(client, org_id, independence_key="src_b", evidence_level="B")
    _evidence(client, org_id, independence_key="src_c")

    report = client.get(f"/api/organizations/{org_id}/reputation").json()
    topic = next(t for t in report["topics"] if t["topic"] == "startup_funding_fulfillment")
    assert topic["eligible_for_scoring"] is True

    provider = _Provider(
        evaluation_output={
            "summary": "", "scores": {"fit": 80, "reputation": 70},
            "risk_level": "low", "confidence": "high",
        }
    )
    evaluation = evaluate_job(db_session, db_session.get(Job, job["id"]), provider)
    db_session.commit()
    assert provider.seen_contexts[0]["evidence"][0]["eligible_for_reputation_scoring"] is True
    assert evaluation.reputation_score == 70


def test_cross_department_evidence_never_enters_evaluation(
    client, sample_job_with_evidence, db_session
):
    """化学学院岗位：医学院 Evidence 永不进入评估 context，也不解锁 reputation。"""
    job, org_id = sample_job_with_evidence
    _evidence(client, org_id, claim="医学院青年教师行政特别重",
              scope_level="department", scope_name="医学院", independence_key="med1")
    provider = _Provider(
        evaluation_output={
            "summary": "", "scores": {"fit": 80, "reputation": 60},
            "risk_level": "medium", "confidence": "medium",
        }
    )
    evaluation = evaluate_job(db_session, db_session.get(Job, job["id"]), provider)
    db_session.commit()
    # 评估 context 的作用域过滤（evidence_in_scope）已经排除不匹配院系
    assert provider.seen_contexts[0]["evidence"] == []
    assert evaluation.reputation_score is None


# ---------- Evidence 删除保护 ----------

def test_delete_used_evidence_rejected(client, sample_job_with_evidence, db_session):
    """Phase 6.1 P0-3：已参与评估的证据 DELETE → 409；EvaluationEvidence 保留。
    未参与评估的证据可正常删除。"""
    job, org_id = sample_job_with_evidence
    # 两条独立 B 级 → 主题 eligible → 评估后两条都被关联
    b1 = _evidence(client, org_id, independence_key="used_b1", evidence_level="B")
    b2 = _evidence(client, org_id, independence_key="used_b2", evidence_level="B")

    provider = _Provider(
        evaluation_output={
            "summary": "", "scores": {"fit": 80}, "risk_level": "medium",
            "confidence": "medium",
        }
    )
    evaluate_job(db_session, db_session.get(Job, job["id"]), provider)
    db_session.commit()
    # 评估之后创建的证据未参与任何评估 → 可删除
    unused = _evidence(client, org_id, independence_key="unused1")
    assert db_session.query(EvaluationEvidence).filter_by(evidence_id=b1["id"]).count() == 1
    assert db_session.query(EvaluationEvidence).filter_by(evidence_id=b2["id"]).count() == 1

    resp = client.delete(f"/api/evidence/{b1['id']}")
    assert resp.status_code == 409
    assert "审计" in resp.text
    # 关联保留（Phase 4 冻结不变量不被破坏）
    assert db_session.query(EvaluationEvidence).filter_by(evidence_id=b1["id"]).count() == 1
    assert db_session.get(Evidence, b1["id"]) is not None

    # 未参与评估的证据可删除
    assert client.delete(f"/api/evidence/{unused['id']}").status_code == 204
